# WebUI Final Visual Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the BuddySwitch WebUI visual layer from `docs/memo/2026-07-01-webui-final-visual-prototype.html`, preserving only currently supported WebUI API data and removing the old production shell.

**Architecture:** Replace the current app-shell/sidebar/page-header visual structure with prototype-source Team Room and Track Studio shells. Keep the existing `web_management.py` API surface and the existing client-side state/actions in `app.js`, but remap render output into the final prototype's visual components and support-matrix data rules.

**Tech Stack:** Static HTML, CSS, and vanilla JavaScript in `tools/launcher/assets/web-management/`; Node contract/state tests in `tests/web_management_ui_*.test.js`; Python static-serving/API tests in `tests/test_web_management.py`.

---

## Source Of Truth

- Visual target: `docs/memo/2026-07-01-webui-final-visual-prototype.html`
- Support matrix rule: use current WebUI APIs only; do not add backend fields, object mutations, runtime prose mirrors, or Track write endpoints.
- Allowed production files:
  - `tools/launcher/assets/web-management/index.html`
  - `tools/launcher/assets/web-management/styles.css`
  - `tools/launcher/assets/web-management/app.js`
- Allowed tests:
  - `tests/web_management_ui_contract.test.js`
  - `tests/web_management_ui_state.test.js`
  - `tests/test_web_management.py`
- Explicitly out of scope:
  - `tools/launcher/web_management.py`
  - `scripts/env/**`
  - `buddyswitch/objects/**`
  - `buddyswitch/local/private/**`

## File Responsibilities

- `index.html`: Owns the static production DOM skeleton. It must no longer contain `.app-shell`, `.sidebar`, `.workspace-page`, `.page-header`, `.workspace-switcher`, or the old card-console layout. It must contain the final prototype root, primary tab buttons, Team Room shell, and Track Studio shell.
- `styles.css`: Owns all visual restoration. It must import the prototype's proportions, material colors, density, typography scale, list rows, message bubbles, composer, person cards, document page, and studio rail. It must remove old shell/card-grid styles.
- `app.js`: Owns API calls, state, selection, render functions, and actions. It must keep existing routes and action behavior but render actors, messages, runtime, tasks, tracks, and comments into final prototype classes without fake facts.
- `tests/web_management_ui_contract.test.js`: Owns static UI restoration gates and residue bans.
- `tests/web_management_ui_state.test.js`: Owns render behavior using real supported DTO fields.
- `tests/test_web_management.py`: Owns served static-asset smoke checks and API regression coverage.

## Data Rules From Support Matrix

- People roster: supported by `GET /api/actors` and `GET /api/roles`; render role label, actor id, derived initials, runtime status, and health.
- Room nav badges: no fake counts; use API status or neutral labels only.
- Direct message thread: supported by `/api/im/session`, `/api/im/messages`, `/api/im/events`, `/api/im/conversations/direct`; render direction, sender, delivery/wake status, reply target, and content.
- Selected teammate rail: supported by `GET /api/actors/{actor_id}/console`; render runtime, Task Sys counts/tasks, actor-owned Track summaries, IM target, and lifecycle/TUI actions.
- Do not implement load, capacity bars, last-proof elapsed time, fixed collaborators, unread badges, fake people, fake counts, or Track write controls.
- Track list/detail: supported by `GET /api/tracks` and `GET /api/tracks/{track_id}`; render title, id, state, outcome, `now.next`, `now.blocker`, materials, proofs, updates, and comment threads.
- Collaborators rail: not supported; replace with Track context and comment-thread rail.

## Task 1: Strengthen Static UI Restoration Tests

**Files:**
- Modify: `tests/web_management_ui_contract.test.js`
- Modify: `tests/test_web_management.py`

- [ ] **Step 1: Add failing static assertions for total old-shell removal**

Add assertions that production assets exclude old root shell markers:

```js
test('production html removes the old management shell completely', () => {
  [
    'class="app-shell"',
    'class="sidebar"',
    'class="workspace-page"',
    'class="page-header"',
    'class="workspace-switcher"',
    'class="workspace-mark"',
    'class="nav-item"',
    'class="breadcrumb"',
    'id="page-title"',
    'id="page-summary"',
  ].forEach((forbidden) => {
    assertExcludes(indexHtml, forbidden);
  });
});
```

- [ ] **Step 2: Add failing static assertions for final root and tab structure**

Assert final root and two primary tabs:

```js
test('production html uses the final prototype root and primary tabs', () => {
  assertIncludes(indexHtml, 'class="webui-root"');
  assertIncludes(indexHtml, 'class="tabs app-tabs"');
  assertIncludes(indexHtml, 'id="actor-nav-button"');
  assertIncludes(indexHtml, 'id="tracks-nav-button"');
  const primaryNav = indexHtml.match(/<nav class="tabs app-tabs"[\s\S]*?<\/nav>/);
  assert.ok(primaryNav, 'Expected final top-level app tabs');
  const labels = Array.from(primaryNav[0].matchAll(/<button[\s\S]*?>([\s\S]*?)<\/button>/g))
    .map((match) => match[1].replace(/<[^>]*>/g, '').trim().replace(/\s+/g, ' '));
  assert.deepEqual(labels, ['Team room', 'Tracks']);
});
```

- [ ] **Step 3: Add failing static assertions for support-matrix bans**

Update fake-fact exclusions so derived visual initials are allowed but fixed prototype facts are not:

```js
test('production assets do not ship unsupported prototype facts', () => {
  [
    'Dev Actor',
    'PM Actor',
    'Test Actor',
    'Market Actor',
    '72%',
    '68%',
    'last proof',
    'collaborators',
    'current focus',
    'load percentage',
    'capacity bar',
    'unread',
    '4 collaborators',
  ].forEach((forbidden) => {
    assertExcludes(combinedAssets.toLowerCase(), forbidden.toLowerCase());
  });
});
```

- [ ] **Step 4: Update Python static asset smoke**

In `tests/test_web_management.py::WebManagementHTTPActionTests::test_static_assets_are_served`, assert served HTML/CSS include final root markers and exclude old shell markers:

```python
self.assertIn("webui-root", html)
self.assertIn("Team room", html)
self.assertIn("Track Studio", html)
self.assertNotIn("app-shell", html)
self.assertNotIn("workspace-page", html)
self.assertNotIn("Actor Console", html)
self.assertIn(".webui-root", css)
self.assertIn(".proto-shell", css)
self.assertIn(".team-room", css)
self.assertIn(".track-studio", css)
self.assertNotIn(".app-shell", css)
self.assertNotIn(".actor-console-grid", css)
```

- [ ] **Step 5: Run red checks**

Run:

```bash
node tests/web_management_ui_contract.test.js
python3 -m pytest -q tests/test_web_management.py::WebManagementHTTPActionTests::test_static_assets_are_served
```

Expected: fail because current production HTML still has `.app-shell`, `.sidebar`, `.workspace-page`, `.page-header`, and old top-level shell.

## Task 2: Strengthen Render Behavior Tests For Supported Data Only

**Files:**
- Modify: `tests/web_management_ui_state.test.js`

- [ ] **Step 1: Update render element fixture**

Remove required `pageTitle` and `pageSummary` dependencies from `createRenderElements()`. Keep all real controls used by the new shell:

```js
return {
  serverStatus: node(),
  refreshButton: node(),
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
  trackStudioRail: node(),
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
```

- [ ] **Step 2: Add failing actor roster visual test**

Assert `renderActorRowsHtml` returns prototype row shape with derived initials and no fixed demo people:

```js
test('teammate roster renders prototype person rows from supported actor facts', () => {
  const state = app.createState();
  state.roles = [{ id: 'dev', label: 'Developer', scope: 'product' }];
  state.selectedActorId = 'act-dev-demo';
  state.actors = [
    { actor_id: 'act-dev-demo', role: 'dev', runtime: { status: 'active', app_server_health: 'healthy' } },
  ];

  const html = app.renderActorRowsHtml(state);

  assert.match(html, /person-row/);
  assert.match(html, /avatar/);
  assert.match(html, />DV</);
  assert.match(html, /Developer/);
  assert.match(html, /act-dev-demo/);
  assert.match(html, /active/);
  assert.match(html, /healthy/);
  assert.doesNotMatch(html, /Dev Actor|PM Actor|72%|capacity|current focus|last proof/i);
});
```

- [ ] **Step 3: Add failing direct-message visual test**

Assert IM messages render as final prototype message bubbles:

```js
test('direct thread renders final prototype message bubbles', () => {
  const state = app.createState();
  const elements = createRenderElements();
  state.imConversation = [
    { direction: 'reply', sender: 'dev/act-dev-demo', deliveryStatus: '', wakeStatus: '', replyTo: '', content: 'Ready.' },
    { direction: 'sent', sender: 'you', deliveryStatus: 'delivered', wakeStatus: 'submitted', replyTo: '', content: 'Continue.' },
  ];

  app.renderImConversation(state, elements);

  assert.match(elements.imConversation.innerHTML, /class="message reply/);
  assert.match(elements.imConversation.innerHTML, /class="message you/);
  assert.match(elements.imConversation.innerHTML, /reply · dev\/act-dev-demo/);
  assert.match(elements.imConversation.innerHTML, /sent · you · delivered \/ submitted/);
});
```

- [ ] **Step 4: Add failing Track document test**

Assert Track detail renders the final doc page sections and no Track write UI:

```js
test('Track Studio detail renders final document sections from supported Track fields', () => {
  const html = app.renderTrackDetailHtml({
    id: 'track-alpha',
    title: 'Actor console',
    outcome: 'Ship actor-centered Web management.',
    state: 'active',
    now: { next: 'Implement Web DTOs.', blocker: null },
    updated_at: '2026-06-26T10:00:00Z',
    materials: [{ label: 'Brief', artifact_id: 'artifact-material', template: 'markdown' }],
    proofs: [{ label: 'Plan', artifact_id: 'artifact-proof', template: 'markdown' }],
    updates: [{ id: 'upd-plan', summary: 'Phase two boundary confirmed.', kind: 'decision' }],
    comment_summary: { comment_count: 3, open_thread_count: 1, resolved_thread_count: 1 },
    comment_threads: [{ thread_id: 'thread-open', status: 'open', latest_comment_preview: 'Comments stay inside Track detail.', comment_count: 2 }],
  });

  assert.match(html, /doc-title/);
  assert.match(html, /Current state/);
  assert.match(html, /Materials and proofs/);
  assert.match(html, /Updates/);
  assert.match(html, /Comments/);
  assert.match(html, /Total comments/);
  assert.doesNotMatch(html, /textarea|composer|submit|resolve|collaborators/i);
});
```

- [ ] **Step 5: Run red check**

Run:

```bash
node tests/web_management_ui_state.test.js
```

Expected: fail because current render functions still emit old row/detail classes and `renderShell` expects removed page title elements.

## Task 3: Rebuild `index.html` From Final Prototype

**Files:**
- Modify: `tools/launcher/assets/web-management/index.html`

- [ ] **Step 1: Replace old root shell**

Replace the body content with:

```html
<main class="webui-root">
  <nav class="tabs app-tabs" aria-label="Primary">
    <button id="actor-nav-button" class="tab is-active" type="button">Team room</button>
    <button id="tracks-nav-button" class="tab" type="button">Tracks</button>
  </nav>
  ...
</main>
```

Do not keep `.app-shell`, `.sidebar`, `.workspace-page`, `.page-header`, `.workspace-switcher`, `.workspace-mark`, `.breadcrumb`, `#page-title`, or `#page-summary`.

- [ ] **Step 2: Build Team Room shell**

Use the final prototype classes:

```html
<section id="actor-view" class="screen view-section team-room-view">
  <article class="proto-shell team-room" aria-label="Team room">
    <aside class="room-sidebar" aria-label="Team room navigation">
      <div class="brand-line"><span class="brand-mark" aria-hidden="true">BS</span><span>BuddySwitch</span></div>
      <div class="nav-stack" aria-label="Section context">
        <div class="nav-link active"><span>Team room</span><span id="server-status" class="tag">Checking</span></div>
        <div class="nav-link"><span>Tracks</span><span class="tag">open threads</span></div>
      </div>
      <p class="label" id="teammates-heading">People</p>
      <div id="actors-list" class="actor-list list" aria-live="polite"></div>
      <div class="start-teammate-panel person-card">
        <p class="label" id="create-heading">Start teammate</p>
        <label class="field compact-field"><span>Role</span><select id="role-select"></select></label>
        <button id="create-button" class="mini-button primary full-width" type="button">Start</button>
      </div>
    </aside>
    ...
  </article>
</section>
```

- [ ] **Step 3: Build center direct thread**

Use:

```html
<section class="room-main" aria-labelledby="conversation-heading">
  <header class="room-header">
    <div>
      <h2 id="conversation-heading">Direct thread</h2>
      <p class="micro">Selected teammate conversation from the Web IM session and direct conversation APIs.</p>
    </div>
    <div class="pill-row">
      <button id="refresh-button" class="mini-button" type="button">Refresh</button>
    </div>
  </header>
  <div class="room-thread"><div id="im-conversation" class="im-conversation" aria-live="polite"></div></div>
  <div class="composer">...</div>
</section>
```

- [ ] **Step 4: Build selected teammate rail**

Keep the real action IDs in the right rail only:

```html
<aside id="actor-console" class="person-panel" aria-labelledby="teammate-card-heading">
  <section class="person-card selected-teammate-card">...</section>
  <section class="person-card">...</section>
  <section class="person-card">...</section>
  <section class="person-card">...</section>
  <section class="person-card actions-card">...</section>
</aside>
```

- [ ] **Step 5: Build Track Studio shell**

Use the final prototype Track layout:

```html
<section id="track-view" class="screen view-section track-view" hidden>
  <article class="proto-shell track-studio" aria-label="Track Studio">
    <aside class="studio-side" aria-labelledby="tracks-heading">...</aside>
    <section class="studio-doc" aria-labelledby="track-detail-heading">...</section>
    <aside class="studio-rail" aria-label="Track comments and context">...</aside>
  </article>
</section>
```

- [ ] **Step 6: Run static red/green candidate**

Run:

```bash
node tests/web_management_ui_contract.test.js
```

Expected after Task 3 alone: old-shell tests should move toward green, but render/CSS tests may still fail until Tasks 4 and 5.

## Task 4: Rebuild `styles.css` From Final Prototype

**Files:**
- Modify: `tools/launcher/assets/web-management/styles.css`

- [ ] **Step 1: Replace old stylesheet structure**

Replace old shell selectors with the final prototype's token set and layout classes:

```css
.webui-root { width: min(100%, 1520px); margin: 0 auto; padding: 14px; }
.tabs.app-tabs { display: flex; gap: 8px; margin-bottom: 14px; ... }
.proto-shell { display: grid; min-height: calc(100dvh - 82px); overflow: hidden; ... }
.team-room { grid-template-columns: 260px minmax(0, 1fr) 320px; background: #f7f6f1; }
.track-studio { grid-template-columns: 250px minmax(0, 1fr) 320px; background: #f6f5f2; }
```

- [ ] **Step 2: Port core prototype materials**

Ensure exact material markers exist:

```css
.room-sidebar { background: #ebe8dc; }
.room-main { background: #fbfbf8; }
.person-panel { background: #f0eee4; }
.studio-side { background: #ece9e0; }
.studio-rail { background: #f0ede5; }
```

- [ ] **Step 3: Port rows, messages, cards, document, and rail**

Keep these final visual classes:

```css
.person-row, .track-row, .task-row, .doc-block, .comment-thread { ... }
.avatar { ... }
.message { ... }
.message.you { ... }
.composer, .composer-box { ... }
.person-card, .studio-card { ... }
.doc-page, .doc-title, .doc-section, .doc-block { ... }
```

- [ ] **Step 4: Remove old selectors**

Search and remove old selectors:

```bash
rg -n "app-shell|workspace-page|page-header|workspace-switcher|workspace-mark|sidebar\\b|nav-item|actor-console-grid|track-workspace-grid|workspace-panel|console-column|runtime-column" tools/launcher/assets/web-management/styles.css
```

Expected: no output.

- [ ] **Step 5: Add responsive behavior**

Use:

```css
@media (max-width: 1180px) {
  .team-room, .track-studio { grid-template-columns: 230px minmax(0, 1fr); }
  .person-panel, .studio-rail { grid-column: 1 / -1; border-left: 0; border-top: 1px solid var(--line); }
}

@media (max-width: 820px) {
  .webui-root { padding: 10px; }
  .team-room, .track-studio { grid-template-columns: 1fr; }
  .room-header, .doc-block { grid-template-columns: 1fr; }
  .message { max-width: 100%; }
}
```

## Task 5: Remap `app.js` Render Output To Final Prototype Components

**Files:**
- Modify: `tools/launcher/assets/web-management/app.js`

- [ ] **Step 1: Make `renderShell` independent from removed page title nodes**

Remove mandatory `pageTitle` and `pageSummary` writes. Keep:

```js
elements.serverStatus.textContent = state.healthOk ? 'API ready' : 'API unavailable';
elements.actorView.hidden = state.selectedSection !== 'actors';
elements.trackView.hidden = state.selectedSection !== 'tracks';
elements.actorNavButton.classList.toggle('is-active', state.selectedSection === 'actors');
elements.tracksNavButton.classList.toggle('is-active', state.selectedSection === 'tracks');
```

- [ ] **Step 2: Add supported actor initial derivation**

Add:

```js
function actorInitials(roleId, actorId) {
  const role = typeof roleId === 'string' ? roleId.trim() : '';
  if (role) {
    return role.slice(0, 2).toUpperCase();
  }
  const id = typeof actorId === 'string' ? actorId.replace(/^act-/, '') : '';
  return id ? id.slice(0, 2).toUpperCase() : 'BS';
}
```

- [ ] **Step 3: Render actor rows as prototype person rows**

Use `.person-row`, `.avatar`, `.dot`, role label, actor id, status, and health. Do not include fixed sample people or fake facts.

- [ ] **Step 4: Render IM as prototype message bubbles**

Change `renderImConversation` rows to:

```html
<div class="message reply|you pending|failed">
  <span class="meta">sent · you · delivered / submitted</span>
  <p>Message content</p>
</div>
```

- [ ] **Step 5: Render runtime metrics from supported fields**

Change selected teammate card output to use supported values only:

```html
<div class="metric"><span class="micro">Status</span><strong>active</strong></div>
<div class="metric"><span class="micro">Health</span><strong>healthy</strong></div>
<div class="metric"><span class="micro">Task Sys</span><strong>1 active</strong></div>
<div class="metric"><span class="micro">Tracks</span><strong>1 owned</strong></div>
```

This may be implemented by changing `renderRuntimeDetailHtml` to return card content instead of a `dl`, while keeping the `actor-runtime-detail` id.

- [ ] **Step 6: Render Track detail as final document page**

Update `renderTrackDetailHtml` to emit `Current state`, `Materials and proofs`, `Updates`, and `Comments` sections with `doc-block`, `task-row`, and `summary-line`.

- [ ] **Step 7: Render Track rail as supported context and comment threads**

Keep `Context` and `Comment threads`; do not render collaborators or write controls.

- [ ] **Step 8: Export any new pure render helpers used by tests**

Update the module export block with `actorInitials` if tests call it directly.

## Task 6: Run Focused Red-Green Verification

**Files:**
- Verify only; no production edits unless fixing failed assertions.

- [ ] **Step 1: Run JS contract tests**

```bash
node tests/web_management_ui_contract.test.js
```

Expected: all tests pass after Tasks 3-5.

- [ ] **Step 2: Run JS state tests**

```bash
node tests/web_management_ui_state.test.js
```

Expected: all tests pass after render remapping.

- [ ] **Step 3: Run Python WebUI tests**

```bash
python3 -m pytest -q tests/test_web_management.py::WebManagementProductApiTests tests/test_web_management.py::WebManagementHTTPActionTests::test_static_assets_are_served
```

Expected: product API tests remain green; static assets prove final root is served.

## Task 7: Strict UI Restoration Acceptance

**Files:**
- Verify only; no backend changes.

- [ ] **Step 1: Run production residue scan**

```bash
rg -n "app-shell|workspace-page|page-header|workspace-switcher|workspace-mark|nav-item|Actor Console|Create Actor|Runtime health|Workstream OS|Capacity|sideThreads|Refresh mock|Mock data|terminal selector|capacity bar|unread-badge|/api/tracks/.*/comments|/api/web/im|track-workspace-grid|actor-console-grid" tools/launcher/assets/web-management
```

Expected: no output.

- [ ] **Step 2: Run support-matrix fake-fact scan**

```bash
rg -n "Dev Actor|PM Actor|Test Actor|Market Actor|72%|68%|last proof|4 collaborators|collaborators|current focus|load percentage|capacity bar|availability score" tools/launcher/assets/web-management
```

Expected: no output.

- [ ] **Step 3: Run browser smoke if WebUI server can start**

Start:

```bash
./buddyswitch-codex web --host 127.0.0.1 --port 8766
```

Open `http://127.0.0.1:8766/` and verify:

- Desktop Team Room has no horizontal overflow.
- Desktop Team Room computed grid is three columns close to `260px minmax(0, 1fr) 320px`.
- Desktop Track Studio computed grid is three columns close to `250px minmax(0, 1fr) 320px`.
- Mobile width around 390px has no horizontal overflow.
- Body text does not contain old shell labels or unsupported fake facts.
- Tracks view does not contain textarea, submit, resolve, or collaborator write UI.

Stop the server before final response.

## Task 8: Completion Audit

**Files:**
- Verify only.

- [ ] **Step 1: Check git boundary**

Run:

```bash
git status --short
```

Expected modified/created files are limited to WebUI assets, WebUI tests, and implementation/prototype docs. No `buddyswitch/objects/**`, `buddyswitch/local/private/**`, backend service, or env tool changes.

- [ ] **Step 2: Re-read final prototype requirements**

Confirm each explicit user requirement:

- implemented from `docs/memo/2026-07-01-webui-final-visual-prototype.html`
- follows support matrix conclusions
- current WebUI visually cleared and rebuilt
- APIs reused without backend spillover
- strict UI restoration acceptance run
- final response synchronizes result and remaining risk

- [ ] **Step 3: Final response**

Report:

- plan file path
- changed production files
- verification commands and outcomes
- any browser-smoke limitation if present
- remaining risk, if any

Do not commit unless the user explicitly asks for a commit.
