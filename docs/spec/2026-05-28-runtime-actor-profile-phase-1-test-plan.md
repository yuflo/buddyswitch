# Runtime Actor Profile Phase 1 Test Plan

Date: 2026-05-28
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-inst`

## Goal

Split env.tool runtime identity, role authorization, auth-denied feedback, and tool-facing context into small runtime-kernel contracts without changing product behavior.

The tests must prove:

- runtime actor identity is normalized through `actor_profile`;
- role authorization consumes `AuthSubject`, not a raw active-role string;
- standard `E_TOOL_ROLE_AUTH` denial feedback is built by `auth_feedback`;
- `registry` orchestrates identity, auth, feedback, context construction, and dispatch without owning those internals;
- `ToolContext` remains the only tool-facing execution contract;
- tool packages do not import or inspect `RuntimeActorProfile`;
- existing role auth, router, context, semantic, and message behavior stays unchanged.

## Current Code Facts

- `scripts/env/tool_runtime/registry.py` currently receives `active_buddy` and `instance_id` as raw strings, calls `role_auth.authorize(required_permission, active_buddy, manifest)`, builds `E_TOOL_ROLE_AUTH` inline, and constructs `ToolContext(active_buddy=..., instance_id=...)`.
- `scripts/env/tool_runtime/role_auth.py` owns the current role-action policy, but `authorize()` and `role_action_summary()` accept raw active-role strings.
- `scripts/env/tool_runtime/context.py` owns `ToolContext`, but there is no explicit actor profile construction path.
- There is no `scripts/env/tool_runtime/actor_profile.py`.
- There is no `scripts/env/tool_runtime/auth_feedback.py`.
- Tool packages currently import `ToolContext`; they do not need `RuntimeActorProfile`.

## Non-Goals

- Do not change message addressing from role inbox to instance inbox.
- Do not add per-instance auth, delegation, elevation, permission DSL, workflow engine, plugin system, or env capability profile merge.
- Do not duplicate role auth inside tool packages.
- Do not move tool/domain business rules into runtime auth.
- Do not keep old raw-role auth entrypoints as compatibility paths.
- Do not rewrite all tools to depend on `RuntimeActorProfile`.

## Functional Requirements

| ID | Requirement |
| --- | --- |
| FR1 | `actor_profile` defines `RuntimeInstanceRecord`, `RuntimeActorProfile`, and `AuthSubject`. |
| FR2 | Actor profile resolution normalizes trusted local instance identity into `RuntimeActorProfile` and `AuthSubject`. |
| FR3 | Env.tool request payload and tool args are not identity sources. |
| FR4 | `role_auth.authorize()` accepts `AuthSubject`; passing a raw string is rejected. |
| FR5 | `role_auth.role_action_summary()` uses `AuthSubject` while preserving the existing runtime policy preview shape. |
| FR6 | `auth_feedback` owns `E_TOOL_ROLE_AUTH` construction, including receipt fields already required by existing contracts. |
| FR7 | `registry` calls `actor_profile`, `role_auth`, `auth_feedback`, and `ToolContext.from_actor_profile()` instead of doing those jobs inline. |
| FR8 | `ToolContext` continues exposing `active_buddy`, `instance_id`, `instance_json`, `instance_payload`, `manifest`, and existing helpers to tools. |
| FR9 | Tool packages do not import `actor_profile`, `RuntimeActorProfile`, or `AuthSubject`. |
| FR10 | Existing behavior for role auth, router ordering, context preview, semantic contract, and message behavior remains unchanged. |

## Test Cases

### T1: Actor profile normalizes trusted runtime identity

File: `tests/test_runtime_actor_profile.py`

Behavior:

- Build a `RuntimeInstanceRecord` with padded `instance_id` and buddy id.
- Resolve it with `resolve_runtime_actor_profile()`.
- Assert:
  - `profile.instance_id` is stripped;
  - `profile.active_buddy` is stripped;
  - `profile.auth_subject` is an `AuthSubject`;
  - `profile.auth_subject.role_id == profile.active_buddy`;
  - `profile.instance_record` is the normalized record.

Expected failure before implementation:

- `env.tool_runtime.actor_profile` does not exist.

### T2: Actor profile rejects missing local identity

File: `tests/test_runtime_actor_profile.py`

Behavior:

- Construct records with blank `instance_id` or blank `buddy_id`.
- Assert `ValueError` names the invalid field.

Expected failure before implementation:

- `RuntimeInstanceRecord` and resolver do not exist.

### T3: Role auth requires `AuthSubject`

File: `tests/test_role_action_auth.py`

Behavior:

- Import `AuthSubject`.
- Replace direct string calls with `AuthSubject(role_id=role)`.
- Add a regression test that `role_auth.authorize("none", "pm", manifest)` raises `TypeError`.

Expected failure before implementation:

- Existing `authorize()` accepts raw strings.

### T4: Role policy preview uses `AuthSubject`

File: `tests/test_role_action_auth.py`

Behavior:

- Call `role_action_summary(AuthSubject(role_id="market"), manifest, operation_semantics)`.
- Keep existing preview shape assertions:
  - `active_role == "market"`;
  - `source == "env.tool role-action policy"`;
  - `not_authorization_boundary is True`;
  - `not_execution_result is True`;
  - `available_actions`, `restricted_actions`, and `restricted_action_details` are present;
  - PM-only actions are restricted for market/dev and available for PM.

Expected failure before implementation:

- Existing function expects a string and cannot consume `AuthSubject`.

### T5: Auth feedback owns role-auth denial response

File: `tests/test_runtime_actor_profile.py`

Behavior:

- Create a denied `AuthDecision`.
- Call `auth_feedback.role_auth_rejection()`.
- Assert the response still contains:
  - `error.code == "E_TOOL_ROLE_AUTH"`;
  - `permission_boundary == "tool.role_authority"`;
  - `category == "auth_denied"`;
  - `auth_source == "env.tool role-action policy"`;
  - `auth_stage == "pre_dispatch"`;
  - `executed is False`;
  - `required_permission`, `active_role`, `allowed_roles`;
  - `state_changed is False`;
  - `durability == "none"`.

Expected failure before implementation:

- `env.tool_runtime.auth_feedback` does not exist.

### T6: Registry dispatch uses actor profile and keeps payload identity inert

File: `tests/test_env_tool_identity.py`

Behavior:

- Dispatch a PM-only action as a dev runtime actor while tool args contain spoofed identity hints such as `active_buddy="pm"` or `buddy="pm"`.
- Assert `E_TOOL_ROLE_AUTH` reports `active_role == "dev"` and denies before payload validation.

Expected failure before implementation:

- The existing behavior already denies as dev, but the test remains a product-level guard for FR3 while module tests drive the red phase.

### T7: ToolContext can be constructed from actor profile

File: `tests/test_runtime_actor_profile.py`

Behavior:

- Resolve a `RuntimeActorProfile`.
- Build `ToolContext.from_actor_profile(profile, ...)`.
- Assert existing tool-facing fields remain:
  - `context.active_buddy == profile.active_buddy`;
  - `context.instance_id == profile.instance_id`;
  - mapping access for `active_buddy`, `instance_id`, `instance_json`, `instance_payload`, `manifest`, and `manifest_path` still works;
  - `context.runtime_policy_preview(operation_semantics)` returns the same preview shape as role auth.

Expected failure before implementation:

- `ToolContext.from_actor_profile()` and `runtime_policy_preview()` do not exist.

### T8: Runtime boundary ownership is searchable

File: `tests/test_runtime_actor_profile.py`

Behavior:

- Assert `registry` no longer exposes `_role_auth_rejection`.
- Assert `scripts/env/tool_runtime/registry.py` does not contain the literal `E_TOOL_ROLE_AUTH`.
- Assert no file under `scripts/env/tools/**` imports `env.tool_runtime.actor_profile` or contains `RuntimeActorProfile`.

Expected failure before implementation:

- `registry.py` currently defines `_role_auth_rejection()` and contains `E_TOOL_ROLE_AUTH`.

### T9: Existing focused behavior stays green

Files:

- `tests/test_role_action_auth.py`
- `tests/test_env_tool_router.py`
- `tests/test_context_binding_env_tool.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_message_env_tool.py`

Behavior:

- Run all focused tests and keep existing assertions unchanged except for the deliberate `AuthSubject` API migration.

Expected failure before implementation:

- New actor-profile tests fail; role-auth tests fail until code consumes `AuthSubject`.

## Verification Commands

Focused red/green loop:

```bash
python3 -m pytest tests/test_runtime_actor_profile.py -q
python3 -m pytest tests/test_role_action_auth.py -q
python3 -m pytest tests/test_env_tool_router.py -q
python3 -m pytest tests/test_context_binding_env_tool.py -q
python3 -m pytest tests/test_env_tool_semantic_contract.py -q
python3 -m pytest tests/test_message_env_tool.py -q
```

Combined focused verification:

```bash
python3 -m pytest \
  tests/test_runtime_actor_profile.py \
  tests/test_role_action_auth.py \
  tests/test_env_tool_router.py \
  tests/test_context_binding_env_tool.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_message_env_tool.py \
  -q
```

Boundary search verification:

```bash
rg -n "E_TOOL_ROLE_AUTH|_role_auth_rejection|RuntimeActorProfile|AuthSubject|role_auth\\.authorize\\(" scripts/env tests
```

Final relevant regression:

```bash
python3 -m pytest tests/test_env_tool_package_independence.py tests/test_runtime_tool_feedback.py tests/test_env_client_payload_cli.py -q
```

## Review Checklist

- Actor identity changes are isolated in `actor_profile`.
- Role policy changes are isolated in `role_auth`.
- Auth-denied response fields are isolated in `auth_feedback`.
- `registry` is orchestration only for the changed path.
- Tool packages still consume `ToolContext` and do not import actor profile internals.
- No product behavior changed in focused role auth, router, context, semantic, or message tests.
- Search results show no old direct auth-feedback entrypoint remains outside the intended boundary.
