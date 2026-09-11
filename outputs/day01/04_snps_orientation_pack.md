# SNPS Orientation Pack — Day 1

- **解锁条件**: Part A 闭卷已提交（2026-09-07）
- **本文件的边界**: 只提供事实、时间轴、业务结构、术语表、争议数据。
  **不含 thesis、不含 recommendation、不含估值判断、不含对你闭卷答案的评判。**
- **抓取时间**: 2026-09-07 | **口径**: FY2025 10-K（filed 2025-12-22）+ FY2026 Q3（reported 2026-08-26）
- **注意**: SNPS 财年截至 10 月 31 日。FY2026 Q3 = 截至 2026-07-31 的季度。

---

## 栏目图例

| 标记 | 含义 |
|---|---|
| `[S]` | 事实 — 财报/官方披露可核 |
| `[M]` | Management claim — 管理层说法，未经独立验证 |
| `[E]` | Analyst inference — 卖方/媒体/第三方推断 |

---

## 1. 收入结构（三种口径并存，别混用）

SNPS 同时用**两套完全不同的切法**披露收入。这是读这家公司最容易搞混的地方。

### 切法一：按 segment（业务）

| Segment | FY2025 | YoY | FY26 Q3 | YoY | 占比 |
|---|---|---|---|---|---|
| Design Automation | $5,302.4M | +26% | $2,003M | +52.7% | 80.9% |
| Design IP | $1,751.8M | **−8%** | $473.8M | +10.8% | 19.1% |
| **Total** | **$7,054.2M** | **+15%** | **$2,477M** | **+42.4%** | 100% |

`[S]` Design Automation 内含：EDA 软件、验证硬件、**Ansys 的 simulation & analysis (S&A)**、silicon lifecycle management。
`[S]` FY26 Q3 该 segment +52.7%，但**其中 EDA 本身只 +8.5%**——差额主要由 Ansys 并表贡献（约 $711M）。
`[S]` Design IP FY2025 下滑 8%，10-K 归因于客户 IP "drawdown" 时点的自然波动。FY26 Q3 恢复同比增长。

### 切法二：按收入确认方式（会计）

| 类型 | FY2025 | 占比 | FY26 Q3 | YoY |
|---|---|---|---|---|
| Time-based products | $3,489.6M | 49% | $1,000M | +12.4% |
| Upfront products | $2,010.6M | 29% | $665.2M | +28.8% |
| Maintenance & service | ~$1,554M | 22% | $808.8M | **+144.4%** |

`[S]` **Time-based (TSL)**：按 license 期间**或**客户付款进度确认，取**较晚**者。
`[S]` **Upfront (Term License)**：软件发运完成后**全额**确认，条件是至少 75% license fee 在发运后一年内支付。
`[S]` Maintenance & service：维护期内确认 + 专业服务/培训费。
`[S]` Maintenance +144% 的量级跳升与 Ansys 并表同期发生。

`[S]` 10-K 明确列出的收入形式还包括：**perpetual licenses、hardware product sales、royalties**。
`[S]` 10-K 原文表述：客户就**广泛产品组合的总合同价值**谈判，而非按单位定价（"customers negotiate total arrangement value across broad product portfolios rather than unit pricing"）。
`[S]` 造成期间波动的三个披露因素：**FSA drawdown 时点、IP 产品时点、硬件销售**。

---

## 2. 成本与利润结构

| 项目 | FY2025 | FY2024 |
|---|---|---|
| Revenue | $7,054.2M | $6,127.4M |
| Cost of revenue | $1,623.5M | $1,245.3M |
| Operating expenses | $4,515.7M | $3,526.4M |
| **Operating income** | **$914.9M** | **$1,355.7M** |
| Net income (continuing ops) | $1,336.1M | $1,441.7M |
| R&D | ~$2,500M（≈35% of revenue） | — |
| Long-term debt | **$13.4B** | **$15.6M** |
| Interest expense | **$447M** | $37M |

`[S]` FY2025 GAAP 营业利润**同比下降**（$1,355.7M → $914.9M），尽管收入 +15%。
`[S]` 长期债务从 1,560 万美元跳到 134 亿美元；利息费用从 3,700 万跳到 4.47 亿。
`[S]` FY26 Q3 non-GAAP 营业利润率 41.6%；分部调整后：Design Automation 45.2%（去年 44.5%），Design IP 26.5%（去年 20.1%）。
`[S]` FY26 Q3 总债务约 $100 亿（提前偿还了部分 term loan）；现金及短期投资 $36.1 亿。
`[S]` FY26 Q3 FCF $746M；前九个月经营现金流 $23.0 亿。
`[S]` TTM 毛利率 72.35%；TTM 净利润 $10.77 亿；TTM FCF $27.48 亿。

---

## 3. 客户与地区

`[S]` 10-K 客户描述：设计集成电路与先进计算系统的**半导体与电子公司**；覆盖 digital / custom / FPGA 设计流程。

FY2025 全年地区占比 `[E]`（第三方汇总，与下方季度数据口径不同）：
北美 45% · 中国 12% · 欧洲 13% · 韩国 13% · 其他 18%

FY2025 Q4 单季地区 `[S]`：
北美 $1.05B（46%）· 欧洲 $361.4M（16%）· 韩国 $236.9M · 中国 $235.6M · 其他 $373.7M

`[S]` FY2025 中国收入 $814M，上年接近 $10 亿（下滑）。
`[S]` 10-K 表述：中国客户占业务的**实质性部分**（material portion）。

---

## 4. 时间轴（近期结构性事件）

| 日期 | 事件 | 等级 |
|---|---|---|
| 2025-05-29 | BIS 发出对华 EDA 软件出口许可要求 | `[S]` |
| 2025-07-02 | 上述许可要求被撤销 | `[S]` |
| 2025-07（前后） | Ansys 收购完成 | `[S]` |
| 2025-10-31 | FY2025 结束 | `[S]` |
| 2025-12-22 | FY2025 10-K 提交 | `[S]` |
| 2026-08-26 | FY2026 Q3 业绩发布；Ansys 并表满一年 | `[S]` |
| 2026-12-02（估） | 下一次业绩发布 | `[E]` |

---

## 5. Ansys 后的结构（只记结构，不评协同）

`[S]` Ansys 产品被并入 **Design Automation** segment，不单列。
`[S]` FY26 Q3 Ansys 贡献约 **$711M**（占该季总收入约 28.7%）。
`[S]` FY2025 Q4 Ansys 贡献占总收入 29.6%。
`[S]` FY2026 全年 Ansys 预计贡献约 **$29.8 亿**（指引，上调 $20M）。
`[S]` 分工描述：Synopsys 面向 **silicon**（芯片本身），Ansys 面向 **system**（物理、热、结构分析）。
`[S]` 2026 年推出首个联合产品 **Multiphysics Fusion**。
`[M]` 早期客户验证显示 design closure 快至 10 倍、runtime 快 3 倍。
`[M]` 管理层预期这类 add-on 能力从 **FY2027** 开始贡献 EDA 增长。
`[M]` Ansys 成本协同"进度超前"（ahead of schedule）。
`[S]` FY26 Q4 计划进行重组，将产生"significant charges"。

---

## 6. 竞争对手（10-K 与第三方表述）

`[S]` 10-K/公开表述中的 EDA 竞争者：**Cadence Design Systems**、**Siemens EDA（原 Mentor Graphics）**。
`[E]` 第三方 peer 列表（含非 EDA 的软件类可比公司）：Cadence、Autodesk、Aspen Technology、Adobe、Roper、Salesforce、Workday、Intuit。
`[S]` 10-K 关于转换成本的原文口径：客户就广泛产品组合、扩展 license 用量、未来采购权进行**多产品打包**谈判，使替换代价高昂（"making displacement costly"）。

> 注意：上面最后一条是 10-K 的**自我表述**，属于公司披露内容；它是不是真实的 barrier，是 Day 2 的练习内容，本 pack 不作判断。

---

## 7. 订单与前瞻（事实与指引分开）

`[S]` FY26 Q3 backlog **$10.9B**。
`[S]` Backlog 环比小幅下降，与一项 divestiture 相关。
`[S]` FY2026 指引：收入 $9.69–9.74B（中点 $9.715B）· non-GAAP EPS $15.04–15.10 · non-GAAP OPM ~41.5% · 经营现金流 ~$28 亿 · capex ~$2.25 亿 · FCF ~$26 亿。
`[S]` FY26 Q4 指引：收入 $2.53–2.58B · non-GAAP EPS $4.10–4.16。
`[S]` 指引前提：**假设出口管制与 Entity List 限制无进一步变化**。
`[M]` 管理层预期 Q4 及全年 EDA 实现**双位数有机增长**。
`[M]` 30 多个客户正在试用 agentic AI 平台，设计目标是自动化工程流程**同时提高对底层 EDA 工具的使用量**。
`[M]` die-to-die 业务同比"on pace to double"，累计超过 100 个 design win。
`[M]` CEO 归因：AI 带来"前所未有的复杂度"，推动对 silicon IP 与工程解决方案的需求。

---

## 8. 术语表

| 术语 | 含义 |
|---|---|
| **TSL** (Technology Subscription License) | 时间型订阅 license，对应 time-based 收入 |
| **Term License** | 定期 license，满足付款条件后**前置全额**确认，对应 upfront 收入 |
| **FSA drawdown** | Flexible Spending Account：客户预付额度池，按实际取用转为收入；取用时点造成期间波动 |
| **IP drawdown** | 客户实际调用已授权 IP 块的时点 |
| **die-to-die IP** | 多 die 封装中芯片间互连的接口 IP |
| **hardware-assisted verification** | 用专用硬件（emulation/prototyping）加速验证，属硬件销售 |
| **SLM** (Silicon Lifecycle Management) | 芯片投产后的监测与良率分析（Yield Explorer、Silicon.da、PVT IP 等） |
| **S&A** (Simulation & Analysis) | Ansys 带来的仿真分析业务（结构、热、CFD） |
| **Multiphysics Fusion** | 首个 Synopsys-Ansys 联合产品 |

---

## 9. 争议 / 冲突数据（并列保留，不择一）

| 项目 | 来源 A | 来源 B | 状态 |
|---|---|---|---|
| FY2025 北美收入占比 | 45%（全年，第三方汇总）`[E]` | 46%（Q4 单季）`[S]` | 口径不同（全年 vs 单季），非矛盾 |
| Maintenance & service 占比 | FY2025 22% | FY26 Q3 32.6% | 结构变化，需拆 Ansys 影响 `gap` |
| Design IP 走势 | FY2025 −8% | FY26 Q3 +10.8% | 反转已发生，原因未独立验证 `gap` |
| TTM 净利润 vs FY2025 | TTM $1,077M `[E]` | FY2025 continuing $1,336M `[S]` | 口径含重组/利息，需回原表 |

**未验证缺口 `gap`**：
1. 各收入类型在 **segment 之间**如何分布（time-based 里多少属于 IP？披露未交叉列示）
2. Royalty 收入的**绝对金额**（10-K 提及形式，未见单列金额）
3. 客户集中度（前十大客户占比）
4. FSA 余额与 drawdown 节奏
5. EDA 有机增长的季度序列（剔除 Ansys 后）

---

## 10. 对照检查清单 — 你自己去看，我不给答案

回到 `00_closed_book_FIRST.md` 的七个子问题，本 pack 中对应的**证据位置**如下。
**逐条对照，把差异写进 `01_snps_company_map_v0.md` 的「10-K 校正」列，并保留你的原始答案。**

| 你的子问题 | 去看本文件哪一节 |
|---|---|
| 客户是谁？ | §3 客户与地区、§6 竞争对手 |
| 客户不买会怎样？ | §6 最后一条（注意那是公司自我表述） |
| 收费的计量单位是什么？ | §1 切法二全部 + §8 术语表（TSL / Term License / FSA / royalty） |
| 收入是一次性还是重复的？ | §1 切法二的三类占比 |
| 谁决定续约？ | §1「总合同价值谈判」那条 + `gap` #3 客户集中度 |
| 主要成本是什么？ | §2 成本结构（注意 R&D 之外还有什么变大了） |
| 钱最终来自产业链哪一段？ | §3 地区分布 + §5 Ansys 的 system 侧 + §7 die-to-die/agentic AI |

对照完成后，Part C 的 `?` 计数应该有一部分能被消掉——但**很可能会新增更多 `?`**。新增的直接进 `03_twenty_unknowns.md`。

---

## 11. Primary source（本 pack 的所有事实应回溯至此）

- Synopsys SEC filings: https://investor.synopsys.com/financials/sec-filings/default.aspx
- FY2026 Q3 官方新闻稿: https://news.synopsys.com/2026-08-26-Synopsys-Posts-Financial-Results-for-Third-Quarter-Fiscal-Year-2026

> 本 pack 中标 `[E]` 的条目来自第三方汇总，**未回溯到 filing 原文**。
> 若某条 `[E]` 将进入你的 model 关键假设，必须先自己回原文核对再使用。
