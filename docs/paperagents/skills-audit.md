# Skills 调研与审查

核查日期：2026-11-03。范围为官方仓库的实际技能、角色文件及相关执行代码；不是仅比较 README，也不是对所有科研系统的排名。未安装或执行这些项目的研究流水线。

## 分类结论

保留按研究能力组织的 `knowledge / engineering / ideation / review`。领域专家和论文专家会共用思路提取、假设生成、质询等能力，按专家复制目录会形成两份难以同步的流程。增加独立的角色说明层 `profiles/`，由程序注入；特定论文和领域知识仍放在项目的版本化 `library/`。

专家 = 角色职责 + 特定知识资产 + 当前任务技能 + 实际可用工具 + 验证记录。`build-paper-expert` 是构建专家知识的操作，并不是该论文专家的全部运行行为。详见[分类与组合表](../../skills/README.md)。

## 对照项目的实际写法

| 项目与核查版本 | 真实文件和内容 | 本项目取舍 |
| --- | --- | --- |
| Paper2Agent `8c2d0591` | [总 SKILL](https://github.com/jmiao24/Paper2Agent/blob/8c2d059165ef8cdcb70dbea76655b9c2b55b38e6/skills/paper2agent/SKILL.md) 路由到论文知识包与代码 MCP 工具两条流程；子技能、角色 Markdown、脚本分别承担不同职责 | 借鉴知识材料与执行能力分离，不要求内部工具只能用 MCP |
| EvoScientist / EvoSkills `209bdaa9` / `4889c227` | [research-ideation](https://github.com/EvoScientist/EvoSkills/blob/4889c2270af5f9a7658bb6a6709bf37040902006/skills/research-ideation/SKILL.md) 写操作；[EXPERT.md](https://github.com/EvoScientist/EvoSkills/blob/4889c2270af5f9a7658bb6a6709bf37040902006/skills/paper-review/EXPERT.md) 写角色与任务接口；[运行代码](https://github.com/EvoScientist/EvoScientist/blob/209bdaa92f0126549daefd8cb3239692deff685f/EvoScientist/tools/skills_manager.py#L155) 根据 EXPERT.md 识别专家 | 借鉴角色与技能分离，但不为了外观照搬文件名；不把 Elo 或固定复现阈值设为科学准入标准 |
| ARIS `2927b40b` | [idea-discovery/SKILL.md](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep/blob/2927b40b2ea37774de53763338c5e8f91a7601e6/skills/idea-discovery/SKILL.md) 定义输入、阶段、产物和恢复；[gate 程序](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep/blob/2927b40b2ea37774de53763338c5e8f91a7601e6/tools/idea_discovery_gate.py) 检查产物、阶段和审查回执 | 借鉴明确失败状态与实际产物检查；不把文件齐全当作科学正确，也不引入固定廉价 pilot |
| AI-Scientist-v3，本地 `df831388` | [create-idea](../../src/agents/skills/create-idea/SKILL.md) 明确六字段 idea、rubric、可选脚本和输出路径；[scientific-evidence](../../src/agents/skills/scientific-evidence/SKILL.md) 用实际脚本与 schema 校验证据链 | 保留实验层契约，前置领域学习及科研级选题；引用已存在的验证程序，避免技能重复造 schema |
| Karpathy autoresearch `228791fb` | [program.md](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md) 是项目实验指令，没有标准 skill frontmatter，写明编辑边界、命令、指标、日志和保留/丢弃循环 | 学习执行步骤的具体程度；五分钟预算和单指标循环属于该项目设置，不搬到通用科研流程 |

Paper2Agent 当前确实有 `SKILL.md`，不能沿用旧版只讨论 agent prompts 与 MCP 的印象。

### Paper2Agent 最有价值的工程细节

[paper2skill](https://github.com/jmiao24/Paper2Agent/blob/8c2d059165ef8cdcb70dbea76655b9c2b55b38e6/skills/paper2agent/paper2skill/SKILL.md) 将论文、补充材料、图表、索引和页面审查组织成可检查的阅读包。[其自身论文 skill 实例](https://github.com/jmiao24/Paper2Agent/blob/8c2d059165ef8cdcb70dbea76655b9c2b55b38e6/skills/paper2agent/paper2agent-paper/SKILL.md) 从短索引导航到相关原文、图表与锚点，检索只负责定位。

代码流程先执行原实现形成参考，再最小封装，最后让新的 verifier 检查。[工作流检查器](https://github.com/jmiao24/Paper2Agent/blob/8c2d059165ef8cdcb70dbea76655b9c2b55b38e6/skills/paper2agent/paper2mcp/scripts/verify_workflow.py#L264) 核对记录中的实现者与验证者、阶段及被测文件哈希；[MCP 检查器](https://github.com/jmiao24/Paper2Agent/blob/8c2d059165ef8cdcb70dbea76655b9c2b55b38e6/skills/paper2agent/paper2mcp/scripts/verify_mcp_server.py#L102) 实际启动服务并调用验收用例。身份记录与调用成功仍不自动证明独立性或科学数值正确。

Evo 的 [paper-review 执行脚本](https://github.com/EvoScientist/EvoSkills/blob/4889c2270af5f9a7658bb6a6709bf37040902006/skills/paper-review/scripts/five_aspect_review.js) 也值得区分：它实际派发子审查、约束返回结构、重试失败项并报告 incomplete，但依赖宿主的 task API，不能当普通 Node 脚本直接运行。

## 格式与内容标准

[Agent Skills 规范](https://agentskills.io/specification) 的核心是文件夹中的 `SKILL.md`：YAML `name`、`description` 加 Markdown 正文；脚本、references、assets 按需要提供。`allowed-tools` 等可选字段不等于宿主已经提供或授权了这些工具；Evo 的 `EXPERT.md`、ARIS 的额外元数据也不是所有宿主共有的标准。

本项目的技能入口应能回答六件事：何时使用；需要什么输入；怎样完成关键操作；用哪个实际工具或已有程序；输出如何核验；缺证据时怎样诚实停止。正文保持聚焦，长例子和协议按需链接。没有重复确定性操作的技能无需为了目录整齐增加空 scripts/。

本项目采用自定义注册表及共享 references，尚非每个子目录都可独立安装的发行包。程序按 stage 装载技能，按 role 装载 profile；`registry.skills.*.roles` 只是适用性说明。

## 2026-11-04：按需加载与原生实验接管

当时 20 项技能按操作划分为知识 10 项、工程 3 项、构思 6 项、评审 1 项（2026-11-04 后为 21 项，见讨论循环说明），角色通过 profile 组合这些能力。保留论文理解、思路重建和策略迁移的独立边界：分别回答“论文做了什么”“主张如何由证据和前提连起来”“哪些操作可在明确条件下迁移”。这不是 20 个同时工作的 agent。

论文任务默认预载 5 项：`build-paper-expert`、`understand-paper`、`trace-paper-ideas`、`distill-reasoning-patterns`、`map-paper-code`。配置 `execution.paper_capabilities` 中的 `communication` 才额外预载表达学习；`method_tools` 预载方法封装和验证。未预载技能仍可按链接读取；图表、实验和代码的科学理解不因这种调整而删除。

本机实验的工程和独立审查任务复用现有技能，不新增 skills。已审提案直接进入本项目的实验控制器，实际搜索结果自动返回专家修订，旧单 agent `create-idea` 不再进入主链。调度仍采用固定阶段和显式版本，没有实现完全自适应的讨论议程。知识是项目内可追溯资产；跨项目自动检索、自动 MCP 发布及策略迁移的真实科学效果仍未验证。

下表保留早期审查记录。其“综合可替换机制”问题现在已对新运行增加候选摘要及核心字段一致性检查；“prompt 重复”已改为读取唯一冻结请求。工程审查新增实际代码交接，但并不等于每篇论文都已独立复现。

## 早期审查结果

| 发现 | 处理与边界 |
| --- | --- |
| 领域、论文和临时专家缺少显式使用职责；临时专家在构思阶段被标成 paper | 新增三个 profile 并实际注入；临时专家保留 consultant 身份 |
| 技能正文在 prompt 的正文和序列化 request 中重复 | prompt 仅保留一份正文，并显式标出原文件路径，便于解析相对引用；request 仍保存指令快照 |
| 思路提取偏重论文论证摘要，缺少可迁移推理策略的具体例子 | 增加思维操作、被挑战前提、额外假设、反事实与判别预测的示例及索引约定；作者真实发现历史仍保持未知边界 |
| 工具技能只有原则，调用与证据记录不够具体 | 补调用、来源、接口和验证记录示例；独立工具验证 runner 尚未实现，不以文案替代程序 |
| verify-expert 文字暗示存在专家实际答题 | 明确当前只审查知识与能力资产；没有实际答题任务就不能生成或报告答题表现 |
| challenge 文字暗示作者已收到反馈并回复 | 明确当前是一轮提案→独立交叉质询→综合；不虚构回复或已完成修订 |
| synthesis 可以组合成新机制却沿用旧候选查新身份 | 技能要求实质变化返回 needs_evidence 并重做相应阶段；目前程序仍不能自动识别自然语言中的机制变化 |
| 仅有两篇合格全文时 selection 被迫满足三 ID schema | 程序在派发前进入 needs_evidence；不鼓励造 ID 或重复重试 |

### 尚未解决的实际能力差距

1. **工具验证与交付**：paper worker 当前同时获得映射、封装和自测技能，独立 expert_review 主要审资产。需要把参考执行、实现、独立运行验证及迁移环境验收做成真实交接；工具 schema 也仍只强制少量字段，示例中的完整契约尚未全部由程序强制。
2. **全文摄取与覆盖**：全文存在检查不证明图表、公式、补充材料被准确摄取；单个 corpus 任务不等于已实现大规模逐篇并行学习。需要页面/图表检查、逐篇任务与可审计索引。
3. **专家能力实测与讨论循环**：实际问答探针、作者答辩、候选版本更新后重新查新，都需要调度器继续实现。当前不宣称这些已由 skill 自动实现。
4. **独立分发**：要把单篇知识包单独安装到其他 agent，需要自包含引用、针对性索引及完整交付验证；当前通用资产入口与路径快照还不足以替代这一步。

本轮修复针对分类、实际路由、可操作说明及错误能力宣称，没有把研究整套流程扩成未验证的新系统。

## 验证

新增框架回归共 50 项通过，覆盖临时专家角色路由与论文不足时补证阻塞；Ruff 通过。技能格式、注册表、阶段绑定、角色路径和本地引用另行核查。文中示例为明确标记的练习材料，不是科研结果。结构检查与模拟请求不能证明真实文献理解或工具复现能力。

另用未继承本次讨论的独立 agent 做了一次 `trace-paper-ideas` 行为探针：只提供该技能和四段新虚构材料，材料描述贡献筛选、可能的测量噪声、同时更换缓存及缺少消融，没有提供预期答案。实际输出识别了缓存与筛选的混杂，提出固定缓存和随机筛选的区分实验，将迁移策略标为系统重建，保留真实发现历史未知，未声称实验已经运行。该检查支持技能在这个案例中能区分论证、推断与未知；不代表真实领域理解或多轮科研效果已验证。
