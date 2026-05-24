# Buddy Web Management MVP Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` before implementation, then use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete first local BuddySwitch web management page for creating, viewing, instructing, interrupting, stopping, and deleting buddy instances.

**Architecture:** Add a thin local HTTP server that serves one static management page and exposes JSON endpoints. Every lifecycle endpoint delegates to existing `./buddyswitch-codex instance <command>` commands through a small explicit command runner; lifecycle truth stays in the launcher and app-server service-mode path.

**Tech Stack:** Bash launcher entrypoint, Python standard library HTTP server, Python subprocess command runner, vanilla HTML/CSS/JavaScript, pytest/unittest.

---

## Scope

Implement the full MVP described in:

```text
docs/memo/2026-05-24-buddy-web-management-mvp.md
docs/spec/2026-05-24-buddy-web-management-mvp-objective.md
docs/spec/2026-05-24-buddy-web-management-mvp-test-plan.md
```

This plan is complete for the first product slice. It is not only an API spike.

## Non-Goals

Do not implement:

- remote bind or shared network access
- auth or user accounts
- direct app-server Unix socket access from the browser
- embedded terminal or TUI
- live transcript or log viewer
- model or settings switcher
- background job queue
- plugin or workflow framework
- direct writes under `buddyswitch/objects/**`
- direct writes under `buddyswitch/local/buddybox/**`
- compatibility support for removed top-level commands

## Files To Create

```text
tools/launcher/web_management.py
tools/launcher/assets/web-management/index.html
tools/launcher/assets/web-management/styles.css
tools/launcher/assets/web-management/app.js
tests/test_web_management.py
tests/web_management_ui_state.test.js
```

## Files To Modify

```text
buddyswitch-codex
```

Modify `buddyswitch-codex` only to:

- declare the web helper path
- include the helper in startup checks
- add help text for `buddyswitch-codex web`
- dispatch the top-level `web` command to `python3 tools/launcher/web_management.py`

Do not modify service-mode lifecycle behavior unless tests reveal a real bug
while implementing the web layer.

## Implementation Contract

### CLI Entrypoint

Add:

```bash
./buddyswitch-codex web
./buddyswitch-codex web --host 127.0.0.1 --port 8765
```

Default values:

```text
host: 127.0.0.1
port: 8765
```

Reject non-local hosts:

```bash
./buddyswitch-codex web --host 0.0.0.0
```

must exit non-zero with a clear error.

### HTTP Routes

Implement exactly:

```text
GET    /
GET    /static/styles.css
GET    /static/app.js
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

Return `404` JSON for unknown `/api/*` routes and a simple HTML 404 for
unknown static routes.

### JSON Response Shape

Success:

```json
{
  "ok": true
}
```

Failure:

```json
{
  "ok": false,
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Human-readable message."
  }
}
```

Never return Python tracebacks to the browser.

### Instance Id Validation

Use the same accepted pattern as the launcher:

```text
^inst-[A-Za-z0-9._-]+$
```

Reject invalid ids before invoking the command runner.

### Buddy Validation

For create, call:

```bash
./buddyswitch-codex instance buddies
```

Parse valid buddy ids from the first TSV column. Reject unknown buddy ids before
calling `instance start`.

### Command Runner

The command runner must call the root launcher with explicit argument lists:

```python
[str(repo_root / "buddyswitch-codex"), "instance", "list"]
[str(repo_root / "buddyswitch-codex"), "instance", "start", "--buddy", buddy]
```

Do not use `shell=True`.

Use operation-specific timeouts:

| Operation | Timeout Seconds |
| --- | --- |
| health route | no CLI command |
| buddies | 10 |
| list | 10 |
| status | 10 |
| start | 120 |
| input | 60 |
| interrupt | 30 |
| stop | 60 |
| delete | 60 |

### CLI Error Mapping

Map command results:

| CLI Result | HTTP Status | Error Code |
| --- | --- | --- |
| return code 0 | success status | no error |
| return code 2 | 400 | `INVALID_REQUEST` |
| return code 3 | 409 | `LIFECYCLE_BLOCKED` |
| return code 1 with stderr starting `Instance input blocked:` | 409 | `LIFECYCLE_BLOCKED` |
| timeout | 504 | `COMMAND_TIMEOUT` |
| other non-zero return code | 502 | `COMMAND_FAILED` |

### Busy Guard

Add one in-process busy guard:

- key `start` for create requests
- key `instance:<instance_id>` for input, interrupt, stop, and delete

Rules:

- duplicate create while `start` is busy returns `409 BUSY`
- duplicate mutation for the same instance returns `409 BUSY`
- list and status still run while mutations are busy
- no queue is added

## Task 1: Add Web Management Tests

**Files:**

- Create: `tests/test_web_management.py`

- [ ] **Step 1: Create the test file skeleton**

Add imports and helper classes:

```python
#!/usr/bin/env python3
"""Tests for the BuddySwitch local web management API."""

from __future__ import annotations

import json
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.responses = {}

    def add(self, args: list[str], result: object) -> None:
        self.responses[tuple(args)] = result

    def run(self, args: list[str], *, timeout_seconds: float) -> object:
        del timeout_seconds
        self.calls.append(list(args))
        key = tuple(args)
        if key not in self.responses:
            raise AssertionError(f"unexpected command: {args!r}")
        return self.responses[key]
```

- [ ] **Step 2: Add HTTP request helpers**

Add helpers that start the web service with `FakeRunner`, send JSON requests,
and return `(status, payload)`. Use `ThreadingHTTPServer` through the web
management module so route behavior is exercised through real HTTP parsing.

- [ ] **Step 3: Add parser tests**

Cover:

- buddies TSV parsing
- empty instance list output
- multi-row instance list output
- started turn output
- steered turn output
- interrupted turn output
- invalid JSON from `status --json`

- [ ] **Step 4: Add API route tests**

Add the required cases from
`docs/spec/2026-05-24-buddy-web-management-mvp-test-plan.md`.

- [ ] **Step 5: Add launcher dispatch tests**

Add tests that run:

```bash
./buddyswitch-codex help
./buddyswitch-codex web --host 0.0.0.0
```

Expected:

- help includes `buddyswitch-codex web`
- non-local host exits non-zero and prints a local-only error

- [ ] **Step 6: Run tests and confirm expected failure**

Run:

```bash
python3 -m pytest tests/test_web_management.py -q
```

Expected before implementation:

```text
FAILED
```

Failures should be missing module, missing route, or missing launcher dispatch.

## Task 2: Implement Python Web Management Module

**Files:**

- Create: `tools/launcher/web_management.py`

- [ ] **Step 1: Add data structures and validation**

Implement:

```python
@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
```

Implement:

```python
def validate_host(host: str) -> None
def validate_instance_id(instance_id: str) -> None
def parse_json_body(raw: bytes) -> dict[str, object]
```

`validate_host` accepts only `127.0.0.1`.

- [ ] **Step 2: Add parsers for current CLI output**

Implement:

```python
def parse_buddies_tsv(stdout: str) -> list[dict[str, object]]
def parse_instances_tsv(stdout: str) -> list[dict[str, object]]
def parse_start_instance_id(stdout: str) -> str
def parse_input_result(stdout: str) -> dict[str, object]
def parse_interrupt_result(stdout: str) -> dict[str, object]
```

These parsers must match the current output facts listed in the objective doc.

- [ ] **Step 3: Add command runner**

Implement a concrete runner:

```python
class LauncherCommandRunner:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def run(self, args: list[str], *, timeout_seconds: float) -> CommandResult:
        completed = subprocess.run(
            [str(self.repo_root / "buddyswitch-codex"), *args],
            cwd=str(self.repo_root),
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)
```

Catch `subprocess.TimeoutExpired` and return `CommandResult(124, stdout, stderr,
timed_out=True)`.

- [ ] **Step 4: Add service object**

Implement a small service class with methods:

```python
class WebManagementService:
    def health(self) -> tuple[int, dict[str, object]]
    def buddies(self) -> tuple[int, dict[str, object]]
    def instances(self) -> tuple[int, dict[str, object]]
    def status(self, instance_id: str) -> tuple[int, dict[str, object]]
    def create(self, body: dict[str, object]) -> tuple[int, dict[str, object]]
    def input(self, instance_id: str, body: dict[str, object]) -> tuple[int, dict[str, object]]
    def interrupt(self, instance_id: str) -> tuple[int, dict[str, object]]
    def stop(self, instance_id: str) -> tuple[int, dict[str, object]]
    def delete(self, instance_id: str) -> tuple[int, dict[str, object]]
```

Each mutating method must use the busy guard and delegate to the command runner.

- [ ] **Step 5: Add HTTP handler**

Implement a `BaseHTTPRequestHandler` subclass that:

- routes the exact paths in this plan
- serves `/`, `/static/styles.css`, and `/static/app.js`
- serializes API responses as JSON
- returns `405` for unsupported methods on known routes
- suppresses noisy default request logs unless a debug flag is added

- [ ] **Step 6: Add CLI parser and main**

Implement:

```python
def build_parser() -> argparse.ArgumentParser
def main(argv: list[str] | None = None) -> int
```

The parser accepts `--host` and `--port`. `main` validates host, starts the
HTTP server, prints the local URL, and runs until interrupted.

- [ ] **Step 7: Run focused tests**

Run:

```bash
python3 -m pytest tests/test_web_management.py -q
```

Expected after this task:

```text
PASS
```

Static UI tests may still fail until Task 4 if assets are not created yet.

## Task 3: Add Top-Level Web Command

**Files:**

- Modify: `buddyswitch-codex`

- [ ] **Step 1: Add helper path**

Near the other helper variables, add:

```bash
WEB_MANAGEMENT_HELPER="${REPO_ROOT}/tools/launcher/web_management.py"
```

Include it in the helper existence check.

- [ ] **Step 2: Add help text**

Add usage line:

```text
buddyswitch-codex web [--host 127.0.0.1] [--port 8765]
```

Add command description:

```text
web      Start the local BuddySwitch web management page.
```

- [ ] **Step 3: Add dispatch**

In `main()`, add:

```bash
web)
  shift || true
  python3 "${WEB_MANAGEMENT_HELPER}" "$@"
  ;;
```

- [ ] **Step 4: Run launcher tests**

Run:

```bash
python3 -m pytest tests/test_web_management.py -q
./buddyswitch-codex help | rg "buddyswitch-codex web"
```

Expected:

- web management tests pass
- help output contains the web command

## Task 4: Add Static One-Page UI

**Files:**

- Create: `tools/launcher/assets/web-management/index.html`
- Create: `tools/launcher/assets/web-management/styles.css`
- Create: `tools/launcher/assets/web-management/app.js`

- [ ] **Step 1: Add HTML structure**

The HTML must include stable selectors:

```html
<div id="api-status" data-testid="api-status"></div>
<button id="refresh-button" data-testid="refresh-button" type="button">Refresh</button>
<select id="buddy-select" data-testid="buddy-select"></select>
<button id="create-button" data-testid="create-button" type="button">Create</button>
<table id="instances-table" data-testid="instances-table"></table>
<section id="instance-detail" data-testid="instance-detail"></section>
<textarea id="instruction-input" data-testid="instruction-input"></textarea>
<button id="send-button" data-testid="send-button" type="button">Send</button>
<button id="interrupt-button" data-testid="interrupt-button" type="button">Interrupt</button>
<button id="stop-button" data-testid="stop-button" type="button">Stop</button>
<button id="delete-button" data-testid="delete-button" type="button">Delete</button>
<div id="operation-result" data-testid="operation-result"></div>
```

- [ ] **Step 2: Add CSS for a management surface**

Use a compact operational layout:

- top bar
- control strip
- instance table
- detail panel
- clear disabled states
- row busy state
- error and success message area

Do not build a hero section, marketing page, decorative dashboard, or nested
card layout.

- [ ] **Step 3: Add vanilla JavaScript API client**

Implement functions:

```javascript
async function apiRequest(path, options = {}) {}
async function refreshAll() {}
async function createInstance() {}
async function sendInstruction() {}
async function interruptInstance() {}
async function stopInstance() {}
async function deleteInstance() {}
```

Use the exact API routes from this plan.

Expose pure helpers for Node tests without changing browser behavior:

```javascript
const BuddyWeb = (() => {
  function isHealthy(instance) {
    if (!instance) {
      return false;
    }
    if (instance.app_server && typeof instance.app_server.healthy === "boolean") {
      return instance.app_server.healthy;
    }
    return instance.app_server_health === "healthy";
  }

  function deriveActionState(instance, instructionText, busy) {
    const selected = Boolean(instance);
    const active = selected && instance.status === "active";
    const inactive = selected && instance.status === "inactive";
    const healthy = active && isHealthy(instance);
    const hasInstruction = typeof instructionText === "string" && instructionText.trim().length > 0;
    const blocked = Boolean(busy);

    return {
      canSend: healthy && hasInstruction && !blocked,
      canInterrupt: healthy && !blocked,
      canStop: active && !blocked,
      canDelete: inactive && !blocked
    };
  }

  return { deriveActionState };
})();

if (typeof window !== "undefined") {
  window.BuddyWeb = BuddyWeb;
}

if (typeof module !== "undefined") {
  module.exports = BuddyWeb;
}
```

- [ ] **Step 4: Add UI state rules**

Implement:

- active and healthy enables Send, Interrupt, Stop
- active but unhealthy enables Stop only
- inactive enables Delete and disables Send and Interrupt
- busy rows disable duplicate mutating actions
- empty instruction disables Send

- [ ] **Step 5: Run UI/static tests**

Run:

```bash
python3 -m pytest tests/test_web_management.py -q
```

Expected:

```text
PASS
```

## Task 5: Add UI State Tests

**Files:**

- Create: `tests/web_management_ui_state.test.js`
- Modify: `tools/launcher/assets/web-management/app.js`

- [ ] **Step 1: Add Node test script**

Use Node built-in `assert` only:

```javascript
const assert = require("assert");
const BuddyWeb = require("../tools/launcher/assets/web-management/app.js");

function state(instance, instructionText = "Advance brief", busy = false) {
  return BuddyWeb.deriveActionState(instance, instructionText, busy);
}

const activeHealthy = {
  status: "active",
  app_server_health: "healthy",
  app_server: { healthy: true }
};

assert.deepStrictEqual(state(activeHealthy), {
  canSend: true,
  canInterrupt: true,
  canStop: true,
  canDelete: false
});

assert.strictEqual(state(activeHealthy, "").canSend, false);

const activeUnhealthy = {
  status: "active",
  app_server_health: "unhealthy",
  app_server: { healthy: false }
};

assert.deepStrictEqual(state(activeUnhealthy), {
  canSend: false,
  canInterrupt: false,
  canStop: true,
  canDelete: false
});

const inactive = {
  status: "inactive",
  app_server_health: "unhealthy",
  app_server: { healthy: false }
};

assert.deepStrictEqual(state(inactive), {
  canSend: false,
  canInterrupt: false,
  canStop: false,
  canDelete: true
});

assert.deepStrictEqual(state(activeHealthy, "Advance brief", true), {
  canSend: false,
  canInterrupt: false,
  canStop: false,
  canDelete: false
});
```

- [ ] **Step 2: Run UI state tests**

```bash
node tests/web_management_ui_state.test.js
```

Expected:

```text
no output and exit code 0
```

## Task 6: Run Focused Service-Mode Regression Gate

**Files:**

- No edits expected.

- [ ] **Step 1: Run app-server client tests**

```bash
python3 -m pytest tests/test_app_server_client.py -q
```

Expected:

```text
9 passed
```

- [ ] **Step 2: Run launcher service-mode group**

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'start_with_buddy_starts_app_server_service_and_returns or input_ or attach_ or stop_ or status_reports_app_server_health_and_thread_metadata or list_includes_app_server_health_and_thread_id or interrupt_' -q
```

Expected:

```text
passed
```

- [ ] **Step 3: Run active guard group**

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'instance_delete_blocks_active_app_server or data_cleanup_is_blocked_when_active_app_server_exists or reset_is_blocked_when_active_app_server_exists' -q
```

Expected:

```text
passed
```

- [ ] **Step 4: Run browser and cleanup tests**

```bash
python3 -m pytest tests/test_browser_cockpit_launcher.py tests/test_cleanup_system.py -q
```

Expected:

```text
passed
```

## Task 7: Manual Product Smoke

**Files:**

- No edits expected unless the smoke reveals a real bug.

- [ ] **Step 1: Start the web server**

```bash
./buddyswitch-codex web --host 127.0.0.1 --port 8765
```

Expected output includes:

```text
BuddySwitch web management: http://127.0.0.1:8765/
```

- [ ] **Step 2: Open the page**

Open:

```text
http://127.0.0.1:8765/
```

- [ ] **Step 3: Verify product flow**

Check:

- API status becomes ready
- buddies load
- create `pm` instance works
- table shows the new row
- detail panel shows thread id, workspace, health, and browser port
- sending instruction works
- interrupt returns a visible result when a turn is active
- stop changes the row to inactive
- delete is enabled only after stop
- delete removes the row

- [ ] **Step 4: Stop the web server**

Use `Ctrl-C`. Confirm no required long-running test session remains.

## Task 8: Full Verification And Review

**Files:**

- No edits expected unless verification finds a real bug.

- [ ] **Step 1: Run full tests**

```bash
python3 -m pytest -q
node tests/web_management_ui_state.test.js
```

Expected:

```text
passed
node exits 0
```

- [ ] **Step 2: Check diff**

```bash
git diff --stat
git diff -- buddyswitch-codex tools/launcher/web_management.py tools/launcher/assets/web-management tests/test_web_management.py
```

- [ ] **Step 3: Review scope**

Confirm:

- only the web entrypoint, web module, static UI, tests, and docs changed
- no service-mode tests were skipped or weakened
- no lifecycle logic was duplicated into web code
- no direct writes to runtime object or buddybox paths were added
- no framework dependency was added
- the UI is one management page

- [ ] **Step 4: Run final status**

```bash
git status --short --branch
```

Expected:

```text
## clean-runtime-env
```

plus only intentional modified or added files for this task.

## Completion Report Requirements

The final implementation report must include:

- what product flow is now available
- root design decision: local Web API wraps existing CLI
- files changed
- focused test results
- full `python3 -m pytest -q` result
- manual smoke result or clear blocker
- review conclusion
- any remaining risk or user confirmation needed
