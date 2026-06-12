"""Eval case for workspace-bench task 107."""

from tests.conftest import run_task_eval


def test_task_107():
    score, passed, total = run_task_eval("107")
    assert score >= 1.0
