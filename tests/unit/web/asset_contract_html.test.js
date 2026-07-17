'use strict';

const { test } = require('node:test');
const { assert, fs, path, root, assetDir, indexHtml, appJs, markdownRendererPath, markdownRendererJs, stylesCss, combinedAssets, assertIncludes, assertExcludes, assertNotMatches, collectCssDeclarations, assertCssDeclarations, assertCssDeclarationsExclude } = require('./asset_contract_harness');

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
    'copy-command-button',
    'copy-command-status',
    'message-banner',
    'im-conversation',
    'new-reply-chip',
  ].forEach((id) => {
    assertIncludes(indexHtml, `id="${id}"`);
  });
  [
    'open-tui-fallback',
    'open-tui-command',
    'copy-tui-command-button',
  ].forEach((id) => {
    assertExcludes(indexHtml, `id="${id}"`);
  });
});

test('B2 task ledger uses terminal projection and canonical external fields only', () => {
  [
    'taskSys.terminal_tasks',
    'taskSys.terminal_count',
    'task.status',
    'task.task_id',
    'task.updated_at',
    'name="actor-task-row-detail"',
  ].forEach((marker) => {
    assertIncludes(appJs, marker);
  });
  ['<span>Active</span>', '<span>Recoverable</span>'].forEach((marker) => {
    assertExcludes(appJs, marker);
  });
  ['task_desc', 'relation', 'execution', 'task_relation', 'active_processor', 'failure_result'].forEach((marker) => {
    assertExcludes(appJs, marker);
  });
});

test('B2 task ledger keeps its approved width while the right rail remains scrollable', () => {
  assertCssDeclarations('.person-panel', ['scrollbar-width: none;']);
  assertIncludes(stylesCss, '.person-panel::-webkit-scrollbar');
  assertCssDeclarations('.task-ledger-card', ['width: calc(100% + 1px);']);
});

test('B2 task ledger explicitly supports keyboard disclosure activation', () => {
  assertIncludes(appJs, "elements.actorTaskSummary.addEventListener('keydown'");
  assertIncludes(appJs, "event.key !== 'Enter' && event.key !== ' '");
  assertIncludes(appJs, 'taskToggle.click()');
  assertIncludes(stylesCss, '.task-ledger-row:focus-visible');
  assertIncludes(stylesCss, '.task-ledger-recent-toggle:focus-visible');
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

test('actor capability UI uses a quiet typed matrix with read-only model details', () => {
  [
    'id="actor-capability-card"',
    'id="actor-capability-toggle"',
    'id="actor-capability-status"',
    'id="actor-capability-parent-summary"',
    'id="actor-capability-side-summary"',
    'id="actor-capability-panel"',
    'id="actor-capability-matrix"',
    'id="actor-capability-details"',
    'id="actor-capability-save"',
    'id="actor-capability-cancel"',
    '<summary>Model details</summary>',
  ].forEach((marker) => {
    assertIncludes(indexHtml, marker);
  });

  [
    'actor-model-' + 'config',
    'model-' + 'config',
    'actorModel' + 'Config',
    'parent-model',
    'side-model',
    'parent-effort',
    'side-effort',
    'schema-strip',
    '<summary>Schema</summary>',
    'allowed_' + 'efforts',
    'VALID_' + 'EFFORTS',
    'capability-config.json',
    'effort must be',
    'payload editor',
    '<textarea id="actor-capability',
  ].forEach((forbidden) => {
    assertExcludes(combinedAssets, forbidden);
  });
  assertIncludes(appJs, 'buildActorCapabilitiesUrl(actorId)');
  assertIncludes(appJs, 'capabilitySelectionFromConsole(actorConsole)');
  assertIncludes(appJs, 'sameCapabilitySelection(left, right)');
  assertIncludes(stylesCss, '.actor-capability-card');
  assertIncludes(stylesCss, '.capability-matrix-row');
  assertIncludes(stylesCss, '.capability-choice.is-selected');
  assertCssDeclarations('.capability-choice.is-selected', [
    'background: var(--teal-soft);',
  ]);
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
    'id="copy-command-button"',
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
