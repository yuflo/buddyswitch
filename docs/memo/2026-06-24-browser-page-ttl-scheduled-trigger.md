# Browser Page TTL Scheduled Trigger

Date: 2026-06-24
Status: architecture/task memo for daemon-service and browser-tool implementation
Branch: `fea-tool`
Worktree: `.worktrees/fea-tool`

## Summary

Upgrade browser page opening so every newly opened browser page has a simple lifetime boundary.

The first behavior is:

```text
ttl_seconds = 600
```

When a browser tool opens a new page, the actor should see a short TTL fact in the tool response.
After the TTL expires, the instance daemon should trigger a tool-owned handler that either reminds
the actor or closes the page through the browser/CDP capability.

This is not a browser-specific daemon feature. The daemon-service should provide a generic scheduled
trigger capability and a cleaned-up trigger handler pipeline. Browser page expiry is the first
consumer.

## Current Bottleneck

The browser page limit gate already prevents unbounded page creation. It counts existing pages,
reuses exact target URLs, blocks at the hard limit, and warns near pressure.

That gate does not solve the next problem:

- users and actors often finish browser work without closing pages;
- the actor only sees pressure when another open action happens;
- there is no lifecycle signal after a page has been opened;
- there is no clean daemon-level way to produce a future trigger for tool-owned cleanup.

The bottleneck is therefore not "how to close a browser page". It is "how to let tool-owned
temporary resources create a durable, future trigger without making daemon-service understand the
resource semantics".

## Existing Startup Order

The current launcher order matters.

For a new or resumed instance, browser setup happens before instance daemon startup:

```text
instance start/resume
  -> bind instance and prepare workspace/runtime surfaces
  -> ensure runtime broker
  -> ensure env MCP
  -> browser_bootstrap
       -> set browser port/profile/log defaults
       -> ensure Chrome CDP endpoint
       -> ensure chrome-devtools-cockpit MCP
  -> write instance.browser_port
  -> ensure app-server and start/resume thread
  -> write app-server/thread fields to instance record
  -> daemon_start
       -> ensure central daemon
       -> start instance daemon
       -> load daemon handlers/subscriptions
       -> start daemon mailbox
       -> register actor endpoint/subscriptions
```

The TTL handler must not initialize browser profile directories, Chrome, or MCP configuration.
Those remain owned by `browser_bootstrap`. The handler can rely on instance state such as
`browser_port` after the daemon is running.

## Desired Actor-Facing Behavior

The actor should not learn daemon internals.

For browser open actions, the extra actor-facing fact should be limited to a short TTL statement and
structured fields that are directly useful:

```text
ttl_seconds = 600
expires_at = <timestamp>
expiry_policy = auto_close | notify
```

The response text should stay short, for example:

```text
Browser page TTL: 600s.
```

Do not expose scheduled trigger storage, handler names, daemon routing, or schedule internals unless
a future renew/cancel/status tool needs them.

## Architecture Decision

Use a generic scheduled trigger pipeline:

```text
tool opens page
  -> tool creates scheduled trigger
  -> daemon persists schedule
  -> daemon scheduled source emits trigger when due
  -> daemon dispatches trigger to registered handler
  -> browser/tool-owned handler reminds or closes
```

Keep these boundaries:

```text
daemon-service
  owns: schedule persistence, due sweep, trigger envelope, handler dispatch, handler result state

browser/tool owner
  owns: event type, payload contract, open semantics, TTL policy, page close implementation

launcher browser bootstrap
  owns: browser profile/log defaults, Chrome endpoint, chrome-devtools-cockpit MCP setup
```

## Task 1: Daemon Trigger Architecture Cleanup

Highlight: unify daemon event handling into a light trigger pipeline and remove handler dual paths.

Target shape:

```text
TriggerSource -> TriggerEnvelope -> TriggerHandler -> HandlerResult
```

Key work:

- replace ad hoc handler duck typing with a single light handler abstraction;
- keep the interface small: event type match, payload parse/validation, handle;
- migrate existing handlers into the unified abstraction:
  - task checkout;
  - message available;
  - track comment added;
- rename or reshape `notification_center` into a generic trigger registration center if needed;
- app-server notifications, mailbox signals, local triggers, and scheduled triggers should all enter
  the same dispatch path;
- daemon core should only dispatch, record handler status, and record errors;
- delete old handler paths after migration instead of keeping compatibility wrappers.

Non-goal:

- do not introduce a resource framework, workflow engine, or browser-specific daemon branch.

## Task 2: Daemon Scheduled Trigger Capability

Highlight: add instance-local durable scheduled triggers.

The daemon-service should expose a generic schedule API, not a browser API.

Minimal schedule registration shape:

```json
{
  "delay_seconds": 600,
  "type": "browser.page.expired",
  "payload": {}
}
```

Daemon should compute and persist:

```text
schedule_id
due_at
type
payload
status = pending | delivered | failed | canceled
created_at
updated_at
last_error
```

Key work:

- persist schedules under instance runtime state;
- sweep pending schedules whose `due_at <= now`;
- convert due schedules into the unified trigger envelope;
- dispatch through the unified handler pipeline;
- mark schedule delivered, failed, or canceled;
- make the API instance-local, so callers do not pass `target_actor_address`;
- use the current instance actor context when producing the trigger envelope.

Non-goals for v1:

- no idempotency key;
- no exactly-once guarantee;
- no generic lease/resource model;
- no daemon-owned browser page cleanup policy;
- no dynamic handler creation per schedule.

## Task 3: Browser Tool Owner Trigger Registration

Highlight: browser/tool capability statically registers the page-expired handler with the instance
daemon.

The browser/tool owner should provide a static registration equivalent to:

```text
browser.page.expired -> BrowserPageExpiredHandler
```

Likely files:

```text
tools/launcher/browser_inbound.py
tools/launcher/browser_page_expired_handler.py
```

The registration should be loaded during instance daemon startup alongside existing message and
track registrations. It should not run during each browser open action.

Handler responsibility:

```text
input: trigger type browser.page.expired
payload: target_id, target_url, ttl_seconds, expiry_policy

if expiry_policy == notify:
  submit a concise parent/side prompt to the actor

if expiry_policy == auto_close:
  call browser/CDP close target helper
  mark handled if the target is closed or already gone
```

The handler must not:

- bootstrap Chrome;
- add or remove MCP servers;
- read arbitrary browser policy from daemon-service;
- decide global browser cleanup rules.

## Task 4: Browser Open Flow Creates Scheduled Trigger

Highlight: only successful new page creation creates a TTL schedule.

Affected open paths:

```text
search.open_browser
chrome-devtools-cockpit proxy new_page
```

Required behavior:

- only a real new page open schedules expiry;
- exact URL reuse does not refresh TTL;
- page selection does not refresh TTL;
- failed opens do not schedule expiry;
- actor-facing response includes `ttl_seconds = 600`;
- response text stays short and does not expose daemon internals.

Suggested payload:

```json
{
  "target_id": "<cdp target id>",
  "target_url": "<opened url>",
  "ttl_seconds": 600,
  "expiry_policy": "auto_close"
}
```

If schedule registration fails after a page has opened, the browser tool response must be explicit:

```text
page_opened = true
ttl_registered = false
```

Do not claim TTL protection when schedule registration failed.

## Task 5: TTL Risk Check

Highlight: prevent TTL loss, accidental TTL refresh, stale target close, and infinite retry noise.

Current code inspection:

- `search.open_browser` already uses `evaluate_page_open_gate()` before opening. Reuse and limit-block
  paths return before calling `Target.createTarget`.
- `search.open_browser` currently calls `scripts/env/cdp_background_page.py`, whose CDP response includes
  `targetId`, but `_open_browser_page()` discards it and returns only `(opened, reason)`.
- `chrome-devtools-cockpit proxy` also uses `evaluate_page_open_gate()` before forwarding `new_page`.
  Reuse and limit-block paths are local responses and do not reach the upstream MCP.
- `chrome-devtools-cockpit proxy` forwards successful `new_page` requests to upstream and only appends a
  page-count hint to the upstream response today. It does not currently inspect the successful response or
  resolve the newly created CDP target.
- `select_page` only forces `bringToFront=false`. It does not call the page gate and must not touch TTL.
- There is no existing `Target.closeTarget` or `/json/close` helper. TTL implementation must add a small
  CDP close helper instead of assuming close support already exists.
- Instance start/resume normally bootstraps browser and writes `browser_port` before daemon start. The
  daemon handler should still reload current instance state at expiry time rather than rely only on the
  daemon startup snapshot.

Risk conclusions and required defenses:

1. Open succeeds but schedule registration fails.
   - This can happen because schedule registration is a second operation after the page exists.
   - Do not roll back the open in v1.
   - Return success for the open but expose:

     ```text
     page_opened = true
     ttl_registered = false
     ```

   - Do not claim TTL protection in either structured fields or response text.

2. Schedule registration succeeds but open failed.
   - Schedule creation must happen only after the open path has observed a real new CDP target id.
   - For `search.open_browser`, change `_open_browser_page()` to parse helper stdout and return the new
     `targetId`.
   - For cockpit `new_page`, register after upstream success and after resolving the new `targetId`. If
     upstream response does not expose it, compare the pre-open and post-open `/json/list` page target id
     sets for that forwarded request. If the diff is not exactly one new page target, do not guess; do not
     schedule and return `ttl_registered=false`.

3. `search.open_browser` and cockpit `new_page` diverge.
   - Both paths must call one shared browser TTL registration helper after successful new-page creation.
   - Both paths use the same default:

     ```text
     ttl_seconds = 600
     expiry_policy = auto_close
     ```

   - Both paths must share the same no-schedule decisions for reuse, select, block, and failed open.

4. Duplicate/reuse creates duplicate schedules or refreshes TTL.
   - Current exact-URL reuse is detected by `evaluate_page_open_gate()` before open.
   - Reuse must return without schedule registration.
   - Reuse must not refresh the old page's TTL. This keeps TTL behavior simple and prevents accidental
     infinite lifetime through repeated reuse.

5. `select_page` refreshes TTL.
   - `select_page` must remain a selection/focus-control operation only.
   - Do not call schedule registration from `select_page`.
   - Add/keep focused proxy tests that prove `select_page` forwards with `bringToFront=false` and produces
     no TTL schedule call.

6. Manual page close before expiry.
   - The expiry handler must close by `target_id`, not by URL.
   - If `/json/list` no longer contains the target id, treat the schedule as handled. This covers manual
     close and avoids false failure.

7. Target missing or browser restarted at expiry.
   - CDP target ids are not durable across browser restart.
   - If the current browser endpoint is unavailable, or the target id is absent, the schedule should be
     treated as stale/handled for `auto_close`. Do not close a page by matching only `target_url`.
   - `target_url` is diagnostic context, not a close selector.

8. Close command fails.
   - Add a small CDP close helper, likely using `Target.closeTarget`.
   - If the helper reports "target not found", treat it as handled.
   - If the helper reaches the browser but the close command fails for another reason, mark the schedule
     failed once with `last_error`.

9. Infinite retry or repeated actor prompts.
   - Scheduled trigger v1 should be one-shot:

     ```text
     pending -> delivered
     pending -> failed
     pending -> canceled
     ```

   - The sweeper must only emit `pending` schedules. `failed` schedules are not retried automatically.
   - A scheduled trigger that dispatches with no matching handler must not be marked `delivered`; mark it
     `failed` once with `last_error` so TTL loss is visible without creating a retry loop.
   - `auto_close` failures should be visible in daemon schedule/handler state, not repeated side prompts.

10. Page limit gate conflicts with TTL close.
    - Page gate remains the pre-open guard.
    - Limit-block and reuse paths must not create schedules.
    - TTL close naturally reduces future `/json/list` page count; no special coupling with the page gate is
      needed.
    - Concurrent opens can still race the current count gate; TTL does not solve that existing gate race.

11. Schedule storage across daemon restart.
    - Schedules must be persisted under instance runtime state, not kept only in memory.
    - Daemon startup should load pending schedules and the run loop should sweep due schedules on its normal
      timeout/heartbeat cycle as well as after local activity.

12. Actor-facing state.
    - The actor should see only lifecycle facts:

      ```text
      ttl_seconds
      expires_at
      expiry_policy
      ttl_registered
      ```

    - Do not expose daemon schedule ids, handler names, storage paths, or dispatch internals in normal open
      responses.

Core rules:

```text
new page open with target_id -> schedule TTL
new page open without target_id -> no schedule, ttl_registered=false
reuse -> no schedule, no TTL refresh
select -> no schedule, no TTL refresh
failed open -> no schedule
expired close missing target -> handled idempotently
failed close -> one failed schedule state, no automatic retry loop
```

## Verification Targets

Focused verification should prove:

- daemon scheduled triggers persist and fire after `delay_seconds`;
- existing message, track, and task handlers still work after trigger pipeline cleanup;
- daemon status reports registered handlers and schedule state clearly;
- browser open response includes TTL only after actual new page creation;
- reuse and select do not create or refresh TTL schedules;
- expired browser page handler closes an existing target;
- expired browser page handler handles already-closed targets without failure;
- browser bootstrap still happens before daemon start and is not duplicated by handlers.

Suggested focused test areas:

```text
tests/test_daemon_trigger_router.py
tests/test_daemon_service_contract.py
tests/test_instance_daemon_entrypoint.py
tests/test_browser_cockpit_proxy.py
tests/test_search_env_tool.py
```

Do not run broad service-starting suites until focused tests and lifecycle cleanup checks are green.

## Final Target Flow

```text
launcher starts browser/MCP before daemon
daemon starts and loads browser.page.expired handler
browser tool opens new page
browser tool creates scheduled trigger with delay_seconds=600
actor sees concise TTL fact in open response
daemon scheduled source reaches due_at
daemon emits browser.page.expired trigger
BrowserPageExpiredHandler reminds actor or closes target through CDP helper
schedule is marked delivered or failed
```
