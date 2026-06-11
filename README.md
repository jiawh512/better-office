# better-office

better-harness 与 Workspace-Bench 的融合开发项目。通过 Better-Harness 外层优化框架，自动优化 Workspace-Bench 评测任务中的 Agent Harness，提升 Agent 在文件组织/分析类任务上的正确率。

---

## 项目结构

```
better-office/
├── Workspace-Bench/          # Workspace-Bench 评测框架
│   ├── evaluation/           # 评测执行环境（Docker + Python）
│   │   ├── src/              # agent_runner.py / agent_eval.py / agent_as_a_judge.py
│   │   ├── docker/           # Docker Compose 配置
│   │   └── scripts/          # 数据下载、配置生成工具
│   └── viz/                  # 评测结果可视化面板（React + Vite）
├──
│   ├── libs/deepagents/      # 核心 SDK（LangGraph agent 框架）
│   ├── libs/code/            # 终端 TUI（deepagents-code / dcode）
│   ├── examples/better-harness/  # better-harness 优化框架
│   ├── my_agent_demo/        # Agent 示例项目
│   └── workspace_bench_demo/ # Workspace-Bench × Better-Harness 集成演示
└── README.md
```

---

## Better-Harness 使用指南

### 1. 环境准备

**依赖：**
- Docker
- Python 3
- API 密钥（DeepSeek / Moonshot / OpenAI）

**配置 API 密钥：**

```bash
cd deepagents/workspace_bench_demo
cp .env.example .env
# 编辑 .env，填入你的 API 密钥
```

`.env` 示例：
```bash
OPENAI_API_KEY=sk-xxx
OPENAI_API_BASE=https://api.deepseek.com

JUDGE_API_KEY=sk-xxx
JUDGE_BASE_URL=https://api.deepseek.com
JUDGE_MODEL=deepseek-v4-pro
```

### 2. 启动容器

```bash
cd deepagents/workspace_bench_demo
docker compose up -d better-harness-wb
```

容器会自动挂载：
- `/Users/zxc/workspace-bench/Workspace-Bench` → `/workspace/Workspace-Bench`
- `/Users/zxc/deepagents/deepagents/examples/better-harness` → `/workspace/better-harness`
- 当前目录 → `/workspace/workspace_bench_demo`

### 3. 运行基线评估

基线评估用于检查 Agent 在初始状态下的表现：

```bash
docker compose exec better-harness-wb bash -c \
  "cd /workspace/workspace_bench_demo && python run_baseline_multiple.py"
```

输出示例：
```
Running baseline eval 3 times...
Model: openai:deepseek-v4-pro
Train cases: 6
Holdout cases: 4

Run 1/3 -> baseline-run-1-20240611T033155Z
  Train: correctness=0.312, scores={...}
  Holdout: correctness=0.000, scores={...}
```

### 4. 启动优化循环

优化循环会自动迭代改进 Agent 的 prompt、tools 和 graph：

```bash
./start.sh [后缀]
# 例如：
./start.sh hard04
```

`start.sh` 会执行：
1. 检查并启动 Docker 容器
2. 清理残留进程
3. 设置环境（软链接 deepagents、安装依赖）
4. 启动优化循环：`better_harness.core run experiment.toml --output-dir ...`

**查看进度：**
```bash
docker compose exec better-harness-wb tail -f \
  /workspace/workspace_bench_demo/runs/workspace-bench-10tasks-*/workspace-bench-10tasks-*.log
```

**查看已完成任务数：**
```bash
docker compose exec better-harness-wb bash -c \
  "ls /workspace/workspace_bench_demo/runs/.../history/visible/train/baseline/cases/*/summary.json | wc -l"
```

### 5. 实验配置

`experiment.toml` 核心字段：

```toml
[experiment]
name = "workspace-bench-10tasks-hard"
runner = "pytest"
workspace_root = "./workspace_bench_agent"
model = "openai:deepseek-v4-pro"
max_iterations = 3          # 优化迭代次数
score_mode = "sum"          # 评分模式：count 或 sum

[better_agent]
model = "openai:deepseek-v4-pro"
max_turns = 300

# 可编辑表面（Surfaces）—— Better Agent 会自动修改这些文件
[surfaces.prompt]
kind = "module_attr"
target = "workspace_bench_agent.graph:BASE_PROMPT"

[surfaces.middleware_registration]
kind = "workspace_file"
target = "graph.py"

[surfaces.tools]
kind = "workspace_file"
target = "tools.py"
```

### 6. 核心概念

| 概念 | 说明 |
|------|------|
| **Surface** | Better-Harness 可以自动修改的 Agent 组件（prompt、graph.py、tools.py） |
| **Baseline** | 初始版本评估 |
| **Train** | 训练集（6 个任务），Better Agent 可见 |
| **Holdout** | 测试集（4 个任务），Better Agent 不可见，用于验证泛化 |
| **Variant** | 每个 Surface 值的快照（baseline → iter-001 → iter-002...） |
| **Correctness** | 评分 = passed / total |

---

## Workspace-Bench 评测

### 快速开始

```bash
cd Workspace-Bench/evaluation

# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API 密钥

# 2. 下载数据集
python3 scripts/download_hf_assets.py --lite --workspaces

# 3. 构建 Docker 环境
docker compose -f docker/docker-compose.yaml build

# 4. 运行单任务 smoke 测试
docker compose -f docker/docker-compose.yaml run --rm workspace-bench \
  bash /workspace/Workspace-Bench/evaluation/docker/run-benchmark.sh \
  --harness codex --model kimi-k2.5 --dataset smoke

# 5. 运行完整 Lite 评测（100 任务）
docker compose -f docker/docker-compose.yaml run --rm workspace-bench \
  bash /workspace/Workspace-Bench/evaluation/docker/run-benchmark.sh \
  --harness codex --model kimi-k2.5 --dataset lite
```

### 结果查看

```bash
# 启动可视化面板
cd Workspace-Bench/viz
npm install
npm run dev   # http://localhost:5173
```

---

## 开发指南

### 常用命令

```bash
# 提交前清理运行时产物
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type d -name .pytest_cache -exec rm -rf {} +
rm -rf runs/ tmp/ .venv/

# 推送到两个仓库
git push origin main
git push blue main
```

---

## 参考文档

- `deepagents/workspace_bench_demo/BETTER_HARNESS_OPTIMIZATION_FLOW.md` — 优化流程详解
- `deepagents/workspace_bench_demo/PROJECT_REPORT.md` — 项目技术汇报
- `Workspace-Bench/README.md` — Workspace-Bench 完整文档
