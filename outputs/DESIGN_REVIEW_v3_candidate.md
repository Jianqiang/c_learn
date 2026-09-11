# Design Review — v3 候选方案（"Bootcamp: Build the Map → Live Investing: Build the Skill"）

**日期**：2026-09-11
**输入**：owner 转发的外部对话（另一 AI 对当前 curriculum 的重构建议）
**目的**：在采纳前做核实与压力测试，而非course summary，属于系统设计类产物，比照 `outputs/DESIGN_REVIEW_v2.md` 的定位保存
**结论先行**：内容取舍（新增 Capital Allocation、砍 MS&E435/多余 strategy papers 到 Appendix）方向正确，但发现 **1 处事实错误 + 2 处会架空已验证有效设计的结构性倒退 + 2 处校准风险**。建议先解决这 5 项再落地，不宜直接照搬执行。

---

## A. 事实错误（blocking）：Jacobides 2006 被误标为已完成

v3 候选文档「已完成｜约15h」清单第 4 项声称：

> Michael G. Jacobides, Thorbjørn Knudsen & Mie Augier — *Benefiting from Innovation* … **状态：DONE**

但系统实际记录（`data/module_progress.yaml` + `AGENTS.md` §1 + `content/bootcamp_modules.yaml` M1.materials）显示：

| 来源 | Jacobides 2006 状态 |
|---|---|
| `data/module_progress.yaml`（唯一权威 log） | 未出现，log 只有 Teece+B&S(3.5h, 09-08) 与 AI rent memo 应用(1.5h, 09-09) |
| `AGENTS.md` §1「M1 材料进度」 | `Jacobides 2006 ⬜` |
| `content/bootcamp_modules.yaml` materials | `status: pending` |
| `done_so_far` 清单 | 只列 Teece 三概念 + Baldwin 概念，未提 Jacobides |

**影响**：v3 文档据此推出"M0 只剩 Henderson & Clark 2-2.5h"，这个数字是错的。若 Jacobides 2006 仍要保留为 core，真实剩余是 H&C(2-2.5h) + Jacobides 2006(2-3h) ≈ 4.5-5.5h，M0 总时长应为 ~20-21h 而非 17-18h。

（附带记账问题，非 v3 的错，是系统自身欠账：Baldwin 的阅读时间从未 log 过，`module_progress.yaml` 的 5.0h 因此本身就低估了实际投入——这也是为什么"已投入 15h"这类口头估计和系统 log 对不上，两边都不完全可信，需要重新对一次账。）

---

## B. 结构性倒退：g1/g2/g3 三闸门在 module 层面被架空

`AGENTS.md` §1 明确记录这三个闸门"脚本已强制执行，实测有效"：

| 闸门 | 规则 |
|---|---|
| g1 | 材料时间 ≤ module 总时间 50% |
| g2 | module 以「闭卷跑通框架 + 匿名 transfer test」出口，不以「读完」出口 |
| g3 | 每 module ≥3 条可结算预测，forecast linter 强制 |

v3 候选文档在 Phase A 层面写了一句原则："75%-80% Knowledge + 20%-25% Retrieval/Quiz/Micro Exercise"，但**逐 module 拆解后这个比例完全没有兑现**：

| Module | 总时长 | 材料时长 | 应用/练习时长 | 应用占比 | 是否满足 g1(应用≥50%) |
|---|---|---|---|---|---|
| M0 | 17-18h | ~17-17.5h | 30-45min | ~4% | ✗ 严重违反 |
| M1 (Accounting) | 6-7h | 6-7h | 0（视频自带 post-class test，非 owner 产出） | ~0% | ✗ 违反 |
| M2 | 9-10h | 8.5-9.5h | 45min | ~8% | ✗ 违反 |
| M3 | 2-2.5h | 1.5-2h | 30min | ~20% | ✗ 违反 |
| M4 | 8-10h | 8-10h | 未提及 | ~0% | ✗ 违反 |
| M5 | 9-11h | 9-11h | 未提及 | ~0% | ✗ 违反 |
| M6 | 7-9h | 7-9h | 未提及 | ~0% | ✗ 违反 |
| M7 | 6-7h | 5.5-6.5h | "10 个可结算预测"（与阅读时间混算，未拆分） | 不明确 | 存疑 |

且**没有一个 module 写出闭卷出口考试（g2）或≥3条可结算预测（g3）的具体安排**——只在 M7 提了一句"10 个可结算概率预测"，且是全 bootcamp 一次性的，不是逐 module 的。

这不是小问题：MEMO（`outputs/MEMO_learning_progress_and_design_lessons.md` §3.1/§3.6/§4.1）把这三个闸门定性为 v1→v2 迭代中"实测有效"的核心防线。v3 把总时长做得更诚实（72-78h vs v1 的 20h），但如果应用占比重新塌陷到个位数，本质上是**在总量层面修正了 v1 的错误，却在结构层面重演了 v1 的错误**（材料挤掉应用）——只是这次数字看起来更体面。

---

## C. 对照案例（反测）体系整体消失

当前系统的核心检验设计——"框架是否依赖你的 edge"——依赖三个具体对照标的 + 本地数据 + PIT 用法铁律：

- M1(旧)/M0(新)：深南电路 002916.SZ — 检验"HBM/GPU/光模块通常只是 specialized"这条判断
- M2(旧)：立讯精密 002475.SZ — 商誉/摊销/在建工程转固，与 SNPS 配对辨析会计人为 vs 真实经济差异
- M4(旧)：中国船舶 600150.SH — 供给刚性的压力测试
- 外加 17 份带时间戳的 PIT memo（`fin/co_investor/output/chatgpt_cases_archive/`）与严格的"先闭卷、后对照"使用顺序

v3 候选文档里完全没有出现这套机制，只用"熟悉公司""陌生系统"这类泛化措辞做 micro exercise。`AGENTS.md` §1 明确写："**这个检验不能省**。在自己有 edge 的领域学新框架，最容易发生的是用新词汇包装旧判断。"——v3 如果照搬，等于把这条防线撤了。

---

## D. Module 编号冲突（数据完整性风险，技术性，非内容判断）

v3 候选文档把 M1-M7 重新定义为完全不同的内容（M1=Financial Accounting，M2=Financial Statement→FCF……），但 `data/module_progress.yaml` 里已有一个 key 叫 `M1`，当前记录着 Teece/B&S/Baldwin 相关的 5.0h。若直接照搬新编号，这 5 小时会在系统里被误记成"Financial Accounting"模块的投入，历史记录被污染，`modules.py status` 的累计工时也会算错。

v3 文档本身用的是 M0-M7（把旧 M1 内容挪到新 M0），这个编号方向是对的，但**需要在落地时显式把 `module_progress.yaml` 里的 `M1` key 迁移为 `M0`**，而不是简单覆盖 manifest 文件。这一步我可以直接处理，不需要 owner 决策。

---

## E. 时间估算的校准方法风险

`MEMO_learning_progress_and_design_lessons.md` §5 第 1 条明确写："**时间估算必须先用 1-2 篇代表性材料实测校准，再推算全课时长，不要用页数/字数线性估算**"——这是 v1 付出 4.5-6 倍代价换来的规则。

owner 目前唯一被实测校准过的阅读速度，是 30-40 页学术论文的精读速度：Teece+B&S 单独就要 3-4 小时。v3 候选文档里几个书籍/章节级别的估时并未用这个基准校准：

| 材料 | v3 估时 | 风险点 |
|---|---|---|
| Penman 选读（viewing business/profitability/growth/forecasting/accounting quality 五个主题） | 5-6h | 覆盖一本 1000+ 页教科书的 5 个大主题，按论文精读速度换算明显偏低 |
| Valentine 选读 Ch.7-10 + Ch.17-20（共 8 章） | 5-7h | 约 40-50 分钟/章，专业书籍精读通常更慢 |
| Superforecasting"快速/选择性读" | 4-5h | ~340 页书，即便跳读也偏紧 |
| Capital Returns"建议基本读完" | 6-8h | 400+ 页文集，偏紧 |

不是说这些材料不能用，而是**不应该直接采纳外部对话给出的估时**，应先读一个代表性章节实测校准，再定总预算——这正是 v1 犯过的错。

---

## F.（次要，非阻塞）M6 Equity Research OS 的边际价值待确认

Valentine 的书是 v3 里唯一"当前系统完全没有"的新增内容，方向合理（owner 的链条确实缺"专业研究流程"这一层）。但 owner 已有一套相当成熟的自建研究 pipeline（PITDataService / wiki-ingest / bounded_evidence_pass / audit_forecast_decision 等）。建议明确这本书要解决当前系统里的哪个**具体**缺口，而非泛泛"值得学"——否则违反 M2 已确立的"缺口驱动 JIT 读法"原则（`bootcamp_modules.yaml` M2.reading_mode）。

---

## 总体建议

1. **先纠正 A**：明确 Jacobides 2006 是保留 core（M0 预算上修至 ~20-21h）还是正式砍掉（需要 owner 主动决定，而非因为外部对话的误判而被动带过）。
2. **必须解决 B**：v3 若要采纳，每个 module 都要补上明确的闭卷出口 + 匿名 transfer test + ≥3 条可结算预测的时间块，重新核算总时长（会比 72-78h 更长，但这是"诚实"这个词在 v3 文档里反复强调的真正含义）。
3. **建议保留 C**：把深南电路/立讯精密/中国船舶三个对照案例映射到新的 module 编号上（M0→深南电路，新 M2→立讯精密，新 M4→中国船舶），而不是放弃。
4. **D 我可直接处理**：manifest 重编号为 M0-M7 时，同步把 `module_progress.yaml` 的 `M1` key 迁移为 `M0`，保留历史 log。
5. **E 建议**：采用 v3 的内容取舍，但暂不采用其估时；改为"先读一段代表性材料实测校准，再定 module 总预算"，与 M2 当年的处理方式一致。
6. **F 可后置**：M6 保留在 Appendix / 待 M2-M5 跑完后再评估是否需要，不急于纳入 core。
