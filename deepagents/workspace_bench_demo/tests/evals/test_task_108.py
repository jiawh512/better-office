"""Eval case for workspace-bench task 108."""

from tests.conftest import run_task_eval


def test_task_108():
    score, passed, total = run_task_eval("108")
    assert score >= 1.0
