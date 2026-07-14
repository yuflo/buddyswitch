'use strict';

const { test } = require('node:test');
const { assert, fs, path, root, assetDir, indexHtml, appJs, markdownRendererPath, markdownRendererJs, stylesCss, combinedAssets, assertIncludes, assertExcludes, assertNotMatches, collectCssDeclarations, assertCssDeclarations, assertCssDeclarationsExclude } = require('./asset_contract_harness');

test('production javascript has one actor selection state owner and no retired side paths', () => {
  const selectionWrites = appJs.match(/state\.selectedActorId\s*=\s*[^=]/g) || [];
  assert.equal(selectionWrites.length, 1);
  assertIncludes(appJs, 'function beginActorSelection(state, actorId)');
  assertIncludes(appJs, 'async function loadActorSelection(state, elements, actorId)');
  assertExcludes(appJs, 'suppressNextRosterAutoSelection');
  assertExcludes(appJs, 'refreshSelectedActorConversation');

  const createdStart = appJs.indexOf('function beginCreatedActorReconciliation');
  const createdEnd = appJs.indexOf('function nextActorIdAfterRemoval', createdStart);
  const createdSource = appJs.slice(createdStart, createdEnd);
  assertIncludes(createdSource, 'await loadActorSelection(state, elements, actorId)');
  assertExcludes(createdSource, 'refreshActorCard(');
  assertExcludes(createdSource, 'refreshConversation(');

  const lifecycleStart = appJs.indexOf('async function reconcileLifecycleOperation');
  const lifecycleEnd = appJs.indexOf('async function createInstance', lifecycleStart);
  const lifecycleSource = appJs.slice(lifecycleStart, lifecycleEnd);
  assertIncludes(lifecycleSource, 'loadActorSelection(state, elements, restoreActorId)');
  assertIncludes(lifecycleSource, "beginActorSelection(state, '')");

  const refreshStart = appJs.indexOf('async function refreshVisibleRegionsWithFeedback');
  const refreshEnd = appJs.indexOf('async function bootstrap', refreshStart);
  const refreshSource = appJs.slice(refreshStart, refreshEnd);
  assertIncludes(refreshSource, 'reconcileActorSelectionAfterRoster');
  assertIncludes(refreshSource, 'loadActorSelection(state, elements, state.selectedActorId)');

  const bootstrapStart = appJs.indexOf('async function bootstrap');
  const bootstrapEnd = appJs.indexOf("if (typeof document !== 'undefined')", bootstrapStart);
  const bootstrapSource = appJs.slice(bootstrapStart, bootstrapEnd);
  assertIncludes(bootstrapSource, 'reconcileActorSelectionAfterRoster');
  assertExcludes(bootstrapSource, 'refreshActorCard(');
  assertExcludes(bootstrapSource, 'refreshConversation(');
  assert.equal(
    (bootstrapSource.match(/await Promise\.allSettled\(\[appBasicsPromise, tracksPromise\]\)/g) || []).length,
    2
  );
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
  assertIncludes(appJs, "const targetIdentityId = target && target.identity_id ? target.identity_id : ''");
  assertIncludes(appJs, 'target_identity_id: targetIdentityId');
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
  assertExcludes(appJs, '/api/tasks');
  assertExcludes(appJs, "fetchJson('/api/tracks', {");
  assertExcludes(appJs, "fetchJson(buildTrackDetailUrl(state.selectedTrackId), {");
  assertExcludes(appJs, "method: 'PATCH'");
  [
    "/api/instances/' + encodeURIComponent(state.selectedActorId) + '/si" + "de'",
    "/api/instances/' + encodeURIComponent(state.selectedActorId) + '/si" + "de/close'",
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
