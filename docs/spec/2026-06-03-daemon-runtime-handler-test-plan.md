# Daemon Runtime Handler Rebuild Test Plan

Date: 2026-06-03
Source memo: `docs/memo/2026-06-03-daemon-runtime-handler-rebuild-task.md`

## Goal

Prove the daemon is rebuilt as:

```text
daemon ingress -> DaemonTrigger -> registered handler -> optional DaemonRuntime
```

The tests must prove behavior from the product requirements, not preserve the old `ActionGateway` or mailbox business-special-case implementation.

## Resource Safety

Most focused daemon tests are in-process and may be run repeatedly. Before running broad launcher tests that can start persistent services, follow `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`:

1. Prefer focused in-process tests first.
2. Do not run broad service-starting suites until focused behavior is green.
3. After any broad launcher run, check for leftover daemon/app-server/browser/broker processes before claiming completion.
4. Treat resource leakage as a test failure, even when assertions pass.

## Focused Test Matrix

### Daemon Core Contract

Files:

- `tests/test_daemon_core.py`
- `tests/test_daemon_service_contract.py`
- `tests/test_daemon_trigger_router.py`

Required coverage:

- `DaemonHandler` exists as a lightweight protocol with `name`, `handles(trigger)`, and `handle(context, state, runtime, trigger)`.
- `DaemonRuntime` exists and `ActionGateway` does not exist.
- `dispatch_trigger` accepts `runtime`, not `actions`, and passes the same runtime object to handlers.
- `dispatch_notification` injects a `DaemonRuntime`.
- `start_daemon_mailbox` builds a mailbox without `actions_factory`.
- Handler failures, invalid returns, and exceptions still update handler state and continue dispatching later handlers.

### Runtime State And Status

Files:

- `tests/test_daemon_core.py`
- `tests/test_daemon_service_contract.py`

Required coverage:

- Missing state initializes `daemon_runtime_call_ids` and `daemon_runtime_calls`.
- Missing state does not initialize `daemon_action_ids` or `daemon_actions`.
- Loading state drops stale `daemon_action_ids`, `daemon_actions`, and stale handler `last_action_turn_id`.
- `record_runtime_call(...)` records `runtime_call_id`, `runtime_method`, `handler_name`, `origin_id`, thread ids, turn ids, status, timestamps, and errors.
- Runtime call status accepts only `succeeded` and `failed`.
- `daemon_status(... )["runtime"]` exposes runtime call records.
- `daemon_status(... )` does not expose `actions`.
- Handler status uses `last_runtime_turn_id`, not `last_action_turn_id`.

### DaemonRuntime Behavior

Files:

- `tests/test_daemon_service_contract.py`
- `tests/test_task_checkout_handler.py`
- `tests/test_message_available_handler.py`

Required coverage:

- `submit_parent_prompt(interrupt_policy="none")` submits to the main thread, records a `parent_submit` runtime call, records daemon turn provenance, and updates `last_runtime_turn_id`.
- `submit_parent_prompt(interrupt_policy="before_submit")` records `parent_interrupt` and `parent_submit`.
- Submit or interrupt failures record failed runtime calls and do not record daemon-origin turn ids for missing turns.
- `parent_activity()` returns idle, running, or unavailable from the app-server helpers.
- `submit_side_triage_prompt(...)` starts a new side thread or reuses an open one, records `side_start` or `side_send`, and keeps side registry usage inside runtime only.
- The public runtime handler-facing surface is exactly `parent_activity`, `submit_parent_prompt`, and `submit_side_triage_prompt`.

### Mailbox Ingress

Files:

- `tests/test_daemon_mailbox.py`
- `tests/test_daemon_core_decoupling.py`

Required coverage:

- `mailbox.deliver` and generic cross-actor signal delivery remain unchanged.
- `mailbox.local_trigger` accepts arbitrary non-empty trigger types such as `example.attention_needed`.
- Local trigger payload passes through unchanged and must be an object.
- Local trigger `source_context` passes through unchanged, defaults to `{}`, and must be an object when provided.
- `origin_id` and `correlation_id` pass through when provided and must be non-empty strings when provided.
- Wrong actor returns `wrong_target_actor`.
- Invalid generic shape returns `invalid_local_trigger`.
- `message_id`, `reason`, `parent_thread_id`, and `side_thread_id` are not required by mailbox ingress.
- `daemon_mailbox.py` does not hardcode `message.parent_required`.
- `daemon_mailbox.py` does not call `side_thread_registry.require_side_thread`.

### Business Handlers

Files:

- `tests/test_task_checkout_handler.py`
- `tests/test_message_available_handler.py`

Required coverage:

- Task checkout still handles only completed main-thread user turns and ignores daemon-origin task checkout turns.
- Task checkout submits parent prompt through `runtime.submit_parent_prompt`.
- Task checkout tests use `FakeDaemonRuntime`.
- Message available still validates target actor and `message_id`.
- Idle parent submits parent prompt through runtime.
- Running parent submits side triage prompt through runtime.
- Runtime failure is returned as handler failure.
- Message available side prompt no longer instructs side threads to rely on daemon mailbox `message.parent_required`.
- Message handler tests do not keep `FakeActionGateway`.

### Delivery And Entrypoint Regression

Files:

- `tests/test_message_env_tool.py`
- `tests/test_runtime_actor_profile.py`
- `tests/test_central_daemon_service.py`
- `tests/test_daemon_communication_boundary.py`
- `tests/test_instance_daemon_entrypoint.py`

Required coverage:

- `message.send` still writes the durable inbox message and delivers generic `message.available`.
- Delivery failure and target-not-online cleanup behavior remain stable.
- Central daemon remains reachability-only and forwards `mailbox.deliver`.
- Instance daemon keeps static task/message handler registration and does not add plugin loading.

## Verification Commands

Run focused tests first:

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

Run source audits:

```bash
rg -n 'ActionGateway|FakeActionGateway|actions_factory|record_daemon_action|daemon_actions|daemon_action_ids|last_action_turn_id|_action_status_payload' tools/launcher tests/test_daemon*.py tests/test_task_checkout_handler.py tests/test_message_available_handler.py
rg -n 'message\.parent_required|require_side_thread' tools/launcher/daemon_mailbox.py tests/test_daemon_mailbox.py tests/test_daemon_core_decoupling.py
rg -n 'mailbox\.local_trigger\(type="message\.parent_required"|FakeActionGateway' tools/launcher/message_available_handler.py tests/test_message_available_handler.py
```

Run broader validation only after focused tests and audits pass:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -q
python3 -m pytest --collect-only -q tests
git diff --check
```

If broad validation starts persistent services, record the pre-run and post-run process state and confirm no owned residual services remain.

