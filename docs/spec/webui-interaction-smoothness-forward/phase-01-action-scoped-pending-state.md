# Phase 01: Action-Scoped Pending State

## Phase Goal

Replace global mutation-derived action disabling with independent pending-state fields for send, lifecycle, refresh, Open TUI, actor selection, and track selection.

## Source Requirements

- Memo Task 1.
- `state.mutationKey` must be replaced by scoped pending fields.
- Send pending disables only Send.
- Open TUI pending disables only Open TUI.

## Code Research Findings

- `createState()` currently defines `mutationKey`.
- `computeInstanceActionState()` and `describeInstanceActionState()` accept `isMutating`.
- `computeOpenTuiState()` accepts `isMutating`.
- State tests currently assert the old global busy behavior.

## Scope

- Modify `tests/web_management_ui_state.test.js`.
- Modify `tools/launcher/assets/web-management/app.js`.

## Non-Goals

- Do not change runtime API routes.
- Do not migrate handlers in this phase beyond pure state helpers.

## Old Path / Residue Definition

- Old: `mutationKey`, `isMutating`, `Action running.`
- New: `sendPending`, `lifecyclePendingAction`, `openTuiPending`, `refreshPending`, `actorSelectionPendingId`, `trackSelectionPendingId`

## Development Plan

1. Replace old busy-state tests with send/Open TUI pending tests.
2. Run the focused state test and record the expected red failure.
3. Replace `mutationKey` in `createState()` with scoped pending fields.
4. Replace `computeInstanceActionState()` option handling.
5. Replace `describeInstanceActionState()` pending reason handling.
6. Replace `computeOpenTuiState()` option handling.
7. Run the focused state test and record the green result.

## Test Plan

Focused command:

```bash
node tests/web_management_ui_state.test.js
```

Expected red result:

- Fails before implementation because `computeInstanceActionState()` and `computeOpenTuiState()` still expect `isMutating`.

Expected green result:

- All state tests pass.

## Red Verification Expectation

The new tests must fail before implementation because the old global mutation option is still the only supported pending input.

## Green Verification Commands

```bash
node tests/web_management_ui_state.test.js
```

## Residue Scan Commands

Residue remains expected after this phase because later handlers still use the old terms:

```bash
rg -n "mutationKey|isMutating|Action running\.|runMutation\(" tools/launcher/assets/web-management/app.js tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js -S
```

## Acceptance Criteria

- State defaults expose scoped pending fields.
- Send pending disables only Send.
- Lifecycle pending is represented independently.
- Open TUI pending disables only Open TUI.
- Focused state test passes.

## Execution Record

- Replaced old state tests that asserted global mutation busy behavior with scoped pending tests.
- Replaced `createState().mutationKey` with `sendPending`, `refreshPending`, `lifecyclePendingAction`, `openTuiPending`, `actorSelectionPendingId`, and `trackSelectionPendingId`.
- Updated `computeInstanceActionState()`, `describeInstanceActionState()`, and `computeOpenTuiState()` to read scoped pending options.
- Updated state tests to stop passing `isMutating` options.

## Test Results

Red:

```text
$ node tests/web_management_ui_state.test.js
not ok - send pending disables only send while preserving independent actor controls
AssertionError: actual canSend true, expected canSend false
exit 1
```

Green:

```text
$ node tests/web_management_ui_state.test.js
ok - create button requires selected role and no start busy state
...
ok - polling connection-wide events acks off-selected actor message without rendering it
exit 0
```

## Residue Results

Expected old handler/render residue remains for later phases:

```text
$ rg -n "mutationKey|isMutating|Action running\.|runMutation\(" tools/launcher/assets/web-management/app.js tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js -S
tools/launcher/assets/web-management/app.js:694:      isMutating: Boolean(state.mutationKey),
tools/launcher/assets/web-management/app.js:707:      isMutating: Boolean(state.mutationKey),
tools/launcher/assets/web-management/app.js:709:    const openingTui = state.mutationKey === 'open-tui';
tools/launcher/assets/web-management/app.js:807:      && !state.mutationKey
tools/launcher/assets/web-management/app.js:887:  async function runMutation(state, elements, key, requestFactory) {
tools/launcher/assets/web-management/app.js:888:    state.mutationKey = key;
tools/launcher/assets/web-management/app.js:904:      state.mutationKey = '';
tools/launcher/assets/web-management/app.js:1035:      isMutating: Boolean(state.mutationKey),
tools/launcher/assets/web-management/app.js:1043:    state.mutationKey = 'open-tui';
tools/launcher/assets/web-management/app.js:1062:      state.mutationKey = '';
tools/launcher/assets/web-management/app.js:1172:      runMutation(state, elements, 'messages', function () {
tools/launcher/assets/web-management/app.js:1179:      runMutation(state, elements, 'interrupt', function () {
tools/launcher/assets/web-management/app.js:1186:      runMutation(state, elements, 'stop', function () {
tools/launcher/assets/web-management/app.js:1193:      runMutation(state, elements, 'clear', function () {
tools/launcher/assets/web-management/app.js:1200:      runMutation(state, elements, 'resume', function () {
tools/launcher/assets/web-management/app.js:1219:      runMutation(state, elements, 'delete', function () {
```

## Phase Acceptance Decision

Accepted. Phase 01 criteria are met; remaining old mutation residue is intentionally queued for handler and cleanup phases.

## Remaining Risk

The browser handlers still use global mutation/full-render behavior until later phases replace them.
