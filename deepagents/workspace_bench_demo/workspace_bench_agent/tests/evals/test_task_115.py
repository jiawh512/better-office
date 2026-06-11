"""Eval case for workspace-bench task 115."""

from workspace_bench_agent.conftest import run_task_eval


def test_task_115():
    score, passed, total = run_task_eval("115")
    assert score >= 1.0
