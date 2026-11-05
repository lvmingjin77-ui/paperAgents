# 专家知识组织建议

实际字段由 `request.output_schema` 决定。增强的论文专家契约要求结构化 `knowledge.paper_understanding` 和 `knowledge.reasoning_patterns`；其余组织建议不能替代正式字段。没有内容的部分记录缺口，不填虚构条目或用空模板冒充已学习。

## 共用内容

| 建议字段 | 内容 |
| --- | --- |
| `profile` | 专家范围、知识版本、学习材料版本、适用任务与明确边界 |
| `source_index` | 来源 ID、论文/代码版本、全文或运行证据位置、读取/验证状态 |
| `claims` | 主张 ID、陈述、`basis`、支撑/反驳引用、适用条件、未知与依赖 |
| `paper_understanding` | 论文类型、来源与阅读覆盖、可引用导航及方法/形式化/图表/证据等分析；增强论文任务必需 |
| `reasoning_patterns` | 可复用推理策略索引：具体操作、来源轨迹、适用条件、反例及迁移时须检验的前提 |
| `communication_analysis` | 写作组织、图表表达与迁移条件；可选扩展，见[表达分析协议](paper-communication-protocol.md) |
| `reuse_assessment` | 旧资产匹配、保留内容、更新依据与能力降级；可选扩展，见[复用协议](expert-reuse-protocol.md) |
| `open_questions` | 未解决问题、为什么影响判断、需要何种证据 |
| `maintenance` | 新版本变化、触发原因、受影响结论及需重验的能力 |

`claims[].basis` 使用 `source_fact`、`author_reasoning`、`system_inference`、`unknown`。结构化 `source_refs` 尽可能包含来源 ID、版本及定位。运行证据引用实际记录，论文来源引用原文；二者不能相互冒充。

表达分析和复用评估存在时，v2 资产生成相应 JSON 分视图并纳入哈希检查。两者尚无专用 schema 字段/引用检查，仍需独立审查实际依据；派生视图格式版本纳入资产版本，更新渲染方式也不会覆盖旧知识包。

## 论证轨迹与推理策略

`idea_trace` 记录论文公开呈现的论证及明确标注的系统重建；`knowledge.reasoning_patterns` 索引系统从这些材料学到的可复用操作。策略归纳不证明作者曾有相同的内心过程。论文未披露的研究历史仍是未知，不能用一个漂亮的论证链补齐。

增强任务中一条策略的正式字段如下；可选扩展只用于进一步展开，不得替换字段或改变类型：

| 字段 | 应记录的内容 |
| --- | --- |
| `pattern_id`、`name` | 稳定标识及具体操作名 |
| `problem_type`、`reasoning_move` | 触发的问题类别与实际操作字符串；可扩展 `trigger`、`transformation` 表达 before/operation/after |
| `trace_refs`、`source_refs` | 论文/节点关系及原文锚点；两类引用分别保留，不随展示顺序改变 |
| `preconditions`、`failure_modes` | 非空前提与反例/失败边界列表，可扩展 `invariants` 描述应保持的关系 |
| `evidence_status` | 来源直接支持用 `source_supported`，含系统归纳用 `source_inferred`；都不等于迁移验证 |
| `transfer_status`、`test_plan` | 当前迁移状态固定 `unvalidated`，检验计划说明如何区分与反驳；可扩展具体 `target_transfer` |

论文策略引用本论文的已读 `{source_id, anchor_id}` 和真实 `{paper_id, trace_id}`。领域策略来源为 `{paper_id, locator}`，保留跨论文差异；缺稳定语料节点时允许空 `trace_refs` 加非空 `trace_link_limitations`。策略列表整体为空时需 `reasoning_patterns_reason`。完整字段规则与迁移扩展示意见[策略协议](reasoning-patterns-protocol.md)。

策略必须能解释一个具体变换，例如“把混合总体中的误差改写为条件误差，再检验条件是否造成尺度差异”。“多角度思考”“做类比”等标签本身不能指导下一步操作。跨论文合并策略时保留支持和失败案例，不因多个 agent 使用相同标签就认为它是普遍规律。

参考[虚构轨迹练习](idea-trace-example.md)：包含可通过当前 `paper` schema 的产物，演示作者论证、系统策略归纳、未执行预测与未知历史的不同表达。只复用表达结构，不复用其中的虚构知识。

## 领域专家

领域内容可按 `problem_map`、`mechanism_families`、`research_evolution`、`evaluation_protocols`、`disagreements`、`research_opportunities` 组织。每项跨论文归纳关联具体主张与来源，保留相反结果及条件差异。

`research_evolution` 表示可被公开文献支撑的思想关系和时间顺序，不声称知道作者未公开的研究历史。领域地图必须覆盖已定义语料的主要路线，不能只解释后来选中的三篇。

## 论文专家

增强论文知识的核心是 `paper_understanding`：`paper_type`、`sources`、`coverage`、`navigation`、`analysis`、`limitations`。来源固定版本与文件摘要，导航给稳定锚点，阅读覆盖区分已读/未读；`analysis` 分别处理 `problem`、`method`、`formalism`、`figures_tables`、`evidence`、`assumptions`、`limitations`，分析、不适用与未知明确分开。字段细节遵循任务 schema，不能以泛泛摘要替代各项检查。

可额外按 `mechanism`、`design_choices`、`transfer_conditions` 组织便于检索的视图，均回链到上述来源与正式分析。`idea_trace` 与 `code_tools` 已是论文任务的正式字段，直接引用这些条目，不维护互相矛盾的副本。论证图关系见[图协议](reasoning-trace-protocol.md)。

`design_choices` 中作者明确理由、系统重建理由和未说明原因分别保留。`empirical_evidence` 同时记录主结果、消融、负面结果、评估协议与解释限制。`transfer_conditions` 说明新任务中哪些前提仍成立、哪些需要先测量或验证。

## 临时专家

临时专家沿用共同证据结构，围绕指定 `specialty` 的具体问题组织知识，写清进入团队的原因、证据来源、材料缺口和退出/交接条件。没有来源支持的能力不能以专业角色名填补。专题结束后，把已核验内容回链到领域或论文知识版本，不把所有聊天内容自动升为持久知识。
