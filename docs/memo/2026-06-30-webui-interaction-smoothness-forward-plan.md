# WebUI Interaction Smoothness Forward Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Web Management UI interaction state so sending, actor switching, refresh, and navigation feel immediate while keeping all changes inside the WebUI frontend asset boundary.

**Architecture:** Keep `/api/im/*` and all runtime services as the product contracts. The browser UI owns only transient interaction state, rendering, and action feedback. Replace the current global mutation lock and whole-page rerender loop with action-scoped pending state and focused render functions.

**Tech Stack:** Plain browser JavaScript in `tools/launcher/assets/web-management/app.js`, CSS in `tools/launcher/assets/web-management/styles.css`, static HTML in `tools/launcher/assets/web-management/index.html`, Node UI state/contract tests, and a local browser smoke at `http://127.0.0.1:8765/`.

---

## Task Goal Restatement

The task is to make the current WebUI smoother without changing backend semantics.

Primary user loop:

```text
user selects an actor
  -> types a direct message
  -> clicks Send
  -> input clears immediately
  -> one message row appears immediately
  -> only the Send control enters pending state
  -> the actor runtime summary refreshes when the backend accepts the message
  -> actor replies appear through existing IM events or direct conversation restore
```

Secondary user loops:

```text
user clicks another actor
  -> the new row is selected immediately
  -> stale actor messages disappear immediately
  -> the selected actor panel shows a local loading state
  -> fetched runtime and conversation replace the loading state
```

```text
user clicks Tracks
  -> the visible page title and summary switch to Track workspace
  -> actor polling does not redraw hidden actor panels
```

```text
user clicks Refresh
  -> the Refresh button shows pending feedback
  -> the refresh action does not overwrite the composer while the user is typing
  -> completion is visible through updated status text
```

## Current Code Findings

The current bottleneck is not visual styling. It is the WebUI state model.

- `state.mutationKey` is a global lock. `computeInstanceActionState()` and `computeOpenTuiState()` treat any mutation as a reason to disable all actor controls.
- `render()` rewrites the actor list, runtime detail, task summary, track detail, conversation, and button states on every input event.
- `render()` attaches row click listeners after every rerender, which makes DOM replacement part of normal typing and polling.
- The Send click path calls `runMutation(..., 'messages', ...)`; `runMutation()` calls `refreshAll()` after success, so sending one message refetches health, roles, actors, tracks, actor console, IM session, and direct conversation.
- The Send click handler clears `state.draftText` only in `.then()` after `runMutation()`, and that change is not followed by a focused composer render.
- `refreshSelectedActorConversation()` already normalizes `E_IM_NOT_FOUND` to empty UI history. Keep that frontend adaptation and do not change backend 404 semantics.
- The page title is static `Actor Console`, so the visible page heading stays actor-oriented when `selectedSection === 'tracks'`.

## Bitter Principles Applied

From `docs/bitter`:

- Do not compensate for unclear runtime contracts with more prompt or doc bulk. This plan keeps `/api/im/*` as the contract and fixes only browser projection behavior.
- Do not route a local WebUI experience fix through shared backend hotspots. The implementation boundary stays in WebUI assets and WebUI tests.
- Do not keep dual tracks. Remove the global `mutationKey` model instead of adding a second pending model beside it.
- A replacement is not finished while live surfaces still teach the old semantics. Add residue scans for stale busy-state and compatibility names.
- A sliced plan still needs one user-visible contract sentence. The Send loop above is the acceptance contract.
- Tests must prove behavior and live surface. Node state tests prove behavior; scoped scans prove no stale frontend state model remains.

## Scope Boundary

Modify only:

- `tools/launcher/assets/web-management/app.js`
- `tools/launcher/assets/web-management/styles.css`
- `tools/launcher/assets/web-management/index.html`
- `tests/web_management_ui_state.test.js`
- `tests/web_management_ui_contract.test.js`

Do not modify:

- `tools/launcher/im_http_router.py`
- `tools/launcher/web_management.py`
- `scripts/env/**`
- `buddyswitch/objects/**`
- `buddyswitch/local/private/**`

The backend contract remains:

```text
GET /api/im/conversations/direct?... may return 404 E_IM_NOT_FOUND
```

The frontend contract becomes:

```text
404 E_IM_NOT_FOUND from the selected direct conversation endpoint means empty selected-actor history, not a WebUI failure.
```

## Replacement Invariants

- `state.mutationKey` is removed.
- No function accepts or passes an `isMutating` option.
- Message sending has its own `state.sendPending`.
- Lifecycle actions share `state.lifecyclePendingAction`.
- Open TUI has its own `state.openTuiPending`.
- Refresh has its own `state.refreshPending`.
- Create keeps `state.createPending`.
- Actor selection has `state.actorSelectionPendingId`.
- Track selection has `state.trackSelectionPendingId`.
- The input event path does not call the full page render.
- Row click handlers are installed once through event delegation.
- Send success does not call `refreshAll()`.
- `refreshAll()` remains only for initial boot, manual Refresh, and create.
- Actor polling updates actor panels only when the actor view is visible and no actor selection is pending.
- Current actor feedback is cleared when selected actor changes.
- Section title and summary derive from `state.selectedSection`.

## File Structure

### `tools/launcher/assets/web-management/app.js`

Owns:

- state creation;
- pure action-state computation;
- API route builders;
- selected actor and Track transient state;
- focused render functions;
- event handlers;
- polling coordination.

This file remains plain browser JavaScript. Do not introduce a frontend framework.

### `tools/launcher/assets/web-management/index.html`

Owns static structure and stable element ids. Add only ids needed for focused renders:

```html
<h1 id="page-title">Actor Console</h1>
<p id="page-summary" class="page-summary">Select an actor, inspect runtime and task state, message directly, and use lifecycle controls in one place.</p>
```

### `tools/launcher/assets/web-management/styles.css`

Owns visual feedback classes:

```css
.is-loading {
  cursor: progress;
}

.selectable-row.is-loading {
  background: var(--surface-soft);
}

.button.is-pending {
  cursor: progress;
}

.inline-loading {
  color: var(--muted);
  font-size: 12px;
}

.im-row.pending {
  border-style: dashed;
}

.im-row.failed {
  border-color: #efc2bd;
  background: var(--danger-soft);
}
```

### `tests/web_management_ui_state.test.js`

Owns behavior coverage for state transitions and pure rendering helpers.

### `tests/web_management_ui_contract.test.js`

Owns live-surface checks for ids, API surface, and residue gates.

## Task 1: Replace Global Mutation State With Action-Scoped Pending State

**Files:**
- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tools/launcher/assets/web-management/app.js`

- [ ] **Step 1: Replace the busy-state tests**

In `tests/web_management_ui_state.test.js`, replace `mutation busy state disables all instance controls` with:

```js
test('send pending disables only send while preserving independent actor controls', () => {
  const instance = {
    status: 'active',
    app_server_health: 'healthy',
    thread: { status: 'idle' },
  };

  assert.deepEqual(
    app.computeInstanceActionState(instance, {
      draftText: 'Advance the brief',
      sendPending: true,
      lifecyclePendingAction: '',
    }),
    {
      canSend: false,
      canInterrupt: false,
      canStop: true,
      canDelete: false,
      canClear: true,
      canResume: false,
    }
  );
});
```

Replace `mutation busy state disables open tui` with:

```js
test('open tui pending disables only open tui', () => {
  assert.deepEqual(
    app.computeOpenTuiState(
      {
        status: 'active',
        app_server_health: 'healthy',
        thread_id: 'thread-main',
      },
      { openTuiPending: true }
    ),
    {
      canOpenTui: false,
      message: 'Opening...',
    }
  );
});
```

- [ ] **Step 2: Run the focused state test and verify failure**

Run:

```bash
node tests/web_management_ui_state.test.js
```

Expected before implementation: failures because `computeInstanceActionState()` still expects `isMutating`, and `computeOpenTuiState()` still expects `isMutating`.

- [ ] **Step 3: Replace state fields**

In `createState()`, replace:

```js
mutationKey: '',
```

with:

```js
sendPending: false,
refreshPending: false,
lifecyclePendingAction: '',
openTuiPending: false,
actorSelectionPendingId: '',
trackSelectionPendingId: '',
```

- [ ] **Step 4: Replace `computeInstanceActionState()`**

Replace the whole function with:

```js
function computeInstanceActionState(instance, options) {
  const draftText = options && typeof options.draftText === 'string' ? options.draftText.trim() : '';
  const sendPending = Boolean(options && options.sendPending);
  const lifecyclePendingAction = options && typeof options.lifecyclePendingAction === 'string'
    ? options.lifecyclePendingAction
    : '';
  if (!instance) {
    return {
      canSend: false,
      canInterrupt: false,
      canStop: false,
      canDelete: false,
      canClear: false,
      canResume: false,
    };
  }

  const status = instance.status || '';
  const threadStatus = instance.thread && typeof instance.thread.status === 'string'
    ? instance.thread.status
    : '';
  const appServerHealthy = instance.app_server_health === 'healthy'
    || Boolean(instance.app_server && instance.app_server.healthy);
  const isActive = status === 'active';
  const isInactive = status === 'inactive';
  const threadBusy = threadStatus === 'active' || threadStatus === 'in_progress';
  const lifecyclePending = Boolean(lifecyclePendingAction);

  return {
    canSend: isActive && appServerHealthy && draftText.length > 0 && !sendPending,
    canInterrupt: isActive && appServerHealthy && threadBusy && !lifecyclePending,
    canStop: isActive && !lifecyclePending,
    canDelete: isInactive && !lifecyclePending,
    canClear: isActive && appServerHealthy && !threadBusy && !lifecyclePending,
    canResume: isInactive && !lifecyclePending,
  };
}
```

- [ ] **Step 5: Replace `describeInstanceActionState()` pending logic**

Inside `describeInstanceActionState()`, replace `isMutating` handling with:

```js
const lifecyclePendingAction = options && typeof options.lifecyclePendingAction === 'string'
  ? options.lifecyclePendingAction
  : '';
```

Replace:

```js
} else if (isMutating) {
  clearReason = 'Action running.';
```

with:

```js
} else if (lifecyclePendingAction) {
  clearReason = lifecyclePendingAction + ' running.';
```

Call `computeInstanceActionState()` with `sendPending` and `lifecyclePendingAction`.

- [ ] **Step 6: Replace `computeOpenTuiState()`**

Replace:

```js
const isMutating = Boolean(options && options.isMutating);
if (!instance || isMutating) {
```

with:

```js
const openTuiPending = Boolean(options && options.openTuiPending);
if (!instance) {
```

Then add after the no-instance block:

```js
if (openTuiPending) {
  return {
    canOpenTui: false,
    message: 'Opening...',
  };
}
```

- [ ] **Step 7: Run the focused state test**

Run:

```bash
node tests/web_management_ui_state.test.js
```

Expected after implementation: all tests in the file pass.

## Task 2: Split Full Page Render Into Focused Render Functions

**Files:**
- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tools/launcher/assets/web-management/app.js`
- Modify: `tools/launcher/assets/web-management/index.html`

- [ ] **Step 1: Add page title ids**

In `index.html`, replace:

```html
<h1>Actor Console</h1>
<p class="page-summary">Select an actor, inspect runtime and task state, message directly, and use lifecycle controls in one place.</p>
```

with:

```html
<h1 id="page-title">Actor Console</h1>
<p id="page-summary" class="page-summary">Select an actor, inspect runtime and task state, message directly, and use lifecycle controls in one place.</p>
```

- [ ] **Step 2: Add render element stubs in state tests**

In `createRenderElements()`, add:

```js
pageTitle: node(),
pageSummary: node(),
refreshButton: node(),
```

- [ ] **Step 3: Add section copy tests**

Add:

```js
test('section copy follows selected workspace', () => {
  assert.deepEqual(app.sectionCopy('actors'), {
    title: 'Actor Console',
    summary: 'Select an actor, inspect runtime and task state, message directly, and use lifecycle controls in one place.',
  });
  assert.deepEqual(app.sectionCopy('tracks'), {
    title: 'Track workspace',
    summary: 'Review shared Tracks, materials, proofs, updates, and comments.',
  });
});
```

- [ ] **Step 4: Add focused composer render test**

Add:

```js
test('renderComposer updates the input and send button without actor list writes', () => {
  const state = app.createState();
  const elements = createRenderElements();
  state.draftText = 'ping';
  state.actors = [{ actor_id: 'act-market-demo', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } }];
  state.selectedActorId = 'act-market-demo';
  state.actorConsole = {
    actor: { actor_id: 'act-market-demo', role: 'market' },
    runtime: { status: 'active', app_server_health: 'healthy', thread_status: 'idle' },
  };
  elements.actorsList.innerHTML = 'unchanged';

  app.renderComposer(state, elements);

  assert.equal(elements.instructionInput.value, 'ping');
  assert.equal(elements.sendButton.disabled, false);
  assert.equal(elements.actorsList.innerHTML, 'unchanged');
});
```

- [ ] **Step 5: Run the focused state test and verify failure**

Run:

```bash
node tests/web_management_ui_state.test.js
```

Expected before implementation: failures because `sectionCopy` and `renderComposer` are not exported.

- [ ] **Step 6: Add `sectionCopy()`**

Add before `render()`:

```js
function sectionCopy(section) {
  if (section === 'tracks') {
    return {
      title: 'Track workspace',
      summary: 'Review shared Tracks, materials, proofs, updates, and comments.',
    };
  }
  return {
    title: 'Actor Console',
    summary: 'Select an actor, inspect runtime and task state, message directly, and use lifecycle controls in one place.',
  };
}
```

- [ ] **Step 7: Add focused render functions**

Split `render()` into these functions:

```js
function renderShell(state, elements) {
  const copy = sectionCopy(state.selectedSection);
  elements.serverStatus.textContent = state.healthOk ? 'API Ready' : 'API Unavailable';
  elements.serverStatus.classList.toggle('is-loading', state.refreshPending);
  elements.refreshButton.textContent = state.refreshPending ? 'Refreshing...' : 'Refresh';
  elements.refreshButton.disabled = state.refreshPending;
  elements.refreshButton.classList.toggle('is-pending', state.refreshPending);
  elements.messageBanner.textContent = state.message;
  elements.pageTitle.textContent = copy.title;
  elements.pageSummary.textContent = copy.summary;
  elements.actorView.hidden = state.selectedSection !== 'actors';
  elements.trackView.hidden = state.selectedSection !== 'tracks';
  elements.actorNavButton.classList.toggle('is-active', state.selectedSection === 'actors');
  elements.tracksNavButton.classList.toggle('is-active', state.selectedSection === 'tracks');
  elements.createButton.disabled = !computeCreateEnabled({
    selectedRole: state.selectedRole,
    isCreating: state.createPending,
  });
}

function renderRoleSelect(state, elements) {
  if (elements.roleSelect.options.length === 0) {
    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = 'Select role';
    elements.roleSelect.appendChild(placeholder);
    state.roles.forEach(function (role) {
      const option = document.createElement('option');
      option.value = role.id;
      option.textContent = role.label + ' (' + role.id + ')';
      elements.roleSelect.appendChild(option);
    });
  }
  elements.roleSelect.value = state.selectedRole;
}

function renderActorList(state, elements) {
  elements.actorsList.innerHTML = renderActorRowsHtml(state);
}

function renderActorDetail(state, elements) {
  elements.actorRuntimeDetail.innerHTML = renderRuntimeDetailHtml(state);
  elements.actorTaskSummary.innerHTML = renderTaskSummaryHtml(state);
  elements.actorTrackSummary.innerHTML = renderActorTrackSummaryHtml(state);
}

function renderTrackList(state, elements) {
  elements.tracksList.innerHTML = renderTrackRowsHtml(state);
}

function renderTrackDetail(state, elements) {
  elements.trackDetail.innerHTML = renderTrackDetailHtml(state.selectedTrackDetail);
}

function renderComposer(state, elements) {
  elements.instructionInput.value = state.draftText;
  const runtime = selectedActorRuntime(state);
  const actionState = describeInstanceActionState(runtime, {
    draftText: state.draftText,
    sendPending: state.sendPending,
    lifecyclePendingAction: state.lifecyclePendingAction,
  });
  elements.sendButton.disabled = !actionState.canSend;
  elements.sendButton.textContent = state.sendPending ? 'Sending...' : 'Send';
  elements.sendButton.classList.toggle('is-pending', state.sendPending);
  elements.interruptButton.disabled = !actionState.canInterrupt;
  elements.stopButton.disabled = !actionState.canStop;
  elements.deleteButton.disabled = !actionState.canDelete;
  elements.clearButton.disabled = !actionState.canClear;
  elements.resumeButton.disabled = !actionState.canResume;
  elements.actionAvailabilityStatus.textContent = !actionState.canClear && actionState.clearReason
    ? 'Clear disabled: ' + actionState.clearReason
    : '';
}

function renderOpenTui(state, elements) {
  const runtime = selectedActorRuntime(state);
  const openTuiState = computeOpenTuiState(runtime, {
    openTuiPending: state.openTuiPending,
  });
  elements.openTuiButton.disabled = !openTuiState.canOpenTui;
  elements.openTuiButton.textContent = state.openTuiPending ? 'Opening...' : 'Open TUI';
  elements.openTuiButton.classList.toggle('is-pending', state.openTuiPending);
  elements.openTuiStatus.textContent = state.openTuiPending
    ? 'Opening...'
    : (openTuiState.canOpenTui ? state.openTuiMessage : openTuiState.message);
  elements.openTuiCommand.textContent = state.openTuiCommand;
  elements.openTuiFallback.hidden = !state.openTuiCommand || !openTuiState.canOpenTui;
  elements.copyTuiCommandButton.disabled = !state.openTuiCommand || !openTuiState.canOpenTui;
}

function renderAll(state, elements) {
  renderShell(state, elements);
  renderRoleSelect(state, elements);
  renderActorList(state, elements);
  renderActorDetail(state, elements);
  renderTrackList(state, elements);
  renderTrackDetail(state, elements);
  renderComposer(state, elements);
  renderOpenTui(state, elements);
  renderImConversation(state, elements);
}
```

Keep a wrapper for existing internal call sites while migrating:

```js
function render(state, elements) {
  renderAll(state, elements);
}
```

The wrapper must be deleted in Task 6 after call sites are converted.

- [ ] **Step 8: Export focused render helpers**

Export:

```js
renderComposer,
sectionCopy,
```

- [ ] **Step 9: Run the focused state test**

Run:

```bash
node tests/web_management_ui_state.test.js
```

Expected after implementation: all tests in the file pass.

## Task 3: Install Row Event Delegation Once

**Files:**
- Modify: `tools/launcher/assets/web-management/app.js`
- Modify: `tests/web_management_ui_contract.test.js`

- [ ] **Step 1: Add residue gates**

In `tests/web_management_ui_contract.test.js`, add:

```js
test('production javascript does not attach row click handlers from render', () => {
  assertExcludes(appJs, "elements.actorsList.querySelectorAll('[data-actor-id]').forEach");
  assertExcludes(appJs, "elements.tracksList.querySelectorAll('[data-track-id]').forEach");
});
```

- [ ] **Step 2: Run the contract test and verify failure**

Run:

```bash
node tests/web_management_ui_contract.test.js
```

Expected before implementation: failure because row listeners are still installed inside `render()`.

- [ ] **Step 3: Delete listener installation from `render()`**

Remove the two `querySelectorAll(...).forEach(...)` blocks from `render()`.

- [ ] **Step 4: Add delegated listeners in `bootstrap()`**

After the nav button listeners in `bootstrap()`, add:

```js
elements.actorsList.addEventListener('click', function (event) {
  const row = event.target && event.target.closest
    ? event.target.closest('[data-actor-id]')
    : null;
  if (!row) {
    return;
  }
  selectActor(state, elements, row.getAttribute('data-actor-id') || '').catch(function (error) {
    state.message = error.message;
    renderShell(state, elements);
  });
});

elements.tracksList.addEventListener('click', function (event) {
  const row = event.target && event.target.closest
    ? event.target.closest('[data-track-id]')
    : null;
  if (!row) {
    return;
  }
  selectTrack(state, elements, row.getAttribute('data-track-id') || '').catch(function (error) {
    state.message = error.message;
    renderShell(state, elements);
  });
});
```

- [ ] **Step 5: Run the contract test**

Run:

```bash
node tests/web_management_ui_contract.test.js
```

Expected after implementation: all tests in the file pass.

## Task 4: Rebuild Send as a Focused Action

**Files:**
- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tools/launcher/assets/web-management/app.js`

- [ ] **Step 1: Add pending-send state tests**

Add:

```js
test('pending sent IM message is replaced with accepted server message', () => {
  const state = app.createState();
  const pendingId = app.recordImPendingSend(state, 'ping');

  assert.equal(state.imConversation.length, 1);
  assert.equal(state.imConversation[0].id, pendingId);
  assert.equal(state.imConversation[0].deliveryStatus, 'sending');

  app.replaceImPendingSend(state, pendingId, {
    message: { id: 'msg-sent-1' },
    delivery_status: 'accepted',
    wake_status: 'submitted',
  }, 'ping');

  assert.deepEqual(state.imConversation, [
    {
      id: 'msg-sent-1',
      direction: 'sent',
      sender: 'you',
      content: 'ping',
      deliveryStatus: 'accepted',
      wakeStatus: 'submitted',
      replyTo: '',
    },
  ]);
  assert.equal(state.imSeenMessageIds['msg-sent-1'], true);
  assert.equal(state.imSeenMessageIds[pendingId], undefined);
});
```

Add:

```js
test('failed pending send is removed and draft can be restored by caller', () => {
  const state = app.createState();
  const pendingId = app.recordImPendingSend(state, 'ping');

  app.removeImEntry(state, pendingId);

  assert.deepEqual(state.imConversation, []);
  assert.equal(state.imSeenMessageIds[pendingId], undefined);
});
```

- [ ] **Step 2: Run the focused state test and verify failure**

Run:

```bash
node tests/web_management_ui_state.test.js
```

Expected before implementation: failures because `recordImPendingSend`, `replaceImPendingSend`, and `removeImEntry` are not exported.

- [ ] **Step 3: Add pending message helpers**

Add before `recordImSent()`:

```js
function createPendingMessageId() {
  return 'pending-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8);
}

function recordImPendingSend(state, content) {
  const pendingId = createPendingMessageId();
  rememberImEntry(state, {
    id: pendingId,
    direction: 'sent',
    sender: 'you',
    content: typeof content === 'string' ? content : '',
    deliveryStatus: 'sending',
    wakeStatus: '',
    replyTo: '',
  });
  return pendingId;
}

function removeImEntry(state, messageId) {
  if (!messageId) {
    return false;
  }
  const beforeLength = state.imConversation.length;
  state.imConversation = state.imConversation.filter(function (entry) {
    return entry.id !== messageId;
  });
  delete state.imSeenMessageIds[messageId];
  return state.imConversation.length !== beforeLength;
}

function replaceImPendingSend(state, pendingId, payload, content) {
  const messageId = payload && payload.message && payload.message.id ? payload.message.id : '';
  const replacement = {
    id: messageId,
    direction: 'sent',
    sender: 'you',
    content: typeof content === 'string' ? content : '',
    deliveryStatus: payload && payload.delivery_status ? payload.delivery_status : '',
    wakeStatus: payload && payload.wake_status ? payload.wake_status : '',
    replyTo: '',
  };
  let replaced = false;
  state.imConversation = state.imConversation.map(function (entry) {
    if (entry.id !== pendingId) {
      return entry;
    }
    replaced = true;
    return replacement;
  });
  delete state.imSeenMessageIds[pendingId];
  if (messageId) {
    state.imSeenMessageIds[messageId] = true;
  }
  if (!replaced) {
    rememberImEntry(state, replacement);
  }
  return replaced;
}
```

- [ ] **Step 4: Change `sendImDraft()` to take explicit content**

Replace:

```js
async function sendImDraft(state, elements) {
```

with:

```js
async function sendImDraft(state, elements, content) {
```

Replace the body payload content field:

```js
content: state.draftText,
```

with:

```js
content: content,
```

Delete:

```js
recordImSent(state, payload, content);
```

The caller owns pending-row replacement.

- [ ] **Step 5: Add focused send handler**

Add:

```js
async function sendCurrentDraft(state, elements) {
  const content = typeof state.draftText === 'string' ? state.draftText.trim() : '';
  if (!content || state.sendPending) {
    return;
  }
  const previousDraft = state.draftText;
  const pendingId = recordImPendingSend(state, content);
  state.draftText = '';
  state.sendPending = true;
  state.message = '';
  renderComposer(state, elements);
  renderImConversation(state, elements);
  try {
    const payload = await sendImDraft(state, elements, content);
    replaceImPendingSend(state, pendingId, payload, content);
    const imMessageId = payload && payload.message && payload.message.id ? payload.message.id : '';
    state.message = imMessageId
      ? 'Sent message ' + imMessageId + (payload.delivery_status ? ' (' + payload.delivery_status + ').' : '.')
      : 'Message sent.';
    await refreshSelectedActorConsole(state);
    renderActorDetail(state, elements);
  } catch (error) {
    removeImEntry(state, pendingId);
    state.draftText = previousDraft;
    state.message = error.message;
  } finally {
    state.sendPending = false;
    renderShell(state, elements);
    renderComposer(state, elements);
    renderImConversation(state, elements);
  }
}
```

- [ ] **Step 6: Replace the Send click handler**

Replace:

```js
elements.sendButton.addEventListener('click', function () {
  runMutation(state, elements, 'messages', function () {
    return sendImDraft(state, elements);
  }).then(function () {
    state.draftText = '';
  });
});
```

with:

```js
elements.sendButton.addEventListener('click', function () {
  sendCurrentDraft(state, elements).catch(function (error) {
    state.message = error.message;
    state.sendPending = false;
    renderShell(state, elements);
    renderComposer(state, elements);
  });
});
```

- [ ] **Step 7: Export helpers**

Export:

```js
recordImPendingSend,
replaceImPendingSend,
removeImEntry,
```

- [ ] **Step 8: Run the focused state test**

Run:

```bash
node tests/web_management_ui_state.test.js
```

Expected after implementation: all tests in the file pass.

## Task 5: Convert Lifecycle, Refresh, Open TUI, and Selection Paths to Focused Renders

**Files:**
- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tools/launcher/assets/web-management/app.js`

- [ ] **Step 1: Add action state tests for lifecycle pending**

Add:

```js
test('lifecycle pending disables lifecycle buttons without disabling send', () => {
  assert.deepEqual(
    app.computeInstanceActionState(
      {
        status: 'active',
        app_server_health: 'healthy',
        thread: { status: 'idle' },
      },
      {
        draftText: 'keep typing',
        sendPending: false,
        lifecyclePendingAction: 'clear',
      }
    ),
    {
      canSend: true,
      canInterrupt: false,
      canStop: false,
      canDelete: false,
      canClear: false,
      canResume: false,
    }
  );
});
```

- [ ] **Step 2: Run the focused state test**

Run:

```bash
node tests/web_management_ui_state.test.js
```

Expected after Task 1: this test passes.

- [ ] **Step 3: Replace lifecycle calls to `runMutation()`**

Add:

```js
async function runLifecycleAction(state, elements, action) {
  if (!action || state.lifecyclePendingAction) {
    return;
  }
  state.lifecyclePendingAction = action;
  state.message = '';
  renderComposer(state, elements);
  try {
    const payload = await fetchJson(actorActionUrl(state, action), {
      method: 'POST',
    });
    state.message = payload && payload.turn_id
      ? 'Action completed for ' + state.selectedActorId + ' (' + payload.turn_id + ').'
      : 'Action completed.';
    clearOpenTuiFeedback(state);
    await refreshSelectedActorConsole(state);
    renderActorDetail(state, elements);
  } catch (error) {
    state.message = error.message;
  } finally {
    state.lifecyclePendingAction = '';
    renderShell(state, elements);
    renderComposer(state, elements);
    renderOpenTui(state, elements);
  }
}
```

Replace interrupt, stop, clear, and resume handlers with:

```js
elements.interruptButton.addEventListener('click', function () {
  runLifecycleAction(state, elements, 'interrupt').catch(function (error) {
    state.message = error.message;
    state.lifecyclePendingAction = '';
    renderShell(state, elements);
    renderComposer(state, elements);
  });
});
```

Use the same pattern for `stop`, `clear`, and `resume`.

- [ ] **Step 4: Replace delete with focused delete action**

Add:

```js
async function deleteSelectedActor(state, elements) {
  if (!state.selectedActorId || state.lifecyclePendingAction) {
    return;
  }
  const actorId = state.selectedActorId;
  state.lifecyclePendingAction = 'delete';
  state.message = '';
  renderComposer(state, elements);
  try {
    const payload = await fetchJson('/api/instances/' + encodeURIComponent(actorId), {
      method: 'DELETE',
    });
    state.message = payload && payload.ok ? 'Deleted ' + actorId + '.' : 'Deleted actor.';
    state.selectedActorId = '';
    state.actorConsole = null;
    clearImConversation(state, '');
    clearOpenTuiFeedback(state);
    await refreshAll(state, elements);
  } catch (error) {
    state.message = error.message;
    renderShell(state, elements);
  } finally {
    state.lifecyclePendingAction = '';
    renderAll(state, elements);
  }
}
```

Replace the delete click handler with:

```js
elements.deleteButton.addEventListener('click', function () {
  deleteSelectedActor(state, elements).catch(function (error) {
    state.message = error.message;
    state.lifecyclePendingAction = '';
    renderAll(state, elements);
  });
});
```

- [ ] **Step 5: Replace Open TUI pending state**

Inside `openTui()`, replace `state.mutationKey = 'open-tui';` with:

```js
state.openTuiPending = true;
```

Replace the `finally` assignment with:

```js
state.openTuiPending = false;
```

Replace `render(state, elements)` calls inside `openTui()` with:

```js
renderOpenTui(state, elements);
renderComposer(state, elements);
```

- [ ] **Step 6: Replace manual Refresh**

Add:

```js
async function refreshAllWithFeedback(state, elements) {
  if (state.refreshPending) {
    return;
  }
  state.refreshPending = true;
  state.message = '';
  renderShell(state, elements);
  try {
    await refreshAll(state, elements);
    state.message = 'Refreshed.';
  } catch (error) {
    state.message = error.message;
  } finally {
    state.refreshPending = false;
    renderAll(state, elements);
  }
}
```

Replace the Refresh click handler with:

```js
elements.refreshButton.addEventListener('click', function () {
  refreshAllWithFeedback(state, elements).catch(function (error) {
    state.message = error.message;
    state.refreshPending = false;
    renderAll(state, elements);
  });
});
```

- [ ] **Step 7: Render immediately during actor selection**

Replace `selectActor()` with:

```js
async function selectActor(state, elements, actorId) {
  if (!actorId || actorId === state.selectedActorId || state.actorSelectionPendingId) {
    return;
  }
  state.selectedActorId = actorId;
  state.actorConsole = null;
  state.actorSelectionPendingId = actorId;
  state.message = '';
  clearImConversation(state, actorId);
  clearOpenTuiFeedback(state);
  renderActorList(state, elements);
  renderActorDetail(state, elements);
  renderComposer(state, elements);
  renderOpenTui(state, elements);
  renderImConversation(state, elements);
  try {
    await refreshSelectedActorConsole(state);
    await refreshSelectedActorConversation(state);
  } finally {
    state.actorSelectionPendingId = '';
    renderActorList(state, elements);
    renderActorDetail(state, elements);
    renderComposer(state, elements);
    renderOpenTui(state, elements);
    renderImConversation(state, elements);
    scheduleActorConsoleRefresh(state, elements);
  }
}
```

- [ ] **Step 8: Render immediately during track selection**

Replace `selectTrack()` with:

```js
async function selectTrack(state, elements, trackId) {
  if (!trackId || trackId === state.selectedTrackId || state.trackSelectionPendingId) {
    return;
  }
  state.selectedTrackId = trackId;
  state.selectedTrackDetail = null;
  state.trackSelectionPendingId = trackId;
  renderTrackList(state, elements);
  renderTrackDetail(state, elements);
  try {
    await refreshSelectedTrackDetail(state);
  } finally {
    state.trackSelectionPendingId = '';
    renderTrackList(state, elements);
    renderTrackDetail(state, elements);
  }
}
```

- [ ] **Step 9: Run focused tests**

Run:

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
```

Expected after implementation: both files pass.

## Task 6: Remove Old Full-Render and Global-Mutation Residue

**Files:**
- Modify: `tools/launcher/assets/web-management/app.js`
- Modify: `tests/web_management_ui_contract.test.js`

- [ ] **Step 1: Add residue gates**

Add:

```js
test('production javascript does not keep global mutation state residue', () => {
  assertExcludes(appJs, 'mutationKey');
  assertExcludes(appJs, 'isMutating');
  assertExcludes(appJs, 'Action running.');
  assertExcludes(appJs, "runMutation(state, elements, 'messages'");
});
```

Add:

```js
test('production javascript keeps draft input off the full page render path', () => {
  assertExcludes(appJs, 'render(state, elements);');
});
```

- [ ] **Step 2: Run contract test and verify failure**

Run:

```bash
node tests/web_management_ui_contract.test.js
```

Expected before cleanup: failure while old strings remain.

- [ ] **Step 3: Convert input handler to focused render**

Replace:

```js
elements.instructionInput.addEventListener('input', function (event) {
  state.draftText = event.target.value;
  render(state, elements);
});
```

with:

```js
elements.instructionInput.addEventListener('input', function (event) {
  state.draftText = event.target.value;
  renderComposer(state, elements);
});
```

- [ ] **Step 4: Delete `runMutation()`**

After Task 5, no live handler uses `runMutation()`. Delete the function.

- [ ] **Step 5: Delete the compatibility `render()` wrapper**

Replace remaining internal `render(state, elements)` call sites with focused render functions or `renderAll(state, elements)`. Then delete:

```js
function render(state, elements) {
  renderAll(state, elements);
}
```

- [ ] **Step 6: Run residue scans**

Run:

```bash
rg -n "mutationKey|isMutating|Action running\\.|runMutation\\(" tools/launcher/assets/web-management/app.js tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js -S
```

Expected: no output.

Run:

```bash
rg -n "querySelectorAll\\('\\[data-actor-id\\]'\\)|querySelectorAll\\('\\[data-track-id\\]'\\)" tools/launcher/assets/web-management/app.js -S
```

Expected: no output.

Run:

```bash
rg -n "POST /api/web/im|/api/web/im|buildWebImConversationUrl|ensureWebImSession|connection_key|participant_token|event_cursor|cursor=" tools/launcher/assets/web-management/app.js tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js -S
```

Expected: no output.

- [ ] **Step 7: Run Node tests**

Run:

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
```

Expected after cleanup: both files pass.

## Task 7: CSS Feedback and Mobile Priority Polish

**Files:**
- Modify: `tools/launcher/assets/web-management/styles.css`
- Modify: `tools/launcher/assets/web-management/index.html`
- Modify: `tests/web_management_ui_contract.test.js`

- [ ] **Step 1: Add CSS contract markers**

Add to `tests/web_management_ui_contract.test.js`:

```js
test('production stylesheet supports pending and loading feedback states', () => {
  [
    '.is-loading',
    '.button.is-pending',
    '.selectable-row.is-loading',
    '.inline-loading',
    '.im-row.pending',
    '.im-row.failed',
  ].forEach((marker) => {
    assertIncludes(stylesCss, marker);
  });
});
```

- [ ] **Step 2: Run contract test and verify failure**

Run:

```bash
node tests/web_management_ui_contract.test.js
```

Expected before CSS implementation: failure because the new classes do not exist.

- [ ] **Step 3: Add feedback CSS**

Add after `.button[disabled]`:

```css
.is-loading {
  cursor: progress;
}

.button.is-pending {
  cursor: progress;
}

.selectable-row.is-loading {
  background: var(--surface-soft);
}

.inline-loading {
  color: var(--muted);
  font-size: 12px;
}

.im-row.pending {
  border-style: dashed;
}

.im-row.failed {
  border-color: #efc2bd;
  background: var(--danger-soft);
}
```

- [ ] **Step 4: Improve narrow-screen action priority**

Inside `@media (max-width: 960px)`, add:

```css
.runtime-column {
  order: -1;
}
```

This places Actions before the deep runtime detail column on narrow screens while preserving desktop layout.

- [ ] **Step 5: Run contract test**

Run:

```bash
node tests/web_management_ui_contract.test.js
```

Expected after implementation: all tests in the file pass.

## Task 8: Browser Smoke and End-To-End Acceptance

**Files:**
- No required source edits.
- Runtime smoke uses the existing local Web Management server.

- [ ] **Step 1: Run focused automated verification**

Run:

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
```

Expected: both commands exit `0`.

- [ ] **Step 2: Run scoped residue verification**

Run:

```bash
rg -n "mutationKey|isMutating|Action running\\.|runMutation\\(" tools/launcher/assets/web-management/app.js tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js -S
```

Expected: no output.

Run:

```bash
rg -n "Modify: `tools/launcher/(im_http_router|web_management)|Create: `tools/launcher/(im_http_router|web_management)|Modify: `scripts/|Modify: `buddyswitch/objects" docs/memo/2026-06-30-webui-interaction-smoothness-forward-plan.md -S
```

Expected: no output.

- [ ] **Step 3: Smoke Send in the browser**

Open:

```text
http://127.0.0.1:8765/
```

Steps:

1. Select an active actor.
2. Type `webui smoothness smoke`.
3. Click Send.
4. Observe the textarea clears immediately.
5. Observe one pending or sent message row appears immediately.
6. Observe Send shows `Sending...` while the request is pending.
7. Observe Open TUI, Clear, Stop, and Refresh are not disabled by Send pending state.
8. Observe the final status says `Sent message <id> (accepted).`

- [ ] **Step 4: Smoke Actor switch**

Steps:

1. Click another actor.
2. Observe the selected row changes immediately.
3. Observe old actor messages disappear immediately.
4. Observe selected actor runtime replaces stale details when fetch completes.
5. Observe no old actor success banner remains after the switch.

- [ ] **Step 5: Smoke Tracks navigation**

Steps:

1. Click Tracks.
2. Observe the page title changes to `Track workspace`.
3. Observe page summary changes to `Review shared Tracks, materials, proofs, updates, and comments.`
4. Click Actors.
5. Observe page title returns to `Actor Console`.

- [ ] **Step 6: Smoke narrow viewport**

Use a viewport around `390x844`.

Expected:

- Actions appear before deep runtime detail.
- Message textarea and Send button are visible before long runtime metadata.
- Button text does not wrap.

## Acceptance Criteria

- Send clears the input before the network response returns.
- Send no longer calls `refreshAll()`.
- Send pending disables only Send.
- Lifecycle pending disables lifecycle buttons without disabling Send.
- Open TUI pending disables only Open TUI.
- Manual Refresh has visible pending and completion feedback.
- Typing in the textarea does not rerender actor rows, track rows, runtime details, or conversation.
- Actor row click handlers are installed once through event delegation.
- Actor selection has immediate selected-row and empty-history feedback.
- Section title and summary match the active section.
- `E_IM_NOT_FOUND` remains a backend 404 but renders as empty WebUI history.
- No backend route, IM service, runtime object, or product persistence file is modified.
- Scoped residue scans show no global mutation state or old Web IM route residue in live WebUI surfaces.

## Verification Commands

Run:

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
```

Expected:

```text
all tests print ok lines and exit 0
```

Run:

```bash
rg -n "mutationKey|isMutating|Action running\\.|runMutation\\(" tools/launcher/assets/web-management/app.js tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js -S
```

Expected:

```text
no output
```

Run:

```bash
rg -n "/api/web/im|buildWebImConversationUrl|ensureWebImSession|connection_key|participant_token|event_cursor|cursor=" tools/launcher/assets/web-management/app.js tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js -S
```

Expected:

```text
no output
```

Run:

```bash
git diff --name-only
```

Expected implementation diff after this plan is executed:

```text
tools/launcher/assets/web-management/app.js
tools/launcher/assets/web-management/index.html
tools/launcher/assets/web-management/styles.css
tests/web_management_ui_contract.test.js
tests/web_management_ui_state.test.js
```

## Non-Goals

- Do not change `E_IM_NOT_FOUND` HTTP status.
- Do not add a Web-specific backend adapter for empty direct conversations.
- Do not aggregate histories across different external identities.
- Do not add React, Vue, state-management libraries, build tooling, or a design system.
- Do not redesign the product information architecture.
- Do not preserve both old global mutation behavior and new action-scoped behavior.

## Remaining Risk

- The live backend can still take around one second for `/api/actors` and direct conversation requests. This plan removes those requests from the Send critical path rather than making those backend calls faster.
- Long-poll `/api/im/events?wait_ms=15000` remains part of the current IM contract. This plan keeps it but prevents it from forcing broad visible rerenders.
- If future product intent requires history across multiple external identities, that is a new IM product requirement and must not be hidden inside WebUI cache logic.
