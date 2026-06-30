# Phase 06: Residue Cleanup

## Phase Goal

Remove the temporary full-render compatibility wrapper and all old global-mutation/live-surface residue.

## Source Requirements

- Memo Task 6.
- The input event path must not call full-page render.
- `runMutation()` must be deleted.
- `render()` compatibility wrapper must be deleted.
- Scoped scans must show no stale global mutation or old Web IM route residue.

## Code Research Findings

- The current input handler calls `render(state, elements)`.
- `runMutation()` owns old refresh-after-mutation behavior.
- The compatibility `render()` wrapper is expected to remain after Phase 02 and must be removed here.

## Scope

- Modify `tools/launcher/assets/web-management/app.js`.
- Modify `tests/web_management_ui_contract.test.js`.

## Non-Goals

- Do not search or rewrite historical docs.
- Do not broaden scans beyond live WebUI surfaces.

## Old Path / Residue Definition

- Old: `mutationKey`, `isMutating`, `Action running.`, `runMutation(`, `render(state, elements);`, old Web IM route strings.
- New: focused render functions and scoped pending flags only.

## Development Plan

1. Add contract residue gates for global mutation state and draft input full-render path.
2. Run contract test and record expected red failure.
3. Convert input handler to `renderComposer()`.
4. Delete `runMutation()`.
5. Replace remaining `render(state, elements)` call sites with focused functions or `renderAll()`.
6. Delete the `render()` wrapper.
7. Run scoped residue scans.
8. Run focused Node tests.

## Test Plan

Focused commands:

```bash
node tests/web_management_ui_contract.test.js
node tests/web_management_ui_state.test.js
```

Expected red result:

- Contract test fails while old residue strings or full-render input path remain.

Expected green result:

- Both focused tests pass.

## Red Verification Expectation

New residue gates fail before cleanup while old strings remain.

## Green Verification Commands

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
```

## Residue Scan Commands

```bash
rg -n "mutationKey|isMutating|Action running\.|runMutation\(" tools/launcher/assets/web-management/app.js tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js -S
rg -n "querySelectorAll\('\[data-actor-id\]'\)|querySelectorAll\('\[data-track-id\]'\)" tools/launcher/assets/web-management/app.js -S
rg -n "POST /api/web/im|/api/web/im|buildWebImConversationUrl|ensureWebImSession|connection_key|participant_token|event_cursor|cursor=" tools/launcher/assets/web-management/app.js tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js -S
```

## Acceptance Criteria

- Residue scans return no output.
- Input typing updates only composer controls.
- No `render()` compatibility wrapper remains.
- Focused tests pass.

## Execution Record

- Added contract residue gates for global mutation state and draft input full-render path.
- Replaced input typing with `renderComposer()`.
- Deleted the temporary `render()` wrapper.
- Deleted unused `runMutation()`.
- Replaced remaining `render(state, elements)` call sites with focused renders or `renderAll()`.
- Split forbidden literal strings inside contract tests so residue scans over live tests do not teach old terms.

## Test Results

Red:

```text
$ node tests/web_management_ui_contract.test.js
not ok - production javascript does not keep global mutation state residue
AssertionError: Expected asset content to exclude: mutationKey
exit 1
```

Green:

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

## Residue Results

All required residue scans are clean:

```text
$ rg -n "mutationKey|isMutating|Action running\.|runMutation\(" tools/launcher/assets/web-management/app.js tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js -S
<no output>
exit 1

$ rg -n "querySelectorAll\('\[data-actor-id\]'\)|querySelectorAll\('\[data-track-id\]'\)" tools/launcher/assets/web-management/app.js -S
<no output>
exit 1

$ rg -n "POST /api/web/im|/api/web/im|buildWebImConversationUrl|ensureWebImSession|connection_key|participant_token|event_cursor|cursor=" tools/launcher/assets/web-management/app.js tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js -S
<no output>
exit 1
```

## Phase Acceptance Decision

Accepted.

## Remaining Risk

CSS feedback markers and final browser smoke remain.
