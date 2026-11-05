# 方法工具调用与证据示例

以下是虚构的教学示例，未创建文件、未运行方法、未验证任何论文。路径、版本、期望值均用于解释记录方式；不要原样提交或据此提升能力状态。工具 `affine_values` 只演示简单接口行为，不代表科研方法或论文结论。

## 兼容当前 schema 的工具条目

该对象放入 `paper.code_tools`；`implementation` 与 `invocation` 是当前允许的扩展字段，不是新增强制 schema。这里只描述拟议接口，故状态为 `documented`，验证引用为空。实际 wrapper、依赖说明和验证文件存在后，再把对应目录放入 `paper.source_paths`；示例不冒充这些文件已经存在。

```json
{
  "name": "affine_values",
  "status": "documented",
  "verification_evidence": [],
  "implementation": {
    "kind": "upstream_wrapper",
    "source": {
      "repository": "示例：实际作者仓库 URL",
      "revision": "示例：实际完整 commit 或源码指纹",
      "symbol": "src/transforms.py:affine_values",
      "license": "示例：核实后的许可"
    },
    "wrapper_path": "tools/affine/cli.py",
    "adaptations": ["JSON 文件输入输出；保留上游 scale 和 offset 语义"]
  },
  "invocation": {
    "transport": "cli",
    "cwd": "tools/affine",
    "argv_template": [".venv/bin/python", "cli.py", "--input", "{input_json}", "--scale", "{scale}", "--offset", "{offset}", "--output", "{output_json}"],
    "input": {"values": "非空有限数值数组，顺序有意义，无量纲", "scale": "有限数，默认 1", "offset": "有限数，默认 0"},
    "output": {"values": "与输入等长且同序的数值数组"},
    "errors": "输入格式错误退出 2；上游计算失败退出非零且不返回伪成功结果",
    "artifacts": "调用者提供新的输出路径，已有文件则拒绝覆盖",
    "environment": {"requirements": "tools/affine/requirements.lock", "platform": "示例：实际测试平台", "hardware": "CPU", "required_env_names": []},
    "side_effects": ["写一个指定输出文件"],
    "randomness": "拟议调用不含随机步骤；需核查上游实现"
  }
}
```

相对于 `project_dir` 定位工具和证据；进入任务快照后按 `source_path_map` 解析原路径。`cwd` 下的解释器路径必须由真实安装说明恢复，不把开发机虚拟环境复制路径当成可移植承诺。若采用 Python API，记录模块、公开符号、调用参数和异常契约；MCP 则记录 server 启动/连接方式、工具名与客户端实参，验证时经过该协议。

## 实际调用记录需要填什么

下面展示**尚未执行**的记录形状；实际运行后才能填写观察字段，并将真实报告加入 `verification_evidence`。`execution_status` 等是证据对象的自描述字段，不是调度器的新状态枚举。

```json
{
  "example_only": true,
  "execution_status": "not_run",
  "executor_relation": "示例：implementer_self_test 或 independent_recheck",
  "versions": {
    "upstream_revision": null,
    "implementation_files_sha256": {},
    "test_files_sha256": {},
    "input_files_sha256": {},
    "reference_files_sha256": {},
    "environment_manifest_sha256": null
  },
  "call": {
    "cwd": "tools/affine",
    "argv": [".venv/bin/python", "cli.py", "--input", "tests/input.json", "--scale", "2", "--offset", "1", "--output", "runs/case-001/output.json"],
    "input_contents": {"values": [1, 2]},
    "started_at": null,
    "finished_at": null,
    "actual_exit_code": null,
    "stdout_log": null,
    "stderr_log": null
  },
  "comparison": {
    "reference_basis": "示例解析预期 y=2x+1；忠实封装还需要单独的直接上游调用对照",
    "expected": {"values": [3, 5]},
    "rule": "本例小整数精确一致；真实浮点任务另行预定容差和非有限值策略",
    "observed": null,
    "result": "unknown"
  }
}
```

实际执行记录还应关联独立获取参考结果的调用与日志。测试源码、封装源码或输入变更后，保留旧记录并重跑受影响用例。对本例，改变 `scale` 应改变输出；输入含非有限值应明确失败；重复调用不应覆盖上次产物。对真实方法，选择能揭露忽略参数、标识符错位、默认值改变和机制失效的用例，不能把本例预期套在科研任务上。

实际调用成功后，`tested` 仅覆盖已完成的检查；复现论文结论还需要对应数据、协议、预算和不确定性证据。由同一个构建者运行上述检查仍属自测；`expert_review` 只有真实重新调用并保存独立记录，才支持相应范围的独立复验声明。

参考官方 Paper2Agent 的[工具实现与字段示例](https://github.com/jmiao24/Paper2Agent/blob/8c2d059165ef8cdcb70dbea76655b9c2b55b38e6/skills/paper2agent/paper2mcp/references/agents/tutorial-tool-extractor-implementor.md)及[运行验收用例](https://github.com/jmiao24/Paper2Agent/blob/8c2d059165ef8cdcb70dbea76655b9c2b55b38e6/skills/paper2agent/paper2mcp/references/runtime-verification.md)。这里借鉴信息结构，不要求本项目使用 FastMCP。
