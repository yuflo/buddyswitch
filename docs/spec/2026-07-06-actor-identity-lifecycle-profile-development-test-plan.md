# Actor Identity Lifecycle Profile Development And Test Plan

**Date:** 2026-07-06

**Source memo:** `docs/memo/2026-07-06-actor-identity-lifecycle-profile-fix-plan.md`

**Goal:** Make actor lifecycle persist a static actor identity profile before runtime reachability registration, while keeping Central IM resolver strict and Web/central daemon as projections.

**Architecture:** Identity owns static actor facts; daemon lifecycle ensures the identity profile before readiness/reachability; central daemon owns only runtime reachability. Web IM and HTTP layers consume the identity-first contract and do not synthesize identity state.

## Phase 2 - Failing Regression Tests

### Files

- Modify: `tests/test_daemon_core.py`
- Modify: `tests/test_web_management.py`
- Modify if needed: `tests/test_buddyswitch_launcher.py`

### Test Design

Add lifecycle tests in `tests/test_daemon_core.py`:

- `test_start_daemon_passes_actor_identity_env_to_child_process`
  - Proves `start_daemon(...)` projects `BUDDYSWITCH_ACTOR_ID` and `BUDDYSWITCH_ROLE_ID` into the daemon child process.
  - Expected red: `BUDDYSWITCH_ROLE_ID` is missing.
- `test_run_daemon_ensures_actor_identity_profile_before_registering_reachability`
  - Observes identity repo state from inside `register_daemon_actor(...)`.
  - Expected red: observed profile is `None`, then final profile is missing.
- `test_run_daemon_rejects_conflicting_existing_actor_identity_profile`
  - Seeds an actor profile with the wrong role.
  - Expected red: daemon registers or proceeds instead of raising before registration.
- `test_stop_daemon_preserves_actor_identity_profile`
  - Seeds profile, stops a live daemon, and verifies the profile remains.
  - Expected result may already pass; keep it as a preservation contract.

Update Web tests in `tests/test_web_management.py`:

- Split `_instance_list_for_identity_routes(...)` into pure projection plus explicit `_seed_actor_identity_profiles(...)`.
- Update send-success tests to call `_seed_actor_identity_profiles(...)` before using fake instance rows.
- Add `test_web_im_actor_roster_does_not_create_actor_identity_profile`.
  - Expected red before helper cleanup: roster call creates the profile because the helper seeds it.

Update delete coverage if existing shared-state tests are too indirect:

- Add identity-profile fixture to `test_instance_delete_removes_only_target_instance_without_shared_state` or a focused sibling test.
- Verify `state/buddyswitch/objects/identities/actors/<actor-id>.json` remains after `instance delete --yes`.

### Focused Red Commands

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_daemon_core.py::DaemonCoreLifecycleTests::test_start_daemon_passes_actor_identity_env_to_child_process \
  tests/test_daemon_core.py::DaemonCoreRunLoopTests::test_run_daemon_ensures_actor_identity_profile_before_registering_reachability \
  tests/test_daemon_core.py::DaemonCoreRunLoopTests::test_run_daemon_rejects_conflicting_existing_actor_identity_profile \
  -q
```

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_web_management.py::WebManagementStableImIdentityTests::test_web_im_actor_roster_does_not_create_actor_identity_profile \
  -q
```

Record the red output in this document after running the tests.

## Phase 3 - Implementation

### Files

- Modify: `tools/launcher/daemon_core.py`
- Modify: `tests/test_daemon_core.py`
- Modify: `tests/test_web_management.py`
- Modify if needed: `tests/test_buddyswitch_launcher.py`

### Changes And Reasons

- Import `env.repos.identities as identity_repo` in `daemon_core.py`.
  - Architecture reason: daemon lifecycle is the bridge from instance runtime facts to identity profile existence.
- Extend `derive_daemon_runtime_env(context)` with:
  - `BUDDYSWITCH_ACTOR_ID`
  - `BUDDYSWITCH_ROLE_ID`
  - Architecture reason: daemon child process has explicit actor identity context instead of relying only on instance JSON.
- Add `ensure_actor_identity_profile(context, identity_route)`.
  - If profile exists with matching role, reuse it.
  - If profile exists with conflicting role, raise `ValueError("actor identity profile role mismatch: ...")`.
  - If missing, save `{"identity": {"id": identity_id, "type": "actor"}, "role_id": role_id}`.
  - Architecture reason: identity repo owns static actor profile; lifecycle ensures it before runtime reachability.
- Call `ensure_actor_identity_profile(...)` in `run_daemon(...)` after `runtime_files.refresh_runtime_roots_from_env()` and before `state.record_ready(...)`, mailbox startup, or central registration.
  - Architecture reason: no actor may be marked ready or reachable before its static identity exists.
- Keep `stop_daemon(...)` as reachability/process cleanup only.
  - Architecture reason: actor identity survives runtime stop/delete.
- Refactor Web test helper so roster projection does not seed profiles.
  - Architecture reason: Web roster projects runtime instances; it does not own identity creation.

## Phase 4 - Focused Verification

Run daemon lifecycle tests:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_daemon_core.py -q
```

Run Web IM projection tests:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_web_management.py -q
```

Run focused IM/lifecycle contract suite:

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_daemon_core.py \
  tests/test_web_management.py \
  tests/test_external_im_session.py \
  tests/test_im_http_router.py \
  tests/test_message_tool_im_client.py \
  -q
```

Record command, result, any failure, and fix point in this document.

## Phase 5 - Broader Verification And Residue Cleanup

Run broader contract tests:

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_context_binding_env_tool.py \
  tests/test_repo_consistency.py \
  -q
```

Run Web UI state tests:

```bash
node --test tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js
```

Run residue scans:

```bash
rg -n "target_identity_id is not a reachable actor identity|reply target cannot be derived from identity projection" scripts tools tests
```

Expected: no hits.

```bash
rg -n "fallback.*actor identity profile|actor identity profile.*fallback|daemon registry.*identity profile" scripts tools tests
```

Expected: no fallback implementation hits.

```bash
rg -n "_instance_list_for_identity_routes|save_test_actor_identity_profile" tests/test_web_management.py
```

Expected: `_instance_list_for_identity_routes` is pure projection and `save_test_actor_identity_profile` is called only by explicit seed helpers or tests.

Also inspect:

```bash
rg -n "save_actor_identity_profile|get_actor_identity_profile|list_actor_identity_profiles" tools/launcher/central_daemon_core.py tools/launcher/web_management.py tools/launcher/im_http_router.py tools/launcher/external_im_session.py
```

Expected: no static profile writes outside lifecycle/tests/identity repo.

## Phase 6 - Live Smoke Acceptance

Before smoke, confirm no stale mixed-runtime daemons:

```bash
ps -axo pid,command | rg "buddyswitch|central_daemon|instance_daemon|fea-tool|fea-im"
```

Stop stale BuddySwitch daemons if they are attached to the wrong shared root.

Start clean actors:

```bash
./buddyswitch-codex instance start --role dev --json
./buddyswitch-codex instance start --role market --json
```

Verify profiles:

```bash
find ~/.codex-buddyswitch/state/buddyswitch/objects/identities/actors -maxdepth 1 -type f -print
```

Verify Web IM actor roster and send:

```bash
curl -sS http://127.0.0.1:8766/api/im/actors | jq .
curl -sS -i -X POST http://127.0.0.1:8766/api/im/messages \
  -H 'Content-Type: application/json' \
  -d '{"target_identity_id":"<started-actor-id>","content":"smoke ping"}'
```

Expected:

- One actor identity profile per started actor.
- `/api/im/messages` returns HTTP 200.
- `delivery_status=accepted`.
- No `E_IM_TARGET actor identity profile not found`.

## Execution Record

### Phase 2 Red Output

Command:

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_daemon_core.py::DaemonCoreLifecycleTests::test_start_daemon_passes_actor_identity_env_to_child_process \
  tests/test_daemon_core.py::DaemonCoreRunLoopTests::test_run_daemon_ensures_actor_identity_profile_before_registering_reachability \
  tests/test_daemon_core.py::DaemonCoreRunLoopTests::test_run_daemon_rejects_conflicting_existing_actor_identity_profile \
  -q
```

Result:

```text
3 failed
- KeyError: 'BUDDYSWITCH_ACTOR_ID'
- profile was None after run_daemon(...)
- conflicting existing profile raised StopDaemonLoop instead of role mismatch ValueError
```

Command:

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_web_management.py::WebManagementStableImIdentityTests::test_web_im_actor_roster_does_not_create_actor_identity_profile \
  -q
```

Result:

```text
1 passed
```

### Phase 5 Broader Verification And Residue

Command:

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_context_binding_env_tool.py \
  tests/test_repo_consistency.py \
  -q
```

Result:

```text
107 passed, 685 subtests passed
```

Command:

```bash
node --test tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js
```

Result:

```text
pass 2, fail 0
```

Residue scan:

```bash
rg -n "target_identity_id is not a reachable actor identity|reply target cannot be derived from identity projection" scripts tools tests
```

Result: no hits.

Residue scan:

```bash
rg -n "fallback.*actor identity profile|actor identity profile.*fallback|daemon registry.*identity profile" scripts tools tests
```

Result: no hits.

Boundary scan:

```bash
rg -n "save_actor_identity_profile|get_actor_identity_profile|list_actor_identity_profiles" \
  tools/launcher/central_daemon_core.py \
  tools/launcher/web_management.py \
  tools/launcher/im_http_router.py \
  tools/launcher/external_im_session.py
```

Result: no hits.

Web helper scan:

```bash
rg -n "_instance_list_for_identity_routes|save_test_actor_identity_profile" tests/test_web_management.py
```

Result: `_instance_list_for_identity_routes(...)` remains a pure projection helper. Profile creation appears only in `save_test_actor_identity_profile(...)`, `_seed_actor_identity_profiles(...)`, and explicit send-success test setup.

### Phase 6 Live Smoke

Precheck:

```text
Found stale fea-tool central daemon, fea-tool actor daemons, and fea-tool Web server on 8766.
Stopped actor daemons with `./buddyswitch-codex instance stop <actor-id> --json`.
Stopped stale central daemon with `python3 tools/launcher/central_daemon.py stop --shared-root /Users/chen/.codex-buddyswitch`.
Stopped stale Web server on 8766.
Also found a later 8766 Web listener from the main checkout (`/Users/chen/Dev/buddyswitch/tools/launcher/web_management.py`) and stopped it before smoke.
Verified no central_daemon, instance_daemon, or 8766 Web listener before starting clean fea-im smoke.
```

Started clean actors:

```bash
./buddyswitch-codex instance start --role dev --json
./buddyswitch-codex instance start --role market --json
```

Result:

```text
act-dev-dd2486892914
act-market-eb1f160d6682
```

Profile check:

```bash
find ~/.codex-buddyswitch/state/buddyswitch/objects/identities/actors -maxdepth 1 -type f -print | sort
```

Result included:

```text
/Users/chen/.codex-buddyswitch/state/buddyswitch/objects/identities/actors/act-dev-dd2486892914.json
/Users/chen/.codex-buddyswitch/state/buddyswitch/objects/identities/actors/act-market-eb1f160d6682.json
```

Central registry check:

```bash
python3 tools/launcher/central_daemon.py request \
  --shared-root /Users/chen/.codex-buddyswitch \
  --method daemon.registry \
  --params '{}'
```

Result: registry contained current-shape `identity_id`, `identity`, `role_id`, and `status: online` rows for both clean `fea-im` actors.

Process source check during smoke:

```text
central_daemon.py serve path: /Users/chen/Dev/buddyswitch/.worktrees/fea-im/tools/launcher/central_daemon.py
instance_daemon.py run paths: /Users/chen/Dev/buddyswitch/.worktrees/fea-im/tools/launcher/instance_daemon.py
No fea-tool central/actor daemon process was present during the clean smoke.
The main checkout process found during precheck was Web-only on port 8766 and was stopped before the smoke request.
```

Web smoke:

```bash
./buddyswitch-codex web --port 8766
curl -sS http://127.0.0.1:8766/api/im/actors | jq .
curl -sS -i -X POST http://127.0.0.1:8766/api/im/messages \
  -H 'Content-Type: application/json' \
  -d '{"target_identity_id":"act-dev-dd2486892914","content":"smoke ping"}'
```

Result:

```text
/api/im/actors returned count=2 with act-dev-dd2486892914 and act-market-eb1f160d6682.
/api/im/messages returned HTTP/1.0 200 OK.
delivery_status=accepted.
actor_handling_status=submitted.
No E_IM_TARGET actor identity profile not found.
```

Cleanup:

```text
Stopped the temporary Web server.
Stopped smoke actors act-dev-dd2486892914 and act-market-eb1f160d6682.
Ran central_daemon.py stop-if-idle.
Verified no central_daemon, instance_daemon, or 8766 Web listener remained.
Verified central_daemon.py status reports healthy=false, pid=null, pid_live=false after cleanup.
Verified registry rows are current-shape identity_id rows with status=registered_offline after cleanup.
Verified both smoke actor identity profile files still exist after stop.
```

Note: this is a test-boundary cleanup check. Splitting `_instance_list_for_identity_routes(...)` into pure projection plus explicit seeding removes the masking in tests; Web production behavior already does not write actor profiles.

### Phase 4 Focused Verification

Command:

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_daemon_core.py::DaemonCoreLifecycleTests::test_start_daemon_passes_actor_identity_env_to_child_process \
  tests/test_daemon_core.py::DaemonCoreRunLoopTests::test_run_daemon_ensures_actor_identity_profile_before_registering_reachability \
  tests/test_daemon_core.py::DaemonCoreRunLoopTests::test_run_daemon_rejects_conflicting_existing_actor_identity_profile \
  -q
```

Result:

```text
3 passed
```

Command:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_daemon_core.py -q
```

Result:

```text
38 passed
```

Command:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_web_management.py -q
```

Result:

```text
66 passed, 43 subtests passed
```

Command:

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_daemon_core.py \
  tests/test_web_management.py \
  tests/test_external_im_session.py \
  tests/test_im_http_router.py \
  tests/test_message_tool_im_client.py \
  -q
```

Result:

```text
121 passed, 49 subtests passed
```

Command:

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_delete_removes_only_target_instance_without_shared_state \
  -q
```

Result:

```text
1 passed
```
