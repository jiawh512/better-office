"""Judge Agent Core — evaluates a task directory against rubrics.

Responsibilities:
  1. Read metadata.json and output files from a task directory
  2. Run the Workspace-Bench native judge (LLM-as-a-judge)
  3. Return per-rubric pass/fail results + summary

Does NOT:
  - Invoke the agent (that's runner_agent's job)
  - Prepare workspaces
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

Json = Any
logger = logging.getLogger(__name__)

# Make workspace-bench evaluation/src importable
sys.path.insert(0, os.getenv("WB_EVAL_SRC", "/workspace/Workspace-Bench/evaluation/src"))
import agent_eval  # noqa: E402

from judge_agent.judge_model import judge_chat_completion  # noqa: E402

_original_chat_completions = agent_eval._chat_completions


def _chat_completions_langchain(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Json]],
    timeout_s: int = 120,
    max_retries: int = 10,
    total_timeout_s: float = 200.0,
) -> tuple[dict[str, Json] | None, dict[str, Json] | None, str]:
    """Drop-in replacement for agent_eval._chat_completions using LangChain."""
    logger.debug("[Judge LangChain] model=%s, msgs=%d", model, len(messages))
    return judge_chat_completion(
        messages=messages,
        model=model,
        api_key=api_key,
        base_url=base_url,
    )


def enable_langchain_judge() -> None:
    """Switch agent_eval to use LangChain-based judge LLM calls."""
    agent_eval._chat_completions = _chat_completions_langchain
    logger.info("LangChain judge enabled")


def disable_langchain_judge() -> None:
    """Restore original urllib-based judge LLM calls."""
    agent_eval._chat_completions = _original_chat_completions
    logger.info("Original urllib judge restored")


def run_judge(
    *,
    task_dir: Path,
    metadata: dict | None = None,
    output_files: list[str] | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    use_langchain_judge: bool = True,
) -> dict[str, Json]:
    """Run native workspace-bench judge on a task directory.

    Expects task_dir to contain:
      - metadata.json
      - agent.json (evaluation_sys format with trace)
      - output/ subdirectory with result files

    Args:
        task_dir: Path to the task work directory.
        metadata: Optional pre-loaded metadata dict. If None, reads from task_dir/metadata.json.
        output_files: Optional list of output file paths. If None, scans task_dir/output/.
        api_key: Judge API key. Defaults to JUDGE_API_KEY env var.
        base_url: Judge API base URL. Defaults to JUDGE_BASE_URL env var.
        model: Judge model name. Defaults to JUDGE_MODEL env var.
        use_langchain_judge: If True, replaces urllib with LangChain ChatOpenAI.

    Returns:
        Judge result dict with "rubrics" and "summary" keys.
    """
    api_key = api_key or os.environ.get("JUDGE_API_KEY")
    base_url = base_url or os.environ.get("JUDGE_BASE_URL", "https://api.deepseek.com")
    model = model or os.environ.get("JUDGE_MODEL", "deepseek-v4-pro")

    if not api_key:
        raise ValueError("JUDGE_API_KEY not provided")

    if metadata is None:
        meta_path = task_dir / "metadata.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"metadata.json not found in {task_dir}")
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))

    rubrics = metadata.get("rubrics", [])

    # Auto-discover output files if not provided
    if output_files is None:
        output_dir = task_dir / "output"
        if output_dir.exists():
            output_files = [str(f) for f in output_dir.iterdir() if f.is_file()]
        else:
            output_files = []

    # Ensure agent.json exists for native judge
    agent_json_path = task_dir / "agent.json"
    if not agent_json_path.exists():
        # Build minimal agent.json
        agent_json = {
            "trace": {
                "prompt": {"user": ""},
                "executionTrace": [],
                "outputs": {
                    "returnedPaths": [os.path.relpath(f, task_dir) for f in output_files],
                    "outputManifest": [
                        {
                            "sourcePath": os.path.basename(f),
                            "outputPath": os.path.basename(f),
                            "sizeBytes": os.path.getsize(f),
                        }
                        for f in output_files
                        if os.path.isfile(f)
                    ],
                },
            }
        }
        agent_json_path.write_text(json.dumps(agent_json, ensure_ascii=False, indent=2), encoding="utf-8")

    # Ensure output/ dir exists for native judge
    output_dir = task_dir / "output"
    output_dir.mkdir(exist_ok=True)
    for src in output_files:
        if os.path.isfile(src):
            dst = output_dir / os.path.basename(src)
            if not dst.exists():
                shutil.copy2(src, dst)

    # Patch agent_eval
    if use_langchain_judge:
        enable_langchain_judge()

    # Write eval config
    eval_yaml = task_dir / "eval_config.yaml"
    eval_yaml.write_text(
        f'model_name: "{model}"\n'
        f'baseUrl: "{base_url}"\n'
        f'model: "{model}"\n'
        f'apiKey: "{api_key}"\n',
        encoding="utf-8",
    )

    result = agent_eval.evaluate_task(
        task_dir=str(task_dir),
        eval_yaml_path=str(eval_yaml),
        overwrite=True,
        max_retries=3,
    )

    # Restore original judge
    if use_langchain_judge:
        disable_langchain_judge()

    if not (isinstance(result, dict) and result.get("success") is True):
        err = result.get("error") if isinstance(result, dict) else str(result)
        return {
            "rubrics": [
                {"rubric": r, "passed": False, "evidence": f"Judge evaluation failed: {err}"}
                for r in rubrics
            ],
            "summary": {"total": len(rubrics), "passed": 0, "failed": len(rubrics)},
            "_judge_error": err,
        }

    # Load rubrics result
    model_name = result.get("evalModel") or model or "unknown"
    rubrics_path = task_dir / f"rubrics_judge--{model_name}.json"
    if rubrics_path.exists():
        rubrics_result = json.loads(rubrics_path.read_text(encoding="utf-8"))
        if isinstance(rubrics_result, dict) and "rubrics" in rubrics_result:
            return rubrics_result

    return {
        "rubrics": [
            {"rubric": r, "passed": False, "evidence": "Native judge did not produce rubric output"}
            for r in rubrics
        ],
        "summary": {"total": len(rubrics), "passed": 0, "failed": len(rubrics)},
    }
