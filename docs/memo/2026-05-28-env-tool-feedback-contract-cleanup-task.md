# Env Tool Feedback Contract Cleanup Task

Date: 2026-05-28

## Task In One Sentence

Clean up env.tool feedback after role-action auth so Codex can clearly distinguish runtime execution receipts from read-only planning previews, with no old manifest-permission or permission-ownership residue.

## Core Goal

The system should communicate two separate facts:

- **Runtime execution feedback**: whether a tool action ran, where it was rejected, and whether runtime state changed.
- **Read-only planning preview**: which actions the current role is expected to be able to try, and which actions are restricted.

The preview must never be presented as an authorization boundary or as proof that an action was executed successfully.

## What To Change

### 1. Make `E_TOOL_ROLE_AUTH` A Clear Runtime Receipt

When dispatch auth rejects a tool action, the response should say:

- `category=auth_denied`
- `auth_source=env.tool role-action policy`
- `auth_stage=pre_dispatch`
- `executed=false`
- `state_changed=false`
- `durability=none`

The message should describe the action as restricted by role-action policy. It should not say that a buddy owns or lacks manifest permissions.

Expected owner files:

- `scripts/env/tool_runtime/registry.py`
- `scripts/env/tool_runtime/results.py` only if the shared response contract needs a small field addition.

### 2. Rename Context Auth Preview To `runtime_policy_preview`

`context.get` and `context.summarize` remain env tool layer read-only discovery tools.

Their auth preview should move to:

- `runtime_policy_preview`
- `available_actions`
- `restricted_actions`
- `restricted_action_details`
- `not_authorization_boundary=true`
- `not_execution_result=true`

Remove the old auth preview fields:

- `allowed_actions`
- `denied_actions`
- `denied_action_details`
- `allowed_action_permissions`

Expected owner files:

- `scripts/env/tool_runtime/role_auth.py`
- `scripts/env/tools/context/_impl.py`

### 3. Remove Old Permission Ownership Wording From Tool Metadata

Remove tool catalog / operation semantics text such as:

```text
active buddy owns ... permission
```

Replace it with role-action policy language, for example:

```text
env.tool role-action policy allows this action for the active role
```

Expected owner files:

- `scripts/env/tools/*/tool.py`

This is a metadata wording cleanup only. It must not change tool behavior.

### 4. Update Tests

Tests should prove:

- auth deny still happens before tool `_impl.py` invocation;
- rejected auth calls report `executed=false`, `state_changed=false`, and `durability=none`;
- context preview comes from runtime role-action policy;
- market restricted actions still include `track.create`, `track.archive`, and `comment.resolve`;
- old preview fields do not remain;
- `active buddy owns ... permission` no longer appears in tool catalog or operation semantics.

Likely test files:

- `tests/test_role_action_auth.py`
- `tests/test_context_binding_env_tool.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_env_tool_semantic_contract.py`
- focused router / runtime feedback tests if contract assertions require updates.

## Explicit Non-Goals

- Do not touch daemon, STOP, Task TUI, or launcher lifecycle.
- Do not touch `runtime_kernel/*` unless a focused test proves the public feedback envelope cannot pass through.
- Do not restore manifest `permissions`.
- Do not keep compatibility fields for old preview names.
- Do not move all business rejections into dispatch.
- Do not add per-tool duplicate role-action auth checks.
- Do not introduce profile, DSL, workflow, gate, plugin system, or UI changes.

## Boundary Notes

This is a small runtime feedback contract migration, not a broad runtime redesign.

The intended boundary remains:

```text
context tool = read-only discovery and planning preview
registry + role_auth = forced pre-dispatch authorization
tool _impl + domain = payload, resource, lifecycle, and state-conflict feedback
broker / TUI / logs = structured feedback consumers only
```

## Definition Of Done

- Focused tests pass for role auth, context preview, env tool response contract, and env tool semantic contract.
- No old manifest buddy permission path is restored.
- No old preview auth fields remain.
- No permission ownership wording remains in runtime tool catalog or operation semantics.
- No daemon, STOP, Task TUI, launcher lifecycle, or unrelated runtime kernel code is changed.
