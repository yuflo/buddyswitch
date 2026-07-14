# Independent Copy Command Forward Rebuild Implementation Plan

> **For agentic workers:** execute this plan inline, task by task, using the repository's `./buddyswitch-test focused` entry only. Do not run `./buddyswitch-test full`, introduce compatibility reads, or retain the retired Open-TUI fallback path.

**Goal:** Rebuild `Copy command` as an independent, minimal, paste-ready CLI-copy feature while keeping `Open TUI` exclusively responsible for opening Terminal.app through the private attach descriptor.

**Architecture:** `Open TUI` stays on `WebManagementService -> ActorSession.resolve_attach -> terminal_command_from_descriptor -> Terminal.app`. `Copy command` gets its own read-only `GET /api/instances/<actor-id>/attach-command` endpoint, which only formats `cd <repo-root> && ./buddyswitch-codex instance attach <actor-id>`. The browser requests and copies that public command directly; it never obtains a command from Open TUI success or error payloads.

**Tech stack:** Python 3.13, `ThreadingHTTPServer`, `unittest`/pytest integration tests, vanilla JavaScript, Node test runner, static HTML/CSS, BuddySwitch focused test runner.

## Scope and invariants

- Preserve the private Terminal execution descriptor and its environment-rich command.
- Add one public copy DTO: `{ok, actor_id, command}` from a GET route.
- Open TUI success becomes `{ok, actor_id, terminal}`; its errors expose no `command` field.
- Copy and Open TUI have separate pending state and feedback state.
- Actor attach availability may be shared; action progress may not be shared.
- Delete `openTuiCommand`, `commandFromError`, `copyOpenTuiCommand`, fallback markup, fallback CSS, and their DOM bindings/tests.
- Do not add aliases, old-field reads, migration branches, wrapper APIs, or alternate test entrypoints.
- Verification is focused by behavior risk. No full suite is part of this change.

## Task 1: Define the independent backend contract with failing tests

**Files:**

- Modify: `tests/unit/web/test_management_service.py`
- Modify: `tests/integration/web/test_management_http.py`
- Modify: `tests/integration/web/management_harness.py`

### Step 1: Add the command formatter unit test

Add a test that gives the formatter a repository path containing a space and a valid actor ID, then asserts the exact shell-safe result:

```python
def test_build_copy_attach_command_is_short_shell_safe_and_paste_ready(self) -> None:
    command = WEB_MANAGEMENT.build_copy_attach_command(
        Path("/tmp/Buddy Switch"),
        "act-pm.demo",
    )

    self.assertEqual(
        command,
        "cd '/tmp/Buddy Switch' && ./buddyswitch-codex instance attach act-pm.demo",
    )
```

### Step 2: Add independent route tests

Add integration cases proving:

```python
status, payload = service.handle_api(
    "GET",
    "/api/instances/act-pm-demo/attach-command",
    b"",
)
self.assertEqual(status, 200)
self.assertEqual(
    payload,
    {
        "ok": True,
        "actor_id": "act-pm-demo",
        "command": f"cd {shlex.quote(str(ROOT))} && ./buddyswitch-codex instance attach act-pm-demo",
    },
)
self.assertEqual(host_control.calls, [])
self.assertEqual(opener.commands, [])
resolve_attach.assert_not_called()
```

Also prove an invalid actor ID maps to `400 INVALID_REQUEST` without calling Host Control, ActorSession, or Terminal.

### Step 3: Run only the new backend tests and observe RED

```bash
./buddyswitch-test focused \
  tests/unit/web/test_management_service.py::WebManagementUnitTests::test_build_copy_attach_command_is_short_shell_safe_and_paste_ready \
  tests/integration/web/test_management_http.py::WebManagementHTTPTests::test_attach_command_route_returns_short_public_cli_without_opening_terminal \
  tests/integration/web/test_management_http.py::WebManagementHTTPTests::test_attach_command_route_rejects_invalid_actor_id_without_side_effects
```

Expected: fail because the formatter and `/attach-command` route do not exist.

## Task 2: Implement the smallest independent backend path

**Files:**

- Modify: `tools/launcher/web_management.py`

### Step 1: Add the shell-safe public formatter

Import `shlex` and add one concrete formatter:

```python
def build_copy_attach_command(repo_root: Path, actor_id: str) -> str:
    return (
        f"cd {shlex.quote(str(repo_root))} && "
        f"./buddyswitch-codex instance attach {shlex.quote(actor_id)}"
    )
```

### Step 2: Add the GET route without execution coupling

- Parse `/api/instances/<actor-id>/attach-command` as action `attach-command`.
- Dispatch only `GET`.
- Validate through `host_control_module.validate_actor_id`; map `HostControlError` with the existing mapper.
- Return the formatter payload directly.
- Do not call `_host_control`, `ActorSession`, or `_terminal_opener`.

### Step 3: Re-run the three backend tests and observe GREEN

Run the exact command from Task 1. All three cases must pass.

## Task 3: Remove Copy semantics from Open TUI

**Files:**

- Modify: `tools/launcher/web_management.py`
- Modify: `tests/integration/web/test_management_http.py`
- Modify: `tests/integration/web/management_harness.py`

### Step 1: Rewrite the existing Open TUI assertions first

- Rename `assert_open_tui_command_uses_descriptor` to `assert_terminal_command_uses_descriptor`.
- Unsupported platform: assert `raised.exception.details is None`.
- Terminal failure: capture `opener.commands[0]`, verify it uses the descriptor, and assert no error details.
- Success: verify the opener command privately, while the HTTP payload is exactly:

```python
{
    "ok": True,
    "actor_id": "act-pm-demo",
    "terminal": "Terminal.app",
}
```

### Step 2: Run the three changed Open TUI cases and observe RED

```bash
./buddyswitch-test focused \
  tests/integration/web/test_management_http.py::WebManagementHTTPTests::test_open_tui_route_rejects_unsupported_os_without_copy_command \
  tests/integration/web/test_management_http.py::WebManagementHTTPTests::test_open_tui_route_delegates_private_descriptor_to_terminal_only \
  tests/integration/web/test_management_http.py::WebManagementHTTPTests::test_open_tui_route_does_not_return_command_when_terminal_open_fails
```

Expected: fail because Open TUI still serializes the command into payloads/errors.

### Step 3: Delete the payload coupling

- Rename `build_open_tui_attach_command` to `build_terminal_attach_command`.
- Keep using `actor_session.terminal_command_from_descriptor` for Terminal execution.
- Remove `details={"command": command}` from both error paths.
- Remove `command` from the success payload.

### Step 4: Re-run the same three cases and observe GREEN

The Terminal opener must still receive the full private descriptor command.

## Task 4: Define the independent browser behavior with failing tests

**Files:**

- Modify: `tests/unit/web/ui_state_roster_actions.test.js`
- Modify: `tests/unit/web/ui_state_selection_refresh.test.js`
- Modify: `tests/unit/web/ui_state_harness.js`

### Step 1: Replace the coupled availability contract

Replace `computeOpenTuiState` tests with `computeAttachActionState` tests. The exact result shape is:

```javascript
{ canAttach: true, message: '' }
```

Cover no selection, inactive runtime, unhealthy runtime, missing thread, and active/healthy/thread-ready runtime. Pending state is intentionally absent from this shared predicate.

### Step 2: Add an independent copy success case

Prove `copyAttachCommand`:

- fetches `/api/instances/act-copy-a/attach-command` with GET semantics;
- copies the returned short CLI command;
- updates only `copyCommandPending` and `copyCommandMessage`;
- does not call `/open-tui` or change `openTuiPending`/`openTuiMessage`.

### Step 3: Replace the stale-copy regression case

Use a deferred `/attach-command` response, change selection, then resolve it. Assert the old response neither writes to the clipboard nor writes feedback into the new selection. Keep the existing stale Open TUI test, but remove every assertion involving `openTuiCommand`.

### Step 4: Run only the changed JS behavior tests and observe RED

```bash
./buddyswitch-test focused tests/unit/web/ui_state_roster_actions.test.js \
  --node-name-pattern='attach action state'
./buddyswitch-test focused tests/unit/web/ui_state_selection_refresh.test.js \
  --node-name-pattern='(open tui response|copy command)'
```

Expected: fail because the independent state/function/API flow does not exist.

## Task 5: Rebuild the browser controls as two parallel tools

**Files:**

- Modify: `tools/launcher/assets/web-management/app.js`
- Modify: `tools/launcher/assets/web-management/index.html`
- Modify: `tools/launcher/assets/web-management/styles.css`
- Modify: `tests/unit/web/ui_state_harness.js`

### Step 1: Replace state and availability ownership

- Replace `computeOpenTuiState(instance, options)` with `computeAttachActionState(instance)` returning `{canAttach, message}`.
- Keep `openTuiPending` and `openTuiMessage`.
- Add `copyCommandPending` and `copyCommandMessage`.
- Delete `openTuiCommand` entirely.
- Selection reset clears both actions' pending/feedback fields.

### Step 2: Render separate controls

The Tools row becomes:

```html
<button id="open-tui-button" class="mini-button" type="button">Open TUI</button>
<button id="copy-command-button" class="mini-button" type="button">Copy command</button>
<button id="clear-button" class="mini-button" type="button">Clear</button>
```

Keep `open-tui-status` and add `copy-command-status`. Delete `open-tui-fallback`, `open-tui-command`, and `copy-tui-command-button`.

### Step 3: Implement independent actions

- `openTui` posts to `/open-tui`, uses only its own pending/message fields, and never reads `payload.command` or error details.
- `copyAttachCommand` gets `/attach-command`, requires a non-empty string command, copies it, and uses only its own pending/message fields.
- Both actions use the same selection request ownership check.
- Open TUI pending does not disable Copy; Copy pending does not disable Open TUI.
- Preserve `fallbackCopyText` only as the clipboard API fallback.

### Step 4: Delete retired presentation residue

Remove `.command-fallback`, `.command-fallback[hidden]`, and `.command-fallback .mini-button`. Do not remove generic `.long-value` unless a repository search proves it unused outside this feature.

### Step 5: Re-run the behavior tests and observe GREEN

Run the exact two commands from Task 4.

## Task 6: Lock the forward-only asset and architecture contract

**Files:**

- Modify: `tests/unit/web/asset_contract_html.test.js`
- Modify: `tests/unit/web/asset_contract_javascript.test.js`
- Modify: `tests/unit/web/asset_contract_styles.test.js`
- Modify: `tests/unit/architecture/test_external_control.py`
- Modify: `tests/unit/web/ui_state_lifecycle.test.js`
- Modify: `tests/unit/web/ui_state_im.test.js` only if the renamed shared predicate changes its fixture path

### Step 1: Make residue checks explicit

Assert the new IDs and `/attach-command` are present. Assert these strings are absent from production assets:

```text
open-tui-fallback
open-tui-command
copy-tui-command-button
openTuiCommand
commandFromError
copyOpenTuiCommand
command-fallback
```

### Step 2: Refine the architecture boundary

The Web module may contain the public launcher string as returned text, so replace the broad `buddyswitch-codex` ban with executable-coupling bans:

- no `LauncherCommandRunner`;
- no `subprocess` execution of `buddyswitch-codex`;
- no `--json` CLI bridge;
- no `/side` routes;
- still require `HostControl` and `ActorSession` owners.

### Step 3: Update unrelated state expectations mechanically

Where lifecycle/selection tests currently preserve or clear `openTuiCommand`, replace those assertions with the two independent feedback states. Keep their original lifecycle or selection intent; do not add new behavior to those modules.

### Step 4: Run focused asset and architecture coverage

```bash
./buddyswitch-test focused \
  tests/unit/web/asset_contract_html.test.js \
  tests/unit/web/asset_contract_javascript.test.js \
  tests/unit/web/asset_contract_styles.test.js
./buddyswitch-test focused \
  tests/unit/architecture/test_external_control.py::ExternalControlArchitectureTests::test_web_uses_private_owners_without_cli_execution_or_side_routes
```

Expected: all pass and the retired dual-track strings are absent.

## Task 7: Focused acceptance and final audit

### Step 1: Search for residue before tests

```bash
rg -n "openTuiCommand|commandFromError|copyOpenTuiCommand|open-tui-fallback|open-tui-command|copy-tui-command-button|command-fallback|build_open_tui_attach_command|assert_open_tui_command_uses_descriptor" \
  tools/launcher
```

Expected: no matches in production code. Tests may contain these strings only as explicit negative assertions that prevent their return.

### Step 2: Run the narrow backend acceptance set

```bash
./buddyswitch-test focused \
  tests/unit/web/test_management_service.py \
  tests/integration/web/test_management_http.py \
  tests/unit/architecture/test_external_control.py
```

### Step 3: Run the narrow frontend acceptance set

```bash
./buddyswitch-test focused \
  tests/unit/web/ui_state_roster_actions.test.js \
  tests/unit/web/ui_state_selection_refresh.test.js \
  tests/unit/web/ui_state_lifecycle.test.js \
  tests/unit/web/ui_state_im.test.js \
  tests/unit/web/asset_contract_html.test.js \
  tests/unit/web/asset_contract_javascript.test.js \
  tests/unit/web/asset_contract_styles.test.js
```

These are the broadest permitted checks for this task. Do not run the repository-wide full suite.

### Step 4: Manual main-path check if the local Web UI is available

- Select one active healthy actor with a thread.
- Click `Copy command`; paste into a scratch text field and confirm the exact short CLI form with the selected actor ID.
- Confirm no Terminal opens.
- Click `Open TUI`; confirm Terminal opens and the Copy status does not change.
- On unsupported platform simulation or a Terminal failure, confirm Copy remains independently available.

### Step 5: Audit the diff

Confirm:

- the backend has one formatting path for public Copy and one private descriptor path for Terminal;
- the frontend has no command cache or Open-TUI error fallback;
- no compatibility branch or old DOM ID remains;
- only scoped source, tests, and this memo changed;
- the user-owned investigation handoff memo remains untouched.

## Self-review

- Product semantics are fully covered: Copy is a standalone paste-ready CLI feature; Open TUI is Terminal execution only.
- API, browser state, DOM, CSS, concurrency ownership, architecture boundaries, and deletion checks have explicit test homes.
- All names and result shapes are concrete; there are no placeholders or optional implementation branches.
- Test commands match the optimized runner: Python uses nodeids, JavaScript uses one file plus `--node-name-pattern`, and acceptance runs only affected files.
- No full-suite run, compatibility layer, legacy field read, or speculative abstraction is included.
