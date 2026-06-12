"""Eval case for workspace-bench task 102."""

from tests.conftest import run_task_eval


def test_task_102():
    score, passed, total = run_task_eval("102")
    assert score >= 1.0
