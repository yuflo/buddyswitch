# Phase 03: Row Event Delegation

## Phase Goal

Install actor and Track row click handling once through event delegation instead of attaching row handlers from render output.

## Source Requirements

- Memo Task 3.
- Row click handlers are installed once.
- Rendering actor/track rows no longer creates per-row listeners.

## Code Research Findings

- `render()` currently calls `elements.actorsList.querySelectorAll('[data-actor-id]').forEach(...)`.
- `render()` currently calls `elements.tracksList.querySelectorAll('[data-track-id]').forEach(...)`.
- `bootstrap()` is the correct once-per-page setup boundary for delegated listeners.

## Scope

- Modify `tools/launcher/assets/web-management/app.js`.
- Modify `tests/web_management_ui_contract.test.js`.

## Non-Goals

- Do not alter actor or Track fetch semantics.
- Do not delete the render wrapper in this phase.

## Old Path / Residue Definition

- Old: render-time row listener installation through `querySelectorAll(...).forEach(...)`.
- New: list container `click` listeners in `bootstrap()`.

## Development Plan

1. Add contract residue gate excluding render-time row listener installation.
2. Run contract test and record expected red failure.
3. Delete row listener installation from render.
4. Add delegated `click` listeners for `actorsList` and `tracksList` in `bootstrap()`.
5. Run contract test and record green result.

## Test Plan

Focused command:

```bash
node tests/web_management_ui_contract.test.js
```

Expected red result:

- Fails because old `querySelectorAll(...).forEach(...)` listener installation is still present.

Expected green result:

- Contract test passes.

## Red Verification Expectation

The new residue gate must fail before implementation while render-time listener installation exists.

## Green Verification Commands

```bash
node tests/web_management_ui_contract.test.js
```

## Residue Scan Commands

```bash
rg -n "querySelectorAll\('\[data-actor-id\]'\)|querySelectorAll\('\[data-track-id\]'\)" tools/launcher/assets/web-management/app.js -S
```

## Acceptance Criteria

- No render-time actor/Track row listener installation remains.
- Delegated listeners call `selectActor()` and `selectTrack()`.
- Contract test passes.

## Execution Record

- Added a contract test excluding render-time actor and Track row listener installation.
- Removed per-row `querySelectorAll(...).forEach(...)` listener installation from `render()`.
- Added delegated click handlers on `actorsList` and `tracksList` in `bootstrap()`.

## Test Results

Red:

```text
$ node tests/web_management_ui_contract.test.js
not ok - production javascript does not attach row click handlers from render
AssertionError: Expected asset content to exclude: elements.actorsList.querySelectorAll('[data-actor-id]').forEach
exit 1
```

Green:

```text
$ node tests/web_management_ui_contract.test.js
ok - production html keeps all real control ids used by the web UI
...
ok - first version does not ship mock-only controls
exit 0
```

## Residue Results

No row listener residue:

```text
$ rg -n "querySelectorAll\('\[data-actor-id\]'\)|querySelectorAll\('\[data-track-id\]'\)" tools/launcher/assets/web-management/app.js -S
<no output>
exit 1
```

## Phase Acceptance Decision

Accepted.

## Remaining Risk

Other full-render call sites still exist until Phase 06.
