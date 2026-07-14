'use strict';

const { test } = require('node:test');
const { assert, fs, path, rendererModule, MarkdownIt, app, identityRef, imMessage, deferred, okResponse, lifecycleOperation, imNotFoundResponse, waitFor, createRenderElements } = require('./ui_state_harness');

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

test('create teammate keeps pending actor visible until roster reconciliation', async () => {
  const originalFetch = globalThis.fetch;
  const originalDocument = globalThis.document;
  const originalSetTimeout = globalThis.setTimeout;
  let actorRosterCalls = 0;
  let actorRefreshSchedules = 0;
  let state;
  globalThis.document = { hidden: false };
  globalThis.setTimeout = function (callback, delay, ...args) {
    if (delay === 3000) {
      actorRefreshSchedules += 1;
    }
    return originalSetTimeout(callback, delay, ...args);
  };
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
    state = app.createState();
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
    await waitFor(
      () => state.actorSelectionPendingId === '',
      'created actor selection settlement'
    );

    assert.equal(state.selectedActorId, 'act-market-new');
    assert.equal(state.actorSelectionPendingId, '');
    assert.equal(app.shouldRefreshSelectedActorConsole(state, { documentHidden: false }), true);
    assert.ok(state.actorRefreshTimer);
    assert.equal(actorRefreshSchedules, 1);
    assert.deepEqual(state.rosterPendingActors, {});
    assert.match(elements.actorsList.innerHTML, /act-market-new/);
    assert.doesNotMatch(elements.actorsList.innerHTML, /pending|initializing/i);
  } finally {
    if (state && state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
    globalThis.fetch = originalFetch;
    globalThis.document = originalDocument;
    globalThis.setTimeout = originalSetTimeout;
  }
});

test('created actor roster reconciliation starts while selected actor projection is still loading', async () => {
  const originalFetch = globalThis.fetch;
  const originalSetTimeout = globalThis.setTimeout;
  const consoleResponse = deferred();
  let actorRosterCalls = 0;
  let state;
  globalThis.setTimeout = function (callback, delay, ...args) {
    if (delay === 0) {
      Promise.resolve().then(callback);
      return 1;
    }
    return originalSetTimeout(callback, delay, ...args);
  };
  globalThis.fetch = async function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/operations/op-start-projection-slow') {
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-start-projection-slow',
          action: 'start',
          status: 'succeeded',
          label: 'Starting Market',
          target: { actor_id: 'act-projection-slow', role: 'market' },
          result: { ok: true, actor_id: 'act-projection-slow' },
        }),
      });
    }
    if (requestUrl === '/api/actors/act-projection-slow/console') {
      return consoleResponse.promise;
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-projection-slow&limit=50') {
      return imNotFoundResponse();
    }
    if (requestUrl === '/api/actors') {
      actorRosterCalls += 1;
      return okResponse({
        actors: [
          { actor_id: 'act-projection-slow', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
        ],
      });
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    state = app.createState();
    const elements = createRenderElements();
    state.lifecycleOperationPollDelaysMs = [];
    state.rosterReconcileDelaysMs = [0];
    state.selectedLifecycleOperationId = 'op-start-projection-slow';
    app.recordLifecycleOperation(state, lifecycleOperation({
      id: 'op-start-projection-slow',
      action: 'start',
      status: 'running',
      label: 'Starting Market',
      target: { actor_id: '', role: 'market' },
    }));

    const poll = app.pollLifecycleOperations(state, elements);
    await waitFor(() => actorRosterCalls === 1, 'created actor roster confirmation while selection is loading');

    assert.equal(state.selectedActorId, 'act-projection-slow');
    assert.equal(state.actorSelectionPendingId, 'act-projection-slow');
    assert.deepEqual(state.rosterPendingActors, {});

    consoleResponse.resolve(okResponse({
      console: {
        actor: { actor_id: 'act-projection-slow', role: 'market' },
        runtime: { status: 'active', app_server_health: 'healthy', thread_status: 'idle' },
        task_sys: { active_tasks: [] },
        tracks: { items: [] },
        im: { target: { identity_id: 'act-projection-slow', role_id: 'market' } },
      },
    }));
    await poll;
  } finally {
    if (state && state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
    globalThis.fetch = originalFetch;
    globalThis.setTimeout = originalSetTimeout;
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
    if (requestUrl === '/api/actors/act-market-old/console') {
      return okResponse({
        console: {
          actor: { actor_id: 'act-market-old', role: 'market' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-old', thread_status: 'idle' },
          task_sys: { active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-market-old', role_id: 'market' } },
        },
      });
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-market-old&limit=50') {
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

    await app.createInstance(state, elements);

    assert.equal(state.selectedActorId, '');
    assert.equal(state.selectedLifecycleOperationId, 'op-start-failed');
    assert.match(elements.actorsList.innerHTML, /Starting Market/);

    await app.pollLifecycleOperations(state, elements);

    assert.equal(state.selectedActorId, 'act-market-old');
    assert.equal(state.actorConsole.actor.actor_id, 'act-market-old');
    assert.equal(state.imConversationIdentityId, 'act-market-old');
    assert.deepEqual(state.imConversation, []);
    assert.equal(state.actorSelectionPendingId, '');
    assert.equal(state.selectedLifecycleOperationId, '');
    assert.deepEqual(state.lifecycleOperations, {});
    assert.doesNotMatch(elements.actorsList.innerHTML, /Starting Market/);
    assert.match(elements.messageBanner.textContent, /Thread bootstrap failed/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
