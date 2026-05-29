# Runtime Actor Address Message/Daemon Boundary Test Plan

Date: 2026-05-29
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-inst`

## Goal

Prove that BuddySwitch has one runtime actor address language:

```text
RuntimeActorAddress(buddy_id, instance_id)
```

and that daemon presence/routing, daemon notification delivery, and durable message data consume that address without duplicating identity parsing or pushing runtime facts into `actor_profile`.

## Current Code Facts

- `scripts/env/tool_runtime/actor_profile.py` currently exposes `AuthSubject`, `RuntimeInstanceRecord`, `RuntimeActorProfile`, and `resolve_runtime_actor_profile()`, but no `RuntimeActorAddress`.
- `RuntimeActorProfile` exposes `instance_id` and `active_buddy`; it does not expose `actor_address`.
- `tools/launcher/daemon_core.py` owns per-instance daemon lifecycle, state, handler dispatch, and status. It has no central presence registry or actor address projection.
- `scripts/env/tools/message/_impl.py` writes durable message objects only. It returns no `notification_status` and has no daemon presence/delivery boundary.
- `scripts/env/repos/messages.py` owns durable message storage and should stay independent from daemon presence and delivery.
- Env tool packages are black-box packages. They must not directly import `env.repos`, `env.domain`, `env_manifest`, `runtime_kernel`, or sibling tools.

## Non-Goals

- Do not rename or remove `active_buddy`.
- Do not add a generic event bus, routing engine, plugin system, permission framework, workflow engine, or message transport platform.
- Do not make durable message creation depend on target online state.
- Do not implement a multi-online actor selection policy.
- Do not put endpoint, heartbeat, online status, routing choice, delivery status, message storage, or message business rules into `actor_profile`.
- Do not start real daemons, browsers, app servers, or brokers in focused unit tests.

## Functional Requirements

| ID | Requirement |
| --- | --- |
| FR1 | `actor_profile` defines `RuntimeActorAddress(buddy_id, instance_id)`. |
| FR2 | `RuntimeActorAddress` accepts only buddy ids matching `^[a-z][a-z0-9-]*$`. |
| FR3 | `RuntimeActorAddress` accepts the current launcher-compatible instance id shape `^inst-[A-Za-z0-9._-]+$`. |
| FR4 | `RuntimeActorAddress` also requires buddy-prefix consistency: `instance_id.startswith(f"inst-{buddy_id}-")`. |
| FR5 | `RuntimeActorAddress.to_payload()` returns stable JSON projection `{"buddy_id": ..., "instance_id": ...}`. |
| FR6 | `RuntimeActorAddress.from_payload(payload)` reuses the same validation rules and rejects non-identity fields such as endpoint, heartbeat, or status. |
| FR7 | `RuntimeActorProfile.actor_address` exists and satisfies `active_buddy == actor_address.buddy_id` and `instance_id == actor_address.instance_id`. |
| FR8 | `actor_profile` does not expose endpoint, heartbeat, presence, status, routing, delivery, or message fields. |
| FR9 | Daemon registration writes identity under `actor_address`, not `buddy`, `daemon_buddy`, or `target_buddy_instance`. |
| FR10 | Daemon registry keeps endpoint, heartbeat, status, and `last_seen_at` at registry layer. |
| FR11 | Presence lookup by `buddy_id` returns online actor address payloads. |
| FR12 | Direct notification routing returns `skipped_offline` for zero online actors, target delivery for one online actor, and `ambiguous_online_actor` for multiple online actors. |
| FR13 | `message.send` creates the durable message before consulting daemon presence. |
| FR14 | Offline target still returns success with `notification_status == "skipped_offline"`. |
| FR15 | Delivery failure does not roll back the message object and returns `notification_status == "delivery_failed"`. |
| FR16 | Online notification event carries only `type`, `message_id`, `from_actor_address`, and `to_actor_address`; it does not carry message body or message object. |
| FR17 | Message routing consumes daemon presence results and does not parse target instance JSON directly. |
| FR18 | Existing message inbox/list semantics remain unchanged. |

## Test Cases

### T1: RuntimeActorAddress validates and serializes the address

File: `tests/test_runtime_actor_profile.py`

Behavior:

- Construct `RuntimeActorAddress(buddy_id="dev", instance_id="inst-dev-daemon")`.
- Assert fields are stripped and stable.
- Assert `to_payload()` equals:

```python
{"buddy_id": "dev", "instance_id": "inst-dev-daemon"}
```

- Assert `RuntimeActorAddress.from_payload(...)` returns an equal address.

Expected red result before implementation: import or attribute failure for `RuntimeActorAddress`.

### T2: RuntimeActorAddress rejects invalid identity

File: `tests/test_runtime_actor_profile.py`

Cases:

- blank `buddy_id`;
- uppercase buddy id;
- buddy id containing underscore or dot;
- blank `instance_id`;
- instance id missing the `inst-` prefix;
- instance id containing whitespace;
- instance id whose prefix buddy does not equal `buddy_id`.
- payload containing endpoint, heartbeat, or status fields.

Expected red result before implementation: invalid values are accepted or `RuntimeActorAddress` is missing.

### T3: RuntimeActorProfile exposes actor_address without owning runtime facts

File: `tests/test_runtime_actor_profile.py`

Behavior:

- Resolve a record with `instance_id="inst-dev-1a2b3c4d5e6f"` and `buddy_id="dev"`.
- Assert:
  - `profile.actor_address == RuntimeActorAddress("dev", "inst-dev-1a2b3c4d5e6f")`;
  - `profile.active_buddy == profile.actor_address.buddy_id`;
  - `profile.instance_id == profile.actor_address.instance_id`;
  - `profile` has no `endpoint`, `heartbeat`, `presence`, `status`, `routing`, `delivery_status`, or `message` attributes.

Expected red result before implementation: `actor_address` is missing.

### T4: Daemon registry writes actor_address and keeps runtime facts outside identity

File: `tests/test_daemon_core.py`

Behavior:

- Load a daemon context for a valid dev instance.
- Register it in the daemon presence registry.
- Assert the stored registry row contains:
  - `actor_address == {"buddy_id": "dev", "instance_id": "inst-dev-1a2b3c4d5e6f"}`;
  - `endpoint`;
  - `heartbeat`;
  - `status == "online"`;
  - `last_seen_at`.
- Assert the row does not contain `buddy`, `daemon_buddy`, `target_buddy_instance`, `endpoint` under `actor_address`, or `status` under `actor_address`.

Expected red result before implementation: no registry API or no `actor_address` field.

### T5: Presence lookup and routing return v1 statuses

File: `tests/test_daemon_core.py`

Behavior:

- Empty registry for `dev` returns `notification_status == "skipped_offline"`.
- One online dev address returns `notification_status == "target_online"` and the target `actor_address`.
- Two online dev addresses return `notification_status == "ambiguous_online_actor"` and no selected target.

Expected red result before implementation: no presence routing API.

### T6: Message send succeeds offline and reports skipped notification

File: `tests/test_message_env_tool.py`

Behavior:

- Dispatch `message.send` from `design` to `dev` with no dev actor in presence registry.
- Assert response is ok.
- Assert message file exists and is returned.
- Assert `notification_status == "skipped_offline"`.
- Assert non-message object dirs are unchanged.

Expected red result before implementation: response has no `notification_status`.

### T7: Message send consumes online actor_address and emits reference-only event

File: `tests/test_message_env_tool.py`

Behavior:

- Register one online dev actor in daemon presence using `RuntimeActorAddress`.
- Dispatch `message.send` from `design` to `dev`.
- Assert response is ok and `notification_status == "delivered"`.
- Read the recorded daemon notification event.
- Assert event shape:

```python
{
    "type": "message.available",
    "message_id": response["message_id"],
    "from_actor_address": {"buddy_id": "design", "instance_id": "inst-design-..."},
    "to_actor_address": {"buddy_id": "dev", "instance_id": "inst-dev-..."},
}
```

- Assert the event has no `content`, `message`, `from_buddy`, or `to_buddy` fields.

Expected red result before implementation: no registry, no event, or event includes message body.

### T8: Delivery failure does not roll back durable message

File: `tests/test_message_env_tool.py`

Behavior:

- Register one online dev actor with a delivery endpoint that intentionally fails.
- Dispatch `message.send`.
- Assert response is ok.
- Assert the message object exists.
- Assert `notification_status == "delivery_failed"` and `notification_error` contains the delivery failure.

Expected red result before implementation: delivery errors either fail the whole send or are not represented.

### T9: Ambiguous online actor does not choose a target and does not roll back message

File: `tests/test_message_env_tool.py`

Behavior:

- Register two online dev actor addresses.
- Dispatch `message.send` from `pm` to `dev`.
- Assert response is ok.
- Assert message object exists.
- Assert `notification_status == "ambiguous_online_actor"`.
- Assert no notification event was written.

Expected red result before implementation: no ambiguity status or target is chosen implicitly.

### T10: Boundary search prevents duplicated identity parsing

File: `tests/test_runtime_actor_profile.py` or `tests/test_daemon_core.py`

Behavior:

- Assert `scripts/env/tools/message/_impl.py` does not contain `instance_json`, `glob("instances")`, `json.loads`, or target instance path parsing for routing.
- Assert daemon/message code uses `actor_address` field name for registry identity.
- Assert no daemon registry row uses `daemon_buddy` or `target_buddy_instance`.

Expected red result before implementation: no address language or direct parsing violation appears when added incorrectly.

## Deferred Contract Migration

The launcher currently validates instance ids with the broad `^inst-[A-Za-z0-9._-]+$` rule while generated ids already use `inst-<buddy>-<12hex>`. `RuntimeActorAddress` is not a raw launcher validator wrapper: it accepts the launcher-compatible shape and additionally requires buddy-prefix consistency. Tightening to `^inst-[a-z][a-z0-9-]*-[0-9a-f]{12}$` should be a separate launcher/runtime/web-management/tests migration.

## Verification Commands

Run focused red/green tests first:

```bash
python3 -m pytest tests/test_runtime_actor_profile.py -q
python3 -m pytest tests/test_daemon_core.py -q
python3 -m pytest tests/test_message_env_tool.py -q
```

Run combined focused verification:

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

Run boundary search verification:

```bash
rg -n "daemon_buddy|target_buddy_instance|message\\.available|actor_address|notification_status|RuntimeActorAddress|glob\\(.*instances|json\\.loads" scripts/env tools/launcher tests
```

Final broad verification must respect `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`:

1. Run focused unit tests above.
2. Confirm they do not start persistent services.
3. Run broad Python suite only after focused tests are green:

```bash
python3 -m pytest tests -q
```

4. If broad verification starts service-heavy tests or shows resource warning signs, stop, capture the failing command/output, and do not keep scaling the run.

## Review Checklist

- `RuntimeActorAddress` is the only JSON address projection.
- `RuntimeActorProfile` exposes `actor_address` but no runtime fact fields.
- Daemon registry owns presence facts and writes `actor_address`.
- Message send writes durable data before notification work.
- Message notification status cannot roll back durable message creation.
- Online event contains only references, not message body.
- No target instance JSON parsing was added to message routing.
- No generic routing engine, event bus, plugin registry, or compatibility wrapper was added.
