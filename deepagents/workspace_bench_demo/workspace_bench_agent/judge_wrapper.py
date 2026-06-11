"""Workspace-bench native judge wrapper.

Calls agent_eval.evaluate_task() from the workspace-bench framework.

Monkey-patches agent_eval._chat_completions to use our LangChain judge model
instead of raw urllib, for better connection stability (timeout, retries, SSL).
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

# Import our LangChain judge wrapper
from workspace_bench_agent.judge_model import judge_chat_completion  # noqa: E402

# ═══════════════════════════════════════════════════════════════
# Monkey-patch: replace urllib-based _chat_completions with
# LangChain ChatOpenAI-based implementation.
# ═══════════════════════════════════════════════════════════════

_original_chat_completions = agent_eval._chat_completions


def _chat_completions_langchain(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Json]],
    timeout_s: int = 120,          # noqa: ARG001 — handled by judge_model build
    max_retries: int = 10,         # noqa: ARG001 — handled by judge_model build
    total_timeout_s: float = 200.0,  # noqa: ARG001 — handled by judge_model build
) -> tuple[dict[str, Json] | None, dict[str, Json] | None, str]:
    """Drop-in replacement for agent_eval._chat_completions using LangChain.

    Keeps the same signature so agent_eval internals don't need any changes.
    Timeout / retry logic is delegated to judge_model.build_judge_llm().
    """
    logger.debug(f"[Judge LangChain] model={model}, base_url={base_url}, msgs={len(messages)}")
    return judge_chat_completion(
        messages=messages,
        model=model,
        api_key=api_key,
        base_url=base_url,
    )


def enable_langchain_judge() -> None:
    """Switch agent_eval to use LangChain-based judge LLM calls."""
    agent_eval._chat_completions = _chat_completions_langchain
    logger.info("✅ LangChain judge enabled (agent_eval._chat_compositions patched)")


def disable_langchain_judge() -> None:
    """Restore original urllib-based judge LLM calls."""
    agent_eval._chat_completions = _original_chat_completions
    logger.info("⏪ Original urllib judge restored")


def run_judge(
    *,
    task_dir: Path,
    metadata: dict,
    output_files: list[str],
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    use_langchain_judge: bool = True,
) -> dict[str, Json]:
    """Run native workspace-bench judge on a task directory.

    Expects task_dir to contain:
    - metadata.json
    - agent.json (evaluation_sys format)
    - output/ subdirectory with result files

    Args:
        use_langchain_judge: If True (default), replaces urllib with LangChain
            ChatOpenAI for better connection stability.
    """
    api_key = api_key or os.environ.get("JUDGE_API_KEY")
    base_url = base_url or os.environ.get("JUDGE_BASE_URL", "https://api.deepseek.com")
    model = model or os.environ.get("JUDGE_MODEL", "deepseek-v4-pro")

    if not api_key:
        raise ValueError("JUDGE_API_KEY not provided")

    # Patch agent_eval to use LangChain judge if requested
    if use_langchain_judge:
        enable_langchain_judge()

    # Write a temporary eval YAML for the native judge
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

    # If native judge failed, fall back to a synthetic failure result
    if not (isinstance(result, dict) and result.get("success") is True):
        err = result.get("error") if isinstance(result, dict) else str(result)
        rubrics = metadata.get("rubrics", [])
        return {
            "rubrics": [
                {
                    "rubric": r,
                    "passed": False,
                    "evidence": f"Judge evaluation failed: {err}",
                }
                for r in rubrics
            ],
            "summary": {
                "total": len(rubrics),
                "passed": 0,
                "failed": len(rubrics),
            },
            "_judge_error": err,
        }

    # Load the rubrics result written by the native judge
    model_name = result.get("evalModel") or model or "unknown"
    rubrics_path = task_dir / f"rubrics_judge--{model_name}.json"
    if rubrics_path.exists():
        rubrics_result = json.loads(rubrics_path.read_text(encoding="utf-8"))
        if isinstance(rubrics_result, dict) and "rubrics" in rubrics_result:
            return rubrics_result

    # Fallback: derive from result dict if rubrics file missing
    rubrics = metadata.get("rubrics", [])
    return {
        "rubrics": [
            {"rubric": r, "passed": False, "evidence": "Native judge did not produce rubric output"}
            for r in rubrics
        ],
        "summary": {"total": len(rubrics), "passed": 0, "failed": len(rubrics)},
    }
