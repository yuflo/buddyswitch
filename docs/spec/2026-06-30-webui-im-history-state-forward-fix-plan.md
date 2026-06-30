# WebUI IM History State Forward Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix Web Management actor message history so the UI never shows stale or off-selected actor IM history after the unified `/api/im/*` route migration.

**Architecture:** Keep `/api/im/*` as the only IM HTTP product contract. The IM router and `ExternalImSession` keep owning IM semantics and may return `404 E_IM_NOT_FOUND` for a missing direct conversation; the Browser UI owns the transient selected-actor render cache and must normalize that 404 into an empty selected-actor history without introducing a compatibility route or server-side Web BFF branch.

**Tech Stack:** Plain browser JavaScript in `tools/launcher/assets/web-management/app.js`, Node `node --test` UI contract/state tests, Python `unittest` Web Management/IM router tests, local Web Management server at `http://127.0.0.1:8765/` for live smoke.

---

## Current Bottleneck

The recent `1929e32 feat: unify IM API routes` change moved WebUI from retired `/api/web/im/*` routes to the unified `/api/im/*` contract. The backend route semantics are now coherent, but the Browser UI still treats selected actor history as a single unowned cache.

Confirmed failures:

- `GET /api/im/conversations/direct?identity_id=act-market-1e9c7bec4ab8&limit=50` returns `404 E_IM_NOT_FOUND`.
- `GET /api/im/conversations/direct?identity_id=act-market-cdf9ce181c79&limit=50` returns a direct conversation with two messages.
- In the live page, switching from `act-market-cdf9ce181c79` back to `act-market-1e9c7bec4ab8` leaves the two `act-market-cdf9ce181c79` messages rendered under the selected `act-market-1e9c7bec4ab8` actor.
- A VM reproduction of current `pollImEventsOnce()` shows that a connection-wide event for `act-other` is appended to the single `state.imConversation` while `state.selectedActorId` remains `act-selected`.

## Boundary Decisions

- Browser UI owns selected actor interaction state, rendering, and transient render caches.
- Web-interface API continues to expose Browser-facing routes and delegates IM routes to `ImHttpRouter`.
- `ImHttpRouter` owns HTTP projection for `/api/im/*` and keeps mapping `E_IM_NOT_FOUND` to HTTP 404.
- `ExternalImSession` owns IM identity, direct conversation lookup, event reads, message fetches, and explicit ack semantics.
- Repo/persistence remains behind the IM service and must not become a Browser-facing API.

## Non-Negotiables

- Do not restore `/api/web/im/*`.
- Do not add `_web_im_*` compatibility helpers.
- Do not change `ImHttpRouter._status_for_direct_conversation()` to return 200 for `E_IM_NOT_FOUND`.
- Do not add a Web-specific backend branch that translates missing conversations into empty payloads.
- Do not introduce actor-history aggregation across different external identities.
- Do not preserve both old and new frontend routes, helper names, or event payload semantics.
- Do not leave a global unowned `imConversation` cache that can be rendered for a different selected actor.

## State Invariants

After the fix:

- `state.imConversationIdentityId` is the actor identity id that owns `state.imConversation`.
- `state.imConversationIdentityId === selectedActorImTarget(state).identity_id` whenever `state.imConversation.length > 0`.
- Selecting, creating, deleting, or losing the selected actor clears IM render cache before any async fetch can fail.
- `E_IM_NOT_FOUND` from `/api/im/conversations/direct` means empty history for the selected WebUI identity and is not rendered as a banner error.
- Connection-wide `/api/im/events` may be fetched and acked, but only messages touching the currently selected actor identity may be appended to the selected actor conversation.
- Off-selected actor events are not rendered in the current actor panel; their durable history remains available through `/api/im/conversations/direct?identity_id=<actor>` when that actor becomes selected.

## Files

- Modify: `tools/launcher/assets/web-management/app.js`
  - Own selected-actor IM cache identity.
  - Normalize missing selected direct conversation to empty UI history.
  - Record fetched event messages only for the current selected actor.
  - Delete stale known-actor event filtering logic.
- Modify: `tests/web_management_ui_state.test.js`
  - Add focused state tests for cache ownership, missing conversation normalization, actor switch clearing, and off-selected event filtering.
- Modify: `tests/web_management_ui_contract.test.js`
  - Add residue gates for removed helper names and compatibility route family.
- Do not modify: `tools/launcher/im_http_router.py`
- Do not modify: `tools/launcher/web_management.py` for IM BFF compatibility.

## Task 1: Add Owned IM Conversation Cache State

**Files:**
- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tools/launcher/assets/web-management/app.js`

- [ ] **Step 1: Write the failing default-state test**

Add this assertion to the existing `state defaults to actor console as the primary section` test:

```js
assert.equal(state.imConversationIdentityId, '');
```

- [ ] **Step 2: Write the failing clear-helper test**

Add this test near the existing IM state tests:

```js
test('clearing im conversation records owner identity and removes stale rows', () => {
  const state = app.createState();
  app.recordImProjectedMessage(state, {
    id: 'msg-stale',
    from_identity_id: 'act-market-old',
    to_identity_id: 'ext-web',
    content: 'stale',
    reply_to: null,
  });

  app.clearImConversation(state, 'act-market-new');

  assert.equal(state.imConversationIdentityId, 'act-market-new');
  assert.deepEqual(state.imConversation, []);
  assert.deepEqual(state.imSeenMessageIds, {});
});
```

- [ ] **Step 3: Run the focused Node test and verify it fails**

Run:

```bash
node --test tests/web_management_ui_state.test.js
```

Expected: failure because `imConversationIdentityId` and `app.clearImConversation` do not exist yet.

- [ ] **Step 4: Add owned cache state and helper**

In `createState()` add:

```js
imConversationIdentityId: '',
```

Add this helper before `rememberImEntry()`:

```js
function clearImConversation(state, identityId) {
  state.imConversationIdentityId = typeof identityId === 'string' ? identityId : '';
  state.imConversation = [];
  state.imSeenMessageIds = {};
}
```

Update `applyImConversationPayload()` to accept the owner identity:

```js
function applyImConversationPayload(state, payload, identityId) {
  clearImConversation(state, identityId);
  const messages = payload && Array.isArray(payload.messages) ? payload.messages : [];
  messages.forEach(function (message) {
    recordImProjectedMessage(state, message);
  });
}
```

Update existing call sites that intentionally clear without a target:

```js
applyImConversationPayload(state, { messages: [] }, '');
```

Update the existing `direct conversation payload replaces local render cache with persisted history` test so the payload apply call passes an owner identity:

```js
app.applyImConversationPayload(state, {
  messages: [
    {
      id: 'msg-sent-1',
      from_identity_id: 'ext-web',
      to_identity_id: 'act-market-1',
      content: 'ping',
      reply_to: null,
    },
    {
      id: 'msg-reply-1',
      from_identity_id: 'act-market-1',
      to_identity_id: 'ext-web',
      content: 'pong',
      reply_to: 'msg-sent-1',
    },
  ],
}, 'act-market-1');
```

Add this assertion to that test:

```js
assert.equal(state.imConversationIdentityId, 'act-market-1');
```

Export the helper:

```js
clearImConversation,
```

- [ ] **Step 5: Run the focused Node test and verify it passes**

Run:

```bash
node --test tests/web_management_ui_state.test.js
```

Expected: all tests in the file pass.

## Task 2: Treat Missing Selected Direct Conversation as Empty History

**Files:**
- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tools/launcher/assets/web-management/app.js`

- [ ] **Step 1: Write the failing missing-conversation test**

Add this async test near the direct conversation payload test:

```js
test('selected actor conversation treats missing direct conversation as empty history', async () => {
  const originalFetch = global.fetch;
  global.fetch = async function (url) {
    assert.equal(
      url,
      '/api/im/conversations/direct?identity_id=act-market-empty&limit=50'
    );
    return {
      ok: false,
      json: async function () {
        return {
          ok: false,
          error: {
            code: 'E_IM_NOT_FOUND',
            message: 'direct conversation not found',
          },
        };
      },
    };
  };

  try {
    const state = app.createState();
    state.selectedActorId = 'act-market-empty';
    state.actors = [{ actor_id: 'act-market-empty', role: 'market' }];
    state.actorConsole = {
      im: {
        target: {
          identity_id: 'act-market-empty',
          role_id: 'market',
        },
      },
    };
    app.recordImProjectedMessage(state, {
      id: 'msg-stale',
      from_identity_id: 'act-market-old',
      to_identity_id: 'ext-web',
      content: 'stale',
      reply_to: null,
    });

    await app.refreshSelectedActorConversation(state);

    assert.equal(state.imConversationIdentityId, 'act-market-empty');
    assert.deepEqual(state.imConversation, []);
    assert.deepEqual(state.imSeenMessageIds, {});
    assert.equal(state.message, '');
  } finally {
    global.fetch = originalFetch;
  }
});
```

- [ ] **Step 2: Run the focused Node test and verify it fails**

Run:

```bash
node --test tests/web_management_ui_state.test.js
```

Expected: failure because `refreshSelectedActorConversation` is not exported and missing conversation still throws.

- [ ] **Step 3: Add a missing-conversation error predicate**

Add this helper near `fetchJson()`:

```js
function isImConversationNotFoundError(error) {
  const payload = error && error.payload && typeof error.payload === 'object' ? error.payload : null;
  const detail = payload && payload.error && typeof payload.error === 'object' ? payload.error : null;
  return Boolean(detail && detail.code === 'E_IM_NOT_FOUND');
}
```

- [ ] **Step 4: Normalize missing selected conversation in the Browser UI**

Replace `refreshSelectedActorConversation()` with:

```js
async function refreshSelectedActorConversation(state) {
  const target = selectedActorImTarget(state);
  const identityId = target && target.identity_id ? target.identity_id : '';
  clearImConversation(state, identityId);
  if (!identityId) {
    return;
  }
  try {
    const payload = await fetchJson(
      buildImConversationUrl(identityId, 50)
    );
    applyImConversationPayload(state, payload, identityId);
  } catch (error) {
    if (isImConversationNotFoundError(error)) {
      if (state.message === error.message) {
        state.message = '';
      }
      return;
    }
    throw error;
  }
}
```

Export the function for focused state tests:

```js
refreshSelectedActorConversation,
```

- [ ] **Step 5: Run the focused Node test and verify it passes**

Run:

```bash
node --test tests/web_management_ui_state.test.js
```

Expected: all tests in the file pass.

## Task 3: Clear IM Cache on Actor Selection Boundary Changes

**Files:**
- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tools/launcher/assets/web-management/app.js`

- [ ] **Step 1: Write the failing actor-list selection-change test**

Extend the existing `actor payload sync chooses first actor and clears stale selection` test:

```js
app.recordImProjectedMessage(state, {
  id: 'msg-stale',
  from_identity_id: 'act-missing',
  to_identity_id: 'ext-web',
  content: 'stale',
  reply_to: null,
});
```

Add these assertions after the existing selected actor assertions:

```js
assert.equal(state.imConversationIdentityId, 'act-pm-demo');
assert.deepEqual(state.imConversation, []);
assert.deepEqual(state.imSeenMessageIds, {});
```

- [ ] **Step 2: Run the focused Node test and verify it fails**

Run:

```bash
node --test tests/web_management_ui_state.test.js
```

Expected: failure because `applyActorsPayload()` does not clear IM cache when it changes selected actor.

- [ ] **Step 3: Clear cache in `applyActorsPayload()` when selected actor changes**

Update the selected-actor change block:

```js
if (state.selectedActorId !== previousActorId) {
  clearOpenTuiFeedback(state);
  clearImConversation(state, state.selectedActorId);
}
```

- [ ] **Step 4: Clear cache immediately in explicit actor selection**

Update `selectActor()`:

```js
state.selectedActorId = actorId;
state.actorConsole = null;
clearImConversation(state, actorId);
clearOpenTuiFeedback(state);
```

- [ ] **Step 5: Clear cache in create/delete/no-selection paths**

In `createInstance()` after selecting the created actor:

```js
clearImConversation(state, payload.actor_id);
```

In the delete handler after clearing `selectedActorId`:

```js
clearImConversation(state, '');
```

In `refreshSelectedActorConsole()` when no actor is selected:

```js
clearImConversation(state, '');
```

- [ ] **Step 6: Run the focused Node test and verify it passes**

Run:

```bash
node --test tests/web_management_ui_state.test.js
```

Expected: all tests in the file pass.

## Task 4: Record Event Messages Only for the Selected Actor

**Files:**
- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tools/launcher/assets/web-management/app.js`

- [ ] **Step 1: Write the failing selected-event-message helper test**

Add this test near `fetched im message appends projected reply without browser cursor state`:

```js
test('connection-wide fetched event messages only append when they touch selected actor', () => {
  const state = app.createState();
  state.selectedActorId = 'act-market-selected';
  state.imConversationIdentityId = 'act-market-selected';

  const offScopeRecorded = app.recordSelectedActorEventMessage(
    state,
    {
      id: 'msg-dev',
      from_identity_id: 'act-dev-other',
      to_identity_id: 'ext-web',
      content: 'dev pong',
      reply_to: null,
    },
    'act-market-selected'
  );

  const selectedRecorded = app.recordSelectedActorEventMessage(
    state,
    {
      id: 'msg-market',
      from_identity_id: 'act-market-selected',
      to_identity_id: 'ext-web',
      content: 'market pong',
      reply_to: null,
    },
    'act-market-selected'
  );

  assert.equal(offScopeRecorded, false);
  assert.equal(selectedRecorded, true);
  assert.deepEqual(state.imConversation.map((entry) => [entry.id, entry.content]), [
    ['msg-market', 'market pong'],
  ]);
});
```

- [ ] **Step 2: Write the failing polling integration test**

Add this render-elements helper near the top of `tests/web_management_ui_state.test.js` after `test()`:

```js
function createRenderElements() {
  const node = () => ({
    textContent: '',
    value: '',
    hidden: false,
    disabled: false,
    innerHTML: '',
    classList: { toggle() {} },
    querySelectorAll() { return []; },
  });
  return {
    serverStatus: node(),
    messageBanner: node(),
    instructionInput: node(),
    actorView: node(),
    trackView: node(),
    actorNavButton: node(),
    tracksNavButton: node(),
    createButton: node(),
    roleSelect: Object.assign(node(), { options: [{}], appendChild() {} }),
    actorsList: node(),
    actorRuntimeDetail: node(),
    actorTaskSummary: node(),
    actorTrackSummary: node(),
    tracksList: node(),
    trackDetail: node(),
    imConversation: node(),
    sendButton: node(),
    interruptButton: node(),
    stopButton: node(),
    deleteButton: node(),
    clearButton: node(),
    resumeButton: node(),
    actionAvailabilityStatus: node(),
    openTuiButton: node(),
    openTuiStatus: node(),
    openTuiCommand: node(),
    openTuiFallback: node(),
    copyTuiCommandButton: node(),
  };
}
```

Add this async test after the selected-event-message helper test:

```js
test('polling connection-wide events acks off-selected actor message without rendering it', async () => {
  const originalFetch = global.fetch;
  const calls = [];
  global.fetch = async function (url, options) {
    calls.push({ url, method: options && options.method ? options.method : 'GET' });
    if (url === '/api/im/events?wait_ms=15000') {
      return {
        ok: true,
        json: async function () {
          return {
            ok: true,
            events: [{ event_id: 'imev-dev', message_id: 'msg-dev' }],
          };
        },
      };
    }
    if (url === '/api/im/messages/msg-dev') {
      return {
        ok: true,
        json: async function () {
          return {
            ok: true,
            message: {
              id: 'msg-dev',
              from_identity_id: 'act-dev-other',
              to_identity_id: 'ext-web',
              content: 'dev pong',
              reply_to: null,
            },
          };
        },
      };
    }
    if (url === '/api/im/events/ack') {
      return {
        ok: true,
        json: async function () {
          return { ok: true };
        },
      };
    }
    throw new Error('unexpected fetch ' + url);
  };

  try {
    const state = app.createState();
    state.imSessionReady = true;
    state.selectedActorId = 'act-market-selected';
    state.imConversationIdentityId = 'act-market-selected';
    state.actors = [
      {
        actor_id: 'act-market-selected',
        role: 'market',
        runtime: { status: 'active', app_server_health: 'healthy', thread: { status: 'idle' } },
      },
      {
        actor_id: 'act-dev-other',
        role: 'dev',
        runtime: { status: 'active', app_server_health: 'healthy', thread: { status: 'idle' } },
      },
    ];
    state.actorConsole = {
      actor: { actor_id: 'act-market-selected', role: 'market' },
      runtime: { status: 'active', app_server_health: 'healthy', thread: { status: 'idle' } },
      task_sys: { active_tasks: [] },
      tracks: { items: [] },
      im: { target: { identity_id: 'act-market-selected', role_id: 'market' } },
    };

    await app.pollImEventsOnce(state, createRenderElements());

    assert.deepEqual(calls, [
      { url: '/api/im/events?wait_ms=15000', method: 'GET' },
      { url: '/api/im/messages/msg-dev', method: 'GET' },
      { url: '/api/im/events/ack', method: 'POST' },
    ]);
    assert.equal(state.imConversationIdentityId, 'act-market-selected');
    assert.deepEqual(state.imConversation, []);
  } finally {
    global.fetch = originalFetch;
  }
});
```

- [ ] **Step 3: Run the focused Node test and verify it fails**

Run:

```bash
node --test tests/web_management_ui_state.test.js
```

Expected: failure because `recordSelectedActorEventMessage` and `pollImEventsOnce` are not exported, and the current polling implementation records off-selected known actor messages.

- [ ] **Step 4: Add selected-actor event recording helper**

Replace the known-or-selected helper with:

```js
function recordSelectedActorEventMessage(state, message, selectedIdentityId) {
  if (!messageTouchesActor(message, selectedIdentityId)) {
    return false;
  }
  if (state.imConversationIdentityId !== selectedIdentityId) {
    clearImConversation(state, selectedIdentityId);
  }
  return recordImProjectedMessage(state, message);
}
```

Delete the old `messageTouchesKnownOrSelectedActor()` helper entirely.

- [ ] **Step 5: Use selected-only recording in `pollImEventsOnce()`**

Replace:

```js
if (message && messageTouchesKnownOrSelectedActor(state, message)) {
  recordImProjectedMessage(state, message);
  selectedActorMessageProcessed = selectedActorMessageProcessed || messageTouchesActor(message, selectedIdentityId);
}
```

With:

```js
if (message && recordSelectedActorEventMessage(state, message, selectedIdentityId)) {
  selectedActorMessageProcessed = true;
}
```

Keep the explicit ack after the fetch for every fetched event:

```js
await fetchJson('/api/im/events/ack', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify(buildImAckPayload(event.event_id)),
});
```

Export the helper:

```js
recordSelectedActorEventMessage,
```

Export `pollImEventsOnce` for the focused state test:

```js
pollImEventsOnce,
```

- [ ] **Step 6: Run the focused Node test and verify it passes**

Run:

```bash
node --test tests/web_management_ui_state.test.js
```

Expected: all tests in the file pass.

## Task 5: Add Frontend Residue Gates

**Files:**
- Modify: `tests/web_management_ui_contract.test.js`

- [ ] **Step 1: Add residue exclusions**

In `production javascript keeps the real api surface`, add these exclusions near the existing `/api/web` and cursor exclusions. Use split-string literals for retired names so residue scans over test source do not match the retired strings themselves:

```js
assertExcludes(appJs, '/api/web/' + 'im');
assertExcludes(appJs, 'buildWeb' + 'ImConversationUrl');
assertExcludes(appJs, 'ensureWeb' + 'ImSession');
assertExcludes(appJs, 'apply' + 'ImEventsPayload');
assertExcludes(appJs, 'messageTouches' + 'KnownOrSelectedActor');
```

- [ ] **Step 2: Confirm the unified route requirements remain**

Keep these existing required strings:

```js
assertIncludes(appJs, '/api/im/session');
assertIncludes(appJs, '/api/im/messages');
assertIncludes(appJs, '/api/im/events');
assertIncludes(appJs, '/api/im/events/ack');
assertIncludes(appJs, '/api/im/conversations/direct');
```

- [ ] **Step 3: Run the focused Node contract test**

Run:

```bash
node --test tests/web_management_ui_contract.test.js
```

Expected: pass after Tasks 1-4.

## Task 6: Verify Backend Boundary Was Not Reintroduced

**Files:**
- Do not modify production files in this task.

- [ ] **Step 1: Run Web Management and IM router focused tests**

Run:

```bash
python3 -m unittest tests.test_web_management.WebManagementStableImIdentityTests tests.test_im_http_router.ImHttpRouterTests
```

Expected: pass. These tests prove unified `/api/im/*` browser and external contracts still work and retired `/api/web/im/*` routes are not live.

- [ ] **Step 2: Run broader Web Management/router regression tests**

Run:

```bash
python3 -m unittest tests.test_web_management tests.test_im_http_router
```

Expected: pass. ResourceWarning output from local test sockets may appear; failures are not acceptable.

- [ ] **Step 3: Run residue scans**

Run:

```bash
rg -n "/api/web/im|_handle_web_im|_web_im_send_message|_web_im_events|_web_im_direct_conversation" tools/launcher tests docs/arch -S
```

Expected:

```text
no matches
```

Run:

```bash
rg -n "messageTouchesKnownOrSelectedActor|applyImEventsPayload|buildWebImConversationUrl|ensureWebImSession" tools/launcher/assets/web-management tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js -S
```

Expected:

```text
no matches
```

## Task 7: Live Smoke the Original Failure

**Files:**
- Do not modify production files in this task.

- [ ] **Step 1: Start or reuse the local Web Management server**

Check whether the server is already running:

```bash
lsof -nP -iTCP:8765 -sTCP:LISTEN
```

If nothing is listening, start it:

```bash
./buddyswitch-codex web --host 127.0.0.1 --port 8765
```

- [ ] **Step 2: Verify selected actor with no WebUI direct conversation renders empty history**

Discover current actors:

```bash
curl -sS http://127.0.0.1:8765/api/actors | jq -r '.actors[].actor_id'
```

For each actor id, check whether its WebUI identity direct conversation exists:

```bash
curl -sS -i 'http://127.0.0.1:8765/api/im/conversations/direct?identity_id=<actor-id>&limit=50'
```

Use one actor whose direct conversation request returns `200` and one actor whose direct conversation request returns `404 E_IM_NOT_FOUND`. The original reproduction used:

```text
empty-history actor: act-market-1e9c7bec4ab8
history actor: act-market-cdf9ce181c79
```

Expected for `act-market-1e9c7bec4ab8`:

- selected actor row is `act-market-1e9c7bec4ab8`;
- `#im-conversation .im-row` count is `0`;
- `#message-banner` is not `direct conversation not found`.

- [ ] **Step 3: Verify no stale history after switching actors**

Click `act-market-cdf9ce181c79`, wait for its history to render, then click `act-market-1e9c7bec4ab8`.

Expected after returning to `act-market-1e9c7bec4ab8`:

- selected actor row is `act-market-1e9c7bec4ab8`;
- `#im-conversation .im-row` count is `0`;
- no message content from `act-market-cdf9ce181c79` remains visible.

- [ ] **Step 4: Inspect network requests**

Expected network sequence:

```text
GET /api/im/conversations/direct?identity_id=act-market-cdf9ce181c79&limit=50 -> 200
GET /api/im/conversations/direct?identity_id=act-market-1e9c7bec4ab8&limit=50 -> 404
```

The 404 is acceptable backend behavior. The UI must still render empty selected history.

## Final Verification Command Set

Run all commands before declaring the fix complete:

```bash
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Expected:

```text
2 test files passed; 0 failed
```

```bash
python3 -m unittest tests.test_web_management tests.test_im_http_router
```

Expected:

```text
OK
```

```bash
rg -n "/api/web/im|_handle_web_im|_web_im_send_message|_web_im_events|_web_im_direct_conversation" tools/launcher tests docs/arch -S
```

Expected:

```text
no matches
```

```bash
rg -n "messageTouchesKnownOrSelectedActor|applyImEventsPayload|buildWebImConversationUrl|ensureWebImSession" tools/launcher/assets/web-management tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js -S
```

Expected:

```text
no matches
```

## Acceptance Criteria

- Missing direct conversation for the selected WebUI identity renders as empty history, not an error banner.
- Switching actors cannot leave previous actor messages visible.
- Creating, deleting, or losing selection cannot leave previous actor messages visible.
- Connection-wide event polling never appends off-selected actor messages to the selected actor conversation.
- `/api/im/*` remains the only live IM HTTP route family.
- `ImHttpRouter` still maps `E_IM_NOT_FOUND` to 404.
- No retired Web BFF helper names or `/api/web/im/*` route strings remain in active frontend/backend code.
- Verification commands pass and the original live reproduction no longer reproduces.

## Remaining Risk

- The live iMessage channel may still create conversations under a different external identity than WebUI. That is expected under the current identity model and should not be solved by merging histories in this fix.
- If product intent changes to aggregate actor-visible history across multiple external identities, that is a separate product and domain design change, not a WebUI cache bug fix.
