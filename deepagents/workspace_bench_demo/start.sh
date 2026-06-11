#!/bin/bash
# Start the better-harness optimization loop reliably.
# Usage: ./start.sh [output_dir_suffix]
# Example: ./start.sh hard04

set -euo pipefail

SUFFIX="${1:-$(date +%Y%m%d%H%M%S)}"
OUTPUT_DIR="runs/workspace-bench-10tasks-${SUFFIX}"
LOG_FILE="${OUTPUT_DIR}.log"

# ── 1. Ensure container is running ───────────────────────────────
echo "[1/5] Checking container status..."
if ! docker compose ps better-harness-wb 2>/dev/null | grep -q "Up"; then
    echo "  Container not running, starting..."
    docker compose up -d better-harness-wb
    sleep 3
fi

# ── 2. Clean up stale processes ──────────────────────────────────
echo "[2/5] Cleaning up stale processes..."
docker compose exec better-harness-wb bash -c '
for pid in /proc/[0-9]*; do
  [ -f "$pid/cmdline" ] || continue
  cmdline=$(cat "$pid/cmdline" 2>/dev/null | tr "\0" " ")
  if echo "$cmdline" | grep -qE "better_harness|pytest" && ! echo "$cmdline" | grep -q "grep"; then
    kill -9 "$(basename "$pid")" 2>/dev/null && echo "  Killed stale PID $(basename "$pid")"
  fi
done
' || true

# ── 3. Fix environment ───────────────────────────────────────────
echo "[3/5] Fixing environment..."
docker compose exec better-harness-wb bash -c \
    "rm -rf /workspace/libs/deepagents && mkdir -p /workspace/libs && ln -s /workspace/Workspace-Bench/deepagents/libs/deepagents /workspace/libs/deepagents"

docker compose exec better-harness-wb pip install --break-system-packages \
    httpx langchain-openai deepagents -e /workspace/Workspace-Bench/deepagents/libs/deepagents/ -q

# ── 4. Check for existing run ────────────────────────────────────
echo "[4/5] Checking output directory..."
if docker compose exec better-harness-wb test -d "/workspace/workspace_bench_demo/${OUTPUT_DIR}"; then
    echo "  WARNING: ${OUTPUT_DIR} already exists."
    read -r -p "  Delete and restart? [y/N] " confirm </dev/tty
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        docker compose exec better-harness-wb rm -rf "/workspace/workspace_bench_demo/${OUTPUT_DIR}"
        rm -f "${OUTPUT_DIR}.log" 2>/dev/null || true
        echo "  Old run removed."
    else
        echo "  Abort. Use a different suffix, e.g.: ./start.sh ${SUFFIX}2"
        exit 1
    fi
fi

# ── 5. Start optimization loop (detached) ────────────────────────
echo "[5/5] Starting optimization loop -> ${OUTPUT_DIR}..."
# Use 'docker compose exec -d' instead of 'setsid' for reliable background execution
docker compose exec -d better-harness-wb bash -c \
    "cd /workspace/workspace_bench_demo && python -m better_harness.core run experiment.toml --output-dir ${OUTPUT_DIR} > ${OUTPUT_DIR}.log 2>&1"

# ── 6. Verify startup ────────────────────────────────────────────
echo ""
echo "Waiting 5s to verify startup..."
sleep 5

RUNNING_PIDS=$(docker compose exec better-harness-wb bash -c '
count=0
for pid in /proc/[0-9]*; do
  [ -f "$pid/cmdline" ] || continue
  cmdline=$(cat "$pid/cmdline" 2>/dev/null | tr "\0" " ")
  if echo "$cmdline" | grep -q "better_harness.core" && ! echo "$cmdline" | grep -q "grep"; then
    count=$((count + 1))
  fi
done
echo "$count"
' 2>/dev/null) || RUNNING_PIDS="0"

if [ "$RUNNING_PIDS" -gt 0 ]; then
    echo "✅ Process is running (${RUNNING_PIDS} instance(s) found)"
else
    echo "⚠️  Process may have failed to start. Recent log:"
    docker compose exec better-harness-wb bash -c \
        "tail -n 20 /workspace/workspace_bench_demo/${OUTPUT_DIR}.log 2>/dev/null || echo '(no log yet)'"
    echo ""
    echo "Check full log with:"
    echo "  docker compose exec better-harness-wb tail -f /workspace/workspace_bench_demo/${OUTPUT_DIR}.log"
    exit 1
fi

echo ""
echo "========================================"
echo "Started: ${OUTPUT_DIR}"
echo "========================================"
echo ""
echo "Check progress:"
echo "  docker compose exec better-harness-wb tail -f /workspace/workspace_bench_demo/${OUTPUT_DIR}.log"
echo ""
echo "Check per-task status:"
echo "  docker compose exec better-harness-wb bash -c 'ls /workspace/workspace_bench_demo/${OUTPUT_DIR}/history/visible/train/baseline/cases/*/summary.json 2>/dev/null | wc -l'"
