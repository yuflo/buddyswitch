# Buddy Web Management MVP Test Plan

Date: 2026-05-24

## Test Goal

Prove that the first BuddySwitch web management page lets a product manager
manage multiple buddy instances through a local browser surface while preserving
the existing service-mode lifecycle and safety boundaries.

Tests must start from functional requirements. They must not be shaped only to
match private helper functions or to make implementation details pass.

## Functional Requirements

| ID | Requirement |
| --- | --- |
| FR1 | The web server starts only on a local bind address by default. |
| FR2 | The page can prove API liveness without touching instance state. |
| FR3 | The API lists valid buddies from the manifest-backed CLI path. |
| FR4 | The API lists zero, one, or many stored instances from the current `instance list` output. |
| FR5 | The API exposes selected instance status using the same JSON shape as `instance status <id> --json`. |
| FR6 | The API creates an instance by delegating to `instance start --buddy <buddy>`. |
| FR7 | Create rejects unknown buddy ids before running `instance start`. |
| FR8 | Send instruction delegates to `instance input <id> --text <text>`. |
| FR9 | Send instruction rejects empty text before invoking the CLI. |
| FR10 | Send instruction reports started versus steered turns when the CLI output is parseable. |
| FR11 | Interrupt delegates to `instance interrupt <id>`. |
| FR12 | Stop delegates to `instance stop <id>` and refreshes instance status. |
| FR13 | Delete delegates to `instance delete <id> --yes` only for validated instance ids. |
| FR14 | Delete maps active-instance refusal to an HTTP conflict and preserves the CLI safety guard. |
| FR15 | Malformed JSON bodies return a structured client error without invoking lifecycle commands. |
| FR16 | Malformed or traversal instance ids are rejected before invoking the CLI. |
| FR17 | CLI failures and timeouts are converted to structured JSON errors without exposing stack traces. |
| FR18 | Concurrent duplicate mutating actions are blocked with a clear busy error. |
| FR19 | The static page renders the complete one-screen management surface. |
| FR20 | UI controls enable and disable according to instance state. |
| FR21 | The web layer never directly mutates `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**`. |
| FR22 | Existing service-mode launcher and app-server tests remain green. |

## Coverage Matrix

| Requirement | Primary Verification |
| --- | --- |
| FR1 | Web module host validation unit test and CLI `web --host 0.0.0.0` rejection test. |
| FR2 | HTTP test for `GET /api/health`. |
| FR3 | HTTP test for `GET /api/buddies` using fake command runner output matching current TSV. |
| FR4 | Parser and HTTP tests for empty `instance list` output and multi-row TSV output. |
| FR5 | HTTP test for status route preserving JSON keys from fake `status --json`. |
| FR6 | HTTP test records exact `instance start --buddy pm` command and status refresh command. |
| FR7 | HTTP test proves invalid buddy returns 400 and command runner did not run `start`. |
| FR8 | HTTP test records exact `instance input <id> --text <text>` command. |
| FR9 | HTTP test for empty text returns 400 and records no input command. |
| FR10 | Parser tests for `Started turn:` and `Steered turn:` output. |
| FR11 | HTTP test records exact `instance interrupt <id>` command and parses turn id. |
| FR12 | HTTP test records exact `instance stop <id>` command followed by status refresh. |
| FR13 | HTTP test records exact `instance delete <id> --yes` command for inactive delete success. |
| FR14 | HTTP test maps CLI return code 3 and active-delete stderr to HTTP 409. |
| FR15 | HTTP tests for invalid JSON on create and input routes. |
| FR16 | HTTP tests for `../bad`, absolute-path-like ids, and empty ids. |
| FR17 | Command runner tests for timeout, return code 2, return code 3, and return code 1 with blocked stderr. |
| FR18 | Service busy-guard unit test for duplicate start and duplicate per-instance mutations. |
| FR19 | Static page test verifies required controls and route references are present. |
| FR20 | Node standard-library UI state tests verify enabled and disabled states; manual browser smoke verifies the real page wiring. |
| FR21 | Code review checklist plus tests that all web actions go through the command runner. |
| FR22 | Existing focused service-mode gate and final full pytest run. |

## Test Boundaries

Use fakes at the CLI boundary, not below it, for web API tests.

The functional contract of the web layer is:

```text
HTTP request -> validation -> existing CLI command -> parsed JSON response
```

Therefore a fake command runner is the correct fast boundary for most Web API
tests. It records command arguments and returns stdout, stderr, return code, or
timeout. It must not fake route validation or response formatting.

Keep the existing service-mode integration tests as the proof that the CLI
commands themselves still control app-server lifecycle correctly.

## New Test File

Create:

```text
tests/test_web_management.py
tests/web_management_ui_state.test.js
```

`tests/test_web_management.py` should import
`tools/launcher/web_management.py` directly and test:

- parser functions
- host and id validation
- command error mapping
- HTTP route behavior through an in-process server
- static asset serving
- busy guard behavior

`tests/web_management_ui_state.test.js` should import
`tools/launcher/assets/web-management/app.js` through Node and test pure UI
state helpers. Use Node's built-in `assert` module only. Do not add a JavaScript
test framework.

Use Python standard library clients:

```python
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
```

Do not add a new web test framework for the MVP.

## Fake Command Runner Contract

The fake runner records every command as a list of strings:

```python
["instance", "list"]
["instance", "buddies"]
["instance", "status", "inst-pm-demo", "--json"]
["instance", "start", "--buddy", "pm"]
["instance", "input", "inst-pm-demo", "--text", "Advance the brief"]
["instance", "interrupt", "inst-pm-demo"]
["instance", "stop", "inst-pm-demo"]
["instance", "delete", "inst-pm-demo", "--yes"]
```

It returns a result object equivalent to:

```python
CommandResult(
    returncode=0,
    stdout="command stdout",
    stderr="",
    timed_out=False,
)
```

Timeouts must be represented explicitly rather than by sleeping in tests.

## Required Test Cases

### 1. Health Is Read Only

Route:

```text
GET /api/health
```

Expected response:

```json
{"ok": true}
```

Assertions:

- HTTP status is 200.
- Command runner call list is empty.

### 2. Buddies Come From CLI TSV

Fake command:

```text
instance buddies
```

Fake stdout:

```text
pm	PM	Own product iteration and track progression.
dev	Dev	Implement approved scope in project code.
```

Expected response:

```json
{
  "ok": true,
  "buddies": [
    {"id": "pm", "label": "PM", "scope": "Own product iteration and track progression."},
    {"id": "dev", "label": "Dev", "scope": "Implement approved scope in project code."}
  ]
}
```

Assertions:

- HTTP status is 200.
- Runner was called once with `["instance", "buddies"]`.

### 3. Empty Instance List Returns Empty Array

Fake command:

```text
instance list
```

Fake stdout:

```text
No BuddySwitch instances found.
Start one with: ./buddyswitch-codex instance start --buddy <buddy>
```

Expected response:

```json
{"ok": true, "instances": []}
```

### 4. Multi Instance List Parses Current Columns

Fake stdout:

```text
instance_id	buddy	status	app_server_health	thread_id	browser_port	updated_at	workspace_dir
inst-pm-demo	pm	active	healthy	thread-pm	9222	2026-05-24T10:00:00Z	/tmp/shared/instances/inst-pm-demo/workspace
inst-dev-demo	dev	inactive	unhealthy		9223	2026-05-24T10:01:00Z	/tmp/shared/instances/inst-dev-demo/workspace
```

Expected parsed fields:

- `browser_port` is integer `9222` or `9223` when present.
- missing `thread_id` is `null`.
- `app_server_health` remains the string `healthy` or `unhealthy`.

### 5. Status Preserves CLI JSON Shape

Route:

```text
GET /api/instances/inst-pm-demo/status
```

Fake command:

```text
instance status inst-pm-demo --json
```

Fake stdout:

```json
{
  "instance_id": "inst-pm-demo",
  "buddy": "pm",
  "status": "active",
  "workspace_dir": "/tmp/shared/instances/inst-pm-demo/workspace",
  "browser_port": 9222,
  "updated_at": "2026-05-24T10:00:00Z",
  "thread_id": "thread-pm",
  "app_server": {"healthy": true},
  "thread": {"status": "idle", "raw": {"id": "thread-pm"}}
}
```

Expected response wraps the parsed object as:

```json
{"ok": true, "instance": {}}
```

The nested `instance` object must preserve the same top-level keys.

### 6. Create Valid Buddy Starts And Refreshes

Route:

```text
POST /api/instances
```

Body:

```json
{"buddy": "pm"}
```

Expected commands:

```text
instance buddies
instance start --buddy pm
instance status inst-pm-demo --json
```

Fake start stdout:

```text
BuddySwitch instance: inst-pm-demo (pm)
Workspace: /tmp/shared/instances/inst-pm-demo/workspace
```

Expected response:

```json
{
  "ok": true,
  "instance_id": "inst-pm-demo",
  "instance": {
    "instance_id": "inst-pm-demo"
  }
}
```

### 7. Create Unknown Buddy Is Rejected Before Start

Body:

```json
{"buddy": "unknown"}
```

Expected:

- HTTP status is 400.
- response error code is `INVALID_BUDDY`.
- runner was called only for `instance buddies`.
- runner was not called for `instance start`.

### 8. Input Valid Text Delegates And Refreshes

Route:

```text
POST /api/instances/inst-pm-demo/input
```

Body:

```json
{"text": "Advance the PM brief"}
```

Expected commands:

```text
instance input inst-pm-demo --text Advance the PM brief
instance status inst-pm-demo --json
```

Fake input stdout:

```text
Started turn: turn-123
```

Expected response includes:

```json
{"ok": true, "action": "start", "turn_id": "turn-123"}
```

Repeat with:

```text
Steered turn: turn-456
```

Expected action is `steer`.

### 9. Input Empty Text Is Rejected

Bodies:

```json
{"text": ""}
```

```json
{"text": "   "}
```

Expected:

- HTTP status is 400.
- response error code is `EMPTY_INPUT`.
- runner call list has no `instance input`.

### 10. Non Steerable Input Maps To Conflict

Fake CLI result:

- return code: `1`
- stderr contains `Instance input blocked: active turn is not steerable`

Expected:

- HTTP status is 409.
- response error code is `LIFECYCLE_BLOCKED`.
- message is safe for display.

This test is required because the current CLI uses return code 1 for this
specific blocked state.

### 11. Interrupt Delegates To CLI

Route:

```text
POST /api/instances/inst-pm-demo/interrupt
```

Expected command:

```text
instance interrupt inst-pm-demo
```

Fake stdout:

```text
Interrupted turn: turn-123
```

Expected response:

```json
{"ok": true, "turn_id": "turn-123"}
```

### 12. Stop Delegates And Refreshes Status

Route:

```text
POST /api/instances/inst-pm-demo/stop
```

Expected commands:

```text
instance stop inst-pm-demo
instance status inst-pm-demo --json
```

Expected response includes the refreshed inactive instance object.

### 13. Delete Inactive Instance Delegates To CLI

Route:

```text
DELETE /api/instances/inst-pm-demo
```

Expected command:

```text
instance delete inst-pm-demo --yes
```

Fake stdout:

```text
Instance deleted: inst-pm-demo
```

Expected response:

```json
{"ok": true, "deleted": true, "instance_id": "inst-pm-demo"}
```

### 14. Active Delete Refusal Maps To Conflict

Fake CLI result:

- return code: `3`
- stderr: `Instance delete blocked: inst-pm-demo is active.`

Expected:

- HTTP status is 409.
- response error code is `LIFECYCLE_BLOCKED`.
- delete success shape is not returned.

### 15. Malformed JSON Is Rejected

Routes:

```text
POST /api/instances
POST /api/instances/inst-pm-demo/input
```

Body:

```text
{"buddy":
```

Expected:

- HTTP status is 400.
- response error code is `INVALID_JSON`.
- no mutating lifecycle command was run.

### 16. Traversal Instance Id Is Rejected

Routes:

```text
GET /api/instances/../bad/status
POST /api/instances/../bad/input
POST /api/instances/../bad/interrupt
POST /api/instances/../bad/stop
DELETE /api/instances/../bad
```

Expected:

- HTTP status is 400.
- response error code is `INVALID_INSTANCE_ID`.
- command runner was not called for lifecycle commands.

The same validation applies to absolute-path-like ids and empty ids.

### 17. CLI Error Mapping Is Structured

Cases:

| CLI Result | HTTP Status | Error Code |
| --- | --- | --- |
| return code 2 | 400 | `INVALID_REQUEST` |
| return code 3 | 409 | `LIFECYCLE_BLOCKED` |
| return code 1 with stderr starting `Instance input blocked:` | 409 | `LIFECYCLE_BLOCKED` |
| timeout | 504 | `COMMAND_TIMEOUT` |
| other non-zero return code | 502 | `COMMAND_FAILED` |

Each response must be JSON and must not include Python traceback text.

### 18. Busy Guard Blocks Duplicate Mutations

Cases:

- start is already busy, second create returns 409 `BUSY`
- `inst-pm-demo` is stopping, input returns 409 `BUSY`
- `inst-pm-demo` is deleting, interrupt returns 409 `BUSY`
- status and list still run while a mutation is busy

### 19. Static Page Loads Management Surface

Route:

```text
GET /
```

Expected HTML includes stable selectors for:

- API status
- refresh button
- buddy selector
- create button
- instance table
- selected instance detail panel
- instruction textarea
- send button
- interrupt button
- stop button
- delete button

The page must reference the API routes named in this test plan.

### 20. Manual Browser Smoke

Before the manual smoke, run:

```bash
node tests/web_management_ui_state.test.js
```

The Node test must cover:

- active healthy instance enables Send, Interrupt, and Stop, and disables Delete
- active unhealthy instance enables Stop only
- inactive instance enables Delete and disables Send and Interrupt
- empty instruction disables Send
- busy instance disables duplicate mutating actions
- route constants in `app.js` match the API contract in this test plan

Then run the browser smoke.

After implementation, run the local server:

```bash
./buddyswitch-codex web --host 127.0.0.1 --port 8765
```

Manual checks:

1. Open `http://127.0.0.1:8765/`.
2. Confirm API status shows ready.
3. Confirm buddy selector shows `market`, `pm`, `design`, `dev`, `test`.
4. Create a `pm` instance.
5. Confirm a row appears with instance id, buddy, status, app-server health,
   thread id, browser port, updated time, and workspace.
6. Select the row and send a short instruction.
7. Confirm send result shows started or steered turn.
8. Interrupt if a turn is active.
9. Stop the instance.
10. Confirm delete becomes available after stop.
11. Delete the inactive instance.

This manual smoke supplements automated UI state and API tests. It does not
replace them.

## Existing Regression Gate

Run these before declaring the web task complete:

```bash
python3 -m pytest tests/test_app_server_client.py -q
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'start_with_buddy_starts_app_server_service_and_returns or input_ or attach_ or stop_ or status_reports_app_server_health_and_thread_metadata or list_includes_app_server_health_and_thread_id or interrupt_' -q
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'instance_delete_blocks_active_app_server or data_cleanup_is_blocked_when_active_app_server_exists or reset_is_blocked_when_active_app_server_exists' -q
python3 -m pytest tests/test_browser_cockpit_launcher.py tests/test_cleanup_system.py -q
python3 -m pytest tests/test_web_management.py -q
node tests/web_management_ui_state.test.js
python3 -m pytest -q
```

## Review Checks

Before completion, review:

- All Web API actions call `buddyswitch-codex instance <command>`.
- No web code writes `instance.json` directly.
- No web code writes `buddyswitch/objects/**`.
- No web code writes `buddyswitch/local/buddybox/**`.
- No service-mode tests were skipped or weakened.
- No broad framework or generic workflow layer was added.
- The UI is a management screen, not a landing page.
