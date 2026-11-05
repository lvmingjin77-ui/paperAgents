# GLM-5.2 本机配置

当前 CIR 项目位于 `projects/cir-reliability/`，研究问题原样取自根目录的 `task.md`。
其 `paperagents.toml` 使用 `glm` 后端，由统一的 `paperagents.glm_worker` 执行。
全部 ideation 专家、查新、独立评审、实验构建和实验审查共用这个后端。
本轮团队为 1 位领域专家和 2 位论文专家，按需邀请临时专家；独立评审任务仍保留。

模型固定为 `glm-5.2`，通过本机已有的 Claude Code 执行文件读写、检索和命令工具，
推理请求发往智谱官方 `https://open.bigmodel.cn/api/anthropic`。
主模型和内部小模型别名均设为 GLM-5.2，无备用模型。
检索接入智谱 Web Search Prime MCP，也可通过本地命令读取公开论文、仓库和数据源。
MCP 认证引用子进程环境变量，密钥不出现在命令行参数中。
逐任务输出保存在原有 `driver.log` 中。

密钥保存在仓库根目录 `.env.glm.json`，文件权限为 `0600`，由现有 `.env.*` 规则忽略。
也可用 `ZHIPU_API_KEY` 环境变量覆盖。密钥不写入项目配置、研究材料或实验源码。
此设置只影响该项目启动的 worker，不修改系统或用户全局模型配置。

## 启动

使用已安装项目依赖的 Conda `paperAgents` 环境，在仓库根目录执行：

```bash
conda activate paperAgents
cd /Users/lvmingjin/Desktop/paperAgents/paperAgents
python -m paperagents research projects/cir-reliability
```

该命令会真实调用 GLM 完成构思及实验准备，默认不执行研究评价器。
要运行获批实验并将结果回流专家，由操作者执行：

```bash
python -m paperagents research projects/cir-reliability --execute
```

在另一个终端中激活相同环境并进入相同目录，可打开只读网页：

```bash
python -m paperagents web projects/cir-reliability
```

浏览器访问 `http://127.0.0.1:8765`。

GLM-5.2 只支持文本。图像、图表的视觉判断不能当作已由该模型核验；
论文正文、表格及图注可通过本地工具提取，无法核验的视觉证据须记录缺口。
本地检索模型不经过 agent 后端；如实验本身需要在线模型 API，仍只能选用 GLM-5.2，
并须在实验构建时明确其运行凭据需求，不能把密钥塞入冻结源码或结果。

本次只配置接入，没有调用模型验证密钥权限、余额或接口可用性，也没有启动研究或实验。

官方依据：[GLM-5.2](https://docs.bigmodel.cn/cn/guide/models/text/glm-5.2)、
[Claude Code 接入](https://docs.bigmodel.cn/cn/coding-plan/tool/claude)。
