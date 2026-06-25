# Browser Page Idle Lifecycle Development Plan

Date: 2026-06-25

## Target

Replace the launcher-managed browser page TTL implementation with an internal 300 second idle lifecycle, as specified in `docs/memo/2026-06-25-browser-page-idle-lifecycle.md`.

## Current Bottleneck

Current code still uses `register_browser_page_ttl`, append-only schedules, `ttl_seconds`, and `expiry_policy`. That conflicts with the memo and can close an actively reused page because older pending schedules remain active.

## Implementation Steps

### 1. Add Generic Keyed Schedule Upsert

Files:

- `tools/launcher/daemon_core.py`
- `tools/launcher/daemon_mailbox.py`
- `scripts/env/tool_runtime/daemon_client.py`
- `tests/test_daemon_trigger_router.py`
- `tests/test_daemon_mailbox.py`

Work:

- Add optional `schedule_key` to generic schedule rows.
- Add `DaemonState.upsert_schedule(...)`.
- Reuse only pending schedules with the same key.
- Preserve delivered, failed, and canceled history.
- Allow mailbox and daemon client callers to pass `schedule_key`.

No browser semantics may be added to daemon core.

### 2. Rebuild Browser Lifecycle API

Files:

- `scripts/env/cdp_browser_lifecycle.py`
- `tests/test_cdp_browser_session.py`

Work:

- Replace `BROWSER_PAGE_TTL_SECONDS` with `BROWSER_PAGE_IDLE_SECONDS = 300`.
- Replace `register_browser_page_ttl` with `touch_page_idle`.
- Add `runtime/browser/page_idle.json` helpers.
- Persist current `target_id`, optional `page_id` to `target_id` mapping, and per-target `last_used_at`.
- Schedule `browser.page.expired` using key `browser.page.idle:<target_id>`.
- Keep close-target CDP helpers unchanged except where tests require naming cleanup.

### 3. Update Search Page Use

Files:

- `scripts/env/tools/search/_impl.py`
- `tests/test_search_env_tool.py`

Work:

- On successful new page open, call `touch_page_idle`.
- On exact URL reuse, call `touch_page_idle`.
- Return internal idle refresh metadata only: no policy controls, no schedule id, no old TTL names.
- Preserve existing failure behavior: an idle refresh failure does not roll back an opened page.

### 4. Update Cockpit Proxy Page Use

Files:

- `tools/launcher/chrome_devtools_cockpit_proxy.py`
- `tests/test_browser_cockpit_proxy.py`

Work:

- For `new_page`, call `touch_page_idle` after exactly one new CDP target is observed.
- For exact URL reuse in `new_page`, refresh the reused target.
- For successful `select_page`, record the selected page as current and refresh it when the CDP target can be resolved.
- For successful page-scoped actions, refresh current page idle.
- Do not count `list_pages`, `tools/list`, failed responses, blocked focus, or `close_page` as use.

### 5. Update Expiry Handler

Files:

- `tools/launcher/browser_page_expired_handler.py`
- `tools/launcher/browser_inbound.py`
- `tests/test_browser_page_expired_handler.py`

Work:

- Simplify payload to `target_id`.
- Remove notify policy.
- If expired page is current and parent activity is running, call `touch_page_idle` and do not close.
- Otherwise close the target.
- Treat stale browser errors as handled.

### 6. Remove Old TTL Surface

Search for and remove old semantics:

```bash
rg -n 'register_browser_page_ttl|BROWSER_PAGE_TTL_SECONDS|ttl_seconds|expiry_policy|Browser page TTL|notify'
```

Allowed remaining hits must be historical docs or tests intentionally checking absence.

### 7. Verify

Run the focused command from the test plan first. If it passes and cleanup is clean, run broad Python and JS verification. Inspect residual processes after broad verification before claiming completion.

## Review Checklist

- No actor-facing TTL or policy parameter exists.
- No browser-specific state fields were added to daemon core state.
- Repeated page use cannot leave an older pending schedule that expires earlier.
- Current-page protection only applies while the actor main turn is running.
- Tests describe product behavior, not implementation trivia.
- Verification includes resource cleanup evidence.
