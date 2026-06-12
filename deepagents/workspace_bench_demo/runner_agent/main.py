"""Runner Agent CLI — batch execute workspace-bench tasks.

Usage:
    python -m runner_agent.main --task-id 15
    python -m runner_agent.main --task-id 15 --work-dir /tmp/task15
    python -m runner_agent.main --task-ids 15,116,128
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from runner_agent.core import run_single_task

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )


def run_one(task_id: str, work_dir: str | None = None) -> dict:
    """Run a single task and persist outputs."""
    wd = Path(work_dir) if work_dir else None
    output_files, agent_result = run_single_task(task_id, work_dir=wd)

    # Persist a simple manifest for downstream consumers
    manifest = {
        "task_id": task_id,
        "work_dir": str(work_dir or "n/a"),
        "output_files": output_files,
        "agent_message_count": len(agent_result.get("messages", [])),
    }
    if work_dir:
        manifest_path = Path(work_dir) / "runner_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        logger.info("Manifest written to %s", manifest_path)

    logger.info("Task %s finished. Outputs: %s", task_id, output_files)
    return manifest


def run_many(task_ids: list[str], base_dir: str | None = None) -> list[dict]:
    """Run multiple tasks sequentially."""
    results = []
    for task_id in task_ids:
        if base_dir:
            wd = str(Path(base_dir) / f"task_{task_id}")
        else:
            wd = None
        results.append(run_one(task_id, work_dir=wd))
    return results


def main(argv: list[str] | None = None) -> int:
    _setup_logging()
    parser = argparse.ArgumentParser(description="Runner Agent — execute workspace-bench tasks")
    parser.add_argument("--task-id", help="Single task ID to run")
    parser.add_argument("--task-ids", help="Comma-separated task IDs")
    parser.add_argument("--work-dir", help="Work directory override")
    parser.add_argument("--base-dir", help="Base directory for multiple tasks")
    parser.add_argument("--output", "-o", help="Path to write result manifest JSON")
    args = parser.parse_args(argv)

    if args.task_id:
        result = run_one(args.task_id, work_dir=args.work_dir)
    elif args.task_ids:
        ids = [t.strip() for t in args.task_ids.split(",")]
        result = run_many(ids, base_dir=args.base_dir)
    else:
        parser.error("Provide --task-id or --task-ids")
        return 1  # type: ignore[unreachable]

    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        print(args.output)
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
