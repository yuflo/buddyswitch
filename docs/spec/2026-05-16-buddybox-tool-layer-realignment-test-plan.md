# Buddybox Tool Layer Realignment Test Plan

## 1. 测试设计原则

- Tests start from the source memo's observable product contracts: storage location, env.tool payloads, CLI surface, JSON responses, context discovery payloads, artifact/handoff readability, and guidance text.
- Tests must not be shaped around the future implementation's internal helper names except where unit tests directly validate path-safety primitives.
- Tests verify external behavior and persisted state: filesystem real directory versus symlink, absence from shared state, response JSON fields, CLI args, source_refs records, context output, and grep gates.
- Behavior changes use red-green loops: write the focused test, confirm it fails for the current path/shared-state behavior, implement the smallest direct replacement, rerun the focused test.
- Assertions must validate state and semantics, not just function calls. A passing test must prove the host no longer needs path roots or active buddy prefixes.
- Negative and boundary tests are first-class: invalid logical names, legacy `path`, buddy prefixes, symlink escape, missing files, repeated delete, empty lists, and cross-buddy misuse all need explicit coverage.
- Tests must keep SHARP scope: no generic router, no workflow engine, no prompt-heavy behavior enforcement, no long-lived compatibility acceptance.

## 2. 需求覆盖矩阵

| Requirement | Tests |
| --- | --- |
| `REQ-001` | `BBX-STORAGE-001`, `BBX-SERVICE-001`, `BBX-HOST-001` |
| `REQ-002` | `BBX-STORAGE-001`, `BBX-STORAGE-002`, `BBX-BROKER-001` |
| `REQ-003` | `BBX-STORAGE-001` |
| `REQ-004` | `BBX-STORAGE-003`, `BBX-SERVICE-007` |
| `REQ-005` | `BBX-STORAGE-002` |
| `REQ-006` | `BBX-SERVICE-001`, `BBX-SERVICE-002`, `BBX-CLI-001`, `BBX-SEM-001` |
| `REQ-007` | `BBX-SERVICE-001`, `BBX-CONTEXT-001`, `BBX-CONTEXT-002` |
| `REQ-008` | `BBX-NEGATIVE-001`, `BBX-NEGATIVE-002` |
| `REQ-009` | `BBX-NEGATIVE-003` |
| `REQ-010` | `BBX-SERVICE-003`, `BBX-SERVICE-004` |
| `REQ-011` | `BBX-SERVICE-004` |
| `REQ-012` | `BBX-SERVICE-005`, `BBX-CONTEXT-001` |
| `REQ-013` | `BBX-SERVICE-006` |
| `REQ-014` | `BBX-SERVICE-008`, `BBX-E2E-001` |
| `REQ-015` | `BBX-RESPONSE-001`, `BBX-RESPONSE-002` |
| `REQ-016` | `BBX-RESPONSE-003`, `BBX-HOST-001` |
| `REQ-017` | `BBX-REJECTION-001`, `BBX-REJECTION-002` |
| `REQ-018` | `BBX-REJECTION-003`, `BBX-GUIDANCE-001`, `BBX-GREP-001` |
| `REQ-019` | `BBX-CONTEXT-001`, `BBX-CONTEXT-002`, `BBX-SEM-002` |
| `REQ-020` | `BBX-CONTEXT-002`, `BBX-SEM-003`, `BBX-GREP-001` |
| `REQ-021` | `BBX-SEM-001`, `BBX-SEM-002`, `BBX-CLI-001` |
| `REQ-022` | `BBX-HOST-001`, `BBX-CONTEXT-003` |
| `REQ-023` | `BBX-ARTIFACT-001`, `BBX-E2E-001` |
| `REQ-024` | `BBX-HANDOFF-001`, `BBX-E2E-001` |
| `REQ-025` | `BBX-GREP-002`, `BBX-HOST-001` |
| `REQ-026` | `BBX-GUIDANCE-001`, `BBX-GUIDANCE-002`, `BBX-GREP-001` |
| `REQ-027` | `BBX-BROKER-001`, `BBX-E2E-002` |
| `REQ-028` | `BBX-SERVICE-002`, `BBX-MANIFEST-001` |
| `REQ-029` | All focused test groups plus final broader verification |

All requirements are suitable for automated tests. Manual verification is limited to one optional product-mode smoke command because launching a real interactive Codex instance can depend on local credentials; fake launcher tests remain the required automated proof.

## 3. 测试分层

### 单元测试

Purpose: validate logical-name normalization, source_refs normalization, semantic registry fields, and response helper shape without launching the broker.

Coverage:

- `scripts/env/services/buddybox.py::normalize_logical_name`
- `scripts/env/services/source_refs.py::normalize_source_refs`
- `scripts/env/tools/responses.py::rejection`
- `scripts/env/tools/semantics.py` and `scripts/env/tools/contracts.py`

Run:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_artifact_buddybox_source_ref_is_private_provenance -q
```

### 集成测试

Purpose: validate broker-routed env.tool behavior, filesystem state, product object non-mutation, artifact/handoff boundaries, and context payloads.

Coverage:

- `tests/test_buddybox_env_tool.py`
- `tests/test_context_binding_env_tool.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_artifact_env_tool.py`
- `tests/test_handoff_env_tool.py`

Run:

```bash
python3 -m pytest tests/test_buddybox_env_tool.py tests/test_context_binding_env_tool.py tests/test_env_tool_response_contract.py tests/test_artifact_env_tool.py tests/test_handoff_env_tool.py -q
```

### CLI、API、UI 或主路径运行测试

Purpose: validate launcher workspace construction, CLI argument shape, broker health, sandbox roots, and runless main path.

Coverage:

- `tests/test_buddyswitch_launcher.py`
- `tests/test_buddy_env_sandbox.py`
- `tests/test_runtime_broker.py`
- `tests/test_run_env_tool.py`
- `tests/test_env_layer_end_to_end.py`

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py tests/test_buddy_env_sandbox.py tests/test_runtime_broker.py tests/test_run_env_tool.py tests/test_env_layer_end_to_end.py -q
```

### 回归测试

Purpose: ensure retired path contracts, shared-state projections, old buddybox source refs, and prompt-level SOPs do not return.

Coverage:

- `tests/test_repo_consistency.py`
- `tests/test_runtime_agents.py`
- `tests/test_runtime_skills.py`
- grep command in final verification

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py tests/test_runtime_agents.py tests/test_runtime_skills.py -q
```

### 手动验证

Purpose: optional sanity check against a real product-mode launch after automated tests pass.

Command:

```bash
./buddyswitch-codex instance start --buddy pm -- debug prompt-input "buddybox logical name smoke"
```

Manual checks:

- Runtime workspace has `buddyswitch/local/buddybox/pm` as a real directory.
- Shared state does not receive `state/buddyswitch/local/buddybox/pm`.
- `python3 scripts/env/client.py context summarize` in the runtime workspace returns buddybox capability metadata and no buddybox filesystem root.

## 4. 详细测试用例

### `BBX-STORAGE-001`: instance start creates active buddybox real directory

- 覆盖需求：`REQ-001`, `REQ-002`, `REQ-003`
- 用户 / 系统场景：PM instance starts and receives a private buddybox capability.
- 前置条件：Fake launcher environment from `tests/test_buddyswitch_launcher.py` with fake Codex, fake browser, and temp shared root.
- 输入：`./buddyswitch-codex instance start --buddy pm debug prompt-input "Draft the onboarding PRD"`
- 预期输出或状态变化：`workspace/buddyswitch/local/buddybox/pm` exists as a real directory; it is not a symlink; `shared_root/state/buddyswitch/local/buddybox/pm` does not exist.
- 断言重点：Product object dirs remain symlinks to shared state; only buddybox changes to real local directory.
- 测试类型：Launcher integration.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_creates_instance_specific_runtime_workspace`

### `BBX-STORAGE-002`: workspace rebuild keeps files instance-local

- 覆盖需求：`REQ-002`, `REQ-005`
- 用户 / 系统场景：Launcher rebuilds an instance workspace after a private file exists.
- 前置条件：Started PM instance with real local buddybox dir.
- 输入：Create `workspace/buddyswitch/local/buddybox/pm/rebuild/probe.txt`, then call the launcher path that rebuilds or reopens the same instance workspace.
- 预期输出或状态变化：Probe remains under the same instance workspace; no shared buddybox state dir is created.
- 断言重点：Preservation happens through workspace staging, not shared-state sync.
- 测试类型：Launcher integration regression.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_workspace_rebuild_preserves_active_buddybox_inside_instance_workspace`

### `BBX-STORAGE-003`: legacy shared buddybox state is ignored

- 覆盖需求：`REQ-004`
- 用户 / 系统场景：Old shared-state buddybox files exist before an active instance uses buddybox.
- 前置条件：Create `shared_root/state/buddyswitch/local/buddybox/pm/legacy.txt` and retired `buddyswitch/content/buddybox/pm/legacy.txt`.
- 输入：`buddybox.list` and `buddybox.read logical_name="legacy.txt"` as PM.
- 预期输出或状态变化：List does not include legacy files; read returns not found; no migration or cleanup occurs.
- 断言重点：Absence from active files plus legacy files remain untouched.
- 测试类型：Service integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_legacy_shared_buddybox_roots_are_unmanaged`

### `BBX-BROKER-001`: broker env keeps object state shared and buddybox workspace-local

- 覆盖需求：`REQ-002`, `REQ-027`
- 用户 / 系统场景：Runtime broker handles env.tool calls inside launcher workspace.
- 前置条件：`tests/test_runtime_broker.py` temporary runtime workspace with `instance.json`.
- 输入：Broker `status`, then broker-routed `buddybox.write logical_name="broker/out.txt"`.
- 预期输出或状态变化：Broker status remains healthy; private file lands under instance workspace; product object paths still resolve through existing runtime state model.
- 断言重点：`BUDDYSWITCH_WORKSPACE_DIR` and `instance_payload["workspace_dir"]` drive buddybox root.
- 测试类型：Broker integration.
- 建议测试文件路径和测试名称：`tests/test_runtime_broker.py::RuntimeBrokerTests::test_broker_routes_buddybox_to_workspace_local_root`

### `BBX-CLI-001`: CLI exposes logical-name flags only

- 覆盖需求：`REQ-006`, `REQ-021`
- 用户 / 系统场景：A runtime skill calls buddybox through `scripts/env/client.py`.
- 前置条件：Local checkout.
- 输入：`python3 scripts/env/client.py buddybox read --help`, `list --help`, `delete --help`.
- 预期输出或状态变化：Help shows `--logical-name`; help does not show `--path` for buddybox actions.
- 断言重点：CLI cannot construct retired `path` payloads for buddybox.
- 测试类型：CLI unit/integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_cli_uses_logical_name_flags`

### `BBX-SERVICE-001`: text lifecycle uses logical names

- 覆盖需求：`REQ-001`, `REQ-006`, `REQ-007`, `REQ-010`, `REQ-011`, `REQ-012`, `REQ-013`
- 用户 / 系统场景：PM writes, reads, lists, and deletes a private HTML prototype.
- 前置条件：RuntimeWorkspaceTestMixin PM instance.
- 输入：`write logical_name="prototypes/hero.html"`, `read logical_name="prototypes/hero.html"`, `list recursive=true`, `delete logical_name="prototypes/hero.html"`.
- 预期输出或状态变化：File exists only at active workspace private dir; response fields use `logical_name`; delete removes it.
- 断言重点：No response contains `path`; list rows contain summaries only.
- 测试类型：Service integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_logical_name_text_lifecycle`

### `BBX-SERVICE-002`: legacy path payload and buddy prefixes reject

- 覆盖需求：`REQ-006`, `REQ-008`, `REQ-028`
- 用户 / 系统场景：Host still uses old `path` or `pm/...` shape.
- 前置条件：PM runtime instance.
- 输入：`{"path":"pm/prototypes/hero.html","content":"x"}`, `{"logical_name":"pm/prototypes/hero.html","content":"x"}`, `{"logical_name":"dev/report.txt","content":"x"}`.
- 预期输出或状态变化：All reject; no file is written.
- 断言重点：`path` returns `E_BUDDYBOX_PAYLOAD`; buddy prefixes return `E_BUDDYBOX_LOGICAL_NAME`.
- 测试类型：Negative service integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_rejects_legacy_path_and_buddy_prefixed_logical_names`

### `BBX-SERVICE-003`: write create and overwrite are explicit

- 覆盖需求：`REQ-010`
- 用户 / 系统场景：Host overwrites an existing private file.
- 前置条件：PM runtime instance.
- 输入：Two writes to `logical_name="logs/out.txt"` with content `v1` then `v2`.
- 预期输出或状态变化：First response `created=true`, `overwrote=false`; second response `created=false`, `overwrote=true`; file content is `v2`.
- 断言重点：Created and overwrite flags reflect real filesystem state.
- 测试类型：Service integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_overwrite_is_explicit_with_logical_name`

### `BBX-SERVICE-004`: binary read/write returns base64

- 覆盖需求：`REQ-010`, `REQ-011`
- 用户 / 系统场景：Host writes generated binary output.
- 前置条件：PM runtime instance.
- 输入：`write logical_name="assets/snapshot.bin" content_base64=<bytes>`, then `read logical_name="assets/snapshot.bin"`.
- 预期输出或状态变化：Read returns `encoding="base64"` and matching `content_base64`.
- 断言重点：No UTF-8 decoding loss; `content` and `content_base64` are mutually exclusive.
- 测试类型：Service integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_binary_logical_name_round_trip`

### `BBX-SERVICE-005`: list returns summaries without content

- 覆盖需求：`REQ-012`
- 用户 / 系统场景：Host wants to inspect private file inventory.
- 前置条件：PM private files under `notes/a.txt` and `nested/b.txt`.
- 输入：`list recursive=true`, `list logical_name="nested" recursive=true`.
- 预期输出或状态变化：Rows contain `logical_name`, `size_bytes`, `updated_at`, `content_type`, `private_to_buddy`; rows do not contain `path`, `content`, `content_base64`, or `source_ref`.
- 断言重点：Prefix filtering uses logical names and cannot browse outside active buddy private files.
- 测试类型：Service integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_list_returns_logical_summaries_only`

### `BBX-SERVICE-006`: repeated delete is explicit

- 覆盖需求：`REQ-013`
- 用户 / 系统场景：Host deletes the same private file twice.
- 前置条件：PM file `logs/out.txt` exists.
- 输入：`delete logical_name="logs/out.txt"` twice.
- 预期输出或状态变化：First delete `deleted=true`, `state_changed=true`; second delete `deleted=false`, `state_changed=false`.
- 断言重点：Repeat operation does not hide state transition.
- 测试类型：Service integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_repeat_delete_is_explicit_with_logical_name`

### `BBX-SERVICE-007`: old content root is not active storage

- 覆盖需求：`REQ-004`
- 用户 / 系统场景：Retired content root contains files.
- 前置条件：Create `buddyswitch/content/buddybox/pm/old.md` in runtime sandbox.
- 输入：`buddybox.list recursive=true`; `buddybox.read logical_name="old.md"`.
- 预期输出或状态变化：List is empty; read returns `E_BUDDYBOX_NOT_FOUND`; old file remains.
- 断言重点：No fallback from new tool root to retired content root.
- 测试类型：Regression.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_old_content_buddybox_root_is_not_active_storage`

### `BBX-SERVICE-008`: buddybox operations do not mutate product objects

- 覆盖需求：`REQ-014`
- 用户 / 系统场景：Host writes private file while product object store exists.
- 前置条件：Seed one task, one artifact, one handoff.
- 输入：`buddybox.write`, `read`, `list`, `delete`.
- 预期输出或状态变化：Product object JSON file mtimes and payloads remain unchanged.
- 断言重点：Response `mutates_product_state=false` matches persisted object state.
- 测试类型：Service integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_operations_do_not_mutate_product_objects`

### `BBX-NEGATIVE-001`: invalid logical names reject without mutation

- 覆盖需求：`REQ-008`
- 用户 / 系统场景：Host sends malformed logical names.
- 前置条件：PM runtime instance.
- 输入：`""`, `"/tmp/x.txt"`, `"../x.txt"`, `"notes/../../x.txt"`, `"."`, `"pm/x.txt"`.
- 预期输出或状态变化：Reject with `E_BUDDYBOX_LOGICAL_NAME`; no file created.
- 断言重点：`correctable_fields=["logical_name"]`; `state_changed=false`.
- 测试类型：Negative service integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_rejects_invalid_logical_names_without_mutation`

### `BBX-NEGATIVE-002`: payload and encoding errors are structured

- 覆盖需求：`REQ-008`, `REQ-017`
- 用户 / 系统场景：Host sends invalid content payload or invalid read encoding.
- 前置条件：PM runtime instance.
- 输入：Write missing both content fields; write both content fields; write invalid base64; read with `encoding="utf16"`.
- 预期输出或状态变化：Reject with `E_BUDDYBOX_PAYLOAD`, `state_changed=false`.
- 断言重点：Correctable fields name exact fields: `content`, `content_base64`, `encoding`.
- 测试类型：Negative service integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_rejects_payload_and_encoding_errors_with_correction_fields`

### `BBX-NEGATIVE-003`: symlink escapes reject and do not leak content

- 覆盖需求：`REQ-009`
- 用户 / 系统场景：A symlink inside active buddy private root points to another buddy's file.
- 前置条件：Create Dev file and PM symlink to it inside PM buddybox root.
- 输入：PM reads symlink logical name; PM lists recursively; PM writes through parent symlink to Dev dir.
- 预期输出或状态变化：Read/write reject with boundary error; list skips symlink; Dev content is not present in rejection JSON; no write occurs under Dev dir.
- 断言重点：Symlink escape is blocked for read, list, and write.
- 测试类型：Security boundary regression.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_rejects_symlink_escape_from_active_root`

### `BBX-RESPONSE-001`: success responses expose private file state model

- 覆盖需求：`REQ-015`
- 用户 / 系统场景：Host needs to decide whether a buddybox result is product-readable.
- 前置条件：PM runtime instance.
- 输入：Write/read/list/delete private file.
- 预期输出或状态变化：Responses contain `visibility`, `owner_scope`, `lifetime_scope`, `product_readable=false`, `cross_buddy_readable=false`, `mutates_product_state=false`, `mutated_product_objects=[]`.
- 断言重点：Fields exist and are booleans/strings with exact expected values.
- 测试类型：Response contract integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_success_responses_expose_private_file_state_model`

### `BBX-RESPONSE-002`: write durability is active instance local

- 覆盖需求：`REQ-015`
- 用户 / 系统场景：Host sees a private file write result.
- 前置条件：PM runtime instance.
- 输入：`buddybox.write logical_name="logs/out.txt" content="x"`.
- 预期输出或状态变化：Response `durability="active_instance_local"` and `lifetime_scope="active_instance_workspace"`.
- 断言重点：Not `durable` in a product-object sense.
- 测试类型：Response contract regression.
- 建议测试文件路径和测试名称：`tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_buddybox_write_reports_active_instance_local_durability`

### `BBX-RESPONSE-003`: available affordances are structured and conditional

- 覆盖需求：`REQ-016`
- 用户 / 系统场景：Host chooses what to do after a private file write.
- 前置条件：PM runtime instance.
- 输入：`buddybox.write logical_name="prototypes/hero.html" content="<html></html>"`.
- 预期输出或状态变化：`available_affordances` contains structured buddybox read/list rows and a conditional artifact row.
- 断言重点：Artifact row condition contains host decision/product-readable wording; no "always" or "must create artifact".
- 测试类型：Response contract integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_success_affordances_are_structured_and_conditional`

### `BBX-REJECTION-001`: invalid logical name rejection is self-correcting

- 覆盖需求：`REQ-017`
- 用户 / 系统场景：Host uses an absolute logical name.
- 前置条件：PM runtime instance.
- 输入：`buddybox.write logical_name="/tmp/out.txt" content="x"`.
- 预期输出或状态变化：Reject with `error.code="E_BUDDYBOX_LOGICAL_NAME"`, `error.class="invalid_input"`, `boundary="active_buddy_private_file_capability"`, `retryable=true`, `correctable_fields=["logical_name"]`.
- 断言重点：`state_changed=false`, `mutates_product_state=false`.
- 测试类型：Negative response contract.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_invalid_logical_name_rejection_is_self_correcting`

### `BBX-REJECTION-002`: missing file rejection is structured

- 覆盖需求：`REQ-017`
- 用户 / 系统场景：Host reads a file that does not exist.
- 前置条件：Empty PM buddybox.
- 输入：`buddybox.read logical_name="missing.txt"`.
- 预期输出或状态变化：Reject with `E_BUDDYBOX_NOT_FOUND`, `error.class="not_found"`, `state_changed=false`.
- 断言重点：No filesystem root appears; correction suggests logical name or writing the file first through capabilities.
- 测试类型：Negative response contract.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_missing_file_rejection_is_structured`

### `BBX-REJECTION-003`: rejection guidance does not expose filesystem contracts

- 覆盖需求：`REQ-018`
- 用户 / 系统场景：Host receives a rejection and must recover safely.
- 前置条件：PM runtime instance.
- 输入：Invalid `logical_name="pm/private.txt"`.
- 预期输出或状态变化：Rejection has `alternative_capabilities`; no rejection text contains `<active_buddy>`, `buddyswitch/local/buddybox`, `shared state`, `direct edit`, or `retry with path`.
- 断言重点：Recovery can use structured fields without path knowledge.
- 测试类型：Negative response contract.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_rejections_do_not_expose_path_guidance`

### `BBX-CONTEXT-001`: buddybox_desc exposes capability metadata

- 覆盖需求：`REQ-007`, `REQ-012`, `REQ-019`
- 用户 / 系统场景：Host starts with context discovery.
- 前置条件：Runtime context with active buddy Dev and one private file.
- 输入：`context.get`.
- 预期输出或状态变化：`buddybox_desc` includes capability metadata and summary counts; it does not include file rows or content.
- 断言重点：No `logical_root`, no filesystem path roots.
- 测试类型：Context integration.
- 建议测试文件路径和测试名称：`tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_uses_buddybox_capability_desc_not_path_projection`

### `BBX-CONTEXT-002`: list_sources does not expose buddybox source_of_truth

- 覆盖需求：`REQ-019`, `REQ-020`
- 用户 / 系统场景：Host asks what context sources exist.
- 前置条件：Runtime context.
- 输入：`context.list_sources`.
- 预期输出或状态变化：Buddybox row includes capability metadata; `source_of_truth` absent; stringified row has no `buddyswitch/local/buddybox`, `workspace`, or `shared`.
- 断言重点：Context source descriptor is not a filesystem contract.
- 测试类型：Context integration.
- 建议测试文件路径和测试名称：`tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_list_sources_describes_buddybox_capability_without_roots`

### `BBX-CONTEXT-003`: summarize distinguishes buddybox, artifact, handoff, and source writes

- 覆盖需求：`REQ-022`
- 用户 / 系统场景：Host chooses where to put output.
- 前置条件：Runtime context with tool affordances.
- 输入：`context.summarize`.
- 预期输出或状态变化：`tool_affordances` describes buddybox as private file capability, artifact as product-readable deliverable carrier, handoff as collaboration record, and project source as separate.
- 断言重点：No phrase-to-tool trigger or mandatory workflow language.
- 测试类型：Host decision integration.
- 建议测试文件路径和测试名称：`tests/test_host_decision_surface_product_mode.py::HostDecisionSurfaceProductModeTests::test_context_summarize_distinguishes_private_files_from_product_readable_state`

### `BBX-SEM-001`: tool catalog uses logical_name payload fields

- 覆盖需求：`REQ-006`, `REQ-021`
- 用户 / 系统场景：Host inspects full tool catalog.
- 前置条件：Local contract registry.
- 输入：`contracts.env_tools_description()["buddybox"]`.
- 预期输出或状态变化：Payload fields for list/read/write/delete include `logical_name`; no action includes payload field `path`.
- 断言重点：Input descriptions say buddy prefix is invalid.
- 测试类型：Semantic unit contract.
- 建议测试文件路径和测试名称：`tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_buddybox_action_semantics_use_logical_name`

### `BBX-SEM-002`: operation semantics expose capability decision signals

- 覆盖需求：`REQ-019`, `REQ-021`
- 用户 / 系统场景：Host uses operation semantics for tool selection.
- 前置条件：Local contract registry.
- 输入：`contracts.operation_semantics()` and `contracts.compact_tool_affordances()`.
- 预期输出或状态变化：Buddybox rows include owner/lifetime/visibility/product mutation semantics.
- 断言重点：Side effects describe private file workspace, not filesystem path roots.
- 测试类型：Semantic unit contract.
- 建议测试文件路径和测试名称：`tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_buddybox_semantics_expose_capability_decision_signals`

### `BBX-SEM-003`: semantics do not expose filesystem roots

- 覆盖需求：`REQ-020`
- 用户 / 系统场景：Host reads tool catalog and operation semantics.
- 前置条件：Local contract registry.
- 输入：JSON dump of buddybox semantic rows.
- 预期输出或状态变化：No `buddyswitch/local/buddybox`, `<active_buddy>`, `logical_root`, `source_of_truth`, `shared root`, or `workspace root`.
- 断言重点：Tool descriptions cannot become path contract source.
- 测试类型：Semantic regression.
- 建议测试文件路径和测试名称：`tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_buddybox_semantics_do_not_expose_filesystem_roots`

### `BBX-ARTIFACT-001`: artifact keeps buddybox logical_name as private provenance

- 覆盖需求：`REQ-023`
- 用户 / 系统场景：PM promotes private draft content to product-readable artifact.
- 前置条件：PM owns task and private buddybox logical file.
- 输入：`artifact.create_revision` with `source_refs=[{"type":"buddybox","logical_name":"drafts/prd.md"}]` and readable artifact content.
- 预期输出或状态变化：Artifact source ref stores `logical_name`, `private_to_buddy="pm"`, `read_grant=false`; artifact content is readable according to artifact rules.
- 断言重点：Source ref is provenance, not read grant.
- 测试类型：Artifact integration.
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_artifact_buddybox_source_ref_is_private_logical_provenance`

### `BBX-HANDOFF-001`: handoff rejects buddybox logical names as readable payloads

- 覆盖需求：`REQ-024`
- 用户 / 系统场景：Design tries to hand off a private buddybox logical file to Dev.
- 前置条件：Design handoff payload.
- 输入：`handoff.validate` and `handoff.create` with `source_refs=[{"type":"buddybox","logical_name":"handoff/private.md"}]`.
- 预期输出或状态变化：Reject with `E_SOURCE_REFS`; no handoff file is created.
- 断言重点：Rejection explains private provenance is not target-readable content.
- 测试类型：Handoff integration.
- 建议测试文件路径和测试名称：`tests/test_handoff_env_tool.py::HandoffEnvToolTests::test_handoff_rejects_buddybox_logical_names_as_private_payload`

### `BBX-HOST-001`: no phrase-to-tool SOP is encoded

- 覆盖需求：`REQ-001`, `REQ-016`, `REQ-022`, `REQ-025`
- 用户 / 系统场景：PM receives a prototype-like task.
- 前置条件：Product mode decision surface.
- 输入：Context summary, tool catalog, buddybox write response.
- 预期输出或状态变化：Semantic surfaces support deciding between private buddybox file and product-readable artifact; no test asserts a fixed phrase trigger.
- 断言重点：No "prototype means buddybox", no "always create artifact", no mandatory promotion.
- 测试类型：Host decision regression.
- 建议测试文件路径和测试名称：`tests/test_host_decision_surface_product_mode.py::HostDecisionSurfaceProductModeTests::test_host_decision_surface_uses_semantics_not_phrase_routing`

### `BBX-MANIFEST-001`: buddybox permissions remain consistent across buddies

- 覆盖需求：`REQ-028`
- 用户 / 系统场景：Different buddies use same buddybox action permissions.
- 前置条件：`buddyswitch/manifest.toml` loaded.
- 输入：Manifest buddy rows.
- 预期输出或状态变化：No PM-only or buddy-type-specific buddybox read permission exists.
- 断言重点：All buddies with buddybox get the same read/write/delete surface.
- 测试类型：Manifest contract regression.
- 建议测试文件路径和测试名称：`tests/test_env_manifest_v2.py::EnvManifestV2Tests::test_buddybox_permissions_are_role_consistent`

### `BBX-GUIDANCE-001`: route maps use logical names, not roots

- 覆盖需求：`REQ-018`, `REQ-026`
- 用户 / 系统场景：Runtime host reads AGENTS and skills.
- 前置条件：Repository files.
- 输入：`README.md`, `AGENTS.md`, buddy AGENTS templates, role contracts, buddybox shared skill, role-specific skills.
- 预期输出或状态变化：Texts mention buddybox env tool and logical names; they do not encode buddybox filesystem roots or `--path` examples.
- 断言重点：Prompt layer is route map only.
- 测试类型：Repo consistency.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_buddybox_guidance_uses_logical_names_not_filesystem_roots`

### `BBX-GUIDANCE-002`: runtime skills materialize after guidance rewrite

- 覆盖需求：`REQ-026`
- 用户 / 系统场景：Launcher installs runtime skills into an instance workspace.
- 前置条件：Fake launcher start for each buddy.
- 输入：`./buddyswitch-codex instance start --buddy <buddy>`.
- 预期输出或状态变化：Expected skills still materialize; buddybox tool skill content matches source.
- 断言重点：Guidance cleanup does not break skill install.
- 测试类型：Launcher/runtime skill integration.
- 建议测试文件路径和测试名称：`tests/test_runtime_skills.py::RuntimeSkillsTests::test_runtime_skill_install_keeps_buddybox_tool_after_logical_name_rewrite`

### `BBX-GREP-001`: retired path contracts are absent from active surfaces

- 覆盖需求：`REQ-018`, `REQ-020`, `REQ-026`
- 用户 / 系统场景：Regression scan after implementation.
- 前置条件：Repository files.
- 输入：`rg` over active source, tests, guidance excluding memo/spec.
- 预期输出或状态变化：No unexpected active references to buddybox `--path`, root contracts, `logical_root`, or buddybox `source_of_truth`.
- 断言重点：Allow only test strings that assert retired wording is absent.
- 测试类型：Static regression.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_retired_buddybox_path_contract_strings_are_absent`

### `BBX-GREP-002`: no speculative routing systems were added

- 覆盖需求：`REQ-025`
- 用户 / 系统场景：Implementation must not solve tool choice by adding routing machinery.
- 前置条件：Repository files.
- 输入：Search for new phrase router, rule engine, workflow engine, generic permission framework markers.
- 预期输出或状态变化：No new modules or text introduce those mechanisms.
- 断言重点：The change remains a direct service/semantics replacement.
- 测试类型：Static architecture regression.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_buddybox_realignment_does_not_add_speculative_routing_layers`

### `BBX-E2E-001`: artifact carries readable content, buddybox remains private

- 覆盖需求：`REQ-014`, `REQ-023`, `REQ-024`
- 用户 / 系统场景：PM drafts privately, then promotes readable content for another buddy.
- 前置条件：PM task and Dev readable relation.
- 输入：PM writes `logical_name="drafts/prd.html"`, reads it, creates artifact content with buddybox logical provenance, creates handoff with artifact id; Dev gets artifact; Dev attempts buddybox read.
- 预期输出或状态变化：Dev reads artifact content and cannot read PM buddybox file.
- 断言重点：Readability is carried by artifact content, not buddybox logical name.
- 测试类型：End-to-end integration.
- 建议测试文件路径和测试名称：`tests/test_env_layer_end_to_end.py::EnvLayerEndToEndTests::test_private_buddybox_logical_file_can_be_promoted_by_artifact_content_only`

### `BBX-E2E-002`: runless main path remains healthy

- 覆盖需求：`REQ-027`
- 用户 / 系统场景：Standard runless env tool path works after buddybox breaking replacement.
- 前置条件：RuntimeWorkspaceTestMixin.
- 输入：Create track/task/artifact/handoff; context summarize; buddybox write logical file.
- 预期输出或状态变化：All product objects persist; buddybox private file exists only in workspace local dir; context has capability metadata.
- 断言重点：Realignment does not regress runless product object tools.
- 测试类型：End-to-end regression.
- 建议测试文件路径和测试名称：`tests/test_env_layer_end_to_end.py::EnvLayerEndToEndTests::test_runless_main_path_works_with_buddybox_logical_names`

## 5. 负向与边界测试

- 缺失数据：`buddybox.read` without `logical_name`; `buddybox.write` without `content` and `content_base64`; `artifact.source_refs` buddybox without `logical_name`.
- 无效状态：missing file read; directory delete; invalid base64; invalid encoding; malformed source_refs list; stale symlink from workspace buddybox to shared state.
- 重复操作：overwrite same `logical_name`; delete same `logical_name` twice; list empty workspace repeatedly.
- 并发或顺序敏感行为：workspace rebuild after local private file exists; broker dispatch after `BUDDYSWITCH_WORKSPACE_DIR` is set; object state remains shared while buddybox remains local.
- 空输入、空集合、空记录、空配置：empty logical name; list empty root; context summarize with no product objects; source_refs empty list.
- 权限、路径、配置、运行状态、外部依赖异常：active buddy prefix and foreign buddy prefix reject; absolute and traversal logical names reject; symlink escape rejects; launcher fake environment proves no external Codex dependency; optional manual real launch is non-blocking.

## 6. 作弊防护

- Use multiple logical names across tests: `prototypes/hero.html`, `assets/snapshot.bin`, `logs/out.txt`, `nested/b.txt`, `drafts/prd.html`. This prevents hardcoding one file name.
- Use at least two buddies, PM and Dev, plus one Design handoff scenario. This prevents PM special read authority from being silently preserved.
- Assert both filesystem state and JSON response state for write/read/delete. Passing response-only tests is insufficient.
- Assert absence from shared state and absence of symlink, not just existence in workspace.
- Assert no `path` field appears in response rows. This prevents accepting `logical_name` while preserving old output.
- Test legacy `path` payload rejection directly. This prevents a hidden compatibility alias.
- Test active buddy prefix rejection directly. This prevents old `pm/...` shape from surviving under a new field name.
- Test artifact source_refs with `logical_name` and rejection of `path`. This prevents preserving path contract in provenance.
- Test rejection text for forbidden substrings. This prevents implementation from adding correct structured fields while still teaching paths in prose.
- Static grep gates scan guidance, skills, contracts, source, and tests. This prevents prompt-layer filesystem contracts from moving to another file.
- Host decision tests verify semantic signals and absence of phrase triggers. They do not reward hardcoded routing based on words like prototype.

## 7. 验证命令清单

Focused storage verification:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_creates_instance_specific_runtime_workspace -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_workspace_rebuild_preserves_active_buddybox_inside_instance_workspace -q
```

Focused service verification:

```bash
python3 -m pytest tests/test_buddybox_env_tool.py -q
```

Focused context and semantics verification:

```bash
python3 -m pytest tests/test_context_binding_env_tool.py tests/test_env_tool_identity.py tests/test_env_tool_semantic_contract.py -q
```

Focused artifact and handoff verification:

```bash
python3 -m pytest tests/test_artifact_env_tool.py tests/test_handoff_env_tool.py -q
```

Focused launcher, broker, sandbox, and guidance verification:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py tests/test_runtime_broker.py tests/test_buddy_env_sandbox.py tests/test_runtime_agents.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

Broader verification:

```bash
python3 -m pytest tests/test_buddybox_env_tool.py tests/test_context_binding_env_tool.py tests/test_env_tool_identity.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_response_contract.py tests/test_artifact_env_tool.py tests/test_handoff_env_tool.py tests/test_host_decision_surface_product_mode.py tests/test_env_layer_end_to_end.py tests/test_run_env_tool.py tests/test_runtime_broker.py tests/test_buddy_env_sandbox.py tests/test_buddyswitch_launcher.py tests/test_runtime_agents.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

Final static regression scan:

```bash
rg -n "buddybox.*--path|source_of_truth.*buddybox|logical_root|<active_buddy>|buddyswitch/local/buddybox/<|buddyswitch/local/buddybox/pm|buddyswitch/local/buddybox/dev|buddyswitch/local/buddybox/design|buddyswitch/local/buddybox/market|buddyswitch/local/buddybox/test|prototype means buddybox|always create artifact|must create artifact after buddybox" README.md AGENTS.md scripts tools framework buddyswitch tests -g '!docs/memo/**' -g '!docs/spec/**'
```

Final required verification before declaring implementation complete:

```bash
python3 -m pytest tests/test_buddybox_env_tool.py tests/test_context_binding_env_tool.py tests/test_env_tool_identity.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_response_contract.py tests/test_artifact_env_tool.py tests/test_handoff_env_tool.py tests/test_host_decision_surface_product_mode.py tests/test_env_layer_end_to_end.py tests/test_run_env_tool.py tests/test_runtime_broker.py tests/test_buddy_env_sandbox.py tests/test_buddyswitch_launcher.py tests/test_runtime_agents.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
rg -n "buddybox.*--path|source_of_truth.*buddybox|logical_root|<active_buddy>|buddyswitch/local/buddybox/<|buddyswitch/local/buddybox/pm|buddyswitch/local/buddybox/dev|buddyswitch/local/buddybox/design|buddyswitch/local/buddybox/market|buddyswitch/local/buddybox/test|prototype means buddybox|always create artifact|must create artifact after buddybox" README.md AGENTS.md scripts tools framework buddyswitch tests -g '!docs/memo/**' -g '!docs/spec/**'
```
