# WebUI Team Room Stage 9 Acceptance Verification

## Stage Goal

Run the final completion gate for the WebUI Team Room forward redesign. Stage 9 covers memo Task 9: focused JavaScript tests, narrow Python static/API tests, scoped residue scan, implementation boundary check, and browser smoke with cleanup.

## Associated Memo Tasks

- `docs/memo/2026-07-01-webui-team-room-forward-implementation-plan.md` Task 9: Boundary And Acceptance Verification.
- Memo Completion Gate.

## Read And Confirmed Code Locations

- `tools/launcher/assets/web-management/index.html`: static shell now uses Team Room, Tracks, direct thread, teammate card, and Track Studio labels.
- `tools/launcher/assets/web-management/app.js`: dynamic copy uses Team Room and Tracks; roster uses role labels; rapid selection uses request ids; direct IM still posts to `/api/im/messages`.
- `tools/launcher/assets/web-management/styles.css`: Team Room and Track Studio grids use restrained product-tool layout.
- `tests/web_management_ui_contract.test.js`: shell, route, placement, Track Studio, and residue gates.
- `tests/web_management_ui_state.test.js`: state, roster, selection race, IM, and Track read-only renderer tests.

## Current Problems And Residue Points

- No known implementation gaps remain before final verification.
- Browser smoke still needs to prove the served WebUI surface, not only static file assertions.
- Boundary check must account for required `docs/spec` plan files as user-mandated artifacts.

## Development Change Scope

Expected files are already modified:

- `tools/launcher/assets/web-management/index.html`
- `tools/launcher/assets/web-management/app.js`
- `tools/launcher/assets/web-management/styles.css`
- `tests/web_management_ui_contract.test.js`
- `tests/web_management_ui_state.test.js`
- `docs/spec/2026-07-01-webui-team-room-stage-*.md`

No further implementation changes are expected unless verification exposes a real gap.

## Explicit Non-Scope

- No backend, runtime, DTO, env tool, object-store, service, or route changes.
- No expansion into production deployment, release, rollback, or compatibility work.
- No editing `buddyswitch/objects/**` or `buddyswitch/local/private/**`.

## Verification Plan

1. Run focused JavaScript tests:
   - `node tests/web_management_ui_contract.test.js`
   - `node tests/web_management_ui_state.test.js`
2. Run narrow Python tests:
   - `python3 -m pytest -q tests/test_web_management.py::WebManagementProductApiTests tests/test_web_management.py::WebManagementHTTPActionTests::test_static_assets_are_served`
3. Run scoped residue scan over live WebUI surfaces and focused tests.
4. Run boundary diff check.
5. Start `./buddyswitch-codex web --host 127.0.0.1 --port 8765`.
6. Browser-smoke `http://127.0.0.1:8765/`:
   - primary nav exactly Team room and Tracks
   - Team room first screen
   - teammate roster uses supported facts only
   - direct thread center and teammate card right
   - Tracks opens Track Studio read view
   - no forbidden tabs, fake facts, side-thread UI, or Track composer
   - mobile viewport has no obvious horizontal overflow or overlapping text
7. Stop server and confirm no relevant process remains.

## Expected Results

All commands should pass. Any failure means continue implementation at the smallest responsible boundary and rerun the relevant gate.

## Acceptance Commands

```bash
node tests/web_management_ui_contract.test.js
node tests/web_management_ui_state.test.js
python3 -m pytest -q tests/test_web_management.py::WebManagementProductApiTests tests/test_web_management.py::WebManagementHTTPActionTests::test_static_assets_are_served
rg -n "Actor Console|>Actors<|Create Actor|Runtime health|>Artifacts<|Workstream OS|sideThreads|side-thread UI|Refresh mock|Mock data|terminal selector|capacity bar|unread-badge|/api/web/im|/api/tracks/.*/comments" tools/launcher/assets/web-management tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
git diff --name-only | rg -v '^(tools/launcher/assets/web-management/(index\.html|styles\.css|app\.js)|tests/(web_management_ui_contract\.test\.js|web_management_ui_state\.test\.js|test_web_management\.py)|docs/memo/|docs/spec/)'
./buddyswitch-codex web --host 127.0.0.1 --port 8765
```

## Residue Scan Interpretation

- Production asset hits for old shell terms, fake data, side-thread UI, old IM route, or Track write route are failures.
- Test-only negative gates are acceptable when they explicitly assert absence.
- Historical docs and memos are not scanned as live surfaces.

## Stage Completion Standard

- Focused Node tests pass.
- Narrow Python tests pass.
- Scoped residue scan has no positive live-surface hits.
- Boundary diff check has no unexpected paths.
- Browser smoke passes on desktop and mobile viewports.
- Server process is cleaned up.

## Stage 9 Result

Focused JavaScript tests:

```bash
node tests/web_management_ui_contract.test.js
node tests/web_management_ui_state.test.js
```

Result: both pass.

Narrow Python tests:

```bash
python3 -m pytest -q tests/test_web_management.py::WebManagementProductApiTests tests/test_web_management.py::WebManagementHTTPActionTests::test_static_assets_are_served
```

Initial result: failed because `test_static_assets_are_served` still asserted `Actor Console`, `Track workspace`, and `.actor-console-grid`.

Root cause: stale static-asset assertions after the intentional Team Room shell replacement.

Fix: updated only the static asset assertions in `tests/test_web_management.py` to require `Team room`, `Track Studio`, `.team-room-grid`, and `.track-studio-grid`, and to reject old Actor Console/static CSS residue.

Rerun result:

```text
8 passed, 2 subtests passed
```

Scoped residue scan:

```bash
rg -n "Actor Console|>Actors<|Create Actor|Runtime health|>Artifacts<|Workstream OS|sideThreads|side-thread UI|Refresh mock|Mock data|terminal selector|capacity bar|unread-badge|/api/web/im|/api/tracks/.*/comments" tools/launcher/assets/web-management tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Result: only test negative assertions matched; production assets had no positive old-shell/fake-route hits.

Boundary diff:

```bash
git diff --name-only | rg -v '^(tools/launcher/assets/web-management/(index\.html|styles\.css|app\.js)|tests/(web_management_ui_contract\.test\.js|web_management_ui_state\.test\.js|test_web_management\.py)|docs/memo/|docs/spec/)'
```

Result: no unexpected paths.

Browser smoke:

```bash
./buddyswitch-codex web --host 127.0.0.1 --port 8765
```

Desktop checks at `http://127.0.0.1:8765/`:

- Page title: `BuddySwitch Web Management`.
- Primary nav labels: `Team room`, `Tracks`.
- First screen: Team room, with Tracks hidden.
- Direct thread controls are in `.conversation-column`.
- Runtime/TUI/lifecycle actions are in `.teammate-card`.
- Forbidden old/fake terms were absent.
- No horizontal overflow.

Tracks checks:

- Clicking `Tracks` changes page title to `Tracks`.
- Track list heading is `Tracks`.
- Detail heading is `Track Studio`.
- Detail subtitle is `Outcome, current state, materials, proofs, updates, and comments`.
- No Track composer exists.
- Forbidden old/fake terms were absent.
- No horizontal overflow.

Mobile checks at `390x844`:

- Primary nav still exactly `Team room`, `Tracks`.
- Team room remains visible.
- Direct thread and teammate actions are present.
- No horizontal overflow and no overflowing elements found by bounding-box scan.
- Forbidden old/fake terms were absent.

Data-dependent browser smoke:

- Created temporary teammate `act-test-31a4d0590ea7` with role `test` through the UI.
- Roster row rendered `Test`, actor id, `active`, and `healthy`.
- Sent `Browser smoke: direct Team Room message.` through the UI.
- Wrapped page `fetch` confirmed a `POST /api/im/messages` call with `target_identity_id: "act-test-31a4d0590ea7"` and `reply_to: null`.
- Stopped and deleted the temporary teammate through the UI.
- Actor list returned to `No actors available.`

Cleanup:

```bash
lsof -nP -iTCP:8765 -sTCP:LISTEN || true
ps -axo pid,command | rg 'act-test-31a4d0590ea7|buddyswitch-codex web --host 127\.0\.0\.1 --port 8765' || true
```

Result: no listener on port `8765`; process search had no residual actor/server process beyond the search command itself.

## Risks And Boundary Checks

- Risk: browser smoke can leave a server process behind. Start the command in a tracked session and stop it explicitly.
- Risk: broad residue scans can flag negative tests. Interpret scoped test hits carefully and do not hide production hits.
- Risk: final boundary command from the memo did not include mandatory `docs/spec` files. Include `docs/spec/` as an explicitly user-required planning artifact.
