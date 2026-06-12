"""Runner Agent — executes workspace-bench tasks.

Input:  task_id + raw documents from Workspace-Bench tasks_lite/
Output: result data (output_files + agent_result dict)
"""

from runner_agent.core import run_single_task
from runner_agent.harness import build_agent

__all__ = ["run_single_task", "build_agent"]
