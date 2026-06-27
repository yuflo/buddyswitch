# Web Interface Action Availability Refresh Fix Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix stale WebUI lifecycle action availability so `Clear` becomes clickable when the selected actor returns to an idle, healthy state.

**Architecture:** This is a Browser UI state-refresh problem, not a lower runtime or domain API problem. The fix stays in the Web management frontend and continues using the existing Web-interface product API `GET /api/actors/{actor_id}/console`. The host lower API and actor runtime product API remain unchanged.

**Tech Stack:** Plain JavaScript WebUI in `tools/launcher/assets/web-management/app.js`, static HTML/CSS assets, Node `node --test` frontend contract/state tests, Python Web management tests.

---

## Root Cause

`Clear` is disabled from a local frontend snapshot:

```js
canClear = isActive && appServerHealthy && !threadBusy
threadBusy = threadStatus === 'active' || threadStatus === 'in_progress'
```

The rule is correct and must remain. The bug is that the selected actor runtime snapshot is only refreshed on initial load, manual refresh, actor selection, or mutation completion. When an actor moves from `in_progress` back to `idle`, the page can keep rendering stale disabled state until the user manually refreshes.

## Required Behavior

- Keep the safety rule: `Clear` remains disabled while the selected actor thread is `active` or `in_progress`.
- Refresh the selected actor console on a lightweight interval while the Actor Console is visible.
- Refresh the selected actor console when the page becomes visible again.
- Reuse only `GET /api/actors/{actor_id}/console`; do not add lower-layer or subpanel APIs.
- Show a concise disabled reason for lifecycle actions, especially `Clear`, so a disabled button is explainable.
- Do not create compatibility paths, duplicate action models, or hidden fallback logic.

## Execution Result

Implemented on 2026-06-26.

- Browser UI now refreshes the selected actor console every 3 seconds while the Actor Console is visible.
- Browser UI refreshes the selected actor console when the page becomes visible again.
- IM event polling refreshes the selected actor console after message events.
- Disabled `Clear` now shows a concise reason in `action-availability-status`.
- No new backend, domain, runtime, repo, or lower-layer APIs were added.

## Files

- Modify: `tools/launcher/assets/web-management/app.js`
  - Add an action-state explanation helper.
  - Add selected actor console refresh scheduling.
  - Refresh actor state after IM events.
  - Expose pure helpers for tests.
- Modify: `tools/launcher/assets/web-management/index.html`
  - Add one inline status target near lifecycle controls.
- Modify: `tools/launcher/assets/web-management/styles.css`
  - Style the action availability status line.
- Modify: `tests/web_management_ui_state.test.js`
  - Add failing tests for clear disabled reasons and stale-to-idle refresh decisions.
- Modify: `tests/web_management_ui_contract.test.js`
  - Assert the UI has the action availability status target and JS keeps using only existing coarse APIs.

## TDD Tasks

### Task 1: Explain Disabled Action State

- [ ] **Step 1: Write failing state tests**

Add tests showing:

```js
assert.equal(
  app.describeInstanceActionState(null, { draftText: '', isMutating: false }).clearReason,
  'Select an actor.'
);

assert.equal(
  app.describeInstanceActionState(
    { status: 'active', app_server_health: 'healthy', thread: { status: 'in_progress' } },
    { draftText: '', isMutating: false }
  ).clearReason,
  'Thread running.'
);

assert.equal(
  app.describeInstanceActionState(
    { status: 'active', app_server_health: 'healthy', thread: { status: 'idle' } },
    { draftText: '', isMutating: false }
  ).clearReason,
  ''
);
```

- [ ] **Step 2: Verify RED**

Run:

```bash
node --test tests/web_management_ui_state.test.js
```

Expected: fail because `describeInstanceActionState` is not exported.

- [ ] **Step 3: Implement minimal helper**

Implement `describeInstanceActionState(instance, options)` beside `computeInstanceActionState`. It should return existing booleans plus short reason fields such as `clearReason`.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
node --test tests/web_management_ui_state.test.js
```

Expected: pass.

### Task 2: Refresh Selected Actor Availability

- [ ] **Step 1: Write failing state tests**

Add pure tests for refresh eligibility:

```js
const state = app.createState();
state.selectedSection = 'actors';
state.selectedActorId = 'act-market-demo';

assert.equal(app.shouldRefreshSelectedActorConsole(state, { documentHidden: false }), true);
assert.equal(app.shouldRefreshSelectedActorConsole(state, { documentHidden: true }), false);

state.selectedSection = 'tracks';
assert.equal(app.shouldRefreshSelectedActorConsole(state, { documentHidden: false }), false);
```

- [ ] **Step 2: Verify RED**

Run:

```bash
node --test tests/web_management_ui_state.test.js
```

Expected: fail because `shouldRefreshSelectedActorConsole` is not exported.

- [ ] **Step 3: Implement minimal scheduler**

Add:

- `actorRefreshTimer` and `actorRefreshInFlight` to state.
- `shouldRefreshSelectedActorConsole(state, options)`.
- `refreshSelectedActorConsoleAndRender(state, elements)`.
- `scheduleActorConsoleRefresh(state, elements)` using `setTimeout`.
- a visibility-change listener that refreshes immediately when visible.

Use only `refreshSelectedActorConsole`, which calls `GET /api/actors/{actor_id}/console`.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
node --test tests/web_management_ui_state.test.js
```

Expected: pass.

### Task 3: Wire UI Feedback

- [ ] **Step 1: Write failing contract test**

Assert `index.html` contains `id="action-availability-status"` and `app.js` assigns `elements.actionAvailabilityStatus.textContent`.

- [ ] **Step 2: Verify RED**

Run:

```bash
node --test tests/web_management_ui_contract.test.js
```

Expected: fail because the element and assignment do not exist yet.

- [ ] **Step 3: Implement UI**

Add the status element under lifecycle controls:

```html
<p id="action-availability-status" class="inline-status action-availability-status"></p>
```

Render the selected action reason, prioritizing `clearReason` when `Clear` is disabled.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Expected: pass.

### Task 4: Acceptance

- [ ] Run frontend tests:

```bash
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

- [ ] Run Web management backend tests:

```bash
python -m pytest tests/test_web_management.py -q
```

- [ ] Run boundary search:

```bash
rg -n "actor\\.tasks|track\\.workspace|/api/actors/[^\"']+/tasks|/api/actors/[^\"']+/tracks|/api/tracks/[^\"']+/comments" tools scripts
```

Expected: no output.

- [ ] Optional live check if a Web server is running:

```bash
./buddyswitch-codex instance status act-market-dbf0a249d5bd --json
```

If the actor is `active`, healthy, and thread `idle`, WebUI `Clear` should become enabled after the next selected actor refresh without manual page refresh.
