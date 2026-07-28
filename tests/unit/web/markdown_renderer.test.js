#!/usr/bin/env node
'use strict';

const assert = require('assert');
const { test } = require('node:test');
const path = require('path');

const rendererPath = path.join(
  __dirname,
  '..',
  '..',
  '..',
  'src',
  'buddyswitch',
  'launcher',
  'assets',
  'web-management',
  'markdown-renderer.js'
);

const markdownItPath = path.join(
  __dirname,
  '..',
  '..',
  '..',
  'src',
  'buddyswitch',
  'launcher',
  'assets',
  'web-management',
  'vendor',
  'markdown-it',
  'markdown-it.min.js'
);

function loadRendererModule() {
  return require(rendererPath);
}

function loadMarkdownIt() {
  return require(markdownItPath);
}

function createRenderer(overrides) {
  const rendererModule = loadRendererModule();
  return rendererModule.createMarkdownRenderer(Object.assign({
    markdownIt: loadMarkdownIt(),
    DOMPurify: {
      sanitize(html) {
        return html;
      },
    },
    hljs: {
      getLanguage(name) {
        return ['js', 'javascript', 'bash', 'json', 'python'].includes(name);
      },
      highlight(code) {
        return { value: code.replace(/const/g, '<span class="hljs-keyword">const</span>') };
      },
    },
  }, overrides || {}));
}

test('renders CommonMark headings and paragraphs', () => {
  const renderer = createRenderer();
  const html = renderer.renderMarkdownMessageHtml('# PM role\n\n## Scope\n\nBody');
  assert.match(html, /<h1>PM role<\/h1>/);
  assert.match(html, /<h2>Scope<\/h2>/);
  assert.match(html, /<p>Body<\/p>/);
});

test('renders GFM-style structures needed by BuddySwitch conversations', () => {
  const renderer = createRenderer();
  const html = renderer.renderMarkdownMessageHtml([
    '~~removed~~ and *emphasis* and **strong**',
    '',
    '- [x] verified',
    '- [ ] follow up',
    '  - nested item',
    '',
    '| Area | Status |',
    '| --- | --- |',
    '| Render | safe |',
  ].join('\n'));
  assert.match(html, /<del>removed<\/del>/);
  assert.match(html, /<em>emphasis<\/em>/);
  assert.match(html, /<strong>strong<\/strong>/);
  assert.match(html, /type="checkbox"/);
  assert.match(html, /checked/);
  assert.match(html, /disabled/);
  assert.match(html, /nested item/);
  assert.match(html, /<table>/);
});

test('renders fenced code with explicit language highlighting only', () => {
  const renderer = createRenderer();
  const html = renderer.renderMarkdownMessageHtml('```js\nconst ok = true;\n```');
  assert.match(html, /class="[^"]*language-js/);
  assert.match(html, /hljs-keyword/);
  assert.match(html, /ok = true/);
});

test('constrains links and images to safe protocols', () => {
  const renderer = createRenderer();
  const html = renderer.renderMarkdownMessageHtml([
    '[safe](https://example.test/path)',
    '[local](#proof)',
    '[bad](javascript:alert(1))',
    '![diagram](https://example.test/diagram.png)',
    '![bad](data:image/svg+xml;base64,PHN2Zz4=)',
  ].join('\n'));
  assert.match(html, /href="https:\/\/example\.test\/path"/);
  assert.match(html, /target="_blank"/);
  assert.match(html, /rel="noopener noreferrer"/);
  assert.match(html, /href="#proof"/);
  assert.doesNotMatch(html, /javascript:/i);
  assert.match(html, /<img/);
  assert.match(html, /loading="lazy"/);
  assert.doesNotMatch(html, /data:image/i);
});

test('sanitizer is always invoked before returning html', () => {
  let calls = 0;
  let sanitizerConfig = null;
  let sanitizerHook = null;
  const renderer = createRenderer({
    DOMPurify: {
      addHook(name, hook) {
        assert.equal(name, 'afterSanitizeAttributes');
        sanitizerHook = hook;
      },
      sanitize(html, config) {
        calls += 1;
        sanitizerConfig = config;
        assert.match(html, /<h1>/);
        return html.replace('<h1>', '<h1 data-sanitized="1">');
      },
    },
    hljs: null,
  });
  const html = renderer.renderMarkdownMessageHtml('# Safe');
  assert.equal(calls, 1);
  ['target', 'rel', 'type', 'checked', 'disabled', 'loading', 'decoding'].forEach((attr) => {
    assert.equal(sanitizerConfig.ADD_ATTR(attr), true, `Expected DOMPurify ADD_ATTR to allow ${attr}`);
  });
  assert.ok(sanitizerConfig.ADD_TAGS.includes('input'));
  assert.equal(typeof sanitizerHook, 'function');

  const linkAttrs = { href: 'https://example.test' };
  sanitizerHook({
    tagName: 'A',
    getAttribute(name) {
      return linkAttrs[name] || '';
    },
    setAttribute(name, value) {
      linkAttrs[name] = value;
    },
    removeAttribute(name) {
      delete linkAttrs[name];
    },
  });
  assert.equal(linkAttrs.target, '_blank');
  assert.equal(linkAttrs.rel, 'noopener noreferrer');

  const inputAttrs = {};
  sanitizerHook({
    tagName: 'INPUT',
    classList: { contains(name) { return name === 'task-list-item-checkbox'; } },
    setAttribute(name, value) {
      inputAttrs[name] = value;
    },
  });
  assert.equal(inputAttrs.type, 'checkbox');
  assert.equal(inputAttrs.disabled, '');

  assert.match(html, /data-sanitized="1"/);
});
