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
    }
  );
});

test('active healthy instance allows send and stop, but not delete', () => {
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
    }
  );
});

test('inactive instance only allows delete', () => {
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
    }
  );
});
