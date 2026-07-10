#!/usr/bin/env node
'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const assetDir = path.join(root, 'tools', 'launcher', 'assets', 'web-management');
const indexHtml = fs.readFileSync(path.join(assetDir, 'index.html'), 'utf8');
const appJs = fs.readFileSync(path.join(assetDir, 'app.js'), 'utf8');
const markdownRendererPath = path.join(assetDir, 'markdown-renderer.js');
const markdownRendererJs = fs.existsSync(markdownRendererPath) ? fs.readFileSync(markdownRendererPath, 'utf8') : '';
const stylesCss = fs.readFileSync(path.join(assetDir, 'styles.css'), 'utf8');
const combinedAssets = [indexHtml, appJs, markdownRendererJs, stylesCss].join('\n');

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

function assertNotMatches(source, forbiddenPattern) {
  assert.equal(forbiddenPattern.test(source), false, `Expected asset content to exclude pattern: ${forbiddenPattern}`);
}

function collectCssDeclarations(selector) {
  const bodies = Array.from(stylesCss.matchAll(/([^{}]+)\{([^{}]*)\}/g))
    .filter((match) => match[1].split(',').map((part) => part.trim()).includes(selector))
    .map((match) => match[2])
    .join('\n');
  assert.ok(bodies, `Expected stylesheet to include a rule for: ${selector}`);
  return bodies;
}

function assertCssDeclarations(selector, declarations) {
  const body = collectCssDeclarations(selector);
  declarations.forEach((declaration) => {
    assertIncludes(body, declaration);
  });
}

function assertCssDeclarationsExclude(selector, declarations) {
  const body = collectCssDeclarations(selector);
  declarations.forEach((declaration) => {
    assertExcludes(body, declaration);
  });
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
    'lifecycle-operation-status',
    'action-availability-status',
    'open-tui-button',
    'open-tui-status',
    'copy-tui-command-button',
    'open-tui-command',
    'message-banner',
    'im-conversation',
    'new-reply-chip',
  ].forEach((id) => {
    assertIncludes(indexHtml, `id="${id}"`);
  });
});

test('task sys panel uses execution relation fields only', () => {
  ['task_desc', 'task_relation', 'execution'].forEach((marker) => {
    assertIncludes(appJs, marker);
  });
  ['active_processor', 'failure_result'].forEach((marker) => {
    assertExcludes(appJs, marker);
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
    'class="room-header selected-context-header"',
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

test('production stylesheet keeps the workspace compact on desktop viewports', () => {
  [
    'height: calc(100dvh - 78px);',
    'min-height: 640px;',
    'grid-template-columns: 240px minmax(360px, 1fr) 300px;',
    'grid-template-columns: 232px minmax(360px, 1fr) 300px;',
    '@media (max-width: 1040px)',
  ].forEach((marker) => {
    assertIncludes(stylesCss, marker);
  });

  assertExcludes(stylesCss, '@media (max-width: 1180px)');
  assertCssDeclarations('.composer-box', [
    'min-height: 72px;',
    'padding: 9px;',
  ]);
  assertCssDeclarations('.textarea-field textarea', [
    'resize: none;',
  ]);
  assertCssDeclarations('.command-fallback', [
    'grid-template-columns: minmax(0, 1fr) auto;',
    'align-items: center;',
  ]);
  assertCssDeclarations('.person-row', [
    'grid-template-columns: 34px minmax(0, 1fr);',
    'align-items: start;',
  ]);
  assertCssDeclarations('.row-status', [
    'grid-column: 2;',
    'justify-content: flex-start;',
  ]);
});

test('production stylesheet bounds workspace panes vertically instead of clipping controls', () => {
  assertCssDeclarations('.proto-shell', [
    'grid-template-rows: minmax(0, 1fr);',
  ]);
  assertCssDeclarations('.room-main', [
    'grid-template-rows: auto minmax(0, 1fr) auto;',
    'min-height: 0;',
    'overflow: hidden;',
  ]);
  assertCssDeclarations('.room-thread', [
    'min-height: 0;',
    'overflow: auto;',
  ]);
  [
    '.room-sidebar',
    '.person-panel',
    '.studio-side',
    '.studio-doc',
    '.studio-rail',
  ].forEach((selector) => {
    assertCssDeclarations(selector, [
      'min-height: 0;',
    ]);
  });
  [
    '.room-main',
    '.room-thread',
    '.person-panel',
    '.studio-doc',
    '.studio-rail',
  ].forEach((selector) => {
    assertCssDeclarationsExclude(selector, [
      'max-height:',
      'height: calc(100dvh',
    ]);
  });
});

test('production stylesheet restores prototype room and studio proportions', () => {
  [
    'grid-template-columns: 240px minmax(360px, 1fr) 300px;',
    'grid-template-columns: 232px minmax(360px, 1fr) 300px;',
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
    '.lifecycle-operation-status',
  ].forEach((marker) => {
    assertIncludes(stylesCss, marker);
  });
  assertCssDeclarations('.lifecycle-operation-status', [
    'color: var(--blue);',
    'font-weight: 680;',
  ]);
});

test('production roster exposes grouped lifecycle hierarchy and unmistakable selection', () => {
  [
    '.roster-group',
    '.roster-group-head',
    '.roster-group-toggle',
    '.roster-group-rows',
    '.person-row.is-selected::before',
    '.person-row:focus-visible',
  ].forEach((marker) => {
    assertIncludes(stylesCss, marker);
  });
  [
    'data-roster-group',
    'data-roster-toggle',
    'aria-selected',
    'aria-expanded',
    'rosterStoppedExpanded',
    'rosterPendingActors',
  ].forEach((marker) => {
    assertIncludes(appJs, marker);
  });
  assertExcludes(appJs, 'rosterPendingActorId');
  assertExcludes(appJs, 'rosterReconcileActorId');
  assertCssDeclarations('.person-row.is-selected', [
    'border-color: var(--teal);',
    'background: var(--teal-soft);',
  ]);
  assertCssDeclarations('.person-row:focus-visible', [
    'outline: 3px solid rgba(31, 111, 119, 0.24);',
    'outline-offset: 1px;',
  ]);
});

test('production stylesheet keeps hidden operational fallback frames collapsed', () => {
  assertIncludes(stylesCss, '.command-fallback[hidden]');
  assertCssDeclarations('.command-fallback[hidden]', [
    'display: none;',
  ]);
  assertIncludes(stylesCss, '.new-reply-chip[hidden]');
  assertCssDeclarations('.new-reply-chip[hidden]', [
    'display: none;',
  ]);
});

test('actor model config UI uses payload editor without schema or dropdown residue', () => {
  [
    'id="actor-model-config-card"',
    'id="actor-model-config-toggle"',
    'id="actor-model-config-status"',
    'id="actor-model-config-parent-summary"',
    'id="actor-model-config-side-summary"',
    'id="actor-model-config-panel"',
    'id="actor-model-config-payload"',
    'id="actor-model-config-save"',
    'id="actor-model-config-revert"',
  ].forEach((marker) => {
    assertIncludes(indexHtml, marker);
  });

  [
    'parent-model',
    'side-model',
    'parent-effort',
    'side-effort',
    'schema-strip',
    '<summary>Schema</summary>',
    'allowed_efforts',
    'VALID_EFFORTS',
    'model-config.json',
    'effort must be',
    'Payload must include parent and side',
  ].forEach((forbidden) => {
    assertExcludes(combinedAssets, forbidden);
  });
  assertNotMatches(combinedAssets, /minimal\s*[,\n]\s*low\s*[,\n]\s*medium\s*[,\n]\s*high\s*[,\n]\s*ultra/i);

  assertIncludes(appJs, 'buildActorModelConfigUrl(actorId)');
  assertIncludes(appJs, 'parseJsonObjectPayload(text)');
  assertIncludes(appJs, 'summarizeActorModelPayload(payload)');
  assertIncludes(stylesCss, '.actor-model-config-card');
  assertIncludes(stylesCss, '.model-config-payload-editor');
});

test('production stylesheet keeps long direct-thread message content inside bubbles', () => {
  assertCssDeclarations('.room-thread', [
    'min-width: 0;',
    'overflow: auto;',
  ]);
  assertCssDeclarationsExclude('.room-thread', [
    'overflow-x: hidden;',
  ]);
  assertCssDeclarations('.im-conversation', [
    'min-width: 0;',
  ]);
  assertCssDeclarations('.message', [
    'min-width: 0;',
    'max-width: 76%;',
  ]);
  ['.message .meta', '.message p'].forEach((selector) => {
    assertCssDeclarations(selector, [
      'min-width: 0;',
      'max-width: 100%;',
      'overflow-wrap: anywhere;',
    ]);
    assertCssDeclarationsExclude(selector, [
      'word-break: break-all;',
    ]);
  });
});

test('production assets support markdown replies and new reply motion without layout drift', () => {
  [
    '.markdown-body',
    '.markdown-table-wrap',
    '.new-reply-chip',
    '.new-reply-chip.is-chip-pop',
    '.message.is-new',
    '@keyframes reply-pop',
    '@keyframes chip-pop',
    'prefers-reduced-motion',
  ].forEach((marker) => {
    assertIncludes(stylesCss, marker);
  });
  assertCssDeclarations('.message.is-new', [
    'animation: reply-pop 190ms cubic-bezier(0.2, 0.8, 0.2, 1) both;',
  ]);
  assertCssDeclarations('.markdown-body', [
    'min-width: 0;',
    'max-width: 100%;',
    'overflow-wrap: anywhere;',
  ]);
  assertCssDeclarations('.markdown-table-wrap', [
    'max-width: 100%;',
    'overflow-x: auto;',
  ]);
  assertCssDeclarations('.markdown-body pre', [
    'max-width: 100%;',
    'overflow-x: auto;',
  ]);
  assertIncludes(indexHtml, 'id="room-thread"');
  assertIncludes(indexHtml, 'id="new-reply-chip"');
  assertIncludes(markdownRendererJs, 'renderMarkdownMessageHtml');
  assertIncludes(appJs, 'BuddySwitchMarkdownRenderer');
  assertIncludes(appJs, 'imFreshMessageIds');
  assertIncludes(appJs, 'isConversationNearBottom');
});

test('production webui has one markdown renderer boundary and no handwritten parser residue', () => {
  [
    'sanitizeMarkdownHref',
    'renderInlineMarkdownHtml',
    'isFenceLine',
    'isUnorderedListLine',
    'isOrderedListLine',
    'isBlockquoteLine',
    'splitMarkdownTableCells',
    'isTableDividerLine',
    'isTableStart',
    'isMarkdownBlockStart',
    'renderMarkdownTableHtml',
  ].forEach((forbidden) => {
    assertExcludes(appJs, forbidden);
  });
  assertIncludes(appJs, 'renderMessageContentHtml');
  assertIncludes(markdownRendererJs, 'createMarkdownRenderer');
  assertIncludes(markdownRendererJs, 'renderMarkdownMessageHtml');
});

test('production webui vendors local markdown dependencies without cdn or build chain', () => {
  [
    'vendor/markdown-it/markdown-it.min.js',
    'vendor/dompurify/purify.min.js',
    'vendor/highlightjs/highlight.min.js',
    'vendor/highlightjs/github.min.css',
    'vendor/PROVENANCE.md',
  ].forEach((relativePath) => {
    assert.ok(fs.existsSync(path.join(assetDir, relativePath)), `Expected vendor asset: ${relativePath}`);
  });
  [
    '/static/vendor/markdown-it/markdown-it.min.js',
    '/static/vendor/dompurify/purify.min.js',
    '/static/vendor/highlightjs/highlight.min.js',
    '/static/markdown-renderer.js',
    '/static/app.js',
  ].forEach((src) => {
    assertIncludes(indexHtml, `src="${src}"`);
  });
  assert.ok(indexHtml.indexOf('/static/markdown-renderer.js') < indexHtml.indexOf('/static/app.js'));
  assertIncludes(indexHtml, 'href="/static/vendor/highlightjs/github.min.css"');
  assertExcludes(indexHtml, 'https://cdn');
  assertExcludes(indexHtml, 'https://unpkg');
  assertExcludes(indexHtml, 'https://cdn.jsdelivr');
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
  assertIncludes(appJs, 'actor_id: actorId');
  assertIncludes(appJs, 'actorRuntimeForId');
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
  assertExcludes(appJs, 'external_session_' + 'key');
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

test('production javascript removes monolithic refresh functions', () => {
  assertExcludes(appJs, 'async function refreshAll(');
  assertExcludes(appJs, 'async function refreshAllWithFeedback(');
  assertExcludes(appJs, 'await refreshAll(state, elements)');
  assertExcludes(appJs, 'refreshAllWithFeedback(state, elements)');
});

test('production assets expose scoped skeleton and aria busy states', () => {
  [
    '.skeleton-line',
    '.skeleton-card',
    '.conversation-skeleton',
    '.person-row.is-pending',
  ].forEach((marker) => {
    assertIncludes(stylesCss, marker);
  });
  [
    'setRegionBusy',
    "aria-busy",
    'actorCardLoading',
    'conversationLoading',
    'rosterPendingActors',
  ].forEach((marker) => {
    assertIncludes(appJs, marker);
  });
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

test('Team room binds selected actor actions to a compact thread header', () => {
  const roomMain = indexHtml.match(/<section class="room-main"[\s\S]*?<\/section>\s*<aside id="actor-console"/);
  assert.ok(roomMain, 'Expected center room main before teammate rail');
  [
    'class="room-header selected-context-header"',
    'class="conversation-identity"',
    'class="conversation-actions"',
    'id="selected-context-avatar"',
    'id="selected-context-role"',
    'id="selected-context-id"',
    'id="selected-context-runtime"',
    'id="selected-context-health"',
    'id="stop-button"',
    'id="resume-button"',
    'id="delete-button"',
    'id="lifecycle-operation-status"',
    'id="action-availability-status"',
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

  ['stop-button', 'resume-button', 'delete-button'].forEach((id) => {
    const matches = indexHtml.match(new RegExp('id="' + id + '"', 'g')) || [];
    assert.equal(matches.length, 1, `Expected one production control for ${id}`);
  });
  [
    'id="stop-button"',
    'id="resume-button"',
    'id="delete-button"',
    'id="lifecycle-operation-status"',
    'id="action-availability-status"',
  ].forEach((forbidden) => {
    assertExcludes(teammateRail[0], forbidden);
  });
});

test('selected context stays compact and does not replace direct-thread structure', () => {
  [
    '.selected-context-header',
    '.conversation-identity',
    '.conversation-context-copy',
    '.conversation-context-meta',
    '.conversation-actions',
  ].forEach((marker) => {
    assertIncludes(stylesCss, marker);
  });
  assertCssDeclarations('.selected-context-header', [
    'min-height: 64px;',
    'align-items: center;',
  ]);
  assertIncludes(appJs, 'renderSelectedActorContext');
  assertIncludes(indexHtml, '<div id="room-thread" class="room-thread">');
  assertIncludes(indexHtml, '<div id="im-conversation" class="im-conversation" aria-live="polite"></div>');
  assertIncludes(indexHtml, 'src="/static/markdown-renderer.js"');
  assertIncludes(indexHtml, 'src="/static/app.js"');
  assertExcludes(combinedAssets, 'selected-workbar');
});

test('delete uses one accessible exact-target confirmation boundary', () => {
  [
    'id="delete-confirmation-backdrop"',
    'id="delete-confirmation-dialog"',
    'id="delete-confirmation-title"',
    'id="delete-confirmation-target"',
    'id="delete-confirmation-role"',
    'id="delete-confirmation-state"',
    'id="delete-confirmation-input"',
    'id="delete-confirmation-cancel"',
    'id="delete-confirmation-confirm"',
    'role="dialog"',
    'aria-modal="true"',
    'aria-labelledby="delete-confirmation-title"',
  ].forEach((marker) => {
    assertIncludes(indexHtml, marker);
  });
  [
    '.modal-backdrop',
    '.modal-backdrop[hidden]',
    '.confirmation-dialog',
    '.confirmation-warning',
    '.confirmation-actions',
  ].forEach((marker) => {
    assertIncludes(stylesCss, marker);
  });
  [
    'openDeleteConfirmation',
    'updateDeleteConfirmationInput',
    'deleteConfirmationMatches',
    'confirmDelete',
  ].forEach((marker) => {
    assertIncludes(appJs, marker);
  });
  assertIncludes(appJs, "elements.deleteButton.addEventListener('click', function () {\n      openDeleteConfirmation");
  assertNotMatches(appJs, /elements\.deleteButton\.addEventListener\('click',[\s\S]{0,180}runLifecycleAction/);
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
