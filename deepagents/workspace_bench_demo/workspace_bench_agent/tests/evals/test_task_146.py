"""Eval case for workspace-bench task 146."""

from workspace_bench_agent.conftest import run_task_eval


def test_task_146():
    score, passed, total = run_task_eval("146")
    # Score is recorded in summary.json for better-harness.
    # We assert >= 0 so the test always passes; acceptance is decided by score.
    assert score >= 1.0
