'use strict';

const { test } = require('node:test');
const { assert, fs, path, rendererModule, MarkdownIt, app, identityRef, imMessage, deferred, okResponse, lifecycleOperation, imNotFoundResponse, waitFor, createRenderElements } = require('./ui_state_harness');

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

test('stale open tui response cannot write into a newer actor selection', async () => {
  const originalFetch = globalThis.fetch;
  const openTuiResponse = deferred();
  globalThis.fetch = async function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/instances/act-tui-a/open-tui') {
      return openTuiResponse.promise;
    }
    if (requestUrl === '/api/actors/act-tui-b/console') {
      return okResponse({
        console: {
          actor: { actor_id: 'act-tui-b', role: 'pm' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-b', thread_status: 'idle' },
          task_sys: { active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-tui-b', role_id: 'pm' } },
        },
      });
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-tui-b&limit=50') {
      return imNotFoundResponse();
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [
      { actor_id: 'act-tui-a', role: 'market', runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-a' } },
      { actor_id: 'act-tui-b', role: 'pm', runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-b' } },
    ];
    state.selectedActorId = 'act-tui-a';
    state.actorConsole = {
      actor: { actor_id: 'act-tui-a', role: 'market' },
      runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-a', thread_status: 'idle' },
    };

    const opening = app.openTui(state, elements);
    assert.equal(state.openTuiPending, true);

    await app.selectActor(state, elements, 'act-tui-b');
    assert.equal(state.openTuiPending, false);

    openTuiResponse.resolve(okResponse({ terminal: 'Terminal.app' }));
    await opening;

    assert.equal(state.selectedActorId, 'act-tui-b');
    assert.equal(state.openTuiPending, false);
    assert.equal(state.openTuiMessage, '');
    if (state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('copy command fetches and copies independently from open tui', async () => {
  const originalFetch = globalThis.fetch;
  const originalNavigatorDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
  const copied = [];
  const requests = [];
  Object.defineProperty(globalThis, 'navigator', {
    configurable: true,
    value: { clipboard: { writeText: async function (value) { copied.push(value); } } },
  });
  globalThis.fetch = async function (url, options) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    requests.push({ url: requestUrl, options: options });
    if (requestUrl === '/api/instances/act-copy-a/attach-command') {
      return okResponse({
        command: "cd '/tmp/Buddy Switch' && ./buddyswitch-codex instance attach act-copy-a",
      });
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [
      { actor_id: 'act-copy-a', role: 'market', runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-a' } },
    ];
    state.selectedActorId = 'act-copy-a';
    state.openTuiPending = true;
    state.openTuiMessage = 'Opening...';

    await app.copyAttachCommand(state, elements);

    assert.deepEqual(requests, [
      { url: '/api/instances/act-copy-a/attach-command', options: undefined },
    ]);
    assert.deepEqual(copied, [
      "cd '/tmp/Buddy Switch' && ./buddyswitch-codex instance attach act-copy-a",
    ]);
    assert.equal(state.copyCommandPending, false);
    assert.equal(state.copyCommandMessage, 'Command copied.');
    assert.equal(state.openTuiPending, true);
    assert.equal(state.openTuiMessage, 'Opening...');
  } finally {
    globalThis.fetch = originalFetch;
    if (originalNavigatorDescriptor) {
      Object.defineProperty(globalThis, 'navigator', originalNavigatorDescriptor);
    } else {
      delete globalThis.navigator;
    }
  }
});

test('stale copy command response cannot copy or write feedback into a newer actor selection', async () => {
  const originalFetch = globalThis.fetch;
  const originalNavigatorDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
  const attachCommandResponse = deferred();
  const copied = [];
  Object.defineProperty(globalThis, 'navigator', {
    configurable: true,
    value: { clipboard: { writeText: async function (value) { copied.push(value); } } },
  });
  globalThis.fetch = async function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/instances/act-copy-a/attach-command') {
      return attachCommandResponse.promise;
    }
    if (requestUrl === '/api/actors/act-copy-b/console') {
      return okResponse({
        console: {
          actor: { actor_id: 'act-copy-b', role: 'pm' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-b', thread_status: 'idle' },
          task_sys: { active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-copy-b', role_id: 'pm' } },
        },
      });
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-copy-b&limit=50') {
      return imNotFoundResponse();
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [
      { actor_id: 'act-copy-a', role: 'market', runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-a' } },
      { actor_id: 'act-copy-b', role: 'pm', runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-b' } },
    ];
    state.selectedActorId = 'act-copy-a';

    const copying = app.copyAttachCommand(state, elements);
    assert.equal(state.copyCommandPending, true);
    await app.selectActor(state, elements, 'act-copy-b');
    attachCommandResponse.resolve(okResponse({
      command: './buddyswitch-codex instance attach act-copy-a',
    }));
    await copying;

    assert.deepEqual(copied, []);
    assert.equal(state.copyCommandPending, false);
    assert.equal(state.copyCommandMessage, '');
    if (state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
  } finally {
    globalThis.fetch = originalFetch;
    if (originalNavigatorDescriptor) {
      Object.defineProperty(globalThis, 'navigator', originalNavigatorDescriptor);
    } else {
      delete globalThis.navigator;
    }
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

test('deleting final actor clears projection and invalidates prior selection generation', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async function (url, options) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/instances/act-final') {
      assert.equal(options && options.method, 'DELETE');
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-delete-final',
          action: 'delete',
          status: 'running',
          label: 'Deleting act-final',
          target: { actor_id: 'act-final', role: 'market' },
        }),
      });
    }
    if (requestUrl === '/api/operations/op-delete-final') {
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-delete-final',
          action: 'delete',
          status: 'succeeded',
          label: 'Deleting act-final',
          target: { actor_id: 'act-final', role: 'market' },
          result: { ok: true, actor_id: 'act-final' },
        }),
      });
    }
    if (requestUrl === '/api/actors') return okResponse({ actors: [] });
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [
      { actor_id: 'act-final', role: 'market', runtime: { status: 'inactive', app_server_health: 'unhealthy' } },
    ];
    state.selectedActorId = 'act-final';
    state.actorConsole = { actor: { actor_id: 'act-final', role: 'market' } };
    state.imConversationIdentityId = 'act-final';
    state.lifecycleOperationPollDelaysMs = [];
    const requestId = state.actorSelectionRequestId;

    await app.runLifecycleAction(state, elements, 'delete', state.selectedActorId);
    await app.pollLifecycleOperations(state, elements);

    assert.deepEqual(state.actors, []);
    assert.equal(state.selectedActorId, '');
    assert.equal(state.actorConsole, null);
    assert.equal(state.imConversationIdentityId, '');
    assert.equal(state.actorSelectionRequestId, requestId + 1);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('manual refresh explicitly selects and loads preferred actor when selection is missing', async () => {
  const originalFetch = globalThis.fetch;
  let missingActorRequested = false;
  globalThis.fetch = async function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/health') {
      return okResponse({});
    }
    if (requestUrl === '/api/roles') {
      return okResponse({ roles: [{ id: 'market', label: 'Market' }] });
    }
    if (requestUrl === '/api/actors') {
      return okResponse({
        actors: [
          { actor_id: 'act-stopped', role: 'dev', runtime: { status: 'inactive', app_server_health: 'unhealthy' } },
          { actor_id: 'act-preferred', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
        ],
      });
    }
    if (requestUrl === '/api/tracks') {
      return okResponse({ tracks: [] });
    }
    if (requestUrl === '/api/actors/act-missing/console') {
      missingActorRequested = true;
      return okResponse({ console: { actor: { actor_id: 'act-missing', role: 'market' } } });
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-missing&limit=50') {
      return imNotFoundResponse();
    }
    if (requestUrl === '/api/actors/act-preferred/console') {
      return okResponse({
        console: {
          actor: { actor_id: 'act-preferred', role: 'market' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-preferred', thread_status: 'idle' },
          task_sys: { active_count: 0, active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-preferred', role_id: 'market' } },
        },
      });
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-preferred&limit=50') {
      return imNotFoundResponse();
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.selectedActorId = 'act-missing';
    state.actors = [
      { actor_id: 'act-missing', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];

    await app.refreshVisibleRegionsWithFeedback(state, elements);

    assert.equal(missingActorRequested, false);
    assert.equal(state.selectedActorId, 'act-preferred');
    assert.equal(state.actorConsole.actor.actor_id, 'act-preferred');
    assert.equal(state.actorSelectionPendingId, '');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('manual refresh selects stopped-only fallback and expands stopped roster', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/health') return okResponse({});
    if (requestUrl === '/api/roles') return okResponse({ roles: [{ id: 'pm', label: 'PM' }] });
    if (requestUrl === '/api/actors') {
      return okResponse({
        actors: [
          { actor_id: 'act-stopped-only', role: 'pm', runtime: { status: 'inactive', app_server_health: 'unhealthy' } },
        ],
      });
    }
    if (requestUrl === '/api/tracks') return okResponse({ tracks: [] });
    if (requestUrl === '/api/actors/act-stopped-only/console') {
      return okResponse({
        console: {
          actor: { actor_id: 'act-stopped-only', role: 'pm' },
          runtime: { status: 'inactive', app_server_health: 'unhealthy', thread_id: 'thread-stopped', thread_status: 'idle' },
          task_sys: { active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-stopped-only', role_id: 'pm' } },
        },
      });
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-stopped-only&limit=50') {
      return imNotFoundResponse();
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();

    await app.refreshVisibleRegionsWithFeedback(state, elements);

    assert.equal(state.selectedActorId, 'act-stopped-only');
    assert.equal(state.rosterStoppedExpanded, true);
    assert.match(elements.actorsList.innerHTML, /data-actor-id="act-stopped-only"[^>]*aria-selected="true"/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('manual refresh clears actor projection when authoritative roster is empty', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/health') return okResponse({});
    if (requestUrl === '/api/roles') return okResponse({ roles: [] });
    if (requestUrl === '/api/actors') return okResponse({ actors: [] });
    if (requestUrl === '/api/tracks') return okResponse({ tracks: [] });
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.selectedActorId = 'act-removed';
    state.actorConsole = { actor: { actor_id: 'act-removed', role: 'market' } };
    state.imConversationIdentityId = 'act-removed';
    state.imConversation = [{ id: 'msg-stale', direction: 'reply', content: 'stale' }];
    const requestId = state.actorSelectionRequestId;

    await app.refreshVisibleRegionsWithFeedback(state, elements);

    assert.equal(state.selectedActorId, '');
    assert.equal(state.actorConsole, null);
    assert.equal(state.imConversationIdentityId, '');
    assert.deepEqual(state.imConversation, []);
    assert.equal(state.actorSelectionRequestId, requestId + 1);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('manual refresh restarts a pending actor selection instead of sharing its generation', async () => {
  const originalFetch = globalThis.fetch;
  const staleInitialConsole = deferred();
  let actorConsoleCalls = 0;
  globalThis.fetch = async function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/health') return okResponse({});
    if (requestUrl === '/api/roles') return okResponse({ roles: [{ id: 'market', label: 'Market' }] });
    if (requestUrl === '/api/actors') {
      return okResponse({
        actors: [
          { actor_id: 'act-pending', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
        ],
      });
    }
    if (requestUrl === '/api/tracks') return okResponse({ tracks: [] });
    if (requestUrl === '/api/actors/act-pending/console') {
      actorConsoleCalls += 1;
      if (actorConsoleCalls === 1) return staleInitialConsole.promise;
      return okResponse({
        console: {
          actor: { actor_id: 'act-pending', role: 'market' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-fresh', thread_status: 'idle' },
          task_sys: { active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-pending', role_id: 'market' } },
        },
      });
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-pending&limit=50') {
      return imNotFoundResponse();
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [
      { actor_id: 'act-pending', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];

    const initialSelection = app.selectActor(state, elements, 'act-pending');
    await waitFor(() => state.actorSelectionPendingId === 'act-pending', 'pending actor selection');
    const initialRequestId = state.actorSelectionRequestId;

    await app.refreshVisibleRegionsWithFeedback(state, elements);

    assert.equal(actorConsoleCalls, 2);
    assert.equal(state.actorSelectionRequestId, initialRequestId + 1);
    assert.equal(state.actorConsole.runtime.thread_id, 'thread-fresh');

    staleInitialConsole.resolve(okResponse({
      console: {
        actor: { actor_id: 'act-pending', role: 'market' },
        runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-stale', thread_status: 'idle' },
        task_sys: { active_tasks: [] },
        tracks: { items: [] },
        im: { target: { identity_id: 'act-pending', role_id: 'market' } },
      },
    }));
    await initialSelection;

    assert.equal(state.actorConsole.runtime.thread_id, 'thread-fresh');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('manual refresh wins over an older same-generation console refresh', async () => {
  const originalFetch = globalThis.fetch;
  const staleConsole = deferred();
  let actorConsoleCalls = 0;
  globalThis.fetch = async function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/health') return okResponse({});
    if (requestUrl === '/api/roles') return okResponse({ roles: [{ id: 'market', label: 'Market' }] });
    if (requestUrl === '/api/actors') {
      return okResponse({
        actors: [
          { actor_id: 'act-stable', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
        ],
      });
    }
    if (requestUrl === '/api/tracks') return okResponse({ tracks: [] });
    if (requestUrl === '/api/actors/act-stable/console') {
      actorConsoleCalls += 1;
      if (actorConsoleCalls === 1) return staleConsole.promise;
      return okResponse({
        console: {
          actor: { actor_id: 'act-stable', role: 'market' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-manual-fresh', thread_status: 'idle' },
          task_sys: { active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-stable', role_id: 'market' } },
        },
      });
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-stable&limit=50') {
      return imNotFoundResponse();
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [
      { actor_id: 'act-stable', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];
    state.selectedActorId = 'act-stable';
    state.actorConsole = {
      actor: { actor_id: 'act-stable', role: 'market' },
      runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-initial', thread_status: 'idle' },
    };

    const staleRefresh = app.refreshSelectedActorConsoleAndRender(state, elements);
    await app.refreshVisibleRegionsWithFeedback(state, elements);
    assert.equal(state.actorConsole.runtime.thread_id, 'thread-manual-fresh');

    staleConsole.resolve(okResponse({
      console: {
        actor: { actor_id: 'act-stable', role: 'market' },
        runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-auto-stale', thread_status: 'idle' },
        task_sys: { active_tasks: [] },
        tracks: { items: [] },
        im: { target: { identity_id: 'act-stable', role_id: 'market' } },
      },
    }));
    await staleRefresh;

    assert.equal(state.actorConsole.runtime.thread_id, 'thread-manual-fresh');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('rapid actor switching keeps the latest selected teammate visible', async () => {
  const originalFetch = globalThis.fetch;
  let firstConsoleSignal;
  let firstConversationSignal;
  let resolveFirst;
  let resolveSecond;
  const first = new Promise((resolve) => { resolveFirst = resolve; });
  const second = new Promise((resolve) => { resolveSecond = resolve; });

  globalThis.fetch = function (url, options) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/actors/act-first/console') {
      firstConsoleSignal = options && options.signal;
      return first;
    }
    if (requestUrl === '/api/actors/act-second/console') {
      return second;
    }
    if (requestUrl.startsWith('/api/im/conversations/direct')) {
      if (requestUrl.indexOf('identity_id=act-first') >= 0) {
        firstConversationSignal = options && options.signal;
      }
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
    assert.equal(firstConsoleSignal.aborted, false);
    assert.equal(firstConversationSignal.aborted, false);
    const secondSelection = app.selectActor(state, elements, 'act-second');
    assert.equal(firstConsoleSignal.aborted, true);
    assert.equal(firstConversationSignal.aborted, true);

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
    assert.equal(state.actorSelectionPendingId, '');
    assert.equal(state.actorCardLoading, false);
    assert.equal(state.conversationLoading, false);
    if (state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('stale actor console refresh cannot cross an A to B to A selection generation', async () => {
  const originalFetch = globalThis.fetch;
  const staleAConsole = deferred();
  let actorAConsoleCalls = 0;
  globalThis.fetch = async function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/actors/act-a/console') {
      actorAConsoleCalls += 1;
      if (actorAConsoleCalls === 1) {
        return staleAConsole.promise;
      }
      return okResponse({
        console: {
          actor: { actor_id: 'act-a', role: 'market' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-a-fresh', thread_status: 'idle' },
          task_sys: { active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-a', role_id: 'market' } },
        },
      });
    }
    if (requestUrl === '/api/actors/act-b/console') {
      return okResponse({
        console: {
          actor: { actor_id: 'act-b', role: 'dev' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-b', thread_status: 'idle' },
          task_sys: { active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-b', role_id: 'dev' } },
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
    state.actors = [
      { actor_id: 'act-a', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
      { actor_id: 'act-b', role: 'dev', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];
    state.selectedActorId = 'act-a';
    state.actorConsole = {
      actor: { actor_id: 'act-a', role: 'market' },
      runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-a-initial', thread_status: 'idle' },
    };

    const staleRefresh = app.refreshSelectedActorConsoleAndRender(state, elements);
    await app.selectActor(state, elements, 'act-b');
    await app.selectActor(state, elements, 'act-a');

    assert.equal(state.actorConsole.runtime.thread_id, 'thread-a-fresh');

    staleAConsole.resolve(okResponse({
      console: {
        actor: { actor_id: 'act-a', role: 'market' },
        runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-a-stale', thread_status: 'idle' },
        task_sys: { active_tasks: [] },
        tracks: { items: [] },
        im: { target: { identity_id: 'act-a', role_id: 'market' } },
      },
    }));
    await staleRefresh;

    assert.equal(state.selectedActorId, 'act-a');
    assert.equal(state.actorConsole.runtime.thread_id, 'thread-a-fresh');
  } finally {
    globalThis.fetch = originalFetch;
  }
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
