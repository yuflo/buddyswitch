# Phase 08: Browser Smoke And End-To-End Acceptance

## Phase Goal

Verify the rebuilt WebUI behavior through focused Node tests, residue scans, scope checks, and browser smoke at `http://127.0.0.1:8765/` if the local WebUI can be started or is already running.

## Source Requirements

- Memo Task 8.
- Final smoke must cover Send, actor switch, Tracks navigation, and narrow viewport priority.

## Code Research Findings

- The memo identifies the WebUI smoke URL as `http://127.0.0.1:8765/`.
- Broad service-starting tests should not be used unless lifecycle cleanup is proven; browser smoke may use an already-running or locally started WebUI.

## Scope

- No required source edits.
- Create final acceptance document after all phases are accepted.

## Non-Goals

- Do not change source files during smoke unless a verified issue is found.
- Do not modify backend routes to make smoke easier.

## Old Path / Residue Definition

- All old global-mutation/full-render residue must already be gone before this phase is accepted.

## Development Plan

1. Run focused Node UI tests.
2. Run scoped residue scans.
3. Run `git diff --check`.
4. Run `git diff --name-only` and inspect product-code scope.
5. Start or use local WebUI at `http://127.0.0.1:8765/` if feasible.
6. Smoke Send, actor switch, Tracks navigation, and narrow viewport behavior.
7. Record blocker if WebUI/browser smoke cannot be run.
8. Write `99-final-acceptance.md`.

## Test Plan

Focused commands:

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
```

Expected green result:

- Both commands exit `0`.

## Red Verification Expectation

This phase has no new code-first red test. It is an acceptance phase that must not begin until previous phase verification is green.

## Green Verification Commands

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
git diff --check
git diff --name-only
```

## Residue Scan Commands

```bash
rg -n "mutationKey|isMutating|Action running\.|runMutation\(" tools/launcher/assets/web-management/app.js tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js -S
rg -n "querySelectorAll\('\[data-actor-id\]'\)|querySelectorAll\('\[data-track-id\]'\)" tools/launcher/assets/web-management/app.js -S
rg -n "POST /api/web/im|/api/web/im|buildWebImConversationUrl|ensureWebImSession|connection_key|participant_token|event_cursor|cursor=" tools/launcher/assets/web-management/app.js tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js -S
```

## Acceptance Criteria

- Focused tests pass.
- Residue scans pass or hits are explicitly justified as current semantics.
- Product-code diff stays inside memo-approved WebUI boundary.
- Browser smoke evidence is recorded, or a clear blocker is recorded.
- Final acceptance document is written.

## Execution Record

- Verified no server was initially listening on `127.0.0.1:8765`.
- Started Web Management with `./buddyswitch-codex web --host 127.0.0.1 --port 8765`.
- Opened `http://127.0.0.1:8765/` in Playwright.
- Created two temporary actors through the UI because no actors existed at smoke start.
- Added a browser-only delayed `fetch` wrapper for `/api/im/messages` so pending send state could be inspected before the backend response.
- Smoked send pending and accepted states.
- Smoked actor switch immediate selection, empty history, loading detail, and stale-banner removal.
- Smoked Tracks/Actors navigation title and summary switching.
- Smoked `390x844` viewport layout and captured screenshot `webui-smoothness-mobile-smoke.png`.
- Stopped and deleted both temporary actors through the Web Management API; refreshed actor list showed `No actors available.`

## Test Results

Focused verification:

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

Whitespace and scope:

```text
$ git diff --check
<no output>
exit 0

$ git diff --name-only
tests/web_management_ui_contract.test.js
tests/web_management_ui_state.test.js
tools/launcher/assets/web-management/app.js
tools/launcher/assets/web-management/index.html
tools/launcher/assets/web-management/styles.css
```

## Residue Results

All final residue scans were clean:

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

Browser smoke evidence:

```text
Send pending immediate state:
- draftValue: ""
- sendText: "Sending..."
- sendDisabled: true
- refreshDisabled/openTuiDisabled/clearDisabled/stopDisabled: false
- IM rows included class "im-row sent pending" with text containing "sending"

Send accepted state:
- status: "Sent message msg-8632e45832bf (accepted)."
- pending row replaced with class "im-row sent"

Actor switch immediate state:
- selected: act-market-d5459476b194
- runtimeText: "Actoract-market-d5459476b194StatusLoading..."
- rows: []
- status: ""

Tracks navigation:
- Track title: "Track workspace"
- Track summary: "Review shared Tracks, materials, proofs, updates, and comments."
- Actor title restored to "Actor Console"

Mobile 390x844:
- actionBeforeRuntimeDetail: true
- textareaFullyVisible: true
- sendFullyVisible: true
- all button text fits
```

## Phase Acceptance Decision

Accepted.

## Remaining Risk

Console logs include expected `404` resource entries for new actors with no direct conversation yet. This is the preserved backend `E_IM_NOT_FOUND` behavior and the UI renders it as empty history.
