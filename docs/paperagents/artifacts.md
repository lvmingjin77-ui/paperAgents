# 产物与追溯

输入是 `research.md`、`paperagents.toml` 与可选 `inputs/`。新版运行保存在 `runs/<run_id>/`：

| 路径 | 内容 |
|---|---|
| `state/research.json` | 阶段、主张版本、证据、运行、任务、专家与草稿 |
| `events.jsonl` | 阶段和状态事件 |
| `tasks/<id>/attempt-NNN/` | 请求、提示、响应、driver 日志和校验反馈 |
| `workspace/` | 底座、方法和数据工作区 |
| `executions/` | 执行收据、日志、有效性与原始指标 |
| `paper/outline.md` / `outline.json` | 主张—证据提纲 |
| `paper/figures/` | 实测生成的 PDF、PNG 与来源记录 |
| `paper/<version>/` | LaTeX、数字宏、引用、图表、主张绑定与编译日志 |
| `frozen.json` | 最终测试前冻结的方法、协议和主张 |

具体执行路径以状态中的 `request_path`、`artifact_refs` 和草稿 `path` 为准。

主张使用 `claim_id@version`。修订产生新版本，实验不能静默移交给其他版本。成功退出不自动证明科学主张成立；实现失败、协议无效与预算耗尽分别记录。

数字宏来自成功执行，图表区分协议、划分和实现版本。引用必须来自已有文献，语义是否支撑论文由评审判断。网页过滤 `thinking_tokens`，保留实际消息、工具结果和错误；这些是模型公开的记录，不代表隐藏的内部思维过程。

`library/` 保存材料与可复用资产，复用时仍检查来源和用途。旧资产不自动成为新版验收结果。
