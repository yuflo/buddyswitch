# WebUI Team Room Forward Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current actor-console WebUI with a Team Room interface where actors read as teammates, Tracks uses the D-style Track Studio read view, and the visible product surface has no stale Actor Console shell or mock collaboration residue.

**Architecture:** This is a frontend projection rewrite over existing Web-interface APIs. The browser keeps using `/api/actors`, `/api/roles`, `/api/actors/:actor_id/console`, `/api/tracks`, `/api/tracks/:track_id`, `/api/im/*`, and the existing instance lifecycle/TUI routes. Do not add backend routes, DTOs, persistence paths, env tools, runtime services, feature flags, compatibility views, or alternate legacy render paths.

**Tech Stack:** Plain static HTML/CSS/JavaScript in `tools/launcher/assets/web-management/`, Node-based WebUI state/contract tests, existing Python Web management API tests, and browser smoke through `./buddyswitch-codex web`.

---

## Task Goal Restatement

The task is to move the WebUI forward from a runtime control console to a small team coordination room.

Primary user loop:

```text
user opens Web Management
  -> primary navigation shows only Team room and Tracks
  -> Team room shows actors as teammates
  -> selecting a teammate opens a direct conversation in the center
  -> right-side teammate card shows runtime, task, Track, TUI, and lifecycle facts from current DTOs
  -> sending a message uses existing /api/im/* and updates the selected direct thread
```

Tracks user loop:

```text
user clicks Tracks
  -> Tracks tab opens the D-style Track Studio read view
  -> current Track list/detail APIs provide outcome, now, materials, proofs, updates, and comment threads
  -> no Track comment composer, Track mutation UI, collaborator rail, or new Track write route appears
```

The redesign is complete only when both behavior and live surface agree with the new model. It is not enough to add Team Room labels while keeping the old Actor Console shell hidden nearby.

## Non-Negotiable Requirements

- Product implementation stays inside `tools/launcher/assets/web-management/`.
- Test changes are limited to focused WebUI tests unless an existing Web management static-asset assertion must be updated.
- No backend files are changed for this slice: `tools/launcher/web_management.py`, `tools/launcher/im_http_router.py`, `scripts/env/**`, launcher runtime code, and product object stores stay untouched.
- Do not edit `buddyswitch/objects/**` or `buddyswitch/local/private/**`.
- No new backend route, DTO field, persistence shape, env tool, runtime service, or compatibility adapter is introduced.
- Top-level navigation contains only `Team room` and `Tracks`.
- `Artifacts`, `Runtime health`, `Workstream OS`, `Capacity`, side-thread UI, fake unread, fake load, fake avatar, fake availability, Track write UI, and Track comment composer are cut or deferred.
- `Actor Console`, visible top-level `Actors`, and visible `Create Actor` are removed from the user-facing shell. API names such as `/api/actors` remain valid current implementation details.
- Use existing data only. If the current DTO does not provide a fact, the UI omits it or renders a neutral absence state.

## Bitter Principles Applied

From `docs/bitter`:

- Residue cleanup requires two proofs: behavior tests for what the system does and scoped scans for what live surfaces teach.
- A narrow change is wrong if it lands at the wrong boundary. Missing UI projection data is not a reason to add a backend special case.
- Built-in products own semantics below their interface projections. WebUI must project Track, Task Sys, IM, runtime, and actor identity facts without becoming a new product source of truth.
- End-to-end slices keep the user-visible loop alive. Component-level render tests do not replace a browser-visible Team room and Tracks loop.
- Tests that start services need lifecycle discipline. Use focused Node tests and narrow Python tests first; run browser smoke with explicit process cleanup.
- Do not fix stale contracts with prompt/doc bulk. The durable constraints must land in tests and scoped residue scans.

## Current Code Audit

Current production WebUI files:

- `tools/launcher/assets/web-management/index.html`
- `tools/launcher/assets/web-management/app.js`
- `tools/launcher/assets/web-management/styles.css`

Current stale UI findings:

- `index.html` still renders `Actors`, `Create Actor`, and `Actor Console`.
- `app.js` defaults `selectedSection` to `actors` and `sectionCopy('actors')` returns `Actor Console`.
- `tests/web_management_ui_contract.test.js` currently asserts `Actor Console`, `Actors`, and `Track workspace` as positive surface copy.
- `tests/web_management_ui_state.test.js` currently names the default section as actor console and asserts old section copy.
- The direct IM path already uses `/api/im/session`, `/api/im/messages`, `/api/im/events`, `/api/im/messages/:id`, and `/api/im/conversations/direct`.
- Track detail rendering already consumes `materials`, `proofs`, `updates`, `comment_threads`, and `comment_summary` from current read APIs.
- Backend `POST /api/instances/:actor/side` routes still exist, but current frontend assets do not call them. This slice must keep side-thread UI absent without turning the plan into a backend route removal task.

Valid current API surface for this redesign:

```text
GET /api/health
GET /api/roles
GET /api/actors
GET /api/actors/:actor_id/console
GET /api/tracks
GET /api/tracks/:track_id
GET /api/im/session
POST /api/im/messages
GET /api/im/events
POST /api/im/events/ack
GET /api/im/conversations/direct
GET /api/im/messages/:message_id
POST /api/instances
POST /api/instances/:actor_id/interrupt
POST /api/instances/:actor_id/stop
POST /api/instances/:actor_id/resume
POST /api/instances/:actor_id/clear
POST /api/instances/:actor_id/open-tui
DELETE /api/instances/:actor_id
```

Forbidden new or revived WebUI API calls:

```text
/api/web/im/*
/api/actors/:actor_id/input
/api/actors/:actor_id/messages
/api/actors/:actor_id/tasks
/api/actors/:actor_id/tracks
/api/instances/:actor_id/side
/api/instances/:actor_id/side/close
/api/tracks/:track_id/comments
env.tool
env.repos
```

## File Map

Modify:

- `tools/launcher/assets/web-management/index.html` - replace the shell structure and visible copy.
- `tools/launcher/assets/web-management/app.js` - replace visible section copy, teammate roster projection, latest-selection behavior, and focused render wiring.
- `tools/launcher/assets/web-management/styles.css` - replace actor-console layout styling with Team Room and Track Studio layout styling.
- `tests/web_management_ui_contract.test.js` - turn new copy and residue boundaries into live-surface gates.
- `tests/web_management_ui_state.test.js` - cover Team Room section copy, teammate projection, latest actor selection, direct thread behavior, and Tracks read-only rendering.
- `tests/test_web_management.py` - update the static asset copy assertions after frontend copy changes; do not change API behavior tests.

Do not modify:

- `tools/launcher/web_management.py`
- `tools/launcher/im_http_router.py`
- `tools/launcher/web_im_identity.py`
- `tools/launcher/external_im_session.py`
- `scripts/env/**`
- `buddyswitch/objects/**`
- `buddyswitch/local/private/**`

## Task 1: Lock The New Shell Contract First

**Files:**
- Modify: `tests/web_management_ui_contract.test.js`
- Modify only if static assertions fail after frontend change: `tests/test_web_management.py`

- [ ] **Step 1: Replace old positive copy assertions**

In `tests/web_management_ui_contract.test.js`, replace the current actor-centered copy test with a Team Room copy contract:

```js
test('production assets present Team room and Tracks as the only primary tabs', () => {
  assertIncludes(indexHtml, '>Team room<');
  assertIncludes(indexHtml, '>Tracks<');
  assertExcludes(indexHtml, 'Actor Console');
  assertExcludes(indexHtml, '>Actors<');
  assertExcludes(indexHtml, 'Create Actor');
  assertExcludes(indexHtml, 'Runtime health');
  assertExcludes(indexHtml, '>Artifacts<');
  assertExcludes(indexHtml, 'Workstream OS');
  assertExcludes(indexHtml, 'Capacity');
});
```

- [ ] **Step 2: Add primary-navigation count guard**

Add a scoped guard that fails if the primary nav grows beyond the two approved tabs:

```js
test('primary navigation has exactly two visible destinations', () => {
  const primaryNav = indexHtml.match(/<nav class="sidebar-nav"[\s\S]*?<\/nav>/);
  assert.ok(primaryNav, 'Expected sidebar primary nav');
  const buttonLabels = Array.from(primaryNav[0].matchAll(/<button[\s\S]*?>([\s\S]*?)<\/button>/g))
    .map((match) => match[1].replace(/<[^>]*>/g, '').trim().replace(/\s+/g, ' '));
  assert.deepEqual(buttonLabels, ['Team room', 'Tracks']);
});
```

- [ ] **Step 3: Add route residue guard**

Keep current API exclusions and add the side-thread UI route exclusions:

```js
[
  "/api/instances/' + encodeURIComponent(state.selectedActorId) + '/side'",
  "/api/instances/' + encodeURIComponent(state.selectedActorId) + '/side/close'",
  "/api/tracks/' + encodeURIComponent(state.selectedTrackId) + '/comments'",
  '/api/web/' + 'im',
].forEach((forbidden) => {
  assertExcludes(appJs, forbidden);
});
```

- [ ] **Step 4: Run the focused contract test and confirm red**

Run:

```bash
node tests/web_management_ui_contract.test.js
```

Expected before implementation: fails on missing `Team room` and stale `Actor Console` / `Actors` / `Create Actor`.

## Task 2: Replace The Static Shell In Place

**Files:**
- Modify: `tools/launcher/assets/web-management/index.html`
- Modify: `tools/launcher/assets/web-management/styles.css`
- Modify: `tests/web_management_ui_contract.test.js`

- [ ] **Step 1: Replace primary nav labels without changing ids**

Keep stable element ids to reduce test churn, but make the visible destination Team Room:

```html
<button id="actor-nav-button" class="nav-item is-active" type="button">
  <span class="nav-glyph" aria-hidden="true"></span>
  Team room
</button>
<button id="tracks-nav-button" class="nav-item" type="button">
  <span class="nav-glyph track-glyph" aria-hidden="true"></span>
  Tracks
</button>
```

- [ ] **Step 2: Remove the always-visible Create Actor block**

Delete the current sidebar `create-section` from the primary rail. If actor creation remains in the UI, render it later as a compact secondary control labelled `Start teammate`; do not keep visible `Create Actor`.

- [ ] **Step 3: Replace actor-console grid names with Team Room structure**

Use the existing ids so app code can migrate incrementally, but replace visible headings:

```html
<section id="actor-view" class="view-section team-room-view">
  <div class="team-room-grid">
    <section class="workspace-panel teammate-roster-panel" aria-labelledby="teammates-heading">
      <div class="panel-heading">
        <div>
          <h2 id="teammates-heading">Teammates</h2>
          <p class="panel-subtitle">People currently available in this local runtime</p>
        </div>
      </div>
      <div id="actors-list" class="actor-list teammate-list" aria-live="polite"></div>
    </section>

    <section class="workspace-panel conversation-column" aria-labelledby="conversation-heading">
      <div class="panel-heading">
        <div>
          <h2 id="conversation-heading">Direct thread</h2>
          <p class="panel-subtitle">Selected teammate conversation</p>
        </div>
      </div>
      <div id="im-conversation" class="im-conversation" aria-live="polite"></div>
      <label class="field textarea-field">
        <span>Message</span>
        <textarea id="instruction-input" rows="5" placeholder="Message the selected teammate."></textarea>
      </label>
      <div class="action-group">
        <button id="send-button" class="button primary" type="button">Send</button>
        <button id="interrupt-button" class="button secondary" type="button">Interrupt</button>
      </div>
    </section>

    <aside id="actor-console" class="workspace-panel teammate-card" aria-labelledby="teammate-card-heading">
      <div class="panel-heading compact">
        <div>
          <h2 id="teammate-card-heading">Selected teammate</h2>
          <p class="panel-subtitle">Runtime, task, Track, TUI, and lifecycle facts</p>
        </div>
      </div>
      <dl id="actor-runtime-detail" class="detail-grid"></dl>
      <div id="actor-task-summary" class="summary-stack"></div>
      <div id="actor-track-summary" class="summary-stack"></div>
      <div class="terminal-actions" aria-label="TUI actions">
        <div class="terminal-action-row">
          <button id="open-tui-button" class="button secondary accent-action" type="button">Open TUI</button>
          <span id="open-tui-status" class="inline-status"></span>
        </div>
        <div id="open-tui-fallback" class="command-fallback" hidden>
          <code id="open-tui-command" class="mono-value long-value"></code>
          <button id="copy-tui-command-button" class="button secondary compact-button" type="button">Copy command</button>
        </div>
      </div>
      <div class="action-group lifecycle-actions" aria-label="Lifecycle actions">
        <button id="clear-button" class="button secondary" type="button">Clear</button>
        <button id="stop-button" class="button secondary" type="button">Stop</button>
        <button id="resume-button" class="button secondary" type="button">Resume</button>
        <button id="delete-button" class="button danger" type="button">Delete</button>
      </div>
      <p id="action-availability-status" class="inline-status action-availability-status" aria-live="polite"></p>
      <p id="message-banner" class="message-banner" role="status" aria-live="polite"></p>
    </aside>
  </div>
</section>
```

- [ ] **Step 4: Replace old layout classes in CSS**

Replace `.actor-console-grid`, `.console-column`, and `.runtime-column` as user-facing layout concepts:

```css
.team-room-grid {
  display: grid;
  grid-template-columns: minmax(240px, 300px) minmax(0, 1fr) minmax(300px, 380px);
  gap: 16px;
  align-items: start;
}

.conversation-column,
.teammate-card,
.teammate-roster-panel {
  min-width: 0;
}
```

- [ ] **Step 5: Run contract test and iterate**

Run:

```bash
node tests/web_management_ui_contract.test.js
```

Expected after this task: shell copy and primary-nav tests pass. API surface tests may still pass because ids and routes are preserved.

## Task 3: Replace Section Copy And State Tests

**Files:**
- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tools/launcher/assets/web-management/app.js`

- [ ] **Step 1: Change the default-section test language**

Replace the old default-section test with:

```js
test('state defaults to Team room as the primary section', () => {
  const state = app.createState();

  assert.equal(state.selectedSection, 'actors');
  assert.equal(state.selectedActorId, '');
  assert.equal(state.selectedTrackId, '');
  assert.deepEqual(state.actors, []);
  assert.deepEqual(state.tracks, []);
  assert.equal(state.imConversationIdentityId, '');
});
```

The internal value may stay `actors` because it maps to the existing `/api/actors` contract. Visible copy must no longer say Actor Console.

- [ ] **Step 2: Replace section copy expectations**

Update the copy test:

```js
test('section copy follows Team room and Tracks destinations', () => {
  assert.deepEqual(app.sectionCopy('actors'), {
    title: 'Team room',
    summary: 'Message teammates, inspect current runtime facts, and keep coordination in one room.',
  });
  assert.deepEqual(app.sectionCopy('tracks'), {
    title: 'Tracks',
    summary: 'Review Track outcomes, current state, materials, proofs, updates, and comments.',
  });
});
```

- [ ] **Step 3: Implement section copy**

In `app.js`, replace `sectionCopy()`:

```js
function sectionCopy(section) {
  if (section === 'tracks') {
    return {
      title: 'Tracks',
      summary: 'Review Track outcomes, current state, materials, proofs, updates, and comments.',
    };
  }
  return {
    title: 'Team room',
    summary: 'Message teammates, inspect current runtime facts, and keep coordination in one room.',
  };
}
```

- [ ] **Step 4: Run the state test**

Run:

```bash
node tests/web_management_ui_state.test.js
```

Expected: section copy tests pass after implementation.

## Task 4: Render Actors As Teammates With Supported Data Only

**Files:**
- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tools/launcher/assets/web-management/app.js`
- Modify: `tests/web_management_ui_contract.test.js`

- [ ] **Step 1: Add a roster projection test**

Add a test that proves the roster uses current actor/role/runtime fields only:

```js
test('teammate roster uses role label, actor id, status, and health without fake people fields', () => {
  const state = app.createState();
  state.roles = [{ id: 'dev', label: 'Developer', scope: 'product' }];
  state.selectedActorId = 'act-dev-demo';
  state.actors = [
    {
      actor_id: 'act-dev-demo',
      role: 'dev',
      runtime: { status: 'active', app_server_health: 'healthy' },
    },
  ];

  const html = app.renderActorRowsHtml(state);

  assert.match(html, /Developer/);
  assert.match(html, /act-dev-demo/);
  assert.match(html, /active/);
  assert.match(html, /healthy/);
  assert.doesNotMatch(html, /avatar|unread|load|capacity|focus/i);
});
```

- [ ] **Step 2: Export the render helper for the test**

Add `renderActorRowsHtml` to the CommonJS/browser exports at the bottom of `app.js`.

- [ ] **Step 3: Implement role label resolution**

Add:

```js
function roleLabelById(state, roleId) {
  const role = state.roles.find(function (row) {
    return row.id === roleId;
  });
  return role && role.label ? role.label : roleId;
}
```

Use it in `renderActorRowsHtml()` so the row title reads as a teammate role and the actor id remains secondary or monospace.

- [ ] **Step 4: Add a residue guard for fake teammate facts**

In `tests/web_management_ui_contract.test.js`, keep these forbidden fragments:

```js
[
  'unread',
  'avatar',
  'current focus',
  'load percentage',
  'capacity bar',
  'availability score',
].forEach((forbidden) => {
  assertExcludes(combinedAssets.toLowerCase(), forbidden.toLowerCase());
});
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
```

Expected: roster projection test and residue guard pass.

## Task 5: Make Latest Actor Selection Win

**Files:**
- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tools/launcher/assets/web-management/app.js`

- [ ] **Step 1: Add a rapid-switch regression test**

Add a test that two selections can overlap and the stale response cannot overwrite the latest selection:

```js
test('rapid actor switching keeps the latest selected teammate visible', async () => {
  const originalFetch = globalThis.fetch;
  let resolveFirst;
  let resolveSecond;
  const first = new Promise((resolve) => { resolveFirst = resolve; });
  const second = new Promise((resolve) => { resolveSecond = resolve; });

  globalThis.fetch = function (url) {
    if (url === '/api/actors/act-first/console') {
      return first;
    }
    if (url === '/api/actors/act-second/console') {
      return second;
    }
    if (String(url).startsWith('/api/im/conversations/direct')) {
      return Promise.resolve({
        ok: false,
        json: async function () {
          return { ok: false, error: { code: 'E_IM_NOT_FOUND', message: 'not found' } };
        },
      });
    }
    throw new Error('unexpected fetch ' + url);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [
      { actor_id: 'act-first', role: 'dev', runtime: { status: 'active', app_server_health: 'healthy' } },
      { actor_id: 'act-second', role: 'pm', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];
    state.selectedActorId = 'act-old';

    const firstSelection = app.selectActor(state, elements, 'act-first');
    const secondSelection = app.selectActor(state, elements, 'act-second');

    resolveSecond({
      ok: true,
      json: async function () {
        return { ok: true, console: { actor: { actor_id: 'act-second', role: 'pm' }, runtime: { status: 'active', app_server_health: 'healthy' }, task_sys: { active_tasks: [] }, tracks: { items: [] }, im: { target: { identity_id: 'act-second', role_id: 'pm' } } } };
      },
    });
    await secondSelection;

    resolveFirst({
      ok: true,
      json: async function () {
        return { ok: true, console: { actor: { actor_id: 'act-first', role: 'dev' }, runtime: { status: 'active', app_server_health: 'healthy' }, task_sys: { active_tasks: [] }, tracks: { items: [] }, im: { target: { identity_id: 'act-first', role_id: 'dev' } } } };
      },
    });
    await firstSelection;

    assert.equal(state.selectedActorId, 'act-second');
    assert.equal(state.actorConsole.actor.actor_id, 'act-second');
  } finally {
    globalThis.fetch = originalFetch;
  }
});
```

- [ ] **Step 2: Confirm the test fails on current code**

Run:

```bash
node tests/web_management_ui_state.test.js
```

Expected before implementation: the second selection is ignored or the stale first response overwrites the selected console.

- [ ] **Step 3: Replace the single pending guard with request ids**

In `createState()`, add:

```js
actorSelectionRequestId: 0,
trackSelectionRequestId: 0,
```

In `selectActor()`, allow a new selection while a previous fetch is pending:

```js
const requestId = state.actorSelectionRequestId + 1;
state.actorSelectionRequestId = requestId;
state.selectedActorId = actorId;
state.actorConsole = null;
state.actorSelectionPendingId = actorId;
```

After each awaited fetch, apply results only when:

```js
state.actorSelectionRequestId === requestId && state.selectedActorId === actorId
```

- [ ] **Step 4: Keep stale responses from rendering**

When a response is stale, return without clearing the latest pending marker or rendering old details:

```js
if (state.actorSelectionRequestId !== requestId || state.selectedActorId !== actorId) {
  return;
}
```

- [ ] **Step 5: Run the focused state test**

Run:

```bash
node tests/web_management_ui_state.test.js
```

Expected: rapid-switch test passes and existing IM/event tests still pass.

## Task 6: Move Direct Conversation To The Center And Keep Actions In The Teammate Card

**Files:**
- Modify: `tools/launcher/assets/web-management/index.html`
- Modify: `tools/launcher/assets/web-management/app.js`
- Modify: `tools/launcher/assets/web-management/styles.css`
- Modify: `tests/web_management_ui_contract.test.js`

- [ ] **Step 1: Keep the direct IM ids, move their DOM position**

Move `im-conversation`, `instruction-input`, `send-button`, and `interrupt-button` into the center conversation column. Keep lifecycle buttons, Open TUI, Copy command, and runtime summaries in the right teammate card.

- [ ] **Step 2: Keep send behavior on `/api/im/*` only**

Confirm `sendImDraft()` still posts:

```js
await fetchJson('/api/im/messages', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    target_identity_id: target.identity_id,
    content: content,
    reply_to: null,
  }),
});
```

- [ ] **Step 3: Update contract labels**

Ensure the visible input copy is:

```html
<span>Message</span>
<textarea id="instruction-input" rows="5" placeholder="Message the selected teammate."></textarea>
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
node tests/web_management_ui_contract.test.js
node tests/web_management_ui_state.test.js
```

Expected: existing send/pending/direct-history tests pass and no old `/input` or `/api/web/im` route appears.

## Task 7: Shape Tracks Into The D-Style Read-Only Track Studio

**Files:**
- Modify: `tools/launcher/assets/web-management/index.html`
- Modify: `tools/launcher/assets/web-management/app.js`
- Modify: `tools/launcher/assets/web-management/styles.css`
- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tests/web_management_ui_contract.test.js`

- [ ] **Step 1: Add a Track Studio render test**

Use the existing `renderTrackDetailHtml()` export:

```js
test('Track Studio renders read-only materials proofs updates and comment threads', () => {
  const html = app.renderTrackDetailHtml({
    id: 'track-alpha',
    title: 'Team Room redesign',
    outcome: 'Ship the Team room shell',
    state: 'active',
    now: { next: 'Render Track Studio', blocker: null },
    updated_at: '2026-07-01T10:00:00Z',
    materials: [{ label: 'Brief', artifact_id: 'artifact-brief', template: 'markdown' }],
    proofs: [{ label: 'Proof', artifact_id: 'artifact-proof', template: 'markdown' }],
    updates: [{ id: 'upd-1', summary: 'Decision captured', kind: 'decision' }],
    comment_summary: { comment_count: 2, open_thread_count: 1 },
    comment_threads: [{ thread_id: 'thread-open', status: 'open', latest_comment_preview: 'Looks right', comment_count: 2 }],
  });

  assert.match(html, /Team Room redesign/);
  assert.match(html, /Brief/);
  assert.match(html, /Proof/);
  assert.match(html, /Decision captured/);
  assert.match(html, /Looks right/);
  assert.doesNotMatch(html, /textarea|composer|submit|resolve/i);
});
```

- [ ] **Step 2: Update static Track headings**

Use visible labels:

```html
<h2 id="tracks-heading">Tracks</h2>
<p class="panel-subtitle">Track pages for coordination and review</p>
<h2 id="track-detail-heading">Track Studio</h2>
<p class="panel-subtitle">Outcome, current state, materials, proofs, updates, and comments</p>
```

- [ ] **Step 3: Keep Track write routes absent**

Keep this contract guard:

```js
assertExcludes(appJs, "/api/tracks/' + encodeURIComponent(state.selectedTrackId) + '/comments'");
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
```

Expected: Track render test passes and no Track write route appears.

## Task 8: Final CSS Pass Without Adding Decorative Product Fiction

**Files:**
- Modify: `tools/launcher/assets/web-management/styles.css`
- Modify: `tests/web_management_ui_contract.test.js`

- [ ] **Step 1: Keep a utilitarian product-tool layout**

Use a restrained grid:

```css
.team-room-grid {
  grid-template-columns: minmax(240px, 300px) minmax(0, 1fr) minmax(300px, 380px);
}

.track-studio-grid {
  grid-template-columns: minmax(260px, 340px) minmax(0, 1fr);
}
```

- [ ] **Step 2: Preserve mobile behavior**

At the existing mobile breakpoint, stack the columns:

```css
@media (max-width: 860px) {
  .app-shell,
  .team-room-grid,
  .track-workspace-grid {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 3: Keep forbidden design residue absent**

Do not add decorative or unsupported classes such as:

```text
orb
blob
capacity-bar
avatar-stack
unread-badge
fake-metric
```

- [ ] **Step 4: Run CSS/live surface contract**

Run:

```bash
node tests/web_management_ui_contract.test.js
```

Expected: style markers for Team Room and Track Studio pass; mock/fake/capacity residue remains absent.

## Task 9: Boundary And Acceptance Verification

**Files:**
- No implementation files beyond the allowed WebUI set.

- [ ] **Step 1: Run focused JavaScript tests**

Run:

```bash
node tests/web_management_ui_contract.test.js
node tests/web_management_ui_state.test.js
```

Expected: every test line starts with `ok - ` and the process exit code is `0`.

- [ ] **Step 2: Run the narrow Python API/static tests**

Run:

```bash
python3 -m pytest -q tests/test_web_management.py::WebManagementProductApiTests tests/test_web_management.py::WebManagementHTTPActionTests::test_static_assets_are_served
```

Expected: selected tests pass. These prove the current read APIs and static asset serving still work without adding backend code.

- [ ] **Step 3: Run scoped residue scans**

Run:

```bash
rg -n "Actor Console|>Actors<|Create Actor|Runtime health|>Artifacts<|Workstream OS|sideThreads|side-thread UI|Refresh mock|Mock data|terminal selector|capacity bar|unread-badge|/api/web/im|/api/tracks/.*/comments" tools/launcher/assets/web-management tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Expected: no positive live-surface hits. Hits inside `assertExcludes`, `assert.doesNotMatch`, or test names that explicitly forbid residue are acceptable only when the test is a negative gate.

- [ ] **Step 4: Verify implementation boundary**

Run:

```bash
git diff --name-only | rg -v '^(tools/launcher/assets/web-management/(index\.html|styles\.css|app\.js)|tests/(web_management_ui_contract\.test\.js|web_management_ui_state\.test\.js|test_web_management\.py)|docs/memo/)'
```

Expected: no output.

- [ ] **Step 5: Run browser smoke with cleanup**

Run:

```bash
./buddyswitch-codex web --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/` and verify:

```text
1. Primary nav shows exactly Team room and Tracks.
2. Team room is the first screen.
3. Teammate roster uses role/actor/status/health facts only.
4. Selecting a teammate updates the center direct thread and right teammate card.
5. Sending a message posts through /api/im/messages and updates the direct thread.
6. Tracks opens the Track Studio read view.
7. Track detail shows current read-only materials, proofs, updates, and comment threads.
8. No Artifacts tab, Runtime health tab, Workstream view, Capacity view, side-thread UI, fake unread/load/avatar, or Track comment composer is visible.
9. Mobile viewport has no horizontal overflow and no overlapping text.
```

Stop the server after smoke. Check for residual processes only if the command did not return cleanly.

## Completion Gate

The implementation is accepted only when all of these are true:

- `Team room` and `Tracks` are the only top-level destinations.
- The old Actor Console shell is replaced, not hidden behind a second path.
- There is no dual render path, feature flag, compatibility view, or legacy tab.
- Backend files are unchanged.
- Product code changes are confined to `tools/launcher/assets/web-management/`.
- Tests encode the new visible copy and residue gates.
- Focused Node tests pass.
- Narrow Python API/static tests pass.
- Scoped residue scan has no positive live-surface hits.
- Browser smoke proves the Team room and Tracks loops on the served WebUI.

## Implementation Order

1. Task 1: write failing shell/residue contract tests.
2. Task 2: replace static shell structure.
3. Task 3: replace section copy and state tests.
4. Task 4: reshape roster as supported-data-only teammates.
5. Task 5: fix rapid actor switching before moving more interaction surface.
6. Task 6: move direct conversation center and consolidate teammate card actions.
7. Task 7: shape Tracks into read-only Track Studio.
8. Task 8: finish CSS and responsive behavior.
9. Task 9: run acceptance verification.

Do not proceed to a later task if the focused tests for the current task are red.
