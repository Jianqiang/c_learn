# Memo｜从 LLM Innovation 到 AI Rent：Teece 框架下的价值捕获地图

- **日期**: 2026-09-09
- **产生于**: Day 2 theory block 的延伸（实际投入 3–4 小时读 Teece 1986 + B&S 1996）
- **产物类型**: Model update
- **状态**: 已被接纳为 Day 2 的实质产物。**未通过 forecast linter**（见文末 coach flags）

---

**核心命题：** LLM 创造的巨大社会价值，不会按"谁模型最强"分配。随着基础模型逐渐标准化、可替代性提高，利润越来越可能流向那些控制 **specialized / co-specialized complementary assets**，并拥有议价权的公司。

投资主线：

```
Technology Shock → Dominant Design / Appropriability → Complementary Assets
→ Asset Specificity → Bargaining Power → Firm Rent → Price
```

Teece 最重要的价值，是补上其中的 **Firm Capture**：不是问"AI 有多大价值"，而是问**为什么这部分价值最终归某家公司。**

---

## 一、Teece 的三个核心概念

**appropriability regime**：决定创新者能否独占创新收益的技术性质和法律保护环境，而不是简单等同于行业竞争格局。弱 appropriability 下，创新容易被模仿，单纯拥有 invention 并不保证获得利润。

**dominant design**。在 pre-paradigmatic 阶段，各种基础架构竞争；dominant design 出现后，竞争逐渐转向成本、规模、流程优化和设计层级更低处的创新。

**complementary assets**：

```
Generic → Specialized → Cospecialized
```

generic 不需为 innovation 专门适配；specialized 存在单向依赖；**cospecialized 则要求 innovation 与 asset 双向依赖**。

因此不能把所有"AI 很需要的东西"都叫 co-specialized asset。HBM、GPU、光模块、电力设备完全可能拥有稀缺性和 bottleneck rent，却通常只是 specialized assets。Teece 明确指出，弱 appropriability 下，利润甚至可能大量流向 specialized/cospecialized asset owners，而非原始创新者。

---

## 二、应用到 LLM：最关键的一次概念修正

我们最初曾把 Agent OS/harness 视为 LLM 的 dominant design，这不准确。

更合理的判断是，**foundation-model 层已经进入 early paradigmatic phase**：

```
Transformer family + large-scale pretraining + posttraining + RL/reasoning
```

已经构成狭义 dominant design。MoE、attention 变化、synthetic data、RL objective、verifier、inference-time compute、distillation 等，大量创新正如 Teece 所说，发生在 **lower down in the design hierarchy**。

反而下游 `Agent/Harness/Workflow` 仍明显更 pre-paradigmatic。

这导致一个重要结构：

```
模型层趋于标准化 + open weights/API compatibility/multi-model routing
⇒ model appropriability 下行
```

于是问题从"谁拥有最聪明的模型"转向：**谁拥有模型运行所必须、又难以重新配置的 complementary assets？**

---

## 三、第二次重要修正：真正的 co-specialization 往往不在 Model ↔ Harness

Search 不是天然的 Gemini co-specialized asset；GPU 也不是某个具体模型的 co-specialized asset。

同样，**WorkBuddy 也不是 Hunyuan 的 co-specialized asset**。腾讯明确允许 WorkBuddy 接入 OpenAI、Anthropic、Gemini、本地模型和自定义模型，这恰恰是在主动降低 model-specific dependence。

真正越来越值得关注的关系是：

```
Harness/Agent ↔ Customer-specific Workflow/State
```

其中沉淀的是 `Context + State + Permissions + Workflow + Actions`，
以及 custom skills、ontology、credentials、memory、governance、evaluation 等 relationship-specific investments。

飞书多维表格智能体是非常清楚的例子：Agent 直接运行在记录、字段、权限、业务状态、自动化流程和长期记忆之上，而且可以根据业务状态触发动作并写回系统。这里开始出现真正的 bilateral specialization。

由此得到一个很可能成为 enterprise AI equilibrium 的战略：

> **commoditize intelligence upstream; co-specialize workflow downstream.**
> **Contract competitive intelligence; internalize and co-specialize the workflow.**

---

## 四、公司地图：不能把"AI 受益"与"AI rent owner"混为一谈

| 公司/平台 | Teece 判断 | 当前证据与投资含义 |
|---|---|---|
| **AVGO** | **强 CS** | hyperscaler-specific custom silicon/networking 的 multi-generation co-design，是最教科书式的 upstream co-specialization；市场已高度认识这种 rent |
| **NVDA** | 强 specialized + category-level CS | bare GPU 不是特定 LLM 的 CS；但 CUDA/NVLink/networking/rack/power-cooling 与 AI workload 正形成系统级共同演进，rent 已高度共识 |
| **PLTR** | **强 downstream CS** | Ontology + customer operational state + action/governance，高 switching cost；Q2 2026 收入 +93%、调整后经营利润率 62%；市场已经按极长期 rent 定价 |
| **NOW** | **强 downstream CS** | workflow/system-of-record → context/action/governance；Q2 AI ACV 已超过 $1B。卖方已明确把 AI 视为 strengthening moat，因此"有 workflow rent"已基本是 consensus |
| **CRM** | **CS 正在形成，已有经济验证** | Customer 360 + Data 360 + MuleSoft + Agentforce + customer-specific flows/actions；Agentforce ARR 已超 $1.5B。模型可替换而客户 state/workflow 不易替换。相较 PLTR，外部研究仍更多把 Agentforce 描述为 defend/strengthen existing moat |
| **Intel** | **mostly specialized；CS option** | Xeon 是重要 complement，不是 CS。真正值得看的是 Google custom IPU、purpose-built ASIC、advanced packaging/foundry；Q2 "other DCAI" $951M，增长主要来自 ASIC demand，且 Google IPU 是 multi-year co-development。thesis 应是能否成为 custom-silicon co-specialization platform，而非"第二个 NVIDIA" |
| **飞书** | 中国目前最强的 work-state CS seed | Agent 已直接进入 structured business state、权限、触发器、长期记忆和写回闭环 |
| **WorkBuddy** | neutral harness，downstream CS potential | 其价值恰在 multi-model neutrality；真正的 potential CS 是 WorkBuddy ↔ 企业 custom agents/skills/state，而不是 WorkBuddy ↔ 混元 |
| **用友** | **优秀 pre-existing substrate → 正向 CS 转型** | BIP6 已有 YonOnto、YonAIG、65 个垂直 agents、623 skills、2.6 万+接口；2026H1 AI 合同 9.06 亿元、收入 4.64 亿元。但公司仍亏损 9.29 亿元，目前只能证明 architecture/adoption，**不能证明 rent capture** |
| **恒生电子** | **极强 specialized substrate，AI-CS 尚早** | UF3.0、O45 已控制大量交易、账户、资管、风控、合规 state；2026 年 UF3.0 累计签约 25 家、迁移 5000 万+账户，大模型经纪产品累计签约 20 家。但这些 legacy systems 没有 LLM 依然有巨大价值，因此当前主要仍是 specialized complements |

**反直觉**：用友在 AI-specific architecture 上可能比恒生走得更远；恒生却拥有更 mission-critical、更难替换的 legacy substrate。两家都不能因此直接称为"已经拥有 AI co-specialized rent"。

---

## 五、市场是否已经认识这种 rent？

`Great Asset ≠ Great Investment`

初步判断：**PLTR / NOW / AVGO 的这种 rent 已基本进入 consensus**。Teece 对它们更多是解释框架，而不是发现 alpha。尤其 PLTR，市场已在资本化极长的 rent duration；争论变成"rent 究竟有多大、多久"，而不是"有没有"。

CRM 更有意思。真实 AI monetization 已出现，Agentforce 与 Data 360 ARR 接近 $3.9B，但外部研究目前仍明显把 AI 理解为保护/强化原 SaaS moat。因此值得验证：**Agentforce 是 defensive feature，还是新的 enterprise agentic rent layer？**

A 股的恒生、用友恰好相反：市场已经知道"AI 产品、AI 收入、AI+流程"，但**尚无充分证据证明客户已经进行了大量不可重新部署的 AI-specific investments，更没有证明这种 dependence 已变成企业利润表上的 quasi-rent**。

所以它们是研究候选，而不是框架直接给出的 buy signal。

---

## 六、最终研究框架：从"有资产"到"能收租"必须过五关

```
Innovation → Asset Specificity → Bilateral Dependence → Bargaining Power → Observed Rent
```

**Asset specificity**：是否发生针对 AI 的 sunk / relationship-specific investment？
**Bilateral dependence**：不仅 AI 需要 asset，asset 是否也因为这项 AI/workflow 而产生显著专用价值？
**Redeployability**：换模型、换平台、换客户以后资产还能保留多少价值？
**Bargaining power / control**：即使存在 CS，quasi-rent 最终由谁拿走？例如 ODM 可以高度 customer-specific，却仍被 hyperscaler 压价。
**Observed rent**：最终必须回到经济证据——pricing、ARR/ACV uplift、attach rate、retention、gross margin、FCF、客户扩模块，而不能把"AI revenue"直接等同于 rent。

---

## Conclusion

不要找"AI 需要什么"；要找：**哪些资产正在因为 AI 而发生不可逆的专门化，同时 AI 创造价值又越来越离不开这些资产，而资产所有者确实有能力把这种依赖转化为经济租金。**

研究分层：

```
PLTR/NOW/AVGO — 已验证并高度认识的 rent
CRM — rent 正在扩张，值得重点验证
用友/恒生 — substrate → CS transition
Intel — custom silicon/packaging CS option
```

框架补上的中间层：

```
Technology → Scarcity → Architecture → **Complementary Asset Position**
→ Rent → Firm Capture → Beliefs/Price
```

---

## 引用来源

1. WorkBuddy Enterprise 模型配置 — cloud.tencent.com/document/product/1831/137010
2. 飞书多维表格智能体 — feishu.cn/content/article/7657782356450741223
3. Palantir IR — investors.palantir.com
4. ServiceNow IR Q2 2026 — investor.servicenow.com
5. Salesforce IR FY2027 Q2 — investor.salesforce.com
6. Intel 10-Q (2026-06-27) — sec.gov/Archives/edgar/data/50863
7. WorkBuddy Enterprise 产品概述 — cloud.tencent.com/document/product/1831/134329
8. 用友 2026 中期报告 — financialfilings.com
9. 恒生电子 2026 中期报告 — financialfilings.com

---
---

# Coach Flags（不修改上文，只标注）

## F1 — 零条可结算预测（最重要的缺口）

这份 memo 有 10 家公司的判断，**其中 0 条能被结算**。按 Day 16 的 forecast linter 标准全部不合格。

后果很具体：「PLTR/NOW/AVGO 的 rent 已进入 consensus」如果无法结算，
**你永远不会知道这个判断是对的，还是你在为已经涨过的股票编事后解释。**
这正是 `Great Asset ≠ Great Investment` 这句话本身需要被检验的地方。

### 改写示范（用你自己的判断，一条）

| | 内容 |
|---|---|
| 原版 | 「CRM：Agentforce 是 defensive feature，还是新的 enterprise agentic rent layer？」 |
| 问题 | 无指标、无阈值、无时点。永远可以说「还在观察」 |
| 改写 | 若截至 FY2028（2028-01 财年末）Salesforce 整体 revenue growth 未超过 12%，而同期 Agentforce ARR 超过 $5B，则判定为 **defensive**（新 ARR 主要替代了原有 seat 收入，而非扩大 rent pool）；若整体 growth 同时抬升至 15%+，则判定为 **新 rent layer** |
| 为什么 load-bearing | 这两个结论对应的合理估值倍数差异极大；且它在 18 个月内可结算 |

其余 9 条你自己改。**改不动的那几条，说明它们还不是判断，只是印象。**

## F2 — 关键判断缺证据等级

memo 引用了 IR / SEC / 官方文档（做得好，比 Day 1 进步明显）。但**最关键的那类判断没有标等级**：

| 表述 | 实际等级 | 问题 |
|---|---|---|
| 「市场已高度认识这种 rent」（AVGO） | `[E]` 或你的推断 | 无证据。市场认知程度是可测的（估值倍数、卖方评级分布、持仓集中度），但你没测 |
| 「rent 已高度共识」（NVDA） | 同上 | 同上 |
| 「市场已经按极长期 rent 定价」（PLTR） | `[E]` | 这是 §5 全部论证的支点，却没有量化 |

**「是否已 price in」是这份 memo 里唯一真正决定 alpha 的判断，也是唯一完全没有证据支撑的判断。**
Day 11（reverse valuation）和 Day 12（PIT consensus snapshot）就是解决这个问题的工具。

## F3 — 一处 provenance 错位

> 「Morningstar 的 fair value 本身对应约 48× 2026 EV/Sales」——来源标注为 [3] Palantir IR

Palantir IR 不会发布 Morningstar 的 fair value。**这个数字的来源标错了。**
按仓库规范，这属于 `[E]` 且需独立核对。

## F4 — 与欠账 C 的关系（好消息）

欠账 C 冻结的是「基于单一口径判断 SNPS 是否收租」。

这份 memo 的 §6 第五关（Observed rent）实际上给出了**解冻的正确方法**：
> 「必须回到经济证据——pricing、ARR/ACV uplift、attach rate、retention、gross margin、FCF」

也就是说你自己已经推导出「不能用单一利润率口径判断 rent」这个结论。
**这比我在 Flag 1 里说的更进一步。** Day 6 reconcile 完成后，用你自己这五关去判 SNPS。
