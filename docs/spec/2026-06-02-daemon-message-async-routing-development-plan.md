# Daemon Message Async Routing Development Plan

> Superseded for implementation by
> `docs/spec/2026-06-02-daemon-trigger-handler-action-rebuild-development-plan.md`.
> Do not use this file as source of truth for the daemon trigger-handler-action rebuild.

Date: 2026-06-02
Source memo: `docs/memo/2026-06-02-daemon-message-async-routing-task.md`
Test plan: `docs/spec/2026-06-02-daemon-message-async-routing-test-plan.md`

## Goal

Rebuild the daemon message path so `message.available` routes through daemon-owned local runtime actions, with side triage and typed parent escalation, without preserving the old unconditional parent submit path.

## Current Code Facts

- `tools/launcher/message_available_handler.py` currently validates `message.available` and always calls `actions.submit_turn(...)`.
- `tools/launcher/daemon_core.py` currently exposes `ActionGateway.submit_turn(...)` and stores daemon-origin turn records.
- `tools/launcher/app_server.py` already exposes parent thread read, active turn lookup, input, interrupt, side start, and side close primitives.
- `/side` registry operations currently live as inline Python in `tools/launcher/env.sh`, while CLI side orchestration lives in `buddyswitch-codex`.
- `tools/launcher/daemon_mailbox.py` currently supports generic `mailbox.deliver` only.
- `tools/launcher/central_daemon_core.py` owns actor reachability and signal delivery only.

## Target Shape

The final runtime boundary is:

```text
message handler owns payload semantics and prompts
daemon ActionGateway owns parent and side runtime control
side registry helper owns parent/side ownership validation
daemon mailbox owns local typed ingress for parent-required requests
central daemon owns online/offline reachability only
```

## Implementation Tasks

### Task 1: Add side registry helper

Create `tools/launcher/side_thread_registry.py`.

Responsibilities:

- load and validate `instance.json`;
- `register_side_thread(instance_json, actor_id, parent_thread_id, side_thread_id)`;
- `require_side_thread(instance_json, actor_id, parent_thread_id, side_thread_id)`;
- `find_open_side_thread(instance_json, actor_id, parent_thread_id)`;
- `unregister_side_thread(instance_json, actor_id, parent_thread_id, side_thread_id)`;
- atomic writes with temp file replace;
- reject empty ids and reject side thread id equal to parent thread id.

Tests:

- Create `tests/test_side_thread_registry.py`.
- Write failing tests from the side registry section of the test plan before implementation.
- Run `python3 -m pytest tests/test_side_thread_registry.py -q`.

CLI wiring:

- Replace inline Python in `buddyswitch_instance_register_side_thread`, `buddyswitch_instance_require_side_thread`, and `buddyswitch_instance_unregister_side_thread` with calls to `tools/launcher/side_thread_registry.py`.
- Keep existing CLI error messages compatible where tests already assert them.
- Run the focused `/side` launcher tests that do not need a broad suite.

### Task 2: Add neutral daemon action records

Modify `tools/launcher/daemon_core.py`.

Responsibilities:

- add `daemon_actions` and `daemon_action_ids` to state;
- add `record_daemon_action(...)` with action id generation, status, handler name, origin id, action type, parent thread id, side thread id, turn id, interrupted turn id, error, created_at, and updated_at;
- preserve existing `daemon_origin_turn_ids` compatibility for code that checks whether a turn was daemon-originated;
- expose action records in `daemon_status(...)` in a compact form if needed by existing status payload expectations.

Tests:

- Extend `tests/test_daemon_service_contract.py` with parent and side action record assertions.
- Run `python3 -m pytest tests/test_daemon_service_contract.py -q`.

### Task 3: Replace ambiguous parent submit API with explicit parent actions

Modify `ActionGateway` in `tools/launcher/daemon_core.py`.

Actions:

- `parent_activity(handler_name, origin_id=None)`;
- `submit_parent_prompt(text, handler_name, origin_id)`;
- `interrupt_parent(handler_name, origin_id)`;
- `interrupt_and_submit_parent_prompt(text, handler_name, origin_id)`.

Behavior:

- `parent_activity` reads local app-server state only.
- `submit_parent_prompt` delegates to the existing submit helper and records `parent_submit`.
- `interrupt_parent` delegates to `app_server.interrupt_turn` and records `parent_interrupt`.
- `interrupt_and_submit_parent_prompt` calls interrupt then submit in one gateway method and records composite status even if submit fails.
- Keep `submit_turn(...)` only if existing task checkout tests require it, but route it internally to `submit_parent_prompt(...)`; do not use it from the message handler.

Tests:

- Add focused tests for idle/running/unavailable parent activity.
- Add tests for submit, interrupt, interrupt-and-submit success, missing returned turn id, and interrupt success plus submit failure.
- Add a source boundary test proving parent actions do not call goal helpers.

### Task 4: Add side actions to ActionGateway

Modify `tools/launcher/daemon_core.py` and import `side_thread_registry`.

Actions:

- `start_side_triage(text, handler_name, origin_id)`;
- `send_side_triage(side_thread_id, text, handler_name, origin_id)`;
- `close_side_triage(side_thread_id, handler_name, origin_id)`;
- `start_or_reuse_side_triage(text, handler_name, origin_id)`.

Behavior:

- start uses `app_server.side_start`, then registers the returned side thread;
- send validates ownership through side registry, then calls `app_server.input_turn`;
- close validates ownership, calls `app_server.side_close`, then unregisters;
- reuse finds an open side for the current parent and sends follow-up input instead of forking.

Tests:

- Add fake-app-server tests in `tests/test_daemon_service_contract.py`.
- Run `python3 -m pytest tests/test_daemon_service_contract.py tests/test_side_thread_registry.py -q`.

### Task 5: Rebuild message.available routing

Modify `tools/launcher/message_available_handler.py`.

Behavior:

- Validate generic signal and target actor exactly as today.
- Validate `payload.message_id`.
- Call `actions.parent_activity(handler_name="message_available", origin_id=message_id)`.
- If idle, render parent prompt and call `actions.submit_parent_prompt(...)`.
- If running, render side triage prompt and call `actions.start_or_reuse_side_triage(...)`.
- If unavailable, return handler failure.
- Provide helper methods for parent prompt and side triage prompt so parent-required handling reuses the same parent prompt.
- Remove use of `actions.submit_turn(...)` from this handler.

Tests:

- Rewrite `tests/test_message_available_handler.py` fake action gateway around parent/side methods.
- Add routing tests for idle, running, unavailable, prompt content, and source boundary.
- Run `python3 -m pytest tests/test_message_available_handler.py -q`.

### Task 6: Add typed parent-required local ingress

Modify `tools/launcher/daemon_mailbox.py` and `tools/launcher/message_available_handler.py`.

Transport choice:

- Add a local mailbox method `mailbox.parent_required`.
- Keep `mailbox.deliver` generic and unchanged for normal signals.
- Do not route this request through central daemon.

Schema:

```json
{
  "actor_address": {"role_id": "dev", "actor_id": "act-dev-..."},
  "parent_thread_id": "thr-main",
  "side_thread_id": "thr-side",
  "message_id": "msg-...",
  "reason": "side determined parent attention is required"
}
```

Behavior:

- Validate local actor address.
- Validate parent thread id equals daemon context main thread id.
- Validate side thread ownership through `ActionGateway` or side registry.
- Ask `MessageAvailableHandler` to render the parent prompt.
- Call `actions.interrupt_and_submit_parent_prompt(...)`.
- Return a structured result with handling status, side thread id, interrupted turn id when present, and parent turn id when present.

Tests:

- Add mailbox dispatch tests for accepted valid request and rejected wrong actor, wrong parent, unknown side, and parent-as-side.
- Add handler tests for parent-required prompt reuse.
- Run `python3 -m pytest tests/test_daemon_mailbox.py tests/test_message_available_handler.py -q`.

### Task 7: Boundary and central daemon checks

Modify or add tests only unless a boundary violation is found.

Checks:

- `daemon_core.py` does not import message domain logic.
- `central_daemon_core.py` does not import local app-server thread activity or message handler code.
- `message_available_handler.py` does not call launcher parent interrupt or side registry directly.
- `daemon_mailbox.py` typed parent-required support remains narrow and does not become a generic event bus.

Run:

```bash
python3 -m pytest tests/test_daemon_core_decoupling.py tests/test_daemon_mailbox.py tests/test_central_daemon_service.py -q
```

### Task 8: Focused regression and resource audit

Run focused verification:

```bash
python3 -m pytest tests/test_side_thread_registry.py -q
python3 -m pytest tests/test_daemon_service_contract.py -q
python3 -m pytest tests/test_message_available_handler.py -q
python3 -m pytest tests/test_daemon_mailbox.py -q
python3 -m pytest tests/test_daemon_core_decoupling.py -q
python3 -m pytest tests/test_central_daemon_service.py -q
python3 -m pytest tests/test_submit_turn.py tests/test_app_server_client.py tests/test_message_env_tool.py -q
```

Before any broad service-starting verification, run:

```bash
pgrep -fl 'buddyswitch|app-server|runtime_broker|fake_codex|chrome' || true
find /tmp -maxdepth 1 -type s -name 'buddyswitch-*' -print
```

If focused verification passes and no residual resource problem appears, run only the minimal launcher `/side` regression slice needed for the registry replacement. Do not run the full launcher suite unless service lifecycle cleanup is confirmed.

## Development Self-Review

- The plan covers the complete memo scope: parent activity, explicit parent actions, side registry, side actions, typed parent-required request, action provenance, message routing, and boundary tests.
- The plan removes the old message submit-only path instead of layering a compatibility route.
- The daemon remains local runtime coordination; message business semantics stay in the message handler and side prompt.
- Verification is focused and resource-safe before any service-heavy checks.
