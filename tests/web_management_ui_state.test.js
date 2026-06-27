#!/usr/bin/env node
'use strict';

const assert = require('assert');
const path = require('path');

const app = require(path.join(__dirname, '..', 'tools', 'launcher', 'assets', 'web-management', 'app.js'));

function test(name, fn) {
  try {
    fn();
    process.stdout.write(`ok - ${name}\n`);
  } catch (error) {
    process.stderr.write(`not ok - ${name}\n`);
    throw error;
  }
}

test('create button requires selected role and no start busy state', () => {
  assert.equal(app.computeCreateEnabled({ selectedRole: '', isCreating: false }), false);
  assert.equal(app.computeCreateEnabled({ selectedRole: 'pm', isCreating: true }), false);
  assert.equal(app.computeCreateEnabled({ selectedRole: 'pm', isCreating: false }), true);
});

test('state defaults to actor console as the primary section', () => {
  const state = app.createState();

  assert.equal(state.selectedSection, 'actors');
  assert.equal(state.selectedActorId, '');
  assert.equal(state.selectedTrackId, '');
  assert.deepEqual(state.actors, []);
  assert.deepEqual(state.tracks, []);
});

test('actor payload sync chooses first actor and clears stale selection', () => {
  const state = app.createState();
  state.selectedActorId = 'act-missing';
  state.openTuiMessage = 'Terminal opened.';
  state.openTuiCommand = 'attach command';

  app.applyActorsPayload(state, {
    actors: [
      { actor_id: 'act-pm-demo', role: 'pm', runtime: { status: 'active' } },
      { actor_id: 'act-dev-demo', role: 'dev', runtime: { status: 'inactive' } },
    ],
  });

  assert.equal(state.selectedActorId, 'act-pm-demo');
  assert.equal(state.openTuiMessage, '');
  assert.equal(state.openTuiCommand, '');
  assert.deepEqual(state.actors.map((actor) => actor.actor_id), ['act-pm-demo', 'act-dev-demo']);
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
      im: { target: { kind: 'actor', actor_address: { role_id: 'pm', actor_id: 'act-pm-demo' } } },
    },
  });

  assert.deepEqual(
    app.computeInstanceActionState(app.selectedActorRuntime(state), { draftText: 'ping', isMutating: false }),
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
    app.describeInstanceActionState(null, { draftText: '', isMutating: false }).clearReason,
    'Select an actor.'
  );
  assert.equal(
    app.describeInstanceActionState(
      {
        status: 'active',
        app_server_health: 'healthy',
        thread: { status: 'in_progress' },
      },
      { draftText: '', isMutating: false }
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
      { draftText: '', isMutating: false }
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

test('no selection disables all instance actions', () => {
  assert.deepEqual(
    app.computeInstanceActionState(null, { draftText: 'Advance the brief', isMutating: false }),
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
      { draftText: 'Advance the brief', isMutating: false }
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
      { draftText: 'Refine the plan', isMutating: false }
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
      { draftText: 'Refine the plan', isMutating: false }
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
      { draftText: 'Advance the brief', isMutating: false }
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

test('mutation busy state disables all instance controls', () => {
  assert.deepEqual(
    app.computeInstanceActionState(
      {
        status: 'active',
        app_server_health: 'healthy',
        thread: { status: 'in_progress' },
      },
      { draftText: 'Advance the brief', isMutating: true }
    ),
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

test('active idle instance allows clear even without draft text', () => {
  assert.deepEqual(
    app.computeInstanceActionState(
      {
        status: 'active',
        app_server_health: 'healthy',
        thread: { status: 'idle' },
      },
      { draftText: '', isMutating: false }
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
      { draftText: 'Steer', isMutating: false }
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
    app.computeOpenTuiState(null, { isMutating: false }),
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
      { isMutating: false }
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
      { isMutating: false }
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
      { isMutating: false }
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
      { isMutating: false }
    ),
    {
      canOpenTui: false,
      message: 'No thread to attach.',
    }
  );
});

test('mutation busy state disables open tui', () => {
  assert.deepEqual(
    app.computeOpenTuiState(
      {
        status: 'active',
        app_server_health: 'healthy',
        thread_id: 'thread-main',
      },
      { isMutating: true }
    ),
    {
      canOpenTui: false,
      message: '',
    }
  );
});

test('im event URL targets selected actor with cursor and bounded wait', () => {
  assert.equal(
    app.buildImEventsUrl('market', 'act-market demo', 'imev-abc 123', 15000),
    '/api/web/im/events?role_id=market&actor_id=act-market%20demo&cursor=imev-abc%20123&wait_ms=15000'
  );
});

test('im conversation URL targets selected actor without lower im route leakage', () => {
  assert.equal(
    app.buildWebImConversationUrl('market', 'act-market demo', 20),
    '/api/web/im/conversations/direct?role_id=market&actor_id=act-market%20demo&limit=20'
  );
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
      participant: 'you',
      content: 'ping',
      deliveryStatus: 'accepted',
      wakeStatus: 'submitted',
      replyTo: '',
    },
  ]);
});

test('record projected IM messages keeps sent and reply directions', () => {
  const state = app.createState();
  const sentEcho = app.recordImProjectedMessage(state, {
    id: 'msg-sent-1',
    from: { kind: 'external', external_id: 'ext-1' },
    content: 'ping',
    reply_to: null,
  });
  const actorReply = app.recordImProjectedMessage(state, {
    id: 'msg-reply-1',
    from: { kind: 'actor', actor_address: { role_id: 'market', actor_id: 'act-market-1' } },
    content: 'pong',
    reply_to: 'msg-sent-1',
  });

  assert.equal(sentEcho, true);
  assert.equal(actorReply, true);
  assert.deepEqual(state.imConversation, [
    {
      id: 'msg-sent-1',
      direction: 'sent',
      participant: 'you',
      content: 'ping',
      deliveryStatus: '',
      wakeStatus: '',
      replyTo: '',
    },
    {
      id: 'msg-reply-1',
      direction: 'reply',
      participant: 'market/act-market-1',
      content: 'pong',
      deliveryStatus: '',
      wakeStatus: '',
      replyTo: 'msg-sent-1',
    },
  ]);
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
        from: { kind: 'external', external_id: 'ext-web' },
        content: 'ping',
        reply_to: null,
      },
      {
        id: 'msg-reply-1',
        from: { kind: 'actor', actor_address: { role_id: 'market', actor_id: 'act-market-1' } },
        content: 'pong',
        reply_to: 'msg-sent-1',
      },
    ],
  });

  assert.deepEqual(state.imConversation.map((entry) => [entry.id, entry.direction, entry.content]), [
    ['msg-sent-1', 'sent', 'ping'],
    ['msg-reply-1', 'reply', 'pong'],
  ]);
  assert.deepEqual(Object.keys(state.imSeenMessageIds).sort(), ['msg-reply-1', 'msg-sent-1']);
});

test('web im event payload appends projected messages and advances cursor', () => {
  const state = app.createState();
  state.imEventCursor = 'imev-before';

  app.applyImEventsPayload(state, {
    next_cursor: 'imev-after',
    messages: [
      {
        id: 'msg-reply-1',
        from: { kind: 'actor', actor_address: { role_id: 'market', actor_id: 'act-market-1' } },
        content: 'pong',
        reply_to: null,
      },
    ],
  });

  assert.equal(state.imEventCursor, 'imev-after');
  assert.deepEqual(state.imConversation.map((entry) => [entry.id, entry.direction, entry.content]), [
    ['msg-reply-1', 'reply', 'pong'],
  ]);
});
