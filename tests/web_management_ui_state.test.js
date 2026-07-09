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
    actorRuntimeDetail: node(),
    actorTaskSummary: node(),
    actorTrackSummary: node(),
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

test('actor model config render edits request payload without response metadata', () => {
  const state = app.createState();
  const elements = createRenderElements();
  state.selectedActorId = 'act-pm-demo';
  state.actorConsole = {
    actor: { actor_id: 'act-pm-demo', role: 'pm' },
    model_config: {
      schema_version: 1,
      parent: { model: null, effort: null },
      side: { model: null, effort: null },
      allowed_efforts: ['minimal', 'low', 'medium', 'high', 'ultra'],
      effects: { parent: 'next submit', side: 'new side threads' },
    },
  };

  app.renderActorModelConfig(state, elements);

  assert.match(elements.actorModelConfigPayload.value, /"parent"/);
  assert.doesNotMatch(elements.actorModelConfigPayload.value, /schema_version|allowed_efforts|effects/);
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

test('actor model config console refresh preserves open dirty draft', () => {
  const state = app.createState();
  state.actorModelConfigPanelOpen = true;
  state.actorModelConfigSavedText = JSON.stringify({ parent: {}, side: {} }, null, 2);
  state.actorModelConfigDraftText = JSON.stringify({ future: { effort: 'warp' } }, null, 2);
  state.actorConsole = {
    model_config: {
      parent: { model: 'server-model', effort: 'low' },
      side: {},
    },
  };

  app.syncActorModelConfigFromConsole(state);

  assert.match(state.actorModelConfigDraftText, /"future"/);
  assert.doesNotMatch(state.actorModelConfigDraftText, /server-model/);
});

test('actor model config console refresh preserves an open clean panel', () => {
  const state = app.createState();
  state.actorModelConfigPanelOpen = true;
  state.actorModelConfigSavedText = JSON.stringify({ parent: {}, side: {} }, null, 2);
  state.actorModelConfigDraftText = state.actorModelConfigSavedText;
  state.actorConsole = {
    model_config: {
      parent: { model: null, effort: null },
      side: { model: null, effort: null },
    },
  };

  app.syncActorModelConfigFromConsole(state);

  assert.equal(state.actorModelConfigPanelOpen, true);
});

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

test('actor model config render enables save for valid unsaved future payload', () => {
  const state = app.createState();
  const elements = createRenderElements();
  state.actorModelConfigPanelOpen = true;
  state.actorModelConfigSavedText = JSON.stringify({ parent: {}, side: {} }, null, 2);
  app.recordActorModelConfigDraft(state, '{"future":{"effort":"warp"}}');

  app.renderActorModelConfig(state, elements);

  assert.equal(elements.actorModelConfigStatus.textContent, 'Unsaved');
  assert.equal(elements.actorModelConfigSave.disabled, false);
  assert.equal(elements.actorModelConfigMessage.textContent, 'Unsaved payload.');
});

test('actor model config revert returns to saved payload', () => {
  const state = app.createState();
  state.actorModelConfigSavedText = JSON.stringify({ parent: { model: 'gpt-5.4', effort: 'high' }, side: {} }, null, 2);
  state.actorModelConfigDraftText = '{"future": true}';

  app.revertActorModelConfigDraft(state);

  assert.equal(state.actorModelConfigDraftText, state.actorModelConfigSavedText);
  assert.equal(state.actorModelConfigError, '');
});

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
    assert.equal(state.rosterPendingActorId, 'act-market-new');
    assert.match(elements.actorsList.innerHTML, /act-market-new/);
    assert.match(elements.actorsList.innerHTML, /pending|initializing/i);

    await waitFor(() => state.rosterPendingActorId === '', 'roster confirmation');

    assert.equal(state.selectedActorId, 'act-market-new');
    assert.equal(state.rosterPendingActorId, '');
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
    assert.equal(state.rosterPendingActorId, '');
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
    assert.equal(state.rosterPendingActorId, 'act-market-late');
    assert.match(elements.actorsList.innerHTML, /act-market-late/);
    assert.match(elements.actorsList.innerHTML, /initializing/);

    await app.refreshVisibleRegionsWithFeedback(state, elements);

    assert.equal(state.selectedActorId, 'act-market-late');
    assert.equal(state.rosterPendingActorId, '');
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

    await app.runLifecycleAction(state, elements, 'clear');

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

    await app.runLifecycleAction(state, elements, 'delete');

    assert.match(elements.actorsList.innerHTML, /deleting/);
    assert.equal(elements.deleteButton.textContent, 'Deleting...');
    assert.match(elements.lifecycleOperationStatus.textContent, /Deleting act-delete-demo/);

    await app.pollLifecycleOperations(state, elements);

    assert.deepEqual(state.lifecycleOperations, {});
    assert.equal(state.selectedActorId, '');
    assert.deepEqual(state.actors.map((actor) => actor.actor_id), ['act-other-demo']);
    assert.match(elements.messageBanner.textContent, /Deleting act-delete-demo completed/);
    assert.doesNotMatch(elements.actorsList.innerHTML, /act-delete-demo/);
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

    await app.runLifecycleAction(state, elements, 'stop');
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

    await app.runLifecycleAction(state, elements, 'clear');

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
      () => /act-roster-new/.test(elements.actorsList.innerHTML) && /Status/.test(elements.actorRuntimeDetail.innerHTML),
      'progressive roster and card render before conversation resolves',
      200
    );

    try {
      assert.match(elements.actorsList.innerHTML, /act-roster-new/);
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

  app.renderComposer(state, elements);

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

  app.renderComposer(state, elements);

  assert.equal(elements.instructionInput.value, 'ping');
  assert.equal(elements.sendButton.disabled, false);
  assert.equal(elements.actorsList.innerHTML, 'unchanged');
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
