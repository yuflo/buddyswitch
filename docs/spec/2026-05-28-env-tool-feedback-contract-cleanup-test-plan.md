# Env Tool Feedback Contract Cleanup Test Plan

Date: 2026-05-28
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-auth`

## Goal

Clean up env.tool feedback after role-action auth so runtime denial feedback reads as an execution receipt, while context role-policy data reads as a read-only planning preview.

The test suite must prove:

- role-auth denial still happens before selected tool implementation import and before args validation;
- `E_TOOL_ROLE_AUTH` exposes clear receipt fields, including `executed=false`;
- auth-denial wording no longer implies manifest permission ownership;
- context returns `runtime_policy_preview` instead of old auth preview field names;
- preview data is computed from runtime role-action policy and explicitly marked as not authorization and not execution proof;
- tool catalog and operation semantics no longer contain `active buddy owns ... permission`;
- CLI/broker-facing env client preserves the receipt fields at top level;
- manifest buddy permissions remain retired.

## Current Code Facts

- `scripts/env/tool_runtime/registry.py` owns env.tool dispatch and already performs role auth before args validation and selected tool `_impl` import.
- `_role_auth_rejection()` currently returns `E_TOOL_ROLE_AUTH` with `permission_boundary`, `required_permission`, `active_role`, `allowed_roles`, `state_changed=false`, and `durability=none`.
- `_role_auth_rejection()` currently does not emit `category`, `auth_source`, `auth_stage`, or `executed`.
- `_role_auth_rejection().why_blocked` currently says `requires permission`, and next-action text refers to `allowed and denied actions` / `required permissions`.
- `scripts/env/tool_runtime/role_auth.py::role_action_summary()` currently returns old preview fields: `role_authority_source`, `allowed_actions`, `denied_actions`, `denied_action_details`, and `allowed_action_permissions`.
- `scripts/env/tools/context/_impl.py::_capability_snapshot()` currently merges `role_action_summary()` directly into `capability_snapshot`.
- Tool metadata currently has six `active buddy owns ... permission` preconditions:
  - `scripts/env/tools/message/tool.py`
  - `scripts/env/tools/task/tool.py`
  - `scripts/env/tools/artifact/tool.py`
  - `scripts/env/tools/track/tool.py`
- `scripts/env/client.py::_error_payload()` currently top-level preserves only selected broker error fields and would not preserve new receipt fields unless updated.
- `scripts/runtime_kernel/dispatcher.py` directly returns env.tool response payloads and does not need changes unless a focused test proves otherwise.

## Non-Goals

- Do not test or change daemon, STOP, Task TUI, launcher lifecycle, UI, workflow, gate, DSL, or profile behavior.
- Do not restore manifest `permissions`.
- Do not keep old and new preview auth fields side by side.
- Do not move payload, resource, lifecycle, or state-conflict rejections into dispatch.
- Do not add per-tool duplicate role-action auth checks.
- Do not touch `runtime_kernel/*` unless focused tests prove receipt fields cannot pass through.

## Functional Requirements

| ID | Requirement |
| --- | --- |
| FR1 | Auth denial remains centralized in env.tool dispatch and runs before selected tool `_impl` import. |
| FR2 | Auth denial runs before args shape validation. |
| FR3 | `E_TOOL_ROLE_AUTH` includes `category=auth_denied`, `auth_source=env.tool role-action policy`, `auth_stage=pre_dispatch`, and `executed=false`. |
| FR4 | `E_TOOL_ROLE_AUTH` keeps `required_permission`, `active_role`, `allowed_roles`, `permission_boundary=tool.role_authority`, `state_changed=false`, and `durability=none`. |
| FR5 | `E_TOOL_ROLE_AUTH` human text uses role-action policy wording and does not say `requires permission` or `owns permission`. |
| FR6 | `context.get` and `context.summarize` expose auth preview under `capability_snapshot.runtime_policy_preview`. |
| FR7 | `runtime_policy_preview` includes `active_role`, `source=env.tool role-action policy`, `not_authorization_boundary=true`, `not_execution_result=true`, `available_actions`, `restricted_actions`, and `restricted_action_details`. |
| FR8 | Old auth preview fields are removed from `capability_snapshot`: `role_authority_source`, `allowed_actions`, `denied_actions`, `denied_action_details`, and `allowed_action_permissions`. |
| FR9 | Market/dev/design restricted actions still include `track.create`, `track.archive`, and `comment.resolve`; PM can use those actions at role-auth layer. |
| FR10 | Tool catalog and operation semantics do not contain `active buddy owns ... permission`. |
| FR11 | Operation semantics remain role-neutral and do not expose `runtime_policy_preview`, `available_actions`, or `restricted_actions`. |
| FR12 | `scripts/env/client.py` preserves auth receipt fields at top level when broker returns an env.tool rejection. |
| FR13 | Manifest loader still rejects per-buddy `permissions`; no manifest compatibility path is reintroduced. |

## Test Cases

### T1: Auth denial receipt fields are explicit

File: `tests/test_env_tool_router.py`

Behavior:

- Dispatch `track.create` as `dev`.
- Assert:
  - `ok is false`;
  - `error.code == "E_TOOL_ROLE_AUTH"`;
  - `permission_boundary == "tool.role_authority"`;
  - `category == "auth_denied"`;
  - `auth_source == "env.tool role-action policy"`;
  - `auth_stage == "pre_dispatch"`;
  - `executed is False`;
  - `required_permission == "track.create"`;
  - `active_role == "dev"`;
  - `allowed_roles == ["pm"]`;
  - `state_changed is False`;
  - `durability == "none"`;
  - `why_blocked` contains `role-action policy`;
  - `why_blocked` does not contain `requires permission`;
  - `why_blocked` does not contain `owns permission`.

Expected failure before implementation:

- Missing `category`, `auth_source`, `auth_stage`, and `executed`.
- `why_blocked` contains `requires permission`.

### T2: Auth denial still precedes selected private implementation import

File: `tests/test_env_tool_router.py`

Behavior:

- Keep the existing subprocess import-block test for `env.tools.track._impl`.
- Dispatch `track.create` as `dev`.
- Assert `E_TOOL_ROLE_AUTH` receipt fields from T1.
- Assert loaded modules do not include `env.tools.track._impl`.

Expected failure before implementation:

- Receipt fields are missing, though the import ordering should already be correct.

### T3: Auth denial still precedes args validation

File: `tests/test_env_tool_router.py`

Behavior:

- Dispatch `track.create` as `dev` with `args` set to `"not-an-object"`.
- Assert:
  - `error.code == "E_TOOL_ROLE_AUTH"`;
  - `permission_boundary == "tool.role_authority"`;
  - `category == "auth_denied"`;
  - `auth_stage == "pre_dispatch"`;
  - `executed is False`;
  - response is not `E_ENV_TOOL_PAYLOAD`.

Expected failure before implementation:

- New receipt fields are missing.

### T4: Role policy summary returns preview shape, not old auth fields

File: `tests/test_role_action_auth.py`

Behavior:

- Call `role_auth.role_action_summary("market", manifest, tool_registry.operation_semantics())`.
- Assert returned object has:
  - `active_role == "market"`;
  - `source == "env.tool role-action policy"`;
  - `not_authorization_boundary is True`;
  - `not_execution_result is True`;
  - `available_actions` list;
  - `restricted_actions` list;
  - `restricted_action_details` dict.
- Assert old keys are absent:
  - `role_authority_source`;
  - `allowed_actions`;
  - `denied_actions`;
  - `denied_action_details`;
  - `allowed_action_permissions`.
- Assert:
  - `track.list`, `artifact.create_revision`, and `request.accept` are in `available_actions`;
  - `track.create`, `track.archive`, and `comment.resolve` are in `restricted_actions`;
  - `restricted_action_details["track.create"]["required_permission"] == "track.create"`;
  - `restricted_action_details["track.create"]["restricted_to_roles"] == ["pm"]`.

Expected failure before implementation:

- Function returns old keys and old names.

### T5: `context.summarize` exposes nested `runtime_policy_preview`

File: `tests/test_context_binding_env_tool.py`

Behavior:

- Dispatch `context.summarize` as `dev`.
- Assert `payload["capability_snapshot"]` exists.
- Assert `payload["capability_snapshot"]["runtime_policy_preview"]` has the shape from T4.
- Assert old auth preview keys are absent from `capability_snapshot`.
- Assert non-auth context facts remain in `capability_snapshot`, including:
  - `task_visibility`;
  - `artifact_publication_path`;
  - `writable_file_surface`.

Expected failure before implementation:

- `capability_snapshot` has old auth keys and no `runtime_policy_preview`.

### T6: `context.get` exposes the same preview and full catalog remains role-neutral

File: `tests/test_context_binding_env_tool.py`

Behavior:

- Dispatch `context.get` as `dev`.
- Assert `capability_snapshot.runtime_policy_preview.restricted_actions` includes `comment.resolve`.
- Assert `operation_semantics["context.get"]` still includes existing generated operation semantic fields.
- Assert `operation_semantics` rows do not contain:
  - `runtime_policy_preview`;
  - `available_actions`;
  - `restricted_actions`;
  - `restricted_action_details`;
  - `active_role`;
  - `allowed_roles`.

Expected failure before implementation:

- Preview is old shape.

### T7: Env tool response contract uses preview shape

File: `tests/test_env_tool_response_contract.py`

Behavior:

- Update `test_context_get_and_summarize_catalog_scope`.
- For `summary["capability_snapshot"]`, assert:
  - `runtime_policy_preview` exists;
  - old auth preview fields are absent;
  - `runtime_policy_preview.source == "env.tool role-action policy"`;
  - `not_authorization_boundary is True`;
  - `not_execution_result is True`.
- Keep existing assertions that `summary` does not include full `tool_catalog` or `operation_semantics`.
- Keep existing assertions that `full["tool_catalog"] == turn_runtime._build_env_tools_desc()`.

Expected failure before implementation:

- Existing test expects old fields.

### T8: Tool catalog and operation semantics have no permission ownership wording

File: `tests/test_env_tool_semantic_contract.py`

Behavior:

- Dump `catalog.env_tools_description()` to JSON.
- Dump `catalog.operation_semantics()` to JSON.
- Assert neither dump contains:
  - `active buddy owns`;
  - `owns message.list permission`;
  - `owns task.read permission`;
  - `owns task.propose permission`;
  - `owns task.confirm permission`;
  - `owns artifact.create permission`;
  - `owns track.read permission`.
- Assert replacement policy wording appears at least once in relevant preconditions:
  - `env.tool role-action policy allows this action for the active role`.

Expected failure before implementation:

- Six existing tool preconditions contain old wording.

### T9: CLI error projection preserves receipt fields

File: `tests/test_env_client_payload_cli.py`

Behavior:

- Mock `request_runtime_broker` to raise `RuntimeBrokerError` with:
  - `code="E_TOOL_ROLE_AUTH"`;
  - `message="active role is not allowed to run this tool action"`;
  - `response` containing top-level receipt fields;
  - `details` containing the same receipt fields.
- Call `client.main()` for `track create`.
- Assert output keeps these at top level:
  - `category`;
  - `permission_boundary`;
  - `auth_source`;
  - `auth_stage`;
  - `executed`;
  - `state_changed`;
  - `durability`;
  - `required_permission`;
  - `active_role`;
  - `allowed_roles`;
  - `allowed_next_actions`.
- Assert `error.code == "E_TOOL_ROLE_AUTH"`.

Expected failure before implementation:

- `scripts/env/client.py::_error_payload()` moves most receipt fields under `error` or drops them from the top-level contract.

### T10: Manifest permissions remain retired

File: `tests/test_env_manifest_v2.py`

Behavior:

- Keep existing negative fixture that injects `permissions = ["track.read"]`.
- Assert loader raises `ManifestError` mentioning retired permissions.
- Assert loaded real manifest buddy rows do not include `permissions`.

Expected failure before implementation:

- None expected; this is a regression guard.

## Focused Test Commands

Run after test edits to confirm intended red:

```bash
python3 -m pytest tests/test_env_tool_router.py tests/test_role_action_auth.py tests/test_context_binding_env_tool.py tests/test_env_tool_response_contract.py tests/test_env_tool_semantic_contract.py tests/test_env_client_payload_cli.py tests/test_env_manifest_v2.py -q
```

Run after implementation until green:

```bash
python3 -m pytest tests/test_env_tool_router.py tests/test_role_action_auth.py tests/test_context_binding_env_tool.py tests/test_env_tool_response_contract.py tests/test_env_tool_semantic_contract.py tests/test_env_client_payload_cli.py tests/test_env_manifest_v2.py -q
```

Broader verification:

```bash
python3 -m pytest tests/test_track_env_tool.py tests/test_comment_env_tool.py tests/test_runtime_broker.py tests/test_runtime_tool_feedback.py tests/test_host_decision_surface_product_mode.py tests/test_runless_runtime_contract.py tests/test_turn_runtime.py -q
```

Final feasible verification:

```bash
python3 -m pytest -q
```

Static residue checks:

```bash
rg -n "active buddy owns .* permission" scripts/env/tools tests
rg -n "\"allowed_actions\"|\"denied_actions\"|\"denied_action_details\"|\"allowed_action_permissions\"|\"role_authority_source\"" scripts tests
rg -n "permissions\\s*=\\s*\\[" buddyswitch/manifest.toml
git diff --check
```

Expected final state:

- residue scans have no runtime/test hits except historical docs/spec text that explicitly describes removed behavior;
- all focused tests pass;
- broader verification passes;
- full suite passes if environment permits.
