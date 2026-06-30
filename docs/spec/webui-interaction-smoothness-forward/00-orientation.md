# WebUI Interaction Smoothness Forward Orientation

## Goal

Complete every optimization task in [the WebUI interaction smoothness memo](../../memo/2026-06-30-webui-interaction-smoothness-forward-plan.md): make Web Management UI send, actor switch, refresh, and navigation interactions feel immediate while preserving backend HTTP semantics and keeping product-code changes inside the memo-approved WebUI frontend/test boundary.

## Required Sources Read

- `AGENTS.md`
- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`
- `docs/bitter/2026-05-28-parallel-change-boundary-principles.md`
- `docs/bitter/2026-06-02-residue-cleanup-principles.md`
- `docs/bitter/2026-06-02-wrong-boundary-narrowness-principles.md`
- `docs/bitter/2026-06-25-built-in-product-interface-principles.md`
- `docs/bitter/2026-06-25-end-to-end-contract-slice-principles.md`
- `docs/memo/2026-06-30-webui-interaction-smoothness-forward-plan.md`

## Scope Boundaries

Product code may change only in:

- `tools/launcher/assets/web-management/app.js`
- `tools/launcher/assets/web-management/styles.css`
- `tools/launcher/assets/web-management/index.html`
- `tests/web_management_ui_state.test.js`
- `tests/web_management_ui_contract.test.js`

Do not modify backend routes, runtime object state, product persistence files, private runtime directories, `tools/launcher/im_http_router.py`, `tools/launcher/web_management.py`, `scripts/**`, `buddyswitch/objects/**`, or `buddyswitch/local/private/**`.

Backend contract preserved:

- `GET /api/im/conversations/direct?...` may return `404` with `E_IM_NOT_FOUND`.
- The frontend adapts that selected direct conversation `404` to empty selected-actor history.

## Residue Terms

Old terms and paths that must disappear from live WebUI surfaces:

- `mutationKey`
- `isMutating`
- `Action running.`
- `runMutation(`
- render-time row click installation via `querySelectorAll('[data-actor-id]')` and `querySelectorAll('[data-track-id]')`
- input handler calling the full page `render(state, elements);`
- old Web IM route residue: `/api/web/im`, `buildWebImConversationUrl`, `ensureWebImSession`, `connection_key`, `participant_token`, `event_cursor`, `cursor=`

Current replacement terms:

- `sendPending`
- `refreshPending`
- `lifecyclePendingAction`
- `openTuiPending`
- `actorSelectionPendingId`
- `trackSelectionPendingId`
- `renderShell`
- `renderComposer`
- `renderActorList`
- `renderActorDetail`
- `renderTrackList`
- `renderTrackDetail`
- `renderOpenTui`
- `renderAll`

## Phase Index

1. `phase-01-action-scoped-pending-state.md`
2. `phase-02-focused-render-functions.md`
3. `phase-03-row-event-delegation.md`
4. `phase-04-focused-send-action.md`
5. `phase-05-focused-lifecycle-refresh-selection.md`
6. `phase-06-residue-cleanup.md`
7. `phase-07-css-feedback-mobile-priority.md`
8. `phase-08-browser-smoke-e2e.md`
9. `99-final-acceptance.md`

## Current Code Research Findings

- `tools/launcher/assets/web-management/app.js` currently contains the old global mutation model: `state.mutationKey`, `isMutating` options, `runMutation()`, and full-page `render(state, elements)` calls.
- `render()` currently rewrites shell, actors, tracks, detail panels, conversation, composer controls, Open TUI controls, and installs row click handlers on every render.
- `sendImDraft()` currently reads `state.draftText`, records the sent message directly, and is called through `runMutation(..., 'messages', ...)`, which refreshes all state after success.
- `refreshSelectedActorConversation()` already treats `E_IM_NOT_FOUND` as empty selected-actor history. This behavior must remain frontend-only.
- `index.html` lacks `page-title` and `page-summary` ids for focused shell rendering.
- `styles.css` lacks the memo-required pending/loading feedback markers.
- `tests/web_management_ui_state.test.js` still asserts old `isMutating` semantics.
- `tests/web_management_ui_contract.test.js` has existing WebUI API/residue checks, but not the new focused-render and pending-state residue gates.

## Verification Method

Focused verification:

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
```

Residue verification:

```bash
rg -n "mutationKey|isMutating|Action running\.|runMutation\(" tools/launcher/assets/web-management/app.js tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js -S
rg -n "querySelectorAll\('\[data-actor-id\]'\)|querySelectorAll\('\[data-track-id\]'\)" tools/launcher/assets/web-management/app.js -S
rg -n "POST /api/web/im|/api/web/im|buildWebImConversationUrl|ensureWebImSession|connection_key|participant_token|event_cursor|cursor=" tools/launcher/assets/web-management/app.js tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js -S
```

Scope verification:

```bash
git diff --check
git diff --name-only
```

Browser smoke target:

```text
http://127.0.0.1:8765/
```
