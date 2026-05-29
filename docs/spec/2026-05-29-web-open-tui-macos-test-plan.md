# Web Open TUI macOS Test Plan

Date: 2026-05-29

## Objective

Verify that BuddySwitch Web Management can open the selected active buddy instance in macOS Terminal.app through a local Web API route, while preserving the existing launcher `instance attach <instance-id>` command as the only attach surface.

This is a Web Management product-experience task. The tests must prove the browser cannot submit arbitrary commands, invalid instance states never touch Terminal, and automated verification never opens a real Terminal window.

## Current Bottleneck

The current Web Management UI can create, inspect, steer, stop, resume, clear, and delete instances, but it cannot hand the selected instance to the existing Codex TUI attach path. Users must copy the attach command manually from CLI output or know the command shape.

The launcher already owns the attach behavior:

```bash
./buddyswitch-codex instance attach <instance-id>
```

The bottleneck is only the missing Web Management bridge from selected instance to macOS Terminal.app.

## Scope

### In Scope

- `POST /api/instances/<instance-id>/open-tui` in `tools/launcher/web_management.py`.
- macOS-only `osascript` Terminal.app opener behind a fakeable test seam.
- Server-side construction of:

```bash
cd <repo-root> && ./buddyswitch-codex instance attach <instance-id>
```

- Security checks for this sensitive POST route:
  - `Content-Type: application/json`
  - `X-BuddySwitch-Web: 1`
  - local `Host` and same-origin `Origin` checks where present
  - no arbitrary command accepted from the request body
- Frontend `Open TUI` CTA for the selected instance.
- Copy-command fallback after Terminal open failure or unsupported platform.
- Automated tests that use fake runners/openers and do not open Terminal.

### Out Of Scope

- Launcher `attach-open` command.
- Changes to `instance attach` behavior.
- Daemon, runtime broker, app-server transport, task runtime, or thread bootstrap changes.
- Linux or Windows terminal support.
- Terminal selector settings.
- New page, wizard, modal flow, plugin system, or generic opener registry.

## Functional Requirements

FR1. The launcher public command surface remains unchanged. `attach-open` must not be added.

FR2. Web API exposes exactly:

```http
POST /api/instances/<instance-id>/open-tui
```

FR3. The route validates `instance-id` before fetching status or invoking the opener.

FR4. The route requires JSON content type and `X-BuddySwitch-Web: 1` before fetching status or invoking the opener.

FR5. The route rejects non-local `Host` and non-local / cross-host `Origin` values when those headers are present.

FR6. The route rejects request bodies with arbitrary fields, including `command`.

FR7. The route fetches current instance status through existing launcher status behavior.

FR8. The route blocks inactive instances before invoking the opener and returns a structured error with user-facing message `Resume this instance first.`

FR9. The route blocks unhealthy app-server instances before invoking the opener and returns `Instance is unhealthy.`

FR10. The route blocks missing thread ids before invoking the opener and returns `No thread to attach.`

FR11. The route blocks unsupported OS before invoking the opener and returns a structured error with the copyable attach command.

FR12. On macOS with active, healthy, thread-present status, the route invokes Terminal.app through `osascript` using the server-built attach command.

FR13. API success means only that the Terminal open request was issued. The success response includes:

- `ok: true`
- `instance_id`
- `command`
- `terminal: "Terminal.app"`

FR14. If `osascript` fails or times out, the route returns `Could not open Terminal.` and includes the copyable command.

FR15. The frontend renders an `Open TUI` CTA in the selected instance action area.

FR16. The frontend enables `Open TUI` only when the selected instance is active, app-server healthy, and has a thread id.

FR17. The frontend disabled-state copy is:

- inactive: `Resume this instance first.`
- unhealthy: `Instance is unhealthy.`
- missing thread: `No thread to attach.`

FR18. Clicking `Open TUI` shows `Opening...`, then `Terminal opened.` on success.

FR19. Failure shows `Could not open Terminal.` and exposes `Copy command`.

FR20. The UI keeps the current quiet local-control-console style and does not add heavy visual effects or a new flow.

## Test Coverage Matrix

| Requirement | Primary Verification |
| --- | --- |
| FR1 | Python unit/static test against launcher source/help surface plus review scan |
| FR2 | `tests/test_web_management.py` route test |
| FR3 | `tests/test_web_management.py` invalid id test |
| FR4 | `tests/test_web_management.py` missing header/content-type tests |
| FR5 | `tests/test_web_management.py` bad host/origin tests |
| FR6 | `tests/test_web_management.py` arbitrary body field test |
| FR7 | `tests/test_web_management.py` ordered fake runner status call |
| FR8-FR10 | `tests/test_web_management.py` blocked-state tests with opener call count |
| FR11 | `tests/test_web_management.py` unsupported platform test |
| FR12-FR14 | `tests/test_web_management.py` fake opener success/failure tests |
| FR15 | `tests/web_management_ui_contract.test.js` required ids |
| FR16-FR17 | `tests/web_management_ui_state.test.js` state helper tests |
| FR18-FR19 | `tests/web_management_ui_contract.test.js` route/header/copy strings plus manual browser check |
| FR20 | static contract, CSS review, browser/manual check |

## Automated Test Plan

### 1. Backend Route And Opener Contract

File: `tests/test_web_management.py`

Add tests that instantiate `WebManagementService` with:

- `OrderedRunner` or `FakeRunner` for launcher status calls;
- fake opener callable that records commands instead of opening Terminal;
- explicit platform override (`darwin`, `linux`).

Focused command:

```bash
PATH=/Users/chen/miniconda3/bin:$PATH PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_web_management.py -q
```

Expected:

- all Web Management API tests pass;
- no real Terminal window opens;
- fake opener call count proves blocked states do not invoke Terminal;
- success payload includes a copyable attach command rooted at the repo root.

### 2. Frontend Open TUI State Helper

File: `tests/web_management_ui_state.test.js`

Add coverage for a helper exported from `tools/launcher/assets/web-management/app.js`:

- no selection disables `Open TUI`;
- active healthy instance with thread id enables it;
- inactive returns `Resume this instance first.`;
- unhealthy returns `Instance is unhealthy.`;
- missing thread returns `No thread to attach.`;
- mutation busy disables it without changing existing send/interrupt/clear rules.

Focused command:

```bash
node tests/web_management_ui_state.test.js
```

Expected:

- all state helper tests pass;
- existing `computeInstanceActionState` behavior remains covered.

### 3. Frontend Static Contract

File: `tests/web_management_ui_contract.test.js`

Extend the static contract to require:

- `open-tui-button`
- `open-tui-status`
- `copy-tui-command-button`
- `open-tui-command`
- `/open-tui`
- `X-BuddySwitch-Web`
- `Copy command`

Also forbid:

- `attach-open`
- terminal selector UI
- onboarding/modal/wizard copy for this action

Focused command:

```bash
node tests/web_management_ui_contract.test.js
```

Expected:

- assets expose the new CTA and route;
- assets do not expose an `attach-open` launcher path or speculative terminal-choice UI.

### 4. Launcher Surface Regression

File: `tests/test_web_management.py`

Add or keep a focused check that `attach-open` is absent from launcher source/help output.

Focused command:

```bash
PATH=/Users/chen/miniconda3/bin:$PATH PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_web_management.py -q
```

Expected:

- `instance attach <instance-id>` remains the only launcher attach command.

### 5. Broader Regression

Run the frontend and backend suites relevant to Web Management:

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
PATH=/Users/chen/miniconda3/bin:$PATH PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_web_management.py -q
```

Then run the full suite before completion:

```bash
PATH=/Users/chen/miniconda3/bin:$PATH PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests -q
```

Expected:

- all focused tests pass;
- full Python regression passes;
- no generated cache files remain due `PYTHONDONTWRITEBYTECODE=1` and disabled pytest cache.

## Manual macOS Verification

Automated tests must not open Terminal. Manual verification is separate:

1. Start the Web Management server:

```bash
python3 tools/launcher/web_management.py --host 127.0.0.1 --port 8765
```

2. Open `http://127.0.0.1:8765`.
3. Select an active healthy instance with a thread id.
4. Click `Open TUI`.
5. Confirm Terminal.app opens a new session and runs:

```bash
cd <repo-root> && ./buddyswitch-codex instance attach <instance-id>
```

6. If macOS Automation permission is denied, confirm the Web UI shows `Could not open Terminal.` and exposes `Copy command`.

## Phase 1 Review Checklist

- The plan covers every memo Definition of Done item.
- Tests are derived from functional behavior, not from implementation shortcuts.
- Tests use fake terminal openers for automation.
- The route remains Web Management-owned.
- No launcher `attach-open` command is planned.
- No daemon/runtime/app-server task behavior is in scope.
- Verification commands are explicit.
