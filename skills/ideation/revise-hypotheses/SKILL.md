---
name: revise-hypotheses
description: 作者回应真实质疑：在去重确认（merge）中处理初筛归组，在讨论轮（rebuttal）逐条答辩编号异议，或在整轮退回后的 hypothesis 中依据质疑、查新与实验反馈修订候选；记录保留、修改、撤回或合并及父版本。
---

# 修订研究假设

先读[候选修订协议](../../references/hypothesis-revision-protocol.md)，产物遵循当前 [运行约定](../../references/runtime-contract.md)与 `request.output_schema`。本技能处理已发生的质疑和观测；没有旧候选及可定位输入时，不能编写假想答辩。

## 操作

1. 读取 `context.revision_context` 中的 `previous_iteration`、`reason`、`previous_hypotheses`、`challenges` 与 `novelty`，核对产物的 `task_id`、`artifact_path`、`artifact_hash` 及实际内容；这些是本专家上轮已提交候选和针对它们的反馈。再核对来源/知识版本及允许使用的 `search_feedback`，不能把别的实验或后续版本的结果套到当前父候选。没有修订上下文时不把首次独立生成变成假想答辩。
2. 将每条异议分为来源缺口、事实或逻辑问题、已知重叠、实现问题及待实验区分的机制问题。检查异议本身的依据，逐条说明采纳、反驳或仍待证据；票数、资历、角色、语气和自信不决定取舍。允许保留有理由的分歧。
3. 选择保留、修改、撤回或合并，并写清证据、科学变化与父版本。保留不能表示已证明；撤回不删除旧记录；合并不能因组件分别可行就假定交互有效。改变核心假设、机制、关键前提或适用问题时生成新候选 ID，记录一个或多个父候选，重新接受挑战和查新，不能沿用父候选的通过状态。
4. 修订后的机制卡仍需有可判别预测、竞争解释、反证及实验方案。用 [design-discriminating-experiments](../design-discriminating-experiments/SKILL.md) 更新必要对照；真实失败、不充分结果、基础设施错误和未运行分别记录，不能为保住假设事后改写预期。
5. 检查是否仍有阻塞：列出需要取得的材料、真实执行或来源核验，交回协调器。讨论轮内的答辩见下文“讨论轮内答辩”；整轮退回时， `revision_context.discussion` 提供上一轮自己候选的各版本、撤回记录和异议台账。不声称自己已调用其他专家、完成下一轮评审或获得新共识。

## 输出与交接

提交 `hypothesis` 的当前专家完整 `candidates`；通过 schema 允许的扩展字段记录 `revision_log`、候选 `lineage` 和未解问题，字段建议见协议。撤回的候选不再列为有效候选，但保留撤回理由和父产物引用；没有可提交候选时允许 `candidates: []`。本阶段没有能改变调度状态的 `decision` 门槛，不以自造 `needs_evidence` 字段冒充流程已暂停。

需要在综合阶段作实质修订时，由 [synthesize-proposal](../synthesize-proposal/SKILL.md) 按协议返回 `needs_evidence` 并交回协调器；它不会因引用本技能就注册新候选或自动启动下一轮。

只写本次被指定的输出，不覆盖已接受的候选、评审、原文知识或实验记录。真实回应仅表示本次任务给出的判断；其他角色不得冒称原候选提出者已经回应。

## 讨论轮内答辩（`stage=rebuttal`）

`context.objections` 是分配给你的编号异议（后续轮次附带你之前的答辩和原质疑者的复核）。每条恰好答复一次，`action` 取：`rebut`（给出证据或推理说明异议不成立）、`revise`（提交新 `idea_id` 的版本，`parent_ids` 含被质疑候选，写 `change_summary`，答辩中用 `revised_idea_id` 指向它）、`withdraw`（列入 `withdrawn_idea_ids`）、`experiment`（写出能区分双方预测的实验；若质疑者同意，它会成为实验必做项）、`accept_limitation`（承认并说明适用边界）。同一候选每轮只能有一个你的后继版本；多条异议可由同一次修订回应，但每条仍单独答复。

`context.merge_issues` 中指派给你的组合议题，可提交组合候选：`parent_ids` 至少含你自己的一个有效候选，可引用他人候选；说明新的交互假设，不能假定效果可以相加。修订和组合都是新主张，会被重新质疑和查新。不要替质疑者判断是否已解决。

## 去重确认（`stage=merge`）

`context.objections` 是初筛归组发给你的通知，每条含 `group_id`、`relation`、`idea_ids`、`representative`、`merge_owner`、`current_idea_id`。每条恰好答复一次（与 rebuttal 同一契约）：

- 同意重复/部分重叠：若你是 `merge_owner`，提交一个合并版（新 `idea_id`，`parent_ids` 列出组内全部候选，保留各方的不同组件与细节，并在 `change_summary` 写明各组件来自谁），答复 `action=revise` 并用 `revised_idea_id` 指向它；若不是，答复 `action=withdraw` 表示同意并入，在 `argument` 中写清你方独有、合并版必须保留的组件。`withdrawn_idea_ids` 保持为空：只有合并版真的把你的候选列为父版本时，协调器才让它退场；否则它继续参与讨论。
- 不同意：答复 `action=rebut`，写出可检验的机制差异（两者在什么条件下预测不同），保持原候选不变。

合并版是新候选：重新接受质疑和查新，不继承任何父版本的结论。

整轮退回后的 `hypothesis` 中，`revision_context.discussion.merges` 给出上一轮所有专家的归组与合并、撤回决定。不要悄悄重新提出已被合并或撤回的同一机制；确有新证据时可以重提，但须在 `change_summary` 或来源中写明新证据。

## 补证据之后的修订

如果 context.evidence_reports 非空，读取相关报告及其证据，而不是把 outcome 当作已经裁决的事实。对照 revision_context 中原候选、质疑和独立评审逐项回应。保留不受影响的科学内容；前提不成立的候选可以放弃或重构，不要求为每个旧候选强行辩护。修改科学核心须新 idea_id 并说明来源和变化，后续由其他专家重新质疑、查新。

区分需要人工资源的缺口与可由专家重新设计的协议；不得因为某个候选缺数据就宣称所有候选不可行。需要实验判断时提出明确判别实验和结论边界，不伪造结果，不把标签/泄漏/统计前提缺陷改写为“实验后再说”。

## 实验反馈后的修订

若 context.search_feedback 非空，先核对最新反馈的 candidate_ref、proposal_hash、
冻结协议和真实结果路径，再回应原预测。comparison_valid=false、执行报错、超时
或缺失对照只能说明本次比较不成立，不能当作机制被证伪。有效比较中，分别解释
支持、反驳和未能区分的假设；每项改变引用具体结果，并给出下一轮判别条件。
不以 combined_score 单项提升代替科学解释，不将 search 结果当作封存最终评估。
