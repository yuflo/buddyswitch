# BuddySwitch Context Panel Information Structure

## 当前重构原则

现阶段面板重构的目标不是发明一套很强、很特别的新结构，也不是先推动大量后端数据结构改造。

当前最关键的问题是：**已有 BuddySwitch 信息没有被清晰组织出来**。

用户在使用 BuddySwitch 开发 project 时，首先需要直观看到：

- 当前有哪些 track。
- 每个 track 下有哪些 task。
- 每个 task 是哪个 buddy 做的，当前状态是什么。
- 每个 task 里有哪些核心物料：artifact、最新产出、关键摘要、变更文件、验证结果、限制、后续问题。
- 每个 track 当前推进到了哪里，下一步该做什么。
- 需要追溯时，能看到对应 run 和 switch 命令。

所以面板应该先成为一个清晰的信息管理面板，而不是复杂的智能驾驶舱。

## 设计边界

### 当前不做

- 不为了面板先改大量后端 object schema。
- 不要求 runtime 新增复杂状态机。
- 不把 debug object path 作为主要阅读入口。
- 不默认展示大段 raw JSON。
- 不把面板设计成另一个执行器；面板仍然只读。

### 当前要做

- 使用现有 `/api/workspace` 数据重新组织展示。
- 让 track、task、artifact、run 的关系一眼清楚。
- 把用户最常用的信息放在默认视野里。
- 把低频 debug 信息折叠。
- 让用户能直接复制下一条合理的 `switch` 继续推进。

## 核心信息模型

当前面板应该围绕一个简单层级组织：

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

这个层级比“Track / Artifact Timeline / Run Audits”更贴近用户理解 project 过程的方式。

用户不是先关心某个 artifact 文件在哪里，而是先关心：

```text
这个 track 下面有哪些任务？
这些任务分别交给谁做了？
每个任务产出了什么核心物料？
现在还缺什么？
下一步怎么继续？
```

## 面板整体结构

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

默认阅读路径应该很短：

```text
看有哪些 tracks -> 点开一个 track -> 看 task 列表 -> 看 task 核心物料 -> 复制下一条 switch
```

## 1. Workspace Overview

### 目的

让用户确认自己正在看哪个 BuddySwitch workspace，以及数据是否是当前的。

### 默认展示

- Workspace name。
- 数据刷新时间。
- Track 数量。
- Task 数量。
- Artifact 数量。
- Run 数量。
- Project code location，例如 `projects/app/`。

### 示例

```text
BuddySwitch Env
Live: 2026-04-12 22:55
Tracks 1 | Tasks 4 | Artifacts 7 | Runs 9
Project code: projects/app
```

### 注意

这里不需要复杂说明。它只是一个确认栏，不应该占据太多空间。

## 2. Track List

### 目的

让用户清晰看到“当前有哪些项目线”，并能快速判断每条线推进到了哪里。

### 每个 track 默认展示

- Track title。
- Track status。
- Track summary。
- Current buddy。
- Next buddy。
- Task 数量。
- 最新更新时间。
- 最新 task。
- 最新 artifact。
- 简短状态提示，例如 `needs test`、`ready for dev`、`has blockers`。

### 示例

```text
日程管理工具 Landing Page 快速开发
active | current: pm | next: dev | 4 tasks | updated 20:44
Latest task: 确认当前最新 PRD 与 design/pm 交接要求
Latest material: DEV implementation report
Status note: implementation done, smoke test missing
```

### 展示重点

Track List 不应该只是 track title 列表。它应该让用户不用进入详情也能大致知道：

- 这个 track 是什么。
- 有多少任务。
- 当前停在哪个 buddy。
- 最新成果是什么。
- 下一步大概是什么。

## 3. Selected Track Detail

选中一个 track 后，主区域展示它的完整过程管理信息。

## 3.1 Track Summary

### 目的

用最短内容回答“这个 track 当前是什么状态”。

### 默认展示

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

### 示例

```text
Track: 日程管理工具 Landing Page 快速开发
Goal: 聚焦首版 landing page 的产品定义与快速开发交付。
State: active
Flow: pm -> dev
Tasks: 4
Latest output: Dev implemented P0 landing page in projects/app.
Next: Run smoke checks for latest implementation.
```

### 注意

这一块不展示 raw ID 作为主内容。ID 可以放在次要位置或折叠详情里。

## 3.2 Task List

### 目的

这是面板当前最需要补强的部分：**清楚展示 track 对应的 task**。

用户必须能直接看到一个 track 下有哪些 task，以及每个 task 的核心产出。

### 每个 task 默认展示

- Task title。
- Task id，次要展示。
- Buddy。
- Status。
- Created / updated time。
- Latest run。
- Latest artifact。
- Artifact count。
- Task summary。
- 核心物料摘要。

### 推荐排列

按 buddy/project 推进顺序优先，其次按更新时间：

```text
PM / track-manager
Market / research-scan
PM / write-prd
Design / ia-spec
Dev / implement-task
Test / smoke-test
```

如果同一个 buddy 有多个 task，不要混成一条；每个 task 保留独立卡片或行。

### 示例

```text
Dev | active
确认当前最新 PRD 与 design/pm 交接要求，不进行开发
Updated: 20:44 | Artifacts: 2 | Latest run: run-00ebe14c15
Summary: Implemented the approved DayFlow consumer landing page P0 in projects/app.
Latest material: implementation report
```

### 展示重点

Task List 是 track 详情的主体。它应该回答：

- 这个 track 由哪些 task 组成？
- 每个 task 是谁做的？
- 每个 task 现在完成到什么程度？
- 每个 task 留下了哪些可用物料？

## 3.3 Selected Task Materials

### 目的

当用户点选或聚焦一个 task 时，清楚展示这个 task 里面的核心物料。

这里是从“任务列表”进入“任务产出”的地方。

### 默认展示

- Latest artifact。
- Artifact history。
- Related runs。
- Material highlights。
- Known limitations。
- Verification results。
- Changed files。
- Open questions。

不是每个 task 都有所有字段。面板应该根据 artifact content 有什么就展示什么，不要强行填空。

### Latest Artifact

展示这个 task 当前最重要的产出。

示例：

```text
Latest Artifact
DEV implement-task - 推进开发
Summary: Implemented the approved DayFlow consumer landing page P0 in projects/app.
Source run: run-00ebe14c15
```

### Material Highlights

根据不同 artifact content 提取核心内容。

PM / PRD 物料可以展示：

- Problem / goal。
- P0 scope。
- P1 scope。
- Out of scope。
- Acceptance criteria。
- Handoff note。

Market 物料可以展示：

- Target users。
- Demand signals。
- Competitor notes。
- Positioning insight。
- Assumptions。

Design 物料可以展示：

- IA structure。
- Key flows。
- Required sections。
- Interaction notes。
- Content hierarchy。

Dev 物料可以展示：

- Changed files。
- Implementation notes。
- Verification runs。
- Known limitations。

Test 物料可以展示：

- Smoke result。
- Passed checks。
- Failed checks。
- Blocked checks。
- Regression notes。

### 示例

```text
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

### 展示重点

用户不应该为了看 task 核心物料去打开 artifact JSON。

Task Materials 区应该把 artifact 里的结构化内容转成可读摘要。

## 3.4 Track Progress Notes

### 目的

给用户一个轻量的过程管理视图，说明当前 track 的推进状态。

这不是复杂状态机，只是基于现有 task、artifact、run 的展示归纳。

### 默认展示

- 已有 buddy 覆盖。
- 最新完成的关键动作。
- 当前缺口。
- 当前风险。
- 数据完整性问题。

### 示例

```text
Progress
- PM: track created and PRD prepared.
- Market: research artifact exists.
- Design: IA spec exists.
- Dev: implementation artifact exists.
- Test: no smoke-test task or artifact yet.

Needs attention
- Latest implementation has not been validated by test.
- Dev artifact lists placeholder backend/product-name/privacy-link limitations.
```

### 注意

这里不要做过度智能判断。第一版只需要把明显事实组织清楚：

- 有哪些 buddy/task 已经出现。
- 哪些 artifact 已经出现。
- 哪些明显物料缺失。
- 哪些 known limitations 明确存在。

## 3.5 Next Commands

### 目的

让用户能直接继续工作。

### 默认展示

- Recommended command。
- Continue current task command。
- Continue current task in track command。
- Handoff command，如果存在。

### 示例

```text
Recommended
switch test -> track-schedule-tool-landing-page: Run smoke checks for latest implementation

Continue current task
switch dev(task-dev-prd-design-pm-45f5a1) -> track-schedule-tool-landing-page: <demand>
```

### 展示重点

只突出一条推荐命令。其他命令作为备选模板。

Cleanup 命令不要混在这个主区域里，可以放到 Source Details 或工具区。

## 4. Run History

### 目的

Run History 用来追溯过程，不是默认主视图。

用户已经能在 Track Detail 里看到 track、task、核心物料后，才需要 run 作为审计证据。

### 每条 run 默认展示

- Time。
- Buddy。
- Skill。
- Demand。
- Execution summary。
- Persisted status。
- Linked task。
- Linked artifact。
- Recommended switch at that time。

### 示例

```text
20:44 | dev / implement-task
Demand: 推进开发
Result: Implemented approved landing page P0 in projects/app.
Task: task-dev-prd-design-pm-45f5a1
Artifact: art-task-dev-prd-design-pm-45f5a1-implementation-report-2
```

### 注意

Run History 可以默认只展示当前 selected track 相关 runs。全局 run audit 列表可以折叠或放到次要区域。

## 5. Source Details

### 目的

保留工程追溯能力，但不影响默认阅读。

### 默认折叠展示

- Track object path。
- Task object path。
- Artifact object path。
- Run audit path。
- Raw structured JSON。
- Manifest path。
- Missing object references。

### 注意

Source Details 是 debug 区，不应该成为用户理解 project 过程的入口。

## 使用现有数据即可支持的内容

当前 `/api/workspace` 已经足够支持第一版重构：

- `tracks[]` 可以展示 track list 和 selected track summary。
- `tracks[].tasks[]` 可以展示 track 对应 task。
- `tasks[].latest_artifact` 可以展示 task 最新核心物料。
- `tasks[].artifact_ids` 可以展示 artifact count 和 artifact history 入口。
- `tasks[].run_ids` / `latest_run_id` 可以关联 task run 过程。
- `artifacts[].summary` 可以展示核心产出摘要。
- `artifacts[].content` 可以提取 changed files、verification、known limitations、PRD scope、design spec 等结构化物料。
- `run_audits[]` 可以展示 run history 和 switch commands。
- `run_audits[].reference_switches` / `recommended_switch` 可以生成命令区。

第一版可以只做前端/展示层归纳，不要求新增后端 object schema。

## 允许的轻量派生

为了展示清楚，前端或 workspace data builder 可以做轻量派生，但这些不应该变成新的复杂后端模型：

- Track 的 task count。
- Track 的 artifact count。
- Track 的 latest task / latest artifact / latest run。
- 每个 task 的 latest artifact highlights。
- 每个 track 的 obvious missing materials，例如 latest dev exists but no test artifact。
- 每个 track 的 visible limitations，直接来自 artifact content。

这些都属于展示层聚合，不是新的业务状态系统。

## 最小可落地重构

第一版重构只需要解决信息组织问题：

1. Track List 从“标题按钮”升级为“track 摘要行”。
2. Selected Track Detail 顶部展示 track summary。
3. Track Detail 主体展示 task list。
4. 每个 task 行展示 buddy、status、summary、latest artifact、artifact count、latest run。
5. 增加 Selected Task Materials，展示该 task 的 artifact 摘要和核心结构化内容。
6. Run History 只展示 selected track 相关 runs，并弱化为追溯区。
7. Next Commands 只突出一条推荐命令，其余模板次要展示。
8. Object path 和 raw JSON 放入 Source Details。

## 判断是否达标

用户打开面板后，应能在 30 秒内回答：

- 有哪些 track？
- 某个 track 下有哪些 task？
- 每个 task 是哪个 buddy 做的？
- 每个 task 当前状态是什么？
- 每个 task 最新核心物料是什么？
- 最新 artifact 里有哪些关键内容？
- 当前 track 还缺哪些明显物料？
- 下一条应该复制的 `switch` 是什么？

如果这些问题还需要用户打开多个 JSON 文件或在 run audit 里来回找，面板就还没有达到当前阶段的目标。
