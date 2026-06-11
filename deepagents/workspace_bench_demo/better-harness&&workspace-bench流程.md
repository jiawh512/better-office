# Better-Harness × Workspace-Bench 流程详解

> 本文档讲解 better-harness 框架、workspace-bench 评测集，以及当前项目的整体目标与架构。

---

## 1. Better-Harness 是什么

**Better-Harness** 是一个 Agent Harness（智能体 harness）的**自动优化框架**。

### 1.1 核心思想

传统的 Agent 调优依赖人工反复修改 prompt、调参数、跑评测。Better-Harness 把这套流程**自动化**：

1. **Baseline**：先跑一轮基准评测，得到当前 harness 的得分
2. **Better-Agent**：用一个"优化 Agent"分析 baseline 的失败案例，提出改进方案（修改 prompt、增加工具、调整参数等）
3. **迭代验证**：把改进方案应用到 harness 上，再跑一轮评测，验证是否提升
4. **循环**：重复 2-3 步，直到分数收敛或达到迭代上限

### 1.2 关键概念

| 术语 | 含义 |
|------|------|
| **Harness** | 包裹 LLM 的一层框架（prompt、工具、middleware、backend），决定 Agent 的行为方式 |
| **Baseline** | 优化前的初始评测结果 |
| **Better-Agent** | 负责提出 harness 改进方案的 LLM（通常是更强的模型，如 GPT-4 / Claude） |
| **Proposer** | 把 Better-Agent 的改进建议转换成可执行的代码/配置修改 |
| **Train / Holdout** | Train 集用于优化过程，Holdout 集用于最终验证泛化能力 |
| **Correctness** | 核心指标：passed / total，即通过评测的用例比例 |

### 1.3 一次完整实验流程

```
┌──────────────────────────────────────────────────────────────┐
│  Step 1: Baseline Eval                                       │
│  ─────────────────────                                       │
│  用当前 harness 跑所有评测任务，得到 correctness 分数          │
│  例如：train=0.333, holdout=0.0                              │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│  Step 2: Better-Agent Analysis                               │
│  ─────────────────────────────                               │
│  把 baseline 的失败案例、日志、错误信息喂给 Better-Agent       │
│  它分析后输出一份 "改进提案"（proposal.md）                    │
│  例如："增加文件探索步骤"、"收紧输出文件名约束"                │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│  Step 3: Proposer Apply                                      │
│  ─────────────────────                                       │
│  把提案转换成具体代码修改（如修改 graph.py 的 system_prompt）  │
│  生成新的 harness 变体（variant）                             │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│  Step 4: Iteration Eval                                      │
│  ─────────────────────                                       │
│  用新 harness 再跑一轮评测，对比 correctness 是否提升          │
│  如果提升 → 保留改进，进入下一轮                               │
│  如果下降 → 回滚，尝试其他方案                                 │
└──────────────────────────────┬───────────────────────────────┘
                               │
                    ┌──────────┘
                    │  循环 N 轮
                    └──────────►
```

---

## 2. Workspace-Bench 是什么

**Workspace-Bench** 是一个面向**工作区文件处理**的 Agent 评测基准测试集。

### 2.1 评测场景

每个任务给 Agent 一个包含各种文件的工作目录，要求 Agent 完成特定的文件处理任务：

- **文件整理**：按规则分类、重命名、移动文件
- **数据分析**：读取 CSV/Excel，计算统计量，生成报告
- **文档处理**：解析 PDF/Word，提取信息，生成 summary
- **去重与校验**：计算 hash、找出重复文件

### 2.2 评测方式（LLM-as-a-Judge）

Workspace-Bench 不依赖固定答案，而是使用 **Rubric（评分细则）+ Judge LLM** 来评分：

1. 每个任务有一份 `metadata.json`，里面定义了若干 rubric（评分标准）
2. Agent 执行完毕后，生成 `agent.json`（执行轨迹）和 `output/`（输出文件）
3. **Judge**（另一个 LLM，如 DeepSeek）读取执行轨迹和输出文件，逐条判断 rubric 是否满足
4. 最终输出每条 rubric 的 `passed: true/false`，汇总为 `correctness = passed / total`

### 2.3 Rubric 示例

```json
{
  "rubrics": [
    "output2.md 文件是否存在",
    "output2.md 中是否包含所有员工的姓名和邮箱",
    "output2.md 中的邮箱格式是否正确",
    "是否去除了重复记录"
  ]
}
```

Judge 会逐条检查，返回：
```json
{
  "rubrics": [
    {"rubric": "output2.md 文件是否存在", "passed": true, "evidence": "文件存在于工作目录"},
    {"rubric": "output2.md 中是否包含所有员工的姓名和邮箱", "passed": false, "evidence": "缺少员工张三的邮箱"}
  ],
  "summary": {"total": 4, "passed": 3, "failed": 1}
}
```

---

## 3. 当前项目在做什么

### 3.1 项目目标

**用 Better-Harness 自动优化一个面向 Workspace-Bench 的 Agent Harness，提升任务通过率。**

具体来说：
- **内层 Agent**：使用 `kimi-k2.6`（Moonshot API）执行 workspace-bench 的文件处理任务
- **外层 Better-Harness**：自动分析失败原因，提出并验证 harness 改进方案
- **Judge**：使用 `deepseek-chat` 对任务输出进行 rubric 评分

### 3.2 当前进展与关键突破

| 阶段 | 成果 |
|------|------|
| **连接稳定性** | 解决 Moonshot API 长连接断开问题（`streaming=True` + `httpx.Timeout(read=30)` + `max_retries=5`） |
| **task_100** | 首次通过（7/7），correctness=1.0 |
| **task_102** | 接近通过（score=0.875），需微调 |
| **task_115** | 出现退化（18/18 → 0/18），streaming 模式下输出格式变化导致 |
| **Holdout** | 目前全失败，泛化能力待提升 |
| **Judge 稳定性** | 已接入 LangChain ChatOpenAI 替代原生 urllib，解决 DeepSeek SSL 连接故障 |

### 3.3 关键文件说明

```
workspace_bench_demo/
├── experiment.toml              # Better-Harness 实验配置（模型、迭代次数等）
├── workspace_bench_agent/
│   ├── graph.py                 # ⭐ Agent 核心配置（LLM、Backend、Prompt、Tools）
│   ├── tools.py                 # 自定义工具（parse_pdf、compute_hash）
│   ├── conftest.py              # 评测入口（pytest fixture，调用 judge）
│   ├── judge_wrapper.py         # Judge 调用包装（原生 workspace-bench + LangChain 补丁）
│   └── judge_model.py           # Judge LLM 实例构建（类似 inner agent 的 ChatOpenAI）
├── tests/evals/                 # 5 个评测任务（task_100, 102, 115, 107, 108）
└── runs/                        # 实验结果目录
    └── workspace-bench-5tasks-.../
        ├── history/visible/train/baseline/      # Train 集 baseline 结果
        ├── history/private/holdout/baseline/    # Holdout 集 baseline 结果
        └── variants/baseline.json               # 配置快照
```

### 3.4 核心配置（解决 Connection 问题的关键）

```python
# workspace_bench_agent/graph.py
llm = ChatOpenAI(
    model="kimi-k2.6",
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://api.moonshot.cn/v1",
    timeout=httpx.Timeout(
        connect=5.0,
        read=30.0,      # 流式传输时，30秒内没收到新 token 就主动断开并重试
        write=10.0,
        pool=5.0,
    ),
    max_retries=5,      # 超时后最多重试 5 次
    streaming=True,     # 启用流式，让 read timeout 控制 token 间隔而非总时长
    extra_body={"thinking": {"type": "disabled"}},
)
```

**原理**：`streaming=True` 让 `httpx.Timeout.read` 控制**相邻 token 的间隔**（而非请求总时长）。30 秒覆盖正常生成间隔，超时后客户端主动断开并重试，避免挂到服务端被强制切断。

---

## 4. 架构图

### 4.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Better-Harness 外层优化循环                           │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │   Baseline      │───▶│  Better-Agent   │───▶│   Iteration     │         │
│  │   Eval (train)  │    │   Analysis      │    │   Eval (train)  │         │
│  │   + Holdout     │    │   + Proposal    │    │   + Holdout     │         │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘         │
│         ▲                                              │                    │
│         └──────────────────────────────────────────────┘                    │
│                              (循环 N 轮)                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Workspace-Bench Agent（内层执行）                        │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  LLM: ChatOpenAI (Moonshot API / kimi-k2.6)                         │   │
│  │  ├─ timeout: httpx.Timeout(read=30, connect=5, write=10, pool=5)    │   │
│  │  ├─ max_retries: 5                                                  │   │
│  │  ├─ streaming: True                                                 │   │
│  │  └─ extra_body: thinking disabled                                   │   │
│  │                                                                     │   │
│  │  Backend: LocalShellBackend                                         │   │
│  │  ├─ root_dir: WB_TASK_WORK_DIR                                      │   │
│  │  ├─ timeout: 60s                                                    │   │
│  │  └─ inherit_env: True                                               │   │
│  │                                                                     │   │
│  │  Tools: parse_pdf, compute_hash                                     │   │
│  │                                                                     │   │
│  │  System Prompt: 文件处理专家（含 3 轮工具调用限制、路径规则等）       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  输入: 工作目录（含待处理文件）                                              │
│  输出: agent.json（执行轨迹）+ output/（结果文件）                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Judge 评分系统                                      │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  原生 Workspace-Bench Rubric 评分逻辑（agent_eval.evaluate_task）    │   │
│  │  ├─ 读取 metadata.json（rubric 定义）                                │   │
│  │  ├─ 读取 agent.json（执行轨迹）                                      │   │
│  │  ├─ 读取 output/ 文件内容                                            │   │
│  │  └─ 逐条 rubric 判断 passed / failed                                 │   │
│  │                                                                     │   │
│  │  底层 LLM 调用（已 Monkey-Patch）                                    │   │
│  │  ├─ 原: urllib.request（裸 HTTP，SSL 不稳定）                        │   │
│  │  └─ 现: LangChain ChatOpenAI（timeout + retry + 连接池）            │   │
│  │                                                                     │   │
│  │  Judge 模型配置:                                                     │   │
│  │  ├─ model: deepseek-chat                                             │   │
│  │  ├─ base_url: https://api.deepseek.com                               │   │
│  │  ├─ temperature: 0（确定性评分）                                     │   │
│  │  └─ streaming: False                                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  输出: rubrics_judge--{model}.json（每条 rubric 评分结果）                  │
│  指标: correctness = passed / total                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 数据流向

```
Experiment Config (experiment.toml)
         │
         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Train Tasks   │────▶│  Agent Harness  │────▶│   Agent Output  │
│  (task_100/102  │     │  (graph.py)     │     │ (agent.json +   │
│   /115)         │     │                 │     │  output/)       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                              ┌─────────────────────────┘
                              ▼
                    ┌─────────────────┐
                    │  Judge Wrapper  │
                    │(judge_wrapper.py│
                    │ + judge_model.py)│
                    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Rubric Scoring │
                    │(agent_eval.py)  │
                    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Correctness    │
                    │  Score          │
                    └─────────────────┘
```

### 4.3 关键配置映射

```
Better-Harness Experiment
├── inner_model   ────────▶  graph.py  LLM (kimi-k2.6)
├── judge_model   ────────▶  judge_model.py LLM (deepseek-chat)
├── train_cases   ────────▶  tests/evals/test_task_{100,102,115}.py
├── holdout_cases ────────▶  tests/evals/test_task_{107,108}.py
└── max_iterations────────▶  实验循环次数
```

---

## 5. 下一步计划

| 优先级 | 事项 | 目标 |
|--------|------|------|
| P0 | 修复 task_115 退化 | streaming 模式下输出格式兼容 |
| P0 | 提升 task_108 | 解决 ReadTimeout（调大 read=60s 或优化 prompt） |
| P1 | 提升 task_102 | score=0.875 → 1.0 |
| P1 | 启动 Better-Harness 迭代 | 让 Better-Agent 自动提出改进方案 |
| P2 | 提升 Holdout 泛化 | holdout correctness > 0 |
