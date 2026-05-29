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

test('create button requires selected buddy and no start busy state', () => {
  assert.equal(app.computeCreateEnabled({ selectedBuddy: '', isCreating: false }), false);
  assert.equal(app.computeCreateEnabled({ selectedBuddy: 'pm', isCreating: true }), false);
  assert.equal(app.computeCreateEnabled({ selectedBuddy: 'pm', isCreating: false }), true);
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
