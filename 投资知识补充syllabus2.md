有必要补，但我会非常克制地补。

你现有 syllabus 已经很好地覆盖了 **AI technical reality、AI economics、valuation、strategy 基础**，而且明确把主轴放在 (B+D+E+F)，并强调 problem-pulls-learning，而不是“修完课程”。 对现在这三个研究方向，最大的缺口不是再学更多 AI，而是补齐下面这条链：

[
\boxed{
Technology
\rightarrow
Industry\ Structure
\rightarrow
Value\ Creation
\rightarrow
Value\ Capture
\rightarrow
Firm\ Capability
\rightarrow
Accounting\ Earnings
\rightarrow
Market\ Expectations
}
]

我会新增大约 **30–45 小时的 targeted syllabus**，然后停止上课，全面转入 case-driven research。

---

# 一、先说结论：真正缺的是四块

| 新增知识                                               | Rent Formation | Capability Revaluation | Hidden AI Earnings |
| -------------------------------------------------- | -------------: | ---------------------: | -----------------: |
| **Industrial Organization / market power**         |            ★★★ |                      ★ |                 ★★ |
| **Bargaining / industry architecture / ecosystem** |            ★★★ |                     ★★ |                 ★★ |
| **Organizational & intangible capital**            |              ★ |                    ★★★ |                 ★★ |
| **Empirical methods / measurement**                |             ★★ |                     ★★ |                ★★★ |

而以下东西**不用明显增加**：

* LLM / Transformer 技术课；
* corporate finance；
* DCF；
* generic strategy；
* startup 方法论；
* 更完整的数学基础课。

你原 syllabus 中的 Expectations Investing、Damodaran、Teece、7 Powers、MS&E435 已经足够作为底座。 

真正应该补的是**理论之间的接口**。

---

# 二、第一条：Rent Formation / Value Migration OS

这是三者中理论要求最高的。

现在我们的直觉版本大致是：

[
Scarcity + Control + Switching\ Cost + Scale + Complementarity
\rightarrow Rent
]

它方向正确，但还缺一个很重要的理论升级：

> **value creation 和 value capture 必须严格分开。**

一家公司的利润，并不只由“它创造多少价值”决定，而取决于它在整个 coalition / value chain 中的 **added value + outside option + bargaining position**。

## 1. 最值得补：Industrial Organization

不用修完整 PhD IO。

我建议直接 selective 看：

### MIT 14.271 Industrial Organization I

MIT 这门课同时处理理论和实证，完整课程包括 competition、market power、dynamic competition、entry、strategic investment 和 online markets。([MIT OpenCourseWare][1])

对你只看：

**Lecture 5–6**
Static Competition / Differentiation

**Lecture 7–8**
Demand, Supply and Market Power

**Lecture 14–15**
Dynamic Competition

**Lecture 16–17**
Entry

**Lecture 18–19**
Strategic Investment

**Lecture 25–26**
Online Markets

大概 12 lectures，1.5×～2× 看。

[MIT 14.271 lecture videos](https://ocw.mit.edu/courses/14-271-industrial-organization-i-fall-2022/video_galleries/lecture-videos/?utm_source=chatgpt.com)

它会让很多我们现在用自然语言讨论的概念变得精确：

[
entry\ deterrence
,\quad
product\ differentiation
,\quad
strategic\ investment
,\quad
market\ power
]

但**不要做 problem sets，不要啃 Tirole 全书**。

如果觉得 14.271 太 academic，MIT 14.27 Economics of Digitization 可以作为更低摩擦版本，内容本来就是用 IO 分析互联网、搜索、广告、platform 等。([MIT OpenCourseWare][2])

---

# 三、Rent OS 最重要的新增论文，不是 Porter

我会新增下面 **5 篇核心论文**。

## ① Brandenburger & Stuart 1996

**Value-Based Business Strategy**

我认为这是整个 Rent OS 最应该新增的一篇。

它正式定义：

[
Value\ Created
]

和

[
Added\ Value
]

并指出 firm's added value 在一定条件下构成它能够 capture 的价值上限。核心来自 cooperative game theory。([Wiley Online Library][3])

这会把我们的：

> “谁控制 bottleneck？”

升级为：

> **如果删除这个 player，整个 coalition 的总价值下降多少？**

即：

[
Added\ Value_i
==============

V(N)-V(N-i)
]

这是 Rent OS 非常强的数学语言。

[Value-Based Business Strategy](https://business.columbia.edu/faculty/research/value-based-business-strategy?utm_source=chatgpt.com)

---

## ② Teece 1986

已经在 syllabus 中，继续保留。

它回答：

> 为什么创新者创造技术，却未必获得 rent？

核心三个对象：

[
Appropriability
+
Complementary\ Assets
+
Dominant\ Design
]

尤其是 complementary asset owner 可能拿走技术创新的大部分利润。([科学直通车][4])

---

## ③ Jacobides, Knudsen & Augier 2006

**Benefiting from Innovation**

这是我认为过去 syllabus 中真正遗漏的重要论文。

Teece 主要看 firm + complementary assets。

Jacobides 往前推进一步：

[
Firm
\rightarrow
Industry\ Architecture
]

产业本身存在一套：

> 谁做什么、谁依赖谁、谁能替代谁、谁拿利润

的 architecture。

他们明确讨论：

* complementarity；
* mobility；
* bargaining position；
* bottleneck；
* architectural advantage。

也就是说：

> 企业甚至不一定需要 vertical integration，也可以通过塑造 architecture 拿走 rent。

([科学直通车][5])

这篇与我们的 **Bottleneck Migration** 几乎直接对接。

---

## ④ Adner 2017

**Ecosystem as Structure**

它最大的价值是防止把“ecosystem”当 PPT buzzword。

Adner 把 ecosystem 定义成一组相互依赖的 actors / activities，并明确讨论 alignment structure。([Sage Journals][6])

它适合回答：

> Nvidia CUDA、TSMC、AWS、Apple ecosystem、AI agent ecosystem 到底结构差异在哪里？

---

## ⑤ Peteraf 1993

**The Cornerstones of Competitive Advantage**

比简单 VRIN 更适合 Rent OS。

她把 sustained rent 压成四个条件：

* resource heterogeneity；
* ex-post limits to competition；
* imperfect mobility；
* ex-ante limits to competition。([Wiley Online Library][7])

尤其最后一点很重要。

如果一个资产的价值**在购买时所有人已经知道**：

[
Price\ of\ resource
\approx
PV(rent)
]

那么竞争优势可能属于这个资产，却不属于股东。

这其实直接通向投资。

---

# 四、这样 Rent Formation OS 会升级成什么？

我现在会把它写成：

[
\boxed{
Rent_i
======

Created\ Surplus
\times
Capture\ Share_i
\times
Persistence
}
]

而：

[
Capture\ Share
==============

f(
Added\ Value,
Alternatives,
Mobility,
Control,
Asset\ Specificity,
Architecture
)
]

Persistence：

# [

f(
Entry,
Imitation,
Substitution,
Scale,
Network\ Effect,
Learning,
Switching\ Cost
)
]

技术变化真正做的是改变：

[
\boxed{
Complementarity
+
Substitutability
+
Mobility
+
Outside\ Options
}
]

因此才产生：

[
Bottleneck\ Migration
\rightarrow
Rent\ Migration
]

这会比现在的直觉模型强很多。

---

# 五、第二条：Capability Revaluation → Rent Revaluation

这里真正缺的不是传统 strategy，而是：

## **Organizational capital + intangible capital + real options**

我们以前常说：

> “中兴原来有这些能力。”

但“capability”如果不 operationalize，很容易沦为事后故事。

必须问：

[
Capability =
?
]

例如：

* 人才；
* engineering routines；
* customer relationships；
* manufacturing know-how；
* distribution；
* proprietary data；
* supply-chain coordination；
* organizational processes；
* existing installed base。

这些很多不会出现在 balance sheet。

---

# 六、Capability 研究最值得补的四组论文

## ① Organizational capital

### Lev & Radhakrishnan

他们尝试直接测量 firm-specific organizational capital，并发现它能够解释企业市场价值，而且市场可能不能充分反映 organization capital 的价值。([NBER][8])

这是 Capability Revaluation hypothesis 的学术近亲。

### Eisfeldt & Papanikolaou

他们把 organization capital 看作：

> firm-specific、部分 embodied in key talent 的 production factor。

并研究它对应的 shareholder claims 与 risk。([Wiley Online Library][9])

不用啃模型，理解概念即可。

---

# 七、第二个必须补：Intangible accounting

这对科技股尤其重要。

传统 accounting：

[
R&D,\ SG&A
\rightarrow Expense
]

但经济意义上：

[
部分R&D/SG&A
\rightarrow Investment
]

Corrado、Hulten、Sichel 的经典框架明确提出：

> 只要支出的目的主要是增加未来而不是当前产出，从经济意义上就应视作 investment。([美联储][10])

再读：

### Peters & Taylor 2017

把：

[
Physical\ Capital + Intangible\ Capital
]

组合成 total capital，并构造 total q。([科学直通车][11])

### Enache & Srivastava

研究 SG&A 中究竟多少实际上属于 organizational/intangible investment；区分这些项目以后，对未来 earnings 和 returns 的预测改善。([PubsOnline][12])

这会直接改善你看：

* PDD；
* Amazon；
* 腾讯；
* AI software；
* R&D-heavy industrial companies

时的 accounting intuition。

---

# 八、我尤其建议加一篇以前没讨论过的论文

## Kogut & Kulatilaka — Capabilities as Real Options

这篇和你的 Capability Revaluation 框架高度契合。

他们提出：

[
Capability
\approx
Real\ Option
]

企业过去建设某种 capability：

当时可能没有明显现金流。

但新的 market opportunity 出现以后：

[
Option\ goes\ into\ the\ money
]

那些**已经拥有相关 capability 的企业**，可以比别人更快、更低成本地响应新机会。([PubsOnline][13])

这实际上就是：

[
\boxed{
Capability\ Revaluation
=======================

Real\ Option\ Repricing
}
]

我觉得这是你这个 hypothesis 目前缺失的一个非常漂亮的理论基石。

不用系统学 Black-Scholes。

理解：

* uncertainty；
* irreversibility；
* flexibility；
* exercise cost；
* underlying opportunity；
* time to build capability

就够了。

---

# 九、第三条：Hidden AI Earnings Elasticity

这个框架最大的风险不是理论不漂亮，而是：

> **特别容易产生 false positives。**

“公司用了很多 AI”

[
\not\Rightarrow
]

“利润对 AI 高弹性”

更不等于：

[
\text{stock undervalued}
]

所以我会把它拆成五层。

[
AI\ Shock
]

↓

### 1. Exposure

AI 是否改变该公司的：

* product demand；
* input cost；
* labor productivity；
* capital productivity？

↓

### 2. Adoption

企业有没有能力真正利用？

↓

### 3. Economic pass-through

收益是：

* 企业拿走；
* 客户拿走；
* 员工拿走；
* supplier 拿走；
* competitor 通过降价拿走？

↓

### 4. Earnings transmission

[
Revenue
,\ Margin
,\ Working\ Capital
,\ Capex
,\ FCF
]

到底怎么变？

↓

### 5. Expectations

市场已经 price in 多少？

---

# 十、这里最值得新增的是 firm-level AI empirical literature

## ★ Tania Babina 2026 review

这是现在非常适合你的一篇。

**Understanding Firms' AI Efforts and Their Economic Impact**

它特别强调：

> 不同 AI measurement 实际上测的是完全不同的东西。

例如：

* invention；
* actual use；
* internal capability building；
* outsourcing；
* investor perception。

混为一谈会得到完全不同的结论。([NBER][14])

这几乎应该成为 **Hidden AI Earnings Elasticity measurement manual**。

---

## Babina et al. 2024

**Artificial Intelligence, Firm Growth, and Product Innovation**

他们用 employee resumes / job data 构造 firm-level AI investment measure。

结果发现 AI-investing firms 后续：

* sales growth 更高；
* employment growth 更高；
* valuation 更高；

主要渠道是 **product innovation**，而且效果集中在较大的企业。([DOI][15])

特别重要的是：

> AI signal 不是只有 earnings call 说了几次“AI”。

可以观察：

[
people
+
jobs
+
products
+
patents
+
organization
]

---

## AI jobs / organization literature

Babina 等也发现企业 AI investment 与 workforce reorganization 同时发生。([NBER][16])

Alekseeva 等最新研究甚至发现 AI adoption 与 managerial vacancies 和所需 managerial skills 的结构变化相关。([Wiley Online Library][17])

因此：

> **organizational redesign 本身可能是 AI capability becoming real 的领先指标。**

这个我认为很值得你后面做 signal research。

---

# 十一、再加一个 optional：Production Networks

如果研究：

* Nvidia → networking；
* Google TPU → Broadcom/Marvell；
* inference → memory；
* AI servers → power/cooling；
* Apple AI → supply chain；

实际上是在研究 shock propagation。

可以 skim：

### Acemoglu et al. — Network Origins of Aggregate Fluctuations

核心不是 macro，而是：

> shock 会沿 input-output network 产生直接和高阶 cascade effects。([DOI][18])

于是 Hidden AI Earnings 的搜索对象可以变成：

[
First-order\ exposure
+
Second-order\ exposure
+
Network\ centrality
]

不需要读完整数学证明。

---

# 十二、最后还要补一点 empirical methods，但一定不要读成 econometrics PhD

你以后很可能做这种问题：

> AI hiring 增加后，两年以后 margin 是否提升？

> Capability revaluation signal 出现后，股票是否 outperform？

> 某种 bottleneck shift 是否导致某环节利润份额上升？

这些都是典型 panel / event-study 问题。

因此只补：

### Causal Inference: The Mixtape

读：

* regression intuition；
* panel data；
* difference-in-differences；
* event studies；
* synthetic control。

它的目录本身就覆盖这些工具。([Stata][19])

或者直接免费读：

### The Effect

重点 **Event Studies**。([The Effect][20])

目标不是发表 economics paper。

只是培养一个 reflex：

> correlation、selection、reverse causality、look-ahead bias 到底在哪里？

约 **5–8h 足够**。

---

# 十三、最终新增 syllabus：我会严格控制在这些

### Tier 1 — 必须

1. **MIT 14.271 selective**：8–12h
2. **Brandenburger & Stuart 1996**
3. **Jacobides et al. 2006**
4. **Peteraf 1993**
5. **Organizational capital：Lev / Eisfeldt selective**
6. **Kogut & Kulatilaka — Capabilities as Real Options**
7. **Babina 2026 review**
8. **Babina et al. 2024**
9. **Causal inference / event study selective**

### Tier 2 — 按问题调用

* Grossman & Hart — property rights；
* Adner — ecosystems；
* Rochet & Tirole — two-sided platforms；
* intangible accounting papers；
* production network；
* superstar-firm / markup literature。

也就是说只新增大概：

[
\boxed{30-45h}
]

之后**禁止继续扩 syllabus**。

---

# 十四、工具：NotebookLM / ima / Codex，我认为都有必要，但角色完全不同

这里我会比较明确：

## 1. NotebookLM：非常值得用

顺便更新一下名称：Google 在 **2026 年 7 月已经把 NotebookLM 更名为 Gemini Notebook**。产品仍然延续原本 source-grounded notebook 的定位。([blog.google][21])

现在它已经远不只是“PDF 聊天”。

Google 今年加入了：

* source-grounded Q&A；
* web source discovery；
* advanced reasoning；
* cloud code execution；
* chart / spreadsheet / slide generation。([blog.google][22])

不同套餐单 notebook 可容纳最高数百个 sources；官方当前最高档可到 600 sources。([Google 帮助][23])

### 我会建三个 permanent notebooks

而不是一家公司一个。

**Notebook A**

> Rent Formation / IO / Strategy

放：

Teece
Brandenburger
Peteraf
Jacobides
Adner
IO notes
historical cases

**Notebook B**

> Organizational Capability / Intangible Capital

放：

Lev
Eisfeldt
Brynjolfsson
Kogut
Babina
company capability cases

**Notebook C**

> AI Economic Transmission

放：

AI economics papers
METR
Babina
earnings/productivity papers
AI infrastructure economics

它最适合：

> “这 40 篇论文对 bottleneck 的定义有什么共同点和冲突？”

而不是：

> “帮我判断买不买中兴。”

这是一个巨大的 distinction。

---

# 十五、ima：有价值，但我不会与 Gemini Notebook 重复建设

如果你说的是腾讯 **ima**，它目前核心仍然是知识库 + 搜读写，而且尤其适合：

* 微信文件；
* 公众号文章；
* 中文网页；
* 本地 PDF；
* 图片/录音；
* 中文知识沉淀。([App Store][24])

所以我会给它非常明确的 role：

[
\boxed{
ima
===

China\ / WeChat\ / fragmented\ source\ ingestion
}
]

例如研究：

* 中兴；
* 立讯；
* 寒武纪；
* A股 AI supply chain；
* 国内基金经理；
* 微信公众号专家资料

ima 很适合做资料池。

而 Gemini Notebook 做：

[
\boxed{
Academic + Global + Canonical\ Corpus
}
]

不要把同样 200 篇 PDF 两边各存一次。

---

# 十六、Codex：我认为长期价值反而最大

但不是让 Codex：

> “自动研究然后自动选股票”。

而是把**重复劳动工程化**。

现在 Codex 已经支持 Skills，将 instructions、scripts、resources 打包成可重复 workflow，并可处理不仅限于 coding 的 research / analyst workflow。([OpenAI][25])

我会直接建立一个：

# `research-os`

而不是继续堆 prompt。

大概这样：

```text
research-os/

  frameworks/
    rent_formation.md
    capability_revaluation.md
    ai_earnings_elasticity.md

  schemas/
    company.yaml
    capability.yaml
    rent_map.yaml
    catalyst.yaml
    forecast.yaml

  data/
    filings/
    transcripts/
    jobs/
    patents/
    prices/
    industry/

  pipelines/
    transcript_diff
    job_signal
    capability_signal
    earnings_revision
    event_study
    valuation

  cases/
    nvidia/
    amazon/
    zte/
    luxshare/
    pdd/
```

---

# 十七、让 Codex 做哪些工作？

例如每次研究一家公司自动生成：

### Capability ledger

```text
Capability
Evidence
First observed
Strength
Replicability
Redeployability
Complementary assets
Monetization evidence
```

---

### Rent map

```text
Actor
Contribution
Alternative suppliers
Alternative customers
Switching cost
Asset specificity
Bargaining power
Current rent
Expected rent direction
```

---

### AI transmission model

```text
AI shock
→ workload
→ product / input
→ revenue
→ gross margin
→ opex
→ capex
→ FCF
→ implied valuation
```

---

### Evidence diff

每个季度自动比较：

```text
Q1 transcript
vs
Q2 transcript
```

找：

* 新增 AI language；
* capex guidance；
* hiring；
* customer mix；
* margin；
* capacity；
* product launch；
* competitor statements。

这种东西 Codex 的价值远高于再帮你“总结 earnings call”。

---

# 十八、最重要的工具架构

最终我不会选择 NotebookLM **vs** ima **vs** Codex。

而是：

[
\boxed{
Sources
\rightarrow
Knowledge\ Layer
\rightarrow
Structured\ Evidence
\rightarrow
Reasoning
\rightarrow
Prediction
\rightarrow
Audit
}
]

具体：

**Gemini Notebook**

→ academic / global canonical literature

**ima**

→ 中文、微信、碎片化 industry intelligence

**Codex**

→ ingestion / normalization / database / calculations / tests / monitoring

**ChatGPT**

→ hypothesis generation / adversarial challenge / synthesis / decision reasoning

---

# 十九、但有一件事千万不要自动化

不要让整个 pipeline 变成：

[
Data
\rightarrow LLM
\rightarrow Score
\rightarrow Buy
]

真正应该保留 human bottleneck 的地方恰恰是：

[
\boxed{
What\ changed?
\rightarrow
Why\ does\ it\ matter?
\rightarrow
Who\ captures\ it?
\rightarrow
What\ does\ price\ imply?
}
]

Codex 应该消灭的是：

> 搜、抄、整理、对齐、计算、重复比较。

而不是消灭你的：

> abstraction、mechanism inference、variant perception。

---

# 二十、所以我会对原 minimal syllabus 做一个相当小但关键的修改

原 syllabus 的核心逻辑是：

[
Technical\ Reality
\rightarrow
Economic\ Mechanism
\rightarrow
Investment\ Judgment
]

这个方向完全保留。

只是在中间插入三个更加明确的 intellectual objects：

[
\boxed{
Technical\ Shock
\rightarrow
Industry\ Architecture
\rightarrow
Capability
\rightarrow
Rent
\rightarrow
Earnings
\rightarrow
Expectations
}
]

于是三个 research program 恰好各负责一段：

[
\underbrace{
Industry\ Architecture
\rightarrow Rent
}_{Rent\ Formation}
]

[
\underbrace{
Capability
\rightarrow Rent
}_{Capability\ Revaluation}
]

[
\underbrace{
AI\ Shock
\rightarrow Earnings
\rightarrow Expectations
}_{Hidden\ AI\ Earnings}
]

这比继续横向扩大知识面重要得多。

**如果让我只选这次新增内容里的 5 个节点**，我会选：

1. **MIT 14.271 selective**
2. **Brandenburger & Stuart**
3. **Jacobides et al.**
4. **Kogut & Kulatilaka — Capabilities as Real Options**
5. **Babina 2026 + 2024**

然后立刻开始做 **20–30 个 historical/company cases**，同时让 Codex 搭 `research-os`。我认为从这里开始，**case study + falsification 的边际收益会明显超过继续听课**。

[1]: https://ocw.mit.edu/courses/14-271-industrial-organization-i-fall-2022/pages/calendar/?utm_source=chatgpt.com "Calendar | Industrial Organization I | Economics | MIT OpenCourseWare"
[2]: https://ocw.mit.edu/courses/14-27-economics-and-e-commerce-fall-2014/?utm_source=chatgpt.com "Economics and E-Commerce | Economics | MIT OpenCourseWare"
[3]: https://onlinelibrary.wiley.com/doi/pdf/10.1111/j.1430-9134.1996.00005.x?utm_source=chatgpt.com "Value‐based Business Strategy - Brandenburger - 1996 - Journal of Economics & Management Strategy - Wiley Online Library"
[4]: https://www.sciencedirect.com/science/article/pii/0048733386900272?utm_source=chatgpt.com "Profiting from technological innovation: Implications for integration, collaboration, licensing and public policy - ScienceDirect"
[5]: https://www.sciencedirect.com/science/article/pii/S0048733306001417?utm_source=chatgpt.com "Benefiting from innovation: Value creation, value appropriation and the role of industry architectures - ScienceDirect"
[6]: https://journals.sagepub.com/doi/abs/10.1177/0149206316678451?utm_source=chatgpt.com "Ecosystem as Structure - Ron Adner, 2017"
[7]: https://sms.onlinelibrary.wiley.com/doi/10.1002/smj.4250140303?utm_source=chatgpt.com "The cornerstones of competitive advantage: A resource‐based view - Peteraf - 1993 - Strategic Management Journal - Wiley Online Library"
[8]: https://www.nber.org/papers/w9581?utm_source=chatgpt.com "The Measurement of Firm-Specific Organization Capital | NBER"
[9]: https://onlinelibrary.wiley.com/doi/10.1111/jofi.12034?utm_source=chatgpt.com "Organization Capital and the Cross‐Section of Expected Returns - EISFELDT - 2013 - The Journal of Finance - Wiley Online Library"
[10]: https://www.federalreserve.gov/econres/feds/measuring-capital-and-technology-an-expanded-framework.htm?utm_source=chatgpt.com "The Fed - Measuring Capital and Technology: An Expanded Framework"
[11]: https://www.sciencedirect.com/science/article/pii/S0304405X16301969?utm_source=chatgpt.com "Intangible capital and the investment-q relation - ScienceDirect"
[12]: https://pubsonline.informs.org/doi/abs/10.1287/mnsc.2017.2769?journalCode=mnsc&utm_source=chatgpt.com "Should Intangible Investments Be Reported Separately or Commingled with Operating Expenses? New Evidence | Management Science"
[13]: https://pubsonline.informs.org/doi/10.1287/orsc.12.6.744.10082?utm_source=chatgpt.com "Capabilities as Real Options | Organization Science"
[14]: https://www.nber.org/papers/w35123?utm_source=chatgpt.com "Understanding Firms' AI Efforts and Their Economic Impact | NBER"
[15]: https://doi.org/10.1016/j.jfineco.2023.103745?utm_source=chatgpt.com "Artificial intelligence, firm growth, and product innovation - ScienceDirect"
[16]: https://www.nber.org/papers/w31325?utm_source=chatgpt.com "Firm Investments in Artificial Intelligence Technologies and Changes in Workforce Composition | NBER"
[17]: https://sms.onlinelibrary.wiley.com/doi/full/10.1002/smj.70099?utm_source=chatgpt.com "Artificial intelligence adoption and the demand for managerial expertise - Alekseeva - Strategic Management Journal - Wiley Online Library"
[18]: https://doi.org/10.3982/ECTA9623?utm_source=chatgpt.com "The Network Origins of Aggregate Fluctuations - Acemoglu - 2012 - Econometrica - Wiley Online Library"
[19]: https://www.stata.com/bookstore/causal-inference-mixtape/?utm_source=chatgpt.com "Stata Bookstore: Causal Inference: The Mixtape"
[20]: https://www.theeffectbook.net/ch-EventStudies.html?utm_source=chatgpt.com "Chapter 17 - Event Studies | The Effect"
[21]: https://blog.google/innovation-and-ai/products/gemini-notebook/notebooklm-gemini-notebook/?utm_source=chatgpt.com "NotebookLM is now Gemini Notebook"
[22]: https://blog.google/innovation-and-ai/products/notebooklm/better-research-notebooklm/?utm_source=chatgpt.com "Do your best research with NotebookLM"
[23]: https://support.google.com/gemininotebook/answer/16337734?hl=zh-Hans&utm_source=chatgpt.com "通过工作/学校 Google 账号使用 Gemini Notebook - NotebookLM帮助"
[24]: https://apps.apple.com/cn/app/ima-%E8%85%BE%E8%AE%AFai%E7%9F%A5%E8%AF%86%E7%AE%A1%E5%AE%B6/id6737188438?platform=ipad&utm_source=chatgpt.com "‎ima - 腾讯AI知识管家 App - App Store"
[25]: https://openai.com/academy/skills/?utm_source=chatgpt.com "Using skills | OpenAI"

