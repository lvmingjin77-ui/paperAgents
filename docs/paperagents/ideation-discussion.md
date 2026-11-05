# Ideation 讨论循环

本文说明 2026-11-04 加入的专家讨论循环。编排只保留 v3：v2 及更早的运行会被拒绝继续（文件原样保留），需要 `paperagents run <project> --new` 开新运行。资产与评审的历史契约版本仍可读。

## 为什么要改

v2 的构思是"多人分别交稿，一人汇总"：每个专家只提一次案、只质疑一次，作者看不到针对自己的异议，修订要靠操作者手动 `revise`。领域专家既提案又裁决，"全部不选"的决定也没有独立复核。v3 在保留独立性和防篡改约束的前提下，补上作者答辩、原质疑者复核和自动推进。

## 阶段

```text
scope → corpus → reading（逐篇）→ domain → selection → paper/consultant → expert_review
 → hypothesis（R0，密封独立提案）
 → triage（轻量重叠初筛 + 机制级归组：duplicate / partial / shared）
 → merge（组内作者确认：合并、撤回或说明差异；无归组时跳过）
 → agenda（领域专家列议题、指派回应人）
 → challenge（R1，编号异议）
 → rebuttal ⇄ recheck（R2/R3，最多 discussion.max_rounds 轮）
 → novelty（只查有效候选）→ synthesis → proposal_review（任何决定都复核）
```

| 阶段 | 谁做 | 产物要点 |
| --- | --- | --- |
| `reading` | 每篇有全文的论文一个任务 | 带唯一 `trace_id` 的论证轨迹、ORKG 式论文卡、阅读覆盖；冻结进 `library/readings/` 并随导出 |
| `triage` | 独立核查者 | 每个候选的 `overlap_risk` 与检索记录；`high` 不等于否决；`groups` 只按机制归组，同主题不算重复 |
| `merge` | duplicate/partial 组内候选的作者 | 与 rebuttal 同契约；代表版本作者写合并版（新 `idea_id`，保留各方组件），其他作者撤回或给出可检验的机制差异；合并版重新受质疑与查新 |
| `agenda` | 领域专家（主持人） | 议题：机制冲突、组合机会、问题价值、证据缺口、可行性、共享前提（`shared_prerequisite`，集中讨论一次）；主持人不裁决 |
| `challenge` | 每位专家，审其他人的候选 | 每条异议有 `objection_id`（以 `专家ID/` 开头）、是否阻塞、解除条件；必须逐条回应主持人指派的议题 |
| `rebuttal` | 被质疑候选的作者 | 逐条：`rebut`、`revise`（新 `idea_id` + `parent_ids`）、`withdraw`、`experiment`、`accept_limitation`；可提交组合候选 |
| `recheck` | 原质疑者 | 只判自己的异议：`resolved`、`unresolved`、`experiment`；并质疑本轮新出现的候选 |

## 领域专家：论文卡 → 领域图谱 → 领域全景

参照 ORKG（研究贡献 = 问题 + 方法 + 结果）、SciAgents（从大量论文构建本体图谱）和 Chain-of-Ideas（发展链），领域专家不再一次读完全部材料：

1. 每篇 `reading` 输出论文卡：问题；贡献（方法、机制、假设、带条件的结果）；与语料内其他论文的关系。
2. 协调器把论文卡按名称（不区分大小写）机械合并成 `runs/<id>/domain_graph/`：`graph.json`、`index.md` 和按问题分文件的 `problems/`。合并不做推断。
3. 领域专家按需阅读图谱，输出 `knowledge.landscape`：演化链（至少两篇论文、每步改变了什么）、争议（正反两方论文）、空白（问题 × 条件或方法；`untested`、`failed`、`inconclusive`，后两者需证据论文）、评估协议盲点。所有论文 ID 必须有阅读记录，程序校验。

图谱路径随后交给所有专家，供提案、初筛、质疑和实验设计使用。语料规模继续增大时，可在此基础上按问题分组派发综合任务；目前未实现。

## 选题与评审取向（2026-11-05）

- 选队先写子问题 × 方法路线的覆盖表；论文专家是方法/算法专家，数据集论文只有其方法相关时才占核心席位。入选只需全文 + complete/partial 阅读，论文专家阶段针对缺口补读。
- 每位专家最多 `discussion.max_candidates_per_expert`（默认 2）个候选，标注 `kind`；卡片简洁，细节放文件引用。baseline 作为对照，不包装成创新。
- 阻塞只用于有效性问题；效果未知由评审写成 `experiment_requirements`，与实验型异议一起成为实验必做项。
- 整轮退回时，修订上下文包含所有专家上一轮的归组、合并与撤回决定；重提已合并或撤回的机制须写明新证据。

## 关键规则

- **异议跟版本走**：复核结论只对它判过的那个版本有效。作者之后修订了候选，相关异议重新打开，由原质疑者在下一次复核中确认是否仍成立。

- **独立性**：R0 密封；复核时质疑者只看到自己的异议和作者答辩。每轮结束后才把台账写入 `runs/<id>/debate/ledger.md`（`ledger.json` 为结构化版本）。
- **谱系**：作者修订自己的候选会生成新版本并取代旧版本；同一候选每轮只能有一个后继，不能分叉。撤回的候选不再参与。组合候选必须包含作者自己的一个有效候选，可以引用其他专家的候选，被引用的他人候选仍然有效。父候选按派发给该作者时的版本校验，与同轮其他人的提交顺序无关。候选 ID 在整个运行内唯一，跨轮次和整轮退回都不能用旧 ID 装新内容。
- **循环条件**：复核后若仍有阻塞异议需要回应，且未达轮数上限，自动进入下一轮答辩；达到上限后未解决的异议如实带入综合。
- **准入**：综合选择 `ready` 的候选不能有未关闭的阻塞异议（状态须为已解决或已转为实验）。
- **转为实验的异议必须做**：状态为 `experiment` 的异议成为实验阶段的编号必做项，实验构建必须在 `protocol.objection_tests` 中逐条给出设计，反馈逐条带回。
- **综合决定都复核**：`needs_evidence`、`no_viable_idea` 同样进入独立评审，评审填写 `decision_assessment`（是否同意及理由）；此时 `accepted` 必须为 `false`。决定为 `ready` 时，`accepted` 与 `agree` 必须一致。所有候选都被撤回时，评审的候选评分为空列表，流程仍能正常给出复核后的结论。
- **返工边界**：从 `rebuttal` 或 `recheck` 返工时退回整个讨论起点，不保留半轮记录。
- **自动退回**：综合给出 `next_action=revise_candidates` 且评审同意时，协调器自动退回 hypothesis，附带上一轮的异议台账，次数受 `discussion.max_auto_revisions` 限制；每次实验反馈开启新一轮构思时计数清零。其他情况停下等待操作者。
- **利益冲突**：综合与评审的请求中列出领域专家自己的候选（`conflict_of_interest`），评审需检查取舍标准是否一致。
- **工作笔记**：专家阶段的产物可带可选 `notebook` 字段。协调器在保存产物前把它剥离，单独写入 `runs/<id>/notebooks/`，只把路径交还给同一专家；共享产物中不含笔记。
- **上下文瘦身**：v3 请求中语料、专家知识包、验收、质疑和查新以路径加哈希传递，worker 按需读取；候选、议程和初筛结果仍内联。
- **备选候选实验**：综合可选填 `secondary_ref`，指向另一个机制不同、同样通过查新且无未关闭阻塞异议的有效候选。实验阶段把它实现为 `program_2`，与基线、主候选使用同一评价器运行，三组结果一起回流。

## 配置

```toml
[research]
core_papers = 3          # 2–5

[discussion]
max_rounds = 2           # 1–5，答辩/复核轮数上限
max_auto_revisions = 1   # 0–3，评审同意时自动退回作者的次数
```

`[discussion]` 不计入研究输入哈希，修改它不会使已有运行失效。

## 设计依据

调研的相关工作：Google AI co-scientist（生成、反思、排序、邻近去重、进化、元评审）、Stanford Virtual Lab（PI 议程主持 + 独立 Scientific Critic）、Paper2Agent（论文转为 MCP 工具服务）、SciAgents、ResearchAgent、Chain-of-Ideas、ORKG、SciMON，以及 Anthropic 的多智能体研究系统和 Building effective agents。取舍：保留编排者-工作者结构和"写文件、传引用"；以论文卡和图谱支撑领域专家；不采用 Elo 或投票作为证据；多智能体辩论研究显示同质模型容易从众，因此保留密封独立提案和"复核只看自己的异议"。

## 尚未验证的部分

讨论循环是否真的改善候选质量，需要用真实问题对照 v2 基线检验：同一语料与专家，比较盲评分数和阻塞异议被真实解除的比例。公开交流可能带来附和，当前只通过"复核只看自己的异议、轮次结束后统一公开"来缓解。校准记录、多模型专家和讨论中途的实验探针尚未实现。
