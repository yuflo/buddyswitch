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
      message: 'Resume this instance first.',
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
      message: 'Instance is unhealthy.',
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

test('im event URL uses cursor and bounded wait', () => {
  assert.equal(
    app.buildImEventsUrl('imev-abc 123', 15000),
    '/api/im/events?cursor=imev-abc%20123&wait_ms=15000'
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

test('record fetched actor IM message appends reply and ignores external echo', () => {
  const state = app.createState();
  const actorReply = app.recordImFetchedMessage(state, {
    id: 'msg-reply-1',
    from: { kind: 'actor', actor_address: { role_id: 'market', actor_id: 'act-market-1' } },
    content: 'pong',
    reply_to: 'msg-sent-1',
  });
  const externalEcho = app.recordImFetchedMessage(state, {
    id: 'msg-echo-1',
    from: { kind: 'external', external_id: 'ext-1' },
    content: 'ping',
    reply_to: null,
  });

  assert.equal(actorReply, true);
  assert.equal(externalEcho, false);
  assert.deepEqual(state.imConversation, [
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
