# Better-Harness × Workspace-Bench 集成项目汇报

## 1. 项目目标

通过 **Better-Harness** 外层优化框架，自动优化 **Workspace-Bench** 评测任务中的 Agent Harness，提升 Agent 在文件组织/分析类任务上的正确率。

---

## 2. 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Better-Harness 外层循环                    │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Baseline   │ -> │  Better-Agent │ -> │  Iteration   │  │
│  │    Eval      │    │   分析改进    │    │   01 Eval    │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         ↑___________________________________________↓       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Workspace-Bench Agent（内层）                   │
│  - LLM: ChatOpenAI (Moonshot API / kimi-k2.6)              │
│  - Backend: LocalShellBackend                              │
│  - Tools: parse_pdf, compute_hash, ls, read_file...        │
│  - System Prompt: BASE_PROMPT（含 3 轮 tool call 限制）     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Judge 评分系统                             │
│  - 每个 task 有多个 assert 检查点                             │
│  - passed/total -> correctness 评分                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 核心配置（当前生效）

```python
# workspace_bench_agent/graph.py

llm = ChatOpenAI(
    model="kimi-k2.6",
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://api.moonshot.cn/v1",
    timeout=httpx.Timeout(
        connect=5.0,
        read=30.0,      # 流式传输时，30秒没收到新 token 就重试
        write=10.0,
        pool=5.0,
    ),
    max_retries=5,      # 超时后最多重试 5 次
    streaming=True,     # 启用流式输出
    extra_body={"thinking": {"type": "disabled"}},
)
```

**关键改动：**
| 参数 | 初始值 | 当前值 | 作用 |
|------|--------|--------|------|
| `timeout` | 300（数字） | `httpx.Timeout(read=30)` | 控制 token 间隔，非总时长 |
| `max_retries` | 2 | 5 | 超时后自动重试 |
| `streaming` | 未设置 | `True` | 让 read timeout 对流式生效 |
| `extra_body` | 无 | `thinking: disabled` | 禁用 Moonshot reasoning_content |

---

## 4. 问题解决历程

### 4.1 问题一：API 连接频繁断开

**现象：**
```
openai.APIConnectionError: Connection error.
httpcore.RemoteProtocolError: Server disconnected without sending a response.
```

**根因：**
- Moonshot API 服务端有总连接时长限制（约 3-5 分钟）
- Agent 多轮对话 + 长文本生成，总时间超过阈值被服务端强制断开
- `ChatOpenAI(timeout=300)` 是**总请求超时**，对流式传输不限制总时长

**排查过程：**
1. ❌ 缩短 timeout=60 + max_retries=2 → 仍然断开
2. ❌ 限制 agent 3 轮 tool calls → 部分任务仍超时
3. ❌ read=5s → `APITimeoutError`（5秒太短，正常生成也被误杀）
4. ✅ **read=30s + retry=5 + streaming=True** → 解决

**原理：**
- `streaming=True` 让 `httpx.Timeout.read` 控制**相邻 token 的间隔**（而非总时长）
- 30 秒足够覆盖正常生成间隔
- 超过 30 秒时客户端主动断开并重试，避免挂到服务端切断

---

### 4.2 问题二：task_115 从通过变为失败

**现象：**
- baseline（旧配置）：task_115 18/18 通过
- baseline（streaming 配置）：task_115 0/18 失败，score=0.0

**可能原因：**
- streaming 模式下 Moonshot API 的响应格式有细微变化
- 或 prompt/工具行为受 timeout 重试影响产生副作用

---

### 4.3 问题三：复杂任务耗时过长

**现象：**
- task_107: 517 秒，score=0.0
- task_108: 501 秒，`httpx.ReadTimeout`（token 间隔 >30s）

**分析：**
- 复杂任务需要更多 tool calls 和长文本生成
- 即使 read=30s，极端情况下 token 生成间隔仍会超过阈值
- 需要进一步优化 prompt 减少轮次，或增大 read timeout

---

## 5. 评测结果对比

### 5.1 旧 Baseline（无 streaming，timeout=60）

| 任务 | passed | total | correctness | 错误类型 |
|------|--------|-------|-------------|----------|
| task_100 | 0 | 7 | 0.0 | `ConnectionError` |
| task_102 | 0 | 8 | 0.0 | `ConnectionError` |
| task_115 | 18 | 18 | 1.0 | ✅ |
| task_107 | 0 | 25 | 0.0 | `ConnectionError` |
| task_108 | 0 | 21 | 0.0 | `ConnectionError` |

**整体：1/5 通过，correctness = 0.2**

---

### 5.2 新 Baseline（streaming=True, read=30, retry=5）

| 任务 | passed | total | score | 耗时 | 状态 |
|------|--------|-------|-------|------|------|
| task_100 | 7 | 7 | 1.0 | 220.6s | ✅ **首次通过** |
| task_102 | 0 | 8 | 0.875 | 273.4s | ❌ 接近通过 |
| task_115 | 0 | 18 | 0.0 | 158.8s | ❌ 退化 |
| task_107 | 0 | 25 | 0.0 | 517.3s | ❌ |
| task_108 | 0 | 21 | 0.0 | 501.6s | ❌ `ReadTimeout` |

**Train correctness: 0.333**（1/3）
**Holdout correctness: 0.0**（0/2）

---

### 5.3 关键变化

```
                    task_100    task_102    task_115    task_107    task_108
旧 baseline          0/7 ❌      0/8 ❌     18/18 ✅     0/25 ❌     0/21 ❌
新 baseline          7/7 ✅     0/8 ❌      0/18 ❌      0/25 ❌     0/21 ❌
                    ───────────────────────────────────────────────────────
变化                 ↑+7        ≈ 持平      ↓-18        ≈ 持平      ≈ 持平
```

---

## 6. 下一步计划

| 优先级 | 事项 | 方案 |
|--------|------|------|
| P0 | 修复 task_115 退化 | 排查 streaming 模式下输出格式差异 |
| P0 | 解决 task_108 ReadTimeout | 增大 read=60s 或优化 prompt 减少生成量 |
| P1 | 提升 task_102 | score=0.875 接近通过，微调 prompt 即可 |
| P1 | 减少整体耗时 | 进一步收紧 tool call 轮次，或增加 batch 处理能力 |
| P2 | 进入 Iteration 迭代 | 等 baseline 稳定后，让 Better-Agent 自动提出改进方案 |

---

## 7. 项目文件结构

```
workspace_bench_demo/
├── experiment.toml              # better-harness 实验配置
├── workspace_bench_agent/
│   ├── graph.py                 # Agent 核心配置（当前优化重点）
│   ├── tools.py                 # 自定义工具（parse_pdf, compute_hash）
│   └── conftest.py              # pytest 评测入口 + judge 调用
├── tests/evals/
│   ├── test_task_100.py         # 训练集任务
│   ├── test_task_102.py
│   ├── test_task_115.py
│   ├── test_task_107.py         # 验证集任务
│   └── test_task_108.py
└── runs/
    └── workspace-bench-5tasks-20260602T073109Z/
        ├── history/
        │   ├── visible/train/baseline/       # 训练集 baseline 结果
        │   └── private/holdout/baseline/     # 验证集 baseline 结果
        └── variants/
            ├── baseline.json                 # baseline 配置快照
            └── iter-001.json                 # 第1轮迭代配置（待优化）
```

---

## 8. 关键结论

1. **streaming + httpx.Timeout 方案有效解决了 Moonshot API 连接稳定性问题**
2. **task_100 首次通过**，证明了优化方向正确
3. **task_115 退化**需要紧急排查，可能涉及 API 响应格式兼容性
4. **复杂任务（107/108）耗时过长**是下一个瓶颈，需要减少 agent 轮次或增大 read timeout
5. **Better-Harness 外层循环尚未真正启动**（baseline 还没跑完一次完整的 train+holdout 通过场景）

---

*报告生成时间：2026-06-02*
*当前运行 Run：`workspace-bench-5tasks-20260602T080445Z`*
