# M1 Guided Lab 01｜IBM PC：谁会控制 PC 的战略瓶颈？

**训练概念：** Baldwin 的 technical bottleneck / strategic bottleneck / module / interface / control point  
**决策时点：** 1981-12-31  
**你扮演：** 1981 年末的产业分析师  
**结果状态：** 结果已知，但由 coach 保持不披露；不会在仓库中存放答案或事后结果。  
**预计时间：** Round 1 约 75–90 分钟；后续两轮在你提交后逐轮释放。

---

## 1. 这不是开放研究题

你不需要判断 AI Factory 的未来，也不需要写 IBM/Intel/Microsoft 的历史综述。

你的唯一任务是：

> **站在 1981 年末，在不使用 1982 年之后的信息的前提下，判断 PC 行业的技术瓶颈、模块边界与潜在 control point；并写出可以在 1991 年检验的预测。**

训练的目标不是“猜中历史赢家”，而是检验你的推理链能否区分：

\[
\text{技术上必要}
\neq
\text{短期紧缺}
\neq
\text{战略 control point}
\neq
\text{最终 rent capture}
\]

---

## 2. 时间边界与信息纪律

### 允许的信息

- **仅限 1981-12-31 或以前**已经公开的信息；
- 下列 Background Pack；
- 你自行搜索的、明确标注出版日期不晚于 1981-12-31 的原始材料；
- 外部 AI 仅可做“截至该时点的事实提取 / 来源定位 / 逻辑质询”。

### 严禁的信息

- 搜索或询问“IBM PC 最后谁赢了”“Wintel 为什么成功”“IBM PC 历史结果”；
- 任何 1982 年之后的市场份额、财务表现、兼容机结果、诉讼或技术演变；
- Wikipedia、现代回顾文章、投资案例总结作为判断依据。

> **关键原则：** 你可以用 AI 帮你找 1981 年的资料；不能让它用未来替你回答 1981 年的问题。

---

## 3. Background Pack（只含 1981 可得事实）

### [S1] IBM 官方历史资料（后写回顾，但此处只允许提取 1981 事实）

**URL：** https://www.ibm.com/history/personal-computer  
**用途：** 锁定 IBM 5150 的设计选择与当时的公开架构。  
**只提取：** 产品上市时点、开发约束、所用 CPU/OS、技术资料公开、扩展总线、第三方部件选择。

可直接使用的事实：

1. IBM 5150 PC 在 **1981 年 8 月**推出；项目目标是大约一年内推出、以约 $1,500 价格进入新市场。
2. 为满足时程与成本，IBM 使用了大量 **off-the-shelf** 部件；CPU 选择 Intel 8088，操作系统由 Microsoft 提供。
3. IBM 采用 open architecture，并发布技术参考资料，以促进软件和外设开发。
4. PC 有扩展总线；第三方可以围绕它开发软件与外围设备。
5. IBM 自己在进入 PC 前，历史上更倾向于垂直整合的企业计算机模式。

### [S2] 可选原始技术材料

**搜索 URL / 关键词：** `IBM PC Technical Reference 1981 PDF`  
**用途：** 识别硬件模块边界、bus/interface 与 IBM 公开了什么。  
**只提取：** 接口、扩展槽、BIOS、技术资料开放范围；不要查后续兼容机历史。

### [S3] 当时产业背景（可选）

**搜索关键词：** `1981 personal computer industry Intel 8088 Microsoft DOS contemporary`  
**用途：** 仅补足当时可观察的竞争选项和技术不确定性。  
**只提取：** 1981 年已存在的替代 CPU、操作系统、PC 厂商、软件生态状态。

---

## 4. 允许调用 AI 的方式

### Prompt A：PIT 事实提取

```text
你是 1981-12-31 的研究助理。只使用在该日或以前公开的原始或同期资料，
提取 IBM PC 5150 的组件、接口、技术资料开放范围与供应关系。
每条标 [S] 事实 / [M] 当时管理层主张，并附来源和发布日期。
不要提及 1982 年之后的事件、市场份额、结果或任何 hindsight。
```

### Prompt B：逻辑质询，不给结论

```text
以下是我在 1981 年末对 IBM PC 架构的因果链。
请只找出：1) 我混淆了“技术 bottleneck / 供需短缺 / control point”的地方；
2) 缺失的 interface；3) 需要写成可检验预测的箭头。
不要判断谁会赢，不要提供历史结果，不要补写我的结论。

[粘贴你的表格]
```

### 禁止 Prompt

```text
IBM 为什么输给微软和英特尔？
Wintel 的成功原因是什么？
1981 年谁最终捕获了 PC 行业利润？
```

---

## 5. Round 1｜1981 年末的 architecture decision（75–90 分钟）

### Step 1：10 分钟闭卷

不看材料，填下面四行：

```text
PC 最可能的技术 bottleneck：
它限制的系统结果：
我认为最可能控制关键 interface 的参与者：
我最不确定的一条箭头：
```

### Step 2：25 分钟证据定位

仅使用 §3 的资料或符合时间边界的自搜材料，补齐下表。每一格都应能回溯到一条 1981 年前的材料。

| 节点 / 模块 | 1981 年的功能 | 对外 interface | IBM 是否控制它？如何控制？ | 采用者或第三方能否替代 / multi-home？ | 证据 `[S]/[M]/?` |
|---|---|---|---|---|---|
| CPU |  |  |  |  |  |
| 操作系统 |  |  |  |  |  |
| BIOS / firmware |  |  |  |  |  |
| 扩展总线 / 外设 |  |  |  |  |  |
| 应用软件 |  |  |  |  |  |
| 整机组装 / 渠道 |  |  |  |  |  |

### Step 3：25 分钟分类，不许写公司结论

| 候选约束 | 具体的 not-good-enough 问题 | 技术 bottleneck / 供需短缺 / 两者皆非 | 若此约束放松，下一处限制在哪里？ | 我还缺什么事实？ |
|---|---|---|---|---|
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |

### Step 4：20 分钟作出 1981 年末的“条件性押注”

> 这里不是投资建议，也不需要股价或估值。你只预测 **industry architecture**。

1. 哪一个模块最可能在 10 年后成为 **strategic control point**？只能选一个。  
2. 你判断它的原因必须是 **interface / entry condition / switching mechanism**，不能只写“技术强”“品牌强”或“需求大”。  
3. 给出两个竞争性解释：为什么该模块也可能被模块化或被其他层替代？

```text
我的主判断：

关键机制：

竞争性解释 1：
竞争性解释 2：

我现在不给这一判断超过 ____% 的概率，因为：
```

### Step 5：10 分钟写 2 条可结算预测草案

不要求 forecast linter 通过，但必须能在后续 Round 3 被判定。

| 预测 | 1981 年可观察的前兆 | 1991 年的结算指标 | 通过条件 | 推翻条件 |
|---|---|---|---|---|
|  |  |  |  |  |
|  |  |  |  |  |

---

## 6. Round 1 的唯一交付

在本文件末尾追加你的答案；**限 600–900 字 + 表格**。不需要写 memo。

提交时只对 coach 说：

> `IBM PC Lab Round 1 complete`

我会先做 **reconciler**：只指出你混淆的概念、漏掉的 interface 与不具可结算性的预测；不会告诉你历史结果。之后才释放 **Round 2（1983–84）** 的新信息。

---

## 7. 评分标准（结果不参与评分）

| 项 | 通过标准 |
|---|---|
| 时间纪律 | 没有使用 1982 年后的信息 |
| 架构纪律 | 区分了技术 bottleneck、供需短缺、module 与 control point |
| 机制完整 | 每个 control-point 候选都有 interface 与 control mechanism |
| 反事实 | 至少给出 2 个能使主判断失效的竞争解释 |
| 预测能力 | 至少 2 条有明确 1991 结算标准的预测草案 |

## 8. 本 Lab 在 curriculum 中的位置（2026-09-11 修订后）

Phase I 的链条已升级为：

\[
Tech\ Change
\rightarrow Constraint
\rightarrow Interdependency
\rightarrow Architecture
\rightarrow Bottleneck
\rightarrow Value\ Capture
\rightarrow Capital\ Response
\]

本 Lab 训练的正是中间三段。阅读顺序被刻意安排为：

| 阶段 | 动作 | 理由 |
|---|---|---|
| 现在 | Round 1（仅用 1981 信息） | 先押注，暴露你自己的架构直觉 |
| Round 1 交卷后 | 读 **Henderson & Clark 1990** | IBM PC 是 architectural innovation 的原型案例；先押注再读理论 |
| Round 2 | 1983–84 证据 | 检验你的 interface 判断 |
| Round 2 后 | 读 **Jacobides & Winter 2005** | firm boundary：为什么纵向范围会重组 |
| Round 3 | 1991 结算 + 复盘 | 只在此时释放结果 |

若在 Round 1 之前读 Henderson & Clark，这个练习的价值会显著下降——你会用论文的分类去套 IBM PC，而不是用自己的推理去发现它。

**JIT 提示**：如果 Round 2 出现「技术边界与组织边界不一致」的现象，再打开 Colfer & Baldwin 2016（Mirroring Hypothesis）。不要提前读。
