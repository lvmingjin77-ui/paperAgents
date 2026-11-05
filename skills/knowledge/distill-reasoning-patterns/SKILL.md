---
name: distill-reasoning-patterns
description: 从有来源的论文论证图提炼可复用研究操作，记录触发问题、变换、前提、反例与检验方案；支持领域跨论文归并和向具体 idea 的可追溯迁移。
---

# 提炼可复用推理策略

输入为论文理解、已读来源及带 ID 的论证图。阅读[策略协议](../../references/reasoning-patterns-protocol.md)，按需查看其中操作微例；不要把策略归纳说成作者真实心理过程。

领域阶段使用当时真实可用的语料与轨迹，不假定三篇论文专家已经构建。尚无稳定节点 ID 时，按领域契约保留来源并填写 `trace_link_limitations`，不要伪造对未来专家图的引用。

## 操作

1. 找到改变问题表述、关键前提或可选机制的具体节点组，说明触发张力。先确认图及来源可追溯，不能从标题或结论口号直接归纳研究套路。
2. 写出 before → operation → after：原来如何描述问题、具体改变什么、得到何种新假设或预测。保留被保持的不变量、被放松或新增的假设；方法名称或“做类比”不足以构成策略。
3. 为每条策略列适用条件、失败模式和反例。区分作者明确提出的操作与系统重建；原文支持只证明此策略的来源，不证明跨任务有效。
4. 领域归并时比较多个论文的机制与前提是否同构，保留每个成员的来源、差异和反证。单篇归纳注明范围；不能按支持篇数或相同标签形成通用定律。
5. 有具体目标时，明确来源结构到目标结构的映射、保留的不变量、新增前提及未成立对应，关联目标 idea ID 与策略 ID/版本。给出能区分竞争解释的预期观测及反证条件；无目标时如实记录尚未迁移。
6. 分别保留原文证据、系统检查和目标实验的状态。当前策略契约 `transfer_status` 只允许 `unvalidated`；不能因原方法已复现而自动宣称其新目标迁移已验证。

## 输出与验收

按当前 schema 写 `knowledge.reasoning_patterns`：每项含 `pattern_id`、`name`、`problem_type`、`reasoning_move`、`preconditions`、`failure_modes`、`source_refs`、`trace_refs`、`evidence_status`、`transfer_status`、`test_plan`。`evidence_status` 使用 `source_supported` 或 `source_inferred`，具体语义及论文/领域引用差异见[策略协议](../../references/reasoning-patterns-protocol.md)。

可在扩展字段保存 `trigger`、before/after、不变量、目标映射与具体反证，不维护与必填字段矛盾的副本。没有可核查策略时输出空列表及非空 `reasoning_patterns_reason`，不要为凑数生成套路。验收时沿策略回查来源和轨迹，并检查别人能否据此判断何时使用、如何操作、何时不该用及如何证伪。
