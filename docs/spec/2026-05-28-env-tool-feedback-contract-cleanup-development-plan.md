# Env Tool Feedback Contract Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make env.tool role-auth feedback read as a runtime execution receipt, and make context role-policy data read as a non-authoritative planning preview.

**Architecture:** Keep forced auth in `registry.py + role_auth.py`, keep context as a read-only env tool, and keep tool/domain `_impl.py` files responsible for payload/resource/lifecycle rejections. This is a one-time contract migration: remove old auth preview fields and old permission-ownership wording rather than keeping compatibility fields.

**Tech Stack:** Python stdlib, existing env.tool runtime registry/results/context modules, TOML manifest loader, pytest/unittest test suite.

---

## Scope

Implement the complete feedback cleanup in one forward change:

- add receipt fields to `E_TOOL_ROLE_AUTH`;
- rename role-action summary output to runtime policy preview terms;
- nest preview under `capability_snapshot.runtime_policy_preview`;
- remove old auth preview keys;
- remove `active buddy owns ... permission` tool metadata wording;
- preserve receipt fields through `scripts/env/client.py`;
- update focused tests and run relevant verification.

Do not keep old and new preview fields side by side.

## Current Code Map

| File | Current responsibility | Planned change |
| --- | --- | --- |
| `scripts/env/tool_runtime/registry.py` | Env tool catalog, operation semantics, dispatch, role-auth rejection | Add auth-denied receipt fields and rewrite auth-denied human guidance. |
| `scripts/env/tool_runtime/role_auth.py` | Runtime role-action policy and old allowed/denied action summary | Return `runtime_policy_preview` shape from `role_action_summary()`. |
| `scripts/env/tools/context/_impl.py` | Read-only context sections and capability snapshot | Put role preview under `capability_snapshot.runtime_policy_preview`; remove old auth keys. |
| `scripts/env/client.py` | CLI wrapper for broker-routed env.tool calls | Preserve receipt fields at top level when broker returns an env.tool rejection. |
| `scripts/env/tools/message/tool.py` | Message action metadata | Replace old permission-ownership precondition text. |
| `scripts/env/tools/task/tool.py` | Task action metadata | Replace old permission-ownership precondition text. |
| `scripts/env/tools/artifact/tool.py` | Artifact action metadata | Replace old permission-ownership precondition text. |
| `scripts/env/tools/track/tool.py` | Track action metadata | Replace old permission-ownership precondition text. |
| `tests/test_env_tool_router.py` | Dispatch/router behavior tests | Assert new `E_TOOL_ROLE_AUTH` receipt fields and wording. |
| `tests/test_role_action_auth.py` | Role policy unit tests | Assert new preview shape and old key removal. |
| `tests/test_context_binding_env_tool.py` | Context env tool tests | Assert nested `runtime_policy_preview` in summarize/get. |
| `tests/test_env_tool_response_contract.py` | Response contract tests | Assert context preview contract and old key removal. |
| `tests/test_env_tool_semantic_contract.py` | Catalog/operation semantics tests | Assert old permission-ownership text is absent and semantics remain role-neutral. |
| `tests/test_env_client_payload_cli.py` | CLI env client tests | Assert broker error receipt fields are preserved top-level. |
| `tests/test_env_manifest_v2.py` | Manifest contract tests | Keep regression guard that buddy `permissions` is retired. |

## Target Contracts

### Auth Denied Receipt

`registry._role_auth_rejection()` should return a payload with these fields:

```python
{
    "ok": False,
    "error": {
        "code": "E_TOOL_ROLE_AUTH",
        "message": "active role is not allowed to run this tool action",
    },
    "permission_boundary": "tool.role_authority",
    "category": "auth_denied",
    "auth_source": "env.tool role-action policy",
    "auth_stage": "pre_dispatch",
    "executed": False,
    "required_permission": "track.create",
    "active_role": "market",
    "allowed_roles": ["pm"],
    "state_changed": False,
    "durability": "none",
    "retryable": False,
}
```

The human text should say the action is restricted by role-action policy. It should not say `requires permission`, `owns permission`, or `manifest permissions`.

### Runtime Policy Preview

`role_auth.role_action_summary(active_role, manifest, operation_semantics)` should return:

```python
{
    "active_role": active_role,
    "source": "env.tool role-action policy",
    "not_authorization_boundary": True,
    "not_execution_result": True,
    "available_actions": ["track.list", "comment.add"],
    "restricted_actions": ["track.create", "track.archive", "comment.resolve"],
    "restricted_action_details": {
        "track.create": {
            "required_permission": "track.create",
            "active_role": "market",
            "restricted_to_roles": ["pm"],
            "reason": "active role 'market' is not allowed by env.tool role-action policy",
        },
    },
}
```

`context.get` and `context.summarize` should expose this as:

```python
payload["capability_snapshot"]["runtime_policy_preview"]
```

`capability_snapshot` may keep non-auth fields such as `task_visibility`, `artifact_publication_path`, `comment_target_support`, `request_lifecycle_visibility`, `search_boundary`, `evidence_boundary`, and `writable_file_surface`.

## Task 1: Update Auth Denial Receipt Tests

**Files:**

- Modify: `tests/test_env_tool_router.py`
- Test: `tests/test_env_tool_router.py`

- [ ] **Step 1: Add a router test helper for role-auth receipt assertions**

Add a private helper in `EnvToolRouterTests`:

```python
def _assert_role_auth_receipt(
    self,
    response: dict[str, object],
    *,
    required_permission: str,
    active_role: str,
) -> None:
    self.assertFalse(response.get("ok"), msg=response)
    self.assertEqual((response.get("error") or {}).get("code"), "E_TOOL_ROLE_AUTH")
    self.assertEqual(response.get("permission_boundary"), "tool.role_authority")
    self.assertEqual(response.get("category"), "auth_denied")
    self.assertEqual(response.get("auth_source"), "env.tool role-action policy")
    self.assertEqual(response.get("auth_stage"), "pre_dispatch")
    self.assertIs(response.get("executed"), False)
    self.assertEqual(response.get("required_permission"), required_permission)
    self.assertEqual(response.get("active_role"), active_role)
    self.assertEqual(response.get("allowed_roles"), ["pm"])
    self.assertIs(response.get("state_changed"), False)
    self.assertEqual(response.get("durability"), "none")
    why_blocked = str(response.get("why_blocked", ""))
    self.assertIn("role-action policy", why_blocked)
    self.assertNotIn("requires permission", why_blocked)
    self.assertNotIn("owns permission", why_blocked)
```

- [ ] **Step 2: Use the helper in existing role-auth router tests**

Update:

- `test_role_auth_denies_before_selected_private_impl_import`;
- `test_role_auth_denial_precedes_args_shape_validation`.

Keep their existing assertions that `_impl` import does not happen and args validation loses to auth.

- [ ] **Step 3: Run focused router tests and confirm failure**

Run:

```bash
python3 -m pytest tests/test_env_tool_router.py -q
```

Expected before implementation:

- failure because `category`, `auth_source`, `auth_stage`, and `executed` are missing;
- failure because `why_blocked` contains `requires permission`.

## Task 2: Update Role Policy Preview Tests

**Files:**

- Modify: `tests/test_role_action_auth.py`
- Test: `tests/test_role_action_auth.py`

- [ ] **Step 1: Add preview shape test**

Add:

```python
def test_role_action_summary_returns_runtime_policy_preview_shape(self) -> None:
    summary = role_auth.role_action_summary("market", self.manifest, self.operation_semantics)
    self.assertEqual(summary.get("active_role"), "market")
    self.assertEqual(summary.get("source"), "env.tool role-action policy")
    self.assertIs(summary.get("not_authorization_boundary"), True)
    self.assertIs(summary.get("not_execution_result"), True)
    self.assertIsInstance(summary.get("available_actions"), list, msg=summary)
    self.assertIsInstance(summary.get("restricted_actions"), list, msg=summary)
    self.assertIsInstance(summary.get("restricted_action_details"), dict, msg=summary)
    for old_key in (
        "role_authority_source",
        "allowed_actions",
        "denied_actions",
        "denied_action_details",
        "allowed_action_permissions",
    ):
        self.assertNotIn(old_key, summary)
    self.assertIn("track.list", summary["available_actions"])
    self.assertIn("artifact.create_revision", summary["available_actions"])
    self.assertIn("request.accept", summary["available_actions"])
    self.assertIn("track.create", summary["restricted_actions"])
    self.assertIn("track.archive", summary["restricted_actions"])
    self.assertIn("comment.resolve", summary["restricted_actions"])
    details = summary["restricted_action_details"]
    self.assertEqual(details.get("track.create", {}).get("required_permission"), "track.create")
    self.assertEqual(details.get("track.create", {}).get("restricted_to_roles"), ["pm"])
```

- [ ] **Step 2: Add PM preview behavior check**

Add:

```python
def test_pm_preview_has_no_pm_only_restricted_actions(self) -> None:
    summary = role_auth.role_action_summary("pm", self.manifest, self.operation_semantics)
    self.assertNotIn("track.create", summary["restricted_actions"])
    self.assertNotIn("track.archive", summary["restricted_actions"])
    self.assertNotIn("comment.resolve", summary["restricted_actions"])
    self.assertIn("track.create", summary["available_actions"])
    self.assertIn("track.archive", summary["available_actions"])
    self.assertIn("comment.resolve", summary["available_actions"])
```

- [ ] **Step 3: Run role policy tests and confirm failure**

Run:

```bash
python3 -m pytest tests/test_role_action_auth.py -q
```

Expected before implementation:

- preview shape assertions fail because old keys are returned.

## Task 3: Update Context Preview Contract Tests

**Files:**

- Modify: `tests/test_context_binding_env_tool.py`
- Modify: `tests/test_env_tool_response_contract.py`
- Test: both files

- [ ] **Step 1: Update `context.summarize` capability snapshot test**

In `tests/test_context_binding_env_tool.py`, update `test_context_summarize_includes_generated_capability_snapshot` so it reads:

```python
snapshot = payload.get("capability_snapshot")
self.assertIsInstance(snapshot, dict, msg=payload)
assert isinstance(snapshot, dict)
for old_key in (
    "role_authority_source",
    "allowed_actions",
    "denied_actions",
    "denied_action_details",
    "allowed_action_permissions",
):
    self.assertNotIn(old_key, snapshot)
preview = snapshot.get("runtime_policy_preview")
self.assertIsInstance(preview, dict, msg=snapshot)
assert isinstance(preview, dict)
self.assertEqual(preview.get("active_role"), "dev")
self.assertEqual(preview.get("source"), "env.tool role-action policy")
self.assertIs(preview.get("not_authorization_boundary"), True)
self.assertIs(preview.get("not_execution_result"), True)
self.assertIn("track.list", preview.get("available_actions", []))
self.assertIn("artifact.create_revision", preview.get("available_actions", []))
self.assertIn("request.accept", preview.get("available_actions", []))
self.assertIn("track.create", preview.get("restricted_actions", []))
self.assertIn("track.archive", preview.get("restricted_actions", []))
self.assertIn("comment.resolve", preview.get("restricted_actions", []))
details = preview.get("restricted_action_details")
self.assertIsInstance(details, dict, msg=preview)
assert isinstance(details, dict)
self.assertEqual(details.get("track.create", {}).get("required_permission"), "track.create")
self.assertEqual(details.get("track.create", {}).get("restricted_to_roles"), ["pm"])
self.assertNotIn("object_" + "permissions", json.dumps(snapshot, ensure_ascii=True))
self.assertIn("active-buddy private", str(snapshot.get("task_visibility")))
```

Keep the existing artifact publication path assertions that follow this block.

- [ ] **Step 2: Update `context.get` metadata test**

In `test_context_get_metadata_and_source_workspace_semantics`, replace access to `snapshot["denied_action_details"]` with:

```python
preview = snapshot.get("runtime_policy_preview")
self.assertIsInstance(preview, dict, msg=snapshot)
assert isinstance(preview, dict)
details = preview.get("restricted_action_details")
self.assertIsInstance(details, dict, msg=preview)
assert isinstance(details, dict)
self.assertEqual(details.get("comment.resolve", {}).get("required_permission"), "comment.resolve")
self.assertEqual(details.get("comment.resolve", {}).get("restricted_to_roles"), ["pm"])
```

Also assert old auth preview keys are absent from `snapshot`.

- [ ] **Step 3: Update response contract context scope test**

In `tests/test_env_tool_response_contract.py::test_context_get_and_summarize_catalog_scope`, replace old `capability_snapshot` checks with:

```python
capability_snapshot = summary.get("capability_snapshot")
self.assertIsInstance(capability_snapshot, dict, msg=summary)
assert isinstance(capability_snapshot, dict)
preview = capability_snapshot.get("runtime_policy_preview")
self.assertIsInstance(preview, dict, msg=summary)
assert isinstance(preview, dict)
self.assertEqual(preview.get("active_role"), "pm")
self.assertEqual(preview.get("source"), "env.tool role-action policy")
self.assertIs(preview.get("not_authorization_boundary"), True)
self.assertIs(preview.get("not_execution_result"), True)
for old_key in (
    "role_authority_source",
    "allowed_actions",
    "denied_actions",
    "denied_action_details",
    "allowed_action_permissions",
):
    self.assertNotIn(old_key, capability_snapshot)
self.assertNotIn("object_" + "permissions", json.dumps(capability_snapshot, ensure_ascii=True))
```

- [ ] **Step 4: Run focused context tests and confirm failure**

Run:

```bash
python3 -m pytest tests/test_context_binding_env_tool.py tests/test_env_tool_response_contract.py -q
```

Expected before implementation:

- failures because `runtime_policy_preview` does not exist and old keys still exist.

## Task 4: Add Catalog Metadata Residue Tests

**Files:**

- Modify: `tests/test_env_tool_semantic_contract.py`
- Test: `tests/test_env_tool_semantic_contract.py`

- [ ] **Step 1: Extend role-neutral field guard**

In `test_operation_semantics_remain_role_neutral`, add these forbidden fields:

```python
"runtime_policy_preview",
"available_actions",
"restricted_actions",
"restricted_action_details",
"not_authorization_boundary",
"not_execution_result",
```

- [ ] **Step 2: Add permission-ownership wording test**

Add:

```python
def test_tool_catalog_and_operation_semantics_do_not_claim_permission_ownership(self) -> None:
    catalog_text = json.dumps(catalog.env_tools_description(), ensure_ascii=True).lower()
    operation_text = json.dumps(catalog.operation_semantics(), ensure_ascii=True).lower()
    combined = f"{catalog_text}\n{operation_text}"
    forbidden = (
        "active buddy owns",
        "owns message.list permission",
        "owns task.read permission",
        "owns task.propose permission",
        "owns task.confirm permission",
        "owns artifact.create permission",
        "owns track.read permission",
    )
    for text in forbidden:
        with self.subTest(text=text):
            self.assertNotIn(text, combined)
    self.assertIn("env.tool role-action policy allows this action for the active role", combined)
```

Confirm `json` is already imported in this file; if not, add `import json`.

- [ ] **Step 3: Run semantic contract test and confirm failure**

Run:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py -q
```

Expected before implementation:

- failure because six tool metadata rows still contain old wording.

## Task 5: Add Env Client Receipt Projection Test

**Files:**

- Modify: `tests/test_env_client_payload_cli.py`
- Test: `tests/test_env_client_payload_cli.py`

- [ ] **Step 1: Import broker error**

Add:

```python
from runtime_kernel.client import RuntimeBrokerError  # noqa: E402
```

- [ ] **Step 2: Add CLI broker-error projection test**

Add:

```python
def test_broker_role_auth_error_preserves_receipt_fields_at_top_level(self) -> None:
    receipt = {
        "tool": "track",
        "action": "track.create",
        "category": "auth_denied",
        "permission_boundary": "tool.role_authority",
        "auth_source": "env.tool role-action policy",
        "auth_stage": "pre_dispatch",
        "executed": False,
        "state_changed": False,
        "durability": "none",
        "retryable": False,
        "retry_guidance": "Use an action allowed for this role.",
        "why_blocked": "Action track.create is restricted by env.tool role-action policy.",
        "impact": "No env action ran and runtime state was unchanged.",
        "required_permission": "track.create",
        "active_role": "market",
        "allowed_roles": ["pm"],
        "allowed_next_actions": ["Use context.summarize to inspect runtime policy preview for this role."],
    }
    error = RuntimeBrokerError(
        "E_TOOL_ROLE_AUTH",
        "active role is not allowed to run this tool action",
        response={"ok": False, "error": {"code": "E_TOOL_ROLE_AUTH", "message": "active role is not allowed to run this tool action"}, **receipt},
        details=dict(receipt),
    )
    stdout = io.StringIO()
    with mock.patch.object(sys, "argv", ["client.py", "track", "create", "--payload", "{}"]):
        with mock.patch.object(self.client, "request_runtime_broker", side_effect=error):
            with contextlib.redirect_stdout(stdout):
                code = self.client.main()
    output = json.loads(stdout.getvalue())
    self.assertEqual(code, 1, msg=output)
    self.assertEqual((output.get("error") or {}).get("code"), "E_TOOL_ROLE_AUTH")
    for key, value in receipt.items():
        with self.subTest(key=key):
            self.assertEqual(output.get(key), value, msg=output)
```

- [ ] **Step 3: Run CLI tests and confirm failure**

Run:

```bash
python3 -m pytest tests/test_env_client_payload_cli.py -q
```

Expected before implementation:

- failure because `_error_payload()` does not preserve the new receipt fields, and also does not currently preserve some existing receipt fields top-level.

## Task 6: Implement Auth Denial Receipt

**Files:**

- Modify: `scripts/env/tool_runtime/registry.py`
- Test: `tests/test_env_tool_router.py`

- [ ] **Step 1: Update `_role_auth_rejection()` text and extra fields**

Change `why_blocked`, `allowed_next_actions`, and `alternative_capabilities` to runtime-policy preview wording:

```python
why_blocked=(
    f"Action {tool}.{action} is restricted by env.tool role-action policy. "
    f"Active role '{decision.active_role}' is not allowed; allowed roles: {allowed_roles_text}."
),
allowed_next_actions=[
    "Use context.summarize to inspect runtime policy preview for this role.",
    "Use context.get to inspect tool payload schema and runtime policy preview.",
],
alternative_capabilities=[
    tool_results.alternative_capability(
        tool="context",
        action="summarize",
        condition="Inspect runtime policy preview before choosing another env.tool action.",
        mutates_product_state=False,
    ),
    tool_results.alternative_capability(
        tool="context",
        action="get",
        condition="Inspect tool payload schema and runtime policy preview before retrying.",
        mutates_product_state=False,
    ),
],
extra={
    "category": "auth_denied",
    "auth_source": "env.tool role-action policy",
    "auth_stage": "pre_dispatch",
    "executed": False,
    "required_permission": decision.required_permission,
    "active_role": decision.active_role,
    "allowed_roles": allowed_roles,
},
```

Do not add auth checks to individual tool `_impl.py` files.

- [ ] **Step 2: Run router tests**

Run:

```bash
python3 -m pytest tests/test_env_tool_router.py -q
```

Expected: pass for updated router tests.

## Task 7: Implement Runtime Policy Preview Shape

**Files:**

- Modify: `scripts/env/tool_runtime/role_auth.py`
- Modify: `scripts/env/tools/context/_impl.py`
- Test: `tests/test_role_action_auth.py`, `tests/test_context_binding_env_tool.py`, `tests/test_env_tool_response_contract.py`

- [ ] **Step 1: Rewrite `role_action_summary()` return shape**

Replace old `allowed_actions`, `denied_actions`, `denied_action_details`, and `allowed_action_permissions` variables with:

```python
available_actions: list[str] = []
restricted_actions: list[str] = []
restricted_action_details: dict[str, dict[str, Any]] = {}
```

For allowed decisions:

```python
available_actions.append(action_id)
```

For rejected decisions:

```python
restricted_actions.append(action_id)
restricted_action_details[action_id] = {
    "required_permission": required_permission,
    "active_role": active_role,
    "restricted_to_roles": list(decision.allowed_roles),
    "reason": f"active role '{active_role}' is not allowed by env.tool role-action policy",
}
```

Return:

```python
return {
    "active_role": active_role,
    "source": "env.tool role-action policy",
    "not_authorization_boundary": True,
    "not_execution_result": True,
    "available_actions": available_actions,
    "restricted_actions": restricted_actions,
    "restricted_action_details": restricted_action_details,
}
```

- [ ] **Step 2: Nest preview under context capability snapshot**

In `_capability_snapshot()`, rename the local summary variable:

```python
runtime_policy_preview = role_auth.role_action_summary(active_buddy, manifest, operation_semantics)
```

Return a dict shaped like:

```python
return {
    "runtime_policy_preview": runtime_policy_preview,
    "task_visibility": str(operation_semantics["task.current"]["visibility"]),
    "artifact_publication_path": " ".join(
        [
            str(artifact_create["success_effect"]),
            "Does not write:",
            ", ".join(str(row) for row in artifact_create["does_not_write"]),
        ]
    ),
    "comment_target_support": str(affordances["comment"]["object_model"]),
    "request_lifecycle_visibility": str(operation_semantics["request.create"]["visibility"]),
    "search_boundary": str(affordances["search"]["object_model"]),
    "evidence_boundary": str(affordances["evidence"]["object_model"]),
    "writable_file_surface": "$BUDDYSWITCH_BUDDYBOX_DIR for persistent private files; $BUDDYSWITCH_INSTANCE_TMP for temporary files.",
}
```

Do not retain old auth preview keys anywhere in `capability_snapshot`.

- [ ] **Step 3: Run preview tests**

Run:

```bash
python3 -m pytest tests/test_role_action_auth.py tests/test_context_binding_env_tool.py tests/test_env_tool_response_contract.py -q
```

Expected: pass for preview contract tests.

## Task 8: Clean Tool Metadata Permission Ownership Wording

**Files:**

- Modify: `scripts/env/tools/message/tool.py`
- Modify: `scripts/env/tools/task/tool.py`
- Modify: `scripts/env/tools/artifact/tool.py`
- Modify: `scripts/env/tools/track/tool.py`
- Test: `tests/test_env_tool_semantic_contract.py`

- [ ] **Step 1: Replace six old precondition strings**

Use this exact replacement string:

```python
"env.tool role-action policy allows this action for the active role"
```

Replace:

- `active buddy owns message.list permission`;
- `active buddy owns task.read permission`;
- `active buddy owns task.propose permission`;
- `active buddy owns task.confirm permission`;
- `active buddy owns artifact.create permission`;
- `active buddy owns track.read permission`.

Keep unrelated preconditions such as `one pending task switch confirmation exists`.

- [ ] **Step 2: Run semantic contract tests**

Run:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py -q
```

Expected: pass.

- [ ] **Step 3: Run residue scan**

Run:

```bash
rg -n "active buddy owns .* permission" scripts/env/tools tests
```

Expected: no output.

## Task 9: Preserve Receipt Fields Through Env Client

**Files:**

- Modify: `scripts/env/client.py`
- Test: `tests/test_env_client_payload_cli.py`

- [ ] **Step 1: Extend `_error_payload()` top-level field allowlist**

In `scripts/env/client.py`, add these fields to `top_level`:

```python
"category",
"human_summary",
"why_blocked",
"impact",
"state_changed",
"durability",
"retryable",
"retry_guidance",
"auth_source",
"auth_stage",
"executed",
"required_permission",
"active_role",
"allowed_roles",
"alternative_capabilities",
"correctable_fields",
"field_errors",
"boundary",
"mutates_product_state",
```

Keep existing fields such as `tool`, `action`, `permission_boundary`, `allowed_next_actions`, and `allowed_next_action_options`.

- [ ] **Step 2: Run env client tests**

Run:

```bash
python3 -m pytest tests/test_env_client_payload_cli.py -q
```

Expected: pass.

## Task 10: Run Focused Suite And Fix Root Causes

**Files:**

- Modify only files already listed in this plan.
- Test: focused env tool feedback suite.

- [ ] **Step 1: Run focused suite**

Run:

```bash
python3 -m pytest tests/test_env_tool_router.py tests/test_role_action_auth.py tests/test_context_binding_env_tool.py tests/test_env_tool_response_contract.py tests/test_env_tool_semantic_contract.py tests/test_env_client_payload_cli.py tests/test_env_manifest_v2.py -q
```

Expected: all pass.

- [ ] **Step 2: If tests fail, fix root causes without weakening tests**

Allowed fixes:

- adjust receipt fields in `registry.py`;
- adjust preview shape in `role_auth.py` or `context/_impl.py`;
- adjust CLI field preservation in `env/client.py`;
- adjust old metadata strings in per-tool `tool.py` files.

Forbidden fixes:

- reintroduce old preview fields;
- relax tests to accept old and new fields;
- move auth checks into tool `_impl.py`;
- add daemon/launcher/runtime_kernel changes without a focused proof.

## Task 11: Run Broader Runtime And Tool Verification

**Files:**

- No new files expected.
- Test: representative runtime/tool contract suite.

- [ ] **Step 1: Run related broader tests**

Run:

```bash
python3 -m pytest tests/test_track_env_tool.py tests/test_comment_env_tool.py tests/test_runtime_broker.py tests/test_runtime_tool_feedback.py tests/test_host_decision_surface_product_mode.py tests/test_runless_runtime_contract.py tests/test_turn_runtime.py -q
```

Expected: all pass.

- [ ] **Step 2: Run static residue checks**

Run:

```bash
rg -n "active buddy owns .* permission" scripts/env/tools tests
rg -n "\"allowed_actions\"|\"denied_actions\"|\"denied_action_details\"|\"allowed_action_permissions\"|\"role_authority_source\"" scripts tests
rg -n "permissions\\s*=\\s*\\[" buddyswitch/manifest.toml
git diff --check
```

Expected:

- first command: no output;
- second command: no runtime/test output for old preview auth fields;
- third command: no output;
- `git diff --check`: no output and exit 0.

## Task 12: Full Verification And Review

**Files:**

- No additional files expected.
- Test: full suite if environment permits.

- [ ] **Step 1: Run full suite**

Run:

```bash
python3 -m pytest -q
```

Expected: all pass.

If full suite cannot run because of environment/resource limits, stop and report the blocker. Do not claim completion.

- [ ] **Step 2: Self-review diff against task memo**

Check:

- `E_TOOL_ROLE_AUTH` has receipt fields and policy wording;
- context preview is nested under `capability_snapshot.runtime_policy_preview`;
- no old preview auth fields remain;
- no `active buddy owns ... permission` wording remains in tool metadata;
- no manifest `permissions` compatibility is restored;
- no daemon, STOP, Task TUI, launcher lifecycle, workflow, gate, UI, or profile files changed;
- no `runtime_kernel/*` files changed unless a focused failing test forced it;
- no per-tool `_impl.py` role-auth duplication was added.

- [ ] **Step 3: Inspect changed files**

Run:

```bash
git status --short
git diff --stat
```

Expected changed tracked files are limited to the test plan, development plan, targeted tests, and targeted env tool feedback implementation files.

## Expected Final Changed Runtime Files

Expected runtime implementation files:

- `scripts/env/tool_runtime/registry.py`
- `scripts/env/tool_runtime/role_auth.py`
- `scripts/env/tools/context/_impl.py`
- `scripts/env/client.py`
- `scripts/env/tools/message/tool.py`
- `scripts/env/tools/task/tool.py`
- `scripts/env/tools/artifact/tool.py`
- `scripts/env/tools/track/tool.py`

Expected test files:

- `tests/test_env_tool_router.py`
- `tests/test_role_action_auth.py`
- `tests/test_context_binding_env_tool.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_env_client_payload_cli.py`
- `tests/test_env_manifest_v2.py` only if the existing retired-permissions guard needs assertion sharpening.

Files that should remain untouched:

- `tools/launcher/*`
- `scripts/runtime_kernel/*`
- daemon / STOP / Task TUI code
- `buddyswitch/manifest.toml`
- `buddyswitch/objects/**`
- `buddyswitch/local/buddybox/**`

## Handoff Notes

- This is not a behavior expansion. It is a contract cleanup for feedback clarity.
- `context` is still an env tool that Codex calls voluntarily through CLI/tool use; it is not injected into developer context and does not grant authority.
- The implementation must not preserve compatibility names for old auth preview fields.
- If a test appears to require old and new fields together, treat that as a bug in the test update and fix the test to assert the new one-way contract.
