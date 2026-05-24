# Buddy Web Management MVP Memo

Date: 2026-05-24

## Purpose

Build a simple local web page for managing BuddySwitch buddy instances.

The product goal is practical control from a browser:

- create a buddy instance
- see multiple buddy instances in one place
- send instructions to a running instance
- interrupt a running turn when needed
- stop an instance
- delete an inactive instance

The first version should be clear and small. It should wrap the existing
BuddySwitch CLI/service-mode control path instead of introducing a new
lifecycle implementation.

## Current Code Facts

Current CLI surface:

```bash
./buddyswitch-codex instance buddies
./buddyswitch-codex instance start --buddy <buddy>
./buddyswitch-codex instance input <instance-id> --text <text>
./buddyswitch-codex instance attach <instance-id>
./buddyswitch-codex instance stop <instance-id>
./buddyswitch-codex instance status <instance-id> --json
./buddyswitch-codex instance interrupt <instance-id>
./buddyswitch-codex instance list [--buddy <buddy>]
./buddyswitch-codex instance delete <instance-id> --yes
```

The service-mode path is already the main path:

- `start` creates a new instance, starts runtime broker, browser cockpit when
  required, Codex app-server, and one app-server thread.
- `input` validates the instance, checks app-server health, then starts an idle
  turn or steers an active turn.
- `interrupt` validates health and interrupts the active in-progress turn.
- `stop` stops app-server, runtime broker, browser cockpit, and marks the
  instance inactive.
- `delete` refuses active instances and deletes only inactive instance roots.
- `status --json` returns instance metadata, app-server health, thread id, and
  thread status.
- `list` returns a tab-separated table with instance id, buddy, status,
  app-server health, thread id, browser port, updated time, and workspace.

Verification state after the clean-runtime-env repair:

```text
python3 -m pytest -q
613 passed, 1363 subtests passed
```

## Recommended First Architecture

Use a local Web API wrapper around the existing CLI.

```text
Browser UI
  -> local BuddySwitch Web API on 127.0.0.1
    -> subprocess calls to ./buddyswitch-codex instance commands
      -> existing launcher/runtime lock/app-server control path
        -> Codex app-server per buddy instance
```

This is intentionally not a terminal UI. The browser never opens a shell for the
user. The local Web API starts background subprocesses, captures stdout/stderr,
maps exit codes to JSON responses, and returns structured status back to the UI.

This is the cleanest first slice because it reuses the tested path and avoids
splitting lifecycle truth between CLI and web code.

Do not let the browser connect directly to Codex app-server Unix sockets.
Do not directly mutate `buddyswitch/objects/**`.
Do not directly mutate `buddyswitch/local/buddybox/**`.

## Web API MVP

The API should bind to `127.0.0.1` by default.

Proposed start command:

```bash
./buddyswitch-codex web
```

Optional flags:

```bash
./buddyswitch-codex web --host 127.0.0.1 --port 8765
```

Non-local bind should either be rejected or require an explicit future flag.

### Endpoints

#### `GET /api/health`

Purpose: prove the web server is alive.

Response:

```json
{"ok": true}
```

#### `GET /api/buddies`

CLI backing:

```bash
./buddyswitch-codex instance buddies
```

Response:

```json
{
  "ok": true,
  "buddies": ["pm", "design", "dev", "market", "test"]
}
```

#### `GET /api/instances`

CLI backing:

```bash
./buddyswitch-codex instance list
```

First version may parse the current TSV output. A later cleanup can add
`instance list --json`, but the MVP does not require that before proving the
page.

Response:

```json
{
  "ok": true,
  "instances": [
    {
      "instance_id": "inst-pm-20260524-demo",
      "buddy": "pm",
      "status": "active",
      "app_server_health": "healthy",
      "thread_id": "thread-demo",
      "browser_port": 9222,
      "updated_at": "2026-05-24T10:00:00Z",
      "workspace_dir": "/Users/example/.codex-buddyswitch/instances/inst-pm-20260524-demo/workspace"
    }
  ]
}
```

#### `GET /api/instances/<instance_id>/status`

CLI backing:

```bash
./buddyswitch-codex instance status <instance-id> --json
```

Response should preserve the current status JSON shape:

```json
{
  "ok": true,
  "instance": {
    "instance_id": "inst-pm-20260524-demo",
    "buddy": "pm",
    "status": "active",
    "workspace_dir": "/Users/example/.codex-buddyswitch/instances/inst-pm-20260524-demo/workspace",
    "browser_port": 9222,
    "updated_at": "2026-05-24T10:00:00Z",
    "thread_id": "thread-demo",
    "app_server": {"healthy": true},
    "thread": {"status": "idle", "raw": {}}
  }
}
```

#### `POST /api/instances`

Request:

```json
{"buddy": "pm"}
```

CLI backing:

```bash
./buddyswitch-codex instance start --buddy pm
```

Behavior:

- validate buddy id before execution
- run synchronously for MVP with a clear timeout
- parse the created instance id from stdout
- call `status --json` for the new instance before returning

Response:

```json
{
  "ok": true,
  "instance_id": "inst-pm-20260524-demo",
  "instance": {}
}
```

#### `POST /api/instances/<instance_id>/input`

Request:

```json
{"text": "Advance the PM brief"}
```

CLI backing:

```bash
./buddyswitch-codex instance input <instance-id> --text "Advance the PM brief"
```

Behavior:

- reject empty text
- reject malformed instance ids
- return whether the CLI started or steered a turn when parseable
- refresh status after success

Response:

```json
{
  "ok": true,
  "action": "start",
  "turn_id": "turn-demo",
  "instance": {}
}
```

#### `POST /api/instances/<instance_id>/interrupt`

CLI backing:

```bash
./buddyswitch-codex instance interrupt <instance-id>
```

Response:

```json
{
  "ok": true,
  "turn_id": "turn-demo",
  "instance": {}
}
```

#### `POST /api/instances/<instance_id>/stop`

CLI backing:

```bash
./buddyswitch-codex instance stop <instance-id>
```

Response:

```json
{
  "ok": true,
  "instance": {}
}
```

#### `DELETE /api/instances/<instance_id>`

CLI backing:

```bash
./buddyswitch-codex instance delete <instance-id> --yes
```

Behavior:

- rely on existing CLI guard to refuse active instances
- map active-instance refusal to HTTP `409 Conflict`
- delete only inactive instance roots

Response:

```json
{
  "ok": true,
  "deleted": true,
  "instance_id": "inst-pm-20260524-demo"
}
```

### Error Mapping

Map CLI return codes and stderr into simple JSON:

```json
{
  "ok": false,
  "error": {
    "code": "INSTANCE_ACTIVE",
    "message": "Instance delete blocked: inst-pm-20260524-demo is active."
  }
}
```

Suggested mapping:

- return code `0`: success
- return code `2`: bad request or invalid input
- return code `3`: valid request blocked by current lifecycle state
- any other return code: command failure
- timeout: command timeout with captured operation name

Do not expose raw stack traces to the browser.

## Web Server Implementation Shape

Keep the first implementation local and dependency-light.

Recommended first module:

```text
tools/launcher/web_management.py
```

Responsibilities:

- serve the static HTML/CSS/JS page
- expose the JSON API
- run `./buddyswitch-codex` subprocess commands
- parse stdout into stable response objects
- preserve stderr in structured error responses
- enforce local-only bind by default
- validate JSON request bodies
- validate instance ids and buddy ids before invoking CLI

Use Python standard library HTTP support unless an existing project web
framework becomes necessary. There is no current app framework dependency in
this repo, and adding one is not needed for the first slice.

The command runner should be small and explicit. It should not become a generic
workflow engine.

## Concurrency Rules

The existing CLI already uses the runtime lock for start, stop, delete, reset,
and cleanup paths.

The Web API should still add a small in-process busy guard:

- only one start request should run at a time
- only one mutating action per instance should run at a time
- status/list should stay available while actions are running
- input while stop/delete is in progress should return a clear busy/stopped
  error

This should be a simple in-memory guard for the local server process, not a
general queue system.

## UI MVP

The UI should be an actual management surface, not a landing page.

### Layout

Use one screen:

```text
Top bar:
  BuddySwitch Web Management
  API status
  Refresh

Left/Top control strip:
  Buddy selector
  Create instance button
  Optional buddy filter

Main table:
  instance id
  buddy
  status
  app-server health
  thread status
  browser port
  updated time
  actions

Right/detail panel or lower panel:
  selected instance metadata
  workspace path
  thread id
  latest operation result
  instruction text area
  Send button
  Interrupt button
  Stop button
  Delete button
```

For the first version, a table plus a detail panel is enough. Do not build a
dashboard, charts, logs, transcript viewer, daemon UI, or multi-page app.

### Instance Row States

Active and healthy:

- show green/ok health
- enable Send, Interrupt, Stop
- disable Delete

Active but unhealthy:

- show warning
- enable Stop
- disable Send and Interrupt
- keep Delete disabled until stopped or inactive

Inactive:

- show inactive
- disable Send and Interrupt
- allow Delete
- Stop can be hidden or disabled

Busy:

- show row-level spinner
- disable duplicate mutating actions for that row

### Send Instruction Flow

User selects an active healthy instance, types a message, and clicks Send.

UI behavior:

- reject empty text client-side
- disable Send while the request is in flight
- show whether the backend started a new turn or steered an active turn
- refresh the selected instance status after success
- show clear error text for non-steerable active turns, unhealthy instances, or
  missing thread id

### Stop And Delete Flow

Stop:

- available for active or unhealthy instances
- after success, refresh status and list

Delete:

- visible for all rows but disabled for active rows
- requires a simple browser confirmation
- backend still enforces the active-instance guard
- after success, remove the row from the table

## First-Version Non-Goals

Do not include these in the MVP:

- remote network access
- user accounts or shared multi-user auth
- direct browser connection to Codex app-server sockets
- embedded terminal or TUI in the browser
- live logs or turn transcript viewer
- daemon coordination controls
- message prioritization
- model/settings switching
- background job queue
- generic plugin/action framework

These can be revisited after the basic management page is verified.

## Test Plan

Add tests before implementation.

API tests:

- `GET /api/buddies` returns buddies from the manifest through CLI backing.
- `GET /api/instances` returns rows parsed from `instance list`.
- `GET /api/instances/<id>/status` delegates to `status --json`.
- `POST /api/instances` validates buddy id and delegates to `start`.
- `POST /api/instances/<id>/input` rejects empty text and delegates to
  `input --text`.
- `POST /api/instances/<id>/interrupt` delegates to `interrupt`.
- `POST /api/instances/<id>/stop` delegates to `stop`.
- `DELETE /api/instances/<id>` delegates to `delete --yes` and maps active
  refusal to conflict.
- Mutating routes reject malformed JSON.
- Path traversal instance ids are rejected before CLI invocation.
- Default bind address is `127.0.0.1`.

UI tests or manual checks:

- page loads and calls `/api/health`
- buddy selector renders
- create button creates an instance and adds a row
- selecting a row opens the detail panel
- Send is enabled only for active healthy rows
- Delete is disabled for active rows and enabled for inactive rows
- Stop refreshes row state

Regression gate to keep before/after web work:

```bash
python3 -m pytest tests/test_app_server_client.py -q
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'start_with_buddy_starts_app_server_service_and_returns or input_ or attach_ or stop_ or status_reports_app_server_health_and_thread_metadata or list_includes_app_server_health_and_thread_id or interrupt_' -q
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'instance_delete_blocks_active_app_server or data_cleanup_is_blocked_when_active_app_server_exists or reset_is_blocked_when_active_app_server_exists' -q
python3 -m pytest tests/test_browser_cockpit_launcher.py tests/test_cleanup_system.py -q
python3 -m pytest -q
```

## Delivery Slice

Recommended first slice:

1. Add Web API tests with a fake CLI runner.
2. Implement local Web API command wrapper.
3. Add static one-page UI.
4. Run focused API/UI tests.
5. Run the existing service-mode gate.
6. Run full pytest.

Done means a product manager can open a local page, create multiple buddy
instances, send instructions, stop them, and delete inactive ones without using
the terminal directly.
