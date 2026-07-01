#!/usr/bin/env node
'use strict';

const assert = require('assert');
const path = require('path');

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

function createRenderElements() {
  const node = () => ({
    textContent: '',
    value: '',
    hidden: false,
    disabled: false,
    innerHTML: '',
    classList: { toggle() {} },
    querySelectorAll() { return []; },
  });
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
    tracksList: node(),
    trackDetail: node(),
    trackStudioRail: node(),
    imConversation: node(),
    sendButton: node(),
    interruptButton: node(),
    stopButton: node(),
    deleteButton: node(),
    clearButton: node(),
    resumeButton: node(),
    actionAvailabilityStatus: node(),
    openTuiButton: node(),
    openTuiStatus: node(),
    openTuiCommand: node(),
    openTuiFallback: node(),
    copyTuiCommandButton: node(),
  };
}

test('create button requires selected role and no start busy state', () => {
  assert.equal(app.computeCreateEnabled({ selectedRole: '', isCreating: false }), false);
  assert.equal(app.computeCreateEnabled({ selectedRole: 'pm', isCreating: true }), false);
  assert.equal(app.computeCreateEnabled({ selectedRole: 'pm', isCreating: false }), true);
});

test('state defaults to Team room as the primary section', () => {
  const state = app.createState();

  assert.equal(state.selectedSection, 'actors');
  assert.equal(state.selectedActorId, '');
  assert.equal(state.selectedTrackId, '');
  assert.deepEqual(state.actors, []);
  assert.deepEqual(state.tracks, []);
  assert.equal(state.imConversationIdentityId, '');
});

test('actor payload sync chooses first actor and clears stale selection', () => {
  const state = app.createState();
  state.selectedActorId = 'act-missing';
  state.openTuiMessage = 'Terminal opened.';
  state.openTuiCommand = 'attach command';
  app.recordImProjectedMessage(state, {
    id: 'msg-stale',
    from_identity_id: 'act-missing',
    to_identity_id: 'ext-web',
    content: 'stale',
    reply_to: null,
  });

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
    app.recordImProjectedMessage(state, {
      id: 'msg-old',
      from_identity_id: 'act-old',
      to_identity_id: 'ext-web',
      content: 'old actor message',
      reply_to: null,
    });
    elements.messageBanner.textContent = 'Created act-old.';

    const selection = app.selectActor(state, elements, 'act-new');
    selection.catch(function () {});

    assert.equal(state.selectedActorId, 'act-new');
    assert.equal(state.message, '');
    assert.equal(elements.messageBanner.textContent, '');
    assert.deepEqual(state.imConversation, []);
    assert.match(elements.actorRuntimeDetail.innerHTML, /Loading/);

    await selection;
    if (state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
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
      lifecyclePendingAction: '',
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
      lifecyclePendingAction: '',
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
        lifecyclePendingAction: '',
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
        lifecyclePendingAction: '',
      }
    ).clearReason,
    ''
  );
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
      lifecyclePendingAction: '',
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
        lifecyclePendingAction: '',
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
        lifecyclePendingAction: '',
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
        lifecyclePendingAction: '',
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
        lifecyclePendingAction: '',
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
        lifecyclePendingAction: '',
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

test('lifecycle pending disables lifecycle buttons without disabling send', () => {
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
        lifecyclePendingAction: 'clear',
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
        lifecyclePendingAction: '',
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
        lifecyclePendingAction: '',
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

test('im event URL is connection-wide with bounded wait only', () => {
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
  const sentEcho = app.recordImProjectedMessage(state, {
    id: 'msg-sent-1',
    from_identity_id: 'ext-1',
    to_identity_id: 'act-market-1',
    content: 'ping',
    reply_to: null,
  });
  const actorReply = app.recordImProjectedMessage(state, {
    id: 'msg-reply-1',
    from_identity_id: 'act-market-1',
    to_identity_id: 'ext-1',
    content: 'pong',
    reply_to: 'msg-sent-1',
  });

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
  app.recordImProjectedMessage(state, {
    id: 'msg-stale',
    from_identity_id: 'act-market-old',
    to_identity_id: 'ext-web',
    content: 'stale',
    reply_to: null,
  });

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
      {
        id: 'msg-sent-1',
        from_identity_id: 'ext-web',
        to_identity_id: 'act-market-1',
        content: 'ping',
        reply_to: null,
      },
      {
        id: 'msg-reply-1',
        from_identity_id: 'act-market-1',
        to_identity_id: 'ext-web',
        content: 'pong',
        reply_to: 'msg-sent-1',
      },
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
    app.recordImProjectedMessage(state, {
      id: 'msg-stale',
      from_identity_id: 'act-market-old',
      to_identity_id: 'ext-web',
      content: 'stale',
      reply_to: null,
    });

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

  app.recordImProjectedMessage(state, {
    id: 'msg-reply-1',
    from_identity_id: 'act-market-1',
    to_identity_id: 'ext-web',
    content: 'pong',
    reply_to: null,
  });

  assert.equal(Object.prototype.hasOwnProperty.call(state, 'imEventCursor'), false);
  assert.deepEqual(state.imConversation.map((entry) => [entry.id, entry.direction, entry.content]), [
    ['msg-reply-1', 'reply', 'pong'],
  ]);
});

test('connection-wide fetched event messages only append when they touch selected actor', () => {
  const state = app.createState();
  state.selectedActorId = 'act-market-selected';
  state.imConversationIdentityId = 'act-market-selected';

  const offScopeRecorded = app.recordSelectedActorEventMessage(
    state,
    {
      id: 'msg-dev',
      from_identity_id: 'act-dev-other',
      to_identity_id: 'ext-web',
      content: 'dev pong',
      reply_to: null,
    },
    'act-market-selected'
  );

  const selectedRecorded = app.recordSelectedActorEventMessage(
    state,
    {
      id: 'msg-market',
      from_identity_id: 'act-market-selected',
      to_identity_id: 'ext-web',
      content: 'market pong',
      reply_to: null,
    },
    'act-market-selected'
  );

  assert.equal(offScopeRecorded, false);
  assert.equal(selectedRecorded, true);
  assert.deepEqual(state.imConversation.map((entry) => [entry.id, entry.content]), [
    ['msg-market', 'market pong'],
  ]);
});

test('polling connection-wide events acks off-selected actor message without rendering it', async () => {
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
            message: {
              id: 'msg-dev',
              from_identity_id: 'act-dev-other',
              to_identity_id: 'ext-web',
              content: 'dev pong',
              reply_to: null,
            },
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
