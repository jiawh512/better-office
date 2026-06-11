# Better-Harness Surface 优化流程详解

## 一、整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Better-Harness 优化循环                             │
│                                                                             │
│   ┌──────────────┐      ┌──────────────┐      ┌──────────────┐             │
│   │  Experiment  │─────▶│   Baseline   │─────▶│  Iteration   │             │
│   │   Config     │      │    Eval      │      │   Loop       │             │
│   └──────────────┘      └──────────────┘      └──────┬───────┘             │
│                                                      │                      │
│   ┌──────────────────────────────────────────────────┘                      │
│   │                                                                         │
│   ▼                                                                         │
│   ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐     │
│   │  Build Proposer  │───▶│  Better Agent    │───▶│  Candidate Eval  │     │
│   │    Workspace     │    │  (Outer Agent)   │    │  (Train+Holdout) │     │
│   └──────────────────┘    └──────────────────┘    └──────────────────┘     │
│                                                         │                   │
│                              ┌──────────────────────────┘                   │
│                              ▼                                              │
│                        ┌─────────────┐                                      │
│                        │   Accept?   │── Yes ──▶ Update current variant     │
│                        │  Score ↑ ?  │── No  ──▶ Keep current variant       │
│                        └─────────────┘                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 二、核心概念

### 2.1 Surface（可编辑表面）

Surface 是 Better-Harness 可以自动修改的 Agent 组件，定义在 `experiment.toml` 的 `[surfaces.*]` 段。

| 类型 | 说明 | 示例 | 应用方式 |
|------|------|------|----------|
| `module_attr` | 模块属性 | `workspace_bench_agent.graph:BASE_PROMPT` | 运行时通过 `sitecustomize.py` + `setattr` 动态替换 |
| `workspace_file` | 工作区文件 | `graph.py`, `tools.py` | 通过临时文件覆盖，测试完恢复 |

### 2.2 Variant（版本）

一个 Variant 是所有 Surface 当前值的快照：
- **baseline**：初始版本，从 `base_file` / `base_value` 读取
- **iter-001, iter-002...**：Better Agent 每轮生成的候选版本
- **changed_surfaces**：记录本轮修改了哪些 Surface

### 2.3 Split（数据集划分）

| Split | 用途 | Better Agent 是否可见 |
|-------|------|----------------------|
| **train** | 训练集，用于优化 | ✅ 可见（反馈给 Better Agent） |
| **holdout** | 测试集，验证泛化 | ❌ 不可见（仅用于评分） |
| **scorecard** | 最终评分（可选） | ❌ 不可见 |

## 三、优化循环详细流程

### Phase 1: 初始化（Initialization）

```python
# 1. 加载配置
experiment = load_experiment("experiment.toml")

# 2. 构建 Baseline Variant
baseline = build_baseline_variant(experiment)
# 读取所有 surfaces 的 base_value，组成初始版本

# 3. 运行 Baseline 评估
baseline_train  = runner.run_split(variant=baseline, split="train")
baseline_holdout = runner.run_split(variant=baseline, split="holdout")
# 逐个 case 运行 pytest，收集 junit.xml + summary.json

# 4. 初始化当前最佳版本
current = baseline
current_train = baseline_train
current_holdout = baseline_holdout
```

**运行细节**：
- 每个 case 独立运行一次 pytest
- 通过 `workspace_override_context` 临时替换 workspace_file 类型的 surface
- 通过 `sitecustomize.py` + `BETTER_HARNESS_VARIANT_FILE` env var 注入 module_attr
- 从 `summary.json` 读取 judge 的 `correctness` 分数（覆盖 pytest 本身的 pass/fail）

---

### Phase 2: 迭代优化（Iteration Loop）

最多运行 `max_iterations` 轮（配置中 ours=3）。

#### Step 2.1: 构建 Proposer Workspace

为 Better Agent 准备一个独立的工作目录，包含：

```
proposer-workspace-{iteration}/
├── current/                    # 当前 surface 文件（可编辑）
│   ├── prompt.txt             # BASE_PROMPT 内容
│   ├── graph.py               # graph.py 内容
│   └── tools.py               # tools.py 内容
├── surface_manifest.json      # surface 映射说明
├── task.md                    # 任务描述（给 Better Agent 的指令）
├── proposal.md                # 提案模板（Better Agent 填写）
├── train_cases/               # 失败的训练用例详情
│   ├── {case_id}/
│   │   ├── stdout.log
││   ├── stderr.log
│   │   └── summary.json
├── history/                   # 历史迭代结果（仅 visible splits）
│   ├── iter-001/
│   ├── iter-002/
│   ...
└── result.json                # 本轮最终结果
```

**task.md 核心内容**：
- 当前 variant 名称和 train 分数
- 可编辑 surfaces 列表
- **Visible train failures**（失败的 case 列表 + 错误信息）
- 编辑规则（只能改 `current/` 下的文件）

#### Step 2.2: Better Agent 分析并修改

Better Agent 是一个独立的 Deep Agent，接收以下输入：

1. **System Prompt**：定义角色为"外层优化 Agent"，规则包括：
   - 优先通用修复，不要针对特定 case hack
   - 不要过拟合到可见样本
   - 编辑的是实际 harness surface，不是笔记
   - 修改工具/中间件时，同时更新实现和注册

2. **Human Message**：
   ```
   "Read /task.md first. Then inspect the current surface files, 
    visible history, and failing train cases, edit only /current, 
    and finish by updating /proposal.md."
   ```

3. **可访问文件**：
   - `task.md` — 任务说明
   - `surface_manifest.json` — surface 映射
   - `current/*` — 当前 surface 值（可编辑）
   - `train_cases/*` — 失败用例的日志和分数
   - `history/*` — 历史迭代结果

**Better Agent 的工作**：
1. 读取 task.md 了解当前失败情况
2. 查看失败的 train case 日志，定位问题
3. 查看 history 避免重复尝试已失败的修改
4. 编辑 `current/` 下的 surface 文件（如修改 prompt、添加工具等）
5. 在 `proposal.md` 中写明修改理由

#### Step 2.3: 构建 Candidate Variant

```python
# 从 workspace 读取修改后的 surface 值
values = load_candidate_values(current=current, workspace=workspace)

# 对比找出哪些 surface 被修改了
changed_surfaces = [name for name in surfaces if values[name] != current.values[name]]

# 构建候选版本
candidate = build_variant(label="iter-{iteration:03d}", values=values)
```

#### Step 2.4: 评估 Candidate

```python
train = runner.run_split(variant=candidate, split="train")
holdout = runner.run_split(variant=candidate, split="holdout")
```

每个 case 重新运行 pytest，使用 candidate 的 surface 值。

#### Step 2.5: 决策（Accept / Reject）

```python
if score_mode == "sum":
    current_score = sum(train.scores) + sum(holdout.scores)
    candidate_score = sum(new_train.scores) + sum(new_holdout.scores)
else:
    current_score = train.passed + holdout.passed
    candidate_score = new_train.passed + new_holdout.passed

accepted = candidate_score > current_score
```

- **Accept**（分数提升）：`current = candidate`，下一轮基于此优化
- **Reject**（分数未提升）：保持当前版本，下一轮继续尝试

**注意**：即使 reject，本轮结果也会记录到 history 中，Better Agent 可以看到。

---

### Phase 3: 结束与报告

循环结束条件（满足任一即停止）：
1. 达到 `max_iterations` 上限
2. 所有 train + holdout case 全部通过
3. Better Agent 本轮没有修改任何 surface（`changed_surfaces` 为空）

最终生成 `RunReport`：
- baseline vs final 的 train/holdout 分数对比
- 每轮 iteration 的决策记录
- 可选的 scorecard 结果

## 四、Surface 修改机制详解

### 4.1 module_attr 类型（如 BASE_PROMPT）

```python
# 1. Better Agent 编辑 current/prompt.txt
# 2. 保存到 variant JSON 文件

# 3. 运行时注入流程：
#    a. ensure_sitecustomize() 创建 sitecustomize.py
#    b. pytest 启动时加载 sitecustomize.py
#    c. sitecustomize.py 读取 BETTER_HARNESS_VARIANT_FILE env var
#    d. 调用 patch_from_env() -> patch_module_attrs()
#    e. importlib.import_module(module_name) + setattr(module, attr, value)
```

### 4.2 workspace_file 类型（如 graph.py, tools.py）

```python
# 1. Better Agent 编辑 current/graph.py
# 2. 保存到 variant JSON 文件

# 3. 运行时注入流程：
#    a. workspace_override_context(experiment.workspace_root, variant.file_overrides())
#    b. 备份原文件内容
#    c. 用 variant 的值覆盖原文件
#    d. 运行 pytest
#    e. 测试结束后恢复备份
```

## 五、关键文件说明

| 文件 | 作用 |
|------|------|
| `experiment.toml` | 实验配置：surfaces、cases、model、max_iterations |
| `better_harness/core.py` | 核心数据模型、run_experiment 主循环 |
| `better_harness/agent.py` | Better Agent 调用、workspace 构建、task.md 生成 |
| `better_harness/patching.py` | Variant 构建、module_attr patch、文件覆盖 |
| `better_harness/runners.py` | PytestRunner：逐个 case 运行 pytest，解析结果 |
| `workspace_bench_agent/graph.py` | Inner Agent 定义（被 surface 修改） |
| `workspace_bench_agent/tools.py` | Inner Agent 工具（被 surface 修改） |
| `workspace_bench_agent/conftest.py` | pytest fixtures，连接 agent + judge |

## 六、当前实验配置

```toml
[experiment]
name = "workspace-bench-5tasks"
runner = "pytest"
model = "openai:kimi-k2.6"
max_iterations = 3
score_mode = "sum"

[better_agent]
model = "openai:kimi-k2.6"
max_turns = 300

[surfaces.prompt]           # module_attr: BASE_PROMPT
[surfaces.middleware_registration]  # workspace_file: graph.py
[surfaces.tools]            # workspace_file: tools.py

[[cases]]  # train: task_100, task_102, task_115
[[cases]]  # holdout: task_107, task_108
```

**优化方向示例**（基于历史失败）：
- Prompt 层面：添加文件类型处理说明、路径规则、效率约束
- Tools 层面：添加 PDF 解析、hash 计算等专用工具
- Graph 层面：调整 LLM 参数（timeout、retries、streaming）

## 七、调优建议

1. **Surfaces 粒度**：不要把所有逻辑放在一个文件里，拆分为独立的 surface 便于 Better Agent 精准修改
2. **Base Value**：提供高质量的初始 prompt/代码，减少迭代次数
3. **Score Mode**：`sum` 适合 rubric 评分（0~1 连续值），`pass_count` 适合二元通过/失败
4. **Max Iterations**：根据 surfaces 数量和 case 复杂度调整，一般 3~5 轮
5. **Train/Holdout 比例**：建议 60/40 或更多 train case，确保有足够反馈给 Better Agent
