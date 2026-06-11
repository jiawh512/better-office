#!/usr/bin/env python3
"""Compare rubric-level scores between baseline and iter-003."""
import json, glob

base_baseline = "/workspace/workspace_bench_demo/runs/workspace-bench-10tasks-hard0605-3/history/visible/train/baseline/cases"
base_iter = "/workspace/workspace_bench_demo/runs/iter003-verify-20260608025856"

cases = ["15", "107", "116", "128", "139", "146"]

for case in cases:
    # Baseline
    baseline_files = glob.glob(f"{base_baseline}/*test-task-{case}*/judge_artifacts/judge_result.json")
    iter_files = glob.glob(f"{base_iter}/*task_{case}*/judge_artifacts/judge_result.json")

    if not baseline_files or not iter_files:
        print(f"\n=== TASK {case} ===")
        print(f"  Baseline file: {baseline_files}")
        print(f"  Iter file: {iter_files}")
        continue

    baseline_data = json.load(open(baseline_files[0]))
    iter_data = json.load(open(iter_files[0]))

    baseline_rubrics = baseline_data.get("rubrics", [])
    iter_rubrics = iter_data.get("rubrics", [])

    print(f"\n{'='*80}")
    print(f"TASK {case} — Baseline: {baseline_data.get('summary',{}).get('passed','?')}/{baseline_data.get('summary',{}).get('total','?')} | Iter-003: {iter_data.get('summary',{}).get('passed','?')}/{iter_data.get('summary',{}).get('total','?')}")
    print(f"{'='*80}")

    max_len = min(len(baseline_rubrics), len(iter_rubrics))
    for i in range(max_len):
        b_r = baseline_rubrics[i]
        i_r = iter_rubrics[i]
        b_pass = b_r.get("passed", False)
        i_pass = i_r.get("passed", False)
        rubric_text = b_r.get("rubric", "")[:60]

        if b_pass and i_pass:
            status = "✅✅ PASS (both)"
        elif not b_pass and not i_pass:
            status = "❌❌ FAIL (both)"
        elif b_pass and not i_pass:
            status = "✅❌ REGRESSION (baseline pass, iter fail)"
        else:
            status = "❌✅ IMPROVED (baseline fail, iter pass)"

        print(f"  [{i}] {status}")
        print(f"      Rubric: {rubric_text}...")
        if b_pass != i_pass:
            print(f"      Baseline evidence: {b_r.get('evidence', 'N/A')[:100]}")
            print(f"      Iter-003 evidence: {i_r.get('evidence', 'N/A')[:100]}")
