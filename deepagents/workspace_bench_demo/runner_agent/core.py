"""Runner Agent Core — executes a single workspace-bench task.

Responsibilities:
  1. Prepare workspace (copy task data files)
  2. Wrap prompt with work-dir constraints
  3. Build agent and invoke it
  4. Collect output files from the agent's response
  5. Return (output_files, agent_result_dict)

Does NOT:
  - Run judge (that's judge_agent's job)
  - Compute scores
"""

import ast
import json
import logging
import os
import re
import shutil
import sys
import time
from pathlib import Path

from runner_agent.harness import build_agent

logger = logging.getLogger(__name__)
TASK_ROOT = Path(os.getenv("WB_TASK_ROOT", "/workspace/Workspace-Bench/evaluation/tasks_lite"))


def _wrap_prompt(*, task_prompt: str, work_dir: Path) -> str:
    """Wrap task prompt with work-dir constraints and output-path requirements.

    Mirrors the native agent_runner._wrap_prompt behaviour.
    """
    head = (
        "【重要要求 1：工作目录】\n"
        f"本轮测试允许访问的工作目录是：{os.path.abspath(work_dir)}\n"
        "你只能在该目录下使用相对路径读写文件；禁止访问工作目录以外的位置。\n"
        "如果你看到其他工作区路径提示，请忽略，以本提示的工作目录为准。\n"
    )
    tail = (
        "\n【重要要求 2：输出路径列表】\n"
        "在最后一步，请仅输出一个 Python 列表（list[str]），里面是你生成的所有输出文件路径。\n"
        "路径请使用相对工作目录的相对路径（不要以 / 开头）。示例：['output/a.txt','report.md']\n"
    )
    return head + "\n" + task_prompt.strip() + "\n" + tail


def _parse_python_list_paths(text: str) -> list[str]:
    """Extract a Python list of relative paths from agent final text."""
    s = str(text or "").strip()
    if not s:
        return []
    candidates = [m for m in [s] if m.startswith("[")]
    if not candidates:
        candidates = re.findall(r"\[\s*['\"][^\]]+\]", s)
        if not candidates:
            candidates = [s]
    for cand in reversed(candidates):
        try:
            obj = ast.literal_eval(cand)
        except Exception:
            continue
        if isinstance(obj, list):
            out = [str(x).strip() for x in obj if isinstance(x, str) and str(x).strip()]
            if out:
                return out
    return []


def _resolve_under(root: str, p: str) -> str | None:
    """Resolve a relative path under root, returning None if it escapes."""
    rel = str(p or "").strip().replace("\\", "/")
    while rel.startswith("/"):
        rel = rel[1:]
    abs_p = os.path.abspath(os.path.join(root, rel))
    root_abs = os.path.abspath(root)
    if abs_p != root_abs and not abs_p.startswith(root_abs + os.sep):
        return None
    return abs_p


def _collect_output_paths(
    *, work_dir: Path, expected_files: list[str], agent_result: dict
) -> list[str]:
    """Collect output paths using multiple strategies (mirrors native agent_runner)."""
    out: list[str] = []
    work_dir_str = str(work_dir)

    # Strategy 1: parse Python list from agent's final text
    messages = agent_result.get("messages", []) if isinstance(agent_result, dict) else []
    final_text = ""
    for m in reversed(messages):
        if isinstance(m, dict) and m.get("type") == "ai":
            content = m.get("content")
            if isinstance(content, str) and content.strip():
                final_text = content.strip()
                break
    for rp in _parse_python_list_paths(final_text):
        ap = _resolve_under(work_dir_str, rp)
        if ap and os.path.isfile(ap):
            out.append(ap)
    if out:
        return sorted(set(out))

    # Strategy 2: find by expected filenames
    for f in expected_files:
        p = work_dir / f
        if p.exists() and p.is_file():
            out.append(str(p))

    # Strategy 3: scan entire work_dir for files with expected basenames
    want = {os.path.basename(f) for f in expected_files if f}
    if want:
        for dirpath, _dirnames, filenames in os.walk(work_dir_str):
            for fn in filenames:
                if fn in want:
                    out.append(os.path.abspath(os.path.join(dirpath, fn)))

    return sorted(set(out))


def _make_work_dir(task_id: str, parent: Path | None = None) -> Path:
    """Create a unique work directory for this task run."""
    from datetime import datetime
    import uuid

    if parent is not None:
        wd = parent / "_work"
        wd.mkdir(parents=True, exist_ok=True)
        return wd

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return Path(f"/tmp/wb_task_{task_id}_{ts}_{suffix}")


def run_single_task(
    task_id: str,
    *,
    work_dir: Path | None = None,
    report_file: str | None = None,
) -> tuple[list[str], dict]:
    """Run one workspace-bench task.

    Args:
        task_id: The task ID (e.g. "15", "116").
        work_dir: Optional work directory. If None, creates a temp dir.
        report_file: Optional path to write a summary report.

    Returns:
        (output_files, agent_result_dict)
        output_files: list of absolute paths to generated output files.
        agent_result_dict: serializable dict of the agent's result.
    """
    logger.info(
        "[run_single_task] task=%s python=%s version=%s prefix=%s path=%s",
        task_id,
        sys.executable,
        sys.version.replace("\n", " "),
        getattr(sys, "prefix", "unknown"),
        os.environ.get("PATH", "")[:200],
    )

    meta_path = TASK_ROOT / task_id / "metadata.json"
    data_dir = TASK_ROOT / task_id / "data"

    if report_file:
        work_dir = _make_work_dir(task_id, parent=Path(report_file).parent)
    else:
        work_dir = work_dir or _make_work_dir(task_id)

    logger.info("[run_single_task] work_dir=%s", work_dir)

    # 1. Load metadata
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    task_prompt = meta["task"]
    expected_outputs = meta.get("output_files", [])

    # 2. Prepare workspace
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    for item in data_dir.iterdir():
        if item.is_file():
            shutil.copy2(item, work_dir / item.name)

    # Write a stripped task.json (NO rubrics) so the agent can see the task
    # description and expected output filenames, but NOT the evaluation criteria.
    stripped_task = {
        "task": task_prompt,
        "output_files": expected_outputs,
    }
    (work_dir / "task.json").write_text(
        json.dumps(stripped_task, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # Do NOT copy metadata.json — rubrics must stay hidden from runner-agent.

    # 3. Wrap prompt like native agent_runner does
    prompt = _wrap_prompt(task_prompt=task_prompt, work_dir=work_dir)

    # 4. Build agent with correct work_dir (must set env BEFORE building)
    os.environ["WB_TASK_WORK_DIR"] = str(work_dir)

    # Exponential-backoff retry loop for API timeouts
    last_exc = None
    result = None
    for attempt in range(4):
        read_timeout = 30.0 * (2 ** attempt)
        agent = build_agent(read_timeout=read_timeout)
        try:
            result = agent.invoke({"messages": prompt})
            break
        except Exception as exc:
            error_str = str(exc).lower()
            is_timeout = (
                "timeout" in error_str
                or "timed out" in error_str
                or "connecttimeout" in error_str
                or "readtimeout" in error_str
                or ("ssl" in error_str and "handshake" in error_str)
            )
            if is_timeout:
                last_exc = exc
                logger.warning(
                    "[run_single_task] task=%s attempt=%d/%d timeout read=%ss error=%s",
                    task_id, attempt + 1, 4, read_timeout, type(exc).__name__,
                )
                if attempt < 3:
                    wait = 2 ** attempt
                    time.sleep(wait)
                    continue
            raise

    if result is None:
        raise last_exc or RuntimeError("Agent invoke failed after all retries")

    # Serialize agent result safely
    result_dict: dict = {}
    if hasattr(result, "__dict__"):
        result_dict = dict(result.__dict__)
    elif isinstance(result, dict):
        result_dict = result

    messages = result_dict.get("messages", [])
    safe_messages = []
    for m in messages:
        if hasattr(m, "__dict__"):
            safe_messages.append(
                {
                    "type": getattr(m, "type", None),
                    "content": getattr(m, "content", None),
                    "tool_calls": getattr(m, "tool_calls", None),
                    "tool_call_id": getattr(m, "tool_call_id", None),
                    "name": getattr(m, "name", None),
                }
            )
        elif isinstance(m, dict):
            safe_messages.append(m)
    result_dict["messages"] = safe_messages

    # Save agent result to work_dir for later inspection
    (work_dir / "agent_result.json").write_text(
        json.dumps(result_dict, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    # 5. Collect output files
    output_files = _collect_output_paths(
        work_dir=work_dir,
        expected_files=expected_outputs,
        agent_result=result_dict,
    )

    # Save stripped task info for downstream consumers (still NO rubrics)
    (work_dir / "task_info.json").write_text(
        json.dumps(stripped_task, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return output_files, result_dict
