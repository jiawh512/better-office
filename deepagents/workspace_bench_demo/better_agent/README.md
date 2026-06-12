# Better Agent

The **Better Agent** is the outer-loop optimization agent provided by the [better-harness](https://github.com/langchain-ai/better-harness) framework.

## What It Does

Better Agent reads eval feedback (train failures, judge results) and automatically edits the harness surface files to improve scores on the next iteration.

## Where It Lives

Better Agent is **not** a local file in this directory. It is part of the `better-harness` Python package mounted at `/workspace/better-harness` inside the Docker container.

Key source files (in the mounted better-harness package):
- `better_harness/agent.py` — `propose_variant()`, builds proposer workspace and invokes outer Deep Agent
- `better_harness/core.py` — `run_experiment()`, the main optimization loop
- `better_harness/runners.py` — `PytestRunner`, executes test cases

## How It Works

```
1. Baseline eval → run all train + holdout cases
2. Better Agent reads train failures
3. Better Agent edits surface files under /current
4. Candidate eval → run train cases with new surfaces
5. Accept if combined score improves, else reject
6. Repeat up to max_iterations
```

## Surfaces (Editable Files)

Better Agent can edit these files:

| Surface | File | What It Controls |
|---------|------|-----------------|
| `prompt` | `runner_agent/prompt.txt` | System prompt for the inner agent |
| `middleware_registration` | `runner_agent/harness.py` | Agent harness setup (tools, backend, LLM) |
| `tools` | `runner_agent/tools.py` | Custom tools (parse_pdf, compute_hash) |

## Proposer Workspace

During each iteration, better-harness creates a proposer workspace at:
```
runs/<experiment>/history/visible/iterations/001/proposer_workspace/
```

Containing:
- `current/` — editable surface files
- `train_cases/` — visible train test files
- `train_failures.json` — failing case summaries
- `task.md` — instructions for Better Agent
- `proposal.md` — Better Agent's explanation of changes

## Configuration

See `../experiment.toml`:
```toml
[better_agent]
model = "openai:deepseek-v4-pro"
max_turns = 300
```
