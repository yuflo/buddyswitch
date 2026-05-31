# Instance Start Bootstrap And Failed-State Cleanup Task

Date: 2026-05-31
Status: implemented and verified

## Problem

`inst-pm-e502018783be` failed during product instance startup.

The failure was not that the PM role logic was invalid. The instance reached the stage where Codex had
created a thread, then BuddySwitch tried to inject the internal bootstrap marker into that thread.
That `thread/bootstrap` step made Codex build the available MCP tool list. During this run,
`buddyswitch-env` and `chrome-devtools-cockpit` were still cold-starting; Chrome DevTools MCP also
had first-run npm package setup in the instance environment. The launcher timed out waiting for this
bootstrap path and failed the start.

After failure, the instance was left as `inactive`, but the instance record still had stale browser
state:

- no active app-server;
- no daemon runtime;
- no usable thread id in `instance.json`;
- stale `browser_port: 9222`;
- no clear durable failure reason.

Later another instance, `inst-market-1dfe68e21f06`, legitimately used port `9222`. When the user tried
to delete the failed PM instance, delete guard logic only checked whether the recorded port had a live
CDP endpoint. It did not verify that the live browser belonged to the PM instance. Market's live
browser was therefore misread as PM's browser, and deletion was blocked with:

```text
Instance delete blocked: active browser cockpit detected for inst-pm-e502018783be.
```

There are two connected issues:

1. Startup is brittle when `thread/bootstrap` waits for cold MCP tool discovery.
2. Failed startup cleanup and delete guards do not distinguish stale recorded state from resources
   owned by the target instance.

## Goal

Make product instance startup and failed-state handling simple, diagnosable, and recoverable.

The first fix should not introduce a new lifecycle platform. It should:

- give `thread/bootstrap` a bounded chance to recover from cold tool startup;
- leave failed instances clean and easy to delete;
- prevent one instance's stale browser port from being treated as another instance's active browser;
- keep Web UI as a caller of launcher/CLI semantics, not an owner of browser lifecycle logic.

## Non-Goals

Do not add:

- global npm package cache work;
- global Chrome DevTools MCP process sharing;
- automatic instance recreation after startup failure;
- automatic deletion of failed instance directories;
- a new browser ownership registry;
- a new daemon coordination path;
- a broad lifecycle state machine;
- Web UI special cases for this failure.

Package caching can be considered later, but this task should not depend on it.

## Existing Boundaries

Keep responsibilities in the current owned layers:

- `buddyswitch-codex` owns instance lifecycle orchestration.
- `tools/launcher/app_server.py` and `tools/launcher/app_server.sh` own app-server RPC helpers and
  RPC timeout behavior.
- `tools/launcher/env.sh` owns `instance.json` state writes.
- `tools/launcher/browser_cockpit.sh` owns browser endpoint, browser process, and browser ownership
  checks.
- `tools/launcher/web_management.py` should keep delegating lifecycle actions to the launcher CLI.

The fix should follow the `docs/bitter` principle: fix the layer that owns the wrong contract. The
wrong browser ownership check belongs in browser lifecycle helpers and launcher delete guard, not in
Web UI.

## Task 1: Bootstrap Timeout And One Retry

### Current Behavior

`start_locked_bootstrap` calls:

1. browser bootstrap;
2. app-server ensure;
3. `thread/start`;
4. `thread/bootstrap`;
5. daemon start.

`thread/bootstrap` injects a small internal marker item into the new thread. That RPC can block while
Codex builds the MCP tool list. In the observed failure, logs showed `list_all_tools` waiting for
`buddyswitch-env` startup while Chrome DevTools MCP was also doing first-run package setup.

The default app-server RPC timeout is shared by many commands. Raising it globally would slow down
unrelated failure paths and hide real app-server hangs.

### Required Behavior

Give only `thread/bootstrap` a dedicated timeout and one bounded retry.

Rules:

- Do not globally increase all app-server RPC timeouts.
- Add an explicit timeout path for the bootstrap RPC.
- If `thread/bootstrap` fails because of timeout, retry once.
- Before retrying, re-run the smallest reasonable readiness step that lets Codex MCP/tool discovery
  settle. Do not create a new instance or a new app-server for this retry.
- Reuse the same thread for the retry.
- Do not retry indefinitely.
- Do not retry non-timeout protocol errors as if they were cold-start delays.
- If the second attempt fails, startup fails closed.

### Thread Id Handling

Do not store a not-yet-bootstrap-confirmed thread id as the canonical `thread_id` for the instance.

Reason: the observed PM instance had a `thread/start` response in logs, but its Codex state database did
not show a durable usable thread entry afterward. Treating that id as a normal resumable thread could
make `resume` target a half-created or missing thread.

Allowed:

- record the id inside `last_failure.thread_id` for diagnostics;
- record it only after bootstrap succeeds as the canonical `thread_id`.

### Expected Result

Cold MCP startup gets one extra bounded chance to complete. If it still fails, the user gets a clean
failed instance instead of an ambiguous half-started instance.

## Task 2: Failed-State Cleanup And Delete Ownership Guard

Task 2 has two parts. Both are required; doing only one leaves a real gap.

### Part A: Cleanup Failed Startup State

When startup fails after the launcher has created runtime resources, cleanup must remove both running
resources and misleading instance record fields.

On failed startup after browser/app-server/broker setup, the launcher must:

- stop this instance's app-server;
- stop this instance's runtime broker;
- stop this instance's browser if this launcher started or owns it;
- clear `app_server_pid`;
- clear `app_server_socket`;
- clear `app_server_log`;
- clear `browser_port`;
- keep `status` as `inactive`;
- write `last_failure`.

`last_failure` should be small and durable, for example:

```json
{
  "phase": "thread_bootstrap",
  "message": "timed out waiting for thread/bootstrap",
  "thread_id": "diagnostic-thread-id-if-known",
  "browser_port": 9222,
  "failed_at": "2026-05-31T07:29:21Z"
}
```

The exact message can use the real error text. The field must be clear enough for `instance status` or
Web UI to explain where startup failed.

Do not delete the failed instance directory automatically. Keep it available for diagnostics and let
the user delete it explicitly.

### Part B: Fix Delete Guard Browser Ownership

Current delete guard blocks an inactive instance when:

- its `browser_port` is recorded; and
- some CDP endpoint is reachable on that port.

This is insufficient because ports can be reused by another instance.

`instance delete <target>` must block only when the live browser is owned by the target instance.

Required behavior:

- If target instance app-server is active, deletion remains blocked.
- If target instance browser pid marker is active, deletion remains blocked.
- If target instance recorded browser endpoint is reachable but belongs to another instance, deletion
  must not be blocked for the target.
- If ownership is clearly target-owned, deletion remains blocked.
- If ownership cannot be determined safely, prefer a conservative block with a clearer reason rather
  than deleting a possibly owned live browser profile.

Ownership check should live in `tools/launcher/browser_cockpit.sh`, not in Web UI.

Recommended helper shape:

```text
buddyswitch_browser_instance_endpoint_is_owned_active <instance_id>
```

Suggested ownership evidence:

- target instance `browser/chrome.pid` is live;
- or live process for the recorded debugging port has command line containing
  `--user-data-dir=<target-instance-root>/browser/profile`.

Keep the old "recorded endpoint is reachable" helper available for broader reset/cleanup behavior.
Do not silently change its semantics, because reset/data cleanup may intentionally use conservative
"any browser is alive" checks.

### Expected Result

A failed PM instance with stale `browser_port: 9222` can be deleted even when Market currently owns
port `9222`.

A PM instance whose own browser is still live remains protected from deletion.

## Recovery UX

After these changes, the expected user path is:

1. User starts an instance.
2. If bootstrap succeeds, instance becomes `active`.
3. If bootstrap times out, launcher retries once.
4. If retry also fails, instance remains `inactive` with `last_failure`.
5. User can inspect the failure and delete the failed instance from Web UI or CLI.
6. User creates a new instance explicitly.

No automatic recreate is required.

## Verification Plan

Add focused launcher tests before implementation where practical.

### Bootstrap Retry

Test that `thread/bootstrap` timeout triggers exactly one retry.

Expected:

- first `thread/inject_items` attempt times out or simulates timeout;
- second attempt is called once;
- success on second attempt makes instance active;
- daemon starts only after successful bootstrap.

### Bootstrap Retry Failure Cleanup

Test that two failed bootstrap attempts leave clean inactive state.

Expected persisted state:

- `status == "inactive"`;
- `app_server_pid is None`;
- `app_server_socket is None`;
- `app_server_log is None`;
- `browser_port is None`;
- no daemon pid remains;
- no app-server pid/socket marker remains;
- no browser pid marker remains;
- `last_failure.phase == "thread_bootstrap"`;
- canonical `thread_id` is absent or null;
- diagnostic thread id may appear only under `last_failure.thread_id`.

### Delete Ignores Foreign Browser Port

Create two instance records:

- failed PM with stale `browser_port: 9222`;
- active Market whose Chrome actually owns `9222`.

Delete PM.

Expected:

- delete succeeds;
- PM instance directory is removed;
- Market instance remains untouched;
- Market browser remains live.

### Delete Blocks Target-Owned Browser

Target instance has a live browser pid marker or owned browser endpoint.

Expected:

- delete returns blocked;
- instance directory remains.

### Cleanup/Reset Regression

Confirm reset/data cleanup semantics still block when any live browser makes broad cleanup unsafe.

Expected:

- existing broad cleanup protections do not become permissive just because delete guard became
  ownership-aware.

## Acceptance Criteria

The task is complete only when:

- `thread/bootstrap` has a dedicated bounded timeout/retry path;
- retry is exactly one attempt and only for timeout-like bootstrap failure;
- failed startup clears runtime resources and misleading instance fields;
- failed startup records a clear `last_failure`;
- canonical `thread_id` is not set for an unconfirmed bootstrap failure;
- `instance delete` checks target browser ownership instead of raw port reachability;
- Web UI does not gain browser lifecycle special cases;
- focused regression tests cover startup retry, failed cleanup, foreign browser port deletion, and
  target-owned browser protection;
- relevant launcher tests pass;
- no app-server, daemon, broker, or browser residual processes remain after service-starting tests.

## Risks And Guardrails

Risk: retrying non-timeout errors could hide real protocol bugs.

Guardrail: retry only timeout-like bootstrap failures.

Risk: clearing `browser_port` could make resume choose the wrong default port.

Guardrail: start/resume browser bootstrap must allocate a fresh free port when no valid owned port is
recorded.

Risk: changing the old endpoint helper could make reset/data cleanup unsafe.

Guardrail: keep the old reachability helper semantics and add a new ownership-specific helper for
delete/resume decisions.

Risk: storing `thread_id` too early could make resume target a half-created thread.

Guardrail: store early thread ids only in `last_failure`, not canonical `thread_id`.

Risk: automatic deletion would erase debugging evidence.

Guardrail: keep failed instance directory until explicit user delete.

## Short Version

Give `thread/bootstrap` one bounded retry for cold MCP startup. If it still fails, cleanly mark the
instance inactive, clear misleading runtime fields, and record why it failed. Fix delete guard so it
blocks only on browsers owned by the target instance, not any live endpoint on a stale recorded port.
