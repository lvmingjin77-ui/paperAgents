# Ideation 代码审查与待修清单

原始审查日期：2026-11-03。下文保留当时的复现和原因分析。

2026-11-04 修复状态：A1–A9 的已复现程序路径已增加对应防护和回归。新运行绑定综合提案的候选版本及五个科学核心字段，要求结构化查新日志和完整审查标准；执行核对可信导出收据与完整资产文件集合；修改输入时在写入前拒绝；真实拒绝意见回传修订；损坏旧运行可显式新建；超时清理整个 worker 进程组。历史请求保留旧契约。A1 仍不能自动证明实施细节与机制语义一致；A5 的完整审查条目也不证明领域知识质量，均需真实材料核查。末尾列出的自动主持、多轮讨论及自动实验回流尚未实现。验证见[框架验证记录](verification.md)。

范围为 `paperagents/workflow.py`、`contracts.py`、`assets.py`、`providers.py`、`v3.py` 和 `cli.py`。本会话上一轮执行的 75 项回归测试通过；本轮通过额外的反例检查暴露了原测试未覆盖的路径，不能把原测试通过解释为下面问题不存在。

复现使用临时合成项目或内存数据；v3 执行调用由 mock 截获，未真正启动模型、容器或研究实验。超时测试只启动了合成子进程，测试后已清理。

## 优先修复：审查对象和执行对象的一致性

### A1 · P1 · 综合提案没有绑定已审查候选的科学内容

位置：[workflow.py](../../paperagents/workflow.py) 的 `_relationships()` synthesis 分支（335–342 行）；[contracts.py](../../paperagents/contracts.py) 的 `_proposal()`（130 行起）。

触发：保持 `selected_idea_id` 不变，将已查新候选的假设和实施方案替换成另一研究方案，仍提交 `decision=ready`。内存复现把图像分类剪枝候选换成药物递送方案，结构校验、关系检查和阶段门控均通过。

原因：代码只检查 ID 存在、对应 novelty 状态为 `distinct`；没有绑定候选版本或不可变科学核心。技能要求发生实质修改时退回，但程序没有执行这条约束。此问题此前已在 [skills-audit.md](skills-audit.md) 记录，仍未修复。

修复方向：将候选的科学核心与版本摘要绑定到综合提案及评审；表达和实施细化与科学核心变更分开处理。核心改变需要新候选及新一轮质询、查新；结构绑定本身不能代替语义审查。

### A2 · P1 · 没有任何检索记录也能声明 distinct

位置：[contracts.py](../../paperagents/contracts.py) novelty schema（236–239 行）；[workflow.py](../../paperagents/workflow.py) synthesis 晋级检查（340–342 行）。

触发：提交 `status=distinct`、`nearest_work=[]`、`search_log=[]`、`reason=Not searched`，能够通过结构和关系检查，并让对应候选满足 ready 的查新门槛。v1/v2 均可复现。

修复方向：对 distinct 要求可核对的检索记录、范围与结果；确实没有近邻时保留实际空结果及局限，不强迫编造一篇近邻论文。程序检查记录完整性，独立审查检查其真实性和实质差异。

### A3 · P1 · 执行前没有核验已审查导出的完整性

位置：[cli.py](../../paperagents/cli.py) v3 分支（81–85 行）；[v3.py](../../paperagents/v3.py) `build_command()`（356 行起）。

触发：合成流程完成后改写导出的 `task/task.md`，使其与 `export_manifest.json` 不符，再调用 `v3 --execute`。CLI 仍成功进入非 dry-run 调用。执行函数已 mock，未实际执行研究任务。导出专家副本也缺少相同的执行前核验。

原因：执行入口只检查流程 completed 和 task.md 存在；导出函数具有幂等比较，但正常执行不会再次调用导出函数。

修复方向：在受控状态中固定可信导出收据及其摘要，执行前检查已审查文件。允许后续合法添加 benchmark 文件；不要把可随文件一起修改的 manifest 单独当作信任根。

### A4 · P1 · 冻结资产中的新增文件未经核验也会导出

位置：[assets.py](../../paperagents/assets.py) `verify_asset()`（183–193 行）；[v3.py](../../paperagents/v3.py) `_copy_asset()`（129–139 行）。

触发：冻结资产后在其目录新增 `unreviewed.py`，完整性核验仍通过；导出函数复制整个目录，新增文件随后出现在实验任务中。

原因：核验只遍历登记文件，导出却遍历目录全部文件，两个集合不同。

修复方向：严格核对冻结目录的文件集合，或者只导出可信收据覆盖的文件。明确区分不可变专家资产与允许增加 benchmark 文件的下游任务目录。

## 需要补齐的验收与恢复逻辑

### A5 · P2 · 单条格式检查即可代替科学验收

位置：[contracts.py](../../paperagents/contracts.py) `_review()`（97–111 行）、domain v2 schema（335 行起）；[workflow.py](../../paperagents/workflow.py) `_gate()`（423–428 行）。

触发：最终审查只提交一项 `Title exists`、证据 `proposal.title`、verdict=pass，并标 accepted=true，即可满足放行结构。领域产物只含空 reasoning_patterns 和理由、一个来源 ID，也能满足结构校验；其领域学习内容没有相应必检维度保障。

修复方向：按专家类型和审查阶段定义必须覆盖的维度，绑定关键异议的处置记录；确实不适用时允许有理由地标记不适用。允许没有可迁移策略本身是合理设计，问题是缺乏对其他必要知识的验收。

### A6 · P2 · 输入变化检查发生在状态修改之后

位置：[workflow.py](../../paperagents/workflow.py) `start()`（60–64 行）、`submit()`（354 行起）、`revise()`（533–545 行）；[cli.py](../../paperagents/cli.py) 相应调用分支。

触发：创建 pending 请求后修改 research.md，再通过 CLI submit。命令最终报告 Research input changed 并退出失败，但任务已标 completed、产物已写盘。对已完成项目改变输入再 revise，也会先增加轮次、删除下游 batch 和 task_dir，然后才报错。

修复方向：所有改变当前运行的操作都在写入前核验任务输入与运行快照一致；失败命令不得留下部分状态变化。将需要允许的后端配置更新与研究目标变更分开处理。

### A7 · P2 · 独立裁决的拒绝原因没有回到修订任务

位置：[workflow.py](../../paperagents/workflow.py) `_revision_context()`（129–161 行）与 `_assignments()`。

触发：proposal_review 以明确 blocking_issues 拒绝提案，显式退回 hypothesis 或 synthesis。新请求没有此前裁决的拒绝文本及回执；reason 中只有操作者自己填写的概述。

原因：历史上下文目前只回传 hypothesis、challenge 和 novelty。

修复方向：将与本次返工相关的 synthesis、proposal_review 及阻塞项按真实版本和回执传入请求；覆盖退回 hypothesis 与 synthesis 等不同路径，避免要求用户手工转述。

### A8 · P2 · 损坏旧运行会阻止创建独立新运行

位置：[workflow.py](../../paperagents/workflow.py) `__init__()`（52–58 行）；CLI 构造 Workflow 的顺序。

触发：误改旧 run 的一个已接收产物，`run --new` 在构造 Workflow 时就被完整性校验阻止；错误建议的 revise 也会在同一位置失败。

修复方向：保持旧历史不变，允许显式新建独立运行。损坏运行的诊断与恢复路径不能提示一个实际无法执行的修订命令；不得通过忽略损坏来恢复信任。

### A9 · P2 · 超时清理可能遗留子进程

位置：[providers.py](../../paperagents/providers.py) `execute_command()`（30–38 行）。

触发：合成 driver 的父进程在 SIGTERM 时退出，子进程忽略 SIGTERM。超时处理已经返回失败，但子进程仍存活；已通过进程状态检查确认并清理。

原因：发出进程组 SIGTERM 后只等待直接父进程；父进程一旦退出，就不会进入后续 SIGKILL 分支。

修复方向：以进程组是否完成清理为依据，处理 leader 先退出的情况，防止遗留调用与重试重叠。清理不应扩大到该任务进程组之外。

## 另行实现：已确定的新设计

以下属于功能尚未落地，不是本轮新发现的回归：

- 输入契约明确表达研究问题／任务、目标、约束和评价意图。
- 逐篇或分批阅读任务、覆盖记录和跨论文领域知识的完整验收。
- 领域专家作为科研主持人，产出可由程序执行的讨论议程、分工及下一轮决策。
- 有真实作者回应、修订、重新质询和停止条件的自动多轮讨论。
- 强制检查支持、反对、未知、判断和改判依据，允许有说明的空反对证据。
- 候选版本与实验结果绑定，并让允许的搜索反馈自动进入专家下一轮；封存最终评估不回流。

建议先修 A1–A6 与 A9 等会影响首次真实试跑可信度和执行行为的问题，再补 A7–A8 的完整恢复路径，同时按上述目标接入新的调度逻辑。新增和修订的契约应保留历史请求版本，不能让旧任务被当前必填字段突然拒绝。
