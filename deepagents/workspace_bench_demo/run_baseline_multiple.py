"""Run baseline eval multiple times to check score stability."""

from __future__ import annotations

import json
import os
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add better-harness to path
BETTER_HARNESS_ROOT = Path(os.getenv("BETTER_HARNESS_ROOT", "/workspace/better-harness"))
sys.path.insert(0, str(BETTER_HARNESS_ROOT))

from better_harness.core import RunLayout  # noqa: E402
from better_harness.patching import build_baseline_variant  # noqa: E402
from better_harness.runners import build_runner  # noqa: E402
from better_harness.core import load_experiment  # noqa: E402


def run_baseline_round(
    experiment: Experiment,
    output_dir: Path,
) -> dict:
    """Run one round of baseline train + holdout eval."""
    runner = build_runner(experiment)
    layout = RunLayout(output_dir.resolve())
    layout.write_manifest(experiment)

    baseline = build_baseline_variant(experiment)

    train = runner.run_split(
        experiment=experiment,
        variant=baseline,
        split="train",
        layout=layout,
        reuse_existing=False,
    )
    holdout = runner.run_split(
        experiment=experiment,
        variant=baseline,
        split="holdout",
        layout=layout,
        reuse_existing=False,
    )

    return {
        "train": {
            "correctness": train.correctness,
            "passed": train.passed,
            "total": train.total,
            "scores": {o.case_id: o.score for o in train.outcomes},
        },
        "holdout": {
            "correctness": holdout.correctness,
            "passed": holdout.passed,
            "total": holdout.total,
            "scores": {o.case_id: o.score for o in holdout.outcomes},
        },
    }


def main() -> None:
    """Run baseline multiple times and print statistics."""
    config_path = Path(__file__).parent / "experiment.toml"
    experiment = load_experiment(config_path)

    n_runs = 3  # Number of baseline runs
    results: list[dict] = []

    print(f"Running baseline eval {n_runs} times...")
    print(f"Model: {experiment.model}")
    print(f"Train cases: {len([c for c in experiment.cases if c.split == 'train'])}")
    print(f"Holdout cases: {len([c for c in experiment.cases if c.split == 'holdout'])}")
    print()

    for i in range(1, n_runs + 1):
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_dir = Path(__file__).parent / "runs" / f"baseline-run-{i}-{timestamp}"
        print(f"Run {i}/{n_runs} -> {output_dir.name}")

        result = run_baseline_round(experiment, output_dir)
        results.append(result)

        train_scores = result["train"]["scores"]
        holdout_scores = result["holdout"]["scores"]
        print(f"  Train: correctness={result['train']['correctness']:.3f}, scores={train_scores}")
        print(f"  Holdout: correctness={result['holdout']['correctness']:.3f}, scores={holdout_scores}")
        print()

    # Summary statistics
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    train_correctness = [r["train"]["correctness"] for r in results]
    holdout_correctness = [r["holdout"]["correctness"] for r in results]

    print(f"\nTrain correctness: {train_correctness}")
    print(f"  mean={statistics.mean(train_correctness):.3f}, stdev={statistics.stdev(train_correctness):.4f}")
    print(f"  min={min(train_correctness):.3f}, max={max(train_correctness):.3f}")

    print(f"\nHoldout correctness: {holdout_correctness}")
    print(f"  mean={statistics.mean(holdout_correctness):.3f}, stdev={statistics.stdev(holdout_correctness):.4f}")
    print(f"  min={min(holdout_correctness):.3f}, max={max(holdout_correctness):.3f}")

    # Per-task stats
    all_case_ids = set()
    for r in results:
        all_case_ids.update(r["train"]["scores"].keys())
        all_case_ids.update(r["holdout"]["scores"].keys())

    print("\nPer-task scores:")
    for case_id in sorted(all_case_ids):
        scores = []
        for r in results:
            s = r["train"]["scores"].get(case_id) or r["holdout"]["scores"].get(case_id)
            if s is not None:
                scores.append(s)
        if scores:
            mean = statistics.mean(scores)
            stdev = statistics.stdev(scores) if len(scores) > 1 else 0.0
            print(f"  {case_id}: scores={scores}, mean={mean:.3f}, stdev={stdev:.4f}")

    # Save raw results
    output_file = Path(__file__).parent / "runs" / f"baseline-stability-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(results, indent=2) + "\n")
    print(f"\nRaw results saved to: {output_file}")


if __name__ == "__main__":
    main()
