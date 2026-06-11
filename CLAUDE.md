# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a fusion monorepo combining **better-harness** (agent harness development) and **better-office** (workspace benchmarking). It contains two major sub-projects:

1. **Workspace-Bench** — A benchmark for evaluating AI agents on workspace tasks with large-scale file dependencies
2. **deepagents** — A LangChain/LangGraph-based agent harness with sub-agents, filesystem access, and terminal UI

## Workspace-Bench (`Workspace-Bench/`)

### Architecture

The benchmark evaluates agents in realistic workspaces where they must explore directories, locate relevant evidence, understand cross-file relations, and produce correct deliverables.

- **`evaluation/`** — Python-based evaluation harness
  - `src/agent_runner.py` — Main task execution runner; dispatches to different agent harnesses (codex, openclaw, deepagent, claudecode)
  - `src/agent_eval.py` — Offline evaluation: rubric judging (LLM-as-a-judge) and I/O dependency graph construction from tool call traces
  - `src/agent_as_a_judge.py` — Rubric scoring via ClaudeCode harness; requires an Anthropic-compatible judge endpoint
  - `src/filesys_utils.py` — Filesystem rollback and workspace preparation utilities
  - `scripts/` — Data download, run config generation, workdir preparation, and report assertion helpers
  - `docker/` — Docker Compose setup and benchmark execution scripts
  - `runs/` — YAML run configurations
  - `output/` — Task outputs, logs, and judge artifacts (generated at runtime)
- **`viz/`** — React + TypeScript + Vite dashboard for browsing runs and rubric judgments
  - Express API server (`api/`) that discovers results under `evaluation/output/`
  - Frontend uses Tailwind CSS, Zustand for state, Monaco Editor for file viewing
- **`docs/`** — MkDocs documentation site

### Common Commands

All benchmark execution happens inside Docker. The evaluation environment is a Node.js 24 + Python 3 image with Codex, OpenClaw, and uv pre-installed.

```bash
cd Workspace-Bench/evaluation

# Copy and fill API credentials
cp .env.example .env

# Download Lite dataset (100 tasks) and workspace files
python3 scripts/download_hf_assets.py --lite --workspaces

# Build and bootstrap Docker environment
docker compose -f docker/docker-compose.yaml build
docker compose -f docker/docker-compose.yaml run --rm workspace-bench \
  bash /workspace/Workspace-Bench/evaluation/docker/bootstrap.sh

# Run single smoke task
docker compose -f docker/docker-compose.yaml run --rm workspace-bench \
  bash /workspace/Workspace-Bench/evaluation/docker/run-benchmark.sh \
  --harness codex --model kimi-k2.5 --dataset smoke

# Run Lite benchmark (100 tasks)
docker compose -f docker/docker-compose.yaml run --rm workspace-bench \
  bash /workspace/Workspace-Bench/evaluation/docker/run-benchmark.sh \
  --harness codex --model kimi-k2.5 --dataset lite

# Judge results (single task)
docker compose -f docker/docker-compose.yaml run --rm workspace-bench \
  python3 -u /workspace/Workspace-Bench/evaluation/src/agent_as_a_judge.py \
  --task-dir /workspace/Workspace-Bench/evaluation/output/Codex--Kimi-K2.5--Smoke \
  --eval-yaml /workspace/Workspace-Bench/evaluation/runs/judge.yaml \
  --overwrite

# Judge results (parallel, Lite)
docker compose -f docker/docker-compose.yaml run --rm workspace-bench \
  python3 -u /workspace/Workspace-Bench/evaluation/src/agent_as_a_judge.py \
  --task-dir /workspace/Workspace-Bench/evaluation/output/Codex--Kimi-K2.5--Lite \
  --eval-yaml /workspace/Workspace-Bench/evaluation/runs/judge.yaml \
  --parallel --workers 3

# Verify smoke report
python3 scripts/assert_agent_runner_report.py \
  output/Codex--Kimi-K2.5--Smoke/agent_runner_report.json
```

**Viz dashboard (requires Node.js):**

```bash
cd Workspace-Bench/viz
npm install
npm run dev   # http://localhost:5173
```

Viz scripts:
- `npm run client:dev` — Vite dev server only
- `npm run server:dev` — Express API server only (with nodemon)
- `npm run dev` — Both client and server concurrently
- `npm run lint` — ESLint
- `npm run check` — TypeScript type check (no emit)
- `npm run test` — Node.js test runner with tsx

### Environment Variables

The `.env` file in `Workspace-Bench/evaluation/` provides API credentials for agent models and the judge. Key variables:

- `KIMIK25_BASE_URL`, `KIMIK25_API_KEY` — Default model for smoke runs
- `JUDGE_BASE_URL`, `JUDGE_MODEL`, `JUDGE_API_KEY` — Required for rubric judging
- `CODEX_CHAT_ADAPTER=auto` — Bridges non-GPT models from Responses API to Chat Completions

## deepagents (`deepagents/`)

### Architecture

A Python monorepo with multiple independently versioned packages under `libs/`:

- **`libs/deepagents/`** — Core SDK (`deepagents` on PyPI)
  - `deepagents/graph.py` — `create_deep_agent()`, the main entry point. Assembles a LangGraph agent with planning, filesystem, subagent, and summarization middleware.
  - `deepagents/middleware/` — Middleware modules: filesystem, subagents, async_subagents, summarization, memory, skills, patch_tool_calls
  - `deepagents/backends/` — Pluggable backends: local_shell, filesystem, sandbox, state, store, composite
  - `deepagents/profiles/` — Harness profiles for different model capabilities
  - Built on `langchain.agents.create_agent` with a custom `_DeepAgentState` using `DeltaChannel` on messages to reduce checkpoint growth from O(N²) to O(N)
- **`libs/code/`** — Terminal TUI (`deepagents-code` / `dcode` on PyPI)
  - Textual-based interactive REPL with file operations, shell access, and sub-agent capabilities
  - `deepagents_code/app.py` — Main TUI application (~400KB, contains the bulk of UI logic)
  - `deepagents_code/main.py` — CLI entry point and server lifecycle management
  - Runs a `langgraph dev` subprocess for each interactive session
- **`libs/cli/`** — Deployment CLI (`deepagents-cli` on PyPI)
  - `init`, `dev`, `deploy` subcommands for bundling and shipping agents to LangGraph Platform
- **`libs/evals/`** — Evaluation suite (`deepagents-evals` on PyPI)
  - Harbor integration for running benchmark evaluations
  - `deepagents_evals/cli.py` — Evaluation CLI
- **`libs/acp/`** — Agent Context Protocol support
- **`libs/partners/`** — Optional integration packages (daytona, modal, runloop, quickjs)

### Development Tools & Commands

Uses `uv` for package management, `make` for task running, `ruff` for lint/format, `ty` for static type checking.

```bash
cd deepagents/libs

# Run tests for a specific package
cd deepagents && make test
cd code && make test
cd cli && make test
cd evals && make test

# Run a specific test file
uv run --group test pytest tests/unit_tests/test_specific.py

# Lint and format (per-package Makefile delegates to ruff + ty)
make lint
make format

# Update all lockfiles
make lock

# Check lockfiles are up to date
make lock-check

# Build CLI frontend
make build-frontends
```

### Key Conventions

- **Python versions:** Most packages require `>=3.11,<4.0`. `acp` requires 3.14. `evals` requires `>=3.12,<3.14`.
- **Editable installs:** Local development uses `[tool.uv.sources]` for cross-package editable references.
- **Ruff:** Prefer inline `# noqa: RULE` over `per-file-ignores` for individual exceptions. Reserve `per-file-ignores` for categorical policy (e.g., `tests/**` relaxes docstring and annotation rules).
- **Commits:** Follow Conventional Commits with scope. All PR titles must include a scope.
- **Lazy imports:** Used extensively in CLI/code packages for startup performance.

### Deep Agents Code (TUI) Development

```bash
cd deepagents/libs/code
uv sync --group test

# Run with textual devtools (hot CSS reload)
# Terminal 1: uv run --group test textual console
# Terminal 2: uv run --group test textual run --dev /tmp/dev_deepagents.py
```

Debug environment variables:
- `DEEPAGENTS_CODE_DEBUG=1` — Preserves server subprocess log on shutdown
- `DEEPAGENTS_CODE_DEBUG_FILE=<path>` — Overrides default debug log path

When the TUI shows a startup failure banner, the real traceback is in a temp file matching `deepagents_server_log_*.txt` under `$TMPDIR` (macOS) or `/tmp` (Linux). Search for `Failed to initialize server graph`.

## Cross-Project Relationships

- `Workspace-Bench/deepagents/` is a vendored/copy of the deepagents package used by the benchmark's `deepagent` harness.
- The evaluation harness supports running `deepagents` as one of its agent backends alongside Codex, OpenClaw, and ClaudeCode.
- `viz/` reads the JSON output structure produced by `evaluation/src/agent_runner.py` and `evaluation/src/agent_as_a_judge.py`.
