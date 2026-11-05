---
name: build-paper-expert
description: 全文学习单篇论文及补充材料，构建包含研究轨迹、机制、假设、证据、代码映射与验证状态的可复用论文专家，供构思、实验和写作持续调用。
---

# 构建论文专家

使用[证据规则](../../references/evidence-policy.md)、[专家生命周期](../../references/expert-lifecycle.md)及任务实际全文。读懂论文与能够运行方法是两个独立目标，分别举证。

## 操作

`context.paper` 已带有逐篇阅读阶段的论文卡（`card`）、论证轨迹（`idea_trace`，含 `trace_id`）和阅读资产路径（`reading_asset`）。在其基础上只做有目标的补读：优先读阅读记录标为缺口（partial、未覆盖章节、方法细节、可迁移组件）以及 `context.selection` 中你负责子问题所需的部分，核对并细化轨迹、提炼策略和代码映射，不要从零重读全文；与阅读记录不一致时以全文为准并说明差异。你是方法专家，重点是方法如何工作、为什么有效、能迁移到哪里。

若 `context.reuse_candidates` 非空，先用 [reuse-and-update-expert](../reuse-and-update-expert/SKILL.md) 检查旧版本：保留仍有效的知识，只补充受变化影响的部分；候选路径不代表复用已获批准。

默认构建加载全文理解、论证轨迹、迁移策略和源码映射。`context.paper_capabilities` 中的 `communication` 增加表达学习，`method_tools` 增加实际封装与验证；这些能力仍可从下列链接按任务需要读取。没有预载不表示删除能力，也不能把未完成的能力写成已掌握。全文图表与实验内容的理解始终属于核心阅读；按需进行的是表达策略学习和具体方法工具构建。

1. **理解材料。** 用 [understand-paper](../understand-paper/SKILL.md) 清点并固定正文、附录、图表和可用代码，完成全文分块覆盖、检索导航与科学分析，写入 `knowledge.paper_understanding`。材料缺失或不可读的范围显式保留，按理论、实证、方法或 benchmark 等实际类型调整分析。
   本任务要求表达能力或该能力影响当前判断时，按需使用 [analyze-paper-communication](../analyze-paper-communication/SKILL.md) 学习论点如何组织成章节、段落和图表，形成有来源、有适用条件的表达策略，存入 `knowledge.communication_analysis`。论文叙事顺序与作者发现历史分开。
2. **追踪论证。** 用 [trace-paper-ideas](../trace-paper-ideas/SKILL.md) 建立有来源的论证轨迹，区分作者直接说明、系统重建与未知；关键设计连接假设、替代解释和判别证据，不声称恢复作者真实发现过程。
3. **提炼策略。** 用 [distill-reasoning-patterns](../distill-reasoning-patterns/SKILL.md) 在 `knowledge.reasoning_patterns` 保存可复用思维操作，回链来源和轨迹。说明什么问题触发该操作、保留什么前提、如何检验目标对应关系，以及哪些反例会阻止迁移；原论文成绩不是新任务的结果保证。
4. **建立方法能力。** 用 [map-paper-code](../../engineering/map-paper-code/SKILL.md) 核查实现来源与公式映射；需要可调用能力时通过 [build-method-tools](../../engineering/build-method-tools/SKILL.md) 和 [verify-method-tools](../../engineering/verify-method-tools/SKILL.md) 构建、测试并记录状态。知识理解、原实现封装、重新实现与结果复现各自举证。
5. **交付审查。** 建立简短入口与按需加载的详细知识，把实际材料、笔记和工具文件通过允许的 `source_paths` 提交快照。交给 [verify-expert](../verify-expert/SKILL.md) 分别审查材料忠实性、科学理解、论证与策略、方法能力及未决问题；核心失败修订后重验，保留旧版本和失败记录。

## 输出与验收

按当前 `request.output_schema` 和[运行约定](../../references/runtime-contract.md)输出 `paper` 产物；`knowledge.paper_understanding` 保存材料与理解，`idea_trace` 保存论证轨迹，`knowledge.reasoning_patterns` 保存迁移策略，`code_tools` 保存真实方法能力。使用[知识组织建议](../../references/knowledge-layout.md)补充导航，避免同一主张出现互相矛盾的副本。

v2 来源引用使用匹配的 `source_id` 与已读 `anchor_id`；真实来源文件和哈希交由协调器核验。部分覆盖可保存但不能晋级。协调器从产物生成 `knowledge/index.md` 与理解、轨迹、策略 JSON；有表达分析或复用评估时也生成对应分视图。这两个扩展是技能约定，尚无专门的字段/语义校验；这些检索文件不代表自动完成材料转换或科学验证。旧请求仍遵循自身契约，不用伪造记录把历史资产补成新格式。

知识四种来源类型分开；工具状态与实际证据一致。没有代码也可形成有边界的论文知识，使用空工具列表并在 `limitations` 说明。资产审查不等于专家实际问答能力已测得，当前流程没有自动独立问答测评。该专家后续按具体任务参与反证、实验诊断与写作核对；未来使用不能反向充当本次已经完成验证的证据。
