# WebUI Actor Model Config Payload Interaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a clean WebUI interaction for actor-scoped parent/side model config management using the existing actor model config Web API, with a payload-first editor, no duplicated schema in the frontend, no legacy dropdown form, and no dual-track compatibility path.

**Architecture:** `actor_model_config.py` remains the product core and schema owner. `web_management.py` already projects that core through actor-scoped API routes. The WebUI will be a consumer projection only: it reads `actorConsole.model_config`, edits a JSON payload, submits `PUT /api/actors/{actor_id}/model-config`, and reflects the server result back into the selected actor console state.

**Tech Stack:** Existing static WebUI assets under `tools/launcher/assets/web-management/`, existing browser-facing Web API in `tools/launcher/web_management.py`, Node-based UI tests in `tests/web_management_ui_contract.test.js` and `tests/web_management_ui_state.test.js`, Python consistency tests in `tests/test_repo_consistency.py`, focused Web API tests in `tests/test_web_management.py`.

---

## Task Goal Restatement

Implement the WebUI-side interaction for the actor model config capability that is already available at the API/CLI/runtime boundary:

```text
GET /api/actors/{actor_id}/model-config
PUT /api/actors/{actor_id}/model-config
actor console payload -> model_config
```

The UI must let a user configure the selected actor by editing a JSON payload directly. It must not rebuild the old dropdown form. It must not teach a frontend-owned schema. It must not read `model-config.json`. It must not create a second configuration path parallel to the backend API.

## Core Product Contract

The end-to-end contract sentence for this slice is:

```text
Selected actor Configure -> user edits JSON payload -> WebUI PUTs actor-scoped model-config API -> server returns canonical model_config -> selected actor console shows the saved payload summary without frontend schema ownership.
```

This contract must be proven by tests and live-browser verification before the work is accepted.

## Requirements

- The selected actor panel gets one compact `Model defaults` card.
- Default collapsed state shows:
  - title `Model defaults`;
  - status badge: `Saved`, `Unsaved`, or `Invalid`;
  - `Configure` or `Review` button;
  - two summary rows: `Parent` and `Side`.
- Expanded state shows:
  - one JSON textarea labelled `Payload · PUT /api/actors/{actor_id}/model-config`;
  - `Save` and `Revert` buttons;
  - status/error text only when there is something actionable.
- The frontend validates only that the payload is valid JSON and that the top-level value is a JSON object.
- The frontend does not list allowed efforts, required fields, schema versions, or section key rules.
- The backend remains the only schema authority. Server rejections are displayed as server errors.
- If the payload has recognizable `parent` or `side` objects with string `model` or `effort`, the summary shows those values.
- If the payload shape is unknown or future-shaped, the summary shows `Custom payload`.
- Save writes only through `PUT /api/actors/{actor_id}/model-config`.
- Revert returns the editor to the last server-confirmed payload.
- Actor selection discards unsaved local editor state for the previous actor and initializes from the newly selected actor console payload.
- No compatibility route, feature flag, old dropdown form, frontend schema constants, or direct file access may be added.

## Key Problems To Guard

1. **Schema drift in UI:** A visible schema or frontend effort enum will become stale and mislead users. The UI must avoid schema documentation and delegate validation to the API.
2. **Dual-track state:** A separate parent/side form state alongside payload state will create two sources of truth. The payload text and parsed payload are canonical; summary state is derived only.
3. **Wrong-layer ownership:** `app.js` must not understand `model-config.json`, disk format, schema version, or runtime application timing.
4. **Residue:** Old ids such as `parent-model`, `side-model`, `parent-effort`, and `side-effort` must not remain on live WebUI surfaces.
5. **Contract gap:** Unit tests for helper functions are not enough. At least one test must prove the save path reaches the actor-scoped API shape and applies the server-returned canonical payload.
6. **Unowned resource verification:** Avoid service-starting broad suites unless lifecycle ownership is explicit. Prefer Node UI tests and focused Python API tests first.

## Bitter Principles Applied

- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`: The WebUI must use runtime-visible API semantics and server feedback. It must not become a prompt-like schema catalog.
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`: Use focused non-daemon UI tests first; only run live browser/server checks with explicit local server ownership.
- `docs/bitter/2026-05-28-parallel-change-boundary-principles.md`: Keep the work inside the WebUI asset slice plus focused tests. Do not move unrelated assets or refactor the whole app.
- `docs/bitter/2026-06-02-residue-cleanup-principles.md`: Add live-surface residue scans for retired form ids and schema language.
- `docs/bitter/2026-06-02-wrong-boundary-narrowness-principles.md`: Do not add a narrow WebUI-specific schema parser that becomes a hidden registry.
- `docs/bitter/2026-06-25-built-in-product-interface-principles.md`: Product core is `actor_model_config.py`; WebUI is only an interface projection.
- `docs/bitter/2026-06-25-end-to-end-contract-slice-principles.md`: Keep the selected actor edit/save/render loop as the acceptance contract.
- `docs/bitter/2026-07-07-guarded-residue-boundary-principles.md`: Do not keep retired dropdown shape and blacklist it. Delete retired live shape from the WebUI.

## Current Code Review

### API/Core

- `tools/launcher/actor_model_config.py` already owns model config pathing, management read/replace, runtime resolve, schema validation, and CLI subcommands.
- `tools/launcher/web_management.py` already owns actor-scoped API projection:
  - `_parse_actor_model_config_path()`
  - `_read_actor_model_config()`
  - `_replace_actor_model_config()`
  - actor console `model_config` projection.
- The frontend must call these API routes; it must not duplicate their validation rules.

### WebUI Assets

- `tools/launcher/assets/web-management/index.html` currently has no model config card.
- `tools/launcher/assets/web-management/app.js` is a single-file WebUI module that already exports pure helpers for Node tests.
- `tools/launcher/assets/web-management/styles.css` owns the compact Team Room card styling.
- Existing WebUI tests are suitable for this slice:
  - `tests/web_management_ui_contract.test.js` for live asset structure and residue checks;
  - `tests/web_management_ui_state.test.js` for pure state/render behavior.

### Current Prototype Review

- The ignored prototype at `docs/spec/2026-07-08-webui-actor-model-config-interaction-prototype.html` has already been cleaned to payload-only canonical data.
- It has no visible schema, no dropdown controls, no fallback from actor parent/side fields, and no dual state named `savedConfig`/`draftConfig`.
- It is not production code and must not be copied wholesale without adapting to the real `app.js` state/render patterns.

## Module Boundaries

### `tools/launcher/assets/web-management/index.html`

Owns static DOM anchors only:

- Add a `Model defaults` card in the selected actor console.
- Add the stable ids used by `app.js`.
- Does not include schema text, effort options, or hardcoded example payloads.

### `tools/launcher/assets/web-management/app.js`

Owns browser interaction state:

- Build actor model config API URL.
- Normalize server `model_config` into pretty JSON editor text.
- Parse user JSON as a generic JSON object.
- Derive parent/side summary labels from the parsed payload when possible.
- Render collapsed and expanded states.
- Submit the parsed payload to the actor-scoped Web API.
- Apply server-returned `model_config` as the new canonical saved payload.

Does not own:

- `model-config.json` file path.
- `schema_version`.
- allowed effort lists.
- required section keys.
- runtime application timing.

### `tools/launcher/assets/web-management/styles.css`

Owns visual layout only:

- Compact card header.
- Summary rows.
- Collapsible payload editor.
- Invalid/saving status.

Does not own product semantics.

### Tests

Node tests own fast UI behavior proof. Python tests own API and residue proof. Live browser verification owns final visual/interaction proof.

---

### Task 1: Replace Deferred-WebUI Residue Test With Payload-Editor Boundary Tests

**Files:**

- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/web_management_ui_contract.test.js`
- Test: `python3 -m unittest tests.test_repo_consistency -k actor_model_config`
- Test: `node tests/web_management_ui_contract.test.js`

- [x] **Step 1: Change the old deferred-control consistency test into current live-surface residue checks**

Replace `test_actor_model_config_webui_controls_are_deferred_from_interface_slice` in `tests/test_repo_consistency.py` with two tests:

```python
def test_actor_model_config_webui_assets_do_not_duplicate_schema(self) -> None:
    hits = self._scan_targets(
        "allowed_efforts|VALID_EFFORTS|schema_version|minimal.*low.*medium.*high.*ultra|effort must be|must include parent and side",
        ["tools/launcher/assets/web-management"],
    )
    self.assertEqual(hits, [], msg="\n".join(hits))

def test_actor_model_config_webui_assets_do_not_keep_retired_form_controls(self) -> None:
    hits = self._scan_targets(
        "parent-model|side-model|parent-effort|side-effort|model-config\\.json|schema-strip",
        ["tools/launcher/assets/web-management"],
    )
    self.assertEqual(hits, [], msg="\n".join(hits))
```

- [x] **Step 2: Run the focused consistency tests and verify the new tests fail before implementation**

Run:

```bash
python3 -m unittest tests.test_repo_consistency -k actor_model_config
```

Expected before implementation:

```text
FAIL: test_actor_model_config_webui_assets_do_not_keep_retired_form_controls
```

The failure is expected once the WebUI placeholders or old forbidden strings are present during development. If both tests pass before adding any UI, continue; the contract tests in the next step must fail because required UI ids are missing.

- [x] **Step 3: Add production asset contract checks**

Append this test to `tests/web_management_ui_contract.test.js`:

```javascript
test('actor model config UI uses payload editor without schema or dropdown residue', () => {
  [
    'id="actor-model-config-card"',
    'id="actor-model-config-toggle"',
    'id="actor-model-config-status"',
    'id="actor-model-config-parent-summary"',
    'id="actor-model-config-side-summary"',
    'id="actor-model-config-panel"',
    'id="actor-model-config-payload"',
    'id="actor-model-config-save"',
    'id="actor-model-config-revert"',
  ].forEach((marker) => {
    assertIncludes(indexHtml, marker);
  });

  [
    'parent-model',
    'side-model',
    'parent-effort',
    'side-effort',
    'schema-strip',
    '<summary>Schema</summary>',
    'allowed_efforts',
    'VALID_EFFORTS',
    'model-config.json',
  ].forEach((forbidden) => {
    assertExcludes(combinedAssets, forbidden);
  });

  assertIncludes(appJs, "buildActorModelConfigUrl(actorId)");
  assertIncludes(appJs, "parseJsonObjectPayload(text)");
  assertIncludes(appJs, "summarizeActorModelPayload(payload)");
  assertIncludes(stylesCss, '.actor-model-config-card');
  assertIncludes(stylesCss, '.model-config-payload-editor');
});
```

- [x] **Step 4: Run the Node contract test and verify it fails before implementation**

Run:

```bash
node tests/web_management_ui_contract.test.js
```

Expected before implementation:

```text
not ok - actor model config UI uses payload editor without schema or dropdown residue
```

The failure proves the test is guarding the new UI contract.

---

### Task 2: Add Pure Payload Helpers And State Shape

**Files:**

- Modify: `tools/launcher/assets/web-management/app.js`
- Modify: `tests/web_management_ui_state.test.js`
- Test: `node tests/web_management_ui_state.test.js`

- [x] **Step 1: Add failing state tests for generic payload parsing and summaries**

Append these tests to `tests/web_management_ui_state.test.js`:

```javascript
test('actor model config payload parser accepts generic JSON objects only', () => {
  assert.deepEqual(app.parseJsonObjectPayload('{"future": {"effort": "warp"}}'), {
    ok: true,
    value: { future: { effort: 'warp' } },
  });

  assert.equal(app.parseJsonObjectPayload('[1,2,3]').ok, false);
  assert.match(app.parseJsonObjectPayload('[1,2,3]').error, /JSON object/);
  assert.equal(app.parseJsonObjectPayload('{bad json').ok, false);
  assert.match(app.parseJsonObjectPayload('{bad json').error, /Invalid JSON/);
});

test('actor model config summary is derived from payload without schema validation', () => {
  assert.deepEqual(app.summarizeActorModelPayload({
    parent: { model: 'gpt-5.4', effort: 'high' },
    side: { model: 'gpt-5.4-mini', effort: 'medium' },
  }), {
    parent: 'gpt-5.4 · high',
    side: 'gpt-5.4-mini · medium',
  });

  assert.deepEqual(app.summarizeActorModelPayload({
    model_overrides: {
      parent: { model: 'gpt-future', effort: 'warp' },
    },
  }), {
    parent: 'Custom payload',
    side: 'Custom payload',
  });
});

test('actor model config URL is actor scoped', () => {
  assert.equal(
    app.buildActorModelConfigUrl('act-pm-demo'),
    '/api/actors/act-pm-demo/model-config'
  );
  assert.equal(
    app.buildActorModelConfigUrl('act demo/one'),
    '/api/actors/act%20demo%2Fone/model-config'
  );
});
```

- [x] **Step 2: Run the state tests and verify they fail before helper implementation**

Run:

```bash
node tests/web_management_ui_state.test.js
```

Expected:

```text
TypeError: app.parseJsonObjectPayload is not a function
```

- [x] **Step 3: Add the pure helpers in `app.js` near the existing URL builder helpers**

Add:

```javascript
function buildActorModelConfigUrl(actorId) {
  return '/api/actors/' + encodeURIComponent(actorId) + '/model-config';
}

function parseJsonObjectPayload(text) {
  let payload;
  try {
    payload = JSON.parse(text);
  } catch (error) {
    return { ok: false, error: 'Invalid JSON: ' + error.message };
  }
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return { ok: false, error: 'Payload must be a JSON object.' };
  }
  return { ok: true, value: payload };
}

function stablePayloadText(payload) {
  return JSON.stringify(payload || {}, null, 2);
}

function summarizeActorModelSection(section) {
  if (!section || typeof section !== 'object' || Array.isArray(section)) {
    return 'Custom payload';
  }
  if (!Object.prototype.hasOwnProperty.call(section, 'model')
      && !Object.prototype.hasOwnProperty.call(section, 'effort')) {
    return 'Custom payload';
  }
  const model = typeof section.model === 'string' && section.model.trim()
    ? section.model.trim()
    : 'Codex default';
  const effort = typeof section.effort === 'string' && section.effort.trim()
    ? section.effort.trim()
    : 'default effort';
  return model + ' · ' + effort;
}

function summarizeActorModelPayload(payload) {
  return {
    parent: summarizeActorModelSection(payload && payload.parent),
    side: summarizeActorModelSection(payload && payload.side),
  };
}

function sameJsonObjectText(leftText, rightText) {
  const left = parseJsonObjectPayload(leftText);
  const right = parseJsonObjectPayload(rightText);
  return Boolean(left.ok && right.ok && JSON.stringify(left.value) === JSON.stringify(right.value));
}
```

- [x] **Step 4: Add actor model config fields to `createState()`**

Add these fields near the selected actor console state:

```javascript
actorModelConfigPanelOpen: false,
actorModelConfigSavedText: '',
actorModelConfigDraftText: '',
actorModelConfigError: '',
actorModelConfigSaving: false,
actorModelConfigStatus: '',
```

- [x] **Step 5: Export the helpers**

Add these names to the returned export object:

```javascript
buildActorModelConfigUrl,
parseJsonObjectPayload,
stablePayloadText,
summarizeActorModelPayload,
sameJsonObjectText,
```

- [x] **Step 6: Run the state tests and verify helper tests pass**

Run:

```bash
node tests/web_management_ui_state.test.js
```

Expected:

```text
ok - actor model config payload parser accepts generic JSON objects only
ok - actor model config summary is derived from payload without schema validation
ok - actor model config URL is actor scoped
```

---

### Task 3: Add Static Model Defaults Card

**Files:**

- Modify: `tools/launcher/assets/web-management/index.html`
- Modify: `tools/launcher/assets/web-management/styles.css`
- Test: `node tests/web_management_ui_contract.test.js`

- [x] **Step 1: Insert the model config card after the selected teammate card**

In `tools/launcher/assets/web-management/index.html`, inside `<aside id="actor-console" ...>`, place this section after `.selected-teammate-card` and before the existing `Runtime` card:

```html
<section id="actor-model-config-card" class="person-card actor-model-config-card" aria-labelledby="actor-model-config-heading">
  <div class="model-config-card-head">
    <h3 id="actor-model-config-heading">Model defaults</h3>
    <div class="model-config-head-actions">
      <span id="actor-model-config-status" class="status-badge healthy">Saved</span>
      <button id="actor-model-config-toggle" class="mini-button" type="button" aria-expanded="false" aria-controls="actor-model-config-panel">Configure</button>
    </div>
  </div>
  <div class="model-config-summary" aria-label="Current actor model defaults">
    <div class="model-config-summary-row">
      <span>Parent</span>
      <strong id="actor-model-config-parent-summary">Codex default · default effort</strong>
      <span class="tag blue">next</span>
    </div>
    <div class="model-config-summary-row">
      <span>Side</span>
      <strong id="actor-model-config-side-summary">Codex default · default effort</strong>
      <span class="tag blue">new</span>
    </div>
  </div>
  <div id="actor-model-config-panel" class="model-config-panel" hidden>
    <label class="field model-config-payload-field">
      <span>Payload · PUT /api/actors/{actor_id}/model-config</span>
      <textarea id="actor-model-config-payload" class="model-config-payload-editor" rows="7" spellcheck="false" aria-describedby="actor-model-config-message"></textarea>
    </label>
    <div class="pill-row">
      <button id="actor-model-config-revert" class="mini-button" type="button" disabled>Revert</button>
      <button id="actor-model-config-save" class="mini-button primary" type="button" disabled>Save</button>
    </div>
    <p id="actor-model-config-message" class="inline-status" role="status" aria-live="polite" hidden></p>
  </div>
</section>
```

- [x] **Step 2: Add compact styles**

Add to `tools/launcher/assets/web-management/styles.css` near existing card styles:

```css
.actor-model-config-card {
  border-color: #b9d3d8;
  box-shadow: inset 3px 0 0 var(--teal);
}

.model-config-card-head {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.model-config-card-head h3 {
  margin-bottom: 0;
}

.model-config-head-actions {
  display: flex;
  flex: 0 0 auto;
  gap: 6px;
  align-items: center;
}

.model-config-summary {
  display: grid;
  gap: 2px;
}

.model-config-summary-row {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  min-height: 28px;
  border-bottom: 1px solid var(--line);
}

.model-config-summary-row:last-child {
  border-bottom: 0;
}

.model-config-summary-row span:first-child {
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}

.model-config-summary-row strong {
  min-width: 0;
  overflow: hidden;
  color: var(--ink);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-config-panel {
  display: grid;
  gap: 8px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--line);
}

.model-config-panel[hidden] {
  display: none;
}

.model-config-payload-field {
  gap: 5px;
}

.model-config-payload-editor {
  width: 100%;
  min-height: 110px;
  padding: 10px;
  border: 1px solid var(--line-strong);
  border-radius: 7px;
  outline: 0;
  background: #20201d;
  color: #f7f6f1;
  font-family: var(--mono);
  font-size: 12px;
  line-height: 1.45;
  resize: vertical;
}

.model-config-payload-editor:focus {
  border-color: var(--teal);
  box-shadow: 0 0 0 3px rgba(31, 111, 119, 0.16);
}

.model-config-payload-editor.is-invalid {
  border-color: #d9b1ac;
  box-shadow: 0 0 0 3px rgba(170, 60, 52, 0.13);
}
```

Inside the existing mobile media query, add:

```css
.model-config-card-head,
.model-config-head-actions {
  align-items: stretch;
  flex-direction: column;
}

.model-config-summary-row {
  grid-template-columns: 1fr;
  align-items: stretch;
}
```

- [x] **Step 3: Run the UI contract test**

Run:

```bash
node tests/web_management_ui_contract.test.js
```

Expected:

```text
ok - actor model config UI uses payload editor without schema or dropdown residue
```

Other pre-existing UI contract tests must continue passing.

---

### Task 4: Render Actor Console Model Config State

**Files:**

- Modify: `tools/launcher/assets/web-management/app.js`
- Modify: `tests/web_management_ui_state.test.js`
- Test: `node tests/web_management_ui_state.test.js`

- [x] **Step 1: Extend the test render element harness**

In `createRenderElements()` in `tests/web_management_ui_state.test.js`, add:

```javascript
actorModelConfigCard: node(),
actorModelConfigStatus: node(),
actorModelConfigToggle: node(),
actorModelConfigParentSummary: node(),
actorModelConfigSideSummary: node(),
actorModelConfigPanel: node(),
actorModelConfigPayload: node(),
actorModelConfigSave: node(),
actorModelConfigRevert: node(),
actorModelConfigMessage: node(),
```

- [x] **Step 2: Add failing render-state tests**

Append:

```javascript
test('actor model config render initializes from actor console model_config', () => {
  const state = app.createState();
  const elements = createRenderElements();
  state.selectedActorId = 'act-pm-demo';
  state.actorConsole = {
    actor: { actor_id: 'act-pm-demo', role: 'pm' },
    runtime: { actor_id: 'act-pm-demo', role: 'pm', status: 'active' },
    model_config: {
      parent: { model: 'gpt-5.4', effort: 'high' },
      side: { model: 'gpt-5.4-mini', effort: 'medium' },
    },
  };

  app.renderActorModelConfig(state, elements);

  assert.equal(elements.actorModelConfigParentSummary.textContent, 'gpt-5.4 · high');
  assert.equal(elements.actorModelConfigSideSummary.textContent, 'gpt-5.4-mini · medium');
  assert.equal(elements.actorModelConfigStatus.textContent, 'Saved');
  assert.equal(elements.actorModelConfigPanel.hidden, true);
  assert.match(elements.actorModelConfigPayload.value, /"parent"/);
});

test('actor model config render uses custom summary for future payload shape', () => {
  const state = app.createState();
  const elements = createRenderElements();
  state.selectedActorId = 'act-pm-demo';
  state.actorModelConfigSavedText = JSON.stringify({ model_overrides: { parent: { effort: 'warp' } } }, null, 2);
  state.actorModelConfigDraftText = state.actorModelConfigSavedText;

  app.renderActorModelConfig(state, elements);

  assert.equal(elements.actorModelConfigParentSummary.textContent, 'Custom payload');
  assert.equal(elements.actorModelConfigSideSummary.textContent, 'Custom payload');
});
```

- [x] **Step 3: Add model config state initialization helper**

Add to `app.js`:

```javascript
function actorConsoleModelConfigPayload(actorConsole) {
  const modelConfig = actorConsole && actorConsole.model_config && typeof actorConsole.model_config === 'object'
    ? actorConsole.model_config
    : {};
  return JSON.parse(JSON.stringify(modelConfig));
}

function syncActorModelConfigFromConsole(state) {
  const payload = actorConsoleModelConfigPayload(state.actorConsole);
  const text = stablePayloadText(payload);
  state.actorModelConfigSavedText = text;
  state.actorModelConfigDraftText = text;
  state.actorModelConfigError = '';
  state.actorModelConfigStatus = '';
  state.actorModelConfigSaving = false;
  state.actorModelConfigPanelOpen = false;
}
```

Call `syncActorModelConfigFromConsole(state)` after successful selected actor console payload application, and when actor selection changes to a different actor before rendering the new detail.

- [x] **Step 4: Add render function**

Add to `app.js`:

```javascript
function renderActorModelConfig(state, elements) {
  if (!elements.actorModelConfigCard) {
    return;
  }

  const parseResult = parseJsonObjectPayload(state.actorModelConfigDraftText || '{}');
  const payload = parseResult.ok ? parseResult.value : {};
  const summary = summarizeActorModelPayload(payload);
  const dirty = !state.actorModelConfigError
    && !sameJsonObjectText(state.actorModelConfigDraftText || '{}', state.actorModelConfigSavedText || '{}');

  elements.actorModelConfigParentSummary.textContent = summary.parent;
  elements.actorModelConfigSideSummary.textContent = summary.side;
  elements.actorModelConfigPanel.hidden = !state.actorModelConfigPanelOpen;
  elements.actorModelConfigPayload.value = state.actorModelConfigDraftText || '{}';
  elements.actorModelConfigPayload.classList.toggle('is-invalid', Boolean(state.actorModelConfigError));
  elements.actorModelConfigSave.disabled = !dirty || state.actorModelConfigSaving || Boolean(state.actorModelConfigError);
  elements.actorModelConfigRevert.disabled = (!dirty && !state.actorModelConfigError) || state.actorModelConfigSaving;
  elements.actorModelConfigSave.textContent = state.actorModelConfigSaving ? 'Saving...' : 'Save';
  elements.actorModelConfigStatus.textContent = state.actorModelConfigError ? 'Invalid' : (dirty ? 'Unsaved' : 'Saved');
  elements.actorModelConfigStatus.className = 'status-badge ' + (state.actorModelConfigError ? 'danger' : (dirty ? 'busy' : 'healthy'));
  elements.actorModelConfigToggle.textContent = state.actorModelConfigPanelOpen ? 'Close' : (dirty || state.actorModelConfigError ? 'Review' : 'Configure');
  elements.actorModelConfigToggle.setAttribute('aria-expanded', state.actorModelConfigPanelOpen ? 'true' : 'false');
  elements.actorModelConfigToggle.classList.toggle('primary', !state.actorModelConfigPanelOpen && (dirty || Boolean(state.actorModelConfigError)));
  elements.actorModelConfigMessage.textContent = state.actorModelConfigStatus || '';
  elements.actorModelConfigMessage.hidden = !state.actorModelConfigPanelOpen || !state.actorModelConfigStatus;
}
```

Call `renderActorModelConfig(state, elements)` inside `renderActorDetail(state, elements)`.

- [x] **Step 5: Export render and sync helpers for tests**

Add:

```javascript
actorConsoleModelConfigPayload,
syncActorModelConfigFromConsole,
renderActorModelConfig,
```

- [x] **Step 6: Run state tests**

Run:

```bash
node tests/web_management_ui_state.test.js
```

Expected:

```text
ok - actor model config render initializes from actor console model_config
ok - actor model config render uses custom summary for future payload shape
```

---

### Task 5: Wire Payload Editing, Revert, And Save

**Files:**

- Modify: `tools/launcher/assets/web-management/app.js`
- Modify: `tests/web_management_ui_state.test.js`
- Test: `node tests/web_management_ui_state.test.js`

- [x] **Step 1: Add state tests for edit, invalid payload, revert, and save API path**

Append:

```javascript
test('actor model config edit state accepts future payload and rejects non-object JSON', () => {
  const state = app.createState();
  state.actorModelConfigSavedText = JSON.stringify({ parent: { model: null, effort: null }, side: {} }, null, 2);
  state.actorModelConfigDraftText = state.actorModelConfigSavedText;

  app.recordActorModelConfigDraft(state, '{"future": {"effort": "warp"}}');
  assert.equal(state.actorModelConfigError, '');
  assert.match(state.actorModelConfigStatus, /Unsaved/);

  app.recordActorModelConfigDraft(state, '[1,2,3]');
  assert.equal(state.actorModelConfigError, 'Payload must be a JSON object.');
});

test('actor model config revert returns to saved payload', () => {
  const state = app.createState();
  state.actorModelConfigSavedText = JSON.stringify({ parent: { model: 'gpt-5.4', effort: 'high' }, side: {} }, null, 2);
  state.actorModelConfigDraftText = '{"future": true}';

  app.revertActorModelConfigDraft(state);

  assert.equal(state.actorModelConfigDraftText, state.actorModelConfigSavedText);
  assert.equal(state.actorModelConfigError, '');
});
```

- [x] **Step 2: Add pure state mutation helpers**

Add:

```javascript
function recordActorModelConfigDraft(state, text) {
  state.actorModelConfigDraftText = text;
  const result = parseJsonObjectPayload(text);
  if (!result.ok) {
    state.actorModelConfigError = result.error;
    state.actorModelConfigStatus = result.error;
    return false;
  }
  state.actorModelConfigError = '';
  state.actorModelConfigStatus = sameJsonObjectText(text, state.actorModelConfigSavedText || '{}')
    ? ''
    : 'Unsaved payload.';
  return true;
}

function revertActorModelConfigDraft(state) {
  state.actorModelConfigDraftText = state.actorModelConfigSavedText || '{}';
  state.actorModelConfigError = '';
  state.actorModelConfigStatus = 'Reverted to saved payload.';
}
```

- [x] **Step 3: Add async save helper**

Add:

```javascript
async function saveActorModelConfig(state) {
  if (!state.selectedActorId || state.actorModelConfigSaving) {
    return null;
  }

  const result = parseJsonObjectPayload(state.actorModelConfigDraftText || '{}');
  if (!result.ok) {
    state.actorModelConfigError = result.error;
    state.actorModelConfigStatus = result.error;
    return null;
  }

  if (sameJsonObjectText(state.actorModelConfigDraftText || '{}', state.actorModelConfigSavedText || '{}')) {
    return null;
  }

  state.actorModelConfigSaving = true;
  state.actorModelConfigStatus = 'Saving payload...';
  try {
    const response = await fetchJson(buildActorModelConfigUrl(state.selectedActorId), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(result.value),
    });
    const canonicalPayload = response && response.model_config && typeof response.model_config === 'object'
      ? response.model_config
      : result.value;
    state.actorModelConfigSavedText = stablePayloadText(canonicalPayload);
    state.actorModelConfigDraftText = state.actorModelConfigSavedText;
    state.actorModelConfigError = '';
    state.actorModelConfigStatus = '';
    state.actorModelConfigPanelOpen = false;
    if (state.actorConsole) {
      state.actorConsole.model_config = JSON.parse(JSON.stringify(canonicalPayload));
    }
    return response;
  } catch (error) {
    state.actorModelConfigError = error && error.message ? error.message : 'Request failed.';
    state.actorModelConfigStatus = state.actorModelConfigError;
    return null;
  } finally {
    state.actorModelConfigSaving = false;
  }
}
```

- [x] **Step 4: Wire event listeners in `bootstrap()`**

In the element lookup block, add:

```javascript
actorModelConfigCard: document.getElementById('actor-model-config-card'),
actorModelConfigStatus: document.getElementById('actor-model-config-status'),
actorModelConfigToggle: document.getElementById('actor-model-config-toggle'),
actorModelConfigParentSummary: document.getElementById('actor-model-config-parent-summary'),
actorModelConfigSideSummary: document.getElementById('actor-model-config-side-summary'),
actorModelConfigPanel: document.getElementById('actor-model-config-panel'),
actorModelConfigPayload: document.getElementById('actor-model-config-payload'),
actorModelConfigSave: document.getElementById('actor-model-config-save'),
actorModelConfigRevert: document.getElementById('actor-model-config-revert'),
actorModelConfigMessage: document.getElementById('actor-model-config-message'),
```

In the event binding section, add:

```javascript
if (elements.actorModelConfigToggle) {
  elements.actorModelConfigToggle.addEventListener('click', function () {
    state.actorModelConfigPanelOpen = !state.actorModelConfigPanelOpen;
    if (state.actorModelConfigPanelOpen && state.actorModelConfigError) {
      state.actorModelConfigStatus = state.actorModelConfigError;
    }
    renderActorDetail(state, elements);
  });
}

if (elements.actorModelConfigPayload) {
  elements.actorModelConfigPayload.addEventListener('input', function () {
    recordActorModelConfigDraft(state, elements.actorModelConfigPayload.value);
    renderActorDetail(state, elements);
  });
}

if (elements.actorModelConfigRevert) {
  elements.actorModelConfigRevert.addEventListener('click', function () {
    revertActorModelConfigDraft(state);
    renderActorDetail(state, elements);
  });
}

if (elements.actorModelConfigSave) {
  elements.actorModelConfigSave.addEventListener('click', function () {
    saveActorModelConfig(state).then(function () {
      renderActorDetail(state, elements);
    });
    renderActorDetail(state, elements);
  });
}
```

- [x] **Step 5: Export mutation and save helpers**

Add:

```javascript
recordActorModelConfigDraft,
revertActorModelConfigDraft,
saveActorModelConfig,
```

- [x] **Step 6: Run state tests**

Run:

```bash
node tests/web_management_ui_state.test.js
```

Expected:

```text
ok - actor model config edit state accepts future payload and rejects non-object JSON
ok - actor model config revert returns to saved payload
```

---

### Task 6: Prove API Contract And No Frontend Schema Ownership

**Files:**

- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tests/web_management_ui_contract.test.js`
- Modify: `tests/test_repo_consistency.py`
- Test: `node tests/web_management_ui_state.test.js`
- Test: `node tests/web_management_ui_contract.test.js`
- Test: `python3 -m unittest tests.test_repo_consistency -k actor_model_config`

- [x] **Step 1: Add async save test with fake fetch**

Append to `tests/web_management_ui_state.test.js`:

```javascript
test('actor model config save PUTs actor-scoped API and accepts server canonical payload', async () => {
  const state = app.createState();
  state.selectedActorId = 'act-pm-demo';
  state.actorConsole = { model_config: { parent: {}, side: {} } };
  state.actorModelConfigSavedText = JSON.stringify({ parent: {}, side: {} }, null, 2);
  state.actorModelConfigDraftText = JSON.stringify({ future: { effort: 'warp' } }, null, 2);

  const calls = [];
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async function (url, options) {
    calls.push({ url, options });
    return okResponse({
      actor_id: 'act-pm-demo',
      model_config: { future: { effort: 'warp' } },
    });
  };

  try {
    await app.saveActorModelConfig(state);
  } finally {
    globalThis.fetch = previousFetch;
  }

  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, '/api/actors/act-pm-demo/model-config');
  assert.equal(calls[0].options.method, 'PUT');
  assert.deepEqual(JSON.parse(calls[0].options.body), { future: { effort: 'warp' } });
  assert.equal(state.actorModelConfigPanelOpen, false);
  assert.equal(state.actorModelConfigError, '');
  assert.deepEqual(state.actorConsole.model_config, { future: { effort: 'warp' } });
});
```

- [x] **Step 2: Add contract assertion that frontend owns no effort enum**

In `tests/web_management_ui_contract.test.js`, add to the forbidden list for actor model config UI:

```javascript
'minimal|low|medium|high|ultra',
'effort must be',
'Payload must include parent and side',
```

- [x] **Step 3: Run focused tests**

Run:

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
python3 -m unittest tests.test_repo_consistency -k actor_model_config
```

Expected:

```text
all Node UI tests print ok lines and exit 0
python unittest exits 0
```

---

### Task 7: Focused API And Browser Acceptance

**Files:**

- No production code changes in this task.
- Verify: `tests/test_web_management.py`
- Verify: live browser at the local Web Management URL.

- [x] **Step 1: Run focused backend API tests**

Run:

```bash
python3 -m unittest \
  tests.test_web_management.WebManagementProductApiTests.test_actor_model_config_get_api_returns_creation_default_dto \
  tests.test_web_management.WebManagementProductApiTests.test_actor_model_config_put_api_replaces_config_and_runtime_resolve_uses_same_core \
  tests.test_web_management.WebManagementProductApiTests.test_actor_model_config_put_invalid_payload_is_400_and_preserves_file \
  tests.test_web_management.WebManagementHTTPActionTests.test_model_config_put_route_accepts_http_put_method
```

Expected:

```text
Ran 4 tests
OK
```

- [x] **Step 2: Run final live-surface residue scans**

Run:

```bash
rg -n "model-config\\.json|parent-model|side-model|parent-effort|side-effort|schema-strip|<summary>Schema</summary>|allowed_efforts|VALID_EFFORTS|effort must be|must include parent and side" tools/launcher/assets/web-management
rg -n "/api/instances/.*/model-config|/api/instances/.*model-config" tools/launcher/web_management.py
rg -n "read_management_payload|replace_management_payload" tools/launcher/app_server.py tools/launcher/submit_turn.py tools/launcher/side_thread_lifecycle.py tools/launcher/daemon_core.py tools/launcher/task_sys_runtime.py
```

Expected:

```text
no output from all three commands
```

- [x] **Step 3: Verify live browser interaction**

Use the in-app browser against the running Web Management UI and verify:

```text
1. Select an actor.
2. Model defaults card is visible and collapsed by default.
3. Card shows Parent and Side summaries from actor console model_config.
4. Click Configure.
5. No Schema/details block is visible.
6. Payload textarea is visible.
7. Enter a valid future-shaped JSON object such as:
   {"future":{"effort":"warp"}}
8. Save is enabled.
9. Click Save.
10. PUT request succeeds or server rejection is shown as server feedback.
11. On success, card collapses and summary shows Custom payload.
12. Enter [1,2,3].
13. Save is disabled and error says Payload must be a JSON object.
14. Browser console has no warning/error entries from the UI code.
```

- [x] **Step 4: Check worktree scope**

Run:

```bash
git status --short --branch
git -C /Users/chen/Dev/buddyswitch status --short --branch
```

Expected:

```text
current worktree branch is fea-webui
root checkout remains clean unless the user explicitly requested otherwise
```

---

## Final Acceptance Checklist

- [x] `Model defaults` card exists in production WebUI, not only in `docs/spec`.
- [x] WebUI uses only `GET/PUT /api/actors/{actor_id}/model-config` and actor console `model_config`.
- [x] No WebUI code reads or names `model-config.json`.
- [x] No WebUI visible schema exists.
- [x] No frontend effort enum, allowed effort list, schema version, or required parent/side key validation exists.
- [x] No old dropdown/form ids exist on live WebUI surfaces.
- [x] Payload editor accepts generic JSON objects and rejects arrays/scalars/invalid JSON before save.
- [x] Server schema errors are displayed as server errors, not reimplemented in frontend.
- [x] Summary is derived from payload only and falls back to `Custom payload`.
- [x] Save path updates selected actor console state from the server response.
- [x] Focused Node UI tests pass.
- [x] Focused Python API and consistency tests pass.
- [x] Live browser check passes with no UI JavaScript warning/error entries. The intentional rejected PUT path is accepted only as server-feedback validation.

## Plan Self-Review

Spec coverage:

- Payload-first UI: Tasks 2 through 5.
- No schema in frontend: Tasks 1, 3, 6, and 7.
- No dual-track compatibility: Tasks 2, 4, 5, and residue scans in Task 7.
- Product core boundary: Requirements, module boundaries, and API tests in Task 7.
- End-to-end contract: Task 6 save test plus Task 7 browser acceptance.

Placeholder scan:

- This plan contains concrete files, ids, helper names, test code, commands, and expected outputs.

Type and name consistency:

- Canonical state names use `actorModelConfig*`.
- URL helper is `buildActorModelConfigUrl(actorId)`.
- Parser helper is `parseJsonObjectPayload(text)`.
- Summary helper is `summarizeActorModelPayload(payload)`.
- Render helper is `renderActorModelConfig(state, elements)`.
- Save helper is `saveActorModelConfig(state)`.

## Implementation Order

1. Tests for residue and contract.
2. Pure helper functions and state.
3. Static card HTML/CSS.
4. Rendering.
5. Editing and save events.
6. API contract and no-schema tests.
7. Focused backend, residue, and live-browser acceptance.

## Execution Acceptance Results

Completed on 2026-07-09 in `/Users/chen/Dev/buddyswitch/.worktrees/fea-webui`.

Implementation result:

- Production WebUI now has one compact `Model defaults` card on the selected actor panel.
- The card is collapsed by default and expands into a single JSON payload editor.
- Save writes through `PUT /api/actors/{actor_id}/model-config` only.
- New actor creation defaults are seeded by the product core as `gpt-5.5` with `medium` effort for both Parent and Side.
- A payload with all `model` and `effort` values set to `null` is treated as an explicit reset to Codex defaults, not as the creation default.
- The editable payload strips server response metadata when `parent` or `side` are present, so the textarea reflects the request payload instead of frontend schema documentation.
- Summary text is derived from the payload only and falls back to `Custom payload` for unknown future shapes.
- Periodic actor console refresh preserves an open clean panel and dirty draft; actor selection force-resets the previous actor draft.
- No dropdown form, schema block, frontend effort enum, feature flag, compatibility route, or direct file path behavior was added.

Automated verification:

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
python3 -m unittest tests.test_repo_consistency -k actor_model_config
python3 -m unittest \
  tests.test_web_management.WebManagementProductApiTests.test_actor_model_config_get_api_returns_creation_default_dto \
  tests.test_web_management.WebManagementProductApiTests.test_actor_model_config_put_api_replaces_config_and_runtime_resolve_uses_same_core \
  tests.test_web_management.WebManagementProductApiTests.test_actor_model_config_put_invalid_payload_is_400_and_preserves_file \
  tests.test_web_management.WebManagementHTTPActionTests.test_model_config_put_route_accepts_http_put_method
```

All commands passed.

Residue verification:

```bash
rg -n "model-config\\.json|parent-model|side-model|parent-effort|side-effort|schema-strip|<summary>Schema</summary>|allowed_efforts|VALID_EFFORTS|effort must be|must include parent and side" tools/launcher/assets/web-management
rg -n "savedConfig|draftConfig|parentModel|sideModel|parentEffort|sideEffort|schema_version|allowedEfforts|effortOptions|modelConfig\\.parent|modelConfig\\.side" tools/launcher/assets/web-management/app.js tools/launcher/assets/web-management/index.html tools/launcher/assets/web-management/styles.css
rg -n "/api/instances/.*/model-config|/api/instances/.*model-config" tools/launcher/web_management.py
rg -n "read_management_payload|replace_management_payload" tools/launcher/app_server.py tools/launcher/submit_turn.py tools/launcher/side_thread_lifecycle.py tools/launcher/daemon_core.py tools/launcher/task_sys_runtime.py
```

All residue scans returned no matches.

Live UI verification:

- Verified `http://127.0.0.1:8766/` was served by this `fea-webui` worktree server.
- Verified `Model defaults` is visible, compact, and collapsed by default.
- Verified `Configure` expands the payload editor and no Schema/details block is visible.
- Verified future-shaped object text enables Save; current backend rejects unknown top-level keys and the UI displays that server feedback without reimplementing schema rules.
- Verified valid backend payload saves successfully, collapses the card, and updates Parent/Side summaries.
- Verified array payload `[1,2,3]` disables Save and shows `Payload must be a JSON object.`
- Restored the actor payload to explicit null values after the live test, which means `Codex default` inheritance for that existing actor.
- Final DOM state for the reset actor: `Saved`, `Configure`, panel hidden, Parent and Side summaries both `Codex default · default effort`, and no visible schema text.

Post-acceptance default adjustment:

- Creation seed now writes `{"model":"gpt-5.5","effort":"medium"}` for both `parent` and `side`.
- Missing config files resolve to the same creation default without writing.
- Explicit null management payloads still write empty `parent` and `side` disk sections and resolve as `codex_default`.

Scope verification:

- Current worktree: `fea-webui`, with changes limited to WebUI assets, focused tests, and this memo/spec documentation.
- Root checkout `/Users/chen/Dev/buddyswitch` remained clean.
