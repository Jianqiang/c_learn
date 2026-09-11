# Day 1 Reconciliation Flags

- **模式**: reconciliation checker — **只报告哪里对不上，不报告原因**
- **用途**: 防止未 reconcile 的口径差异变成 Day 2 的错误 anchor
- **规则**: 下面每一条我都不解释。你自己回 filing 找差额构成。

---

## Flag 1 — 你的营业利润率算术正确，但你只用了一个口径

你在 `01_snps_company_map_v0.md` §6 写：

> 「看上去这个生意的毛利没有想象的高（OP margin似乎只有13%？），SNPS在产业链上是不是并没有收租权（rent）？」

**算术核对**：914.9 / 7,054.2 = **12.97%** ✅ 你算对了。

**但 orientation pack §2 里同时存在这些数字**：

| 口径 | 数值 | 期间 | 出处 |
|---|---|---|---|
| GAAP 营业利润率 | **13.0%** | FY2025 全年 | pack §2 |
| non-GAAP 营业利润率 | **41.6%** | FY26 Q3 | pack §2 |
| non-GAAP 营业利润率（指引） | **41.5%** | FY2026 全年 | pack §7 |
| 毛利率（TTM） | **72.35%** | TTM | pack §2 |

**差额约 28.6 个百分点。这里对不上。**

你要自己回答的是：**这 28.6pt 由哪些具体科目构成？**

一条线索：你在 §1.4「Cost」里唯一写下的那一项，是构成之一。但不是全部。

**我不告诉你答案。** 完整 reconciliation 是 Day 6（Accounting anatomy）的正式内容。

---

## Flag 2 — 术语混用

你写「**毛利**没有想象的高」，但引用的数字是 **OP margin**。

毛利率和营业利润率是两个不同的东西，中间隔着 opex（R&D、SG&A、无形资产摊销等）。
pack §2 两个数字都有。**先把术语分清楚，再下判断。**

---

## Flag 3 — 这个判断目前建立在未 reconcile 的口径上

> 「SNPS 在产业链上是不是并没有收租权（rent）？」

这是个好问题——它正是 **Day 2（value creation ≠ value capture）和 Day 13（fade）** 的核心。

但**在 Flag 1 的 28.6pt 被 reconcile 之前，任何基于「13%」的 rent 结论都不成立**。
今天不要下这个结论。把它作为**待检验的假设**写进 `03_twenty_unknowns.md`，标注前置条件是 Flag 1。

---

## Flag 4 — 一个将在 Day 2 被重新处理的比较

你在 §1.5 Value 写：

> 「NVDA 2025 年拿走了 130B，AVGO 大约 63B 的收入，客户拿走的至少 20-100 倍收入」

**事实层面**：这是拿两家公司的**收入规模**做比较。

Day 2 的 Brandenburger & Stuart 框架处理的是 **added value**——一个和收入规模不同的量。
不需要现在改。**保留这个写法**，Day 2 用新框架重做一遍，两版对比本身就是训练记录。

---

## Flag 5 — 未完成项

| 文件 | 状态 |
|---|---|
| `03_twenty_unknowns.md` | **完全空白**。你在 SNPS map §6 写了 3 条，需要转录并扩充到 20 条 |
| `02_tencent_company_map_v0.md` | 引擎表、关系图、SNPS 对比表、未知问题 — 全部空白 |
| Day 2 AI 证据任务书 | 未写（`03_twenty_unknowns.md` 末尾） |

Day 1 的三个 output 目前完成度：SNPS map ✅ / Tencent map ❌ / 20 unknowns ❌

---

## 关于 Flag 1 的一个程序提醒

不要现在就去查「non-GAAP 调整了什么」然后抄下来。

Day 6 的练习是**你自己从零 reconcile**：拿 NI → OCF → FCF，逐项找出差额。
今天你只需要知道**「存在两个差 28.6pt 的口径，我还没解释它」**，并且**不在任一口径上下 rent 结论**。

知道自己没解释，比提前拿到解释更有价值。
