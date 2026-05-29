# Runtime Actor Address Message/Daemon Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` before implementation, then use `superpowers:executing-plans` or inline TDD to execute this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a single `RuntimeActorAddress(buddy_id, instance_id)` identity/address contract and wire daemon presence plus message notification status through that contract without moving presence or message data into `actor_profile`.

**Architecture:** Keep `actor_profile` responsible only for runtime actor identity. Add a small daemon presence/delivery boundary owned by tool runtime/daemon code, register daemon contexts with `actor_address`, and let message send write durable messages first, then ask the daemon boundary for best-effort notification. Keep message tools black-box by accessing daemon delivery through `ToolContext`, not by importing repos, runtime kernel, or launcher internals.

**Tech Stack:** Python stdlib dataclasses/JSON files, existing env.tool runtime context, existing daemon core tests, pytest/unittest.

---

## Scope

Implement the complete boundary change in this worktree:

- extend `scripts/env/tool_runtime/actor_profile.py`;
- add a small daemon presence/delivery module under `scripts/env/tool_runtime/`;
- update `scripts/env/tool_runtime/context.py`;
- update `tools/launcher/daemon_core.py`;
- update `scripts/env/tools/message/_impl.py`;
- update focused actor profile, daemon, and message tests;
  - keep fixture ids launcher-compatible and buddy-prefix-consistent without making strict `inst-<buddy>-<12 hex>` a hidden prerequisite for this phase.

Do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.

## Target File Structure

Create:

- `scripts/env/tool_runtime/daemon_presence.py`
  - file-backed presence registry helpers;
  - `actor_address` registry row validation/projection;
  - v1 target resolution statuses;
  - reference-only message notification event creation/delivery.

Modify:

- `scripts/env/tool_runtime/actor_profile.py`
  - add `RuntimeActorAddress`;
  - add address validation and payload projection;
  - add `RuntimeActorProfile.actor_address`.

- `scripts/env/tool_runtime/context.py`
  - add `actor_address` to `ToolContext`;
  - add `DaemonAccess` wrapper exposed as `context.daemon`;
  - keep mapping keys stable unless a test deliberately adds `actor_address`.

- `tools/launcher/daemon_core.py`
  - resolve daemon context actor address through `actor_profile`;
  - register/unregister online actor records through `daemon_presence`;
  - keep endpoint, heartbeat, status, and timestamps in registry rows only.

- `scripts/env/tools/message/_impl.py`
  - after durable message creation, call `context.daemon.notify_message_available(...)`;
  - merge `notification_status` and related metadata into success response;
  - never parse target instance JSON.

- `tests/test_runtime_actor_profile.py`
  - add address validation/serialization/profile/boundary tests.

- `tests/test_daemon_core.py`
  - add daemon registry and presence routing tests.

- `tests/test_message_env_tool.py`
  - add offline, online, delivery failure, and ambiguous actor tests.

## Data Contracts

### Actor Address

```python
RuntimeActorAddress(
    buddy_id="dev",
    instance_id="inst-dev-daemon",
)
```

Payload:

```python
{"buddy_id": "dev", "instance_id": "inst-dev-daemon"}
```

Validation:

- `buddy_id`: `^[a-z][a-z0-9-]*$`
- `instance_id`: current launcher-compatible shape `^inst-[A-Za-z0-9._-]+$`
- `instance_id` must start with `f"inst-{buddy_id}-"`.
- Strict `inst-<buddy>-<12hex>` validation is a separate cross-module runtime instance id contract migration.

### Presence Registry Row

```json
{
  "actor_address": {
    "buddy_id": "dev",
    "instance_id": "inst-dev-daemon"
  },
  "endpoint": {
    "kind": "daemon_state_file",
    "path": "/tmp/.../instances/inst-dev-daemon/runtime/daemon/notifications.jsonl"
  },
  "heartbeat": {
    "kind": "daemon_ready_state"
  },
  "status": "online",
  "last_seen_at": "2026-05-29T00:00:00Z"
}
```

The registry may be a JSON file under the runtime state root. It must be isolated by `runtime_files` test overrides and must not write to the source checkout in unit tests.

### Message Notification Event

```json
{
  "type": "message.available",
  "message_id": "msg-123456789abc",
  "from_actor_address": {
    "buddy_id": "design",
    "instance_id": "inst-design-1a2b3c4d5e6f"
  },
  "to_actor_address": {
    "buddy_id": "dev",
    "instance_id": "inst-dev-7a8b9c0d1e2f"
  }
}
```

No message body, message object, `from_buddy`, or `to_buddy` fields belong in this event.

## Task 1: Add RuntimeActorAddress Tests

**Files:**

- Modify: `tests/test_runtime_actor_profile.py`

- [ ] **Step 1: Write failing address serialization test**

Add a test named `test_runtime_actor_address_serializes_stable_payload` that imports `RuntimeActorAddress`, constructs `dev/inst-dev-daemon`, asserts `to_payload()`, and asserts `from_payload()` round-trips.

- [ ] **Step 2: Run red test**

```bash
python3 -m pytest tests/test_runtime_actor_profile.py::RuntimeActorProfileTests::test_runtime_actor_address_serializes_stable_payload -q
```

Expected: fail because `RuntimeActorAddress` does not exist.

- [ ] **Step 3: Write failing validation test**

Add `test_runtime_actor_address_rejects_invalid_identity` with invalid buddy ids, invalid instance ids, and buddy/instance mismatch cases. Add a payload test proving `from_payload()` rejects endpoint, heartbeat, status, or other non-identity fields.

- [ ] **Step 4: Run red validation test**

```bash
python3 -m pytest tests/test_runtime_actor_profile.py::RuntimeActorProfileTests::test_runtime_actor_address_rejects_invalid_identity -q
```

Expected: fail because validation does not exist.

## Task 2: Implement RuntimeActorAddress

**Files:**

- Modify: `scripts/env/tool_runtime/actor_profile.py`

- [ ] **Step 1: Add regex constants and address dataclass**

Implement `BUDDY_ID_PATTERN`, the launcher-compatible `INSTANCE_ID_PATTERN`, `RuntimeActorAddress.__post_init__`, `to_payload()`, and `from_payload()`. `from_payload()` must reject non-identity fields.

- [ ] **Step 2: Update RuntimeActorProfile**

Add `actor_address: RuntimeActorAddress` and construct it in `resolve_runtime_actor_profile()`.

- [ ] **Step 3: Update existing focused fixtures**

In `tests/test_runtime_actor_profile.py`, replace `inst-dev` fixtures with launcher-compatible, buddy-prefix-consistent ids.

- [ ] **Step 4: Run actor profile tests**

```bash
python3 -m pytest tests/test_runtime_actor_profile.py -q
```

Expected: all actor-profile tests pass.

## Task 3: Add Daemon Presence Registry Tests

**Files:**

- Modify: `tests/test_daemon_core.py`

- [ ] **Step 1: Add registry row test**

Add `test_daemon_registration_projects_actor_address_and_registry_facts` using a valid instance id. Assert registry rows use `actor_address`, and endpoint/heartbeat/status/last_seen_at remain outside that address.

- [ ] **Step 2: Run red registry row test**

```bash
python3 -m pytest tests/test_daemon_core.py::DaemonCoreStateTests::test_daemon_registration_projects_actor_address_and_registry_facts -q
```

Expected: fail because daemon registration/presence API does not exist.

- [ ] **Step 3: Add presence routing status test**

Add `test_daemon_presence_resolves_offline_single_and_ambiguous_actor_statuses`.

- [ ] **Step 4: Run red presence routing test**

```bash
python3 -m pytest tests/test_daemon_core.py::DaemonCoreStateTests::test_daemon_presence_resolves_offline_single_and_ambiguous_actor_statuses -q
```

Expected: fail because presence routing API does not exist.

## Task 4: Implement Daemon Presence Registry

**Files:**

- Create: `scripts/env/tool_runtime/daemon_presence.py`
- Modify: `tools/launcher/daemon_core.py`
- Modify: `tests/test_daemon_core.py`

- [ ] **Step 1: Create daemon_presence module**

Implement:

- `registry_path()`;
- `clear_registry()`;
- `load_registry()`;
- `register_online_actor(...)`;
- `unregister_actor(...)`;
- `online_actor_records_for_buddy(...)`;
- `resolve_notification_target(...)`;
- `message_available_event(...)`;
- `deliver_message_available(...)`.

Use `RuntimeActorAddress.from_payload()` when reading rows.

- [ ] **Step 2: Wire daemon_core registration helpers**

Add `actor_address_for_context(context)`, `register_daemon_presence(context)`, and `unregister_daemon_presence(context)`.

- [ ] **Step 3: Register/unregister in daemon lifecycle**

Call `register_daemon_presence(context)` after `run_daemon()` records ready state. Call `unregister_daemon_presence(context)` when `run_daemon()` exits and when `stop_daemon()` stops or clears a daemon.

- [ ] **Step 4: Run daemon focused tests**

```bash
python3 -m pytest tests/test_daemon_core.py tests/test_daemon_service_contract.py -q
```

Expected: pass without starting real daemon processes because tests patch process/lifecycle paths.

## Task 5: Add Message Notification Tests

**Files:**

- Modify: `tests/test_message_env_tool.py`

- [ ] **Step 1: Update message fixture ids**

Change message dispatch instance ids to launcher-compatible, buddy-prefix-consistent values where message send/list dispatch goes through the actor profile.

- [ ] **Step 2: Add offline success test**

Assert `message.send` to an offline buddy still creates a durable message and returns `notification_status == "skipped_offline"`.

- [ ] **Step 3: Run red offline test**

```bash
python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_send_offline_target_creates_message_with_skipped_notification -q
```

Expected: fail because `notification_status` is missing.

- [ ] **Step 4: Add online reference-only event test**

Register one online target actor, dispatch `message.send`, assert `notification_status == "delivered"`, and assert the event contains only address references.

- [ ] **Step 5: Add delivery failure and ambiguous actor tests**

Assert delivery failure and ambiguous target both keep durable message creation successful.

## Task 6: Implement Message Notification Boundary

**Files:**

- Modify: `scripts/env/tool_runtime/context.py`
- Modify: `scripts/env/tools/message/_impl.py`

- [ ] **Step 1: Add ToolContext actor_address and DaemonAccess**

`ToolContext.from_actor_profile()` should pass `actor_profile.actor_address`. `DaemonAccess.notify_message_available(...)` should delegate to `daemon_presence.deliver_message_available(...)`.

- [ ] **Step 2: Call daemon access after durable write**

In `send_message()`, create the message first. Then call:

```python
notification = context.daemon.notify_message_available(
    message_id=message["id"],
    from_actor_address=context.actor_address,
    to_buddy=to_buddy,
)
```

Merge `notification_status`, `to_actor_address`, `notification_event`, and `notification_error` when present into `extra`.

- [ ] **Step 3: Run message focused tests**

```bash
python3 -m pytest tests/test_message_env_tool.py -q
```

Expected: pass.

## Task 7: Boundary Search And Focused Regression

**Files:**

- Modify only if a focused regression exposes a real boundary issue.

- [ ] **Step 1: Run focused combined verification**

```bash
python3 -m pytest \
  tests/test_runtime_actor_profile.py \
  tests/test_daemon_core.py \
  tests/test_daemon_service_contract.py \
  tests/test_message_env_tool.py \
  tests/test_env_tool_identity.py \
  tests/test_black_box_tool_runtime.py \
  tests/test_env_tool_package_independence.py \
  -q
```

- [ ] **Step 2: Run boundary search**

```bash
rg -n "daemon_buddy|target_buddy_instance|glob\\(.*instances|json\\.loads|notification_status|message\\.available|actor_address|RuntimeActorAddress" scripts/env tools/launcher tests
```

Inspect results. `json.loads` is expected in repository/storage and daemon context loading; it must not be newly used by message routing to parse target instance records.

- [ ] **Step 3: Run broad verification only after focused tests are green**

```bash
python3 -m pytest tests -q
```

If resource warning signs appear, stop immediately and record the command/output. Do not continue scaling service-starting tests.

## Self-Review Checklist

- Every requirement in the test plan maps to a task above.
- No task requires starting real services before unit-level proof exists.
- The plan does not add compatibility wrappers or old/new identity dual paths.
- The plan does not place presence or delivery fields in `actor_profile`.
- The plan does not ask message code to parse target instance records.
- The plan preserves durable message creation as the source of truth.
