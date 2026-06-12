"""Judge Agent — evaluates runner-agent outputs against rubrics.

Input:  runner result data (output files + metadata)
Output: judge result (per-rubric pass/fail + summary)
"""

from judge_agent.judge import run_judge

__all__ = ["run_judge"]
