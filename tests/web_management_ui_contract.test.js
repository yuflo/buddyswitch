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

test('production html uses the Team Room and Track Studio workspace layout', () => {
  [
    'class="webui-root"',
    'class="tabs app-tabs"',
    'class="screen view-section team-room-view"',
    'class="screen view-section track-view"',
    'class="proto-shell team-room"',
    'class="room-sidebar"',
    'class="room-main"',
    'class="room-header"',
    'class="room-thread"',
    'class="composer"',
    'class="person-panel"',
    'class="person-card"',
    'class="proto-shell track-studio"',
    'class="studio-side"',
    'class="studio-doc"',
    'class="doc-page"',
    'class="studio-rail"',
  ].forEach((marker) => {
    assertIncludes(indexHtml, marker);
  });
});

test('production html removes the old management shell completely', () => {
  [
    'class="app-shell"',
    'class="sidebar"',
    'class="workspace-page"',
    'class="page-header"',
    'class="workspace-switcher"',
    'class="workspace-mark"',
    'class="nav-item"',
    'class="breadcrumb"',
    'id="page-title"',
    'id="page-summary"',
  ].forEach((forbidden) => {
    assertExcludes(indexHtml, forbidden);
  });
});

test('production html uses the final prototype root and primary tabs', () => {
  assertIncludes(indexHtml, 'class="webui-root"');
  assertIncludes(indexHtml, 'class="tabs app-tabs"');
  assertIncludes(indexHtml, 'id="actor-nav-button"');
  assertIncludes(indexHtml, 'id="tracks-nav-button"');
  const primaryNav = indexHtml.match(/<nav class="tabs app-tabs"[\s\S]*?<\/nav>/);
  assert.ok(primaryNav, 'Expected final top-level app tabs');
  const labels = Array.from(primaryNav[0].matchAll(/<button[\s\S]*?>([\s\S]*?)<\/button>/g))
    .map((match) => match[1].replace(/<[^>]*>/g, '').trim().replace(/\s+/g, ' '));
  assert.deepEqual(labels, ['Team room', 'Tracks']);
});

test('production stylesheet supports Team Room and Track Studio states', () => {
  [
    '.webui-root',
    '.tabs.app-tabs',
    '.view-section[hidden]',
    '.proto-shell',
    '.team-room',
    '.room-sidebar',
    '.room-main',
    '.room-header',
    '.room-thread',
    '.composer',
    '.person-panel',
    '.person-card',
    '.track-studio',
    '.studio-side',
    '.studio-doc',
    '.doc-page',
    '.studio-rail',
    '.actor-list',
    '.track-list',
    '.selectable-row.is-selected',
    '.button.danger',
    '@media (max-width: 860px)',
  ].forEach((marker) => {
    assertIncludes(stylesCss, marker);
  });
});

test('production stylesheet restores prototype room and studio proportions', () => {
  [
    'grid-template-columns: 260px minmax(0, 1fr) 320px;',
    'grid-template-columns: 250px minmax(0, 1fr) 320px;',
    'background: #f7f6f1;',
    'background: #ebe8dc;',
    'background: #fbfbf8;',
    'background: #f0eee4;',
    'background: #f6f5f2;',
    'background: #ece9e0;',
    'background: #f0ede5;',
  ].forEach((marker) => {
    assertIncludes(stylesCss, marker);
  });
});

test('production stylesheet supports pending and loading feedback states', () => {
  [
    '.is-loading',
    '.button.is-pending',
    '.selectable-row.is-loading',
    '.inline-loading',
    '.message.pending',
    '.message.failed',
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
    '/api/im/session',
    '/api/im/messages',
    '/api/im/events',
    '/api/im/events/ack',
    '/api/im/conversations/direct',
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
  assertIncludes(appJs, 'content: content');
  assertExcludes(appJs, 'content: state.draftText');
  assertIncludes(appJs, 'target_identity_id: target.identity_id');
  assertIncludes(appJs, 'buildImConversationUrl');
  assertIncludes(appJs, 'buildImEventsUrl(15000)');
  assertIncludes(appJs, 'buildImMessageUrl');
  assertIncludes(appJs, 'buildImAckPayload');
  assertIncludes(appJs, '/api/im/events?wait_ms=');
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
  [
    "/api/instances/' + encodeURIComponent(state.selectedActorId) + '/side'",
    "/api/instances/' + encodeURIComponent(state.selectedActorId) + '/side/close'",
    "/api/tracks/' + encodeURIComponent(state.selectedTrackId) + '/comments'",
    '/api/web/' + 'im',
  ].forEach((forbidden) => {
    assertExcludes(appJs, forbidden);
  });
  assertExcludes(appJs, 'buildWeb' + 'ImConversationUrl');
  assertExcludes(appJs, 'ensureWeb' + 'ImSession');
  assertExcludes(appJs, 'apply' + 'ImEventsPayload');
  assertExcludes(appJs, 'messageTouches' + 'KnownOrSelectedActor');
  assertExcludes(appJs, 'external-participants');
  assertExcludes(appJs, 'connection_' + 'key');
  assertExcludes(appJs, 'imParticipantToken');
  assertExcludes(appJs, 'participant_' + 'token');
  assertExcludes(appJs, 'event_' + 'cursor');
  assertExcludes(appJs, 'imEventCursor');
  assertExcludes(appJs, 'cursor' + '=');
  assertExcludes(appJs, 'Authorization');
  assertExcludes(appJs, 'env.tool');
  assertExcludes(appJs, 'env.repos');
  assertExcludes(appJs, 'env.tools.track');
});

test('production javascript does not attach row click handlers from render', () => {
  assertExcludes(appJs, "elements.actorsList.querySelectorAll('[data-actor-id]').forEach");
  assertExcludes(appJs, "elements.tracksList.querySelectorAll('[data-track-id]').forEach");
});

test('production javascript does not keep global mutation state residue', () => {
  assertExcludes(appJs, 'mutation' + 'Key');
  assertExcludes(appJs, 'is' + 'Mutating');
  assertExcludes(appJs, 'Action ' + 'running.');
  assertExcludes(appJs, 'run' + "Mutation(state, elements, 'messages'");
});

test('production javascript keeps draft input off the full page render path', () => {
  assertExcludes(appJs, 'render(state, ' + 'elements);');
});

test('production assets present Team room and Tracks as the only primary tabs', () => {
  assertIncludes(indexHtml, '>Team room<');
  assertIncludes(indexHtml, '>Tracks<');
  assertExcludes(indexHtml, 'Actor Console');
  assertExcludes(indexHtml, '>Actors<');
  assertExcludes(indexHtml, 'Create Actor');
  assertExcludes(indexHtml, 'Runtime health');
  assertExcludes(indexHtml, '>Artifacts<');
  assertExcludes(indexHtml, 'Workstream OS');
  assertExcludes(indexHtml, 'Capacity');
});

test('primary navigation has exactly two visible destinations', () => {
  const primaryNav = indexHtml.match(/<nav class="tabs app-tabs"[\s\S]*?<\/nav>/);
  assert.ok(primaryNav, 'Expected final primary nav');
  const buttonLabels = Array.from(primaryNav[0].matchAll(/<button[\s\S]*?>([\s\S]*?)<\/button>/g))
    .map((match) => match[1].replace(/<[^>]*>/g, '').trim().replace(/\s+/g, ' '));
  assert.deepEqual(buttonLabels, ['Team room', 'Tracks']);
});

test('Team room keeps direct thread centered and actions in the teammate card', () => {
  const roomMain = indexHtml.match(/<section class="room-main"[\s\S]*?<\/section>\s*<aside id="actor-console"/);
  assert.ok(roomMain, 'Expected center room main before teammate rail');
  [
    'class="room-header"',
    'class="room-thread"',
    'id="im-conversation"',
    'class="composer"',
    'id="instruction-input"',
    'placeholder="Message the selected teammate."',
    'id="send-button"',
    'id="interrupt-button"',
    '>Message<',
  ].forEach((marker) => {
    assertIncludes(roomMain[0], marker);
  });
  [
    'id="open-tui-button"',
    'id="clear-button"',
    'id="stop-button"',
    'id="resume-button"',
    'id="delete-button"',
  ].forEach((forbidden) => {
    assertExcludes(roomMain[0], forbidden);
  });

  const teammateRail = indexHtml.match(/<aside id="actor-console" class="person-panel"[\s\S]*?<\/aside>/);
  assert.ok(teammateRail, 'Expected selected teammate rail');
  [
    'class="person-card"',
    'id="actor-runtime-detail"',
    'id="actor-task-summary"',
    'id="actor-track-summary"',
    'id="open-tui-button"',
    'id="clear-button"',
    'id="stop-button"',
    'id="resume-button"',
    'id="delete-button"',
    'id="action-availability-status"',
    'id="message-banner"',
  ].forEach((marker) => {
    assertIncludes(teammateRail[0], marker);
  });
  [
    'id="instruction-input"',
    'id="send-button"',
    'id="interrupt-button"',
  ].forEach((forbidden) => {
    assertExcludes(teammateRail[0], forbidden);
  });
});

test('Tracks shell presents read-only Track Studio labels', () => {
  const trackView = indexHtml.match(/<section id="track-view"[\s\S]*?<\/section>\s*<\/main>/);
  assert.ok(trackView, 'Expected Tracks view');
  assertIncludes(trackView[0], '>Tracks<');
  assertIncludes(trackView[0], '>Track Studio<');
  assertIncludes(trackView[0], 'Outcome, current state, materials, proofs, updates, and comments');
  assertIncludes(trackView[0], 'id="track-studio-rail"');
  assertIncludes(trackView[0], 'aria-label="Track comments and context"');
  [
    '<textarea',
    'composer',
    'Submit',
    'Resolve',
  ].forEach((forbidden) => {
    assertExcludes(trackView[0], forbidden);
  });
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

test('Team room assets do not invent fake teammate facts', () => {
  [
    'Dev Actor',
    'PM Actor',
    'Test Actor',
    'Market Actor',
    '72%',
    '68%',
    'last proof',
    '4 collaborators',
    'collaborators',
    'unread',
    'current focus',
    'load percentage',
    'capacity bar',
    'availability score',
  ].forEach((forbidden) => {
    assertExcludes(combinedAssets.toLowerCase(), forbidden.toLowerCase());
  });
});

test('production assets do not add decorative or fake layout markers', () => {
  [
    'track-workspace-grid',
    'orb',
    'blob',
    'capacity-bar',
    'avatar-stack',
    'unread-badge',
    'fake-metric',
  ].forEach((forbidden) => {
    assertExcludes(combinedAssets, forbidden);
  });
});
