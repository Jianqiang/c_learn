# SNPS Company Map v0

- **Day 1** · Primary deliberate practice（140 分钟）· 2026-09-07
- **前置**: `00_closed_book_FIRST.md` 必须已完成
- **产物类型**: Model update（三类正式产物之一）

---

## 1. 主链：Customer problem → Product → Revenue → Cost → Value

> 自己画。每一格先写你的理解，再用 10-K 校正。**校正时用不同颜色/标记，保留原始错误**——错误位置就是明天的研究问题来源。

### 1.1 Customer problem
客户到底卡在哪里？（具体到一个工程场景，不是「芯片设计很难」）

```
1. 芯片设计极其复杂，无法用手工或者物理图纸来进行，必须依赖设计软件（EDA）
2. 芯片不止有数字逻辑，更是存在物理世界中，因此对物理、热、结构的分析和建模比不可少 -- 同样，这依赖于软件实现，以保证准确和效率
3. 重复设计一些底层IP（芯片模块，如CPU core，USB等）的复杂度很高，经济/时间上上也不划算，因此直接拿SNPS等公司的IP直接复用能降低成本，缩减开发周期

```

### 1.2 Product
这个问题被拆成哪几个产品？它们之间是替代还是互补？

```
EDA：芯片设计
Ansys：物理层面如热力、解构的分析
Design IP：已有、可以复用的底层模块设计（授权）

他们之间是互补的

```

### 1.3 Revenue
| 维度 | 我的理解 | 10-K 校正 | 差异 |
|---|---|---|---|
| 计费单位 |  按流片 | licence 为主，少量服务/培训费   |  完全不同 -- SNPS的收入与客户流片的规模无关|
| 合同期限 | 重复的 | 重复为主 |  也有少量一次性的 |
| 确认方式（前置/分期） | 之前没问这个问题| 分期为主：前置 = 5:3 | 没预料到前置比例不小 |
| 续约驱动 | 客户 | 客户 | 相同 |
| 价格由谁定 | 之前没问这个问题 | 客户于公司协商 | / |




### 1.4 Cost
主要成本结构，以及**哪部分成本是为了维持 rent 而不得不持续投入的**：

```
Amortization of acquired intangible assets
```

### 1.5 Value
客户拿走多少、SNPS 拿走多少？谁在这条链上还分了一杯羹？

```
FY 2025， SNPS拿走了7B 的收入）（0.9B operating income）。
客户拿走多少？我假设NVDA是它的单一大客户，2025年拿走了130B，AVGO拿走大约63B的收入 ，客户拿走的至少20-100倍收入，但看总量SNPS也不少

```

---

## 2. Segment / product structure（看完 10-K 再填）

| Segment | 收入占比 | 增长 | 我不理解的地方 |
|---|---|---|---|
|Design Automation | 80.9% | Q3 YoY +52.7% | EDA和 Ansys 的 simulation & analysis (S&A) 各占多少？两者是否可以整合，整合后是否有增量|
|Design IP | 19.1%  | Q3 YoY  +10.8% | 我只理解是可复用的现有的底层模块设计如cpu核心，具体细节不太懂|


---

## 3. Ansys 后的公司结构

> 只记录**结构事实**，不做协同效应判断（那是 Day 2 的活）。

- 合并后新增了什么能力：Ansys 的 simulation & analysis (S&A) 对物理如热力学、解构的分析
- 客户重叠 / 不重叠的部分：芯片设计的客户是重叠的，ansys应该还有些传统行业如飞机、汽车制造厂商
- 收入模型是否一致：我猜测是一致
- 我不知道的：/

---

## 4. Competitors

| 玩家 | 在哪一段竞争 | 客户为什么会选它 | 证据等级 |
|---|---|---|---|
| Cadence | 所有阶段 | PPA / runtime / convergence 等性能更好、full-flow integration  | 次高等级，台积电网站公开信息 https://wwwpoc.cld.tsmc.com/english/dedicatedFoundry/oip/eda_alliance?utm_source=chatgpt.com |
| Siemens EDA | verification, physical sign-off| validator最强| 次高等级，台积电网站公开信息 https://wwwpoc.cld.tsmc.com/english/dedicatedFoundry/oip/eda_alliance?utm_source=chatgpt.com ||
| 内部自研团队 | all | 垂直集成？更快响应？定制化？ | 无 |
| 其他 | | | |

---

## 5. 本图最脆弱的三个链接（fragile links）

> Week 1 的目标是找到脆弱链接，不是形成 thesis。

1. product：无法端到端且敏捷的阶段客户问题
2. revenue：收入模式为liscence，不随客户流片数量scale，收入扩展空间有限？大客户多，价格为协商产生，公司自身议价权有限？
3. value：整个市场相比半导体行业是不大的，且市场面临Cadence正面竞争，西门子在validation侧的强势，还面临客户内部可能的自研，市场空间和增速优先，估计以大客户为主，小市场里有一定的实质性竞争 -- 可能客户拿走大多数value

---

## 6. 我此刻仍然无法回答的问题

（这些直接进入 `02_twenty_unknowns.md`）

- SNPS有没有真正的护城河，享有franchise的哪种？
- AI boom带来semi领域的收入增长，对SNPS的正面影响是不是sublinear的（因为NVDA等流片越多赚越多，但SNPS卖liscence，只能从**已有**客户的新需求获利）
- 看上去这个生意的毛利没有想象的高（OP margin似乎只有13%？），SNPS在产业链上是不是并没有收租权（rent）？
