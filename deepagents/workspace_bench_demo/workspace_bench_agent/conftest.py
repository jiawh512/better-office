"""Pytest fixtures and shared eval logic for workspace-bench tasks."""

import ast
import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path

import pytest

# Ensure workspace_bench_agent is importable when pytest runs from uv run --project
sys.path.insert(0, str(Path(__file__).resolve().parent))

from workspace_bench_agent.graph import build_agent
from workspace_bench_agent.judge_wrapper import run_judge

logger = logging.getLogger(__name__)
TASK_ROOT = Path(os.getenv("WB_TASK_ROOT", "/workspace/Workspace-Bench/evaluation/tasks_lite"))


def pytest_addoption(parser):
    """Register --evals-report-file option."""
    parser.addoption("--evals-report-file", action="store", default=None, help="Path to write eval score report")


def pytest_configure(config):
    """Capture --evals-report-file path so tests can write scores there."""
    report_file = config.getoption("--evals-report-file")
    if report_file:
        os.environ["PYTEST_EVAL_REPORT"] = report_file


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
    # Prefer the last bracketed Python list in the text
    candidates = [m for m in [s] if m.startswith("[")]
    if not candidates:
        # Try to find any bracketed list
        import re
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


def _collect_output_paths(*, work_dir: Path, expected_files: list[str], agent_result: dict) -> list[str]:
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


def _make_work_dir(task_id: str) -> Path:
    """Create a unique work directory for this eval run.

    If PYTEST_EVAL_REPORT is set (better-harness mode), place the work dir
    alongside the report file so artifacts are preserved with the case.
    Otherwise fall back to a timestamped directory under /tmp.
    """
    report_file = os.environ.get("PYTEST_EVAL_REPORT")
    if report_file:
        case_dir = Path(report_file).parent
        if case_dir.exists():
            wd = case_dir / "_work"
            wd.mkdir(parents=True, exist_ok=True)
            return wd
    # Fallback: timestamped + random suffix to avoid collisions
    from datetime import datetime
    import uuid

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return Path(f"/tmp/wb_task_{task_id}_{ts}_{suffix}")


def run_task_eval(task_id: str) -> tuple[float, int, int]:
    """Generic eval logic for any workspace-bench task.

    Returns:
        (score, passed_rubrics, total_rubrics)
    """
    # ── Log Python environment for debugging version mismatches ──
    logger.info(
        "[run_task_eval] task=%s  python=%s  version=%s  prefix=%s  path=%s",
        task_id,
        sys.executable,
        sys.version.replace("\n", " "),
        getattr(sys, "prefix", "unknown"),
        os.environ.get("PATH", "")[:200],
    )

    meta_path = TASK_ROOT / task_id / "metadata.json"
    data_dir = TASK_ROOT / task_id / "data"
    work_dir = _make_work_dir(task_id)
    logger.info("[run_task_eval] work_dir=%s", work_dir)

    # 1. Load metadata
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    task_prompt = meta["task"]
    expected_outputs = meta.get("output_files", [])
    rubrics = meta.get("rubrics", [])

    # 2. Prepare workspace
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    for item in data_dir.iterdir():
        if item.is_file():
            shutil.copy2(item, work_dir / item.name)
    # Copy metadata.json for native judge compatibility
    shutil.copy2(meta_path, work_dir / "metadata.json")

    # 3. Wrap prompt like native agent_runner does
    prompt = _wrap_prompt(task_prompt=task_prompt, work_dir=work_dir)

    # 4. Build agent with correct work_dir (must set env BEFORE building)
    os.environ["WB_TASK_WORK_DIR"] = str(work_dir)
    from workspace_bench_agent.graph import build_agent

    # ── Exponential-backoff retry loop for API timeouts ──
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
                or "ssl" in error_str and "handshake" in error_str
            )
            if is_timeout:
                last_exc = exc
                logger.warning(
                    "[run_task_eval] task=%s attempt=%d/%d timeout read=%ss error=%s",
                    task_id, attempt + 1, 4, read_timeout, type(exc).__name__,
                )
                if attempt < 3:
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    time.sleep(wait)
                    continue
            # Non-timeout error or final attempt exhausted — write score 0 and raise
            _write_score_report(0.0, 0, len(rubrics))
            raise

    if result is None:
        # All retries exhausted on timeout
        _write_score_report(0.0, 0, len(rubrics))
        raise last_exc or RuntimeError("Agent invoke failed after all retries")

    # Log agent result for debugging
    try:
        result_dict: dict = {}
        if hasattr(result, "__dict__"):
            result_dict = dict(result.__dict__)
        elif isinstance(result, dict):
            result_dict = result
        # Also try to serialize messages safely
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
        (work_dir / "agent_result.json").write_text(
            json.dumps(result_dict, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    except Exception:
        pass

    # 5. Collect output files (multi-strategy, mirrors native agent_runner)
    output_files = _collect_output_paths(
        work_dir=work_dir,
        expected_files=expected_outputs,
        agent_result=result_dict if "result_dict" in dir() else {},
    )

    # 5.5 Prepare native judge directory structure
    # Native judge expects:
    #   task_dir/metadata.json  (already there)
    #   task_dir/output/        (copy output files here)
    #   task_dir/agent.json     (evaluation_sys format with trace)
    output_dir = work_dir / "output"
    output_dir.mkdir(exist_ok=True)
    for src in output_files:
        if os.path.isfile(src):
            dst = output_dir / os.path.basename(src)
            shutil.copy2(src, dst)

    # Build a minimal agent.json in evaluation_sys format for the native judge
    execution_trace = []
    if isinstance(result_dict, dict):
        for m in result_dict.get("messages", []):
            if isinstance(m, dict):
                execution_trace.append({
                    "type": m.get("type"),
                    "role": "assistant" if m.get("type") == "ai" else "tool",
                    "content": m.get("content"),
                    "tool": m.get("name"),
                })
    agent_json = {
        "trace": {
            "prompt": {"user": prompt},
            "executionTrace": execution_trace,
            "outputs": {
                "returnedPaths": [os.path.relpath(f, work_dir) for f in output_files],
                "outputManifest": [
                    {"sourcePath": os.path.basename(f), "outputPath": os.path.basename(f), "sizeBytes": os.path.getsize(f)}
                    for f in output_files if os.path.isfile(f)
                ],
            },
        }
    }
    (work_dir / "agent.json").write_text(json.dumps(agent_json, ensure_ascii=False, indent=2), encoding="utf-8")

    # 6. Run judge (no outputs → score 0)
    if not output_files or not rubrics:
        _write_score_report(0.0, 0, len(rubrics))
        return 0.0, 0, len(rubrics)

    try:
        judge_result = run_judge(
            task_dir=work_dir,
            metadata=meta,
            output_files=output_files,
        )
    except Exception:
        # Judge failed — fall back to file-existence heuristic
        _write_score_report(0.0, 0, len(rubrics))
        return 0.0, 0, len(rubrics)

    judged_rubrics = judge_result.get("rubrics", [])
    passed = sum(1 for r in judged_rubrics if r.get("passed"))
    total = len(rubrics)
    score = passed / total if total > 0 else 0.0

    # Save judge result for debugging
    (work_dir / "judge_result.json").write_text(
        json.dumps(judge_result, ensure_ascii=False, indent=2)
    )

    # 7. Copy judge artifacts to better-harness case directory (if available)
    report_file = os.environ.get("PYTEST_EVAL_REPORT")
    if report_file:
        case_dir = Path(report_file).parent
        if case_dir.exists():
            case_judge_dir = case_dir / "judge_artifacts"
            case_judge_dir.mkdir(exist_ok=True)
            for artifact in [
                work_dir / "judge_result.json",
                work_dir / "agent.json",
                work_dir / "agent_result.json",
            ]:
                if artifact.exists():
                    shutil.copy2(artifact, case_judge_dir / artifact.name)
            # Also copy native judge rubrics file
            for rubrics_file in work_dir.glob("rubrics_judge--*.json"):
                shutil.copy2(rubrics_file, case_judge_dir / rubrics_file.name)
            for dep_graph_file in work_dir.glob("dependency_graph--*.json"):
                shutil.copy2(dep_graph_file, case_judge_dir / dep_graph_file.name)
            # Copy output files
            if (work_dir / "output").exists():
                case_output_dir = case_judge_dir / "output"
                case_output_dir.mkdir(exist_ok=True)
                for f in (work_dir / "output").iterdir():
                    if f.is_file():
                        shutil.copy2(f, case_output_dir / f.name)

    # 8. Write score report for better-harness
    _write_score_report(score, passed, total)

    return score, passed, total


def _write_score_report(score: float, passed: int, total: int) -> None:
    """Write summary.json so better-harness can read the partial score."""
    report_file = os.environ.get("PYTEST_EVAL_REPORT")
    if not report_file:
        return
    summary = {
        "passed": passed,
        "total": total,
        "correctness": score,
    }
    Path(report_file).write_text(json.dumps(summary, indent=2) + "\n")


@pytest.fixture
def agent():
    """Build the inner agent for workspace-bench tasks."""
    return build_agent()
