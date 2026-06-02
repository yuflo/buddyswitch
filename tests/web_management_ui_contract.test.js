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
    'role-select',
    'create-button',
    'instances-body',
    'instance-detail',
    'instruction-input',
    'send-button',
    'interrupt-button',
    'stop-button',
    'clear-button',
    'resume-button',
    'delete-button',
    'open-tui-button',
    'open-tui-status',
    'copy-tui-command-button',
    'open-tui-command',
    'message-banner',
  ].forEach((id) => {
    assertIncludes(indexHtml, `id="${id}"`);
  });
});

test('production html uses the first-version workspace control layout', () => {
  [
    'class="app-shell"',
    'class="sidebar"',
    'class="workspace-page"',
    'class="content-grid"',
    'class="detail-column"',
    'class="block-panel instance-panel"',
    'class="block-panel detail-panel"',
    'class="block-panel action-panel"',
  ].forEach((marker) => {
    assertIncludes(indexHtml, marker);
  });
});

test('production stylesheet supports the first-version control-room states', () => {
  [
    '.app-shell',
    '.sidebar',
    '.workspace-page',
    '.content-grid',
    '.detail-column',
    '.instances-table tbody tr.is-selected',
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
    '/api/instances',
    '/status',
    '/input',
    '/interrupt',
    '/stop',
    '/clear',
    '/resume',
    '/open-tui',
    'X-BuddySwitch-Web',
  ].forEach((apiPath) => {
    assertIncludes(appJs, apiPath);
  });

  assertIncludes(appJs, "method: 'DELETE'");
  assertIncludes(combinedAssets, 'Copy command');
});

test('production assets present role-configured actor instance wording', () => {
  assertIncludes(indexHtml, '>Role<');
  assertIncludes(indexHtml, 'Stored local actor instances');
  assertExcludes(combinedAssets, '>' + 'Buddy' + '<');
  assertExcludes(combinedAssets, 'selected' + 'Buddy');
  assertExcludes(combinedAssets, 'Stored local ' + 'role instances');
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
