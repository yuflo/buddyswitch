# WebUI Interaction Smoothness Final Acceptance

## Source Memo

[WebUI Interaction Smoothness Forward Plan](../../memo/2026-06-30-webui-interaction-smoothness-forward-plan.md)

## Phase Status

- `00-orientation.md`: complete.
- `phase-01-action-scoped-pending-state.md`: accepted.
- `phase-02-focused-render-functions.md`: accepted.
- `phase-03-row-event-delegation.md`: accepted.
- `phase-04-focused-send-action.md`: accepted.
- `phase-05-focused-lifecycle-refresh-selection.md`: accepted.
- `phase-06-residue-cleanup.md`: accepted.
- `phase-07-css-feedback-mobile-priority.md`: accepted.
- `phase-08-browser-smoke-e2e.md`: accepted.

## Acceptance Matrix

| Memo acceptance criterion | Evidence |
| --- | --- |
| Send clears the input before the network response returns. | Browser smoke delayed `/api/im/messages`; immediate state had `draftValue: ""`. |
| Send no longer calls `refreshAll()`. | `sendCurrentDraft()` calls `refreshSelectedActorConsole()` only; Phase 06 residue gates remove old send `runMutation()` path. |
| Send pending disables only Send. | State test `send pending disables only send while preserving independent actor controls`; browser smoke had Send disabled and Refresh/Open TUI/Clear/Stop enabled. |
| Lifecycle pending disables lifecycle buttons without disabling Send. | State test `lifecycle pending disables lifecycle buttons without disabling send`. |
| Open TUI pending disables only Open TUI. | State test `open tui pending disables only open tui`. |
| Manual Refresh has pending/completion feedback. | `refreshAllWithFeedback()` sets `refreshPending`, `Refreshing...`, and final `Refreshed.`; contract test verifies pending CSS support. |
| Typing in textarea does not rerender actor rows, track rows, runtime details, or conversation. | State test `renderComposer updates the input and send button without actor list writes`; Phase 06 contract gate excludes input full-render path. |
| Actor row click handlers are installed once through event delegation. | Phase 03 contract test and residue scan exclude render-time row listener installation. |
| Actor selection has immediate selected-row and empty-history feedback. | Browser smoke actor switch immediate state: selected actor changed, rows were `[]`, runtime showed `Loading...`. |
| Section title and summary match the active section. | State test `section copy follows selected workspace`; browser smoke verified Track and Actor titles/summaries. |
| `E_IM_NOT_FOUND` remains backend 404 but renders as empty WebUI history. | State test `selected actor conversation treats missing direct conversation as empty history`; browser smoke console showed expected 404 resource entries for new actors while UI rendered empty history. |
| No backend route, IM service, runtime object, or product persistence file is modified. | `git diff --name-only` tracked product-code output contains only the five memo-approved WebUI files. |
| Scoped residue scans show no global mutation state or old Web IM route residue in live WebUI surfaces. | Final scans for global mutation, render-time row handlers, and old Web IM route residue returned no output. |

## Final Verification

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

## Browser Smoke

Server:

```text
$ ./buddyswitch-codex web --host 127.0.0.1 --port 8765
BuddySwitch web management listening on http://127.0.0.1:8765
```

Smoke summary:

- Page loaded at `http://127.0.0.1:8765/` with title `BuddySwitch Web Management`.
- Created temporary actors because no actors existed at smoke start.
- Send pending state with delayed `/api/im/messages`: draft cleared, Send showed `Sending...`, one pending row appeared, and Refresh/Open TUI/Clear/Stop stayed enabled.
- Send accepted state: final banner showed `Sent message msg-8632e45832bf (accepted).`
- Actor switch: selected row changed immediately, stale messages disappeared immediately, runtime detail showed `Loading...`, and stale success banner was cleared.
- Tracks navigation changed title/summary to Track copy and restored Actor copy on return.
- Mobile `390x844`: Actions appeared before runtime detail, textarea and Send were fully visible, and button text fit.
- Screenshot evidence: `webui-smoothness-mobile-smoke.png` from Playwright output.
- Temporary actors were stopped and deleted through Web Management API; refreshed actor list showed `No actors available.`

## Remaining Risk

- Browser console resource errors for direct conversation `404` are expected for actors with no direct conversation yet; this preserves backend `E_IM_NOT_FOUND` as `404` while the UI shows empty history.
- Live backend latency remains outside this frontend-only scope.
