# WebUI Team Room Stage 8 CSS Residue Pass

## Stage Goal

Finish the restrained product-tool CSS pass without adding decorative product fiction. Stage 8 covers memo Task 8: keep Team Room and Track Studio as utilitarian layouts, preserve responsive stacking, and block fake visual markers such as capacity bars, avatars, unread badges, blobs, or mock metrics.

## Associated Memo Tasks

- `docs/memo/2026-07-01-webui-team-room-forward-implementation-plan.md` Task 8: Final CSS Pass Without Adding Decorative Product Fiction.

## Read And Confirmed Code Locations

- `tools/launcher/assets/web-management/styles.css`: Team Room uses `.team-room-grid`, but Tracks still uses `.track-workspace-grid`.
- `tools/launcher/assets/web-management/index.html`: Tracks wrapper still uses `class="track-workspace-grid"`.
- `tests/web_management_ui_contract.test.js`: current stylesheet contract does not yet require `.track-studio-grid` or block decorative CSS marker classes.

## Current Problems And Residue Points

- Track Studio static copy is correct, but layout class naming still says `track-workspace-grid`.
- No explicit contract prevents decorative classes such as `orb`, `blob`, `capacity-bar`, `avatar-stack`, `unread-badge`, or `fake-metric`.
- Responsive rules stack the grids at `960px`; this is acceptable, but the final class name should match Track Studio semantics.

## Development Change Scope

Modify:

- `tests/web_management_ui_contract.test.js`
- `tools/launcher/assets/web-management/index.html`
- `tools/launcher/assets/web-management/styles.css`

## Explicit Non-Scope

- No JavaScript behavior changes.
- No backend, route, DTO, env tool, runtime, service, or object-store changes.
- No visual decoration, fake metrics, avatars, unread badges, capacity bars, gradient orbs, or blobs.
- No unrelated CSS refactor.

## TDD And Test Plan

1. Update the contract stylesheet/layout test to require `.track-studio-grid` and `class="track-studio-grid"`.
2. Add a decorative/fake CSS marker guard.
3. Run the focused contract test and confirm red because current assets still use `track-workspace-grid`.
4. Rename `track-workspace-grid` to `track-studio-grid` in `index.html` and `styles.css`.
5. Run focused tests and residue scan.

## Expected Failing Test

Command after contract update and before implementation:

```bash
node tests/web_management_ui_contract.test.js
```

Expected red:

- Contract fails because `class="track-studio-grid"` or `.track-studio-grid` is missing.

## Implementation Steps

1. Add Track Studio grid markers to `tests/web_management_ui_contract.test.js`.
2. Add forbidden decorative/fake marker checks to the contract test.
3. Run focused contract test and record red.
4. Patch `index.html` to use `class="track-studio-grid"`.
5. Patch `styles.css` base and responsive selectors from `.track-workspace-grid` to `.track-studio-grid`.
6. Run focused state and contract tests.

## Acceptance Commands

```bash
node tests/web_management_ui_contract.test.js
node tests/web_management_ui_state.test.js
```

Expected result after implementation:

- Both commands exit `0`.
- `.team-room-grid` and `.track-studio-grid` are present.
- Decorative/fake marker guard passes.

## Residue Scan Command

```bash
rg -n "track-workspace-grid|orb|blob|capacity-bar|avatar-stack|unread-badge|fake-metric" tools/launcher/assets/web-management tests/web_management_ui_contract.test.js
```

Expected after Stage 8:

- No production hits.
- Test-only forbidden-marker assertions are allowed.

## Stage Completion Standard

- Stage 8 spec exists before code edits.
- Contract test fails first on missing Track Studio grid class.
- Track layout class is renamed to `.track-studio-grid`.
- Decorative/fake CSS markers are blocked by test.
- Focused state and contract tests pass.

## Stage 8 Result

Expected red before implementation:

```bash
node tests/web_management_ui_contract.test.js
```

Result: failed at `production html uses the Team Room and Track Studio workspace layout` because `class="track-studio-grid"` was missing.

Implemented changes:

- Renamed the Track layout wrapper from `track-workspace-grid` to `track-studio-grid`.
- Updated base and responsive CSS selectors.
- Added decorative/fake marker guard to the contract test.

Verification:

```bash
node tests/web_management_ui_contract.test.js
node tests/web_management_ui_state.test.js
```

Result: both pass.

Residue scan:

```bash
rg -n "track-workspace-grid|orb|blob|capacity-bar|avatar-stack|unread-badge|fake-metric" tools/launcher/assets/web-management tests/web_management_ui_contract.test.js
```

Result: only test negative assertions match; production assets have no positive hits.

## Risks And Boundary Checks

- Risk: doing broad CSS polish in a residue stage. Keep changes to naming and guard coverage unless a test exposes a real issue.
- Risk: removing responsive stacking while renaming classes. Update both base and media selectors.
- Risk: scanning common words too broadly. Use exact class-like markers for decorative/fake residue.

Boundary check:

```bash
git diff --name-only | rg -v '^(tools/launcher/assets/web-management/(index\.html|styles\.css|app\.js)|tests/(web_management_ui_contract\.test\.js|web_management_ui_state\.test\.js)|docs/spec/2026-07-01-webui-team-room-stage-[12345678].*\.md)$'
```

Expected during Stage 8: no output, ignoring pre-existing untracked memo files.
