# Buddybox Local Workspace Test Plan

## 1. 测试设计原则

- Tests start from the source memo's product semantics: buddybox is the active buddy's private local working directory, not shared product state, not a handoff transport, and not visible to other buddies.
- Tests validate external observable behavior: env.tool JSON responses, CLI help, filesystem state, persisted JSON records, context payloads, workspace projection JSON, console normalization, launcher-created paths, sandbox config, docs/guidance text, and grep gates.
- Tests verify behavior and state, not internal calls. A passing implementation must write to the correct root, reject wrong identities, remove old projection fields, and preserve structured feedback.
- Tests must not be derived from future implementation details. They assert the public contract from the memo: privacy boundary, local root, conditional artifact/readable-reference guidance for product-readable content, active-buddy-only operations, and no cross-buddy buddybox read grant.
- Semantic tests verify hard boundaries without over-constraining the Codex CLI host. They must allow multiple safe next actions and must not require artifact creation after ordinary buddybox operations.
- Tests use multiple buddies (`pm`, `dev`, `design`) so PM cannot pass as a privileged exception and implementation cannot hard-code one buddy.
- Tests cover text and binary payloads, create and overwrite, missing files, old-root files, repeated delete, list filters, path traversal, foreign prefixes, empty roots, and cross-buddy handoff misuse.
- Manual launcher checks are supplemental; automated focused tests, broader regression tests, and grep gates are completion gates.

## 2. 需求覆盖矩阵

All requirements are suitable for automated testing. The manual launcher smoke check validates real instance behavior but does not replace automated proof.

| Requirement | Automated coverage |
| --- | --- |
| `REQ-001` | `BBX-SEM-001`, `BBX-GUIDANCE-001`, `BBX-GREP-001` |
| `REQ-002` | `BBX-STORAGE-001`, `BBX-LAUNCHER-001`, `BBX-GREP-001` |
| `REQ-003` | `BBX-OLDROOT-001`, `BBX-CLEANUP-001`, `BBX-GREP-001` |
| `REQ-004` | `BBX-OLDROOT-001`, `BBX-CLEANUP-001` |
| `REQ-005` | `BBX-REG-001`, `BBX-DESC-001`, `BBX-CLI-001` |
| `REQ-006` | `BBX-DESC-001`, `BBX-CONTEXT-001` |
| `REQ-007` | `BBX-DESC-001` |
| `REQ-008` | `BBX-DESC-001`, `BBX-CONTEXT-001` |
| `REQ-009` | `BBX-LIST-001` |
| `REQ-010` | `BBX-LIST-001`, `BBX-FOREIGN-001` |
| `REQ-011` | `BBX-READ-001`, `BBX-FOREIGN-001` |
| `REQ-012` | `BBX-WRITE-001`, `BBX-STORAGE-001`, `BBX-RESPONSE-001` |
| `REQ-013` | `BBX-DELETE-001` |
| `REQ-014` | `BBX-RESPONSE-001` |
| `REQ-015` | `BBX-RESPONSE-001`, `BBX-NEGATIVE-001` |
| `REQ-016` | `BBX-SEM-001`, `BBX-SEM-003` |
| `REQ-017` | `BBX-SEM-001`, `BBX-SEM-003` |
| `REQ-018` | `BBX-SEM-002`, `BBX-GREP-001` |
| `REQ-019` | `BBX-CONTEXT-001` |
| `REQ-020` | `BBX-CONTEXT-001` |
| `REQ-021` | `BBX-CONTEXT-002` |
| `REQ-022` | `BBX-CONTEXT-001` |
| `REQ-023` | `BBX-PROJECTION-001`, `BBX-CONSOLE-001` |
| `REQ-024` | `BBX-LAUNCHER-001` |
| `REQ-025` | `BBX-SANDBOX-001` |
| `REQ-026` | `BBX-PROFILE-001`, `BBX-GUIDANCE-001`, `BBX-DOC-001` |
| `REQ-027` | `BBX-RUNTIME-AGENTS-001`, `BBX-GUIDANCE-001` |
| `REQ-028` | `BBX-HANDOFF-001`, `BBX-PROJECTION-001` |
| `REQ-029` | `BBX-HANDOFF-001`, `BBX-SEM-003`, `BBX-ARTIFACT-001` |
| `REQ-030` | `BBX-SOURCEREF-001`, `BBX-SOURCEREF-002` |
| `REQ-031` | `BBX-HANDOFF-002`, `BBX-SEM-003` |
| `REQ-032` | `BBX-SOURCEREF-002`, `BBX-ARTIFACT-001` |
| `REQ-033` | `BBX-MANIFEST-001`, `BBX-FOREIGN-001` |
| `REQ-034` | `BBX-REGRESSION-001`, `BBX-E2E-001` |
| `REQ-035` | `BBX-WORKTREE-001` |
| `REQ-036` | `BBX-GIT-001` |

## 3. 测试分层

### 单元测试

Purpose: prove registry, semantics, path normalization, source_refs normalization, profile validation, and projection contract shape without launching a broker.

Coverage:

- `scripts/env/tools/contracts.py`
- `scripts/env/tools/semantics.py`
- `scripts/env/services/buddybox.py` helper functions
- `scripts/env/services/source_refs.py`
- `scripts/env_store.py`
- `scripts/env_profiles.py`
- `framework/contracts/workspace-projection.json`

Commands:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_semantic_contract.py tests/test_env_store_v2.py tests/test_buddy_env_profiles.py tests/test_parallel_contracts.py -q
```

### 集成测试

Purpose: prove broker-routed env.tool behavior enforces active-buddy-only boundaries and writes the expected runtime state.

Coverage:

- `runtime_kernel.broker.dispatch_runtime_request`
- `scripts/env/tools/router.py`
- `scripts/env/tools/dispatch.py`
- `scripts/env/services/buddybox.py`
- `scripts/env/services/context.py`
- `scripts/env/services/handoffs.py`
- `scripts/env/services/artifacts.py`
- `tests.runtime_root_test_helper.RuntimeWorkspaceTestMixin`

Commands:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddybox_env_tool.py tests/test_context_binding_env_tool.py tests/test_handoff_env_tool.py tests/test_artifact_env_tool.py tests/test_env_tool_response_contract.py tests/test_runtime_tool_feedback.py -q
```

### CLI、API、UI 或主路径运行测试

Purpose: verify public command surfaces and visible data shapes.

Coverage:

- `python3 scripts/env/client.py buddybox desc --help`
- `python3 scripts/env/client.py buddybox list --help`
- `python3 scripts/env/client.py context summarize --help`
- `workspace_data.build_workspace_data()`
- `framework/console/app.js`
- launcher tests around `./buddyswitch-codex instance start --buddy pm`

Commands:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_console_app_contract.py tests/test_buddyswitch_launcher.py tests/test_buddy_env_sandbox.py tests/test_runless_runtime_contract.py -q
python3 scripts/env/client.py buddybox desc --help
python3 scripts/env/client.py context summarize --help
```

### 回归测试

Purpose: prove remaining runless product paths still work after buddybox boundary correction.

Coverage:

- task/track/artifact/handoff/context/evidence/search env tools
- env manifest and router consistency
- launcher workspace setup
- cleanup backend boundaries
- repo consistency gates

Commands:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_handoff_env_tool.py tests/test_context_binding_env_tool.py tests/test_evidence_env_tool.py tests/test_search_env_tool.py tests/test_env_tool_router.py tests/test_env_manifest_v2.py tests/test_cleanup_system.py tests/test_repo_consistency.py -q
```

### 手动验证

Purpose: confirm a real launcher-managed instance sees only active buddy local buddybox semantics.

Steps:

1. Run `pwd` and confirm `/Users/chen/Dev/buddyswitch/.worktrees/dev2258`.
2. Run `git branch --show-current` and confirm `dev2258`.
3. Run `./buddyswitch-codex instance start --buddy pm`.
4. In the launched workspace, run `python3 scripts/env/client.py buddybox desc`.
5. Confirm the response contains `logical_root="buddyswitch/local/buddybox/pm"` and the privacy facts from `REQ-008`: active-buddy private local directory, other buddies cannot list/read/write/delete it, and artifact guidance is conditional on product-readable need.
6. Run `python3 scripts/env/client.py buddybox list --path dev`.
7. Confirm the response rejects the foreign prefix with `state_changed=false`.
8. Confirm the workspace contains `buddyswitch/local/buddybox/pm` and does not expose `buddyswitch/local/buddybox/dev` or `buddyswitch/content/buddybox`.

## 4. 详细测试用例

### `BBX-WORKTREE-001`: worktree guard

- 覆盖需求：`REQ-035`
- 用户 / 系统场景：Implementation must run in dev2258 and not main.
- 前置条件：Repository checkout exists.
- 输入：`pwd`, `git branch --show-current`, `git status --short`.
- 预期输出或状态变化：cwd is `/Users/chen/Dev/buddyswitch/.worktrees/dev2258`; branch is `dev2258`; no main worktree path is changed.
- 断言重点：Worktree isolation is confirmed before implementation and final report.
- 测试类型：manual command guard plus repo consistency.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_worktree_isolated_for_dev2258`.

### `BBX-REG-001`: registry exposes buddybox.desc

- 覆盖需求：`REQ-005`
- 用户 / 系统场景：Host discovers buddybox through runtime-visible contracts.
- 前置条件：Import `env.tools.contracts`.
- 输入：`contracts.supported_actions("buddybox")`, `contracts.env_tools_description()["buddybox"]`, `contracts.operation_semantics()`.
- 预期输出或状态变化：Actions equal `{"desc","list","read","write","delete"}`; scope says active-buddy private local workspace; `buddybox.desc` is read-only and returns `buddybox_desc`.
- 断言重点：Exact action set prevents hidden missing desc or stale extra actions.
- 测试类型：unit contract.
- 建议测试文件路径和测试名称：`tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_registry_semantics_cover_every_registered_tool_and_action`.

### `BBX-CLI-001`: CLI exposes buddybox desc

- 覆盖需求：`REQ-005`
- 用户 / 系统场景：Skill-facing host discovers desc from CLI help.
- 前置条件：Run from repo root.
- 输入：`python3 scripts/env/client.py buddybox --help`, `python3 scripts/env/client.py buddybox desc --help`.
- 预期输出或状态变化：Top-level buddybox help lists `desc`; desc help exits 0 and does not require path or payload.
- 断言重点：CLI route exists before broker invocation.
- 测试类型：CLI.
- 建议测试文件路径和测试名称：`tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_env_client_help_exposes_runless_resources`.

### `BBX-DESC-001`: desc returns safe private workspace description

- 覆盖需求：`REQ-005`, `REQ-006`, `REQ-007`, `REQ-008`
- 用户 / 系统场景：Active buddy asks what buddybox means.
- 前置条件：Runtime sandbox active buddy `dev`; local root has `dev/notes/a.md`.
- 输入：Broker `env.tool` request `tool="buddybox"`, `action="desc"`, `args={}`.
- 预期输出或状态变化：`ok=true`; `state_changed=false`; `durability="none"`; `buddybox_desc.active_buddy="dev"`; `logical_root="buddyswitch/local/buddybox/dev"`; privacy message contains all facts from `REQ-008` without presenting artifact creation as the only next action; summary reports one file and byte count; no `files`, `content`, or `content_base64`.
- 断言重点：Description is context-safe and contains the complete semantic boundary.
- 测试类型：broker integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_desc_returns_private_local_workspace_summary`.

### `BBX-STORAGE-001`: writes use local root only

- 覆盖需求：`REQ-002`, `REQ-003`, `REQ-012`
- 用户 / 系统场景：PM writes a private local draft.
- 前置条件：Runtime sandbox active buddy `pm`.
- 输入：`buddybox.write` with `{"path":"pm/prototypes/hero.html","content":"<html>hero</html>"}`.
- 预期输出或状态变化：File exists at `buddyswitch/local/buddybox/pm/prototypes/hero.html`; old path `buddyswitch/content/buddybox/pm/prototypes/hero.html` does not exist; response says private local file was created and no artifact/handoff/task/track was created.
- 断言重点：Filesystem state proves root replacement.
- 测试类型：broker integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_text_and_binary_lifecycle`.

### `BBX-OLDROOT-001`: old content root is unmanaged and unread

- 覆盖需求：`REQ-003`, `REQ-004`, `REQ-011`
- 用户 / 系统场景：A stale file remains under old content root.
- 前置条件：Runtime sandbox contains only `buddyswitch/content/buddybox/pm/old.md`.
- 输入：`buddybox.list` as `pm`; `buddybox.read path="pm/old.md"` as `pm`.
- 预期输出或状态变化：List excludes `pm/old.md`; read returns not found; stale file remains on disk; no local root file is synthesized.
- 断言重点：No compatibility read or migration occurs.
- 测试类型：integration plus filesystem assertion.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_old_content_buddybox_root_is_not_active_storage`.

### `BBX-LIST-001`: list returns active-buddy summaries only

- 覆盖需求：`REQ-009`, `REQ-010`
- 用户 / 系统场景：Dev lists private local files.
- 前置条件：Runtime sandbox has `dev/a.md`, `dev/nested/b.md`, and `pm/hidden.md` under local buddybox.
- 输入：`buddybox.list args={"recursive":true}` as `dev`; `buddybox.list args={"path":"dev/nested","recursive":true}` as `dev`.
- 预期输出或状态变化：Only dev paths returned; rows contain `buddy`, `path`, `size_bytes`, `updated_at`, `content_type`, `private_to_buddy`; no `content`, `content_base64`, or `source_ref`.
- 断言重点：List is summary-only and active-buddy-only.
- 测试类型：broker integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_list_returns_active_private_summaries_without_content`.

### `BBX-READ-001`: read returns text or base64 without product mutation

- 覆盖需求：`REQ-011`
- 用户 / 系统场景：Active buddy reads text and binary files.
- 前置条件：Write `pm/readme.md` through `buddybox.write`; write `pm/assets/snapshot.bin` through `content_base64`.
- 输入：`buddybox.read path="pm/readme.md"`; `buddybox.read path="pm/assets/snapshot.bin"`.
- 预期输出或状态变化：Text returns `encoding="utf-8"` and `content`; binary returns `encoding="base64"` and `content_base64`; both have `state_changed=false`, `durability="none"`, and no product object changes.
- 断言重点：Encoding behavior is preserved while semantics are corrected.
- 测试类型：broker integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_text_and_binary_lifecycle`.

### `BBX-WRITE-001`: write reports created versus overwritten

- 覆盖需求：`REQ-012`, `REQ-014`
- 用户 / 系统场景：Active buddy updates a local draft.
- 前置条件：Runtime sandbox active buddy `pm`.
- 输入：First write `pm/logs/out.txt` with `v1`; second write same path with `v2`.
- 预期输出或状态变化：First response has `overwrote=false` and `created_ids=["pm/logs/out.txt"]`; second has `overwrote=true` and `updated_ids=["pm/logs/out.txt"]`; final content is `v2`.
- 断言重点：Response describes actual local file transition.
- 测试类型：broker integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_overwrite_and_repeat_delete_are_explicit`.

### `BBX-DELETE-001`: delete is per-file and repeat-safe

- 覆盖需求：`REQ-013`
- 用户 / 系统场景：Active buddy deletes one private local file twice.
- 前置条件：File `pm/logs/out.txt` exists; directory `pm/logs` exists.
- 输入：`buddybox.delete path="pm/logs/out.txt"` twice; `buddybox.delete path="pm/logs"` once.
- 预期输出或状态变化：First delete returns `deleted=true`; second returns `deleted=false` and `state_changed=false`; directory delete is rejected; sibling files remain.
- 断言重点：No bulk cleanup or directory deletion behavior is introduced.
- 测试类型：broker integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_overwrite_and_repeat_delete_are_explicit`.

### `BBX-FOREIGN-001`: PM has no foreign buddybox exception

- 覆盖需求：`REQ-010`, `REQ-011`, `REQ-033`
- 用户 / 系统场景：PM attempts to inspect Dev's private buddybox.
- 前置条件：Runtime sandbox local root has `dev/report.md`.
- 输入：As `pm`, call `buddybox.list path="dev"`, `buddybox.read path="dev/report.md"`, `buddybox.write path="dev/report.md"`, `buddybox.delete path="dev/report.md"`.
- 预期输出或状态变化：All calls fail with structured rejection; no dev file content returned or mutated; response text contains `private` and `active buddy`; `state_changed=false`.
- 断言重点：No buddy type can bypass active-buddy-only boundary.
- 测试类型：broker integration negative.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_pm_cannot_read_list_write_or_delete_foreign_buddybox_paths`.

### `BBX-NEGATIVE-001`: invalid paths and payloads reject without mutation

- 覆盖需求：`REQ-015`
- 用户 / 系统场景：Host sends invalid path and content combinations.
- 前置条件：Runtime sandbox active buddy `pm`.
- 输入：Paths `""`, `"/tmp/x.txt"`, `"../x.txt"`, `"pm/../../x.txt"`; write with neither content nor content_base64; write with both; read with invalid encoding.
- 预期输出或状态变化：Each returns `ok=false`, code `E_BUDDYBOX_SCOPE` or `E_BUDDYBOX_PAYLOAD`, structured feedback fields present, no file created.
- 断言重点：Error handling is explicit and state preserving.
- 测试类型：broker integration negative.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_rejects_path_traversal_foreign_scope_and_bad_payloads`.

### `BBX-RESPONSE-001`: feedback describes real impact

- 覆盖需求：`REQ-014`, `REQ-015`
- 用户 / 系统场景：Host reads response to decide whether product state changed.
- 前置条件：Runtime sandbox active buddy `pm`.
- 输入：`buddybox.write`, `buddybox.read`, `buddybox.list`, foreign read rejection.
- 预期输出或状态变化：Success summaries distinguish local file change from product object changes; read/list say no product state changed; rejection impact says no local buddybox file or product object changed.
- 断言重点：Assertions inspect response text and canonical fields, not only `ok`.
- 测试类型：response contract.
- 建议测试文件路径和测试名称：`tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_buddybox_responses_describe_private_local_impact`.

### `BBX-SEM-001`: semantics require private/local vocabulary

- 覆盖需求：`REQ-001`, `REQ-016`, `REQ-017`
- 用户 / 系统场景：Host reads `env_tools_description()` to choose between buddybox and artifact.
- 前置条件：Import `contracts.env_tools_description()`.
- 输入：Serialized buddybox capability and action semantics.
- 预期输出或状态变化：Text includes `active buddy`, `private`, `local workspace` or `local working directory`, `not collaborative`, `not visible to other buddies`, `not product object`, and conditional `use artifact for product-readable deliverables` wording.
- 断言重点：All action rows and capability row carry product meaning.
- 测试类型：unit semantic contract.
- 建议测试文件路径和测试名称：`tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_buddybox_semantics_explain_private_local_workspace_boundary`.

### `BBX-SEM-002`: semantics reject old ambiguous wording

- 覆盖需求：`REQ-018`
- 用户 / 系统场景：A regression reintroduces vague durable-output wording.
- 前置条件：Import semantic projection.
- 输入：Serialized buddybox, context and handoff semantics.
- 预期输出或状态变化：No unqualified phrases `durable output`, `buddy-owned files`, `readable scope`, or source_ref language implying read authority.
- 断言重点：Prevents passing by adding only one good sentence.
- 测试类型：unit semantic regression.
- 建议测试文件路径和测试名称：`tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_buddybox_semantics_reject_old_ambiguous_wording`.

### `BBX-SEM-003`: semantics preserve host decision space

- 覆盖需求：`REQ-008`, `REQ-016`, `REQ-017`, `REQ-029`, `REQ-031`
- 用户 / 系统场景：Codex CLI host reads buddybox semantics and decides whether to keep working locally, inspect local files, delete local files, create an artifact, or refer to another readable product/external object.
- 前置条件：Import buddybox action semantics and `buddybox.desc` response builder.
- 输入：Serialized buddybox capability/action semantics and sample desc response for active buddy `pm`.
- 预期输出或状态变化：Semantics state the privacy boundary and include artifact/readable-reference guidance only as a conditional option for product-readable or cross-buddy-readable content; ordinary `desc/list/read/write/delete` success semantics do not say artifact creation is mandatory.
- 断言重点：Assert no phrase such as `only next action`, `always create artifact`, `must create artifact after buddybox.write`, or `artifact-required-for-cross-buddy-readable-content`; assert `allowed_next_actions` contains at least two non-artifact local workspace actions and one conditional readable-content option.
- 测试类型：unit semantic contract.
- 建议测试文件路径和测试名称：`tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_buddybox_semantics_keep_host_decision_space`.

### `BBX-CONTEXT-001`: context exposes buddybox_desc only

- 覆盖需求：`REQ-006`, `REQ-008`, `REQ-019`, `REQ-020`, `REQ-022`
- 用户 / 系统场景：Host calls context before deciding next action.
- 前置条件：Runtime sandbox active buddy `dev`; local buddybox contains `dev/notes/context.txt`.
- 输入：`context.get args={}` and `context.summarize args={}`.
- 预期输出或状态变化：Both responses contain `buddybox_desc`; both omit `buddybox_files`; no file content appears; readiness uses `has_buddybox_workspace`; state summary count reflects active file.
- 断言重点：Context remains orientation, not data plane.
- 测试类型：broker integration.
- 建议测试文件路径和测试名称：`tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_uses_buddybox_desc_not_file_projection`.

### `BBX-CONTEXT-002`: context source descriptor is local and tool-backed

- 覆盖需求：`REQ-021`
- 用户 / 系统场景：Host lists context sources.
- 前置条件：Runtime sandbox active buddy `dev`.
- 输入：`context.list_sources args={}`.
- 预期输出或状态变化：`sources["buddybox"].scope` says active-buddy private local workspace; source_of_truth says `buddyswitch/local/buddybox/<active_buddy>/**`; description directs file operations to buddybox tools; no old content path appears.
- 断言重点：Context metadata no longer teaches product-content semantics.
- 测试类型：broker integration.
- 建议测试文件路径和测试名称：`tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_list_sources_describes_buddybox_private_local_workspace`.

### `BBX-PROJECTION-001`: workspace projection excludes buddybox file rows

- 覆盖需求：`REQ-023`, `REQ-028`
- 用户 / 系统场景：Console API builds workspace projection.
- 前置条件：Runtime sandbox has tracks, tasks, artifacts, handoffs and local buddybox files for multiple buddies.
- 输入：`workspace_data.build_workspace_data()`.
- 预期输出或状态变化：Payload keys match contract without `content_root` and `buddybox_files`; handoff rows omit `buddybox_paths`; local buddybox files do not affect projection.
- 断言重点：Projection cannot leak all buddybox roots.
- 测试类型：projection contract integration.
- 建议测试文件路径和测试名称：`tests/test_parallel_contracts.py::WorkspaceProjectionContractTests::test_contract_matches_runless_workspace_projection`.

### `BBX-CONSOLE-001`: console has no buddybox_files dependency

- 覆盖需求：`REQ-023`
- 用户 / 系统场景：Console loads workspace data.
- 前置条件：JS contract test reads `framework/console/app.js`.
- 输入：App source and normalization expectations.
- 预期输出或状态变化：Source does not contain `buddybox_files`; normalized workspace does not create that key.
- 断言重点：UI cannot silently keep old projection dependency.
- 测试类型：UI contract/static.
- 建议测试文件路径和测试名称：`tests/test_console_app_contract.py::ConsoleAppContractTests::test_console_workspace_normalization_excludes_buddybox_files`.

### `BBX-HANDOFF-001`: buddybox_paths are rejected and omitted

- 覆盖需求：`REQ-028`, `REQ-029`
- 用户 / 系统场景：Design tries to hand off a private buddybox file to Dev.
- 前置条件：Design owns track, task, artifact, and private local buddybox file.
- 输入：`handoff.validate` and `handoff.create` with `buddybox_paths=["design/handoff/handoff.txt"]`.
- 预期输出或状态变化：Both calls reject with `E_HANDOFF_PAYLOAD`; no handoff file is created; handoff using artifact content succeeds and returned row has no `buddybox_paths`.
- 断言重点：Buddybox is not a cross-buddy transport.
- 测试类型：broker integration negative and positive.
- 建议测试文件路径和测试名称：`tests/test_handoff_env_tool.py::HandoffEnvToolTests::test_handoff_rejects_buddybox_paths_as_private_workspace_payload`.

### `BBX-HANDOFF-002`: handoff rejects buddybox source_refs

- 覆盖需求：`REQ-031`
- 用户 / 系统场景：A source buddy encodes buddybox path as handoff source_ref.
- 前置条件：Design owns valid track/task/artifact.
- 输入：`handoff.validate` with `source_refs=[{"type":"buddybox","path":"design/private.md"}]`.
- 预期输出或状态变化：Rejected with `E_SOURCE_REFS`; message says buddybox source_refs are private provenance, not read grants, and readable handoff content must come from artifact content or another explicit product/external reference chosen by the host.
- 断言重点：source_refs cannot become a cross-buddy read hint.
- 测试类型：broker integration negative.
- 建议测试文件路径和测试名称：`tests/test_handoff_env_tool.py::HandoffEnvToolTests::test_handoff_rejects_buddybox_source_ref`.

### `BBX-SOURCEREF-001`: buddybox source_refs enforce active prefix

- 覆盖需求：`REQ-030`
- 用户 / 系统场景：Dev records provenance from buddybox.
- 前置条件：Runtime sandbox active buddy `dev`.
- 输入：Normalize `[{"type":"buddybox","path":"pm/x.md"}]` with active buddy `dev`; normalize `[{"type":"buddybox","path":"dev/x.md"}]`.
- 预期输出或状态变化：PM path raises `ValueError`; Dev path succeeds.
- 断言重点：Private provenance cannot point at another buddy.
- 测试类型：unit.
- 建议测试文件路径和测试名称：`tests/test_env_store_v2.py::SourceRefsV2Tests::test_buddybox_source_refs_require_active_buddy_prefix`.

### `BBX-SOURCEREF-002`: artifact provenance is private and not read grant

- 覆盖需求：`REQ-030`, `REQ-032`
- 用户 / 系统场景：PM creates an artifact from a private local buddybox draft.
- 前置条件：PM task exists; local buddybox draft exists.
- 输入：`artifact.create_revision` with `source_refs=[{"type":"buddybox","path":"pm/drafts/prd.md"}]` and product-readable content.
- 预期输出或状态变化：Saved artifact source_ref has `private_to_buddy="pm"` and `read_grant=false`; artifact content body is present.
- 断言重点：Provenance and content access are separate.
- 测试类型：artifact service integration.
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_buddybox_source_ref_is_private_provenance_not_read_grant`.

### `BBX-ARTIFACT-001`: cross-buddy deliverable uses artifact content

- 覆盖需求：`REQ-029`, `REQ-032`
- 用户 / 系统场景：Design wants Dev to consume a prototype brief created from local files.
- 前置条件：Design local buddybox contains `design/prototype/notes.md`.
- 输入：Create artifact with content copied into artifact body and private buddybox source_ref; create handoff with artifact id only; Dev calls `artifact.get`; Dev attempts buddybox read of design path.
- 预期输出或状态变化：Dev can read artifact according to artifact rules; Dev cannot read design buddybox path.
- 断言重点：Cross-buddy readability is carried by artifact, not buddybox path.
- 测试类型：E2E integration.
- 建议测试文件路径和测试名称：`tests/test_env_layer_end_to_end.py::EnvLayerEndToEndTests::test_cross_buddy_deliverable_uses_artifact_not_buddybox_path`.

### `BBX-PROFILE-001`: profiles use local buddybox root

- 覆盖需求：`REQ-026`
- 用户 / 系统场景：Profile validator loads all buddy profiles.
- 前置条件：Manifest contains five buddies.
- 输入：`env_profiles.require_env_profile()` for each buddy.
- 预期输出或状态变化：Each `profile["buddybox"]["root"]` equals `buddyswitch/local/buddybox/<buddy>`; temp profile with old content root fails validation.
- 断言重点：Profile source used by launcher sandbox is correct.
- 测试类型：unit/profile contract.
- 建议测试文件路径和测试名称：`tests/test_buddy_env_profiles.py::BuddyEnvProfilesTests::test_profiles_validate_with_matrix_rules`.

### `BBX-MANIFEST-001`: no buddybox permission special case

- 覆盖需求：`REQ-033`
- 用户 / 系统场景：Manifest permission surface is checked.
- 前置条件：Load `buddyswitch/manifest.toml`.
- 输入：All buddy permission lists.
- 预期输出或状态变化：Every buddy has same `buddybox.read`, `buddybox.write`, `buddybox.delete`; no `buddybox.read_foreign`, `buddybox.pm_override`, or buddy-type-specific buddybox permission.
- 断言重点：Permission data cannot reintroduce PM special casing.
- 测试类型：manifest contract.
- 建议测试文件路径和测试名称：`tests/test_env_manifest_v2.py::EnvManifestV2Tests::test_buddy_permissions_have_no_buddybox_special_cases`.

### `BBX-SANDBOX-001`: sandbox writes active buddy local root only

- 覆盖需求：`REQ-025`
- 用户 / 系统场景：Launcher patches Codex config.
- 前置条件：Temp shared root, instance root, workspace dir, project workspace dir.
- 输入：`tools/launcher/codex_config.py patch` through existing test helper.
- 预期输出或状态变化：Writable paths include `workspace/buddyswitch/local/buddybox/pm` for PM and `workspace/buddyswitch/local/buddybox/dev` for Dev; old content path absent; other buddy local roots absent; shared state root remains non-writable.
- 断言重点：Sandbox matches privacy boundary.
- 测试类型：launcher config integration.
- 建议测试文件路径和测试名称：`tests/test_buddy_env_sandbox.py::BuddyEnvSandboxTests::test_profile_mode_permissions_include_active_buddy_local_buddybox_only`.

### `BBX-LAUNCHER-001`: instance workspace projects only active buddy local buddybox

- 覆盖需求：`REQ-024`
- 用户 / 系统场景：Product-mode instance starts for PM.
- 前置条件：Fake Codex launcher test environment.
- 输入：`./buddyswitch-codex instance start --buddy pm` through launcher test.
- 预期输出或状态变化：Object dirs are shared state symlinks; `workspace/buddyswitch/local/buddybox/pm` exists and points to active PM local root; `workspace/buddyswitch/local/buddybox/dev` absent; `workspace/buddyswitch/content/buddybox` absent.
- 断言重点：No global buddybox projection is visible.
- 测试类型：launcher integration.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_creates_buddy_locked_workspace_and_runtime_surface`.

### `BBX-RUNTIME-AGENTS-001`: runtime AGENTS enforce private semantics

- 覆盖需求：`REQ-027`
- 用户 / 系统场景：Runtime AGENTS template is validated for each buddy.
- 前置条件：Checked-in templates under `tools/launcher/assets/buddies`.
- 输入：`python3 scripts/runtime_agents.py validate-all`.
- 预期输出或状态变化：Each template mentions private local workspace, active buddy root, other buddies cannot read, conditional artifact/readable-reference guidance for product-readable content, and direct edit prohibition for local buddybox path.
- 断言重点：Host guidance cannot teach bypassing tools.
- 测试类型：template validator.
- 建议测试文件路径和测试名称：`tests/test_runtime_agents.py::RuntimeAgentsValidationTests::test_runtime_agents_point_to_private_local_buddybox_boundary`.

### `BBX-GUIDANCE-001`: guidance has no shared-content wording

- 覆盖需求：`REQ-001`, `REQ-026`, `REQ-027`
- 用户 / 系统场景：A buddy reads framework contract or skill guidance.
- 前置条件：Active docs and skill files checked in.
- 输入：Text from `framework/contracts/*.md`, `tools/launcher/assets/buddies/*/AGENTS.md`, `buddyswitch/skills/**/*.md`.
- 预期输出或状态变化：No active file says buddybox is shared product content or target buddy can consume buddybox files; files mention local root and conditional artifact/readable-reference guidance.
- 断言重点：Guidance aligns with runtime behavior.
- 测试类型：static docs contract.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_active_docs_teach_private_local_buddybox_boundary`.

### `BBX-DOC-001`: architecture docs describe context desc and no projection

- 覆盖需求：`REQ-026`
- 用户 / 系统场景：Developer reads architecture docs.
- 前置条件：Active framework docs exist.
- 输入：`README.md`, `framework/docs/turn-runtime-spec.md`, `framework/docs/interface-spec.md`, `framework/docs/architecture-overview.md`.
- 预期输出或状态变化：Docs describe `buddybox.desc` and private local root; docs state context exposes desc, not file rows; workspace projection docs do not list `buddybox_files`.
- 断言重点：Docs do not contradict contracts.
- 测试类型：static docs contract.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_active_docs_match_buddybox_local_workspace_contract`.

### `BBX-CLEANUP-001`: cleanup does not manage old buddybox content

- 覆盖需求：`REQ-004`
- 用户 / 系统场景：Cleanup is run after stale old-root files exist.
- 前置条件：Temp repo has `buddyswitch/content/buddybox/pm/old.md`, current object files, and manifest.
- 输入：`env_cleanup.build_cleanup_plan(scope="buddy", buddy="pm")` and `scope="all-data"`.
- 预期输出或状态变化：Plan does not include old content buddybox file; cleanup categories exclude `buddybox_files`; skeleton recreation does not create old content root; old file remains unmanaged.
- 断言重点：No cleanup/migration behavior is smuggled in.
- 测试类型：cleanup integration.
- 建议测试文件路径和测试名称：`tests/test_cleanup_system.py::CleanupSystemTests::test_cleanup_ignores_retired_buddybox_content_root`.

### `BBX-E2E-001`: main runless path still works

- 覆盖需求：`REQ-034`
- 用户 / 系统场景：PM creates track/task/artifact, writes private local note, hands off artifact to Dev.
- 前置条件：Runtime sandbox active buddies PM and Dev.
- 输入：Track create, task create, buddybox.write `pm/e2e/notes.md`, artifact.create_revision with content, handoff.create with artifact id only, context.summarize.
- 预期输出或状态变化：Track/task/artifact/handoff objects exist; local buddybox file exists under local root; handoff has no buddybox path; context has buddybox_desc; no old root created.
- 断言重点：Buddybox correction does not break core product loop.
- 测试类型：end-to-end integration.
- 建议测试文件路径和测试名称：`tests/test_env_layer_end_to_end.py::EnvLayerEndToEndTests::test_runless_flow_uses_private_buddybox_and_artifact_handoff`.

### `BBX-REGRESSION-001`: non-buddybox env tools remain stable

- 覆盖需求：`REQ-034`
- 用户 / 系统场景：Existing task/track/artifact/evidence/search behavior runs after buddybox changes.
- 前置条件：Runtime sandbox.
- 输入：Existing focused suites for task, track, artifact, evidence, search and router.
- 预期输出或状态变化：Existing expected behavior passes; no unrelated product behavior changed.
- 断言重点：Scope did not drift.
- 测试类型：regression suite.
- 建议测试文件路径和测试名称：Existing suites: `tests/test_task_env_tool.py`, `tests/test_track_env_tool.py`, `tests/test_artifact_env_tool.py`, `tests/test_evidence_env_tool.py`, `tests/test_search_env_tool.py`, `tests/test_env_tool_router.py`.

### `BBX-GREP-001`: active surface has no retired buddybox tokens

- 覆盖需求：`REQ-001`, `REQ-002`, `REQ-003`, `REQ-018`, `REQ-023`, `REQ-026`
- 用户 / 系统场景：A stale string remains in active code or docs.
- 前置条件：Implementation complete.
- 输入：

```bash
rg -n "BUDDYBOX_CONTENT_DIR|buddyswitch/content/buddybox|buddybox_files|buddybox_paths|durable buddy-owned|readable buddybox scope" README.md AGENTS.md scripts framework buddyswitch tools tests -g '!docs/memo/**' -g '!docs/spec/**'
```

- 预期输出或状态变化：No matches; `rg` exits 1.
- 断言重点：Catches stale docs, tests, contracts and code.
- 测试类型：static grep gate.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_active_buddybox_surface_uses_private_local_workspace_contract`.

### `BBX-GIT-001`: existing dirty changes are not reverted

- 覆盖需求：`REQ-036`
- 用户 / 系统场景：Implementation completes in dirty worktree with existing memory-removal changes.
- 前置条件：Before implementation, record `git status --short`.
- 输入：After implementation, run `git status --short`.
- 预期输出或状态变化：New changes are buddybox implementation/tests/docs; existing memory-removal dirty files remain and are not reverted.
- 断言重点：No destructive cleanup of user changes.
- 测试类型：manual final review.
- 建议测试文件路径和测试名称：Final implementation report includes status summary.

## 5. 负向与边界测试

- 缺失数据：`buddybox.read` missing `path`; `buddybox.write` missing both content fields; `buddybox.desc` with unexpected field.
- 无效状态：old content root contains files; local root missing before first desc/list/write; read target is a directory; malformed base64.
- 重复操作：write same file twice reports overwrite; delete same file twice reports deleted false on second call.
- 顺序敏感行为：list after overwrite sees final size and mtime; delete after read does not leave partial file.
- 空输入和空集合：empty local root desc returns zero counts; list empty root returns empty files list; context with no files still has `buddybox_desc`.
- 权限和路径异常：PM foreign read/list/write/delete rejected; non-PM foreign read rejected; path traversal and absolute paths rejected; `path="dev"` rejected for active `pm`.
- 配置异常：profile with old content root fails validation; sandbox config does not expose old or foreign buddybox roots.
- Cross-buddy misuse：`buddybox_paths` rejected; handoff source_refs with buddybox rejected; artifact source_refs from buddybox are private provenance and not read grants.

## 6. 作弊防护

- Semantic tests require all required vocabulary in capability and action semantics, so one added sentence is insufficient.
- Multiple buddies prevent hard-coding PM or Dev.
- Storage tests seed old and new roots with different contents, so fallback reads or silent migration fail.
- Context tests assert absence of `buddybox_files`, absence of content fields, and presence of `buddybox_desc`.
- Projection tests assert exact payload key order from `workspace-projection.json`.
- Handoff tests cover both `buddybox_paths` and `source_refs.type="buddybox"`.
- Artifact provenance tests assert `private_to_buddy` and `read_grant=false` while also asserting artifact content exists.
- Response tests inspect canonical fields and impact text, not only `ok`.
- Grep gates scan active code, tests, docs and guidance with historical docs excluded.
- Full regression tests run after focused tests.

## 7. 验证命令清单

Focused tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddybox_env_tool.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_semantic_contract.py tests/test_context_binding_env_tool.py tests/test_runtime_tool_feedback.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_handoff_env_tool.py tests/test_env_store_v2.py tests/test_artifact_env_tool.py -q
```

Broader verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_parallel_contracts.py tests/test_console_app_contract.py tests/test_buddy_env_profiles.py tests/test_runtime_agents.py tests/test_buddy_env_sandbox.py tests/test_buddyswitch_launcher.py tests/test_cleanup_system.py tests/test_repo_consistency.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_context_binding_env_tool.py tests/test_evidence_env_tool.py tests/test_search_env_tool.py tests/test_env_tool_router.py tests/test_env_manifest_v2.py -q
```

CLI and static gates:

```bash
python3 scripts/env/client.py buddybox desc --help
python3 scripts/env_profiles.py validate-all
python3 scripts/runtime_agents.py validate-all
rg -n "BUDDYBOX_CONTENT_DIR|buddyswitch/content/buddybox|buddybox_files|buddybox_paths|durable buddy-owned|readable buddybox scope" README.md AGENTS.md scripts framework buddyswitch tools tests -g '!docs/memo/**' -g '!docs/spec/**'
```

Expected grep result: no output and exit code `1`.

Final verification before completion:

```bash
pwd
git branch --show-current
git status --short
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests -q
python3 scripts/env_profiles.py validate-all
python3 scripts/runtime_agents.py validate-all
rg -n "BUDDYBOX_CONTENT_DIR|buddyswitch/content/buddybox|buddybox_files|buddybox_paths|durable buddy-owned|readable buddybox scope" README.md AGENTS.md scripts framework buddyswitch tools tests -g '!docs/memo/**' -g '!docs/spec/**'
```
