# BuddySwitch Phase 2C Direct Convergence Plan

## 1. 目标

直接做到 Phase 2C，不再拆 A/B 兼容阶段。

本阶段目标是移除派生 markdown artifact 和 run summary 作为运行产物，只保留三类 BuddySwitch 托管状态：

- artifact object
- track object
- run audit JSON

`artifacts/*.md` 和 `runs/summaries/**` 不再作为 runtime 输出、Context Panel 数据源或兼容层。

## 2. Public Interfaces

### Artifact object

Artifact object 是唯一 artifact 载体。

保留：

- `id`
- `track_id`
- `buddy`
- `skill_id`
- `title`
- `summary`
- `content`
- created / updated timestamps

移除：

- `path`
- `summary_path`
- 任何指向 `artifacts/*.md` 或 `runs/summaries/**` 的派生输出字段

Artifact 的对象文件位置由 object id 决定：

`buddyswitch/objects/artifacts/<artifact-id>.json`

### Resolve

`scripts/switch_runtime.py resolve` 不再返回 artifact markdown 或 summary 默认路径。

如果任务或显式参数要求输出到：

- `artifacts/*.md`
- `runs/summaries/*.md`

runtime 应返回明确错误，提示派生 markdown 输出已退役，应使用 artifact object 和 run audit。

### Persist receipt

`scripts/switch_runtime.py persist` 的 receipt 只返回对象和 run audit 路径。

保留：

- `artifact`
- `track`
- `run`

移除：

- `artifact_markdown`
- `summary`

### Workspace API

`/api/workspace` 不再返回：

- `untracked_artifacts`
- `summaries`

新增或保留一个明确的运行历史字段：

- `run_audits`

`run_audits` 来源于 canonical run audit JSON，而不是 `runs/summaries/**`。

## 3. Implementation Changes

### Runtime persistence

更新 `scripts/switch_runtime.py`：

- 删除 artifact markdown path 推导。
- 删除 summary path 推导。
- 删除 `_render_artifact_markdown`。
- 删除 `_render_summary_markdown`。
- 删除 persist 阶段对 `artifacts/*.md` 和 `runs/summaries/**` 的写入。
- track-manager 和 artifact skill 都只写 object store 与 run audit。

### Store and schema

更新 artifact object schema 与 store helpers：

- artifact object 不再需要 markdown `path`。
- artifact object 不再记录 `summary_path`。
- create / update / delete artifact 不再生成、校验、删除 markdown 文件。
- UI 需要展示对象位置时，展示 object path，而不是 markdown path。

### Run audit

Run audit 只保存执行审计所需信息，避免复制 canonical content。

保留：

- switch / buddy / task
- `skill_id`
- `run_id`
- `artifact_id`
- `track_id`
- track action
- receipt paths
- writes
- execution summary
- working notes
- deliverables or changed files
- suggested next switch
- timestamp

移除：

- 完整 result payload
- 完整 artifact content
- 派生 markdown summary 内容
- `artifact_path`
- `summary_path`

Artifact 正文只存在 artifact object 中。

### Context Panel

更新 `scripts/workspace_data.py` 与 `framework/console/`：

- artifact 列表和详情从 artifact object 读取。
- artifact 内容展示来自 object `content`。
- run history 来自 `run_audits`。
- 删除 artifact inbox diagnostics。
- 删除 run summaries 面板。
- 删除 markdown exists / missing file 等兼容状态。

### Cleanup

更新 cleanup 系统：

- 移除 `artifact_markdown` cleanup category。
- 移除 `run_summaries` cleanup category。
- skeleton 不再创建 `artifacts/` 或 `runs/summaries/` 作为 BuddySwitch 必需目录。
- 删除仓库中用于保留这些目录的 tracked placeholder。

已有本地未跟踪 markdown 文件不自动删除，只在最终执行报告中列出。

### Docs

同步更新：

- `README.md`
- `AGENTS.md`
- `framework/docs/**`
- 本审查包状态页

文档应明确：

- canonical state 是 object + run audit。
- markdown artifacts / summaries 已退役。
- panel 不再依赖 markdown 兼容层。

## 4. Test Plan

执行并更新测试，使以下场景成立：

- `python3 -m unittest discover -s tests` 通过。
- `python3 -m py_compile` 覆盖 runtime、store、workspace、cleanup 脚本。
- persist 不写 `artifacts/*.md`。
- persist 不写 `runs/summaries/**`。
- persist receipt 不包含 `artifact_markdown` 或 `summary`。
- artifact object 包含 canonical `content`。
- run audit 不包含完整 artifact content 或完整 result payload。
- `/api/workspace` 不包含 `untracked_artifacts` 和 `summaries`。
- `/api/workspace` 包含基于 run audit JSON 的运行历史。
- 显式请求 markdown 输出时得到明确错误。
- `git diff --check` 通过。

## 5. Assumptions

- 本阶段不保留 shadow markdown 输出。
- 本阶段不增加 feature flag。
- `artifacts/*.md` 和 `runs/summaries/**` 不再属于 BuddySwitch 托管状态。
- 历史本地 markdown 文件如果存在，只作为人工遗留，不由 runtime 或 cleanup 自动维护。
- `projects/app/` 不在本次改造范围内，除非测试发现它直接依赖已删除的 workspace 字段。

## 6. Acceptance Criteria

- （Phase 2 术语）一次 `switch <buddy>: <task>` 持久化后，只产生或更新 artifact object、track object、run audit JSON。
- （当前 Phase 3）一次 `switch <buddy>...: <demand>` 持久化后，run 必须绑定 task，并产生或更新 task object、artifact object、（必要时）track object 与 run audit JSON。
- Context Panel 能在没有 `artifacts/*.md` 和 `runs/summaries/**` 的情况下展示 workspace。
- 仓库文档不再宣称 markdown artifacts 或 run summaries 是当前兼容层。
- 测试覆盖新的对象化路径，并移除对 markdown 兼容输出的断言。
