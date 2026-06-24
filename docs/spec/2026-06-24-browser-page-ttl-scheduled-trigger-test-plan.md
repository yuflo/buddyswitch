# Browser Page TTL Scheduled Trigger Test Plan

Date: 2026-06-24
Source memo: `docs/memo/2026-06-24-browser-page-ttl-scheduled-trigger.md`
Resource guidance: `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`

## Goal

Prove that every real newly opened browser page gets a durable, one-shot TTL schedule, and that the
instance daemon can later emit a generic scheduled trigger that a browser-owned handler handles
without daemon browser policy.

## Bottleneck

The current browser page gate prevents unbounded page creation at open time, but it cannot create a
future lifecycle signal for temporary tool-owned resources. The test focus is therefore scheduled
trigger durability and browser TTL behavior, not a general browser resource framework.

## Resource Lifecycle Rules

- Do not use real `instance start` or real Chrome for the primary verification loop.
- Prefer in-process daemon state tests, Unix-socket mailbox tests, short-lived fake CDP HTTP servers,
  and fake upstream MCP subprocesses that already have teardown.
- Before any broad service-starting suite, inspect or add process registration and teardown, then run
  one focused test and a residual-process check.
- Focused verification for this feature must finish without leaving daemon, app-server, broker,
  browser, or fake upstream processes.

## Functional Test Matrix

### Scheduled trigger persistence and dispatch

File: `tests/test_daemon_trigger_router.py`

1. `test_scheduled_trigger_registration_persists_pending_schedule`
   - Register a schedule with `delay_seconds=600`, `type="browser.page.expired"`, and a payload object.
   - Assert state contains one schedule with generated `schedule_id`, computed `due_at`, source
     `scheduled_trigger`, status `pending`, timestamps, and unchanged payload.
   - Assert no trigger is dispatched at registration time.

2. `test_due_scheduled_trigger_dispatch_marks_delivered_once`
   - Create a due pending schedule.
   - Sweep due schedules through a handler that returns `handled`.
   - Assert dispatch sees trigger type and payload.
   - Assert schedule moves to `delivered` with `delivered_at`, `handling_status="handled"`, and is not
     emitted again on a second sweep.

3. `test_due_scheduled_trigger_with_no_handler_marks_failed_once`
   - Create a due pending schedule with no matching handler.
   - Sweep due schedules.
   - Assert schedule moves to `failed`, `last_error` says no matching handler, and second sweep emits
     nothing.

4. `test_due_scheduled_trigger_handler_failure_marks_failed_without_retry`
   - Create a due pending schedule.
   - Handler returns `failed("close failed")`.
   - Assert status `failed`, `last_error="close failed"`, and second sweep emits nothing.

5. `test_canceled_schedule_is_not_dispatched`
   - Cancel a pending schedule.
   - Sweep after due time.
   - Assert handler is not called and status remains `canceled`.

File: `tests/test_daemon_service_contract.py`

6. `test_daemon_status_reports_schedule_state`
   - Persist pending, delivered, failed, and canceled schedule rows.
   - Assert `daemon_status()` includes schedule ids/items and does not expose corrupt rows.

### Mailbox schedule API

File: `tests/test_daemon_mailbox.py`

1. `test_mailbox_schedule_trigger_registers_instance_local_schedule`
   - Dispatch `mailbox.schedule_trigger` with `delay_seconds`, trigger type, payload, and source context.
   - Assert result contains schedule metadata and state file contains the pending schedule.

2. `test_mailbox_schedule_trigger_rejects_invalid_payload_without_dispatch`
   - Invalid delay, type, or payload returns protocol error.
   - Assert no schedule row is written.

3. `test_mailbox_local_trigger_still_dispatches_existing_handlers`
   - Existing local trigger behavior remains green after adding the new method.

### Daemon run-loop sweep

File: `tests/test_daemon_core.py`

1. `test_run_daemon_sweeps_due_schedules_on_app_server_timeout`
   - Stub app-server client to time out once, then raise a controlled stop exception.
   - Seed a due schedule.
   - Assert `sweep_due_scheduled_triggers()` is called during the timeout heartbeat path.

This is a unit-style run-loop test with fake client functions. It must not start a real daemon
process.

### Browser expired handler

File: `tests/test_browser_page_expired_handler.py`

1. `test_auto_close_closes_existing_target_by_target_id`
   - Fake CDP server returns `/json/list` containing the target id.
   - Handler receives `browser.page.expired` payload with `target_id`, `target_url`, `ttl_seconds`, and
     `expiry_policy="auto_close"`.
   - Assert it calls `Target.closeTarget` with the target id and returns handled.

2. `test_auto_close_missing_target_is_handled`
   - `/json/list` does not contain the target id.
   - Assert no close RPC is sent and handler returns handled.

3. `test_auto_close_browser_unavailable_is_handled_as_stale`
   - Browser endpoint cannot be read.
   - Assert handler returns handled because target ids are not durable across browser restart.

4. `test_auto_close_close_failure_returns_failed_once`
   - Close RPC returns a CDP error for an existing target.
   - Assert handler returns failed with the CDP error.

5. `test_notify_policy_submits_concise_parent_prompt`
   - Runtime parent activity is idle.
   - Handler submits one concise TTL prompt and returns handled.

6. `test_handler_rejects_wrong_target_actor`
   - Trigger target actor does not match context actor.
   - Assert failed result and no CDP call.

### Search open TTL registration

File: `tests/test_search_env_tool.py`

1. `test_search_open_browser_creates_ttl_schedule_after_new_target`
   - Fake CDP server returns `Target.createTarget` with target id.
   - Patch `daemon_client.schedule_trigger`.
   - Assert schedule payload has target id, target URL, `ttl_seconds=600`, `expiry_policy="auto_close"`.
   - Assert response includes `ttl_registered=True`, `ttl_seconds=600`, `expires_at`, and concise TTL
     text in `effect_summary`.

2. `test_search_open_browser_reports_ttl_registration_failure_without_rolling_back_open`
   - `Target.createTarget` succeeds, schedule registration raises `DaemonClientError`.
   - Assert response is still ok with `page_opened=True`, `ttl_registered=False`, and no TTL protection
     claim.

3. `test_search_open_browser_without_target_id_does_not_schedule`
   - Helper returns success without `targetId`.
   - Assert open fails or returns explicit no-TTL failure according to implementation, and no schedule is
     registered.

4. `test_search_reuse_does_not_register_or_refresh_ttl`
   - Exact URL already open.
   - Assert no schedule helper call and no TTL fields.

5. Existing block, page-count verification failure, browser unavailable, and open failure tests must keep
   proving no schedule registration happens.

### Chrome DevTools cockpit proxy TTL registration

File: `tests/test_browser_cockpit_proxy.py`

1. `test_new_page_registers_ttl_after_exactly_one_new_target`
   - Fake CDP `/json/list` returns pre-open targets, then post-open targets with exactly one new page id.
   - Fake upstream returns success for `new_page`.
   - Patch or fake schedule registration through environment-configured daemon socket helper.
   - Assert response has TTL text and schedule payload uses the new target id.

2. `test_new_page_ttl_registration_failure_is_reported_without_marking_tool_error`
   - Open succeeds, registration fails.
   - Assert upstream response remains success with appended `ttl_registered=false` text.

3. `test_new_page_ambiguous_target_diff_does_not_guess`
   - Post-open `/json/list` has zero or multiple new page ids.
   - Assert no schedule registration and response says TTL was not registered.

4. `test_new_page_reuse_and_block_do_not_register_ttl`
   - Reuse and hard-limit local paths do not call schedule registration.

5. `test_select_page_forces_no_bring_to_front_and_does_not_register_ttl`
   - Existing focus-control assertion remains.
   - Assert no schedule registration call.

### CDP browser session helpers

File: `tests/test_cdp_browser_session.py`

1. `test_close_target_sends_target_close_target`
   - Fake browser websocket records one `Target.closeTarget` RPC.
   - Assert result reports closed target id.

2. `test_close_target_missing_target_is_handled`
   - `/json/list` does not contain id.
   - Assert helper returns already gone without RPC.

3. `test_target_diff_requires_exactly_one_new_page`
   - Pre/post target snapshots identify exactly one new page id.
   - Ambiguous diffs return no target id.

## Verification Order

1. Run one new focused test at a time and confirm it fails before implementation.
2. Make the smallest direct implementation change.
3. Re-run that focused test until green.
4. Run the related focused file.
5. Run the full focused group:

```bash
python3 -m unittest \
  tests.test_daemon_trigger_router \
  tests.test_daemon_service_contract \
  tests.test_daemon_mailbox \
  tests.test_daemon_core \
  tests.test_instance_daemon_entrypoint \
  tests.test_browser_page_expired_handler \
  tests.test_cdp_browser_session \
  tests.test_browser_cockpit_proxy \
  tests.test_search_env_tool
```

6. If any service-starting tests are added to verification, first prove cleanup and then check residual
   processes after the run.

## Review Checklist

- New-page opens schedule TTL only after observing a real new target id.
- Reuse, select, block, failed open, and ambiguous target detection do not register schedules.
- Scheduled trigger status is one-shot: `pending -> delivered | failed | canceled`.
- No failed schedule auto-retries.
- Browser expired handler closes by target id only, never by URL.
- Daemon status exposes useful schedule state without actor-facing open responses exposing daemon internals.
- Existing message, track, and task handler tests still pass through the unified handler interface.
