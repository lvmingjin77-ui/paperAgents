# 上游归属

PaperAgents 最初从 [SakanaAI/AI-Scientist-v3](https://github.com/SakanaAI/AI-Scientist-v3) 派生，初始版本为 `df8313889a004f8a44a472e19a833cd547bb828a`。保留 Apache-2.0 许可证和作者归属，见根目录 `LICENSE`、`NOTICE` 与 `CITATION.cff`。

0.2 在独立副本 `paperAgents02/` 重构，不修改相邻原项目与上游仓库。新版使用自己的知识准备、协调器、运行器和写作链，不再依赖 v3 的 Hydra、Docker、任务导出或 `agsci` 入口，也不兼容旧运行格式。

ScientistTwo 提供整体迭代设计参考，见 [调研笔记](scientisttwo-notes.md) 与 [改造方案](redesign.md)。参考方法的论文质量不构成本项目效果证明。
