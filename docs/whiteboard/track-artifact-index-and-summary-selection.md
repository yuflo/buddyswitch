# BuddySwitch Track Artifact Index And Summary Selection

## 版本信息

- Document: Track Artifact Index And Summary Selection
- Date: 2026-04-13
- Status: Draft
- Scope: `scripts/switch_runtime.py`, `scripts/env_store.py`, `framework/contracts/**`, `framework/schemas/**`

## 1. 文档目的

本文档整理本轮讨论的结论，聚焦回答下面几个问题：

1. 当前 `switch <buddy> -> <track-id>: <demand>` 在没有完善“目录索引”时，如何让当前执行的 buddy 了解 track 信息并继续工作。
2. 当前机制的真实边界是什么，尤其是为什么默认只能看到每个 task 的 `latest_artifact`。
3. 是否需要 `track_artifact_index`，以及它应当是什么数据结构。
4. `track_artifact_index` 应该动态生成还是持久化成 canonical 文件。
5. 现有 artifact `summary` 是否足够支持后续 artifact 选择；如果不够，应如何强化而不新增字段。
6. 选择 artifact ids 的过程应该是独立 skill，还是固定流程。

本文档只处理 buddy 获取上下文的效率和效果，不讨论“人是否看得懂”的展示问题。

## 2. 当前机制

## 2.1 基本运行流程

当前 BuddySwitch 的运行模型是：

```text
parse -> resolve -> host run -> persist
```

- `parse` 解析 `switch` 指令。
- `resolve` 校验 buddy、task、track，并构造当前 run 的上下文。
- host session 在当前上下文里执行被路由到的 skill。
- `persist` 把 task / artifact / run / track 的变更写回 canonical objects。

## 2.2 以 design 跟进为例

例子：

```text
switch design -> track-id: 根据 market buddy 的报告 和 pm buddy 需求描述，跟进一下这块的设计稿
```

这条指令在当前机制下的处理方式如下：

1. runtime 根据 `manifest` 里的 `buddy -> skills` 路由到 `design` buddy 的 `ia-spec` skill。
2. 如果指令里没有显式 `task-id`，`resolve` 会为这次 run 派生一个新的 design task id，但在 `persist` 之前不会落盘。
3. `resolve` 读取指定 `track-id` 对应的 track object。
4. `resolve` 根据 `track.task_ids` 逐个读取 task object。
5. 对 track 下每个 task，只取该 task 的 `latest_artifact_id` 指向的 artifact，并把它挂到 `track_context.tasks[*].latest_artifact`。
6. host session 在这个 `track_context` 基础上执行 `ia-spec`。

所以，当前 buddy 不是通过某个独立“目录文件”理解 track，而是通过下面这条对象链路理解：

```text
track
  -> task_ids
    -> task
      -> latest_artifact_id
        -> artifact
```

## 2.3 当前 `track_context` 的实际内容

当前 `resolve` 给下游 buddy 的 `track_context` 是轻量的，核心结构等价于：

```json
{
  "track": {
    "id": "track-xxx",
    "title": "Track title",
    "status": "active",
    "current_buddy": "pm",
    "next_buddy": "design",
    "summary": "Track summary"
  },
  "tasks": [
    {
      "task_id": "task-market-xxx",
      "buddy": "market",
      "status": "active",
      "summary": "Task summary",
      "latest_artifact": {
        "id": "art-task-market-xxx-research",
        "title": "MARKET research-scan - ...",
        "summary": "Completed a quick market scan...",
        "content": { "...": "..." }
      }
    },
    {
      "task_id": "task-pm-xxx",
      "buddy": "pm",
      "status": "active",
      "summary": "Task summary",
      "latest_artifact": {
        "id": "art-task-pm-xxx-prd-3",
        "title": "PM write-prd - ...",
        "summary": "Resolved the remaining PM decisions...",
        "content": { "...": "..." }
      }
    }
  ]
}
```

## 2.4 当前 buddy 默认能看到什么

默认上下文里，当前执行的 buddy 可以直接拿到：

- 当前 track 的基础信息：`id / title / status / current_buddy / next_buddy / summary`
- track 下每个 task 的基础信息：`task_id / buddy / status / summary`
- track 下每个 task 的一份 `latest_artifact`

## 2.5 当前 buddy 默认看不到什么

默认上下文里，当前执行的 buddy 看不到：

- 其它 task 的历史 artifacts 全量列表
- 哪些历史 artifact 已经被 supersede
- 这次执行推荐优先读取哪些 artifact ids
- 哪些 artifact 是“权威输入”，哪些只是过程性产物

换句话说，在当前机制下：

- “仓库里有这些 artifacts” 和
- “当前 run 的默认上下文会把这些 artifacts 喂给 buddy”

是两回事。

当前机制默认只喂每个 task 的 `latest_artifact`。

## 3. 当前机制的边界

## 3.1 为什么默认只取 `latest_artifact`

当前设计背后的隐含假设是：

1. 每个 task 都应该有一个“当前最应被下游信任的产物”。
2. 对后续 buddy 来说，最小必要上下文优先于完整历史。
3. `latest_artifact_id` 是当前 task 的 handoff 指针。

因此，track 层默认只收敛到“每个 task 的当前代表产物”。

## 3.2 当前边界带来的问题

这个假设在简单 track 上能工作，但它有明显边界：

1. 如果一个 task 有多版 artifact，当前 buddy 默认不知道历史版本有哪些。
2. 如果最新 artifact 不是最适合本次消费的那个，当前 buddy 默认不会知道还有其它候选。
3. 如果上游 task 的最新 artifact 是过程性说明，而不是最好的输入摘要，默认上下文质量会下降。
4. 如果 demand 明确提到“根据 market 报告和 pm 需求描述”，当前机制虽然能把 market 和 pm 的 latest artifact 给到 design buddy，但不会告诉它还有没有值得回看的旧 artifact。

所以当前缺的不是“有没有信息”，而是“缺一层完整但轻量的可选材料索引”。

## 4. 问题定义

本轮讨论确认的问题不是：

- 再增加一个新的 buddy
- 再增加一个新的执行 skill
- 先做复杂的人工维护文档

真正的问题是：

```text
当前执行的 buddy 缺少一个 track 级的 artifact 可选索引，
因此默认只能消费每个 task 的 latest artifact，
无法稳定地为本次 run 选择最合适的上下文集合。
```

## 5. 方案结论

## 5.1 需要 `track_artifact_index`

需要。

`track_artifact_index` 的作用不是替代 canonical objects，而是为当前 run 提供一份完整但轻量的可选 artifact 索引，让当前 buddy 能基于它选择本次真正需要读取的 artifacts。

## 5.2 不需要新增字段来承载 artifact 摘要

不需要新增 `desc` 或其它新字段。

现有 artifact 已经有：

- `title`
- `summary`

其中：

- `title` 用于标签和快速识别
- `summary` 用于后续 artifact selection

因此本方案明确要求：

```text
不增加额外字段；
直接强化原有 artifact.summary 的生成要求。
```

## 5.3 不需要把 artifact 选择单独抽成 skill

不需要。

原因：

1. 这是当前 buddy 的取材准备步骤，不是新的业务产出。
2. 如果把它做成独立 skill，会引入额外路由和执行层级。
3. 这一过程更适合做成 `resolve` 之后的固定流程。

结论：

```text
artifact 选择 = 固定流程
不是独立 skill
```

## 6. `track_artifact_index` 数据结构

## 6.1 第一版目标

第一版只解决“完整列出候选 artifacts 并支持 selection”。

第一版不处理这些更高级的信息：

- `authoritative_artifact_ids`
- `recommended_read_order`
- `superseded_artifact_ids`
- `handoff_contract`

这些可以留到后续阶段。

## 6.2 推荐结构

```json
{
  "track_id": "track-schedule-tool-landing-page",
  "track_title": "日程管理工具 Landing Page 快速开发",
  "track_summary": "聚焦首版 landing page 的产品定义与快速开发交付。",
  "updated_at": "2026-04-12T20:44:03+08:00",
  "tasks": [
    {
      "task_id": "task-market-artifact-88eb93",
      "buddy": "market",
      "task_title": "研究竞品和定价信号",
      "task_summary": "Completed a quick market scan for schedule-management tools...",
      "latest_artifact_id": "art-task-market-artifact-88eb93-research",
      "artifacts": [
        {
          "artifact_id": "art-task-market-artifact-88eb93-research",
          "title": "MARKET research-scan - ...",
          "summary": "Completed a quick market scan for schedule-management tools, focusing on category shape, target users, and current pricing patterns across official pricing pages plus lightweight social validation.",
          "skill_id": "research-scan",
          "updated_at": "2026-04-12T19:56:20+08:00",
          "is_latest": true
        }
      ]
    },
    {
      "task_id": "task-pm-landing-page-track-5cc187",
      "buddy": "pm",
      "task_title": "写 landing page PRD",
      "task_summary": "Resolved the remaining PM decisions for the landing page...",
      "latest_artifact_id": "art-task-pm-landing-page-track-5cc187-prd-3",
      "artifacts": [
        {
          "artifact_id": "art-task-pm-landing-page-track-5cc187-prd-3",
          "title": "PM write-prd - ...",
          "summary": "Resolved the remaining PM decisions for the landing page: set a consumer freemium pricing anchor, removed open questions, and confirmed that dev can implement directly without a separate design artifact.",
          "skill_id": "write-prd",
          "updated_at": "2026-04-12T20:06:36+08:00",
          "is_latest": true
        },
        {
          "artifact_id": "art-task-pm-landing-page-track-5cc187-prd-2",
          "title": "PM write-prd - ...",
          "summary": "Updated the landing page PRD to reflect a 2C schedule-management product with free and paid tiers, a consumer-oriented value proposition, and clearer pricing-positioning guidance.",
          "skill_id": "write-prd",
          "updated_at": "2026-04-12T19:56:20+08:00",
          "is_latest": false
        }
      ]
    }
  ]
}
```

## 6.3 字段说明

第一版建议保留这些字段：

- track level
  - `track_id`
  - `track_title`
  - `track_summary`
  - `updated_at`
- task level
  - `task_id`
  - `buddy`
  - `task_title`
  - `task_summary`
  - `latest_artifact_id`
  - `artifacts`
- artifact level
  - `artifact_id`
  - `title`
  - `summary`
  - `skill_id`
  - `updated_at`
  - `is_latest`

这些字段已经足够支持第一版 artifact selection。

## 7. `track_artifact_index` 的创建与更新

## 7.1 第一版结论：动态生成，不单独持久化

第一版建议：

```text
不把 track_artifact_index 单独持久化成 canonical 文件；
每次 resolve(track_id) 时动态计算。
```

## 7.2 为什么第一版动态生成就够了

原因：

1. 当前所有数据都在本地 JSON objects 中，读取成本很低。
2. `track -> task_ids -> task.artifact_ids -> artifact` 的遍历是完全程序化的，当前规模下足够快。
3. 第一版 `track_artifact_index` 中的大部分信息都可以可靠推导，没有必要做重复存储。
4. 动态生成能避免 index 与 task/artifact 主对象脱同步。

## 7.3 动态生成算法

每次 `resolve` 时：

1. 读取目标 track。
2. 根据 `track.task_ids` 读取所有 task。
3. 对每个 task，根据 `task.artifact_ids` 读取全部 artifact。
4. 按 `updated_at` 排序该 task 的 artifacts。
5. 用 `task.latest_artifact_id` 标记 `is_latest`。
6. 组装成 `track_artifact_index` 返回给 host session。

## 7.4 为什么第一版不建议单独持久化成 canonical 文件

“单独持久化成 canonical 文件”的意思是：

- 把 `track_artifact_index` 写回正式 object
- 后续 runtime 可以直接信任它
- 它本身成为一份需要维护的正式状态

第一版不建议这样做，因为：

1. 会制造重复数据。
2. 会引入新的同步点。
3. 需要在多个写入点更新 index：
   - `create_artifact`
   - `update_artifact`
   - `remove_artifact_from_task`
   - `register_task_to_track`
   - task `track_id` 变化
4. 一旦不同步，当前 buddy 会被旧索引误导。

## 7.5 什么时候才值得持久化

只有当后续要存的是“不可可靠推导”的信息时，才值得持久化，例如：

- 当前 handoff 的权威输入 artifact ids
- 推荐阅读顺序
- supersede 关系
- 明确给下游 buddy 的 handoff contract

这类信息不是单靠 `task.artifact_ids` 和 `latest_artifact_id` 能稳定推出的，才有持久化价值。

## 8. Artifact 选择流程

## 8.1 固定流程

本轮讨论结论是：

```text
artifact 选择不拆 skill；
作为 resolve 之后的固定流程执行。
```

推荐固定流程：

1. `resolve switch`
2. 返回 `track_artifact_index`
3. 当前 buddy 根据 `track_artifact_index` 选择本次需要读取的 `artifact_ids`
4. 用 `artifact_id` 读取 artifact 正文
5. 执行当前 buddy 的正式 skill

## 8.2 选择维度

artifact selection 主要基于这些维度：

1. `demand` 中明确提到的 buddy 或材料类型
2. artifact 所属 buddy
3. 是否 `is_latest`
4. artifact 的 `skill_id`
5. `title`
6. `summary`
7. 当前 buddy 是否在继续自己已有的工作

## 8.3 第一版选择规则

第一版建议优先使用硬规则，而不是复杂选择器：

1. 如果 demand 明确点名 buddy，优先选这些 buddy 对应 task 的 artifacts。
2. 每个 task 默认优先 `is_latest = true` 的 artifact。
3. 如果当前 buddy 是 continuation，可补一个自己最近的 relevant artifact。
4. 只有当旧 artifact 的 `summary` 明显包含最新 artifact 没有的关键信息时，才补充旧 artifact。
5. 默认控制在最小必要集合，不要一次读取过多 artifacts。

## 8.4 选择器 prompt 草案

如果后续仍然希望做一个轻量选择器，可参考下面的 prompt：

```text
你是 BuddySwitch 的 artifact selector。

输入：
- current_buddy: design
- demand: 根据 market buddy 的报告 和 pm buddy 需求描述，跟进一下这块的设计稿
- track_summary: <string>
- track_artifact_index: <json>

任务：
从 track_artifact_index 中选出本次执行必须读取的 artifact_ids。
只返回最小必要集合，避免过多上下文。

选择规则：
1. 优先选择 demand 里明确点名的 buddy 对应 artifacts。
2. 对每个 task，默认优先 latest artifact。
3. 如果当前 buddy 是延续已有工作，可补充当前 buddy 自己最近一次 relevant artifact。
4. 优先“需求/决策/研究结论”类材料，弱化“确认性、过程性、测试性、实现性”材料，除非 demand 明确要求。
5. 如果同一 task 有多个 artifacts，只有当旧 artifact 仍提供最新 artifact 中没有的关键信息时，才补充旧 artifact。
6. 输出数量尽量控制在 2-4 个。

输出格式：
{
  "selected_artifact_ids": ["..."],
  "reasoning": [
    "why selected artifact A",
    "why selected artifact B"
  ],
  "omitted_artifact_ids": ["..."]
}
```

但第一版并不要求马上引入这个选择器；第一版硬规则已经足够。

## 8.5 读取 artifact 正文的 helper 能力

`track_artifact_index` 只负责列出候选，不负责承载完整正文。

因此固定流程里还需要一个按 `artifact_id` 取正文的 helper 能力，形式可以是：

```text
get_artifact(artifact_id) -> artifact object
```

或等价的 runtime/helper API。

它的职责很简单：

1. 输入 `artifact_id`
2. 返回完整 artifact object
3. 当前 buddy 再从 `artifact.content` 中消费正文

第一版不要求额外设计复杂接口；只要存在一个稳定的“按 id 取 artifact 正文”的程序化能力即可。

## 9. 对 `summary` 的判断与结论

## 9.1 当前 `artifact.summary` 的来源

当前 `artifact.summary` 不是单独生成的检索摘要。

当前 persist 逻辑是：

```text
artifact.summary = result.execution_summary
```

也就是说，artifact 的 `summary` 其实就是各 buddy run 的 `execution_summary` 原样写入。

## 9.2 当前 `summary` 是否足够

结论：

```text
当前 summary 足够做粗筛；
不够做稳定、可靠的 artifact selection 输入。
```

原因：

1. contract 只要求每次 run 产出 `execution_summary`。
2. schema 只要求 `execution_summary` 是一个 `string`。
3. 当前 contract 没有把 `summary` 定义成“给后续 artifact selection 用的摘要”。
4. 因此它能不能适合 selector，取决于当次写得好不好，而不是协议保证。

## 9.3 当前 `summary` 缺少的稳定信号

当前 summary 经常缺少这些对 artifact 选择很重要的信号：

1. 这份 artifact 的输入角色是什么：
   - research
   - requirement
   - design
   - implementation
   - validation
2. 这份 artifact 解决了什么核心问题或收敛了什么决策。
3. 哪个下游 buddy 最应该消费它。
4. 它是权威收敛版，还是一次过程性确认。

## 10. `summary` 强化方案

## 10.1 结论

本轮明确要求：

```text
不新增任何字段；
只强化原有 artifact.summary 的生成要求。
```

## 10.2 强化目标

强化后的 `summary` 既要能作为：

- run 结果摘要

也要能作为：

- `track_artifact_index` 中供后续 artifact selection 使用的主索引文本

## 10.3 推荐写法约束

后续各 buddy 的 `execution_summary` / artifact `summary` 应至少覆盖下面三件事：

1. 这份 artifact 的类型或角色
2. 这份 artifact 完成了什么关键收敛
3. 它对下游 buddy 的价值或适用方向

推荐压缩成 1-2 句，但必须具备选择意义，而不只是泛泛的“做了什么”。

## 10.4 推荐模板

推荐模板：

```text
[artifact role] + [resolved decision / produced outcome] + [downstream relevance]
```

例如：

```text
Market research summary for consumer schedule-management tools, identifying category positioning and pricing anchors that PM and design can use for landing-page scope and messaging.
```

```text
PM requirement summary for the landing page, finalizing 2C positioning, free-vs-Pro pricing anchors, and implementation-ready scope for design and dev handoff.
```

```text
Design IA summary for the landing page, defining the section structure, primary flows, and state handling that dev should implement directly.
```

## 10.5 不推荐的写法

不推荐：

```text
推进开发
```

```text
更新了 PRD
```

```text
确认了一下当前要求
```

这些句子虽然能表达“做了某件事”，但不足以支撑后续 selection。

## 11. 最终方案总结

本轮收敛后的方案如下：

1. 保留当前 canonical object model，不新增 buddy，不新增 artifact 字段。
2. 在 `resolve` 阶段新增动态生成的 `track_artifact_index`。
3. `track_artifact_index` 列出 track 下所有 task 的所有 artifacts，并保留 `title + summary + skill_id + updated_at + is_latest`。
4. artifact 选择不拆 skill，作为 `resolve` 之后的固定流程执行。
5. 第一版不把 `track_artifact_index` 单独持久化成 canonical 文件。
6. 继续使用现有 `artifact.summary`，但强化其生成要求，使其同时适合 run 总结和后续 artifact selection。

## 12. 建议的落地顺序

## Phase 1

1. 在 `resolve` 中新增 `track_artifact_index` 返回结构。
2. 保留当前 `track_context`，不要直接替换。
3. 实现基于 `track_artifact_index` 的固定 artifact selection 流程。

## Phase 2

1. 强化各 buddy contract 对 `execution_summary` 的写法要求。
2. 用新的 summary 写法逐步改善后续 artifacts 的可选性。

## Phase 3

根据实际使用情况再决定是否需要：

1. 更强的选择器
2. `authoritative_artifact_ids`
3. `recommended_read_order`
4. 可持久化的 handoff contract

但这些都不属于第一版必须项。

## 13. 本轮明确不做的事

1. 不新增 `desc` 字段。
2. 不新增“目录 buddy”。
3. 不把 artifact selection 先做成新 skill。
4. 不在第一版把 `track_artifact_index` 写成独立 canonical 文件。

## 14. 参考位置

- `scripts/switch_runtime.py`
- `scripts/env_store.py`
- `framework/docs/track-registry.md`
- `framework/docs/switch-spec.md`
- `framework/contracts/design.md`
- `framework/contracts/pm.md`
- `framework/contracts/market.md`
- `framework/contracts/dev.md`
- `framework/contracts/test.md`
