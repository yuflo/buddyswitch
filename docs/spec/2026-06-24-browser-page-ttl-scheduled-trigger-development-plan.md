# Browser Page TTL Scheduled Trigger Development Plan

> **For agentic workers:** Use test-driven development. Write each focused test first, run it and see
> the expected failure, then implement the smallest direct change. Do not start real long-lived
> services unless the focused unit/in-process checks are green and cleanup has been inspected.

**Goal:** Add generic instance-local scheduled triggers to the daemon and use them to give newly
opened browser pages a 600 second TTL with browser-owned expiry handling.

**Architecture:** Extend the existing unified `DaemonTrigger` and `DaemonHandler` path. Schedules are
persisted in instance daemon state, registered through the instance mailbox, swept by daemon core, and
dispatched as normal triggers. Browser tools call one shared TTL registration helper only after a real
new page target id is known.

**Tech Stack:** Python stdlib, `unittest`, Unix-domain mailbox protocol, Chrome DevTools Protocol
helpers, existing BuddySwitch env tool result helpers.

## Target Files

- Modify: `tools/launcher/daemon_triggers.py`
  - Add `SCHEDULED_TRIGGER` source and `normalize_scheduled_trigger()`.
- Modify: `tools/launcher/daemon_core.py`
  - Add schedule state normalization, create/cancel/update helpers, due sweep, status payload, and
    run-loop sweep call.
- Modify: `tools/launcher/daemon_mailbox.py`
  - Add `mailbox.schedule_trigger` and optional `mailbox.cancel_schedule`.
- Modify: `scripts/env/tool_runtime/daemon_client.py`
  - Add instance mailbox helpers `mailbox_socket_path_for_instance_root()` and `schedule_trigger()`.
- Create: `scripts/env/cdp_browser_lifecycle.py`
  - Shared CDP target list, target diff, `Target.closeTarget`, and browser TTL registration helpers.
- Modify: `scripts/env/cdp_background_page.py`
  - Keep printing `Target.createTarget` result so callers can read `targetId`.
- Modify: `scripts/env/tools/search/_impl.py`
  - Parse helper JSON result, call shared TTL helper, and expose actor-facing TTL fields only on real
    new page opens.
- Modify: `tools/launcher/chrome_devtools_cockpit_proxy.py`
  - Resolve one new target id around forwarded `new_page`, call shared TTL helper, append concise TTL
    response text, and keep `select_page` TTL-free.
- Create: `tools/launcher/browser_page_expired_handler.py`
  - Browser-owned `browser.page.expired` handler.
- Create: `tools/launcher/browser_inbound.py`
  - Static inbound registration for browser page expiry.
- Modify: `tools/launcher/instance_daemon.py`
  - Load browser registration with message and track registrations.
- Tests:
  - `tests/test_daemon_trigger_router.py`
  - `tests/test_daemon_service_contract.py`
  - `tests/test_daemon_mailbox.py`
  - `tests/test_daemon_core.py`
  - `tests/test_instance_daemon_entrypoint.py`
  - `tests/test_browser_page_expired_handler.py`
  - `tests/test_cdp_browser_session.py`
  - `tests/test_browser_cockpit_proxy.py`
  - `tests/test_search_env_tool.py`

## Implementation Tasks

### Task 1: Persist Generic Schedules

- [ ] Add failing tests in `tests/test_daemon_trigger_router.py` for pending schedule creation,
      delivered one-shot dispatch, failed no-handler dispatch, failed handler dispatch, and canceled
      schedule skip.
- [ ] Run:

```bash
python3 -m unittest tests.test_daemon_trigger_router.DaemonTriggerRouterTests.test_scheduled_trigger_registration_persists_pending_schedule
```

Expected: fail because daemon state has no schedule API.

- [ ] Implement in `daemon_triggers.py`:
  - `SCHEDULED_TRIGGER = "scheduled_trigger"`
  - `normalize_scheduled_trigger(schedule, target_actor_address)` returning `DaemonTrigger`.
- [ ] Implement in `DaemonState`:
  - schedule row normalization during `load()`;
  - `create_schedule(delay_seconds, trigger_type, payload, source_context=None, now=None)`;
  - `cancel_schedule(schedule_id)`;
  - `due_schedules(now=None)`;
  - `mark_schedule_delivered(schedule_id, dispatch_result)`;
  - `mark_schedule_failed(schedule_id, message, dispatch_result=None)`.
- [ ] Implement `sweep_due_scheduled_triggers(context, state, runtime, handlers, now=None)` in
      `daemon_core.py`.
- [ ] Re-run each new daemon trigger router test, then the full file:

```bash
python3 -m unittest tests.test_daemon_trigger_router
```

Expected: pass.

### Task 2: Expose Schedule State and Mailbox API

- [ ] Add failing status test in `tests/test_daemon_service_contract.py` for `daemon_status()["schedules"]`.
- [ ] Add failing mailbox tests in `tests/test_daemon_mailbox.py` for `mailbox.schedule_trigger`
      success and invalid input rejection.
- [ ] Run the new focused tests and confirm expected failure.
- [ ] Implement `daemon_status()` schedule payload with ids/items and pending/delivered/failed/canceled
      counts.
- [ ] Implement `DaemonMailboxServer._dispatch_schedule_trigger()` and method routing for
      `mailbox.schedule_trigger`.
- [ ] Keep existing `mailbox.local_trigger` behavior unchanged.
- [ ] Re-run:

```bash
python3 -m unittest tests.test_daemon_service_contract tests.test_daemon_mailbox
```

Expected: pass.

### Task 3: Sweep Due Schedules During Daemon Runtime

- [ ] Add failing unit-style run-loop test in `tests/test_daemon_core.py` that simulates
      `AppServerTimeoutError` and proves due schedules are swept during the heartbeat path.
- [ ] Run that test and confirm failure because the run loop only heartbeats today.
- [ ] In `run_daemon()`, call `sweep_due_scheduled_triggers()` after mailbox setup and on each app-server
      timeout before or after heartbeat.
- [ ] Do not spawn a real daemon in this test.
- [ ] Re-run the focused test and then:

```bash
python3 -m unittest tests.test_daemon_core tests.test_instance_daemon_entrypoint
```

Expected: pass.

### Task 4: Add Browser Expiry Registration and Handler

- [ ] Add failing tests in `tests/test_instance_daemon_entrypoint.py` expecting default handler names to
      include `browser_page_expired` and notify subscriptions to include `browser.page.expired` only if
      central-daemon notification subscription is needed. For scheduled-only local dispatch, assert the
      handler is registered but not in notify subscriptions.
- [ ] Add failing handler tests in `tests/test_browser_page_expired_handler.py`.
- [ ] Create `browser_page_expired_handler.py`:
  - validate trigger type `browser.page.expired`;
  - verify trigger target actor equals local context actor;
  - require payload fields `target_id`, `target_url`, `ttl_seconds`, `expiry_policy`;
  - `notify`: submit concise parent prompt;
  - `auto_close`: close target by id using shared CDP helper;
  - missing target or unavailable endpoint returns handled as stale;
  - close command failure returns failed.
- [ ] Create `browser_inbound.py` registration for handler construction and payload contract.
- [ ] Modify `instance_daemon.py` to include browser registration.
- [ ] Re-run:

```bash
python3 -m unittest tests.test_browser_page_expired_handler tests.test_instance_daemon_entrypoint
```

Expected: pass.

### Task 5: Shared Browser Lifecycle Helpers

- [ ] Add failing tests in `tests/test_cdp_browser_session.py` for target id extraction, pre/post target
      diff, `Target.closeTarget`, and missing target behavior.
- [ ] Create `scripts/env/cdp_browser_lifecycle.py` with:
  - `BROWSER_PAGE_TTL_SECONDS = 600`;
  - `BROWSER_PAGE_EXPIRY_POLICY = "auto_close"`;
  - `read_page_targets(browser_url, timeout_seconds=3.0)`;
  - `new_page_target_id(before_targets, after_targets)`;
  - `close_page_target(browser_url, target_id, timeout_seconds=3.0)`;
  - `register_browser_page_ttl(instance_json, target_id, target_url, ttl_seconds=600, expiry_policy="auto_close")`.
- [ ] In `daemon_client.py`, add:
  - `mailbox_socket_path_for_instance_root(instance_root)`;
  - `schedule_trigger(instance_root, delay_seconds, trigger_type, payload, source_context=None)`.
- [ ] Re-run:

```bash
python3 -m unittest tests.test_cdp_browser_session
```

Expected: pass.

### Task 6: Search Open Registers TTL

- [ ] Add failing tests in `tests/test_search_env_tool.py` for successful TTL registration, schedule
      registration failure reporting, missing target id no-schedule behavior, and reuse no-schedule
      behavior.
- [ ] Change `_open_browser_page()` to parse `cdp_background_page.py` stdout JSON and return
      `(opened, reason, result)` or a named result with `target_id`.
- [ ] After real open with target id, call `register_browser_page_ttl()`.
- [ ] On schedule success, add actor-facing fields:
  - `ttl_registered=True`
  - `ttl_seconds=600`
  - `expires_at`
  - `expiry_policy="auto_close"`
  - short `Browser page TTL: 600s.` fact in effect summary.
- [ ] On registration failure after open, keep `ok=True`, `page_opened=True`, set
      `ttl_registered=False`, and do not include TTL protection text.
- [ ] Reuse, block, verification failure, browser unavailable, and failed open paths must not call the TTL
      helper.
- [ ] Re-run:

```bash
python3 -m unittest tests.test_search_env_tool
```

Expected: pass.

### Task 7: Cockpit Proxy Registers TTL

- [ ] Add failing tests in `tests/test_browser_cockpit_proxy.py` for new-page TTL registration, registration
      failure text, ambiguous target diff no-schedule, reuse/block no-schedule, and select no-schedule.
- [ ] Before forwarding `new_page`, read pre-open page targets only after page gate allows.
- [ ] After upstream success, read post-open page targets and resolve exactly one new target id.
- [ ] If exactly one target id is resolved, call `register_browser_page_ttl()`.
- [ ] Append concise TTL text to upstream success response when registration succeeds.
- [ ] Append concise `ttl_registered=false` text when target id resolution or schedule registration fails.
- [ ] Do not make upstream success into a tool error solely because TTL registration failed.
- [ ] Re-run:

```bash
python3 -m unittest tests.test_browser_cockpit_proxy
```

Expected: pass.

### Task 8: Focused Verification and Review

- [ ] Run the focused group:

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

- [ ] Run a residual-process check if any service-starting tests were executed:

```bash
ps -axo pid,ppid,command | rg 'instance_daemon.py|central_daemon.py|fake_codex.py|chrome-devtools|Chrome|chromium|fake_upstream.py' || true
```

- [ ] Review the diff for:
  - no direct `tools/launcher` import from `scripts/env/tools/search/_impl.py`;
  - no daemon browser policy;
  - no schedule retry loop;
  - no TTL refresh on reuse/select;
  - no actor-facing schedule ids or handler names.

## Non-Goals

- Do not add a generic resource lease framework.
- Do not add exactly-once delivery.
- Do not close by URL.
- Do not roll back an already opened page when TTL registration fails.
- Do not run broad real-service integration suites before focused tests and cleanup checks are green.
