---
name: build-literature-corpus
description: 围绕研究方向确定检索范围（scope），并系统检索、筛选、下载近三年相关文献，产出可追溯的文献清单与覆盖记录（corpus）；不负责精读，精读由逐篇 reading 任务完成。
---

# 构建领域文献语料

依据[系统检索协议](../../references/literature-protocol.md)、[证据规则](../../references/evidence-policy.md)和[运行约定](../../references/runtime-contract.md)。

## 范围（`stage=scope`）

产出方向、会议、查询和纳入标准，供 corpus 执行：

- `venues` 每项是 `{venue_id, note}`：`venue_id` 用简短稳定的会议标识（如 `CVPR`），说明写在 `note`。时间范围固定为请求中的滚动窗口 `search_window`，不要另改为“最近几届”。
- 纳入规则与排除规则不能矛盾。直接解决本问题的工作是 `core`；其他领域可迁移的机制（如风险控制、选择性预测、拒答检测）是 `transferable`，同样重要，不因模态或任务不同而排除。
- 写明检索优先级与停止条件：先覆盖什么、什么缺口必须补齐、什么可以留到下一轮。
- 对数据集、基准的结构性描述标注“已核验（附来源）”或“待核验”；不要把设想写成数据集现成的字段。
- 若 `context.previous_outputs` 非空，在上一版基础上修订，保留已核验内容。

## 语料（`stage=corpus`）

职责是**找全、筛准、存好**，不精读。

1. 按 scope 的优先级执行查询、会议目录枚举与引文扩展；记录实际查询、日期、返回数量和局限。
2. 去重并逐条筛选：依据标题、摘要和必要的局部阅读决定纳入、排除或待定。为每篇写 `relevance`（`core` / `transferable`）和一句 `reason`。
3. 下载可取得的全文到项目目录，填 `full_text_path`；取不到用 `null` 并记入 `missing_sources`。
4. 时间与会议：`venue_id` 必须是 scope 中的标识，`year` 和 `pub_date` 对应**所收录的版本**（不要混用预印本与正式发表日期，日期不确定填 `null`）。窗口外或会议外的重要论文标 `background: true` 保留；需要精读的背景论文另加 `read: true` 并在 `reason` 说明原因。
5. 版本：同一工作的不同版本各自成条，填 `doi` 或带版本号的 `arxiv_id`，用 `same_as` 指向主条目；有实质差异的扩展版用 `related_to`。
6. 若 `context.previous_outputs` 非空，先读这些旧清单（包括被拒绝的提交）和 `existing_library` 中已下载的全文，按当前范围重新筛选并补缺，不要从头检索；旧条目也要重新判断，不能直接沿用。

`coverage.status=complete` 只表示按当前范围完成了检索与筛选，不代表已经读懂论文，也不代表全球无遗漏。
