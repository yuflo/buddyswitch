# BuddySwitch Phase 3 Task-Centric Runtime Plan

## 1. 目标

本阶段直接进入 task-centric 模型，不做兼容层，不保留旧数据结构的 shadow 字段。

本阶段要完成的不是“补一个 task 字段”，而是把 BuddySwitch 的运行抽象收敛为两层：

- 编排层：`run`、`task`、`track`
- 成果层：`artifact`

其中：

- `run` 是一次实际执行
- `task` 是一个 buddy domain 下的一件事，`run` 必须归属 `task`
- `track` 是一次显式标记的产品迭代串联，`task` 可选挂载到 `track`
- `artifact` 是当前阶段唯一的 durable 成果对象，是 run 的核心产出与协作信息载体

本阶段的核心硬决策：

- 每个 `run` 都必须有一个 `task`
- `run` 和 `task` 都可以不依赖 `track`
- `track` 的主串联关系改为 `task_ids`
- `artifact` 不与 `run/task/track` 视为同层容器，而是对象层产物
- 不做任何“隐式续接已有 task”的猜测；未显式写 `task-id` 时一律新建 task

## 2. Public Interfaces

### 2.1 Switch invocation 语法升级

canonical form 升级为：

```text
switch <buddy>(<task-id>) -> <track-id>: <demand>
```

可用形态只有以下 4 种：

1. `switch buddy -> track-id: demand`
2. `switch buddy(task-id): demand`
3. `switch buddy: demand`
4. `switch buddy(task-id) -> track-id: demand`

解析语义固定如下：

- `switch buddy -> track-id: demand`
  - 显式指定 `track-id`
  - 未指定 `task-id`
  - 自动创建一个新 task，`task.buddy = buddy`
  - 新 task 直接绑定到该 `track-id`
  - 首个 run 归属该 task

- `switch buddy(task-id): demand`
  - 显式指定 `task-id`
  - 本次 invocation 不显式指定 track
  - 在该 task 下继续 run
  - 如果 task 自身已有 `track_id`，则本次 run 的 effective track 继承该值

- `switch buddy: demand`
  - 未指定 `task-id`
  - 未指定 `track-id`
  - 自动创建一个新的无 track task
  - 首个 run 归属该 task

- `switch buddy(task-id) -> track-id: demand`
  - 显式指定 `task-id`
  - 显式指定 `track-id`
  - 在该 task 下继续 run
  - 若 task 尚未绑定 track，则在 persist 时把 task 绑定到该 track
  - 若 task 已绑定不同 track，则直接拒绝

parser / router / runtime 的结构化 payload 中，冒号后的文本不再使用 `task` 命名，统一改为 `demand`，避免与 task object 混淆。

### 2.2 Invocation / resolve payload contract

`parse_switch.py`、`codex_router.py`、`switch_runtime.py resolve` 的结构化 invocation 统一改为：

- `buddy`
- `task_id` (`null` when omitted)
- `track_id` (`null` when omitted)
- `demand`
- `raw_text`
- `normalized_text`

`switch_runtime.py resolve` 额外返回：

- `task_resolution`
  - `mode`: `create` | `reuse`
  - `task_id`
  - `task_exists`
  - `task_buddy`
  - `task_track_id`
- `effective_track_id`
  - 显式 track 优先
  - 否则继承 task 自身的 `track_id`
  - 否则为 `null`
- `task_context`
- `track_context`
- `eligible_skills`
- `skill_cards`
- `required_output_schema_by_skill`

`resolve` 仍保持 non-mutating；task 的实际创建和 task-track 绑定发生在 `persist`。

### 2.3 Object schemas

#### Task object

新增 canonical object：

`buddyswitch/objects/tasks/<task-id>.json`

Task schema v1：

- `id`
- `buddy`
- `title`
- `status` (`active | blocked | done | archived`)
- `track_id` (nullable)
- `artifact_ids`
- `run_ids`
- `latest_run_id`
- `latest_artifact_id` (nullable)
- `summary`
- `created_at`
- `updated_at`

规则：

- `task.buddy` 必填且不可变
- `run_ids` 至少包含 1 个 run；系统不支持“空 task”
- `track_id` 可为空
- `latest_run_id` 必须属于 `run_ids`
- `latest_artifact_id` 若非空，必须属于 `artifact_ids`

Task ID 自动生成规则：

- 默认前缀：`task-<buddy>-<slug(demand)>`
- 若冲突，按 `-2`, `-3` 追加
- `title` 默认取 `demand` 的前 6 到 8 个词，按现有 artifact title 策略截断

#### Artifact object

Artifact 继续作为第一种 durable object，但 schema 改为 task-first：

- 保留：`id`、`title`、`buddy`、`skill_id`、`summary`、`content`、timestamps
- 新增必填：`task_id`、`source_run_id`
- 移除：`track_id`

Artifact 与 track 的关系不再直接存储；需要时通过 `artifact.task_id -> task.track_id` 反查。

#### Track object

Track schema 改为 task-centric：

- 保留：`id`、`title`、`status`、`current_buddy`、`next_buddy`、`summary`、`updated_at`
- 移除：`artifact_ids`
- 新增：`task_ids`

Track 只串联 `task_ids`。任何 artifact 展示都通过 task 间接得到。

#### Run audit

Run audit 继续写入：

`buddyswitch/content/runs/<run-id>.json`

Run audit schema 调整为：

- `run_id`
- `timestamp`
- `switch`
  - `buddy`
  - `task_id`
  - `track_id`
  - `demand`
  - `raw_text`
  - `normalized_text`
- `resolved_task_id`
- `effective_track_id`
- `skill_id`
- `artifact_ids`
- `track_action` (nullable)
- `paths`
- `writes`
- `execution_summary`
- `working_notes`
- `deliverables_or_changed_files`
- `suggested_next_switch`

Run audit 仍是 receipt，不保存 canonical artifact content，也不承担当前状态 authority。

### 2.4 Context contract

本阶段把 context 明确做成两层，且都由脚本化控制层装配，不让宿主 LLM 自己拼 JSON。

#### Task context

`task_context` 默认包含：

- task 头信息：`id`、`buddy`、`status`、`summary`、`track_id`、`latest_run_id`、`latest_artifact_id`
- 该 task 下最新 5 个 artifacts，按更新时间倒序
- 该 task 下最新 3 个 run audits 的轻量 receipt，按时间倒序
  - 仅带 `run_id`、`skill_id`、`execution_summary`、`timestamp`

Task context 以 artifact 为主，run receipt 只作最近状态补充。

#### Track context

当 `effective_track_id` 存在时，`track_context` 默认包含：

- track 头信息：`id`、`title`、`status`、`current_buddy`、`next_buddy`、`summary`
- track 下所有 task 的轻量摘要
  - `task_id`
  - `buddy`
  - `status`
  - `summary`
  - `latest_artifact`

Track context 默认不注入 task 下的完整 run 历史。

## 3. Implementation Changes

### 3.1 Parser / router / runtime

更新 `scripts/parse_switch.py`、`scripts/codex_router.py`、`scripts/switch_runtime.py`：

- 支持新的 invocation 语法和规范化输出
- 把 `switch.task` 全量替换为 `switch.demand`
- 删除当前 runtime 里基于 `track_mode` 的通用 gate
- 所有技能统一改成 task-first；track 是否存在由 invocation 和 task state 决定，而不是由 skill metadata 决定
- `resolve` 负责：
  - 解析 `buddy/task_id/track_id/demand`
  - 校验显式 task 是否存在且归属 buddy
  - 校验显式 track 是否存在
  - 计算 `task_resolution`
  - 计算 `effective_track_id`
  - 组装 task / track context
- `persist` 负责：
  - 在 `mode=create` 时先创建 task
  - 在显式 task + 显式 track 且 `task.track_id is null` 时绑定 task 到 track
  - 生成 run audit
  - 写 artifact
  - 回写 task 聚合字段
  - 回写 track.task_ids

### 3.2 Skill metadata and output schemas

更新 `buddyswitch/skills/**/SKILL.md` 与 `framework/schemas/**`：

- 从 runtime metadata 中移除 `track_mode` 的控制语义
- skill 是否利用 track context，改为 resolve 自动装配；无 effective track 时 `track_context = null`
- 当前 artifact skills 继续一 run 产出一 artifact
- `track-manager` 的 track requirement 改为操作级校验：
  - `list` 可无 track
  - `create` 可无既有 track；创建成功后把当前 task 绑定到新 track
  - 其他操作要求有显式或 effective track target

### 3.3 Store helpers and debug APIs

更新 `scripts/env_store.py`：

- 增加 `TASKS_DIR`
- 增加 task validate / list / get / save / create / update helpers
- 更新 artifact validate / create / update 以支持 `task_id`、`source_run_id`
- 更新 track validate / save 以支持 `task_ids` 并移除 `artifact_ids`
- 增加 task 与 track、task 与 artifact 的 register / detach helpers

新增 `scripts/env_tasks.py` 作为 manual/debug API：

- `list`
- `read`
- `update`
- `archive`

更新 `buddyswitch/manifest.toml` 的 permissions metadata：

- 新增 `task.read`
- 新增 `task.create`
- 新增 `task.update`
- 新增 `task.archive`

manual/debug API 的 authority 规则：

- 所有 buddies 可以 `task.read`
- buddy 只能创建和更新自己名下的 task
- `pm` 仍独占 track lifecycle authority

### 3.4 Workspace API and console

更新 `scripts/workspace_data.py`、`framework/console/index.html`、`framework/console/app.js`、`framework/console/styles.css`：

- `/api/workspace` 新增 `tasks`
- track view 改为通过 `track.task_ids` 组装 task rows
- selected track 的 timeline 改为渲染 task cards，而不是 artifact 扁平列表
- 每个 task card 展示：
  - `task_id`
  - `buddy`
  - `status`
  - `summary`
  - `latest_artifact` preview
- run audit 列表改为显示 `buddy / task_id / demand / skill_id`
- 本阶段保持 panel track-first，不新增独立 task 浏览器

### 3.5 Cleanup

更新 `scripts/env_cleanup.py` 与 `scripts/cleanup_buddyswitch.sh` 对应行为：

- 新增 `task_objects` cleanup category
- launcher runtime workspace bootstrap 负责准备 `buddyswitch/objects/tasks/`
- cleanup 发现并删除 task objects
- 删除 task 时同步从所属 track 的 `task_ids` 中移除
- 删除 artifact 时同步从 task 的 `artifact_ids` 中移除
- 按 buddy cleanup 时，task 以 `task.buddy` 为筛选 authority
- run audit 的筛选继续以 `switch.buddy` 为准

### 3.6 Docs

实现时同步更新：

- `README.md`
- `AGENTS.md`
- `framework/docs/switch-spec.md`
- `framework/docs/track-registry.md`
- `framework/docs/interface-spec.md`
- `framework/docs/artifacts-runs-git-policy.md`
- 本审查包状态页

文档必须明确：

- `task` 已成为 canonical object
- `switch` 冒号后的语义是 `demand`，不再是 task text
- `track` 串联 task，不再直接串联 artifact
- `artifact` 通过 task 参与协作流转
- context 由 BuddySwitch 控制层脚本拼装，而不是由宿主 LLM 自行拼接

## 4. Test Plan

执行并更新测试，使以下场景成立：

- `python3 -m unittest discover -s tests` 通过
- `python3 -m py_compile` 覆盖 parser / router / runtime / store / workspace / cleanup 脚本
- 4 种新 switch 语法都能 parse / route / resolve
- 未显式写 `task-id` 时，一律生成 `mode=create` 的 task resolution
- `switch buddy(task-id): demand` 会校验 task 存在且 `task.buddy == buddy`
- `switch buddy(task-id) -> track-id: demand` 在 task 已绑定其他 track 时拒绝
- `switch buddy(task-id): demand` 在 task 自带 track 时得到正确 `effective_track_id`
- persist 会先创建或复用 task，再写 run audit
- persist 创建 artifact 时写入 `task_id` 和 `source_run_id`
- track object 只包含 `task_ids`
- workspace data 会返回 `tasks`
- panel 以 task cards 展示 track 内容
- cleanup 能删除 task objects，并同步修复 track/task 的引用
- `track-manager` create track 场景会把当前 task 绑定到新建 track
- run audit 不再出现 `artifact_id` 单数字段，只使用 `artifact_ids`
- `git diff --check` 通过

## 5. Assumptions

- 本阶段不引入通用 object 抽象；`artifact` 继续作为第一种 concrete durable object
- 本阶段不新增用户侧“显式创建 task”语法；task 创建只通过未显式写 `task-id` 的 run 自动发生
- 本阶段不做旧 track/artifact schema 的兼容读写
- 本阶段不做“自动续接最近 task / 唯一 active task”的隐式推断
- 当前技能仍维持“一 run 一 artifact”的结果结构；run audit 先升级为 `artifact_ids` 数组，预留未来多 artifact
- `projects/app/` 不在本次改造范围内，除非测试发现它直接依赖旧 workspace data 结构

## 6. Acceptance Criteria

- `switch buddy: demand` 会自动新建一个无 track task，并把首个 run 落到该 task
- `switch buddy -> track-id: demand` 会自动新建一个绑定该 track 的 task，并把首个 run 落到该 task
- `switch buddy(task-id): demand` 会稳定续接该 task，而不是隐式猜测其他 task
- `track` 通过 `task_ids` 串联跨 buddy 协作，track context 通过 task 的 latest artifact 传递信息
- task context 和 track context 都由 BuddySwitch 脚本控制层装配
- runtime、workspace API、cleanup、console、docs、tests 全部切换到 task-centric 模型，没有旧字段残留为 canonical state
