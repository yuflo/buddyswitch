# Web Management Notion Redesign Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` before implementation, then use `superpowers:executing-plans` or `superpowers:subagent-driven-development` to execute this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the existing BuddySwitch Web Management UI into a cleaner Notion-like local control console while preserving current behavior exactly.

**Architecture:** Replace the current flat card layout with a sidebar plus workspace layout in the existing static HTML/CSS/JS assets. Keep the current Web API, UMD-style `app.js`, exported action-state helpers, and no-build-chain deployment path. Use `tmp/buddyswitch-web-rebuild-notion/` only as visual reference; do not copy its mock state machine or feature set.

**Tech Stack:** Native HTML, CSS, browser JavaScript, Node built-in `assert`, Python `pytest`, existing `tools/launcher/web_management.py` static serving.

---

## Current State

Current production Web UI files:

- `tools/launcher/assets/web-management/index.html`
- `tools/launcher/assets/web-management/styles.css`
- `tools/launcher/assets/web-management/app.js`

Current relevant tests:

- `tests/web_management_ui_state.test.js`
- `tests/test_web_management.py`

Visual reference:

- `tmp/buddyswitch-web-rebuild-notion/index.html`
- `tmp/buddyswitch-web-rebuild-notion/styles.css`
- `tmp/buddyswitch-web-rebuild-notion/app.js`

The mock is not a code source. It contains out-of-scope behavior including status metrics, search/filter, activity feed, side thread UI, tabs, and Retry Initialize. These must not enter production UI in this first version.

## Design Read

Reading this as: local operational control panel for BuddySwitch maintainers, with a restrained Notion-like workspace language, leaning toward native HTML/CSS/JS with dense admin-console hierarchy.

Design dials:

- `DESIGN_VARIANCE: 3`
- `MOTION_INTENSITY: 1`
- `VISUAL_DENSITY: 8`

## Forward Strategy

Use a direct replacement, not a transition layer.

- No feature flag
- No old/new UI switch
- No compatibility wrapper
- No new frontend dependency
- No build tooling
- No backend route changes

The shortest validated path is to replace the static UI structure and styling, then adjust the existing render functions to populate the new structure with the same real data and same action rules.

## Files To Modify

- Modify: `tools/launcher/assets/web-management/index.html`
  - Replace flat sections with sidebar/workspace structure.
  - Preserve all required existing element ids used by `app.js`.
  - Do not add status strip, search, filters, tabs, activity, side controls, or initialize controls.

- Modify: `tools/launcher/assets/web-management/styles.css`
  - Replace current minimal styling with Notion-like tokens and layout.
  - Add responsive behavior for sidebar/workspace/detail layout.
  - Add selected, disabled, danger, focus, and long-value handling.

- Modify: `tools/launcher/assets/web-management/app.js`
  - Preserve API calls, state shape, action-state helpers, and exports.
  - Update render functions for the new DOM structure.
  - Escape dynamic values before writing through `innerHTML`.
  - Keep action endpoints and enablement semantics unchanged.

- Create: `tests/web_management_ui_contract.test.js`
  - Enforce required production ids.
  - Enforce forbidden first-version strings.
  - Enforce required real API paths.

- Keep: `tools/launcher/web_management.py`
  - No backend changes for this task.

- Keep: `tests/test_web_management.py`
  - No expected API behavior changes for this task.

## Implementation Tasks

### Task 1: Add Static UI Contract Test

**Files:**

- Create: `tests/web_management_ui_contract.test.js`

- [ ] **Step 1: Create the contract test file**

Create `tests/web_management_ui_contract.test.js` with this complete content:

```javascript
#!/usr/bin/env node
'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const assetDir = path.join(root, 'tools', 'launcher', 'assets', 'web-management');
const indexHtml = fs.readFileSync(path.join(assetDir, 'index.html'), 'utf8');
const appJs = fs.readFileSync(path.join(assetDir, 'app.js'), 'utf8');
const stylesCss = fs.readFileSync(path.join(assetDir, 'styles.css'), 'utf8');
const combinedAssets = [indexHtml, appJs, stylesCss].join('\n');

function test(name, fn) {
  try {
    fn();
    process.stdout.write(`ok - ${name}\n`);
  } catch (error) {
    process.stderr.write(`not ok - ${name}\n`);
    throw error;
  }
}

function assertIncludes(source, expected) {
  assert.ok(source.includes(expected), `Expected asset content to include: ${expected}`);
}

function assertExcludes(source, forbidden) {
  assert.equal(source.includes(forbidden), false, `Expected asset content to exclude: ${forbidden}`);
}

test('production html keeps all real control ids used by the web UI', () => {
  [
    'server-status',
    'refresh-button',
    'buddy-select',
    'create-button',
    'instances-body',
    'instance-detail',
    'instruction-input',
    'send-button',
    'interrupt-button',
    'stop-button',
    'clear-button',
    'resume-button',
    'delete-button',
    'message-banner',
  ].forEach((id) => {
    assertIncludes(indexHtml, `id="${id}"`);
  });
});

test('production javascript keeps the real api surface', () => {
  [
    '/api/health',
    '/api/buddies',
    '/api/instances',
    '/status',
    '/input',
    '/interrupt',
    '/stop',
    '/clear',
    '/resume',
  ].forEach((apiPath) => {
    assertIncludes(appJs, apiPath);
  });

  assertIncludes(appJs, "method: 'DELETE'");
});

test('first version does not reintroduce removed initialize ui or route', () => {
  [
    'Retry Initialize',
    'retry-init',
    'canInitialize',
    'initialize-button',
    '/initialize',
    'Initialize this BuddySwitch thread',
    'Reply exactly: ready',
  ].forEach((forbidden) => {
    assertExcludes(combinedAssets, forbidden);
  });
});

test('first version does not ship mock-only controls', () => {
  [
    'Refresh mock',
    'Mock data',
    'sideThreads',
    'side-draft',
    'metric-active',
    'metric-busy',
    'metric-attention',
    'metric-side',
    'status-strip',
    'search-input',
    'activity-list',
    'data-mode',
    'data-view',
    'Runtime logs',
    'Artifacts',
    'Threads',
  ].forEach((forbidden) => {
    assertExcludes(combinedAssets, forbidden);
  });
});
```

- [ ] **Step 2: Run the contract test before UI changes**

Run:

```bash
node tests/web_management_ui_contract.test.js
```

Expected:

- PASS on required ids and real API surface
- PASS on initialize exclusions
- PASS on mock-only exclusions for current production assets

- [ ] **Step 3: Commit the test**

Run:

```bash
git add tests/web_management_ui_contract.test.js
git commit -m "test: add web management ui contract"
```

### Task 2: Replace HTML With Notion-Like Functional Layout

**Files:**

- Modify: `tools/launcher/assets/web-management/index.html`
- Test: `tests/web_management_ui_contract.test.js`

- [ ] **Step 1: Replace the body structure**

Update `tools/launcher/assets/web-management/index.html` so the `<body>` contains this complete production structure:

```html
<body>
  <div class="app-shell">
    <aside class="sidebar" aria-label="BuddySwitch workspace">
      <div class="workspace-switcher">
        <div class="workspace-mark" aria-hidden="true">BS</div>
        <div>
          <div class="workspace-name">BuddySwitch</div>
          <div class="workspace-meta">Local runtime</div>
        </div>
      </div>

      <nav class="sidebar-nav" aria-label="Primary">
        <span class="nav-item is-active">
          <span class="nav-glyph" aria-hidden="true"></span>
          Control room
        </span>
      </nav>

      <section class="sidebar-section create-section" aria-labelledby="create-heading">
        <div class="sidebar-heading" id="create-heading">Create Instance</div>
        <label class="field compact-field">
          <span>Buddy</span>
          <select id="buddy-select"></select>
        </label>
        <button id="create-button" class="button primary full-width" type="button">Create</button>
      </section>
    </aside>

    <main class="workspace-page" data-api-instances="/api/instances">
      <header class="page-header">
        <div class="breadcrumb">BuddySwitch / Web management</div>
        <div class="title-row">
          <div>
            <h1>Instance control room</h1>
            <p class="page-summary">Create, inspect, steer, and recover local buddy instances from one workspace.</p>
          </div>
          <div class="header-actions">
            <span id="server-status" class="status-pill">Checking</span>
            <button id="refresh-button" class="button secondary" type="button">Refresh</button>
          </div>
        </div>
      </header>

      <section class="content-grid">
        <section class="block-panel instance-panel" aria-labelledby="instances-heading">
          <div class="panel-heading">
            <div>
              <h2 id="instances-heading">Instances</h2>
              <p class="panel-subtitle">Stored local buddy instances</p>
            </div>
          </div>
          <div class="table-wrap">
            <table class="instances-table">
              <thead>
                <tr>
                  <th>Instance</th>
                  <th>Buddy</th>
                  <th>Status</th>
                  <th>App Server</th>
                  <th>Thread</th>
                  <th>Browser</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody id="instances-body"></tbody>
            </table>
          </div>
        </section>

        <aside class="detail-column" aria-label="Selected instance controls">
          <section class="block-panel detail-panel" aria-labelledby="detail-heading">
            <div class="panel-heading compact">
              <div>
                <h2 id="detail-heading">Selected instance</h2>
                <p class="panel-subtitle">Current runtime and workspace details</p>
              </div>
            </div>
            <dl id="instance-detail" class="detail-grid"></dl>
          </section>

          <section class="block-panel action-panel" aria-labelledby="action-heading">
            <div class="panel-heading compact">
              <div>
                <h2 id="action-heading">Actions</h2>
                <p class="panel-subtitle">Main-thread control and lifecycle recovery</p>
              </div>
            </div>
            <div class="action-body">
              <label class="field textarea-field">
                <span>Instruction</span>
                <textarea id="instruction-input" rows="6" placeholder="Send the next instruction to the selected instance."></textarea>
              </label>
              <div class="action-group" aria-label="Main thread actions">
                <button id="send-button" class="button primary" type="button">Send</button>
                <button id="interrupt-button" class="button secondary" type="button">Interrupt</button>
              </div>
              <div class="action-group lifecycle-actions" aria-label="Lifecycle actions">
                <button id="clear-button" class="button secondary" type="button">Clear</button>
                <button id="stop-button" class="button secondary" type="button">Stop</button>
                <button id="resume-button" class="button secondary" type="button">Resume</button>
                <button id="delete-button" class="button danger" type="button">Delete</button>
              </div>
              <p id="message-banner" class="message-banner" role="status" aria-live="polite"></p>
            </div>
          </section>
        </aside>
      </section>
    </main>
  </div>
  <script src="/static/app.js"></script>
</body>
```

- [ ] **Step 2: Run the static contract test**

Run:

```bash
node tests/web_management_ui_contract.test.js
```

Expected:

- PASS

- [ ] **Step 3: Commit the HTML layout**

Run:

```bash
git add tools/launcher/assets/web-management/index.html tests/web_management_ui_contract.test.js
git commit -m "refactor: rebuild web management html layout"
```

### Task 3: Replace CSS With Restrained Notion-Like Styling

**Files:**

- Modify: `tools/launcher/assets/web-management/styles.css`
- Test: `tests/web_management_ui_contract.test.js`

- [ ] **Step 1: Replace the stylesheet**

Replace `tools/launcher/assets/web-management/styles.css` with a complete stylesheet that defines:

- root tokens for Notion-like color, radius, line, muted text, focus, and shadow
- `app-shell` sidebar/workspace grid
- sticky desktop sidebar
- workspace switcher
- single active nav item
- create controls in sidebar
- page header and header actions
- `content-grid` with main instances panel and right detail/actions column
- table wrapper with horizontal overflow contained inside the panel
- table row hover and selected state
- status badges for status and app server values
- detail grid with safe wrapping
- action groups
- danger button
- disabled button state
- focus-visible state
- responsive single-column behavior below `860px`

Use these constraints while writing the stylesheet:

- no status strip selectors
- no search/filter selectors
- no activity selectors
- no side-thread selectors
- no large hero typography
- no decorative gradient orbs
- no animations beyond small color/background/box-shadow transitions
- all text must fit or wrap safely

- [ ] **Step 2: Run CSS and contract checks**

Run:

```bash
node tests/web_management_ui_contract.test.js
```

Expected:

- PASS

Run:

```bash
rg -n 'status-strip|search-input|activity-list|sideThreads|side-draft|data-mode|data-view|metric-active|metric-busy|metric-attention|metric-side' tools/launcher/assets/web-management/styles.css
```

Expected:

- no matches

- [ ] **Step 3: Commit the stylesheet**

Run:

```bash
git add tools/launcher/assets/web-management/styles.css tests/web_management_ui_contract.test.js
git commit -m "style: apply web management control room design"
```

### Task 4: Update JavaScript Render Layer For New UI

**Files:**

- Modify: `tools/launcher/assets/web-management/app.js`
- Test: `tests/web_management_ui_state.test.js`
- Test: `tests/web_management_ui_contract.test.js`

- [ ] **Step 1: Add HTML escaping helper**

Add this helper near `formatValue`:

```javascript
function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
```

- [ ] **Step 2: Add compact display helpers**

Add helpers near `resolveHealthLabel`:

```javascript
function resolveThreadStatus(instance) {
  return instance && instance.thread && typeof instance.thread.status === 'string'
    ? instance.thread.status
    : '';
}

function resolveStatusTone(value) {
  if (value === 'active' || value === 'healthy' || value === 'idle') {
    return 'healthy';
  }
  if (value === 'in_progress' || value === 'active_thread' || value === 'active turn') {
    return 'busy';
  }
  if (value === 'inactive' || value === 'unhealthy' || value === 'stopped' || value === 'interrupted') {
    return 'danger';
  }
  return 'neutral';
}

function badge(value, tone) {
  const displayValue = formatValue(value);
  return '<span class="status-badge ' + escapeHtml(tone || resolveStatusTone(displayValue)) + '">' + escapeHtml(displayValue) + '</span>';
}
```

Use `active` as the runtime status string from the instance record. Do not invent a new `active_thread` data value; the helper only maps display values to CSS tones.

- [ ] **Step 3: Update `renderTable`**

Change `renderTable` so it:

- keeps using `state.instances`
- keeps selecting by `instance.instance_id`
- renders an empty-state row when no instances exist
- escapes all dynamic values
- uses `badge` for `status` and `app_server_health`
- keeps click-to-select behavior
- applies `is-selected`
- sets `aria-current="true"` on the selected row

The generated row cells should preserve these columns:

- Instance
- Buddy
- Status
- App Server
- Thread
- Browser
- Updated

- [ ] **Step 4: Update `renderDetail`**

Change `renderDetail` so it:

- keeps the same detail fields:
  - Instance
  - Buddy
  - Status
  - Health
  - Thread
  - Thread State
  - Browser Port
  - Updated
  - Workspace
- escapes all dynamic values
- uses `formatValue` for empty values
- wraps long workspace and thread values safely through CSS classes

- [ ] **Step 5: Keep `render` semantics unchanged**

Confirm `render` still:

- writes `API Ready` or `API Unavailable` into `server-status`
- writes `state.message` into `message-banner`
- syncs `instruction-input.value`
- populates buddy options once
- disables create through `computeCreateEnabled`
- disables instance actions through `computeInstanceActionState`

Do not add:

- status metric rendering
- search rendering
- filter rendering
- tab rendering
- activity rendering
- side thread rendering

- [ ] **Step 6: Run JavaScript tests**

Run:

```bash
node --check tools/launcher/assets/web-management/app.js
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
```

Expected:

- syntax check passes
- UI state tests pass
- UI contract tests pass

- [ ] **Step 7: Commit JavaScript render changes**

Run:

```bash
git add tools/launcher/assets/web-management/app.js tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js
git commit -m "refactor: render redesigned web management ui"
```

### Task 5: Verify Backend Contract Is Unchanged

**Files:**

- Verify: `tools/launcher/web_management.py`
- Verify: `tests/test_web_management.py`

- [ ] **Step 1: Run Web Management API tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_web_management.py -q
```

Expected:

- PASS

- [ ] **Step 2: Confirm initialize remains absent from production UI**

Run:

```bash
rg -n 'Retry Initialize|retry-init|canInitialize|initialize-button|/initialize|Initialize this BuddySwitch thread|Reply exactly: ready' tools/launcher/assets/web-management tools/launcher/web_management.py
```

Expected:

- no matches in `tools/launcher/assets/web-management`
- no Web initialize route in `tools/launcher/web_management.py`

- [ ] **Step 3: Confirm first-version exclusions remain absent**

Run:

```bash
rg -n 'Refresh mock|Mock data|sideThreads|side-draft|metric-active|metric-busy|metric-attention|metric-side|status-strip|search-input|activity-list|data-mode|data-view|Runtime logs|Artifacts|Threads' tools/launcher/assets/web-management
```

Expected:

- no matches

### Task 6: Browser Layout Verification

**Files:**

- Verify: `tools/launcher/assets/web-management/index.html`
- Verify: `tools/launcher/assets/web-management/styles.css`
- Verify: `tools/launcher/assets/web-management/app.js`

- [ ] **Step 1: Start local Web Management server**

Run:

```bash
python3 tools/launcher/web_management.py --host 127.0.0.1 --port 8765
```

Expected:

- server starts and serves `/`
- `/static/app.js` returns JavaScript
- `/static/styles.css` returns CSS

- [ ] **Step 2: Inspect desktop viewport**

Open:

```text
http://127.0.0.1:8765/
```

Use viewport:

```text
1440x980
```

Expected:

- sidebar is visible on the left
- create controls are in the sidebar
- page header contains title, summary, API status, and refresh
- instances table is the main content
- selected instance details and actions are in the right column
- selected table row is visually obvious
- disabled buttons look disabled
- delete button is danger-styled
- long ids and workspace paths do not overlap adjacent content
- no status strip, side tab, activity feed, search/filter, extra nav, or initialize UI appears

- [ ] **Step 3: Inspect mobile viewport**

Use viewport:

```text
390x844
```

Expected:

- layout becomes single-column
- sidebar is no longer sticky
- create controls remain above instances
- instances table scrolls within its panel if columns exceed viewport width
- detail and actions remain below instances
- buttons wrap without text overlap
- message banner remains below actions

- [ ] **Step 4: Save screenshots**

Save:

```text
tmp/web-management-notion-redesign-desktop.png
tmp/web-management-notion-redesign-mobile.png
```

- [ ] **Step 5: Stop local server**

Stop the server process started in Step 1.

### Task 7: Final Verification Batch

**Files:**

- Verify all modified files

- [ ] **Step 1: Run all focused automated checks**

Run:

```bash
node --check tools/launcher/assets/web-management/app.js
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_web_management.py -q
```

Expected:

- all commands pass

- [ ] **Step 2: Run first-version boundary scan**

Run:

```bash
rg -n 'Retry Initialize|retry-init|canInitialize|initialize-button|/initialize|Refresh mock|Mock data|sideThreads|side-draft|metric-active|metric-busy|metric-attention|metric-side|status-strip|search-input|activity-list|data-mode|data-view|Runtime logs|Artifacts|Threads' tools/launcher/assets/web-management
```

Expected:

- no matches

- [ ] **Step 3: Review changed files**

Run:

```bash
git diff --stat HEAD
git diff -- tools/launcher/assets/web-management/index.html tools/launcher/assets/web-management/styles.css tools/launcher/assets/web-management/app.js tests/web_management_ui_contract.test.js
git diff -- package.json package-lock.json pnpm-lock.yaml yarn.lock
```

Expected:

- only first-version Web UI redesign files changed
- no backend file changed
- no package file changed
- no mock-only behavior added

- [ ] **Step 4: Commit final verification state**

If Task 2 through Task 4 were not committed separately, commit all remaining changes:

```bash
git add tools/launcher/assets/web-management/index.html tools/launcher/assets/web-management/styles.css tools/launcher/assets/web-management/app.js tests/web_management_ui_contract.test.js
git commit -m "refactor: redesign web management control room"
```

## Completion Criteria

The task is complete only when:

- the Web UI visually reads as a restrained Notion-like local control console
- all current production controls remain present
- no status strip is added
- no side UI is added
- no activity feed is added
- no search/filter UI is added
- no initialize UI or route usage returns
- current API tests pass
- current action-state tests pass
- new static UI contract test passes
- desktop and mobile screenshots show no incoherent overlap
- the implementation stays inside the `clean-runtime-env` worktree

## Plan Self-Review

- Spec coverage: every functional requirement from `docs/spec/2026-05-28-web-management-notion-redesign-test-plan.md` maps to a test, a task, or browser verification step.
- Placeholder scan: no plan step relies on unspecified controls, omitted files, or future feature work.
- Type and name consistency: all required element ids match the current production `app.js` element map or the planned HTML.
- Scope check: the plan is limited to the current Web UI first-version redesign and does not change backend behavior.
- Forward check: the plan directly replaces the current UI assets instead of creating a feature flag, compatibility layer, or parallel UI path.
