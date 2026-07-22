'use strict';

const { test } = require('node:test');
const { assert, fs, path, root, assetDir, indexHtml, appJs, markdownRendererPath, markdownRendererJs, stylesCss, combinedAssets, assertIncludes, assertExcludes, assertNotMatches, collectCssDeclarations, assertCssDeclarations, assertCssDeclarationsExclude } = require('./asset_contract_harness');

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
  assertExcludes(stylesCss, '.command-fallback');
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

test('production stylesheet keeps the new reply chip collapsed while hidden', () => {
  assertIncludes(stylesCss, '.new-reply-chip[hidden]');
  assertCssDeclarations('.new-reply-chip[hidden]', [
    'display: none;',
  ]);
});

test('empty state heading and detail remain visually separated', () => {
  assertCssDeclarations('.empty-state > strong', [
    'display: block;',
  ]);
  assertCssDeclarations('.empty-state > span', [
    'display: block;',
    'margin-top: 4px;',
  ]);
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
