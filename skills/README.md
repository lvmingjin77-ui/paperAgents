# PaperAgents 项目技能

本目录包含本项目调用的研究技能，不需要全局安装。调度器通过 [registry.json](registry.json) 中的 ID 找到 `SKILL.md`；`roles` 声明适用角色，不代表独立权限或实际工具可用性。

技能定义研究操作和证据标准。阶段顺序、状态持久化、产物格式及执行权限由主程序负责；模型遵循了技能不等于科学结论已经得到程序证明。

## 按能力分类，按专家组合

目录的一级分类是**可复用的研究能力**，不是专家身份。领域专家和论文专家都需要思路提取、提出假设和质询，因此不复制两套同名技能。`build-domain-expert` / `build-paper-expert` 是“构建知识”的技能；已构建的专家在工作时使用其他操作技能。

| 层 | 保存什么 | 谁负责 |
| --- | --- | --- |
| 工作技能 `knowledge/engineering/ideation/review` | 这项操作怎样完成、输入输出与证据要求 | 调度器按 stage 选择 |
| 角色说明 `profiles/*.md` | 领域、单篇论文或临时专题应关注什么 | 调度器按实际 role 注入；不是独立 skill |
| 知识资产 `项目/library/` | 特定领域/论文的事实、论证、工具及来源版本 | 构建任务产生，独立审查后使用 |
| 主程序 `paperagents/` | 阶段顺序、并发、状态、schema、快照与交接 | Python 代码执行 |

| 专家 | 构建时使用 | 参与构思时使用 |
| --- | --- | --- |
| 领域专家 | 语料检索、研究思路提取、领域知识构建；有旧资产时先评估复用 | [领域角色](profiles/domain-expert.md)＋假设/质询；按任务加选题、综合或修订 |
| 三位论文专家 | 核心为全文理解、思路与策略、源码映射；表达学习和方法工具按需；有旧资产时先评估复用 | 各自的论文知识＋[论文角色](profiles/paper-expert.md)＋假设/质询；有真实历史时修订 |
| 临时专家 | 按邀请专题构建知识与边界 | [临时角色](profiles/temporary-expert.md)＋当前分配的操作技能 |
| 独立审查者 | 不充当被审专家 | 知识资产审查、查新或提案审查技能 |

运行时技能选择见 [STAGE_SKILLS](../paperagents/skills.py)，角色文件注册在 `registry.json.expert_profiles`。注册表内技能的 `roles` 是能力适用说明，**不是自动调度器或权限控制**。角色说明不把全部构建技能再次加载进每轮构思。

这些技能通过本项目注册表加载；共享 `../../references` 和跨技能链接依赖完整目录。单独复制一个子文件夹并不是可独立安装的交付包。生成的专家资产入口也由本项目管理，尚不宣称等同于 Paper2Skill 的可独立安装阅读包。

## 技能目录

| 类别 | 技能 | 产物或用途 |
| --- | --- | --- |
| 知识 | [build-literature-corpus](knowledge/build-literature-corpus/SKILL.md) | 系统检索、全文语料与覆盖记录 |
| 知识 | [understand-paper](knowledge/understand-paper/SKILL.md) | 材料清单、阅读覆盖、导航与七类论文理解 |
| 知识 | [analyze-paper-communication](knowledge/analyze-paper-communication/SKILL.md) | 论证组织、写作结构、图表表达与迁移条件 |
| 知识 | [trace-paper-ideas](knowledge/trace-paper-ideas/SKILL.md) | 有来源的研究论证轨迹 |
| 知识 | [distill-reasoning-patterns](knowledge/distill-reasoning-patterns/SKILL.md) | 有条件、反例和检验计划的可迁移策略 |
| 知识 | [build-domain-expert](knowledge/build-domain-expert/SKILL.md) | 领域地图、机制谱系与证据分歧 |
| 知识 | [select-paper-team](knowledge/select-paper-team/SKILL.md) | 核心论文（默认三篇）与临时能力需求 |
| 知识 | [build-paper-expert](knowledge/build-paper-expert/SKILL.md) | 全文知识、假设、实现和边界 |
| 知识 | [reuse-and-update-expert](knowledge/reuse-and-update-expert/SKILL.md) | 旧资产匹配、增量更新与能力降级 |
| 知识 | [verify-expert](knowledge/verify-expert/SKILL.md) | 独立知识/能力检查 |
| 工程 | [map-paper-code](engineering/map-paper-code/SKILL.md) | 论文到固定源码的映射 |
| 工程 | [build-method-tools](engineering/build-method-tools/SKILL.md) | 可调用方法与输入输出契约 |
| 工程 | [verify-method-tools](engineering/verify-method-tools/SKILL.md) | 实际测试及结果复现记录 |
| 构思 | [generate-hypotheses](ideation/generate-hypotheses/SKILL.md) | 独立、可检验的机制卡 |
| 构思 | [challenge-claims](ideation/challenge-claims/SKILL.md) | 编号异议、议题回应；复核自己异议 |
| 构思 | [revise-hypotheses](ideation/revise-hypotheses/SKILL.md) | 轮内逐条答辩与整轮修订：修订/撤回/组合与谱系 |
| 构思 | [moderate-discussion](ideation/moderate-discussion/SKILL.md) | 领域专家列出讨论议题并指派回应人 |
| 构思 | [audit-novelty](ideation/audit-novelty/SKILL.md) | 轻量初筛与深度查新：最近邻比较与检索日志 |
| 构思 | [design-discriminating-experiments](ideation/design-discriminating-experiments/SKILL.md) | 区分竞争解释的实验方案 |
| 构思 | [synthesize-proposal](ideation/synthesize-proposal/SKILL.md) | 提案、备选与晋级/补证据决策 |
| 审查 | [review-research](review/review-research/SKILL.md) | 独立提案审查及后续证据核对 |

## 共同规则

- [运行与产物约定](references/runtime-contract.md)：`request.json`、任务 schema 与输出路径。
- [证据规则](references/evidence-policy.md)：原文事实、作者明确思路、系统推断、未知的区分。
- [系统检索协议](references/literature-protocol.md)：近三年范围、会议目录、全文学习与遗漏披露。
- [专家生命周期](references/expert-lifecycle.md)：领域先行、核心四人加临时专家、独立思考与知识复用。
- [方法工具协议](references/method-tool-protocol.md)：静态映射、真实调用、行为验证与复现层次。
- [构思协议](references/ideation-protocol.md)：机制组合、证据讨论、判别实验与回流。
- [知识组织建议](references/knowledge-layout.md)：领域和论文知识包的可追溯组织。

按当前任务需要加载引用，不把所有知识一次塞入上下文。技能之间通过产物和来源 ID 协作，不互相默认已经执行或验证。

具体记录方式见[研究思路练习](references/idea-trace-example.md)和[方法工具契约示例](references/method-tool-example.md)。二者是明确标记的教学材料，不得作为真实论文或已执行验证的产物提交。与 Paper2Agent、EvoScientist、ARIS 和 v3 的对照及未完成能力见[本次审查](../docs/paperagents/skills-audit.md)。

论文专家的三层能力、新任务 v2 契约和版本化知识导航见[能力设计](../docs/paperagents/paper-expert-capabilities.md)。现有 **21 项**技能按阶段及任务条件装载，不一起注入所有专家：

- `paper` 默认加载构建入口、全文理解、论证轨迹、迁移策略、源码映射五项。论文理解说明“原文说什么及证据支持什么”，轨迹说明“论证如何成立”，策略说明“哪些思维操作可有条件地迁移”，三者分别保留。
- 请求的 `context.paper_capabilities` 包含 `communication` 时预载写作／图表表达学习，包含 `method_tools` 时预载方法封装及验证。项目可用 `[research] paper_capabilities = ["communication", "method_tools"]` 明确要求全部能力；默认空列表。其他名称会被拒绝，避免配置拼写错误被静默忽略。
- 未预载的能力仍保留在注册表及构建技能的链接中，可按实际任务需要读取。不能因为没有预载表达学习就跳过论文图表和实验理解，也不能把尚未封装的方法声明为可调用。
- `domain/paper` 发现旧资产才加载复用检查；`hypothesis` 有真实 `revision_context` 才加载修订。
- 本地实验构建使用现有实验设计与工具构建技能，实验审查使用现有工具验证与研究审查技能。它们分别绑定 `experiment_build`、`experiment_review` 请求，没有新增技能；具体产物仍以该请求的 schema 为准。

拆分标准是独立的触发条件、产物和验收方式。写作结构与图表设计共同服务于论文表达学习，合并为一项；单位、图例、段落功能等细节放参考协议，不再各建 skill。角色、具体论文知识和参考文件都不计为新技能。正文覆盖、论证图和策略引用已有结构校验；表达分析、复用评估及修订日志目前是可保存的扩展记录，其科学质量与语义一致性仍需独立审查。

## 维护

新增技能时为 `SKILL.md` 提供简洁的 `name` 和 `description`，在注册表添加真实相对路径和适用角色；路径相对于本目录。参考文件必须由入口链接，并说明何时读取。

验证时检查 frontmatter、注册表与目录一致性、链接、未完成占位内容，以及输出是否尊重当前 `request.output_schema`。有新脚本或方法封装时另行执行针对性验证；Markdown 校验不会证明研究质量。专家架构与边界见 [experts.md](../docs/paperagents/experts.md)。
