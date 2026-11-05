# 运行与扩展

## 输入和后端

`research.md` 保存明确研究问题或任务及科学约束；`paperagents.toml` 管后端、并发、重试、检索时间窗和实验超时。`init --brief-file <Markdown路径>` 原样导入输入，也保留 `--direction` 文本入口。新项目使用 `native_expert_loop`：PaperAgents 负责专家构思、实验构建、独立审查、执行和结果回流，原 v3 的 `create-idea` 不在主链中。

`manual` 产生任务供宿主 agent 执行，便于检查。`command` 每个任务启动新进程，cwd 为任务目录，配置为 argv 数组，不经 shell 拼接。占位符 `{request}`、`{prompt}`、`{response}` 分别指向任务 JSON、提示文件和输出数据 JSON。

本机 Codex CLI 的配置示例：

```toml
[backend]
kind = "command"
command = ["codex", "exec", "--skip-git-repo-check", "--sandbox", "workspace-write", "Read {prompt} and complete the assignment. Write the data JSON to {response}. Read validation_feedback.json if present."]
timeout_seconds = 1800
```

模型、登录和检索工具沿用宿主配置。项目材料和工具目录的写权限须由宿主/容器配置提供。框架不会绕过权限。请求层隔离首轮意见，**不提供进程文件系统隔离**；强隔离时使用可访问指定材料和技能路径的容器 driver。

命令成功退出并产生合规 JSON 后才提交。非零退出、超时、缺产物、非法 JSON 不晋级。默认最多两次自动尝试，错误保存在状态和 `validation_feedback.json`；失效结果留档。可人工提交修复结果，或用 `revise` 创建新轮次。超时终止进程组。

每次尝试使用独立的 `attempts/<编号-ID>/`，保存请求、响应、日志和成功退出凭据。进程中断后不会自动采纳未经提交的输出；恢复可能重新消耗一次尝试。

`prompt.md` 只指向当前目录的 `request.json`。上下文、技能正文、角色说明及输出 schema 以该冻结请求为单一来源，避免在提示与请求中重复展开；链接的详细参考仍按需读取。

共保留 21 项 skills（讨论循环新增主持议程一项；初筛、答辩、复核分别并入查新、修订、质疑技能）。`paper` 默认预载构建论文专家、全文理解、研究论证轨迹、可迁移策略、代码映射这五项能力；`execution.paper_capabilities` 中加入 `communication` 或 `method_tools` 时，再加载表达分析或方法封装／验证技能。旧专家复用和历史假设修订仍按实际上下文加载。这是按任务加载，不是删除这些能力。

## 状态与恢复

`active_run.json` 指向当前 run；状态、请求、产物和摘要持久化，CLI 持项目锁。写入原子替换，恢复时核对已接受产物的摘要。

- `running`：可推进。
- `awaiting_workers`：等待任务结果或修复失败。
- `needs_evidence`：覆盖、专家验收或提案存在缺口。
- `completed`：ideation 已审查并导出；不表示实验或论文完成。

`run` 恢复当前 run；`run --new` 用新输入开始，保留旧 run 和 library。改变 brief 或 research 配置不能悄悄继续旧 run。

`revise --from <phase> --reason ...` 保留旧产物并重做该阶段及下游。每次导出位于新的 `exports/rNNN/task`；冻结任务不覆盖。

退回 `hypothesis` 或更早阶段时，保存退回前的 batch 引用；存在本专家已接收候选时，新假设任务通过 `revision_context` 获得这些候选及针对它们的真实质疑/查新，附历史路径、任务 ID 与产物哈希，同时加载 `revise-hypotheses`。不注入同轮尚未提交观点，不编造缺失历史；旧版本未记录 batch 引用的修订不自动推断关联。改变旧 ID 下的问题、假设、机制、前提、最近邻、反证、实验计划或来源字段会被拒绝，需要新 ID 重新通过下游。这是字段值检查，不是自然语言语义证明；谱系和回应日志仍需审查。

首轮 hypothesis 所有请求在接收任何候选前创建，只有各自知识和共同材料。全员完成后才创建 challenge，审查其他专家的候选。临时专家通过 selection 邀请，经 consultant 构建、独立验收后参加。

ideation 使用带讨论循环的 16 个阶段，见[讨论循环](ideation-discussion.md)。领域专家选论文、主持议程并综合方案，程序控制派单与推进；这是独立上下文之间的产物交接，不是自由对话池。旧契约创建的运行会被拒绝继续，需要 `run --new`。

修订回传最近实际发生的综合和终审记录，保留各自原始版本，防止只剩操作者填写的简短原因。多次作者修订但尚无新裁决时，旧裁决继续作为历史证据；不继承其批准状态。`submit/revise/feedback` 在写入前检查当前及冻结的研究输入。损坏旧记录时显式 `run --new` 可以新建独立运行，普通恢复仍拒绝损坏记录。

## 查看六维评审

独立终审为当前全部候选及最终提案分别填写六维评分：问题价值、新颖性与研究增量、机制与逻辑合理性、已有依据的可靠性、实验判别力、实施可行性。各项是 1–5 的整数及其理由和证据；材料不足显示“未知”，不以 0 分或中间分代替。

```bash
paperagents review <project>
```

该命令显示当前轮次的中文 Markdown 报告，含候选对照表、最终提案评分、逐项理由与证据、准入检查和阻塞项。终审未通过也能查看，不必等待 `completed`；尚无终审或历史记录没有评分时明确提示。报告不生成加权总分或综合排名，不根据分数自动改变选择和批准状态。最终提案单独评分，避免直接沿用原候选的分数。

有当前终审记录时，`status` 的 `review_summary` 提供评分摘要，`review_artifact` 指向原始评审 JSON。修订后只展示新一轮当前评审；旧记录仍保存在历史产物中，不作为新版本的批准或分数。

评分通过 `context.review_targets` 中的候选和提案摘要绑定版本；提交时检查候选覆盖和摘要匹配。它保证评分记录指向指定对象，不证明内容理解正确，也不解决综合方案与原候选科学内容是否一致的全部审查问题。评分标准见[六维评分约定](../../skills/references/review-scoring.md)，结构见[产物契约](artifacts.md)。

评审没有旧格式分支；不会事后补造分数。

## 资产与反馈

`library/papers/<id>/<version>` 保存论文记录和全文；`library/experts/<id>/<version>` 保存专家知识与知识 skill。领域/论文构建前按 `expert_id` 发现项目内旧 `asset.json`，有候选才加载 `reuse-and-update-expert`。这是身份检索，worker 仍需核验完整性、来源、范围、时效、契约和工具条件，并重新提交完整产物接受审查；不会自动跳过构建、导入其他项目或继承验收。

v2 知识含 `communication_analysis` 或 `reuse_assessment` 时，生成相应 JSON 分视图及索引，纳入快照哈希检查。这些是允许的扩展记录，暂未提供专用字段/引用校验；保存成功不证明分析或复用判断正确。

论文全文、工具源码与验证材料按内容保存版本。导出任务包含材料副本和 `source_path_map`，将原始绝对路径映射到任务内相对路径；原记录中的工具 entrypoint 通过此映射定位，科学文本不被自动改写。

公开搜索反馈格式：

```json
{
  "evaluation_split": "search",
  "run_id": "真实运行标识",
  "code_version": "真实代码版本",
  "data_description": "数据集、划分、范围",
  "configuration": {"配置": "实际值"},
  "findings": ["观察与不确定性"],
  "artifact_refs": ["可定位的结果文件"]
}
```

手工 `feedback` 只接受 `evaluation_split=search`。这是结构和来源登记接口，不能识别人为错标或替代科学真实性审核。原生实验由协调器自动生成更完整的反馈，附候选引用、提案摘要、代码和数据说明、冻结协议及真实结果路径，并触发 `hypothesis` 修订；不需要用户手工转写分数。该主链目前只执行搜索实验，没有实现封存的最终评估，最终评估数据不得混入回流。

专家资产可在本项目内按身份和版本发现、检查并复用；当前没有自动跨项目语义检索，也不会仅因保存了方法记录就自动启动 MCP 服务。可调用工具仍取决于真实实现、环境和验证证据。

## 原生实验与回流

`research` 先推进 ideation，提案通过后进入实验准备；`experiment` 要求 ideation 已完成，直接准备或恢复该提案的实验。两者默认不执行评估器，只有 `--execute` 才运行获批的实验。未加该参数仍可能调用已配置的模型后端完成构思、代码构建和独立审查，因此它不是整个流程的空运行。

1. **experiment_build**：工程 worker 根据已审查提案创建 `evaluate.py`、基线 `program_0` 和候选 `program_1`，记录同一评价协议、数据、配置、对照、指标及判读规则。资料或资源缺失时返回 `needs_evidence`，不使用占位数据代替。
2. **experiment_review**：另一个独立 worker 检查协议与假设一致性、基线公平性、代码忠实性、数据完整性和资源可行性。审查绑定提案、源码清单与构建版本，五项有证据通过且无阻塞项才放行。
3. **实际执行**：协调器在本机 Python 环境，以同一份冻结评价器和输入分别评估基线、候选，保存命令结果、原始指标、有效性记录及收据。基线运行失败或协议无效时不继续拿候选作有效比较。`correct` 表示协议有效，不表示假设得到支持；`combined_score` 的科学含义和方向由已审查的协议说明。
4. **专家修订**：真实 `search` 结果由协调器登记，再显式调用 `revise("hypothesis", ...)` 和 `workflow.run()`。领域、论文及已邀请专家获得结果和历史记录，重新提出、质疑、查新与审查。一次执行只处理一组基线／候选并启动下一轮 ideation，不是无限实验循环。

实验记录位于 `runs/<run_id>/experiments/rNNN/`，包含 `requests/`、冻结的 `workspace/`、执行副本、`results/`、`feedback.json` 与 `state.json`。构建／审查期间，`research/experiment` 返回 `awaiting_workers`、`needs_evidence` 或 `ready_for_experiment`；周期完成回流后，`experiment_status=completed`，顶层 `status/phase/pending` 显示下一轮 ideation 的实际状态，例如 `awaiting_workers/hypothesis`。不要把周期完成解释为整个研究完成或科学成功。手工后端填写返回的 `response_path`，再调用 `research/experiment` 继续，实验任务不通过 ideation 的 `submit` 命令提交。

构建因资料不足返回 `needs_evidence` 时，补齐真实文件并更新原构建响应后继续。当前轮次的独立实验审查拒绝后，使用 `paperagents experiment <project> --rebuild` 创建新的构建目录（例如 `r001-build002`），保留原文件与拒绝记录，并将旧意见交给新构建任务；不要直接改写已经冻结的构建或评审。后续专家提案再次获批后，可再次显式调用实验入口，为新版本建立新的实验周期。

协调器在执行前核验获批导出、构建、评审及输入文件，运行中断会留下不充分记录而不是伪造完成。原生执行复用 v3 的底层 Python `run_evaluation` 与程序接口，不进入其任务构建／调查控制循环。执行副本和哈希用于可追溯性，不提供操作系统级沙箱；Python 可执行文件和输入文件有身份记录，已安装依赖仍需真实环境记录支持。

## 首轮真实试跑

先用一个明确问题跑通“真实文献 → 专家构思 → 获批提案 → 判别实验 → 专家修订”，用于找流程问题。默认 `manual` 会等待真实 worker 产物，不能把它理解为已配置自动模型调用；可以由当前宿主 agent 逐项执行，也可配置 `command` driver。

在仓库根目录使用本地虚拟环境，收到问题 Markdown 后：

```bash
.venv/bin/python -m paperagents init projects/first-study --brief-file /absolute/path/to/question.md
.venv/bin/python -m paperagents research projects/first-study
.venv/bin/python -m paperagents review projects/first-study
# 构思已通过后，可单独准备／恢复实验构建及独立审查。
.venv/bin/python -m paperagents experiment projects/first-study
# 审查通过才执行；结果自动回到专家的 hypothesis 修订。
.venv/bin/python -m paperagents experiment projects/first-study --execute
# 也可从当前构思状态推进到同一条实验链路。
.venv/bin/python -m paperagents research projects/first-study --execute
```

上面两种 `--execute` 入口是替代用法；实际试跑选择其中一种推进并按返回状态继续。获批任务书、专家材料和提示由运行状态中的收据核验，原生实验代码与结果保存在实验周期目录。旧运行没有可信导出收据时，需重新综合、评审和导出。

原生主链的协调与评估器调用走本机 Python，不强制 Docker、Bash 4+ 或 Headless。研究算法、数据和模型依赖仍需按具体问题准备，并在构建产物中指定可用的绝对 Python 解释器路径；虚拟环境放在冻结源码目录之外。`execution.experiment_timeout_seconds` 控制单次评估超时。执行时要求所需输入已就绪，不能把资源不足静默改成较小目标或假数据。

截至本轮文档更新，尚未收到首轮真实研究问题 Markdown，也未完成实际模型驱动的科研试跑。已有框架测试与合成 CPU evaluator 检查只能证明对应控制和执行路径，不能证明 ideation 的科学效果或优于单 agent。

首次试跑检查四类实际证据：

1. **文献与理解**：抽查关键主张、原文锚点、实验解释和代码映射，发现失真时回到相应阶段；来源数量和填满字段不代表学会。
2. **讨论是否有用**：保留候选、具体异议、真实修订和六维评分；指出每次改动解决了什么问题。无依据的附和、格式返工与有科学意义的修订分别记录。
3. **能否执行并检验**：核对实际实现仍对应获批机制，固定数据划分、基线、指标、资源条件和支持／反驳／不充分的判读规则。运行失败与假设被反驳分开，负面但有判别力的结果也是有效信息。
4. **能否纠错**：导入允许的搜索反馈，观察专家是否依据结果修改假设、撤回错误解释或请求真正有用的新实验。只重复原说法不能算闭环有效。

每阶段保存实际调用次数、可获得的 token／费用、耗时、格式重试、缺证阻塞及人工介入；后端没有提供的计量记“不可得”，不估造。当前框架保存任务、尝试、driver 日志及产物，但没有统一 token／费用统计器。

确认链路能执行后，再比较三组：A 原 v3 单 agent；B 单 agent 加相同文献；C 当前专家协作。A→B 看文献贡献，B→C 看专家协作增益。各组使用同一研究问题、模型、冻结实验框架、数据／指标、明确的构思预算和实验资源条件；不能让各自生成不同评估器后直接比分数。匿名独立核查新颖性、实现成功率、有效实验结论、相对基线效果及不确定性，同时记录额外开销。六维自评分用于解释过程，不作为系统有效的唯一结论；一个问题只能检验这一案例，不能证明总体优于 v3。

## 已留出的扩展边界

- 检索、下载和实际工具构建由 worker 的真实工具完成，框架不生成假搜索记录。
- `code_tools` 清单与真实调用能力分开验收。
- 原生主链已能把一次实际搜索实验回流到专家修订；v3 已有领域专家议程、多轮作者答辩与复核。讨论中途的实验探针和自动连续实验策略尚未实现。
- 原生实验工程、审查与评估要求真实 worker 和实际依赖；结构通过不能代替原方法复现、科学解释或最终封存评估。
- Skills 固定版本，尚未自动自我修改。

## 旧 v3 与独立对照

原 v3 源码和安装说明保留用于参考及独立对照；其 `create-idea`、单 agent 调查循环和论文流程不属于当前原生主链。`paperagents v3` 仅兼容旧版／显式 `legacy` 导出，新项目的 `native_expert_loop` 导出会拒绝这个入口，避免悄悄退回旧构思循环。显式比较旧流程时才使用其 Hydra、Docker、Bash、Headless 等实际运行要求，详见[上游说明](upstream.md)和[旧 v3 安装说明](../install.md)。

## 连续研究与中断恢复

`python -m paperagents research <project> --execute` 现在统一推进：
构思与补证据 → 独立评审 → 实验构建 → 实现独立审核 → 基线/候选实际执行
→ 保存 search 反馈 → 作者修订 → 讨论/查新/重新评审。

默认累计完成一轮实验及其反馈后的 ideation；`--max-experiments 2` 允许累计两轮。
上限按当前运行已完成的实验周期计算，不按命令调用次数重置；需要继续更多实验时
显式提高上限。失败的实际执行也会形成反馈，专家必须区分执行故障和科学负结果。

恢复时优先接回未完成的实验（尤其是反馈登记过程中中断的情况），再推进 ideation。
已提交的实验结果由现有收据复用，不重复运行。构建缺资源、实现审核拒绝、
专家需要人工或工作任务重试耗尽时停止，保留具体原因；不会无限循环。

不加 `--execute` 仍可构建和审核实验，但停在 ready_for_experiment，不执行评价。
`run` 继续保持纯 ideation；单次 `experiment` 入口仍保留。
当前正在执行 run 的进程不会热切换成 research：等它结束后再执行新命令，
同一项目不要同时启动两个协调器。不必 --new，也不必重新构建文献和专家。
