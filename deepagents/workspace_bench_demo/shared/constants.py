"""Shared constants across agents."""

import os
from pathlib import Path

TASK_ROOT = Path(os.getenv("WB_TASK_ROOT", "/workspace/Workspace-Bench/evaluation/tasks_lite"))
