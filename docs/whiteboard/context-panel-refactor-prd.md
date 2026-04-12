# BuddySwitch Context Panel Refactor PRD

## 版本信息

- Document: Context Panel Refactor PRD
- Date: 2026-04-13
- Status: Draft
- Source structure: `docs/whiteboard/context-panel-iteration-structure.md`
- Target area: `framework/console/` and `/api/workspace`

## 1. 背景

BuddySwitch 的 Context Panel 当前已经能读取 workspace 中的 canonical objects：

- tracks: `buddyswitch/objects/tracks/*.json`
- tasks: `buddyswitch/objects/tasks/*.json`
- artifacts: `buddyswitch/objects/artifacts/*.json`
- run audits: `buddyswitch/content/runs/*.json`

但当前面板更像对象查看器：左侧看 tracks，中间看 selected track 的 artifact timeline，右侧看 run audits。它能展示数据，但没有把 BuddySwitch 用户在开发 project 时最需要的信息组织清楚。

用户真正需要的是：快速理解当前有哪些 project track、每个 track 下有哪些 task、每个 task 的核心物料是什么、当前推进到哪里、下一步该执行哪条 `switch`。

因此本次重构的目标是：在不优先改动大量后端 schema 的前提下，把现有数据重新组织成清晰、高效的 project 信息管理面板。

## 2. 问题定义

### 2.1 当前问题

1. Track 只是入口列表，没有足够说明每条 track 当前推进状态。
2. Task 没有成为主视图，用户不能直观看到 track 下的 task 结构。
3. Artifact 信息被混在 timeline 或 debug detail 中，核心物料不够突出。
4. Run audit 占据重要阅读空间，但它本质上是追溯证据，不是用户理解 project 的第一入口。
5. 下一步命令存在，但缺少和当前 task / material / gap 的明确关系。
6. 用户要回答“这个 project 做到哪里了、还缺什么、下一步做什么”时，需要跨多个区块推理。

### 2.2 当前阶段最重要的问题

本次重构首先解决信息组织问题，而不是设计复杂 UI 或引入新业务状态系统。

核心问题是：

```text
现有 track、task、artifact、run 关系没有被以用户理解 project 过程的方式展示出来。
```

## 3. 产品目标

### 3.1 核心目标

让用户打开 Context Panel 后，能在 30 秒内回答：

- 当前有哪些 track？
- 某个 track 下有哪些 task？
- 每个 task 是哪个 buddy 做的？
- 每个 task 当前状态是什么？
- 每个 task 最新核心物料是什么？
- 最新 artifact 里有哪些关键内容？
- 当前 track 还缺哪些明显物料？
- 下一条应该复制的 `switch` 是什么？

### 3.2 体验目标

- 面板默认展示项目推进信息，而不是对象文件信息。
- Track、task、artifact、run 的层级关系要一眼清楚。
- Task 必须成为 selected track detail 的主体。
- Artifact 必须以“核心物料”形式展示摘要和结构化重点。
- Run audit 降级为追溯区。
- Debug path / raw JSON 默认折叠。
- 不让用户为了理解当前状态去打开多个 JSON 文件。

### 3.3 工程目标

- 第一版主要基于现有 `/api/workspace` 数据。
- 允许在 `scripts/workspace_data.py` 或前端展示层做轻量派生。
- 不要求修改 BuddySwitch runtime persist 语义。
- 不要求新增复杂 object schema。
- 保持 Context Panel 只读，不执行 buddy、不调用 LLM、不写仓库文件。

## 4. 非目标

本次 PRD 不包含：

- 不实现新的 BuddySwitch runtime 状态机。
- 不改变 canonical `switch <buddy>...` 指令格式。
- 不改变 task、track、artifact、run 的持久化规则。
- 不在面板内触发 buddy、LLM、cleanup 或 shell command。
- 不把 Context Panel 做成项目管理 SaaS。
- 不优先做复杂 UI 动效、拖拽、图表、筛选器或多视图配置。
- 不要求所有 artifact schema 立即统一。

## 5. 用户与场景

### 5.1 目标用户

主要用户是正在通过 BuddySwitch 开发 project 的 Codex host session 用户。

用户通常通过这样的方式推进项目：

```text
switch market: ...
switch pm -> track-id: ...
switch design(task-id) -> track-id: ...
switch dev(task-id) -> track-id: ...
switch test -> track-id: ...
```

### 5.2 核心使用场景

#### 场景 A：查看当前有哪些项目线

用户打开面板后，想快速知道当前 workspace 里有哪些 track，每条 track 分别是什么状态。

#### 场景 B：查看某个 track 的任务构成

用户选中一个 track，想看到这个 track 下有几个 task，每个 task 是哪个 buddy 创建或推进的，分别产出了什么。

#### 场景 C：查看某个 task 的核心物料

用户想确认某个 task 的最新 artifact 内容，例如 PRD scope、design spec、dev changed files、verification result、known limitations。

#### 场景 D：判断下一步

用户想知道这个 track 下一步应该交给哪个 buddy，以及应该复制哪条 `switch` 命令。

#### 场景 E：追溯过程

用户想看某一步 run 的 demand、execution summary、linked artifact 和当时推荐的 next switch。

## 6. 信息架构

### 6.1 主信息模型

面板围绕以下层级展示：

```text
Workspace
  Track
    Task
      Core Materials
        Latest Artifact
        Artifact History
        Related Runs
      Commands
```

### 6.2 页面结构

```text
1. Workspace Overview
2. Track List
3. Selected Track Detail
   3.1 Track Summary
   3.2 Task List
   3.3 Selected Task Materials
   3.4 Track Progress Notes
   3.5 Next Commands
4. Run History
5. Source Details
```

### 6.3 默认阅读路径

```text
看有哪些 tracks
-> 点开一个 track
-> 看 track 下有哪些 tasks
-> 看 task 核心物料
-> 看当前缺口
-> 复制下一条 switch
```

## 7. 功能需求

## 7.1 Workspace Overview

### 需求

面板顶部必须展示 workspace 当前数据概况。

### 必须展示

- Workspace name。
- Data status：loading / live / failed。
- Generated time。
- Track count。
- Task count。
- Artifact count。
- Run count。
- Project code location：当前固定展示 `projects/app/`。

### 展示示例

```text
BuddySwitch Env
Live: 2026-04-13 10:30
Tracks 1 | Tasks 4 | Artifacts 7 | Runs 9
Project code: projects/app
```

### 验收标准

- 用户能在顶部确认数据是否成功加载。
- 用户能看到 workspace 内对象数量。
- 顶部区域不展示 raw object path 列表。

## 7.2 Track List

### 需求

Track List 必须让用户清楚看到当前有哪些 track，并快速判断每条 track 的推进状态。

### 每个 track 必须展示

- Track title。
- Track summary。
- Track status。
- Current buddy。
- Next buddy。
- Task count。
- Artifact count。
- Latest task title。
- Latest artifact title 或 summary。
- Latest updated time。
- Status note。

### Status note 规则

第一版只做轻量事实归纳，不做复杂判断：

- 如果 track 有 dev artifact 但没有 test task 或 test artifact，显示 `needs test`。
- 如果 task reference 缺失，显示 `missing task reference`。
- 如果没有 artifact，显示 `no material yet`。
- 如果有 known limitations，显示 `has limitations`。
- 如果没有明显问题，显示 `ready` 或空状态。

### 展示示例

```text
日程管理工具 Landing Page 快速开发
active | current: pm | next: dev | tasks 4 | artifacts 7
Latest task: 确认当前最新 PRD 与 design/pm 交接要求
Latest material: DEV implement-task - 推进开发
Status note: needs test
```

### 验收标准

- 用户不用进入详情也能看到每个 track 的 task 数量和最新核心物料。
- Track row 不只显示 title/status。
- Track row 不默认显示 object path。

## 7.3 Selected Track Summary

### 需求

选中 track 后，详情顶部必须用简短摘要说明该 track 当前状态。

### 必须展示

- Track title。
- Track summary。
- Status。
- Current buddy。
- Next buddy。
- Task count。
- Artifact count。
- Latest run。
- Latest artifact。
- Next suggested action。

### 展示示例

```text
Track: 日程管理工具 Landing Page 快速开发
Goal: 聚焦首版 landing page 的产品定义与快速开发交付。
State: active
Flow: pm -> dev
Tasks: 4 | Artifacts: 7
Latest output: Dev implemented P0 landing page in projects/app.
Next: Run smoke checks for latest implementation.
```

### 验收标准

- 用户在 track detail 顶部能看到当前状态和下一步。
- Raw task id / artifact id 不是摘要主内容。
- 如果没有 next command，必须显示明确 fallback，例如 `No recommended command available`。

## 7.4 Task List

### 需求

Task List 是 selected track detail 的主体。它必须清楚展示该 track 下所有 task。

### 每个 task 必须展示

- Buddy。
- Task status。
- Task title。
- Task id，次要展示。
- Updated time。
- Task summary。
- Artifact count。
- Latest artifact title。
- Latest artifact summary。
- Latest run id。

### 排序规则

默认按 project 推进顺序分组，再按更新时间排序：

```text
pm
market
pm
design
dev
test
```

如果不能可靠识别 task 对应 skill，则按 track.task_ids 原始顺序展示，避免误导。

### 交互状态

第一版需要支持 selected task 状态：

- 默认选中 selected track 下最新 updated task。
- 点击 task 后，`Selected Task Materials` 更新为该 task 的核心物料。

### 空状态

- 如果 track 没有 task，展示 `No task objects attached to this track`。
- 如果 track 引用 missing task id，展示 missing row，但不要中断其他 task 展示。

### 验收标准

- 用户能看到 selected track 下所有 task。
- 每个 task 能直接看到 buddy、status、summary、latest artifact。
- 点击或选择 task 后，能看到该 task 的物料详情。
- 同一 buddy 的多个 task 不被合并成一条。

## 7.5 Selected Task Materials

### 需求

Selected Task Materials 必须展示当前 task 的核心物料，避免用户打开 artifact JSON。

### 必须展示

- Selected task title。
- Latest artifact title。
- Latest artifact summary。
- Source run。
- Artifact history。
- Related runs。
- Material highlights。

### Material highlights 提取规则

根据 artifact content 中存在的字段展示，不强行填空。

#### PM / PRD 类物料

优先展示：

- Goal / problem。
- P0 scope。
- P1 scope。
- Out of scope。
- Acceptance criteria。
- Handoff notes。
- Open questions。

#### Market 类物料

优先展示：

- Target users。
- Demand signals。
- Competitors。
- Positioning。
- Assumptions。
- Open questions。

#### Design 类物料

优先展示：

- IA structure。
- Key flows。
- Required sections。
- Interaction notes。
- Content hierarchy。
- Open questions。

#### Dev 类物料

优先展示：

- Changed files。
- Implementation notes。
- Verification runs。
- Known limitations。
- Open questions。

#### Test 类物料

优先展示：

- Overall result。
- Passed checks。
- Failed checks。
- Blocked checks。
- Regression notes。
- Open questions。

### 展示示例

```text
Selected Task
Dev | active
确认当前最新 PRD 与 design/pm 交接要求，不进行开发

Latest Material
DEV implement-task - 推进开发
Summary: Implemented the approved DayFlow consumer landing page P0 in projects/app.
Source run: run-00ebe14c15

Changed files
- projects/app/index.html
- projects/app/main.js
- projects/app/styles.css

Verification
- node --check projects/app/main.js: passed
- local preview: passed
- Playwright responsive preview: passed

Known limitations
- Signup still uses localStorage fallback.
- Product name is placeholder.
- Privacy link is placeholder.
```

### 空状态

- 如果 task 没有 artifact，展示 `No material has been persisted for this task yet`。
- 如果 artifact content 为空，只展示 title、summary、source run。
- 如果 artifact id 缺失或无法匹配，展示 missing material note。

### 验收标准

- 用户能在 task detail 中读到 artifact summary。
- Dev artifact 中的 changed files、verification、limitations 能被展示出来。
- 不存在的字段不显示空标题。
- Raw JSON 默认不展开。

## 7.6 Track Progress Notes

### 需求

Track Progress Notes 提供轻量过程管理视图，帮助用户看到当前 track 的明显进度和缺口。

### 必须展示

- Buddy coverage：哪些 buddy 已经有 task 或 artifact。
- Latest completed action。
- Missing materials。
- Visible limitations。
- Data issues。

### 第一版判断规则

只做明确、低风险判断：

- 如果有 buddy task，标记该 buddy 已出现。
- 如果有 task.latest_artifact，标记该 task 有 material。
- 如果 latest dev artifact 存在且没有 test artifact，标记 `needs test`。
- 如果 artifact content 中有 `known_limitations`，直接展示为 visible limitations。
- 如果 track.missing_task_ids 非空，展示 data issue。

### 展示示例

```text
Progress
- PM: track and PRD material exist.
- Market: research material exists.
- Design: IA material exists.
- Dev: implementation material exists.
- Test: no smoke-test material yet.

Needs attention
- Latest implementation has not been validated by test.
- Signup still uses localStorage fallback.
```

### 验收标准

- 用户能看到每个 buddy 是否已有相关 task/material。
- 明显缺失项被集中展示。
- 面板不声称无法从数据确认的结论。

## 7.7 Next Commands

### 需求

Next Commands 必须帮助用户直接继续推进 selected track。

### 必须展示

- One recommended command。
- Template command。
- Continue current task command，如果可用。
- Handoff command，如果可用。

### 推荐命令来源

优先级：

1. selected track 相关最新 run 的 `recommended_switch`。
2. selected track 相关最新 run 的 `reference_switches.handoff_to_next_buddy`。
3. selected track 相关最新 run 的 `reference_switches.continue_current_task_in_track`。
4. selected track 相关最新 run 的 `reference_switches.continue_current_task`。
5. fallback：`switch <next_buddy> -> <track-id>: <demand>`。

### 展示规则

- 只突出一条 recommended command。
- 其他命令放在 templates。
- Cleanup commands 不放在主命令区。

### 验收标准

- 用户能复制一条推荐 `switch`。
- 推荐命令和 selected track 相关。
- 没有相关 run 时也有合理 fallback。

## 7.8 Run History

### 需求

Run History 用于追溯 selected track 的过程，不作为默认主阅读入口。

### 必须展示

- Time。
- Buddy。
- Skill。
- Demand。
- Execution summary。
- Persisted status。
- Linked task。
- Linked artifact。
- Recommended switch at that time。

### 范围规则

- 默认只展示 selected track 相关 runs。
- 全局 run audit 可以作为 secondary view 或折叠区。
- 最近 runs 优先展示。

### 验收标准

- 用户能追溯 selected track 的 run 历史。
- Run history 不干扰 task/material 主视图。
- Invalid run audit 能显示 failed/invalid 状态。

## 7.9 Source Details

### 需求

Source Details 保留工程调试信息，但默认折叠。

### 可展示内容

- Manifest path。
- Track object path。
- Task object path。
- Artifact object path。
- Run audit path。
- Raw structured JSON。
- Missing object references。

### 验收标准

- Debug 信息仍可访问。
- 默认视图不被 object path 和 raw JSON 淹没。

## 8. 数据需求

## 8.1 现有数据来源

第一版使用现有 `/api/workspace` 返回数据：

- `generated_at`
- `manifest_path`
- `objects_root`
- `buddies[]`
- `tracks[]`
- `tracks[].tasks[]`
- `tracks[].missing_task_ids[]`
- `tasks[]`
- `tasks[].latest_artifact`
- `artifacts[]`
- `run_audits[]`

## 8.2 允许的展示层派生

允许在 `scripts/workspace_data.py` 或前端中派生以下字段：

- `track.task_count`
- `track.artifact_count`
- `track.latest_task`
- `track.latest_artifact`
- `track.latest_run`
- `track.status_note`
- `track.buddy_coverage`
- `task.artifact_count`
- `task.material_highlights`
- `track.progress_notes`
- `track.next_commands`

这些字段是展示层聚合，不改变 canonical object 的含义。

## 8.3 不要求新增的持久化字段

第一版不要求新增：

- persisted track health。
- persisted buddy coverage。
- persisted current handoff。
- persisted material highlights。
- persisted command recommendation。

如未来需要，可以在验证面板价值后再决定是否沉淀到 runtime。

## 9. 内容规范

### 9.1 默认展示语言

面板文案应优先使用用户能直接理解的 project 语言：

- 使用 `Latest material`，少用 `latest_artifact_id`。
- 使用 `Needs test`，少用 `missing test artifact inferred from object graph`。
- 使用 `Changed files`，少用 `artifact.content.changed_files`。

### 9.2 ID 展示原则

- Title / summary 优先。
- ID 作为次要信息展示。
- Object path 默认折叠。
- Raw JSON 只在 Source Details 中展示。

### 9.3 空状态原则

空状态必须说明“缺什么”和“下一步怎么补”，而不是只写 `none`。

示例：

```text
No material has been persisted for this task yet.
Continue this task with:
switch dev(task-id) -> track-id: <demand>
```

## 10. 状态与边界场景

### 10.1 无 tracks

展示：

```text
No tracks found.
Start with: switch pm: create a track for <project goal>
```

### 10.2 Track 无 tasks

展示：

```text
No task objects attached to this track.
Continue with: switch pm -> <track-id>: define the first task
```

### 10.3 Task 无 artifacts

展示：

```text
No material has been persisted for this task yet.
```

### 10.4 Artifact content 不符合预期

展示 artifact title 和 summary，隐藏 raw content 到 Source Details。

### 10.5 Missing references

如果 track 引用了不存在的 task，或 task 引用了不存在的 artifact/run：

- 正常展示可用对象。
- 在 Track Progress Notes 中展示 data issue。
- 在 Source Details 中展示具体 missing id。

### 10.6 Run audit invalid

在 Run History 中展示 invalid 状态，不阻断 workspace 其他数据展示。

## 11. MVP 范围

第一版必须完成：

1. Workspace Overview 显示对象计数和 live 状态。
2. Track List 显示 track 摘要行，而不是只有标题按钮。
3. Selected Track Summary 显示状态、latest output、next action。
4. Selected Track Detail 主体改为 Task List。
5. Task List 每条展示 buddy、status、summary、latest artifact、artifact count、latest run。
6. 支持 selected task。
7. Selected Task Materials 展示 latest artifact summary 和核心 highlights。
8. Track Progress Notes 展示 buddy coverage、missing materials、known limitations、data issues。
9. Next Commands 展示一条推荐 switch 和备用模板。
10. Run History 只展示 selected track 相关 run。
11. Source Details 默认折叠。

## 12. 暂缓范围

以下内容不进入 MVP：

- 多 workspace 切换。
- 全文搜索。
- 高级筛选和排序配置。
- 拖拽调整 task 顺序。
- 图形化流程图。
- 面板内运行 switch。
- 面板内 cleanup execute。
- 多项目代码目录自动发现。
- 新 artifact schema 迁移。

## 13. 验收标准

### 13.1 用户验收

使用当前示例数据时，用户应能在 30 秒内回答：

- 当前有 `日程管理工具 Landing Page 快速开发` 这个 track。
- 该 track 有 4 个 task。
- task 覆盖 pm、market、design、dev。
- dev task 有 implementation report。
- dev implementation 改了 `projects/app/index.html`、`projects/app/main.js`、`projects/app/styles.css`。
- dev implementation 有 verification runs。
- 当前仍缺 test smoke material。
- 下一条推荐命令应指向 test 或至少能继续 selected track。

### 13.2 功能验收

- `/api/workspace` 加载成功时，面板显示 live 状态。
- 选择 track 后，Task List 更新为该 track 下的 tasks。
- 选择 task 后，Selected Task Materials 更新为该 task 的 latest artifact。
- Artifact content 中的 known limitations 能出现在 material 或 progress notes 中。
- Missing task references 能被展示为 data issue。
- Run History 默认过滤 selected track。
- Source Details 默认折叠。

### 13.3 边界验收

- 没有 tracks 时页面不报错。
- Track 没有 tasks 时页面不报错。
- Task 没有 artifact 时页面不报错。
- Artifact content 字段缺失时页面不报错。
- Invalid run audit 不影响其他区域展示。

## 14. 成功指标

### 定性指标

- 用户不再需要打开 JSON 文件理解当前 track。
- 用户能从 track 直接进入 task，再进入 task materials。
- 用户能明确知道下一条 `switch`。
- 用户能区分 project information 和 debug source details。

### 定量指标

可用人工检查方式验证：

- 找到某个 track 下所有 task 的时间小于 10 秒。
- 找到某个 task 最新 artifact 摘要的时间小于 10 秒。
- 找到 dev changed files 的时间小于 15 秒。
- 找到下一条 recommended switch 的时间小于 10 秒。

## 15. 实施建议

### Phase 1: 信息重排

- 重构 `framework/console/index.html` 的区域结构。
- 重构 `framework/console/app.js` 的 render 层。
- 保持 `/api/workspace` 返回结构基本不变。
- 用前端 helper 从现有对象派生 counts、latest、status note。

### Phase 2: 展示层派生下沉

- 如果前端 helper 变复杂，再把稳定派生移动到 `scripts/workspace_data.py`。
- 只下沉明显通用字段，例如 task count、artifact count、latest run。

### Phase 3: 后续增强

- 根据真实使用反馈决定是否需要搜索、筛选、流程图或更强 health model。
- 如果 artifact highlights 变成稳定需求，再考虑 schema-level standardization。

## 16. 风险与约束

### 风险

- Artifact content schema 不统一，highlights 提取需要容错。
- Current buddy / next buddy 可能与最新 run 推荐不完全一致。
- 如果 status note 过度推断，会误导用户。
- 如果默认展示过多字段，面板会重新变得拥挤。

### 约束

- Context Panel 必须保持只读。
- Debug 信息必须可追溯，但不能成为默认入口。
- 第一版不得依赖复杂后端迁移。
- 展示层派生必须能在数据缺失时 graceful fallback。

## 17. Open Questions

- Track task 排序最终以 `track.task_ids` 为准，还是以 buddy 推荐顺序为准？
- Test task 不存在时，是否应该在面板中显示一个 virtual missing step？
- `current_buddy` / `next_buddy` 与 latest run recommendation 不一致时，面板应该优先信任哪个？
- Cleanup commands 是否完全移到 Source Details，还是保留一个独立 Tools 区？

## 18. 最终判断标准

这次重构不是为了让面板看起来更复杂，而是为了让 BuddySwitch project 过程更容易被管理。

达标后的面板应该让用户自然按下面路径工作：

```text
我有哪些 track
-> 这个 track 有哪些 task
-> 这个 task 有哪些核心物料
-> 现在还缺什么
-> 下一条 switch 是什么
```

如果用户仍然需要在 Track、Artifact Timeline、Run Audits、JSON details 之间来回找信息，说明重构没有成功。
