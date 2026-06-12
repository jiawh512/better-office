# Task 116 — Rubric 与原始数据矛盾分析报告

> **任务 ID:** 116  
> **角色:** Logistics Manager  
> **难度:** hard  
> **分析日期:** 2026-06-11

---

## 一、任务描述

在 `ansible` 文件夹中有 7 个聊天记录文件，要求：
1. 总结 API 文档修改记录（谁改了什么，标注信息来源）
2. 发送会议改期通知（stand-up 改到下午 3 点，通知所有员工）
3. 将结果记录到 `output20.md`

---

## 二、Rubric 声称的事实

Task 116 共有 **21 条评判标准**，其中涉及具体事实判断的 rubric 如下：

| # | Rubric 声称的事实 |
|---|------------------|
| #2 | 郑鹏更新了 inventory-service，来源 `chat_8002.txt` |
| #3 | 王杰更新了 api-gateway，来源 `chat_1376.txt` |
| #4 | **关键（Guan Jian）** 更新了 api-gateway，来源 `chat_2395.txt` |
| #5 | 周健有两条更新：notification-service（来源 `chat_3163.txt`）和 message-broker（来源 `chat_6805.txt`） |
| #6 | 张明更新了 notification-service，来源 `chat_5034.txt` |
| #7 | 赵亮更新了 message-broker，来源 `chat_7486.txt` |
| #12 | `chat_1376.txt` 中会议改期的发起人是 **孙伟** |
| #13 | `chat_2395.txt` 中会议改期的发起人是 **周健** |
| #14 | `chat_5034.txt` 由 **李强** 发起，且李强回复"没问题，下午见" |

---

## 三、原始文件实际内容

### `chat_1376.txt`

```text
[09:11:25] Zhao Liang: Everyone, today's stand-up has been moved to 3 PM. Any issues?
[09:13:25] Wang Jie: No problem, see you this afternoon.
[09:16:25] Zhou Jian: @all message-broker API documentation has been updated. Please review it.
[09:19:25] Hu Jun: Has the code review been finished?
[09:21:25] Zhou Jian: Still working on it. It should be done in about half an hour.
```

**实际事实：**
- 发起人：**赵亮（Zhao Liang）**
- API 更新者：**周健（Zhou Jian）**
- 更新服务：**message-broker**

---

### `chat_2395.txt`

```text
[09:11:25] Li Qiang: Everyone, today's stand-up has been moved to 3 PM. Any issues?
[09:13:25] Zheng Peng: No problem, see you this afternoon.
[09:16:25] Zhou Jian: @all notification-service API documentation has been updated. Please review it.
[09:19:25] Zhao Liang: Has the code review been finished?
[09:21:25] Zheng Peng: Still working on it. It should be done in about half an hour.
```

**实际事实：**
- 发起人：**李强（Li Qiang）**
- API 更新者：**周健（Zhou Jian）**
- 更新服务：**notification-service**

---

### `chat_3163.txt`

```text
[09:11:25] Li Qiang: Everyone, today's stand-up has been moved to 3 PM. Any issues?
[09:13:25] Hu Jun: No problem, see you this afternoon.
[09:16:25] Zheng Peng: @all inventory-service API documentation has been updated. Please review it.
[09:19:25] Li Qiang: Has the code review been finished?
[09:21:25] Wu Hao: Still working on it. It should be done in about half an hour.
```

**实际事实：**
- 发起人：**李强（Li Qiang）**
- API 更新者：**郑鹏（Zheng Peng）**
- 更新服务：**inventory-service**

---

### `chat_5034.txt`

```text
[09:11:25] Sun Wei: Everyone, today's stand-up has been moved to 3 PM. Any issues?
[09:13:25] Huang Jun: No problem, see you this afternoon.
[09:16:25] Wang Jie: @all api-gateway API documentation has been updated. Please review it.
[09:19:25] Chen Lin: Has the code review been finished?
[09:21:25] Li Qiang: Still working on it. It should be done in about half an hour.
```

**实际事实：**
- 发起人：**孙伟（Sun Wei）**
- API 更新者：**王杰（Wang Jie）**
- 更新服务：**api-gateway**
- 李强仅在最后一句出现，说的是"Still working on it"，**并非发起人也未回复"没问题"**

---

### `chat_6805.txt`

```text
[09:11:25] Li Qiang: Everyone, today's stand-up has been moved to 3 PM. Any issues?
[09:13:25] Li Qiang: No problem, see you this afternoon.
[09:16:25] Zhang Ming: @all notification-service API documentation has been updated. Please review it.
[09:19:25] Huang Jun: Has the code review been finished?
[09:21:25] Ma Chao: Still working on it. It should be done in about half an hour.
```

**实际事实：**
- 发起人：**李强（Li Qiang）**
- API 更新者：**张明（Zhang Ming）**
- 更新服务：**notification-service**

---

### `chat_7486.txt`

```text
[09:11:25] Zhou Jian: Everyone, today's stand-up has been moved to 3 PM. Any issues?
[09:13:25] Guan Jian: No problem, see you this afternoon.
[09:16:25] Guan Jian: @all api-gateway API documentation has been updated. Please review it.
[09:19:25] Wang Jie: Has the code review been finished?
[09:21:25] Liu Tao: Still working on it. It should be done in about half an hour.
```

**实际事实：**
- 发起人：**周健（Zhou Jian）**
- API 更新者：**关键（Guan Jian）**
- 更新服务：**api-gateway**

---

### `chat_8002.txt`

```text
[09:11:25] Liu Tao: Everyone, today's stand-up has been moved to 3 PM. Any issues?
[09:13:25] Chen Lin: No problem, see you this afternoon.
[09:16:25] Zhao Liang: @all message-broker API documentation has been updated. Please review it.
[09:19:25] Wang Jie: Has the code review been finished?
[09:21:25] Zhang Ming: Still working on it. It should be done in about half an hour.
```

**实际事实：**
- 发起人：**刘涛（Liu Tao）**
- API 更新者：**赵亮（Zhao Liang）**
- 更新服务：**message-broker**

---

## 四、矛盾点逐条对比

### 4.1 API 更新记录类

| Rubric | Rubric 声称 | 文件实际内容 | 矛盾程度 |
|--------|------------|-------------|---------|
| #2 | 郑鹏 → inventory-service → `chat_8002.txt` | 赵亮 → message-broker → `chat_8002.txt` | **完全矛盾：人、服务、文件全错** |
| #3 | 王杰 → api-gateway → `chat_1376.txt` | 周健 → message-broker → `chat_1376.txt` | **完全矛盾：人、服务、文件全错** |
| #4 | 关键 → api-gateway → `chat_2395.txt` | 周健 → notification-service → `chat_2395.txt` | **完全矛盾：人、服务、文件全错** |
| #5 | 周健 → notification-service → `chat_3163.txt` | 郑鹏 → inventory-service → `chat_3163.txt` | **完全矛盾：人、服务、文件全错** |
| #5 | 周健 → message-broker → `chat_6805.txt` | 张明 → notification-service → `chat_6805.txt` | **完全矛盾：人、服务、文件全错** |
| #6 | 张明 → notification-service → `chat_5034.txt` | 王杰 → api-gateway → `chat_5034.txt` | **完全矛盾：人、服务、文件全错** |
| #7 | 赵亮 → message-broker → `chat_7486.txt` | 关键 → api-gateway → `chat_7486.txt` | **完全矛盾：人、服务、文件全错** |

### 4.2 会议发起人及对话类

| Rubric | Rubric 声称 | 文件实际内容 | 矛盾程度 |
|--------|------------|-------------|---------|
| #12 | `chat_1376.txt` 发起人是 **孙伟** | 发起人是 **赵亮** | **完全矛盾** |
| #13 | `chat_2395.txt` 发起人是 **周健** | 发起人是 **李强** | **完全矛盾** |
| #14 | `chat_5034.txt` **李强** 发起，李强回复"没问题" | 发起人 **孙伟**，回复"没问题"的是 **黄军**，李强仅说"Still working on it" | **完全矛盾** |

### 4.3 正确的文件-人物-服务映射（基于实际文件内容）

| 文件 | 实际发起人 | 实际 API 更新者 | 实际更新服务 |
|------|-----------|----------------|-------------|
| `chat_1376.txt` | 赵亮 | 周健 | message-broker |
| `chat_2395.txt` | 李强 | 周健 | notification-service |
| `chat_3163.txt` | 李强 | 郑鹏 | inventory-service |
| `chat_5034.txt` | 孙伟 | 王杰 | api-gateway |
| `chat_6805.txt` | 李强 | 张明 | notification-service |
| `chat_7486.txt` | 周健 | 关键 | api-gateway |
| `chat_8002.txt` | 刘涛 | 赵亮 | message-broker |

---

## 五、矛盾性质分析

### 5.1 不是个别错误，而是系统性错位

Rubric 中的人物与来源文件的对应关系呈现出一种**循环错位**模式：

- Rubric 把 `chat_8002.txt` 的内容（赵亮 + message-broker）错误地安到了 **郑鹏 + inventory-service** 上
- Rubric 把 `chat_1376.txt` 的内容（周健 + message-broker）错误地安到了 **王杰 + api-gateway** 上
- Rubric 把 `chat_2395.txt` 的内容（周健 + notification-service）错误地安到了 **关键 + api-gateway** 上
- 以此类推……

**所有人、所有服务、所有来源文件都被交叉混淆了。**

### 5.2 Judge 无法发现矛盾的原因

Baseline Run 3 在 Task 116 上得了 **21/21 满分**，但这不代表 Agent"做对了"，而是因为：

1. **Judge 只评审 Agent 的输出**，不读取原始源文件
2. Agent 的 prompt 被明确告知：*"rubric-specified facts as authoritative requirements for your output"*
3. Agent 故意按照 rubric 的期望输出，即使这些期望与文件内容完全相反
4. Judge 看到 Agent 的输出与 rubric 期望一致，就给满分

### 5.3 这是一个"Rubric 优先"任务

Task 116 的真实测试目标可能不是"准确读取并总结聊天文件"，而是**测试 Agent 是否能严格遵循预设的评判标准输出**，即使标准本身与源数据矛盾。

这类似于一个"指令遵循"测试：Agent 被要求在 rubric 和源文件冲突时，**优先服从 rubric**。

---

## 六、影响与结论

### 6.1 对 Agent 优化的影响

如果 Better-Harness 的优化目标是让 Agent 在 Task 116 上得高分，那么优化方向应该是：
- **强化"rubric 优先于源文件"的指令**
- 让 Agent 学会在 rubric 和文件内容冲突时，**输出 rubric 期望的内容**

但这与真实世界场景相悖 —— 在实际工作中，用户期望 Agent **忠实于源数据**，而不是为了迎合预设答案而编造。

### 6.2 数据集质量问题

Task 116 暴露了 Workspace-Bench 数据集中可能存在的** rubric 设计缺陷**：
- Rubric 本身包含系统性错误
- Judge 无法验证 rubric 与源数据的一致性
- 得高分的 Agent 实际上是"迎合评测标准"而非"正确理解数据"

### 6.3 建议

1. **修正 Rubric：** 将 rubric 中的人物-服务-来源映射修正为与源文件一致
2. **增强 Judge：** 让 Judge 同时读取源文件，验证 rubric 本身的正确性
3. **区分任务类型：** 明确区分"数据忠实度任务"和"指令遵循任务"，避免用错误数据测试数据理解能力

---

## 七、附录：原始文件 vs Rubric 对照总表

| 文件 | 实际发起人 | 实际 API 更新者 | 实际服务 | Rubric 声称的更新者 | Rubric 声称的服务 | Rubric 声称的来源 |
|------|-----------|----------------|---------|-------------------|------------------|------------------|
| `chat_1376.txt` | 赵亮 | 周健 | message-broker | 王杰 | api-gateway | `chat_1376.txt` |
| `chat_2395.txt` | 李强 | 周健 | notification-service | 关键 | api-gateway | `chat_2395.txt` |
| `chat_3163.txt` | 李强 | 郑鹏 | inventory-service | 周健 | notification-service | `chat_3163.txt` |
| `chat_5034.txt` | 孙伟 | 王杰 | api-gateway | 张明 | notification-service | `chat_5034.txt` |
| `chat_6805.txt` | 李强 | 张明 | notification-service | 周健 | message-broker | `chat_6805.txt` |
| `chat_7486.txt` | 周健 | 关键 | api-gateway | 赵亮 | message-broker | `chat_7486.txt` |
| `chat_8002.txt` | 刘涛 | 赵亮 | message-broker | 郑鹏 | inventory-service | `chat_8002.txt` |

> **注：** 上表中"Rubric 声称的来源"列虽然文件名对了，但对应的人和服务全错。
