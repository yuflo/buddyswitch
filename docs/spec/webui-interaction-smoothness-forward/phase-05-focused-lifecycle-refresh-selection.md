# Phase 05: Focused Lifecycle, Refresh, Open TUI, And Selection

## Phase Goal

Convert lifecycle, Refresh, Open TUI, actor selection, track selection, and polling paths to action-scoped pending state and focused renders.

## Source Requirements

- Memo Task 5.
- Lifecycle pending disables lifecycle buttons without disabling Send.
- Refresh shows pending/completion feedback and preserves draft typing.
- Open TUI pending disables only Open TUI.
- Actor selection immediately selects the row and clears stale conversation.
- Track selection immediately updates list/detail loading state.
- Actor polling does not redraw hidden actor panels or run during selection pending.

## Code Research Findings

- Lifecycle buttons currently use `runMutation()`.
- Refresh button currently calls `refreshAll()` directly.
- `openTui()` currently uses `state.mutationKey`.
- `selectActor()` and `selectTrack()` wait for fetches before rendering.
- `shouldRefreshSelectedActorConsole()` blocks on `state.mutationKey`.

## Scope

- Modify `tests/web_management_ui_state.test.js`.
- Modify `tools/launcher/assets/web-management/app.js`.

## Non-Goals

- Do not change create-instance semantics except to cooperate with focused renders.
- Do not modify backend lifecycle routes.

## Old Path / Residue Definition

- Old: lifecycle/refresh/Open TUI/selection depends on global render and `mutationKey`.
- New: `runLifecycleAction()`, `deleteSelectedActor()`, `refreshAllWithFeedback()`, selection pending ids, focused render calls.

## Development Plan

1. Add lifecycle pending action-state test.
2. Run focused state test and record result.
3. Add `runLifecycleAction()` and replace interrupt/stop/clear/resume handlers.
4. Add `deleteSelectedActor()` and replace delete handler.
5. Convert `openTui()` to `openTuiPending`.
6. Add `refreshAllWithFeedback()` and replace Refresh handler.
7. Replace `selectActor()` with immediate focused rendering and pending id.
8. Replace `selectTrack()` with immediate focused rendering and pending id.
9. Update polling refresh/render path to focused actor/detail/conversation rendering.
10. Run focused state and contract tests.

## Test Plan

Focused commands:

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
```

Expected red result:

- The lifecycle pending state test should pass after Phase 01.
- Any failures after handler migration indicate incomplete focused-render conversion.

Expected green result:

- Both focused Node tests pass.

## Red Verification Expectation

The new lifecycle pending test is expected to be green after Phase 01; this phase is primarily a handler conversion phase protected by existing behavior and later residue gates.

## Green Verification Commands

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
```

## Residue Scan Commands

Global mutation residue remains fully enforced in Phase 06:

```bash
rg -n "mutationKey|isMutating|Action running\.|runMutation\(" tools/launcher/assets/web-management/app.js tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js -S
```

## Acceptance Criteria

- Lifecycle handlers use scoped pending state.
- Refresh handler uses visible pending feedback.
- Open TUI uses `openTuiPending`.
- Actor and Track selection render immediate feedback.
- Focused tests pass.

## Execution Record

- Added lifecycle pending action-state test.
- Updated actor polling eligibility to use `actorSelectionPendingId` instead of global mutation state.
- Converted selected actor polling renders to focused actor/detail/composer/Open TUI renders.
- Converted actor and Track selection to immediate selected-row/loading-state renders with pending ids.
- Added `runLifecycleAction()` and converted interrupt, stop, clear, and resume handlers.
- Added `deleteSelectedActor()` and converted the delete handler.
- Converted Open TUI and copy feedback paths to `openTuiPending` and focused Open TUI renders.
- Added `refreshAllWithFeedback()` and converted the Refresh handler.
- Added actor/Track selection loading classes and inline loading detail copy.
- Phase 08 browser smoke exposed stale success banner residue on actor switch; added a regression test and rendered the shell immediately when `selectActor()` clears `state.message`.

## Test Results

Lifecycle pending check:

```text
$ node tests/web_management_ui_state.test.js
ok - lifecycle pending disables lifecycle buttons without disabling send
...
exit 0
```

Focused verification:

```text
$ node tests/web_management_ui_state.test.js
ok - create button requires selected role and no start busy state
...
ok - polling connection-wide events acks off-selected actor message without rendering it
exit 0

$ node tests/web_management_ui_contract.test.js
ok - production html keeps all real control ids used by the web UI
...
ok - first version does not ship mock-only controls
exit 0
```

Smoke-driven regression red/green:

```text
$ node tests/web_management_ui_state.test.js
not ok - actor selection clears stale feedback before fetch completes
AssertionError: 'Created act-old.' == ''
exit 1

$ node tests/web_management_ui_state.test.js
ok - actor selection clears stale feedback before fetch completes
...
ok - polling connection-wide events acks off-selected actor message without rendering it
exit 0
```

## Residue Results

Only the now-unused `runMutation()` implementation remains for Phase 06 deletion:

```text
$ rg -n "mutationKey|isMutating|Action running\.|runMutation\(" tools/launcher/assets/web-management/app.js tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js -S
tools/launcher/assets/web-management/app.js:1085:  async function runMutation(state, elements, key, requestFactory) {
tools/launcher/assets/web-management/app.js:1086:    state.mutationKey = key;
tools/launcher/assets/web-management/app.js:1102:      state.mutationKey = '';
```

## Phase Acceptance Decision

Accepted.

## Remaining Risk

The unused `runMutation()` body, temporary `render()` wrapper, and remaining `render(state, elements)` call sites must still be removed in Phase 06.
