#!/usr/bin/env node
'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const assetDir = path.join(root, 'tools', 'launcher', 'assets', 'web-management');
const indexHtml = fs.readFileSync(path.join(assetDir, 'index.html'), 'utf8');
const appJs = fs.readFileSync(path.join(assetDir, 'app.js'), 'utf8');
const stylesCss = fs.readFileSync(path.join(assetDir, 'styles.css'), 'utf8');
const combinedAssets = [indexHtml, appJs, stylesCss].join('\n');

function test(name, fn) {
  try {
    fn();
    process.stdout.write(`ok - ${name}\n`);
  } catch (error) {
    process.stderr.write(`not ok - ${name}\n`);
    throw error;
  }
}

function assertIncludes(source, expected) {
  assert.ok(source.includes(expected), `Expected asset content to include: ${expected}`);
}

function assertExcludes(source, forbidden) {
  assert.equal(source.includes(forbidden), false, `Expected asset content to exclude: ${forbidden}`);
}

test('production html keeps all real control ids used by the web UI', () => {
  [
    'server-status',
    'refresh-button',
    'actor-nav-button',
    'tracks-nav-button',
    'role-select',
    'create-button',
    'actors-list',
    'actor-console',
    'actor-runtime-detail',
    'actor-task-summary',
    'tracks-list',
    'track-detail',
    'instruction-input',
    'send-button',
    'interrupt-button',
    'stop-button',
    'clear-button',
    'resume-button',
    'delete-button',
    'action-availability-status',
    'open-tui-button',
    'open-tui-status',
    'copy-tui-command-button',
    'open-tui-command',
    'message-banner',
    'im-conversation',
  ].forEach((id) => {
    assertIncludes(indexHtml, `id="${id}"`);
  });
});

test('production html uses the actor-console workspace layout', () => {
  [
    'class="app-shell"',
    'class="sidebar"',
    'class="workspace-page"',
    'class="view-section actor-view"',
    'class="view-section track-view"',
    'class="actor-console-grid"',
    'console-column',
    'runtime-column',
    'class="workspace-panel actor-roster-panel"',
    'class="workspace-panel track-list-panel"',
  ].forEach((marker) => {
    assertIncludes(indexHtml, marker);
  });
});

test('production stylesheet supports actor console and track workspace states', () => {
  [
    '.app-shell',
    '.sidebar',
    '.workspace-page',
    '.view-section[hidden]',
    '.actor-console-grid',
    '.console-column',
    '.runtime-column',
    '.actor-list',
    '.track-list',
    '.selectable-row.is-selected',
    '.button.danger',
    '@media (max-width: 860px)',
  ].forEach((marker) => {
    assertIncludes(stylesCss, marker);
  });
});

test('production javascript keeps the real api surface', () => {
  [
    '/api/health',
    '/api/roles',
    '/api/actors',
    '/api/actors/',
    '/console',
    '/api/tracks',
    '/api/instances',
    '/api/web/im/session',
    '/api/web/im/messages',
    '/api/web/im/events',
    '/api/web/im/conversations/direct',
    "'interrupt'",
    "'stop'",
    "'clear'",
    "'resume'",
    '/open-tui',
    'X-BuddySwitch-Web',
  ].forEach((apiPath) => {
    assertIncludes(appJs, apiPath);
  });

  assertIncludes(appJs, "method: 'DELETE'");
  assertIncludes(appJs, 'actor_id: state.selectedActorId');
  assertIncludes(appJs, 'content: state.draftText');
  assertIncludes(appJs, 'target_identity_id: target.identity_id');
  assertIncludes(appJs, 'buildWebImConversationUrl');
  assertIncludes(appJs, 'buildImEventsUrl(target.identity_id, 15000)');
  assertIncludes(appJs, "'&wait_ms='");
  assertExcludes(appJs, "role_id=' + encodeURIComponent");
  assertExcludes(appJs, "actor_id=' + encodeURIComponent");
  assertIncludes(appJs, 'buildActorConsoleUrl');
  assertIncludes(appJs, 'buildTrackDetailUrl');
  assertIncludes(appJs, 'actionAvailabilityStatus.textContent');
  assertIncludes(appJs, 'shouldRefreshSelectedActorConsole');
  assertExcludes(appJs, "selectedActorId) + '/messages'");
  assertExcludes(appJs, 'JSON.stringify({ text: state.draftText })');
  assertIncludes(combinedAssets, 'Copy command');
  assertExcludes(appJs, "selectedActorId) + '/input'");
  assertExcludes(appJs, "/api/actors/' + encodeURIComponent(state.selectedActorId) + '/tasks'");
  assertExcludes(appJs, "/api/actors/' + encodeURIComponent(state.selectedActorId) + '/tracks'");
  assertExcludes(appJs, "/api/tracks/' + encodeURIComponent(state.selectedTrackId) + '/comments'");
  assertExcludes(appJs, '/api/im');
  assertExcludes(appJs, 'external-participants');
  assertExcludes(appJs, 'imParticipantToken');
  assertExcludes(appJs, 'participant_token');
  assertExcludes(appJs, 'event_cursor');
  assertExcludes(appJs, 'imEventCursor');
  assertExcludes(appJs, 'cursor=');
  assertExcludes(appJs, 'Authorization');
  assertExcludes(appJs, 'env.tool');
  assertExcludes(appJs, 'env.repos');
  assertExcludes(appJs, 'env.tools.track');
});

test('production assets present actor-centered console wording', () => {
  assertIncludes(indexHtml, '>Role<');
  assertIncludes(indexHtml, 'Actor Console');
  assertIncludes(indexHtml, 'Actors');
  assertIncludes(indexHtml, 'Tracks');
  assertIncludes(indexHtml, 'Runtime');
  assertIncludes(indexHtml, 'Task');
  assertIncludes(indexHtml, 'Track workspace');
  assertIncludes(indexHtml, '>Message<');
  assertIncludes(indexHtml, 'Send a direct message to the selected actor.');
  assertExcludes(combinedAssets, 'Instance control room');
  assertExcludes(combinedAssets, 'Control room');
  assertExcludes(combinedAssets, '>' + 'Buddy' + '<');
  assertExcludes(combinedAssets, 'selected' + 'Buddy');
  assertExcludes(combinedAssets, 'Stored local ' + 'role instances');
  assertExcludes(combinedAssets, '>Instruction<');
  assertExcludes(combinedAssets, 'thread input');
  assertExcludes(combinedAssets, 'steer');
  assertIncludes(combinedAssets, 'BuddySwitch');
});

test('first version does not reintroduce removed initialize ui or route', () => {
  [
    'Retry Initialize',
    'retry-init',
    'canInitialize',
    'initialize-button',
    '/initialize',
    'Initialize this BuddySwitch thread',
    'Reply exactly: ready',
  ].forEach((forbidden) => {
    assertExcludes(combinedAssets, forbidden);
  });
});

test('first version does not ship mock-only controls', () => {
  [
    'Refresh mock',
    'Mock data',
    'sideThreads',
    'side-draft',
    'metric-active',
    'metric-busy',
    'metric-attention',
    'metric-side',
    'status-strip',
    'search-input',
    'activity-list',
    'data-mode',
    'data-view',
    'Runtime logs',
    'Artifacts',
    'Threads',
    'attach-open',
    'terminal selector',
    'terminal-select',
    'open-terminal-choice',
  ].forEach((forbidden) => {
    assertExcludes(combinedAssets, forbidden);
  });
});
