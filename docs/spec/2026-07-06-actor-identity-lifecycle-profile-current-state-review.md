# Actor Identity Lifecycle Profile Current State Review

**Date:** 2026-07-06

**Source memo:** `docs/memo/2026-07-06-actor-identity-lifecycle-profile-fix-plan.md`

**Phase:** 0 - current-state confirmation before development.

## Current Problem Chain

The current IM target resolver is identity-first and fail-closed for actor sends:

```text
sender calls /api/im/messages or message.send
-> env.services.messages.resolve_im_send_target(...)
-> actor target requires identities/actors/<actor-id>.json
-> actor target then requires daemon reachability_status == online
-> missing actor profile returns E_IM_TARGET before message write
```

Actor lifecycle does not currently complete the matching identity write:

```text
instance start/resume
-> tools/launcher/env.sh writes instance.json
-> tools/launcher/daemon_core.py starts/runs actor daemon
-> daemon_core registers runtime reachability with central daemon
-> identities/actors/<actor-id>.json is not written
```

That leaves a split state where roster and reachability can know an actor is active while Central IM rejects the same actor as an unknown identity target.

## System Boundaries

- Identity repo owns static actor identity profiles at `state/buddyswitch/objects/identities/actors/*.json`.
- Actor daemon lifecycle owns the transition from a local `instance.json` to a runnable actor process.
- Central daemon owns runtime reachability registry rows under `state/runtime/central-daemon/registry.json`.
- Web management and IM HTTP routes are projections. They must not synthesize actor identity profiles.
- IM resolver remains strict. It must not fallback from missing identity profile to daemon registry or instance list.
- Stop/delete may remove process/runtime instance surfaces, but must not remove shared identity profiles.

## Code Facts Confirmed

- `scripts/env/services/messages.py` already has `resolve_im_send_target(...)`.
- `resolve_im_send_target(...)` checks `identity_repo.get_actor_identity_profile(...)` before actor reachability.
- Actor reachability is checked through an injected `actor_reachability_checker`; external targets require only an external identity profile.
- `scripts/env/repos/identities.py` owns `save_actor_identity_profile(...)`, `get_actor_identity_profile(...)`, and `list_actor_identity_profiles(...)`.
- `tools/launcher/daemon_core.py` imports `runtime_files` but does not import `env.repos.identities`.
- `daemon_core.derive_daemon_runtime_env(...)` projects shared root, state root, instance root/json, and workspace dir, but not `BUDDYSWITCH_ACTOR_ID` or `BUDDYSWITCH_ROLE_ID`.
- `daemon_core.run_daemon(...)` refreshes runtime roots and derives `identity_route`, then records ready and registers reachability without ensuring an actor identity profile first.
- `daemon_core.stop_daemon(...)` removes the daemon pid and unregisters reachability; it does not touch identity profile files.
- `tools/launcher/central_daemon_core.py` normalizes and stores runtime registry rows only; it does not import or write the identity repository.
- `tests/test_web_management.py` has `_instance_list_for_identity_routes(...)` that silently calls `save_test_actor_identity_profile(...)` before returning fake instance rows.
- Existing launcher delete tests assert shared state is kept, but they do not explicitly cover an actor identity profile file yet.

## Memo Consistency

The memo matches the current code state for the main defect:

- The resolver is already strict and identity-first.
- Actor lifecycle is the missing write point.
- Central daemon is currently runtime reachability only.
- Web IM tests currently hide the missing lifecycle profile by seeding profiles in the fake roster helper.

One acceptance detail needs explicit coverage beyond the memo's test snippets: stop/delete behavior must preserve identity profiles. Current code appears aligned, but the fix plan should lock it with tests or existing stronger evidence.

## Risks And Non-Actions

- Do not relax `resolve_im_send_target(...)`.
- Do not add daemon-registry fallback for actor identity lookup.
- Do not create profiles in Web routes, IM HTTP router, or `ExternalImSession`.
- Do not make central daemon the static identity owner.
- Do not delete identity profiles during daemon stop or instance delete.
- Do not migrate historical profiles or add a new contact/resolver service.
- Live smoke can be blocked by existing local daemons or port state; verification must record exact cleanup and runtime evidence before claiming completion.
