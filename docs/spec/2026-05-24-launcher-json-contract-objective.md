# Launcher JSON Contract Objective

Date: 2026-05-24

## Goal

Clean the BuddySwitch web management boundary by adding a machine-readable
JSON contract to the launcher commands that the Web API already uses.

The target chain remains:

```text
Browser UI -> local Web API -> ./buddyswitch-codex instance ... -> existing lifecycle
```

The Web API must stop parsing human CLI text and TSV tables. It should consume
explicit launcher JSON responses instead.

## Current Code Facts

The current web management MVP is implemented in:

```text
buddyswitch-codex
tools/launcher/web_management.py
tools/launcher/assets/web-management/index.html
tools/launcher/assets/web-management/styles.css
tools/launcher/assets/web-management/app.js
tests/test_web_management.py
tests/web_management_ui_state.test.js
```

The current launcher lifecycle implementation is split across:

```text
buddyswitch-codex
tools/launcher/instance.sh
tools/launcher/app_server.sh
tools/launcher/app_server.py
scripts/env_manifest.py
```

Current web calls use the existing CLI commands:

```text
instance buddies
instance list
instance status <instance-id> --json
instance start --buddy <buddy>
instance input <instance-id> --text <text>
instance interrupt <instance-id>
instance stop <instance-id>
instance delete <instance-id> --yes
```

Only `instance status <instance-id> --json` is already structured. The Web API
currently parses:

- buddy TSV rows from `instance buddies`
- instance list TSV rows from `instance list`
- `BuddySwitch instance: <id>` from start output
- `Started turn:` / `Steered turn:` from input output
- `Interrupted turn:` from interrupt output

Those parsers are the current cleanup target.

## Current Bottleneck

The Web API is correctly thin, but its CLI boundary is still coupled to
human-readable command output. That is brittle because copy changes or table
formatting changes can break Web behavior.

The core bottleneck is the missing machine contract between the Web API and the
launcher.

## Required Direction

Add `--json` to the launcher instance commands that the Web API consumes:

```text
instance buddies --json
instance list [--buddy <buddy>] --json
instance start --buddy <buddy> --json
instance input <instance-id> --text <text> --json
instance interrupt <instance-id> --json
instance stop <instance-id> --json
instance delete <instance-id> --yes --json
```

Keep the existing human output when `--json` is not passed.

Keep `instance status <instance-id> --json` as the canonical status payload.
Do not redesign the status shape in this task.

## JSON Contract

### Buddies

Command:

```bash
./buddyswitch-codex instance buddies --json
```

Success stdout:

```json
{
  "buddies": [
    {
      "id": "pm",
      "label": "PM",
      "scope": "Own product iteration and track progression."
    }
  ]
}
```

### Instance List

Command:

```bash
./buddyswitch-codex instance list --json
```

Success stdout when empty:

```json
{
  "instances": []
}
```

Success stdout when instances exist:

```json
{
  "instances": [
    {
      "instance_id": "inst-pm-demo",
      "buddy": "pm",
      "status": "active",
      "app_server_health": "healthy",
      "thread_id": "thread-demo",
      "browser_port": 9222,
      "updated_at": "2026-05-24T10:00:00Z",
      "workspace_dir": "/tmp/shared/instances/inst-pm-demo/workspace"
    }
  ]
}
```

The list payload is a summary optimized for table rendering. Full selected
instance detail remains `instance status <id> --json`.

### Start

Command:

```bash
./buddyswitch-codex instance start --buddy pm --json
```

Success stdout:

```json
{
  "instance_id": "inst-pm-demo",
  "buddy": "pm",
  "workspace_dir": "/tmp/shared/instances/inst-pm-demo/workspace",
  "project_workspace_dir": "/tmp/shared/project/workspace",
  "instance_record": "/tmp/shared/instances/inst-pm-demo/instance.json"
}
```

The command still performs the same lifecycle work as the current human command.
Only stdout changes when `--json` is passed.

### Input

Command:

```bash
./buddyswitch-codex instance input inst-pm-demo --text "Advance the brief" --json
```

Success stdout for a new turn:

```json
{
  "instance_id": "inst-pm-demo",
  "thread_id": "thread-demo",
  "action": "start",
  "turn_id": "turn-demo"
}
```

Success stdout for steering an active turn:

```json
{
  "instance_id": "inst-pm-demo",
  "thread_id": "thread-demo",
  "action": "steer",
  "turn_id": "turn-demo",
  "expected_turn_id": "turn-demo"
}
```

### Interrupt

Command:

```bash
./buddyswitch-codex instance interrupt inst-pm-demo --json
```

Success stdout:

```json
{
  "instance_id": "inst-pm-demo",
  "thread_id": "thread-demo",
  "turn_id": "turn-demo"
}
```

### Stop

Command:

```bash
./buddyswitch-codex instance stop inst-pm-demo --json
```

Success stdout:

```json
{
  "instance_id": "inst-pm-demo",
  "status": "inactive"
}
```

### Delete

Command:

```bash
./buddyswitch-codex instance delete inst-pm-demo --yes --json
```

Success stdout:

```json
{
  "instance_id": "inst-pm-demo",
  "deleted": true
}
```

Delete without `--yes` remains the human preview path. Web does not call the
preview path.

## Web API Contract After Cleanup

The browser-facing HTTP API remains unchanged:

```text
GET    /api/health
GET    /api/buddies
GET    /api/instances
GET    /api/instances/<instance_id>/status
POST   /api/instances
POST   /api/instances/<instance_id>/input
POST   /api/instances/<instance_id>/interrupt
POST   /api/instances/<instance_id>/stop
DELETE /api/instances/<instance_id>
```

Only the Web-to-launcher boundary changes.

The Web API should call:

```text
instance buddies --json
instance list --json
instance status <instance-id> --json
instance start --buddy <buddy> --json
instance input <instance-id> --text <text> --json
instance interrupt <instance-id> --json
instance stop <instance-id> --json
instance delete <instance-id> --yes --json
```

The Web API keeps responsibility for:

- HTTP route validation
- local bind validation
- JSON request body validation
- `ok: true` and structured HTTP error envelopes
- HTTP error mapping from launcher exit codes
- in-process busy guard
- status refresh after create, input, interrupt, and stop

The launcher keeps responsibility for:

- instance lifecycle
- app-server lifecycle
- browser cockpit lifecycle
- runtime lock safety
- delete safety
- runtime state mutation

## Non-Goals

Do not implement:

- a generic launcher SDK
- dynamic command discovery
- automatic HTTP proxying for every launcher command
- a plugin system
- a workflow engine
- a queue
- a remote management server
- an auth system
- direct app-server socket access from the browser
- direct writes under `buddyswitch/objects/**`
- direct writes under `buddyswitch/local/buddybox/**`
- a second lifecycle path in Python
- a compatibility dual path where Web accepts both legacy text and new JSON

## Compatibility Rule

Human CLI output is preserved by default. `--json` is opt-in.

The Web API is allowed to rely on the JSON contract only. After cleanup, it
should fail clearly with `502 COMMAND_FAILED` if a launcher command that should
return JSON emits malformed JSON.

## Forward Rule

This task should replace the brittle Web parsing path. Do not keep long-lived
fallbacks that parse the old text output for Web.

## Definition Of Done

The task is done when:

1. The listed launcher commands support the JSON contract.
2. Existing human CLI output remains covered by regression tests.
3. The Web API calls the JSON contract for all launcher-backed routes.
4. Web text and TSV parsers are removed.
5. Web API tests prove malformed launcher JSON returns a structured failure.
6. Existing service-mode behavior remains green.
7. Full test suite passes.
8. Final review confirms one lifecycle truth, no direct runtime path writes, and
   no speculative framework or abstraction.
