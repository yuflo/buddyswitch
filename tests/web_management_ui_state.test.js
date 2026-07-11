#!/usr/bin/env node
'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const rendererModule = require(path.join(
  __dirname,
  '..',
  'tools',
  'launcher',
  'assets',
  'web-management',
  'markdown-renderer.js'
));
const MarkdownIt = require(path.join(
  __dirname,
  '..',
  'tools',
  'launcher',
  'assets',
  'web-management',
  'vendor',
  'markdown-it',
  'markdown-it.min.js'
));

globalThis.BuddySwitchMarkdownRenderer = {
  createMarkdownRenderer() {
    return rendererModule.createMarkdownRenderer({
      markdownIt: MarkdownIt,
      DOMPurify: {
        sanitize(html) {
          return html;
        },
      },
      hljs: null,
    });
  },
};

const app = require(path.join(__dirname, '..', 'tools', 'launcher', 'assets', 'web-management', 'app.js'));

let testChain = Promise.resolve();
let testsFlushed = false;

function test(name, fn) {
  testChain = testChain.then(async function () {
    try {
      await fn();
      process.stdout.write(`ok - ${name}\n`);
    } catch (error) {
      process.stderr.write(`not ok - ${name}\n`);
      throw error;
    }
  });
}

process.on('beforeExit', async function () {
  if (testsFlushed) {
    return;
  }
  testsFlushed = true;
  await testChain;
});

function identityRef(identityId) {
  return { id: identityId, type: identityId.indexOf('ext-') === 0 ? 'external' : 'actor' };
}

function imMessage({ id, sender, target, content, replyTo = null }) {
  return {
    id,
    sender_identity: identityRef(sender),
    target_identity: identityRef(target),
    content,
    reply_to: replyTo,
  };
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}

function okResponse(payload) {
  return {
    ok: true,
    json: async function () {
      return Object.assign({ ok: true }, payload || {});
    },
  };
}

function lifecycleOperation(overrides) {
  const operation = Object.assign({
    id: 'op-demo',
    action: 'clear',
    status: 'running',
    label: 'Clearing thread for act-market-demo',
    detail: 'Launcher command is running.',
    target: { actor_id: 'act-market-demo', role: 'market' },
    result: null,
    error: null,
  }, overrides || {});
  if (!operation.target) {
    operation.target = { actor_id: '', role: '' };
  }
  return operation;
}

function imNotFoundResponse() {
  return {
    ok: false,
    json: async function () {
      return {
        ok: false,
        error: { code: 'E_IM_NOT_FOUND', message: 'direct conversation not found' },
      };
    },
  };
}

async function waitFor(predicate, description, timeoutMs = 800) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (predicate()) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  throw new Error('Timed out waiting for ' + description);
}

function createRenderElements() {
  const node = () => {
    const attributes = {};
    const classes = new Set();
    return {
    textContent: '',
    value: '',
    hidden: false,
    disabled: false,
    innerHTML: '',
    className: '',
    classList: {
      toggle(name, force) {
        const shouldHave = force === undefined ? !classes.has(name) : Boolean(force);
        if (shouldHave) {
          classes.add(name);
        } else {
          classes.delete(name);
        }
      },
      contains(name) {
        return classes.has(name);
      },
    },
    querySelectorAll() { return []; },
      setAttribute(name, value) { attributes[name] = String(value); },
      getAttribute(name) {
        return Object.prototype.hasOwnProperty.call(attributes, name) ? attributes[name] : null;
      },
      removeAttribute(name) { delete attributes[name]; },
      focus() { this.focused = true; },
    };
  };
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
    selectedContextAvatar: node(),
    selectedContextRole: node(),
    selectedContextId: node(),
    selectedContextRuntime: node(),
    selectedContextHealth: node(),
    actorRuntimeDetail: node(),
    actorTaskSummary: node(),
    actorTrackSummary: node(),
    actorCapabilityCard: node(),
    actorCapabilityStatus: node(),
    actorCapabilityToggle: node(),
    actorCapabilityParentSummary: node(),
    actorCapabilitySideSummary: node(),
    actorCapabilityPanel: node(),
    actorCapabilityMatrix: node(),
    actorCapabilityDetails: Object.assign(node(), { parentElement: { open: true } }),
    actorCapabilitySave: node(),
    actorCapabilityCancel: node(),
    actorCapabilityMessage: node(),
    tracksList: node(),
    trackDetail: node(),
    trackStudioRail: node(),
    imConversation: node(),
    roomThread: Object.assign(node(), { scrollTop: 0, scrollHeight: 0, clientHeight: 0, scrollTo(options) { this.lastScrollTo = options; } }),
    newReplyChip: Object.assign(node(), { classList: { add() {}, remove() {}, toggle() {} } }),
    sendButton: node(),
    interruptButton: node(),
    stopButton: node(),
    deleteButton: node(),
    clearButton: node(),
    resumeButton: node(),
    lifecycleOperationStatus: node(),
    actionAvailabilityStatus: node(),
    openTuiButton: node(),
    openTuiStatus: node(),
    openTuiCommand: node(),
    openTuiFallback: node(),
    copyTuiCommandButton: node(),
    deleteConfirmationBackdrop: node(),
    deleteConfirmationTarget: node(),
    deleteConfirmationRole: node(),
    deleteConfirmationState: node(),
    deleteConfirmationLabel: node(),
    deleteConfirmationInput: node(),
    deleteConfirmationConfirm: node(),
    deleteConfirmationCancel: node(),
  };
}

test('create button requires selected role and no start busy state', () => {
  assert.equal(app.computeCreateEnabled({ selectedRole: '' }), false);
  assert.equal(app.computeCreateEnabled({ selectedRole: 'pm' }), true);
});

test('state defaults to Team room as the primary section', () => {
  const state = app.createState();

  assert.equal(state.selectedSection, 'actors');
  assert.equal(state.selectedActorId, '');
  assert.equal(state.selectedTrackId, '');
  assert.deepEqual(state.actors, []);
  assert.deepEqual(state.tracks, []);
  assert.deepEqual(state.lifecycleOperations, {});
  assert.equal(Object.prototype.hasOwnProperty.call(state, 'createPending'), false);
  assert.equal(Object.prototype.hasOwnProperty.call(state, 'lifecycle' + 'PendingAction'), false);
  assert.equal(state.imConversationIdentityId, '');
});

test('actor payload sync chooses first actor and clears stale selection', () => {
  const state = app.createState();
  state.selectedActorId = 'act-missing';
  state.openTuiMessage = 'Terminal opened.';
  state.openTuiCommand = 'attach command';
  app.recordImProjectedMessage(state, imMessage({
    id: 'msg-stale',
    sender: 'act-missing',
    target: 'ext-web',
    content: 'stale',
  }));

  app.applyActorsPayload(state, {
    actors: [
      { actor_id: 'act-pm-demo', role: 'pm', runtime: { status: 'active' } },
      { actor_id: 'act-dev-demo', role: 'dev', runtime: { status: 'inactive' } },
    ],
  });

  assert.equal(state.selectedActorId, 'act-pm-demo');
  assert.equal(state.openTuiMessage, '');
  assert.equal(state.openTuiCommand, '');
  assert.equal(state.imConversationIdentityId, 'act-pm-demo');
  assert.deepEqual(state.imConversation, []);
  assert.deepEqual(state.imSeenMessageIds, {});
  assert.deepEqual(state.actors.map((actor) => actor.actor_id), ['act-pm-demo', 'act-dev-demo']);
});

test('actor payload reconciliation retains each unconfirmed created actor independently', () => {
  const state = app.createState();
  state.selectedActorId = 'act-dev-two';
  state.rosterPendingActors = {
    'act-market-one': 'market',
    'act-dev-two': 'dev',
  };
  state.actors = [
    { actor_id: 'act-market-one', role: 'market', pending: true, runtime: { status: 'initializing' } },
    { actor_id: 'act-dev-two', role: 'dev', pending: true, runtime: { status: 'initializing' } },
  ];

  app.applyActorsPayload(state, {
    actors: [
      { actor_id: 'act-market-one', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
    ],
  });

  assert.deepEqual(state.rosterPendingActors, { 'act-dev-two': 'dev' });
  assert.equal(state.selectedActorId, 'act-dev-two');
  assert.deepEqual(state.actors.map((actor) => actor.actor_id), ['act-market-one', 'act-dev-two']);
  assert.equal(state.actors[0].pending, undefined);
  assert.equal(state.actors[1].pending, true);

  app.applyActorsPayload(state, {
    actors: [
      { actor_id: 'act-market-one', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
      { actor_id: 'act-dev-two', role: 'dev', runtime: { status: 'active', app_server_health: 'healthy' } },
    ],
  });

  assert.deepEqual(state.rosterPendingActors, {});
  assert.equal(state.selectedActorId, 'act-dev-two');
  assert.equal(state.actors[1].pending, undefined);
});

test('teammate roster renders prototype person rows from supported actor facts', () => {
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

  assert.match(html, /person-row/);
  assert.match(html, /avatar/);
  assert.match(html, />DV</);
  assert.match(html, /Developer/);
  assert.match(html, /act-dev-demo/);
  assert.match(html, /active/);
  assert.match(html, /healthy/);
  assert.doesNotMatch(html, /Dev Actor|PM Actor|72%|capacity|current focus|last proof/i);
});

test('actor roster groups starting active and stopped work with accurate counts', () => {
  const state = app.createState();
  state.roles = [
    { id: 'market', label: 'Market', scope: 'product' },
    { id: 'dev', label: 'Developer', scope: 'product' },
    { id: 'pm', label: 'PM', scope: 'product' },
  ];
  state.actors = [
    { actor_id: 'act-dev-active', role: 'dev', runtime: { status: 'active', app_server_health: 'healthy' } },
    { actor_id: 'act-pm-stopped', role: 'pm', runtime: { status: 'inactive', app_server_health: 'unhealthy' } },
  ];
  state.lifecycleOperations = {
    'op-start-market': lifecycleOperation({
      id: 'op-start-market',
      action: 'start',
      status: 'running',
      label: 'Starting Market',
      target: { actor_id: '', role: 'market' },
    }),
  };
  state.selectedLifecycleOperationId = 'op-start-market';

  const collapsedHtml = app.renderActorRowsHtml(state);

  assert.match(collapsedHtml, /data-roster-group="starting"/);
  assert.match(collapsedHtml, />Starting<[^]*>1</);
  assert.match(collapsedHtml, /data-roster-group="active"/);
  assert.match(collapsedHtml, />Active<[^]*>1</);
  assert.match(collapsedHtml, /data-roster-group="stopped"/);
  assert.match(collapsedHtml, />Stopped<[^]*>1</);
  assert.match(collapsedHtml, /act-dev-active/);
  assert.doesNotMatch(collapsedHtml, /act-pm-stopped/);
  assert.match(collapsedHtml, /data-operation-id="op-start-market"[^>]*role="option"[^>]*aria-selected="true"/);
  assert.match(collapsedHtml, /data-roster-toggle="stopped"[^>]*aria-expanded="false"/);

  state.rosterStoppedExpanded = true;
  const expandedHtml = app.renderActorRowsHtml(state);

  assert.match(expandedHtml, /act-pm-stopped/);
  assert.match(expandedHtml, /data-actor-id="act-pm-stopped"[^>]*role="option"[^>]*aria-selected="false"/);
  assert.match(expandedHtml, /data-roster-toggle="stopped"[^>]*aria-expanded="true"/);
});

test('initial roster selection prefers active actor over stopped inventory', () => {
  const state = app.createState();

  app.applyActorsPayload(state, {
    actors: [
      { actor_id: 'act-stopped-first', role: 'pm', runtime: { status: 'inactive', app_server_health: 'unhealthy' } },
      { actor_id: 'act-active-second', role: 'dev', runtime: { status: 'active', app_server_health: 'healthy' } },
    ],
  });

  assert.equal(state.selectedActorId, 'act-active-second');
  assert.equal(state.rosterStoppedExpanded, false);
  assert.match(app.renderActorRowsHtml(state), /data-actor-id="act-active-second"[^>]*aria-selected="true"/);
});

test('stopped-only roster expands stopped group for its automatic selection', () => {
  const state = app.createState();

  app.applyActorsPayload(state, {
    actors: [
      { actor_id: 'act-stopped-only', role: 'pm', runtime: { status: 'inactive', app_server_health: 'unhealthy' } },
    ],
  });

  assert.equal(state.selectedActorId, 'act-stopped-only');
  assert.equal(state.rosterStoppedExpanded, true);
  const html = app.renderActorRowsHtml(state);
  assert.match(html, /data-actor-id="act-stopped-only"[^>]*aria-selected="true"/);
  assert.match(html, /data-roster-toggle="stopped"[^>]*aria-expanded="true"/);
});

test('start operation rows distinguish queued from running lifecycle work', () => {
  const state = app.createState();
  state.roles = [
    { id: 'market', label: 'Market', scope: 'product' },
    { id: 'pm', label: 'PM', scope: 'product' },
  ];
  state.lifecycleOperations = {
    'op-start-running': lifecycleOperation({
      id: 'op-start-running',
      action: 'start',
      status: 'running',
      label: 'Starting Market',
      target: { actor_id: '', role: 'market' },
    }),
    'op-start-queued': lifecycleOperation({
      id: 'op-start-queued',
      action: 'start',
      status: 'queued',
      label: 'Starting PM',
      detail: 'Waiting for lifecycle queue.',
      target: { actor_id: '', role: 'pm' },
    }),
  };

  const html = app.renderActorRowsHtml(state);

  assert.match(html, /op-start-running/);
  assert.match(html, /starting/);
  assert.match(html, /op-start-queued/);
  assert.match(html, /queued/);
});

test('selected actor context binds full identity to lifecycle state and actions', () => {
  const state = app.createState();
  const elements = createRenderElements();
  state.roles = [{ id: 'market', label: 'Market', scope: 'product' }];
  state.actors = [
    {
      actor_id: 'act-market-0123456789ab',
      role: 'market',
      runtime: { status: 'active', app_server_health: 'healthy', thread: { status: 'idle' } },
    },
  ];
  state.selectedActorId = 'act-market-0123456789ab';

  app.renderSelectedActorContext(state, elements);

  assert.equal(elements.selectedContextRole.textContent, 'Market');
  assert.equal(elements.selectedContextId.textContent, 'act-market-0123456789ab');
  assert.equal(elements.selectedContextRuntime.textContent, 'active');
  assert.equal(elements.selectedContextHealth.textContent, 'healthy');
  assert.equal(elements.stopButton.hidden, false);
  assert.equal(elements.stopButton.disabled, false);
  assert.equal(elements.resumeButton.hidden, true);
  assert.equal(elements.deleteButton.disabled, true);
});

test('selected start operation context shows operation identity without inventing actor id', () => {
  const state = app.createState();
  const elements = createRenderElements();
  state.roles = [{ id: 'market', label: 'Market', scope: 'product' }];
  state.lifecycleOperations = {
    'op-start-market': lifecycleOperation({
      id: 'op-start-market',
      action: 'start',
      status: 'running',
      label: 'Starting Market',
      target: { actor_id: '', role: 'market' },
    }),
  };
  state.selectedLifecycleOperationId = 'op-start-market';

  app.renderSelectedActorContext(state, elements);

  assert.equal(elements.selectedContextRole.textContent, 'Market');
  assert.equal(elements.selectedContextId.textContent, 'op-start-market');
  assert.equal(elements.selectedContextRuntime.textContent, 'starting');
  assert.equal(elements.selectedContextHealth.hidden, true);
  assert.equal(elements.stopButton.hidden, true);
  assert.equal(elements.resumeButton.hidden, true);
  assert.equal(elements.deleteButton.hidden, true);
  assert.match(elements.lifecycleOperationStatus.textContent, /Starting Market/);
});

test('delete confirmation opens for exact selected actor without sending a request', () => {
  const state = app.createState();
  const elements = createRenderElements();
  let fetchCalls = 0;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = function () {
    fetchCalls += 1;
    throw new Error('Delete confirmation must not fetch while opening.');
  };
  state.roles = [{ id: 'market', label: 'Market', scope: 'product' }];
  state.actors = [
    { actor_id: 'act-market-delete', role: 'market', runtime: { status: 'inactive', app_server_health: 'unhealthy' } },
  ];
  state.selectedActorId = 'act-market-delete';

  try {
    app.openDeleteConfirmation(state, elements, elements.deleteButton);

    assert.equal(fetchCalls, 0);
    assert.equal(state.deleteConfirmationActorId, 'act-market-delete');
    assert.equal(elements.deleteConfirmationBackdrop.hidden, false);
    assert.equal(elements.deleteConfirmationTarget.textContent, 'act-market-delete');
    assert.equal(elements.deleteConfirmationRole.textContent, 'Market');
    assert.equal(elements.deleteConfirmationState.textContent, 'inactive');
    assert.equal(elements.deleteConfirmationConfirm.disabled, true);
    assert.equal(elements.deleteConfirmationInput.focused, true);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('delete confirmation requires exact actor id and keeps captured request target', async () => {
  const originalFetch = globalThis.fetch;
  const requests = [];
  globalThis.fetch = async function (url, options) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    requests.push({ url: requestUrl, method: options && options.method });
    if (requestUrl === '/api/instances/act-delete-captured') {
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-delete-captured',
          action: 'delete',
          status: 'running',
          label: 'Deleting act-delete-captured',
          target: { actor_id: 'act-delete-captured', role: 'market' },
        }),
      });
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.roles = [{ id: 'market', label: 'Market', scope: 'product' }];
    state.actors = [
      { actor_id: 'act-delete-captured', role: 'market', runtime: { status: 'inactive', app_server_health: 'unhealthy' } },
      { actor_id: 'act-other-active', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];
    state.selectedActorId = 'act-delete-captured';
    state.lifecycleOperationPollDelaysMs = [];

    app.openDeleteConfirmation(state, elements, elements.deleteButton);
    app.updateDeleteConfirmationInput(state, elements, 'act-delete');
    assert.equal(app.deleteConfirmationMatches(state), false);
    assert.equal(elements.deleteConfirmationConfirm.disabled, true);

    app.updateDeleteConfirmationInput(state, elements, 'act-delete-captured');
    assert.equal(app.deleteConfirmationMatches(state), true);
    assert.equal(elements.deleteConfirmationConfirm.disabled, false);

    state.selectedActorId = 'act-other-active';
    await app.confirmDelete(state, elements);

    assert.deepEqual(requests, [{ url: '/api/instances/act-delete-captured', method: 'DELETE' }]);
    assert.equal(elements.deleteConfirmationBackdrop.hidden, true);
    assert.match(elements.actorsList.innerHTML, /act-delete-captured/);
    assert.match(elements.actorsList.innerHTML, /deleting/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('delete confirmation revalidates target runtime before submitting', async () => {
  const originalFetch = globalThis.fetch;
  let fetchCalls = 0;
  globalThis.fetch = async function () {
    fetchCalls += 1;
    throw new Error('Delete must not submit after the target becomes active.');
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.roles = [{ id: 'market', label: 'Market', scope: 'product' }];
    state.actors = [
      { actor_id: 'act-delete-stale', role: 'market', runtime: { status: 'inactive', app_server_health: 'unhealthy' } },
    ];
    state.selectedActorId = 'act-delete-stale';

    app.openDeleteConfirmation(state, elements, elements.deleteButton);
    app.updateDeleteConfirmationInput(state, elements, 'act-delete-stale');
    assert.equal(elements.deleteConfirmationConfirm.disabled, false);

    state.actors[0].runtime = { status: 'active', app_server_health: 'healthy' };
    state.actorConsole = {
      actor: { actor_id: 'act-delete-stale', role: 'market' },
      runtime: { status: 'active', app_server_health: 'healthy', thread_status: 'idle' },
    };
    await app.confirmDelete(state, elements);

    assert.equal(fetchCalls, 0);
    assert.equal(state.deleteConfirmationActorId, 'act-delete-stale');
    assert.equal(elements.deleteConfirmationBackdrop.hidden, false);
    assert.equal(elements.deleteConfirmationConfirm.disabled, true);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('delete confirmation stays closed while actor lifecycle is protected', () => {
  const state = app.createState();
  const elements = createRenderElements();
  state.actors = [
    { actor_id: 'act-delete-protected', role: 'market', runtime: { status: 'inactive', app_server_health: 'unhealthy' } },
  ];
  state.selectedActorId = 'act-delete-protected';
  app.recordLifecycleOperation(state, lifecycleOperation({
    id: 'op-resume-protected',
    action: 'resume',
    status: 'running',
    target: { actor_id: 'act-delete-protected', role: 'market' },
  }));

  app.openDeleteConfirmation(state, elements, elements.deleteButton);

  assert.equal(state.deleteConfirmationActorId, '');
  assert.equal(elements.deleteConfirmationBackdrop.hidden, true);
});

test('closing delete confirmation restores trigger focus without a request', () => {
  const state = app.createState();
  const elements = createRenderElements();
  state.actors = [
    { actor_id: 'act-delete-cancel', role: 'market', runtime: { status: 'inactive', app_server_health: 'unhealthy' } },
  ];
  state.selectedActorId = 'act-delete-cancel';

  app.openDeleteConfirmation(state, elements, elements.deleteButton);
  app.closeDeleteConfirmation(state, elements);

  assert.equal(state.deleteConfirmationActorId, '');
  assert.equal(elements.deleteConfirmationBackdrop.hidden, true);
  assert.equal(elements.deleteButton.focused, true);
});

test('role select repopulates role options after initial empty-shell render', () => {
  const originalDocument = globalThis.document;
  globalThis.document = {
    createElement(tagName) {
      return {
        tagName,
        value: '',
        textContent: '',
      };
    },
  };

  try {
    const state = app.createState();
    const appended = [];
    const elements = createRenderElements();
    elements.roleSelect = {
      options: [{ value: '', textContent: 'Select role' }],
      value: '',
      appendChild(option) {
        appended.push(option);
        this.options.push(option);
      },
    };
    state.roles = [
      { id: 'market', label: 'Market' },
      { id: 'dev', label: 'Dev' },
    ];
    state.selectedRole = 'market';

    app.renderRoleSelect(state, elements);

    assert.deepEqual(
      elements.roleSelect.options.map((option) => [option.value, option.textContent]),
      [
        ['', 'Select role'],
        ['market', 'Market (market)'],
        ['dev', 'Dev (dev)'],
      ]
    );
    assert.equal(elements.roleSelect.value, 'market');
  } finally {
    globalThis.document = originalDocument;
  }
});

function capabilityDto(parent = 'balanced', side = 'fast') {
  const levels = [
    { id: 'fast', label: 'Fast', description: 'Responsive, high-strength reasoning', model: 'gpt-5.6-luna', effort: 'xhigh' },
    { id: 'balanced', label: 'Balanced', description: 'Strong everyday work', model: 'gpt-5.6-terra', effort: 'high' },
    { id: 'deep', label: 'Deep', description: 'Complex reasoning and coding', model: 'gpt-5.6-sol', effort: 'xhigh' },
    { id: 'maximum', label: 'Maximum', description: 'Highest capability and cost', model: 'gpt-5.6-sol', effort: 'max' },
  ];
  const byId = Object.fromEntries(levels.map((row) => [row.id, row]));
  return {
    catalog_version: 1,
    levels,
    parent: { ...byId[parent], level: parent, effect: 'applies_before_next_parent_submit' },
    side: { ...byId[side], level: side, effect: 'applies_to_new_side_threads_only' },
  };
}

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

test('track payload sync chooses first track and keeps comments inside detail state', () => {
  const state = app.createState();

  app.applyTracksPayload(state, {
    tracks: [
      { id: 'track-alpha', title: 'Actor console' },
      { id: 'track-beta', title: 'Follow up' },
    ],
  });
  app.applyTrackDetailPayload(state, {
    track: {
      id: 'track-alpha',
      comment_threads: [{ thread_id: 'thread-open', comments: [{ id: 'comment-1' }] }],
      comment_summary: { comment_count: 1, open_thread_count: 1, resolved_thread_count: 0 },
    },
  });

  assert.equal(state.selectedTrackId, 'track-alpha');
  assert.equal(state.selectedTrackDetail.id, 'track-alpha');
  assert.deepEqual(state.selectedTrackDetail.comment_threads[0].comments.map((row) => row.id), ['comment-1']);
});

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
  assert.match(html, /doc-title/);
  assert.match(html, /Current state/);
  assert.match(html, /Materials and proofs/);
  assert.match(html, /Brief/);
  assert.match(html, /Proof/);
  assert.match(html, /Decision captured/);
  assert.match(html, /Total comments/);
  assert.match(html, /Looks right/);
  assert.doesNotMatch(html, /<textarea|composer|submit|<button[^>]*>Resolve|collaborators/i);
});

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

test('direct thread renders markdown replies inside stable bubble boundaries', () => {
  const state = app.createState();
  const elements = createRenderElements();
  state.imConversation = [
    {
      id: 'msg-markdown',
      direction: 'reply',
      sender: 'market/act-market-demo',
      deliveryStatus: '',
      wakeStatus: '',
      replyTo: '',
      content: [
        '**Short answer:** launch is viable.',
        '',
        '- Keep actor health visible',
        '- Keep proof details in Track view',
        '',
        '> Decision: ship once send and reply are inspectable.',
        '',
        '```bash',
        'node tests/web_management_ui_state.test.js',
        '```',
        '',
        '| Area | Status |',
        '| --- | --- |',
        '| Message body | Markdown safe |',
        '',
        'Links stay low-key: [review](#proof) and `code`.',
      ].join('\n'),
    },
  ];

  app.renderImConversation(state, elements);

  assert.match(elements.imConversation.innerHTML, /class="markdown-body"/);
  assert.match(elements.imConversation.innerHTML, /<strong>Short answer:<\/strong>/);
  assert.match(elements.imConversation.innerHTML, /<li>Keep actor health visible<\/li>/);
  assert.match(elements.imConversation.innerHTML, /<li>Keep proof details in Track view<\/li>/);
  assert.match(elements.imConversation.innerHTML, /<blockquote>\s*<p>Decision: ship once send and reply are inspectable\.<\/p>\s*<\/blockquote>/);
  assert.match(elements.imConversation.innerHTML, /<pre><code class="[^"]*language-bash[^"]*">node tests\/web_management_ui_state\.test\.js\s*<\/code><\/pre>/);
  assert.match(elements.imConversation.innerHTML, /class="markdown-table-wrap"/);
  assert.match(elements.imConversation.innerHTML, /<th>Area<\/th>/);
  assert.match(elements.imConversation.innerHTML, /<td>Markdown safe<\/td>/);
  assert.match(elements.imConversation.innerHTML, /<a href="#proof">review<\/a>|<a href="#proof"[^>]*>review<\/a>/);
  assert.match(elements.imConversation.innerHTML, /<code>code<\/code>/);
});

test('new projected replies pop once and then settle into history', () => {
  const state = app.createState();
  const elements = createRenderElements();
  state.selectedActorId = 'act-market-demo';
  state.imConversationIdentityId = 'act-market-demo';

  const recorded = app.recordSelectedActorEventMessage(state, imMessage({
    id: 'msg-new-reply',
    sender: 'act-market-demo',
    target: 'ext-web',
    content: 'Fresh reply.',
  }), 'act-market-demo');

  assert.equal(recorded, true);

  app.renderImConversation(state, elements);

  assert.match(elements.imConversation.innerHTML, /message reply is-new/);
  assert.equal(state.imFreshMessageIds['msg-new-reply'], undefined);

  app.renderImConversation(state, elements);

  assert.doesNotMatch(elements.imConversation.innerHTML, /message reply is-new/);
  assert.match(elements.imConversation.innerHTML, /Fresh reply/);
});

test('new reply auto-scroll uses the pre-render bottom position', () => {
  const state = app.createState();
  const elements = createRenderElements();
  state.selectedActorId = 'act-market-demo';
  state.imConversationIdentityId = 'act-market-demo';
  elements.roomThread.scrollTop = 300;
  elements.roomThread.clientHeight = 200;
  elements.roomThread.scrollHeight = 500;
  elements.roomThread.scrollTo = function (options) {
    this.lastScrollTo = options;
    this.scrollTop = options.top;
  };
  Object.defineProperty(elements.imConversation, 'innerHTML', {
    get() {
      return this.renderedHtml || '';
    },
    set(value) {
      this.renderedHtml = value;
      elements.roomThread.scrollHeight = 650;
    },
  });

  app.recordSelectedActorEventMessage(state, imMessage({
    id: 'msg-bottom-reply',
    sender: 'act-market-demo',
    target: 'ext-web',
    content: 'Fresh reply while already at bottom.',
  }), 'act-market-demo');

  app.renderImConversation(state, elements);

  assert.match(elements.imConversation.innerHTML, /message reply is-new/);
  assert.equal(elements.newReplyChip.hidden, true);
  assert.deepEqual(elements.roomThread.lastScrollTo, { top: 650, behavior: 'smooth' });
});

test('Track Studio rail renders read-only comment context without write controls', () => {
  const html = app.renderTrackStudioRailHtml({
    id: 'track-alpha',
    state: 'active',
    outcome: 'Ship the Team room shell',
    now: { next: 'Render Track Studio', blocker: null },
    comment_summary: { comment_count: 2, open_thread_count: 1, resolved_thread_count: 1 },
    comment_threads: [
      {
        thread_id: 'thread-open',
        status: 'open',
        latest_comment_preview: 'Looks right',
        comment_count: 2,
      },
    ],
  });

  assert.match(html, /Context/);
  assert.match(html, /Comments/);
  assert.match(html, /thread-open/);
  assert.match(html, /Looks right/);
  assert.doesNotMatch(html, /<textarea|composer|submit|<button[^>]*>Resolve/i);
});

test('actor selection clears stale feedback before fetch completes', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/actors/act-new/console') {
      return {
        ok: true,
        json: async function () {
          return {
            ok: true,
            console: {
              actor: { actor_id: 'act-new', role: 'market' },
              runtime: { status: 'active', app_server_health: 'healthy', thread_status: 'idle' },
              task_sys: { active_tasks: [] },
              tracks: { items: [] },
              im: { target: { identity_id: 'act-new', role_id: 'market' } },
            },
          };
        },
      };
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-new&limit=50') {
      return {
        ok: false,
        json: async function () {
          return {
            ok: false,
            error: { code: 'E_IM_NOT_FOUND', message: 'direct conversation not found' },
          };
        },
      };
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.healthOk = true;
    state.message = 'Created act-old.';
    state.selectedActorId = 'act-old';
    state.actors = [
      { actor_id: 'act-old', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
      { actor_id: 'act-new', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];
    app.recordImProjectedMessage(state, imMessage({
      id: 'msg-old',
      sender: 'act-old',
      target: 'ext-web',
      content: 'old actor message',
    }));
    elements.messageBanner.textContent = 'Created act-old.';

    const selection = app.selectActor(state, elements, 'act-new');
    selection.catch(function () {});

    assert.equal(state.selectedActorId, 'act-new');
    assert.equal(state.message, '');
    assert.equal(elements.messageBanner.textContent, '');
    assert.deepEqual(state.imConversation, []);
    assert.match(elements.actorRuntimeDetail.innerHTML, /skeleton-card/);
    assert.equal(elements.selectedContextId.textContent, 'act-new');

    await selection;
    if (state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('create teammate keeps pending actor visible until roster reconciliation', async () => {
  const originalFetch = globalThis.fetch;
  let actorRosterCalls = 0;
  globalThis.fetch = async function (url, options) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/instances') {
      assert.equal(options && options.method, 'POST');
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-start-market',
          action: 'start',
          status: 'running',
          label: 'Starting Market',
          target: { actor_id: '', role: 'market' },
        }),
      });
    }
    if (requestUrl === '/api/operations/op-start-market') {
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-start-market',
          action: 'start',
          status: 'succeeded',
          label: 'Starting Market',
          target: { actor_id: 'act-market-new', role: 'market' },
          result: { ok: true, actor_id: 'act-market-new' },
        }),
      });
    }
    if (requestUrl === '/api/actors') {
      actorRosterCalls += 1;
      return okResponse({
        actors: actorRosterCalls === 1
          ? [
              { actor_id: 'act-market-old', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
            ]
          : [
              { actor_id: 'act-market-old', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
              { actor_id: 'act-market-new', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
            ],
      });
    }
    if (requestUrl === '/api/actors/act-market-new/console') {
      return okResponse({
        console: {
          actor: { actor_id: 'act-market-new', role: 'market' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-new', thread_status: 'idle' },
          task_sys: { active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-market-new', role_id: 'market' } },
        },
      });
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-market-new&limit=50') {
      return imNotFoundResponse();
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.roles = [{ id: 'market', label: 'Market', scope: 'product' }];
    state.selectedRole = 'market';
    state.actors = [
      { actor_id: 'act-market-old', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];
    state.selectedActorId = 'act-market-old';
    state.lifecycleOperationPollDelaysMs = [];
    state.rosterReconcileDelaysMs = [0, 1];

    await app.createInstance(state, elements);

    assert.equal(state.selectedActorId, '');
    assert.equal(state.selectedLifecycleOperationId, 'op-start-market');
    assert.match(elements.actorsList.innerHTML, /Starting Market/);
    assert.doesNotMatch(elements.actorsList.innerHTML, /act-market-new/);

    await app.pollLifecycleOperations(state, elements);

    assert.equal(state.selectedActorId, 'act-market-new');
    assert.deepEqual(state.rosterPendingActors, { 'act-market-new': 'market' });
    assert.match(elements.actorsList.innerHTML, /act-market-new/);
    assert.match(elements.actorsList.innerHTML, /pending|initializing/i);

    await waitFor(() => Object.keys(state.rosterPendingActors).length === 0, 'roster confirmation');

    assert.equal(state.selectedActorId, 'act-market-new');
    assert.deepEqual(state.rosterPendingActors, {});
    assert.match(elements.actorsList.innerHTML, /act-market-new/);
    assert.doesNotMatch(elements.actorsList.innerHTML, /pending|initializing/i);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('create teammate accepts repeated start operations while one is still active', async () => {
  const originalFetch = globalThis.fetch;
  let createCalls = 0;
  globalThis.fetch = async function (url, options) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/instances') {
      assert.equal(options && options.method, 'POST');
      createCalls += 1;
      return okResponse({
        operation: lifecycleOperation({
          id: createCalls === 1 ? 'op-start-running' : 'op-start-queued',
          action: 'start',
          status: createCalls === 1 ? 'running' : 'queued',
          label: createCalls === 1 ? 'Starting Market' : 'Starting Market',
          detail: createCalls === 1 ? 'Launcher command is running.' : 'Waiting for lifecycle queue.',
          target: { actor_id: '', role: 'market' },
        }),
      });
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.roles = [{ id: 'market', label: 'Market', scope: 'product' }];
    state.selectedRole = 'market';
    state.lifecycleOperationPollDelaysMs = [];

    await app.createInstance(state, elements);

    assert.equal(elements.createButton.disabled, false);
    assert.equal(elements.createButton.textContent, 'Start');
    assert.match(elements.actorsList.innerHTML, /op-start-running/);

    await app.createInstance(state, elements);

    assert.equal(createCalls, 2);
    assert.equal(elements.createButton.disabled, false);
    assert.match(elements.actorsList.innerHTML, /op-start-running/);
    assert.match(elements.actorsList.innerHTML, /op-start-queued/);
    assert.match(elements.actorsList.innerHTML, /queued/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('start terminal reconciliation preserves a newer actor selection', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async function (url, options) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/instances') {
      assert.equal(options && options.method, 'POST');
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-start-latest-intent',
          action: 'start',
          status: 'running',
          label: 'Starting Market',
          target: { actor_id: '', role: 'market' },
        }),
      });
    }
    if (requestUrl === '/api/actors/act-user-intent/console') {
      return okResponse({
        console: {
          actor: { actor_id: 'act-user-intent', role: 'pm' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-user', thread_status: 'idle' },
          task_sys: { active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-user-intent', role_id: 'pm' } },
        },
      });
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-user-intent&limit=50') {
      return imNotFoundResponse();
    }
    if (requestUrl === '/api/operations/op-start-latest-intent') {
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-start-latest-intent',
          action: 'start',
          status: 'succeeded',
          label: 'Starting Market',
          target: { actor_id: 'act-market-new', role: 'market' },
          result: { ok: true, actor_id: 'act-market-new' },
        }),
      });
    }
    if (requestUrl === '/api/actors/act-market-new/console') {
      return okResponse({
        console: {
          actor: { actor_id: 'act-market-new', role: 'market' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-new', thread_status: 'idle' },
          task_sys: { active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-market-new', role_id: 'market' } },
        },
      });
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-market-new&limit=50') {
      return imNotFoundResponse();
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.roles = [
      { id: 'market', label: 'Market', scope: 'product' },
      { id: 'pm', label: 'PM', scope: 'product' },
    ];
    state.selectedRole = 'market';
    state.actors = [
      { actor_id: 'act-market-old', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
      { actor_id: 'act-user-intent', role: 'pm', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];
    state.selectedActorId = 'act-market-old';
    state.lifecycleOperationPollDelaysMs = [];
    state.rosterReconcileDelaysMs = [];

    await app.createInstance(state, elements);
    await app.selectActor(state, elements, 'act-user-intent');
    await app.pollLifecycleOperations(state, elements);

    assert.equal(state.selectedActorId, 'act-user-intent');
    assert.equal(state.selectedLifecycleOperationId, '');
    assert.deepEqual(state.rosterPendingActors, { 'act-market-new': 'market' });
    assert.match(elements.actorsList.innerHTML, /data-actor-id="act-user-intent"[^>]*aria-selected="true"/);
    assert.match(elements.actorsList.innerHTML, /data-actor-id="act-market-new"[^>]*aria-selected="false"/);
    if (state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('parallel start completions keep operation and pending actor contexts isolated', async () => {
  const originalFetch = globalThis.fetch;
  let createCalls = 0;
  let secondOperationPolls = 0;
  globalThis.fetch = async function (url, options) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/instances') {
      assert.equal(options && options.method, 'POST');
      createCalls += 1;
      return okResponse({
        operation: lifecycleOperation({
          id: createCalls === 1 ? 'op-start-one' : 'op-start-two',
          action: 'start',
          status: 'running',
          label: createCalls === 1 ? 'Starting Market' : 'Starting Dev',
          target: { actor_id: '', role: createCalls === 1 ? 'market' : 'dev' },
        }),
      });
    }
    if (requestUrl === '/api/operations/op-start-one') {
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-start-one',
          action: 'start',
          status: 'succeeded',
          label: 'Starting Market',
          target: { actor_id: 'act-market-one', role: 'market' },
          result: { ok: true, actor_id: 'act-market-one' },
        }),
      });
    }
    if (requestUrl === '/api/operations/op-start-two') {
      secondOperationPolls += 1;
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-start-two',
          action: 'start',
          status: secondOperationPolls === 1 ? 'running' : 'succeeded',
          label: 'Starting Dev',
          target: { actor_id: secondOperationPolls === 1 ? '' : 'act-dev-two', role: 'dev' },
          result: secondOperationPolls === 1 ? null : { ok: true, actor_id: 'act-dev-two' },
        }),
      });
    }
    if (requestUrl === '/api/actors/act-market-one/console' || requestUrl === '/api/actors/act-dev-two/console') {
      const actorId = requestUrl.indexOf('act-market-one') >= 0 ? 'act-market-one' : 'act-dev-two';
      const role = actorId === 'act-market-one' ? 'market' : 'dev';
      return okResponse({
        console: {
          actor: { actor_id: actorId, role },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-' + actorId, thread_status: 'idle' },
          task_sys: { active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: actorId, role_id: role } },
        },
      });
    }
    if (requestUrl.indexOf('/api/im/conversations/direct?identity_id=') === 0) {
      return imNotFoundResponse();
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.roles = [
      { id: 'market', label: 'Market', scope: 'product' },
      { id: 'dev', label: 'Dev', scope: 'product' },
    ];
    state.selectedRole = 'market';
    state.lifecycleOperationPollDelaysMs = [];
    state.rosterReconcileDelaysMs = [];

    await app.createInstance(state, elements);
    state.selectedRole = 'dev';
    await app.createInstance(state, elements);
    assert.equal(state.selectedLifecycleOperationId, 'op-start-two');

    await app.pollLifecycleOperations(state, elements);

    assert.equal(state.selectedActorId, '');
    assert.equal(state.selectedLifecycleOperationId, 'op-start-two');
    assert.deepEqual(state.rosterPendingActors, { 'act-market-one': 'market' });
    assert.match(elements.actorsList.innerHTML, /data-actor-id="act-market-one"[^>]*aria-selected="false"/);
    assert.match(elements.actorsList.innerHTML, /data-operation-id="op-start-two"[^>]*aria-selected="true"/);

    await app.pollLifecycleOperations(state, elements);

    assert.equal(state.selectedActorId, 'act-dev-two');
    assert.equal(state.selectedLifecycleOperationId, '');
    assert.deepEqual(state.rosterPendingActors, {
      'act-market-one': 'market',
      'act-dev-two': 'dev',
    });
    assert.match(elements.actorsList.innerHTML, /data-actor-id="act-market-one"[^>]*aria-selected="false"/);
    assert.match(elements.actorsList.innerHTML, /data-actor-id="act-dev-two"[^>]*aria-selected="true"/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('create teammate selects start operation context and protects actor actions', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async function (url, options) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/instances') {
      assert.equal(options && options.method, 'POST');
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-start-protect',
          action: 'start',
          status: 'running',
          label: 'Starting Market',
          detail: 'Launcher command is running.',
          target: { actor_id: '', role: 'market' },
        }),
      });
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.roles = [{ id: 'market', label: 'Market', scope: 'product' }];
    state.selectedRole = 'market';
    state.actors = [
      { actor_id: 'act-market-old', role: 'market', runtime: { status: 'active', app_server_health: 'healthy', thread: { status: 'idle' } } },
    ];
    state.selectedActorId = 'act-market-old';
    state.lifecycleOperationPollDelaysMs = [];

    await app.createInstance(state, elements);

    assert.equal(state.selectedActorId, '');
    assert.equal(state.selectedLifecycleOperationId, 'op-start-protect');
    assert.match(elements.actorsList.innerHTML, /op-start-protect/);
    assert.match(elements.actorsList.innerHTML, /is-selected/);
    assert.equal(elements.stopButton.disabled, true);
    assert.equal(elements.clearButton.disabled, true);
    assert.equal(elements.deleteButton.disabled, true);
    assert.match(elements.lifecycleOperationStatus.textContent, /Starting Market/);
    assert.equal(
      elements.actionAvailabilityStatus.textContent,
      'Start in progress. Actor actions are protected until Start completes.'
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('failed create preserves previous selection and leaves no pending actor', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/instances') {
      return {
        ok: false,
        json: async function () {
          return { ok: false, error: { message: 'launcher refused start' } };
        },
      };
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.roles = [{ id: 'market', label: 'Market', scope: 'product' }];
    state.selectedRole = 'market';
    state.actors = [
      { actor_id: 'act-market-old', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];
    state.selectedActorId = 'act-market-old';

    await app.createInstance(state, elements);

    assert.equal(state.selectedActorId, 'act-market-old');
    assert.deepEqual(state.rosterPendingActors, {});
    assert.doesNotMatch(elements.actorsList.innerHTML, /act-market-new/);
    assert.match(elements.messageBanner.textContent, /launcher refused start/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('failed start operation surfaces backend error and removes pending operation', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async function (url, options) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/instances') {
      assert.equal(options && options.method, 'POST');
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-start-failed',
          action: 'start',
          status: 'running',
          label: 'Starting Market',
          target: { actor_id: '', role: 'market' },
        }),
      });
    }
    if (requestUrl === '/api/operations/op-start-failed') {
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-start-failed',
          action: 'start',
          status: 'failed',
          label: 'Starting Market',
          target: { actor_id: '', role: 'market' },
          error: { code: 'COMMAND_FAILED', message: 'Thread bootstrap failed' },
        }),
      });
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.roles = [{ id: 'market', label: 'Market', scope: 'product' }];
    state.selectedRole = 'market';
    state.actors = [
      { actor_id: 'act-market-old', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];
    state.selectedActorId = 'act-market-old';
    state.lifecycleOperationPollDelaysMs = [];

    await app.createInstance(state, elements);

    assert.equal(state.selectedActorId, '');
    assert.equal(state.selectedLifecycleOperationId, 'op-start-failed');
    assert.match(elements.actorsList.innerHTML, /Starting Market/);

    await app.pollLifecycleOperations(state, elements);

    assert.equal(state.selectedActorId, 'act-market-old');
    assert.equal(state.selectedLifecycleOperationId, '');
    assert.deepEqual(state.lifecycleOperations, {});
    assert.doesNotMatch(elements.actorsList.innerHTML, /Starting Market/);
    assert.match(elements.messageBanner.textContent, /Thread bootstrap failed/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('create reconciliation timeout keeps selected pending row and manual refresh can confirm it', async () => {
  const originalFetch = globalThis.fetch;
  let actorRosterCalls = 0;
  globalThis.fetch = async function (url, options) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/instances') {
      assert.equal(options && options.method, 'POST');
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-start-late',
          action: 'start',
          status: 'running',
          label: 'Starting Market',
          target: { actor_id: '', role: 'market' },
        }),
      });
    }
    if (requestUrl === '/api/operations/op-start-late') {
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-start-late',
          action: 'start',
          status: 'succeeded',
          label: 'Starting Market',
          target: { actor_id: 'act-market-late', role: 'market' },
          result: { ok: true, actor_id: 'act-market-late' },
        }),
      });
    }
    if (requestUrl === '/api/actors') {
      actorRosterCalls += 1;
      return okResponse({
        actors: actorRosterCalls < 2
          ? [
              { actor_id: 'act-market-old', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
            ]
          : [
              { actor_id: 'act-market-old', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
              { actor_id: 'act-market-late', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
            ],
      });
    }
    if (requestUrl === '/api/actors/act-market-late/console') {
      return okResponse({
        console: {
          actor: { actor_id: 'act-market-late', role: 'market' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-late', thread_status: 'idle' },
          task_sys: { active_count: 0, active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-market-late', role_id: 'market' } },
        },
      });
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-market-late&limit=50') {
      return imNotFoundResponse();
    }
    if (requestUrl === '/api/health') {
      return okResponse({});
    }
    if (requestUrl === '/api/roles') {
      return okResponse({ roles: [{ id: 'market', label: 'Market' }] });
    }
    if (requestUrl === '/api/tracks') {
      return okResponse({ tracks: [] });
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.roles = [{ id: 'market', label: 'Market', scope: 'product' }];
    state.selectedRole = 'market';
    state.actors = [
      { actor_id: 'act-market-old', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];
    state.selectedActorId = 'act-market-old';
    state.lifecycleOperationPollDelaysMs = [];
    state.rosterReconcileDelaysMs = [0];

    await app.createInstance(state, elements);
    await app.pollLifecycleOperations(state, elements);
    await waitFor(
      () => /has not confirmed/.test(elements.messageBanner.textContent),
      'roster timeout message',
      300
    );

    assert.equal(state.selectedActorId, 'act-market-late');
    assert.deepEqual(state.rosterPendingActors, { 'act-market-late': 'market' });
    assert.match(elements.actorsList.innerHTML, /act-market-late/);
    assert.match(elements.actorsList.innerHTML, /initializing/);

    await app.refreshVisibleRegionsWithFeedback(state, elements);

    assert.equal(state.selectedActorId, 'act-market-late');
    assert.deepEqual(state.rosterPendingActors, {});
    assert.match(elements.actorsList.innerHTML, /act-market-late/);
    assert.doesNotMatch(elements.actorsList.innerHTML, /initializing/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('clear lifecycle operation polls to terminal result and refreshes selected actor', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async function (url, options) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/instances/act-clear-demo/clear') {
      assert.equal(options && options.method, 'POST');
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-clear-demo',
          action: 'clear',
          status: 'running',
          label: 'Clearing thread for act-clear-demo',
          target: { actor_id: 'act-clear-demo', role: 'market' },
        }),
      });
    }
    if (requestUrl === '/api/operations/op-clear-demo') {
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-clear-demo',
          action: 'clear',
          status: 'succeeded',
          label: 'Clearing thread for act-clear-demo',
          target: { actor_id: 'act-clear-demo', role: 'market' },
          result: {
            ok: true,
            previous_thread_id: 'thread-old',
            thread_id: 'thread-new',
            instance: {
              actor_id: 'act-clear-demo',
              status: 'active',
              app_server_health: 'healthy',
              thread_id: 'thread-new',
              thread: { status: 'idle' },
            },
          },
        }),
      });
    }
    if (requestUrl === '/api/actors/act-clear-demo/console') {
      return okResponse({
        console: {
          actor: { actor_id: 'act-clear-demo', role: 'market' },
          runtime: {
            status: 'active',
            app_server_health: 'healthy',
            thread_id: 'thread-new',
            thread_status: 'idle',
          },
          task_sys: { active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-clear-demo', role_id: 'market' } },
        },
      });
    }
    if (requestUrl === '/api/actors') {
      return okResponse({
        actors: [
          { actor_id: 'act-clear-demo', role: 'market', runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-new' } },
        ],
      });
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [
      { actor_id: 'act-clear-demo', role: 'market', runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-old' } },
    ];
    state.selectedActorId = 'act-clear-demo';
    state.actorConsole = {
      actor: { actor_id: 'act-clear-demo', role: 'market' },
      runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-old', thread_status: 'idle' },
    };
    state.lifecycleOperationPollDelaysMs = [];

    await app.runLifecycleAction(state, elements, 'clear', state.selectedActorId);

    assert.match(elements.actorsList.innerHTML, /clearing/);
    assert.equal(elements.clearButton.textContent, 'Clearing...');
    assert.match(elements.lifecycleOperationStatus.textContent, /Clearing thread for act-clear-demo/);

    await app.pollLifecycleOperations(state, elements);

    assert.deepEqual(state.lifecycleOperations, {});
    assert.equal(app.selectedActorRuntime(state).thread_id, 'thread-new');
    assert.match(elements.messageBanner.textContent, /completed/);
    assert.match(elements.messageBanner.textContent, /thread-new/);
    assert.doesNotMatch(elements.actorsList.innerHTML, /clearing/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('delete lifecycle operation removes actor after terminal operation result', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async function (url, options) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/instances/act-delete-demo') {
      assert.equal(options && options.method, 'DELETE');
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-delete-demo',
          action: 'delete',
          status: 'running',
          label: 'Deleting act-delete-demo',
          target: { actor_id: 'act-delete-demo', role: 'market' },
        }),
      });
    }
    if (requestUrl === '/api/operations/op-delete-demo') {
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-delete-demo',
          action: 'delete',
          status: 'succeeded',
          label: 'Deleting act-delete-demo',
          target: { actor_id: 'act-delete-demo', role: 'market' },
          result: { ok: true, actor_id: 'act-delete-demo' },
        }),
      });
    }
    if (requestUrl === '/api/actors') {
      return okResponse({
        actors: [
          { actor_id: 'act-other-demo', role: 'market', runtime: { status: 'inactive', app_server_health: 'unhealthy' } },
        ],
      });
    }
    if (requestUrl === '/api/actors/act-other-demo/console') {
      return okResponse({
        console: {
          actor: { actor_id: 'act-other-demo', role: 'market' },
          runtime: { status: 'inactive', app_server_health: 'unhealthy', thread_id: 'thread-other', thread_status: 'idle' },
          task_sys: { active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-other-demo', role_id: 'market' } },
        },
      });
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-other-demo&limit=50') {
      return imNotFoundResponse();
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [
      { actor_id: 'act-delete-demo', role: 'market', runtime: { status: 'inactive', app_server_health: 'unhealthy' } },
      { actor_id: 'act-other-demo', role: 'market', runtime: { status: 'inactive', app_server_health: 'unhealthy' } },
    ];
    state.selectedActorId = 'act-delete-demo';
    state.lifecycleOperationPollDelaysMs = [];

    await app.runLifecycleAction(state, elements, 'delete', state.selectedActorId);

    assert.match(elements.actorsList.innerHTML, /deleting/);
    assert.equal(elements.deleteButton.textContent, 'Deleting...');
    assert.match(elements.lifecycleOperationStatus.textContent, /Deleting act-delete-demo/);

    await app.pollLifecycleOperations(state, elements);

    assert.deepEqual(state.lifecycleOperations, {});
    assert.equal(state.selectedActorId, 'act-other-demo');
    assert.deepEqual(state.actors.map((actor) => actor.actor_id), ['act-other-demo']);
    assert.match(elements.messageBanner.textContent, /Deleting act-delete-demo completed/);
    assert.doesNotMatch(elements.actorsList.innerHTML, /act-delete-demo/);
    assert.match(elements.actorsList.innerHTML, /data-actor-id="act-other-demo"[^>]*aria-selected="true"/);
    if (state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('delete terminal reconciliation preserves a newer actor selection', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async function (url, options) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/instances/act-delete-old') {
      assert.equal(options && options.method, 'DELETE');
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-delete-old',
          action: 'delete',
          status: 'running',
          label: 'Deleting act-delete-old',
          target: { actor_id: 'act-delete-old', role: 'market' },
        }),
      });
    }
    if (requestUrl === '/api/operations/op-delete-old') {
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-delete-old',
          action: 'delete',
          status: 'succeeded',
          label: 'Deleting act-delete-old',
          target: { actor_id: 'act-delete-old', role: 'market' },
          result: { ok: true, actor_id: 'act-delete-old' },
        }),
      });
    }
    if (requestUrl === '/api/actors') {
      return okResponse({
        actors: [
          { actor_id: 'act-delete-neighbor', role: 'market', runtime: { status: 'inactive', app_server_health: 'unhealthy' } },
          { actor_id: 'act-user-intent', role: 'pm', runtime: { status: 'active', app_server_health: 'healthy' } },
        ],
      });
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [
      { actor_id: 'act-delete-old', role: 'market', runtime: { status: 'inactive', app_server_health: 'unhealthy' } },
      { actor_id: 'act-delete-neighbor', role: 'market', runtime: { status: 'inactive', app_server_health: 'unhealthy' } },
      { actor_id: 'act-user-intent', role: 'pm', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];
    state.selectedActorId = 'act-delete-old';
    state.lifecycleOperationPollDelaysMs = [];

    await app.runLifecycleAction(state, elements, 'delete', 'act-delete-old');
    state.selectedActorId = 'act-user-intent';
    state.actorConsole = {
      actor: { actor_id: 'act-user-intent', role: 'pm' },
      runtime: { status: 'active', app_server_health: 'healthy', thread_status: 'idle' },
    };
    await app.pollLifecycleOperations(state, elements);

    assert.equal(state.selectedActorId, 'act-user-intent');
    assert.match(elements.actorsList.innerHTML, /data-actor-id="act-user-intent"[^>]*aria-selected="true"/);
    assert.doesNotMatch(elements.actorsList.innerHTML, /act-delete-old/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('stop lifecycle operation applies terminal instance before removing pending badge', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async function (url, options) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/instances/act-stop-demo/stop') {
      assert.equal(options && options.method, 'POST');
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-stop-demo',
          action: 'stop',
          status: 'running',
          label: 'Stopping act-stop-demo',
          target: { actor_id: 'act-stop-demo', role: 'market' },
        }),
      });
    }
    if (requestUrl === '/api/operations/op-stop-demo') {
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-stop-demo',
          action: 'stop',
          status: 'succeeded',
          label: 'Stopping act-stop-demo',
          target: { actor_id: 'act-stop-demo', role: 'market' },
          result: {
            ok: true,
            instance: {
              actor_id: 'act-stop-demo',
              role: 'market',
              status: 'inactive',
              app_server_health: 'unhealthy',
              thread_id: 'thread-stop',
              thread: { status: 'idle' },
            },
          },
        }),
      });
    }
    if (requestUrl === '/api/actors/act-stop-demo/console') {
      return okResponse({
        console: {
          actor: { actor_id: 'act-stop-demo', role: 'market' },
          runtime: {
            status: 'inactive',
            app_server_health: 'unhealthy',
            thread_id: 'thread-stop',
            thread_status: 'idle',
          },
          task_sys: { active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-stop-demo', role_id: 'market' } },
        },
      });
    }
    if (requestUrl === '/api/actors') {
      return okResponse({
        actors: [
          { actor_id: 'act-stop-demo', role: 'market', runtime: { status: 'inactive', app_server_health: 'unhealthy', thread_id: 'thread-stop' } },
        ],
      });
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    const actorListWrites = [];
    let actorsHtml = '';
    Object.defineProperty(elements.actorsList, 'innerHTML', {
      get() {
        return actorsHtml;
      },
      set(value) {
        actorsHtml = value;
        actorListWrites.push(value);
      },
    });
    state.actors = [
      { actor_id: 'act-stop-demo', role: 'market', runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-stop' } },
    ];
    state.selectedActorId = 'act-stop-demo';
    state.actorConsole = {
      actor: { actor_id: 'act-stop-demo', role: 'market' },
      runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-stop', thread_status: 'idle' },
    };
    state.lifecycleOperationPollDelaysMs = [];

    await app.runLifecycleAction(state, elements, 'stop', state.selectedActorId);
    await app.pollLifecycleOperations(state, elements);

    const stoppingIndex = actorListWrites.findIndex((html) => html.indexOf('stopping') >= 0);
    const staleActiveAfterStopping = actorListWrites.slice(stoppingIndex + 1).some((html) => (
      html.indexOf('>active<') >= 0
      && html.indexOf('>healthy<') >= 0
      && html.indexOf('stopping') < 0
    ));
    assert.notEqual(stoppingIndex, -1);
    assert.equal(staleActiveAfterStopping, false);
    assert.equal(app.selectedActorRuntime(state).status, 'inactive');
    assert.equal(app.selectedActorRuntime(state).app_server_health, 'unhealthy');
    assert.equal(state.rosterStoppedExpanded, true);
    assert.match(elements.actorsList.innerHTML, /data-roster-group="stopped"/);
    assert.match(elements.actorsList.innerHTML, /data-actor-id="act-stop-demo"[^>]*aria-selected="true"/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('failed clear lifecycle operation removes pending state and re-enables controls', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async function (url, options) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/instances/act-clear-demo/clear') {
      assert.equal(options && options.method, 'POST');
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-clear-failed',
          action: 'clear',
          status: 'running',
          label: 'Clearing thread for act-clear-demo',
          target: { actor_id: 'act-clear-demo', role: 'market' },
        }),
      });
    }
    if (requestUrl === '/api/operations/op-clear-failed') {
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-clear-failed',
          action: 'clear',
          status: 'failed',
          label: 'Clearing thread for act-clear-demo',
          target: { actor_id: 'act-clear-demo', role: 'market' },
          error: { code: 'COMMAND_FAILED', message: 'Daemon start failed' },
        }),
      });
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [
      { actor_id: 'act-clear-demo', role: 'market', runtime: { status: 'active', app_server_health: 'healthy', thread: { status: 'idle' } } },
    ];
    state.selectedActorId = 'act-clear-demo';
    state.actorConsole = {
      actor: { actor_id: 'act-clear-demo', role: 'market' },
      runtime: { status: 'active', app_server_health: 'healthy', thread_status: 'idle' },
    };
    state.lifecycleOperationPollDelaysMs = [];

    await app.runLifecycleAction(state, elements, 'clear', state.selectedActorId);

    assert.match(elements.actorsList.innerHTML, /clearing/);
    assert.equal(elements.clearButton.disabled, true);

    await app.pollLifecycleOperations(state, elements);

    assert.deepEqual(state.lifecycleOperations, {});
    assert.match(elements.messageBanner.textContent, /Daemon start failed/);
    assert.doesNotMatch(elements.actorsList.innerHTML, /clearing/);
    assert.equal(elements.clearButton.disabled, false);
    assert.equal(elements.stopButton.disabled, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('actor card renders as soon as console resolves before conversation', async () => {
  const originalFetch = globalThis.fetch;
  const conversation = deferred();
  const conversationStarted = deferred();
  let selection;
  let assertionError = null;

  globalThis.fetch = function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/actors/act-new/console') {
      return Promise.resolve(okResponse({
        console: {
          actor: { actor_id: 'act-new', role: 'market' },
          runtime: {
            status: 'active',
            app_server_health: 'healthy',
            thread_id: 'thread-new',
            browser_port: 8765,
            thread_status: 'idle',
          },
          task_sys: { active_count: 0, active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-new', role_id: 'market' } },
        },
      }));
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-new&limit=50') {
      conversationStarted.resolve();
      return conversation.promise;
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [
      { actor_id: 'act-old', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
      { actor_id: 'act-new', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];
    state.selectedActorId = 'act-old';

    selection = app.selectActor(state, elements, 'act-new');
    selection.catch(function () {});
    await conversationStarted.promise;
    await waitFor(
      () => /Status/.test(elements.actorRuntimeDetail.innerHTML),
      'actor card render before conversation resolves',
      200
    );

    try {
      assert.equal(state.selectedActorId, 'act-new');
      assert.match(elements.actorRuntimeDetail.innerHTML, /Status/);
      assert.match(elements.actorRuntimeDetail.innerHTML, /Health/);
      assert.match(elements.actorRuntimeDetail.innerHTML, /Task Sys/);
      assert.match(elements.actorRuntimeDetail.innerHTML, /Tracks/);
      assert.doesNotMatch(elements.actorRuntimeDetail.innerHTML, /Loading/);
      assert.match(elements.imConversation.innerHTML, /thread|conversation|skeleton|loading/i);
    } catch (error) {
      assertionError = error;
    }

    conversation.resolve(imNotFoundResponse());
    await selection;
    if (assertionError) {
      throw assertionError;
    }
    if (state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('slow conversation does not disable runtime actions after console loads', async () => {
  const originalFetch = globalThis.fetch;
  const conversation = deferred();
  const conversationStarted = deferred();
  let selection;
  let assertionError = null;

  globalThis.fetch = function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/actors/act-controls/console') {
      return Promise.resolve(okResponse({
        console: {
          actor: { actor_id: 'act-controls', role: 'market' },
          runtime: {
            status: 'active',
            app_server_health: 'healthy',
            thread_id: 'thread-controls',
            thread_status: 'idle',
          },
          task_sys: { active_count: 0, active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-controls', role_id: 'market' } },
        },
      }));
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-controls&limit=50') {
      conversationStarted.resolve();
      return conversation.promise;
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [
      { actor_id: 'act-controls', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];

    selection = app.selectActor(state, elements, 'act-controls');
    selection.catch(function () {});
    await conversationStarted.promise;
    await waitFor(
      () => elements.stopButton.disabled === false
        && elements.clearButton.disabled === false
        && elements.openTuiButton.disabled === false,
      'runtime controls after console before conversation resolves',
      200
    );

    try {
      assert.equal(elements.stopButton.disabled, false);
      assert.equal(elements.clearButton.disabled, false);
      assert.equal(elements.openTuiButton.disabled, false);
      assert.equal(elements.actionAvailabilityStatus.textContent, '');
    } catch (error) {
      assertionError = error;
    }

    conversation.resolve(imNotFoundResponse());
    await selection;
    if (assertionError) {
      throw assertionError;
    }
    if (state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('manual refresh renders roster before selected conversation completes', async () => {
  const originalFetch = globalThis.fetch;
  const conversation = deferred();
  const conversationStarted = deferred();
  let refresh;
  let assertionError = null;

  globalThis.fetch = function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/health') {
      return Promise.resolve(okResponse({}));
    }
    if (requestUrl === '/api/roles') {
      return Promise.resolve(okResponse({ roles: [{ id: 'market', label: 'Market' }] }));
    }
    if (requestUrl === '/api/actors') {
      return Promise.resolve(okResponse({
        actors: [
          { actor_id: 'act-old', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
          { actor_id: 'act-roster-new', role: 'market', runtime: { status: 'inactive', app_server_health: 'unhealthy' } },
        ],
      }));
    }
    if (requestUrl === '/api/tracks') {
      return Promise.resolve(okResponse({ tracks: [] }));
    }
    if (requestUrl === '/api/actors/act-old/console') {
      return Promise.resolve(okResponse({
        console: {
          actor: { actor_id: 'act-old', role: 'market' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-old', thread_status: 'idle' },
          task_sys: { active_count: 0, active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-old', role_id: 'market' } },
        },
      }));
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-old&limit=50') {
      conversationStarted.resolve();
      return conversation.promise;
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.selectedActorId = 'act-old';
    state.actors = [
      { actor_id: 'act-old', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];

    refresh = app.refreshVisibleRegionsWithFeedback(state, elements);
    refresh.catch(function () {});
    await conversationStarted.promise;
    await waitFor(
      () => /data-roster-group="stopped"/.test(elements.actorsList.innerHTML)
        && />Stopped<[^]*>1</.test(elements.actorsList.innerHTML)
        && /Status/.test(elements.actorRuntimeDetail.innerHTML),
      'progressive roster and card render before conversation resolves',
      200
    );

    try {
      assert.match(elements.actorsList.innerHTML, />Stopped<[^]*>1</);
      assert.doesNotMatch(elements.actorsList.innerHTML, /act-roster-new/);
      assert.match(elements.actorRuntimeDetail.innerHTML, /Status/);
      assert.match(elements.imConversation.innerHTML, /thread|conversation|skeleton|loading/i);
    } catch (error) {
      assertionError = error;
    }

    conversation.resolve(imNotFoundResponse());
    await refresh;
    if (assertionError) {
      throw assertionError;
    }
    if (state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('manual refresh preserves visible conversation while revalidating it', async () => {
  const originalFetch = globalThis.fetch;
  const conversation = deferred();
  const conversationStarted = deferred();
  let refresh;
  let assertionError = null;

  globalThis.fetch = function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/health') {
      return Promise.resolve(okResponse({}));
    }
    if (requestUrl === '/api/roles') {
      return Promise.resolve(okResponse({ roles: [{ id: 'market', label: 'Market' }] }));
    }
    if (requestUrl === '/api/actors') {
      return Promise.resolve(okResponse({
        actors: [
          { actor_id: 'act-old', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
        ],
      }));
    }
    if (requestUrl === '/api/tracks') {
      return Promise.resolve(okResponse({ tracks: [] }));
    }
    if (requestUrl === '/api/actors/act-old/console') {
      return Promise.resolve(okResponse({
        console: {
          actor: { actor_id: 'act-old', role: 'market' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-old', thread_status: 'idle' },
          task_sys: { active_count: 0, active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-old', role_id: 'market' } },
        },
      }));
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-old&limit=50') {
      conversationStarted.resolve();
      return conversation.promise;
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.selectedActorId = 'act-old';
    state.actors = [
      { actor_id: 'act-old', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];
    state.imConversationIdentityId = 'act-old';
    state.imConversation = [
      { id: 'msg-old', direction: 'reply', sender: 'market/act-old', deliveryStatus: '', wakeStatus: '', replyTo: '', content: 'still visible' },
    ];
    state.imSeenMessageIds = { 'msg-old': true };
    app.renderImConversation(state, elements);

    refresh = app.refreshVisibleRegionsWithFeedback(state, elements);
    refresh.catch(function () {});
    await conversationStarted.promise;

    try {
      assert.match(elements.imConversation.innerHTML, /still visible/);
      assert.doesNotMatch(elements.imConversation.innerHTML, /conversation-skeleton/);
      assert.equal(elements.imConversation.getAttribute('aria-busy'), 'true');
    } catch (error) {
      assertionError = error;
    }

    conversation.resolve(okResponse({
      messages: [
        imMessage({
          id: 'msg-new',
          sender: 'act-old',
          target: 'ext-web',
          content: 'fresh reply',
        }),
      ],
    }));
    await refresh;
    if (assertionError) {
      throw assertionError;
    }
    assert.match(elements.imConversation.innerHTML, /fresh reply/);
    if (state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('manual refresh renders tracks list before selected conversation completes', async () => {
  const originalFetch = globalThis.fetch;
  const conversation = deferred();
  const conversationStarted = deferred();
  let refresh;
  let assertionError = null;

  globalThis.fetch = function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/health') {
      return Promise.resolve(okResponse({}));
    }
    if (requestUrl === '/api/roles') {
      return Promise.resolve(okResponse({ roles: [{ id: 'market', label: 'Market' }] }));
    }
    if (requestUrl === '/api/actors') {
      return Promise.resolve(okResponse({
        actors: [
          { actor_id: 'act-old', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
        ],
      }));
    }
    if (requestUrl === '/api/tracks') {
      return Promise.resolve(okResponse({
        tracks: [
          { id: 'track-new', title: 'Progressive refresh', state: 'active', comment_summary: { open_thread_count: 2 } },
        ],
      }));
    }
    if (requestUrl === '/api/actors/act-old/console') {
      return Promise.resolve(okResponse({
        console: {
          actor: { actor_id: 'act-old', role: 'market' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-old', thread_status: 'idle' },
          task_sys: { active_count: 0, active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-old', role_id: 'market' } },
        },
      }));
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-old&limit=50') {
      conversationStarted.resolve();
      return conversation.promise;
    }
    if (requestUrl === '/api/tracks/track-new') {
      return Promise.resolve(okResponse({
        track: { id: 'track-new', title: 'Progressive refresh', state: 'active' },
      }));
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.selectedActorId = 'act-old';
    state.actors = [
      { actor_id: 'act-old', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];

    refresh = app.refreshVisibleRegionsWithFeedback(state, elements);
    refresh.catch(function () {});
    await conversationStarted.promise;
    await waitFor(
      () => /track-new/.test(elements.tracksList.innerHTML),
      'tracks list before conversation resolves',
      200
    );

    try {
      assert.match(elements.tracksList.innerHTML, /track-new/);
      assert.match(elements.tracksList.innerHTML, /Progressive refresh/);
      assert.match(elements.imConversation.innerHTML, /thread|conversation|skeleton|loading/i);
    } catch (error) {
      assertionError = error;
    }

    conversation.resolve(imNotFoundResponse());
    await refresh;
    if (assertionError) {
      throw assertionError;
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('console failure does not clear the visible direct thread', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/health') {
      return Promise.resolve(okResponse({}));
    }
    if (requestUrl === '/api/roles') {
      return Promise.resolve(okResponse({ roles: [{ id: 'market', label: 'Market' }] }));
    }
    if (requestUrl === '/api/actors') {
      return Promise.resolve(okResponse({
        actors: [
          { actor_id: 'act-old', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
        ],
      }));
    }
    if (requestUrl === '/api/tracks') {
      return Promise.resolve(okResponse({ tracks: [] }));
    }
    if (requestUrl === '/api/actors/act-old/console') {
      return Promise.resolve({
        ok: false,
        json: async function () {
          return { ok: false, error: { message: 'console unavailable' } };
        },
      });
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-old&limit=50') {
      return Promise.resolve(okResponse({
        messages: [
          imMessage({
            id: 'msg-still-here',
            sender: 'act-old',
            target: 'ext-web',
            content: 'thread survives',
          }),
        ],
      }));
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.selectedActorId = 'act-old';
    state.actors = [
      { actor_id: 'act-old', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];
    state.imConversationIdentityId = 'act-old';
    state.imConversation = [
      { id: 'msg-old', direction: 'reply', sender: 'market/act-old', deliveryStatus: '', wakeStatus: '', replyTo: '', content: 'thread survives' },
    ];
    state.imSeenMessageIds = { 'msg-old': true };

    await app.refreshVisibleRegionsWithFeedback(state, elements);

    assert.match(elements.actorRuntimeDetail.innerHTML, /console unavailable/);
    assert.match(elements.imConversation.innerHTML, /thread survives/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('rapid actor switching keeps the latest selected teammate visible', async () => {
  const originalFetch = globalThis.fetch;
  let resolveFirst;
  let resolveSecond;
  const first = new Promise((resolve) => { resolveFirst = resolve; });
  const second = new Promise((resolve) => { resolveSecond = resolve; });

  globalThis.fetch = function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/actors/act-first/console') {
      return first;
    }
    if (requestUrl === '/api/actors/act-second/console') {
      return second;
    }
    if (requestUrl.startsWith('/api/im/conversations/direct')) {
      return Promise.resolve({
        ok: false,
        json: async function () {
          return { ok: false, error: { code: 'E_IM_NOT_FOUND', message: 'not found' } };
        },
      });
    }
    throw new Error('unexpected fetch ' + requestUrl);
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
        return {
          ok: true,
          console: {
            actor: { actor_id: 'act-second', role: 'pm' },
            runtime: { status: 'active', app_server_health: 'healthy' },
            task_sys: { active_tasks: [] },
            tracks: { items: [] },
            im: { target: { identity_id: 'act-second', role_id: 'pm' } },
          },
        };
      },
    });
    await secondSelection;

    resolveFirst({
      ok: true,
      json: async function () {
        return {
          ok: true,
          console: {
            actor: { actor_id: 'act-first', role: 'dev' },
            runtime: { status: 'active', app_server_health: 'healthy' },
            task_sys: { active_tasks: [] },
            tracks: { items: [] },
            im: { target: { identity_id: 'act-first', role_id: 'dev' } },
          },
        };
      },
    });
    await firstSelection;

    assert.equal(state.selectedActorId, 'act-second');
    assert.equal(state.actorConsole.actor.actor_id, 'act-second');
    if (state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('rapid actor switching keeps stale conversation from overwriting latest selection', async () => {
  const originalFetch = globalThis.fetch;
  let resolveFirstConversation;
  let resolveSecondConversation;
  const firstConversation = new Promise((resolve) => { resolveFirstConversation = resolve; });
  const secondConversation = new Promise((resolve) => { resolveSecondConversation = resolve; });

  globalThis.fetch = function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/actors/act-first/console') {
      return Promise.resolve(okResponse({
        console: {
          actor: { actor_id: 'act-first', role: 'dev' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-first', thread_status: 'idle' },
          task_sys: { active_count: 0, active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-first', role_id: 'dev' } },
        },
      }));
    }
    if (requestUrl === '/api/actors/act-second/console') {
      return Promise.resolve(okResponse({
        console: {
          actor: { actor_id: 'act-second', role: 'pm' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-second', thread_status: 'idle' },
          task_sys: { active_count: 0, active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-second', role_id: 'pm' } },
        },
      }));
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-first&limit=50') {
      return firstConversation;
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-second&limit=50') {
      return secondConversation;
    }
    throw new Error('unexpected fetch ' + requestUrl);
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
    firstSelection.catch(function () {});
    const secondSelection = app.selectActor(state, elements, 'act-second');
    secondSelection.catch(function () {});

    resolveSecondConversation(okResponse({
      messages: [
        imMessage({
          id: 'msg-second',
          sender: 'act-second',
          target: 'ext-web',
          content: 'second wins',
        }),
      ],
    }));
    await waitFor(
      () => /second wins/.test(elements.imConversation.innerHTML),
      'latest conversation render',
      300
    );

    resolveFirstConversation(okResponse({
      messages: [
        imMessage({
          id: 'msg-first',
          sender: 'act-first',
          target: 'ext-web',
          content: 'first stale',
        }),
      ],
    }));

    await Promise.allSettled([firstSelection, secondSelection]);

    assert.equal(state.selectedActorId, 'act-second');
    assert.equal(state.imConversationIdentityId, 'act-second');
    assert.match(elements.imConversation.innerHTML, /second wins/);
    assert.doesNotMatch(elements.imConversation.innerHTML, /first stale/);
    if (state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('stale selected actor console refresh cannot overwrite a newer lifecycle selection', async () => {
  const originalFetch = globalThis.fetch;
  const staleConsole = deferred();
  globalThis.fetch = function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/actors/act-design-old/console') {
      return staleConsole.promise;
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [
      { actor_id: 'act-design-old', role: 'design', runtime: { status: 'active', app_server_health: 'healthy' } },
      { actor_id: 'act-pm-new', role: 'pm', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];
    state.selectedActorId = 'act-design-old';
    state.actorConsole = {
      actor: { actor_id: 'act-design-old', role: 'design' },
      runtime: { status: 'active', app_server_health: 'healthy', thread_status: 'idle' },
    };

    const refresh = app.refreshSelectedActorConsoleAndRender(state, elements);
    refresh.catch(function () {});
    state.selectedActorId = 'act-pm-new';
    state.actorConsole = null;
    app.renderActorRowsHtml(state);

    staleConsole.resolve(okResponse({
      console: {
        actor: { actor_id: 'act-design-old', role: 'design' },
        runtime: { status: 'active', app_server_health: 'healthy', thread_status: 'idle' },
        task_sys: { active_tasks: [] },
        tracks: { items: [] },
        im: { target: { identity_id: 'act-design-old', role_id: 'design' } },
      },
    }));
    await refresh;

    assert.equal(state.selectedActorId, 'act-pm-new');
    assert.equal(state.actorConsole, null);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('selected actor runtime drives existing lifecycle controls', () => {
  const state = app.createState();
  app.applyActorConsolePayload(state, {
    console: {
      actor: { actor_id: 'act-pm-demo', role: 'pm' },
      runtime: {
        status: 'active',
        app_server_health: 'healthy',
        thread_id: 'thread-main',
        thread_status: 'idle',
      },
      task: { task_state: 'none' },
      tracks: { items: [] },
      im: { target: { identity: { id: 'act-pm-demo', type: 'actor' }, identity_id: 'act-pm-demo', role_id: 'pm' } },
    },
  });

  assert.deepEqual(
    app.computeInstanceActionState(app.selectedActorRuntime(state), {
      draftText: 'ping',
      sendPending: false,
      lifecycleOperation: null,
    }),
    {
      canSend: true,
      canInterrupt: false,
      canStop: true,
      canDelete: false,
      canClear: true,
      canResume: false,
    }
  );
});

test('action state explains why clear is disabled', () => {
  assert.equal(
    app.describeInstanceActionState(null, {
      draftText: '',
      sendPending: false,
      lifecycleOperation: null,
    }).clearReason,
    'Select an actor.'
  );
  assert.equal(
    app.describeInstanceActionState(
      {
        status: 'active',
        app_server_health: 'healthy',
        thread: { status: 'in_progress' },
      },
      {
        draftText: '',
        sendPending: false,
        lifecycleOperation: null,
      }
    ).clearReason,
    'Thread running.'
  );
  assert.equal(
    app.describeInstanceActionState(
      {
        status: 'active',
        app_server_health: 'healthy',
        thread: { status: 'idle' },
      },
      {
        draftText: '',
        sendPending: false,
        lifecycleOperation: null,
      }
    ).clearReason,
    ''
  );
});

test('lifecycle operation disables conflicting actor actions without disabling send', () => {
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
        lifecycleOperation: lifecycleOperation({
          action: 'clear',
          status: 'running',
          target: { actor_id: 'act-market-demo', role: 'market' },
        }),
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

test('queued lifecycle operation protects selected actor controls without blocking send', () => {
  const actionState = app.describeInstanceActionState(
    {
      status: 'active',
      app_server_health: 'healthy',
      thread: { status: 'idle' },
    },
    {
      draftText: 'keep typing',
      sendPending: false,
      lifecycleOperation: lifecycleOperation({
        action: 'stop',
        status: 'queued',
        label: 'Stopping act-market-demo',
        detail: 'Waiting for lifecycle queue.',
        target: { actor_id: 'act-market-demo', role: 'market' },
      }),
    }
  );

  assert.equal(actionState.canSend, true);
  assert.equal(actionState.canStop, false);
  assert.equal(actionState.canClear, false);
  assert.equal(actionState.canResume, false);
  assert.match(actionState.lifecycleStatus, /Waiting for lifecycle queue/);
  assert.equal(actionState.clearReason, 'Stopping act-market-demo.');
  assert.equal(
    actionState.lifecycleProtectionStatus,
    'Stop queued. Other lifecycle actions are protected until Stop completes.'
  );
});

test('action state describes active lifecycle operation with action-specific text', () => {
  const actionState = app.describeInstanceActionState(
    {
      status: 'active',
      app_server_health: 'healthy',
      thread: { status: 'idle' },
    },
    {
      draftText: '',
      sendPending: false,
      lifecycleOperation: lifecycleOperation({
        action: 'clear',
        status: 'running',
        label: 'Clearing thread for act-market-demo',
      }),
    }
  );

  assert.equal(actionState.clearReason, 'Clearing thread for act-market-demo.');
  assert.match(actionState.lifecycleStatus, /Clearing thread for act-market-demo/);
  assert.equal(
    actionState.lifecycleProtectionStatus,
    'Clear in progress. Other lifecycle actions are protected until Clear completes.'
  );
});

test('rendered actions describe lifecycle protection instead of a single disabled button', () => {
  const state = app.createState();
  const elements = createRenderElements();
  state.selectedActorId = 'act-market-demo';
  state.actors = [
    {
      actor_id: 'act-market-demo',
      role: 'market',
      runtime: {
        status: 'active',
        app_server_health: 'healthy',
        thread: { status: 'idle' },
      },
    },
  ];
  app.recordLifecycleOperation(state, lifecycleOperation({
    action: 'stop',
    status: 'running',
    label: 'Stopping act-market-demo',
    target: { actor_id: 'act-market-demo', role: 'market' },
  }));

  app.renderSelectedActorContext(state, elements);

  assert.equal(
    elements.actionAvailabilityStatus.textContent,
    'Stop in progress. Other lifecycle actions are protected until Stop completes.'
  );
  assert.equal(elements.stopButton.textContent, 'Stopping...');
  assert.equal(elements.clearButton.disabled, true);
  assert.equal(elements.resumeButton.disabled, true);
});

test('selected actor console refresh is limited to visible actor workspace', () => {
  const state = app.createState();
  state.selectedSection = 'actors';
  state.selectedActorId = 'act-market-demo';

  assert.equal(app.shouldRefreshSelectedActorConsole(state, { documentHidden: false }), true);
  assert.equal(app.shouldRefreshSelectedActorConsole(state, { documentHidden: true }), false);

  state.selectedSection = 'tracks';
  assert.equal(app.shouldRefreshSelectedActorConsole(state, { documentHidden: false }), false);

  state.selectedSection = 'actors';
  state.selectedActorId = '';
  assert.equal(app.shouldRefreshSelectedActorConsole(state, { documentHidden: false }), false);
});

test('web product route builders target coarse phase-two APIs only', () => {
  assert.equal(app.buildActorConsoleUrl('act-pm-demo'), '/api/actors/act-pm-demo/console');
  assert.equal(app.buildTrackDetailUrl('track-alpha'), '/api/tracks/track-alpha');
});

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

test('renderComposer updates the input and send button without actor list writes', () => {
  const state = app.createState();
  const elements = createRenderElements();
  state.draftText = 'ping';
  state.actors = [
    {
      actor_id: 'act-market-demo',
      role: 'market',
      runtime: { status: 'active', app_server_health: 'healthy' },
    },
  ];
  state.selectedActorId = 'act-market-demo';
  state.actorConsole = {
    actor: { actor_id: 'act-market-demo', role: 'market' },
    runtime: { status: 'active', app_server_health: 'healthy', thread_status: 'idle' },
  };
  elements.actorsList.innerHTML = 'unchanged';
  elements.stopButton.textContent = 'lifecycle-owned';

  app.renderComposer(state, elements);

  assert.equal(elements.instructionInput.value, 'ping');
  assert.equal(elements.sendButton.disabled, false);
  assert.equal(elements.actorsList.innerHTML, 'unchanged');
  assert.equal(elements.stopButton.textContent, 'lifecycle-owned');
});

test('no selection disables all instance actions', () => {
  assert.deepEqual(
    app.computeInstanceActionState(null, {
      draftText: 'Advance the brief',
      sendPending: false,
      lifecycleOperation: null,
    }),
    {
      canSend: false,
      canInterrupt: false,
      canStop: false,
      canDelete: false,
      canClear: false,
      canResume: false,
    }
  );
});

test('active healthy instance allows send, stop, and clear, but not delete', () => {
  assert.deepEqual(
    app.computeInstanceActionState(
      {
        status: 'active',
        app_server_health: 'healthy',
        thread: { status: 'idle' },
      },
      {
        draftText: 'Advance the brief',
        sendPending: false,
        lifecycleOperation: null,
      }
    ),
    {
      canSend: true,
      canInterrupt: false,
      canStop: true,
      canDelete: false,
      canClear: true,
      canResume: false,
    }
  );
});

test('active in-progress instance enables interrupt and still allows steering input', () => {
  assert.deepEqual(
    app.computeInstanceActionState(
      {
        status: 'active',
        app_server_health: 'healthy',
        thread: { status: 'in_progress' },
      },
      {
        draftText: 'Refine the plan',
        sendPending: false,
        lifecycleOperation: null,
      }
    ),
    {
      canSend: true,
      canInterrupt: true,
      canStop: true,
      canDelete: false,
      canClear: false,
      canResume: false,
    }
  );
});

test('active app-server thread enables interrupt and still allows steering input', () => {
  assert.deepEqual(
    app.computeInstanceActionState(
      {
        status: 'active',
        app_server_health: 'healthy',
        thread: { status: 'active' },
      },
      {
        draftText: 'Refine the plan',
        sendPending: false,
        lifecycleOperation: null,
      }
    ),
    {
      canSend: true,
      canInterrupt: true,
      canStop: true,
      canDelete: false,
      canClear: false,
      canResume: false,
    }
  );
});

test('inactive instance allows resume and delete only', () => {
  assert.deepEqual(
    app.computeInstanceActionState(
      {
        status: 'inactive',
        app_server_health: 'unhealthy',
        thread: { status: 'stopped' },
      },
      {
        draftText: 'Advance the brief',
        sendPending: false,
        lifecycleOperation: null,
      }
    ),
    {
      canSend: false,
      canInterrupt: false,
      canStop: false,
      canDelete: true,
      canClear: false,
      canResume: true,
    }
  );
});

test('send pending disables only send while preserving independent actor controls', () => {
  assert.deepEqual(
    app.computeInstanceActionState(
      {
        status: 'active',
        app_server_health: 'healthy',
        thread: { status: 'idle' },
      },
      {
        draftText: 'Advance the brief',
        sendPending: true,
        lifecycleOperation: null,
      }
    ),
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

test('active lifecycle operation disables lifecycle buttons without disabling send', () => {
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
        lifecycleOperation: lifecycleOperation({
          action: 'clear',
          status: 'running',
          target: { actor_id: 'act-market-demo', role: 'market' },
        }),
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

test('active idle instance allows clear even without draft text', () => {
  assert.deepEqual(
    app.computeInstanceActionState(
      {
        status: 'active',
        app_server_health: 'healthy',
        thread: { status: 'idle' },
      },
      {
        draftText: '',
        sendPending: false,
        lifecycleOperation: null,
      }
    ),
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

test('active in-progress instance disables clear while allowing interrupt', () => {
  assert.deepEqual(
    app.computeInstanceActionState(
      {
        status: 'active',
        app_server_health: 'healthy',
        thread: { status: 'in_progress' },
      },
      {
        draftText: 'Steer',
        sendPending: false,
        lifecycleOperation: null,
      }
    ),
    {
      canSend: true,
      canInterrupt: true,
      canStop: true,
      canDelete: false,
      canClear: false,
      canResume: false,
    }
  );
});

test('open tui is disabled without a selected instance', () => {
  assert.deepEqual(
    app.computeOpenTuiState(null, { openTuiPending: false }),
    {
      canOpenTui: false,
      message: '',
    }
  );
});

test('active healthy instance with a thread enables open tui', () => {
  assert.deepEqual(
    app.computeOpenTuiState(
      {
        status: 'active',
        app_server_health: 'healthy',
        thread_id: 'thread-main',
      },
      { openTuiPending: false }
    ),
    {
      canOpenTui: true,
      message: '',
    }
  );
});

test('inactive instance tells user to resume before opening tui', () => {
  assert.deepEqual(
    app.computeOpenTuiState(
      {
        status: 'inactive',
        app_server_health: 'unhealthy',
        thread_id: 'thread-main',
      },
      { openTuiPending: false }
    ),
    {
      canOpenTui: false,
      message: 'Resume this actor first.',
    }
  );
});

test('unhealthy instance blocks open tui', () => {
  assert.deepEqual(
    app.computeOpenTuiState(
      {
        status: 'active',
        app_server_health: 'unhealthy',
        thread_id: 'thread-main',
      },
      { openTuiPending: false }
    ),
    {
      canOpenTui: false,
      message: 'Actor runtime is unhealthy.',
    }
  );
});

test('missing thread blocks open tui', () => {
  assert.deepEqual(
    app.computeOpenTuiState(
      {
        status: 'active',
        app_server_health: 'healthy',
        thread_id: null,
      },
      { openTuiPending: false }
    ),
    {
      canOpenTui: false,
      message: 'No thread to attach.',
    }
  );
});

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

test('im event URL is external-session-wide with bounded wait only', () => {
  assert.equal(
    app.buildImEventsUrl(15000),
    '/api/im/events?wait_ms=15000'
  );
});

test('im conversation URL targets selected actor through unified im route', () => {
  assert.equal(
    app.buildImConversationUrl('act-market demo', 20),
    '/api/im/conversations/direct?identity_id=act-market%20demo&limit=20'
  );
});

test('im message URL fetches an individual message through unified im route', () => {
  assert.equal(app.buildImMessageUrl('msg demo/1'), '/api/im/messages/msg%20demo%2F1');
});

test('im ack payload uses explicit event id only', () => {
  assert.deepEqual(app.buildImAckPayload('imev-1'), { event_id: 'imev-1' });
});

test('record sent IM message keeps compact delivery status', () => {
  const state = app.createState();
  app.recordImSent(state, {
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
});

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

test('failed pending send is removed and draft can be restored by caller', () => {
  const state = app.createState();
  const pendingId = app.recordImPendingSend(state, 'ping');

  app.removeImEntry(state, pendingId);

  assert.deepEqual(state.imConversation, []);
  assert.equal(state.imSeenMessageIds[pendingId], undefined);
});

test('record projected IM messages keeps sent and reply directions', () => {
  const state = app.createState();
  const sentEcho = app.recordImProjectedMessage(state, imMessage({
    id: 'msg-sent-1',
    sender: 'ext-1',
    target: 'act-market-1',
    content: 'ping',
  }));
  const actorReply = app.recordImProjectedMessage(state, imMessage({
    id: 'msg-reply-1',
    sender: 'act-market-1',
    target: 'ext-1',
    content: 'pong',
    replyTo: 'msg-sent-1',
  }));

  assert.equal(sentEcho, true);
  assert.equal(actorReply, true);
  assert.deepEqual(state.imConversation, [
    {
      id: 'msg-sent-1',
      direction: 'sent',
      sender: 'you',
      content: 'ping',
      deliveryStatus: '',
      wakeStatus: '',
      replyTo: '',
    },
    {
      id: 'msg-reply-1',
      direction: 'reply',
      sender: 'market/act-market-1',
      content: 'pong',
      deliveryStatus: '',
      wakeStatus: '',
      replyTo: 'msg-sent-1',
    },
  ]);
});

test('clearing im conversation records owner identity and removes stale rows', () => {
  const state = app.createState();
  app.recordImProjectedMessage(state, imMessage({
    id: 'msg-stale',
    sender: 'act-market-old',
    target: 'ext-web',
    content: 'stale',
  }));

  app.clearImConversation(state, 'act-market-new');

  assert.equal(state.imConversationIdentityId, 'act-market-new');
  assert.deepEqual(state.imConversation, []);
  assert.deepEqual(state.imSeenMessageIds, {});
});

test('direct conversation payload replaces local render cache with persisted history', () => {
  const state = app.createState();
  app.recordImSent(state, {
    message: { id: 'msg-stale' },
    delivery_status: 'accepted',
    wake_status: 'submitted',
  }, 'stale');

  app.applyImConversationPayload(state, {
    messages: [
      imMessage({
        id: 'msg-sent-1',
        sender: 'ext-web',
        target: 'act-market-1',
        content: 'ping',
      }),
      imMessage({
        id: 'msg-reply-1',
        sender: 'act-market-1',
        target: 'ext-web',
        content: 'pong',
        replyTo: 'msg-sent-1',
      }),
    ],
  }, 'act-market-1');

  assert.equal(state.imConversationIdentityId, 'act-market-1');
  assert.deepEqual(state.imConversation.map((entry) => [entry.id, entry.direction, entry.content]), [
    ['msg-sent-1', 'sent', 'ping'],
    ['msg-reply-1', 'reply', 'pong'],
  ]);
  assert.deepEqual(Object.keys(state.imSeenMessageIds).sort(), ['msg-reply-1', 'msg-sent-1']);
});

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
    app.recordImProjectedMessage(state, imMessage({
      id: 'msg-stale',
      sender: 'act-market-old',
      target: 'ext-web',
      content: 'stale',
    }));

    await app.refreshSelectedActorConversation(state);

    assert.equal(state.imConversationIdentityId, 'act-market-empty');
    assert.deepEqual(state.imConversation, []);
    assert.deepEqual(state.imSeenMessageIds, {});
    assert.equal(state.message, '');
  } finally {
    global.fetch = originalFetch;
  }
});

test('fetched im message appends projected reply without browser cursor state', () => {
  const state = app.createState();

  app.recordImProjectedMessage(state, imMessage({
    id: 'msg-reply-1',
    sender: 'act-market-1',
    target: 'ext-web',
    content: 'pong',
  }));

  assert.equal(Object.prototype.hasOwnProperty.call(state, 'imEventCursor'), false);
  assert.deepEqual(state.imConversation.map((entry) => [entry.id, entry.direction, entry.content]), [
    ['msg-reply-1', 'reply', 'pong'],
  ]);
});

test('external-session-wide fetched event messages only append when they touch selected actor', () => {
  const state = app.createState();
  state.selectedActorId = 'act-market-selected';
  state.imConversationIdentityId = 'act-market-selected';

  const offScopeRecorded = app.recordSelectedActorEventMessage(
    state,
    imMessage({
      id: 'msg-dev',
      sender: 'act-dev-other',
      target: 'ext-web',
      content: 'dev pong',
    }),
    'act-market-selected'
  );

  const selectedRecorded = app.recordSelectedActorEventMessage(
    state,
    imMessage({
      id: 'msg-market',
      sender: 'act-market-selected',
      target: 'ext-web',
      content: 'market pong',
    }),
    'act-market-selected'
  );

  assert.equal(offScopeRecorded, false);
  assert.equal(selectedRecorded, true);
  assert.deepEqual(state.imConversation.map((entry) => [entry.id, entry.content]), [
    ['msg-market', 'market pong'],
  ]);
});

test('polling external-session-wide events acks off-selected actor message without rendering it', async () => {
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
            message: imMessage({
              id: 'msg-dev',
              sender: 'act-dev-other',
              target: 'ext-web',
              content: 'dev pong',
            }),
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

test('actor task summary renders task sys execution relation contract', async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/actors/act-task/console') {
      return Promise.resolve(okResponse({
        console: {
          actor: { actor_id: 'act-task', role: 'dev' },
          runtime: { status: 'active', app_server_health: 'healthy', thread: { status: 'idle' } },
          task_sys: {
            active_count: 1,
            recoverable_count: 1,
            active_tasks: [
              {
                task_id: 'task-ui-current',
                source_type: 'test.ui',
                status: 'in_progress',
                task_desc: 'Draft brief',
                task_relation: { kind: 'after', target_task_id: 'task-ui-prior' },
                execution: { processor: 'side', handoff: null, result: null },
              },
            ],
            recoverable_tasks: [
              {
                task_id: 'task-ui-failed',
                source_type: 'test.ui',
                status: 'in_progress',
                task_desc: 'Retry brief',
                task_relation: { kind: 'independent', target_task_id: null },
                execution: {
                  processor: null,
                  handoff: null,
                  result: { type: 'failure', reason: 'runtime_failed' },
                },
              },
            ],
          },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-task', role_id: 'dev' } },
        },
      }));
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-task&limit=50') {
      return Promise.resolve(imNotFoundResponse());
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [
      { actor_id: 'act-task', role: 'dev', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];

    await app.selectActor(state, elements, 'act-task');

    assert.match(elements.actorTaskSummary.innerHTML, /Draft brief/);
    assert.match(elements.actorTaskSummary.innerHTML, /side/);
    assert.match(elements.actorTaskSummary.innerHTML, /after/);
    assert.match(elements.actorTaskSummary.innerHTML, /task-ui-prior/);
    assert.match(elements.actorTaskSummary.innerHTML, /runtime_failed/);
    assert.doesNotMatch(elements.actorTaskSummary.innerHTML, /active_processor/);
    assert.doesNotMatch(elements.actorTaskSummary.innerHTML, /failure_result/);
    if (state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('active WebUI sources do not carry retired lifecycle feedback residue', () => {
  const root = path.join(__dirname, '..');
  const sources = [
    path.join(root, 'tools', 'launcher', 'assets', 'web-management', 'app.js'),
    path.join(root, 'tools', 'launcher', 'assets', 'web-management', 'index.html'),
    path.join(root, 'tests', 'web_management_ui_contract.test.js'),
  ].map((filePath) => fs.readFileSync(filePath, 'utf8')).join('\n');
  const retiredMarkers = [
    'lifecycle' + 'PendingAction',
    'Action ' + 'completed.',
    'clear ' + 'running',
    'confirm' + 'ing',
  ];
  retiredMarkers.forEach((marker) => {
    assert.equal(sources.includes(marker), false, 'retired lifecycle residue found: ' + marker);
  });
});
