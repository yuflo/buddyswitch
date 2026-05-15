# Memory Removal Test Plan

## 1. 测试设计原则

- 测试从源 memo 的功能需求、用户工作流、系统不变量和失败模式出发：active runtime must not expose, accept, write, read, validate, project, clean, or guide `memory`.
- 测试验证外部可观察行为：CLI help/exit status, `turn_runtime.py status` JSON, broker-routed `env.tool` responses, manifest validation, context payloads, workspace projection JSON, launcher-created paths, cleanup plan JSON, active docs/guidance grep results.
- 测试不根据即将写出的实现细节倒推刚好能通过的断言；核心断言是 memory absence, unsupported feedback, no state mutation, and old files ignored.
- 测试覆盖多个入口：registry, router, dispatch, CLI, context service, source_refs normalizers, evidence service, handoff service, projection builder, console normalizer, launcher shell, cleanup backend, docs consistency.
- 测试数据必须包含多个 input combinations：valid artifact target, invalid memory target, unsupported `memory_ids`, unsupported `memory_kind`, old memory file present on disk, normal artifact/handoff/buddybox workflow.
- 负向测试必须断言 no mutation：state snapshots, missing token, no memory directory creation, no projection output, cleanup delete paths unchanged.
- 手动验证只作为 launcher smoke 的补充；自动化 tests and grep gates are completion gates.

## 2. 需求覆盖矩阵

All requirements are suitable for automated testing. Manual launcher smoke is supplemental and does not replace automated proof.

| Requirement | Automated coverage |
| --- | --- |
| `REQ-001` | `MRM-REG-001`, `MRM-GREP-001` |
| `REQ-002` | `MRM-REG-001`, `MRM-CLI-001`, `MRM-DISPATCH-001` |
| `REQ-003` | `MRM-REG-001`, `MRM-SEM-001` |
| `REQ-004` | `MRM-DISPATCH-001`, `MRM-ROUTER-001` |
| `REQ-005` | `MRM-CLI-002` |
| `REQ-006` | `MRM-CLI-001` |
| `REQ-007` | `MRM-MANIFEST-001` |
| `REQ-008` | `MRM-DOC-001` |
| `REQ-009` | `MRM-EVIDENCE-001`, `MRM-DOC-001` |
| `REQ-010` | `MRM-CONTEXT-001`, `MRM-CLI-001` |
| `REQ-011` | `MRM-CONTEXT-002`, `MRM-OLD-001` |
| `REQ-012` | `MRM-CONTEXT-003` |
| `REQ-013` | `MRM-PROJECTION-001`, `MRM-OLD-001` |
| `REQ-014` | `MRM-CONSOLE-001` |
| `REQ-015` | `MRM-STORE-001`, `MRM-OLD-001` |
| `REQ-016` | `MRM-LAUNCHER-001` |
| `REQ-017` | `MRM-OLD-001`, `MRM-CLEANUP-001` |
| `REQ-018` | `MRM-SOURCE-001`, `MRM-SOURCE-002` |
| `REQ-019` | `MRM-SOURCE-002` |
| `REQ-020` | `MRM-EVIDENCE-001`, `MRM-EVIDENCE-002` |
| `REQ-021` | `MRM-BROWSER-EVIDENCE-001` |
| `REQ-022` | `MRM-HANDOFF-001` |
| `REQ-023` | `MRM-HANDOFF-002`, `MRM-PROJECTION-001` |
| `REQ-024` | `MRM-HANDOFF-003` |
| `REQ-025` | `MRM-REG-001`, `MRM-GREP-001` |
| `REQ-026` | `MRM-STORE-001`, `MRM-GREP-001` |
| `REQ-027` | `MRM-SEM-001`, `MRM-DOC-001` |
| `REQ-028` | `MRM-DOC-001`, `MRM-GREP-001` |
| `REQ-029` | `MRM-BUDDYBOX-001` |
| `REQ-030` | `MRM-NONMEM-001` |
| `REQ-031` | `MRM-CLEANUP-001` |
| `REQ-032` | `MRM-REGRESSION-001`, `MRM-GREP-001` |
| `REQ-033` | `MRM-GREP-001` |
| `REQ-034` | `MRM-WORKTREE-001` |

## 3. 测试分层

### 单元测试

Purpose: prove registry, semantics, source_refs, env_store schemas, and manifest permission rules exclude memory without requiring a broker.

Coverage:

- `scripts/env/tools/contracts.py`
- `scripts/env/tools/semantics.py`
- `scripts/env/services/source_refs.py`
- `scripts/env_store.py`
- `scripts/env_manifest.py`

Commands:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_memory_removal_contract.py::MemoryRemovalContractTests::test_tool_registry_status_and_help_exclude_memory tests/test_memory_removal_contract.py::MemoryRemovalContractTests::test_source_refs_reject_memory_type tests/test_env_tool_semantic_contract.py tests/test_env_manifest_v2.py -q
```

### 集成测试

Purpose: prove broker-routed runtime behavior rejects memory, preserves state, and keeps non-memory services working.

Coverage:

- `runtime_kernel.broker.dispatch_runtime_request`
- `scripts/env/tools/router.py`
- `scripts/env/tools/dispatch.py`
- `scripts/env/services/context.py`
- `scripts/env/services/evidence.py`
- `scripts/env/services/handoffs.py`
- `tests.runtime_root_test_helper.RuntimeWorkspaceTestMixin`

Commands:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_memory_removal_contract.py tests/test_env_tool_router.py tests/test_context_binding_env_tool.py tests/test_handoff_env_tool.py tests/test_evidence_env_tool.py tests/test_env_tool_response_contract.py -q
```

### CLI、API、UI 或主路径运行测试

Purpose: verify public command surfaces and visible data shapes.

Coverage:

- `python3 scripts/env/client.py --help`
- `python3 scripts/env/client.py memory list`
- `python3 scripts/turn_runtime.py status`
- `python3 scripts/browser_evidence.py issue --help`
- `workspace_data.build_workspace_data()`
- `framework/console/app.js` contract tests

Commands:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_turn_runtime.py tests/test_prepare_runtime_context.py tests/test_console_app_contract.py tests/test_parallel_contracts.py tests/test_market_browser_evidence.py -q
python3 scripts/env/client.py --help
python3 scripts/env/client.py memory list
python3 scripts/browser_evidence.py issue --help
```

Expected for `python3 scripts/env/client.py memory list`: non-zero exit code and argparse invalid choice output; no JSON broker call is required.

### 回归测试

Purpose: prove memory removal did not break the remaining runless product path.

Coverage:

- task/track/artifact/handoff/buddybox/context/evidence/search env tools
- launcher workspace projection
- cleanup behavior for supported state
- repo consistency
- product-mode host decision surface

Commands:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_handoff_env_tool.py tests/test_buddybox_env_tool.py tests/test_context_binding_env_tool.py tests/test_evidence_env_tool.py tests/test_search_env_tool.py tests/test_buddyswitch_launcher.py tests/test_cleanup_system.py tests/test_repo_consistency.py tests/test_host_decision_surface_product_mode.py -q
```

### 手动验证

Purpose: confirm a real launcher-managed workspace sees the same memory-free surface.

Steps:

1. Run `pwd` and confirm `/Users/chen/Dev/buddyswitch/.worktrees/dev2258`.
2. Run `git branch --show-current` and confirm `dev2258`.
3. Run `./buddyswitch-codex instance start --buddy pm`.
4. In the launched workspace, run `python3 scripts/turn_runtime.py status`.
5. Confirm JSON `env_tools` includes `task`, `track`, `artifact`, `handoff`, `buddybox`, `context`, `evidence`, `search`, and excludes `memory`.
6. Run `python3 scripts/env/client.py memory list`.
7. Confirm argparse rejects `memory` and no `buddyswitch/objects/memories` directory is created in the instance workspace.

## 4. 详细测试用例

### `MRM-WORKTREE-001`: worktree guard

- 覆盖需求：`REQ-034`
- 用户 / 系统场景：Implementation must run in dev2258 and not main.
- 前置条件：Repository checkout exists.
- 输入：`pwd`, `git branch --show-current`, `git status --short`.
- 预期输出或状态变化：cwd is `/Users/chen/Dev/buddyswitch/.worktrees/dev2258`; branch is `dev2258`; status does not show unexpected main-worktree paths.
- 断言重点：Commands are recorded before implementation; plan docs are the only intended changes during planning.
- 测试类型：manual command guard plus final report evidence.
- 建议测试文件路径和测试名称：No automated file; required preflight command in implementation phase.

### `MRM-REG-001`: registry excludes memory tool and actions

- 覆盖需求：`REQ-001`, `REQ-002`, `REQ-003`, `REQ-025`
- 场景：Runtime catalog no longer advertises memory.
- 前置条件：`sys.path` includes `scripts`.
- 输入：`contracts.supported_tools()`, `contracts.env_tools_description()`, `contracts.operation_semantics()`.
- 预期输出或状态变化：`memory` absent; no action key starts with `memory.`; remaining tools match exact expected set.
- 断言重点：Exact set equality prevents hidden extra tools.
- 测试类型：unit contract.
- 建议测试文件路径和测试名称：`tests/test_memory_removal_contract.py::MemoryRemovalContractTests::test_tool_registry_status_and_help_exclude_memory`.

### `MRM-SEM-001`: semantic projection excludes memory and stale guidance

- 覆盖需求：`REQ-003`, `REQ-027`
- 场景：Host sees no memory semantics and no guidance to use memory from remaining tools.
- 前置条件：`contracts.env_tools_description()` imports.
- 输入：All capability/action semantic rows.
- 预期输出或状态变化：No tool key `memory`; no action semantics key `memory`; semantic text for artifact/handoff/buddybox/context/evidence does not mention memory.
- 断言重点：Check serialized semantic projection, not only source text.
- 测试类型：unit contract.
- 建议测试文件路径和测试名称：`tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_registry_semantics_cover_every_registered_tool_and_action` and `tests/test_memory_removal_contract.py::MemoryRemovalContractTests::test_tool_registry_status_and_help_exclude_memory`.

### `MRM-DISPATCH-001`: memory env.tool request rejected without mutation

- 覆盖需求：`REQ-004`, `REQ-017`
- 场景：A buddy attempts old `memory.write`.
- 前置条件：Runtime sandbox contains one existing task and no memory directory.
- 输入：Broker request with `tool="memory"`, `action="write"`, valid-looking args.
- 预期输出或状态变化：`ok=false`, `error.code="E_ENV_TOOL"`, `permission_boundary="env.tool"`, `state_changed=false`; object snapshot unchanged; no memory dir created.
- 断言重点：Reject before dispatch and no partial state.
- 测试类型：broker integration.
- 建议测试文件路径和测试名称：`tests/test_memory_removal_contract.py::MemoryRemovalContractTests::test_env_tool_memory_request_is_rejected_without_state_mutation`.

### `MRM-ROUTER-001`: router and dispatch action sets match registry

- 覆盖需求：`REQ-004`
- 场景：Router cannot keep stale memory handler after registry removal.
- 前置条件：Import `env.tools.router`, `env.tools.dispatch`, `env.tools.contracts`.
- 输入：`router._TOOL_ACTIONS`, `dispatch.dispatch_handler_actions()`, registry action map.
- 预期输出或状态变化：Router and dispatch maps equal registry; `memory` absent from all three.
- 断言重点：Exact action map equality.
- 测试类型：unit/integration contract.
- 建议测试文件路径和测试名称：`tests/test_env_tool_router.py::EnvToolRouterTests::test_router_supported_tools_and_actions_match_registry`.

### `MRM-CLI-001`: env client help and invalid resource behavior

- 覆盖需求：`REQ-006`, `REQ-010`
- 场景：CLI users cannot discover or invoke memory, and context CLI cannot pass memory filters.
- 前置条件：Run from repo root.
- 输入：`python3 scripts/env/client.py --help`, `python3 scripts/env/client.py memory list`, `python3 scripts/env/client.py context get --help`.
- 预期输出或状态变化：Top-level help excludes `memory`; `memory list` returns code 2 with invalid choice; context get help excludes `--memory-kind`.
- 断言重点：No broker JSON response for invalid resource; argparse handles it.
- 测试类型：CLI.
- 建议测试文件路径和测试名称：`tests/test_memory_removal_contract.py::MemoryRemovalContractTests::test_tool_registry_status_and_help_exclude_memory` and `tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_env_client_help_exposes_runless_resources`.

### `MRM-CLI-002`: turn runtime status excludes memory

- 覆盖需求：`REQ-005`
- 场景：Host asks for runtime status.
- 前置条件：Repo root command execution.
- 输入：`python3 scripts/turn_runtime.py status`.
- 预期输出或状态变化：JSON `ok=true`, `runtime_mode="runless"`, `env_tools` contains remaining tools and excludes `memory`.
- 断言重点：Status projection uses runtime contract, not static docs.
- 测试类型：CLI/main path.
- 建议测试文件路径和测试名称：`tests/test_turn_runtime.py::TurnRuntimeRunlessTests::test_status_lists_only_runless_tool_surfaces`.

### `MRM-MANIFEST-001`: manifest permissions exclude memory

- 覆盖需求：`REQ-007`
- 场景：No buddy can be granted memory capability from manifest.
- 前置条件：`buddyswitch/manifest.toml` loads.
- 输入：`env_manifest.load_manifest()` and all buddy permissions.
- 预期输出或状态变化：No permission starts with `memory.`; `_validate_permission("memory.read", "synthetic")` raises `ManifestError`.
- 断言重点：Both current manifest and future validation rule.
- 测试类型：unit contract.
- 建议测试文件路径和测试名称：`tests/test_env_manifest_v2.py::EnvManifestV2Tests::test_buddy_permissions_exclude_memory_permissions`.

### `MRM-CONTEXT-001`: context rejects memory_kind

- 覆盖需求：`REQ-010`
- 场景：A caller uses retired context filter.
- 前置条件：Runtime sandbox and active instance.
- 输入：`env.tool` context.get args `{"memory_kind": "decision"}`.
- 预期输出或状态变化：`ok=false`, `E_CONTEXT_PAYLOAD`, unsupported field message, `state_changed=false`.
- 断言重点：Filter is rejected rather than silently ignored.
- 测试类型：integration.
- 建议测试文件路径和测试名称：`tests/test_memory_removal_contract.py::MemoryRemovalContractTests::test_context_rejects_memory_kind_and_omits_memory_sections`.

### `MRM-CONTEXT-002`: context responses omit memory sections

- 覆盖需求：`REQ-011`
- 场景：Old memory file exists but context summarizes current state.
- 前置条件：Runtime sandbox contains tracks/tasks/artifacts/handoffs/buddybox and a directly written old memory JSON file.
- 输入：`context.summarize`, `context.get`.
- 预期输出或状态变化：No `memory_summaries`; no `has_memories`; no `current_context_summary.memories`.
- 断言重点：Old file presence does not affect output.
- 测试类型：integration.
- 建议测试文件路径和测试名称：`tests/test_memory_removal_contract.py::MemoryRemovalContractTests::test_context_rejects_memory_kind_and_omits_memory_sections`.

### `MRM-CONTEXT-003`: context sources omit memories

- 覆盖需求：`REQ-012`
- 场景：Host discovers context source descriptors.
- 前置条件：Active instance.
- 输入：`context.list_sources`.
- 预期输出或状态变化：`sources` contains tracks/tasks/artifacts/handoffs/buddybox and excludes `memories`.
- 断言重点：Source descriptors do not mention memory path.
- 测试类型：integration.
- 建议测试文件路径和测试名称：`tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_list_sources_excludes_memory_and_includes_buddybox`.

### `MRM-SOURCE-001`: service source_refs reject memory

- 覆盖需求：`REQ-018`
- 场景：Artifact or handoff tries to record memory provenance.
- 前置条件：Import `env.services.source_refs`.
- 输入：`[{"type": "memory", "id": "mem-old"}]`.
- 预期输出或状态变化：`ValueError` with unsupported source_ref type.
- 断言重点：Rejects at shared service normalizer.
- 测试类型：unit.
- 建议测试文件路径和测试名称：`tests/test_memory_removal_contract.py::MemoryRemovalContractTests::test_source_refs_reject_memory_type`.

### `MRM-SOURCE-002`: store source_refs reject memory and full-summary checks are artifact-only

- 覆盖需求：`REQ-018`, `REQ-019`
- 场景：Raw store validation sees memory source_ref.
- 前置条件：Valid artifact payload except source_refs.
- 输入：`env_store.validate_artifact()` with `source_refs=[{"type": "memory", "id": "mem-old"}]`; `source_refs.normalize_source_refs()` with artifact read claim variations.
- 预期输出或状态变化：Memory ref raises; artifact full-summary scope checks still work.
- 断言重点：No call path requires `env_store.get_memory`.
- 测试类型：unit.
- 建议测试文件路径和测试名称：`tests/test_memory_removal_contract.py::MemoryRemovalContractTests::test_source_refs_reject_memory_type`.

### `MRM-HANDOFF-001`: handoff payload rejects memory_ids

- 覆盖需求：`REQ-022`
- 场景：Old caller sends `memory_ids`.
- 前置条件：Valid track/task/artifact setup.
- 输入：`handoff.validate` payload with `memory_ids=["mem-old"]`.
- 预期输出或状态变化：`ok=false`, `E_HANDOFF_PAYLOAD`, unsupported field message, `state_changed=false`.
- 断言重点：Rejects explicit retired field.
- 测试类型：integration.
- 建议测试文件路径和测试名称：`tests/test_memory_removal_contract.py::MemoryRemovalContractTests::test_handoff_rejects_memory_ids_and_created_record_omits_memory_ids`.

### `MRM-HANDOFF-002`: created handoff records omit memory_ids

- 覆盖需求：`REQ-023`
- 场景：Valid handoff create with artifact and buddybox refs.
- 前置条件：Valid track/task/artifact/buddybox path.
- 输入：`handoff.create` payload without memory fields.
- 预期输出或状态变化：Response `handoff` lacks `memory_ids`; saved JSON lacks `memory_ids`; projection handoff view lacks `memory_ids`.
- 断言重点：No empty compatibility field.
- 测试类型：integration plus projection.
- 建议测试文件路径和测试名称：`tests/test_memory_removal_contract.py::MemoryRemovalContractTests::test_handoff_rejects_memory_ids_and_created_record_omits_memory_ids`.

### `MRM-HANDOFF-003`: old handoff memory_ids are ignored on read

- 覆盖需求：`REQ-024`
- 场景：Old handoff JSON contains `memory_ids`.
- 前置条件：Write old handoff JSON directly with `memory_ids`, plus required valid fields.
- 输入：`env_store.list_handoffs()` and `handoff.list`.
- 预期输出或状态变化：Read succeeds; normalized record and service response omit `memory_ids`; no memory file lookup is performed.
- 断言重点：Old field is not exposed as compatibility surface.
- 测试类型：unit/integration.
- 建议测试文件路径和测试名称：`tests/test_memory_removal_contract.py::MemoryRemovalContractTests::test_handoff_rejects_memory_ids_and_created_record_omits_memory_ids`.

### `MRM-EVIDENCE-001`: evidence rejects memory target

- 覆盖需求：`REQ-020`, `REQ-009`
- 场景：Market tries evidence downgrade or browser token for memory.
- 前置条件：Active market instance; no memory service.
- 输入：`evidence.issue_browser` and `evidence.approve_downgrade` with `target_type="memory"`.
- 预期输出或状态变化：`E_EVIDENCE_TARGET_TYPE`, `permission_boundary="evidence.target_type"`, `state_changed=false`, no `tool_evidence`.
- 断言重点：No token allocation for memory target.
- 测试类型：integration.
- 建议测试文件路径和测试名称：`tests/test_memory_removal_contract.py::MemoryRemovalContractTests::test_evidence_rejects_memory_target_and_accepts_artifact_target`.

### `MRM-EVIDENCE-002`: evidence still accepts artifact target

- 覆盖需求：`REQ-020`, `REQ-030`
- 场景：Remaining market quality gate works with artifact target.
- 前置条件：Market task and artifact exist.
- 输入：`evidence.issue_browser` with `target_type="artifact"`.
- 预期输出或状态变化：`ok=true`, token target_type artifact, target_id matches artifact, no run id.
- 断言重点：Removal does not break valid artifact evidence.
- 测试类型：integration regression.
- 建议测试文件路径和测试名称：`tests/test_evidence_env_tool.py::EvidenceEnvToolTests::test_issue_browser_is_artifact_scoped_and_runless`.

### `MRM-BROWSER-EVIDENCE-001`: browser evidence CLI target choices are artifact-only

- 覆盖需求：`REQ-021`
- 场景：User invokes wrapper help and retired memory target.
- 前置条件：Repo root.
- 输入：`python3 scripts/browser_evidence.py issue --help`; `python3 scripts/browser_evidence.py issue --target-type memory --target-id mem-old`.
- 预期输出或状态变化：Help lists artifact and excludes memory; memory target returns argparse invalid choice.
- 断言重点：CLI rejects before broker call.
- 测试类型：CLI.
- 建议测试文件路径和测试名称：`tests/test_market_browser_evidence.py::MarketBrowserEvidenceTests::test_browser_evidence_cli_target_type_is_artifact_only`.

### `MRM-STORE-001`: runtime dir setup and store API expose no memory

- 覆盖需求：`REQ-015`, `REQ-026`
- 场景：Runtime creates directories for supported state only.
- 前置条件：Runtime sandbox.
- 输入：`env_store.ensure_runtime_dirs()`; module attribute checks.
- 预期输出或状态变化：tracks/tasks/artifacts/handoffs/buddybox dirs exist; `buddyswitch/objects/memories` absent; `hasattr(env_store, "create_memory")` false.
- 断言重点：No helper API remains for accidental use.
- 测试类型：unit/integration.
- 建议测试文件路径和测试名称：`tests/test_memory_removal_contract.py::MemoryRemovalContractTests::test_workspace_projection_launcher_and_cleanup_ignore_old_memory_files`.

### `MRM-PROJECTION-001`: workspace projection excludes memories

- 覆盖需求：`REQ-013`, `REQ-023`
- 场景：Context panel reads workspace projection.
- 前置条件：Runtime state has track/task/artifact/handoff/buddybox and an old memory JSON file.
- 输入：`workspace_data.build_workspace_data()`.
- 预期输出或状态变化：Payload top-level lacks `memories`; handoff rows lack `memory_ids`; old memory file not represented.
- 断言重点：Projection state shape matches contract exactly.
- 测试类型：integration/projection contract.
- 建议测试文件路径和测试名称：`tests/test_parallel_contracts.py::WorkspaceProjectionContractTests::test_contract_matches_runless_workspace_projection`.

### `MRM-CONSOLE-001`: console normalizer has no memories field

- 覆盖需求：`REQ-014`
- 场景：Console receives workspace JSON without memories.
- 前置条件：Console app contract test can read `framework/console/app.js`.
- 输入：Fixture workspace payload and JS source/static checks.
- 预期输出或状态变化：Normalizer does not add `memories`; app source does not contain `memories`.
- 断言重点：UI cannot silently keep stale memory data shape.
- 测试类型：UI contract/static.
- 建议测试文件路径和测试名称：`tests/test_console_app_contract.py::ConsoleAppContractTests::test_console_workspace_shape_excludes_memories`.

### `MRM-LAUNCHER-001`: launcher does not project memory directory

- 覆盖需求：`REQ-016`
- 场景：Starting an instance creates live state symlinks.
- 前置条件：Launcher test temp shared root.
- 输入：`./buddyswitch-codex instance start --buddy pm` through existing launcher test harness.
- 预期输出或状态变化：Projection pairs include tracks/tasks/artifacts/handoffs/buddybox; no `buddyswitch/objects/memories` state dir or symlink; git exclude lacks memory pattern.
- 断言重点：No projected memory path even in shared state skeleton.
- 测试类型：launcher integration.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_creates_buddy_locked_workspace`.

### `MRM-CLEANUP-001`: cleanup ignores old memory files

- 覆盖需求：`REQ-017`, `REQ-031`
- 场景：Old memory file exists but cleanup manages supported state only.
- 前置条件：Temp repo root with old `buddyswitch/objects/memories/mem-pm.json`.
- 输入：`env_cleanup.build_cleanup_plan(scope="buddy")`, `env_cleanup.build_cleanup_plan(scope="all-data")`, `env_cleanup.execute_cleanup_plan()`.
- 预期输出或状态变化：Plan has no `memory_object_ids`; `delete_paths` lacks memory path; execution does not delete old memory file; skeleton recreation does not create memory dir if absent.
- 断言重点：No migration or cleanup process is added.
- 测试类型：unit/integration.
- 建议测试文件路径和测试名称：`tests/test_cleanup_system.py::CleanupSystemRunlessTests::test_cleanup_ignores_retired_memory_objects`.

### `MRM-OLD-001`: old memory files are ignored across active reads

- 覆盖需求：`REQ-011`, `REQ-013`, `REQ-015`, `REQ-017`
- 场景：Runtime root contains legacy memories from prior iteration.
- 前置条件：Directly write two old JSON files under `buddyswitch/objects/memories`.
- 输入：`context.summarize`, `workspace_data.build_workspace_data()`, cleanup plan, `env_store.ensure_runtime_dirs()`.
- 预期输出或状态变化：No context memory fields; no projection memories; cleanup ignores paths; ensure dirs does not create memory dir in a clean root.
- 断言重点：Multiple old files and different buddies do not change output.
- 测试类型：integration regression.
- 建议测试文件路径和测试名称：`tests/test_memory_removal_contract.py::MemoryRemovalContractTests::test_workspace_projection_launcher_and_cleanup_ignore_old_memory_files`.

### `MRM-DOC-001`: active docs and buddy guidance exclude memory

- 覆盖需求：`REQ-008`, `REQ-009`, `REQ-027`, `REQ-028`
- 场景：Buddies and docs should not instruct users to use memory.
- 前置条件：Active docs and launcher assets exist.
- 输入：Text of `README.md`, `framework/docs/*.md`, `framework/contracts/*.md`, `tools/launcher/assets/buddies/*/AGENTS.md`, `buddyswitch/skills/shared/*.md`.
- 预期输出或状态变化：No active file mentions memory runtime surface; Market guidance says artifact-scoped evidence.
- 断言重点：Historical `docs/memo/**` and old `docs/spec/2026-05-14-*` are excluded from this active-doc check.
- 测试类型：repo consistency.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_active_docs_and_buddy_guidance_exclude_memory`.

### `MRM-BUDDYBOX-001`: buddybox behavior remains unchanged except memory guidance

- 覆盖需求：`REQ-029`
- 场景：Buddybox remains supported.
- 前置条件：Active buddy runtime sandbox.
- 输入：`buddybox.write`, `buddybox.read`, `buddybox.list`, `buddybox.delete`; source_ref with type `buddybox`.
- 预期输出或状态变化：Buddybox operations still pass; response guidance does not mention attaching path to memory.
- 断言重点：Memory removal does not reduce buddybox capability.
- 测试类型：integration regression.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_write_read_list_delete_for_owner`.

### `MRM-NONMEM-001`: task/track/artifact/handoff main path still works

- 覆盖需求：`REQ-030`
- 场景：Runless collaboration uses supported objects only.
- 前置条件：PM, design, dev runtime test helpers.
- 输入：Create track, create task, create artifact with `source_refs=[{"type":"note",...}]`, create handoff with artifact and buddybox refs.
- 预期输出或状态变化：All operations succeed; saved objects contain no run fields and no memory fields.
- 断言重点：No behavioral regression outside memory removal.
- 测试类型：integration regression.
- 建议测试文件路径和测试名称：`tests/test_env_layer_end_to_end.py::EnvLayerEndToEndTests::test_runless_artifact_handoff_and_buddybox_flow_without_memory`.

### `MRM-REGRESSION-001`: memory lifecycle tests are removed or inverted

- 覆盖需求：`REQ-032`
- 场景：Test suite should not prove removed behavior.
- 前置条件：Repo tests collected by pytest.
- 输入：`pytest --collect-only` or file existence checks.
- 预期输出或状态变化：`tests/test_memory_env_tool.py` does not exist; no collected test name contains `memory_owner_lifecycle`.
- 断言重点：No stale lifecycle test remains.
- 测试类型：repo consistency.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_memory_lifecycle_tests_are_removed`.

### `MRM-GREP-001`: final active-surface grep gate

- 覆盖需求：`REQ-001`, `REQ-025`, `REQ-026`, `REQ-028`, `REQ-032`, `REQ-033`
- 场景：No active runtime/docs/contracts/launcher surfaces retain memory runtime behavior text.
- 前置条件：Implementation complete.
- 输入：Final grep command from section 7.
- 预期输出或状态变化：No matches in active files.
- 断言重点：Gate scans active runtime-facing surfaces only (tests are excluded so intentional rejection assertions can remain).
- 测试类型：verification command gate.
- 建议测试文件路径和测试名称：Command gate recorded in final implementation verification.

## 5. 负向与边界测试

- 缺失数据：`MRM-DISPATCH-001` sends valid-looking memory payload to unsupported tool; `MRM-EVIDENCE-001` sends memory target with no memory service; `MRM-HANDOFF-001` sends retired `memory_ids`.
- 无效状态：`MRM-OLD-001` places legacy memory JSON files on disk; active context/projection/cleanup ignore them.
- 重复操作：Run `env.tool` memory rejection twice and assert state snapshots remain identical both times; run cleanup plan before and after old memory file creation and assert memory paths remain unmanaged.
- 顺序敏感行为：Create artifact evidence before memory rejection in `MRM-EVIDENCE-001` to prove artifact target still works and memory target fails independently.
- 空输入：`context.get {}` succeeds without memory sections; `context.get {"memory_kind": ""}` rejects unsupported field because the field itself is retired.
- 空集合：Workspace projection with no tasks/artifacts/handoffs returns no `memories` top-level key, not an empty `memories: []`.
- 空记录：Old memory directory may be empty; projection and cleanup still do not include it.
- 空配置：Manifest without memory permissions loads; synthetic memory permission is rejected.
- 权限异常：Foreign artifact evidence rejection still works; memory target rejection is target-type rejection rather than buddy-scope memory rejection.
- 路径异常：Old `buddyswitch/objects/memories` directory can exist as regular dir; launcher does not symlink it; cleanup does not delete it.
- 外部依赖：Browser evidence CLI target choices are checked via argparse without requiring browser or broker availability.

## 6. 作弊防护

- Exact set assertions prevent implementation from hiding memory by filtering output while leaving registry entries.
- Broker tests snapshot runtime state before and after unsupported memory requests, preventing a handler from writing and then returning an error.
- Old memory files are written directly by tests, not through removed helpers, so implementation cannot pass by only deleting creation code.
- Tests verify both positive artifact evidence and negative memory evidence in the same suite, preventing broad evidence disablement.
- Source refs are checked at both service normalizer and store validator levels, preventing only one layer from rejecting memory.
- Handoff tests inspect response, saved JSON, and projection shape, preventing an implementation from only hiding `memory_ids` in one layer.
- CLI tests assert invalid choice behavior and help text, preventing a hidden CLI command from remaining undocumented.
- Final grep gate catches stale runtime/docs/contracts/launcher guidance strings that behavioral tests might not execute.
- Non-memory regression tests keep task/track/artifact/handoff/buddybox/context/search paths alive, preventing removal by over-broad deletion.
- No test only asserts that a function was called; all key assertions inspect output JSON, file system state, saved object content, or command output.

## 7. 验证命令清单

Focused tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_memory_removal_contract.py tests/test_env_tool_router.py tests/test_turn_runtime.py tests/test_prepare_runtime_context.py tests/test_runless_runtime_contract.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_response_contract.py -q
```

Runtime service tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_handoff_env_tool.py tests/test_buddybox_env_tool.py tests/test_context_binding_env_tool.py tests/test_evidence_env_tool.py tests/test_search_env_tool.py -q
```

Projection, launcher, cleanup, docs:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py tests/test_parallel_contracts.py tests/test_console_app_contract.py tests/test_cleanup_system.py tests/test_env_manifest_v2.py tests/test_repo_consistency.py tests/test_runtime_agents.py tests/test_runtime_skills.py -q
```

Broader verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py tests/test_env_layer_end_to_end.py tests/test_host_decision_surface_product_mode.py tests/test_market_browser_evidence.py tests/test_output_schema_boundaries.py tests/test_buddy_env_profiles.py tests/test_buddy_env_sandbox.py -q
```

Final required verification:

```bash
pwd
git branch --show-current
git status --short
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_memory_removal_contract.py tests/test_env_tool_router.py tests/test_turn_runtime.py tests/test_prepare_runtime_context.py tests/test_runless_runtime_contract.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_response_contract.py tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_handoff_env_tool.py tests/test_buddybox_env_tool.py tests/test_context_binding_env_tool.py tests/test_evidence_env_tool.py tests/test_search_env_tool.py tests/test_buddyswitch_launcher.py tests/test_parallel_contracts.py tests/test_console_app_contract.py tests/test_cleanup_system.py tests/test_env_manifest_v2.py tests/test_repo_consistency.py tests/test_runtime_agents.py tests/test_runtime_skills.py tests/test_runtime_broker.py tests/test_env_layer_end_to_end.py tests/test_host_decision_surface_product_mode.py tests/test_market_browser_evidence.py tests/test_output_schema_boundaries.py tests/test_buddy_env_profiles.py tests/test_buddy_env_sandbox.py -q
rg -n "memory|memories|memory_ids|memory_kind|MEMORY_|create_memory|get_memory|list_memories|update_memory|memory\\." README.md scripts framework buddyswitch tools projects/app/README.md -g '!docs/memo/**' -g '!docs/spec/2026-05-14-*' -g '!docs/spec/2026-05-15-memory-removal-*'
```

Expected final command results:

- `pwd` prints `/Users/chen/Dev/buddyswitch/.worktrees/dev2258`.
- `git branch --show-current` prints `dev2258`.
- Pytest command passes.
- Final grep returns no active hits.
