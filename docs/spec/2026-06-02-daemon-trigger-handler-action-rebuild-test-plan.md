# Daemon Trigger-Handler-Action Rebuild Test Plan

Date: 2026-06-02
Authoritative sources:
- `docs/memo/2026-06-02-daemon-trigger-handler-action-dispatch-rebuild.md`
- `docs/memo/2026-06-02-daemon-api-surface-cleanup-task.md`
- `docs/memo/2026-06-02-trigger-handler-action-business-adjustments-task.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`

Do not use `docs/memo/2026-06-02-daemon-message-async-routing-task.md` as implementation source of truth.

## Goal

Prove that daemon runtime inputs are normalized into one `DaemonTrigger` shape, dispatched through one
`handler.handles(trigger)` / `handler.handle(context, state, actions, trigger)` interface, and executed through the
clean handler-facing `ActionGateway` surface:

```text
actions.parent_activity()
actions.submit_parent_prompt(..., interrupt_policy="none" | "before_submit")
actions.submit_side_triage_prompt(...)
```

The old split surfaces are not compatibility paths. Tests must drive their removal:

```text
handle_notification
handle_signal
handle_parent_required
mailbox.parent_required
actions.interrupt_and_submit_parent_prompt
actions.start_or_reuse_side_triage
actions.require_side_thread from message handlers
```

## Resource Safety Rules

Default to pure unit tests, fake app-server helpers, temporary files, fake socket servers, and direct mailbox dispatch.

Before running any broad service-starting group, verify the lifecycle checklist from
`docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`:

- each started daemon, app-server, browser, worker, broker, watcher, or detached process is explicitly registered;
- teardown runs after assertion failure;
- pid or process-group termination escalates from graceful stop to force kill;
- pid files, sockets, markers, and temporary runtime files are cleaned;
- residual process and socket checks return to baseline.

Focused non-service tests are the primary gate for this rebuild.

## Functional Test Matrix

### DaemonTrigger Shape And Ingress Normalization

File: `tests/test_daemon_trigger_router.py`

- App-server `turn/completed` notifications normalize to:
  - `source="app_server_notification"`;
  - `type="app_server.turn_completed"`;
  - `target_actor_address` equal to the local daemon actor;
  - `origin_id` equal to the completed turn id;
  - `payload` containing the raw notification params needed by task checkout;
  - `source_context` containing raw method, thread id, turn id, and turn status.
- Cross-actor `mailbox.deliver` with a valid daemon signal normalizes to:
  - `source="mailbox_cross_actor_signal"`;
  - `type` equal to the signal type, such as `message.available`;
  - `target_actor_address` equal to the signal target;
  - `origin_id` equal to the signal id;
  - `payload` equal to the signal payload;
  - `source_context` containing source actor and created-at metadata.
- Local `mailbox.local_trigger` with `type="message.parent_required"` normalizes to:
  - `source="mailbox_local_trigger"`;
  - `type="message.parent_required"`;
  - `target_actor_address` equal to the local daemon actor;
  - `origin_id` equal to the triggering `message_id`;
  - `payload={"message_id": ..., "reason": ...}`;
  - `source_context` containing parent thread id and side thread id.
- Unknown trigger types are still valid `DaemonTrigger` values and are ignored by handlers that do not handle them.
- Missing required trigger fields are rejected before handler dispatch.

### Trigger Router

File: `tests/test_daemon_trigger_router.py`

- The router calls only `handler.handles(trigger)` and `handler.handle(context, state, actions, trigger)`.
- It records `matched_count`, `handled_count`, `handling_status`, and handler errors for every ingress source.
- It records handler state for handled and failed results with `origin_id` from the trigger.
- It treats invalid handler return values as handler failures.
- It does not inspect business payload fields such as `message_id`.
- Source inspection proves router code has no calls to `handle_notification`, `handle_signal`, or `handle_parent_required`.

### Unified Daemon Registration

Files: `tests/test_instance_daemon_entrypoint.py`, `tests/test_daemon_core.py`

- The instance daemon registers one daemon handler list containing `TaskCheckoutHandler` and `MessageAvailableHandler`.
- Runtime status exposes one handler registration surface; there is no split `mailbox_handlers` surface for business
  handlers.
- App-server notifications and mailbox triggers both dispatch through the same router.

### Task Input TUI

Files: `tests/test_task_input_context.py`, existing task input wrapper tests

- Task input TUI remains a launcher input wrapper, not a daemon trigger handler.
- Existing task input wrapper composition and rendered content remain behavior-equivalent.
- No daemon registration includes task input TUI.

### Task Checkout Handler

File: `tests/test_task_checkout_handler.py`

- `TaskCheckoutHandler.handles(trigger)` returns true only for `DaemonTrigger(type="app_server.turn_completed")`.
- Non-completed turns, side-thread turns, missing turn fields, and daemon-origin task checkout turns are ignored.
- The handler reads normalized trigger `payload` and `source_context`; it does not parse raw app-server notifications.
- Accepted turns render existing task checkout TUI with unchanged content.
- Accepted turns call `actions.submit_parent_prompt(..., handler_name="task_checkout", origin_id=<turn_id>, interrupt_policy="none")`.
- Source inspection proves `TaskCheckoutHandler` has no `handle_notification` method and no `import app_server`.

### Message Handler: `message.available`

File: `tests/test_message_available_handler.py`

- `MessageAvailableHandler.handles(trigger)` handles `message.available`.
- Wrong target actor is rejected before parent activity or prompt submission.
- Missing or invalid `payload.message_id` is rejected.
- Parent idle:
  - calls `actions.parent_activity()`;
  - renders parent message TUI;
  - calls `actions.submit_parent_prompt(..., interrupt_policy="none")`;
  - passes the message id as `origin_id`.
- Parent running:
  - calls `actions.parent_activity()`;
  - renders side triage prompt;
  - calls `actions.submit_side_triage_prompt(...)`;
  - passes the message id as `origin_id`;
  - side triage prompt carries the triggering `message_id`;
  - side triage prompt instructs escalation through
    `mailbox.local_trigger(type="message.parent_required", payload={message_id, reason})`.
- Parent unavailable records handler failure and does not submit to parent or side.
- Parent prompt and side triage prompt do not embed message body content or fallback CLI instructions.

### Message Handler: `message.parent_required`

Files: `tests/test_message_available_handler.py`, `tests/test_daemon_mailbox.py`

- `MessageAvailableHandler.handles(trigger)` handles `message.parent_required`.
- Side ownership validation is performed by local-trigger ingress before handler business logic.
- Handler business logic validates `payload.message_id` and treats `payload.reason` as context only.
- Handler renders existing parent message TUI and calls
  `actions.submit_parent_prompt(..., interrupt_policy="before_submit")`.
- The result includes handled status, side thread id from `source_context`, interrupted turn id when present, and parent
  turn id when submit succeeds.
- Source inspection proves the message handler has no calls to `actions.require_side_thread`,
  `actions.interrupt_and_submit_parent_prompt`, launcher parent interrupt helpers, or side registry mutation helpers.

### Clean ActionGateway Surface

File: `tests/test_daemon_service_contract.py`

- `parent_activity()` reports idle, running with active turn id, and unavailable from local app-server state only.
- `submit_parent_prompt(..., interrupt_policy="none")` submits once to the parent thread and records a `parent_submit`
  action.
- `submit_parent_prompt(..., interrupt_policy="before_submit")` interrupts the parent first, then submits once, and
  records the parent interrupt and parent submit action facts in order.
- Invalid interrupt policies are rejected.
- If interrupt fails, submit is not attempted and the failure is recorded.
- If submit fails after a successful interrupt, the interrupt action remains recorded and the submit failure is recorded.
- `submit_side_triage_prompt(...)` reuses an open side thread for the parent when one exists; otherwise it starts and
  registers a side thread.
- Side send/start actions preserve workspace roots, `buddyswitch-runtime` permissions, and parent thread immutability.
- Handler-facing source inspection proves only these public calls are used by business handlers:
  `parent_activity`, `submit_parent_prompt`, and `submit_side_triage_prompt`.

### Local Trigger Mailbox

File: `tests/test_daemon_mailbox.py`

- `mailbox.deliver` remains the cross-actor signal ingress.
- `mailbox.local_trigger` accepts a local trigger request with:

```json
{
  "actor_address": {"role_id": "dev", "actor_id": "act-dev-daemon"},
  "type": "message.parent_required",
  "parent_thread_id": "thr-main",
  "side_thread_id": "thr-side-1",
  "payload": {"message_id": "msg-readable", "reason": "parent is required"}
}
```

- It rejects wrong actor, wrong parent thread, unknown side thread, parent thread id used as side thread id, missing
  payload, missing message id, and missing reason.
- It validates side ownership before routing; if validation fails, no handler is called.
- It dispatches a `DaemonTrigger` through the same trigger router used by `mailbox.deliver`.
- There is no `mailbox.parent_required` method.

### Boundary Tests

Files: `tests/test_daemon_core_decoupling.py`, `tests/test_daemon_communication_boundary.py`

- `daemon_core.py` does not import message domain modules or task domain modules.
- `central_daemon_core.py` does not import `app_server`, `daemon_core`, message handler code, or thread activity helpers.
- `daemon_mailbox.py` exposes generic local-trigger ingress, not business-specific mailbox methods.
- `message_available_handler.py` owns message payload validation and prompt text.
- `task_checkout_handler.py` owns task checkout business decisions and TUI rendering.
- No source file contains `mailbox.parent_required`.
- No business handler depends on raw mailbox method names.
- No generic event bus, workflow DSL, subscription router, or plugin router is added.

## Verification Commands

Focused loop:

```bash
python3 -m pytest tests/test_daemon_trigger_router.py -q
python3 -m pytest tests/test_message_available_handler.py -q
python3 -m pytest tests/test_task_checkout_handler.py -q
python3 -m pytest tests/test_daemon_mailbox.py -q
python3 -m pytest tests/test_daemon_service_contract.py -q
python3 -m pytest tests/test_instance_daemon_entrypoint.py tests/test_daemon_core.py -q
python3 -m pytest tests/test_daemon_core_decoupling.py tests/test_daemon_communication_boundary.py tests/test_central_daemon_service.py -q
```

Broader non-service regression:

```bash
python3 -m pytest tests/test_side_thread_registry.py tests/test_submit_turn.py tests/test_app_server_client.py tests/test_message_env_tool.py tests/test_task_input_context.py -q
```

Residual resource checks before and after any service-starting group:

```bash
pgrep -fl 'buddyswitch|app-server|runtime_broker|fake_codex|chrome' || true
find /tmp -maxdepth 1 -type s -name 'buddyswitch-*' -print
```

## Phase 1 Self-Review

- The matrix is derived from the three authoritative memos, not the old async-routing task.
- It covers all three stable ingress sources, unified router dispatch, clean handler-facing actions, task checkout,
  message available, message parent escalation, task input TUI preservation, and boundary constraints.
- It requires deletion of the old split entry methods and business-specific mailbox method rather than preserving them.
- It keeps broad service-starting verification out of the default path until resource lifecycle safety is proven.
