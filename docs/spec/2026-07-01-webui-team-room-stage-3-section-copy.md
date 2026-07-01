# WebUI Team Room Stage 3 Section Copy

## Stage Goal

Replace remaining dynamic Actor Console section copy with Team Room and Tracks copy in the JavaScript state projection. Stage 3 covers memo Task 3 only and keeps internal `selectedSection: 'actors'` unchanged because it maps to current `/api/actors` contracts.

## Associated Memo Tasks

- `docs/memo/2026-07-01-webui-team-room-forward-implementation-plan.md` Task 3: Replace Section Copy And State Tests.

## Read And Confirmed Code Locations

- `tools/launcher/assets/web-management/app.js`: `sectionCopy()` currently returns `Actor Console` for the actor section and `Track workspace` for Tracks.
- `tests/web_management_ui_state.test.js`: current default-state test is named around actor console and the section copy test expects old copy.
- `tests/web_management_ui_contract.test.js`: static shell contract is green after Stage 2 and excludes `Actor Console` from `index.html`.
- `tools/launcher/assets/web-management/index.html`: static shell already starts as `Team room`.

## Current Problems And Residue Points

- Dynamic render path can still write `Actor Console` into `page-title`.
- Dynamic render path can still write old actor-centered summary copy into `page-summary`.
- State test still accepts old section copy, so the old dynamic model is not yet blocked.
- Tracks dynamic copy still says `Track workspace`, while the new destination should read `Tracks`.

## Development Change Scope

Modify:

- `tests/web_management_ui_state.test.js`
- `tools/launcher/assets/web-management/app.js`

## Explicit Non-Scope

- No static HTML/CSS work in this stage.
- No route, DTO, backend, service, persistence, env tool, or object-store changes.
- No actor selection race fix; that belongs to Task 5.
- No teammate roster projection changes; that belongs to Task 4.
- No Track Studio detail rendering changes; that belongs to Task 7.

## TDD And Test Plan

1. Rename and update the default-state test to say the visible primary section is Team Room while the internal section key remains `actors`.
2. Replace `section copy follows selected workspace` expectations with Team Room and Tracks copy from the memo.
3. Run `node tests/web_management_ui_state.test.js` and confirm red because `app.sectionCopy('actors')` still returns `Actor Console`.
4. Replace `sectionCopy()` in `app.js` with the new copy.
5. Run focused state and contract tests.

## Expected Failing Test

Command after state test update and before implementation:

```bash
node tests/web_management_ui_state.test.js
```

Expected red:

- `section copy follows Team room and Tracks destinations` fails because the current implementation returns `Actor Console` / `Track workspace`.
- Failure must be an assertion mismatch, not a syntax or module load error.

## Implementation Steps

1. Update `tests/web_management_ui_state.test.js` default-state test name to `state defaults to Team room as the primary section`.
2. Update the section copy test to expect:
   - actors: `Team room`, `Message teammates, inspect current runtime facts, and keep coordination in one room.`
   - tracks: `Tracks`, `Review Track outcomes, current state, materials, proofs, updates, and comments.`
3. Run the state test and record expected red.
4. Patch `sectionCopy()` in `app.js` with the same copy.
5. Run focused state and contract tests.

## Acceptance Commands

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
```

Expected result after implementation:

- Both commands exit `0`.
- `rg -n "Actor Console|Track workspace" tools/launcher/assets/web-management tests/web_management_ui_state.test.js` has no positive hits.

## Residue Scan Command

```bash
rg -n "Actor Console|Track workspace|Select an actor, inspect runtime and task state|Review shared Tracks" tools/launcher/assets/web-management tests/web_management_ui_state.test.js
```

Expected after Stage 3:

- No output.

## Stage Completion Standard

- Stage 3 spec exists before code edits.
- State test fails first on old dynamic copy.
- `app.js` dynamic copy returns Team Room and Tracks copy.
- Focused state and contract tests pass.
- Dynamic Actor Console residue is removed from production WebUI assets.

## Stage 3 Result

Expected red before implementation:

```bash
node tests/web_management_ui_state.test.js
```

Result: failed at `section copy follows Team room and Tracks destinations` because `app.sectionCopy('actors')` still returned:

```text
Actor Console
Select an actor, inspect runtime and task state, message directly, and use lifecycle controls in one place.
```

Implemented production change:

- Replaced `sectionCopy()` output with Team Room and Tracks copy.

Verification:

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
```

Result: both pass.

Residue scan:

```bash
rg -n "Actor Console|Track workspace|Select an actor, inspect runtime and task state|Review shared Tracks" tools/launcher/assets/web-management tests/web_management_ui_state.test.js
```

Result: no matches.

## Risks And Boundary Checks

- Risk: renaming internal `selectedSection` from `actors` would create unnecessary JS churn. Keep the internal key as `actors` for now.
- Risk: changing Track rendering early could mix Task 7 into this stage. Only update title/summary copy.

Boundary check:

```bash
git diff --name-only | rg -v '^(tools/launcher/assets/web-management/(index\.html|styles\.css|app\.js)|tests/(web_management_ui_contract\.test\.js|web_management_ui_state\.test\.js)|docs/spec/2026-07-01-webui-team-room-stage-[123].*\.md)$'
```

Expected during Stage 3: no output, ignoring pre-existing untracked memo files.
