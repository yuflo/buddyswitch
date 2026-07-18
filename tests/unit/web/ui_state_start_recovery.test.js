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

function actor(actorId, role, lifecycleState, status, health) {
  return {
    actor_id: actorId,
    role,
    lifecycle_state: lifecycleState,
    last_failure: lifecycleState === 'start_failed'
      ? { phase: 'daemon_start', message: 'Daemon start failed.' }
      : null,
    runtime: {
      status,
      app_server_health: health || '',
      thread_status: 'idle',
    },
  };
}

function rowHtml(html, actorId) {
  const marker = 'data-actor-id="' + actorId + '"';
  const start = html.indexOf(marker);
  assert.notEqual(start, -1, 'expected row for ' + actorId);
  const rowStart = html.lastIndexOf('<button', start);
  const rowEnd = html.indexOf('</button>', start);
  return html.slice(rowStart, rowEnd + '</button>'.length);
}

test('lifecycle_state alone groups one actor row across start recovery states', () => {
  const state = app.createState();
  state.roles = [
    { id: 'dev', label: 'Dev' },
    { id: 'pm', label: 'PM' },
  ];
  state.rosterStoppedExpanded = true;
  state.actors = [
    actor('act-dev-starting', 'dev', 'starting', 'inactive', 'healthy'),
    actor('act-dev-retrying', 'dev', 'retrying', 'inactive', 'healthy'),
    actor('act-dev-active', 'dev', 'active', 'active', 'healthy'),
    actor('act-pm-failed', 'pm', 'start_failed', 'inactive', 'healthy'),
    actor('act-pm-stopped', 'pm', 'stopped', 'inactive', 'unhealthy'),
  ];

  const html = app.renderActorRowsHtml(state);

  assert.match(html, /data-roster-group="starting"/);
  assert.match(html, />Starting<[^]*>2</);
  assert.match(html, /data-roster-group="active"/);
  assert.match(html, />Active<[^]*>1</);
  assert.match(html, /data-roster-group="needs-attention"/);
  assert.match(html, />Needs attention<[^]*>1</);
  assert.match(html, /data-roster-group="stopped"/);
  assert.match(rowHtml(html, 'act-dev-starting'), /starting/);
  assert.match(rowHtml(html, 'act-dev-retrying'), /retrying/);
  assert.match(rowHtml(html, 'act-pm-failed'), /status-badge danger[^>]*>start failed/);
  assert.doesNotMatch(rowHtml(html, 'act-dev-starting'), /healthy|unhealthy|class="dot/);
  assert.doesNotMatch(rowHtml(html, 'act-dev-retrying'), /healthy|unhealthy|class="dot/);
  assert.doesNotMatch(html, /data-operation-id|op-start|op-retry/);
});

test('one active Start operation never reclassifies unrelated actors with absent Retry ids', () => {
  const state = app.createState();
  state.roles = [
    { id: 'dev', label: 'Dev' },
    { id: 'market', label: 'Market' },
    { id: 'test', label: 'Test' },
  ];
  state.actors = [
    actor('act-dev-existing', 'dev', 'active', 'active', 'healthy'),
    actor('act-market-existing', 'market', 'active', 'active', 'healthy'),
    actor('act-test-starting', 'test', 'starting', 'inactive', ''),
  ];
  app.recordLifecycleOperation(state, lifecycleOperation({
    id: 'op-start-test-only',
    action: 'start',
    status: 'running',
    target: { actor_id: 'act-test-starting', role: 'test' },
  }));

  const html = app.renderActorRowsHtml(state);

  assert.match(html, />Starting<[^]*>1</);
  assert.match(html, />Active<[^]*>2</);
  assert.match(rowHtml(html, 'act-dev-existing'), />active</);
  assert.match(rowHtml(html, 'act-market-existing'), />active</);
  assert.match(rowHtml(html, 'act-test-starting'), />starting</);
});

test('starting retrying and failed selections never fetch identity-backed surfaces', async () => {
  const originalFetch = globalThis.fetch;
  const fetchCalls = [];
  globalThis.fetch = async function (url) {
    fetchCalls.push(String(url));
    throw new Error('identity-backed request must not run');
  };

  try {
    for (const lifecycleState of ['starting', 'retrying', 'start_failed']) {
      const state = app.createState();
      const elements = createRenderElements();
      const actorId = 'act-dev-' + lifecycleState;
      state.actors = [actor(actorId, 'dev', lifecycleState, 'inactive', '')];

      await app.selectActor(state, elements, actorId);

      assert.equal(state.selectedActorId, actorId);
      assert.equal(state.actorSelectionPendingId, '');
      assert.equal(state.actorCardLoading, false);
      assert.equal(state.conversationLoading, false);
      if (lifecycleState === 'starting') {
        assert.match(elements.actorRuntimeDetail.innerHTML, /Starting actor/);
      } else if (lifecycleState === 'retrying') {
        assert.match(elements.actorRuntimeDetail.innerHTML, /Retrying actor/);
      } else {
        assert.match(elements.actorRuntimeDetail.innerHTML, /Start failed/);
        assert.match(elements.actorRuntimeDetail.innerHTML, /Daemon start failed/);
      }
    }
    assert.deepEqual(fetchCalls, []);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('start failure exposes Retry and Delete only while stopped retains Resume and Delete', () => {
  assert.deepEqual(
    app.computeInstanceActionState({
      lifecycle_state: 'start_failed',
      status: 'inactive',
      app_server_health: '',
      thread: { status: '' },
    }, {}),
    {
      canSend: false,
      canInterrupt: false,
      canStop: false,
      canDelete: true,
      canClear: false,
      canResume: false,
      canRetry: true,
    }
  );
  const stopped = app.computeInstanceActionState({
    lifecycle_state: 'stopped',
    status: 'inactive',
    app_server_health: '',
    thread: { status: '' },
  }, {});
  assert.equal(stopped.canResume, true);
  assert.equal(stopped.canDelete, true);
  assert.equal(stopped.canRetry, false);
  for (const lifecycleState of ['starting', 'retrying']) {
    const actionState = app.computeInstanceActionState({
      lifecycle_state: lifecycleState,
      status: 'inactive',
      thread: { status: '' },
    }, {});
    assert.equal(Object.values(actionState).some(Boolean), false);
  }
});

test('start failure guidance names Retry or Delete and never tells the user to Resume', () => {
  const failedRuntime = {
    lifecycle_state: 'start_failed',
    status: 'inactive',
    app_server_health: '',
    thread_id: null,
    thread: { status: '' },
  };

  const lifecycleState = app.describeInstanceActionState(failedRuntime, {});
  const attachState = app.computeAttachActionState(failedRuntime);

  assert.equal(lifecycleState.clearReason, 'Retry or delete this actor.');
  assert.equal(attachState.message, 'Retry or delete this actor.');
  assert.doesNotMatch(lifecycleState.clearReason + attachState.message, /Resume/);
  for (const lifecycleStateName of ['starting', 'retrying']) {
    const pendingAttachState = app.computeAttachActionState({
      lifecycle_state: lifecycleStateName,
      status: 'inactive',
      app_server_health: '',
      thread_id: null,
    });
    assert.equal(pendingAttachState.message, 'Available after startup completes.');
  }
});

test('Retry posts once without confirmation and turns the selected failed row into retrying', async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async function (url, options) {
    calls.push([String(url), options && options.method]);
    return okResponse({
      operation: lifecycleOperation({
        id: 'op-retry-demo',
        action: 'retry',
        status: 'running',
        label: 'Retrying dev',
        target: {
          actor_id: 'act-dev-failed',
          replacement_actor_id: 'act-dev-replacement',
          role: 'dev',
        },
      }),
    });
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [actor('act-dev-failed', 'dev', 'start_failed', 'inactive', '')];
    state.selectedActorId = 'act-dev-failed';
    state.lifecycleOperationPollDelaysMs = [];

    await app.runLifecycleAction(state, elements, 'retry', state.selectedActorId);

    assert.deepEqual(calls, [['/api/instances/act-dev-failed/retry', 'POST']]);
    assert.equal(state.deleteConfirmationActorId, '');
    assert.equal(state.lifecycleOperations['op-retry-demo'].action, 'retry');
    assert.match(rowHtml(elements.actorsList.innerHTML, 'act-dev-failed'), /retrying/);
    assert.match(elements.actorRuntimeDetail.innerHTML, /Retrying actor/);
    assert.doesNotMatch(elements.actorRuntimeDetail.innerHTML, /Start failed/);
    assert.equal(elements.retryButton.disabled, true);
    assert.equal(elements.deleteButton.disabled, true);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('authoritative roster refresh resumes polling an already-running Start operation', async () => {
  const originalFetch = globalThis.fetch;
  const runningStart = lifecycleOperation({
    id: 'op-start-restored',
    action: 'start',
    status: 'running',
    label: 'Starting dev',
    target: { actor_id: 'act-dev-restored', role: 'dev' },
  });
  globalThis.fetch = async function (url) {
    const requestUrl = String(url);
    if (requestUrl === '/api/health') return okResponse({});
    if (requestUrl === '/api/roles') return okResponse({ roles: [{ id: 'dev', label: 'Dev' }] });
    if (requestUrl === '/api/tracks') return okResponse({ tracks: [] });
    if (requestUrl === '/api/actors') {
      const startingActor = actor('act-dev-restored', 'dev', 'starting', 'inactive', '');
      startingActor.lifecycle_operation = runningStart;
      return okResponse({ actors: [startingActor] });
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  const state = app.createState();
  const elements = createRenderElements();
  state.lifecycleOperationPollDelaysMs = [60_000];
  try {
    await app.refreshVisibleRegionsWithFeedback(state, elements);

    assert.equal(state.selectedActorId, 'act-dev-restored');
    assert.equal(state.lifecycleOperations['op-start-restored'].status, 'running');
    assert.notEqual(state.lifecycleOperationPollTimer, null);
  } finally {
    if (state.lifecycleOperationPollTimer) {
      clearTimeout(state.lifecycleOperationPollTimer);
    }
    globalThis.fetch = originalFetch;
  }
});

test('manual refresh of a selected Start failed actor does not fetch identity-backed surfaces', async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  const failedActor = actor('act-dev-refresh-failed', 'dev', 'start_failed', 'inactive', '');
  globalThis.fetch = async function (url) {
    const requestUrl = String(url);
    calls.push(requestUrl);
    if (requestUrl === '/api/health') return okResponse({});
    if (requestUrl === '/api/roles') return okResponse({ roles: [{ id: 'dev', label: 'Dev' }] });
    if (requestUrl === '/api/tracks') return okResponse({ tracks: [] });
    if (requestUrl === '/api/actors') return okResponse({ actors: [failedActor] });
    throw new Error('identity-backed request must not run: ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [failedActor];
    state.selectedActorId = failedActor.actor_id;

    await app.refreshVisibleRegionsWithFeedback(state, elements);

    assert.equal(state.selectedActorId, failedActor.actor_id);
    assert.equal(calls.some((url) => url.includes('/console') || url.includes('/conversations/')), false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

function retryOperation(status, overrides) {
  return lifecycleOperation(Object.assign({
    id: 'op-retry-terminal',
    action: 'retry',
    status,
    label: 'Retrying dev',
    target: {
      actor_id: 'act-dev-failed',
      replacement_actor_id: 'act-dev-replacement',
      role: 'dev',
    },
  }, overrides || {}));
}

function activeReplacementActor() {
  return actor('act-dev-replacement', 'dev', 'active', 'active', 'healthy');
}

function replacementConsoleResponse() {
  return okResponse({
    console: {
      actor: { actor_id: 'act-dev-replacement', role: 'dev' },
      runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-new', thread_status: 'idle' },
      task_sys: { active_tasks: [] },
      tracks: { items: [] },
      im: { target: { identity_id: 'act-dev-replacement', role_id: 'dev' } },
    },
  });
}

test('active Retry transfers the one selected row from previous id to published replacement id', async () => {
  const originalFetch = globalThis.fetch;
  let operationCalls = 0;
  globalThis.fetch = async function (url) {
    const requestUrl = String(url);
    if (requestUrl === '/api/instances/act-dev-failed/retry') {
      return okResponse({ operation: retryOperation('running') });
    }
    if (requestUrl === '/api/operations/op-retry-terminal') {
      operationCalls += 1;
      return okResponse({ operation: retryOperation('running') });
    }
    if (requestUrl === '/api/actors') {
      const replacement = actor('act-dev-replacement', 'dev', 'retrying', 'inactive', '');
      replacement.previous_actor_id = 'act-dev-failed';
      replacement.lifecycle_operation = retryOperation('running');
      return okResponse({ actors: [replacement] });
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [actor('act-dev-failed', 'dev', 'start_failed', 'inactive', '')];
    state.selectedActorId = 'act-dev-failed';
    state.lifecycleOperationPollDelaysMs = [];

    await app.runLifecycleAction(state, elements, 'retry', state.selectedActorId);
    await app.pollLifecycleOperations(state, elements);

    assert.equal(operationCalls, 1);
    assert.equal(state.selectedActorId, 'act-dev-replacement');
    assert.deepEqual(state.actors.map((row) => row.actor_id), ['act-dev-replacement']);
    assert.equal(state.actors[0].lifecycle_state, 'retrying');
    assert.equal(state.actorConsole, null);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('successful Retry selects one Active replacement and loads its identity only after readiness', async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async function (url) {
    const requestUrl = String(url);
    calls.push(requestUrl);
    if (requestUrl === '/api/instances/act-dev-failed/retry') {
      return okResponse({ operation: retryOperation('running') });
    }
    if (requestUrl === '/api/operations/op-retry-terminal') {
      return okResponse({
        operation: retryOperation('succeeded', {
          result: {
            ok: true,
            previous_actor_id: 'act-dev-failed',
            actor_id: 'act-dev-replacement',
          },
        }),
      });
    }
    if (requestUrl === '/api/actors') {
      return okResponse({ actors: [activeReplacementActor()] });
    }
    if (requestUrl === '/api/actors/act-dev-replacement/console') {
      return replacementConsoleResponse();
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-dev-replacement&limit=50') {
      return imNotFoundResponse();
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [actor('act-dev-failed', 'dev', 'start_failed', 'inactive', '')];
    state.selectedActorId = 'act-dev-failed';
    state.lifecycleOperationPollDelaysMs = [];

    await app.runLifecycleAction(state, elements, 'retry', state.selectedActorId);
    assert.equal(calls.filter((url) => url.includes('/console') || url.includes('/conversations/')).length, 0);
    await app.pollLifecycleOperations(state, elements);

    assert.equal(state.selectedActorId, 'act-dev-replacement');
    assert.deepEqual(state.actors.map((row) => row.actor_id), ['act-dev-replacement']);
    assert.equal(state.actors[0].lifecycle_state, 'active');
    assert.equal(state.actorConsole.actor.actor_id, 'act-dev-replacement');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('published replacement failure leaves one replacement Start failed row with Retry and Delete', async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async function (url) {
    const requestUrl = String(url);
    calls.push(requestUrl);
    if (requestUrl === '/api/instances/act-dev-failed/retry') {
      return okResponse({ operation: retryOperation('running') });
    }
    if (requestUrl === '/api/operations/op-retry-terminal') {
      return okResponse({
        operation: retryOperation('failed', {
          error: { code: 'COMMAND_FAILED', message: 'Replacement daemon failed.' },
        }),
      });
    }
    if (requestUrl === '/api/actors') {
      return okResponse({ actors: [actor('act-dev-replacement', 'dev', 'start_failed', 'inactive', '')] });
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [actor('act-dev-failed', 'dev', 'start_failed', 'inactive', '')];
    state.selectedActorId = 'act-dev-failed';
    state.lifecycleOperationPollDelaysMs = [];

    await app.runLifecycleAction(state, elements, 'retry', state.selectedActorId);
    await app.pollLifecycleOperations(state, elements);

    assert.equal(state.selectedActorId, 'act-dev-replacement');
    assert.deepEqual(state.actors.map((row) => row.actor_id), ['act-dev-replacement']);
    assert.equal(elements.retryButton.hidden, false);
    assert.equal(elements.retryButton.disabled, false);
    assert.equal(elements.deleteButton.disabled, false);
    assert.equal(elements.resumeButton.hidden, true);
    assert.equal(calls.filter((url) => url.includes('/console') || url.includes('/conversations/')).length, 0);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('unpublished replacement failure removes the failed attempt and preserves the same selected role', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async function (url) {
    const requestUrl = String(url);
    if (requestUrl === '/api/instances/act-dev-failed/retry') {
      return okResponse({ operation: retryOperation('running') });
    }
    if (requestUrl === '/api/operations/op-retry-terminal') {
      return okResponse({
        operation: retryOperation('failed', {
          error: { code: 'COMMAND_FAILED', message: 'Replacement failed before publication.' },
        }),
      });
    }
    if (requestUrl === '/api/actors') {
      return okResponse({ actors: [] });
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.selectedRole = 'dev';
    state.actors = [actor('act-dev-failed', 'dev', 'start_failed', 'inactive', '')];
    state.selectedActorId = 'act-dev-failed';
    state.lifecycleOperationPollDelaysMs = [];

    await app.runLifecycleAction(state, elements, 'retry', state.selectedActorId);
    await app.pollLifecycleOperations(state, elements);

    assert.equal(state.selectedRole, 'dev');
    assert.equal(state.selectedActorId, '');
    assert.deepEqual(state.actors, []);
    assert.match(elements.messageBanner.textContent, /Replacement failed before publication/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
