# WebUI Actor Selection Single-Owner Forward Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task in the current `fea-webui` worktree. Steps use checkbox (`- [ ]`) syntax for progress tracking.

**Goal:** Replace every live WebUI actor-selection side path with one explicit state owner so create, manual selection, lifecycle recovery, Delete reselection, roster fallback, bootstrap, and refresh converge through one race-safe path.

**Architecture:** One internal actor-selection coordinator owns selection intent, generation, request cancellation, initial console/conversation loading, settlement, and entry into the existing single refresh scheduler. Roster and payload appliers expose facts only; lifecycle and UI callers decide the target actor and call the coordinator. The rebuild deletes the old duplicated and implicit paths in the same change, with no compatibility wrapper, feature flag, fallback path, or retired-state guard.

**Tech Stack:** Browser-native JavaScript UMD module, Node state/contract tests, Python `unittest`, real BuddySwitch WebUI/browser acceptance.

---

## 1. Task Objective

The current created-actor fix correctly clears `actorSelectionPendingId`, but it copies the manual-selection settlement protocol into `beginCreatedActorReconciliation()`. A complete code scan shows that selection intent is also mutated by roster payload application, console DTO application, lifecycle failure recovery, Delete reconciliation, and bootstrap.

This task rebuilds that whole frontend chain around one current contract:

```text
selection trigger
  -> caller resolves target actor id
  -> one actor-selection coordinator
  -> cancel old generation
  -> set current selection intent
  -> load console and conversation concurrently
  -> reject stale actor/generation results
  -> settle current generation
  -> enter one console refresh scheduler
```

Completion means both behavior and live code surfaces express this single path.

## 2. Core Problems To Remove

### 2.1 Duplicated selection protocol

- `selectActor()` owns one full abort/load/settle/schedule implementation.
- `beginCreatedActorReconciliation()` owns a second implementation.
- The second implementation originally omitted settlement and caused newly created actors to stop auto-refreshing permanently.

### 2.2 Selection ownership leaks

- `applyActorsPayload()` currently chooses a fallback actor and writes `selectedActorId`.
- `applyActorConsolePayload()` currently writes `selectedActorId` from a response DTO.
- These lower-level projection appliers can change UI intent without running request invalidation, loading, settlement, or rendering as one transaction.

### 2.3 Lifecycle and bootstrap side paths

- Start failure restores only the previous actor id instead of restoring its full projection through the normal path.
- Delete uses `suppressNextRosterAutoSelection` to compensate for roster-owned implicit selection.
- Bootstrap starts console and conversation reads directly instead of invoking the same initial selection contract.
- Manual refresh can discover that the selected actor disappeared, but selection fallback is implicit rather than an explicit caller decision.

### 2.4 Generation gap

- `refreshSelectedActorConsole()` validates actor id but does not capture the selection generation.
- An A -> B -> A switch can allow an old A response to apply to the new A selection.
- Selection generation alone cannot order two console reads for the same settled actor; automatic, manual, and post-action refreshes need a separate current-console-request sequence.

### 2.5 Live residue

- `refreshSelectedActorConversation()` is exported and tested but has no production caller.
- `selectActor()` contains a duplicated nested current-request guard.
- The current created-actor patch must be replaced by the coordinator, not retained beneath it.

## 3. System Boundary

### Actor-selection coordinator owns

- `selectedActorId` writes and clears;
- `actorSelectionRequestId` generation changes;
- invalidating the current console-request sequence whenever selection intent changes;
- aborting and replacing actor console/conversation controllers;
- clearing actor-scoped console, capability, conversation, and TUI projections;
- `actorSelectionPendingId` lifecycle;
- initial `actorCardLoading` and `conversationLoading` lifecycle;
- initial console/conversation request settlement;
- starting the existing single actor-console refresh scheduler.

### Roster owns

- actor rows returned by `/api/actors`;
- pending-created actor projection until authoritative roster confirmation;
- preferred-actor facts used by an explicit caller selection decision;
- stopped-group expansion facts.

Roster does not write selection intent.

### Payload appliers own

- applying already validated console/conversation DTOs;
- synchronizing capability and conversation projections.

Payload appliers do not write selection intent.

### Lifecycle owns

- deciding whether a completed operation should select, restore, retain, or remove an actor;
- operation messages and operation-row state;
- invoking the selection coordinator with the chosen actor id.

Lifecycle does not reproduce selection mechanics.

### Refresh scheduler owns

- one timer handle;
- one periodic console refresh in flight;
- visibility/section eligibility.

It does not change actor selection and does not gain a second polling path.

### Actor console read path owns

- one monotonically increasing `actorConsoleRequestId` for every console read;
- accepting a response only when actor id, selection generation, and console request id are all current.

This request sequence orders reads inside one stable selection generation; it is not a second selection path.

## 4. Required Invariants

1. `selectedActorId` is current user/system intent, never a value inferred from a response payload.
2. Every selection or clear increments `actorSelectionRequestId` before old responses may apply.
3. Every console read advances `actorConsoleRequestId`; only the latest console read inside the current selection generation may apply.
4. `actorSelectionPendingId` is empty or equals the current selected actor.
5. Only the current `{actorId, selectionRequestId}` generation may clear pending/loading or schedule refresh.
6. Console and conversation may render independently; selection settlement waits for both.
7. Roster refresh never silently chooses an actor.
8. Bootstrap, create success, Start failure, Delete, and roster fallback explicitly use the coordinator.
9. Only one actor-console timer and one periodic request may be active.
10. No old selection block, suppression flag, compatibility wrapper, or dead export remains in live assets/tests.

## 5. Non-Goals

- No backend route or DTO change.
- No Task Sys, IM domain, daemon, or persistence change.
- No CSS or visual redesign.
- No full `app.js` module split.
- No generic state-machine framework, event bus, store library, or dependency-injection layer.
- No preservation of old internal state shapes for compatibility.

## 6. File Impact

- Modify: `tools/launcher/assets/web-management/app.js`
  - add one internal selection transition/load coordinator;
  - route all selection callers through it;
  - remove implicit/duplicated/dead paths;
  - harden selected-console refresh generation validation.
- Modify: `tests/web_management_ui_state.test.js`
  - define the new ownership and behavior contract first;
  - replace tests that teach roster/payload-owned selection;
  - add lifecycle, ABA, timer, and residue regressions.
- Modify only if a live-surface contract requires it: `tests/web_management_ui_contract.test.js`
  - add exact source-boundary guards; do not mirror implementation text broadly.
- Reference and progress record: `docs/memo/2026-07-12-webui-actor-selection-single-owner-forward-rebuild-plan.md`

No new production JavaScript file is planned. A separate controller file would require injecting fetch, render, timer, identity, and browser-global dependencies and would widen this focused rebuild.

## 7. TDD Implementation Tasks

### Task 1: Make selection ownership explicit

**Files:**

- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tools/launcher/assets/web-management/app.js:607-676`

- [x] **Step 1: Replace the roster-owned selection tests with fact-only expectations**

The tests must demonstrate that payload application preserves a valid selection but does not invent or replace selection intent:

```javascript
test('actor roster payload exposes preferred facts without choosing actor', () => {
  const state = app.createState();
  const result = app.applyActorsPayload(state, {
    actors: [
      { actor_id: 'act-inactive', role: 'dev', runtime: { status: 'inactive' } },
      { actor_id: 'act-active', role: 'market', runtime: { status: 'active' } },
    ],
  });

  assert.equal(state.selectedActorId, '');
  assert.equal(result.selectedActorPresent, false);
  assert.equal(result.preferredActorId, 'act-active');
});
```

- [x] **Step 2: Add a payload-ownership regression**

```javascript
test('actor console payload cannot change selection intent', () => {
  const state = app.createState();
  state.selectedActorId = 'act-current';

  app.applyActorConsolePayload(state, {
    console: { actor: { actor_id: 'act-response' } },
  });

  assert.equal(state.selectedActorId, 'act-current');
});
```

- [x] **Step 3: Run RED**

Run:

```bash
node tests/web_management_ui_state.test.js
```

Expected: the new tests fail because roster and console payload appliers still write `selectedActorId`.

- [x] **Step 4: Make payload application fact-only**

`applyActorsPayload()` must return explicit reconciliation facts without choosing:

```javascript
return {
  selectedActorPresent: Boolean(state.selectedActorId && actorById(state, state.selectedActorId)),
  preferredActorId: preferredActorId(state.actors),
};
```

Remove its selection mutation, `clearOpenTuiFeedback()`, and `clearImConversation()` selection side effects. Remove the `selectedActorId` assignment from `applyActorConsolePayload()`.

- [x] **Step 5: Run GREEN**

Run the state suite and confirm the new ownership tests pass before proceeding.

### Task 2: Introduce the single selection coordinator

**Files:**

- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tools/launcher/assets/web-management/app.js:2407-2475`

- [x] **Step 1: Add coordinator behavior tests**

Tests must cover:

- selection increments generation and cancels the prior controllers;
- console and conversation render progressively;
- pending clears only after both settle;
- stale generation cannot clear a newer pending selection;
- settlement schedules browser refresh exactly once.

The created-actor timer test must install a minimal browser environment before invoking the real flow:

```javascript
const originalDocument = globalThis.document;
globalThis.document = { hidden: false };
try {
  // Run created actor reconciliation through the real public create/poll path.
  await waitFor(() => state.actorSelectionPendingId === '', 'selection settlement');
  assert.ok(state.actorRefreshTimer);
} finally {
  if (state.actorRefreshTimer) clearTimeout(state.actorRefreshTimer);
  globalThis.document = originalDocument;
}
```

- [x] **Step 2: Run RED**

Expected: ownership/settlement tests fail until the common coordinator exists and the created path uses it.

- [x] **Step 3: Add one internal coordinator**

Use a narrow internal shape rather than a framework:

```javascript
function beginActorSelection(state, actorId) {
  abortActorSelectionRequests(state);
  const requestId = state.actorSelectionRequestId + 1;
  state.actorSelectionRequestId = requestId;
  state.selectedActorId = actorId || '';
  // Reset actor-scoped projection and loading state exactly once.
  return { actorId: actorId || '', requestId, consoleAbortController, conversationAbortController };
}

async function loadActorSelection(state, elements, actorId) {
  const selection = beginActorSelection(state, actorId);
  renderActorSelectionRegions(state, elements);
  if (!selection.actorId) return;
  await Promise.allSettled([consolePromise, conversationPromise]);
  settleActorSelection(state, elements, selection);
}
```

Helper names may follow local naming style, but responsibilities and one-owner invariants must remain exact. Do not introduce options for old/new behavior.

- [x] **Step 4: Route manual `selectActor()` through the coordinator**

Keep only user-interaction policy in `selectActor()`:

- no-op for empty/same actor;
- close Delete confirmation;
- clear selected lifecycle operation;
- expand Stopped when appropriate;
- clear the prior banner;
- call `loadActorSelection()`.

- [x] **Step 5: Run GREEN and refactor duplicate rendering**

Keep progressive rendering tests green. Extract at most one local render helper for the actor-selection regions; do not add a global render framework.

### Task 3: Route create and lifecycle transitions through the coordinator

**Files:**

- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tools/launcher/assets/web-management/app.js:2477-2508`
- Modify: `tools/launcher/assets/web-management/app.js:2730-2959`

- [x] **Step 1: Add RED lifecycle regressions**

Add behavior tests proving:

- created actor selection settles and starts refresh without copied request code;
- a newer user selection still wins over Start completion;
- failed Start restores the prior actor console and conversation, not only its id;
- Delete selects and loads the deterministic next actor;
- clearing actor selection increments generation and invalidates old requests.

- [x] **Step 2: Run RED**

Expected: failed Start projection restoration and common created-path ownership fail under the current implementation.

- [x] **Step 3: Rebuild created-actor reconciliation**

`beginCreatedActorReconciliation()` keeps only create-specific work:

```javascript
recordPendingCreatedActor(state, actorId, roleId);
upsertPendingActor(state, actorId, roleId);
scheduleCreatedActorReconciliation(state, elements);
if (selectCreatedActor) {
  state.selectedSection = 'actors';
  await loadActorSelection(state, elements, actorId);
}
```

Delete its copied abort/controller/request/loading/settlement/render/scheduler block completely.

- [x] **Step 4: Rebuild lifecycle clear/restore/reselection**

- lifecycle-operation context clears selection through the same transition owner;
- failed Start calls the coordinator for the previous actor and then restores the failure message;
- Delete refreshes authoritative roster and explicitly selects the next/preferred actor;
- final-actor Delete explicitly clears selection through the coordinator.

- [x] **Step 5: Remove `suppressNextRosterAutoSelection`**

Delete the state field and every read/write. Do not replace it with another suppression flag.

- [x] **Step 6: Run GREEN**

Run the complete state suite and verify all existing parallel Start/Delete precedence tests remain green.

### Task 4: Route bootstrap and manual roster fallback explicitly

**Files:**

- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tools/launcher/assets/web-management/app.js:2128-2143`
- Modify: `tools/launcher/assets/web-management/app.js:3210-3242`
- Modify: `tools/launcher/assets/web-management/app.js:3537-3560`

- [x] **Step 1: Add RED tests for explicit roster fallback**

Cover:

- initial roster selects the preferred active actor through the coordinator;
- stopped-only initial roster expands Stopped and loads that actor;
- manual refresh retains a present current actor;
- manual refresh explicitly selects and loads a preferred actor when the old actor disappeared;
- empty roster explicitly clears actor-scoped projections.

- [x] **Step 2: Run RED**

Expected: tests fail after roster applier stops choosing implicitly and before callers adopt the explicit selection result.

- [x] **Step 3: Return roster reconciliation facts from `refreshRoster()`**

```javascript
const reconciliation = applyActorsPayload(state, payload);
return reconciliation;
```

The return value is a current contract, not a compatibility adapter.

- [x] **Step 4: Add one explicit roster-selection policy helper**

The helper consumes `{selectedActorPresent, preferredActorId}` and either keeps the current selection, loads the preferred actor, or clears selection. It calls the coordinator and does not write selection itself.

- [x] **Step 5: Replace bootstrap and manual-refresh direct actor loads**

- bootstrap awaits roster facts, resolves selection once, and removes its direct `refreshActorCard()` / `refreshConversation()` branch;
- manual refresh resolves roster selection before refreshing current actor projections;
- no old direct initial-load path remains.

- [x] **Step 6: Run GREEN**

Verify initial-selection, manual-refresh partial rendering, and no-selection behavior.

### Task 5: Harden generation checks and remove dead surfaces

**Files:**

- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tests/web_management_ui_contract.test.js` if needed for exact residue guards
- Modify: `tools/launcher/assets/web-management/app.js:2267-2371`
- Modify: `tools/launcher/assets/web-management/app.js:3610-3635`

- [x] **Step 1: Add the A -> B -> A RED regression**

Start an A console refresh, select B, select A again, resolve the first A response last, and assert it cannot overwrite the new A projection.

- [x] **Step 2: Run RED**

Expected: the old selected-console refresh applies because it only compares actor id.

- [x] **Step 3: Capture and validate selection generation**

```javascript
const requestedActorId = state.selectedActorId;
const requestId = state.actorSelectionRequestId;
// fetch
if (!isCurrentActorRequest(state, requestedActorId, requestId)) return;
```

Apply the check before every state mutation from that response.

- [x] **Step 4: Delete dead/duplicated live surfaces**

- remove `refreshSelectedActorConversation()` and its export/test-only contract;
- remove the duplicated nested current-request guard;
- ensure the current created-actor patch has been fully replaced by the coordinator;
- retain the one `scheduleActorConsoleRefresh()` implementation and its browser-environment guard.

- [x] **Step 5: Add scoped residue assertions/scans**

Required no-hit checks over live JavaScript and state tests:

```bash
! rg -n "suppressNextRosterAutoSelection|refreshSelectedActorConversation" \
  tools/launcher/assets/web-management/app.js \
  tests/web_management_ui_state.test.js
```

Manual review must also confirm `selectedActorId =` production writes occur only inside the coordinator owner.

- [x] **Step 6: Run GREEN**

Run state and contract suites plus JavaScript syntax and `git diff --check`.

### Task 6: Full automated and live acceptance

**Files:**

- Update progress and completion record in this memo.

- [x] **Step 1: Run focused automated verification**

```bash
node --check tools/launcher/assets/web-management/app.js
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
node tests/web_management_markdown_renderer.test.js
python -m unittest -q tests.test_web_management
python -m unittest -q tests.test_repo_consistency
git diff --check
```

- [x] **Step 2: Run exact residue scans**

Confirm all retired fields/functions and duplicate production selection writers are absent. Historical memos are evidence and are not cleanup targets.

- [x] **Step 3: Run the real browser contract**

Use a disposable actor on the worktree-owned WebUI:

```text
Create actor
  -> automatic actor selection settles
  -> send a message that starts/observes side Task work
  -> receive the real reply
  -> Task Active changes to 0 without Refresh or reload
  -> Capability save still works
  -> Stop -> Resume -> Delete still work
```

Also exercise rapid A -> B -> A switching while console requests are active when practical.

- [x] **Step 4: Verify resource cleanup**

- delete disposable actors;
- stop the temporary WebUI server;
- confirm no worktree-owned instance/runtime/browser/test process remains;
- confirm ports and runtime roots return to baseline.

- [x] **Step 5: Final code review**

Review the diff against every invariant and non-goal. Tests passing does not excuse a remaining side path or compatibility residue.

- [x] **Step 6: Record completion evidence**

Append exact commands, results, browser observations, cleanup evidence, and any remaining risk to this memo before reporting completion.

## 8. Verification Contract

### Behavior proof

- all selection triggers produce one coherent actor projection;
- no stale generation can update or settle a newer selection;
- created actor auto-refresh reaches updated Task state without manual action;
- lifecycle selection precedence remains deterministic.

### Surface proof

- retired selection helpers/flags have zero hits in live code/tests;
- only the coordinator writes selection intent;
- bootstrap and created-actor code contain no direct duplicated load protocol;
- no alternate refresh scheduler exists.

### Resource proof

```text
behavior passes + browser path passes + host resources return to baseline
```

## 9. Baseline Before Rebuild

Verified on 2026-07-12 before changing the current implementation:

```bash
node --check tools/launcher/assets/web-management/app.js
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
python -m unittest -q tests.test_web_management
git diff --check
```

Result: all commands passed; Python Web Management reported 81 tests passing. This baseline includes the current local created-actor settlement fix and exists only as the starting behavior reference. It is not the final architecture.

## 10. Development Rules

- Tests first; observe every new regression test fail for the intended reason.
- Implement one ownership slice at a time and keep the state suite green between slices.
- Direct replacement only; no old/new branches or temporary adapters.
- Delete stale live code/tests in the same task that introduces the current contract.
- Do not widen into backend/domain changes or a whole-file frontend framework.
- Do not claim completion from unit tests alone; the real async browser loop is mandatory.
- Do not run broad service-starting acceptance until cleanup ownership is prepared.

## 11. Progress Record

- [x] Architecture review completed and option B approved.
- [x] All `docs/bitter` principles re-read and converted into task constraints.
- [x] Pre-change focused baseline verified.
- [x] Tasks 1-5 implemented through RED/GREEN cycles.
- [x] Full automated verification passed.
- [x] Real browser acceptance passed.
- [x] Resource residue check passed.
- [x] Final architecture review passed.

## 12. Completion Evidence

Completed on 2026-07-12 in `/Users/chen/Dev/buddyswitch/.worktrees/fea-webui`.

### 12.1 Final architecture

- `beginActorSelection()` is the only production writer of `selectedActorId`.
- Create, manual selection, Start failure restore, Delete reselection/clear, roster fallback, bootstrap, and manual refresh all enter the same coordinator.
- Created-actor authoritative roster confirmation starts before console/conversation selection I/O and cannot be blocked by it.
- Console responses require the current actor id, selection generation, and console-request sequence.
- Conversation, send, IM polling, Open TUI, Copy TUI, Interrupt, and lifecycle-submission actor-scoped effects all require the current selection generation.
- Delete stops on authoritative roster failure and never selects from a stale local roster.
- Bootstrap settles concurrent sibling promises on both success and failure.
- The retired suppression flag, dead conversation refresh export, copied create-selection block, compatibility wrapper, and second refresh path are absent.

### 12.2 Automated verification

The final post-implementation run passed:

```text
node --check tools/launcher/assets/web-management/app.js
node --unhandled-rejections=strict tests/web_management_ui_state.test.js  # 116 passed
node --unhandled-rejections=strict tests/web_management_ui_contract.test.js  # 34 passed
node tests/web_management_markdown_renderer.test.js  # 5 passed
python -m unittest -q tests.test_web_management  # 81 passed
python -m unittest -q tests.test_repo_consistency  # 64 passed
git diff --check
```

Exact residue scans found zero production/test hits for `suppressNextRosterAutoSelection` and `refreshSelectedActorConversation`. The exact production selection-writer scan found one assignment, inside `beginActorSelection()`.

### 12.3 Real browser acceptance

Using the worktree-owned WebUI at `http://127.0.0.1:8766/` and disposable actor `act-market-b26949c394a3`:

1. Browser-created Market actor became selected automatically and completed selection settlement.
2. Sent a real message requesting a side Task; the visible Task Sys count changed from `1 active` to `0 active` without clicking Refresh or reloading.
3. The direct thread received the real final reply `WEBUI_SELECTION_OK`.
4. Capability Parent changed from Balanced to Fast and returned to visible `Saved` state.
5. Stop, Resume, second Stop, exact-id Delete confirmation, and final empty-roster projection all succeeded.
6. A -> B -> A and overlapping async races were covered deterministically by automated tests rather than adding two more live disposable actors.

The browser recorded one expected initial `404` for the not-yet-created direct conversation; the UI handles this API empty-state response and rendered `No direct messages yet.` It did not affect the acceptance path and is not selection architecture residue.

### 12.4 Cleanup and final review

- Disposable actor deleted; `instance list --json` returned `{"instances":[]}`.
- Actor instance directory removed.
- Temporary WebUI server stopped; port 8766 returned to no-listener baseline.
- Playwright browser closed and `.playwright-cli/` removed.
- Final independent read-only architecture review found no remaining blocking, important, or minor selection-chain issue.
- Remaining selection-rebuild risk: none identified. The initial empty-conversation `404` is an existing API empty-state convention outside this memo's frontend selection boundary.
