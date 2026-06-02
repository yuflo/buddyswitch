# Daemon Trigger-Handler-Action Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild daemon dispatch to `trigger -> handler -> action`, clean the handler-facing action surface, and
migrate current task/message business supports without preserving old split dispatch methods.

**Architecture:** Add one concrete `DaemonTrigger` type and one trigger router. Ingress adapters normalize app-server
notifications, cross-actor mailbox signals, and local mailbox triggers before dispatch. Business handlers handle typed
triggers and call only `ActionGateway` runtime actions.

**Tech Stack:** Python launcher modules, pytest/unittest tests, fake app-server helpers, temporary instance JSON files,
UNIX socket mailbox tests.

---

## Source Of Truth And Current State

Authoritative memos:

- `docs/memo/2026-06-02-daemon-trigger-handler-action-dispatch-rebuild.md`
- `docs/memo/2026-06-02-daemon-api-surface-cleanup-task.md`
- `docs/memo/2026-06-02-trigger-handler-action-business-adjustments-task.md`

Do not implement from `docs/memo/2026-06-02-daemon-message-async-routing-task.md`.

Current code facts from this worktree:

- `tools/launcher/daemon_core.py` still dispatches app-server notifications through `handle_notification(...)`.
- `tools/launcher/daemon_mailbox.py` still dispatches cross-actor signals through `handle_signal(...)`.
- `tools/launcher/daemon_mailbox.py` still exposes business-specific `mailbox.parent_required`.
- `tools/launcher/message_available_handler.py` still exposes `handle_signal(...)` and `handle_parent_required(...)`.
- `tools/launcher/task_checkout_handler.py` still exposes `handle_notification(...)`.
- `ActionGateway` already has partial parent/side primitives, but still exposes old handler-facing
  `interrupt_and_submit_parent_prompt`, `start_or_reuse_side_triage`, and `require_side_thread`.
- `tools/launcher/side_thread_registry.py` exists and should be reused for local-trigger side ownership validation.

## File Responsibilities

- Create `tools/launcher/daemon_triggers.py`: `DaemonTrigger` data shape and source-specific normalization helpers.
- Modify `tools/launcher/daemon_core.py`: `TriggerRouter`, app-server notification adapter, unified daemon registration,
  clean `ActionGateway` public surface, status payload cleanup.
- Modify `tools/launcher/daemon_mailbox.py`: keep `mailbox.deliver`, replace `mailbox.parent_required` with
  `mailbox.local_trigger`, validate local side ownership before dispatch, call injected trigger dispatcher.
- Modify `tools/launcher/task_checkout_handler.py`: migrate task checkout business logic to `handles(trigger)` /
  `handle(...)` while preserving TUI behavior.
- Modify `tools/launcher/message_available_handler.py`: migrate message available and parent-required business logic to
  trigger handling and cleaned actions.
- Modify `tools/launcher/instance_daemon.py`: register one daemon handler list containing task checkout and message
  handler.
- Modify tests listed in `docs/spec/2026-06-02-daemon-trigger-handler-action-rebuild-test-plan.md`.

## Task 1: Add DaemonTrigger And Router Tests

**Files:**
- Create: `tools/launcher/daemon_triggers.py`
- Create: `tests/test_daemon_trigger_router.py`
- Modify: `tools/launcher/daemon_core.py`

- [ ] Write failing tests in `tests/test_daemon_trigger_router.py` for:
  - `DaemonTrigger` field preservation;
  - app-server `turn/completed` normalization;
  - cross-actor signal normalization;
  - router dispatch through `handles(trigger)` and `handle(...)`;
  - router result counts and handler state recording;
  - source scan rejecting `handle_notification`, `handle_signal`, and `handle_parent_required` in router code.
- [ ] Run:

```bash
python3 -m pytest tests/test_daemon_trigger_router.py -q
```

Expected before implementation: failures for missing `daemon_triggers` and trigger router APIs.

- [ ] Implement `tools/launcher/daemon_triggers.py` with:
  - `DaemonTrigger`;
  - `APP_SERVER_NOTIFICATION`, `MAILBOX_CROSS_ACTOR_SIGNAL`, `MAILBOX_LOCAL_TRIGGER`;
  - `normalize_app_server_notification(...)`;
  - `normalize_cross_actor_signal(...)`;
  - `normalize_local_trigger(...)`.
- [ ] Implement `TriggerRouter` and `dispatch_trigger(...)` in `tools/launcher/daemon_core.py`.
- [ ] Rerun:

```bash
python3 -m pytest tests/test_daemon_trigger_router.py -q
```

Expected after implementation: pass.

## Task 2: Replace Mailbox Parent-Required With Local Trigger

**Files:**
- Modify: `tools/launcher/daemon_mailbox.py`
- Modify: `tests/test_daemon_mailbox.py`
- Modify: `tests/test_daemon_communication_boundary.py`

- [ ] Rewrite mailbox tests so `mailbox.local_trigger` is the only local typed ingress.
- [ ] Add tests proving `mailbox.parent_required` returns `mailbox_unknown_method`.
- [ ] Add tests proving wrong actor, wrong parent, unknown side, parent-as-side, missing payload, missing message id, and
  missing reason are rejected before handlers are called.
- [ ] Run:

```bash
python3 -m pytest tests/test_daemon_mailbox.py tests/test_daemon_communication_boundary.py -q
```

Expected before implementation: failures because `mailbox.local_trigger` is missing and `mailbox.parent_required`
still exists.

- [ ] Change `DaemonMailboxServer.dispatch(...)`:
  - keep `mailbox.deliver`;
  - add `mailbox.local_trigger`;
  - remove `_validate_parent_required_request(...)` and `_dispatch_parent_required(...)`;
  - call the injected trigger dispatcher for both mailbox ingress methods.
- [ ] Use `side_thread_registry.require_side_thread(...)` inside local-trigger validation for
  `type="message.parent_required"` before dispatch.
- [ ] Rerun:

```bash
python3 -m pytest tests/test_daemon_mailbox.py tests/test_daemon_communication_boundary.py -q
```

Expected after implementation: pass.

## Task 3: Clean ActionGateway Handler-Facing Surface

**Files:**
- Modify: `tools/launcher/daemon_core.py`
- Modify: `tests/test_daemon_service_contract.py`

- [ ] Write failing tests for:
  - `submit_parent_prompt(..., interrupt_policy="none")`;
  - `submit_parent_prompt(..., interrupt_policy="before_submit")`;
  - invalid interrupt policy rejection;
  - interrupt failure prevents submit;
  - submit failure after interrupt records both action facts;
  - `submit_side_triage_prompt(...)` starts a side thread when no reusable side exists;
  - `submit_side_triage_prompt(...)` sends to an existing side thread when reusable.
- [ ] Add source-boundary assertions that business handlers do not call:
  - `interrupt_and_submit_parent_prompt`;
  - `start_or_reuse_side_triage`;
  - `require_side_thread`.
- [ ] Run:

```bash
python3 -m pytest tests/test_daemon_service_contract.py -q
```

Expected before implementation: failures for old method names and missing interrupt-policy behavior.

- [ ] Update `ActionGateway.submit_parent_prompt(...)` to accept required keyword
  `interrupt_policy: Literal["none", "before_submit"] = "none"`.
- [ ] Move parent interrupt, side start/send/close, and side validation to daemon-internal helper methods.
- [ ] Add `submit_side_triage_prompt(...)` as the only handler-facing side triage action.
- [ ] Remove handler-facing `interrupt_and_submit_parent_prompt`, `start_or_reuse_side_triage`, and
  `require_side_thread`.
- [ ] Rerun:

```bash
python3 -m pytest tests/test_daemon_service_contract.py -q
```

Expected after implementation: pass.

## Task 4: Migrate Task Checkout Handler To Triggers

**Files:**
- Modify: `tools/launcher/task_checkout_handler.py`
- Modify: `tests/test_task_checkout_handler.py`

- [ ] Rewrite task checkout tests to construct `DaemonTrigger(type="app_server.turn_completed")`.
- [ ] Preserve tests for completed main-thread turn, side-thread ignored, non-completed statuses ignored, missing fields
  ignored, daemon-origin task checkout turn ignored, and non-task daemon-origin turns accepted.
- [ ] Update prompt submission assertions to require:

```text
actions.submit_parent_prompt(prompt, handler_name="task_checkout", origin_id=<turn_id>, interrupt_policy="none")
```

- [ ] Run:

```bash
python3 -m pytest tests/test_task_checkout_handler.py -q
```

Expected before implementation: failures because the handler still uses `handle_notification(...)`.

- [ ] Replace `handle_notification(...)` with:
  - `handles(trigger)`;
  - `handle(context, state, actions, trigger)`.
- [ ] Make filtering read normalized trigger fields and source context, not raw app-server method names.
- [ ] Keep task checkout TUI rendering unchanged.
- [ ] Rerun:

```bash
python3 -m pytest tests/test_task_checkout_handler.py -q
```

Expected after implementation: pass.

## Task 5: Migrate Message Handler To Triggers

**Files:**
- Modify: `tools/launcher/message_available_handler.py`
- Modify: `tests/test_message_available_handler.py`

- [ ] Rewrite message tests to construct `DaemonTrigger` values for `message.available` and `message.parent_required`.
- [ ] Add assertions that side triage prompt contains the triggering message id and local-trigger escalation wording.
- [ ] Add assertions that parent-required handling uses
  `submit_parent_prompt(..., interrupt_policy="before_submit")`.
- [ ] Add source assertions that the handler has no `handle_signal`, no `handle_parent_required`, no
  `actions.require_side_thread`, and no old action names.
- [ ] Run:

```bash
python3 -m pytest tests/test_message_available_handler.py -q
```

Expected before implementation: failures because the handler still uses split entry methods and old action names.

- [ ] Replace `handle_signal(...)` and `handle_parent_required(...)` with:
  - `handles(trigger)`;
  - `handle(context, state, actions, trigger)`;
  - private helpers for message available and parent-required business cases.
- [ ] Bind `message_id` into side triage prompt and pass it as `origin_id` for parent and side actions.
- [ ] Rerun:

```bash
python3 -m pytest tests/test_message_available_handler.py -q
```

Expected after implementation: pass.

## Task 6: Unify Daemon Registration And Dispatch

**Files:**
- Modify: `tools/launcher/daemon_core.py`
- Modify: `tools/launcher/instance_daemon.py`
- Modify: `tests/test_instance_daemon_entrypoint.py`
- Modify: `tests/test_daemon_core.py`

- [ ] Rewrite entrypoint/status tests to expect one daemon handler list with `TaskCheckoutHandler` and
  `MessageAvailableHandler`.
- [ ] Add tests proving app-server notifications normalize to `DaemonTrigger` and dispatch through the same router used
  by mailbox triggers.
- [ ] Run:

```bash
python3 -m pytest tests/test_instance_daemon_entrypoint.py tests/test_daemon_core.py -q
```

Expected before implementation: failures because `mailbox_handlers` is still split.

- [ ] Replace `default_handlers()` / `default_mailbox_handlers()` with one `default_daemon_handlers()`.
- [ ] Update `run_daemon(...)`, `start_daemon_mailbox(...)`, `daemon_status(...)`, and `dispatch_notification(...)` to
  use one handler list and trigger dispatch.
- [ ] Remove business handler registration split from status output.
- [ ] Rerun:

```bash
python3 -m pytest tests/test_instance_daemon_entrypoint.py tests/test_daemon_core.py -q
```

Expected after implementation: pass.

## Task 7: Boundary Sweep And Legacy Removal

**Files:**
- Modify: `tests/test_daemon_core_decoupling.py`
- Modify: `tests/test_daemon_communication_boundary.py`
- Modify production files only if boundary tests expose remaining old surfaces.

- [ ] Add source assertions:

```bash
rg 'mailbox\.parent_required|handle_notification|handle_signal|handle_parent_required|interrupt_and_submit_parent_prompt|start_or_reuse_side_triage|require_side_thread\\(' tools/launcher tests
```

The only allowed matches should be negative assertions in tests/spec docs.

- [ ] Run:

```bash
python3 -m pytest tests/test_daemon_core_decoupling.py tests/test_daemon_communication_boundary.py tests/test_central_daemon_service.py -q
```

Expected before cleanup: failures if any old dispatch or business-specific mailbox surface remains.

- [ ] Remove remaining old method names, stale compatibility tests, and stale status assertions.
- [ ] Rerun the same command.

Expected after cleanup: pass.

## Task 8: Focused Regression And Resource Audit

**Files:**
- No production changes unless verification exposes a root cause.

- [ ] Run focused verification:

```bash
python3 -m pytest tests/test_daemon_trigger_router.py -q
python3 -m pytest tests/test_message_available_handler.py -q
python3 -m pytest tests/test_task_checkout_handler.py -q
python3 -m pytest tests/test_daemon_mailbox.py -q
python3 -m pytest tests/test_daemon_service_contract.py -q
python3 -m pytest tests/test_instance_daemon_entrypoint.py tests/test_daemon_core.py -q
python3 -m pytest tests/test_daemon_core_decoupling.py tests/test_daemon_communication_boundary.py tests/test_central_daemon_service.py -q
```

- [ ] Run broader non-service regression:

```bash
python3 -m pytest tests/test_side_thread_registry.py tests/test_submit_turn.py tests/test_app_server_client.py tests/test_message_env_tool.py tests/test_task_input_context.py -q
```

- [ ] Run residual resource checks:

```bash
pgrep -fl 'buddyswitch|app-server|runtime_broker|fake_codex|chrome' || true
find /tmp -maxdepth 1 -type s -name 'buddyswitch-*' -print
```

- [ ] Do not run broad service-starting suites unless the lifecycle checklist in
  `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md` is satisfied.

## Development Self-Review

- This plan implements all three authoritative memos and avoids the old async-routing memo as source of truth.
- The implementation order removes wrong boundaries directly instead of layering compatibility.
- The TDD loop starts with behavior tests from functional requirements.
- Task input TUI remains outside daemon dispatch.
- Verification is focused and resource-safe before any broader run.
