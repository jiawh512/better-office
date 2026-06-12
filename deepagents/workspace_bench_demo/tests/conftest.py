"""Pytest fixtures and shared eval logic for workspace-bench tasks.

This is the GLUE layer between runner_agent, judge_agent, and better-harness.

Responsibilities:
  - pytest configuration (options, fixtures)
  - Orchestrate: runner_agent.run_single_task() → judge_agent.run_judge()
  - Compute score from judge result and write summary.json
"""

import json
import logging
import os
import shutil
import sys
from pathlib import Path

import pytest

# Ensure runner_agent and judge_agent are importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from judge_agent.judge import run_judge
from runner_agent.core import run_single_task, TASK_ROOT

logger = logging.getLogger(__name__)


def pytest_addoption(parser):
    """Register --evals-report-file option."""
    parser.addoption("--evals-report-file", action="store", default=None, help="Path to write eval score report")


def pytest_configure(config):
    """Capture --evals-report-file path so tests can write scores there."""
    report_file = config.getoption("--evals-report-file")
    if report_file:
        os.environ["PYTEST_EVAL_REPORT"] = report_file


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


def run_task_eval(task_id: str) -> tuple[float, int, int]:
    """Generic eval logic for any workspace-bench task.

    Returns:
        (score, passed_rubrics, total_rubrics)
    """
    report_file = os.environ.get("PYTEST_EVAL_REPORT")

    # 1. Run task via runner_agent
    try:
        output_files, agent_result = run_single_task(
            task_id,
            report_file=report_file,
        )
    except Exception:
        _write_score_report(0.0, 0, 0)
        raise

    # Determine work_dir (either from report_file parent or from the call)
    work_dir: Path | None = None
    if report_file:
        work_dir = Path(report_file).parent / "_work"
    if work_dir is None or not work_dir.exists():
        # Fallback: try to infer from output_files
        if output_files:
            work_dir = Path(output_files[0]).parent

    if work_dir is None or not work_dir.exists():
        _write_score_report(0.0, 0, 0)
        return 0.0, 0, 0

    # Load FULL metadata (including rubrics) from TASK_ROOT — NOT from work_dir.
    # Runner-agent's work_dir intentionally does NOT contain metadata.json,
    # so rubrics are physically hidden from the runner.
    meta_path = TASK_ROOT / task_id / "metadata.json"
    if not meta_path.exists():
        _write_score_report(0.0, 0, 0)
        return 0.0, 0, 0

    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    rubrics = metadata.get("rubrics", [])
    expected_outputs = metadata.get("output_files", [])

    # 2. No outputs → score 0
    if not output_files:
        _write_score_report(0.0, 0, len(rubrics))
        return 0.0, 0, len(rubrics)

    # 3. Write FULL metadata.json (with rubrics) to work_dir for judge to read.
    # Runner has already finished, so it cannot see this file.
    # This gives judge access to both the task description and rubrics.
    (work_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 4. Prepare output/ directory for judge
    output_dir = work_dir / "output"
    output_dir.mkdir(exist_ok=True)
    for src in output_files:
        if os.path.isfile(src):
            dst = output_dir / os.path.basename(src)
            if not dst.exists():
                shutil.copy2(src, dst)

    # Build minimal agent.json for native judge compatibility
    agent_json_path = work_dir / "agent.json"
    if not agent_json_path.exists():
        execution_trace = []
        if isinstance(agent_result, dict):
            for m in agent_result.get("messages", []):
                if isinstance(m, dict):
                    execution_trace.append({
                        "type": m.get("type"),
                        "role": "assistant" if m.get("type") == "ai" else "tool",
                        "content": m.get("content"),
                        "tool": m.get("name"),
                    })
        agent_json = {
            "trace": {
                "prompt": {"user": metadata.get("task", "")},
                "executionTrace": execution_trace,
                "outputs": {
                    "returnedPaths": [os.path.relpath(f, work_dir) for f in output_files],
                    "outputManifest": [
                        {
                            "sourcePath": os.path.basename(f),
                            "outputPath": os.path.basename(f),
                            "sizeBytes": os.path.getsize(f),
                        }
                        for f in output_files if os.path.isfile(f)
                    ],
                },
            }
        }
        agent_json_path.write_text(json.dumps(agent_json, ensure_ascii=False, indent=2), encoding="utf-8")

    # 5. Run judge via judge_agent
    try:
        judge_result = run_judge(
            task_dir=work_dir,
            metadata=metadata,
            output_files=output_files,
        )
    except Exception:
        _write_score_report(0.0, 0, len(rubrics))
        return 0.0, 0, len(rubrics)

    judged_rubrics = judge_result.get("rubrics", [])
    passed = sum(1 for r in judged_rubrics if r.get("passed"))
    total = len(rubrics)
    score = passed / total if total > 0 else 0.0

    # Save judge artifacts for debugging
    judge_artifacts_dir = work_dir / "judge_artifacts"
    judge_artifacts_dir.mkdir(exist_ok=True)
    for artifact_name in ["judge_result.json", "agent.json", "agent_result.json"]:
        src = work_dir / artifact_name
        if src.exists():
            shutil.copy2(src, judge_artifacts_dir / artifact_name)
    for rubrics_file in work_dir.glob("rubrics_judge--*.json"):
        shutil.copy2(rubrics_file, judge_artifacts_dir / rubrics_file.name)
    for dep_graph_file in work_dir.glob("dependency_graph--*.json"):
        shutil.copy2(dep_graph_file, judge_artifacts_dir / dep_graph_file.name)
    if output_dir.exists():
        case_output_dir = judge_artifacts_dir / "output"
        case_output_dir.mkdir(exist_ok=True)
        for f in output_dir.iterdir():
            if f.is_file():
                shutil.copy2(f, case_output_dir / f.name)

    # Also copy to better-harness case dir if report_file is set
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
            for rubrics_file in work_dir.glob("rubrics_judge--*.json"):
                shutil.copy2(rubrics_file, case_judge_dir / rubrics_file.name)
            for dep_graph_file in work_dir.glob("dependency_graph--*.json"):
                shutil.copy2(dep_graph_file, case_judge_dir / dep_graph_file.name)
            if output_dir.exists():
                case_output_dir = case_judge_dir / "output"
                case_output_dir.mkdir(exist_ok=True)
                for f in output_dir.iterdir():
                    if f.is_file():
                        shutil.copy2(f, case_output_dir / f.name)

    # 5. Write score report for better-harness
    _write_score_report(score, passed, total)

    return score, passed, total


@pytest.fixture
def agent():
    """Build the inner agent for workspace-bench tasks."""
    from runner_agent.harness import build_agent

    return build_agent()
