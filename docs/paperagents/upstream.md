# 上游版本

- 来源：https://github.com/SakanaAI/AI-Scientist-v3
- 固定 commit：`df8313889a004f8a44a472e19a833cd547bb828a`
- 提取日期：2026-11-03（Asia/Shanghai）
- 使用 `git archive HEAD` 提取全部跟踪文件，不包含 `.git`、凭据、未跟踪文件或运行缓存。
- 原仓库 `/Users/lvmingjin/Desktop/paperAgents/AI-Scientist-v3` 未修改。
- 保留根目录 Apache-2.0 `LICENSE` 和源码原作者信息。

原 README 位于 [README.v3.md](../upstream/README.v3.md)，其中相对链接仍以原仓库根目录为基准。

## 当前主链与复用边界

新增的 `paperagents/`、根 `skills/`、相关示例、文档与测试构成当前项目主链。新运行导出 `native_expert_loop`，入口是 `paperagents research` 和 `paperagents experiment`；加 `--execute` 才运行经过审查的实验。原 v3 的 `create-idea`、任务构建／调查控制循环和自动论文流程不在这条主链中。

PaperAgents 自己负责 `experiment_build → experiment_review → 基线／候选执行 → search 反馈 → 专家 hypothesis 修订`。底层复用 `src/investigation/evaluate_program.py` 的 Python `run_evaluation` 及程序接口，负责实际进程运行、输出和评估收据；这不等于调用原 v3 的构思 agent。主链在本机 Python 执行，不以 Docker、Bash 4+ 或 Headless 作为必需条件。具体算法的数据、模型、环境与算力仍由研究任务决定。

已审查科学核心、专家知识和来源版本随任务导出；运行状态保存可信收据，实验源码、评价器和协议另行冻结。真实结果回到专家修订，原生实验当前只覆盖搜索阶段，没有实现封存最终评估或自动写作。知识复用限于项目内版本发现与重新验收，尚非自动跨项目检索或自动 MCP 服务部署。

## 旧版对照与兼容

保留 v3 源码、原作者信息、许可证和安装文档用于参考及独立对照；相邻原仓库保持不变。项目内原调查入口的条件 hook 仍用于旧版专家材料导出；检测到原生任务时会拒绝进入旧的单 agent 构思流程。`paperagents/v3.py` 的 `export_task(..., mode="legacy")` 与旧 `paperagents v3` 入口保留对照兼容，新主链显式使用 `mode="native"`。

需要比较旧 v3 时，单独使用其任务快照、idea bundle、harness、search/final 隔离及安装要求，不能把两种模式混在同一实验中。旧流程的 Hydra、Docker、Headless 和 Bash 要求见[旧安装说明](../install.md)；不把这些要求套用于原生主链。

截至本轮，尚未收到首轮真实研究问题 Markdown，也没有完成实际模型驱动的科研试跑；框架与合成 evaluator 测试不证明科学效果。带讨论循环的 16 阶段 ideation、21 项按需加载的 skills 及当前边界见[运行指南](runtime.md)与[专家设计](experts.md)。
