'use strict';

const { test } = require('node:test');
const { assert, app, deferred, okResponse, createRenderElements, capabilityDto } = require('./ui_state_harness');

test('actor capabilities URL is actor scoped', () => {
  assert.equal(app.buildActorCapabilitiesUrl('act-pm-demo'), '/api/actors/act-pm-demo/capabilities');
  assert.equal(app.buildActorCapabilitiesUrl('act demo/one'), '/api/actors/act%20demo%2Fone/capabilities');
});

test('console capabilities initialize typed saved and draft levels', () => {
  const state = app.createState();
  state.selectedActorId = 'act-pm-demo';
  state.actorConsole = { actor: { actor_id: 'act-pm-demo' }, capabilities: capabilityDto() };

  app.syncActorCapabilitiesFromConsole(state);

  assert.equal(state.actorCapabilityActorId, 'act-pm-demo');
  assert.deepEqual(state.actorCapabilitySaved, { parent: 'balanced', side: 'fast' });
  assert.deepEqual(state.actorCapabilityDraft, { parent: 'balanced', side: 'fast' });
  assert.equal(state.actorCapabilityCatalog.length, 4);
});

test('capability editor stays unavailable without a selected actor catalog', () => {
  const state = app.createState();
  const elements = createRenderElements();
  state.actorCapabilityPanelOpen = true;

  app.renderActorCapabilities(state, elements);

  assert.equal(state.actorCapabilityPanelOpen, false);
  assert.equal(elements.actorCapabilityPanel.hidden, true);
  assert.equal(elements.actorCapabilityToggle.disabled, true);
  assert.equal(elements.actorCapabilityToggle.textContent, 'Configure');
  assert.equal(elements.actorCapabilityToggle.getAttribute('aria-expanded'), 'false');
  assert.equal(elements.actorCapabilityStatus.textContent, 'Unavailable');
});

test('changing one capability marks card unsaved and matrix selected cells', () => {
  const state = app.createState();
  const elements = createRenderElements();
  state.selectedActorId = 'act-pm-demo';
  state.actorConsole = { actor: { actor_id: 'act-pm-demo' }, capabilities: capabilityDto() };
  app.syncActorCapabilitiesFromConsole(state);
  state.actorCapabilityPanelOpen = true;

  app.selectActorCapability(state, 'parent', 'deep');
  app.renderActorCapabilities(state, elements);

  assert.deepEqual(state.actorCapabilityDraft, { parent: 'deep', side: 'fast' });
  assert.equal(elements.actorCapabilityStatus.textContent, 'Unsaved');
  assert.equal(elements.actorCapabilitySave.disabled, false);
  assert.equal(elements.actorCapabilitySave.textContent, 'Save config');
  assert.equal(elements.actorCapabilityParentSummary.textContent, 'Balanced');
  assert.match(elements.actorCapabilityMatrix.innerHTML, /data-capability-role="parent" data-capability-level="deep"[^>]*is-selected/);
});

test('cancel restores saved levels and closes capability editor', () => {
  const state = app.createState();
  state.actorCapabilitySaved = { parent: 'balanced', side: 'fast' };
  state.actorCapabilityDraft = { parent: 'deep', side: 'maximum' };
  state.actorCapabilityPanelOpen = true;

  app.cancelActorCapabilityDraft(state);

  assert.deepEqual(state.actorCapabilityDraft, state.actorCapabilitySaved);
  assert.equal(state.actorCapabilityPanelOpen, false);
  assert.equal(state.actorCapabilityError, '');
});

test('capability save PUTs two levels and accepts canonical response', async () => {
  const state = app.createState();
  state.selectedActorId = 'act-pm-demo';
  state.actorCapabilityActorId = 'act-pm-demo';
  state.actorCapabilityPanelOpen = true;
  state.actorCapabilitySaved = { parent: 'balanced', side: 'fast' };
  state.actorCapabilityDraft = { parent: 'deep', side: 'maximum' };
  state.actorConsole = { capabilities: capabilityDto() };
  const calls = [];
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async function (url, options) {
    calls.push({ url, options });
    return okResponse({ actor_id: 'act-pm-demo', capabilities: capabilityDto('deep', 'maximum') });
  };

  try {
    await app.saveActorCapabilities(state);
  } finally {
    globalThis.fetch = previousFetch;
  }

  assert.equal(calls[0].url, '/api/actors/act-pm-demo/capabilities');
  assert.deepEqual(JSON.parse(calls[0].options.body), { parent: 'deep', side: 'maximum' });
  assert.deepEqual(state.actorCapabilitySaved, { parent: 'deep', side: 'maximum' });
  assert.equal(state.actorCapabilityPanelOpen, false);
  assert.equal(state.actorConsole.capabilities.parent.level, 'deep');
});

test('failed capability save preserves draft and open editor', async () => {
  const state = app.createState();
  state.selectedActorId = 'act-pm-demo';
  state.actorCapabilityActorId = 'act-pm-demo';
  state.actorCapabilityPanelOpen = true;
  state.actorCapabilitySaved = { parent: 'balanced', side: 'fast' };
  state.actorCapabilityDraft = { parent: 'deep', side: 'maximum' };
  state.actorCapabilityCatalog = capabilityDto().levels;
  state.actorConsole = { actor: { actor_id: 'act-pm-demo' }, capabilities: capabilityDto() };
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async function () { throw new Error('save rejected'); };

  try {
    await app.saveActorCapabilities(state);
  } finally {
    globalThis.fetch = previousFetch;
  }

  assert.deepEqual(state.actorCapabilityDraft, { parent: 'deep', side: 'maximum' });
  assert.equal(state.actorCapabilityPanelOpen, true);
  assert.equal(state.actorCapabilityError, 'save rejected');

  const elements = createRenderElements();
  app.renderActorCapabilities(state, elements);
  assert.equal(elements.actorCapabilitySave.disabled, false);

  globalThis.fetch = async function () {
    return okResponse({ actor_id: 'act-pm-demo', capabilities: capabilityDto('deep', 'maximum') });
  };
  try {
    await app.saveActorCapabilities(state);
  } finally {
    globalThis.fetch = previousFetch;
  }
  assert.deepEqual(state.actorCapabilitySaved, { parent: 'deep', side: 'maximum' });
  assert.equal(state.actorCapabilityPanelOpen, false);
});

test('same-actor console refresh cannot strand an in-flight capability save', async () => {
  const state = app.createState();
  state.selectedActorId = 'act-pm-demo';
  state.actorCapabilityActorId = 'act-pm-demo';
  state.actorCapabilityPanelOpen = true;
  state.actorCapabilitySaved = { parent: 'balanced', side: 'fast' };
  state.actorCapabilityDraft = { parent: 'deep', side: 'fast' };
  state.actorCapabilityCatalog = capabilityDto().levels;
  state.actorConsole = { actor: { actor_id: 'act-pm-demo' }, capabilities: capabilityDto() };
  let resolveSave;
  const previousFetch = globalThis.fetch;
  globalThis.fetch = function () {
    return new Promise((resolve) => { resolveSave = resolve; });
  };

  try {
    const savePromise = app.saveActorCapabilities(state);
    app.applyActorConsolePayload(state, {
      console: { actor: { actor_id: 'act-pm-demo' }, capabilities: capabilityDto() },
    });
    resolveSave(okResponse({ actor_id: 'act-pm-demo', capabilities: capabilityDto('deep', 'fast') }));
    await savePromise;
  } finally {
    globalThis.fetch = previousFetch;
  }

  assert.equal(state.actorCapabilitySaving, false);
  assert.deepEqual(state.actorCapabilitySaved, { parent: 'deep', side: 'fast' });
  assert.equal(state.actorCapabilityPanelOpen, false);
});

test('malformed capability save response preserves the draft for retry', async () => {
  const previousFetch = globalThis.fetch;
  try {
    for (const response of [
      { actor_id: 'act-other', capabilities: capabilityDto('deep', 'maximum') },
      { actor_id: 'act-pm-demo', capabilities: { ...capabilityDto('deep', 'maximum'), catalog_version: undefined } },
      { actor_id: 'act-pm-demo', capabilities: { levels: [] } },
    ]) {
      const state = app.createState();
      state.selectedActorId = 'act-pm-demo';
      state.actorCapabilityActorId = 'act-pm-demo';
      state.actorCapabilityPanelOpen = true;
      state.actorCapabilitySaved = { parent: 'balanced', side: 'fast' };
      state.actorCapabilityDraft = { parent: 'deep', side: 'maximum' };
      state.actorConsole = { actor: { actor_id: 'act-pm-demo' }, capabilities: capabilityDto() };
      globalThis.fetch = async function () { return okResponse(response); };

      await app.saveActorCapabilities(state);

      assert.equal(state.actorCapabilityError, 'Capability response is invalid.');
      assert.deepEqual(state.actorCapabilityDraft, { parent: 'deep', side: 'maximum' });
      assert.equal(state.actorCapabilityPanelOpen, true);
    }
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('stale capability save failure cannot mark a newly selected actor', async () => {
  const state = app.createState();
  state.selectedActorId = 'act-first';
  state.actorCapabilityActorId = 'act-first';
  state.actorCapabilityPanelOpen = true;
  state.actorCapabilitySaved = { parent: 'balanced', side: 'fast' };
  state.actorCapabilityDraft = { parent: 'deep', side: 'maximum' };
  let rejectSave;
  const previousFetch = globalThis.fetch;
  globalThis.fetch = function () {
    return new Promise((_resolve, reject) => { rejectSave = reject; });
  };

  try {
    const savePromise = app.saveActorCapabilities(state);
    state.actorSelectionRequestId += 1;
    state.selectedActorId = 'act-second';
    state.actorConsole = { actor: { actor_id: 'act-second' }, capabilities: capabilityDto() };
    app.syncActorCapabilitiesFromConsole(state);
    rejectSave(new Error('late rejection'));
    await savePromise;
  } finally {
    globalThis.fetch = previousFetch;
  }

  assert.equal(state.actorCapabilityActorId, 'act-second');
  assert.equal(state.actorCapabilityError, '');
  assert.deepEqual(state.actorCapabilityDraft, { parent: 'balanced', side: 'fast' });
});

test('actor switch discards prior draft and binds new actor capabilities', () => {
  const state = app.createState();
  state.selectedActorId = 'act-first';
  state.actorCapabilityActorId = 'act-first';
  state.actorCapabilitySaved = { parent: 'balanced', side: 'fast' };
  state.actorCapabilityDraft = { parent: 'maximum', side: 'maximum' };
  state.actorCapabilityPanelOpen = true;
  state.selectedActorId = 'act-second';
  state.actorConsole = { actor: { actor_id: 'act-second' }, capabilities: capabilityDto('deep', 'balanced') };

  app.syncActorCapabilitiesFromConsole(state);

  assert.equal(state.actorCapabilityActorId, 'act-second');
  assert.deepEqual(state.actorCapabilityDraft, { parent: 'deep', side: 'balanced' });
  assert.equal(state.actorCapabilityPanelOpen, false);
});

test('capability model details render canonical model and effort as text', () => {
  const state = app.createState();
  const elements = createRenderElements();
  state.selectedActorId = 'act-pm-demo';
  const capabilities = capabilityDto('deep', 'maximum');
  capabilities.parent.model = 'saved-sol-v1';
  capabilities.parent.effort = 'saved-xhigh-v1';
  state.actorConsole = { actor: { actor_id: 'act-pm-demo' }, capabilities };

  app.renderActorCapabilities(state, elements);

  assert.equal(elements.actorCapabilityParentSummary.textContent, 'Deep');
  assert.equal(elements.actorCapabilitySideSummary.textContent, 'Maximum');
  assert.match(elements.actorCapabilityDetails.innerHTML, /saved-sol-v1/);
  assert.match(elements.actorCapabilityDetails.innerHTML, /saved-xhigh-v1/);
  assert.match(elements.actorCapabilityDetails.innerHTML, /max/);
  assert.doesNotMatch(elements.actorCapabilityDetails.innerHTML, /<input|<select|<textarea/);
  assert.equal(elements.actorCapabilityDetails.parentElement.open, false);
});
