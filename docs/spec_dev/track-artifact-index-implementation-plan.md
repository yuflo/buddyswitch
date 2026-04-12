# BuddySwitch Track Artifact Index Implementation Plan

## 版本信息

- Document: Track Artifact Index Implementation Plan
- Date: 2026-04-13
- Status: Draft
- Source: `docs/whiteboard/track-artifact-index-and-summary-selection.md`
- Scope: `scripts/switch_runtime.py`, `scripts/env_store.py`, `framework/contracts/**`, `buddyswitch/skills/**/SKILL.md`, `tests/**`

## 1. 目标

本计划定义 `track_artifact_index` 与强化后的 `artifact.summary` 的落地方案。

最终目标只有四个：

1. `resolve` 能返回完整、可选的 track artifact 索引，而不是只给每个 task 的 `latest_artifact`。
2. 当前执行的 buddy 可以按固定流程选择本次需要的 `artifact_ids`。
3. `artifact.summary` 在不新增字段的前提下，足够承担后续 artifact selection 的索引文本职责。
4. 整个实现以“前进式开发”为原则，不引入双轨逻辑、历史兼容壳、冗余持久化对象。

## 2. 前进式开发原则

本项目这一轮实现必须遵守下面的规则。

## 2.1 单一真相

- canonical objects 仍然只有 `track / task / artifact / run`
- 不新增持久化的 `track_artifact_index` object
- 不新增 `artifact.desc`、`artifact.selection_summary` 等平行字段

## 2.2 不做兼容壳

- 不为了“也许以后要兼容”而增加双轨输出
- 不引入旧流程和新流程同时长期并存的状态
- 不把 `track_context.latest_artifact` 和 `track_artifact_index` 同时作为 artifact selection authority

结论：

```text
artifact selection 的权威输入只能是 track_artifact_index
track_context 只保留为轻量背景上下文，不再扩展成选择层
```

## 2.3 不做历史回填工程

- 不回填历史 artifact 的 summary
- 不写 migration 脚本去批量重算历史 index
- 历史数据质量不足时，按现有字段退化处理，而不是补一个迁移层

## 2.4 先做可验证的固定流程

- 第一版不引入独立 skill
- 第一版不依赖模型自由判断做核心控制逻辑
- 先实现 deterministic 的选择流程，再决定是否需要更高级选择器

## 3. 目标状态

## 3.1 `resolve` 输出结构

目标状态下，`resolve` 至少包含：

- `task_context`
- `track_context`
- `track_artifact_index`
- `eligible_skills`
- `required_output_schema_by_skill`

其中：

- `track_context` 继续保留轻量摘要作用
- `track_artifact_index` 成为 artifact 选择的唯一权威输入

## 3.2 `track_artifact_index` 结构

第一版采用白板文档里已经确认的结构：

```json
{
  "track_id": "track-xxx",
  "track_title": "Track title",
  "track_summary": "Track summary",
  "updated_at": "2026-04-13T10:00:00+08:00",
  "tasks": [
    {
      "task_id": "task-pm-xxx",
      "buddy": "pm",
      "task_title": "Task title",
      "task_summary": "Task summary",
      "latest_artifact_id": "art-task-pm-xxx-prd-3",
      "artifacts": [
        {
          "artifact_id": "art-task-pm-xxx-prd-3",
          "title": "PM write-prd - ...",
          "summary": "Requirement summary for ...",
          "skill_id": "write-prd",
          "updated_at": "2026-04-13T09:00:00+08:00",
          "is_latest": true
        }
      ]
    }
  ]
}
```

## 3.3 `artifact.summary` 目标语义

`artifact.summary` 不再被视为“随便一行 run 结果摘要”。

目标语义是：

```text
artifact.summary = 可供后续 buddy 做 artifact selection 的短摘要
```

必须同时表达：

1. 这份 artifact 的角色
2. 它解决了什么关键问题或收敛了什么决策
3. 它对哪个下游 buddy 或下游工作有用

## 3.4 固定流程

目标固定流程：

1. `resolve switch`
2. 读取 `track_artifact_index`
3. 按固定规则选择 `artifact_ids`
4. 按 `artifact_id` 读取 artifact 正文
5. 执行当前 buddy skill

## 4. 非目标

本轮实现不做这些事情：

1. 不新增持久化的 track index 文件
2. 不新增 selection buddy
3. 不新增 selection skill
4. 不把 artifact selection 建成复杂工作流引擎
5. 不给 artifact 新增并行摘要字段
6. 不做历史 artifact summary backfill
7. 不改动 track/task/artifact 基础 schema 的核心所有权关系

## 5. 架构决策

## 5.1 `track_artifact_index` 动态生成

第一版 `track_artifact_index` 每次在 `resolve` 期间现算，不写回 object store。

原因：

1. 当前规模下本地 JSON 遍历足够快
2. 避免重复状态
3. 避免同步点爆炸
4. 保持对象模型干净

## 5.2 `track_context` 不退休，但降级

`track_context` 继续保留，因为它已经是现有 resolve payload 的一部分，且对快速背景理解仍然有价值。

但从本轮实现开始，明确规定：

- `track_context` 不再承担 artifact selection authority
- 任何新选择逻辑都只读 `track_artifact_index`
- 后续不要继续往 `track_context` 上堆 artifact 目录能力

## 5.3 选择逻辑 deterministic 化

第一版选择逻辑采用明确规则，不做 prompt-first 设计。

理由：

1. 这是控制层，不是内容生成层
2. deterministic 规则更容易测试
3. deterministic 规则更容易清理，不会形成黑箱 debt

后续如果需要更复杂选择器，也只能建立在 deterministic baseline 已稳定之后。

## 5.4 历史弱 summary 的处理方式

历史 artifact 的 summary 可能不够理想。

这一轮不做回填，只采用如下退化策略：

1. 优先 `summary`
2. summary 过弱时退回 `title`
3. 再配合 `is_latest`、`buddy`、`skill_id`

这是一种前进式退化，不是兼容系统。

## 6. 实施阶段

## Phase 0: 规范冻结

### 目标

先冻结边界，避免边做边改。

### 工作项

1. 把白板结论收敛成 spec_dev 实施计划
2. 明确以下规则进入规范：
   - 不新增字段
   - 不持久化 index
   - 不做 selection skill
   - 不做历史回填
   - `track_artifact_index` 是 artifact selection authority

### 输出

- 本文档

### 验收标准

- 后续实现不需要再争论对象边界
- 任一开发者能明确知道哪些方案被拒绝

## Phase 1: Runtime Index 基础能力

### 目标

让 `resolve` 能稳定返回 `track_artifact_index`。

### 修改范围

- `scripts/env_store.py`
- `scripts/switch_runtime.py`
- `tests/test_switch_runtime.py`

### 设计要求

1. index 组装逻辑必须抽成清晰函数，不允许塞进 `resolve_switch` 主流程里变成长函数
2. helper 必须围绕现有 canonical objects 构建，不创建新状态
3. 排序规则必须固定且可测试

### 建议实现

在 [env_store.py](/Users/chen/Dev/buddyswitch/scripts/env_store.py) 增加只读 helper：

- `list_task_artifacts(task_id: str) -> list[dict[str, Any]]`
- `build_track_artifact_index(track_id: str) -> dict[str, Any] | None`

建议语义：

- `list_task_artifacts`：
  - 读取 task
  - 根据 `task.artifact_ids` 拉取 artifacts
  - 按 `updated_at desc` 排序
- `build_track_artifact_index`：
  - 读取 track
  - 遍历 `track.task_ids`
  - 对每个 task 调 `list_task_artifacts`
  - 标记 `is_latest`
  - 组装标准 index 结构

在 [switch_runtime.py](/Users/chen/Dev/buddyswitch/scripts/switch_runtime.py) 中：

1. 保留现有 `_build_track_context`
2. 新增 `track_artifact_index` 组装调用
3. 在 `resolve_switch` 返回 payload 里加入 `track_artifact_index`

### 不允许的实现

- 不允许在 `resolve_switch` 里现场拼大段 list/dict 逻辑
- 不允许把 `track_artifact_index` 直接写进 track object
- 不允许新增 `artifact.track_id`

### 验收标准

1. `resolve(track_id)` 返回完整 `track_artifact_index`
2. index 中包含 track 下所有 task 的所有 artifacts
3. `is_latest` 与 `task.latest_artifact_id` 一致
4. track 不存在时返回 `null` 或等价空值，不抛出多余异常

### 测试

在 [test_switch_runtime.py](/Users/chen/Dev/buddyswitch/tests/test_switch_runtime.py) 新增：

1. `resolve` 返回 `track_artifact_index`
2. index 包含历史 artifacts，不只 latest
3. `is_latest` 标记正确
4. task 没有 artifact 时 `artifacts` 为空数组
5. 缺失 task / artifact 时处理行为清晰稳定

## Phase 2: Artifact Read Helper

### 目标

把“按 `artifact_id` 读取正文”变成明确能力，而不是 host 临时拼文件路径。

### 修改范围

- `scripts/env_store.py`
- 如有必要新增轻量 CLI helper
- `tests/test_debug_apis.py` 或新增对应测试

### 设计要求

1. helper 职责必须单一
2. 不引入选择逻辑
3. 不引入上下文推理

### 建议实现

优先复用现有 `get_artifact(artifact_id)`。

如果当前对 host 的调用方式不够清晰，则新增一个非常薄的 CLI/read helper，例如：

```text
python3 scripts/env_artifacts.py get <artifact-id>
```

前提是它只是把现有 `get_artifact` 暴露出来，不增加新语义。

### 不允许的实现

- 不允许在 read helper 里顺手做 selection
- 不允许在 read helper 里混入 track 推理

### 验收标准

1. 给定 `artifact_id` 能稳定拿到完整 artifact object
2. 错误处理与现有 debug API 风格一致

## Phase 3: Summary Contract 强化

### 目标

让未来写入的 `artifact.summary` 可以稳定作为 selection 输入。

### 修改范围

- `framework/contracts/design.md`
- `framework/contracts/pm.md`
- `framework/contracts/market.md`
- `framework/contracts/dev.md`
- `framework/contracts/test.md`
- 对应 `buddyswitch/skills/**/SKILL.md`
- `tests/test_repo_consistency.py`

### 设计要求

必须明确写进 contract：

1. `execution_summary` 会落为 `artifact.summary`
2. 它不仅是 run 摘要，也是后续 artifact selection 的索引文本
3. 它必须覆盖：
   - artifact 角色
   - 关键收敛/决策
   - downstream relevance

### 推荐统一模板

```text
[artifact role] + [resolved outcome / decision] + [downstream relevance]
```

### 示例要求

每个 buddy contract 至少增加：

1. 一条正例
2. 一条反例

正例表达“适合 selection 的 summary”，反例表达“流水账式 summary 不合格”。

### 关于 schema

第一版不改 JSON schema 结构。

原因：

1. schema 只能约束 shape，不能可靠约束摘要质量
2. 质量约束更适合放在 contract 和测试样例里

如果后续需要最弱约束，可以只考虑 `minLength`，但这不是第一版必须项。

### 验收标准

1. 所有 buddy contract 都明确声明 `execution_summary -> artifact.summary`
2. 所有 buddy contract 都明确声明 summary 的 selection 语义
3. skill docs 与 contracts 不冲突

### 测试

在 [test_repo_consistency.py](/Users/chen/Dev/buddyswitch/tests/test_repo_consistency.py) 新增或扩展检查：

1. 每个 buddy contract 都包含 summary 语义说明
2. 每个相关 skill doc 都没有与 contract 冲突的表述

## Phase 4: Deterministic Artifact Selection

### 目标

把 artifact 选择从“人工临时判断”收敛成明确、可测试的固定流程。

### 修改范围

- 新增 `scripts/artifact_selection.py` 或等价模块
- 如需要，新增一个极薄 CLI 入口
- `tests/test_switch_runtime.py`
- 新增 `tests/test_artifact_selection.py`

### 设计要求

1. 选择逻辑必须 deterministic
2. 选择逻辑必须只依赖：
   - `current_buddy`
   - `demand`
   - `track_artifact_index`
3. 不允许读取仓库其它隐式状态
4. 不允许调用模型来决定控制层输出

### 第一版规则表

建议第一版采用规则表，而不是自由文本推理。

建议默认 upstream mapping：

- `design`:
  - 优先 `market.latest`
  - 再取 `pm.latest`
  - continuation 时可补 `design.latest`
- `dev`:
  - 优先 `pm.latest`
  - 再取 `design.latest`
  - continuation 时可补 `dev.latest`
- `test`:
  - 优先 `dev.latest`
  - 再取 `pm.latest`
  - 必要时补 `design.latest`
- `pm`:
  - 根据 demand 决定是否取 `market.latest`
  - continuation 时可补 `pm.latest`

然后再加一层显式 demand 覆盖：

1. demand 里点名 buddy，则优先该 buddy
2. demand 出现“历史/之前/上一版/compare/演进”等词，才允许引入旧 artifact
3. 默认不要选历史 artifact

### 推荐输出

选择器返回：

```json
{
  "selected_artifact_ids": ["..."],
  "reasons": ["..."],
  "selection_mode": "deterministic-v1"
}
```

### 不允许的实现

- 不允许 prompt-first 选择器成为控制层主路径
- 不允许在规则不清楚时偷偷 fallback 到“全部读取”
- 不允许让 `track_context` 和 `track_artifact_index` 双轨决定结果

### 验收标准

1. 同一输入必然得到同一选择结果
2. design/dev/test 三条主链路有明确 upstream 规则
3. 默认选择结果数量受控，不产生上下文爆炸

### 测试

新增 [test_artifact_selection.py](/Users/chen/Dev/buddyswitch/tests/test_artifact_selection.py)：

1. design 默认取 `market.latest + pm.latest`
2. design continuation 会补 `design.latest`
3. dev 默认取 `pm.latest + design.latest`
4. test 默认取 `dev.latest` 为主
5. demand 点名 buddy 时优先命中
6. demand 未要求历史时，不返回旧 artifact
7. demand 要求回看历史时，允许返回旧 artifact

## Phase 5: Host Flow 文档与旧路径退休

### 目标

把新流程写死，并明确旧思路退休。

### 修改范围

- `framework/docs/switch-spec.md`
- 必要时补充 `docs/buddyswitch` 或其它操作文档

### 必须新增的规范

在 host flow 中写清：

```text
resolve
-> read track_artifact_index
-> run deterministic artifact selection
-> read selected artifacts by id
-> execute skill
-> persist
```

### 必须退休的旧思路

明确写明：

1. 不能再把 `track_context.tasks[*].latest_artifact` 当作唯一 artifact 输入源
2. 不能再默认认为“latest artifact = 唯一需要读取的 artifact”
3. 不能再扩展 `track_context` 去承载完整目录能力

### 验收标准

1. 文档中只有一条主流程
2. 不存在旧新两条同级推荐流程

## 7. 文件变更清单

本轮实施计划覆盖的主要文件：

- [switch_runtime.py](/Users/chen/Dev/buddyswitch/scripts/switch_runtime.py)
- [env_store.py](/Users/chen/Dev/buddyswitch/scripts/env_store.py)
- [design.md](/Users/chen/Dev/buddyswitch/framework/contracts/design.md)
- [pm.md](/Users/chen/Dev/buddyswitch/framework/contracts/pm.md)
- [market.md](/Users/chen/Dev/buddyswitch/framework/contracts/market.md)
- [dev.md](/Users/chen/Dev/buddyswitch/framework/contracts/dev.md)
- [test.md](/Users/chen/Dev/buddyswitch/framework/contracts/test.md)
- `buddyswitch/skills/**/SKILL.md`
- [switch-spec.md](/Users/chen/Dev/buddyswitch/framework/docs/switch-spec.md)
- [test_switch_runtime.py](/Users/chen/Dev/buddyswitch/tests/test_switch_runtime.py)
- [test_repo_consistency.py](/Users/chen/Dev/buddyswitch/tests/test_repo_consistency.py)
- `tests/test_artifact_selection.py`

## 8. 测试矩阵

## 8.1 Runtime

必须覆盖：

1. `resolve` 返回 `track_artifact_index`
2. index 包含历史 artifacts
3. `is_latest` 正确
4. 空 task / 空 artifact 行为正确

## 8.2 Selection

必须覆盖：

1. 各 buddy 默认 upstream 选择规则
2. demand 显式点名覆盖
3. continuation 规则
4. 历史 artifact 选择开关

## 8.3 Contract Consistency

必须覆盖：

1. 所有 contract 都声明 summary 新语义
2. 所有 skill docs 都与 contract 对齐

## 8.4 Regression

必须确认：

1. `persist` 语义不变
2. `artifact.summary = execution_summary` 语义不变
3. track/task/artifact 对象结构核心字段不变

## 9. 风险与应对

## 风险 1

历史 artifact summary 太弱，导致选择器前期不够准。

应对：

- 第一版用 deterministic upstream 规则兜底
- summary 只作为加权信号，不是唯一信号

## 风险 2

`track_context` 与 `track_artifact_index` 被并行使用，导致后续逻辑分叉。

应对：

- 在 spec 中明确 authority
- 在实现中只给 `track_artifact_index` 接 selection

## 风险 3

开发时为了快，把 index 组装逻辑散落到多个模块。

应对：

- index builder 只允许一处实现
- helper 放在 `env_store.py` 或一个明确的只读模块中

## 10. 完成定义

满足下面条件，视为这一轮实现完成：

1. `resolve` 返回 `track_artifact_index`
2. 存在 deterministic 的 artifact selection 能力
3. host flow 文档切换到新流程
4. contracts 已强化 summary 语义
5. 不存在新增字段
6. 不存在持久化 index 文件
7. 不存在 selection 双轨 authority

## 11. 推荐执行顺序

推荐严格按下面顺序推进：

1. `Phase 1` Runtime Index
2. `Phase 2` Artifact Read Helper
3. `Phase 3` Summary Contract 强化
4. `Phase 4` Deterministic Selection
5. `Phase 5` Host Flow 文档与旧路径退休

这个顺序的理由：

1. 先把数据供给做好
2. 再把读取接口收敛清楚
3. 再强化未来 summary 质量
4. 再把选择逻辑固化
5. 最后统一文档和流程，避免中途双轨

## 12. 本计划明确拒绝的方案

1. 持久化 `track_artifact_index` 文件
2. 新增 `artifact.desc`
3. 新增 selection skill
4. 模型自由决策作为控制层主路径
5. 历史 summary 回填工程
6. 长期保留 `track_context` 与 `track_artifact_index` 双权威
