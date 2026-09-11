# AI Profit Pool Map v1

- **Week**: 1/16 — "AI stack 上钱现在在哪里？"
- **日期**: 2026-09-04 | **状态**: v1 锚点版（事实层完成，判断列待填）
- **规则**: 事实由 AI 锚定并标证据等级；「钱在哪里」的判断和 decision rep 由 owner 填写
- **证据等级**: [S] = 财报/官方口径 | [E] = 媒体/研报估计 | [U] = 未验证判断

---

## 0. 读图方式

资金沿 stack **向上游支付**（apps → models → infra → chips），当前利润池**集中在最下游的硬件层**。注意：**各层收入不能简单相加**——NVDA 的成本就是 TSMC/SK hynix 的收入，比较利润池必须用各层自身的营业利润。

## 1. 四层数据锚点（2026 Q2 口径，年化 = 单季 × 4）

### Layer 4 — Apps（应用层）
| 项目 | 数字 | 等级 | 来源/时点 |
|---|---|---|---|
| AI coding 工具市场 | ~$12.8B（2024 年 $5.1B） | [E] | 行业估计, 2026 |
| Cursor ARR | $2B（2月）→ 近期估 ~$4B | [E] | Bloomberg/行业，口径不一 |
| Claude Code run-rate | >$2.5B | [E] | Anthropic 口径, 2026 初 |
| GitHub Copilot | 470 万付费订阅, ARR ~$1B | [E] | MSFT FY26Q2 |
| Salesforce Agentforce | $0.8B ARR (+169%) | [E] | FY26 |
| ChatGPT 订阅 | ~$22B ARR（计入 OpenAI） | [E] | 泄露财报/媒体 |
| 层利润状态 | 规模小、多数未盈利；「谁捕获」远未收敛 | [U] | — |

### Layer 3 — Models（模型层）
| 项目 | 数字 | 等级 | 来源/时点 |
|---|---|---|---|
| OpenAI ARR | $40B+（8月），2–6 月曾停滞在 ~$25B | [E] | Bloomberg 2026-08-13 |
| OpenAI 盈利 | 2025 booked 收入 $13.07B，经营亏损 $20.9B；GM ~33% | [E] | 泄露审计财报 |
| Anthropic ARR | $65B（7月底），年初 $9B → 7 个月 ~7x | [E] | Reuters 2026-08-17 |
| Anthropic 盈利 | Q2 2026 首次调整后营业利润转正（Q2 收入 ~$11.5B） | [E] | SemiAnalysis/媒体 |
| 两家合计 | ~$105B ARR（年初 ~$30B） | [E] | Epoch AI |
| 收入结构差异 | Anthropic 75–85% 为 usage-based API；OpenAI 偏订阅 | [E] | SemiAnalysis |

### Layer 2 — Infra（基础设施层）
| 项目 | 数字 | 等级 | 来源/时点 |
|---|---|---|---|
| 四大 CSP 2026 capex | AMZN ~$220-230B / MSFT ~$175-190B / GOOG $195-205B / META $125-145B，合计 ~$700B+ | [S] | 各公司指引（多次上调），2026-07 |
| 九大 CSP（含中系） | ~$830B，+79% YoY | [E] | TrendForce 2026-05 |
| 2027 展望 | 可能 >$1T | [E] | S&P |
| 云增速 | GCP +63%（OPM 32.9%，去年同期 17.8%）/ AWS +28% / Azure +39% | [S] | 各公司财报 |
| FCF 压缩 | AMZN TTM FCF $38.2B→$11.2B，2026E -170~-280 亿美元；GOOG 26/27E FCF -58%/-80% | [E] | MS/BofA 估计 |
| 订单 | MSFT 商业 RPO $625B（+110%），**45% 来自 OpenAI 单一客户** | [S] | MSFT 财报 |
| 物理层 | VRT：Q2 收入 $3.27B(+24%)、backlog $15B、2026 指引 ~$14B(+31%)；ETN：Q2 $8.5B(+21%)、DC 订单 +85%；GEV 燃机 backlog 116GW；美国电力缺口 38GW(至2028)、变压器交期 36 个月 | [S] | 各公司财报 |
| 层利润状态 | 云利润在加速（GCP OPM 近翻倍），但被 capex 折旧吞掉大半 → FCF 收缩；**全层净利润待你估算** | — | gap |

### Layer 1 — Chips（芯片层）
| 项目 | 数字 | 等级 | 来源/时点 |
|---|---|---|---|
| NVDA Data Center | $89.0B/季（+117% YoY），总营收 $96.2B，GM 75.0%，OP $63.7B（OPM ~66%），NI $59.7B | [S] | 官方新闻稿 2026-08-26 |
| NVDA 指引 | Q3 FY27 $108B ±2%，GM 74%，**中国 DC 收入 = 零假设** | [S] | 同上 |
| NVDA 年化 | 收入 ~$385B run-rate，OP ~$255B | [S] | 推算 |
| 注意 | +117% 含 H20 低基数效应（去年同期对华受阻），绝对量 $89B 才是硬事实 | [E] | 财报分析 |
| SK hynix | Q2 收入 $52.8B，GM ~83%，OP $40.3B（OPM ~76%）；NI $62.5B 含 $35.4B 非经常收益 | [S] | 财报聚合数据 2026-07-29 |
| SK hynix 冲突数据 | 第三方有 42% OPM / HBM 收入 $12.4B 的报道，与财报口径严重冲突，**待核对原报** | [E] | 冲突 |
| HBM 格局 | SK hynix 份额 56-58%，HBM 占其 DRAM 收入 58%；与 NVDA 共同开发至 2030（Vera Rubin） | [E] | 多来源 |
| TSMC | 7 月收入 NT$467.6B（+44.7%）；H1 NT$2.4T（~$75B，+35.6%）；全年指引 >40% USD 增长；capex 上调至 $60-64B；HPC 占 Q2 收入 66% | [S] | 公司月度披露 2026-08 |

### 利润池对比（年化 OP，2026 Q2 × 4，粗算）
| 层 | 年化营业利润 | 等级 |
|---|---|---|
| Chips（NVDA ~255 + hynix ~161 + TSMC ~75，含供应链重叠仅供量级） | **~$490B** | [S]→推算 |
| Infra 云利润（三大云 OP 合计） | 待估（gap，见 §4） | — |
| Models | ≈ 0 至负（OpenAI 亏损 vs Anthropic 调整后打平） | [E] |
| Apps | 小，多数未盈利 | [U] |

## 2. 资金流与三个结构性观察（事实，非判断）

1. **循环性**：模型层最大的"支出"是 compute → 成为云厂商收入（MSFT RPO 45% 来自 OpenAI）；同时 OpenAI 的 ARR 里有一部分是客户（如 Cursor 曾年付 $1B+）的支出。上下游互为收入，统一结算要看**层间净现金流**。
2. **资金来源迁移**：NVDA 发债 $24.9B 并与 Apollo/贝莱德/黑石/KKR 等搭建 >$500B 第三方算力融资平台；Oracle 用 bring-your-own-hardware + 客户预付款扩容。算力资金的来源正从「云厂商经营现金流」扩展到「私募信贷/结构化融资」——需求被前置。
3. **FCF 与利润的分裂**：chips 层利润史上最厚（NVDA GM 75%、hynix OPM 76%），infra 层 FCF 却在收缩（AMZN 2026E 转负）。这个分裂由谁买单、能持续多久，是本 map 最核心的问题。

## 3. 判断列（owner 填写）

> 填写时对每条标注：置信度（%）、基准率、什么证据会让你改变判断。

- **Q1 当前最大的单一利润池是哪里？它会停在那里多久？**
  - 我的判断：＿＿＿＿（候选：NVDA / HBM 寡头 / TSMC / 云利润）
- **Q2 Anthropic 调整后盈利 + usage-based API 占 75-85%：模型层盈利是结构性拐点，还是收入跑在成本前面的暂时现象？**
  - 我的判断：＿＿＿＿
- **Q3 私募信贷入场（$500B 平台）会让周期更长还是让崩塌更陡？**
  - 我的判断：＿＿＿＿
- **Q4 哪一层的利润率最先被竞争/资本反应消灭？（提示：Week 2 的 Constraint→Rent、Week 4 的 capital response 会回到这里）**
  - 我的判断：＿＿＿＿

## 4. 缺口清单（决定 MS&E435 #1 怎么看）

1. 三大云（AWS/Azure/GCP）合计年化 OP 是多少？→ 决定 infra 层利润池与 chips 层的相对大小。**这是本 map 最大的数字缺口。**
2. NVDA +117% 里的 H20 基数效应到底多大？剔除后真实需求增速？
3. hynix 42% vs 76% OPM 的口径冲突——需回原财报核对（含非经常项拆分）。
4. OpenAI「调整后」亏损 vs booked 亏损的口径差。
5. 观看 MS&E435 #1 时只带三个问题：**What changed? What is scarce? Who captures?** —— 用上面的缺口校准答案，而不是泛泛看课。

## 5. Decision Rep（本周必交）

```
判断: ＿＿＿＿（一个 AI value-pool 判断，必须可证伪）
置信度: ＿＿%
基准率: ＿＿＿＿（历史上类似判断的基准）
可证伪条件: 若 ＿＿（具体指标）在 ＿＿（时间窗）内 达到/跌破 ＿＿（阈值），则判断错误
结算日: ＿＿＿＿
记录日: 2026-09-04
```

候选判断（供参考，二选一或自拟）：
- A. 「未来 4 个季度（至 2027Q2），chips 层年化 OP 增速将降至 <30%，利润池占比开始向 infra/models 层迁移」
- B. 「四大 CSP 2027 capex 合计 ≥ $900B（继续扩张），且 AMZN FCF 在 2027 内回正」

## 6. 数据附录

- 检索时间：2026-09-04（session 内），搜索结果页面标注 2026-09-07 抓取缓存
- 主要来源：NVIDIA IR 官方新闻稿（Q2 FY27）、TSMC 月度披露、四大 CSP 财报/指引（经 S&P/TrendForce/华泰汇总）、Reuters/Bloomberg（OpenAI/Anthropic run-rate）、各公司财报（VRT/ETN/SKHY 经聚合与媒体）
- 已知冲突：SK hynix OPM（76% vs 42%）；OpenAI 亏损额（经营亏损 $20.9B vs 净亏损 $38.5B，口径不同）；Cursor ARR（$2B vs $4B，时点不同）
- 未验证：所有 [E] 级数字；Apps 层利润总额；三大云合计 OP
