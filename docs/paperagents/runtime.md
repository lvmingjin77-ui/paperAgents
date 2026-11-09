# 运行与恢复

## 新建

```bash
python -m paperagents init projects/my-research --brief-file /absolute/path/to/research.md
```

检查 `research.md` 与 `paperagents.toml`。科学要求放 Markdown；执行资源、模型和预算放 TOML。`inputs/` 可放已有数据、代码或论文。

`manual` 是默认后端：暂停在 `awaiting_workers`，请求位于 `runs/<run_id>/tasks/<task_id>/attempt-001/request.json`。完成请求指定的 JSON schema 后提交：

```bash
python -m paperagents submit projects/my-research TASK_ID /absolute/path/to/response.json
python -m paperagents research projects/my-research
```

自动后端见 [GLM 设置](glm.md)。`--execute` 仅控制协调器的实验执行，不控制模型调用或文献下载。

## 真实运行由操作者启动

```bash
python -m paperagents research projects/my-research --new --execute
python -m paperagents status projects/my-research
python -m paperagents web projects/my-research --port 8766
```

网页只读，地址 `http://127.0.0.1:8766`。`--new` 创建新运行，恢复时不要加。`run` 与 `research` 是同一链路的入口。

添加 `--until PHASE` 可在某阶段前停止；可选阶段见 `python -m paperagents research --help`。Ctrl+C 保留完成任务和执行收据；未完成任务会重新尝试，不能恢复模型尚未提交的内部状态。

```bash
python -m paperagents research projects/my-research --execute
```

## 暂停后怎么处理

| 状态或原因 | 操作 |
|---|---|
| `awaiting_workers` | manual：提交响应；GLM：查看失败任务和工具错误 |
| 任务尝试耗尽 | 修复具体原因，执行 `retry PROJECT TASK_ID`，再运行 `research` |
| `ready_for_experiment` | 使用 `research PROJECT --execute` 继续 |
| 检查点要求确认 | `approve PROJECT testbed/final_method/submission`，再运行 `research` |
| `needs_materials` / `needs_human` | 阅读缺口，补材料或调整研究条件 |
| `needs_latex` | 安装或修复本机 TeX 环境，恢复后重新编译 |
| 最终测试已打开 | 不自动重试或回到构思；新研究使用新的独立测试集和新运行 |

`retry`、`approve`、`submit` 只登记，不启动研究。科学修订用：

```bash
python -m paperagents revise projects/my-research --from evolve --reason '修订原因'
python -m paperagents research projects/my-research --execute
```

入口为 `knowledge`、`testbed`、`evolve`。仍在知识阶段时，可用 `--from domain` 定向修订领域全景并重新选队、构建专家，复用文献与阅读，保留旧产物，不消耗方向轮数。评测底座建立后，领域前提改变应使用完整 `knowledge` 修订。修改科学输入或数据范围后须新建运行；旧版 `experiment`、`feedback` 入口不适用于 0.2。

## 预算与资源

互不依赖的 worker 任务按 `execution.max_parallel` 并发，实验执行串行；`wall_clock_days` 只计运行时间。评测器须输出 `units.json`，比较按统计单位做配对 bootstrap。配置 `gpu = "mps"` 不代表已验证所有模型可运行，仍取决于实验依赖。

`api_budget` 与 `api_cost_per_call` 使用同一货币单位；协调器每次调用保守预留后者，不读取供应商账单。`api_budget = 0` 表示无货币上限；调用次数与墙钟上限仍生效。

自动模式要求系统沙箱。Linux bubblewrap 路径尚未在本机验证；显式 `sandbox = "none"` 会失去相应隔离。LaTeX 需要本地 `latexmk` 或 `pdflatex`，有引用时还需 BibTeX 工具；程序不会自动安装。

## 复制项目迁移

`paperAgents02/projects/cir-reliability/` 的旧输入备份到 `.backup/input-migration/`。新输入保留科学目标并移除旧流程指令；旧运行与 `active_run.json` 未改动。

```bash
cd /Users/lvmingjin/Desktop/paperAgents/paperAgents02
conda activate paperAgents
python -m pip install -e .
python -m paperagents research projects/cir-reliability --new --execute
```

运行前按需配置 GLM 凭据。原 `paperAgents/` 目录不受迁移影响；同一 Python 环境的 editable 安装会指向最后安装的项目副本。
