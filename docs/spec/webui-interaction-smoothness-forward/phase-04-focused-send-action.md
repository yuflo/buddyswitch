# Phase 04: Focused Send Action

## Phase Goal

Make send clear the input immediately, show a pending IM row immediately, disable only Send while pending, avoid `refreshAll()`, and replace/remove the pending row based on send outcome.

## Source Requirements

- Memo Task 4.
- Send success does not call `refreshAll()`.
- Input clears before network response.
- The sent row appears immediately.
- Failed send restores caller-owned draft and removes the pending row.

## Code Research Findings

- `sendImDraft()` currently reads `state.draftText`, records sent messages directly, and is invoked through `runMutation(..., 'messages', ...)`.
- `recordImSent()` exists for accepted messages.
- There are no pending-row helpers yet.

## Scope

- Modify `tests/web_management_ui_state.test.js`.
- Modify `tools/launcher/assets/web-management/app.js`.

## Non-Goals

- Do not change backend IM routes.
- Do not change event polling contract.
- Do not introduce a second send path beside the new focused path.

## Old Path / Residue Definition

- Old: `runMutation(state, elements, 'messages', ...)` and send-owned `refreshAll()`.
- New: `recordImPendingSend()`, `replaceImPendingSend()`, `removeImEntry()`, `sendCurrentDraft()`, focused composer/conversation/detail renders.

## Development Plan

1. Add pending-send helper state tests.
2. Run focused state test and record expected red failure.
3. Add pending message helpers.
4. Change `sendImDraft()` to accept explicit content and stop recording the UI row.
5. Add `sendCurrentDraft()`.
6. Replace Send click handler with focused send handler.
7. Export pending message helpers.
8. Run focused state test and record green result.

## Test Plan

Focused command:

```bash
node tests/web_management_ui_state.test.js
```

Expected red result:

- Fails because pending-send helpers are missing.

Expected green result:

- All state tests pass.

## Red Verification Expectation

Pending-send tests fail before helper implementation.

## Green Verification Commands

```bash
node tests/web_management_ui_state.test.js
```

## Residue Scan Commands

Full send residue is cleared in Phase 06, but this phase should remove direct send use of `runMutation`:

```bash
rg -n "runMutation\(state, elements, 'messages'|content: state\.draftText|recordImSent\(state, payload, content\);" tools/launcher/assets/web-management/app.js -S
```

## Acceptance Criteria

- Pending send helper tests pass.
- Send click path uses `sendCurrentDraft()`.
- `sendImDraft()` sends explicit content.
- Send success refreshes selected actor console only, not all WebUI state.

## Execution Record

- Added pending-send helper tests.
- Updated contract API-surface assertion to require explicit `content: content` and exclude `content: state.draftText`.
- Added `recordImPendingSend()`, `replaceImPendingSend()`, and `removeImEntry()`.
- Changed `sendImDraft()` to take explicit content and stop recording UI rows directly.
- Added `sendCurrentDraft()` with immediate draft clear, pending row, send-only pending state, selected actor console refresh, and focused renders.
- Replaced the Send click handler with `sendCurrentDraft()`.
- Exported pending-send helpers.

## Test Results

Red:

```text
$ node tests/web_management_ui_state.test.js
not ok - pending sent IM message is replaced with accepted server message
TypeError: app.recordImPendingSend is not a function
exit 1
```

Contract red:

```text
$ node tests/web_management_ui_contract.test.js
not ok - production javascript keeps the real api surface
AssertionError: Expected asset content to include: content: content
exit 1
```

Green:

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

## Residue Results

Initial broad scan hit the still-valid `recordImSent()` helper declaration:

```text
$ rg -n "runMutation\(state, elements, 'messages'|content: state\.draftText|recordImSent\(state, payload, content\)" tools/launcher/assets/web-management/app.js -S
426:  function recordImSent(state, payload, content) {
```

Narrow call-site scan is clean:

```text
$ rg -n "runMutation\(state, elements, 'messages'|content: state\.draftText|recordImSent\(state, payload, content\);" tools/launcher/assets/web-management/app.js -S
<no output>
exit 1
```

## Phase Acceptance Decision

Accepted.

## Remaining Risk

Lifecycle, delete, refresh, Open TUI, selection, and final full-render cleanup remain for later phases.
