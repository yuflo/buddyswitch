# WebUI Simulated User Test Plan

## Goal

Evaluate the rebuilt BuddySwitch WebUI as a real user would: start from the browser, create multiple teammates, switch between them, send direct Team Room messages, exercise lifecycle controls, inspect Track Studio, and compare the interaction result with server logs and observable runtime state.

This is not a unit test plan. Automated assertions may support evidence collection, but the core test path must be browser-driven and must record what the user sees and feels.

## Scope

In scope:

- Launch WebUI with `./buddyswitch-codex web --host 127.0.0.1 --port <port>`.
- Operate the UI in a browser from `http://127.0.0.1:<port>/`.
- Create at least three actor roles through the UI, including `dev`, `pm`, and `test` when those roles are available.
- Exercise Team Room roster, selected teammate card, direct thread composer, action buttons, refresh, and Tracks tab.
- Observe server stdout/stderr and browser-side request/console behavior during interaction.
- Record interaction smoothness, confusing states, stale data, disabled states, layout problems, and unsupported visual/data gaps.
- Clean up actors created by the test through the UI when possible.

Out of scope:

- Editing production WebUI implementation unless this test exposes a blocking bug and the user asks for a fix.
- Editing runtime object files under `buddyswitch/objects/**`.
- Using direct API calls as the primary interaction path.
- Treating static contract tests as a replacement for browser experience.

## Test Artifacts

Write outputs into this directory:

- Plan: `docs/spec/webui-simulated-user-test/00-simulated-user-test-plan.md`
- Raw log excerpt: `docs/spec/webui-simulated-user-test/webui-server-log.txt`
- Browser observation notes: `docs/spec/webui-simulated-user-test/browser-observations.md`
- Final result: `docs/spec/webui-simulated-user-test/01-simulated-user-test-result.md`

## Environment Setup

1. Confirm worktree status:

   ```bash
   git status --short
   ```

2. Choose a local port. Prefer `8767` unless it is already occupied:

   ```bash
   lsof -nP -iTCP:8767 -sTCP:LISTEN || true
   ```

3. Start WebUI and capture logs:

   ```bash
   ./buddyswitch-codex web --host 127.0.0.1 --port 8767 2>&1 | tee docs/spec/webui-simulated-user-test/webui-server-log.txt
   ```

4. Open browser at:

   ```text
   http://127.0.0.1:8767/
   ```

## User Personas And Scenarios

### Scenario A: First Arrival And Empty State

User intent: "I opened the WebUI and need to understand whether this is the Team Room I asked for."

Browser steps:

1. Load `/`.
2. Confirm the first visible screen is Team Room.
3. Confirm primary tabs are only `Team room` and `Tracks`.
4. Inspect People list, Direct thread, selected teammate card, Task summary, Track summary, Actions, and Start teammate.
5. Confirm old visual shell terms such as `Actor Console`, `Create Actor`, `Workspace`, or fake progress data are not visible.

Observe:

- Does the UI feel like the prototype layout: left people rail, central direct thread, right teammate card?
- Is any section blank without an explanation?
- Does any text overflow or overlap?
- Does server log show normal health/roles/actors/tracks fetches without tracebacks?

### Scenario B: Create Dev Teammate And Send Direct Message

User intent: "I want to start a developer teammate and send a direct instruction."

Browser steps:

1. In Start teammate, select `dev` if available.
2. Click `Start`.
3. Wait until a new People row appears and is selected.
4. Inspect selected teammate card status, health, task count, Track summary, and action availability.
5. Type:

   ```text
   Simulated WebUI test: please acknowledge the Team Room direct thread.
   ```

6. Click `Send`.
7. Watch the Direct thread for pending, sent, failed, or reply states.
8. Click `Refresh`.

Observe:

- Does Start show pending feedback and recover?
- Does the roster row use real role/actor data, not fake names?
- Does Send disable correctly while empty and while pending?
- Does the message render in the thread without layout jump or confusing copy?
- Does server log show create and IM message requests without uncaught exceptions?

### Scenario C: Create PM And Test Teammates, Then Rapid Switch

User intent: "I have multiple teammates and need to switch between them quickly."

Browser steps:

1. Create a `pm` teammate through Start teammate when available.
2. Create a `test` teammate through Start teammate when available.
3. Click dev, pm, and test rows in quick succession.
4. After rapid switching stops, inspect the selected teammate card and Direct thread.
5. Send a short message to the final selected teammate:

   ```text
   Simulated WebUI test: checking selected teammate routing.
   ```

Observe:

- Does the final selected row match the selected teammate card?
- Does the Direct thread belong to the final selected teammate, not a previous request?
- Does any row remain stuck in a loading state?
- Does server log show console fetches for selected actors without stale response errors?

### Scenario D: Lifecycle Controls On One Test Actor

User intent: "I need to manage a teammate without leaving the WebUI."

Use the `test` actor if available, otherwise use the last created actor.

Browser steps:

1. Select the actor.
2. Inspect which action buttons are enabled.
3. Click `Open TUI` and record whether Terminal opens or fallback command appears.
4. Click `Clear` if enabled and record thread/card changes.
5. Click `Stop`.
6. Confirm `Resume` becomes enabled and send actions become disabled.
7. Click `Resume`.
8. Confirm status returns to active or a clear error appears.
9. Do not click `Delete` until cleanup.

Observe:

- Are disabled reasons clear and accurate?
- Do button labels and pending states avoid double-submit confusion?
- Does the UI recover after stop/resume without reload?
- Does server log show lifecycle command execution and any errors?

### Scenario E: Tracks Tab / Studio Read View

User intent: "I switch to Tracks to inspect product work without writing comments."

Browser steps:

1. Click `Tracks`.
2. Inspect left Track list and center Track Studio document.
3. Select the first available track if any exists.
4. Inspect title, outcome, current state, materials/proofs, updates, comments, and right rail.
5. Switch back to `Team room`, then back to `Tracks`.

Observe:

- Does Tracks use the prototype Studio layout, not the old workspace shell?
- If no tracks exist, is the empty state clear?
- Are write controls absent from Track Studio?
- Does switching tabs preserve or sensibly restore selection?
- Does server log show track list/detail fetches without 404/500 noise?

### Scenario F: Responsiveness And Interaction Smoothness

User intent: "I use the UI in a narrow browser window."

Browser steps:

1. Resize browser to a narrow/mobile-width viewport if the tooling allows it.
2. Repeat one Team Room selection and one Tracks selection.
3. Check horizontal scrolling and overlapping content.

Observe:

- Is there horizontal overflow?
- Are buttons still reachable?
- Does the central thread remain usable?
- Does the right teammate card stack in a readable order?

## Log Review Checklist

Review `webui-server-log.txt` after browser testing and extract:

- Server startup line and port.
- HTTP/API errors, tracebacks, or invalid JSON messages.
- Actor creation requests and lifecycle requests.
- IM message send or channel worker errors.
- Track list/detail errors.
- Shutdown/cleanup confirmation.

Do not mark a scenario as passed if the browser looked acceptable but logs show a backend error that the UI hides.

## Cleanup Checklist

1. For every actor created during this test, use UI lifecycle controls to stop/delete when available.
2. If UI cleanup fails, record the failure and only then inspect non-object runtime commands needed to identify leftovers.
3. Stop the WebUI server.
4. Confirm no server listener remains:

   ```bash
   lsof -nP -iTCP:8767 -sTCP:LISTEN || true
   ```

## Pass / Fail Standard

Pass requires:

- Browser-driven execution of all scenarios that are supported by available roles/data.
- At least three actor-role attempts, covering `dev`, `pm`, and `test` if those roles exist.
- Direct thread send attempted from the browser.
- Lifecycle controls exercised from the browser on at least one actor.
- Tracks tab inspected from the browser.
- Logs reviewed and summarized.
- Result file records pass/fail per scenario, defects, suspected root cause, severity, and cleanup state.

Fail or partial requires:

- Any scenario blocked by UI, backend, tool, or environment issues.
- Any hidden server traceback or persistent failed request.
- Any created actor left running or undeleted without clear reason.
- Any major mismatch with the intended Team Room / Track Studio visual structure.
