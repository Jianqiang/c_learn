# Personal Learning OS v1 — Product & Technical Plan

状态：可交给工程师实现的 MVP 计划
工作区：/Users/jma/PycharmProjects/c_learn
输入材料：投资技术学习清单.md、投资知识补充syllabus2.md、Personal Learning OS v0.2 产品与实现备忘录

## 1. 执行摘要

Personal Learning OS 是一个本地优先、以 concept 为中心、与真实研究相连的学习工作台。

它不以“看完多少课程”作为目标，而以以下闭环为产品核心：

~~~text
选择下一步
→ 先尝试
→ 有目标地学习 source
→ 闭卷 recall
→ 修复具体缺口
→ 有限复习
→ 在真实 case/research 中应用
→ 达到使用标准后停止主动复习
~~~

v1 只解决五件事：

1. 从现有 Markdown syllabus 建立可确认的学习地图；
2. 管理 module、source、concept、practice item 与当前 focus；
3. 用少量 drill/recall 暴露错误，而不是生成大量卡片；
4. 在每日时间上限内生成可解释的 2–4 个 Next Best Actions；
5. 记录 concept 是否被真实研究使用，并允许 retirement/reactivation。

v1 不做完整 LMS、自动课程规划、自动扩展 syllabus、社交/积分系统、知识图谱或自动投资判断。

### 1.1 产品北极星指标

~~~text
更少的 coordination cost
→ 更快暴露关键误解
→ 更早进入真实研究
→ 不挤占真实研究时间
~~~

系统输出的是“下一步行动和证据”，不是一个看似精确的总学习分数。

## 2. 对 v0.2 方案的 critical review

### 2.1 保留的设计判断

以下判断是正确的，应直接进入实现约束：

- 学习目标是可调用能力，而不是课程完成率；
- concept-centric，多个 source 汇聚到同一个 concept；
- 先 attempt，再学习，再 recall；
- deterministic grading 优先于 LLM grading；
- review 必须有硬预算，不能制造 backlog；
- 用户选择最终的 Next Best Action，Workspace 是地图，不是老板；
- 真实 case 应优先于完美 retention；
- Learning OS 只处理学习协作，不替代“发生了什么、为什么重要、谁捕获价值、价格隐含什么”。

### 2.2 必须修正的地方

| 原方案中的风险 | 修正后的工程规则 |
|---|---|
| module/concept/source 的状态混在一起，ACTIVE/USABLE/STABLE 的含义不够明确 | source 使用独立状态；concept 使用 workflow status；review 使用独立 due/review state；不得用一个字段表达所有含义 |
| Markdown syllabus 是自由文本，无法可靠地自动抽取 module、时间、priority、output | 导入必须保留原文件、heading、行号和 content hash；无法解析的字段进入 draft warning，由用户确认 |
| 开放题容易被 LLM 伪装成 83% understood | rubric 只输出 PASS/PARTIAL/MISS/MISCONCEPTION；LLM 只能提出判定和证据，不能成为不可追溯的 canonical truth |
| v0.1 一开始就依赖 FSRS，可能把调度算法问题误当成学习效果问题 | 先实现可复现的固定间隔 scheduler 和统一接口；FSRS 作为后续 adapter，不改变上层数据契约 |
| Next Best Action 只有抽象公式，没有可解释输入 | v1 使用固定优先级规则，并展示每个推荐的 reason、预计时间和依赖；不做黑箱 ranking |
| “应用于研究”只有文本标签，无法判断是否真的发生过 transfer | 建立最小 applications 记录：关联 concept、case/research ref、用户笔记、结果（success/partial/failure） |
| CLI 与 Web 可能各自实现业务逻辑 | CLI、Web、未来 API 只能调用同一个 application/service layer |
| 三到四周后“研究质量提升”难以归因 | pilot 只测行为、协调成本、练习结果和应用证据；不得据此宣称因果性的学习提升 |
| 没有 backup、export、migration 和 LLM 隐私边界 | v1 必须支持 SQLite backup/export、schema version、显式的外部 LLM 开关；默认本地运行 |

### 2.3 本版新增的关键决策

本次 review 后，v1 进一步收紧为以下规则：

- **CLI-first**：M0–M3 只实现 CLI 和 service layer；Web UI 推迟到 M4，且必须先通过 pilot 的使用门槛；
- **小步内容生产**：第一条 vertical slice 只准备 10–15 个高质量 item，不把 20–30 个 item 当作 M0 前置条件；
- **摄入受容量约束**：新 source 不会自动生成 review item；P4 推荐受 phase gate 和 review-load gate 双重限制；
- **语义不丢失**：source 增加 resource mode、pace mode、scope note；syllabus output 作为一等对象；
- **证据分层**：真实 research application 是强证据，syllabus 声明的 notebook/memo/map 是 research-adjacent partial evidence；两者都可支持 USABLE，但只有真实 transfer 才能支持 STABLE；
- **单人统计克制**：v1 记录 confidence，但不展示 calibration curve；pilot 数据不足时不制造统计结论；
- **反复失败要人工介入**：item 达到 leech 条件后暂停自动排程，推荐重写题目、拆分 concept 或人工退休；
- **reference/sensor/external-paced 不进入普通学习管道**：它们只用于导航和按需查阅。

### 2.4 关键边界

系统可以自动化：

~~~text
导入、规范化、链接检查、题目选择、确定性计算、记录、排程、排序、视图生成
~~~

系统不应替代用户：

~~~text
抽象机制、判断研究重要性、识别价值捕获者、判断估值含义、做资本行动
~~~

## 3. 产品范围

### 3.1 v1 必须有

- 导入现有 Markdown syllabus，并生成 import report；
- 用户确认后写入 module/source/concept 草稿；
- 当前 focus 的设置和展示；
- concept drill：确定性题和 rubric 题；
- source-linked recall：少量闭卷题；
- attempt、confidence、latency、misconception 的记录；
- 人工 rubric adjudication；AI-assisted adjudication 只作为显式可选 adapter；
- 每日最多 12 个 review item、最多 20 分钟；
- concept 的 USABLE/STABLE/RETIRED/REACTIVATED 操作；
- concept 与真实 case/research 的应用记录；
- CLI 和共用的 service layer；M4 后再按 pilot 结果决定是否加入本地 Web UI；
- JSON/CSV 导出和 SQLite 单文件 backup；
- 无 LLM 时仍可正常运行。

### 3.2 v1 明确不做

- 自动生成或扩张 syllabus；
- 自动摘要全部 source；
- 自动安排详细每日课程表；
- streak、points、排行榜、completion percentage；
- 无限 flashcard；
- vector database、knowledge graph、云端部署、登录系统；
- 自动创建完整 case analysis、forecast app 或 misconception app；
- 自动从互联网抓取大量论文；
- 从学习状态直接推导投资结论、买卖建议或仓位。

## 4. 目标用户流程

### 4.1 正常学习流程

~~~text
1. 查看 Current Focus / Next Best Actions
2. 选择一个 source 或 concept
3. 先做 2–4 个、5–10 分钟的 drill
4. 打开原始 source 学习，系统不默认生成摘要
5. 进行 2–5 个 source-linked recall
6. 按 rubric 修复 MISS/MISCONCEPTION
7. 将合格 item 放入有预算的 review queue
8. 在真实 case/research 中记录应用
9. 达到使用标准后手动确认 retirement
~~~

### 4.2 Session 类型

| session type | 目的 | 结束条件 |
|---|---|---|
| drill | 学习前暴露 mental model | item 完成，或用户主动结束 |
| learn | 记录 source 的实际学习 | 用户确认完成/跳过，并可写 output |
| recall | 闭卷检验 source/concept | recall item 完成并 adjudicate |
| review | 延迟检索 | 达到 12 item 或 20 分钟，先到为止 |
| apply | 与真实研究/case 建立连接 | 保存 application evidence |

learn 不要求系统追踪用户在外部 source 中的每一分钟；系统只记录开始、结束、source、目标和用户输出，避免工具本身成为负担。

## 5. v1 内容范围与第一批种子数据

### 5.1 Domain A：LLM Economics / Systems

第一批 concept：

~~~text
conditional-probability-and-bayes
statistical-significance-and-p-values
selection-bias-and-multiple-comparisons
parameter-memory
kv-cache
training-flops
inference-flops
arithmetic-intensity
moe-active-parameters
context-scaling
compute-optimal-scaling
~~~

优先实现确定性/辨析题：参数量、precision、KV cache、FLOPs、单位换算、数量级、Bayes/条件概率和统计证据边界。

### 5.2 Domain B：Economic / Strategy Concepts

第一批 concept：

~~~text
value-creation
value-capture
added-value
complementary-assets
industry-architecture
bottleneck
capability-as-real-option
economic-pass-through
event-study-identification
~~~

这些 concept 的第一版题目以 source-grounded rubric 和人工 adjudication 为主，不伪装成确定性测验。

### 5.3 第一条 vertical slice

工程实现顺序不应从全量 syllabus 开始，而应先完成：

- 3 个 LLM 确定性 concept；
- 2 个数学/统计辨析 concept；
- 2 个经济/战略 rubric concept；
- 10–15 个高质量 item；
- 2 个真实 research/case application reference；
- 一次完整的 import → drill → recall → review → apply → retire 流程。

只有这条 vertical slice 可用后，才扩充其他内容。

## 6. 状态机与语义

### 6.1 Module、Phase 与 Focus

Module status 只表达工作流，不表达掌握程度：

~~~text
AVAILABLE → ACTIVE → PAUSED
     └────────────────→ ARCHIVED
~~~

- `AVAILABLE`：存在于 syllabus，可被当前 phase gate 检查；
- `ACTIVE`：当前 focus 正在处理；
- `PAUSED`：暂时停止，不删除历史；
- `ARCHIVED`：不出现在正常推荐中。

Phase 不自动推进。`focus_state.current_phase` 由用户显式设置，P4 只能推荐 `module.phase <= current_phase` 的 consumable source；phase 之前的 source 可以回补，未来 phase 的 source 只能在 syllabus 页面查看。

Focus 必须有数据模型，且只允许一个当前 focus：

~~~text
focus_state:
current_phase, target_type, target_id, rationale, updated_at
~~~

`target_type` 可以是 module 或 concept。focus 的设置、清除和切换写入 `status_events`，但不改变 concept mastery status。

### 6.2 Source 状态

Source 还必须声明两个正交属性：

~~~text
resource_mode = consumable | reference | sensor
pace_mode     = self_paced | external_paced
~~~

- `consumable`：可以进入 QUEUED，用户确认后可触发 drill/learn/recall；
- `reference`：按需查阅资料，不进入 QUEUED，不自动产生 drill/review item；
- `sensor`：信息流或 frontier refresh，不进入普通学习排程；
- `external_paced`：节奏由外部任务/他人推进（例如算法/OI），只做导航和按需记录，不使用固定 review scheduler。

~~~text
PROPOSED → QUEUED → OPEN → CONSUMED
                    └──→ SKIPPED
PROPOSED → VISIBLE  （reference/sensor/external-paced）
任何状态 ───────────────→ ARCHIVED
~~~

- PROPOSED：导入或用户新增但尚未批准；
- QUEUED：用户批准，且仅适用于 `resource_mode=consumable`、`pace_mode=self_paced` 的 source；
- VISIBLE：已确认可供导航或按需查阅，但不进入普通学习排程；
- OPEN：用户开始处理；
- CONSUMED：用户确认 source 已处理并可留下 output；
- SKIPPED：明确不处理；
- ARCHIVED：不再出现在正常视图，但保留历史记录；v1 只允许软删除，不物理删除。

### 6.3 Concept workflow 状态

~~~text
QUEUED → ACTIVE → USABLE → STABLE → RETIRED
             ↑                         │
             └────── REACTIVATED ◄────┘
~~~

- QUEUED：还未进入当前学习；
- ACTIVE：当前正在建立或修复；
- USABLE：已经能在至少一个真实问题中调用；
- STABLE：多次检索和应用没有 recurring misconception；
- RETIRED：不再主动复习，不代表删除或永久掌握；
- REACTIVATED：因失败、研究需求或知识变化重新进入 active queue。

状态转换必须由用户显式确认，或由系统提出待确认建议；系统不得静默改变 concept 状态。

### 6.4 掌握判断

不使用百分比 completion，也不使用单一总分。

可采用以下 evidence gate：

~~~text
USABLE = 至少一个核心 rubric atom 通过
         + 一个 evidence record
         （真实 research application = strong；syllabus output = partial）

STABLE = delayed recall 通过
         + 两个不同 case 正确调用，或用户明确确认足够稳定
         + 没有未修复的 recurring misconception
         + 至少一个 strong application

RETIRED = 用户确认暂不主动复习
~~~

这是工作流门槛，不是对“理解程度”的科学测量。

若当前没有合适的真实研究机会，用户可以先完成 syllabus 中声明的 notebook、memo、map 或 ledger 作为 partial evidence，使 concept 进入 USABLE；页面必须明确标注“待真实 transfer”，不得把它等同于 STABLE。

## 7. 数据架构

### 7.1 Source of truth

- 内容定义（module、source、concept、item、rubric）存放在可审阅的 YAML/Markdown 文件中；
- 用户状态（session、attempt、review、application、状态变化）存放在 SQLite；
- SQLite 是运行时状态，不替换原始 syllabus；
- 所有导入记录带 source_file、source_line、content_hash，可追溯回原文；
- schema 有版本号，升级必须有 migration；
- 每次 pilot 前可执行 SQLite 单文件 backup，支持从 backup 恢复；backup 是运维命令，不单独发展成同步系统。

### 7.2 最小数据表

#### modules

~~~text
id, slug, name, phase, importance, status, notes, created_at, updated_at
~~~

status：AVAILABLE、ACTIVE、PAUSED、ARCHIVED。它只表达 module 工作流，不表达 concept 掌握程度。

#### sources

~~~text
id, module_id, title, type, url_or_path, estimated_minutes,
priority, status, resource_mode, pace_mode, scope_note, scope_confirmed,
output_hint, source_file, source_line, content_hash
~~~

#### concepts

~~~text
id, module_id, slug, name, importance, workflow_status,
description, research_relevance, created_at, updated_at
~~~

#### focus_state

~~~text
id, current_phase, target_type, target_id, rationale, updated_at
~~~

只允许一条 active row；focus 切换必须留下 status event。

#### learning_outputs

~~~text
id, module_id, title, kind, phase, required, status,
source_file, source_line, evidence_level, reference
~~~

从 syllabus 明确声明的 notebook、memo、map、ledger 等产出物导入。evidence_level 为 PARTIAL 或 STRONG；v1 不自动评估产出质量。

output status：PROPOSED、ACTIVE、SUBMITTED、ARCHIVED。用户完成并提交 reference 后，系统可将其作为 partial evidence 写入 applications；不能仅因 source 被 CONSUMED 就自动完成 output。

#### concept_sources

~~~text
concept_id, source_id, relationship, notes
~~~

#### items

~~~text
id, concept_id, type, prompt, grading_mode, reference_answer,
rubric_json, answer_schema_json, difficulty, calibration_eligible,
content_version, active
~~~

type：numeric、symbolic、discrimination、explanation、counterfactual。
grading_mode：deterministic、rubric、manual。

#### sessions

~~~text
id, session_type, target_type, target_id, started_at, ended_at,
time_budget_seconds, item_limit, status, user_goal, user_output
~~~

#### attempts

~~~text
id, session_id, item_id, started_at, submitted_at, answer,
outcome, confidence, latency_seconds, misconception_code,
feedback, evaluator_kind, evaluator_version, human_override
~~~

outcome：PASS、PARTIAL、MISS、MISCONCEPTION、SKIPPED。

#### review_state

~~~text
item_id, due_at, stability, difficulty, last_outcome,
last_reviewed_at, scheduler_kind, scheduler_version, active,
lapse_count, failure_streak, intervention_required, suspended_until
~~~

#### applications

~~~text
id, concept_id, output_id, reference_type, reference,
note, evidence, evidence_level, result, created_at
~~~

result：SUCCESS、PARTIAL、FAILURE、UNASSESSED。reference 建议使用可解析的外部引用（例如 co_investor episode id），同时保留人工可读文本。

#### status_events

~~~text
id, entity_type, entity_id, from_status, to_status,
reason, actor, created_at
~~~

status_events 用于解释状态为什么变化，不做复杂事件溯源系统。

### 7.3 不保存的字段

不要保存或展示一个未经定义的 understanding_score、learning_quality_score 或总 completion percentage。需要汇总时展示可审计的计数和证据：通过的 rubric atoms、失败次数、最近应用、最近 recall、待复习 item 数量。

## 8. Syllabus Markdown 导入契约

### 8.1 导入原则

现有两份 syllabus 是人类写作的 Markdown，不应假设格式完全结构化。导入器必须“尽可能提取，不能猜测补全”。

每次导入生成：

~~~text
ImportReport
├── parsed modules/sources/concepts
├── unresolved fields
├── duplicate candidates
├── source locations
└── warnings requiring user confirmation
~~~

解析失败的字段留空并标记 warning，不由 AI 自动生成内容。

### 8.2 v1 解析规则

- 一级/二级 heading 作为候选 module 或 section；
- 同时解析 inline link、reference-style link（正文 [Title][N] + 文末 [N]: URL）和 link definition block；
- h、小时、min、分钟等明确表达提取 estimated time；
- ★、◎、optional、必看、R/reference、H/information flow、只看/跳过/不做等只作为 priority、resource_mode、scope_note 的候选 hint，必须在 import report 中显示原文；
- “只看哪些 lecture/chapter/assignment”进入 scope_note；scope_confirmed 未确认前，source 不得开始普通 drill/recall；
- 明确命名的 notebook、memo、map、ledger 等产出物导入 learning_outputs；
- G 模块或类似“跟随孩子/外部任务”的资源标记 pace_mode=external_paced；
- 代码块、公式和段落保留为 raw context，不自动变成 item；
- 只有明确命名的对象才候选为 concept；
- 原文件不被重写；
- 用 file path + heading + content hash 实现幂等导入；
- 已存在且内容发生变化时，仅对已 QUEUED 以上的 consumable source 生成 diff/warning；不静默覆盖用户状态；PROPOSED/VISIBLE 对象可重新解析。

### 8.3 确认流程

~~~text
parse
→ report
→ user confirms/edits
→ persist draft
→ approve PROPOSED → QUEUED
~~~

未确认的 source 不得进入 Next Best Actions。

reference、sensor 和 external-paced source 经过确认后进入 VISIBLE，只在 Concept/Source 页面展示；它们不产生普通 review debt。

### 8.4 Syllabus 语义映射表

| syllabus 原文语义 | v1 字段/对象 | 处理规则 |
|---|---|---|
| Phase 1–5、执行顺序 | modules.phase、focus_state.current_phase | P4 只推荐当前 phase 及之前；不自动推进 phase |
| ★、◎、必看、optional | sources.priority + import warning | 只作候选 hint，用户确认后生效 |
| 只看某几讲/某几章/跳过 assignment | sources.scope_note、scope_confirmed | scope 未确认前不得开始该 source 的普通 drill |
| R、reference、按需查阅 | sources.resource_mode=reference | VISIBLE；不进入 queue，不生成 review debt |
| H、信息流、frontier refresh | sources.resource_mode=sensor | VISIBLE；按需查看，不进入普通 scheduler |
| 跟随外部任务/孩子进度 | sources.pace_mode=external_paced | 只做导航，不使用固定间隔排程 |
| Notebook、memo、map、ledger | learning_outputs | 作为 partial/strong evidence target，不能自动标记完成 |
| 正文引用式链接和文末定义块 | source provenance + URL | 必须解析并保留原始行号 |
| 重复出现的论文/课程 | canonical source + alias/import diff | 合并候选交给用户确认，不复制为两个 source |

无法可靠映射的文本只保留在 raw context 和 warning 中，不能悄悄丢失，也不能由导入器猜成学习任务。

## 9. 判分与 AI 边界

### 9.1 Level 1：确定性判分

优先覆盖：

- 数值题：绝对/相对误差、数量级、边界；
- 单位题：Pint 转换和维度检查；
- 符号题：SymPy 等价性与指定假设；
- 选择/辨析题：显式正确答案和 disqualifier。

确定性判分必须有自动化测试，记录输入、答案 schema、tolerance 和 evaluator version。

### 9.2 Level 2：Source-grounded rubric

每个开放题拆成少量 atomic criteria：

~~~yaml
must_understand:
  - fixed-compute constraint
  - model/data allocation
  - empirical fitted relationship
disqualifiers:
  - bigger model is always optimal
  - a fitted ratio is a universal law
~~~

结果只能是：

~~~text
PASS | PARTIAL | MISS | MISCONCEPTION
~~~

第一版默认人工确认。若启用 LLM：

- LLM 只返回每个 rubric atom 的 proposed outcome、引用的答案片段和理由；
- 必须保存 model、prompt/evaluator version 和时间；
- 用户可以 override；
- LLM 不能修改 canonical reference 或静默改变 concept 状态；
- 默认不上传本地研究材料，外部调用需要显式开启。

### 9.3 Personal reference

用户修复后的个人答案可以保存，用于比较表达是否退化，但不能替代 source-grounded reference，也不能被当作客观真理。

### 9.4 Confidence calibration

v1 只记录 confidence，不在 UI 展示 calibration curve。confidence 只在有明确 outcome 的 item 上保留为未来分析数据：

~~~text
numeric | symbolic | discrimination | forecast-like item
~~~

开放式 explanation 默认不进入 calibration。pilot 结束后若样本量足够，再离线分析 confidence vs actual accuracy；任何分析只用于发现 high-confidence errors，不用于 gamification 或总评分。

## 10. Review 与 Scheduler

### 10.1 v1 预算

~~~text
MAX_REVIEW_ITEMS = 12
MAX_REVIEW_TIME = 20 minutes/day
~~~

两者先到为止。超出预算的 item 不算失败，不产生“补债任务”；它们只保留 due 状态，下一次按优先级重新候选。

### 10.2 摄入节流

source 被 CONSUMED 不会自动生成 3–8 个永久 review item。新 item 必须由用户或内容作者显式创建，并绑定 concept、scope 和 grader/rubric。

定义：

~~~text
review_load = 今日 due item 的预计秒数 / 1200
~~

当 review_load ≥ 0.8 时，P4 不再推荐新的 consumable source；只推荐 review、repair、apply 或 reference 查阅。该规则只限制系统推荐，不阻止用户显式打开 source。

### 10.3 v1 基线 scheduler

先实现可解释的固定间隔：

~~~text
PASS after first exposure: 1d → 3d → 7d → 14d → 30d
PARTIAL/MISS: 立即 repair，下一次 1d
MISCONCEPTION: repair 后重新从 1d 开始
~~~

具体间隔应配置化并有测试，不写死在 UI 中。

实现接口：

~~~python
class Scheduler:
    def next_due(self, review_state, outcome, now): ...
~~~

FSRS 可以作为后续 FSRSScheduler adapter 接入，但不能改变 review_state 和 attempts 契约。只有完成至少一个 pilot、确认记录质量和预算逻辑稳定后才比较调度算法。

### 10.4 Leech 处理

若同一 item 连续 3 次为 MISS/MISCONCEPTION，或最近 5 次中有 4 次非 PASS：

1. 设置 intervention_required=true 并暂停自动 due；
2. 不再重复消耗普通 review 预算；
3. 推荐人工选择“重写题目、拆分 concept、补充 source、改为 manual 或 retire item”；
4. 只有用户确认 repair 后才重新进入 1d schedule。

### 10.5 Review selection

在时间预算内按以下顺序选取：

1. 当前 research/application 明确依赖的 item；
2. 当前 ACTIVE concept 的失败或高 confidence 错误；
3. 重要性高且 due 的 item；
4. 其他 due item。

每个 review item 必须显示入选原因，避免产生不可解释的“算法命令”。

## 11. Next Best Actions

v1 不使用复杂公式或机器学习 ranking，采用确定性规则：

~~~text
P1  explicit research dependency
P2  current ACTIVE concept repair
P3  important concept with recent failure/high-confidence error
P4  approved QUEUED source（仅 current_phase 及之前，且 review_load < 0.8）
~~~

输出 2–4 个 action，每个包含：

~~~text
action type
target
estimated minutes
reason
expected output
~~~

同一 target 的重复推荐需要去重。用户可以 dismiss、defer 或选择其他动作；这些操作必须记录，但不构成负面评分。

推荐器必须过滤：resource_mode 不是 consumable、pace_mode 不是 self_paced、scope_confirmed=false、module.phase > focus.current_phase 的 source。

未来若需要 scoring，只能作为排序细节，且必须保留 reason，不得把 importance × relevance × gap / time 展示成伪精确结论。

## 12. CLI 与 Web 约定

### 12.1 CLI

建议命令：

~~~bash
learn init
learn import-syllabus "投资技术学习清单.md"
learn import-syllabus "投资知识补充syllabus2.md"
learn focus set <module-or-concept>
learn status [<slug>]
learn drill <concept-slug>
learn learn <source-slug>
learn recall <concept-or-source-slug>
learn review
learn apply <concept-slug> --ref "..."
learn output list [<module-slug>]
learn output complete <output-id> --ref "..."
learn retire <concept-slug>
learn reactivate <concept-slug>
learn export --out <path>
~~~

CLI 的最小体验要求：一次命令能继续 session；中断后不丢 attempt；没有 LLM 时 drill/recall/manual adjudication 仍能完成。

### 12.2 Web 页面（M4 后的可选交付）

M0–M3 不以 Web 页面为前置条件。只有 CLI pilot 显示确实需要降低导航成本，才实现服务端渲染的轻量页面：

1. Today/Focus：当前 focus、2–4 个推荐、review budget；
2. Syllabus：module/source/concept 导航和状态；
3. Concept：关联 source、items、attempts、应用证据、状态操作；
4. Session：答题、confidence、提交、repair、结束；
5. Import Report：确认/修改/批准导入对象；
6. Review：显示当前预算、入选原因和结束按钮。

不做 React SPA。CLI 和 Web 必须调用相同的 service layer、repository 和 domain rules；Web 不得先于可用 CLI 独立开发。

## 13. 建议技术架构

### 13.1 技术选择

~~~text
Python 3.11+
SQLite + sqlite3/SQLModel
Typer 或 argparse CLI
FastAPI/Flask + Jinja2 server-rendered UI
SymPy + Pint
pytest
可选：LLM adapter、FSRS adapter
~~~

具体 Web framework 可由工程师按团队现有习惯选择，但必须满足：本地启动简单、无前端构建链依赖、业务逻辑不复制。

### 13.2 建议目录

~~~text
c_learn/
  投资技术学习清单.md
  投资知识补充syllabus2.md
  Personal_Learning_OS_v1_Tech_Plan.md
  pyproject.toml
  data/
    learning.db
    backups/
  content/
    modules.yaml
    sources.yaml
    concepts/
    items/
  src/
    learning_os/
      cli.py
      config.py
      db.py
      models.py
      repositories.py
      services/
        import_service.py
        session_service.py
        grading_service.py
        review_service.py
        recommendation_service.py
        application_service.py
      graders/
        deterministic.py
        rubric.py
        llm_assisted.py
      schedulers/
        baseline.py
        fsrs_adapter.py
      web/
        app.py
        templates/
  tests/
    fixtures/
    test_import.py
    test_grading.py
    test_review_budget.py
    test_recommendation.py
    test_state_transitions.py
~~~

不要求工程师一开始实现所有目录；目录的目的是固定边界，避免 CLI、Web、LLM 各自生长一套业务规则。

## 14. Implementation milestones

### M0 — Contract-first vertical slice

完成：

- schema migration 和 seed content 格式；
- 3 个 LLM 确定性 concept、2 个数学/统计辨析 concept、2 个经济/战略 rubric concept；
- 10–15 个高质量 item；
- 状态转换、attempt outcome、session、application 的测试；
- CLI 可运行；
- SQLite 单文件 backup 和 JSON export 的最小命令可用。

验收：新环境初始化后，可从 drill 走到 apply，SQLite 中有完整可追溯记录。

### M1 — Syllabus import + Workspace

完成：

- 两份现有 Markdown 的导入；
- import report、source location、hash、duplicate warning；
- phase、resource_mode、pace_mode、scope_note、learning_outputs 的语义映射；
- 用户确认和 PROPOSED → QUEUED；
- focus_state 和 phase gate；
- CLI 版 deterministic Next Best Actions。

验收：原始 Markdown 不被修改；导入结果中的每个对象都能回指原文或明确标记 unresolved。

M1 必须包含以下 fixtures：reference-style link、文末 link definition block、两份 syllabus 中重复出现的 Teece 1986、R/reference source、H/sensor source、G/external-paced source、selective scope 和至少两个 syllabus output。

### M2 — Deterministic Drill

完成：

- numeric、symbolic、unit、discrimination grader；
- tolerance/assumption/schema；
- confidence、latency、evaluator version；
- high-confidence error 视图。

验收：KV cache、parameter memory、FLOPs 至少各有一组边界测试和错误测试。

### M3 — Recall + Repair

完成：

- source-linked recall；
- rubric atom adjudication；
- PASS/PARTIAL/MISS/MISCONCEPTION；
- manual override 和 repair note；
- 可选 LLM adapter，但不作为默认依赖。

验收：没有任何页面出现 Understanding = xx%；开放题的判定能看到 rubric、版本和证据。

### M4 — Review + Apply + Retirement

完成：

- baseline scheduler；
- 12 item/20 minute hard budget；
- review reason；
- applications；
- retirement/reactivation 和 status_events；
- leech intervention；
- 若 pilot 证明 CLI 导航成本确实存在，再实现最小 Web UI。

验收：review 达到任一预算后稳定结束；重复运行不会重复扣减或丢失 review state。

### M5 — 3–4 周真实 pilot

规则：完成 M4 后停止功能开发，使用现有两个 domain，除 bug 外不扩 scope。

每周记录：

- 使用次数和 session 类型；
- 从打开 Workspace 到开始第一次有效 attempt 的时间；
- Learning OS overhead；
- deterministic item accuracy 和 high-confidence errors；
- source consumed、concept usable、application evidence；
- 实际 research 时间是否被挤占。

## 15. 验收标准

### 15.1 工程验收

- learn init 在干净环境可完成；
- 两份 syllabus 可导入并生成可读 import report；
- 导入是幂等的，重复导入不会复制记录；
- 原始 Markdown 不被修改；
- 所有状态转换有测试和 status event；
- 若实现 Web，CLI/Web 共用 service layer；
- 没有 LLM key 也能完成确定性 drill、人工 recall 和 review；
- review 严格受 12 item/20 minute 限制；
- backup 可恢复；
- 关键计算和 scheduler 有自动化测试。

### 15.2 学习产品验收

三到四周后只回答以下问题：

1. 是否自然使用至少每周 3 次？
2. 是否减少了“下一步学什么、链接在哪、学到哪”的协调成本？
3. LLM Systems 的数量级直觉是否在确定性题上改善？
4. 是否发现过 high-confidence misconception？
5. 是否有至少若干条真实 application evidence？
6. Learning OS overhead 是否控制在学习时间的 10%–20% 内？
7. 是否没有挤占真实 research 时间？

这些是 pilot 指标，不是 Alpha、投资能力或因果学习效果证明。

## 16. Go / No-Go 与止损规则

### Go

满足以下大部分条件才扩充内容或接入 FSRS：

- 每周至少 3 次真实使用；
- 用户能在一次 session 内完成 attempt → recall → repair；
- overhead ≤ 20%；
- 至少记录到可复核的 high-confidence error 或真实应用；
- 系统没有明显减少真实 research 时间；
- 数据可导出、恢复、追溯。

### No-Go / 缩小范围

出现以下任一情况，先缩小系统，不继续增加功能：

- 用户主要浏览 dashboard，不做 attempt 或 apply；
- overhead 连续两周超过 20%；
- 推荐动作不被选择，且原因不可解释；
- import 维护成本高于手工维护；
- 开放题判分争议无法通过 rubric/人工 override 解决；
- review 变成新的 backlog 或挤占真实 research；
- 3–4 周没有任何真实 application evidence。

## 17. 工程师交付清单

工程师交付 v1 时应同时提供：

1. 可运行的本地项目和启动命令；
2. schema migration 和 seed data；
3. 两份 syllabus 的 import report 示例；
4. CLI/Web 共用的 service layer；
5. 确定性 grader、rubric grader、baseline scheduler 的测试；
6. 一次完整 session 的 demo 数据；
7. backup/export/restore 说明；
8. 明确列出未实现的功能和已知限制；
9. pilot 记录模板，而不是只交 feature list。

## 18. 一句话定义

> Personal Learning OS 是一个 syllabus-aware 的本地学习工作台：它帮助用户选择下一步，用少量可审计的 retrieval 暴露具体缺口，记录修复和真实应用，并在能力足够可调用后允许学习停止。
