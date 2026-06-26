# Browser Page TTL Lifecycle Fix Plan

Date: 2026-06-26

## Goal

Fix the BuddySwitch browser page idle TTL lifecycle without changing actor browser tool browsing behavior.

The browser page TTL mechanism remains a resource-governance feature: pages that are no longer active should be closed after the configured idle window, while pages protected by the existing current-page rule must not be closed by stale or internally inconsistent schedules.

## Scope

This task is limited to the current 300-second browser page TTL implementation.

In scope:

- Preserve the existing default idle TTL of 300 seconds.
- Fix the schedule reset bug where a protected current page refreshes the same keyed schedule and the daemon sweep then marks that refreshed schedule `delivered`.
- Prevent old due triggers from closing a page whose `page_idle.json` `last_used_at` shows it has already been refreshed.
- Add file-lock protection around `page_idle.json` read/modify/write updates to avoid concurrent lost updates.
- Add focused regression tests for the TTL behavior above.

Out of scope:

- Do not enable `--experimentalPageIdRouting`.
- Do not modify Codex.
- Do not change Chrome DevTools MCP schemas.
- Do not make `current page` equivalent to "actor is using this page".
- Do not force actor browser tool calls to provide `pageId`.
- Do not change `new_page`, `select_page`, `take_snapshot`, `click`, `navigate_page`, or `evaluate_script` browsing semantics.

## Current Findings

### 300-Second TTL

The TTL is currently 300 seconds via `BROWSER_PAGE_IDLE_SECONDS = 300`.

`refresh_page_idle()` schedules a `browser.page.expired` trigger with:

- `delay_seconds=idle_seconds`
- `schedule_key=browser.page.idle:<target_id>`
- payload `{"target_id": <target_id>}`

This value and the keyed schedule model should remain unchanged.

### Current-Page Protection Schedule Bug

When a due schedule fires, `BrowserPageExpiredHandler` checks whether the target is the current page and whether the parent turn is running.

If both are true, the handler calls `refresh_current_page_idle()` and returns handled. That refresh uses the same schedule key, so `DaemonState.upsert_schedule()` updates the same pending schedule row with a future `due_at`.

The bug is in the daemon sweep after the handler returns: it still calls `mark_schedule_delivered(schedule_id)` on the originally swept `schedule_id`. If the handler refreshed that same row, the future schedule is immediately changed to `status=delivered`, so it will never fire again.

Expected behavior: a handler that refreshes the same schedule row must leave the refreshed row pending.

### Stale Due Trigger Risk

A schedule can be selected for sweep, then the page can be used and refreshed before the handler closes it. The handler currently validates only:

- target id
- current-page identity
- parent turn status

It does not compare the trigger's `due_at` with the latest target `last_used_at` in `page_idle.json`.

Expected behavior: before closing a page, the handler should treat a trigger as stale when the current target state shows `last_used_at + 300s > trigger.due_at`. A stale trigger must not close or forget that target.

### `page_idle.json` Lost Update Risk

`refresh_page_idle()`, `mark_current_page()`, and `forget_page_idle_target()` currently read the full `page_idle.json`, mutate it, and atomically replace the file.

Atomic replace prevents partial writes, but it does not prevent two concurrent read/modify/write operations from overwriting each other's changes.

Expected behavior: page idle state read/modify/write operations should hold an exclusive browser page-idle lock for the whole state mutation.

## Test Plan

Use focused tests only; do not run the whole repository suite for this task.

### 1. Daemon Sweep Preserves Refreshed Pending Schedules

File: `tests/test_daemon_trigger_router.py`

Add a test where:

- A keyed `browser.page.expired` schedule is due.
- The handler simulates current-page protection by calling `state.upsert_schedule()` for the same `schedule_key`.
- The handler returns handled.

Expected result:

- `swept_count == 1`
- `delivered_count == 0`
- `failed_count == 0`
- The same `schedule_id` remains `status=pending`
- The row has the refreshed future `due_at`
- A second sweep before the refreshed `due_at` does not dispatch it again

This test should fail before the fix because the row is currently marked `delivered`.

### 2. Browser Expiry Handler Ignores Stale Due Triggers

File: `tests/test_browser_page_expired_handler.py`

Add a test where:

- `page_idle.json` contains target `target-idle-1` with `last_used_at` later than the trigger's effective scheduled generation.
- The trigger source context has `due_at=2026-06-24T00:05:00Z`.
- The target's latest `last_used_at` is `2026-06-24T00:04:30Z`, so the latest expiry is `2026-06-24T00:09:30Z`.
- The parent runtime is idle and the target is not protected as current.

Expected result:

- The handler returns handled.
- `close_page_target()` is not called.
- `forget_page_idle_target()` is not called.
- The target remains in `page_idle.json`.

This test should fail before the fix because the handler currently closes the target.

### 3. Page Idle State Updates Use an Exclusive Lock

File: `tests/test_cdp_browser_session.py`

Add a focused lock test where:

- The test process holds the page idle lock file.
- A subprocess attempts to call `mark_current_page()` for the same instance root.
- The subprocess must still be running while the lock is held.
- After the lock is released, the subprocess completes and the state file is updated.

This test should fail before the fix because `mark_current_page()` currently does not wait on a page-idle lock.

### 4. Existing Focused Regression Suite

After implementation, run:

```bash
python3 -m pytest \
  tests/test_cdp_browser_session.py \
  tests/test_browser_page_expired_handler.py \
  tests/test_daemon_trigger_router.py \
  tests/test_daemon_mailbox.py
```

Run `tests/test_browser_cockpit_proxy.py` only if the implementation touches proxy-facing lifecycle behavior. The planned implementation should not touch that path.

## Implementation Plan

### Step 1: Preserve Refreshed Schedule Rows in Daemon Sweep

Modify `tools/launcher/daemon_core.py`.

Add a schedule snapshot comparison before marking a swept schedule as terminal.

The sweep should mark a schedule `delivered` or `failed` only when the current schedule row still matches the due row that was dispatched. At minimum compare:

- `schedule_id`
- `status`
- `type`
- `payload`
- `source_context`
- `due_at`
- `updated_at`
- `schedule_key`

If the row changed during handler execution, append the current row to the sweep result and leave counts as non-terminal for that schedule.

### Step 2: Add Stale Trigger Validation to Browser Expiry

Modify `scripts/env/cdp_browser_lifecycle.py` and `tools/launcher/browser_page_expired_handler.py`.

Add a lifecycle helper that checks whether a target's current `last_used_at` implies an expiry later than the trigger's `due_at`.

Use this helper in `BrowserPageExpiredHandler._handle_expiry()` before `_auto_close()`.

If the trigger is stale, return handled without closing or forgetting the target.

### Step 3: Lock Page Idle State Mutations

Modify `scripts/env/cdp_browser_lifecycle.py`.

Add an exclusive lock file under:

```text
<instance_root>/runtime/browser/page_idle.lock
```

Hold the lock across each read/modify/write mutation in:

- `refresh_page_idle()`
- `mark_current_page()`
- `forget_page_idle_target()`

Read-only helpers may keep using plain reads unless later evidence shows they need stronger consistency.

### Step 4: Verify Focused Tests

Run the focused suite from the test plan.

Expected result: all selected tests pass, including the new regression tests.

## Acceptance Criteria

- Default browser page TTL remains 300 seconds.
- A current page protected by a running parent turn gets a future pending schedule, not a delivered schedule.
- A stale due trigger cannot close a target whose latest `last_used_at` shows it has been refreshed.
- `page_idle.json` write mutations are protected by an exclusive lock.
- No actor browser tool behavior is changed.
- Focused regression tests pass.
