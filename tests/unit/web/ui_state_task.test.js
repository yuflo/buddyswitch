'use strict';

const { test } = require('node:test');
const { assert, fs, path, rendererModule, MarkdownIt, app, identityRef, imMessage, deferred, okResponse, lifecycleOperation, imNotFoundResponse, waitFor, createRenderElements } = require('./ui_state_harness');

test('actor task summary renders canonical lifecycle status without retired relation fields', async () => {
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
                source_type: 'demand',
                demand_ref: { demand_id: 'demand-ui-current', basis_revision: 1 },
                status: 'in_progress.parent_processing',
                actor: { actor_id: 'act-task', role_id: 'dev' },
              },
            ],
            recoverable_tasks: [
              {
                task_id: 'task-ui-failed',
                source_type: 'demand',
                demand_ref: { demand_id: 'demand-ui-failed', basis_revision: 1 },
                status: 'in_progress.side_processing',
                actor: { actor_id: 'act-task', role_id: 'dev' },
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

    assert.match(elements.actorTaskSummary.innerHTML, /in_progress\.parent_processing/);
    assert.match(elements.actorTaskSummary.innerHTML, /Recoverable/);
    assert.match(elements.actorTaskSummary.innerHTML, /in_progress\.side_processing/);
    assert.match(elements.actorTaskSummary.innerHTML, /task-ui-failed/);
    assert.doesNotMatch(elements.actorTaskSummary.innerHTML, /Processor/);
    assert.doesNotMatch(elements.actorTaskSummary.innerHTML, /runtime_failed/);
    assert.doesNotMatch(elements.actorTaskSummary.innerHTML, /execution/);
    assert.doesNotMatch(elements.actorTaskSummary.innerHTML, /task_relation/);
    assert.doesNotMatch(elements.actorTaskSummary.innerHTML, /Relation/);
    assert.doesNotMatch(elements.actorTaskSummary.innerHTML, /Description/);
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
