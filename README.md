# PaperAgents

PaperAgents 的主链：明确研究问题 → 领域／论文专家构思 → 独立评审 → 本机实验 → 结果回流专家。复用 AI-Scientist-v3 的底层 Python 评估器，主链不调用旧单 agent 构思或容器任务构建器。

## 当前实现

- 主入口是 `paperagents research`；保留 v3 源码及 `agsci` 入口用于参考和单独对照，新的原生任务会拒绝交给旧构思入口。
- 已实现可恢复状态机、独立 worker 任务、并行命令后端、产物契约与跨产物校验、独立验收、补证后重做和版本化知识资产。
- 新运行使用专家讨论循环（作者逐条答辩、原质疑者复核、领域专家主持议程），详见[讨论循环](docs/paperagents/ideation-discussion.md)。
- 21 个项目内 skills。论文专家默认预载 5 项核心技能，表达学习和方法封装／验证按需加载；理解、论证轨迹、迁移策略、源码映射始终保留。
- 实验工程任务只实现获批方案，独立审查后用同一评价器执行基线与候选；真实搜索结果自动登记并触发专家修订。新主链不要求 Docker、Bash 或 Headless。

这是可运行的框架。真实检索、全文阅读、工具构建和科学判断由配置的 agent/工具执行。默认仅生成任务，不调用模型。测试中的虚构论文仅用于临时测试，不是研究成果。JSON 校验与 dry-run 不证明科学结论成立。

## 目录

```text
paperAgents/
├── paperagents/            # 专家调度、本机实验、契约、知识资产与交接
├── skills/
│   ├── knowledge/         # 文献、研究思路、领域/论文专家、验收
│   ├── engineering/       # 论文代码映射、工具封装和验证
│   ├── ideation/          # 假设、质疑、查新、判别实验、提案
│   ├── review/            # 科学工作审查
│   ├── profiles/          # 领域、论文、临时专家的角色职责
│   ├── references/        # 共用证据及产物协议
│   └── registry.json      # 技能注册表
├── src/                    # 保留的 v3 底层执行工具及单独对照实现
├── configs/                # v3 Hydra 配置
├── examples/research/      # 研究需求示例
├── tests/paperagents/      # 新框架与交接测试
└── docs/paperagents/       # 运行、专家、产物和版本说明
```

## 开始使用

需要 Python 3.11+。本次已建立本地 `.venv`，可用 `.venv/bin/python` 运行下面命令。完整依赖可用 `uv sync --group dev` 或 `python -m pip install -e .` 安装；本版以源码/可编辑安装运行。

```bash
python -m paperagents init projects/my-research --direction "提高长上下文语言模型的推理效率"
python -m paperagents plan projects/my-research
python -m paperagents research projects/my-research
python -m paperagents status projects/my-research
```

已有研究问题 Markdown 时，用 `python -m paperagents init projects/my-research --brief-file /absolute/path/to/question.md` 原样导入；它与 `--direction` 二选一。首轮试跑步骤和效果判定见[运行指南](docs/paperagents/runtime.md#首轮真实试跑)。

默认 `manual` 后端生成 `requests/<task_id>/request.json` 和 `prompt.md`，在 `awaiting_workers` 等待结果。由有相应工具的 agent 完成任务，把符合 schema 的数据对象写入 `response.json` 后提交：

```bash
python -m paperagents submit projects/my-research TASK_ID /absolute/path/to/response.json
```

提交会推进下一阶段；也可让 worker 写入指定响应路径后再次 `run`。自动执行使用项目配置中的 `command` 后端，每个 worker 独立启动进程，详见[运行指南](docs/paperagents/runtime.md)。

## 用 GLM 运行并在网页上观察

所有模型调用都走智谱 GLM：每个 worker 是 Claude Code CLI，模型端点指向智谱的 Anthropic 兼容接口，文献检索用智谱的 `webSearchPrime` 搜索工具。

```bash
export ZHIPU_API_KEY=你的智谱APIKey          # 只从环境变量读取，不写入任何文件
paperagents init myproj --brief-file task.md  # 原样复制你的研究简介
# 把 myproj/paperagents.toml 里 [backend] 的 kind 改为 "glm"；模型名等在 [glm] 段
paperagents web myproj &                      # 打开 http://127.0.0.1:8765
paperagents research myproj --execute         # 构思 → 一轮实验 → 反馈修订与重新评审，可中断续跑
```

需要先安装 Claude Code CLI（`claude` 命令）。网页只读，不修改运行目录，可在运行中随时打开：

- **对话池**：所有专家的提案、议题、异议、答辩、复核、查新、综合和评审，按顺序排列，可筛选；
- **任务**：按阶段列出每个任务的状态、尝试次数和错误；展开可看输入（上下文、技能）、agent 每一步的消息与工具调用、被拒绝的提交和最终输出；
- **错误**：停止原因、当前失败的任务、历史拒绝记录；
- **专家 / 领域图谱 / 实验 / 时间线 / 研究简介**。

左侧阶段栏显示运行到哪一步（✓ 已完成，▶ 当前），数字是该阶段完成的任务数，`!` 表示有失败。

## 研究流程

```text
research.md
 → scope：方向、近三年会议范围和相关性标准
 → corpus：检索相关论文、全文路径、覆盖记录
 → reading：逐篇阅读，输出论证轨迹和结构化论文卡（问题、方法、结果及条件、论文间关系）
 → domain：协调器把论文卡合并为领域图谱；领域专家据此给出演化链、争议、空白、评估协议盲点
 → selection：核心论文（默认三篇，可配 2–5）＋按需临时专家
 → paper / consultant：知识、代码映射和工具能力
 → expert_review：独立验收
 → hypothesis：各专家独立提案（密封）
 → triage：轻量重叠初筛
 → agenda：领域专家列出讨论议题
 → challenge：编号异议
 → rebuttal ⇄ recheck：作者答辩 ⇄ 原质疑者复核（多轮）
 → novelty：对有效候选深度查新
 → synthesis：研究提案或补证请求
 → proposal_review：独立复核（含"全部不选"的决定）
 → experiment_build：实现获批方案、基线和搜索评价器
 → experiment_review：独立审查代码与实验协议
 → 本机 Python：运行基线和候选，保存真实输出
 → search 反馈 → hypothesis 修订与重新审查
```

近三年默认是运行开始时向前滚动三个日历年，截止日期固定在 run 中。不得以 Top-K 检索冒充全部相关论文学习；缺全文或覆盖不完整时暂停补证。必要的更早奠基论文可作为注明身份的背景材料。

研究思路区分 `author_stated`、`reconstructed`、`unknown`。工具能力区分 `documented`、`wrapped`、`tested`、`reproduced`。验证规模由研究问题决定，不强制低成本实验。

新 run 对领域/论文知识启用 v2 契约：论文需交付理解档案、带来源的论证图和策略卡，校验文件哈希、已读锚点及策略引用。知识包提供分视图索引；材料覆盖不完整时保存缺口并停止晋级。详见[论文专家能力设计](docs/paperagents/paper-expert-capabilities.md)。

## 本机实验与反馈

独立提案审查通过后导出 `runs/<run_id>/exports/rNNN/task/`。继续准备本机实验；显式执行后，结果会回到专家：

```bash
python -m paperagents experiment projects/my-research
python -m paperagents experiment projects/my-research --execute
# 从 ideation 开始持续推进到一次实验及其专家修订：
python -m paperagents research projects/my-research --execute
# 最多完成两轮实验，每轮之后均回到专家修订及独立评审：
python -m paperagents research projects/my-research --execute --max-experiments 2
```

`manual` 后端遇到工程或审查请求时会返回待处理任务；宿主完成指定响应后再次调用同一命令继续。`command` 使用配置的真实 agent driver。没有 `--execute` 时停在实验准备就绪；一次执行完成后进入专家修订，不无限循环开新实验。

实验代码被独立审查拒绝时，用 `paperagents experiment projects/my-research --rebuild` 派发新的构建任务，保留旧代码与拒绝意见。工程或审查响应直接写入返回的 `response_path` 后重跑 `experiment`；`submit` 只接收 ideation 任务。

原生实验仍需要真实的数据、模型／算法依赖及适合问题的算力；缺失时停止并报告，不生成虚构指标。执行使用独立工作目录和版本校验，不提供容器级文件系统隔离。本入口只处理公开搜索实验，封存最终评估须另行管理。旧 v3 容器流程的要求不再是本项目主链的要求。

本机实验自动回传结果；外部实验仍可显式登记并返回指定阶段：

```bash
python -m paperagents feedback projects/my-research /absolute/path/to/search-feedback.json
python -m paperagents revise projects/my-research --from hypothesis --reason "补充了区分两个机制的搜索实验"
```

领域与论文专家的知识包保存在项目内版本库；后续构思与实验回流复用既有知识，不重新构建所有专家。临时专家主动邀请、完全自适应的多轮议程、跨项目自动知识检索和自动 skill 修改仍未实现。最终保留评估的数据不得回流构思。

## 检查与文档

```bash
python -m pytest tests/paperagents -q --basetemp=/private/tmp/paperagents-tests
```

[运行指南](docs/paperagents/runtime.md) · [讨论循环](docs/paperagents/ideation-discussion.md) · [专家设计](docs/paperagents/experts.md) · [产物协议](docs/paperagents/artifacts.md) · [Skills](skills/README.md) · [Skills 调研与审查](docs/paperagents/skills-audit.md) · [验证记录](docs/paperagents/verification.md) · [上游版本](docs/paperagents/upstream.md)

底座来自 SakanaAI/AI-Scientist-v3，保留 Apache-2.0 [许可证](LICENSE)和原作者信息。旁边的原始 `AI-Scientist-v3/` 未修改。
