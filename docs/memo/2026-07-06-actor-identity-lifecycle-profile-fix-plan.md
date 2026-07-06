# Actor Identity Lifecycle Profile Fix Plan

> For agentic workers: implement this plan task-by-task. Keep the fix forward-moving: no compatibility branch, no fallback resolver, no duplicated identity source.

**Goal:** Make every runnable actor have a persisted actor identity profile before it enters daemon reachability, so `/api/im/*`, actor tools, and Central IM resolve actor targets through one identity source.

**Architecture:** Identity owns static actor facts. Central daemon owns runtime reachability only. Actor lifecycle bridges them by ensuring the identity profile exists before registering the actor as reachable.

**Tech Stack:** Python launcher/runtime code, Bash launcher wrapper, JSON runtime state, pytest/unittest.

---

## 1. Task Target

Fix the current `fea-im` regression:

```text
/api/im/actors lists active actors
/api/im/messages rejects send with:
E_IM_TARGET: actor identity profile not found: act-...
```

The fix must close the migration loop introduced by the identity-first send resolver:

```text
actor lifecycle start/resume
-> persist actor identity profile
-> register central daemon runtime reachability
-> IM target resolver validates identity profile + online reachability
-> message send succeeds
```

## 2. Bitter Principles Applied

From `docs/bitter`:

- Fix the owning layer, not the prompt or UI surface.
- Do not compensate for runtime contract gaps with prompt bulk, wrapper behavior, or fallback branches.
- Product core must own semantics; interfaces only project it.
- A sliced implementation is incomplete until the user-visible contract crosses all required layers.
- Residue cleanup requires behavior proof and live-surface proof.

## 3. Current Root Cause

The resolver now correctly treats identity as the static target source:

- `scripts/env/services/messages.py:102` `resolve_im_send_target(...)`
- actor target requires `identity_repo.get_actor_identity_profile(target_id)`
- then actor reachability is checked via daemon

But actor lifecycle still only writes runtime facts:

- `tools/launcher/env.sh:373` writes `instance.json`
- `tools/launcher/daemon_core.py:1844` loads daemon context from `instance.json`
- `tools/launcher/daemon_core.py:1875` registers actor reachability
- `tools/launcher/central_daemon_core.py:237` stores online registry row

Missing write:

```text
state/buddyswitch/objects/identities/actors/<actor-id>.json
```

So the system is currently split:

```text
instance list / daemon registry know the actor is online
identity module does not know the actor exists
send resolver rejects the target
```

## 4. Architecture Boundary

Keep these boundaries strict:

```text
identity profile
  Owns: actor id, identity type, role id, optional label/created_at
  Does not own: online status, mailbox, socket, handler state

central daemon registry
  Owns: current reachability, mailbox/socket endpoint, heartbeat, last_seen_at
  Does not own: canonical static actor identity

instance record
  Owns: local launcher process state and workspace pointers
  Does not own: product identity truth
```

Correct invariant:

```text
No actor may be registered reachable before its identity profile exists.
```

Incorrect fixes:

- Do not relax `resolve_im_send_target`.
- Do not fallback from identity profile lookup to daemon registry.
- Do not make Web `/api/im/messages` synthesize actor profiles.
- Do not make central daemon become the static identity owner.
- Do not delete identity profile on actor stop.

## 5. Implementation Plan

### Task 1: Add lifecycle regression tests

**Files:**

- Modify: `tests/test_daemon_core.py`

Add imports:

```python
from env.repos import identities as identity_repo
```

Extend `RUNTIME_ENV_KEYS`:

```python
RUNTIME_ENV_KEYS = (
    "BUDDYSWITCH_SHARED_ROOT",
    "BUDDYSWITCH_STATE_ROOT",
    "BUDDYSWITCH_INSTANCE_ROOT",
    "BUDDYSWITCH_INSTANCE_JSON",
    "BUDDYSWITCH_WORKSPACE_DIR",
    "BUDDYSWITCH_ACTOR_ID",
    "BUDDYSWITCH_ROLE_ID",
)
```

Add a failing test proving daemon child environment carries actor identity context:

```python
def test_start_daemon_passes_actor_identity_env_to_child_process(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root:
        instance = self._instance(temp_root)
        _commands, popen_kwargs = self._patch_process_start([4330])
        self._patch_pid_live({4330})
        self._patch_sleep_to_record_ready(instance_root=instance["instance_root"], pid=4330)

        payload = self.core.start_daemon(instance["instance_json"])

        self.assertTrue(payload["started"])
        env = popen_kwargs[0].get("env")
        self.assertIsInstance(env, dict)
        assert isinstance(env, dict)
        self.assertEqual(env["BUDDYSWITCH_ACTOR_ID"], "act-dev-daed00000001")
        self.assertEqual(env["BUDDYSWITCH_ROLE_ID"], "dev")
```

Add a failing test proving `run_daemon` persists profile before central registration:

```python
def test_run_daemon_ensures_actor_identity_profile_before_registering_reachability(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root:
        instance = self._instance(temp_root)
        fake_client = FakeRunDaemonClient(notifications=[StopDaemonLoop("stop")])
        self._patch_app_server_client(fake_client)
        self._patch_daemon_communication()
        observed_profile_at_register: list[dict[str, object] | None] = []

        original_register = self.core.register_daemon_actor

        def observing_register(context: object, identity_route: dict[str, str]) -> dict[str, object]:
            observed_profile_at_register.append(identity_repo.get_actor_identity_profile(identity_route["identity_id"]))
            return original_register(context, identity_route)

        self.addCleanup(setattr, self.core, "register_daemon_actor", original_register)
        self.core.register_daemon_actor = observing_register

        with self.assertRaises(StopDaemonLoop):
            self.core.run_daemon(instance["instance_json"], handlers=[])

        profile = identity_repo.get_actor_identity_profile("act-dev-daed00000001")
        self.assertEqual(profile, {"identity": {"id": "act-dev-daed00000001", "type": "actor"}, "role_id": "dev"})
        self.assertEqual(observed_profile_at_register, [profile])
```

Add a fail-closed test for identity role conflicts:

```python
def test_run_daemon_rejects_conflicting_existing_actor_identity_profile(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root:
        instance = self._instance(temp_root)
        os.environ["BUDDYSWITCH_SHARED_ROOT"] = str(Path(temp_root))
        os.environ["BUDDYSWITCH_STATE_ROOT"] = str(Path(temp_root) / "state")
        os.environ["BUDDYSWITCH_ACTOR_ID"] = "act-dev-daed00000001"
        runtime_files.refresh_runtime_roots_from_env()
        identity_repo.save_actor_identity_profile(
            {"identity": {"id": "act-dev-daed00000001", "type": "actor"}, "role_id": "pm"}
        )
        fake_client = FakeRunDaemonClient(notifications=[])
        self._patch_app_server_client(fake_client)
        communication = self._patch_daemon_communication()

        with self.assertRaisesRegex(ValueError, "actor identity profile role mismatch"):
            self.core.run_daemon(instance["instance_json"], handlers=[])

        self.assertEqual(communication["registered"], [])
```

Expected before implementation:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_daemon_core.py -q
```

The new tests fail because actor env is incomplete and no actor profile is written.

### Task 2: Implement actor identity profile ensure in daemon lifecycle

**Files:**

- Modify: `tools/launcher/daemon_core.py`

Add import:

```python
from env.repos import identities as identity_repo  # noqa: E402
```

Extend `derive_daemon_runtime_env(context)`:

```python
return {
    "BUDDYSWITCH_SHARED_ROOT": str(shared_root),
    "BUDDYSWITCH_STATE_ROOT": str(shared_root / "state"),
    "BUDDYSWITCH_INSTANCE_ROOT": str(context.instance_root),
    "BUDDYSWITCH_INSTANCE_JSON": str(context.instance_json),
    "BUDDYSWITCH_WORKSPACE_DIR": str(context.workspace_dir),
    "BUDDYSWITCH_ACTOR_ID": context.actor_id,
    "BUDDYSWITCH_ROLE_ID": context.role,
}
```

Add helper:

```python
def ensure_actor_identity_profile(context: DaemonContext, identity_route: dict[str, str]) -> dict[str, Any]:
    existing = identity_repo.get_actor_identity_profile(identity_route["identity_id"])
    if isinstance(existing, dict):
        if existing.get("role_id") != identity_route["role_id"]:
            raise ValueError(
                "actor identity profile role mismatch: "
                f"{identity_route['identity_id']} has {existing.get('role_id')}, "
                f"instance has {identity_route['role_id']}"
            )
        return existing
    return identity_repo.save_actor_identity_profile(
        {
            "identity": {"id": identity_route["identity_id"], "type": "actor"},
            "role_id": identity_route["role_id"],
        }
    )
```

Call it inside `run_daemon(...)` after runtime roots are refreshed and before `state.record_ready(...)`:

```python
identity_route = identity_route_for_context(context)
ensure_actor_identity_profile(context, identity_route)
```

The call must happen before the daemon marks itself ready and before central registration. If profile ensure fails, the parent start path must fail closed instead of leaving an online actor without identity.

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_daemon_core.py -q
```

Expected: daemon lifecycle tests pass.

### Task 3: Remove hidden test masking around Web IM

**Files:**

- Modify: `tests/test_web_management.py`

Current helper `_instance_list_for_identity_routes(...)` silently writes actor identity profiles before returning instance rows. That hides the exact regression.

Change it into two explicit helpers:

```python
@staticmethod
def _seed_actor_identity_profiles(identity_routes: list[dict[str, str]]) -> None:
    for route in identity_routes:
        save_test_actor_identity_profile(actor_id=route["actor_id"], role_id=route["role_id"])

@staticmethod
def _instance_list_for_identity_routes(identity_routes: list[dict[str, str]]) -> dict[str, object]:
    return {
        "instances": [
            {
                "actor_id": route["actor_id"],
                "role": route["role_id"],
                "status": "active",
                "app_server_health": "healthy",
                "thread_id": f"thread-{index}",
                "browser_port": None,
                "updated_at": "2026-06-26T10:10:00Z",
                "workspace_dir": f"/tmp/buddyswitch/instances/{route['actor_id']}/workspace",
            }
            for index, route in enumerate(identity_routes)
        ]
    }
```

For tests that intentionally require send success with fake instance rows, call `_seed_actor_identity_profiles(...)` explicitly before constructing the service.

Add a targeted negative test:

```python
def test_web_im_actor_roster_does_not_create_actor_identity_profile(self) -> None:
    routes = [{"actor_id": "act-web-profile-missing", "role_id": "dev"}]
    runner = FakeRunner()
    runner.add(["instance", "list", "--json"], command_json(self._instance_list_for_identity_routes(routes)))
    service = self._service(runner)

    status, payload = service.handle_api("GET", "/api/im/actors", b"")

    self.assertEqual(status, 200)
    self.assertEqual(payload["count"], 1)
    self.assertIsNone(identity_repo.get_actor_identity_profile("act-web-profile-missing"))
```

This preserves the boundary: Web roster is a projection; lifecycle owns profile creation.

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_web_management.py -q
```

Expected: Web tests pass without hidden lifecycle seeding.

### Task 4: Contract verification tests

**Files:**

- Modify if needed: `tests/test_im_http_router.py`
- Modify if needed: `tests/test_external_im_session.py`
- Modify if needed: `tests/test_message_tool_im_client.py`

Keep these resolver behaviors intact:

```text
missing actor identity profile -> E_IM_TARGET
existing actor profile + online reachability -> send accepted
external identity profile -> send accepted without actor reachability
offline actor reachability -> E_IM_TARGET
```

Run:

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_daemon_core.py \
  tests/test_web_management.py \
  tests/test_external_im_session.py \
  tests/test_im_http_router.py \
  tests/test_message_tool_im_client.py \
  -q
```

Expected: focused IM/lifecycle suite passes.

### Task 5: Live smoke on clean `fea-im` runtime

After code tests pass, restart the `fea-im` central daemon and actor instances. Do not mix `fea-tool` and `fea-im` processes.

Smoke checks:

```bash
./buddyswitch-codex instance start --role dev --json
./buddyswitch-codex instance start --role market --json
find ~/.codex-buddyswitch/state/buddyswitch/objects/identities/actors -maxdepth 1 -type f -print
```

Expected:

```text
one actor identity profile per started actor
```

Then verify Web IM:

```bash
curl -sS http://127.0.0.1:8766/api/im/actors | jq .
curl -sS -i -X POST http://127.0.0.1:8766/api/im/messages \
  -H 'Content-Type: application/json' \
  -d '{"target_identity_id":"<started-actor-id>","content":"smoke ping"}'
```

Expected:

```text
HTTP 200
delivery_status=accepted
no E_IM_TARGET actor identity profile not found
```

## 6. Acceptance Criteria

The task is done only when all are true:

- Starting or resuming an actor persists `identities/actors/<actor-id>.json`.
- The profile is written before daemon reachability registration.
- Existing profile with matching role is reused.
- Existing profile with conflicting role fails closed before registration.
- Actor stop only changes runtime reachability and process state; identity profile remains.
- Central daemon remains runtime-only and does not write identity profiles.
- `resolve_im_send_target` remains strict and does not fallback to daemon registry.
- Web `/api/im/actors` remains a roster projection and does not create identity profiles.
- Focused tests pass.
- A clean live `fea-im` smoke proves `/api/im/messages` can send to a started actor.

## 7. Residue Checks

Run targeted scans after implementation:

```bash
rg -n "target_identity_id is not a reachable actor identity|reply target cannot be derived from identity projection" scripts tools tests
```

Expected: no live code hits.

```bash
rg -n "fallback.*actor identity profile|actor identity profile.*fallback|daemon registry.*identity profile" scripts tools tests
```

Expected: no fallback implementation.

```bash
rg -n "_instance_list_for_identity_routes|save_test_actor_identity_profile" tests/test_web_management.py
```

Expected: profile seeding is explicit, not hidden inside instance-list projection.

## 8. Non-Goals

- Do not change external channel adapters.
- Do not implement actor -> external channel push in this task.
- Do not migrate/delete historical actor profiles.
- Do not introduce a new contact table, resolver service, or compatibility layer.
- Do not change the IM resolver contract to accept daemon registry as identity truth.

## 9. Final Validation Command Set

Run the focused suite:

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_daemon_core.py \
  tests/test_web_management.py \
  tests/test_external_im_session.py \
  tests/test_im_http_router.py \
  tests/test_message_tool_im_client.py \
  -q
```

Run broader contract checks:

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_context_binding_env_tool.py \
  tests/test_repo_consistency.py \
  -q
```

Run Web UI state checks:

```bash
node --test tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js
```

Run live smoke only after ensuring no stale `fea-tool` central daemon or actor daemon remains attached to the shared root.

