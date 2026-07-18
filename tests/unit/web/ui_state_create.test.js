'use strict';

const { test } = require('node:test');
const {
  assert,
  app,
  createRenderElements,
  lifecycleOperation,
  okResponse,
  imNotFoundResponse,
} = require('./ui_state_harness');

function actor(actorId, lifecycleState, status) {
  return {
    actor_id: actorId,
    role: 'market',
    lifecycle_state: lifecycleState,
    last_failure: lifecycleState === 'start_failed'
      ? { phase: 'daemon_start', message: 'Daemon start failed.' }
      : null,
    runtime: {
      status,
      app_server_health: status === 'active' ? 'healthy' : '',
      thread_status: 'idle',
    },
  };
}

function startOperation(actorId, status, overrides) {
  return lifecycleOperation(Object.assign({
    id: 'op-start-' + actorId,
    action: 'start',
    status,
    label: 'Starting Market',
    target: { actor_id: actorId, role: 'market' },
  }, overrides || {}));
}

function consoleResponse(actorId) {
  return okResponse({
    console: {
      actor: { actor_id: actorId, role: 'market' },
      runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-' + actorId, thread_status: 'idle' },
      task_sys: { active_tasks: [] },
      tracks: { items: [] },
      im: { target: { identity_id: actorId, role_id: 'market' } },
    },
  });
}

test('create teammate immediately selects one Starting actor row with the owner-issued id', async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async function (url, options) {
    calls.push([String(url), options && options.method]);
    return okResponse({ operation: startOperation('act-market-new', 'running') });
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.roles = [{ id: 'market', label: 'Market' }];
    state.selectedRole = 'market';
    state.lifecycleOperationPollDelaysMs = [];

    await app.createInstance(state, elements);

    assert.deepEqual(calls, [['/api/instances', 'POST']]);
    assert.equal(state.selectedActorId, 'act-market-new');
    assert.equal(state.actors.length, 1);
    assert.equal(state.actors[0].lifecycle_state, 'starting');
    assert.match(elements.actorsList.innerHTML, /data-actor-id="act-market-new"/);
    assert.match(elements.actorsList.innerHTML, /starting/);
    assert.doesNotMatch(elements.actorsList.innerHTML, /data-operation-id|op-start-act-market-new/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('parallel Start responses remain separate actor attempts without operation rows', async () => {
  const originalFetch = globalThis.fetch;
  let createCount = 0;
  globalThis.fetch = async function (url) {
    assert.equal(String(url), '/api/instances');
    createCount += 1;
    return okResponse({ operation: startOperation('act-market-' + createCount, createCount === 1 ? 'running' : 'queued') });
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.roles = [{ id: 'market', label: 'Market' }];
    state.selectedRole = 'market';
    state.lifecycleOperationPollDelaysMs = [];

    await app.createInstance(state, elements);
    await app.createInstance(state, elements);

    assert.deepEqual(state.actors.map((row) => row.actor_id), ['act-market-1', 'act-market-2']);
    assert.equal(state.selectedActorId, 'act-market-2');
    assert.equal((elements.actorsList.innerHTML.match(/data-actor-id=/g) || []).length, 2);
    assert.doesNotMatch(elements.actorsList.innerHTML, /data-operation-id/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('successful Start replaces the Starting projection with one Active actor and then loads identity surfaces', async () => {
  const originalFetch = globalThis.fetch;
  const actorId = 'act-market-success';
  const calls = [];
  globalThis.fetch = async function (url) {
    const requestUrl = String(url);
    calls.push(requestUrl);
    if (requestUrl === '/api/instances') {
      return okResponse({ operation: startOperation(actorId, 'running') });
    }
    if (requestUrl === '/api/operations/op-start-' + actorId) {
      return okResponse({
        operation: startOperation(actorId, 'succeeded', {
          result: { ok: true, actor_id: actorId, instance: { actor_id: actorId, status: 'active' } },
        }),
      });
    }
    if (requestUrl === '/api/actors') {
      return okResponse({ actors: [actor(actorId, 'active', 'active')] });
    }
    if (requestUrl === '/api/actors/' + actorId + '/console') {
      return consoleResponse(actorId);
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=' + actorId + '&limit=50') {
      return imNotFoundResponse();
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.selectedRole = 'market';
    state.lifecycleOperationPollDelaysMs = [];

    await app.createInstance(state, elements);
    assert.equal(calls.filter((url) => url.includes('/console') || url.includes('/conversations/')).length, 0);
    await app.pollLifecycleOperations(state, elements);

    assert.equal(state.selectedActorId, actorId);
    assert.equal(state.actors.length, 1);
    assert.equal(state.actors[0].lifecycle_state, 'active');
    assert.equal(state.actorConsole.actor.actor_id, actorId);
    assert.equal(calls.filter((url) => url.includes('/console')).length, 1);
  } finally {
    if (globalThis.document && globalThis.document.hidden === false) {
      globalThis.document = undefined;
    }
    globalThis.fetch = originalFetch;
  }
});

test('published Start failure keeps one Start failed row selected without identity requests', async () => {
  const originalFetch = globalThis.fetch;
  const actorId = 'act-market-failed';
  const calls = [];
  globalThis.fetch = async function (url) {
    const requestUrl = String(url);
    calls.push(requestUrl);
    if (requestUrl === '/api/instances') {
      return okResponse({ operation: startOperation(actorId, 'running') });
    }
    if (requestUrl === '/api/operations/op-start-' + actorId) {
      return okResponse({
        operation: startOperation(actorId, 'failed', {
          error: { code: 'COMMAND_FAILED', message: 'Daemon start failed.' },
        }),
      });
    }
    if (requestUrl === '/api/actors') {
      return okResponse({ actors: [actor(actorId, 'start_failed', 'inactive')] });
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.selectedRole = 'market';
    state.lifecycleOperationPollDelaysMs = [];

    await app.createInstance(state, elements);
    await app.pollLifecycleOperations(state, elements);

    assert.equal(state.selectedActorId, actorId);
    assert.equal(state.actors[0].lifecycle_state, 'start_failed');
    assert.match(elements.actorsList.innerHTML, /start failed/);
    assert.equal(calls.filter((url) => url.includes('/console') || url.includes('/conversations/')).length, 0);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('unpublished Start failure removes the provisional row, retains the role, and restores a valid actor selection', async () => {
  const originalFetch = globalThis.fetch;
  const failedActorId = 'act-market-unpublished';
  const previousActorId = 'act-market-existing';
  globalThis.fetch = async function (url) {
    const requestUrl = String(url);
    if (requestUrl === '/api/instances') {
      return okResponse({ operation: startOperation(failedActorId, 'running') });
    }
    if (requestUrl === '/api/operations/op-start-' + failedActorId) {
      return okResponse({
        operation: startOperation(failedActorId, 'failed', {
          error: { code: 'COMMAND_FAILED', message: 'Failed before instance publication.' },
        }),
      });
    }
    if (requestUrl === '/api/actors') {
      return okResponse({ actors: [actor(previousActorId, 'active', 'active')] });
    }
    if (requestUrl === '/api/actors/' + previousActorId + '/console') {
      return consoleResponse(previousActorId);
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=' + previousActorId + '&limit=50') {
      return imNotFoundResponse();
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.selectedRole = 'market';
    state.actors = [actor(previousActorId, 'active', 'active')];
    state.selectedActorId = previousActorId;
    state.lifecycleOperationPollDelaysMs = [];

    await app.createInstance(state, elements);
    await app.pollLifecycleOperations(state, elements);

    assert.equal(state.selectedRole, 'market');
    assert.equal(state.selectedActorId, previousActorId);
    assert.deepEqual(state.actors.map((row) => row.actor_id), [previousActorId]);
    assert.match(elements.messageBanner.textContent, /Failed before instance publication/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
