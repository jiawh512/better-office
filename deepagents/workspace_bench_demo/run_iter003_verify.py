#!/usr/bin/env python3
"""Run train baseline cases with iter-003 prompt and collect scores."""
import json
import os
import subprocess
import time
from pathlib import Path

TRAIN_CASES = [
    "tests/evals/test_task_15.py::test_task_15",
    "tests/evals/test_task_107.py::test_task_107",
    "tests/evals/test_task_116.py::test_task_116",
    "tests/evals/test_task_128.py::test_task_128",
    "tests/evals/test_task_139.py::test_task_139",
    "tests/evals/test_task_146.py::test_task_146",
]

OUTPUT_DIR = f"/workspace/workspace_bench_demo/runs/iter003-verify-{time.strftime('%Y%m%d%H%M%S')}"
os.makedirs(OUTPUT_DIR, exist_ok=True)

results = []

for case in TRAIN_CASES:
    case_id = case.replace("/", "_").replace("::", "__")
    case_dir = Path(OUTPUT_DIR) / case_id
    case_dir.mkdir(exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Running: {case}")
    print(f"{'='*60}")

    cmd = [
        "uv", "run", "--group", "test",
        "pytest", "-p", "better_harness_plugin",
        "--evals-report-file", str(case_dir / "summary.json"),
        "--junitxml", str(case_dir / "junit.xml"),
        "-q", "--tb=short", "-s",
        case,
    ]

    result = subprocess.run(cmd, cwd="/workspace/workspace_bench_demo/workspace_bench_agent", capture_output=True, text=True)
    print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
    if result.stderr:
        print(result.stderr[-500:] if len(result.stderr) > 500 else result.stderr)

    # Read summary
    summary_file = case_dir / "summary.json"
    if summary_file.exists():
        d = json.load(open(summary_file))
        passed = d.get("passed", "N/A")
        total = d.get("total", "N/A")
        correctness = d.get("correctness", "N/A")
        results.append((case_id, passed, total, correctness))
        print(f"RESULT: {passed}/{total} ({correctness})")
    else:
        results.append((case_id, "N/A", "N/A", "N/A"))
        print(f"RESULT: summary.json not found")

# Final report
print(f"\n{'='*60}")
print("FINAL REPORT")
print(f"{'='*60}")
for case_id, passed, total, correctness in results:
    short = case_id.replace("tests_evals_", "").replace("_py__", ": ")
    print(f"{short}: {passed}/{total} ({correctness})")

# Write report
report = {"cases": [{"case": c, "passed": p, "total": t, "correctness": cr} for c, p, t, cr in results]}
json.dump(report, open(Path(OUTPUT_DIR) / "report.json", "w"), indent=2)
print(f"\nReport saved to: {OUTPUT_DIR}/report.json")
