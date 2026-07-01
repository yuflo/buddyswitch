# WebUI Team Room Stage 4 Teammate Roster

## Stage Goal

Render actors as teammates using only supported role, actor id, runtime status, and health fields. Stage 4 covers memo Task 4 and adds a focused renderer test plus residue guards against fake teammate facts.

## Associated Memo Tasks

- `docs/memo/2026-07-01-webui-team-room-forward-implementation-plan.md` Task 4: Render Actors As Teammates With Supported Data Only.

## Read And Confirmed Code Locations

- `tools/launcher/assets/web-management/app.js`: `renderActorRowsHtml(state)` currently renders actor id as the title, raw role id as the subtitle, runtime status, and app server health. It is not exported.
- `tests/web_management_ui_state.test.js`: currently has no direct roster projection test.
- `tests/web_management_ui_contract.test.js`: currently blocks old route and mock-only controls but does not explicitly block fake teammate facts such as avatar, unread, load, or capacity.

## Current Problems And Residue Points

- The visible roster still reads as an actor id list rather than a teammate-role list.
- The renderer does not resolve `state.roles[].label`.
- The renderer helper is not exported, so the projection is not directly covered.
- No explicit contract guard prevents fake teammate fields from entering static assets.

## Development Change Scope

Modify:

- `tests/web_management_ui_state.test.js`
- `tests/web_management_ui_contract.test.js`
- `tools/launcher/assets/web-management/app.js`

## Explicit Non-Scope

- No backend, DTO, route, persistence, env tool, or runtime changes.
- No fake people fields, generated avatars, unread counters, load percentages, capacity bars, availability scores, or presence fiction.
- No rapid actor selection race fix; that belongs to Task 5.
- No Track Studio rendering changes; that belongs to Task 7.

## TDD And Test Plan

1. Add a state test that calls `app.renderActorRowsHtml(state)` with:
   - role `{ id: 'dev', label: 'Developer' }`
   - actor id `act-dev-demo`
   - runtime status `active`
   - app server health `healthy`
2. Assert that output includes `Developer`, `act-dev-demo`, `active`, and `healthy`.
3. Assert output does not match fake facts: `avatar`, `unread`, `load`, `capacity`, `focus`.
4. Run state tests and confirm red because `renderActorRowsHtml` is not exported yet.
5. Add `roleLabelById(state, roleId)` and use it in `renderActorRowsHtml()`.
6. Export `renderActorRowsHtml`.
7. Add contract guards for fake teammate facts in combined production assets.
8. Run focused state and contract tests.

## Expected Failing Test

Command after adding the state test and before implementation:

```bash
node tests/web_management_ui_state.test.js
```

Expected red:

- `teammate roster uses role label, actor id, status, and health without fake people fields` fails because `app.renderActorRowsHtml` is not exported.
- After export, the same test would fail if the renderer kept raw role id instead of `Developer`.

## Implementation Steps

1. Add the roster projection test to `tests/web_management_ui_state.test.js`.
2. Run the state test and record expected red.
3. Add `roleLabelById(state, roleId)` in `app.js`.
4. Update `renderActorRowsHtml()` so row title is the role label and actor id remains secondary in monospace.
5. Export `renderActorRowsHtml`.
6. Add fake teammate fact guards to `tests/web_management_ui_contract.test.js`.
7. Run focused state and contract tests.

## Acceptance Commands

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
```

Expected result after implementation:

- Both commands exit `0`.
- The roster test proves supported data only.
- Contract tests block fake teammate facts.

## Residue Scan Command

```bash
rg -n "avatar|unread|current focus|load percentage|capacity bar|availability score" tools/launcher/assets/web-management tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Expected after Stage 4:

- Production assets have no positive hits.
- Test-only negative assertions are allowed.

## Stage Completion Standard

- Stage 4 spec exists before code edits.
- The roster projection test fails before implementation.
- `renderActorRowsHtml()` uses role label, actor id, status, and health only.
- Fake teammate fact residue guards are in the contract test.
- Focused state and contract tests pass.

## Stage 4 Result

Expected red before implementation:

```bash
node tests/web_management_ui_state.test.js
```

Result: failed at `teammate roster uses role label, actor id, status, and health without fake people fields` because `app.renderActorRowsHtml` was not exported.

Implemented changes:

- Added `roleLabelById(state, roleId)`.
- Updated `renderActorRowsHtml()` so the row title is the role label and the actor id remains visible as monospace secondary text.
- Exported `renderActorRowsHtml`.
- Added a contract test that blocks fake teammate facts in production assets.

Verification:

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
```

Result: both pass.

Residue scan:

```bash
rg -n "avatar|unread|current focus|load percentage|capacity bar|availability score" tools/launcher/assets/web-management tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Result: only test negative assertions match; production assets have no positive fake-fact hits.

## Risks And Boundary Checks

- Risk: making teammate identity prettier by inventing unsupported people fields. Do not add any such field.
- Risk: removing actor id would hide the stable runtime identity. Keep actor id visible as secondary text.
- Risk: broad UI changes would mix this stage with later shell/layout work. Keep the change inside the roster projection.

Boundary check:

```bash
git diff --name-only | rg -v '^(tools/launcher/assets/web-management/(index\.html|styles\.css|app\.js)|tests/(web_management_ui_contract\.test\.js|web_management_ui_state\.test\.js)|docs/spec/2026-07-01-webui-team-room-stage-[1234].*\.md)$'
```

Expected during Stage 4: no output, ignoring pre-existing untracked memo files.
