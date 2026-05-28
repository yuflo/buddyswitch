# Runtime Actor Profile Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split env.tool runtime identity, role auth input, auth-denied feedback, and tool-facing context into clear runtime-kernel modules without changing product behavior.

**Architecture:** Add `actor_profile` as the identity normalization owner, update `role_auth` to consume `AuthSubject`, extract `auth_feedback` for standard pre-dispatch denial responses, and have `registry` orchestrate these modules before constructing `ToolContext` from the resolved actor profile. Tool packages continue using `ToolContext` and do not import actor profile internals.

**Tech Stack:** Python stdlib dataclasses, existing env.tool runtime modules, pytest/unittest tests.

---

## Scope

Implement the complete Phase 1 change in one forward pass:

- create `scripts/env/tool_runtime/actor_profile.py`;
- create `scripts/env/tool_runtime/auth_feedback.py`;
- update `scripts/env/tool_runtime/role_auth.py`;
- update `scripts/env/tool_runtime/context.py`;
- update `scripts/env/tool_runtime/registry.py`;
- update focused tests to use `AuthSubject` and assert boundaries;
- run focused and relevant regression verification.

Do not keep raw-string role-auth compatibility. Do not move tool/domain business rules into runtime auth.

## Current Code Map

| File | Current responsibility | Planned change |
| --- | --- | --- |
| `scripts/env/tool_runtime/actor_profile.py` | Missing | Define runtime instance record, runtime actor profile, auth subject, and normalization helpers. |
| `scripts/env/tool_runtime/role_auth.py` | Role-action policy using raw active-role strings | Consume `AuthSubject` in `authorize()` and `role_action_summary()`. |
| `scripts/env/tool_runtime/auth_feedback.py` | Missing | Own `E_TOOL_ROLE_AUTH` response construction. |
| `scripts/env/tool_runtime/registry.py` | Dispatch, inline auth feedback, raw identity strings | Resolve actor profile, call role auth with `AuthSubject`, route denied decisions through `auth_feedback`, build `ToolContext` from actor profile. |
| `scripts/env/tool_runtime/context.py` | Stable tool-facing context | Add `from_actor_profile()` and `runtime_policy_preview()` while keeping existing tool-facing fields. |
| `tests/test_runtime_actor_profile.py` | Missing | Add actor profile, auth feedback, context construction, and boundary tests. |
| `tests/test_role_action_auth.py` | Role auth tests using strings | Migrate to `AuthSubject`; add raw-string rejection guard. |
| `tests/test_env_tool_identity.py` | Identity boundary tests | Add payload identity spoofing guard. |

## Target Contracts

### Actor Profile

`RuntimeInstanceRecord` is the trusted local runtime instance identity source for env.tool dispatch.

```python
RuntimeInstanceRecord(
    instance_id="inst-dev-example",
    buddy_id="dev",
    instance_json=Path("instance.json"),
    payload={...},
)
```

`resolve_runtime_actor_profile(record)` returns:

```python
RuntimeActorProfile(
    instance_id="inst-dev-example",
    active_buddy="dev",
    auth_subject=AuthSubject(role_id="dev"),
    instance_record=normalized_record,
)
```

### Role Auth

`role_auth.authorize()` accepts only:

```python
role_auth.authorize("track.create", AuthSubject(role_id="dev"), manifest)
```

Raw string input is rejected with `TypeError`.

### Auth Feedback

`auth_feedback.role_auth_rejection()` returns the existing `E_TOOL_ROLE_AUTH` receipt shape and owns the literal code and standard fields.

### ToolContext

`ToolContext.from_actor_profile(actor_profile=profile, ...)` preserves existing tool-facing access:

```python
context.active_buddy
context.instance_id
context["active_buddy"]
context["instance_id"]
context.runtime_policy_preview(operation_semantics)
```

## Task 1: Add Actor Profile Tests

**Files:**

- Create: `tests/test_runtime_actor_profile.py`

- [ ] **Step 1: Write failing actor profile normalization tests**

Add tests for:

- `RuntimeInstanceRecord`;
- `resolve_runtime_actor_profile()`;
- blank `instance_id`;
- blank `buddy_id`;
- `AuthSubject(role_id=profile.active_buddy)`.

- [ ] **Step 2: Run red test**

Run:

```bash
python3 -m pytest tests/test_runtime_actor_profile.py -q
```

Expected: fail because `env.tool_runtime.actor_profile` and `auth_feedback` do not exist.

## Task 2: Add Actor Profile Implementation

**Files:**

- Create: `scripts/env/tool_runtime/actor_profile.py`

- [ ] **Step 1: Implement concrete dataclasses**

Implement:

- `AuthSubject(role_id: str)`;
- `RuntimeInstanceRecord(instance_id: str, buddy_id: str, instance_json: Path, payload: dict[str, Any])`;
- `RuntimeActorProfile(instance_id: str, active_buddy: str, auth_subject: AuthSubject, instance_record: RuntimeInstanceRecord)`;
- `runtime_instance_record_from_dispatch(...)`;
- `resolve_runtime_actor_profile(record)`.

- [ ] **Step 2: Run actor profile tests**

Run:

```bash
python3 -m pytest tests/test_runtime_actor_profile.py -q
```

Expected after this task: actor-profile tests pass except auth-feedback/context/boundary tests that depend on later tasks.

## Task 3: Migrate Role Auth To AuthSubject

**Files:**

- Modify: `scripts/env/tool_runtime/role_auth.py`
- Modify: `tests/test_role_action_auth.py`

- [ ] **Step 1: Update tests to construct `AuthSubject`**

Replace direct string auth calls with:

```python
AuthSubject(role_id=role)
```

Add:

```python
with self.assertRaises(TypeError):
    role_auth.authorize("none", "pm", self.manifest)  # type: ignore[arg-type]
```

- [ ] **Step 2: Run red role-auth test**

Run:

```bash
python3 -m pytest tests/test_role_action_auth.py -q
```

Expected: fail because `authorize()` still accepts raw strings.

- [ ] **Step 3: Update `role_auth.py`**

Require `AuthSubject` in `authorize()` and `role_action_summary()`. Keep `AuthDecision.active_role` and existing response metadata unchanged.

- [ ] **Step 4: Run green role-auth test**

Run:

```bash
python3 -m pytest tests/test_role_action_auth.py -q
```

Expected: pass.

## Task 4: Extract Auth Feedback

**Files:**

- Create: `scripts/env/tool_runtime/auth_feedback.py`
- Modify: `scripts/env/tool_runtime/registry.py`
- Test: `tests/test_runtime_actor_profile.py`
- Test: `tests/test_env_tool_router.py`

- [ ] **Step 1: Add failing feedback owner assertions**

In `tests/test_runtime_actor_profile.py`, assert:

- `auth_feedback.role_auth_rejection()` returns the existing `E_TOOL_ROLE_AUTH` shape;
- `registry` has no `_role_auth_rejection`;
- `registry.py` does not contain literal `E_TOOL_ROLE_AUTH`.

- [ ] **Step 2: Run red tests**

Run:

```bash
python3 -m pytest tests/test_runtime_actor_profile.py tests/test_env_tool_router.py -q
```

Expected: fail because feedback is still inline in registry.

- [ ] **Step 3: Move feedback construction**

Move the existing body of `registry._role_auth_rejection()` into `auth_feedback.role_auth_rejection()`. Keep response shape unchanged.

- [ ] **Step 4: Update registry call site**

Import `auth_feedback` and call:

```python
auth_feedback.role_auth_rejection(...)
```

- [ ] **Step 5: Run green tests**

Run:

```bash
python3 -m pytest tests/test_runtime_actor_profile.py tests/test_env_tool_router.py -q
```

Expected: pass for feedback and router behavior after role-auth migration is complete.

## Task 5: Construct ToolContext From Actor Profile

**Files:**

- Modify: `scripts/env/tool_runtime/context.py`
- Modify: `scripts/env/tools/context/_impl.py`
- Modify: `scripts/env/tool_runtime/registry.py`
- Test: `tests/test_runtime_actor_profile.py`
- Test: `tests/test_context_binding_env_tool.py`

- [ ] **Step 1: Add context construction test**

Assert `ToolContext.from_actor_profile()` preserves existing mapping and helper behavior.

- [ ] **Step 2: Run red context test**

Run:

```bash
python3 -m pytest tests/test_runtime_actor_profile.py -q
```

Expected: fail because `from_actor_profile()` and `runtime_policy_preview()` are missing.

- [ ] **Step 3: Update `ToolContext`**

Add:

- `auth_subject: AuthSubject`;
- classmethod `from_actor_profile(...)`;
- method `runtime_policy_preview(operation_semantics)`.

Do not add `RuntimeActorProfile` to `ToolContext.__getitem__()` or iteration.

- [ ] **Step 4: Update context tool preview**

Replace direct `role_auth.role_action_summary(active_buddy, ...)` in `scripts/env/tools/context/_impl.py` with:

```python
context.runtime_policy_preview(operation_semantics)
```

- [ ] **Step 5: Run context tests**

Run:

```bash
python3 -m pytest tests/test_runtime_actor_profile.py tests/test_context_binding_env_tool.py -q
```

Expected: pass.

## Task 6: Wire Registry Through Actor Profile

**Files:**

- Modify: `scripts/env/tool_runtime/registry.py`
- Modify: `tests/test_env_tool_identity.py`

- [ ] **Step 1: Add payload identity spoofing guard**

Add a test that dev runtime actor dispatching `track.create` with spoofed args such as `{"active_buddy": "pm", "buddy": "pm"}` still receives `E_TOOL_ROLE_AUTH` with `active_role == "dev"`.

- [ ] **Step 2: Run focused identity/router tests**

Run:

```bash
python3 -m pytest tests/test_env_tool_identity.py tests/test_env_tool_router.py -q
```

Expected before registry wiring: product behavior may already pass the spoofing guard; this test is a behavior guard while module tests force the structural change.

- [ ] **Step 3: Update registry orchestration**

At dispatch start:

- build `RuntimeInstanceRecord` from trusted dispatch fields;
- resolve `RuntimeActorProfile`;
- use `profile.active_buddy` and `profile.instance_id` for rejections and context;
- call `role_auth.authorize(action.required_permission, profile.auth_subject, manifest)`;
- construct `ToolContext.from_actor_profile(...)`.

- [ ] **Step 4: Run focused tests**

Run:

```bash
python3 -m pytest tests/test_env_tool_identity.py tests/test_env_tool_router.py tests/test_role_action_auth.py -q
```

Expected: pass.

## Task 7: Boundary And Regression Verification

**Files:**

- Test: focused runtime/auth/context/message tests

- [ ] **Step 1: Run combined focused verification**

Run:

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

- [ ] **Step 2: Run relevant regression**

Run:

```bash
python3 -m pytest tests/test_env_tool_package_independence.py tests/test_runtime_tool_feedback.py tests/test_env_client_payload_cli.py -q
```

- [ ] **Step 3: Run search verification**

Run:

```bash
rg -n "E_TOOL_ROLE_AUTH|_role_auth_rejection|RuntimeActorProfile|AuthSubject|role_auth\\.authorize\\(" scripts/env tests
```

Review the output:

- `E_TOOL_ROLE_AUTH` should be owned by `auth_feedback.py` and tests;
- `_role_auth_rejection` should not exist in runtime code;
- tool packages should not import `actor_profile` or name `RuntimeActorProfile`;
- runtime code should call `role_auth.authorize()` with `AuthSubject`.

## Phase 1 Review Checklist

- Test plan maps every memo requirement to a behavior or boundary test.
- Development plan has no transitional raw-role compatibility path.
- Actor profile, role auth, auth feedback, context, registry, and tools have separate responsibilities.
- Existing behavior is preserved by focused role auth, router, context, semantic, and message tests.
- No main or unrelated worktree pollution.
