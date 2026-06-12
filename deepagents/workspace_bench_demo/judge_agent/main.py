"""Judge Agent CLI — evaluate runner-agent outputs.

Usage:
    python -m judge_agent.main --task-dir /path/to/task/_work
    python -m judge_agent.main --task-dir /path/to/task/_work --output judge_result.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from judge_agent.judge import run_judge

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    _setup_logging()
    parser = argparse.ArgumentParser(description="Judge Agent — evaluate task outputs")
    parser.add_argument("--task-dir", required=True, help="Path to task work directory")
    parser.add_argument("--output", "-o", help="Path to write judge result JSON")
    parser.add_argument("--model", help="Judge model override")
    args = parser.parse_args(argv)

    task_dir = Path(args.task_dir)
    if not task_dir.exists():
        print(f"Error: task-dir does not exist: {task_dir}", file=sys.stderr)
        return 1

    kwargs = {}
    if args.model:
        kwargs["model"] = args.model

    result = run_judge(task_dir=task_dir, **kwargs)

    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        print(args.output)
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
