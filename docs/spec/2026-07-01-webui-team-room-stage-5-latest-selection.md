# WebUI Team Room Stage 5 Latest Selection

## Stage Goal

Make rapid teammate switching keep the latest selected teammate visible. Stage 5 covers memo Task 5: overlapping actor-console fetches must not allow a stale earlier response to overwrite the newer selection.

## Associated Memo Tasks

- `docs/memo/2026-07-01-webui-team-room-forward-implementation-plan.md` Task 5: Make Latest Actor Selection Win.

## Read And Confirmed Code Locations

- `tools/launcher/assets/web-management/app.js`: `createState()` currently has `actorSelectionPendingId` and `trackSelectionPendingId`, but no request ids.
- `tools/launcher/assets/web-management/app.js`: `selectActor()` currently returns early when `state.actorSelectionPendingId` is set, which ignores rapid second selections.
- `tools/launcher/assets/web-management/app.js`: `refreshSelectedActorConsole()` fetches using mutable `state.selectedActorId` and applies the response immediately.
- `tests/web_management_ui_state.test.js`: current actor selection test covers stale feedback clearing but not overlapping selections.

## Current Problems And Residue Points

- A second teammate click during the first actor-console fetch is ignored.
- A slower old actor-console response can still apply through shared mutable state if overlapping requests are later allowed without a request guard.
- The UI can teach the wrong selected teammate after rapid switching.

## Development Change Scope

Modify:

- `tests/web_management_ui_state.test.js`
- `tools/launcher/assets/web-management/app.js`

## Explicit Non-Scope

- No backend, route, DTO, service, persistence, env tool, object-store, or API changes.
- No broad selection architecture rewrite.
- No Track detail race fix beyond adding the memo's request id field in state.
- No roster, shell, CSS, direct thread layout, or Track Studio changes.

## TDD And Test Plan

1. Add a rapid-switch regression test with two controlled actor-console fetch promises.
2. Start selecting `act-first`, then select `act-second` before the first fetch resolves.
3. Resolve the second response first and verify the selected console is `act-second`.
4. Resolve the first response afterward and verify it does not overwrite `state.selectedActorId` or `state.actorConsole`.
5. Run state tests and confirm red on the current pending guard or stale apply behavior.
6. Add request ids to state.
7. Update `selectActor()` to allow a newer selection while an older fetch is pending and apply results only when the request id and actor id still match.
8. Run focused state and contract tests.

## Expected Failing Test

Command after adding the regression test and before implementation:

```bash
node tests/web_management_ui_state.test.js
```

Expected red:

- `rapid actor switching keeps the latest selected teammate visible` fails because the second selection is ignored while `actorSelectionPendingId` is set, or because the stale first response overwrites the latest console.

## Implementation Steps

1. Add the rapid-switch regression test to `tests/web_management_ui_state.test.js`.
2. Run the state test and record expected red.
3. Add `actorSelectionRequestId: 0` and `trackSelectionRequestId: 0` to `createState()`.
4. In `selectActor()`, remove the pending-selection guard while keeping the empty and same-actor guard.
5. Increment and capture a local request id at selection start.
6. Fetch the actor console by local `actorId`, not mutable `state.selectedActorId`.
7. Apply actor-console and direct-conversation results only when `state.actorSelectionRequestId === requestId` and `state.selectedActorId === actorId`.
8. In `finally`, clear `actorSelectionPendingId` and render only for the current request.
9. Run focused tests.

## Acceptance Commands

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
```

Expected result after implementation:

- Both commands exit `0`.
- The rapid-switch regression proves stale first responses cannot overwrite the latest selected teammate.

## Residue Scan Command

```bash
rg -n "actorSelectionRequestId|trackSelectionRequestId|actorSelectionPendingId" tools/launcher/assets/web-management/app.js tests/web_management_ui_state.test.js
```

Expected after Stage 5:

- Request ids exist in `createState()` and `selectActor()`.
- `actorSelectionPendingId` remains only as a loading marker, not as a broad selection lock.

## Stage Completion Standard

- Stage 5 spec exists before code edits.
- Regression test fails before implementation.
- Latest selected teammate wins when actor-console fetches resolve out of order.
- Focused state and contract tests pass.
- No backend or route changes are made.

## Stage 5 Result

Expected red before implementation:

```bash
node tests/web_management_ui_state.test.js
```

Result: failed at `rapid actor switching keeps the latest selected teammate visible` with final `state.selectedActorId` equal to `act-first` instead of `act-second`.

Implemented changes:

- Added `actorSelectionRequestId` and `trackSelectionRequestId` to state.
- Removed the broad pending-selection lock from `selectActor()`.
- Fetches actor console by local `actorId`.
- Applies console and direct-conversation results only when the local request id and selected actor still match.
- Clears `actorSelectionPendingId` only for the current request.

Verification:

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
```

Result: both pass.

Request-id scan:

```bash
rg -n "actorSelectionRequestId|trackSelectionRequestId|actorSelectionPendingId" tools/launcher/assets/web-management/app.js tests/web_management_ui_state.test.js
```

Result: request ids exist in state and `selectActor()`; `actorSelectionPendingId` remains as loading and refresh gating state.

## Risks And Boundary Checks

- Risk: stale direct-conversation fetches can still overwrite messages. Guard conversation apply with the same request id.
- Risk: clearing the pending marker from a stale request can hide the newer loading state. Clear pending only for the current request.
- Risk: modifying `refreshSelectedActorConsole()` could affect periodic refresh. Keep the race-specific fetch/apply logic local to `selectActor()`.

Boundary check:

```bash
git diff --name-only | rg -v '^(tools/launcher/assets/web-management/(index\.html|styles\.css|app\.js)|tests/(web_management_ui_contract\.test\.js|web_management_ui_state\.test\.js)|docs/spec/2026-07-01-webui-team-room-stage-[12345].*\.md)$'
```

Expected during Stage 5: no output, ignoring pre-existing untracked memo files.
