# Day 2 闭卷 Worksheet — 先写这个

- **日期**: 2026-09-08 | **主题**: Value creation ≠ value capture
- **理论**: Teece 1986（appropriability regime + complementary assets）· Brandenburger & Stuart 1996（added value）
- **规则**: 前 10 分钟闭卷。不查 pack、不查 filing、不问 AI。
- 完成后运行：`.venv/bin/python scripts/bootcamp.py closed-book 2`

---

## Part A — 核心闭卷题（10 分钟，限时）

### 客户为什么不能把 SNPS 拿掉？

> 连续写。**禁止使用「护城河」「moat」「壁垒」这三个词**——它们是结论标签，不是机制。
> 每一句都要能回答「具体是什么在阻止客户走？」

```
SNPS足够好，直接拿掉SNPS，在设计和IP库方面改用其他的供应商，对现在芯片设计流程会造成影响，需要重新磨合。这种迁移会造成芯片设计工作的停滞或者放缓，经济损失不小，不值得。

SNPS可能别家并不具有的IP库，或者设计能力，如果带来芯片设计质量的下降（从而之后实际流片才发现问题），整个研发成本会很高 -- 这里我并不确定，我对他家软件与竞争对手的差别了解有限。





```

---

## Part B — 八个维度分开检验（Primary block，140 分钟）

> **这是今天的核心训练。** 「moat」是一个词，但它掩盖了至少八种完全不同的机制。
> 有些机制很强，有些很弱，有些根本不存在——统称会让你永远发现不了哪个是真的。

对每个维度：**先写机制（具体是什么在起作用），再自评强度，最后写什么证据能推翻它。**
**不确定或不存在就写「弱」或「不适用」——这比硬凑更有价值。**

### B1. Technology（技术领先）
| 项 | 内容 |
|---|---|
| 具体机制 | |
| 强度（强/中/弱/不适用） | |
| 什么证据能推翻 | |
| 持续多久（duration） | |

### B2. Switching cost（切换成本）
| 项 | 内容 |
|---|---|
| 切换成本的**形态**是什么（人月？重跑验证？签核风险？工艺重认证？） | |
| 谁承担这个成本（工程师/项目/公司） | |
| 强度 | |
| 什么证据能推翻 | |

### B3. Workflow（工作流嵌入）
| 项 | 内容 |
|---|---|
| SNPS 嵌在设计流程的哪几步 | |
| 上下游交接点在哪 | |
| 拿掉后流程断在哪里 | |
| 强度 | |

### B4. IP（知识产权）
| 项 | 内容 |
|---|---|
| 这里的 IP 指什么（专利？Design IP 产品？工艺库？） | |
| 法律保护 vs 事实保护，哪个更重要 | |
| 强度 | |

### B5. Ecosystem（生态）
| 项 | 内容 |
|---|---|
| 谁在这个生态里（foundry / IP vendor / 客户 / 教育体系） | |
| 生态成员的**转换意愿**如何 | |
| 强度 | |

### B6. Complementary assets（互补资产）— Teece 的核心
| 项 | 内容 |
|---|---|
| SNPS 需要哪些互补资产才能变现技术 | |
| 这些资产是 **generic / specialized / cospecialized**？ | |
| 这些资产**由谁控制**（SNPS？foundry？客户？） | |
| 如果由别人控制，价值会流向谁 | |

> Teece 的关键论点：**弱 appropriability regime 下，谁控制 cospecialized complementary assets，谁 capture。**
> 这一栏答不出来，Day 2 就没做完。

### B7. Co-development（协同开发）
| 项 | 内容 |
|---|---|
| SNPS 与谁共同开发（foundry 工艺认证？大客户定制？） | |
| 这种协同产生的资产**归谁** | |
| 强度 | |

### B8. Customer risk aversion（客户风险规避）
| 项 | 内容 |
|---|---|
| 客户在什么环节最怕出错 | |
| 出错的代价量级 | |
| 这种恐惧如何转化为 SNPS 的定价能力 | |
| 强度 | |

### B9. 汇总：哪几个是真的？
| 维度 | 强度 | 这是**你**的判断还是**公司**的说法 |
|---|---|---|
| Technology | | |
| Switching cost | | |
| Workflow | | |
| IP | | |
| Ecosystem | | |
| Complementary assets | | |
| Co-development | | |
| Customer risk aversion | | |

> 提醒：SNPS 10-K 自己声称「多产品打包谈判使替换代价高昂」。
> 那是**公司的说法**（Day 1 pack §6 已标注）。你这一栏必须区分你的判断和它的说法。

---

## Part C — Added value（Brandenburger & Stuart 框架）

> B&S 的定义：**某方的 added value = 有它时的总价值 − 没它时的总价值。**
> 关键推论：**任何一方 capture 的上限，就是它的 added value。**

这个定义直接给出了今天 AI 的用法（counterfactual removal），但**你必须先自己做一遍**。

### C1. 有 SNPS 时
芯片设计这条链上，总共创造了什么价值？（不要只写钱，写能力）

```

```

### C2. 没有 SNPS 时（自己先推演）
假设 SNPS 明天消失。客户如何重构 workflow？

```
第 1 个月：

第 6 个月：

第 24 个月：

最终稳态：

```

### C3. 差额去哪了
| 接收方 | 会拿到什么 | 需要多久 | 代价 |
|---|---|---|---|
| Cadence | | | |
| Siemens EDA | | | |
| 客户内部设计团队 | | | |
| Foundry（TSMC 等） | | | |
| 独立 IP provider | | | |
| **无法被替代、直接消失的价值** | | | |

> 最后一行是关键。**能被别人接走的部分不是 SNPS 的 added value；只有会直接消失的部分才是。**

### C4. 修正 Day 1 的一个比较
Day 1 你在 SNPS map §1.5 写「NVDA 拿走 130B、AVGO 63B，客户拿走 20-100 倍收入」。

用 added value 框架重做一次——**不要删掉原来那版**：

```
原版（收入规模比较）：客户拿走 20-100 倍

新版（added value 比较）：


两版的差异说明了什么：

```

---

## Part D — 中船防务迁移（Transfer block，60 分钟）

> 新公司。**你大概不熟，这没关系——写得空本身是信息。**
> 先闭卷写，写完标 `?`，然后才给你 orientation pack。

### D1. 三方各自创造什么价值？
| 参与方 | 创造了什么价值 | 我的确定度 |
|---|---|---|
| 船东（下单方） | | |
| 船厂（中船防务） | | |
| 船机/设备商（主机、导航、动力等） | | |

### D2. 三方各自 capture 多少？为什么？
```

```

### D3. 与 SNPS 的对照
| 维度 | SNPS | 中船防务 |
|---|---|---|
| appropriability regime 强弱 | | |
| 关键 complementary asset 是什么 | | |
| 谁控制它 | | |
| added value 最大的一方 | | |

---

## Part E — 诚实标记

`?` 的数量：______ 个

Day 1 你标了 6 个。今天这个数字**很可能更大**——因为中船是全新的，而且八维度检验会暴露你以前用「moat」一个词盖住的东西。

**`?` 变多是进步，不是退步。**

---

## 交卷检查

- [ ] Part A 在 10 分钟内写完，全程没用「护城河/moat/壁垒」
- [ ] Part B 八个维度**每一个**都有判断（含「弱」和「不适用」）
- [ ] Part B9 区分了「我的判断」和「公司的说法」
- [ ] Part C2 自己先推演了 counterfactual，**没有先问 AI**
- [ ] Part D 中船闭卷写了（写得空也算写）
- [ ] 已运行 `bootcamp.py closed-book 2`

**Part C2 是今天的关键闭锁**：counterfactual removal 必须你先做，我才给反事实推演素材。
顺序反了，这个练习就废了。
