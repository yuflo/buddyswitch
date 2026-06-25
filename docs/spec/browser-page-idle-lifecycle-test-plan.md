# Browser Page Idle Lifecycle Test Plan

Date: 2026-06-25

## Goal

Verify that launcher-managed browser pages use an internal 300 second idle lifecycle:

- opening or reusing a page refreshes that page's idle schedule;
- successful page-scoped cockpit actions refresh the current page's idle schedule;
- repeated use replaces the pending idle schedule for the same target instead of appending schedules;
- expiry closes unused pages, but protects the current page while the actor's main turn is still running;
- daemon-service stays generic and stores only opaque keyed schedules;
- browser lifecycle state is stored under `runtime/browser/page_idle.json`, not product objects, private workspace, or browser-specific daemon fields.

This replaces the old TTL/expiry-policy model. There is no actor-facing TTL parameter, no notify policy, no accumulated extension, and no maximum TTL cap.

## Resource Lifecycle Constraint

Follow `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.

Most tests for this change must use in-process fakes, temporary directories, and short-lived HTTP servers with explicit shutdown. Do not start broad launcher instances until focused tests prove cleanup. After any test command that can start services, inspect for residual test-owned processes before broad verification.

## Functional Test Coverage

### Browser Lifecycle Unit Behavior

File: `tests/test_cdp_browser_session.py`

Required tests:

- `touch_page_idle` writes `runtime/browser/page_idle.json` with current target, target mapping, and `last_used_at`.
- `touch_page_idle` schedules `browser.page.expired` after 300 seconds with `schedule_key` equal to `browser.page.idle:<target_id>`.
- repeated `touch_page_idle` for the same target upserts the same keyed schedule instead of creating a second pending schedule.
- `set_current_page` records the current CDP `target_id` and optional upstream `pageId` mapping without treating `pageId` as a CDP target id.
- invalid or blank `target_id` is rejected before daemon scheduling.

### Generic Daemon Schedule Upsert

Files:

- `tests/test_daemon_trigger_router.py`
- `tests/test_daemon_mailbox.py`

Required tests:

- `DaemonState.upsert_schedule` creates a pending schedule when no pending row has the provided `schedule_key`.
- `DaemonState.upsert_schedule` updates due time, payload, and source context on the existing pending row when the key matches.
- delivered, failed, and canceled rows with the same key are not reused.
- mailbox `mailbox.schedule_trigger` accepts optional `schedule_key` and routes it to the generic scheduler.
- daemon client `schedule_trigger` accepts optional `schedule_key` and posts it to the mailbox.
- persisted daemon state contains generic `schedule_key` on schedule rows, but no browser-specific top-level state fields.

### Search Tool Behavior

File: `tests/test_search_env_tool.py`

Required tests:

- `search.open_browser` for a newly opened page calls `touch_page_idle` with 300 second semantics and returns internal idle metadata without exposing policy controls.
- `search.open_browser` when reusing an exact URL also refreshes idle state for the reused target.
- idle refresh failure is reported in the tool result without rolling back an already-opened browser page.
- results do not contain old `expiry_policy`, `ttl_seconds`, `ttl_registered`, or schedule identifiers.

### Chrome DevTools Cockpit Proxy Behavior

File: `tests/test_browser_cockpit_proxy.py`

Required tests:

- `new_page` registers idle state after exactly one new CDP page target is observed.
- `new_page` exact-URL reuse refreshes idle state for the reused target.
- `select_page` successful response refreshes idle state for the selected page by resolving upstream `pageId` to CDP `target_id`.
- page-scoped successful cockpit calls refresh the current page idle state.
- `list_pages`, `tools/list`, blocked focus calls, `close_page`, and failed tool responses do not count as page use.
- user-facing proxy text says browser page idle was refreshed/opened, not "TTL".

### Browser Expiry Handler

File: `tests/test_browser_page_expired_handler.py`

Required tests:

- expiry payload requires only `target_id`.
- if the expired target is current and `runtime.parent_activity()` reports a running main turn, the handler refreshes idle and does not close the page.
- if the actor is idle, the handler closes the target.
- if the target is not current, the handler closes the target even if the actor is active.
- already-gone or stale browser errors are handled.
- notify policy is absent.

## Verification Commands

Focused loop:

```bash
python -m unittest \
  tests.test_cdp_browser_session \
  tests.test_daemon_trigger_router \
  tests.test_daemon_mailbox \
  tests.test_search_env_tool \
  tests.test_browser_cockpit_proxy \
  tests.test_browser_page_expired_handler
```

Broad Python suite after focused cleanup is proven:

```bash
python -m unittest discover tests
```

JavaScript UI checks, because they are part of the repo test surface:

```bash
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Resource residual check after broad verification:

```bash
ps -axo pid,ppid,pgid,command | rg 'buddyswitch|fake_codex|chrome-devtools|runtime_broker|app_server' || true
```

Treat this command as an inspection step. Expected result is no unexplained residual process owned by the test run.
