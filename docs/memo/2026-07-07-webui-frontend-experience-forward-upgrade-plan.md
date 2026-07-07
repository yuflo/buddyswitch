# WebUI Frontend Experience Forward Upgrade Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. This plan is for a future implementation pass; it intentionally does not change production WebUI code.

**Goal:** Rebuild the current WebUI frontend interaction flow so People creation, People selection, roster refresh, right-side teammate facts, and direct thread loading feel immediate, progressive, and stable without adding backend routes or compatibility paths.

**Architecture:** Replace the current monolithic `refreshAll()` / `renderAll()` action path with region-scoped resource refreshers and explicit user-intent state. The browser still calls only the existing Web-interface HTTP APIs, keeps product truth on the backend, and uses short optimistic/pending frontend projections only to preserve user feedback while background reconciliation catches up.

**Tech Stack:** Existing static `index.html`, `styles.css`, and vanilla `app.js` in `tools/launcher/assets/web-management/`; existing Node WebUI state/contract tests; existing Python Web management API tests; optional browser smoke through `./buddyswitch-codex web`.

---

## Scope

This is a frontend experience rebuild plan, not a backend expansion.

Modify only:

- `tools/launcher/assets/web-management/app.js`
- `tools/launcher/assets/web-management/styles.css`
- `tools/launcher/assets/web-management/index.html` only if region status or accessibility attributes need stable DOM anchors
- `tests/web_management_ui_state.test.js`
- `tests/web_management_ui_contract.test.js`
- selected static/API assertions in `tests/test_web_management.py` only if copy or static asset expectations change

Do not modify:

- `tools/launcher/web_management.py`
- `tools/launcher/im_http_router.py`
- `tools/launcher/external_im_session.py`
- `scripts/env/**`
- `buddyswitch/objects/**`
- runtime object stores, env tools, launcher daemon behavior, or Web DTO shapes

Do not add:

- React, SWR, TanStack Query, a bundler, a frontend framework, a global state library, a service worker, or a new backend static-serving path
- feature flags, old/new dual render paths, compatibility wrappers, alternate legacy views, or a second actor roster model

## Design Read

Reading this as: a local operational Team Room UI for people coordinating actor instances, with a quiet cockpit-style product language, leaning toward dense but calm native HTML/CSS/JS and explicit region feedback rather than decorative motion.

The target feeling is not marketing polish. It is the absence of hesitation:

```text
click -> selection visibly changes now
start teammate -> pending row appears now
console facts arrive -> right card updates now
conversation arrives -> center thread updates independently
background reconciliation -> stale provisional state quietly becomes real
```

## Current Evidence

### 1. Create Teammate Has No Stable Roster Reconciliation

Current path:

```text
createInstance()
  -> POST /api/instances
  -> state.selectedActorId = payload.actor_id
  -> await refreshAll()
```

Problem:

- `refreshAll()` reads `/api/actors` only once.
- If that one roster snapshot does not include the new actor yet, `applyActorsPayload()` treats the selected actor as missing and falls back to the first old actor.
- The 3-second automatic refresh only refreshes selected actor console state, not the People roster.
- The user must click `Refresh` to see the actor that was already created.

User-visible failure:

```text
Start teammate succeeds
  -> success message mentions act-market-...
  -> People list still does not show act-market-...
  -> selected teammate can revert to an old actor
  -> user assumes creation failed
```

### 2. People Selection Blocks The Right Card Behind Conversation Loading

Current path:

```text
selectActor()
  -> render selected row + loading shell
  -> await GET /api/actors/:actor_id/console
  -> applyActorConsolePayload()
  -> await GET /api/im/conversations/direct
  -> finally renderActorDetail(), renderComposer(), renderOpenTui(), renderImConversation()
```

Problem:

- Console data can already be in `state.actorConsole`, but the right-side teammate card is not rendered until the direct conversation request finishes.
- A slow, empty, or missing conversation therefore makes runtime/task/Track facts look slow.

Verified with a Node probe:

```text
console fetch returned
state.actorConsole === true
actorRuntimeDetail DOM still shows Loading...
conversation fetch returned
actorRuntimeDetail finally shows Status / Health / Task Sys / Tracks
```

User-visible failure:

```text
click People row
  -> row selection changes
  -> right card stays in Loading...
  -> only after direct thread finishes does the card update
```

### 3. `refreshAll()` Couples Unrelated Regions

Current `refreshAll()` does:

```text
Promise.all([
  /api/health,
  /api/roles,
  /api/actors,
  /api/tracks,
])
apply roster + tracks
await Promise.all([
  selected actor console,
  selected track detail,
])
await ensure IM session
await selected actor conversation
renderAll()
```

Problem:

- Roster, tracks, selected actor card, selected track detail, IM session, and conversation are treated as one transaction.
- Rendering is delayed until the slowest step in the chain completes.
- Manual `Refresh` becomes a blunt full-page repair action rather than an action-scoped update.

User-visible failure:

```text
one region is slow
  -> unrelated regions feel slow
  -> old data disappears into loading states
  -> the UI feels frozen even when useful partial data is ready
```

### 4. Loading Feedback Is Textual, Not Shape-Stable

Current CSS has pending and loading classes, but most loading UI is text such as `Loading...` or opacity changes. It does not reserve the final layout shape for the teammate card, roster rows, or thread sections.

User-visible failure:

```text
user sees text placeholders and opacity
  -> the area feels blocked
  -> useful structure is not preserved
  -> updates look like late replacement instead of progressive fill
```

## Research Notes

These sources inform the plan, not new dependencies:

- web.dev defines Interaction to Next Paint as responsiveness across click/tap/keyboard interactions over the whole page lifecycle and recommends a good INP threshold of 200ms or less at the 75th percentile. The plan therefore prioritizes immediate post-click paint over waiting for complete data. Sources: https://web.dev/articles/inp and https://web.dev/articles/optimize-inp
- React `useOptimistic` documents the core interaction idea: show an immediate optimistic state while an async action is underway. BuddySwitch will apply the same pattern in vanilla JS for the created teammate pending row. Source: https://react.dev/reference/react/useOptimistic
- TanStack Query and SWR document common community practice for optimistic mutation, local cache updates, rollback on error, and revalidation after mutation. BuddySwitch should implement the pattern directly in the existing static JS rather than install these libraries. Sources: https://tanstack.com/query/v5/docs/framework/react/guides/optimistic-updates and https://swr.vercel.app/docs/mutation
- web.dev's `stale-while-revalidate` explanation provides the user-experience model: use available stale content immediately and revalidate in the background when bounded staleness is acceptable. The WebUI should use this as a frontend interaction model, not an HTTP cache change. Source: https://web.dev/articles/stale-while-revalidate
- MDN documents `AbortController.abort()` as able to abort fetch requests and response consumption. Selection changes should abort or ignore superseded console/conversation requests instead of letting old work compete with current intent. Source: https://developer.mozilla.org/en-US/docs/Web/API/AbortController/abort
- NN/g and Carbon both recommend skeleton/loading states that preserve structure and signal progress instead of leaving users with blank or frozen regions. BuddySwitch should use compact region skeletons only for structured containers, not for action buttons or the whole app. Sources: https://www.nngroup.com/articles/skeleton-screens/ and https://carbondesignsystem.com/patterns/loading-pattern/
- MDN's `aria-live` guidance distinguishes update importance and supports polite announcements for dynamic content. The WebUI should keep announcements scoped and avoid noisy global live-region churn during background refresh. Source: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-live

## Bitter And SHARP Constraints

From `AGENTS.md` and `docs/bitter`:

- Rebuild forward through the shortest tested path; do not preserve old refresh structure just for comfort.
- A narrow change is still wrong if it lands at the wrong boundary.
- The Browser UI owns user interaction state and rendering, but must call only Web-interface HTTP APIs.
- Built-in products own semantics below Web; the frontend may project pending UI but must not become a product source of truth.
- Residue cleanup requires behavior tests and live-surface scans.
- End-to-end visible contracts matter more than component-level coverage.
- Do not keep retired shape names in active runtime code unless there is a real migration or external compatibility requirement.

Retired frontend semantics for this upgrade:

```text
refreshAll as the default action completion path
renderAll as the only moment useful data becomes visible
selected actor card waits for selected actor conversation
created actor must wait for roster list before appearing anywhere
manual Refresh as the user's repair action for normal create/select flows
```

## Target Frontend Model

### State Model

Replace the implicit all-or-nothing state model with explicit regions:

```text
state.app
  healthOk
  roles
  selectedRole
  message

state.roster
  actors
  pendingCreatedActorId
  reconcileTargetActorId
  reconcileAttempt
  loading
  error

state.selection
  selectedActorId
  actorSelectionRequestId
  consoleRequestId
  conversationRequestId
  consoleAbortController
  conversationAbortController

state.actorCard
  console
  loading
  error
  lastRenderedActorId

state.conversation
  identityId
  rows
  loading
  error
  seenMessageIds

state.tracks
  list
  selectedTrackId
  detail
  listLoading
  detailLoading
  error
```

Implementation can keep this as one object inside `createState()`. Do not split into modules in this slice because the current static server only serves `/static/app.js`; module splitting would force backend/static route changes and broaden the boundary.

### Render Model

Every async operation renders only the regions it owns:

```text
renderAppShell()
renderRoster()
renderActorCard()
renderConversation()
renderComposer()
renderOpenTui()
renderTracksList()
renderTrackDetail()
renderTrackRail()
```

`renderAll()` should be removed from interaction paths. If a helper remains for initial bootstrapping, it must not be the only path by which ready data becomes visible. Prefer deleting `renderAll()` outright once region renderers cover bootstrap.

### Request Model

Every selected actor interaction uses current-intent guards:

```text
new actor selection
  -> increment request ids
  -> abort previous actor console request if still active
  -> abort previous conversation request if still active
  -> set selectedActorId immediately
  -> render roster + card skeleton + conversation skeleton
  -> start console fetch
  -> start conversation fetch
```

Console and conversation must be independent:

```text
console resolves first
  -> if request still current
  -> apply actor console
  -> render actor card, composer, Open TUI

conversation resolves first
  -> if request still current
  -> apply conversation
  -> render conversation
```

Conversation failure must not clear the card. Console failure must not clear the thread.

## User-Visible Acceptance Contracts

Each contract must have at least one focused test.

### Contract 1: Create Teammate Feels Created Immediately

```text
user clicks Start for role market
  -> POST /api/instances returns actor_id act-market-new
  -> People list immediately includes act-market-new as pending
  -> act-market-new stays selected even if the next /api/actors response omits it
  -> WebUI short-polls /api/actors until act-market-new appears or times out
  -> pending row becomes normal when roster confirms it
```

Failure behavior:

```text
POST /api/instances fails
  -> no pending actor remains
  -> previous selection is preserved
  -> inline status says creation failed
```

```text
POST succeeds but roster reconciliation times out
  -> pending row remains selected with a clear "created, waiting for roster" status
  -> user is not told creation failed
  -> manual Refresh can still reconcile
```

### Contract 2: People Selection Updates The Right Card Independently

```text
user clicks act-market-new
  -> selected row changes immediately
  -> right card shows skeleton for act-market-new immediately
  -> /api/actors/act-market-new/console returns
  -> right card updates immediately
  -> direct thread may continue loading independently
```

The test must simulate:

```text
console request resolves
conversation request remains unresolved
right card already shows Status / Health / Task Sys / Tracks
```

### Contract 3: Conversation Loading Never Blocks Runtime Controls

```text
conversation is slow, empty, or E_IM_NOT_FOUND
  -> right card still shows console facts
  -> lifecycle buttons reflect current console/runtime facts
  -> center thread alone shows empty/loading/error state
```

### Contract 4: Latest User Intent Wins

```text
user clicks act-first
then quickly clicks act-second
act-second console returns first
act-first console returns later
  -> selection remains act-second
  -> actor card remains act-second
  -> conversation remains act-second
```

This is partially covered today and must remain covered after the request model is rebuilt.

### Contract 5: Refresh Is Progressive, Not Global Blocking

```text
user clicks Refresh
  -> refresh button shows pending
  -> roster updates when /api/actors returns
  -> selected card updates when /console returns
  -> conversation updates when /conversation returns
  -> no already-ready region waits for the slowest unrelated request
```

### Contract 6: Loading States Preserve Shape

```text
region is loading
  -> its final structure remains reserved
  -> only that region shows skeleton/loading state
  -> controls outside that region keep their current enabled/disabled state
```

## Implementation Tasks

### Task 1: Lock Failing Experience Tests First

**Files:**

- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tests/web_management_ui_contract.test.js`

Add focused tests before changing production code:

1. `create teammate keeps pending actor visible until roster reconciliation`
   - Mock `POST /api/instances` returning `act-market-new`.
   - Mock first `/api/actors` response without `act-market-new`.
   - Assert roster HTML contains `act-market-new` with pending status.
   - Assert `state.selectedActorId === 'act-market-new'`.
   - Mock later `/api/actors` response with `act-market-new`.
   - Assert pending marker is removed and actor remains selected.

2. `actor card renders as soon as console resolves before conversation`
   - Mock `/api/actors/act-new/console` resolving immediately.
   - Hold `/api/im/conversations/direct?identity_id=act-new&limit=50` unresolved.
   - Call `selectActor(state, elements, 'act-new')`.
   - Await only a microtask after console resolution.
   - Assert `elements.actorRuntimeDetail.innerHTML` contains `Status`, `Health`, `Task Sys`, and does not contain only `Loading`.
   - Assert `elements.imConversation.innerHTML` still shows a conversation loading/empty state.

3. `slow conversation does not disable runtime actions after console loads`
   - Use active healthy console payload.
   - Keep conversation pending.
   - Assert `stopButton.disabled === false`, `clearButton.disabled === false` for an idle healthy actor, and `openTuiButton.disabled === false` when thread id is present.

4. `manual refresh renders returned regions independently`
   - Mock roster returning before console/conversation.
   - Assert actor list updates before the slow selected conversation completes.

5. Contract residue test:
   - Forbid `async function refreshAll(`.
   - Forbid `await refreshAll(state, elements)`.
   - Forbid `selectActor` containing a console fetch followed by an awaited conversation before any actor-card render call.

The residue check may use source string assertions in `tests/web_management_ui_contract.test.js`. Keep it narrow to the WebUI assets and tests; do not scan historical docs.

### Task 2: Rebuild State Around Regions And Intent

**Files:**

- Modify: `tools/launcher/assets/web-management/app.js`
- Test: `tests/web_management_ui_state.test.js`

Replace broad state flags with region-scoped fields in `createState()`:

```text
rosterPendingActorId
rosterReconcileActorId
rosterReconcileAttempt
rosterLoading
rosterError
actorCardLoading
actorCardError
conversationLoading
conversationError
actorConsoleAbortController
actorConversationAbortController
```

Keep existing fields only where they still represent current behavior:

```text
selectedActorId
actorSelectionRequestId
trackSelectionRequestId
imSeenMessageIds
imPolling
imPollTimer
```

Delete or replace fields that only support the old all-or-nothing model:

```text
refreshPending as global page pending
actorSelectionPendingId as the only loading indicator for both card and conversation
actorRefreshInFlight if it prevents region refreshes from rendering independently
```

If `refreshPending` remains, narrow its meaning to the visible Refresh button only; it must not suppress region rendering.

### Task 3: Replace `refreshAll()` With Region Refreshers

**Files:**

- Modify: `tools/launcher/assets/web-management/app.js`
- Test: `tests/web_management_ui_state.test.js`
- Test: `tests/web_management_ui_contract.test.js`

Delete `refreshAll()` and `refreshAllWithFeedback()` as the default action path.

Introduce concrete region refreshers:

```text
refreshAppBasics(state, elements)
  -> /api/health and /api/roles
  -> renderShell + renderRoleSelect

refreshRoster(state, elements, options)
  -> /api/actors
  -> applyActorsPayload preserving pending created actor
  -> renderActorList

refreshTracksList(state, elements)
  -> /api/tracks
  -> renderTrackList

refreshActorCard(state, elements, actorId, requestId, options)
  -> /api/actors/:actor_id/console
  -> applyActorConsolePayload
  -> renderActorDetail + renderComposer + renderOpenTui

refreshConversation(state, elements, identityId, requestId, options)
  -> /api/im/conversations/direct
  -> applyImConversationPayload or empty on E_IM_NOT_FOUND
  -> renderImConversation

refreshSelectedTrackDetailAndRender(state, elements)
  -> /api/tracks/:track_id
  -> renderTrackDetail + renderTrackStudioRail
```

Bootstrap should start independent loads and render each region as it resolves:

```text
bootstrap
  -> createState
  -> render initial empty shell once
  -> refreshAppBasics
  -> refreshRoster
  -> refreshTracksList
  -> if selected actor exists, refreshActorCard and refreshConversation independently
  -> if selected track exists, refreshSelectedTrackDetailAndRender
```

Manual Refresh should call the same region refreshers for visible regions. It must not blank all regions or wait for the slowest request before showing returned data.

### Task 4: Make Actor Selection Progressive

**Files:**

- Modify: `tools/launcher/assets/web-management/app.js`
- Test: `tests/web_management_ui_state.test.js`

Rewrite `selectActor()` around immediate paint:

```text
selectActor(state, elements, actorId)
  -> return if empty or same actor
  -> increment actorSelectionRequestId
  -> abort prior actor-card and conversation fetches
  -> selectedActorId = actorId
  -> actorConsole = null
  -> actorCardLoading = true
  -> conversationLoading = true
  -> clearOpenTuiFeedback()
  -> clearImConversation(state, actorId)
  -> renderShell()
  -> renderActorList()
  -> renderActorDetail()
  -> renderComposer()
  -> renderOpenTui()
  -> renderImConversation()
  -> start refreshActorCard(...)
  -> start refreshConversation(...) using actor row fallback identity
```

Important details:

- Use `selectedActorImTarget()` fallback from actor row so conversation can start without waiting for console.
- Render right card immediately after console resolves.
- Render conversation independently after conversation resolves.
- Preserve current request-id checks so stale responses cannot overwrite the latest selection.
- Use `AbortController` where available; request-id checks remain the correctness boundary because abort is best-effort.

### Task 5: Make Create Teammate Optimistic And Reconciled

**Files:**

- Modify: `tools/launcher/assets/web-management/app.js`
- Modify: `tools/launcher/assets/web-management/styles.css`
- Test: `tests/web_management_ui_state.test.js`
- Test: `tests/web_management_ui_contract.test.js`

Rewrite `createInstance()`:

```text
createInstance(state, elements)
  -> disable Start only
  -> POST /api/instances
  -> on success:
       build pending actor from payload.actor_id, selectedRole, payload.instance/runtime if present
       insert or replace pending actor in state.actors
       selectedActorId = payload.actor_id
       rosterPendingActorId = payload.actor_id
       rosterReconcileActorId = payload.actor_id
       selectedSection = actors
       message = Created <actor_id>. Waiting for roster...
       renderActorList + renderActorDetail + renderComposer + renderOpenTui
       start actor-card refresh
       start conversation refresh
       start bounded roster reconciliation
  -> on failure:
       preserve previous selection
       remove provisional actor if created in this attempt
       show inline failure
```

Bounded reconciliation:

```text
reconcileCreatedActorInRoster(state, elements, actorId)
  -> attempt /api/actors immediately
  -> if actor appears:
       applyActorsPayload with pending actor removed
       message = Created <actor_id>.
       renderActorList
       stop
  -> if actor missing:
       keep pending row
       schedule next attempt with short backoff
  -> after max attempts:
       keep pending row selected
       message = Created <actor_id>. Roster has not confirmed it yet.
```

Recommended backoff for local UI:

```text
0ms, 150ms, 300ms, 600ms, 1000ms, 1500ms, 2500ms
```

Total wait stays under normal user attention limits, does not become a long-running poller, and stops once confirmed.

Pending row rendering:

```text
role label
actor id
status badge: creating or confirming
stable avatar initials
no fake health, unread count, workload, or availability facts
```

### Task 6: Replace Text Loading With Region Skeletons

**Files:**

- Modify: `tools/launcher/assets/web-management/app.js`
- Modify: `tools/launcher/assets/web-management/styles.css`
- Modify: `tools/launcher/assets/web-management/index.html` only if needed for stable `aria-busy` or status nodes
- Test: `tests/web_management_ui_contract.test.js`

Add shape-stable skeletons for:

- actor card metric grid
- runtime summary
- task summary
- track summary
- conversation thread body
- roster pending row

Do not skeletonize:

- buttons
- select inputs
- textarea
- toast/message banner
- modal-like structures, because none exist in this UI

Accessibility:

- Use `aria-busy="true"` only on the region currently loading.
- Keep `message-banner` as `role="status"` for user-action outcomes.
- Keep routine background refresh announcements quiet unless user action requires feedback.
- Keep `aria-live="polite"` on roster and conversation, but avoid replacing entire parent content unnecessarily when only a small status changes.

### Task 7: Keep IM Polling From Re-Coupling Regions

**Files:**

- Modify: `tools/launcher/assets/web-management/app.js`
- Test: `tests/web_management_ui_state.test.js`

Current `pollImEventsOnce()` refreshes selected actor console and selected conversation sequentially when a selected actor message is processed.

Rebuild it so:

```text
incoming selected actor message
  -> append/fetch/ack message
  -> render conversation immediately
  -> refresh actor card independently
  -> do not block conversation render on card refresh
```

The selected conversation cache should update from fetched messages first. A full direct conversation refetch can remain as background reconciliation only if it does not block the visible append.

### Task 8: Verification And Residue Gates

Run focused verification first:

```bash
node --test tests/web_management_ui_state.test.js
node --test tests/web_management_ui_contract.test.js
python3 -m unittest \
  tests.test_web_management.WebManagementProductApiTests.test_actor_roster_api_projects_instance_list_as_actor_rows \
  tests.test_web_management.WebManagementHTTPTests.test_create_instance_delegates_to_launcher_start_without_initialize_input
```

Run scoped residue scan over live WebUI assets and tests:

```bash
rg -n "async function refreshAll\\(|refreshAllWithFeedback|await refreshAll\\(|renderAll\\(state, elements\\).*conversation|selected actor card waits|Refresh mock|Mock data|/api/web/im|/api/actors/' \\+ encodeURIComponent\\(state.selectedActorId\\) \\+ '/messages|/api/instances/' \\+ encodeURIComponent\\(state.selectedActorId\\) \\+ '/side'" tools/launcher/assets/web-management tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js
```

Expected:

- No production hit for `refreshAll` or `refreshAllWithFeedback`.
- No production hit for retired route calls.
- Test-only hits are acceptable only when they are negative assertions.

Run manual smoke after implementation:

```bash
./buddyswitch-codex web --host 127.0.0.1 --port 8765
```

Smoke checks:

```text
1. Open Team room.
2. Click each People row quickly; selected row changes immediately.
3. Right teammate card updates as soon as console facts return and does not wait for direct thread history.
4. Direct thread loading is isolated to the center column.
5. Start a market teammate; a pending act-market-* row appears immediately.
6. The pending row remains selected until roster confirms it.
7. Once roster confirms, the pending state disappears without user Refresh.
8. Manual Refresh updates visible regions progressively.
9. No global blanking, no full-page spinner, no fake teammate facts, no old Actor Console shell.
10. Mobile viewport has no horizontal overflow and loading skeletons do not cause layout jumps.
```

## Completion Gate

This upgrade is complete only when all are true:

- Starting a teammate no longer depends on a user clicking Refresh to see the created actor.
- Created actors remain selected through roster reconciliation.
- Clicking a People row updates selection immediately.
- The right teammate card renders from `/api/actors/:id/console` independently of `/api/im/conversations/direct`.
- Direct thread loading never blocks runtime controls or teammate facts.
- Manual Refresh is progressive and scoped, not an all-or-nothing transaction.
- `refreshAll()` and `refreshAllWithFeedback()` are removed from production WebUI code.
- Loading states are region-level and shape-stable.
- No backend routes, DTOs, storage shapes, env tools, or runtime services are changed.
- Focused Node tests pass.
- Narrow Python API/static tests pass.
- Scoped residue scan has no positive production hits.
- Browser smoke proves the create, select, refresh, and message-visible loops.

## Implementation Order

1. Add failing tests for created actor reconciliation and actor-card-before-conversation rendering.
2. Add contract residue checks for retired all-or-nothing refresh semantics.
3. Rebuild state fields around roster, actor card, conversation, and tracks.
4. Replace `refreshAll()` with region refreshers.
5. Rebuild `selectActor()` for immediate paint and independent console/conversation fetches.
6. Rebuild `createInstance()` with pending roster row and bounded reconciliation.
7. Replace text loading with region skeletons and scoped `aria-busy`.
8. Decouple IM event polling render order.
9. Run focused tests and residue scans.
10. Run browser smoke and record observed create/select behavior.

## Self-Review

- No implementation code was changed by this plan.
- The plan keeps the existing Web-interface API boundary and does not ask for backend work.
- The plan does not introduce a frontend framework or data-fetching dependency.
- The plan retires the old global refresh semantics instead of layering a compatibility path on top.
- Every observed user-facing issue has a corresponding acceptance contract and focused test target.
- Verification includes behavior tests, live-surface residue scan, and browser smoke.
