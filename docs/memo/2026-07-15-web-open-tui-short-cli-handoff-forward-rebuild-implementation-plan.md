# Web Open TUI Short CLI Handoff Forward Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Execute inline because this task does not authorize sub-agent delegation. Use only the repository's `./buddyswitch-test focused` entry for automated tests.

**Goal:** Make one Open TUI click launch exactly one Terminal.app window with the same short, paste-ready BuddySwitch attach command exposed by Copy command, while removing Web-owned descriptor expansion and reporting launch acceptance honestly.

**Architecture:** The browser posts a local, validated launch request. Web validates the request and actor ID, builds the canonical short command `cd <repo-root> && ./buddyswitch-codex instance attach <actor-id>`, hands that command to Terminal.app, and returns `202 Accepted`. Terminal then invokes the public CLI, whose existing `instance attach` path owns `ActorSession.exec_attach`, descriptor resolution, environment construction, runtime resolution, and process replacement. Open TUI is an explicit human-terminal handoff; Web does not parse CLI output or use CLI as its lifecycle/domain API.

**Tech Stack:** Python 3.13, AppleScript/Terminal.app, `ThreadingHTTPServer`, BuddySwitch public CLI, `unittest`/pytest integration tests, vanilla JavaScript, Node test runner, real local Codex runtime.

---

## Scope and non-negotiable invariants

- Work only in `/Users/chen/Dev/buddyswitch/.worktrees/fea-webui`.
- Keep exactly one production command builder for both Open TUI and Copy command.
- Open TUI must not call `ActorSession.resolve_attach`, expand `AttachDescriptor`, or transport the full runtime environment through AppleScript.
- Keep `ActorSession.resolve_attach` and `ActorSession.exec_attach` as the CLI-owned attach implementation.
- Delete `build_terminal_attach_command`, `terminal_command_from_descriptor`, their tests/imports, and all Open-TUI descriptor mocks.
- Preserve local Host/Origin, content-type, `X-BuddySwitch-Web`, empty-body, and actor-ID validation before Terminal is touched.
- Execute exactly one `do script <short command>` branch. If Terminal is already running, unscoped `do script` creates the requested new window before activation. If Terminal is stopped, activation creates its one default window and scoped `do script ... in front window` reuses that window instead of creating a second one.
- A successful `osascript` call means the launch was accepted, not that the Codex TUI is ready: return `202` with `status: "accepted"` and show `Launch sent to Terminal.`.
- Keep Copy command's pending/feedback behavior independent from Open TUI and preserve stale-selection response gating.
- Do not add a temporary `.command` file, launcher state machine, wrapper, alias, fallback path, feature flag, compatibility read, or second test entrypoint.
- Final product acceptance must create a new actor through `./buddyswitch-codex instance start --role dev` and attach the installed real Codex runtime. Fake Codex is forbidden for that acceptance.
- No commit, push, merge, or unrelated cleanup is in scope.

## Task 1: Lock the backend handoff contract with RED tests

**Files:**

- Modify: `tests/unit/web/test_management_service.py`
- Modify: `tests/integration/web/test_management_http.py`

- [ ] Rename the formatter test to `test_build_attach_cli_command_is_short_shell_safe_and_paste_ready` and make it call `build_attach_cli_command`.
- [ ] Add a unit regression proving `open_macos_terminal_app` selects one mutually exclusive window strategy for already-running and stopped Terminal, and preserves the exact short command in both branches.
- [ ] Replace descriptor-based Open TUI integration cases with a success case that proves:

```python
status, payload = service.handle_api(
    "POST",
    "/api/instances/act-pm-demo/open-tui",
    b"{}",
    OPEN_TUI_HEADERS,
)
self.assertEqual(status, 202)
self.assertEqual(
    payload,
    {
        "ok": True,
        "actor_id": "act-pm-demo",
        "terminal": "Terminal.app",
        "status": "accepted",
    },
)
self.assertEqual(
    opener.commands,
    [f"cd {shlex.quote(str(ROOT))} && ./buddyswitch-codex instance attach act-pm-demo"],
)
```

- [ ] Rewrite unsupported-platform and Terminal-failure cases around the short command, using `Could not launch Terminal.` and `TERMINAL_LAUNCH_FAILED` for launcher failure.
- [ ] Delete the obsolete ActorSession-blocker/runtime-mismatch Open TUI cases: those failures now occur visibly inside the user-owned Terminal after handoff.
- [ ] Strengthen the invalid-actor case so it proves no opener call and no ActorSession construction/resolution.
- [ ] Run the exact RED slice:

```bash
./buddyswitch-test focused \
  tests/unit/web/test_management_service.py::WebManagementUnitTests::test_build_attach_cli_command_is_short_shell_safe_and_paste_ready \
  tests/unit/web/test_management_service.py::WebManagementUnitTests::test_open_macos_terminal_app_targets_one_window_for_running_and_stopped_terminal \
  tests/integration/web/test_management_http.py::WebManagementHTTPTests::test_open_tui_route_hands_short_cli_command_to_terminal_and_returns_accepted \
  tests/integration/web/test_management_http.py::WebManagementHTTPTests::test_open_tui_route_rejects_invalid_actor_id_before_terminal_handoff \
  tests/integration/web/test_management_http.py::WebManagementHTTPTests::test_open_tui_route_maps_terminal_launch_failure
```

Expected RED: renamed builder is absent, AppleScript lacks an explicit stopped-vs-running single-window target, success is still `200`, and Open TUI still resolves a descriptor.

## Task 2: Rebuild the backend through the shortest single path

**Files:**

- Modify: `tools/launcher/web_management.py`
- Modify: `tools/launcher/actor_session.py`
- Modify: `tests/unit/actor/test_session.py`

- [ ] Implement one canonical builder and use it in both `_open_tui` and `_attach_command`:

```python
def build_attach_cli_command(repo_root: Path, actor_id: str) -> str:
    return (
        f"cd {shlex.quote(str(repo_root))} && "
        f"./buddyswitch-codex instance attach {shlex.quote(actor_id)}"
    )
```

- [ ] In `_open_tui`, validate the local request, validate the actor ID through `host_control_module.validate_actor_id`, reject non-macOS before calling the opener, hand the short command to `_terminal_opener`, and return the accepted payload.
- [ ] Change the POST route dispatch to return `202, self._open_tui(...)`.
- [ ] Make the AppleScript lifecycle strategy exactly:

```applescript
set terminalWasRunning to application "Terminal" is running
tell application "Terminal"
  if terminalWasRunning then
    do script "<short command>"
    activate
  else
    activate
    do script "<short command>" in front window
  end if
end tell
```

- [ ] Rename launcher failure semantics to `TERMINAL_LAUNCH_FAILED` / `Could not launch Terminal.` while keeping `TerminalOpenError` as the low-level automation exception.
- [ ] Delete `build_terminal_attach_command` from Web.
- [ ] Delete `terminal_command_from_descriptor` and the now-unused `shlex` import from Actor Session; delete its unit test if present.
- [ ] Run the exact Task 1 slice and require GREEN.

## Task 3: Lock and implement truthful browser feedback

**Files:**

- Modify: `tests/unit/web/ui_state_selection_refresh.test.js`
- Modify: `tests/unit/web/ui_state_lifecycle.test.js`
- Modify: `tests/unit/web/ui_state_roster_actions.test.js`
- Modify: `tools/launcher/assets/web-management/app.js`

- [ ] Add `open tui success reports launch acceptance` proving a successful POST sets only `openTuiMessage = 'Launch sent to Terminal.'` and clears pending state.
- [ ] Keep `stale open tui response cannot write into a newer actor selection` and the independent Copy command regression unchanged in meaning.
- [ ] Update lifecycle/roster fixtures from the retired success string to the accepted string.
- [ ] Run the new browser test and observe RED:

```bash
./buddyswitch-test focused tests/unit/web/ui_state_selection_refresh.test.js \
  --node-name-pattern='open tui success reports launch acceptance'
```

- [ ] Change the production success message to `Launch sent to Terminal.`; keep `Opening...` and the launch-error message scoped to Open TUI.
- [ ] Run the full focused browser-state slice and require GREEN:

```bash
./buddyswitch-test focused \
  tests/unit/web/ui_state_selection_refresh.test.js \
  tests/unit/web/ui_state_lifecycle.test.js \
  tests/unit/web/ui_state_roster_actions.test.js
```

## Task 4: Rewrite the durable architecture contract and residue gate

**Files:**

- Modify: `docs/arch/web-interface-call-architecture.md`
- Modify: `tests/unit/architecture/test_external_control.py`

- [ ] Define the explicit valid path:

```text
Browser -> Web Open-TUI route -> Terminal handoff -> public CLI instance attach -> Actor Session
```

- [ ] Preserve peer-interface semantics: Web may hand a human-facing command to Terminal, but it must not execute/parse CLI output as an internal lifecycle, message, Task, Track, or console API.
- [ ] State that Actor Session remains the owner of attach resolution; Web owns only local validation and Terminal handoff.
- [ ] Update the architecture gate to require `build_attach_cli_command`, forbid Web calls to `resolve_attach` and `terminal_command_from_descriptor`, and keep direct subprocess execution of `./buddyswitch-codex` forbidden.
- [ ] Run and require GREEN:

```bash
./buddyswitch-test focused tests/unit/architecture/test_external_control.py
```

## Task 5: Focused combined verification and physical residue audit

- [ ] Run the complete risk-owned slice once:

```bash
./buddyswitch-test focused \
  tests/unit/actor/test_session.py \
  tests/unit/web/test_management_service.py \
  tests/integration/web/test_management_http.py \
  tests/unit/web/ui_state_selection_refresh.test.js \
  tests/unit/web/ui_state_lifecycle.test.js \
  tests/unit/web/ui_state_roster_actions.test.js \
  tests/unit/web/asset_contract_javascript.test.js \
  tests/unit/architecture/test_external_control.py
```

- [ ] Require a clean syntax/whitespace diff:

```bash
git diff --check
```

- [ ] Require no retired implementation residue outside historical memos:

```bash
rg -n \
  'build_terminal_attach_command|terminal_command_from_descriptor|build_copy_attach_command|Terminal opened\.|TERMINAL_OPEN_FAILED|resolve_attach' \
  tools/launcher/web_management.py \
  tools/launcher/actor_session.py \
  tools/launcher/assets/web-management \
  tests/unit/web \
  tests/integration/web \
  tests/unit/architecture
```

Expected: no retired Web/Open-TUI tokens. `resolve_attach` may remain only in Actor Session/CLI-owned actor tests, not Web implementation or Web tests.

- [ ] Review `git diff --stat` and `git diff` to confirm the change stays inside the planned files and physically removes the descriptor-expansion path.

## Task 6: Real actor, real Codex, real browser/Terminal acceptance

- [ ] Confirm port `8766` is unused, then launch this worktree's server:

```bash
./buddyswitch-codex web --host 127.0.0.1 --port 8766
```

- [ ] Create a new real actor and parse its `actor_id` from the CLI JSON; do not reuse the pre-existing actor:

```bash
./buddyswitch-codex instance start --role dev
```

- [ ] Confirm the new actor is `active`, `app_server_health` is `healthy`, and `thread_id` is non-empty via:

```bash
./buddyswitch-codex instance list --role dev
```

- [ ] Open `http://127.0.0.1:8766/` in the in-app browser, select the new actor, and capture the selected actor ID plus initial Tools state.
- [ ] Record the Terminal window count, click Open TUI exactly once, and prove the count increases by exactly one.
- [ ] Prove the browser displays `Launch sent to Terminal.`.
- [ ] Prove the new Terminal runs the short `./buddyswitch-codex instance attach <new-actor-id>` handoff and reaches the real installed Codex TUI for that actor/thread. A fake Codex process or synthetic PTY is not acceptance evidence.
- [ ] Observe briefly that no second window appears and no repeated command text is injected.
- [ ] Close only the acceptance Terminal window/process, then stop and delete only the newly created actor using the public CLI:

```bash
./buddyswitch-codex instance stop <new-actor-id>
./buddyswitch-codex instance delete <new-actor-id> --yes
```

- [ ] Verify the acceptance actor is absent, stop the port-8766 server, verify 8766 has no listener, and verify the user's original `http://127.0.0.1:8765/api/health` remains healthy.

## Task 7: Final audit and acceptance decision

- [ ] Audit every invariant in this plan against source, tests, live browser state, Terminal window/process evidence, and cleanup evidence.
- [ ] Report separately: changed behavior, deleted baggage, automated verification counts, real-runtime acceptance, cleanup, and remaining risk.
- [ ] Mark the persistent goal complete only if every required item is proven; otherwise leave it active and name the exact blocker.

## Execution and acceptance record

- Plan execution completed on 2026-07-15 in the `fea-webui` worktree with no compatibility path retained.
- RED evidence:
  - initial five-test slice failed on the missing shared builder, old AppleScript ordering, old descriptor resolution, and old HTTP semantics;
  - the browser acceptance-message test failed on `Terminal opened.`;
  - after a stopped-Terminal live probe exposed two windows, the exact lifecycle regression failed against the single unconditional AppleScript path.
- Final IMPACT evidence: `./buddyswitch-test focused` over Actor Session, Web service/HTTP, browser selection/lifecycle/roster, JavaScript asset contract, and external-control architecture passed with 75 Python tests plus 131 subtests and 75 JavaScript tests (run `14e8222de69a42608b5405f5a5910912`).
- Real actor evidence: `./buddyswitch-codex instance start --role dev` created `act-dev-44f72c375e63`, active and healthy on thread `019f64e6-4666-73e2-bece-23e9053ece3a`; the in-app browser selected it on port 8766 and displayed `Launch sent to Terminal.` after one Open TUI click.
- Real runtime evidence: that click produced one Terminal window, one full short-command echo, and the real Codex v0.144.4 `resume --remote` process/TUI for the actor's exact socket and thread.
- Terminal lifecycle evidence after the final fix:
  - with the Terminal process absent, one accepted request produced one window after 3 seconds and still one after 5 seconds;
  - with Terminal already running and one existing test window, one accepted request increased the count by exactly one.
- Cleanup evidence: the created acceptance actor was stopped and deleted with the public CLI, all acceptance attach processes/windows were removed, port 8766 had no listener, and the user's existing port-8765 health route remained HTTP 200.
- Residual limitation: audio output itself is not machine-capturable here; acceptance instead proves the repeated-window and repeated-command-injection mechanics are absent. The real TUI's normal terminal control sequences remain owned by Codex/Terminal.app.
