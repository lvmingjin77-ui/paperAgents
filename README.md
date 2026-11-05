# PaperAgents

从明确的研究问题出发，让领域与论文专家提出方法，经独立批评、真实实验和论文评审迭代，形成可追溯的 LaTeX 论文。当前是 0.2 重构版本，科研质量仍需真实试跑验证。

三个循环共用主张版本、证据和运行记录：

- **研究方向**：文献与专家 → 评测底座 → 检查问题是否值得且能够研究。
- **想法与实验**：独立提案 → 交流与去重 → 实现和筛选 → 解释、查新、消融 → 修订。
- **论文**：随证据更新提纲 → 初稿和独立评审 → 必要的开发集补充实验 → 冻结 → 最终测试 → 定稿。

效果未知可以交给实验；实现错误、协议无效与假设被反驳分别记录。最终测试数据不回流构思。

## 使用

需要 Python 3.11+，安装到自己选定的环境。研究运行由操作者启动。

```bash
python -m pip install -e '.[dev]'
python -m paperagents init projects/my-research --brief-file examples/research/research.md
# 或：python -m paperagents init projects/my-research --question '一个明确的研究问题'
```

输入是 `research.md`（问题、指标、有效性要求和非约束线索）与 `paperagents.toml`（模型、资源、数据许可、预算、循环和输出）。已有材料可以放进项目的 `inputs/`。

默认 `backend.kind = "manual"`：生成任务后等待人工提供响应，不调用模型。自动运行改为 `"glm"`，安装可用的 Claude Code CLI，并通过 `ZHIPU_API_KEY` 环境变量提供凭据。不要把密钥写入研究输入或 Git。

```bash
python -m paperagents research projects/my-research --new --execute
python -m paperagents status projects/my-research
# 在另一个终端打开只读网页：http://127.0.0.1:8766
python -m paperagents web projects/my-research --port 8766
```

`--new` 只用于新建运行，恢复时去掉；`--execute` 授权协调器执行审查后的实验。省略它仍可能调用 GLM、下载材料和生成代码，但会在执行实验前暂停。

```bash
# Ctrl+C 后恢复当前新版运行
python -m paperagents research projects/my-research --execute
# 给失败任务增加一次尝试，然后恢复
python -m paperagents retry projects/my-research TASK_ID
# 仅在已启用的检查点暂停时确认，然后恢复
python -m paperagents approve projects/my-research testbed
# 科学修订入口：knowledge、testbed 或 evolve
python -m paperagents revise projects/my-research --from evolve --reason '根据开发集结果修改机制'
```

旧版本运行不能续接新版。保留旧产物，新建运行；旧 `library/` 只能作为资料来源，不能直接视为已验收的新证据或专家。

## 当前边界

- 当前串行调度。
- API 货币预算使用每次调用的保守预留，不是真实账单；`api_budget = 0` 取消货币上限，调用次数上限仍生效。
- macOS 使用系统沙箱，Linux 提供 bubblewrap 路径但尚未在本机验证；默认不静默降级为无沙箱。
- 需要真实数据、模型和可用资源；资源不足会保留缺口，不生成虚构分数。
- LaTeX 编译器缺失会暂停。图表来自成功运行，引用和数值来源可追溯，程序核对不能替代科学评审。

网页展示任务输入输出、专家交流、证据、六维评分、工具错误、实验、图谱和草稿；过滤 `thinking_tokens` 噪声，刷新保留折叠，时间使用北京时间。

[运行说明](docs/paperagents/runtime.md) · [链路梳理](docs/paperagents/链路梳理.md) · [专家](docs/paperagents/experts.md) · [产物](docs/paperagents/artifacts.md) · [改造方案](docs/paperagents/redesign.md) · [验证边界](docs/paperagents/verification.md)

最初从 AI-Scientist-v3 派生；新版使用自己的协调器、运行器和写作链。保留 Apache-2.0 [LICENSE](LICENSE)、[NOTICE](NOTICE)及[上游归属](docs/paperagents/upstream.md)。
