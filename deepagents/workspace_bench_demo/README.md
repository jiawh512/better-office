# Better-Harness × Workspace-Bench Demo

This project is an **outer optimization loop** that uses [better-harness](https://github.com/langchain-ai/better-harness) to automatically improve an agent harness against [Workspace-Bench](https://github.com/ibm-research/workspace-bench) tasks.

It replaces the native Workspace-Bench runner with a custom harness built on [`deepagents`](https://github.com/jiawh512/deepagents), then runs an iterative optimization loop where the Better Agent edits the harness surface files to improve rubric scores.

---

## Architecture

The project is split into **three physically isolated agents**:

| Agent | Directory | Responsibility |
|-------|-----------|----------------|
| **Runner Agent** | `runner_agent/` | Executes a Workspace-Bench task. Only sees the task description and expected output filenames. Cannot see rubrics. |
| **Judge Agent** | `judge_agent/` | Scores the runner's outputs against the full rubrics. Sees both task and rubrics. |
| **Better Agent** | `better_agent/` (meta docs) | Edits the harness surfaces between iterations based on train failures. |

### Rubric Isolation

Workspace-Bench stores task description, output filenames, and rubrics in a single `metadata.json`. To prevent rubric leakage:

- `runner_agent/core.py` writes a **stripped** `task.json` (`task` + `output_files`) into the work directory.
- Full `metadata.json` is never copied into the work directory while the runner is running.
- After the runner finishes, `tests/conftest.py` writes the full `metadata.json` into the work directory for the judge.

This guarantees physical path-level isolation: the runner cannot access rubrics even if it tried to read every file in its work directory.

---

## Directory Structure

```
workspace_bench_demo/
├── runner_agent/              # Inner task-execution agent
│   ├── core.py               # Workspace prep, agent invoke, output collection
│   ├── harness.py            # Agent assembly (LLM, tools, backend)
│   ├── prompt.txt            # System prompt (editable surface)
│   ├── tools.py              # Custom tools (editable surface)
│   └── main.py               # Standalone CLI entry point
├── judge_agent/               # Rubric scoring agent
│   ├── judge.py              # Wraps Workspace-Bench evaluate_task()
│   ├── judge_model.py        # LangChain judge LLM setup
│   └── main.py               # Standalone CLI entry point
├── tests/                     # Pytest glue layer
│   ├── conftest.py           # Orchestrates runner → judge
│   └── evals/                # One pytest case per Workspace-Bench task
├── better_agent/              # Documentation for the outer-loop optimizer
│   └── README.md
├── scripts/                   # Auxiliary analysis/verification scripts
│   ├── compare_rubrics.py
│   ├── run_iter003_verify.py
│   └── ...
├── shared/                    # Shared utilities
├── experiment.toml            # Better-harness configuration
├── docker-compose.yaml        # Container definition
├── start.sh                   # One-command optimization loop launcher
└── run_baseline_multiple.py   # Baseline stability runner
```

---

## Quick Start

### 1. Start the container

```bash
cd deepagents/workspace_bench_demo
docker compose up -d better-harness-wb
```

### 2. Run a single task

```bash
docker compose exec better-harness-wb bash -c \
  "cd /workspace/workspace_bench_demo && uv run --group test pytest tests/evals/test_task_15.py -s"
```

### 3. Start the optimization loop

```bash
./start.sh <suffix>
```

Example:

```bash
./start.sh exp01
```

This creates:
- `runs/workspace-bench-10tasks-exp01/`
- `runs/workspace-bench-10tasks-exp01.log`

### 4. Watch logs

```bash
docker compose exec better-harness-wb tail -f \
  /workspace/workspace_bench_demo/runs/workspace-bench-10tasks-exp01.log
```

---

## Configuration

`experiment.toml` defines:

- `max_iterations` — number of optimization rounds
- `model` / `better_agent.model` — LLM used for runner and optimizer
- `surfaces` — files the Better Agent can edit
- `cases` — train/holdout task split

Current editable surfaces:

| Surface | File | Purpose |
|---------|------|---------|
| `prompt` | `runner_agent/prompt.txt` | Inner agent system prompt |
| `middleware_registration` | `runner_agent/harness.py` | Agent setup (tools, backend, LLM) |
| `tools` | `runner_agent/tools.py` | Custom tools (parse_pdf, compute_hash, etc.) |

---

## Manual Optimization Loop

If you prefer not to use `start.sh`, run the loop manually inside the container:

```bash
docker compose exec better-harness-wb bash
cd /workspace/workspace_bench_demo

# Fix environment
rm -rf /workspace/libs/deepagents
mkdir -p /workspace/libs
ln -s /workspace/Workspace-Bench/deepagents/libs/deepagents /workspace/libs/deepagents
pip install --break-system-packages \
  httpx langchain-openai deepagents \
  -e /workspace/Workspace-Bench/deepagents/libs/deepagents/ -q

# Run optimization loop
python -m better_harness.core run experiment.toml --output-dir runs/manual-01
```

---

## Notes

- The runner works exclusively within the `_work/` directory created under each case directory.
- Each case is scored by `tests/conftest.py` and writes a `summary.json` for better-harness to consume.
- Judge artifacts (rubric scores, dependency graphs, agent traces) are saved under each case's `judge_artifacts/` directory.
- See `better_agent/README.md` for details on the outer-loop optimizer.

---

## Related Repositories

- [`jiawh512/better-office`](https://github.com/jiawh512/better-office) — parent monorepo
- [`jiawen-2012/better-office`](https://github.com/jiawen-2012/better-office) — upstream fork
- [`jiawh512/deepagents`](https://github.com/jiawh512/deepagents) — deepagents SDK
