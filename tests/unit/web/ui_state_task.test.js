'use strict';

const { test } = require('node:test');
const { assert, app, imNotFoundResponse, okResponse, createRenderElements } = require('./ui_state_harness');

function task(taskId, status, updatedAt) {
  return {
    task_id: taskId,
    source_type: 'test.ui',
    status,
    actor: { actor_id: 'act-task', role_id: 'dev' },
    updated_at: updatedAt,
  };
}

const terminalTasks = [
  task('task-terminal-5', 'completed', '2026-07-17T10:05:00Z'),
  task('task-terminal-4', 'canceled', '2026-07-17T10:04:00Z'),
  task('task-terminal-3', 'completed', '2026-07-17T10:03:00Z'),
  task('task-terminal-2', 'completed', '2026-07-17T10:02:00Z'),
  task('task-terminal-1', 'canceled', '2026-07-17T10:01:00Z'),
];

async function renderTaskPanel(taskSys, interactionState) {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/actors/act-task/console') {
      return Promise.resolve(okResponse({
        console: {
          actor: { actor_id: 'act-task', role: 'dev' },
          runtime: { status: 'active', app_server_health: 'healthy', thread: { status: 'idle' } },
          task_sys: taskSys,
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
    if (interactionState) {
      state.actorTaskRecentExpanded = interactionState.recentExpanded === true;
      state.actorTaskOpenId = interactionState.openTaskId || '';
      await app.refreshSelectedActorConsoleAndRender(state, elements);
    }
    if (state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
    return elements.actorTaskSummary.innerHTML;
  } finally {
    globalThis.fetch = originalFetch;
  }
}

test('B2 Task ledger renders active current task and two visible recent rows', async () => {
  const html = await renderTaskPanel({
    active_count: 1,
    recoverable_count: 0,
    terminal_count: 5,
    active_tasks: [task('task-current', 'in_progress.parent_processing', '2026-07-17T10:06:00Z')],
    recoverable_tasks: [],
    terminal_tasks: terminalTasks,
  });

  assert.match(html, /class="task-ledger-count"[^>]*>1 active · 5 recent/);
  assert.match(html, /class="task-ledger-row is-current"/);
  assert.match(html, /Now · in_progress\.parent_processing/);
  assert.match(html, /task-current/);
  assert.match(html, /2 of 5 · Show all/);
  assert.match(html, /5 of 5 · Show fewer/);
  assert.match(html, /class="task-ledger-recent-collapsed"/);
  assert.match(html, /task-terminal-5/);
  assert.match(html, /task-terminal-4/);
});

test('B2 Task ledger prioritizes recoverable work with one amber attention row', async () => {
  const html = await renderTaskPanel({
    active_count: 2,
    recoverable_count: 1,
    terminal_count: 2,
    active_tasks: [task('task-current', 'in_progress.parent_processing', '2026-07-17T10:06:00Z')],
    recoverable_tasks: [task('task-attention', 'in_progress.side_processing', '2026-07-17T10:07:00Z')],
    terminal_tasks: terminalTasks.slice(0, 2),
  });

  assert.match(html, /2 active · 2 recent/);
  assert.match(html, /class="task-ledger-row is-current needs-attention"/);
  assert.match(html, /Needs attention · in_progress\.side_processing/);
  assert.match(html, /task-attention/);
  assert.doesNotMatch(html, /task-current/);
});

test('B2 Task ledger keeps recent terminal work visible without an active task', async () => {
  const html = await renderTaskPanel({
    active_count: 0,
    recoverable_count: 0,
    terminal_count: 2,
    active_tasks: [],
    recoverable_tasks: [],
    terminal_tasks: terminalTasks.slice(0, 2),
  });

  assert.match(html, /0 active · 2 recent/);
  assert.match(html, /No active task/);
  assert.match(html, /Recent stays visible/);
  assert.match(html, /task-terminal-5/);
  assert.match(html, /task-terminal-4/);
});

test('B2 Task ledger renders one compact no-task row when the actor has no tasks', async () => {
  const html = await renderTaskPanel({
    active_count: 0,
    recoverable_count: 0,
    terminal_count: 0,
    active_tasks: [],
    recoverable_tasks: [],
    terminal_tasks: [],
  });

  assert.match(html, /0 active · 0 recent/);
  assert.match(html, /class="task-ledger-empty"/);
  assert.match(html, /No tasks yet/);
  assert.doesNotMatch(html, /task-ledger-recent-disclosure/);
});

test('B2 Task ledger uses native exclusive details and exposes only safe row detail', async () => {
  const html = await renderTaskPanel({
    active_count: 1,
    recoverable_count: 0,
    terminal_count: 5,
    active_tasks: [task('task-current', 'in_progress.parent_processing', '2026-07-17T10:06:00Z')],
    recoverable_tasks: [],
    terminal_tasks: terminalTasks,
  });

  assert.match(html, /<details class="task-ledger-recent-disclosure">/);
  assert.match(html, /<summary class="task-ledger-recent-toggle"[^>]*aria-expanded="false">/);
  assert.match(html, /<details class="task-ledger-row-detail" name="actor-task-row-detail"[^>]*>/);
  assert.match(html, /<summary class="task-ledger-row is-current"[^>]*aria-expanded="false">/);
  assert.match(html, /<span>Task ID<\/span><code>task-current<\/code>/);
  assert.match(html, /<span>Updated<\/span><time datetime="2026-07-17T10:06:00Z">2026-07-17T10:06:00Z<\/time>/);
  assert.doesNotMatch(html, /<span>Active<\/span>/);
  assert.doesNotMatch(html, /<span>Recoverable<\/span>/);
  assert.doesNotMatch(html, /Processor|runtime_failed|execution|events|task_relation|Relation|Description|active_processor|failure_result|Cancel|Retry/);
});

test('B2 Task ledger preserves recent and exclusive row disclosure state across console refresh', async () => {
  const html = await renderTaskPanel({
    active_count: 0,
    recoverable_count: 0,
    terminal_count: 5,
    active_tasks: [],
    recoverable_tasks: [],
    terminal_tasks: terminalTasks,
  }, {
    recentExpanded: true,
    openTaskId: 'task-terminal-4',
  });

  assert.match(html, /<details class="task-ledger-recent-disclosure" open>/);
  assert.match(html, /<summary class="task-ledger-recent-toggle"[^>]*aria-expanded="true"/);
  assert.match(html, /<details class="task-ledger-row-detail" name="actor-task-row-detail" data-task-ledger-task-id="task-terminal-4" open>/);
  assert.match(html, /data-task-ledger-task-id="task-terminal-4"[^>]*aria-expanded="true"/);
  assert.equal((html.match(/data-task-ledger-task-id="[^"]+" open/g) || []).length, 1);
});
