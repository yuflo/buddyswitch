# Phase 1: Identity Core

## Goal

Define the shared identity core and runtime projections so the system has one bottom-level way to express "who": `IdentityRef { id, type }`.

## Code Audit

- `scripts/env/tool_runtime/actor_profile.py` currently treats `ActorAddress { actor_id, role_id }` as both active actor identity and routeable daemon projection.
- `scripts/env/tool_runtime/context.py` carries `actor_id`, `role_id`, `active_actor`, `actor_address`, and `auth_subject`; it does not expose `current_identity`.
- `scripts/env/services/messages.py` creates external ids and authenticates connection keys, but external identity is still represented as IM participant data.
- Existing runtime auth tests in `tests/test_runtime_actor_profile.py` already protect the rule that `role_id` remains auth, not identity.

## Plan

1. Add a focused identity core module with `IdentityRef`.
2. Add actor/external construction helpers without relying on id prefixes for business branching.
3. Add runtime actor profile projection: current actor -> `IdentityRef(actor_id, "actor")`.
4. Add route projection helper: actor identity + trusted role -> `ActorAddress`.
5. Add external IM participant -> identity helper for Phase 4/Phase 3 consumers.
6. Expose `current_identity` on `ToolContext`.

## Test Plan

Use TDD in `tests/test_runtime_actor_profile.py`:

- `IdentityRef` validates non-empty id and type.
- Runtime actor profile exposes `current_identity`.
- `ToolContext` exposes `current_identity` as a payload, while `auth_subject` remains internal.
- External participant identity resolves to `{ id: external_id, type: "external" }`.
- Actor identity route projection rejects external identity.

Focused command:

```bash
python -m pytest tests/test_runtime_actor_profile.py tests/test_env_tool_identity.py -q
```

## Implementation

- Added `scripts/env/domain/identity.py` with `IdentityRef`, actor/external construction helpers, and IM participant-to-identity resolution.
- Added `current_identity` to `ActorProfile`.
- Added `actor_identity_to_address()` as an explicit actor identity to daemon route projection.
- Added `current_identity` to `ToolContext` and its mapping projection.
- Added runtime identity tests in `tests/test_runtime_actor_profile.py`.

## Verification

Focused red-green checks run:

```bash
python -m pytest tests/test_runtime_actor_profile.py::ActorProfileTests::test_identity_ref_serializes_stable_payload_and_validates_type -q
```

Red result before implementation:

```text
FAILED ... ModuleNotFoundError: No module named 'env.domain.identity'
```

Green result after implementation:

```text
1 passed in 0.02s
```

```bash
python -m pytest tests/test_runtime_actor_profile.py::ActorProfileTests::test_actor_profile_normalizes_trusted_runtime_identity -q
```

Red result before implementation:

```text
FAILED ... AttributeError: 'ActorProfile' object has no attribute 'current_identity'
```

Green result after implementation:

```text
1 passed in 0.02s
```

```bash
python -m pytest tests/test_runtime_actor_profile.py::ActorProfileTests::test_tool_context_can_be_constructed_from_actor_profile -q
```

Red result before implementation:

```text
FAILED ... AttributeError: 'ToolContext' object has no attribute 'current_identity'
```

Green result after implementation:

```text
1 passed in 0.02s
```

```bash
python -m pytest tests/test_runtime_actor_profile.py::ActorProfileTests::test_identity_helpers_resolve_actor_external_and_route_projection -q
```

Red result before implementation:

```text
FAILED ... ImportError: cannot import name 'actor_identity' from 'env.domain.identity'
```

Green result after implementation:

```text
1 passed in 0.02s
```

Focused phase command:

```bash
python -m pytest tests/test_runtime_actor_profile.py tests/test_env_tool_identity.py -q
```

Result:

```text
16 passed, 11 subtests passed in 0.07s
```

Phase-scoped residue check:

```bash
rg -n "IdentityRef|current_identity|identity_from_im_participant|actor_identity_to_address" scripts/env tests docs/spec/identity-redesign -S
```

Result: hits are limited to the new identity core, runtime/context projections, tests, and phase docs.

## Gate

Complete.

- Phase test command passed.
- Phase goal is implemented.
- No old write path was replaced in this phase, so no old write path deletion is due yet.
- No new actor-facing or web-facing public locator was introduced.
- No identity concept outside `IdentityRef { id, type }` was introduced.
- README updated to set `phase-02-runtime-auth-routing` as current.
