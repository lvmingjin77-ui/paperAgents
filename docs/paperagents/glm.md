# GLM 后端

`[backend] kind = "glm"` 使用 Claude Code CLI 作为工具驱动，模型请求发往 `[glm].base_url`。模型、快速模型和子任务模型均使用配置的 GLM 名称。默认模板为 `manual`，不会主动调用模型。

先确认环境能找到 `claude`，再由操作者将 `ZHIPU_API_KEY` 加入终端环境。不要把真实密钥放进 TOML、研究简介、Git 或日志。本地旧凭据文件不是项目交付内容。

```toml
[backend]
kind = "glm"
timeout_seconds = 1800

[glm]
model = "glm-5.2"
fast_model = "glm-5.2"
base_url = "https://open.bigmodel.cn/api/anthropic"
api_key_env = "ZHIPU_API_KEY"
search_mcp_url = "https://open.bigmodel.cn/api/mcp/web_search_prime/mcp"
agent_command = "claude"
```

模型与搜索服务可能使用不同的资源额度。权限、余额或工具错误先看任务输出和网页错误页；失败不能冒充检索完成。修复具体原因后，用 `retry` 登记任务，再恢复研究。

本轮改造未测试供应商模型可用性、账户额度或真实科研效果。不同角色使用同一基础模型仍可能共享偏差，角色隔离不保证认知独立。
