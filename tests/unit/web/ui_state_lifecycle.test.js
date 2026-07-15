'use strict';

const { test } = require('node:test');
const { assert, fs, path, rendererModule, MarkdownIt, app, identityRef, imMessage, deferred, okResponse, lifecycleOperation, imNotFoundResponse, waitFor, createRenderElements } = require('./ui_state_harness');

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

test('stale interrupt response cannot mutate or keep pending on a newer actor selection', async () => {
  const originalFetch = globalThis.fetch;
  const interruptResponse = deferred();
  globalThis.fetch = async function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/instances/act-interrupt-a/interrupt') {
      return interruptResponse.promise;
    }
    if (requestUrl === '/api/actors/act-interrupt-b/console') {
      return okResponse({
        console: {
          actor: { actor_id: 'act-interrupt-b', role: 'pm' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-b', thread_status: 'idle' },
          task_sys: { active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-interrupt-b', role_id: 'pm' } },
        },
      });
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-interrupt-b&limit=50') {
      return imNotFoundResponse();
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [
      { actor_id: 'act-interrupt-a', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
      { actor_id: 'act-interrupt-b', role: 'pm', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];
    state.selectedActorId = 'act-interrupt-a';
    state.actorConsole = {
      actor: { actor_id: 'act-interrupt-a', role: 'market' },
      runtime: { status: 'active', app_server_health: 'healthy', thread_status: 'in_progress' },
    };

    const interrupt = app.runInterruptAction(state, elements);
    await waitFor(() => state.interruptPending, 'A interrupt pending');
    await app.selectActor(state, elements, 'act-interrupt-b');

    assert.equal(state.interruptPending, false);
    interruptResponse.resolve(okResponse({ turn_id: 'turn-a' }));
    await interrupt;

    assert.equal(state.selectedActorId, 'act-interrupt-b');
    assert.equal(state.message, '');
    assert.equal(state.openTuiMessage, '');
    assert.equal(state.interruptPending, false);
    if (state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
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
    assert.equal(state.actorConsole.actor.actor_id, 'act-other-demo');
    assert.equal(state.imConversationIdentityId, 'act-other-demo');
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

test('stale lifecycle submission cannot clear attach tool feedback for a newer actor selection', async () => {
  const originalFetch = globalThis.fetch;
  const stopResponse = deferred();
  globalThis.fetch = async function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/instances/act-lifecycle-a/stop') {
      return stopResponse.promise;
    }
    if (requestUrl === '/api/actors/act-lifecycle-b/console') {
      return okResponse({
        console: {
          actor: { actor_id: 'act-lifecycle-b', role: 'pm' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-b', thread_status: 'idle' },
          task_sys: { active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-lifecycle-b', role_id: 'pm' } },
        },
      });
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-lifecycle-b&limit=50') {
      return imNotFoundResponse();
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [
      { actor_id: 'act-lifecycle-a', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
      { actor_id: 'act-lifecycle-b', role: 'pm', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];
    state.selectedActorId = 'act-lifecycle-a';
    state.actorConsole = {
      actor: { actor_id: 'act-lifecycle-a', role: 'market' },
      runtime: { status: 'active', app_server_health: 'healthy', thread_status: 'idle' },
    };
    state.lifecycleOperationPollDelaysMs = [];

    const stop = app.runLifecycleAction(state, elements, 'stop', 'act-lifecycle-a');
    await app.selectActor(state, elements, 'act-lifecycle-b');
    state.openTuiMessage = 'Launch sent to Terminal.';
    state.copyCommandMessage = 'Command copied.';

    stopResponse.resolve(okResponse({
      operation: lifecycleOperation({
        id: 'op-stop-lifecycle-a',
        action: 'stop',
        status: 'running',
        label: 'Stopping act-lifecycle-a',
        target: { actor_id: 'act-lifecycle-a', role: 'market' },
      }),
    }));
    await stop;

    assert.equal(state.selectedActorId, 'act-lifecycle-b');
    assert.equal(state.openTuiMessage, 'Launch sent to Terminal.');
    assert.equal(state.copyCommandMessage, 'Command copied.');
    assert.ok(state.lifecycleOperations['op-stop-lifecycle-a']);
    if (state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('delete roster failure leaves selection clear and never selects from stale local roster', async () => {
  const originalFetch = globalThis.fetch;
  let staleActorConsoleCalls = 0;
  globalThis.fetch = async function (url, options) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/instances/act-delete-roster-error') {
      assert.equal(options && options.method, 'DELETE');
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-delete-roster-error',
          action: 'delete',
          status: 'running',
          label: 'Deleting act-delete-roster-error',
          target: { actor_id: 'act-delete-roster-error', role: 'market' },
        }),
      });
    }
    if (requestUrl === '/api/operations/op-delete-roster-error') {
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-delete-roster-error',
          action: 'delete',
          status: 'succeeded',
          label: 'Deleting act-delete-roster-error',
          target: { actor_id: 'act-delete-roster-error', role: 'market' },
          result: { ok: true, actor_id: 'act-delete-roster-error' },
        }),
      });
    }
    if (requestUrl === '/api/actors') {
      return {
        ok: false,
        json: async function () {
          return { ok: false, error: { code: 'E_ROSTER', message: 'Authoritative roster unavailable' } };
        },
      };
    }
    if (requestUrl === '/api/actors/act-stale-local/console') {
      staleActorConsoleCalls += 1;
      return okResponse({});
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [
      { actor_id: 'act-delete-roster-error', role: 'market', runtime: { status: 'inactive', app_server_health: 'unhealthy' } },
      { actor_id: 'act-stale-local', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];
    state.selectedActorId = 'act-delete-roster-error';
    state.actorConsole = { actor: { actor_id: 'act-delete-roster-error', role: 'market' } };
    state.imConversationIdentityId = 'act-delete-roster-error';
    state.lifecycleOperationPollDelaysMs = [];

    await app.runLifecycleAction(state, elements, 'delete', state.selectedActorId);
    await app.pollLifecycleOperations(state, elements);

    assert.equal(state.selectedActorId, '');
    assert.equal(state.actorConsole, null);
    assert.equal(state.imConversationIdentityId, '');
    assert.equal(staleActorConsoleCalls, 0);
    assert.match(elements.messageBanner.textContent, /Authoritative roster unavailable/);
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
  state.selectedActorId = 'act-pm-demo';
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

test('inactive instance tells user to resume before attach tools are available', () => {
  assert.deepEqual(
    app.computeAttachActionState({
      status: 'inactive',
      app_server_health: 'unhealthy',
      thread_id: 'thread-main',
    }),
    {
      canAttach: false,
      message: 'Resume this actor first.',
    }
  );
});

test('active WebUI sources do not carry retired lifecycle feedback residue', () => {
  const root = path.resolve(__dirname, '..', '..', '..');
  const sources = [
    path.join(root, 'tools', 'launcher', 'assets', 'web-management', 'app.js'),
    path.join(root, 'tools', 'launcher', 'assets', 'web-management', 'index.html'),
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
