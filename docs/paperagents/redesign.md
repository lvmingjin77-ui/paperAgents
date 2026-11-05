# PaperAgents 整体改造方案

日期：2026-11-05　状态：设计草案，待审　范围：构思、实验、写作三阶段的整体结构

> 依据：[ScientistTwo 分析笔记](scientisttwo-notes.md)。本方案不以 AI-Scientist-v3 为范式。

## 1. 为什么改

本次 `cir-reliability` 运行约 40 worker 小时：知识准备约 71%（逐篇阅读 54%），实验前讨论约 29%，实验和写作为 0。

主要问题：

- 三段靠导出文件交接，论证、实验、解释、写作无法相互修正；
- 效果在实验前被反复争论，系统趋于保守，瓶颈被提前预设；
- 只有一个 idea 进入实验，没有消融、写作与实验型反驳。

仓库体量也失衡：PaperAgents 自身约 4.9k 行，却背着整套 v3 上游——`src/` 约 12.8 万行，测试约 9 万行，另有 `examples/`、`apps/`、`configs/` 与 v3 文档。主链真正用到的只有 `src.investigation` 里的两个函数。

**目标**：输出会议 LaTeX 论文，每条主张都有实测证据，方法与代码一致，引用真实。保留两个长处：多专家跨论文迁移；实验前的有效性把关。

## 2. 改造原则

1. **先拆后建。** 每一步先删掉被替代的部分，再写新的。新功能尽量通过替换或合并现有模块实现，不平行新增。
2. **不留兼容层与兜底。**
   - 旧运行保留在磁盘上可读，但不续跑、不迁移；
   - 不保留旧格式分支、旧阶段别名、legacy 导出；
   - 契约只在边界校验一次，内部不重复检查，不为假想错误写兜底路径。
3. **一个共享研究状态。** 主张、证据、运行、论文是同一张图，论文是它的视图。
4. **证据门控。** 主张状态只由证据推进。实验前的讨论只处理有效性，不讨论效果。
5. **三层嵌套循环。** 方向（天）、idea（小时）、实现（分钟），加一条贯穿的写作与评审通道。每层有预算和回退条件。
6. **专家贯穿全程。** 同一位专家负责提出、诊断、撰写、评审。
7. **统一控制原语。** 每一步都是“产出者 + 批评者 + 有上限循环”。协调器只管状态、预算、回执。
8. **规模预算。** 改造完成后，`paperagents/` 总行数不超过现在（约 4.9k 行），技能数量不增加。

## 3. 拆除清单

| 拆除对象 | 规模 | 理由 |
| --- | --- | --- |
| `src/`（v3 上游全部） | 约 12.8 万行 | 自有运行器取代 `src.investigation` 两处调用；其余从未进入主链 |
| `examples/`、`apps/`、`configs/`、`scripts/` | 约 8k 行 | v3 任务样例、应用与 Hydra 配置 |
| v3 测试（`tests/` 下除 `tests/paperagents` 外） | 约 8 万行以上 | 对应代码已删除 |
| v3 文档（`docs/` 下除 `docs/paperagents` 外）及 `README.v3.md` | 约 3k 行 | 同上 |
| `pyproject.toml` 中的 v3 依赖与链接 | — | 删除 hydra、omegaconf、fastapi、uvicorn、scholarly 等未使用依赖，项目信息改为 PaperAgents |
| `paperagents/v3.py` | 552 行 | legacy / native 导出；研究状态取代导出交接 |
| `paperagents/review.py` | 110 行 | 六维评分绑定 proposal_review；该阶段删除 |
| `paperagents/debate.py` | 137 行 | 谱系并入研究状态，多轮台账删除 |
| `paperagents/experiments.py` | 683 行 | 由更小的自有运行器取代 |
| `workflow.py` 中的 rebuttal、recheck、novelty（实验前）、synthesis、proposal_review、evidence、auto_revision 及 v4→v5 迁移代码 | 约 600 行 | 阶段删除；不做迁移 |
| `contracts.py` 中上述阶段的契约 | 约 300 行 | 同上 |
| 技能 synthesize-proposal、design-discriminating-experiments、moderate-discussion、review-research 及 references 中的 review-scoring、hypothesis-revision-protocol、ideation-protocol | — | 合并到新技能或删除，见第 7 节 |
| 文档 ideation-discussion、evidence-recovery、ideation-code-audit、skills-audit、upstream、链路梳理 | — | 描述已删除的结构 |
| 测试 test_v3、test_native_handoff、test_handoff_integrity、test_evidence_recovery、test_review_score*、test_discussion_*、test_research_loop、test_native_experiments、test_trial_entrypoints、test_scientific_gates | — | 覆盖的是被删除的代码，随新结构重写 |
| backend 中的通用 `command` 驱动 | — | 只保留 glm（运行）与 manual（测试注入） |

## 4. 共享研究状态

每次运行一个 `state/` 目录，协调器是唯一写入者。只有四类对象：

| 对象 | 关键字段 | 说明 |
| --- | --- | --- |
| Claim 主张 | `claim_id`、`kind`（problem / hypothesis / method / result / limitation）、`text`、`status`、`version`、`parents`、`owner`、`evidence_ids` | 论文中可检验的陈述都来自主张 |
| Evidence 证据 | `evidence_id`、`kind`（literature / run / diagnosis / review）、`source`、`hash` | 文献证据沿用阅读锚点 |
| Run 运行 | `run_id`、`claim_id`、代码清单哈希、`split`、`seed`、`metrics`、`status`（completed / impl_failed / protocol_failed） | 实现即代码哈希，不另设对象；实现失败与机制失败分开 |
| Draft 草稿 | LaTeX 章节，段落标注 claim_id，数字用由证据生成的宏 | 不手抄数字 |

**主张生命周期**：

```text
proposed → valid → screened → confirmed → attributed → reported → written
```

被否定的主张不删除，保留为负面结果或局限。现有的候选谱系、哈希回执、阅读锚点并入这张图。

## 5. 三层循环

### 5.1 外层：方向（天）

- **K1 知识准备**：scope → corpus → reading → domain → selection → expert。
  - reading 只产出论文卡和覆盖记录；深读只对核心论文，在 expert 阶段进行。
  - 领域全景按问题组织；选队先比较团队（已实现）。
- **K2 评测底座**：数据划分为开发子集、开发全集、封存测试；定义指标与种子数；复现强基线；做诊断分解（召回 / 感知 / 联合判断 / 接受决策）。
- **K3 底座有效性审查**：唯一一次实验前的严格审查，覆盖标签、泄漏、划分独立性、统计前提。不通过回 K2；问题框定被证据推翻则回 K1。

### 5.2 中层：idea（小时）

- **I1 提案**：专家依据实测局限提出 hypothesis，每人不超过 `max_candidates_per_expert`，标注 kind。
- **I2 去重**：triage 与 merge。
- **I3 有效性质疑**：一轮，只处理会让结果无法解释的问题。
- **I4 子集筛选**：前 N 个判定 Good / Bad / Engineer；Engineer 进入内层，超出预算记为实现失败。
- **I5 诊断**：提出该机制的专家诊断失败原因。
- **I6 进化**：读取成败证据，提出新 idea。满 K 轮或得到 S 个 Good 即停；全部失败且诊断指向框定时回外层。
- **I7 确认**：Good 在开发全集上验证。
- **I8 查新**：只对 confirmed 的主张。
- **I9 消融**：归因，删除无效组件。
- **I10 定稿**：确定主方法与对比，冻结要报告的主张清单（预注册）。

### 5.3 内层：实现（分钟）

实现 → 运行 → 调试，有 `engineering_budget`。分数由协调器执行运行器得出，worker 不能提交分数。批评者核对代码与 method 主张是否一致。

### 5.4 写作与评审通道

| 步骤 | 时机 | 内容 |
| --- | --- | --- |
| W0 骨架 | K3 通过后 | 会议 LaTeX 模板；问题、相关工作（来自全景与语料 bib）、实验设置 |
| W1 增量更新 | 主张状态变化时 | 负责专家改写对应段落 |
| W2 封存测试 | I10 之后 | 只对预注册主张评一次，生成结果宏与表图 |
| W3 初稿 | W2 之后 | 结果、分析、局限 |
| W4 评审 | 初稿后 | 意见分为写作修改、补充实验（只用开发集）、主张降级三类 |
| W5 meta-review | 评审处理后 | 达标定稿；否则退回中层或降级主张 |
| W6 编译与核对 | 定稿前 | LaTeX 编译；引用来自语料 bib；数字可追溯；匿名化 |

## 6. 专家职责

| 环节 | 领域专家 | 论文（方法）专家 | 临时专家 | 独立批评者 |
| --- | --- | --- | --- | --- |
| 外层 | 全景、选队、底座设计 | 核心论文深读 | 补缺口 | 底座有效性审查 |
| 中层 | 主持去重与定稿 | 提案、诊断、进化 | 按专长参与 | 有效性质疑、筛选判定 |
| 写作 | 引言、相关工作、叙事 | 方法与分析段落 | 对应章节 | 评审与 meta-review |

## 7. 保留、替换与新增

**保留**
- 协调器核心：请求 / 响应 / 校验、哈希回执、retry / revise、events、锁；
- web 只读视图；
- `glm_worker`、`assets` 与专家库、`landscape`；
- 知识阶段的契约与技能。

**替换（新模块取代旧模块，不并存）**

| 新 | 取代 |
| --- | --- |
| `state.py`（研究状态，含谱系） | `debate.py` 与 `workflow.py` 中的候选 / 台账部分 |
| `runner.py`（划分、多指标、多种子、判定、预算） | `experiments.py` 与 `src.investigation` |
| `writing.py`（LaTeX 视图、宏、编译与核对） | `v3.py` 导出与 `review.py` |
| `workflow.py` 重写为三层循环 | 线性 PHASES 状态机 |

**技能（数量不增加）**

| 新技能 | 合并自 |
| --- | --- |
| build-testbed | design-discriminating-experiments |
| screen-and-diagnose | revise-hypotheses 中的实验反馈部分 |
| plan-ablation | design-discriminating-experiments 中的消融部分 |
| write-section | analyze-paper-communication 的写作用法 |
| review-paper | review-research |

synthesize-proposal、moderate-discussion 删除。challenge-claims、revise-hypotheses 精简为一轮有效性质疑和 merge。

## 8. 实施顺序

每一步先拆后建，完成后都能运行，由你来测。

1. **P0 拆除上游。**
   - 先写最小运行器 `runner.py`，替换 `src.investigation` 的两处调用；
   - 随后删除 `src/`、`examples/`、`apps/`、`configs/`、`scripts/`、v3 测试、v3 文档、`v3.py` 以及 v3 依赖。
2. **P1 研究状态。** `state.py` 取代 `debate.py` 与候选台账；同时删除 rebuttal、recheck、novelty（实验前）、synthesis、proposal_review、evidence、`review.py` 及对应契约、技能和测试。
3. **P2 评测底座。** 加入 K2、K3，运行器支持划分、多指标、多种子、诊断分解。完成后当前 CIR 课题能得到实测瓶颈。
4. **P3 中层循环。** 子集筛选、诊断、进化、确认、查新、消融、定稿；`experiments.py` 删除。
5. **P4 写作通道。** `writing.py`，覆盖 W0–W6。

每一步结束都核对规模预算：`paperagents/` 行数和技能数量。

## 9. 待确认事项

- 算力与时间预算（决定 N、K、S、engineering_budget、种子数）；
- 无解查询与部分匹配负例的构造方法和数据来源；
- 运行环境（本机 GPU / 远程 / 容器）；
- 首个目标会议模板；
- 人工检查点，建议三处：底座有效性、主方法定稿、投稿前终稿。

## 10. 风险

- **重写范围大**：按 P0–P4 分步，每步可运行。
- **子集误杀与评审过拟合**：靠证据和人工检查点把关，不另建兜底机制。
