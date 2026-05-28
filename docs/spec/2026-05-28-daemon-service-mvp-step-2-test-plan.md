# Daemon Service MVP Step 2 Test Plan

Date: 2026-05-28

## Objective

Verify that daemon advances from "daemon core with Task Checkout Handler" to a small, stable Daemon Service MVP:

1. daemon core exposes a concrete handler contract;
2. handlers use a daemon-owned action gateway instead of raw app-server `turn/start` request assembly;
3. handler state stays namespaced and status-visible;
4. handler failures are isolated from daemon health and other handlers;
5. Task Checkout Handler becomes the first standard handler without changing product behavior;
6. launcher bootstrap and input Task TUI remain outside daemon.

This is not a plugin-system task. Tests must prove a standard in-process service contract, not dynamic loading or configuration.

## Current Code Facts

- `tools/launcher/daemon_core.py` owns daemon lifecycle, state, app-server bind, notification loop, and explicit handler dispatch.
- `tools/launcher/task_checkout_handler.py` owns STOP Task TUI filtering/render/send behavior, but still calls `client.request("turn/start", ...)` directly and returns `bool`.
- `tools/launcher/instance_daemon.py` wires `[TaskCheckoutHandler()]` for `run`.
- `daemon_status(...)` reports daemon liveness/readiness paths and top-level last error, but not registered handler health.
- Existing state has `handlers.task_checkout.*`, but Task Checkout uses `last_checkout_turn_id` rather than the service-wide `last_action_turn_id`.
- Launcher bootstrap remains in `tools/launcher/app_server.py` / shell launcher via `thread/inject_items`.
- Input Task TUI remains in `tools/launcher/task_input_context.py` and app-server `input` command.

## Functional Requirements

FR1. Daemon core must define a concrete handler contract result with explicit statuses: `ignored`, `handled`, and `failed`.

FR2. Daemon dispatch must call handlers in explicit list order and pass `DaemonContext`, `DaemonState`, daemon action gateway, and the raw notification.

FR3. Daemon dispatch must continue to later handlers when one handler returns `failed` or raises.

FR4. Handler exceptions and handler-declared failures must be recorded under `handlers.<handler_name>.last_error`; they must not mark top-level daemon `last_error` as fatal.

FR5. Top-level daemon `last_error` is reserved for fatal daemon/app-server/bind/runtime errors.

FR6. Daemon core must expose an `ActionGateway` with `turn_start(text, handler_name, origin_turn_id)` that:

- uses current main thread id;
- uses daemon permissions;
- builds app-server text input payload;
- calls exactly one app-server `turn/start`;
- extracts returned turn id from real app-server response shapes;
- records the returned id as daemon-origin;
- writes `handlers.<handler_name>.last_action_turn_id`;
- exposes app-server/protocol errors by raising `app_server.AppServerError`.

FR7. Handler state namespace must support service-standard fields:

- `registered`;
- `enabled`;
- `active`;
- `last_result`;
- `last_handled_at`;
- `last_origin_turn_id`;
- `last_action_turn_id`;
- `last_error`.

FR8. `daemon_status(...)` must include handler observability for registered handlers and persisted handler state.

FR9. `instance status --json` must expose daemon handler status under `daemon.handlers`.

FR10. Human `instance status` must keep existing daemon health output and add concise handler visibility without changing command shape.

FR11. Task Checkout Handler must use the service contract and `ActionGateway`; it must not assemble raw `turn/start` payloads itself.

FR12. Task Checkout Handler behavior remains unchanged:

- completed user-origin main-thread turn triggers one STOP Task TUI prompt;
- daemon-origin turn does not loop;
- other-thread/malformed/non-completed notifications are ignored;
- input Task TUI does not route through daemon.

FR13. Daemon core remains business-neutral:

- no `task_management` / `task_tui` imports;
- no message business imports or message handler implementation;
- no plugin registry, dynamic handler config, event bus, or workflow engine.

FR14. Launcher start/clear bootstrap remains launcher-owned and still happens before daemon `thread/resume`.

## Required Automated Tests

### 1. Daemon Service Contract Tests

File: `tests/test_daemon_service_contract.py`

Cases:

- `test_handler_result_has_explicit_statuses`
  - Assert `HandlerResult.ignored().status == "ignored"`, `HandlerResult.handled().status == "handled"`, and `HandlerResult.failed("boom").status == "failed"`.
  - Assert failed result carries the error message.

- `test_dispatch_passes_context_state_actions_and_notification`
  - Use a fake handler with signature `handle_notification(context, state, actions, notification)`.
  - Assert it receives an `ActionGateway` instance, not the raw app-server client.
  - Assert dispatch returns `True` when handler returns `HandlerResult.handled()`.

- `test_dispatch_records_declared_failure_under_handler_state_and_continues`
  - First handler returns `HandlerResult.failed("declared failure")`.
  - Second handler returns `HandlerResult.handled()`.
  - Assert both handlers are called for the same notification.
  - Assert state has `handlers.first.last_error.message == "declared failure"` and top-level `last_error is None`.

- `test_dispatch_records_exception_under_handler_state_and_continues`
  - First handler raises `RuntimeError("handler exploded")`.
  - Second handler returns handled.
  - Assert state has `handlers.exploder.last_error.message == "handler exploded"` and top-level `last_error is None`.

### 2. Action Gateway Tests

File: `tests/test_daemon_service_contract.py`

Cases:

- `test_action_gateway_turn_start_uses_main_thread_permissions_and_text_payload`
  - Call `actions.turn_start("prompt", handler_name="fake", origin_turn_id="turn-user-1")`.
  - Assert fake client receives one `turn/start` with current thread id, `buddyswitch-runtime` permissions, and `app_server.text_input_payload(...)` shape.

- `test_action_gateway_records_daemon_origin_and_handler_action_state`
  - Fake `turn/start` returns `{"turn": {"id": "turn-daemon-1"}}`.
  - Assert `daemon_origin_turn_ids == ["turn-daemon-1"]`.
  - Assert `handlers.fake.last_origin_turn_id == "turn-user-1"` and `handlers.fake.last_action_turn_id == "turn-daemon-1"`.

- `test_action_gateway_raises_protocol_error_when_turn_id_missing`
  - Fake `turn/start` returns `{"turn": {}}`.
  - Assert `AppServerProtocolError` is raised.
  - Assert no daemon-origin id is recorded.

- `test_action_gateway_exposes_request_error_without_retry_or_steer`
  - Fake client raises `AppServerRequestError("turn/start", ...)`.
  - Assert the same error class is raised.
  - Assert client methods contain only `turn/start`.

### 3. Handler State And Status Tests

File: `tests/test_daemon_core.py`

Cases:

- `test_handler_registration_state_initializes_observability_fields`
  - Register handler names `["task_checkout", "fake"]`.
  - Assert each handler state has `registered: true`, `enabled: true`, `active: true`, `last_result: null`, and `last_error: null`.

- `test_daemon_status_reports_registered_handler_observability`
  - Call `daemon_status(instance_json, handlers=[FakeHandler("task_checkout")])`.
  - Assert `payload["handlers"]["registered"] == ["task_checkout"]`.
  - Assert `payload["handlers"]["items"]["task_checkout"]` includes active/enabled and last action/error fields.

- `test_daemon_status_includes_persisted_unregistered_handler_state`
  - Persist `handlers.message.last_error`.
  - Call status with only Task Checkout registered.
  - Assert status still shows `message` with `registered: false`.

- `test_top_level_last_error_is_fatal_only_for_app_server_failures`
  - Handler failure does not set top-level `last_error`.
  - Fatal `AppServerUnavailableError` still sets top-level `last_error`.

### 4. Task Checkout Handler Standard-Contract Tests

File: `tests/test_task_checkout_handler.py`

Cases:

- `test_handler_returns_ignored_result_for_ignored_notifications`
  - Other-thread, malformed, daemon-origin, and non-completed notifications return `ignored`.

- `test_accepted_completed_turn_uses_action_gateway`
  - Pass a fake action gateway.
  - Assert handler calls `actions.turn_start(...)` exactly once.
  - Assert handler returns `handled`.
  - Assert prompt starts with `[TASK CHECKOUT]` and does not contain `[TASK CONTEXT]` or `[USER INPUT]`.

- `test_action_failure_returns_failed_result_without_retry_or_steer`
  - Fake action gateway raises `AppServerRequestError`.
  - Assert handler returns `failed`.
  - Assert no retry and no `turn/steer`.

- `test_task_checkout_state_uses_standard_action_field`
  - Through real `ActionGateway`, accepted turn records `handlers.task_checkout.last_action_turn_id`.
  - Assert no new `last_checkout_turn_id` compatibility mirror is written.

### 5. Entrypoint Wiring Tests

File: `tests/test_instance_daemon_entrypoint.py`

Cases:

- `test_run_passes_default_task_checkout_handler_to_daemon_core`
  - Keep existing run wiring coverage.

- `test_status_passes_default_handlers_to_daemon_status`
  - Patch `daemon_core.daemon_status`.
  - Assert `instance_daemon.py status` passes `[TaskCheckoutHandler()]`.

- `test_start_passes_default_handlers_to_start_status_payload`
  - Patch `daemon_core.start_daemon`.
  - Assert start path passes default handlers so returned status includes registered handler observability.

### 6. Launcher Regression Tests

File: `tests/test_buddyswitch_launcher.py`

Cases:

- `test_start_with_buddy_status_reports_task_checkout_handler`
  - After `instance start`, call `instance status --json`.
  - Assert `daemon.handlers.registered` contains `task_checkout`.
  - Assert `daemon.handlers.items.task_checkout.enabled` and `active` are true.

- `test_human_status_reports_daemon_handler_line`
  - Assert human status still includes `Daemon health:` and adds `Daemon handlers: task_checkout`.

- Existing bootstrap regression tests must remain green:
  - start/clear bootstrap calls `thread/inject_items` before daemon `thread/resume`;
  - bootstrap failure leaves no ready daemon.

- Existing fake Codex daemon tests must remain green:
  - real completed event triggers one STOP Task TUI prompt;
  - daemon-origin completion does not loop;
  - other-thread completion is ignored.

- Existing input regression tests must remain green:
  - `instance input` uses `turn/start` or `turn/steer` according to thread status;
  - daemon checkout code never calls `compose_task_context_input(...)`.

## Coverage Matrix

| Requirement | Test Groups |
| --- | --- |
| FR1 | 1 |
| FR2 | 1 |
| FR3 | 1, 3 |
| FR4 | 1, 3 |
| FR5 | 3 |
| FR6 | 2, 4 |
| FR7 | 3, 4 |
| FR8 | 3 |
| FR9 | 6 |
| FR10 | 6 |
| FR11 | 4 |
| FR12 | 4, 6 |
| FR13 | 1, existing `tests/test_daemon_core_decoupling.py` |
| FR14 | 6, existing app-server bootstrap tests |

## Verification Commands

Focused contract and handler tests:

```bash
python3 -m pytest tests/test_daemon_service_contract.py tests/test_daemon_core.py tests/test_task_checkout_handler.py tests/test_instance_daemon_entrypoint.py -q
```

Launcher/app-server/input regression:

```bash
python3 -m pytest tests/test_app_server_client.py tests/test_task_input_context.py tests/test_buddyswitch_launcher.py -q
```

Final related verification:

```bash
python3 -m pytest tests/test_daemon_service_contract.py tests/test_daemon_core_decoupling.py tests/test_daemon_core.py tests/test_task_checkout_handler.py tests/test_instance_daemon_entrypoint.py tests/test_app_server_client.py tests/test_task_input_context.py tests/test_buddyswitch_launcher.py -q
```

## Plan Review

- The plan tests daemon service capability directly with fake handlers, not only Task Checkout behavior.
- It keeps message as persisted example state only; it does not implement message business behavior.
- It preserves launcher bootstrap and input Task TUI regression coverage.
- It avoids plugin registry, event bus, workflow engine, and dynamic handler config.
