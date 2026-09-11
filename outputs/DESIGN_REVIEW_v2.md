# Bootcamp 设计诊断与重构方案

- **日期**: 2026-09-09（Day 3 应有日）
- **触发**: owner 实测 Teece + B&S 需 3–4 小时，原设计给 60 分钟
- **结论**: **owner 的质疑成立，但真实问题比"时间不够"更严重。原设计有一个算术上不可能的前提。**

---

## 1. 先摆事实：Day 2 实际发生了什么

| 项 | 计划 | 实际 |
|---|---|---|
| Part A 闭卷 | 10 分钟 | ✅ 完成，遵守三词禁令，且诚实标注"我对他家软件与竞争对手的差别了解有限" |
| Theory | 60 分钟 | ❌ 实际 3–4 小时（Teece + B&S） |
| Part B 八维度 | 140 分钟 | ❌ 全空，含 B6（唯一 must-answer 项） |
| Part C counterfactual | — | ❌ 全空 |
| Part D 中船 | 60 分钟 | ❌ 全空 |
| `01_value_creation_capture_map.md` | 正式 output | ❌ 111 个空单元 |
| **额外产出** | 无 | ✅ **一份 12 家公司的 Teece 应用 memo + 一个五关框架** |

**判断：owner 没有偷懒，他在时间冲突中选择了深度而非交差。这个选择是对的。**

memo 展示的能力恰好是 Day 2 想训练的：三个概念准确使用、两次真正的概念修正、可复用框架、区分「有资产」与「能收租」。
**深度超过 worksheet 要求，只是载体不同。**

### P2（跨案迁移）算不算满足？

算，而且强度更高。worksheet 要求 SNPS + 中船 = 2 次迁移；
memo 把同一框架跑过 AVGO / NVDA / PLTR / NOW / CRM / Intel / 飞书 / WorkBuddy / 用友 / 恒生 = **10 次**。

但有一个重要的缺口，见 §4。

---

## 2. 根本问题：原设计的算术前提不成立

我把原 manifest 的全部材料按现实工时重估（含"就地应用以加深理解"的时间，因为那才是真学习）：

| 材料 | 类型 | 现实工时 |
|---|---|---|
| MS&E435 W1–2 | 课程材料 | 3–4h |
| Teece 1986 | 密集论文 | **3–4h（已实测）** |
| Brandenburger & Stuart 1996 | 论文 | 2–3h |
| Baldwin — Bottlenecks（HBS WP，约 40 页） | 论文 | 3–4h |
| Jacobides, Knudsen & Augier | 论文 | 2–3h |
| Chancellor — Capital Returns | 书 | 10–15h |
| MIT 15.515 Financial Accounting | 课程 | 8–10h |
| Penman — FSA（选读） | 书（700+ 页） | 10–15h |
| Nissim & Penman | 论文 | 3–4h |
| Mauboussin — ROIC | 长报告 | 2–3h |
| Damodaran #2, #7–10 | 5 讲 | 6–8h |
| Expectations Investing | 书 | 10–12h |
| Expectations tutorials | 工具 | 3–4h |
| MIT 14.271 L16–19 | 4 讲 | 5–7h |
| NBER Ch.7 | 章节 | 2–3h |
| Superforecasting | 书 | 8–10h |
| Howard Marks | 书 | 6–8h |
| **合计** | | **≈ 90–125 小时** |

对比原设计的供给：

```
材料时间供给 = 20 天 × 60 分钟 = 20 小时
材料时间需求 = 90–125 小时
缺口 = 70–105 小时（差 4.5–6 倍）
```

而 bootcamp 的**总**预算是 20 × 6h = 120 小时。

> **结论：如果按原材料清单，把全部 120 小时都用来读材料仍然不够，一分钟都不剩给 project。**

这不是"稍微紧"，是设计前提错误。你的直觉是对的，而且比你说的更严重。

---

## 3. 第二个问题：三个训练器的角色没有分化

原设计让三家公司**并列**，每天在两家上应用当天框架。问题：

**a) 切换成本被忽略。** SNPS（美股软件/SEC filing/non-GAAP 文化）、腾讯（港股/IFRS/中概披露习惯）、中船防务（A 股/周期制造/订单式生产）——
三套会计口径、三套行业逻辑、三种披露风格。每天来回切，认知开销巨大而学习增量很小。

**b) 与 owner 的 edge 不匹配。** owner 的 edge 在 AI/技术/产业认知（这也是他 memo 一小时就能出成果的原因）。
中船防务是纯周期制造，他在那里没有 edge——**学习曲线陡，但迁移价值恰恰因此更高**（见 §4，这是个 feature 不是 bug，只是不该放在每天）。

**c) 真实决策的载体缺失。** owner 有真实 Universe（约 29 只票）。
memo 里那 10 家公司才是他要下注的对象，SNPS/中船只是练习器。
**训练如果不通向真实决策，20 天后不会留下东西。**

---

## 4. 但有一个反向的风险，必须指出

owner 的提议是"更贴近核心材料，用 project 适当扩充"。方向对。
但如果顺着走到极端，会掉进一个陷阱：

> **在自己有 edge 的领域学新框架，最容易发生的事是：用新词汇包装旧判断。**

检验：memo 里 AVGO「强 CS」、NVDA「强 specialized + category-level CS」、PLTR「强 downstream CS」——
这些结论和你原有的 AI 半导体/软件观点基本一致。那么 Teece 到底改变了什么？

**它确实改变了两处**（这是 memo 最有价值的部分）：
1. harness 不是 LLM 的 dominant design，foundation model 层已进入 early paradigmatic
2. 真正的 co-specialization 不在 Model↔Harness，而在 Harness↔Customer workflow/state

这两条是新的，说明框架咬进去了。**但它们仍在你的舒适区内（AI/软件）。**

所以 SNPS 和中船的真正价值不是"多两个 case"，而是：

```
SNPS  = 对照组（中等熟悉度，检验框架是否依赖 edge）
中船  = 压力测试（完全不熟 + 非科技 + 强周期，检验框架的普适性）
```

**如果一个框架只在你有 edge 的地方跑得通，你学到的是新词汇，不是新能力。**
这是不能砍掉它们的唯一理由——但确实不需要每天都碰。

---

## 5. 重构方案

### 核心改动：从「20 天日历」改为「5 个 module，跑通为止」

| Module | 内容 | 材料 | 现实工时 | 主训练器 |
|---|---|---|---|---|
| **M1 Capture** | appropriability / dominant design / complementary assets / added value / bottleneck / industry architecture | Teece · B&S · Baldwin · Jacobides | 12–16h | **AI rent 主线**（已完成大半）+ SNPS 对照 |
| **M2 Financial Translation** | accounting anatomy → decomposition → ROIC → FCF | 15.515 · Penman 选读 · Nissim-Penman · Mauboussin · Damodaran | 35–45h | SNPS（欠账 B 在这里清）+ 腾讯 |
| **M3 Expectations** | reverse DCF / price-implied thesis / PIT consensus | Expectations Investing + tutorials | 15–20h | 腾讯（live position）+ AI 主线中的 CRM |
| **M4 Capital Cycle** | supply response / entry / fade / cyclical expectations | Chancellor · MIT 14.271 L16–19 | 15–22h | **中船防务**（在这里才有用） |
| **M5 Judgment** | forecast / falsification / sizing | Superforecasting · Marks · sizing | 15–20h | 全部 + 真实持仓 |

合计 92–123 小时 — **与原总预算 120 小时匹配**，因为不再假装能压缩材料时间。

### 每个 module 的内部结构（这是关键）

```
1. 材料消化        不设上限，但见下方闸门
2. 就地应用 memo   在 owner 有 edge 的领域（他已自己发明了这个模式，效果好）
3. 强制迁移        换一个完全不同的对象 ← P2 在这里守，不在每天守
4. 闭卷考试        不看材料能否跑通框架 ← module 出口
```

### 防失控闸门（必须有）

不设时间上限会让 bootcamp 退化成读书会。三个闸门：

| 闸门 | 规则 |
|---|---|
| **50% 上限** | 材料时间 ≤ 该 module 总时间的 50%。Teece 花 3–4h 合理；花 10h 还在读就是逃避应用 |
| **出口是闭卷** | module 不以"读完"结束，以**闭卷跑通框架**结束。读完 ≠ 掌握（这条原则不变） |
| **每 module 必须产出可结算预测** | 至少 3 条通过 forecast linter。见 memo 的 F1 flag——你现在 0 条 |

### 时间结构改动

原来每天固定 6 block。改为**两种日型**：

**A 型（材料日）**
```
20m  Market contact
10m  闭卷 recall（前一日概念）
180m 材料消化 + 就地应用
60m  应用 memo 落盘
30m  Synthesis / question queue
```

**B 型（应用日）**
```
20m  Market contact
10m  闭卷 recall
140m Primary（单一训练器，深做）
90m  强制迁移（换对象）
40m  Decision rep
30m  Synthesis
```

**module 内的日型比例约 1:1**，由材料量决定，不预先排死。

---

## 6. 关于第二波（owner 提到的"1–2 个 project 巩固"）

同意，但要明确第二波的性质不同：

- **第一波（M1–M5）**：框架 proceduralize。载体是练习器 + AI 主线
- **第二波**：完整 underwriting，1–2 个真实候选，**不是练习是下注**
  - 产物：Investment Memo + 5 forecasts + 3 kill conditions + position decision tape
  - 这就是原 Day 19/20 的内容，但给它足够时间（原设计给 2 天，现实需要 4–6 天）

---

## 7. 需要 owner 决定的两件事

其余我直接改。这两条涉及偏好，不该我定：

**Q1 — AI rent 主线是否正式成为第三个训练器（替代中船在 M1–M3 的位置）？**

- 支持：owner 有 edge、连接真实 Universe、已产出高质量 memo 和五关框架
- 风险：舒适区内学框架 = 可能只学到新词汇（§4 的问题）
- 缓解：SNPS 保留为对照组，中船在 M4 作为压力测试

**Q2 — 材料清单是否按现实工时删减？**

M2 是最大的时间坑（35–45h）。选项：
- 全保留：M2 独占约 40% 总时间，但 accounting/FCF 是 owner 自称权重最高的一周
- 砍 Penman 全书 → 只读 Nissim-Penman 论文 + 15.515 核心模块（省约 10–12h）
- 砍 Damodaran 视频 → 用 Expectations Investing 的 tutorials 替代（省约 6h）

---

## 8. 立即执行的部分（不等确认）

1. ✅ memo 已存入 `outputs/day02/04_memo_teece_ai_rent.md`，附四条 coach flag
2. ✅ Day 2 记为 **partial**：Part A + memo 完成，八维度/counterfactual/中船未做
3. **新增欠账 F**：memo 有 10 个判断、0 条可结算预测 → M1 出口前必须补 3 条
4. **新增欠账 G**：「是否已 price in」的判断全部无证据 → M3（reverse valuation）解决
5. 八维度检验 + counterfactual removal **不作废**，移入 M1 的"强制迁移"环节
   —— 因为它们是"框架在无 edge 领域是否跑得通"的检验，正是 §4 说的对照组价值
