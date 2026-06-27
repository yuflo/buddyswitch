# Phase 2: Runtime / Auth / Routing

## Goal

Keep identity, auth, and daemon routing as separate layers after Phase 1. Runtime provides trusted `current_identity`, auth uses trusted `role_id`, and daemon delivery keeps `ActorAddress` only as an internal routing projection.

## Code Audit

- `ToolContext` now exposes `current_identity`, but `DaemonAccess` is still initialized directly with `actor_address`.
- `DaemonAccess.deliver_signal()` writes `source_actor_address` from its stored route projection.
- `role_auth.authorize()` uses `AuthSubject(role_id)` and should stay unchanged except for tests proving payload identity hints cannot alter auth.
- Central daemon and mailbox code use `actor_address` as routing protocol data. That is allowed inside daemon boundaries.
- Actor-facing message and web contracts still expose `target_actor_address` and `role_id + actor_id`; those are Phase 3 and Phase 4, not Phase 2.

## Plan

1. Add tests proving `DaemonAccess` derives its local route from `current_identity + role_id`.
2. Update `DaemonAccess` construction to accept `current_identity` and `role_id`, then project to `ActorAddress` internally.
3. Keep `AuthSubject(role_id)` as the only role-action auth input.
4. Do not change Central daemon or mailbox wire protocol in this phase.
5. Run focused runtime/auth/daemon tests.

## Test Plan

Use TDD in `tests/test_runtime_actor_profile.py`:

- `ToolContext.daemon` carries source identity and route projection derived from the actor profile.
- The daemon route projection is not exposed through `ToolContext` mapping as identity.
- External identity cannot be projected to a daemon actor route.

Focused command:

```bash
python -m pytest tests/test_runtime_actor_profile.py tests/test_role_action_auth.py tests/test_daemon_communication_boundary.py tests/test_daemon_mailbox.py tests/test_daemon_trigger_router.py -q
```

## Implementation

- Changed `DaemonAccess` construction to accept `current_identity` and trusted runtime `role_id`.
- `DaemonAccess` now derives the local daemon route with `actor_identity_to_address()`.
- `ToolContext` now creates `DaemonAccess` from `current_identity + role_id`, not from a prebuilt `ActorAddress`.
- Added a regression test proving daemon signal source routing is derived from identity and trusted role.
- Left Central daemon and mailbox wire protocol unchanged; `actor_address` remains daemon-internal route data.

## Verification

Focused red-green check:

```bash
python -m pytest tests/test_runtime_actor_profile.py::ActorProfileTests::test_daemon_access_derives_route_from_current_identity_and_trusted_role -q
```

Red result before implementation:

```text
FAILED ... TypeError: DaemonAccess.__init__() got an unexpected keyword argument 'current_identity'
```

Green result after implementation:

```text
1 passed in 0.05s
```

Focused phase command:

```bash
python -m pytest tests/test_runtime_actor_profile.py tests/test_role_action_auth.py tests/test_daemon_communication_boundary.py tests/test_daemon_mailbox.py tests/test_daemon_trigger_router.py -q
```

Result:

```text
66 passed, 82 subtests passed in 1.38s
```

Phase-scoped residue check:

```bash
rg -n "DaemonAccess\\(actor_address|actor_address=actor_profile\\.actor_address|DaemonAccess\\(" scripts/env tests -S
```

Result: no `DaemonAccess(actor_address=...)` constructor remains. Remaining hits are the new identity-based constructor and `ToolContext.actor_address` assignment, which is still an internal routing projection retained for later message/web/ownership phases.

## Gate

Complete.

- Phase test command passed.
- Phase goal is implemented.
- No public write path was replaced in this phase, so no old public write path deletion is due yet.
- No new actor-facing or web-facing public locator was introduced.
- No identity concept outside `IdentityRef { id, type }` was introduced.
- README updated to set `phase-03-message-conversation` as current.
