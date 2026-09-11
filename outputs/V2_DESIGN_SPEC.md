# v2 设计说明书

- **日期**: 2026-09-09
- **用途**: v1 vs v2 的完整对比，以及每个 module 的目的 / 材料 / 练习设计
- **manifest**: `content/bootcamp_modules.yaml` | **驱动**: `scripts/modules.py`

---

## 0. 先回答一个具体质疑：IO 视频课被砍了吗？

**没有。** MIT 14.271（Ellison）L16–19 在 v2 的 **M4 Capital Cycle** 里，估 5–7h。

但你的怀疑指向了一个真实变化：

| 版本 | IO 的 URL 指向 |
|---|---|
| 原 16 周 curriculum | `resources/lecture-videos/` ← **视频** |
| 你的新 20 天 syllabus | `resources/lecture-notes/` ← 讲义 |
| v1（我照抄你的） | `resources/lecture-notes/` |
| **v2（已修复）** | **两者并存** |

**这个改动发生在你自己的新 syllabus 里，我沿用了它。** 现在 v2 把视频和讲义都保留：讲义用于快速定位，视频用于建立 entry deterrence 的直觉。

### 但对账查出了我的三个真错误

你问这一句，让我做了完整的 v1→v2 材料 diff。结果我确实无意砍掉了三个：

| 被砍的 | v1 位置 | v2 已补回 |
|---|---|---|
| **Stanford MS&E 435**（AI Supercycle W1–2） | Day 1 | → **M1**，3–4h |
| **NBER Ch.7 — Transformative AI and Firms** | Day 3（腾讯 JIT） | → **M1**，2–3h，JIT 读法 |
| **Good Judgment Open** | Day 16 | → **M5** |

补回的理由不只是"原来有"：
- **MS&E435** 与你的 AI rent memo 是互补的：memo 回答「rent 归谁」，这门课回答「池子在哪一层、多大」。而且 Day 1 的 AI Profit Pool Map v1 本来就是它的产物，有连续性
- **NBER Ch.7** 恰好补你 memo 里最薄的理论环节：downstream CS（Harness ↔ Customer workflow/state）为什么难以重新配置 —— 答案在组织的 tacit knowledge 与 decision rights
- **GJ Open** 解决一个真问题：投资预测结算周期太长、样本太少，calibration 练不出来。GJ Open 是唯一能高频结算的练习场

v2 材料总数现在是 **19**（v1 是 16，新增 sizing + 补回 3）。

### 补回后必须承认的代价

| 项 | 原估 | 补回后 |
|---|---|---|
| M1 | 12–16h | **15–20h** |
| modules 合计 | 92–123h | **97–130h** |
| 含第二波 | — | **121–166h** |
| 原始预算 | 120h（20 工作日 × 6h） | **只够覆盖下限，且不含第二波** |

**实际跨度会是 6–8 周，不是 4 周。**

这是承认现实，不是计划失控 —— v1 的错误恰恰是假装 120h 能装进 20 天还能做完 project。
若你要求压回 20 天，**唯一诚实的做法是砍掉整个 module，而不是压缩每个 module 的材料时间**。

---

## 1. v1 vs v2：七个区别

| 维度 | v1（20 天日历制） | v2（module 制） |
|---|---|---|
| **驱动单位** | 日历天。Day N 做 Day N 的事 | module。M1–M5，跑通为止 |
| **材料时间** | 固定 60 分钟/天，共 20h | 不预设上限，按现实工时 92–123h |
| **出口条件** | 到第二天自动进入下一天 | **闭卷跑通框架 + 匿名 transfer test + 3 条可结算预测** |
| **训练器** | 3 家并列（SNPS/腾讯/中船），每天碰 2 家 | AI rent universe（主）+ 腾讯（live）+ **每 module 一个陌生对照案例** |
| **迁移（P2）** | 每天守（transfer block 60min） | **module 出口守**（匿名 transfer test 90min） |
| **失控防护** | 无 | **三个闸门，脚本强制执行** |
| **预测要求** | 只在 Day 16 集中做 | **每个 module 出口 ≥3 条，不达标拒绝出口** |

### 为什么必须改：v1 的算术前提不成立

```
材料现实需求 = 92–123 小时
v1 材料供给  = 20 天 × 60 分钟 = 20 小时
缺口         = 4.5–6 倍
总预算       = 120 小时
```

**把全部 120 小时都用来读材料仍然不够，一分钟都不剩给 project。** 这不是执行不力。

实测证据：Teece + B&S 你用了 3–4 小时，v1 给 60 分钟。

### v2 的三个闸门（已实测生效）

| 闸门 | 规则 | 执行 |
|---|---|---|
| **g1** | 材料时间 ≤ module 总时间 50% | `modules.py log` 超限告警 |
| **g2** | 以闭卷跑通 + transfer test 出口，不以"读完"出口 | 人工判定 |
| **g3** | 每 module ≥3 条可结算预测 | `modules.py exit --pass` **直接拒绝**；`forecast add` 缺 metric/threshold/resolves/source 任一项即标 fail |

g1 存在的理由：不设上限会让 bootcamp 退化成读书会。Teece 花 3–4h 合理，花 10h 还在读就是逃避应用。

---

## 2. 五个 module 的完整设计

### M1 — Capture（12–16h，进行中，已投 5h）

**目的**：回答「为什么这部分价值最终归某家公司」。补上 Technology → Rent 链条中最容易被跳过的一环：**Firm Capture**。

**材料（6 项）**

| 材料 | 工时 | 状态 | 作用 |
|---|---|---|---|
| Teece 1986 | 3–4h | ✅ 已读 | appropriability regime · dominant design · complementary assets 三分类 |
| Brandenburger & Stuart 1996 | 含上 | ✅ 已读 | added value = 有它 − 没它；capture 上限 = added value |
| Baldwin — Bottlenecks | 3–4h | ⬜ | 把 complementary assets 升级为 bottleneck / control point 视角 |
| Jacobides et al. | 2–3h | ⬜ | industry architecture 如何决定 appropriation |
| **MS&E435 W1–2** | 3–4h | ⬜ 补回 | AI stack 的 profit pool 在哪一层、多大 |
| **NBER Ch.7** | 2–3h | ⬜ 补回·JIT | 组织内 state / decision rights 为何难重配置 |

**练习设计**

已完成（你的 memo）：五关框架 + 10 家公司判断地图 + 两次真概念修正。

剩余三项，其中第 2 项是核心：

1. **Baldwin/Jacobides 应用**：AI 栈的 control point 在哪一层？与 memo 的 CS 判断是否一致？
2. **★ 对照案例 深南电路 002916.SZ** — FC-BGA 载板是 specialized 还是 cospecialized？
   > 这不是"多做一个案例"。它**直接检验你 memo 里那条判断**：
   > 「HBM、GPU、光模块、电力设备完全可能拥有稀缺性和 bottleneck rent，却通常只是 specialized assets」
   >
   > AI 载板是同一类叙事。若你的判断成立，深南应归 specialized；
   > **若你在这里改判为 cospecialized，必须解释与 HBM/光模块的差别在哪。**
   > 这个约束已写进 M1 出口条件。
3. **补 3 条可结算预测**（欠账 F。当前 0 条，g3 会拦住出口）

**AI 模式**：independent divergence + fact extraction。
允许多个独立来源分别画 architecture graph，**只呈现分歧节点**；禁止回答「control point 在哪」。

**出口条件**：闭卷跑通五关 · 深南判定有机制依据 · 匿名 transfer test（陌生公司、非 AI 行业）· 3 条预测过 linter。

---

### M2 — Financial Translation（35–45h，★最高优先）

**目的**：产业判断如何变成财务结果与现金流。

**为什么是最高优先** —— 三条独立证据都指向这是你最短的板：
1. 欠账 B：SNPS 的 28.6pt 口径差至今未 reconcile
2. Day 1 把 OP margin 说成"毛利"（术语混用）
3. **memo 有 10 个判断但 0 条可结算预测 —— 根因就是不知道怎么把 rent 判断锚定到具体财务量上**

**读法**：**缺口驱动 JIT**（你的选择）。不预先读完整本 Penman，按当前 reconcile 卡在哪定读什么。

**材料（5 项）**：MIT 15.515（accrual/revenue recognition）· Penman FSA（选读：operating vs financing 切分、reformulation）· Nissim & Penman（margin × turnover）· Mauboussin ROIC（incremental ROIC、多口径并存）· Damodaran #2/#7–10（按需）

**练习设计（4 个锚点任务）**

1. **★ 清欠账 B**：SNPS GAAP OPM 13.0% vs non-GAAP 41.6%，**自己从零 reconcile 28.6pt**
2. **★ 对照案例 立讯精密 002475.SZ**：商誉/无形摊销、在建工程转固、客户集中的应收与返利
   > 与 SNPS 配对的价值：SNPS 的调整主要是无形摊销 + SBC，立讯的逻辑完全不同。
   > 两家一起做才能分清**哪些调整是会计人为，哪些是真实经济差异**。
3. **腾讯三口径 reconcile**：IFRS 归母 +0.7% vs non-IFRS +9% vs 剔除新 AI 产品 861 亿
4. **腾讯现金流辨析**：FCF −138 亿 vs 剔除 514 亿算力预付款后 +376 亿 —— 哪个是真实现金生成能力？
5. 把 memo 五关的第五关（Observed rent）落成具体财务量：pricing / ARR uplift / attach rate / retention / GM / FCF

**AI 模式**：**reconciliation checker** —— 只报「这里对不上 N 亿」，不给 ratio、不给解释、不给调整表。

**出口条件**：给定一个产业变化，闭卷说出「先打哪个 operating driver → 哪个财务科目 → 何时进现金流」· 欠账 B 清除且能解释每项调整的经济含义 · 3 条预测锚定到具体科目与阈值。

---

### M3 — Expectations（15–20h）

**目的**：把「贵不贵」替换成「**当前价格要求什么必须为真**」。

**材料（2 项）**：Expectations Investing（Mauboussin & Rappaport）· 官方 tutorials + spreadsheets（10 个免费）

**练习设计**

1. **★ 清欠账 G** —— 这是本 module 存在的首要理由。你 memo 里这几句是全篇唯一决定 alpha 的判断，却完全没有证据：
   > 「市场已高度认识这种 rent」「rent 已高度共识」「市场已经按极长期 rent 定价」

   用 reverse DCF 把它量化：反解隐含的 revenue growth / margin / duration。
2. **PLTR**：反解当前价格隐含条件，与你「rent 已 consensus」的判断对照
3. **CRM**：反解「defensive feature」与「新 rent layer」两种情形的隐含价格差
   > 你 memo 里已经把这个问题提得很准，只是缺可结算形式。改写示范：
   > 若截至 FY2028 整体 revenue growth 未超 12% 而 Agentforce ARR 超 $5B → defensive；
   > 若整体 growth 同时抬升至 15%+ → 新 rent layer
4. **腾讯**：AI capability → Product KPI → advertiser economics → FCF → value，写 Reality/Consensus/Price 三栏
5. **建立带时间戳的 consensus snapshot，禁止事后覆盖**（PIT discipline）

**★ PIT 铁律**：本地 `chatgpt_cases_archive` 有 CRM / NOW / 腾讯 的历史 memo。
**必须先闭卷写当前判断，再打开旧 memo 对比**「我当时怎么想 / 现在怎么想 / 什么证据让我改变」。顺序反了就退化成抄旧结论。

**AI 模式**：solver, not valuator —— 写 reverse DCF solver 暴露敏感度；**禁止给"合理估值"或目标价**。

---

### M4 — Capital Cycle（15–22h）

**目的**：供给为什么不能迅速回应？高利润为什么会被消灭？

**这是 v2 的核心检验 module** —— 中国船舶是非科技 + 强周期，用来验证「M1 框架是否只在你有 edge 的地方有效」。

**材料（2 项）**

| 材料 | 工时 | 说明 |
|---|---|---|
| Chancellor — Capital Returns | 10–15h | supply-side capital cycle，不是追逐 demand growth |
| **MIT 14.271 L16–19（Ellison）** | 5–7h | entry 与 strategic investment。**视频 + 讲义都保留**，不做 problem sets 除非 case 卡住 |

**练习设计**

1. **中国船舶 600150.SH**：订单 → 船坞 slot → 新船价 → 产能 → backlog → 交付 → 利润 → 现金
2. **先自己划 regime，再让 AI challenge** —— 本地 cninfo 公告可提取订单/交付序列
3. 用 M1 框架回答：**造船业最像 cospecialized asset 的是技术还是 slot？**
4. 回到 AI universe：算力 capex 的 supply response 会在何时压缩 rent？
5. AVGO/NVDA：高 rent 为何未被 entry 消灭？barrier 与 fade 路径

**AI 模式**：raw timeline only —— 只给原始时间序列，**禁止先给 regime 划分或解释**。

**出口条件**：能预测竞争与资本反应而非只外推需求 · **M1 框架在无 edge 领域跑通**。

---

### M5 — Judgment（15–20h）

**目的**：不确定性 → 概率 → 赔率 → 仓位。

**材料（4 项）**：Superforecasting（Tetlock & Gardner）· **Good Judgment Open**（补回）· Howard Marks（Ch.1, 4–7, 10, 14, 16, 19）· sizing（Kelly intuition / correlation，只补所需）

> GJ Open 补回的理由：投资预测结算周期太长、样本太少，calibration 练不出来。
> GJ Open 是唯一能高频结算的练习场。方法迁移到自己的 Forecast Ledger，**不要大量预测政治问题**。

**练习设计**

1. 把 M1–M4 累积的预测整合为 **15–20 条 Forecast Ledger**（prior / probability / resolution date / rule）
2. 为 AI universe 每个标的写**最强 bear mechanism** —— 自己先写，再 blind challenge
3. **腾讯真实仓位**：Probability × Payoff × Confidence × Correlation → Position，找 **decision boundary**

**AI 模式**：forecast linter + blind challenger + sensitivity surface。
**禁止**推荐仓位、给目标价、评价预测内容。

**安全边界**：只记录 decision tape，**不下单、不改变实际仓位**。

---

## 3. 三种日型（不再固定 6 block）

| 日型 | 结构 |
|---|---|
| **A 材料日** | 20m market contact · 10m 闭卷 recall · **180m 材料 + 就地应用** · 60m memo 落盘 · 30m synthesis |
| **B 应用日** | 20m market contact · 10m 闭卷 recall · **140m primary（单一对象深做）** · 90m 强制迁移 · 40m decision rep · 30m synthesis |
| **X 出口考试日** | 90m 闭卷跑通框架 · 90m 匿名 transfer test · 60m forecast linter · 60m error taxonomy + 定下个 module 的 JIT 补读清单 |

**module 内 A:B 约 1:1，由材料量决定，不预先排死。**

---

## 4. 第二波（M1–M5 全部通过后，24–36h）

不是练习，是下注。1–2 个真实候选的完整 underwriting。

**候选优先级**：CRM（rent 性质未决，研究价值最高）· 腾讯（live position）· SNPS（第三）

**交付物**：Investment Memo 3–5 页 · 一个 model · 5 个 load-bearing assumptions · 5 条可结算 forecasts · 3 个 kill conditions · position decision + monitoring plan · postmortem template

---

## 5. 当前欠账（7 条）

| 编号 | 欠账 | 到期 |
|---|---|---|
| A | Day 1 unknowns 只 6 条且 4/6 形态是「差问题」 | M1 出口 |
| B | **SNPS 28.6pt 口径差未 reconcile** | M2 锚点 |
| C | B 未清前禁止基于单一口径下 rent 结论 | 硬约束 |
| D | Tencent map 四引擎未跳出 segment；漏社交网络 325 亿、新 AI 产品、投资组合 8,751 亿 | M1 出口 |
| E | Day 1 证据任务书未写 | 顺延 |
| **F** | **memo 有 10 个判断、0 条可结算预测** | **M1 出口（g3 强制）** |
| **G** | **「已 price in」判断全部无证据** | **M3** |

---

## 6. 一句话总结差异

> **v1 假装材料能被压缩，于是 project 和材料互相挤压，最后两个都做不深。**
> **v2 承认材料需要多少时间就给多少，改用「闭卷 + 迁移 + 可结算预测」三重出口来防止读书会化。**
