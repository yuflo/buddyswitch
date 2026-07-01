# WebUI Team Room Stage 7 Track Studio

## Stage Goal

Shape the Tracks destination into a read-only Track Studio using current Track read APIs only. Stage 7 covers memo Task 7: Track detail should show outcome, current state, materials, proofs, updates, and comment threads without Track write UI or a comment composer.

## Associated Memo Tasks

- `docs/memo/2026-07-01-webui-team-room-forward-implementation-plan.md` Task 7: Shape Tracks Into The D-Style Read-Only Track Studio.

## Read And Confirmed Code Locations

- `tools/launcher/assets/web-management/index.html`: Track list heading is already `Tracks`; detail heading still says `Track detail`.
- `tools/launcher/assets/web-management/app.js`: `renderTrackDetailHtml(track)` already renders title, outcome, state, now, materials, proofs, updates, and comment threads.
- `tests/web_management_ui_state.test.js`: no direct read-only Track Studio detail render test exists yet.
- `tests/web_management_ui_contract.test.js`: route guard already excludes Track comments write route.

## Current Problems And Residue Points

- Static detail heading still says `Track detail`, not `Track Studio`.
- Track read-only behavior is only indirectly covered.
- No focused test proves the renderer omits composer/write UI while still showing materials, proofs, updates, and comments.

## Development Change Scope

Modify:

- `tests/web_management_ui_state.test.js`
- `tests/web_management_ui_contract.test.js`
- `tools/launcher/assets/web-management/index.html`

## Explicit Non-Scope

- No backend, route, DTO, service, env tool, object-store, or runtime changes.
- No Track write route, comment composer, mutation UI, or collaborator rail.
- No changes to Track persistence or comment APIs.
- No broader CSS polish beyond labels unless tests expose a layout issue.

## TDD And Test Plan

1. Add a state test for `renderTrackDetailHtml()` using a Track with materials, proofs, updates, comment summary, and comment threads.
2. Assert the rendered HTML includes the expected read fields.
3. Assert it does not include `textarea`, `composer`, `submit`, or `resolve`.
4. Add a static contract test that requires `Track Studio` heading and the read-only detail subtitle.
5. Run focused tests and confirm red because current static HTML still says `Track detail`.
6. Replace static detail heading with `Track Studio`.
7. Run focused state and contract tests.

## Expected Failing Test

Command after adding tests and before implementation:

```bash
node tests/web_management_ui_contract.test.js
```

Expected red:

- Static Track Studio label test fails because `index.html` lacks `>Track Studio<`.

The new renderer test may already pass because current renderer is read-only; it still becomes a durable guard for the final completion gate.

## Implementation Steps

1. Add `Track Studio renders read-only materials proofs updates and comment threads` to `tests/web_management_ui_state.test.js`.
2. Add `Tracks shell presents read-only Track Studio labels` to `tests/web_management_ui_contract.test.js`.
3. Run focused tests and record expected red.
4. Patch `index.html` detail heading from `Track detail` to `Track Studio`.
5. Keep the detail subtitle as `Outcome, current state, materials, proofs, updates, and comments`.
6. Run focused tests and scoped residue scan.

## Acceptance Commands

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
```

Expected result after implementation:

- Both commands exit `0`.
- Track renderer test proves read-only materials, proofs, updates, and comments.
- Contract test proves static Track Studio labels.

## Residue Scan Command

```bash
rg -n "Track detail|textarea|composer|submit|resolve|/api/tracks/.*/comments" tools/launcher/assets/web-management tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js
```

Expected after Stage 7:

- No production `Track detail`.
- No production Track composer/write-route hits.
- Test-only negative assertions and unrelated implementation words such as helper names are reviewed case by case.

## Stage Completion Standard

- Stage 7 spec exists before code edits.
- Static Track Studio contract fails before HTML change.
- Track detail heading becomes `Track Studio`.
- Track renderer remains read-only and covered.
- Focused state and contract tests pass.

## Stage 7 Result

Expected red before implementation:

```bash
node tests/web_management_ui_contract.test.js
```

Result: failed at `Tracks shell presents read-only Track Studio labels` because `index.html` lacked `>Track Studio<`.

Implemented change:

- Replaced the static Track detail heading with `Track Studio`.

Verification:

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
```

Result: both pass.

Residue scan:

```bash
rg -n "Track detail|textarea|composer|submit|resolve|/api/tracks/.*/comments" tools/launcher/assets/web-management tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js
```

Result: no `Track detail` heading and no production Track write route. Remaining hits are test negative assertions, promise variable names, the shared `resolveStatusTone()` helper, and non-Track textarea usage for direct IM/copy-command behavior.

## Risks And Boundary Checks

- Risk: adding a comment composer to make comments feel interactive. Do not add write UI or routes.
- Risk: hiding Track comments to avoid write complexity. Keep read-only comment threads visible from current API data.
- Risk: matching regex on unrelated `textarea` used for copy command. Interpret residue scans by scoped production surface and test intent.

Boundary check:

```bash
git diff --name-only | rg -v '^(tools/launcher/assets/web-management/(index\.html|styles\.css|app\.js)|tests/(web_management_ui_contract\.test\.js|web_management_ui_state\.test\.js)|docs/spec/2026-07-01-webui-team-room-stage-[1234567].*\.md)$'
```

Expected during Stage 7: no output, ignoring pre-existing untracked memo files.
