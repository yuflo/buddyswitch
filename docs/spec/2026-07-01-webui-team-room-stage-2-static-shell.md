# WebUI Team Room Stage 2 Static Shell

## Stage Goal

Replace the static Actor Console shell with the Team Room shell in `index.html` and layout CSS, while preserving existing DOM ids needed by the current JavaScript and existing backend API surface. This stage satisfies memo Task 2 and turns the Stage 1 red contract green for static shell copy and primary navigation.

## Associated Memo Tasks

- `docs/memo/2026-07-01-webui-team-room-forward-implementation-plan.md` Task 2: Replace The Static Shell In Place.

## Read And Confirmed Code Locations

- `tests/web_management_ui_contract.test.js`: Stage 1 now requires `Team room` and `Tracks` as the only primary tabs but still has old actor-console layout marker assertions that must be replaced.
- `tools/launcher/assets/web-management/index.html`: old sidebar shows `Actors` and `Create Actor`; actor view uses `.actor-console-grid`, `.actor-roster-panel`, `.console-column`, and `.runtime-column`.
- `tools/launcher/assets/web-management/styles.css`: old layout selectors are `.actor-console-grid`, `.console-column`, and `.runtime-column`, with media rules at `1180px` and `960px`.
- `tools/launcher/assets/web-management/app.js`: existing JavaScript relies on stable ids such as `role-select`, `create-button`, `actor-console`, `instruction-input`, and lifecycle buttons. Stage 2 must not require JS rewiring.

## Current Problems And Residue Points

- Contract test is red because `>Team room<` is absent from `index.html`.
- Primary nav currently parses as `['Actors', 'Tracks']`.
- Static layout class names still teach `actor-console` semantics.
- The visible sidebar creation block says `Create Actor`, which is forbidden by the new shell.

## Development Change Scope

Modify:

- `tests/web_management_ui_contract.test.js`
- `tools/launcher/assets/web-management/index.html`
- `tools/launcher/assets/web-management/styles.css`

## Explicit Non-Scope

- No changes to `tools/launcher/assets/web-management/app.js`.
- No changes to backend files, runtime services, DTOs, object stores, env tools, or API routes.
- No feature flag, compatibility tab, hidden legacy shell, or alternate render path.
- No Track Studio detail reshaping beyond keeping existing Track shell reachable.

## TDD And Test Plan

1. Update contract layout assertions to require Team Room static markers:
   - `.team-room-grid`
   - `.teammate-roster-panel`
   - `.conversation-column`
   - `.teammate-card`
2. Run `node tests/web_management_ui_contract.test.js` and confirm it remains red on current production assets for missing Team Room shell markers.
3. Replace `index.html` visible copy and structure:
   - primary nav label `Actors` -> `Team room`
   - page title and summary -> Team Room copy
   - `Create Actor` sidebar block removed from primary rail
   - existing role/create controls moved into teammate roster as `Start teammate`
   - actor view class -> `team-room-view`
   - main grid class -> `team-room-grid`
   - left panel -> `teammate-roster-panel`
   - center panel -> `conversation-column`
   - right panel -> `teammate-card`
4. Replace CSS selectors and media rules for Team Room names.
5. Run focused contract and state tests.

## Expected Failing Test

Command after test assertion update and before production shell replacement:

```bash
node tests/web_management_ui_contract.test.js
```

Expected red:

- Missing `>Team room<`.
- Missing `.team-room-grid` and Team Room layout markers if the copy assertion is temporarily satisfied.
- Failure must be from current stale production assets, not JavaScript syntax or missing ids.

## Implementation Steps

1. Replace the contract test named `production html uses the actor-console workspace layout` with Team Room layout assertions.
2. Replace the contract test named `production stylesheet supports actor console and track workspace states` with Team Room stylesheet assertions.
3. Run the focused contract test and confirm red.
4. Patch `index.html` with the Team Room three-column shell, preserving all ids listed by the id contract.
5. Move `role-select` and `create-button` into the teammate roster panel with visible `Start teammate` copy and no `Create Actor` text.
6. Patch `styles.css` to replace old actor-console layout class selectors with Team Room class selectors and responsive stacking.
7. Run focused tests.

## Acceptance Commands

```bash
node tests/web_management_ui_contract.test.js
node tests/web_management_ui_state.test.js
```

Expected result after implementation:

- Both commands exit `0`.
- Contract test proves the new static shell copy, exactly two primary tabs, and no old `Create Actor` / `Actor Console` shell copy.
- State tests prove the existing JavaScript behavior still runs with stable ids and unchanged route builders.

## Residue Scan Command

```bash
rg -n "Actor Console|>Actors<|Create Actor|Runtime health|>Artifacts<|Workstream OS|Capacity|sideThreads|side-thread|Refresh mock|Mock data|terminal selector|capacity bar|unread-badge|/api/web/im|/api/tracks/.*/comments|actor-console-grid|console-column|runtime-column|actor-roster-panel" tools/launcher/assets/web-management tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Expected after Stage 2:

- No positive production asset hits for `Actor Console`, `>Actors<`, `Create Actor`, or old layout class names.
- Test-only negative gates may still mention forbidden strings.
- `app.js` may still contain internal `Actor Console` section-copy text until Stage 3; that is explicitly queued for the next stage and remains covered by the scan.

## Stage Completion Standard

- Stage 2 spec exists before production edits.
- Focused contract test is red before production changes and green after production shell replacement.
- State tests remain green.
- Static shell visibly uses Team Room semantics and no visible `Create Actor` sidebar block.
- Product code changes are confined to `tools/launcher/assets/web-management/index.html` and `tools/launcher/assets/web-management/styles.css`.

## Stage 2 Result

Implemented contract changes:

- Replaced old static layout assertions with Team Room layout markers.
- Required `.team-room-grid`, `.teammate-roster-panel`, `.conversation-column`, `.teammate-card`, and related stylesheet selectors.

Expected red before production shell replacement:

```bash
node tests/web_management_ui_contract.test.js
```

Result: failed at `production html uses the Team Room workspace layout` because the current asset did not yet include `class="view-section team-room-view"`.

Implemented production changes:

- Primary nav now renders `Team room` and `Tracks`.
- Page title/summary now use Team Room copy.
- The old visible sidebar `Create Actor` block is removed.
- Existing create controls keep `role-select` and `create-button` ids, but are now a compact `Start teammate` control inside the teammate roster.
- Static actor shell classes were replaced with Team Room classes.
- Direct conversation static markup moved into the center conversation column.
- The right panel is now the selected teammate card for runtime, task, Track, TUI, lifecycle, and status facts.

Verification:

```bash
node tests/web_management_ui_contract.test.js
node tests/web_management_ui_state.test.js
```

Result: both pass.

Residue scan:

```bash
rg -n "Actor Console|>Actors<|Create Actor|Runtime health|>Artifacts<|Workstream OS|Capacity|sideThreads|side-thread|Refresh mock|Mock data|terminal selector|capacity bar|unread-badge|/api/web/im|/api/tracks/.*/comments|actor-console-grid|console-column|runtime-column|actor-roster-panel" tools/launcher/assets/web-management tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Result: no static-shell production hits remain. Remaining `Actor Console` hits are `app.js` dynamic section copy and the matching state test, both owned by Stage 3. Test-only route and residue exclusions remain as negative gates.

## Risks And Boundary Checks

- Risk: removing `role-select` and `create-button` would break current JS binding. Preserve the ids and only change visible semantics.
- Risk: old class names can survive as hidden compatibility structure. Replace class names directly instead of adding aliases.
- Risk: Stage 3 still owns dynamic `sectionCopy()` text in `app.js`; do not mix that work into Stage 2.

Boundary check:

```bash
git diff --name-only | rg -v '^(tools/launcher/assets/web-management/(index\.html|styles\.css)|tests/web_management_ui_contract\.test\.js|docs/spec/2026-07-01-webui-team-room-stage-[12].*\.md)$'
```

Expected during Stage 2: no output, ignoring pre-existing untracked memo files.
