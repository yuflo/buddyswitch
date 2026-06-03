# Daemon Runtime Handler Rebuild Task

Date: 2026-06-03
Status: confirmed implementation memo

## 1. Task

Rebuild the daemon as a simple business-neutral runtime coordinator:

```text
daemon ingress -> DaemonTrigger -> registered handler -> optional daemon runtime
```

This is one direct replacement task. Do not keep old names, aliases, wrappers, or dual paths for compatibility.

The daemon task is not to add a larger platform. It is to remove the current daemon-layer residue:

- mailbox ingress has business-specific local trigger validation;
- handler dispatch still passes an `actions` object;
- daemon runtime capability is named and tested as `ActionGateway`;
- daemon state/status still records `daemon_actions`;
- related tests protect the old vocabulary and old mailbox special case.

## 2. Final Concepts

Keep only these daemon concepts:

```text
DaemonTrigger
registered handler
DaemonRuntime
```

### `DaemonTrigger`

The normalized input object passed to handlers.

It carries:

- `source`
- `type`
- `target_actor_address`
- `origin_id`
- `correlation_id`
- `payload`
- `source_context`

Daemon may validate the generic trigger envelope. Daemon must not validate business payload semantics.

### Registered Handler

A handler is business-owned code registered by the daemon entrypoint.

Add a lightweight handler interface for clarity:

```text
DaemonHandler
  name: str
  handles(trigger) -> bool
  handle(context, state, runtime, trigger) -> HandlerResult
```

Prefer a `typing.Protocol` or equivalent small interface in daemon core. The interface documents the contract and supports
tests/type hints, but handlers should not be forced to inherit from a base class.

Dispatch may remain duck-typed:

```text
getattr(handler, "handles")
getattr(handler, "handle")
```

Do not add an abstract framework or plugin system.

### `DaemonRuntime`

`DaemonRuntime` is the daemon instance capability object injected into handlers.

It is not a business action layer. It is a plain runtime helper object. Handlers may ignore it.

Current runtime methods:

```text
runtime.parent_activity()
runtime.submit_parent_prompt(...)
runtime.submit_side_triage_prompt(...)
```

Private implementation helpers may remain private:

```text
_interrupt_parent(...)
_start_side_triage(...)
_send_side_triage(...)
_close_side_triage(...)
```

## 3. Explicit Removals

Remove these daemon-layer concepts and names:

```text
ActionGateway
actions parameter in daemon handler dispatch
actions_factory
record_daemon_action
daemon_action_ids
daemon_actions
action_id
action_type
last_action_turn_id
_action_status_payload
daemon status field: actions
```

Do not keep aliases such as:

```text
ActionGateway = DaemonRuntime
actions = runtime
daemon_actions fallback
status["actions"] fallback
```

Old daemon state fields should be dropped during state normalization. This is cleanup, not compatibility.

## 4. Runtime Record Shape

Runtime calls still need provenance for debugging and verification, but not under an action abstraction.

Use runtime call vocabulary:

```text
daemon_runtime_call_ids
daemon_runtime_calls
runtime_call_id
runtime_method
last_runtime_turn_id
status["runtime"]
```

Suggested record:

```text
{
  "runtime_call_id": "daemon-runtime-call-1",
  "handler_name": "message_available",
  "origin_id": "msg-1",
  "runtime_method": "side_start",
  "parent_thread_id": "thr-main",
  "side_thread_id": "thr-side-1",
  "turn_id": "turn-side-1",
  "interrupted_turn_id": null,
  "status": "succeeded",
  "error": null,
  "created_at": "...",
  "updated_at": "..."
}
```

Allowed `status`:

```text
succeeded
failed
```

Runtime method names can stay concrete:

```text
parent_activity
parent_submit
parent_interrupt
side_start
side_send
side_close
```

Do not introduce a generic operation/action taxonomy.

## 5. Module Changes

### `tools/launcher/daemon_core.py`

Required changes:

- rename `ActionGateway` to `DaemonRuntime`;
- add a lightweight `DaemonHandler` interface, preferably as a `Protocol`;
- rename dispatch parameter `actions` to `runtime`;
- call handlers as `handle(context, state, runtime, trigger)`;
- create `DaemonRuntime(...)` in notification and mailbox dispatch paths;
- remove `actions_factory`;
- rename `record_daemon_action(...)` to `record_runtime_call(...)`;
- rename daemon state fields from action vocabulary to runtime call vocabulary;
- rename `_action_status_payload(...)` to `_runtime_status_payload(...)`;
- expose status as `status["runtime"]`, not `status["actions"]`;
- rename handler state field `last_action_turn_id` to `last_runtime_turn_id`;
- drop old action fields during `DaemonState.load(...)`.

Do not add trigger-type branches in daemon core.

### `tools/launcher/daemon_mailbox.py`

Required changes:

- keep `mailbox.deliver`;
- keep `mailbox.local_trigger`;
- remove `actions_factory` constructor parameter;
- remove side registry validation from mailbox ingress;
- remove business trigger type checks from mailbox ingress;
- remove mailbox dependency on `side_thread_registry` if it becomes unused;
- make `_validate_local_trigger_request(...)` generic or rename it to `_normalize_local_trigger_request(...)`.

`mailbox.local_trigger` validates only:

- `actor_address` is a valid actor address and matches the local actor;
- `type` is a non-empty string;
- `payload` is an object;
- `origin_id`, when provided, is a non-empty string;
- `correlation_id`, when provided, is a non-empty string;
- `source_context`, when provided, is an object.

`source_context` should default to `{}` when omitted.

It must not require or validate:

- `message_id`;
- `reason`;
- `parent_thread_id`;
- `side_thread_id`;
- side ownership;
- any business trigger type.

Wrong actor remains `wrong_target_actor`. Invalid generic shape remains `invalid_local_trigger`.

### `tools/launcher/daemon_triggers.py`

Required changes:

- keep `DaemonTrigger`;
- keep normalization helpers generic;
- ensure `normalize_local_trigger(...)` accepts arbitrary trigger types and generic payload/source context;
- do not add business-specific constructors.

### `tools/launcher/instance_daemon.py`

Required changes:

- keep static handler registration;
- do not introduce plugin loading, subscription registration, or dynamic routing.

### `tools/launcher/task_checkout_handler.py`

Required changes:

- update handler signature to `handle(context, state, runtime, trigger)`;
- update helper signatures from `actions` to `runtime`;
- call `runtime.submit_parent_prompt(...)`;
- keep task business logic inside this handler.

### `tools/launcher/message_available_handler.py`

Required changes:

- update handler signature to `handle(context, state, runtime, trigger)`;
- update helper signatures from `actions` to `runtime`;
- call `runtime.parent_activity()`;
- call `runtime.submit_parent_prompt(...)`;
- call `runtime.submit_side_triage_prompt(...)`;
- keep message business logic inside this handler.

Current daemon-facing residue in this handler must also be removed or rewritten:

- `side_triage_prompt(...)` must not instruct side threads to rely on daemon mailbox business-specific validation;
- handler tests must not protect `mailbox.local_trigger(type="message.parent_required")` as a daemon contract;
- if a message-specific local trigger remains in this business handler, it must validate its own business payload and
  source context without relying on mailbox-injected `message_id`, `reason`, `parent_thread_id`, or `side_thread_id`.

This daemon task does not implement the final message module processing model. Until that model is implemented, do not
preserve the old parent-required path as daemon compatibility. Either remove it from the current message handler surface
or rewrite it so it is purely business-handler-owned and uses only generic local trigger input.

## 6. Current Dependents And Required Adjustments

This section is the dependency checklist for the implementation plan. Every row must be addressed directly; no old/new
dual path should remain.

### Task Checkout Business

Files:

```text
tools/launcher/task_checkout_handler.py
tests/test_task_checkout_handler.py
```

Current dependency:

- consumes `app_server.turn_completed`;
- calls `actions.submit_parent_prompt(...)`;
- tests use `FakeActionGateway` and `ActionGateway`.

Required adjustment:

- use `runtime.submit_parent_prompt(...)`;
- rename fake to `FakeDaemonRuntime`;
- assert `last_runtime_turn_id` where handler status is checked;
- keep task checkout trigger/business behavior unchanged.

### Message Available Business

Files:

```text
tools/launcher/message_available_handler.py
tests/test_message_available_handler.py
```

Current dependency:

- consumes `message.available`;
- calls `actions.parent_activity()`;
- calls `actions.submit_parent_prompt(...)`;
- calls `actions.submit_side_triage_prompt(...)`;
- still references `message.parent_required` and mailbox-local trigger behavior.

Required adjustment:

- use `runtime.*`;
- rename fake to `FakeDaemonRuntime`;
- keep `message.available` handling through registered handler dispatch;
- remove tests that treat `message.parent_required` as daemon mailbox behavior;
- remove or rewrite side prompt text that exposes old daemon-local trigger semantics;
- do not implement final message disposition work in this daemon task.

### Message Send And Runtime Tool Delivery

Files:

```text
scripts/env/tool_runtime/context.py
scripts/env/tools/message/_impl.py
scripts/env/tools/message/tool.py
tests/test_message_env_tool.py
tests/test_runtime_actor_profile.py
```

Current dependency:

- `message.send` checks target reachability through `DaemonAccess`;
- creates a durable inbox message;
- sends `message.available` through `DaemonAccess.deliver_message_available(...)`;
- delivery reaches the target daemon through central daemon `signal.deliver -> mailbox.deliver`.

Required adjustment:

- no daemon runtime rename should leak into env tool action vocabulary;
- keep cross-actor `message.available` signal shape unchanged;
- keep unreachable-target cleanup behavior unchanged;
- keep message env tests proving only the generic signal envelope is delivered.

This is a verification dependency, not a reason to keep daemon action compatibility.

### Central Daemon Delivery

Files:

```text
tools/launcher/central_daemon.py
tools/launcher/central_daemon_core.py
scripts/env/tool_runtime/daemon_client.py
tests/test_central_daemon_service.py
tests/test_daemon_mailbox.py
tests/test_daemon_communication_boundary.py
```

Current dependency:

- central daemon tracks actor reachability;
- central daemon validates generic daemon signal envelope;
- central daemon forwards signals to target instance mailbox with `mailbox.deliver`;
- daemon client owns socket request envelopes.

Required adjustment:

- keep `mailbox.deliver` protocol stable;
- keep central daemon reachability behavior stable;
- update only tests that inspect mailbox local trigger behavior or daemon runtime/status vocabulary;
- do not add central daemon awareness of parent activity, handlers, runtime calls, or message semantics.

### Instance Daemon Entrypoint

Files:

```text
tools/launcher/instance_daemon.py
tests/test_instance_daemon_entrypoint.py
```

Current dependency:

- imports default business handlers;
- passes handler list to daemon core for run/start/status.

Required adjustment:

- keep static registration;
- no plugin loader;
- no subscription registration;
- ensure registered handlers satisfy `DaemonHandler` contract.

### Daemon Shell / Status Consumers

Files:

```text
tools/launcher/daemon.sh
tools/launcher/assets/web-management/*
tests/test_daemon_core.py
tests/test_daemon_service_contract.py
```

Current dependency:

- daemon CLI/status returns status JSON;
- tests currently expect `status["actions"]`;
- web management source does not currently read daemon action records directly.

Required adjustment:

- status JSON exposes `runtime`, not `actions`;
- tests must assert `runtime` records;
- no old `actions` status field remains;
- verify web management has no daemon `actions` data dependency before treating CSS/UI class names as residue.

### Side Thread Registry

Files:

```text
tools/launcher/side_thread_registry.py
tools/launcher/env.sh
tests/test_side_thread_registry.py
```

Current dependency:

- daemon runtime uses side registry for side start/reuse/send/close;
- mailbox currently uses side registry for local trigger validation.

Required adjustment:

- keep side registry usage inside `DaemonRuntime` side-thread methods;
- remove side registry usage from daemon mailbox local trigger ingress;
- keep env.sh side registry helper functions if runtime still uses them elsewhere;
- do not remove side registry itself as part of this daemon cleanup.

## 7. Tests To Rewrite Or Add

### Daemon Runtime Naming

Update daemon service/core tests to assert:

- `DaemonHandler` interface exists and documents `handles` / `handle`;
- `DaemonRuntime` exists;
- `ActionGateway` does not exist;
- handlers receive a `DaemonRuntime` instance;
- handler signatures and test fakes use `runtime`, not `actions`;
- `dispatch_trigger(...)` parameter is `runtime`;
- `dispatch_notification(...)` injects `DaemonRuntime`.

### Runtime Records

Update state/status tests to assert:

- initial state has `daemon_runtime_call_ids` and `daemon_runtime_calls`;
- initial state does not have `daemon_action_ids` or `daemon_actions`;
- `record_runtime_call(...)` writes `runtime_call_id` and `runtime_method`;
- status payload uses `runtime`, not `actions`;
- handler state uses `last_runtime_turn_id`, not `last_action_turn_id`;
- stale daemon action fields are dropped when loading state.

### Local Trigger Ingress

Update mailbox tests to assert:

- `mailbox.local_trigger` accepts arbitrary type such as `example.attention_needed`;
- payload passes through unchanged;
- source context passes through unchanged;
- `origin_id` and `correlation_id` pass through when provided;
- wrong actor is rejected before dispatch;
- empty/non-string type is rejected;
- non-object payload is rejected;
- non-object source context is rejected;
- `message_id`, `reason`, `parent_thread_id`, `side_thread_id` are not required;
- `message.parent_required` is not hardcoded in mailbox source or mailbox tests;
- `side_thread_registry.require_side_thread` is not called from mailbox ingress.

### Handler Contract

Update task/message handler tests to use fake runtime objects.

Required assertions:

- task checkout still submits parent prompt through runtime;
- message available with idle parent submits parent prompt through runtime;
- message available with running parent submits side triage prompt through runtime;
- runtime failure is reported as handler failure;
- handler tests no longer mention `FakeActionGateway`.

### Boundary Tests

Update decoupling tests to assert:

- daemon core does not import business domain modules;
- daemon mailbox does not hardcode business trigger strings;
- daemon core does not branch on business trigger types;
- no daemon-layer source contains `ActionGateway`;
- no daemon-layer source contains `record_daemon_action`;
- no daemon-layer status test expects `actions`.

Scope the source audit to daemon-related files and tests. Do not treat unrelated env tool `actions` vocabulary or web UI
CSS class names as daemon architecture residue.

### Delivery Regression Tests

Keep or add tests proving:

- `message.send` still delivers `message.available` through `DaemonAccess`;
- central daemon still forwards `mailbox.deliver` to target daemon mailbox;
- target-not-online and delivery-failed cleanup paths still work;
- `daemon.sh status` still returns valid JSON after status changes;
- instance daemon still registers task and message handlers.

## 8. Implementation Order

Use this order to avoid partial old/new shapes:

1. Update tests for the final contract.
2. Rename daemon runtime concepts in `daemon_core.py`.
3. Rewrite daemon state/runtime record vocabulary.
4. Generalize `mailbox.local_trigger`.
5. Update task/message handlers to receive `runtime`.
6. Update launcher/daemon integration tests and source boundary tests.
7. Run focused verification.
8. Run broader launcher verification.

Do not land a state where `ActionGateway` and `DaemonRuntime` coexist.

## 9. Verification Commands

Focused:

```bash
python3 -m pytest tests/test_daemon_core.py -q
python3 -m pytest tests/test_daemon_service_contract.py -q
python3 -m pytest tests/test_daemon_mailbox.py -q
python3 -m pytest tests/test_daemon_trigger_router.py -q
python3 -m pytest tests/test_daemon_core_decoupling.py -q
python3 -m pytest tests/test_task_checkout_handler.py -q
python3 -m pytest tests/test_message_available_handler.py -q
python3 -m pytest tests/test_instance_daemon_entrypoint.py -q
python3 -m pytest tests/test_central_daemon_service.py -q
python3 -m pytest tests/test_message_env_tool.py -q
python3 -m pytest tests/test_runtime_actor_profile.py -q
```

Broader launcher validation:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -q
python3 -m pytest --collect-only -q tests
git diff --check
```

Source audits:

```bash
rg -n 'ActionGateway|FakeActionGateway|actions_factory|record_daemon_action|daemon_actions|daemon_action_ids|last_action_turn_id|_action_status_payload' tools/launcher tests/test_daemon*.py tests/test_task_checkout_handler.py tests/test_message_available_handler.py
rg -n 'message\.parent_required|require_side_thread' tools/launcher/daemon_mailbox.py tests/test_daemon_mailbox.py tests/test_daemon_core_decoupling.py
rg -n 'mailbox\.local_trigger\(type="message\.parent_required"|FakeActionGateway' tools/launcher/message_available_handler.py tests/test_message_available_handler.py
```

Expected result for source audits:

- no daemon-layer `ActionGateway` residue;
- no daemon mailbox business trigger hardcoding;
- no daemon mailbox side ownership validation.
- no message handler prompt/test residue that treats old parent-required local trigger as daemon contract.

## 10. Non-Goals

Do not implement the new message processing/disposition model in this daemon task.

Do not add:

- event bus;
- subscription system;
- plugin router;
- workflow engine;
- handler framework;
- generic action system;
- compatibility aliases;
- old/new status dual output.

## 11. Done Criteria

The task is done only when:

- daemon ingress is business-neutral;
- local triggers are generic typed triggers;
- daemon dispatch calls registered handlers through the `runtime` contract;
- `ActionGateway` and daemon action vocabulary are removed from daemon code/tests/status;
- every daemon-dependent business or related module listed in this memo has been adjusted or verified unaffected;
- existing task checkout behavior still works;
- existing message available behavior still works through runtime injection;
- existing message send delivery behavior still works through `mailbox.deliver`;
- central daemon reachability and signal delivery behavior still works;
- focused daemon and handler tests pass;
- broader launcher validation passes;
- source audits show no daemon-layer residue.
