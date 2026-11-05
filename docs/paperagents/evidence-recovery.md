# 从评审停点继续构思

在项目根目录执行 `python -m paperagents run projects/cir-reliability`。
不要加 `--new`，不需要先 revise。此命令不运行候选实验。

已有运行若停在 proposal_review，综合要求 gather_materials 且评审同意，
会按评审阻塞项生成 evidence.N 任务（没有评审阻塞项时使用综合的未解问题）。
旧 scope、文献、精读、专家、候选和评审产物均不改写。

补证据任务可检索、阅读、执行小规模数据检查，不能训练或评估候选方法。
结果分为 resolved、premise_fails、needs_experiment、needs_human、unresolved，
附来源、影响候选、变化维度和下一步。任务中断后沿用现有任务恢复语义：
已验收任务不重做，未完成任务重新尝试；不承诺恢复模型的中间会话。

报告不是裁决。前提变化或讨论台账仍有阻塞异议时返回 hypothesis，作者
接收旧候选、质疑、评审和补证据报告，再经讨论、查新及评审。否则返回
synthesis 并独立评审。单个候选需要人工不会直接停止全部候选；专家和
评审决定是否可搁置它。确需外部材料且无法绕开时选择 stop，列明所需事项。
探索性实验不能绕过标签、泄漏和统计前提问题，必须有明确的检查协议和结论边界。

[discussion] 的 max_evidence_rounds 默认 2，现有项目无需改配置即可使用。
自动候选修订另受 max_auto_revisions 限制；ready 被独立评审否决也会进入
该有界修订路径。轮数用尽后保留产物并暂停，不自动反复消耗 API。

网页任务列表、错误页、时间线和对话池包含 evidence。已有网页服务需重启
以加载后端改动；这与研究进程无关。

离线回归用例：tests/paperagents/test_evidence_recovery.py。
代码交付时未运行研究、实验或测试；仅做语法检查和当前存档只读兼容性检查。
