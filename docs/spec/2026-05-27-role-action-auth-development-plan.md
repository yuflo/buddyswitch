# Role Action Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace manifest-maintained buddy permission lists with centralized runtime role-action authorization for every env tool call.

**Architecture:** Runtime broker still resolves `instance_id` to an instance record and passes `instance_record["buddy"]` as `active_buddy`. A new centralized `env.tool_runtime.role_auth` module treats `active_buddy` as the current role, checks the selected action's `required_permission`, and returns a BuddySwitch-standard rejection before service invocation when the role is not allowed. Tool services keep domain and state rules.

**Tech Stack:** Python stdlib, existing env tool runtime registry/definition/results modules, TOML manifest loader, pytest/unittest test suite.

---

## Scope

Implement the whole auth cleanup in one forward change:

- add centralized role-action auth policy;
- wire auth into `dispatch_env_tool_request`;
- remove per-buddy manifest `permissions`;
- update context capability reporting to use runtime auth policy;
- update contract, manifest, router, and domain tests;
- verify full relevant suite.

Do not add compatibility handling for old manifest permissions.

## Target Design

### Identity Model

Runtime identity remains:

```text
instance_id -> instance record -> record["buddy"] -> active_buddy
```

For this task:

```text
active_role = active_buddy
```

There is no separate buddy profile, buddy type, user id, or profile mapping.

### Auth Layers

```text
runtime broker
  -> dispatch_env_tool_request
  -> load selected ToolDefinition and ActionDefinition
  -> role_auth.authorize_action(active_role, action_definition, manifest)
  -> allowed: validate args payload shape
  -> allowed: invoke selected tool service
  -> denied: return tool_results.rejection(...)
```

Tool services keep:

- payload validation;
- track archive and lifecycle status checks;
- request requester/recipient checks;
- artifact ownership/template/status checks;
- comment target/state checks;
- evidence target ownership checks;
- search backend/profile checks.

### Role Policy

Use a small Python module, not manifest data and not a DSL.

Policy should allow these common permissions to every manifest role:

```python
COMMON_ROLE_PERMISSIONS = frozenset(
    {
        "track.read",
        "track.update_now",
        "track.add_material",
        "track.add_update",
        "track.add_proof",
        "task.read",
        "task.propose",
        "task.confirm",
        "artifact.read",
        "artifact.create",
        "artifact.update",
        "message.send",
        "message.list",
        "comment.add",
        "comment.list",
        "request.read",
        "request.create",
        "request.accept",
        "request.block",
        "request.complete",
        "request.cancel",
        "evidence.issue",
        "evidence.approve",
    }
)
```

PM-only additions:

```python
ROLE_PERMISSION_ADDITIONS = {
    "pm": frozenset({"track.create", "track.archive", "comment.resolve"}),
}
```

`required_permission == "none"` is always allowed for every manifest role.

## Files To Modify

- Create: `scripts/env/tool_runtime/role_auth.py`
- Modify: `scripts/env/tool_runtime/registry.py`
- Modify: `scripts/env/tools/context/_impl.py`
- Modify: `scripts/env_manifest.py`
- Modify: `buddyswitch/manifest.toml`
- Modify: `tests/test_env_manifest_v2.py`
- Create: `tests/test_role_action_auth.py`
- Modify: `tests/test_env_tool_router.py`
- Modify: `tests/test_context_binding_env_tool.py`
- Modify: `tests/test_env_tool_response_contract.py`
- Modify as needed: `tests/test_track_env_tool.py`, `tests/test_comment_env_tool.py`, `tests/test_request_env_tool.py`, `tests/test_artifact_env_tool.py`, `tests/test_evidence_env_tool.py`, `tests/test_runtime_broker.py`, `tests/test_repo_consistency.py`

## Task 1: Lock Manifest Permission Removal Tests

**Files:**
- Modify: `tests/test_env_manifest_v2.py`
- Test: `tests/test_env_manifest_v2.py`

- [ ] **Step 1: Replace permission-list expectations with removal expectations**

Change tests that inspect `buddy["permissions"]` so they assert:

```python
for buddy in self.manifest.get("buddies", []):
    assert isinstance(buddy, dict)
    self.assertNotIn("permissions", buddy, msg=buddy.get("id"))
```

Keep existing checks that every buddy has message/comment/request skills. Remove checks requiring message/comment/request permissions in manifest.

- [ ] **Step 2: Add a rejected legacy permissions test**

Add a synthetic manifest fixture or helper that injects a `permissions` key into one buddy row and asserts:

```python
with self.assertRaisesRegex(env_manifest.ManifestError, "permissions.*retired"):
    env_manifest.load_manifest(path_with_permissions)
```

Use a temporary file under the test runtime temp directory; do not edit product runtime objects.

- [ ] **Step 3: Run the focused test and confirm failure**

Run:

```bash
python3 -m pytest tests/test_env_manifest_v2.py -q
```

Expected before implementation: failure because `manifest.toml` still contains `permissions` and `load_manifest` still requires them.

## Task 2: Remove Manifest Permissions From Manifest Loader And Manifest

**Files:**
- Modify: `scripts/env_manifest.py`
- Modify: `buddyswitch/manifest.toml`
- Test: `tests/test_env_manifest_v2.py`

- [ ] **Step 1: Update manifest loader contract**

In `scripts/env_manifest.py`:

- update the module docstring so buddy rows define skills and artifact templates, not permissions;
- remove `_validate_permission` if no test still owns it;
- stop requiring `buddy["permissions"]`;
- reject a `permissions` key on any buddy row with a clear `ManifestError`;
- remove `buddy_permissions`;
- remove `object_permissions` and `permission_scope` from `buddy_authority_profile`;
- update `runtime_note` to say role-action authority is owned by env.tool runtime policy.

- [ ] **Step 2: Remove manifest permission lists**

In `buddyswitch/manifest.toml`, delete every buddy-level `permissions = [...]` entry. Do not change skills, labels, scopes, or `artifact_templates`.

- [ ] **Step 3: Run focused manifest tests**

Run:

```bash
python3 -m pytest tests/test_env_manifest_v2.py -q
```

Expected: pass.

## Task 3: Add Central Role Auth Policy

**Files:**
- Create: `scripts/env/tool_runtime/role_auth.py`
- Create: `tests/test_role_action_auth.py`

- [ ] **Step 1: Write failing policy coverage tests**

Add tests that load the real manifest and registry and assert:

- every manifest buddy id is a role id;
- every `required_permission` in `tool_registry.operation_semantics()` is covered;
- `"none"` returns all roles;
- `track.create`, `track.archive`, and `comment.resolve` return only `{"pm"}`;
- common permissions return all roles;
- unknown active role is denied;
- unknown permission is denied with policy metadata.

- [ ] **Step 2: Run the new tests and confirm failure**

Run:

```bash
python3 -m pytest tests/test_role_action_auth.py -q
```

Expected: import failure for missing `env.tool_runtime.role_auth`.

- [ ] **Step 3: Implement `role_auth.py`**

Create `scripts/env/tool_runtime/role_auth.py` with these responsibilities:

- `manifest_role_ids(manifest: dict[str, Any]) -> frozenset[str]`
- `allowed_permissions_for_role(role: str, manifest: dict[str, Any]) -> frozenset[str]`
- `allowed_roles_for_permission(required_permission: str, manifest: dict[str, Any]) -> frozenset[str]`
- `authorize(required_permission: str, active_role: str, manifest: dict[str, Any]) -> AuthDecision`
- `role_action_summary(active_role: str, manifest: dict[str, Any], operation_semantics: dict[str, dict[str, Any]]) -> dict[str, Any]`

Use a frozen dataclass for `AuthDecision`:

```python
@dataclass(frozen=True)
class AuthDecision:
    allowed: bool
    required_permission: str
    active_role: str
    allowed_roles: tuple[str, ...]
    reason: str
```

No file IO, no imports from individual tools, no manifest mutation.

- [ ] **Step 4: Run role auth tests**

Run:

```bash
python3 -m pytest tests/test_role_action_auth.py -q
```

Expected: pass.

## Task 4: Wire Auth Into Registry Dispatch

**Files:**
- Modify: `scripts/env/tool_runtime/registry.py`
- Modify: `tests/test_env_tool_router.py`
- Modify/Create: `tests/test_role_action_auth.py`

- [ ] **Step 1: Add failing central deny-before-import test**

Use a subprocess test similar to `test_selected_dispatch_imports_no_sibling_private_impl_modules`, but block `env.tools.track._impl`.

Dispatch as `dev`:

```json
{"tool": "track", "action": "create", "args": {"track_id": "track-denied", "title": "Denied", "outcome": "x", "appetite": "1d"}}
```

Assert:

- `ok` is false;
- `error.code` is `E_TOOL_ROLE_AUTH`;
- `permission_boundary` is `tool.role_authority`;
- `required_permission` is `track.create`;
- `active_role` is `dev`;
- `allowed_roles` is `["pm"]`;
- `state_changed` is false;
- no selected `_impl` was imported.

- [ ] **Step 2: Add allowed-role reaches-service test**

In the same blocked-import setup, dispatch the same action as `pm`. Assert response is `E_ENV_TOOL_DISPATCH` with `permission_boundary = "env.tool.dispatch"`, proving auth allowed the call to reach service import.

- [ ] **Step 3: Add denied-role malformed-args ordering test**

Dispatch `track.create` as `dev` with `args` set to a non-object value. Assert the response is `E_TOOL_ROLE_AUTH` with `permission_boundary = "tool.role_authority"`, not `E_ENV_TOOL_PAYLOAD`.

- [ ] **Step 4: Run router/auth tests and confirm failure**

Run:

```bash
python3 -m pytest tests/test_env_tool_router.py tests/test_role_action_auth.py -q
```

Expected: central role-auth expectations fail before registry wiring.

- [ ] **Step 5: Implement registry auth check**

In `dispatch_env_tool_request`, after selected tool/action validation and before args shape validation, `ToolContext` construction, and `_invoke_tool`:

- load the selected `ActionDefinition`;
- call `role_auth.authorize(action_definition.required_permission, active_buddy, manifest)`;
- if denied, return `tool_results.rejection(...)` with:
  - `code="E_TOOL_ROLE_AUTH"`;
  - `permission_boundary="tool.role_authority"`;
  - `human_summary="Active role is not allowed to run this tool action."`;
  - `why_blocked` naming required permission, active role, and allowed roles;
  - `impact="No env action ran and runtime state was unchanged."`;
  - `state_changed=False`;
  - `durability="none"`;
  - `retryable=False`;
  - `retry_guidance="Use an action allowed for this role, or ask an allowed role to perform this action."`;
  - `allowed_next_actions` pointing to `context.summarize`/`context.get`;
  - extra machine fields `required_permission`, `active_role`, `allowed_roles`.

- [ ] **Step 6: Run router/auth tests**

Run:

```bash
python3 -m pytest tests/test_env_tool_router.py tests/test_role_action_auth.py -q
```

Expected: pass.

## Task 5: Prove Denied State Is Unchanged And Domain Rules Remain

**Files:**
- Modify: `tests/test_track_env_tool.py`
- Modify: `tests/test_comment_env_tool.py`
- Modify: `tests/test_request_env_tool.py`
- Modify: `tests/test_artifact_env_tool.py`
- Modify: `tests/test_evidence_env_tool.py`

- [ ] **Step 1: Update PM-only denial expectations**

Replace tests expecting `track.lifecycle_authority` or `comment.pm_review_authority` for role-denied calls with `tool.role_authority`.

For denied `track.create`, assert no track appears through repo/list/open after denial.

For denied `track.archive`, seed a track as PM, deny archive as non-PM, then assert the track remains unarchived.

For denied `comment.resolve`, seed an open comment, deny resolve as non-PM, then assert status remains `open`.

- [ ] **Step 2: Add/keep domain-rule tests**

Ensure tests still prove:

- PM resolving an already resolved comment returns `comment.state`;
- non-recipient `request.accept` returns `request.recipient_scope`;
- invalid artifact template returns `artifact.template_permission`;
- evidence target not authored by active role returns `artifact.authors`;
- archived track writes return `track.lifecycle_status`.

- [ ] **Step 3: Run focused domain tests**

Run:

```bash
python3 -m pytest \
  tests/test_track_env_tool.py \
  tests/test_comment_env_tool.py \
  tests/test_request_env_tool.py \
  tests/test_artifact_env_tool.py \
  tests/test_evidence_env_tool.py \
  -q
```

Expected: pass.

## Task 6: Update Context Capability Reporting

**Files:**
- Modify: `scripts/env/tools/context/_impl.py`
- Modify: `tests/test_context_binding_env_tool.py`
- Modify: `tests/test_env_tool_response_contract.py`

- [ ] **Step 1: Write failing context tests**

Update context tests so `context.summarize` for `dev` expects `capability_snapshot` to include:

```python
{
    "active_role",
    "role_authority_source",
    "allowed_actions",
    "denied_actions",
    "denied_action_details",
    ...
}
```

Assert:

- `active_role == "dev"`;
- `role_authority_source` names env.tool role action policy;
- `allowed_actions` contains `track.list`, `artifact.create_revision`, and `request.accept`;
- `denied_actions` contains `track.create`, `track.archive`, and `comment.resolve`;
- `denied_action_details` rows include `required_permission` and `allowed_roles`;
- no `object_permissions` appears.

- [ ] **Step 2: Run context tests and confirm failure**

Run:

```bash
python3 -m pytest tests/test_context_binding_env_tool.py tests/test_env_tool_response_contract.py -q
```

Expected: failure because context still reads manifest permissions.

- [ ] **Step 3: Implement context changes**

In `scripts/env/tools/context/_impl.py`:

- remove `_active_buddy_permissions`;
- import `env.tool_runtime.role_auth`;
- build capability snapshot from `role_auth.role_action_summary(...)`;
- keep existing non-auth context fields such as task visibility, artifact publication path, search boundary, evidence boundary, and writable file surface;
- keep `context.summarize` compact by including action names and concise denied details, not full schemas.

- [ ] **Step 4: Run context tests**

Run:

```bash
python3 -m pytest tests/test_context_binding_env_tool.py tests/test_env_tool_response_contract.py -q
```

Expected: pass.

## Task 7: Update Contract And Architecture Tests

**Files:**
- Modify: `tests/test_env_tool_schema_contract.py`
- Modify: `tests/test_env_tool_semantic_contract.py`
- Modify: `tests/test_runtime_broker.py`
- Modify: `tests/test_repo_consistency.py`
- Modify as needed: `tests/test_runtime_skills.py`

- [ ] **Step 1: Schema and semantics**

Keep tests requiring every action to declare `required_permission` and `authority`.

Add or update tests proving:

- every declared `required_permission` is covered by `role_auth`;
- `operation_semantics` remains role-neutral;
- role-specific allowed/denied data comes from context/auth helpers, not from `ActionDefinition`.

- [ ] **Step 2: Runtime broker identity boundary**

Keep tests proving:

- broker rejects mismatched `instance_id`;
- broker rejects mismatched `active_buddy`;
- matching request uses `instance_record["buddy"]` as active role for role auth.

- [ ] **Step 3: Repo consistency scans**

Add scans proving:

```bash
rg -n "permissions = \\[" buddyswitch/manifest.toml
rg -n "buddy_permissions|object_permissions|manual_debug_apis" scripts tests buddyswitch
```

Expected: no active runtime references. Historical docs may be excluded from scans.

- [ ] **Step 4: Run contract tests**

Run:

```bash
python3 -m pytest \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_runtime_broker.py \
  tests/test_repo_consistency.py \
  tests/test_runtime_skills.py \
  -q
```

Expected: pass.

## Task 8: Update User-Facing Skill/Docs Text Only Where It Mirrors Runtime Permissions

**Files:**
- Modify as needed: `buddyswitch/skills/shared/*.md`
- Modify as needed: `tools/launcher/assets/buddies/*/AGENTS.md`

- [ ] **Step 1: Search for stale permission-source wording**

Run:

```bash
rg -n "manifest.*permission|object_permissions|manual_debug_apis|buddy permissions|permissions list" buddyswitch tools/launcher/assets tests
```

- [ ] **Step 2: Update only stale runtime-source claims**

Do not add long prompt instructions. If wording says manifest is the permission source, replace it with a concise pointer to runtime tool feedback and context discovery.

- [ ] **Step 3: Run skill/docs tests**

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

Expected: pass.

## Task 9: Final Verification And Review

**Files:**
- All changed files.

- [ ] **Step 1: Run focused auth suite**

Run:

```bash
python3 -m pytest \
  tests/test_env_manifest_v2.py \
  tests/test_role_action_auth.py \
  tests/test_env_tool_router.py \
  tests/test_context_binding_env_tool.py \
  -q
```

- [ ] **Step 2: Run related contract/domain suite**

Run:

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
  tests/test_runtime_broker.py \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  -q
```

- [ ] **Step 3: Run full suite if environment permits**

Run:

```bash
python3 -m pytest -q
```

If this cannot run because of environment or resources, stop and report the blocker.

- [ ] **Step 4: Static diff checks**

Run:

```bash
git diff --check
rg -n "permissions = \\[" buddyswitch/manifest.toml
rg -n "buddy_permissions|object_permissions|manual_debug_apis" scripts tests buddyswitch
```

Expected:

- `git diff --check` passes;
- no manifest permission list remains;
- no active runtime `buddy_permissions` or `object_permissions` references remain.

- [ ] **Step 5: Resource residual check**

Run:

```bash
pgrep -fl "fake_codex.py|app-server --listen|buddyswitch-app-server|runtime-broker" || true
```

Expected: no unexpected residual processes from tests.

- [ ] **Step 6: Review against plan**

Review diff for:

- no manifest per-buddy permission compatibility;
- no auth checks scattered as primary enforcement inside individual tools;
- role auth happens before selected tool service import;
- service/domain boundaries remain intact;
- context does not present manifest permissions as authority;
- `artifact_templates` unchanged;
- no workflow sequencing in auth policy;
- response feedback matches BuddySwitch rejection contract.

## Known Watch Points

- `evidence.approve` was not present in old manifest permission lists, but existing runtime behavior allowed the action because manifest permissions were not centrally enforced. The new policy should allow it for all roles at role-auth level and leave ownership/reason checks to the evidence service.
- Search actions currently use `required_permission = "none"`; do not invent `search.use` in this change.
- PM-only checks currently exist in `track` and `comment` services. After central auth is in place, remove or relax duplicate role checks only if tests still prove service domain rules. Do not remove state checks.
- Historical docs/spec files may mention old manifest permissions. Active code, manifest, skills, and tests should be updated; old historical docs do not need churn unless a repo consistency test requires it.
