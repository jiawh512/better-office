# Better-Harness + Workspace-Bench 流程图

---

## 图1：现有系统（不含 HALO）

```mermaid
flowchart TB
    subgraph OUTER["外层优化循环 (better-harness)"]
        direction TB
        TOML["experiment.toml\n配置train/holdout/cases"]
        BASE["Baseline Phase\n运行所有train cases"]
        LOOP{"迭代 < max_iterations?"}
        BETTER["Better Agent\n分析失败 → 提出修改"]
        EVAL["Eval Phase\n用新prompt重跑train"]
        DEC{"Decision\ncandidate ≥ current?"}
        ACC["Accept → 更新current/"]
        REJ["Reject → 丢弃"]
        HOLD["Holdout Eval\n最终泛化测试"]
        REP["生成Report\n最优变体 + scores"]

        TOML --> BASE
        BASE --> LOOP
        LOOP -->|Yes| BETTER
        BETTER --> EVAL
        EVAL --> DEC
        DEC -->|Accept| ACC
        DEC -->|Reject| REJ
        ACC --> LOOP
        REJ --> LOOP
        LOOP -->|No| HOLD
        HOLD --> REP
    end

    subgraph INNER["内层单任务执行 (conftest.py::run_task_eval)"]
        direction TB
        META["加载metadata.json\ntask + output_files + rubrics"]
        CP["复制 data/ → work_dir/"]
        BUILD["build_agent()\ncreate_deep_agent()"]
        INV["agent.invoke(\n  {messages: wrapped_prompt}\n)"]
        OUT["多策略收集\noutput files"]

        META --> CP --> BUILD --> INV --> OUT
    end

    subgraph JUDGE["评测层 (judge_wrapper.py)"]
        direction TB
        JLOAD["加载metadata.json\n+ agent.json"]
        JBUILD["build_judge_model()\nChatOpenAI + rubrics prompt"]
        JLLM["LLM评估每个rubric\npassed + evidence"]
        JOUT["输出\njudge_result.json"]

        JLOAD --> JBUILD --> JLLM --> JOUT
    end

    BASE -.->|per task| INNER
    INNER -.-> OUT
    OUT -.-> JUDGE
    JUDGE -.->|score| BASE
    JUDGE -.->|score| EVAL
    EVAL -.->|train scores| BETTER
    BETTER -.->|修改current/\nprompt.txt, graph.py| EVAL

    style OUTER fill:#e1f5fe
    style INNER fill:#fff3e0
    style JUDGE fill:#e8f5e9
```

### 数据流详解

| 阶段 | 输入 | 输出 | 关键文件 |
|------|------|------|---------|
| **Baseline/Eval** | task_id, data/, metadata.json | work_dir/, agent_result.json | `summary.json`, `judge_result.json` |
| **Better Agent** | current/prompt.txt, current/graph.py, task.md, train_failures.json | 修改后的 prompt/graph | `proposer_workspace/current/` |
| **Judge** | metadata.json, output/, agent.json | rubric-level评分 | `judge_result.json` |

---

## 图2：加入 HALO 后的增强系统

```mermaid
flowchart TB
    subgraph OUTER["外层优化循环 (better-harness)"]
        direction TB
        TOML["experiment.toml\n+ trace_collection: true"]
        BASE["Baseline Phase\n运行所有train cases"]
        TRACE["TraceCollector\n记录每步完整输入输出"]
        HALO_ANA["HALO Analyzer\n(可选) 跨轨迹故障模式分析"]
        FAIL_REP["failure_report.md\n系统性问题总结"]
        LOOP{"迭代 < max_iterations?"}
        BETTER["Better Agent\n(+ HALO报告作为上下文)"]
        EVAL["Eval Phase\n(+ TraceCollector)"]
        DEC{"Decision\ncandidate ≥ current?"}
        ACC["Accept → 更新current/"]
        REJ["Reject → 丢弃"]
        HOLD["Holdout Eval"]
        REP["生成Report\n+ trace质量指标"]

        TOML --> BASE
        BASE --> TRACE
        TRACE -.->|失败cases的trace.jsonl| HALO_ANA
        HALO_ANA --> FAIL_REP
        FAIL_REP -.->|增强上下文| BETTER
        TRACE --> LOOP
        LOOP -->|Yes| BETTER
        BETTER --> EVAL
        EVAL --> TRACE
        TRACE --> DEC
        DEC -->|Accept| ACC
        DEC -->|Reject| REJ
        ACC --> LOOP
        REJ --> LOOP
        LOOP -->|No| HOLD
        HOLD --> REP
    end

    subgraph INNER["内层单任务执行 (增强版)"]
        direction TB
        META["加载metadata.json"]
        CP["复制 data/ → work_dir/"]
        BUILD["build_agent()"]
        TC_INIT["TraceCollector(agent)\n初始化跟踪器"]
        INV["collector.invoke()\n包装agent调用"]
        MSG["记录每个span:\n- llm_call_N\n- tool_call_N\n- judge_evaluation"]
        OUT["收集output files"]
        JUDGE["run_judge()"]
        WRITE["collector.write_jsonl()\n→ case_dir/trace.jsonl"]

        META --> CP --> BUILD --> TC_INIT --> INV --> OUT
        INV -.->|拦截messages| MSG
        OUT --> JUDGE
        MSG --> JUDGE
        JUDGE --> WRITE
    end

    subgraph HALO["HALO 分析层 (本地/子进程)"]
        direction TB
        H_IN["输入: OTel JSONL\ntrace.jsonl (多个case)"]
        H_IDX["TraceIndexBuilder\n多进程构建索引"]
        H_AGENT["Root Agent\n调用trace_tools"]
        H_SYN["SynthesisTool\n跨轨迹摘要"]
        H_OUT["输出: 故障报告\nMarkdown格式"]

        H_IN --> H_IDX --> H_AGENT --> H_SYN --> H_OUT
    end

    BASE -.->|per task| INNER
    INNER -.->|trace.jsonl| HALO
    HALO -.->|failure_report.md| BETTER
    BETTER -.->|修改current/| EVAL

    style OUTER fill:#e1f5fe
    style INNER fill:#fff3e0
    style HALO fill:#f3e5f5
```

### 关键增强点

| 组件 | 新增能力 | 解决的问题 |
|------|---------|-----------|
| **TraceCollector** | 每步 LLM/Tool/Judge 记录为 OTel span | "无法定位是agent还是tool出错" |
| **trace.jsonl** | 完整 tool input/output + 时序 + 错误堆栈 | agent_result.json 数据截断、缺失 |
| **HALO Analyzer** | 跨 case 的系统性模式识别 | 单 case 看不出共性，Better Agent 只能试错 |
| **failure_report.md** | 结构化故障报告（含trace_id、证据、建议） | Better Agent 输入质量低，修改方向盲目 |

---

## 图3：单 Case 的详细数据流（对比）

### 现有系统：单 Case 输出

```mermaid
flowchart LR
    AGENT["agent.invoke()"] --> AR["agent_result.json\n(简化messages)"]
    JUDGE["run_judge()"] --> JR["judge_result.json\n(rubrics评分)"]
    AR --> SUM["summary.json\n(score only)"]
    JR --> SUM

    style AR fill:#ffcdd2
    style JR fill:#ffcdd2
```

**问题**：
- `agent_result.json` 只有 `content` 摘要，**没有 tool 完整参数和返回**
- `judge_result.json` 只有评分结果，**无法回溯 agent 哪一步行为导致失败**
- 两个文件是**割裂的**，没有统一 trace_id 关联

### HALO 增强后：单 Case 输出

```mermaid
flowchart LR
    subgraph TRACE["统一 Trace (OTel JSONL)"]
        direction TB
        S1["span: agent_run\ntask_id, model, system_prompt"]
        S2["span: llm_call_1\nprompt, completion, tool_calls"]
        S3["span: tool_call_1\nname='read_file'\nargs='metadata.json'\nresult='{完整内容}'"]
        S4["span: llm_call_2\n..."]
        S5["span: tool_call_N\nname='write_file'\n..."]
        S6["span: judge_evaluation\nscore=0.5\nfailed_rubrics=[...]"]

        S1 --> S2 --> S3 --> S4 --> S5 --> S6
    end

    AGENT["collector.invoke()"] --> TRACE
    JUDGE["collector.add_judge_span()"] --> TRACE
    TRACE --> JSONL["case_dir/trace.jsonl"]

    style TRACE fill:#e1bee7
    style JSONL fill:#c8e6c9
```

**优势**：
- **统一 trace_id** 贯穿 agent_run → llm_calls → tool_calls → judge
- **完整 tool 结果** 保存在 `tool_call_N` span 的 `result` 属性
- **时序信息** 每个 span 有 `start_time`/`end_time`，可定位超时
- **错误保留** agent 异常时 `agent_completion` span 记录 `error_type` + `error_message`

---

## 图4：HALO 分析在优化循环中的位置

```mermaid
sequenceDiagram
    participant U as User
    participant BH as Better-Harness
    participant TC as TraceCollector
    participant IN as Inner Agent
    participant JD as Judge
    participant HA as HALO
    participant BA as Better Agent

    U->>BH: 启动优化 (experiment.toml)
    BH->>TC: 运行 Baseline (train cases)
    loop Per Task
        TC->>IN: invoke()
        IN-->>TC: messages
        TC->>JD: run_judge()
        JD-->>TC: judge_result
        TC->>TC: write_jsonl()
    end

    alt trace_collection enabled
        BH->>HA: 收集失败cases的trace.jsonl
        HA->>HA: TraceIndexBuilder + Agent分析
        HA-->>BH: failure_report.md
    end

    BH->>BA: 生成task.md
    Note over BH,BA: 原有输入: prompt, graph, failures<br/>HALO增强: + failure_report.md

    loop Iteration N
        BA->>BA: 分析失败模式 → 提出修改
        BA-->>BH: proposer_workspace/current/
        BH->>TC: Eval Phase (candidate)
        TC->>IN: invoke() with new prompt
        IN-->>TC: messages
        TC->>JD: run_judge()
        JD-->>TC: judge_result
        TC->>TC: write_jsonl()
        BH->>BH: Decision (accept/reject)
    end

    BH->>BH: Holdout Eval
    BH-->>U: Final Report
```

---

## 实施优先级

```mermaid
flowchart LR
    P1["Phase 1: TraceCollector\n(1-2小时)"] --> P2["Phase 2: trace.jsonl输出\n(30分钟)"]
    P2 --> P3["Phase 3: 本地HALO分析\n(2-3小时)"]
    P3 --> P4["Phase 4: failure_report接入Better Agent\n(1小时)"]

    style P1 fill:#c8e6c9
    style P2 fill:#c8e6c9
    style P3 fill:#fff9c4
    style P4 fill:#fff9c4
```

| 阶段 | 产出 | 价值 |
|------|------|------|
| **Phase 1-2** | 每个 case 有 `trace.jsonl` | 立刻可以手动分析单个 case 的完整执行过程 |
| **Phase 3** | `halo trace.jsonl -p "..."` 生成报告 | 跨 case 系统性问题定位 |
| **Phase 4** | Better Agent 自动读取 HALO 报告 | 优化方向从"试错"变为"数据驱动" |
