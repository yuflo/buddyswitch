# Web Open TUI macOS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` before implementation, then use `superpowers:executing-plans` or direct SHARP execution to execute this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal Web Management `Open TUI` CTA that opens the selected active BuddySwitch instance in macOS Terminal.app using the existing `./buddyswitch-codex instance attach <instance-id>` command.

**Architecture:** Keep the launcher attach surface unchanged and implement the desktop-open behavior entirely in `tools/launcher/web_management.py`. Add a small fakeable Terminal opener seam for tests, then wire the static Web UI to the new route with explicit state gating and copy-command fallback.

**Tech Stack:** Python standard library HTTP service, subprocess `osascript`, native HTML/CSS/JavaScript assets, Python `pytest`/`unittest`, Node built-in `assert`.

---

## Current State

Relevant production files:

- `tools/launcher/web_management.py`
  - owns local static serving and Web API routing;
  - validates instance ids;
  - delegates lifecycle/status/actions to `./buddyswitch-codex`;
  - currently has no `open-tui` route.
- `tools/launcher/assets/web-management/index.html`
  - owns static layout and action controls.
- `tools/launcher/assets/web-management/app.js`
  - owns state helpers, rendering, fetch calls, and mutation flow.
- `tools/launcher/assets/web-management/styles.css`
  - owns the current quiet local control-console style.
- `tests/test_web_management.py`
  - owns Web Management API tests with fake command runners.
- `tests/web_management_ui_state.test.js`
  - owns frontend action-state helper tests.
- `tests/web_management_ui_contract.test.js`
  - owns static frontend contract tests.

Relevant stable launcher command:

```bash
./buddyswitch-codex instance attach <instance-id>
```

## Forward Strategy

Use direct implementation in the Web Management layer.

- Do not add `instance attach-open`.
- Do not add a generic opener registry.
- Do not add terminal preference settings.
- Do not keep old/new frontend paths.
- Do not modify daemon, runtime broker, app-server transport, or task runtime.
- Add only the minimum fakeable seam needed to test `osascript` delegation without opening Terminal.

## Files To Modify

- Modify: `tools/launcher/web_management.py`
  - Add `TerminalOpenError`.
  - Add shell command construction helper.
  - Add AppleScript string quoting helper.
  - Add macOS Terminal opener function/class using `osascript`.
  - Extend `HttpError` to carry optional structured details.
  - Pass request headers from the HTTP handler to `WebManagementService.handle_api`.
  - Add `POST /api/instances/<id>/open-tui`.
  - Require JSON content type, `X-BuddySwitch-Web: 1`, local Host/Origin, and empty JSON object body.
  - Validate active/healthy/thread-present status before invoking opener.

- Modify: `tests/test_web_management.py`
  - Add fake terminal opener helpers.
  - Add backend route, security, invalid-state, unsupported-platform, opener-failure, success, and launcher-surface tests.

- Modify: `tools/launcher/assets/web-management/index.html`
  - Add `Open TUI` button and fallback command elements in the selected instance action panel.

- Modify: `tools/launcher/assets/web-management/app.js`
  - Add `computeOpenTuiState`.
  - Extend state with `openTuiMessage` and `openTuiCommand`.
  - Render the CTA, disabled copy, opening/success/failure states, and copy fallback.
  - Fetch `POST /api/instances/<id>/open-tui` with `Content-Type: application/json`, `X-BuddySwitch-Web: 1`, and body `{}`.

- Modify: `tools/launcher/assets/web-management/styles.css`
  - Add compact styling for the terminal CTA row and copy-command fallback.

- Modify: `tests/web_management_ui_state.test.js`
  - Add state-helper tests for `Open TUI`.

- Modify: `tests/web_management_ui_contract.test.js`
  - Add static ids/path/header/copy assertions and forbid `attach-open`.

## Implementation Tasks

### Task 1: Backend Tests For Open TUI Route

- [ ] Add fake opener recording support in `tests/test_web_management.py`.
- [ ] Add `test_open_tui_route_requires_web_headers_before_status_lookup`.
- [ ] Add `test_open_tui_route_rejects_bad_host_or_origin_before_status_lookup`.
- [ ] Add `test_open_tui_route_rejects_arbitrary_request_fields`.
- [ ] Add `test_open_tui_route_rejects_invalid_instance_id_before_status_lookup`.
- [ ] Add blocked-state tests for inactive, unhealthy, and missing-thread instances.
- [ ] Add unsupported-platform test with active status and fake opener call count zero.
- [ ] Add success test proving command shape and fake opener delegation.
- [ ] Add opener-failure test proving structured error and command fallback.
- [ ] Add launcher-surface test proving `attach-open` is absent.
- [ ] Run:

```bash
PATH=/Users/chen/miniconda3/bin:$PATH PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_web_management.py -q
```

- [ ] Confirm the new tests fail for missing implementation before changing production code.

### Task 2: Backend Implementation

- [ ] Extend `HttpError` with optional `details`.
- [ ] Include details fields in JSON error payloads.
- [ ] Add request header passthrough from `create_server` to `handle_api`.
- [ ] Add header lookup and local host/origin validation helpers.
- [ ] Add attach command builder:

```python
cd <repo-root> && ./buddyswitch-codex instance attach <instance-id>
```

- [ ] Add AppleScript quoting helper and macOS opener using:

```applescript
tell application "Terminal"
  activate
  do script "<quoted attach command>"
end tell
```

- [ ] Add `terminal_opener` and `platform_name` constructor seams to `WebManagementService`.
- [ ] Add route parsing for `/open-tui`.
- [ ] Add `_open_tui` route handler with security checks, status checks, platform check, opener call, and structured response.
- [ ] Run the focused backend test until green:

```bash
PATH=/Users/chen/miniconda3/bin:$PATH PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_web_management.py -q
```

### Task 3: Frontend State Tests

- [ ] Add tests in `tests/web_management_ui_state.test.js` for `computeOpenTuiState`.
- [ ] Cover no selection, active healthy with thread id, inactive, unhealthy, missing thread, and mutation busy.
- [ ] Run:

```bash
node tests/web_management_ui_state.test.js
```

- [ ] Confirm the new tests fail before implementation.

### Task 4: Frontend CTA Implementation

- [ ] Add `open-tui-button`, `open-tui-status`, `copy-tui-command-button`, and `open-tui-command` to `index.html`.
- [ ] Add `computeOpenTuiState` and export it from `app.js`.
- [ ] Render button enablement and disabled status copy.
- [ ] Add `openTuiMessage` and `openTuiCommand` state.
- [ ] Add click handler that posts:

```javascript
fetchJson('/api/instances/' + encodeURIComponent(state.selectedInstanceId) + '/open-tui', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-BuddySwitch-Web': '1',
  },
  body: JSON.stringify({}),
});
```

- [ ] On click set `Opening...`.
- [ ] On success set `Terminal opened.` and keep returned command available.
- [ ] On failure set `Could not open Terminal.` and expose returned `error.command` when present.
- [ ] Add Copy command behavior through `navigator.clipboard.writeText` with textarea fallback if needed.
- [ ] Add restrained CSS for terminal CTA and command fallback.
- [ ] Run:

```bash
node tests/web_management_ui_state.test.js
```

### Task 5: Frontend Static Contract

- [ ] Extend `tests/web_management_ui_contract.test.js` to require the new ids, route path, header name, and `Copy command`.
- [ ] Forbid `attach-open` and terminal-choice controls.
- [ ] Run:

```bash
node tests/web_management_ui_contract.test.js
```

- [ ] Confirm contract passes after the frontend implementation.

### Task 6: Focused Regression

- [ ] Run all focused Web Management checks:

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
PATH=/Users/chen/miniconda3/bin:$PATH PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_web_management.py -q
```

- [ ] Run static boundary scans:

```bash
rg -n 'attach-open|System Events|iTerm|terminal selector|terminal-select|open-terminal-choice' buddyswitch-codex tools/launcher
rg -n '/open-tui|X-BuddySwitch-Web|open-tui-button|Copy command' tools/launcher/assets/web-management tools/launcher/web_management.py tests
```

Expected:

- first scan has no production `attach-open`, `System Events`, iTerm, or terminal selector implementation;
- second scan shows only intended Web Management route/UI/test references.

### Task 7: Broad Verification And Review

- [ ] Run full Python regression:

```bash
PATH=/Users/chen/miniconda3/bin:$PATH PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests -q
```

- [ ] If an active healthy instance is available, perform the memo manual macOS verification.
- [ ] Review against `docs/memo/2026-05-29-web-open-tui-macos-task.md` Definition of Done:
  - minimal CTA exists;
  - Web API owns Terminal open;
  - Terminal command uses existing `instance attach`;
  - launcher public surface unchanged;
  - invalid states blocked before opener;
  - failure exposes copy-command fallback;
  - automated tests cover API, state gating, and fake opener behavior;
  - manual macOS result recorded or blocker stated.
- [ ] Check git status:

```bash
git status --short
```

## Phase 1 Self-Review

- Scope is Web Management only.
- Test plan comes from product requirements and security boundaries, not from implementation shortcuts.
- Backend automation never opens Terminal.
- The development path is TDD-first and directly executable.
- No transition layer, compatibility wrapper, or speculative abstraction is included.
