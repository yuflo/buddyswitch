# WebUI Team Room Stage 1 Shell Contract

## Stage Goal

Lock the first visible Team Room shell contract in focused tests before changing production assets. Stage 1 covers memo Task 1 only: the static WebUI must be tested as having `Team room` and `Tracks` as the only primary destinations, and the old Actor Console shell terms must become explicit residue failures.

## Associated Memo Tasks

- `docs/memo/2026-07-01-webui-team-room-forward-implementation-plan.md` Task 1: Lock The New Shell Contract First.

## Read And Confirmed Code Locations

- `AGENTS.md`: rebuild-forward, testing-bound development, no compatibility-first preservation.
- `docs/bitter/*.md`: residue cleanup requires behavior proof plus scoped scans; interface projections must not become product owners; service-starting tests need lifecycle cleanup.
- `tools/launcher/assets/web-management/index.html`: currently shows `Actors`, `Create Actor`, `Actor Console`, and actor-console layout markers.
- `tools/launcher/assets/web-management/app.js`: current API surface uses existing `/api/actors`, `/api/tracks`, `/api/im/*`, and lifecycle routes.
- `tools/launcher/assets/web-management/styles.css`: current stylesheet supports actor console layout markers.
- `tests/web_management_ui_contract.test.js`: currently asserts actor-centered shell copy as positive behavior.
- `tests/web_management_ui_state.test.js`: currently passes and will be handled in later stages.

## Current Problems And Residue Points

- Current focused tests pass while asserting the old shell as correct.
- Current live residue scan finds `Actor Console` in `app.js`, `index.html`, and tests.
- Current `index.html` includes visible `Actors` and `Create Actor`.
- Stage 1 intentionally changes tests first so these old live surfaces become red before implementation.

Baseline commands already run:

```bash
node tests/web_management_ui_contract.test.js
node tests/web_management_ui_state.test.js
rg -n "Actor Console|>Actors<|Create Actor|Runtime health|>Artifacts<|Workstream OS|Capacity|sideThreads|side-thread|Refresh mock|Mock data|terminal selector|capacity bar|unread-badge|/api/web/im|/api/tracks/.*/comments" tools/launcher/assets/web-management tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Baseline result:

- Both Node focused tests pass.
- The residue scan reports positive old-shell hits in `index.html`, `app.js`, and current tests.

## Development Change Scope

Modify only:

- `tests/web_management_ui_contract.test.js`

Optional later in the same memo task if required by static serving assertions:

- `tests/test_web_management.py`

Stage 1 must not modify production assets.

## Explicit Non-Scope

- No changes to `tools/launcher/assets/web-management/index.html`.
- No changes to `tools/launcher/assets/web-management/app.js`.
- No changes to `tools/launcher/assets/web-management/styles.css`.
- No backend, runtime, DTO, env tool, object-store, route, adapter, feature flag, or compatibility render path changes.
- No edits under `buddyswitch/objects/**` or `buddyswitch/local/private/**`.

## TDD And Test Plan

1. Update `tests/web_management_ui_contract.test.js` so old actor-centered copy is no longer a passing contract.
2. Add a primary navigation count guard that parses `<nav class="sidebar-nav">` and requires exactly `['Team room', 'Tracks']`.
3. Add side-thread and Track write route residue exclusions to the existing JavaScript API-surface test.
4. Run the focused contract test and confirm it fails for the intended reason: current production assets still show `Actors`, `Create Actor`, and `Actor Console`, and do not yet show `Team room`.

## Expected Failing Test

Command:

```bash
node tests/web_management_ui_contract.test.js
```

Expected Stage 1 red result:

- The Team Room copy contract fails because `index.html` does not yet include `>Team room<`.
- The primary navigation guard fails because the current labels are `Actors` and `Tracks`.
- Any failure must point at stale shell copy, not a syntax error or missing fixture.

## Implementation Steps

1. Replace `production assets present actor-centered console wording` with `production assets present Team room and Tracks as the only primary tabs`.
2. Add `primary navigation has exactly two visible destinations`.
3. Extend forbidden API-route fragments with side-thread close/open and Track comments write route checks.
4. Keep existing real API surface positive assertions intact.
5. Run the focused contract test and record the red output in this spec.

## Acceptance Commands

Stage 1 is accepted when this command has the expected red failure:

```bash
node tests/web_management_ui_contract.test.js
```

The state test is not expected to change in Stage 1, but can be used as a sanity check:

```bash
node tests/web_management_ui_state.test.js
```

## Residue Scan Command

Use this scan to confirm the expected current residue is now test-covered and ready for removal in Stage 2:

```bash
rg -n "Actor Console|>Actors<|Create Actor|Runtime health|>Artifacts<|Workstream OS|Capacity|sideThreads|side-thread|Refresh mock|Mock data|terminal selector|capacity bar|unread-badge|/api/web/im|/api/tracks/.*/comments" tools/launcher/assets/web-management tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Positive hits in production assets are expected before Stage 2. Hits in tests are acceptable only when they are negative gates or expected-red assertions.

## Stage Completion Standard

- Stage 1 docs/spec exists before production code changes.
- Focused contract test has new Team Room shell and navigation gates.
- Running the focused contract test fails for stale production shell copy.
- No production asset or backend file changes are included in this stage.

## Stage 1 Result

Implemented test changes:

- Replaced the old actor-centered positive shell-copy test with a Team Room shell contract.
- Added a primary navigation parser that requires exactly `Team room` and `Tracks`.
- Extended JavaScript route exclusions to include side-thread open/close and Track comments write routes.

Verification:

```bash
node tests/web_management_ui_contract.test.js
```

Result: expected red. The test fails at `production assets present Team room and Tracks as the only primary tabs` with:

```text
AssertionError [ERR_ASSERTION]: Expected asset content to include: >Team room<
```

Sanity check:

```bash
node tests/web_management_ui_state.test.js
```

Result: pass. Existing state tests remain green before production shell replacement.

## Risks And Boundary Checks

- Risk: over-broad residue scans could fail on negative test gates. Keep the scan scoped and interpret test-only negative assertions as allowed.
- Risk: preserving old IDs may look like old semantics. IDs remain for compatibility with current JS and are not user-facing; visible copy and render paths are the semantic contract.
- Boundary check:

```bash
git diff --name-only | rg -v '^(tests/web_management_ui_contract\.test\.js|docs/spec/2026-07-01-webui-team-room-stage-1-shell-contract\.md)$'
```

Expected during Stage 1: no output, aside from pre-existing untracked memo files outside this stage.
