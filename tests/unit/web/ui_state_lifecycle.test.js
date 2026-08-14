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

function actor(actorId, lifecycleState, status, health) {
  return {
    actor_id: actorId,
    role: 'market',
    lifecycle_state: lifecycleState,
    last_failure: lifecycleState === 'start_failed'
      ? { phase: 'daemon_start', message: 'Start failed.' }
      : null,
    runtime: {
      status,
      app_server_health: health,
      thread_id: 'thread-' + actorId,
      thread_status: 'idle',
    },
  };
}

function consoleResponse(actorId, status, health) {
  return okResponse({
    console: {
      actor: { actor_id: actorId, role: 'market' },
      runtime: {
        status,
        app_server_health: health,
        thread_id: 'thread-' + actorId,
        thread_status: 'idle',
      },
      task_sys: { active_tasks: [] },
      tracks: { items: [] },
      im: { target: { identity_id: actorId, role_id: 'market' } },
    },
  });
}

test('lifecycle status copy distinguishes progressive, successful, and failed phases', () => {
  const actorId = 'act-market-copy';
  const successCases = [
    ['start', 'Starting ' + actorId, 'Started ' + actorId + '.'],
    ['stop', 'Stopping ' + actorId, 'Stopped ' + actorId + '.'],
    ['resume', 'Resuming ' + actorId, 'Resumed ' + actorId + '.'],
    ['delete', 'Deleting ' + actorId, 'Deleted ' + actorId + '.'],
    ['retry', 'Retrying ' + actorId, 'Retried ' + actorId + '.'],
  ];
  for (const [action, label, expected] of successCases) {
    assert.equal(app.lifecycleOperationStatusText(lifecycleOperation({
      action,
      status: 'succeeded',
      label,
      target: { actor_id: actorId, role: 'market' },
      result: { ok: true, actor_id: actorId },
    })), expected);
  }
  assert.equal(app.lifecycleOperationStatusText(lifecycleOperation({
    action: 'clear',
    status: 'succeeded',
    label: 'Clearing thread for ' + actorId,
    target: { actor_id: actorId, role: 'market' },
    result: { ok: true, actor_id: actorId, thread_id: 'thread-cleared' },
  })), 'Cleared thread for ' + actorId + '. Thread thread-cleared.');
  assert.equal(app.lifecycleOperationStatusText(lifecycleOperation({
    action: 'stop',
    status: 'running',
    label: 'Stopping ' + actorId,
    detail: 'Launcher command is running.',
  })), 'Stopping ' + actorId + '. Launcher command is running.');
  assert.equal(app.lifecycleOperationStatusText(lifecycleOperation({
    action: 'delete',
    status: 'failed',
    label: 'Deleting ' + actorId,
    error: { code: 'DELETE_FAILED', message: 'Delete was refused.' },
  })), 'Deleting ' + actorId + ' failed: Delete was refused.');
});

test('selected actor context renders lifecycle-owned active controls', () => {
  const state = app.createState();
  const elements = createRenderElements();
  state.roles = [{ id: 'market', label: 'Market' }];
  state.actors = [actor('act-market-active', 'active', 'active', 'healthy')];
  state.selectedActorId = 'act-market-active';
  state.actorConsole = (consoleResponse('act-market-active', 'active', 'healthy'));
  state.actorConsole = {
    actor: { actor_id: 'act-market-active', role: 'market' },
    runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-main', thread_status: 'idle' },
  };

  app.renderSelectedActorContext(state, elements);

  assert.equal(elements.selectedContextId.textContent, 'act-market-active');
  assert.equal(elements.selectedContextRuntime.textContent, 'active');
  assert.equal(elements.stopButton.hidden, false);
  assert.equal(elements.stopButton.disabled, false);
  assert.equal(elements.resumeButton.hidden, true);
  assert.equal(elements.retryButton.hidden, true);
  assert.equal(elements.deleteButton.disabled, true);
  assert.equal(elements.clearButton.disabled, false);
});

test('Delete confirmation captures the exact stopped actor and sends only after exact-id confirmation', async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async function (url, options) {
    calls.push([String(url), options && options.method]);
    return okResponse({
      operation: lifecycleOperation({
        id: 'op-delete-confirmed',
        action: 'delete',
        status: 'running',
        label: 'Deleting act-market-stopped',
        target: { actor_id: 'act-market-stopped', role: 'market' },
      }),
    });
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [actor('act-market-stopped', 'stopped', 'inactive', 'unhealthy')];
    state.selectedActorId = 'act-market-stopped';
    state.lifecycleOperationPollDelaysMs = [];

    app.openDeleteConfirmation(state, elements, elements.deleteButton);
    assert.equal(calls.length, 0);
    assert.equal(state.deleteConfirmationActorId, 'act-market-stopped');
    assert.equal(elements.deleteConfirmationConfirm.disabled, true);

    app.updateDeleteConfirmationInput(state, elements, 'act-market-stopped');
    assert.equal(elements.deleteConfirmationConfirm.disabled, false);
    await app.confirmDelete(state, elements);

    assert.deepEqual(calls, [['/api/instances/act-market-stopped', 'DELETE']]);
    assert.equal(state.deleteConfirmationActorId, '');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Delete confirmation revalidates lifecycle before mutation', async () => {
  const originalFetch = globalThis.fetch;
  let fetchCount = 0;
  globalThis.fetch = async function () {
    fetchCount += 1;
    throw new Error('must not send');
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [actor('act-market-stale', 'stopped', 'inactive', 'unhealthy')];
    state.selectedActorId = 'act-market-stale';
    app.openDeleteConfirmation(state, elements, elements.deleteButton);
    app.updateDeleteConfirmationInput(state, elements, 'act-market-stale');
    state.actors[0].lifecycle_state = 'active';
    state.actors[0].runtime.status = 'active';

    await app.confirmDelete(state, elements);

    assert.equal(fetchCount, 0);
    assert.equal(state.deleteConfirmationActorId, 'act-market-stale');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Clear lifecycle operation reaches terminal state and refreshes the selected actor', async () => {
  const originalFetch = globalThis.fetch;
  const actorId = 'act-market-clear';
  globalThis.fetch = async function (url) {
    const requestUrl = String(url);
    if (requestUrl === '/api/instances/' + actorId + '/clear') {
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-clear-demo', action: 'clear', status: 'running',
          label: 'Clearing thread for ' + actorId,
          target: { actor_id: actorId, role: 'market' },
        }),
      });
    }
    if (requestUrl === '/api/operations/op-clear-demo') {
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-clear-demo', action: 'clear', status: 'succeeded',
          label: 'Clearing thread for ' + actorId,
          target: { actor_id: actorId, role: 'market' },
          result: {
            ok: true,
            thread_id: 'thread-new',
            instance: { actor_id: actorId, status: 'active', app_server_health: 'healthy', thread_id: 'thread-new' },
          },
        }),
      });
    }
    if (requestUrl === '/api/actors') {
      const row = actor(actorId, 'active', 'active', 'healthy');
      row.runtime.thread_id = 'thread-new';
      return okResponse({ actors: [row] });
    }
    if (requestUrl === '/api/actors/' + actorId + '/console') {
      return consoleResponse(actorId, 'active', 'healthy');
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [actor(actorId, 'active', 'active', 'healthy')];
    state.selectedActorId = actorId;
    state.actorConsole = { actor: { actor_id: actorId, role: 'market' }, runtime: state.actors[0].runtime };
    state.lifecycleOperationPollDelaysMs = [];

    await app.runLifecycleAction(state, elements, 'clear', actorId);
    assert.equal(elements.clearButton.textContent, 'Clearing...');
    await app.pollLifecycleOperations(state, elements);

    assert.deepEqual(state.lifecycleOperations, {});
    assert.equal(app.selectedActorRuntime(state).thread_id, 'thread-' + actorId);
    assert.equal(
      elements.messageBanner.textContent,
      'Cleared thread for ' + actorId + '. Thread thread-new.'
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Delete terminal result removes the actor and selects the authoritative neighbor', async () => {
  const originalFetch = globalThis.fetch;
  const deletedActorId = 'act-market-delete';
  const neighborActorId = 'act-market-neighbor';
  globalThis.fetch = async function (url, options) {
    const requestUrl = String(url);
    if (requestUrl === '/api/instances/' + deletedActorId) {
      assert.equal(options && options.method, 'DELETE');
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-delete-demo', action: 'delete', status: 'running',
          label: 'Deleting ' + deletedActorId,
          target: { actor_id: deletedActorId, role: 'market' },
        }),
      });
    }
    if (requestUrl === '/api/operations/op-delete-demo') {
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-delete-demo', action: 'delete', status: 'succeeded',
          label: 'Deleting ' + deletedActorId,
          target: { actor_id: deletedActorId, role: 'market' },
          result: { ok: true, actor_id: deletedActorId },
        }),
      });
    }
    if (requestUrl === '/api/actors') {
      return okResponse({ actors: [actor(neighborActorId, 'stopped', 'inactive', 'unhealthy')] });
    }
    if (requestUrl === '/api/actors/' + neighborActorId + '/console') {
      return consoleResponse(neighborActorId, 'inactive', 'unhealthy');
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=' + neighborActorId + '&limit=50') {
      return imNotFoundResponse();
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [
      actor(deletedActorId, 'stopped', 'inactive', 'unhealthy'),
      actor(neighborActorId, 'stopped', 'inactive', 'unhealthy'),
    ];
    state.selectedActorId = deletedActorId;
    state.lifecycleOperationPollDelaysMs = [];

    await app.runLifecycleAction(state, elements, 'delete', deletedActorId);
    await app.pollLifecycleOperations(state, elements);

    assert.equal(state.selectedActorId, neighborActorId);
    assert.deepEqual(state.actors.map((row) => row.actor_id), [neighborActorId]);
    assert.doesNotMatch(elements.actorsList.innerHTML, new RegExp(deletedActorId));
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Stop terminal result moves the same selected actor into Stopped with Resume and Delete', async () => {
  const originalFetch = globalThis.fetch;
  const actorId = 'act-market-stop';
  globalThis.fetch = async function (url) {
    const requestUrl = String(url);
    if (requestUrl === '/api/instances/' + actorId + '/stop') {
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-stop-demo', action: 'stop', status: 'running', label: 'Stopping ' + actorId,
          target: { actor_id: actorId, role: 'market' },
        }),
      });
    }
    if (requestUrl === '/api/operations/op-stop-demo') {
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-stop-demo', action: 'stop', status: 'succeeded', label: 'Stopping ' + actorId,
          target: { actor_id: actorId, role: 'market' },
          result: { ok: true, instance: { actor_id: actorId, status: 'inactive' } },
        }),
      });
    }
    if (requestUrl === '/api/actors') {
      return okResponse({ actors: [actor(actorId, 'stopped', 'inactive', 'unhealthy')] });
    }
    if (requestUrl === '/api/actors/' + actorId + '/console') {
      return consoleResponse(actorId, 'inactive', 'unhealthy');
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [actor(actorId, 'active', 'active', 'healthy')];
    state.selectedActorId = actorId;
    state.actorConsole = { actor: { actor_id: actorId, role: 'market' }, runtime: state.actors[0].runtime };
    state.lifecycleOperationPollDelaysMs = [];

    await app.runLifecycleAction(state, elements, 'stop', actorId);
    await app.pollLifecycleOperations(state, elements);

    assert.equal(state.actors[0].lifecycle_state, 'stopped');
    assert.equal(elements.resumeButton.hidden, false);
    assert.equal(elements.resumeButton.disabled, false);
    assert.equal(elements.deleteButton.disabled, false);
    assert.equal(elements.retryButton.hidden, true);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('failed lifecycle operation clears protection and keeps authoritative actor actions', async () => {
  const originalFetch = globalThis.fetch;
  const actorId = 'act-market-failed-clear';
  globalThis.fetch = async function (url) {
    const requestUrl = String(url);
    if (requestUrl === '/api/instances/' + actorId + '/clear') {
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-clear-failed', action: 'clear', status: 'running', label: 'Clearing ' + actorId,
          target: { actor_id: actorId, role: 'market' },
        }),
      });
    }
    if (requestUrl === '/api/operations/op-clear-failed') {
      return okResponse({
        operation: lifecycleOperation({
          id: 'op-clear-failed', action: 'clear', status: 'failed', label: 'Clearing ' + actorId,
          target: { actor_id: actorId, role: 'market' },
          error: { code: 'COMMAND_FAILED', message: 'Clear failed.' },
        }),
      });
    }
    if (requestUrl === '/api/actors') {
      return okResponse({ actors: [actor(actorId, 'active', 'active', 'healthy')] });
    }
    if (requestUrl === '/api/actors/' + actorId + '/console') {
      return consoleResponse(actorId, 'active', 'healthy');
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [actor(actorId, 'active', 'active', 'healthy')];
    state.selectedActorId = actorId;
    state.actorConsole = { actor: { actor_id: actorId, role: 'market' }, runtime: state.actors[0].runtime };
    state.lifecycleOperationPollDelaysMs = [];

    await app.runLifecycleAction(state, elements, 'clear', actorId);
    await app.pollLifecycleOperations(state, elements);

    assert.deepEqual(state.lifecycleOperations, {});
    assert.equal(elements.clearButton.disabled, false);
    assert.match(elements.messageBanner.textContent, /Clear failed/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('instance action matrix follows lifecycle_state and active-operation protection', () => {
  const active = {
    lifecycle_state: 'active', status: 'active', app_server_health: 'healthy', thread: { status: 'idle' },
  };
  assert.deepEqual(
    app.computeInstanceActionState(active, { draftText: 'Advance', lifecycleOperation: null }),
    {
      canSend: true,
      canInterrupt: false,
      canStop: true,
      canDelete: false,
      canClear: true,
      canResume: false,
      canRetry: false,
    }
  );
  const protectedState = app.computeInstanceActionState(active, {
    draftText: 'Advance',
    lifecycleOperation: lifecycleOperation({ action: 'clear', status: 'queued' }),
  });
  assert.equal(protectedState.canSend, true);
  assert.equal(protectedState.canStop, false);
  assert.equal(protectedState.canClear, false);

  const stopped = app.computeInstanceActionState({
    lifecycle_state: 'stopped', status: 'inactive', thread: { status: '' },
  }, {});
  assert.equal(stopped.canResume, true);
  assert.equal(stopped.canDelete, true);
  assert.equal(stopped.canRetry, false);
});
