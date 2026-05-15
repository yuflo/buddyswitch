# Runless Buddy Output Rebuild Test Plan

## 1. 测试设计原则

- Tests start from user-visible workflow and product invariants: explicit product object writes, no durable execution history, no instance current-work state, no run-based provenance.
- Tests verify observable behavior: env.tool JSON response, CLI stdout JSON, object files, buddybox files, workspace projection JSON, console DOM assumptions, launcher config output, repo guidance text.
- Tests do not assert private implementation shape unless the source memo names that path as a deletion or storage contract.
- Tests must fail if implementation only hides old fields from one response while old services, CLI resources, docs, schemas, or storage paths remain active.
- Tests cover success, rejection, duplicate operations, path traversal, cross-buddy access, empty runtime state, malformed stored records, and residue scans.
- Tests verify structured response semantics: `state_changed`, `durability`, `permission_boundary`, `why_blocked`, `impact`, `retryable`, `retry_guidance`, `allowed_next_actions`.
- Tests treat docs, skills, and AGENTS as active product surfaces because buddies learn runtime behavior from those files.

## 2. 需求覆盖矩阵

| Requirement | Test coverage |
| --- | --- |
| `REQ-001` | `RLC-CONTRACT-001`, `RLC-E2E-001`, `RLC-REG-001` |
| `REQ-002` | `RLC-BROKER-001`, `RLC-BROKER-002`, `RLC-CTX-001` |
| `REQ-003` | `RLC-CONTRACT-002`, `RLC-LAUNCH-001` |
| `REQ-004` | `RLC-CTX-001`, `RLC-REGISTRY-001`, `RLC-E2E-003` |
| `REQ-005` | `RLC-TRACK-001`, `RLC-E2E-003` |
| `REQ-006` | `RLC-STORE-001`, `RLC-TASK-001`, `RLC-NEG-002` |
| `REQ-007` | `RLC-STORE-002`, `RLC-ART-001`, `RLC-SRCREF-001` |
| `REQ-008` | `RLC-ART-002`, `RLC-NEG-003` |
| `REQ-009` | `RLC-ART-003`, `RLC-NEG-001` |
| `REQ-010` | `RLC-HANDOFF-001`, `RLC-HANDOFF-002`, `RLC-SRCREF-001` |
| `REQ-011` | `RLC-MEM-001`, `RLC-MEM-004`, `RLC-E2E-005` |
| `REQ-012` | `RLC-MEM-001`, `RLC-PROJ-001` |
| `REQ-013` | `RLC-MEM-002`, `RLC-NEG-005` |
| `REQ-014` | `RLC-MEM-001`, `RLC-MEM-003`, `RLC-CLI-002` |
| `REQ-015` | `RLC-BOX-001`, `RLC-BOX-004`, `RLC-LAUNCH-002` |
| `REQ-016` | `RLC-BOX-001`, `RLC-BOX-002`, `RLC-NEG-006`, `RLC-CLI-003` |
| `REQ-017` | `RLC-BROKER-001`, `RLC-E2E-001`, `RLC-REG-001` |
| `REQ-018` | `RLC-E2E-002`, `RLC-ART-002` |
| `REQ-019` | `RLC-REGISTRY-001`, `RLC-CLI-001` |
| `REQ-020` | `RLC-REGISTRY-001`, `RLC-CLI-001`, `RLC-NEG-004` |
| `REQ-021` | `RLC-CTX-001`, `RLC-BROKER-001`, `RLC-REG-001` |
| `REQ-022` | `RLC-BROKER-001`, `RLC-BROKER-003` |
| `REQ-023` | `RLC-REG-002`, `RLC-REG-003` |
| `REQ-024` | `RLC-CONTRACT-003`, `RLC-LAUNCH-002`, `RLC-CLEAN-001` |
| `REQ-025` | `RLC-PROJ-001`, `RLC-CONSOLE-001`, `RLC-CLEAN-001` |
| `REQ-026` | `RLC-TASK-002`, `RLC-TRACK-002` |
| `REQ-027` | `RLC-ART-004` |
| `REQ-028` | `RLC-EVID-001`, `RLC-EVID-002`, `RLC-MARKET-001` |
| `REQ-029` | `RLC-LAUNCH-002`, `RLC-PROFILE-001`, `RLC-SANDBOX-001` |
| `REQ-030` | `RLC-SRCREF-001`, `RLC-SRCREF-002`, `RLC-NEG-007` |
| `REQ-031` | `RLC-SRCREF-003`, `RLC-NEG-008` |
| `REQ-032` | `RLC-SEM-001`, `RLC-SEM-002` |
| `REQ-033` | `RLC-RESP-001`, `RLC-RESP-002`, `RLC-RESP-003` |
| `REQ-034` | `RLC-MEM-003`, `RLC-BOX-003`, `RLC-REG-004` |
| `REQ-035` | `RLC-REG-005`, `RLC-MEM-001`, `RLC-BOX-001` |
| `REQ-036` | `RLC-CTX-001`, `RLC-CTX-002`, `RLC-E2E-005` |
| `REQ-037` | `RLC-PROJ-001`, `RLC-CONSOLE-001` |
| `REQ-038` | `RLC-CLEAN-001`, `RLC-CLEAN-002`, `RLC-LAUNCH-002` |
| `REQ-039` | `RLC-DOC-001`, `RLC-SKILL-001`, `RLC-AGENTS-001`, `RLC-IMPORT-001` |
| `REQ-040` | `RLC-REG-001`, `RLC-REG-002`, `RLC-REG-003` |
| `REQ-041` | `RLC-REG-001`, `RLC-REGISTRY-001`, `RLC-CONTRACT-001` |
| `REQ-042` | `RLC-MIG-001` |
| `REQ-043` | `RLC-REG-001`, `RLC-REG-004`, `RLC-REG-005` |
| `REQ-044` | `RLC-WORKTREE-001` |

All requirements are suitable for automated testing except manual inspection of final git status for `REQ-044`; automation covers current working directory and file path scope, and final human check confirms no main-worktree changes.

## 3. 测试分层

### 单元测试

Purpose: validate deterministic schema, path, semantics, and helper behavior without broker process.

Coverage:

- `env_store` validation for task/artifact/handoff/memory.
- `source_refs` normalization and rejection.
- `buddybox` path validation and content encoding helpers.
- `env.tools.contracts` and `env.tools.semantics` coverage.
- Runtime broker method/lock policy helpers.

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_store_v2.py tests/test_env_tool_semantic_contract.py tests/test_runtime_broker.py::RuntimeBrokerCoordinatorTests tests/test_runless_runtime_contract.py -q
```

### 集成测试

Purpose: execute broker-routed env.tool services in runtime workspace fixtures and assert files/responses.

Coverage:

- task/track/artifact/handoff/memory/buddybox/context services.
- structured success/rejection response contracts.
- cross-buddy owner/read/write boundaries.
- evidence target-scoped behavior.

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_context_binding_env_tool.py tests/test_memory_env_tool.py tests/test_buddybox_env_tool.py tests/test_evidence_env_tool.py tests/test_env_tool_response_contract.py -q
```

### CLI、API、UI 或主路径运行测试

Purpose: verify externally used command surfaces and local UI projection.

Coverage:

- `scripts/env/client.py` CLI resources and stdout JSON.
- Runtime broker supported methods and identity checks.
- Workspace projection endpoint contract.
- Context panel console rendering assumptions.
- Launcher instance start/open/list, env profiles, sandbox writable roots.

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py tests/test_buddyswitch_launcher.py tests/test_buddy_env_profiles.py tests/test_buddy_env_sandbox.py tests/test_parallel_contracts.py tests/test_console_app_contract.py -q
```

### 回归测试

Purpose: prevent old run/current-binding architecture from reappearing.

Coverage:

- Registry and CLI absence of `run` and `binding`.
- Absence of `source_run_id`、`run_ids`、`latest_run_id`、`current_task_id`、`current_track_id` in active code/guidance.
- No `buddyswitch/content/runs` or `runs/raw` writes.
- Docs/skills/AGENTS no prepare/persist/run commit guidance.

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runless_runtime_contract.py tests/test_repo_consistency.py tests/test_runtime_agents.py tests/test_runtime_skills.py tests/test_skill_creator_importer.py -q
```

### 手动验证

Purpose: confirm worktree isolation and developer-facing experience after automated tests.

Steps:

```bash
pwd
git status --short --branch
rg -n "run\\.commit|run\\.validate_result|run\\.get_receipt|run\\.get_raw|binding\\." scripts buddyswitch tools framework README.md AGENTS.md
rg -n "source_run_id|run_ids|latest_run_id|current_task_id|current_track_id" scripts buddyswitch tools framework README.md AGENTS.md
rg -n "run_envelope|persist_command_hint|prepare-context|buddyswitch/content/runs|runs/raw" scripts buddyswitch tools framework README.md AGENTS.md
```

Expected:

- `pwd` is `/Users/chen/Dev/buddyswitch/.worktrees/dev2258`.
- Git branch is `dev2258`.
- Residue searches return no active source/guidance hits.

## 4. 详细测试用例

### `RLC-CONTRACT-001`: runless runtime writes no run state

- 覆盖需求：`REQ-001`、`REQ-017`、`REQ-041`
- 用户 / 系统场景：Host performs context discovery and product writes without any execution run record.
- 前置条件：Runtime workspace fixture with active PM instance.
- 输入：broker `env.tool context.summarize`, then `task.create`, then `artifact.create_revision`.
- 预期输出或状态变化：task and artifact JSON exist; `buddyswitch/content/runs`, `buddyswitch/content/runs/reserved`, `runs/raw` absent or empty.
- 断言重点：no `run_envelope`, no run files, artifact has `created_by` and `source_refs`, no `source_run_id`.
- 测试类型：integration regression.
- 建议测试文件路径和测试名称：`tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_context_and_artifact_write_create_no_run_state`.

### `RLC-CONTRACT-002`: instance record contains execution identity only

- 覆盖需求：`REQ-002`、`REQ-003`
- 场景：Launcher creates a buddy instance.
- 前置条件：Temporary shared root and PM start flow fixture.
- 输入：`./buddyswitch-codex instance start --buddy pm` through existing launcher harness.
- 预期输出或状态变化：`instance.json` has allowed execution fields and no current task/track.
- 断言重点：`current_task_id` and `current_track_id` absent, not null placeholders.
- 测试类型：launcher integration.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_writes_runless_instance_record`.

### `RLC-CONTRACT-003`: no canonical run directories are projected or created

- 覆盖需求：`REQ-024`、`REQ-038`
- 场景：Workspace bootstrap creates projected durable state.
- 前置条件：Fresh shared root and active instance workspace.
- 输入：workspace bootstrap via launcher start harness.
- 预期输出或状态变化：tracks/tasks/artifacts/handoffs/memories and buddybox projections exist; run content and run raw paths are not created.
- 断言重点：`buddyswitch/content/runs` and `runs/raw` are absent from workspace skeleton and `.git/info/exclude`.
- 测试类型：launcher/workspace integration.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_workspace_projects_runless_durable_state_only`.

### `RLC-BROKER-001`: broker rejects prepare and persist lifecycle methods

- 覆盖需求：`REQ-021`、`REQ-022`
- 场景：Old host tries broker lifecycle methods.
- 前置条件：Active runtime broker session fixture.
- 输入：broker requests with `method="prepare"` and `method="persist"`.
- 预期输出或状态变化：structured rejection, no files written.
- 断言重点：supported methods mention `env.tool`, `ping`, `status`; no idempotency or rerun prepare guidance.
- 测试类型：broker integration.
- 建议测试文件路径和测试名称：`tests/test_runtime_broker.py::RuntimeBrokerTests::test_prepare_and_persist_methods_are_rejected`.

### `RLC-BROKER-002`: runtime infrastructure still reports identity and status

- 覆盖需求：`REQ-002`
- 场景：Broker remains execution infrastructure after run deletion.
- 前置条件：Active instance record.
- 输入：broker `ping` and `status`.
- 预期输出或状态变化：responses include protocol, instance id, active buddy, runtime root, broker health.
- 断言重点：no current task/track, no run health/reservation fields.
- 测试类型：broker integration.
- 建议测试文件路径和测试名称：`tests/test_runtime_broker.py::RuntimeBrokerTests::test_ping_and_status_report_execution_identity_without_run_health`.

### `RLC-BROKER-003`: broker lock mode follows env tool mutability

- 覆盖需求：`REQ-022`
- 场景：Read and write env.tool requests derive read/write lock mode from registry.
- 前置条件：Registry includes memory/buddybox mutability.
- 输入：`context.summarize`, `memory.write`, `buddybox.write`.
- 预期输出或状态变化：read action gets read lock, writes get write lock.
- 断言重点：no special prepare/persist branch.
- 测试类型：unit.
- 建议测试文件路径和测试名称：`tests/test_runtime_broker.py::RuntimeBrokerCoordinatorTests::test_lock_mode_uses_env_tool_registry_without_prepare_persist_special_case`.

### `RLC-REGISTRY-001`: canonical tool registry is runless

- 覆盖需求：`REQ-019`、`REQ-020`、`REQ-041`
- 场景：Host inspects runtime-visible tool surface.
- 前置条件：Import `env.tools.contracts`.
- 输入：`supported_tools()`, `env_tools_description()`, `operation_semantics()`.
- 预期输出或状态变化：tools include `task`, `track`, `artifact`, `handoff`, `context`, `memory`, `buddybox`; exclude `run`, `binding`.
- 断言重点：no action keys start with `run.` or `binding.`; memory/buddybox semantic coverage complete.
- 测试类型：unit/registry.
- 建议测试文件路径和测试名称：`tests/test_env_tool_router.py::EnvToolRouterTests::test_runless_tool_registry_matches_dispatch_handlers`.

### `RLC-SEM-001`: semantics cover memory and buddybox actions

- 覆盖需求：`REQ-032`
- 场景：Host must understand new tools without service code.
- 前置条件：Tool registry loaded.
- 输入：semantic coverage checker.
- 预期输出或状态变化：no coverage errors.
- 断言重点：all memory/buddybox payload fields appear in `inputs_explained`; side effects mention durability and idempotency.
- 测试类型：unit.
- 建议测试文件路径和测试名称：`tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_memory_and_buddybox_semantics_are_complete`.

### `RLC-SEM-002`: semantic text rejects low-signal placeholders

- 覆盖需求：`REQ-032`
- 场景：Implementation cannot satisfy semantics with empty/generic text.
- 前置条件：Tool semantics loaded.
- 输入：all semantic text fields.
- 预期输出或状态变化：no value is empty, `n/a`, `use this tool`, or a repeated field name.
- 断言重点：checks include new tools and changed source_refs fields.
- 测试类型：unit.
- 建议测试文件路径和测试名称：`tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_runless_semantic_text_has_signal`.

### `RLC-RESP-001`: success responses expose state and durability

- 覆盖需求：`REQ-033`
- 场景：Every successful env tool action tells host what changed or what was read.
- 前置条件：Runtime workspace fixture with minimal objects.
- 输入：one successful action per registered action.
- 预期输出或状态变化：success shape includes `state_changed`, `durability`, `effect_summary`, and read/write-specific fields.
- 断言重点：read actions set `state_changed=false`, writes set true and created/updated ids where meaningful.
- 测试类型：integration response contract.
- 建议测试文件路径和测试名称：`tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_runless_actions_have_success_response_semantics`.

### `RLC-RESP-002`: rejections expose recovery and no partial mutation

- 覆盖需求：`REQ-033`、`REQ-034`
- 场景：Invalid payloads and permission denials are machine-readable.
- 前置条件：Runtime workspace with before-state snapshot.
- 输入：invalid memory kind, buddybox traversal, artifact foreign write.
- 预期输出或状态变化：`ok=false`, no files changed.
- 断言重点：`permission_boundary`, `why_blocked`, `impact`, `retryable`, `retry_guidance`, `allowed_next_actions`.
- 测试类型：integration response contract.
- 建议测试文件路径和测试名称：`tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_runless_rejections_explain_impact_without_partial_mutation`.

### `RLC-RESP-003`: next actions reference registered tools only

- 覆盖需求：`REQ-033`
- 场景：Tool feedback must not point to deleted run/binding tools.
- 前置条件：Collect success/rejection samples from focused actions.
- 输入：all `allowed_next_action_options`, `next_actions`, `command_hint`.
- 预期输出或状态变化：all referenced tools/actions exist in registry; hints use `python3 scripts/env/client.py`.
- 断言重点：no hint contains `run`, `binding`, `buddyswitch/content/runs`, `runs/raw`.
- 测试类型：response contract regression.
- 建议测试文件路径和测试名称：`tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_runless_next_actions_reference_registered_product_tools`.

### `RLC-STORE-001`: task validation rejects run bookkeeping

- 覆盖需求：`REQ-006`
- 场景：Old task JSON appears in object store.
- 前置条件：Task fixture includes `run_ids` and `latest_run_id`.
- 输入：`env_store.validate_task(payload)`.
- 预期输出或状态变化：raises `ValueError`.
- 断言重点：error names retired fields and points to artifact history, not silent normalization.
- 测试类型：unit.
- 建议测试文件路径和测试名称：`tests/test_env_store_v2.py::EnvStoreV2Tests::test_task_validation_rejects_run_bookkeeping_fields`.

### `RLC-STORE-002`: artifact and handoff validation reject source_run_id

- 覆盖需求：`REQ-007`、`REQ-010`
- 场景：Old provenance fields appear in stored objects.
- 前置条件：Artifact and handoff fixtures include `source_run_id`.
- 输入：`env_store.validate_artifact`, `env_store.validate_handoff_record`.
- 预期输出或状态变化：raises `ValueError`.
- 断言重点：new valid fixture with `created_by` and `source_refs` passes.
- 测试类型：unit.
- 建议测试文件路径和测试名称：`tests/test_env_store_v2.py::EnvStoreV2Tests::test_artifact_and_handoff_validation_use_source_refs_not_source_run_id`.

### `RLC-TASK-001`: task create/list/get return no run fields

- 覆盖需求：`REQ-006`
- 场景：Buddy creates and reads own task.
- 前置条件：Active PM runtime.
- 输入：`task.create`, `task.list`, `task.get`.
- 预期输出或状态变化：task file exists without run fields.
- 断言重点：response task rows omit `run_ids`, `latest_run_id`, `current_binding`.
- 测试类型：service integration.
- 建议测试文件路径和测试名称：`tests/test_task_env_tool.py::TaskManagerEnvToolTests::test_task_create_list_get_are_runless`.

### `RLC-TASK-002`: task create can attach explicit track

- 覆盖需求：`REQ-026`
- 场景：Buddy creates task under known track without current binding.
- 前置条件：Existing active track.
- 输入：`task.create {"title": "...", "track_id": "track-demo"}`.
- 预期输出或状态变化：task `track_id` set; track `task_ids` includes task.
- 断言重点：instance JSON unchanged.
- 测试类型：service integration.
- 建议测试文件路径和测试名称：`tests/test_task_env_tool.py::TaskManagerEnvToolTests::test_task_create_attaches_track_without_instance_binding`.

### `RLC-TRACK-001`: PM lifecycle remains concrete and PM-owned

- 覆盖需求：`REQ-005`
- 场景：PM updates track lifecycle; non-PM is rejected.
- 前置条件：Active PM and Dev instances over same state.
- 输入：PM `track.update`, Dev `track.update`.
- 预期输出或状态变化：PM write succeeds; Dev rejection no mutation.
- 断言重点：no generic workflow/rule engine fields appear in response or object.
- 测试类型：service integration.
- 建议测试文件路径和测试名称：`tests/test_track_env_tool.py::TrackManagerEnvToolTests::test_pm_lifecycle_authority_survives_runless_rebuild`.

### `RLC-TRACK-002`: track.join does not write instance binding

- 覆盖需求：`REQ-026`
- 场景：Design joins PM track before reading artifact.
- 前置条件：Existing track and no Design task on track.
- 输入：`track.join {"track_id": "track-demo"}`.
- 预期输出或状态变化：Design task created and attached; `instance.json` has no current fields.
- 断言重点：`state_changes` mention task object and track membership only.
- 测试类型：service integration.
- 建议测试文件路径和测试名称：`tests/test_track_env_tool.py::TrackManagerEnvToolTests::test_track_join_creates_relation_without_instance_binding`.

### `RLC-ART-001`: artifact records use created_by and source_refs

- 覆盖需求：`REQ-007`、`REQ-030`
- 场景：PM writes artifact with provenance refs.
- 前置条件：PM task exists.
- 输入：`artifact.create_revision` with `source_refs` to memory and buddybox.
- 预期输出或状态变化：artifact file has `created_by="pm"` and normalized `source_refs`.
- 断言重点：no `source_run_id`, revision/current slot updated.
- 测试类型：service integration.
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_create_revision_persists_created_by_and_source_refs`.

### `RLC-ART-002`: artifact write authority uses active-buddy owned task

- 覆盖需求：`REQ-008`、`REQ-018`
- 场景：Sub-agent under PM writes artifact to one PM task while another PM task exists.
- 前置条件：Two PM tasks on different tracks.
- 输入：`artifact.create_revision` for each explicit task id.
- 预期输出或状态变化：both artifacts written to intended tasks; no instance selection needed.
- 断言重点：task slots updated independently, no current binding mutation.
- 测试类型：service integration.
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_explicit_task_id_allows_independent_multi_task_artifact_writes`.

### `RLC-ART-003`: missing task_id rejects before write

- 覆盖需求：`REQ-009`
- 场景：Old artifact payload relies on current task fallback.
- 前置条件：Active buddy has tasks but no task id in payload.
- 输入：`artifact.create_revision` without `task_id`.
- 预期输出或状态变化：structured rejection, no artifact file.
- 断言重点：`permission_boundary="request-payload"`, `why_blocked` names `task_id`.
- 测试类型：negative integration.
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_create_revision_requires_explicit_task_id`.

### `RLC-ART-004`: metadata update does not require provenance

- 覆盖需求：`REQ-027`
- 场景：Buddy edits title/summary on owned artifact.
- 前置条件：Owned artifact exists.
- 输入：`artifact.update_metadata {"artifact_id": "...", "title": "New"}`.
- 预期输出或状态变化：title updated, content unchanged.
- 断言重点：no required `source_refs`, no `source_run_id`, content body equal before/after.
- 测试类型：service integration.
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_update_metadata_changes_title_summary_without_provenance_requirement`.

### `RLC-HANDOFF-001`: handoff create uses product refs

- 覆盖需求：`REQ-010`、`REQ-030`
- 场景：PM hands off to Design with artifact, memory, buddybox refs.
- 前置条件：Track, PM task, PM artifact, PM memory, PM buddybox file exist.
- 输入：`handoff.create` with object refs and no source run.
- 预期输出或状态变化：handoff JSON exists with product refs.
- 断言重点：no `source_run_id`, status active, track lifecycle unchanged.
- 测试类型：service integration.
- 建议测试文件路径和测试名称：`tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_handoff_create_uses_product_refs_without_source_run`.

### `RLC-HANDOFF-002`: handoff list reads explicit records only

- 覆盖需求：`REQ-010`、`REQ-025`
- 场景：Track has explicit handoffs and old run audit fixture file exists in a blocked path.
- 前置条件：Explicit handoff object exists; old run audit path is absent from canonical state.
- 输入：`handoff.list {"track_id": "track-demo"}`.
- 预期输出或状态变化：response includes explicit handoff only.
- 断言重点：no scan of `buddyswitch/content/runs`, no run audit-derived row.
- 测试类型：regression integration.
- 建议测试文件路径和测试名称：`tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_handoff_list_reads_explicit_records_not_run_audits`.

### `RLC-SRCREF-001`: source_refs accepts all allowed ref types

- 覆盖需求：`REQ-030`
- 场景：Artifact, memory, and handoff store normalized provenance.
- 前置条件：Objects exist for internal ids and buddybox path.
- 输入：source refs with `artifact`, `memory`, `buddybox`, `track`, `task`, `handoff`, `external`, `note`.
- 预期输出或状态变化：normalized refs are returned in success responses.
- 断言重点：required keys enforced, output order stable.
- 测试类型：unit/integration.
- 建议测试文件路径和测试名称：`tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_source_refs_accept_allowed_types_and_normalize`.

### `RLC-SRCREF-002`: source_refs unknown types reject

- 覆盖需求：`REQ-030`
- 场景：Payload attempts unsupported provenance type.
- 前置条件：Active PM task exists.
- 输入：`source_refs=[{"type":"run","id":"run-old"}]`.
- 预期输出或状态变化：rejection, no write.
- 断言重点：`permission_boundary="source_refs.type"` and no object created.
- 测试类型：negative unit/integration.
- 建议测试文件路径和测试名称：`tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_source_refs_reject_unknown_type_without_write`.

### `RLC-SRCREF-003`: source_refs does not authorize writes

- 覆盖需求：`REQ-031`
- 场景：Dev references PM artifact while attempting to write PM task.
- 前置条件：PM task/artifact and Dev active instance.
- 输入：Dev `artifact.create_revision` with `task_id` PM task and source_refs to PM artifact.
- 预期输出或状态变化：rejection.
- 断言重点：boundary is task ownership, not source_refs; no artifact file.
- 测试类型：negative integration.
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_source_refs_do_not_grant_foreign_task_write_authority`.

### `RLC-MEM-001`: memory owner lifecycle succeeds

- 覆盖需求：`REQ-011`、`REQ-012`、`REQ-014`
- 场景：PM writes, reads, lists, updates, archives memory.
- 前置条件：Active PM runtime.
- 输入：`memory.write`, `memory.get`, `memory.list`, `memory.update`, `memory.archive`.
- 预期输出或状态变化：memory JSON persists under `buddyswitch/objects/memories`.
- 断言重点：id pattern, status transition, changed fields, source_refs normalized.
- 测试类型：service integration.
- 建议测试文件路径和测试名称：`tests/test_memory_env_tool.py::MemoryEnvToolTests::test_memory_write_get_list_update_archive_for_owner`.

### `RLC-MEM-002`: memory kind and status validation

- 覆盖需求：`REQ-013`
- 场景：Buddy sends invalid kind/status.
- 前置条件：Active PM runtime.
- 输入：`kind="transcript"`, update `status="deleted"`.
- 预期输出或状态变化：structured rejection, no file or no field mutation.
- 断言重点：stable boundaries `memory.kind` and `memory.status`.
- 测试类型：negative integration.
- 建议测试文件路径和测试名称：`tests/test_memory_env_tool.py::MemoryEnvToolTests::test_memory_rejects_invalid_kind_status_without_mutation`.

### `RLC-MEM-003`: memory permission enforcement is in service

- 覆盖需求：`REQ-014`、`REQ-034`
- 场景：Design tries to update PM memory and read full restricted content.
- 前置条件：PM memory exists; Design active instance.
- 输入：Design `memory.update`, Design `memory.get`.
- 预期输出或状态变化：owner write rejected; full read denied unless explicit rule permits it.
- 断言重点：rejection fields include `permission_boundary`, no prompt-only behavior.
- 测试类型：negative integration.
- 建议测试文件路径和测试名称：`tests/test_memory_env_tool.py::MemoryEnvToolTests::test_memory_cross_buddy_write_and_full_read_denials_are_enforced_in_service`.

### `RLC-MEM-004`: context includes curated memory, not transcripts

- 覆盖需求：`REQ-011`、`REQ-036`
- 场景：Memory written explicitly appears in later context.
- 前置条件：PM memory exists; no run state.
- 输入：`context.summarize`.
- 预期输出或状态变化：memory summary appears; no automatic execution transcript section.
- 断言重点：context has `memory_summaries`, no run/transcript summary.
- 测试类型：context integration.
- 建议测试文件路径和测试名称：`tests/test_memory_env_tool.py::MemoryEnvToolTests::test_context_summarize_projects_explicit_memory_only`.

### `RLC-BOX-001`: buddybox text and binary write/read/list/delete

- 覆盖需求：`REQ-015`、`REQ-016`
- 场景：PM writes HTML and screenshot bytes to buddybox.
- 前置条件：Active PM runtime.
- 输入：`buddybox.write` with `content`, `buddybox.write` with `content_base64`, then list/read/delete.
- 预期输出或状态变化：files exist under `buddyswitch/content/buddybox/pm`.
- 断言重点：text read returns UTF-8 content, binary read returns base64, summaries include source_ref.
- 测试类型：service integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_text_binary_lifecycle`.

### `RLC-BOX-002`: buddybox path traversal rejects

- 覆盖需求：`REQ-016`
- 场景：Payload attempts to escape buddybox root.
- 前置条件：Active PM runtime.
- 输入：paths `/tmp/a`, `../dev/file`, `pm/../../x`, empty path.
- 预期输出或状态变化：structured rejection, no file.
- 断言重点：`permission_boundary` values distinguish absolute path and traversal.
- 测试类型：negative integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_rejects_absolute_parent_and_empty_paths`.

### `RLC-BOX-003`: buddybox owner write scope enforced in code

- 覆盖需求：`REQ-016`、`REQ-034`
- 场景：PM tries to write under Dev root.
- 前置条件：Active PM runtime.
- 输入：`buddybox.write {"path":"dev/report.txt","content":"x"}`.
- 预期输出或状态变化：rejection and no file.
- 断言重点：boundary `buddybox.owner_scope`, no AGENTS-only permission.
- 测试类型：negative integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_rejects_foreign_buddy_write_and_delete`.

### `RLC-BOX-004`: buddybox is intentional durable output, not scratch rename

- 覆盖需求：`REQ-015`
- 场景：Launcher and docs do not expose generic scratch.
- 前置条件：Env profile loaded.
- 输入：profile validation and AGENTS text scan.
- 预期输出或状态变化：profile contains `buddybox.root`; no `scratch.root`.
- 断言重点：guidance says buddybox for intentional durable files only.
- 测试类型：profile/docs regression.
- 建议测试文件路径和测试名称：`tests/test_buddy_env_profiles.py::BuddyEnvProfilesTests::test_profiles_define_buddybox_not_scratch_root`.

### `RLC-CLI-001`: env client removes run and binding resources

- 覆盖需求：`REQ-019`、`REQ-020`
- 场景：Agent inspects CLI help.
- 前置条件：Source checkout.
- 输入：`python3 scripts/env/client.py --help`.
- 预期输出或状态变化：help includes memory/buddybox, excludes run/binding.
- 断言重点：subcommands `task get-current`, `task set-current`, `track get-current` absent.
- 测试类型：CLI regression.
- 建议测试文件路径和测试名称：`tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_env_client_help_exposes_runless_resources`.

### `RLC-CLI-002`: memory CLI routes through broker

- 覆盖需求：`REQ-014`
- 场景：Buddy writes memory from CLI.
- 前置条件：Live broker fixture with active PM.
- 输入：`python3 scripts/env/client.py memory write --payload memory.json`.
- 预期输出或状态变化：stdout JSON `ok=true`, memory file exists.
- 断言重点：response has service semantics and created id.
- 测试类型：CLI integration.
- 建议测试文件路径和测试名称：`tests/test_memory_env_tool.py::MemoryEnvToolTests::test_memory_cli_prints_structured_json`.

### `RLC-CLI-003`: buddybox CLI routes through broker

- 覆盖需求：`REQ-016`
- 场景：Buddy writes and reads file from CLI.
- 前置条件：Live broker fixture with active PM.
- 输入：`buddybox write --payload file.json`, `buddybox read --path pm/prototypes/a.html`.
- 预期输出或状态变化：stdout JSON includes path, size, content.
- 断言重点：no direct filesystem writes outside service.
- 测试类型：CLI integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_cli_prints_structured_json`.

### `RLC-CTX-001`: context discovery includes product summaries only

- 覆盖需求：`REQ-004`、`REQ-021`、`REQ-036`
- 场景：Buddy asks for orientation.
- 前置条件：State has tracks, tasks, artifacts, handoffs, memories, buddybox files.
- 输入：`context.get` and `context.summarize`.
- 预期输出或状态变化：responses include product summaries and tool catalog.
- 断言重点：no `run_envelope`, `persist_command_hint`, current binding, run audit summaries, source run fields.
- 测试类型：context integration.
- 建议测试文件路径和测试名称：`tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_discovery_projects_product_state_without_run_or_binding`.

### `RLC-CTX-002`: context list_sources names new source of truth

- 覆盖需求：`REQ-036`
- 场景：Host inspects section descriptors.
- 前置条件：Runtime context service loaded.
- 输入：`context.list_sources`.
- 预期输出或状态变化：source descriptors include memories and buddybox.
- 断言重点：no descriptor points to `buddyswitch/content/runs/<run_id>.json`.
- 测试类型：context integration.
- 建议测试文件路径和测试名称：`tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_list_sources_uses_product_object_source_paths`.

### `RLC-PROJ-001`: workspace projection exposes memories and buddybox

- 覆盖需求：`REQ-025`、`REQ-037`
- 场景：Context panel reads `/api/workspace`.
- 前置条件：Runtime state has memory and buddybox file.
- 输入：`runtime_store.projections.build_workspace_projection()`.
- 预期输出或状态变化：top-level `memories` and `buddybox_files`; no `run_audits`.
- 断言重点：contract key order matches `framework/contracts/workspace-projection.json`.
- 测试类型：projection contract.
- 建议测试文件路径和测试名称：`tests/test_parallel_contracts.py::WorkspaceProjectionContractTests::test_contract_matches_runless_workspace_projection`.

### `RLC-CONSOLE-001`: console renders durable outputs, not runs

- 覆盖需求：`REQ-025`、`REQ-037`
- 场景：Browser context panel JavaScript normalizes workspace data.
- 前置条件：Fixture workspace JSON with tracks, tasks, artifacts, handoffs, memories, buddybox.
- 输入：Console JS contract harness.
- 预期输出或状态变化：counts and details use durable outputs.
- 断言重点：no `run_audits`, `runMap`, latest run labels, source run labels.
- 测试类型：UI contract.
- 建议测试文件路径和测试名称：`tests/test_console_app_contract.py::ConsoleAppContractTests::test_console_uses_memory_buddybox_and_handoff_without_run_audits`.

### `RLC-CLEAN-001`: cleanup deletes product objects and buddybox, not runs

- 覆盖需求：`REQ-038`
- 场景：All-data cleanup on shared state.
- 前置条件：Tracks/tasks/artifacts/handoffs/memories/buddybox files exist.
- 输入：`python3 scripts/env_cleanup.py --scope all-data`.
- 预期输出或状态变化：product objects and buddybox deleted; shared root and project workspace kept.
- 断言重点：plan has no `run_content`, `run_raw`, `run_ids`.
- 测试类型：cleanup integration.
- 建议测试文件路径和测试名称：`tests/test_cleanup_system.py::CleanupBackendTests::test_all_data_cleanup_targets_runless_product_state`.

### `RLC-CLEAN-002`: buddy cleanup respects buddybox owner scope

- 覆盖需求：`REQ-038`
- 场景：PM cleanup should not delete Dev buddybox files.
- 前置条件：PM and Dev buddybox files and memories exist.
- 输入：buddy-scoped cleanup for PM.
- 预期输出或状态变化：PM files/memories deleted; Dev files/memories remain.
- 断言重点：symlink guard still blocks unsafe roots.
- 测试类型：cleanup integration.
- 建议测试文件路径和测试名称：`tests/test_cleanup_system.py::CleanupBackendTests::test_buddy_cleanup_removes_only_owned_memory_and_buddybox`.

### `RLC-PROFILE-001`: env profiles validate buddybox root

- 覆盖需求：`REQ-029`
- 场景：Profile validator checks every buddy.
- 前置条件：All profile JSON files updated.
- 输入：`python3 scripts/env_profiles.py validate-all`.
- 预期输出或状态变化：all buddies ok.
- 断言重点：`scratch` key unsupported; `buddybox.root` exact expected path.
- 测试类型：profile unit/CLI.
- 建议测试文件路径和测试名称：`tests/test_buddy_env_profiles.py::BuddyEnvProfilesTests::test_profiles_validate_buddybox_matrix_rules`.

### `RLC-SANDBOX-001`: sandbox grants active buddybox root only

- 覆盖需求：`REQ-029`
- 场景：Codex config writable roots generated for PM and Dev.
- 前置条件：Profile mode config patch harness.
- 输入：`codex_config.build_writable_roots()` with PM/Dev args.
- 预期输出或状态变化：writable roots include active buddybox root; exclude `runs/raw` and broad `state`.
- 断言重点：PM cannot write Dev buddybox; Dev still has project workspace write.
- 测试类型：sandbox unit.
- 建议测试文件路径和测试名称：`tests/test_buddy_env_sandbox.py::BuddyEnvSandboxTests::test_profile_mode_grants_active_buddybox_root_and_no_run_raw`.

### `RLC-LAUNCH-001`: instance list omits current work columns

- 覆盖需求：`REQ-003`
- 场景：User lists instances.
- 前置条件：Stored instances exist.
- 输入：`./buddyswitch-codex instance list`.
- 预期输出或状态变化：tabular output has no `current_task_id` or `current_track_id` columns.
- 断言重点：existing filter by buddy remains.
- 测试类型：launcher CLI.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_list_prints_execution_identity_columns_only`.

### `RLC-LAUNCH-002`: workspace state skeleton is runless

- 覆盖需求：`REQ-024`、`REQ-029`、`REQ-038`
- 场景：Launcher starts product instance.
- 前置条件：Fresh shared root.
- 输入：`instance start --buddy pm`.
- 预期输出或状态变化：projected state dirs include memories/handoffs/buddybox; no run dirs.
- 断言重点：local `runs/raw` absent, shared `state/buddyswitch/content/runs` absent.
- 测试类型：launcher integration.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_projects_runless_state_directories`.

### `RLC-EVID-001`: evidence requires product target, not prepared run

- 覆盖需求：`REQ-028`
- 场景：Market issues browser evidence for an artifact target.
- 前置条件：Market task/artifact exists and browser cockpit fake server ready.
- 输入：`evidence.issue_browser {"target_type":"artifact","target_id":"..."}`.
- 预期输出或状态变化：target-scoped token returned.
- 断言重点：token has no `run_id`; service does not read run envelope.
- 测试类型：evidence integration.
- 建议测试文件路径和测试名称：`tests/test_evidence_env_tool.py::EvidenceEnvToolTests::test_issue_browser_uses_product_target_without_run_context`.

### `RLC-EVID-002`: evidence token cannot be used for another target

- 覆盖需求：`REQ-028`
- 场景：Market tries to attach evidence issued for artifact A to artifact B.
- 前置条件：Two market artifacts exist.
- 输入：write/update target B with evidence token for A.
- 预期输出或状态变化：rejection, target B unchanged.
- 断言重点：boundary names evidence target mismatch, no run fallback.
- 测试类型：negative integration.
- 建议测试文件路径和测试名称：`tests/test_market_browser_evidence.py::MarketBrowserEvidenceTests::test_target_scoped_evidence_rejects_other_artifact`.

### `RLC-MARKET-001`: market quality gate records target evidence without run audit

- 覆盖需求：`REQ-028`
- 场景：Market writes artifact with browser evidence.
- 前置条件：Market task, browser evidence token for target flow.
- 输入：`artifact.create_revision` with evidence/source_refs.
- 预期输出或状态变化：artifact written; no run audit.
- 断言重点：evidence appears in artifact metadata or source refs according to chosen contract.
- 测试类型：market integration.
- 建议测试文件路径和测试名称：`tests/test_market_browser_evidence.py::MarketBrowserEvidenceTests::test_market_artifact_write_records_evidence_without_run_audit`.

### `RLC-DOC-001`: active docs teach explicit durable output model

- 覆盖需求：`REQ-039`
- 场景：Repo guidance is scanned.
- 前置条件：Docs updated.
- 输入：Read README, AGENTS, framework docs and contracts.
- 预期输出或状态变化：new wording present.
- 断言重点：no prepare/persist/run raw/current binding guidance; docs say if it matters later write artifact/memory/handoff/buddybox.
- 测试类型：repo consistency.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_active_docs_teach_runless_durable_output_model`.

### `RLC-SKILL-001`: runtime skills install no run-tool

- 覆盖需求：`REQ-039`
- 场景：Buddy runtime workspace materializes skills.
- 前置条件：Manifest updated.
- 输入：runtime skill install for every buddy.
- 预期输出或状态变化：shared skills include track/task/artifact/handoff and memory/buddybox guidance; run-tool directory absent.
- 断言重点：no skill text says one buddy-run commit or before persist.
- 测试类型：runtime skills integration.
- 建议测试文件路径和测试名称：`tests/test_runtime_skills.py::RuntimeSkillsInstallerTests::test_runtime_skills_install_runless_shared_tools_without_run_tool`.

### `RLC-AGENTS-001`: buddy AGENTS templates validate runless rules

- 覆盖需求：`REQ-039`
- 场景：Launcher validates buddy AGENTS.
- 前置条件：All buddy templates updated.
- 输入：`python3 scripts/runtime_agents.py validate-all`.
- 预期输出或状态变化：all templates ok.
- 断言重点：templates include context discovery and explicit durable write rules; no prepare/persist command references.
- 测试类型：runtime agents CLI.
- 建议测试文件路径和测试名称：`tests/test_runtime_agents.py::RuntimeAgentsValidationTests::test_runtime_agents_validate_runless_templates`.

### `RLC-IMPORT-001`: skill importer appends runless closing rules

- 覆盖需求：`REQ-039`
- 场景：Dev imports a native skill package.
- 前置条件：Temporary skill source.
- 输入：`scripts/skill_creator_importer.py import`.
- 预期输出或状态变化：imported SKILL.md has BuddySwitch runtime rules.
- 断言重点：rules say explicit durable outputs; no buddy run commit or persist.
- 测试类型：importer unit/integration.
- 建议测试文件路径和测试名称：`tests/test_skill_creator_importer.py::SkillCreatorImporterTests::test_import_appends_runless_output_rules`.

### `RLC-E2E-001`: PM writes three track notes without runs

- 覆盖需求：`REQ-001`、`REQ-017`
- 场景：PM creates multiple tasks and artifacts across tracks.
- 前置条件：Active PM runtime.
- 输入：three `track.create`, `task.create`, `artifact.create_revision` sequences.
- 预期输出或状态变化：three artifacts current in their tasks; no run dirs.
- 断言重点：no implicit current task needed.
- 测试类型：end-to-end service.
- 建议测试文件路径和测试名称：`tests/test_env_layer_end_to_end.py::EnvLayerEndToEndTests::test_pm_creates_three_track_notes_without_run_state`.

### `RLC-E2E-002`: sub-agent-style writes to different tasks do not compete

- 覆盖需求：`REQ-018`
- 场景：Parent PM dispatches two artifact-writing workers with explicit task ids.
- 前置条件：Two PM tasks exist.
- 输入：two independent `artifact.create_revision` calls in either order.
- 预期输出或状态变化：each artifact belongs to intended task.
- 断言重点：no instance binding field changes because none exists.
- 测试类型：end-to-end regression.
- 建议测试文件路径和测试名称：`tests/test_env_layer_end_to_end.py::EnvLayerEndToEndTests::test_explicit_task_ids_allow_parallel_style_artifact_writes`.

### `RLC-E2E-003`: PM to Design to Dev to Test loop uses product objects

- 覆盖需求：`REQ-004`、`REQ-005`
- 场景：Full cross-buddy collaboration.
- 前置条件：Shared runtime state across buddy instances.
- 输入：PM artifact and handoff, Design artifact, Dev implementation report, Test report.
- 预期输出或状态变化：all outputs discoverable through context and projection.
- 断言重点：handoffs/object refs connect stages; no run history.
- 测试类型：end-to-end workflow.
- 建议测试文件路径和测试名称：`tests/test_env_layer_end_to_end.py::EnvLayerEndToEndTests::test_pm_design_dev_test_loop_uses_product_objects_without_runs`.

### `RLC-E2E-004`: buddybox file referenced from artifact

- 覆盖需求：`REQ-015`、`REQ-016`
- 场景：PM writes HTML prototype and formal artifact references it.
- 前置条件：PM task exists.
- 输入：`buddybox.write` then `artifact.create_revision` with buddybox `source_refs`.
- 预期输出或状态变化：file and artifact exist; context/projection show both.
- 断言重点：source_ref path normalized and no raw scratch path.
- 测试类型：end-to-end workflow.
- 建议测试文件路径和测试名称：`tests/test_env_layer_end_to_end.py::EnvLayerEndToEndTests::test_buddybox_file_can_be_referenced_from_artifact`.

### `RLC-E2E-005`: memory influences later context

- 覆盖需求：`REQ-011`、`REQ-036`
- 场景：PM writes decision memory, later PM context includes it.
- 前置条件：Active PM runtime.
- 输入：`memory.write`, then `context.summarize`.
- 预期输出或状态变化：memory summary appears in context.
- 断言重点：memory was explicitly written; not derived from final response text.
- 测试类型：end-to-end workflow.
- 建议测试文件路径和测试名称：`tests/test_env_layer_end_to_end.py::EnvLayerEndToEndTests::test_explicit_memory_is_discoverable_in_later_context`.

### `RLC-NEG-001`: source_run_id in artifact payload rejects

- 覆盖需求：`REQ-007`、`REQ-009`
- 场景：Old artifact tool caller sends `source_run_id`.
- 前置条件：Active PM task exists.
- 输入：`artifact.create_revision` args include `source_run_id`.
- 预期输出或状态变化：structured rejection, no artifact file.
- 断言重点：unsupported field error names `source_run_id`.
- 测试类型：negative regression.
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_source_run_id_payload_is_rejected_without_write`.

### `RLC-NEG-002`: old task run fields are not silently accepted

- 覆盖需求：`REQ-006`
- 场景：Object store sees stale task fixture.
- 前置条件：Task JSON includes old run fields.
- 输入：load through `env_store.list_tasks()` in temp runtime root.
- 预期输出或状态变化：malformed object error is surfaced.
- 断言重点：no compatibility normalization.
- 测试类型：negative regression.
- 建议测试文件路径和测试名称：`tests/test_env_store_v2.py::EnvStoreV2Tests::test_stale_task_run_fields_fail_fast`.

### `RLC-NEG-003`: foreign task artifact write rejects

- 覆盖需求：`REQ-008`
- 场景：Design tries to write artifact to PM task.
- 前置条件：PM task exists; active Design.
- 输入：`artifact.create_revision {"task_id":"task-pm"}`.
- 预期输出或状态变化：rejection, no artifact file.
- 断言重点：boundary `task.buddy_scope`.
- 测试类型：negative integration.
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_foreign_task_artifact_write_rejects_without_mutation`.

### `RLC-NEG-004`: run and binding tools rejected at router

- 覆盖需求：`REQ-020`
- 场景：Old caller sends deleted tools.
- 前置条件：Active broker dispatch.
- 输入：`{"tool":"run","action":"commit"}`, `{"tool":"binding","action":"get"}`.
- 预期输出或状态变化：unsupported tool rejection.
- 断言重点：no import of deleted services, supported tools list excludes old tools.
- 测试类型：negative router.
- 建议测试文件路径和测试名称：`tests/test_env_tool_router.py::EnvToolRouterTests::test_run_and_binding_tools_are_not_supported`.

### `RLC-NEG-005`: memory missing data and invalid state

- 覆盖需求：`REQ-013`
- 场景：Memory write/update receives empty title, empty content, invalid status.
- 前置条件：Active PM runtime.
- 输入：bad payload combinations.
- 预期输出或状态变化：structured rejection, no partial write.
- 断言重点：state snapshot unchanged.
- 测试类型：negative integration.
- 建议测试文件路径和测试名称：`tests/test_memory_env_tool.py::MemoryEnvToolTests::test_memory_missing_and_invalid_payloads_preserve_state`.

### `RLC-NEG-006`: buddybox duplicate and destructive operations are explicit

- 覆盖需求：`REQ-016`
- 场景：Write same path twice and delete twice.
- 前置条件：Active PM runtime.
- 输入：two writes to same path, two deletes.
- 预期输出或状态变化：second write states overwrite, second delete states deleted false.
- 断言重点：write durability says may overwrite; delete response states whether file existed.
- 测试类型：boundary integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_overwrite_and_repeat_delete_are_explicit`.

### `RLC-NEG-007`: malformed source_refs boundaries

- 覆盖需求：`REQ-030`
- 场景：Missing required keys and invalid buddybox path refs.
- 前置条件：Active PM task.
- 输入：`{"type":"artifact"}` and `{"type":"buddybox","path":"../x"}`.
- 预期输出或状态变化：rejections.
- 断言重点：boundaries `source_refs.required_fields` and `source_refs.buddybox_path`.
- 测试类型：negative unit/integration.
- 建议测试文件路径和测试名称：`tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_source_refs_reject_missing_required_keys_and_bad_paths`.

### `RLC-NEG-008`: unreadable source summary claim rejects

- 覆盖需求：`REQ-031`
- 场景：Buddy claims to summarize internal object it cannot fully read.
- 前置条件：PM memory exists; Design active.
- 输入：Design write memory/artifact with source_refs plus `read_claim="summarized-full-content"` to PM memory.
- 预期输出或状态变化：rejection.
- 断言重点：boundary `source_refs.read_scope`.
- 测试类型：negative integration.
- 建议测试文件路径和测试名称：`tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_source_refs_reject_unreadable_internal_summary_claim`.

### `RLC-MIG-001`: legacy run raw is not auto-migrated

- 覆盖需求：`REQ-042`
- 场景：Old workspace has run content/raw before product start.
- 前置条件：Legacy files under old paths in source-like workspace fixture.
- 输入：launcher start/open or workspace sync.
- 预期输出或状态变化：old files are not copied into new shared state; no memory/artifact generated automatically.
- 断言重点：no hidden migration.
- 测试类型：launcher regression.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_does_not_migrate_legacy_run_state_into_product_objects`.

### `RLC-REG-001`: residue scan blocks old canonical language

- 覆盖需求：`REQ-001`、`REQ-040`、`REQ-043`
- 场景：Developer reintroduces old terms.
- 前置条件：Repo checkout.
- 输入：three `rg` commands from source memo.
- 预期输出或状态变化：no active hits.
- 断言重点：filter only historical memo paths and tests asserting absence.
- 测试类型：repo consistency.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_runless_architecture_residue_scan`.

### `RLC-REG-002`: deleted files are absent

- 覆盖需求：`REQ-023`
- 场景：Deleted old files accidentally remain.
- 前置条件：Repo checkout.
- 输入：Path existence checks.
- 预期输出或状态变化：old service/skill/contract files do not exist.
- 断言重点：`scripts/env/services/runs.py`, `scripts/env/services/bindings.py`, `scripts/runtime_kernel/persist.py`, run-tool skill, persist contract absent.
- 测试类型：repo consistency.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_run_and_binding_services_and_contracts_are_deleted`.

### `RLC-REG-003`: active specs do not preserve old implementation plans

- 覆盖需求：`REQ-023`、`REQ-040`
- 场景：Older active specs still teach run/persist.
- 前置条件：`docs/spec` contains old documents.
- 输入：scan active specs.
- 预期输出或状态变化：old specs are marked historical/superseded or rewritten.
- 断言重点：no active implementation guidance tells engineers to keep run path.
- 测试类型：repo consistency.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_active_specs_do_not_teach_superseded_run_model`.

### `RLC-REG-004`: permission enforcement is not prompt-only

- 覆盖需求：`REQ-034`、`REQ-043`
- 场景：Docs mention permissions but code must enforce them.
- 前置条件：Memory and buddybox negative tests exist.
- 输入：Repo consistency maps permission-sensitive requirements to service tests.
- 预期输出或状态变化：test references present for owner scope and path validation.
- 断言重点：AGENTS/skills say guidance only, and services contain enforcement functions.
- 测试类型：repo consistency.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_memory_buddybox_permissions_are_enforced_in_services_not_prompts`.

### `RLC-REG-005`: no speculative storage systems introduced

- 覆盖需求：`REQ-035`
- 场景：Implementation tries adding database/vector/indexer/sync system.
- 前置条件：Repo checkout.
- 输入：scan for new imports/files such as sqlite, vector, indexer, background sync.
- 预期输出或状态变化：no forbidden systems in memory/buddybox implementation.
- 断言重点：memory is JSON files, buddybox is ordinary files.
- 测试类型：repo consistency.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_memory_and_buddybox_stay_local_file_implementations`.

### `RLC-WORKTREE-001`: implementation stays in dev2258

- 覆盖需求：`REQ-044`
- 场景：Before completion, verify worktree scope.
- 前置条件：Shell in repo.
- 输入：`pwd`, `git status --short --branch`.
- 预期输出或状态变化：cwd is `.worktrees/dev2258`, branch is `dev2258`.
- 断言重点：no main worktree path.
- 测试类型：manual plus optional smoke.
- 建议测试文件路径和测试名称：manual command in final verification.

## 5. 负向与边界测试

- 缺失数据：
  - Missing `task_id` in `artifact.create_revision` covered by `RLC-ART-003`.
  - Missing memory required fields covered by `RLC-NEG-005`.
  - Missing buddybox path/content covered by `RLC-BOX-002` and `RLC-BOX-001`.
  - Missing source_ref required keys covered by `RLC-NEG-007`.
- 无效状态：
  - Invalid memory kind/status covered by `RLC-MEM-002`.
  - Stale task/artifact/handoff records with run fields covered by `RLC-STORE-001`, `RLC-STORE-002`, `RLC-NEG-002`.
  - Unsupported broker methods covered by `RLC-BROKER-001`.
- 重复操作：
  - Repeated buddybox write/delete covered by `RLC-NEG-006`.
  - Repeated memory archive covered by `RLC-MEM-001`.
  - Repeated `track.join` with existing task covered by `RLC-TRACK-002` extension or existing track join test rewrite.
- 并发或顺序敏感行为：
  - Multiple explicit artifact writes to different tasks covered by `RLC-E2E-002`.
  - Broker lock mode for read/write env tools covered by `RLC-BROKER-003`.
  - Evidence token target mismatch covered by `RLC-EVID-002`.
- 空输入、空集合、空记录、空配置：
  - Empty runtime state context covered by `RLC-CTX-001` variant with no objects.
  - Empty buddybox list covered by `RLC-BOX-001`.
  - Empty memory list covered by `RLC-MEM-001`.
  - Empty source_refs accepted as `[]` when optional, malformed entries rejected by `RLC-NEG-007`.
- 权限、路径、配置、运行状态、外部依赖：
  - Memory cross-buddy write/read denial covered by `RLC-MEM-003`.
  - Buddybox traversal and foreign root writes covered by `RLC-BOX-002`, `RLC-BOX-003`.
  - Sandbox writable roots covered by `RLC-SANDBOX-001`.
  - Browser evidence readiness and target scope covered by `RLC-EVID-001`, `RLC-EVID-002`, `RLC-MARKET-001`.
  - Legacy run state migration refusal covered by `RLC-MIG-001`.

## 6. 作弊防护

- Tests combine registry checks, CLI help checks, broker dispatch, service writes, file-system assertions, projection assertions, and docs scans, so hiding an old field in one response cannot pass the suite.
- Test data uses multiple buddies (`pm`, `design`, `dev`, `test`, `market`), multiple tracks, multiple tasks, text and binary buddybox files, and valid/invalid source_refs combinations.
- Artifact tests verify persisted JSON and task `artifact_slots`, not only response shape.
- Memory and buddybox tests verify actual files and state snapshots before/after rejection.
- Permission tests use cross-buddy attempts to prove enforcement is in services, not wording.
- Residue scans protect active source/guidance from reintroducing `run.*`, `binding.*`, `source_run_id`, `run_ids`, `latest_run_id`, current binding, run envelopes, persist hints, and old paths.
- E2E tests assert absence of run directories after successful product writes.
- Response contract tests require meaningful semantics fields and reject low-signal text, preventing semantics from being faked with placeholders.
- Tests do not reduce requirements to match implementation. Old run/binding tools must be absent, not deprecated aliases.

## 7. 验证命令清单

Focused contract tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runless_runtime_contract.py -q
```

Focused service tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_memory_env_tool.py tests/test_buddybox_env_tool.py tests/test_artifact_env_tool.py tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_context_binding_env_tool.py -q
```

Focused registry and response tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_response_contract.py -q
```

Focused launcher/profile/projection tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py tests/test_buddy_env_profiles.py tests/test_buddy_env_sandbox.py tests/test_parallel_contracts.py tests/test_console_app_contract.py tests/test_cleanup_system.py -q
```

Focused guidance tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py tests/test_runtime_agents.py tests/test_runtime_skills.py tests/test_skill_creator_importer.py -q
```

Focused evidence and end-to-end tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_evidence_env_tool.py tests/test_market_browser_evidence.py tests/test_host_decision_surface_product_mode.py tests/test_env_layer_end_to_end.py tests/test_runtime_tool_feedback.py -q
```

Residue verification:

```bash
rg -n "run\\.commit|run\\.validate_result|run\\.get_receipt|run\\.get_raw|binding\\." scripts buddyswitch tools framework README.md AGENTS.md
rg -n "source_run_id|run_ids|latest_run_id|current_task_id|current_track_id" scripts buddyswitch tools framework README.md AGENTS.md
rg -n "run_envelope|persist_command_hint|prepare-context|buddyswitch/content/runs|runs/raw" scripts buddyswitch tools framework README.md AGENTS.md
```

Broader verification before completion:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runless_runtime_contract.py tests/test_memory_env_tool.py tests/test_buddybox_env_tool.py tests/test_env_tool_router.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_response_contract.py tests/test_artifact_env_tool.py tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_context_binding_env_tool.py tests/test_runtime_broker.py tests/test_buddy_env_profiles.py tests/test_buddy_env_sandbox.py tests/test_cleanup_system.py tests/test_console_app_contract.py tests/test_runtime_skills.py tests/test_runtime_agents.py tests/test_repo_consistency.py tests/test_env_layer_end_to_end.py tests/test_evidence_env_tool.py tests/test_market_browser_evidence.py tests/test_host_decision_surface_product_mode.py tests/test_output_schema_boundaries.py tests/test_parallel_contracts.py -q
```

Final verification command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests -q
```

Final manual worktree check:

```bash
pwd
git status --short --branch
```
