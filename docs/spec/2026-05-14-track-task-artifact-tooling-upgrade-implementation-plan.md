# Track/Task/Artifact Tooling Upgrade Code Implementation Plan

## 1. 任务目标

完成后，BuddySwitch 的普通 env tool 路径支持看到 `track_id`、`task_id`、`artifact_id` 后直接使用 `track.get`、`task.get`、`artifact.get` 继续工作；合法关系下可直接读取当前 track 源 artifact 全文，不合法时同一个工具返回无泄漏、可执行的恢复反馈。

当前核心瓶颈是跨 buddy 协作时 artifact 内容已经存在于 state 和 prepare context 中，但用户可见工具层只自然暴露 summary，Dev、Design、Test 等 buddy 看到 artifact id 后不能用 `artifact.get` 读取合法源材料。它最重要，因为这会让执行 buddy 停在计划阶段，或者被迫学习 binding/context 内部序列，而不是沿着 id 和工具反馈推进。

## 2. 需求提取

- `REQ-001`：普通路径遵守直接 id 规则：看到 `track_id` 用 `track.get`，看到 `task_id` 用 `task.get`，看到 `artifact_id` 用 `artifact.get`。
- `REQ-002`：目标 env tool 表面包含 `track.list`、`track.get`、`track.join`、`artifact.list`、`artifact.get`、`task.list`、`task.get`、`handoff.list`、`handoff.validate`、`handoff.create`、`run.validate_result`、`run.commit`。
- `REQ-003`：`track.list` 按 active buddy 相关性排序，并返回 track id、title、status、current buddy、next buddy、latest handoff summary、active-buddy relation、短 next command。
- `REQ-004`：`track.get` 是主 orientation surface，返回 track metadata、lifecycle、active-buddy relation、tasks、recent handoffs、current artifact summaries、readability flag 和 next action。
- `REQ-005`：`track.get` 不返回 foreign full artifact content，但必须返回 artifact ids，便于下一步调用 `artifact.get`。
- `REQ-006`：`track.join --track-id <track-id>` 创建或复用 active-buddy task，attach 到 track，并选择为当前工作。
- `REQ-007`：`track.join` 不修改 PM lifecycle 字段：`status`、`current_buddy`、`next_buddy`、track ownership。
- `REQ-008`：`track.join` 遇到一个 active-buddy task 时复用；没有时创建；多个可用 active-buddy tasks 时拒绝并要求显式 `--task-id`。
- `REQ-009`：`artifact.list --track-id <track-id>` 返回 track artifact summaries，不返回 full content。
- `REQ-010`：`artifact.list` rows 包含 `track_id`、relation、artifact id、kind、title、summary、source buddy、source task id、source run id、revision、currentness、readable flag、next action。
- `REQ-011`：`artifact.get --artifact-id <artifact-id>` 是 full-content artifact read entry point。
- `REQ-012`：`artifact.get` 允许读取 active-buddy-owned task 的 artifact，包括 owned historical artifact。
- `REQ-013`：`artifact.get` 允许读取 current artifact，当 active buddy 与 artifact 所在 track 存在合理关系。
- `REQ-014`：合理关系集合固定为 `pm_lifecycle_owner`、`participant`、`current_buddy`、`next_buddy`、`handoff_recipient`。
- `REQ-015`：foreign historical artifact 不因 track relation 被读取；relation-wide historical browsing 不在目标范围内。
- `REQ-016`：unrelated buddy、stale foreign artifact、unknown artifact id、malformed artifact id、missing task/track association、archived track relation 必须被拒绝。
- `REQ-017`：所有 blocked artifact body reads 必须包含 `no_content_leak: true`，且响应中不得包含 `content`、preview、partial body、foreign full body string、raw state path。
- `REQ-018`：blocked artifact body read 同一响应必须说明失败原因、permission boundary、detected relation、missing preconditions、next actions、command hint。
- `REQ-019`：`task.list` 显示 active-buddy tasks，以及 active buddy 可围绕其 orientation 的 relevant track-linked tasks。
- `REQ-020`：`task.get --task-id <task-id>` 让可见 task id 有用，返回 task metadata、owner buddy、track associations、active-buddy relation、current artifact summaries、readability flag、next command hints。
- `REQ-021`：`task.get` 不是 full artifact body reader；它必须指向 `artifact.get`。
- `REQ-022`：`handoff.list` 支持 `--track-id`，返回 recent handoffs、source buddy、target buddy、source task、source run、referenced artifact ids、status、是否授权 active buddy read。
- `REQ-023`：`handoff.validate` 校验 source task 属于 active buddy、source artifacts 属于 active buddy、target buddy 有效、track 存在、handoff 不隐含 lifecycle mutation、source artifacts current 或显式标记 historical。
- `REQ-024`：`handoff.create` 创建显式 handoff record，不作为 workflow router，不静默推进 track lifecycle。
- `REQ-025`：`run.validate_result` 校验 task id、track id、artifact ids、handoff payload ids、retired mutation fields、raw runtime state edit intent。
- `REQ-026`：`run.commit` 继续是 audit commit path，只提交声明结果，不修复 lifecycle、current-task、permission、task-track、artifact relation。
- `REQ-027`：`context` 保留 prepare/runtime snapshot、bulk projection、env summary、tool descriptions、active task facts、candidate summaries；不作为 direct artifact body read API。
- `REQ-028`：不得新增 `context.get_track_artifacts`、`context.inspect_track_outputs`、`context.explain_track_access`、`context.validate_sources_available` 作为 artifact read path。
- `REQ-029`：不得新增 normal-path `explain_*` tools；失败解释放在失败的工具响应内。
- `REQ-030`：summary reads 只包含 ids、titles、kinds、brief summaries、source metadata、currentness、readable flag、next action，不包含 foreign content。
- `REQ-031`：artifact writes 只能写 active-buddy-owned tasks；foreign artifacts 是 read sources，不是 write targets。
- `REQ-032`：write payload 在创建 revision 前验证；metadata updates 只改 owned artifact metadata。
- `REQ-033`：所有 collaboration-critical failure 包含 `ok`、`tool`、`action`、`active_buddy`、target id、`why`、`permission_boundary`、`relation`、`missing_preconditions`、`next_actions`、`command_hint`；artifact body withheld 时包含 `no_content_leak: true`。
- `REQ-034`：`next_actions[*].tool/action` 必须存在于 env tool registry；`command_hint` 必须使用 `python3 scripts/env/client.py ...`，不得指向 raw state files。
- `REQ-035`：AGENTS guidance 保持短：使用 env tool，不读写 raw state；看到 id 用 direct-id tools；没有 `artifact.get` full body 就不能声称已读内容。
- `REQ-036`：shared skills 教 workflow，不弥补工具层缺陷；source intake workflow 是 `track.get -> artifact.get`，缺关系时 `track.join -> artifact.get`。
- `REQ-037`：不添加 generic ACL engine、workflow router、event bus、DSL、plugin system、compatibility alias layer、hidden lifecycle mutation。
- `REQ-038`：测试先锁 normal contract 和 no-leak contract，再实现 summary/read/join/handoff/run/context cleanup。
- `REQ-039`：Dev source intake acceptance 不依赖任何 context-specific artifact read action。
- `REQ-040`：implementation 保持在 `.worktrees/dev2258`，不污染 main，不直接编辑 runtime raw state 作为恢复路径。

## 3. 现状探索摘要

### 需要查看的关键目录、文件、测试、运行命令

- `AGENTS.md`：SHARP 和 test-bound execution 规则。
- `README.md`：product runtime loop、`prepare`、`persist`、`env.tool` CLI 主路径。
- `docs/memo/2026-05-14-track-task-artifact-tooling-upgrade-proposal.md`：本任务源需求。
- `docs/memo/2026-05-13-cross-buddy-artifact-access-memo.md`：触发问题和当前 direct read gap。
- `scripts/env/tools/contracts.py`：tool/action registry、mutability、operation semantics、runtime context tool descriptions。
- `scripts/env/tools/router.py`：registry-backed envelope validation。
- `scripts/env/tools/dispatch.py`：tool/action 到 service function 的唯一 dispatch map。
- `scripts/env/tools/responses.py`：canonical response helper 和 structured next-action option builder。
- `scripts/env/client.py`：skill-facing CLI parser；需要新增/替换 `track join`、`artifact list --track-id`、`handoff list/create` 参数。
- `scripts/env_store.py`：tracks、tasks、artifacts、runs 的 object store；需要增加 handoff record store，并复用 current slot/index helper。
- `scripts/env/services/tracks.py`：当前 `track.list/get/attach_task/detach_task`；需要强化 summary、增加 `join`。
- `scripts/env/services/artifacts.py`：当前 `artifact.get` 只允许 active-buddy ownership；需要 relation-aware full read 和 track-scoped list。
- `scripts/env/services/tasks.py`：当前 `task.list/get` 只返回 active-buddy-owned task summary；需要 relation-aware task orientation。
- `scripts/env/services/handoffs.py`：当前只有 `validate`；需要 `list`、`create`、共享 validation。
- `scripts/env/services/runs.py`：当前 validate/commit 做 run audit；需要 handoff payload coherence、retired mutation feedback、no repair guarantee。
- `scripts/env/services/context.py`：candidate summaries、track context、recent handoff scan；需要保留 projection，删除/替换 direct artifact read wording。
- `scripts/env/services/bindings.py`：`binding.set_task` 写 `current_task_id/current_track_id`；`track.join` 应复用 `write_instance_binding`。
- `scripts/artifact_selection.py`：基于 `track_artifact_index` 的 current artifact selection；可保留为 prepare selection helper，不成为 direct read API。
- `buddyswitch/manifest.toml`：新增 `handoff-tool`、`run-tool` skill 时需要注册到 buddies。
- `buddyswitch/skills/shared/{track-tool,artifact-tool,task-tool}/SKILL.md`：更新 direct-id workflow。
- `tools/launcher/assets/buddies/{market,pm,design,dev,test}/AGENTS.md`：保持短规则并投影 direct-id guidance。
- `framework/docs/track-registry.md`：更新 track/task/artifact/handoff object rules 和 `track.join`。
- `framework/docs/turn-runtime-spec.md`：声明 context projection 与 direct artifact read API 的边界。
- `tests/test_track_env_tool.py`：track list/get/join behavior。
- `tests/test_artifact_env_tool.py`：artifact list/get/read rules/no-leak/write rules。
- `tests/test_task_env_tool.py`：task list/get orientation surface。
- `tests/test_context_binding_env_tool.py`：context role、binding behavior、handoff list/validate/create。
- `tests/test_run_env_tool.py` 和 `tests/test_run_env_services.py`：run validate/commit coherence。
- `tests/test_env_tool_response_contract.py`：canonical response and no-leak contract。
- `tests/test_env_tool_router.py`：registry/router/dispatch coverage。
- `tests/test_env_layer_end_to_end.py`：PM -> Design -> Dev -> Test direct artifact id acceptance。
- `tests/test_runtime_skills.py`：skill manifests and generated runtime skills.

探索命令：

```bash
rg -n "artifact\\.get|artifact\\.list|track\\.get|track\\.join|track\\.attach_task|context\\.get_track_artifacts|context\\.inspect_track_outputs|handoff\\.|run\\.validate_result|artifact.list_revisions|raw state|buddyswitch/objects" scripts tests buddyswitch tools framework docs -g '*.py' -g '*.md' -g '*.toml' -g '*.json'
python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_task_env_tool.py -q
python3 -m pytest -p no:cacheprovider tests/test_context_binding_env_tool.py tests/test_run_env_tool.py tests/test_env_tool_response_contract.py -q
```

### 保留、替换、删除、迁移

- 保留：broker-routed `env.tool -> router -> registry-backed dispatch -> service` 主路径。
- 保留：`tracks -> task_ids -> task.artifact_ids/artifact_slots -> artifacts` 数据模型；track 不直接拥有 artifact ids。
- 保留：active-buddy write boundary；artifact content writes 仍通过 `artifact.create_revision`，metadata writes 仍通过 `artifact.update_metadata`。
- 保留：`artifact.get_current` 作为 active-buddy current task owned-artifact convenience，因为它不是 cross-buddy source intake path。
- 保留：`track.attach_task` 和 `track.detach_task` 作为 explicit membership maintenance；normal source intake guidance 不再指向它们。
- 替换：`artifact.list` 的 normal semantics 从 current-task no-arg list 改为 `--track-id` summary list；current-task owned full reads 使用 `artifact.get_current` 或 `artifact.get --artifact-id`。
- 替换：`artifact.get` active-buddy-only scope，改为 owned-or-related-current-track read decision。
- 替换：`track.get` nested task-only summary，增加 top-level current artifact summary rows 和 row-level `readable_by_current_buddy` / `next_action`。
- 替换：`task.get` active-buddy-only lookup，改为 owned or relation-readable task orientation；仍不返回 artifact body。
- 新增：`track.join` action、CLI operation、contract、handler、tests。
- 新增：`handoff.list` 和 `handoff.create` action、CLI operation、contract、handler、tests。
- 新增：`buddyswitch/objects/handoffs/*.json` handoff records，补足 `handoff.create` 需要的 explicit persisted record；`handoff.list` 同时读取 dedicated records 和 existing run audit handoffs。
- 删除：tool feedback 和 skills 中“用 prepare/context 读取 upstream full artifact”作为 normal artifact body path 的指导。
- 删除：不存在的或被 proposal 拒绝的 context action guidance，包括 `context.get_track_artifacts`、`context.inspect_track_outputs`、`context.explain_track_access`、`context.validate_sources_available`。
- 删除：不存在 tool 的 command hint，例如 `artifact.list_revisions` 和 `track attach-task --payload`。
- 不迁移：既有 `buddyswitch/content/runs/*.json` 中的 embedded handoff audit 继续可被 `handoff.list` 读取；不批量改写历史 run audit。

## 4. 最终目标架构

### 文件结构和职责

- 新增 `scripts/env/services/track_relations.py`
  - 负责 relation 和 artifact readability 的小型确定性规则，不做 generic ACL engine。
  - 定义 `ArtifactReadDecision`、`TrackRelation` TypedDict。
  - 提供 `track_relation_for_buddy(track, active_buddy) -> dict[str, Any]`。
  - 提供 `artifact_track_association(artifact) -> dict[str, Any] | None`。
  - 提供 `artifact_read_decision(artifact, active_buddy) -> dict[str, Any]`。
  - 提供 `artifact_summary_row(artifact, active_buddy, track=None, task=None) -> dict[str, Any]`。
  - 提供 `current_artifact_rows_for_track(track_id, active_buddy) -> list[dict[str, Any]]`。
  - 提供 `command_hint(tool, action, args) -> str`，只生成 `python3 scripts/env/client.py ...` 命令。

- 修改 `scripts/env_store.py`
  - 新增 `HANDOFF_OBJECTS_DIR = OBJECTS_ROOT / "handoffs"`。
  - 新增 `VALID_HANDOFF_STATUS = ("active", "superseded", "archived")`。
  - 新增 `handoff_file(handoff_id)`、`validate_handoff_record(record)`、`list_handoffs()`、`get_handoff()`、`save_handoff()`、`create_handoff()`。
  - Handoff record fields：
    - `id`
    - `track_id`
    - `source_buddy`
    - `target_buddy`
    - `source_task_id`
    - `source_run_id`
    - `artifact_ids`
    - `historical_artifact_ids`
    - `reason`
    - `context`
    - `status`
    - `created_at`
    - `updated_at`

- 修改 `scripts/env/tools/contracts.py`
  - `track` actions 增加 `join`，payload fields `["track_id", "task_id"]`，mutates `runtime_objects` 和 `instance_binding`。由于当前 registry 只有单值 mutates，新增 `MUTATES_RUNTIME_OBJECTS_AND_INSTANCE_BINDING = "runtime_objects+instance_binding"`。
  - `artifact.list` payload fields 改为 `["track_id"]`，returns 改为 `["track_id", "relation", "artifacts", "current_binding"]`。
  - `task.list/get` returns 增加 current artifact summaries 和 relation。
  - `handoff` actions 增加 `list` 和 `create`。
  - `run.validate_result` returns 增加 `validated_handoff`、`retired_field_rejections` 的 contract wording。

- 修改 `scripts/env/tools/dispatch.py`
  - Add `track.join -> track_service.join_track_for_active_buddy`。
  - Add `handoff.list -> handoff_service.list_handoffs_for_active_buddy`。
  - Add `handoff.create -> handoff_service.create_handoff_for_active_buddy`。

- 修改 `scripts/env/client.py`
  - `track join --track-id <track-id> [--task-id <task-id>]`。
  - `artifact list --track-id <track-id>`；不带 `--track-id` 时 argparse exit 2。
  - `handoff list [--track-id <track-id>]`。
  - `handoff validate --payload <json>` 保留。
  - `handoff create --payload <json>`。
  - `run commit` 保持现有 `--context <json> --result <json>`，因为 commit by `--run-id` 无法表达 result payload；command hints 使用现有 CLI shape。

- 修改 `scripts/env/services/tracks.py`
  - Import `track_relations` and `bindings`.
  - `_artifact_decision_summary` 改为调用 `track_relations.artifact_summary_row`，输出 `artifact_id` 同时保留 `id` 一个 release cycle 内部测试可迁移字段不作为 user-facing command hint。
  - `_track_context_summary(track, active_buddy)` 增加 top-level `current_artifacts`，保留 `tasks[*].current_artifacts`。
  - `list_tracks_for_active_buddy` rows 增加 `active_buddy_relation`、`latest_handoff_summary`、`command_hint`。
  - `get_track_for_active_buddy` response 增加 `relation`、`current_artifacts`、`recent_handoffs`、`command_hint`。
  - 新增 `_active_buddy_tasks_for_track(track_id, active_buddy) -> list[dict[str, Any]]`，只返回 `status != "archived"` 的 tasks。
  - 新增 `_next_join_task_id(active_buddy, track_id) -> str`。
  - 新增 `join_track_for_active_buddy(args, context)`：
    - require `track.read`, `task.create`, `task.update` permissions。
    - validate `track_id` and optional `task_id`。
    - reject archived track with `permission_boundary="track.lifecycle_status"`。
    - if `task_id` provided, require task owned by active buddy, status not archived, track_id absent or equal target; attach if absent.
    - if no `task_id`, find active-buddy non-archived tasks already on track.
    - no existing task: create active task with title `Join <track title>` and summary `Joined track <track_id> for <active_buddy> work.`。
    - one existing task: reuse.
    - multiple existing tasks: reject with `permission_boundary="track.join_ambiguity"`, include each candidate `task_id`, command hint `python3 scripts/env/client.py track join --track-id <track-id> --task-id <task-id>`。
    - write instance binding through `binding_service.write_instance_binding(context=context, task_id=<id>, track_id=<track_id>)`。
    - return `created_task`, `current_task_selected`, `relation="participant"`, `readable_artifact_count`, `next_actions`, `command_hint`。

- 修改 `scripts/env/services/artifacts.py`
  - `_LIST_FIELDS = {"track_id"}`。
  - `_GET_FIELDS = {"artifact_id"}` 保留。
  - `_artifact_scope_error` 替换为 `_artifact_read_rejection(decision, ...)`，使用 source proposal 的 no-leak contract。
  - 新增 `list_artifacts_for_track(args, context)`，替换 dispatch 中 `list_artifacts_for_current_task` 的 `artifact.list` handler。
  - `get_artifact_for_active_buddy`：
    - resolve artifact id。
    - call `track_relations.artifact_read_decision`。
    - if `allowed == true` return full `artifact.content` and decision fields。
    - if rejected return top-level `no_content_leak: true` and never include summary/title/content of blocked artifact。
  - `validate_artifact_payload`、`create_artifact_revision`、`update_artifact_metadata` 保持 owned-write boundary，并更新 `allowed_next_actions`，避免 context read path。

- 修改 `scripts/env/services/tasks.py`
  - Import `track_relations`。
  - `_task_summary` 增加 `current_artifact_ids`、`current_artifacts` summary rows、`is_current_work`。
  - `_task_read_decision(task, active_buddy)`：
    - owned task allowed with relation `owner`。
    - task on track allowed if active buddy has reasonable track relation。
    - unrelated foreign task rejected with `permission_boundary="task.track_relation"`。
  - `list_tasks_for_active_buddy` 返回 active-buddy tasks 和 relation-readable track-linked tasks，dedupe by task id。
  - `get_task_for_active_buddy` 改名保持 handler name 兼容，但 behavior 变为 relation-aware `task.get`。
  - `task.get` response 不包含 artifact `content`，只返回 summary rows 和 `next_actions` 指向 `artifact.get`。

- 修改 `scripts/env/services/handoffs.py`
  - `_VALIDATE_FIELDS` 扩展为 `track_id`、`source_task_id`、`source_run_id`、`target_buddy`、`next_buddy`、`artifact_ids`、`historical_artifact_ids`、`reason`、`context`。
  - 新增 `_normalize_target_buddy(args)`：接受 `target_buddy`；为兼容 existing run payload，`next_buddy` 也接受并输出 `target_buddy` 和 `next_buddy`。
  - 新增 `_validate_handoff_payload(args, context, action, mutate)`，由 validate/create/run service 复用：
    - source task exists and `task.buddy == active_buddy`。
    - track exists。
    - source task `track_id` 等于 requested track 或在 create 时 attach 已存在 task relation。
    - every artifact id exists, belongs to source task, and owner buddy is active buddy。
    - non-current artifact id must appear in `historical_artifact_ids`。
    - target buddy exists in manifest。
    - reject payload fields `status`、`current_buddy`、`next_buddy_override`、`track_status`、`state_effects` as hidden lifecycle mutation.
  - 新增 `list_handoffs_for_active_buddy(args, context)`：
    - optional `track_id` filter。
    - merge `env_store.list_handoffs()` with `context_service.scan_track_recent_handoffs(track_id)` run audit rows。
    - output canonical rows with `handoff_id`, `track_id`, `source_buddy`, `target_buddy`, `source_task_id`, `source_run_id`, `artifact_ids`, `status`, `read_authorizes_active_buddy`。
  - 新增 `create_handoff_for_active_buddy(args, context)`：
    - validate payload。
    - create `handoff-<track-id>-<source-buddy>-to-<target-buddy>-<shortuuid>`。
    - return created handoff, no lifecycle mutation, next action `run.validate_result` or `artifact.get` for recipient.

- 修改 `scripts/env/services/runs.py`
  - Import `handoffs` validation helper.
  - `_reject_retired_persist_fields` command hints use existing target tools:
    - task changes: `python3 scripts/env/client.py task update --payload <json-file>`
    - track lifecycle: `python3 scripts/env/client.py track update --payload <json-file>` or `track advance`
    - joining: `python3 scripts/env/client.py track join --track-id <track-id>`
    - artifact content: `python3 scripts/env/client.py artifact create-revision --payload <json-file>`
  - `_validate_association_metadata` artifact not found action changes from nonexistent `artifact.list_revisions` to `artifact.list --track-id <track-id>` when track id is known, or `task.get --task-id <task-id>` when only task is known.
  - `_normalize_commit` validates `result.handoff` with handoff helper, including `artifact_ids` and `source_run_id` coherence.
  - `validate_run_result` returns `durable_signals.validated_handoff` with `target_buddy`, `artifact_ids`, `source_task_id`。
  - `commit_buddy_run` still writes one run audit and does not create task/track/artifact/handoff repairs.

- 修改 `scripts/env/services/context.py`
  - `scan_track_recent_handoffs` remains for run audit handoffs; add a sibling `scan_track_handoff_records(track_id, limit)` or delegate to `handoff_service`.
  - `current_context_summary` may show candidate artifact summaries but never declares context as artifact body read API。
  - Remove guidance strings that suggest context-specific artifact read actions.

- 修改 `buddyswitch/skills/shared/track-tool/SKILL.md`
  - Common operations lead with `list`、`get --track-id`、`join --track-id`。
  - Explain that `attach-task` and `detach-task` are maintenance operations, not normal source intake.

- 修改 `buddyswitch/skills/shared/artifact-tool/SKILL.md`
  - State full body read entry point: `artifact get --artifact-id`。
  - State track summaries: `artifact list --track-id`。
  - Explain no-leak rejection fields and `track.join` recovery.
  - Remove "Use upstream artifacts from prepare context" as normal full read path.

- 修改 `buddyswitch/skills/shared/task-tool/SKILL.md`
  - State visible task id path: `task get --task-id`。
  - State task artifact rows are summaries and full bodies require `artifact.get`。

- 新增 `buddyswitch/skills/shared/handoff-tool/SKILL.md`
  - Commands: `handoff list --track-id`、`handoff validate --payload`、`handoff create --payload`。
  - Explain validation fields and no hidden lifecycle mutation.

- 新增 `buddyswitch/skills/shared/run-tool/SKILL.md`
  - Commands: `run validate-result --context --result`、`run commit --context --result`。
  - Explain validate before commit and no repair behavior.

- 修改 `buddyswitch/manifest.toml`
  - Add shared skills `handoff-tool` and `run-tool`。
  - Add both skills to PM、Market、Design、Dev、Test buddy skill lists.

- 修改 `tools/launcher/assets/buddies/{market,pm,design,dev,test}/AGENTS.md`
  - Add exact direct-id rules:
    - `If you see a track_id, use track.get.`
    - `If you see a task_id, use task.get.`
    - `If you see an artifact_id, use artifact.get.`
    - `Do not claim artifact content was read unless artifact.get returned the full body for that artifact id.`
  - Keep raw state prohibition.

- 修改 `framework/docs/track-registry.md`
  - Add handoff object source of truth.
  - Add `track.join` normal membership path.
  - Add relation-aware `artifact.get` current artifact rule.

- 修改 `framework/docs/turn-runtime-spec.md`
  - State context is projection and summary convenience; direct body read API is `artifact.get`。

### 核心调用流

正常 source intake：

1. `track.list` returns candidate tracks with command hint `track get --track-id <id>`。
2. `track.get` returns current artifact rows with artifact ids and `readable_by_current_buddy`。
3. If row is readable, user calls `artifact.get --artifact-id <id>` and receives full `artifact.content`。
4. If row is not readable, `artifact.get` rejects with `no_content_leak: true` and command hint `track join --track-id <id>` or `handoff list --track-id <id>`。
5. `track.join` creates/reuses/selects active-buddy task without lifecycle mutation。
6. Same `artifact.get` now succeeds for current track artifacts.

Run handoff coherence:

1. Producer writes owned artifact through `artifact.create_revision`。
2. Producer validates handoff through `handoff.validate` or creates explicit record through `handoff.create`。
3. Producer runs `run.validate-result --context --result`。
4. `run.commit` writes audit only; it does not create missing task, attach track, repair permissions, or advance lifecycle.

## 5. 分阶段实施计划

### 阶段一：锁定 contract、relation helper、no-leak baseline

目标：先用 failing tests 锁定 direct-id response shape、relation names、no-leak contract、registry actions，避免后面只修 happy path。

具体文件变更：

- Create `scripts/env/services/track_relations.py`。
- Modify `scripts/env/tools/contracts.py`。
- Modify `tests/test_env_tool_router.py`。
- Modify `tests/test_env_tool_response_contract.py`。
- Modify `tests/test_artifact_env_tool.py`。

详细步骤：

1. 在 `tests/test_env_tool_router.py::EnvToolRouterTests::test_dispatch_handler_coverage_matches_registry_actions` 的 expected registry behavior 中加入 `track.join`、`handoff.list`、`handoff.create`，并断言不存在 `context.get_track_artifacts`、`context.inspect_track_outputs`、`context.explain_track_access`、`context.validate_sources_available`、任意 `explain_` action。
2. 在 `tests/test_env_tool_response_contract.py` 新增 `test_collaboration_critical_rejections_include_no_leak_recovery_fields`：
   - seed PM track、PM task、PM artifact with content `{"secret": "full body must not appear"}`。
   - active buddy `dev` 未 join。
   - dispatch `artifact.get`。
   - assert fields `ok=false`、`tool="artifact"`、`action="artifact.get"`、`active_buddy="dev"`、`artifact_id`、`why`、`permission_boundary`、`relation`、`missing_preconditions`、`next_actions`、`command_hint`、`no_content_leak is True`。
   - assert serialized response 不包含 `full body must not appear`、`content`、`preview`、`buddyswitch/objects`。
3. 在 `tests/test_env_tool_response_contract.py` 新增 `test_next_actions_reference_registered_tools_and_command_hints_use_env_client`：
   - collect target action responses from blocked `artifact.get`、ambiguous `track.join`、invalid `handoff.validate`、invalid `run.validate_result`。
   - assert every `next_actions[*].tool/action` exists in `contracts.get_action_spec`。
   - assert every `command_hint` starts with `python3 scripts/env/client.py ` and does not contain `buddyswitch/objects`、`buddyswitch/content/runs`、`runs/raw`。
4. 在 `tests/test_artifact_env_tool.py` 新增 helper `_seed_track_with_pm_and_design_current_artifacts()`，返回 `track_id`、PM artifact id、Design artifact id、unrelated artifact id。
5. Create `scripts/env/services/track_relations.py` with pure read functions listed in architecture. Initial implementation can return existing active-buddy owner decisions and blocked relation decisions, enough for no-leak tests to fail on service wiring rather than missing import.
6. Update `scripts/env/tools/contracts.py` registry entries for new actions and payload fields.
7. Update `scripts/env/tools/dispatch.py` with placeholder handler references only after service functions exist in their service modules during later phases; before that router coverage test should fail, proving missing handlers.

预期行为变化：

- Tests describe the final tool registry and no-leak response contract before behavior is implemented.
- No product behavior is claimed complete in this phase.

对应需求编号：`REQ-001`、`REQ-002`、`REQ-016`、`REQ-017`、`REQ-018`、`REQ-029`、`REQ-033`、`REQ-034`、`REQ-038`、`REQ-040`

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py::EnvToolRouterTests::test_dispatch_handler_coverage_matches_registry_actions tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_collaboration_critical_rejections_include_no_leak_recovery_fields -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_artifact_get_rejects_unrelated_foreign_artifact_with_no_content_leak_contract -q
```

阶段完成标准：

- New tests fail for missing `track.join`/`handoff.list`/`handoff.create` handlers and missing no-leak fields.
- `track_relations.py` imports cleanly with no runtime writes.

### 阶段二：实现 track 和 artifact summary surfaces

目标：让 discovery 自然导向 artifact ids，并且 summary surfaces 不泄漏 foreign full content。

具体文件变更：

- Modify `scripts/env/services/track_relations.py`。
- Modify `scripts/env/services/tracks.py`。
- Modify `scripts/env/services/artifacts.py`。
- Modify `scripts/env/client.py`。
- Modify `tests/test_track_env_tool.py`。
- Modify `tests/test_artifact_env_tool.py`。

详细步骤：

1. 在 `tests/test_track_env_tool.py` 新增 `test_track_get_returns_current_artifact_rows_with_readability_and_next_actions`：
   - seed track with PM PRD and Design handoff current artifacts。
   - active buddy `dev` has no task, `track.current_buddy="pm"`, `track.next_buddy="dev"`。
   - assert `track.get` response contains `current_artifacts` rows for both artifacts。
   - each row contains `artifact_id`、`kind`、`title`、`summary`、`source_buddy`、`source_task_id`、`source_run_id`、`revision`、`currentness="current"`、`readable_by_current_buddy`、`next_action`。
   - assert no row contains `content`。
2. 在 `tests/test_artifact_env_tool.py` 新增 `test_artifact_list_by_track_returns_summary_rows_without_content`：
   - call `artifact.list` with `{"track_id": track_id}`。
   - assert same artifact ids and readability flags as `track.get`。
   - assert serialized payload does not contain seeded body strings。
3. 在 `tests/test_artifact_env_tool.py` 修改 existing `test_list_get_and_get_current_are_scoped_to_active_current_task`：
   - current-task no-arg `artifact.list` assertion 改为 expect payload error from CLI/service。
   - keep `artifact.get_current` assertion for active-buddy current task owned full read。
4. In `scripts/env/client.py`:
   - change `artifact list` parser to require `--track-id`。
   - `_artifact_args_from_cli` returns `{"track_id": ...}` for operation `list`。
5. In `scripts/env/services/artifacts.py`:
   - replace `list_artifacts_for_current_task` dispatch target behavior with `list_artifacts_for_track`。
   - validate `track_id` using `env_store.require_id`。
   - resolve track; missing track returns `permission_boundary="track.lookup"` with command hint `track list`。
   - rows come from `track_relations.current_artifact_rows_for_track(track_id, active_buddy)`。
   - response includes `track_id`、`relation`、`artifacts`、`current_binding`、`command_hint`。
6. In `scripts/env/services/tracks.py`:
   - pass `active_buddy` into `_track_context_summary`。
   - top-level response includes `relation` from `track_relations.track_relation_for_buddy`。
   - response includes `current_artifacts` from relation helper。
   - `allowed_next_actions` and `command_hint` lead to `artifact.get` or `track.join`。
7. Update `scripts/env/tools/contracts.py` `artifact.list` payload fields and returns.

预期行为变化：

- `track.get` and `artifact.list --track-id` return artifact ids, readable flags, source metadata and next action hints.
- Neither surface returns foreign full content.
- `artifact.list` no longer silently means current-task list; current-task owned reads remain through `artifact.get_current` and `artifact.get`.

对应需求编号：`REQ-003`、`REQ-004`、`REQ-005`、`REQ-009`、`REQ-010`、`REQ-019`、`REQ-030`、`REQ-034`

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py::TrackManagerEnvToolTests::test_track_get_returns_current_artifact_rows_with_readability_and_next_actions -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_artifact_list_by_track_returns_summary_rows_without_content -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py tests/test_artifact_env_tool.py -q
```

阶段完成标准：

- Track and artifact summary tests pass.
- No response from `track.get` or `artifact.list --track-id` contains `content` for foreign artifacts.
- CLI help for `artifact list` shows required `--track-id`。

### 阶段三：实现 relation-aware `artifact.get`

目标：让 `artifact.get --artifact-id` 成为合法 full-content 读取入口，并在不合法时返回同工具 no-leak recovery。

具体文件变更：

- Modify `scripts/env/services/track_relations.py`。
- Modify `scripts/env/services/artifacts.py`。
- Modify `tests/test_artifact_env_tool.py`。
- Modify `tests/test_env_tool_response_contract.py`。

详细步骤：

1. 在 `tests/test_artifact_env_tool.py` 新增 `test_artifact_get_allows_owned_artifacts_including_historical_revision`：
   - seed Dev task with two revisions。
   - call `artifact.get` for current and superseded Dev artifact。
   - assert both return `content` and `relation="owner"`。
2. 新增 `test_artifact_get_allows_current_track_artifact_for_each_reasonable_relation`：
   - subtests:
     - PM active buddy reads current track artifact with `relation="pm_lifecycle_owner"`。
     - Dev participant task on track reads PM PRD with `relation="participant"`。
     - Design reads when `track.current_buddy="design"`。
     - Test reads when `track.next_buddy="test"`。
     - Dev reads after latest handoff record targets Dev。
   - assert full seeded content returned only for current artifacts。
3. 新增 `test_artifact_get_rejects_stale_foreign_artifact_even_when_participant`：
   - seed PM artifact revision 1 superseded by revision 2。
   - Dev participant calls `artifact.get` on revision 1。
   - assert `ok=false`、`permission_boundary="artifact.currentness"`、`no_content_leak=true`。
4. 新增 `test_artifact_get_rejects_archived_track_relation_without_content`：
   - archived track with Dev participant task and PM artifact。
   - assert reject boundary `track.lifecycle_status` and no content string.
5. In `track_relations.artifact_read_decision`:
   - resolve owner task。
   - allow owner task immediately。
   - resolve track through owner task `track_id` and verify track contains source task id。
   - require `artifact.is_current is True` for foreign track reads。
   - reject archived track。
   - compute relation priority in order: PM, participant, current buddy, next buddy, latest handoff recipient。
   - return one relation string and detected reasons.
6. In `artifacts.get_artifact_for_active_buddy`:
   - remove `_owned_artifact` as read gate for `artifact.get`。
   - use `_required_artifact_id` for parsing and lookup。
   - apply relation decision。
   - success includes full `artifact` with `content`、`relation`、`readable_by_current_buddy=true`、`command_hint`。
   - rejection includes no `artifact` object and no summary/title/content.
7. Keep `_owned_artifact` for `update_metadata` and write paths only; rename to `_owned_artifact_for_write` to prevent accidental read reuse.

预期行为变化：

- Legal direct artifact id read succeeds without context-specific action.
- Illegal direct artifact id read gives actionable no-leak feedback from `artifact.get` itself.
- Foreign historical browsing remains blocked.

对应需求编号：`REQ-001`、`REQ-011`、`REQ-012`、`REQ-013`、`REQ-014`、`REQ-015`、`REQ-016`、`REQ-017`、`REQ-018`、`REQ-029`、`REQ-033`

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_artifact_get_allows_current_track_artifact_for_each_reasonable_relation -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_artifact_get_rejects_stale_foreign_artifact_even_when_participant tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_artifact_get_rejects_archived_track_relation_without_content -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_artifact_env_tool.py tests/test_env_tool_response_contract.py -q
```

阶段完成标准：

- All relation subtests pass.
- No rejected artifact body read serializes blocked content, title, summary, preview, raw path, or partial body.

### 阶段四：实现 `track.join` 并替换内部准备序列的 normal path

目标：把 create/attach/bind 的多步内部知识替换为普通 `track.join`，并保持 lifecycle fields 不变。

具体文件变更：

- Modify `scripts/env/services/tracks.py`。
- Modify `scripts/env/client.py`。
- Modify `scripts/env/tools/contracts.py`。
- Modify `scripts/env/tools/dispatch.py`。
- Modify `tests/test_track_env_tool.py`。
- Modify `tests/test_artifact_env_tool.py`。

详细步骤：

1. 在 `tests/test_track_env_tool.py` 新增 `test_track_join_creates_attaches_and_selects_active_buddy_task_without_lifecycle_mutation`：
   - snapshot track before join。
   - Dev calls `track.join` on track with PM current fields。
   - assert new task belongs to Dev, `task.track_id == track_id`。
   - assert instance json has `current_task_id` and `current_track_id`。
   - assert track `status/current_buddy/next_buddy/title/summary` unchanged except `task_ids` and `updated_at`。
2. 新增 `test_track_join_reuses_single_existing_active_buddy_task_idempotently`：
   - seed Dev task already attached。
   - call join twice。
   - assert same task id returned, `created_task=false`, no duplicate task id in track。
3. 新增 `test_track_join_rejects_multiple_existing_active_buddy_tasks_with_explicit_task_recovery`：
   - seed two Dev non-archived tasks on track。
   - call join without `task_id`。
   - assert reject, candidate task ids, command hint with `--task-id`。
   - call join with one task id and assert selected.
4. 新增 `test_track_join_rejects_foreign_or_other_track_task_without_mutation`：
   - `task_id` owned by PM rejects `task.buddy_scope`。
   - Dev task bound to different track rejects `track.task_linkage`。
   - snapshots unchanged.
5. In `scripts/env/client.py`:
   - add parser for `track join` with required `--track-id` and optional `--task-id`。
   - `_track_args_from_cli` handles operation `join`。
6. In `scripts/env/services/tracks.py` implement `join_track_for_active_buddy` exactly as architecture describes.
7. In `scripts/env/tools/contracts.py` and dispatch add `join` action.
8. In `tests/test_artifact_env_tool.py` add `test_track_join_then_artifact_get_reads_pm_and_design_sources`:
   - Dev initially blocked reading PM/design artifacts。
   - Dev calls `track.join`。
   - Dev calls `artifact.get` for same artifact ids and receives full content.

预期行为变化：

- Dev can move from visible track id to active relation with one normal command.
- `track.join` success makes subsequent `artifact.get` succeed for current track artifacts.
- Ambiguous existing work rejects before mutation.

对应需求编号：`REQ-006`、`REQ-007`、`REQ-008`、`REQ-013`、`REQ-018`、`REQ-031`、`REQ-036`

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py::TrackManagerEnvToolTests::test_track_join_creates_attaches_and_selects_active_buddy_task_without_lifecycle_mutation tests/test_track_env_tool.py::TrackManagerEnvToolTests::test_track_join_reuses_single_existing_active_buddy_task_idempotently -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py::TrackManagerEnvToolTests::test_track_join_rejects_multiple_existing_active_buddy_tasks_with_explicit_task_recovery tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_track_join_then_artifact_get_reads_pm_and_design_sources -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py tests/test_artifact_env_tool.py -q
```

阶段完成标准：

- `track.join` tests pass.
- Lifecycle field snapshots prove no hidden PM lifecycle mutation.
- Direct read loop `track.get -> track.join -> artifact.get` works without `context.get`。

### 阶段五：实现 task orientation、handoff list/create、run coherence

目标：让 visible task ids、handoff records、run validation 都遵守 direct-id 和 explicit-audit model。

具体文件变更：

- Modify `scripts/env/services/tasks.py`。
- Modify `scripts/env/services/handoffs.py`。
- Modify `scripts/env/services/runs.py`。
- Modify `scripts/env_store.py`。
- Modify `scripts/env/client.py`。
- Modify `scripts/env/tools/contracts.py`。
- Modify `scripts/env/tools/dispatch.py`。
- Modify `tests/test_task_env_tool.py`。
- Modify `tests/test_context_binding_env_tool.py`。
- Modify `tests/test_run_env_tool.py`。
- Modify `tests/test_run_env_services.py`。

详细步骤：

1. 在 `tests/test_task_env_tool.py` 新增 `test_task_list_includes_owned_and_relation_readable_track_tasks_with_current_artifact_ids`：
   - seed PM task, Design task, Dev task on same track。
   - Dev participant lists tasks。
   - assert PM/Design/Dev tasks included; unrelated PM task excluded。
   - rows include `task_id`、`track_id`、`owner_buddy`、`status`、`current_artifact_ids`、`is_current_work`。
2. 新增 `test_task_get_returns_artifact_summaries_and_points_to_artifact_get_without_body`：
   - Dev calls `task.get` on PM task in related track。
   - assert current artifact summaries include `artifact_id` and `readable_by_current_buddy`。
   - assert no `content`。
   - assert next action points to `artifact.get`。
3. In `scripts/env/services/tasks.py` implement relation-aware list/get described in architecture.
4. In `env_store.py` implement handoff record store and validation.
5. In `tests/test_context_binding_env_tool.py` add `test_handoff_list_merges_explicit_records_and_run_audit_handoffs`：
   - seed one explicit handoff record and one run audit handoff for same track。
   - call `handoff.list --track-id` as recipient and unrelated buddy。
   - assert rows include source/target ids, artifact ids, status, `read_authorizes_active_buddy` true only for recipient.
6. Add `test_handoff_create_validates_owned_sources_and_does_not_mutate_track_lifecycle`：
   - active Design has source task and design artifact。
   - create handoff to Dev。
   - assert record exists under `buddyswitch/objects/handoffs` in runtime root。
   - assert track lifecycle fields unchanged。
7. Add `test_handoff_validate_rejects_foreign_source_artifact_non_current_without_historical_flag_and_hidden_lifecycle_fields`：
   - source artifact owned by PM rejects。
   - superseded owned artifact not in `historical_artifact_ids` rejects。
   - payload with `track_status` rejects.
8. In `scripts/env/services/handoffs.py` implement list/create/shared validation.
9. In `scripts/env/client.py` add handoff `list` and `create` parsers.
10. In `tests/test_run_env_tool.py` add `test_run_validate_result_rejects_invalid_handoff_ids_and_retired_mutation_fields`：
    - invalid track id, task id, artifact id, target buddy, foreign artifact, non-current artifact without historical marker, `state_effects`, embedded `artifacts` all reject with specific boundaries.
11. In `tests/test_run_env_tool.py` add `test_run_commit_does_not_repair_missing_join_or_handoff_relation`：
    - result references valid owned artifact but missing task-track relation; validate/commit rejects rather than attaching task.
12. In `scripts/env/services/runs.py` wire handoff validation and update retired hints.

预期行为变化：

- `task.list/get` become useful orientation tools without becoming body readers.
- Handoffs can be listed and explicitly created.
- Run validation catches incoherent ids and hidden mutation attempts before audit commit.

对应需求编号：`REQ-019`、`REQ-020`、`REQ-021`、`REQ-022`、`REQ-023`、`REQ-024`、`REQ-025`、`REQ-026`、`REQ-031`、`REQ-032`、`REQ-033`、`REQ-034`

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py::TaskManagerEnvToolTests::test_task_list_includes_owned_and_relation_readable_track_tasks_with_current_artifact_ids tests/test_task_env_tool.py::TaskManagerEnvToolTests::test_task_get_returns_artifact_summaries_and_points_to_artifact_get_without_body -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_handoff_list_merges_explicit_records_and_run_audit_handoffs tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_handoff_create_validates_owned_sources_and_does_not_mutate_track_lifecycle -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_run_env_tool.py::RunManagerEnvToolTests::test_run_validate_result_rejects_invalid_handoff_ids_and_retired_mutation_fields tests/test_run_env_tool.py::RunManagerEnvToolTests::test_run_commit_does_not_repair_missing_join_or_handoff_relation -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_context_binding_env_tool.py tests/test_run_env_tool.py tests/test_run_env_services.py -q
```

阶段完成标准：

- Task, handoff, run focused tests pass.
- `handoff.create` writes only handoff object records.
- `run.commit` writes only run audit and never repairs task/track/artifact/handoff state.

### 阶段六：清理 context-centric guidance、skills、AGENTS、docs，并跑端到端验收

目标：把正常协作说明收敛到 direct-id tools，证明 Dev/Test 不需要 context artifact read action 即可读取 upstream source。

具体文件变更：

- Modify `scripts/env/services/context.py`。
- Modify `buddyswitch/skills/shared/track-tool/SKILL.md`。
- Modify `buddyswitch/skills/shared/artifact-tool/SKILL.md`。
- Modify `buddyswitch/skills/shared/task-tool/SKILL.md`。
- Create `buddyswitch/skills/shared/handoff-tool/SKILL.md`。
- Create `buddyswitch/skills/shared/run-tool/SKILL.md`。
- Modify `buddyswitch/manifest.toml`。
- Modify `tools/launcher/assets/buddies/{market,pm,design,dev,test}/AGENTS.md`。
- Modify `framework/docs/track-registry.md`。
- Modify `framework/docs/turn-runtime-spec.md`。
- Modify `tests/test_env_layer_end_to_end.py`。
- Modify `tests/test_runtime_skills.py`。
- Modify `tests/test_repo_consistency.py` if existing consistency scans need direct-id forbidden-token checks.

详细步骤：

1. In `scripts/env/services/context.py` replace allowed-next-action strings that imply upstream full artifact reading through context with:
   - `Use track.get to inspect artifact ids.`
   - `Use artifact.get --artifact-id <artifact-id> for full body reads.`
   - `Use track.join --track-id <track-id> when relation is missing.`
2. Add `tests/test_context_binding_env_tool.py::test_context_feedback_points_to_direct_artifact_tools_not_context_read_actions`:
   - dispatch context summary/get in unbound and bound cases。
   - assert serialized responses do not contain `context.get_track_artifacts`、`context.inspect_track_outputs`、`context.explain_track_access`、`context.validate_sources_available`。
   - assert responses contain `track.get` or `artifact.get` where artifact source intake is referenced.
3. Update shared skills exactly as architecture section lists.
4. Create handoff/run shared skills with concise command contracts and verification notes.
5. Update manifest skill entries and all buddy skill lists.
6. Update buddy AGENTS templates with the four direct-id lines and keep raw state prohibition.
7. Add `tests/test_runtime_skills.py::RuntimeSkillsTests::test_shared_tool_skills_project_direct_id_guidance`:
   - materialize runtime skills.
   - assert track/artifact/task/handoff/run skills exist.
   - assert artifact skill contains `artifact get --artifact-id` and does not contain forbidden context read actions.
8. Add `tests/test_repo_consistency.py::RepoConsistencyTests::test_no_context_artifact_read_actions_or_raw_state_recovery_guidance`:
   - scan `scripts`, `buddyswitch/skills`, `tools/launcher/assets/buddies`, `framework/docs` for forbidden strings.
   - allow source memo files under `docs/memo` and historical specs under `docs/spec` by excluding `docs`.
9. In `tests/test_env_layer_end_to_end.py` add `test_pm_design_dev_test_direct_artifact_id_source_intake_without_context_read_action`:
   - PM creates track and PRD artifact。
   - Design reads PRD via `artifact.get`, creates design handoff artifact and `handoff.create` to Dev。
   - Dev starts unjoined, uses `track.get`, sees PM and Design artifact ids, receives no-leak rejection for missing relation if applicable, calls `track.join`, then reads both artifacts via `artifact.get`。
   - Dev creates implementation artifact and `handoff.create` to Test。
   - Test uses `track.get` and `artifact.get` direct ids to read Dev output and upstream PM/Design sources。
   - Assert `self.env_tool_calls` contains no `("context", <artifact-read-action>)` and no context tool call is required for source full body.
10. Update docs `framework/docs/track-registry.md` and `framework/docs/turn-runtime-spec.md` with final tool/data boundary.

预期行为变化：

- Product-facing guidance teaches direct-id env tool usage.
- Context remains useful but is not required for visible artifact id full reads.
- End-to-end collaboration proves PM/Design/Dev/Test direct source intake.

对应需求编号：`REQ-027`、`REQ-028`、`REQ-035`、`REQ-036`、`REQ-037`、`REQ-039`、`REQ-040`

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_feedback_points_to_direct_artifact_tools_not_context_read_actions -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py::RuntimeSkillsTests::test_shared_tool_skills_project_direct_id_guidance -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_layer_end_to_end.py::EnvLayerEndToEndTests::test_pm_design_dev_test_direct_artifact_id_source_intake_without_context_read_action -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
```

阶段完成标准：

- Skills and AGENTS direct-id projection tests pass.
- E2E acceptance passes without context-specific artifact body read action.
- Repository consistency scan finds no forbidden context artifact read guidance outside memo/spec archives.

## 6. 迁移 / 删除策略

- 直接替换 `artifact.list` no-arg current-task semantics with `artifact.list --track-id`。真实原因：proposal 的 normal artifact inspection path 是 track outputs by id；current-task owned current reads 已由 `artifact.get_current` 覆盖，不需要两个 list meanings。退出条件：无；这是目标行为。
- 保留 `artifact.get_current`。真实原因：它读取 active-buddy current task owned artifact revisions，不是 cross-buddy source intake path，也不违反 direct-id rule。
- 保留 `track.attach_task` 和 `track.detach_task`。真实原因：它们是明确 membership maintenance，不是 `track.join` 兼容 alias；技能和 AGENTS 不把它们作为 normal source intake。
- 新增 `buddyswitch/objects/handoffs/*.json`。真实原因：`handoff.create` 要创建显式 handoff record，而现有 run audit handoff 只能由 `run.commit` 产生。`handoff.list` 读取 dedicated records 和历史 run audit handoffs，因为 run audit 是已有真实 persisted data。
- 不批量迁移旧 run audit handoffs。真实原因：已有 run audit 是 audit source；复制会产生重复 truth。`handoff.list` 在展示层 merge，并用 `source_type` 标记 `handoff_record` 或 `run_audit`。
- 删除 guidance，不删除 prepare context projection。真实原因：context projection 仍服务 turn preparation；被删除的是把 context 当 direct artifact body read chain 的说明和 rejected actions。
- 不添加 compatibility aliases：不实现 `context.get_track_artifacts`、`context.inspect_track_outputs`、`context.explain_track_access`、`context.validate_sources_available`、`task.create_for_track`、normal-path `explain_*`。
- 不推荐 raw state recovery。所有 command hints 使用 `python3 scripts/env/client.py ...`。

## 7. 完成定义

整个任务完成必须同时满足：

- `track.list -> track.get -> artifact.get` 能读取合法 visible artifact id 的 full body。
- 缺关系时 `artifact.get` 无泄漏拒绝，并指向 `track.join` 或 `handoff.list`。
- `track.join` 创建/复用/选择 active-buddy task，不修改 PM lifecycle fields，并能让后续 `artifact.get` 读取 current track artifacts。
- `artifact.list --track-id`、`track.get`、`task.get` 返回 summary rows 和 next actions，不返回 foreign content。
- `task.list/get`、`handoff.list/validate/create`、`run.validate_result/commit` 满足对应 contract。
- Context、skills、AGENTS、framework docs 不把 context-specific artifact read action 作为 normal source intake。
- Contract tests、focused service tests、E2E direct source intake test、runtime skill projection tests、repo consistency tests 全部通过。
- Broader verification 通过：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_task_env_tool.py tests/test_context_binding_env_tool.py tests/test_run_env_tool.py tests/test_run_env_services.py tests/test_env_tool_response_contract.py tests/test_env_tool_router.py tests/test_env_layer_end_to_end.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

- `git status --short` 只显示 dev2258 worktree 中本任务代码、测试、docs、skills、AGENTS changes；main worktree 未被修改。
