# Daemon Message Async Routing Test Plan

> Superseded for implementation by
> `docs/spec/2026-06-02-daemon-trigger-handler-action-rebuild-test-plan.md`.
> Do not use this file as source of truth for the daemon trigger-handler-action rebuild.

Date: 2026-06-02
Source memo: `docs/memo/2026-06-02-daemon-message-async-routing-task.md`
Resource warning: `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`

## Goal

Prove that the actor instance daemon routes `message.available` through local runtime state:

- parent idle: submit the existing parent message TUI prompt;
- parent running: start or reuse a daemon-owned side triage thread;
- side requires parent: validate the side request, interrupt the active parent turn, then submit the parent message TUI prompt;
- central daemon remains reachability-only;
- daemon core remains business-neutral and records neutral runtime action facts.

The old unconditional parent `submit_turn` path is not a compatibility path. It is replaced by explicit parent and side actions.

## Resource Safety Rules

Do not start broad service-launching suites until the focused helper tests pass and residual resources are checked.

Default verification uses pure unit tests, fake app-server clients, temporary files, and fake socket servers. Tests that start a persistent daemon, app-server, browser, broker, or fake Codex process must include process registration, teardown on failure, force-kill fallback, socket cleanup, and a residual check before being added to broad verification.

## Functional Test Matrix

### Parent Activity

File: `tests/test_daemon_service_contract.py`

- `ActionGateway.parent_activity()` returns `{"status": "idle", "active_turn_id": None}` when `thread/read` reports idle.
- It returns `{"status": "running", "active_turn_id": "turn-main-1"}` when the parent thread is active and `active_turn_id()` finds an in-progress turn.
- It returns `{"status": "unavailable", "error": "..."} or raises a typed launcher error` when app-server state cannot be read.
- It never calls central daemon APIs.

### Parent Actions

File: `tests/test_daemon_service_contract.py`

- `submit_parent_prompt()` delegates to launcher submit helper with the parent thread id and `buddyswitch-runtime` permissions.
- `interrupt_parent()` delegates to app-server interrupt for the parent thread and records the interrupted turn id.
- `interrupt_and_submit_parent_prompt()` interrupts first, then submits once, records both action facts, and returns both ids.
- If interrupt fails because the parent is already idle, the action records failure and does not hide the failure as business success.
- If interrupt succeeds but submit fails, the interrupted turn id and submit error are both persisted.
- If submit succeeds without a returned turn id, the action fails and records an error action without adding a daemon-origin turn id.
- No parent action clears, pauses, sets, or otherwise mutates the parent thread goal.

### Neutral Action Records

File: `tests/test_daemon_service_contract.py`

- Daemon state stores action records with handler name, origin id, action type, parent thread id, side thread id when present, turn id or interrupted turn id when present, status, error, created_at, and updated_at.
- Handler status `last_action_turn_id` continues to work for parent prompt submissions.
- Legacy daemon-origin turn records still answer `is_daemon_origin_turn_from()` for task checkout regression behavior, but new behavior is recorded through neutral action records.

### Side Registry Helper

File: `tests/test_side_thread_registry.py`

- Register writes an open side row for actor id, parent thread id, side thread id, and timestamps.
- Register replaces an existing row with the same side thread id instead of duplicating it.
- Validate accepts an open side row for the same actor and parent.
- Validate rejects an unknown side thread.
- Validate rejects the parent/main thread id as a side thread.
- Validate rejects a row whose parent thread id belongs to a different parent.
- Find reusable returns the first open side thread for the parent.
- Unregister removes only the matching side row and preserves unrelated side rows.
- Invalid or missing instance JSON fails before mutating files.

### Side Actions

File: `tests/test_daemon_service_contract.py`

- `start_side_triage()` starts a side thread via `app_server.side_start`, registers it through the helper, records `side_start`, and returns side thread id and turn id.
- `send_side_triage()` validates side ownership before calling `app_server.input_turn`, records `side_send`, and never mutates the parent thread.
- `close_side_triage()` validates side ownership, calls `app_server.side_close`, unregisters the side, records `side_close`, and never interrupts the parent.
- `start_or_reuse_side_triage()` reuses an open side thread for the parent when one exists, otherwise starts and registers a new side thread.
- Side actions preserve workspace roots, `buddyswitch-runtime` permissions, ephemeral side fork behavior, and the side boundary prompt by delegating to existing app-server primitives.

### Message Handler Routing

File: `tests/test_message_available_handler.py`

- Non-message signals are ignored.
- Signals for another actor are rejected.
- Missing or invalid `message_id` is rejected.
- Parent idle calls `parent_activity()`, renders the parent message TUI prompt, and calls `submit_parent_prompt()`.
- Parent running calls `parent_activity()`, renders a side triage prompt, and calls `start_or_reuse_side_triage()`.
- Parent unavailable records handler failure; it does not silently submit to parent or central daemon.
- Side triage prompt instructs the side turn to use native `message__list`, `message__conversation`, and `message__send`.
- Parent prompt does not leak message content or embed fallback CLI instructions.
- The message handler does not directly call `app_server.interrupt_turn`, `submit_turn.submit_turn`, or side registry mutation helpers.

### Typed Parent-Required Request

Files: `tests/test_daemon_mailbox.py`, `tests/test_message_available_handler.py`

- A narrow local mailbox method or signal accepts a parent-required request with actor address, parent thread id, side thread id, message id, and reason text.
- The daemon validates that the target actor is local.
- It rejects wrong actor, wrong parent thread, unknown side thread, and parent thread id used as side thread id.
- A valid request asks the message handler for the parent prompt and performs `interrupt_and_submit_parent_prompt()`.
- The request response includes handling status, interrupted turn id when available, and parent action turn id when submit succeeds.
- The request is not delivered through central daemon as a normal self-message.
- No implementation parses natural-language side output to detect escalation.

### Boundary Tests

Files: `tests/test_daemon_core_decoupling.py`, `tests/test_daemon_mailbox.py`, `tests/test_central_daemon_service.py`, `tests/test_message_available_handler.py`

- `daemon_core.py` does not import message domain modules or task domain modules.
- `central_daemon_core.py` does not import `app_server`, `daemon_core`, message handler code, or any thread activity helper.
- `daemon_mailbox.py` remains generic for signal delivery; typed parent-required support is local and narrow.
- `message_available_handler.py` owns `message.available` payload validation and prompt text.
- Message module does not call launcher parent interrupt directly.
- `message.send` offline target behavior remains delivery failure plus cleanup.

### Integration-Style Tests Without Real Service Explosion

Prefer fake app-server state and fake socket tests:

- Parent idle `message.available` produces one parent prompt action.
- Parent running `message.available` produces one side triage action.
- Existing open side thread receives follow-up input instead of a new fork.
- Side parent-required request interrupts parent then submits parent prompt in that order.
- Side triage tool availability is verified through the side runtime permission profile or fake Codex turn metadata without starting a broad service suite.

Run any real service integration only after the lifecycle checklist in `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md` is satisfied.

## Verification Commands

Focused loop:

```bash
python3 -m pytest tests/test_side_thread_registry.py -q
python3 -m pytest tests/test_daemon_service_contract.py -q
python3 -m pytest tests/test_message_available_handler.py -q
python3 -m pytest tests/test_daemon_mailbox.py -q
python3 -m pytest tests/test_daemon_core_decoupling.py -q
python3 -m pytest tests/test_central_daemon_service.py -q
```

Broader non-service regression:

```bash
python3 -m pytest tests/test_submit_turn.py tests/test_app_server_client.py tests/test_message_env_tool.py -q
```

Resource residual check before and after any service-starting test group:

```bash
pgrep -fl 'buddyswitch|app-server|runtime_broker|fake_codex|chrome' || true
find /tmp -maxdepth 1 -type s -name 'buddyswitch-*' -print
```

## Phase 1 Self-Review

- The matrix starts from functional behavior and ownership boundaries, not from implementation shortcuts.
- It covers idle, running, unavailable, side reuse, side escalation, action records, boundary imports, and delivery failure.
- It avoids broad real-service runs until lifecycle cleanup is proven.
- It explicitly rejects transition paths: no old unconditional parent submit, no central thread activity, no natural-language escalation parsing, no generic event bus.
