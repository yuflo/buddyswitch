# Role Action Auth Test Plan

Date: 2026-05-27
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/clean-runtime-env`

## Goal

Replace manifest-maintained buddy permission lists with one runtime role-action authorization layer for all env tool calls.

The test suite must prove:

- role auth happens before any selected tool service implementation runs;
- denied calls return BuddySwitch-standard structured feedback;
- denied calls do not mutate runtime state;
- allowed calls continue into the existing tool services;
- service/domain rules still own object-state boundaries;
- runtime context reports computed role capabilities rather than manifest permission lists;
- `buddyswitch/manifest.toml` no longer accepts or carries per-buddy `permissions`.

## Current Code Facts

- `scripts/runtime_kernel/dispatcher.py` reads `instance_id` from the broker request, loads the instance record, and passes `instance_record["buddy"]` as `active_buddy` into `dispatch_env_tool_request`.
- `active_buddy` is currently the role id: `market`, `pm`, `design`, `dev`, or `test`.
- `scripts/env/tool_runtime/registry.py` already owns the single env.tool dispatch point and already resolves tool/action definitions before invoking the selected tool.
- `ActionDefinition.required_permission` already exists for every action.
- Existing response helpers in `scripts/env/tool_runtime/results.py` already define the rejection contract: `permission_boundary`, `human_summary`, `why_blocked`, `impact`, `state_changed`, `durability`, `retryable`, `retry_guidance`, and `allowed_next_actions`.
- `scripts/env/tools/context/_impl.py` currently derives `capability_snapshot` from `manifest["buddies"][].permissions`; this must change.
- `scripts/env_manifest.py` currently requires and validates per-buddy `permissions`; this must change.

## Non-Goals

- Do not introduce buddy profile, buddy type, user identity, daemon, workflow engine, DSL, plugin system, or external policy service.
- Do not move `artifact_templates`; template enforcement remains in the artifact service.
- Do not encode product workflow sequencing in auth policy.
- Do not keep a compatibility path that accepts per-buddy manifest `permissions`.
- Do not scatter role checks through individual tools as the primary auth mechanism.

## Functional Requirements

| ID | Requirement |
| --- | --- |
| FR1 | Runtime resolves role from the active instance record: `active_role = active_buddy = instance_record["buddy"]`. |
| FR2 | Env tool dispatch performs centralized role-action auth after tool/action existence is resolved and before args shape validation or selected tool invocation. |
| FR3 | Auth uses each action's `required_permission`; `required_permission == "none"` is allowed for every manifest role. |
| FR4 | The role policy is a simple Python runtime table, not manifest per-buddy permissions and not a DSL. |
| FR5 | Manifest buddy rows no longer include or accept `permissions`. |
| FR6 | Role-auth denial returns `ok: false`, `error.code = "E_TOOL_ROLE_AUTH"`, `permission_boundary = "tool.role_authority"`, `state_changed = false`, `durability = "none"`, actionable `why_blocked`, `retry_guidance`, and `allowed_next_actions`. |
| FR7 | Role-auth denial includes machine-readable `required_permission`, `active_role`, and `allowed_roles`. |
| FR8 | Denied calls do not import or execute the selected tool `_impl` module. |
| FR9 | Allowed calls still import and execute the selected tool service. |
| FR10 | PM-only role permissions are enforced centrally for `track.create`, `track.archive`, and `comment.resolve`. |
| FR11 | Common collaboration permissions remain allowed for all roles at role-auth level; domain services continue to enforce requester/recipient, owner, archive, template, and target-state rules. |
| FR12 | Existing domain rejection boundaries remain distinct from role auth boundaries. |
| FR13 | `context.get` and `context.summarize` expose computed role capability information from runtime auth policy, not manifest permissions. |
| FR14 | Tool catalog and operation semantics still expose action `required_permission`; they do not become workflow guidance. |
| FR15 | Full tests still prove response contracts, manifest contracts, router behavior, context behavior, and representative tool behavior. |

## Role Policy Expected Shape

The policy should be behavior-preserving except for removing fake manifest ACL semantics.

| Permission | Allowed roles | Boundary owner after allow |
| --- | --- | --- |
| `none` | all manifest roles | selected tool |
| `track.read` | all manifest roles | track service |
| `track.update_now` | all manifest roles | track service |
| `track.add_material` | all manifest roles | track/artifact scope rules |
| `track.add_update` | all manifest roles | track service |
| `track.add_proof` | all manifest roles | track/artifact scope rules |
| `track.create` | `pm` | track service payload/state rules |
| `track.archive` | `pm` | track service payload/state rules |
| `task.read` | all manifest roles | task service |
| `task.propose` | all manifest roles | task service |
| `task.confirm` | all manifest roles | task service |
| `artifact.read` | all manifest roles | artifact visibility rules |
| `artifact.create` | all manifest roles | artifact template rules |
| `artifact.update` | all manifest roles | artifact owner/status/template rules |
| `message.send` | all manifest roles | message target/self-send rules |
| `message.list` | all manifest roles | message inbox visibility rules |
| `comment.add` | all manifest roles | comment target scope rules |
| `comment.list` | all manifest roles | comment target visibility rules |
| `comment.resolve` | `pm` | comment state rules |
| `request.read` | all manifest roles | request visibility rules |
| `request.create` | all manifest roles | request target/self-request rules |
| `request.accept` | all manifest roles | request recipient/state rules |
| `request.block` | all manifest roles | request recipient/state rules |
| `request.complete` | all manifest roles | request recipient/state rules |
| `request.cancel` | all manifest roles | request requester/state rules |
| `evidence.issue` | all manifest roles | evidence target ownership rules |
| `evidence.approve` | all manifest roles | evidence target ownership/reason rules |

Search actions currently declare `required_permission = "none"` and remain role-auth allowed for all roles. Search profile/backend rules remain in the search service.

## Test Cases

### T1: Manifest no longer carries buddy permissions

File: `tests/test_env_manifest_v2.py`

Behavior:

- `env_manifest.load_manifest()` succeeds when buddy rows contain `id`, `label`, `scope`, `skills`, and `artifact_templates`.
- Every loaded buddy lacks a `permissions` key.
- A synthetic manifest containing `[[buddies]].permissions` raises `ManifestError`.
- `show-buddy` output no longer includes `permissions`, `object_permissions`, or `permission_scope = "manual_debug_apis"`.

Expected failure before implementation:

- Existing manifest still contains `permissions`.
- Existing validator requires `permissions`.

### T2: Role policy covers every registered action

File: `tests/test_role_action_auth.py`

Behavior:

- For every action in `tool_registry.operation_semantics()`, `role_auth.allowed_roles_for_permission(required_permission, manifest_roles)` returns a non-empty role set.
- Returned roles are a subset of manifest buddy ids.
- `required_permission == "none"` returns all manifest roles.
- Unknown required permission raises or returns a deny decision with policy error metadata; no silent allow.

Expected failure before implementation:

- `scripts/env/tool_runtime/role_auth.py` does not exist.

### T3: Central role auth denies before selected tool implementation import

File: `tests/test_env_tool_router.py` or `tests/test_role_action_auth.py`

Behavior:

- In a subprocess, block import of `env.tools.track._impl`.
- Dispatch `{"tool": "track", "action": "create", "args": {...}}` as `dev`.
- Response is role-auth denial:
  - `ok: false`
  - `error.code: E_TOOL_ROLE_AUTH`
  - `permission_boundary: tool.role_authority`
  - `required_permission: track.create`
  - `active_role: dev`
  - `allowed_roles: ["pm"]`
  - `state_changed: false`
  - `durability: none`
- Loaded private impl modules do not include `env.tools.track._impl`.

Expected failure before implementation:

- Current dispatch invokes `track._impl`, which returns `track.lifecycle_authority` and imports the selected service.

### T4: Allowed role still reaches selected tool implementation

File: `tests/test_env_tool_router.py` or `tests/test_role_action_auth.py`

Behavior:

- In a subprocess, block import of `env.tools.track._impl`.
- Dispatch `track.create` as `pm`.
- Response is `E_ENV_TOOL_DISPATCH` with `permission_boundary = "env.tool.dispatch"` and `why_blocked` mentioning the blocked import.

This proves auth does not bypass service execution for allowed roles.

Expected failure before implementation:

- Current behavior already reaches the service, but there is no paired central auth proof.

### T4.5: Role denial wins before args payload validation

File: `tests/test_env_tool_router.py` or `tests/test_role_action_auth.py`

Behavior:

- Dispatch `track.create` as `dev` with `args` set to a non-object value.
- Response is still role-auth denial:
  - `error.code: E_TOOL_ROLE_AUTH`
  - `permission_boundary: tool.role_authority`
  - `required_permission: track.create`
  - `active_role: dev`
- Response is not `E_ENV_TOOL_PAYLOAD`.

Expected failure before implementation:

- Current dispatch validates `payload.args` before any role authority check.

### T5: Role auth denies state-changing PM-only actions without state mutation

Files: `tests/test_role_action_auth.py`, `tests/test_track_env_tool.py`, `tests/test_comment_env_tool.py`

Representative cases:

- `dev` cannot `track.create`.
- `design` cannot `track.archive`.
- `test` cannot `comment.resolve`.

For each:

- Response follows role-auth rejection contract.
- Persisted runtime objects are unchanged:
  - no created track file for denied `track.create`;
  - archived state unchanged for denied `track.archive`;
  - comment status unchanged for denied `comment.resolve`.

Expected failure before implementation:

- Track/comment services return tool-specific authority boundaries and may import service code before denial.

### T6: Domain rules still apply after role auth allows the action

Files: existing domain tool tests plus targeted additions.

Representative cases:

- `pm` can pass role auth for `comment.resolve`, then gets existing comment-state rejection when resolving an already resolved comment.
- `dev` can pass role auth for `request.accept`, then gets `request.recipient_scope` if not recipient.
- `design` can pass role auth for `artifact.create_revision`, then gets `artifact.template_permission` if using a disallowed template.
- `market` can pass role auth for `evidence.issue_browser`, then gets `artifact.authors` for a readable but non-authored artifact.

Expected result:

- Existing service-specific `permission_boundary` values remain intact.

### T7: Context reports runtime-computed role capabilities

Files: `tests/test_context_binding_env_tool.py`, `tests/test_env_tool_response_contract.py`

Behavior:

- `context.summarize` for `dev` includes role capability data derived from auth policy:
  - `active_role: "dev"`
  - `role_authority_source: "env.tool role action policy"` or equivalent explicit value
  - `allowed_actions` includes `track.list`, `request.accept`, `artifact.create_revision`
  - `denied_actions` includes `track.create`, `track.archive`, `comment.resolve`
- `context.get` includes enough detail to map denied actions to `required_permission` and `allowed_roles`.
- Context output does not include `object_permissions` or manifest-derived buddy permission lists.
- Summary remains compact and does not include full JSON schema details.

Expected failure before implementation:

- Current `capability_snapshot` is driven by manifest permissions and does not expose computed allowed/denied action lists.

### T8: Tool catalog remains role-neutral and semantic

Files: `tests/test_env_tool_semantic_contract.py`, `tests/test_env_tool_schema_contract.py`

Behavior:

- Every action still declares `required_permission` and `authority`.
- Tool catalog does not encode workflow steps.
- Operation semantics do not become active-role-specific.
- Role-specific capability data lives in context/auth policy helpers, not in `ActionDefinition`.

### T9: Runtime broker keeps instance-id and active-role boundary

File: `tests/test_runtime_broker.py`

Behavior:

- Broker still rejects mismatched request `instance_id`.
- Broker still rejects mismatched request `active_buddy`.
- For matching request, dispatch uses `instance_record["buddy"]` as the active role for auth.

Expected result:

- Multiple instances with the same role remain separate by `instance_id`.

### T10: Residue and architecture scans

Files: `tests/test_repo_consistency.py` or focused grep verification.

Behavior:

- No `permissions = [` remains in `buddyswitch/manifest.toml`.
- No `buddy_permissions(` helper remains unless renamed and repurposed away from manifest permissions.
- No `object_permissions` remains in manifest output or context.
- No new role checks are scattered as the primary auth mechanism in individual tools.
- Existing service state checks may remain where they enforce domain rules.

## Focused Test Commands

Run after each implementation block:

```bash
python3 -m pytest tests/test_env_manifest_v2.py -q
python3 -m pytest tests/test_role_action_auth.py -q
python3 -m pytest tests/test_env_tool_router.py -q
python3 -m pytest tests/test_context_binding_env_tool.py -q
```

Then run contract/domain coverage:

```bash
python3 -m pytest \
  tests/test_env_tool_response_contract.py \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_track_env_tool.py \
  tests/test_comment_env_tool.py \
  tests/test_request_env_tool.py \
  tests/test_artifact_env_tool.py \
  tests/test_evidence_env_tool.py \
  tests/test_search_env_tool.py \
  -q
```

Then run architecture and launcher-adjacent checks:

```bash
python3 -m pytest \
  tests/test_runtime_broker.py \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  -q
```

Final verification:

```bash
git diff --check
python3 -m pytest -q
pgrep -fl "fake_codex.py|app-server --listen|buddyswitch-app-server|runtime-broker" || true
```

If a broad suite cannot run because of environment or resources, stop and report the blocker with the focused coverage already completed.

## Review Checklist

- [ ] Manifest no longer stores per-buddy permissions.
- [ ] Role policy is centralized and simple.
- [ ] Registry dispatch performs auth before selected tool invocation.
- [ ] Denied auth response uses existing ToolResult rejection semantics.
- [ ] Denied auth response includes `required_permission`, `active_role`, and `allowed_roles`.
- [ ] Context uses runtime auth policy, not manifest permissions.
- [ ] Individual tools retain only payload/domain/state checks.
- [ ] `artifact_templates` remains unchanged.
- [ ] No prompt, skill, or AGENTS text is used to compensate for auth behavior.
- [ ] Tests prove denied state unchanged and allowed service path still works.
