# WebUI Markdown Renderer Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild BuddySwitch Web Management markdown rendering as one clean, standard-based, sanitized rendering boundary, with no retained handwritten parser path and no dual-track compatibility.

**Architecture:** Message state and conversation UI remain owned by `app.js`; markdown parsing, sanitizing, link/image policy, code highlighting, and task-list post-processing move into a new `markdown-renderer.js` module. Static third-party browser assets are vendored locally and served through one path-safe static-file projection under `/static/`, not through CDN and not through a frontend build chain.

**Tech Stack:** Plain browser JavaScript, CommonJS-compatible UMD modules for Node tests, `markdown-it@14.3.0`, `dompurify@3.4.11`, `@highlightjs/cdn-assets@11.11.1`, existing Node assertion tests, existing Python `unittest`, and live validation on `http://127.0.0.1:8766/`.

---

## 1. Task Objective Restatement

The task is to replace the current WebUI markdown rendering implementation, not patch it. The current renderer inside `tools/launcher/assets/web-management/app.js` is a handwritten parser with partial support for inline code, bold, simple links, flat lists, blockquotes, fenced code, and tables. It fails visible product cases already present in the running `http://127.0.0.1:8766/` UI:

- Dev reply headings such as `## 我能做什么` are rendered as plain paragraphs.
- PM reply headings such as `# PM 角色可用技能说明` are rendered as plain paragraphs.
- Paragraph and line structure are flattened too aggressively.
- Nested lists, task lists, strikethrough, italic, image syntax, link titles, language-aware code fences, and several GFM cases are incomplete or wrong.

The rebuilt target is:

```text
actor reply markdown -> direct conversation projection -> WebUI message bubble -> safe CommonMark/GFM HTML visible to the user
```

That contract must be proven in unit, asset, server-static, residue, and live browser checks.

## 2. Bitter Principles Applied

This plan applies the `docs/bitter` principles directly:

- **No retained old shape:** The old parser function names and handwritten parser helpers are deleted from live WebUI surfaces. There is no runtime switch that chooses old or new rendering.
- **No guarded residue:** The rebuilt renderer does not blacklist known old parser cases. It defines the current markdown contract through `markdown-it` configuration, sanitizer allowlists, renderer rules, and tests.
- **End-to-end contract stays alive:** Parser tests are necessary but insufficient. Acceptance requires the live Dev/PM direct-thread page to show markdown headings and structured content correctly.
- **Move the change boundary:** `app.js` is already a high-churn shared file. Markdown behavior moves to `markdown-renderer.js`, leaving `app.js` as the conversation and state projection layer.
- **Stable shared boundary:** `web_management.py` gets one path-safe static asset serving boundary for `/static/...`, not repeated route branches for every vendor file.
- **Behavior plus surface proof:** Completion requires behavior tests and live-surface residue scans.
- **Resource lifecycle caution:** Browser acceptance uses the already-running 8766 service or an explicitly owned server process. Broad checks must not leave extra listeners or orphan services.

## 3. Current Code Evidence

Current relevant surfaces in `fea-webui`:

- `tools/launcher/assets/web-management/app.js` has 2456 lines and owns state, API calls, IM projection, rendering, scrolling, and the handwritten markdown parser.
- `tools/launcher/assets/web-management/styles.css` has 1136 lines and currently contains only the initial markdown styles.
- `tools/launcher/web_management.py` serves only `/`, `/static/styles.css`, and `/static/app.js`.
- `tests/web_management_ui_state.test.js` loads `app.js` through Node and currently asserts the old exact markdown HTML shape.
- `tests/web_management_ui_contract.test.js` reads static files and currently asserts `renderMarkdownMessageHtml` exists in `app.js`.
- `tests/test_web_management.py` verifies only `app.js` and `styles.css` static assets.

Old renderer live-surface terms to remove from active source and active tests:

```text
sanitizeMarkdownHref
renderInlineMarkdownHtml
isFenceLine
isUnorderedListLine
isOrderedListLine
isBlockquoteLine
splitMarkdownTableCells
isTableDividerLine
isTableStart
isMarkdownBlockStart
renderMarkdownTableHtml
renderMarkdownMessageHtml
```

The term `renderMarkdownMessageHtml` may exist only as the new public API exported by `markdown-renderer.js`. It must not remain implemented in `app.js`.

## 4. Standards And Library Decisions

Markdown target:

- Baseline syntax: CommonMark.
- Product extension target: GFM subset needed for BuddySwitch chat output.
- Supported GFM subset: tables, strikethrough, autolink literals where supported by `markdown-it` linkify rules, and task-list rendering for list items beginning with `[ ]`, `[x]`, or `[X]`.
- Raw HTML: disabled as a product feature.

Library sources verified through npm metadata on 2026-07-08:

- `markdown-it@14.3.0`, MIT, repository `https://github.com/markdown-it/markdown-it`, browser files `dist/markdown-it.min.js` and Node test file `dist/index.cjs.js`.
- `dompurify@3.4.11`, `(MPL-2.0 OR Apache-2.0)`, repository `https://github.com/cure53/DOMPurify`, browser file `dist/purify.min.js`.
- `@highlightjs/cdn-assets@11.11.1`, BSD-3-Clause, repository `https://github.com/highlightjs/highlight.js`, browser files `highlight.min.js` and `styles/github.min.css`.

Vendoring rule:

- Use `npm pack <pkg>@<version>` in a temporary directory.
- Copy only the required distributable files and licenses into `tools/launcher/assets/web-management/vendor/`.
- Do not commit `node_modules`.
- Do not add a package manager manifest for this static WebUI rebuild.
- Record exact package name, version, license, npm tarball source, repository, and copied files in `tools/launcher/assets/web-management/vendor/PROVENANCE.md`.

## 5. Module Boundary Design

### 5.1 `markdown-renderer.js`

Path: `tools/launcher/assets/web-management/markdown-renderer.js`

Responsibility:

- Own all markdown rendering behavior.
- Export `createMarkdownRenderer(deps)` for tests.
- Export a default browser renderer as `BuddySwitchMarkdownRenderer` when browser dependencies are present.
- Return sanitized HTML strings safe for insertion into `.markdown-body`.

Public contract:

```js
{
  createMarkdownRenderer,
  renderMarkdownMessageHtml
}
```

No other WebUI file may parse markdown syntax directly.

Required dependency shape:

```js
{
  markdownIt,
  DOMPurify,
  hljs
}
```

Renderer policy:

- Configure `markdown-it` with `html: false`, `linkify: true`, `typographer: false`, `breaks: false`.
- Use `markdown-it` renderer rules to constrain links and images before sanitization.
- Use DOMPurify after markdown rendering with an explicit allowlist.
- Add `target="_blank"` and `rel="noopener noreferrer"` only to external `http` and `https` links.
- Preserve local `#anchor` and root-relative `/path` links without opening a new window.
- Only allow `http:`, `https:`, root-relative `/`, and `#` URLs for links.
- Only allow `http:` and `https:` image URLs.
- Add `loading="lazy"` and `referrerpolicy="no-referrer"` to images.
- Highlight code only when the fenced code language is explicitly recognized by highlight.js.
- Do not use highlight.js auto-detection.
- Render task-list checkboxes as disabled read-only inputs.

### 5.2 `app.js`

Path: `tools/launcher/assets/web-management/app.js`

Responsibility after rebuild:

- Own app state, actor selection, direct conversation loading, event polling, message send state, scroll behavior, and message bubble shell.
- Delegate only `entry.content` rendering to `BuddySwitchMarkdownRenderer.renderMarkdownMessageHtml`.
- Fail fast if the renderer is unavailable in browser runtime.
- Export no old markdown parser functions.

Required app rendering shape:

```js
'<div class="markdown-body">' + markdownRenderer.renderMarkdownMessageHtml(entry.content) + '</div>'
```

### 5.3 `web_management.py`

Path: `tools/launcher/web_management.py`

Responsibility after rebuild:

- Keep API behavior unchanged.
- Serve `/` as `index.html`.
- Serve any `/static/<relative-path>` under `STATIC_ROOT` through a single path-safe helper.
- Reject path traversal and unsupported content types.
- Serve JavaScript as `application/javascript; charset=utf-8`.
- Serve CSS as `text/css; charset=utf-8`.

### 5.4 `styles.css`

Path: `tools/launcher/assets/web-management/styles.css`

Responsibility after rebuild:

- Own markdown visual presentation inside `.markdown-body`.
- Keep chat bubbles compact and bounded.
- Ensure headings, lists, tables, images, and code blocks cannot break message bubble width or room scroll stability.

## 6. Implementation Tasks

### Task 1: Add Failing Markdown Renderer Tests

**Files:**

- Create: `tests/web_management_markdown_renderer.test.js`
- Modify: `tests/web_management_ui_contract.test.js`

- [ ] **Step 1: Create the renderer test file with current expected behavior**

Create `tests/web_management_markdown_renderer.test.js` with a small test harness matching the existing Node tests. The test should require the new renderer module and the vendored `markdown-it` CommonJS build once those files exist.

Initial failing test content:

```js
#!/usr/bin/env node
'use strict';

const assert = require('assert');
const path = require('path');

const rendererModule = require(path.join(
  __dirname,
  '..',
  'tools',
  'launcher',
  'assets',
  'web-management',
  'markdown-renderer.js'
));

const markdownIt = require(path.join(
  __dirname,
  '..',
  'tools',
  'launcher',
  'assets',
  'web-management',
  'vendor',
  'markdown-it',
  'index.cjs.js'
));

function createRenderer() {
  return rendererModule.createMarkdownRenderer({
    markdownIt,
    DOMPurify: {
      sanitize(html) {
        return html;
      },
    },
    hljs: {
      getLanguage(name) {
        return ['js', 'javascript', 'bash', 'json', 'python'].includes(name);
      },
      highlight(code, options) {
        return { value: code.replace(/const/g, '<span class="hljs-keyword">const</span>') };
      },
    },
  });
}

function test(name, fn) {
  try {
    fn();
    process.stdout.write(`ok - ${name}\n`);
  } catch (error) {
    process.stderr.write(`not ok - ${name}\n`);
    throw error;
  }
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
  assert.match(html, /class="language-js/);
  assert.match(html, /hljs-keyword/);
  assert.match(html, /const ok = true/);
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
  const renderer = rendererModule.createMarkdownRenderer({
    markdownIt,
    DOMPurify: {
      sanitize(html) {
        calls += 1;
        assert.match(html, /<h1>/);
        return html.replace('<h1>', '<h1 data-sanitized="1">');
      },
    },
    hljs: null,
  });
  const html = renderer.renderMarkdownMessageHtml('# Safe');
  assert.equal(calls, 1);
  assert.match(html, /data-sanitized="1"/);
});
```

- [ ] **Step 2: Run the renderer test and confirm it fails**

Run:

```bash
node tests/web_management_markdown_renderer.test.js
```

Expected result before implementation:

```text
not ok - renders CommonMark headings and paragraphs
Error: Cannot find module ... markdown-renderer.js
```

- [ ] **Step 3: Add live-surface residue assertions**

Modify `tests/web_management_ui_contract.test.js` so it reads:

```js
const markdownRendererJs = fs.readFileSync(path.join(assetDir, 'markdown-renderer.js'), 'utf8');
```

Add a test:

```js
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
  assertIncludes(markdownRendererJs, 'createMarkdownRenderer');
  assertIncludes(markdownRendererJs, 'renderMarkdownMessageHtml');
});
```

- [ ] **Step 4: Run the contract test and confirm it fails on current code**

Run:

```bash
node tests/web_management_ui_contract.test.js
```

Expected result before implementation:

```text
not ok - production webui has one markdown renderer boundary and no handwritten parser residue
```

### Task 2: Vendor Standard Libraries Without Adding A Build Chain

**Files:**

- Create directory: `tools/launcher/assets/web-management/vendor/markdown-it/`
- Create directory: `tools/launcher/assets/web-management/vendor/dompurify/`
- Create directory: `tools/launcher/assets/web-management/vendor/highlightjs/`
- Create: `tools/launcher/assets/web-management/vendor/PROVENANCE.md`
- Modify: `tests/web_management_ui_contract.test.js`

- [ ] **Step 1: Copy vendored files from npm tarballs**

Run from repo root:

```bash
tmpdir="$(mktemp -d)"
npm pack markdown-it@14.3.0 --pack-destination "$tmpdir"
mkdir -p "$tmpdir/markdown-it"
tar -xzf "$tmpdir/markdown-it-14.3.0.tgz" -C "$tmpdir/markdown-it"
mkdir -p tools/launcher/assets/web-management/vendor/markdown-it
cp "$tmpdir/markdown-it/package/dist/markdown-it.min.js" tools/launcher/assets/web-management/vendor/markdown-it/markdown-it.min.js
cp "$tmpdir/markdown-it/package/dist/index.cjs.js" tools/launcher/assets/web-management/vendor/markdown-it/index.cjs.js
cp "$tmpdir/markdown-it/package/LICENSE" tools/launcher/assets/web-management/vendor/markdown-it/LICENSE

npm pack dompurify@3.4.11 --pack-destination "$tmpdir"
mkdir -p "$tmpdir/dompurify"
tar -xzf "$tmpdir/dompurify-3.4.11.tgz" -C "$tmpdir/dompurify"
mkdir -p tools/launcher/assets/web-management/vendor/dompurify
cp "$tmpdir/dompurify/package/dist/purify.min.js" tools/launcher/assets/web-management/vendor/dompurify/purify.min.js
cp "$tmpdir/dompurify/package/LICENSE" tools/launcher/assets/web-management/vendor/dompurify/LICENSE
cp "$tmpdir/dompurify/package/LICENSE-MPL" tools/launcher/assets/web-management/vendor/dompurify/LICENSE-MPL

npm pack @highlightjs/cdn-assets@11.11.1 --pack-destination "$tmpdir"
mkdir -p "$tmpdir/highlightjs"
tar -xzf "$tmpdir/highlightjs-cdn-assets-11.11.1.tgz" -C "$tmpdir/highlightjs"
mkdir -p tools/launcher/assets/web-management/vendor/highlightjs
cp "$tmpdir/highlightjs/package/highlight.min.js" tools/launcher/assets/web-management/vendor/highlightjs/highlight.min.js
cp "$tmpdir/highlightjs/package/styles/github.min.css" tools/launcher/assets/web-management/vendor/highlightjs/github.min.css
cp "$tmpdir/highlightjs/package/LICENSE" tools/launcher/assets/web-management/vendor/highlightjs/LICENSE
rm -rf "$tmpdir"
```

- [ ] **Step 2: Add provenance**

Create `tools/launcher/assets/web-management/vendor/PROVENANCE.md` with:

```markdown
# Web Management Vendor Provenance

These browser assets are vendored for the static BuddySwitch Web Management UI. They are loaded locally from `/static/vendor/...`; the runtime does not use CDN URLs, `node_modules`, or a frontend build chain.

| Package | Version | License | Source | Copied files |
| --- | --- | --- | --- | --- |
| markdown-it | 14.3.0 | MIT | npm package `markdown-it@14.3.0`, repository `https://github.com/markdown-it/markdown-it` | `dist/markdown-it.min.js`, `dist/index.cjs.js`, `LICENSE` |
| dompurify | 3.4.11 | MPL-2.0 OR Apache-2.0 | npm package `dompurify@3.4.11`, repository `https://github.com/cure53/DOMPurify` | `dist/purify.min.js`, `LICENSE`, `LICENSE-MPL` |
| @highlightjs/cdn-assets | 11.11.1 | BSD-3-Clause | npm package `@highlightjs/cdn-assets@11.11.1`, repository `https://github.com/highlightjs/highlight.js` | `highlight.min.js`, `styles/github.min.css`, `LICENSE` |
```

- [ ] **Step 3: Add static asset contract assertions**

In `tests/web_management_ui_contract.test.js`, assert:

```js
[
  'vendor/markdown-it/markdown-it.min.js',
  'vendor/markdown-it/index.cjs.js',
  'vendor/dompurify/purify.min.js',
  'vendor/highlightjs/highlight.min.js',
  'vendor/highlightjs/github.min.css',
  'vendor/PROVENANCE.md',
].forEach((relativePath) => {
  assert.ok(fs.existsSync(path.join(assetDir, relativePath)), `Expected vendor asset: ${relativePath}`);
});
```

- [ ] **Step 4: Run focused contract verification**

Run:

```bash
node tests/web_management_ui_contract.test.js
```

Expected result after vendoring but before route and HTML changes:

```text
fails on missing script/style references or static route assertions added in later tasks
```

### Task 3: Rebuild Static Asset Serving As A Single Safe Boundary

**Files:**

- Modify: `tools/launcher/web_management.py`
- Modify: `tests/test_web_management.py`

- [ ] **Step 1: Add failing static route tests**

Extend `test_static_assets_are_served` in `tests/test_web_management.py`:

```python
renderer_status, renderer = self._request_text(base_url, method="GET", path="/static/markdown-renderer.js")
markdown_it_status, markdown_it = self._request_text(
    base_url,
    method="GET",
    path="/static/vendor/markdown-it/markdown-it.min.js",
)
purify_status, purify = self._request_text(
    base_url,
    method="GET",
    path="/static/vendor/dompurify/purify.min.js",
)
hljs_status, hljs = self._request_text(
    base_url,
    method="GET",
    path="/static/vendor/highlightjs/highlight.min.js",
)
hljs_css_status, hljs_css = self._request_text(
    base_url,
    method="GET",
    path="/static/vendor/highlightjs/github.min.css",
)
blocked_status, blocked = self._request_text(
    base_url,
    method="GET",
    path="/static/../web_management.py",
)
self.assertEqual(renderer_status, 200)
self.assertIn("BuddySwitchMarkdownRenderer", renderer)
self.assertEqual(markdown_it_status, 200)
self.assertIn("markdownit", markdown_it.lower())
self.assertEqual(purify_status, 200)
self.assertIn("DOMPurify", purify)
self.assertEqual(hljs_status, 200)
self.assertIn("hljs", hljs)
self.assertEqual(hljs_css_status, 200)
self.assertIn(".hljs", hljs_css)
self.assertEqual(blocked_status, 404)
self.assertNotIn("WebManagementService", blocked)
```

- [ ] **Step 2: Run the Python test and confirm it fails**

Run:

```bash
python3 -m unittest tests.test_web_management.WebManagementHTTPActionTests.test_static_assets_are_served
```

Expected result before implementation:

```text
FAIL: renderer_status is 404
```

- [ ] **Step 3: Replace the three static route branches with a safe static handler**

In `tools/launcher/web_management.py`, keep `/` explicit and route all `/static/...` requests through one helper:

```python
STATIC_CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".map": "application/json; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}
```

Add helper methods to the request handler:

```python
def _dispatch(self) -> None:
    try:
        parsed = urlsplit(self.path)
        if parsed.path == "/":
            self._serve_static(STATIC_ROOT / "index.html", "text/html; charset=utf-8")
            return
        if parsed.path.startswith("/static/"):
            self._serve_static_request(parsed.path)
            return
        if parsed.path.startswith("/api/"):
            api_path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
            self._serve_json(*service.handle_api(self.command, api_path, self._read_body(), self.headers))
            return
        self._serve_html_404()
    except HttpError as exc:
        ...

def _serve_static_request(self, request_path: str) -> None:
    relative = request_path[len("/static/") :]
    if not relative or "\x00" in relative:
        self._serve_html_404()
        return
    candidate = (STATIC_ROOT / relative).resolve()
    static_root = STATIC_ROOT.resolve()
    if static_root not in candidate.parents and candidate != static_root:
        self._serve_html_404()
        return
    content_type = STATIC_CONTENT_TYPES.get(candidate.suffix)
    if content_type is None:
        self._serve_html_404()
        return
    self._serve_static(candidate, content_type)
```

- [ ] **Step 4: Run the static asset test again**

Run:

```bash
python3 -m unittest tests.test_web_management.WebManagementHTTPActionTests.test_static_assets_are_served
```

Expected result after implementation:

```text
Ran 1 test ... OK
```

### Task 4: Build The New Markdown Renderer Module

**Files:**

- Create: `tools/launcher/assets/web-management/markdown-renderer.js`
- Modify: `tests/web_management_markdown_renderer.test.js`

- [ ] **Step 1: Create the renderer UMD module**

Create `tools/launcher/assets/web-management/markdown-renderer.js` with this shape:

```js
(function (root, factory) {
  const exportsObject = factory(root);
  if (typeof module === 'object' && module.exports) {
    module.exports = exportsObject;
  }
  root.BuddySwitchMarkdownRenderer = exportsObject.defaultRenderer || exportsObject;
}(typeof globalThis !== 'undefined' ? globalThis : this, function (root) {
  'use strict';

  const SAFE_LINK_PATTERN = /^(https?:\/\/|\/|#)/i;
  const SAFE_IMAGE_PATTERN = /^https?:\/\//i;

  function normalizeUrl(value, pattern) {
    const url = String(value || '').trim();
    return pattern.test(url) ? url : '';
  }

  function isExternalHttpUrl(value) {
    return /^https?:\/\//i.test(String(value || '').trim());
  }

  function escapeAttribute(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function createMarkdownRenderer(deps) {
    const markdownIt = deps && deps.markdownIt ? deps.markdownIt : root.markdownit;
    const purifier = deps && deps.DOMPurify ? deps.DOMPurify : root.DOMPurify;
    const highlighter = deps && Object.prototype.hasOwnProperty.call(deps, 'hljs') ? deps.hljs : root.hljs;
    if (typeof markdownIt !== 'function') {
      throw new Error('Markdown parser dependency is unavailable.');
    }
    if (!purifier || typeof purifier.sanitize !== 'function') {
      throw new Error('Markdown sanitizer dependency is unavailable.');
    }

    const md = markdownIt({
      html: false,
      linkify: true,
      typographer: false,
      breaks: false,
      highlight(code, language) {
        const lang = String(language || '').trim();
        if (highlighter && lang && highlighter.getLanguage && highlighter.getLanguage(lang)) {
          return highlighter.highlight(code, { language: lang, ignoreIllegals: true }).value;
        }
        return '';
      },
    });

    const defaultLinkOpen = md.renderer.rules.link_open || function (tokens, idx, options, _env, self) {
      return self.renderToken(tokens, idx, options);
    };
    md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
      const token = tokens[idx];
      const hrefIndex = token.attrIndex('href');
      const href = hrefIndex >= 0 ? token.attrs[hrefIndex][1] : '';
      const safeHref = normalizeUrl(href, SAFE_LINK_PATTERN);
      if (!safeHref) {
        token.attrs = (token.attrs || []).filter((attr) => attr[0] !== 'href');
      } else {
        token.attrSet('href', safeHref);
        if (isExternalHttpUrl(safeHref)) {
          token.attrSet('target', '_blank');
          token.attrSet('rel', 'noopener noreferrer');
        }
      }
      return defaultLinkOpen(tokens, idx, options, env, self);
    };

    md.renderer.rules.image = function (tokens, idx) {
      const token = tokens[idx];
      const srcIndex = token.attrIndex('src');
      const src = srcIndex >= 0 ? token.attrs[srcIndex][1] : '';
      const safeSrc = normalizeUrl(src, SAFE_IMAGE_PATTERN);
      if (!safeSrc) {
        return '';
      }
      const alt = token.content || '';
      return '<img src="' + escapeAttribute(safeSrc) + '" alt="' + escapeAttribute(alt) + '" loading="lazy" referrerpolicy="no-referrer">';
    };

    function renderTaskLists(html) {
      return html
        .replace(/<li>\s*\[ \]\s+/g, '<li class="task-list-item"><input class="task-list-item-checkbox" type="checkbox" disabled> ')
        .replace(/<li>\s*\[[xX]\]\s+/g, '<li class="task-list-item"><input class="task-list-item-checkbox" type="checkbox" checked disabled> ')
        .replace(/<ul>\s*(<li class="task-list-item">)/g, '<ul class="contains-task-list">$1');
    }

    function sanitize(html) {
      return purifier.sanitize(html, {
        ALLOWED_TAGS: [
          'a', 'blockquote', 'br', 'code', 'del', 'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
          'hr', 'img', 'input', 'li', 'ol', 'p', 'pre', 'span', 'strong', 'table', 'tbody',
          'td', 'th', 'thead', 'tr', 'ul',
        ],
        ALLOWED_ATTR: [
          'alt', 'checked', 'class', 'disabled', 'href', 'loading', 'referrerpolicy', 'rel',
          'src', 'target', 'title', 'type',
        ],
        ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto):|\/|#)/i,
      });
    }

    function renderMarkdownMessageHtml(content) {
      const rendered = md.render(String(content || ''));
      const withTasks = renderTaskLists(rendered);
      const clean = sanitize(withTasks);
      return clean.trim() || '<p></p>';
    }

    return { renderMarkdownMessageHtml };
  }

  let defaultRenderer = null;
  try {
    defaultRenderer = createMarkdownRenderer({});
  } catch (_error) {
    defaultRenderer = null;
  }

  return {
    createMarkdownRenderer,
    defaultRenderer,
    renderMarkdownMessageHtml(content) {
      if (!defaultRenderer) {
        throw new Error('Markdown renderer dependencies are unavailable.');
      }
      return defaultRenderer.renderMarkdownMessageHtml(content);
    },
  };
}));
```

Note: this module has no handwritten Markdown block parser. The small `renderTaskLists` post-process is scoped to the GFM task-list extension only and must stay covered by tests.

- [ ] **Step 2: Run renderer tests**

Run:

```bash
node tests/web_management_markdown_renderer.test.js
```

Expected result after implementation:

```text
ok - renders CommonMark headings and paragraphs
ok - renders GFM-style structures needed by BuddySwitch conversations
ok - renders fenced code with explicit language highlighting only
ok - constrains links and images to safe protocols
ok - sanitizer is always invoked before returning html
```

### Task 5: Wire The Renderer Into HTML And App Without Compatibility

**Files:**

- Modify: `tools/launcher/assets/web-management/index.html`
- Modify: `tools/launcher/assets/web-management/app.js`
- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tests/web_management_ui_contract.test.js`

- [ ] **Step 1: Add browser script and style order**

In `index.html`, replace the single app script with:

```html
    <script src="/static/vendor/markdown-it/markdown-it.min.js"></script>
    <script src="/static/vendor/dompurify/purify.min.js"></script>
    <script src="/static/vendor/highlightjs/highlight.min.js"></script>
    <script src="/static/markdown-renderer.js"></script>
    <script src="/static/app.js"></script>
```

Add the highlight stylesheet:

```html
    <link rel="stylesheet" href="/static/vendor/highlightjs/github.min.css">
```

- [ ] **Step 2: Update contract tests for HTML loading**

In `tests/web_management_ui_contract.test.js`, assert script order by comparing indexes:

```js
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
```

- [ ] **Step 3: Remove old parser from app.js**

Delete these function implementations from `app.js`:

```text
sanitizeMarkdownHref
renderInlineMarkdownHtml
isFenceLine
isUnorderedListLine
isOrderedListLine
isBlockquoteLine
splitMarkdownTableCells
isTableDividerLine
isTableStart
isMarkdownBlockStart
renderMarkdownTableHtml
renderMarkdownMessageHtml
```

At the top of the app factory, capture the renderer:

```js
  const markdownRenderer = root.BuddySwitchMarkdownRenderer;
```

Update the IIFE factory call from `factory()` to `factory(root)`.

Add one app helper:

```js
  function renderMessageContentHtml(content) {
    if (!markdownRenderer || typeof markdownRenderer.renderMarkdownMessageHtml !== 'function') {
      throw new Error('Markdown renderer is not available.');
    }
    return markdownRenderer.renderMarkdownMessageHtml(content);
  }
```

Update `renderImConversation`:

```js
'<div class="markdown-body">' + renderMessageContentHtml(entry.content) + '</div>',
```

Do not keep a local escape-only or old-parser fallback.

- [ ] **Step 4: Update Node UI tests to load the renderer before app.js**

At the top of `tests/web_management_ui_state.test.js`, before requiring `app.js`, set the global renderer:

```js
const rendererModule = require(path.join(__dirname, '..', 'tools', 'launcher', 'assets', 'web-management', 'markdown-renderer.js'));
const markdownIt = require(path.join(__dirname, '..', 'tools', 'launcher', 'assets', 'web-management', 'vendor', 'markdown-it', 'index.cjs.js'));

globalThis.BuddySwitchMarkdownRenderer = rendererModule.createMarkdownRenderer({
  markdownIt,
  DOMPurify: {
    sanitize(html) {
      return html;
    },
  },
  hljs: null,
});

const app = require(path.join(__dirname, '..', 'tools', 'launcher', 'assets', 'web-management', 'app.js'));
```

Replace the old exact HTML assertions in `direct thread renders markdown replies inside stable bubble boundaries` with assertions that prove the conversation bubble uses renderer output:

```js
assert.match(elements.imConversation.innerHTML, /<h2>Short answer<\/h2>|<strong>Short answer:<\/strong>/);
assert.match(elements.imConversation.innerHTML, /<ul>/);
assert.match(elements.imConversation.innerHTML, /<blockquote>/);
assert.match(elements.imConversation.innerHTML, /<pre><code/);
assert.match(elements.imConversation.innerHTML, /<table>/);
assert.match(elements.imConversation.innerHTML, /href="#proof"/);
```

- [ ] **Step 5: Run UI state and contract tests**

Run:

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
```

Expected result after wiring:

```text
all tests print ok lines and exit 0
```

### Task 6: Complete Markdown Bubble CSS

**Files:**

- Modify: `tools/launcher/assets/web-management/styles.css`
- Modify: `tests/web_management_ui_contract.test.js`

- [ ] **Step 1: Add CSS contract checks**

In `tests/web_management_ui_contract.test.js`, extend markdown CSS assertions to cover:

```js
[
  '.markdown-body h1',
  '.markdown-body h2',
  '.markdown-body h3',
  '.markdown-body hr',
  '.markdown-body img',
  '.markdown-body del',
  '.markdown-body .contains-task-list',
  '.markdown-body .task-list-item',
  '.markdown-body .task-list-item-checkbox',
  '.markdown-body pre code.hljs',
].forEach((selector) => {
  assertIncludes(stylesCss, selector);
});
```

- [ ] **Step 2: Add compact markdown styles**

Add styles inside the existing markdown section:

```css
.markdown-body h1,
.markdown-body h2,
.markdown-body h3,
.markdown-body h4,
.markdown-body h5,
.markdown-body h6 {
  margin: 0 0 8px;
  color: var(--ink);
  font-weight: 760;
  letter-spacing: 0;
}

.markdown-body h1 {
  font-size: 18px;
  line-height: 1.22;
}

.markdown-body h2 {
  font-size: 16px;
  line-height: 1.25;
}

.markdown-body h3,
.markdown-body h4,
.markdown-body h5,
.markdown-body h6 {
  font-size: 14px;
  line-height: 1.3;
}

.markdown-body hr {
  height: 1px;
  margin: 10px 0;
  border: 0;
  background: var(--line);
}

.markdown-body del {
  color: var(--muted);
}

.markdown-body img {
  display: block;
  max-width: 100%;
  max-height: 320px;
  margin: 8px 0;
  border: 1px solid var(--line);
  border-radius: 7px;
  object-fit: contain;
}

.markdown-body .contains-task-list {
  padding-left: 0;
  list-style: none;
}

.markdown-body .task-list-item {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr);
  gap: 7px;
  align-items: start;
}

.markdown-body .task-list-item-checkbox {
  width: 13px;
  height: 13px;
  margin: 2px 0 0;
  accent-color: var(--teal);
}

.markdown-body pre code.hljs {
  display: block;
  overflow-x: auto;
}
```

- [ ] **Step 3: Run CSS contract tests**

Run:

```bash
node tests/web_management_ui_contract.test.js
```

Expected result:

```text
all tests print ok lines and exit 0
```

### Task 7: Add Live Residue Scans For Old Markdown Rendering

**Files:**

- Modify: `tests/web_management_ui_contract.test.js`
- Modify: `tests/test_im_web_management_projection.py`

- [ ] **Step 1: Add JS live-surface scan**

Add a contract test that scans active WebUI source files:

```js
test('active webui source has no old handwritten markdown parser names', () => {
  const activeSources = {
    'app.js': appJs,
    'markdown-renderer.js': markdownRendererJs,
    'index.html': indexHtml,
    'styles.css': stylesCss,
  };
  const oldParserNames = [
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
  ];
  Object.entries(activeSources).forEach(([name, source]) => {
    oldParserNames.forEach((oldName) => {
      assert.equal(source.includes(oldName), false, `${name} still contains ${oldName}`);
    });
  });
});
```

- [ ] **Step 2: Add Python live-surface scan**

In `tests/test_im_web_management_projection.py`, add a test that scans the same active surfaces and excludes historical docs:

```python
def test_web_management_markdown_rebuild_has_no_old_parser_residue(self) -> None:
    surfaces = (
        ROOT / "tools" / "launcher" / "assets" / "web-management" / "app.js",
        ROOT / "tools" / "launcher" / "assets" / "web-management" / "markdown-renderer.js",
        ROOT / "tools" / "launcher" / "assets" / "web-management" / "index.html",
        ROOT / "tests" / "web_management_ui_state.test.js",
        ROOT / "tests" / "web_management_ui_contract.test.js",
    )
    forbidden = (
        "sanitizeMarkdownHref",
        "renderInlineMarkdownHtml",
        "isFenceLine",
        "isUnorderedListLine",
        "isOrderedListLine",
        "isBlockquoteLine",
        "splitMarkdownTableCells",
        "isTableDividerLine",
        "isTableStart",
        "isMarkdownBlockStart",
        "renderMarkdownTableHtml",
    )
    for surface in surfaces:
        source = surface.read_text(encoding="utf-8")
        for term in forbidden:
            with self.subTest(surface=surface.name, term=term):
                self.assertNotIn(term, source)
```

- [ ] **Step 3: Run residue scans**

Run:

```bash
node tests/web_management_ui_contract.test.js
python3 -m unittest tests.test_im_web_management_projection.WebManagementIMProjectionTests.test_web_management_markdown_rebuild_has_no_old_parser_residue
```

Expected result:

```text
both commands exit 0
```

### Task 8: Prove The End-To-End WebUI Markdown Contract On 8766

**Files:**

- No source files required.
- Use the running `http://127.0.0.1:8766/` WebUI.

- [ ] **Step 1: Confirm 8766 is owned by the intended worktree**

Run:

```bash
lsof -nP -iTCP:8766 -sTCP:LISTEN
pid="$(lsof -t -nP -iTCP:8766 -sTCP:LISTEN)"
test -n "$pid"
ps -p "$pid" -o pid,ppid,command
```

Expected command contains:

```text
/Users/chen/Dev/buddyswitch/.worktrees/fea-webui/tools/launcher/web_management.py --port 8766
```

- [ ] **Step 2: Reload the browser page**

Use the in-app browser on:

```text
http://127.0.0.1:8766/
```

Read page state after reload. Expected:

```text
selected actor rows load
no console error from markdown-renderer.js
```

- [ ] **Step 3: Verify existing Dev conversation renders headings**

In the Dev actor conversation, verify:

```text
## 我能做什么
## 常见能力
## 工作方式
```

are rendered as heading elements inside `.markdown-body`, not as literal text inside `<p>`.

Browser DOM check shape:

```js
Array.from(document.querySelectorAll('#im-conversation .markdown-body h1, #im-conversation .markdown-body h2, #im-conversation .markdown-body h3')).map((el) => el.textContent.trim())
```

Expected includes:

```text
我能做什么
常见能力
工作方式
```

- [ ] **Step 4: Verify existing PM conversation renders headings and long content**

Switch to PM actor. Verify:

```text
# PM 角色可用技能说明
## artifact-tool
## read-product-context
```

are rendered as headings, with message bubble layout still bounded.

Expected layout checks:

```text
document.scrollingElement.scrollWidth === document.scrollingElement.clientWidth
#room-thread overflow-y is auto
.composer, #instruction-input, and #send-button are visible at 1280x720
```

- [ ] **Step 5: Send one compact markdown smoke message**

Send this to Dev:

````markdown
请只回复下面这段 markdown，不要解释：

# MD_RENDER_SMOKE_20260708

- [x] parsed
- [ ] safe

```js
const ok = true;
```
````

Expected reply contains `MD_RENDER_SMOKE_20260708`. The heading, task-list checkboxes, and code block are rendered in the direct thread.

- [ ] **Step 6: Check runtime logs and layout after reply**

Expected:

```text
error logs: []
message count increases
new reply chip behavior remains stable when user is not at bottom
body horizontal overflow remains false
```

## 7. Verification Command Set

Run focused verification first:

```bash
node tests/web_management_markdown_renderer.test.js
node tests/web_management_ui_contract.test.js
node tests/web_management_ui_state.test.js
python3 -m unittest tests.test_web_management.WebManagementHTTPActionTests.test_static_assets_are_served
python3 -m unittest tests.test_im_web_management_projection.WebManagementIMProjectionTests.test_web_management_markdown_rebuild_has_no_old_parser_residue
node --check tools/launcher/assets/web-management/markdown-renderer.js
node --check tools/launcher/assets/web-management/app.js
```

Run broader relevant verification:

```bash
python3 -m unittest tests.test_web_management.WebManagementHTTPActionTests
python3 -m unittest tests.test_im_web_management_projection
```

Run exact residue scan over live surfaces:

```bash
rg -n "sanitizeMarkdownHref|renderInlineMarkdownHtml|isFenceLine|isUnorderedListLine|isOrderedListLine|isBlockquoteLine|splitMarkdownTableCells|isTableDividerLine|isTableStart|isMarkdownBlockStart|renderMarkdownTableHtml" tools/launcher/assets/web-management tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js tests/test_im_web_management_projection.py
```

Expected result after rebuild:

```text
no matches
```

Run host resource check around any broad run that starts or reuses the local WebUI server:

```bash
lsof -nP -iTCP:8766 -sTCP:LISTEN
```

Expected:

```text
one listener, owned by the intended fea-webui web_management.py process
```

## 8. Completion Criteria

The rebuild is complete only when all criteria are true:

- `app.js` contains no old handwritten markdown parser helper names.
- `app.js` delegates message body rendering to the new renderer boundary.
- `markdown-renderer.js` is the only active WebUI file that defines `renderMarkdownMessageHtml`.
- Vendored assets exist with exact provenance and licenses.
- Static serving supports local vendor assets through a path-safe `/static/...` boundary.
- No CDN URL is introduced.
- No `node_modules` or frontend build chain is introduced.
- Node renderer tests prove CommonMark headings, GFM structures, safe links/images, explicit code highlighting, and sanitizer invocation.
- Python static asset tests prove renderer and vendor files are served and path traversal is rejected.
- Residue scans over live source and tests return no old parser names.
- `http://127.0.0.1:8766/` renders existing Dev and PM markdown headings as heading elements.
- The 8766 direct-thread send/reply smoke still works after rebuild.
- The message layout remains bounded at PC viewport sizes, including 1280x720.
- Console error logs are empty during browser acceptance.

## 9. Non-Goals

- Do not migrate the WebUI to React, Vite, npm scripts, or a frontend bundler.
- Do not render markdown on the Python server.
- Do not support raw HTML as a product feature.
- Do not keep an escape-only renderer as a compatibility path.
- Do not keep the old handwritten parser under a new name.
- Do not add broad WebUI redesign work while performing this renderer rebuild.

## 10. Plan Self-Review

Coverage check:

- Objective is restated as a forward rebuild with no dual path.
- Bitter principles are translated into task gates.
- Current code evidence names the actual files and old parser terms.
- Module boundaries assign parser, sanitizer, UI projection, static serving, and CSS responsibilities clearly.
- Implementation tasks include red tests, vendoring, static routing, renderer creation, app wiring, CSS, residue scans, and browser acceptance.
- Completion criteria map to behavior, live surface cleanup, and 8766 user-visible output.

Ambiguity check:

- The renderer is the only markdown owner.
- `app.js` cannot fall back to old rendering.
- Raw HTML is disabled.
- Highlighting is explicit-language only.
- Task-list handling is the only allowed small post-process and is scoped to GFM task-list markers.

Residual risk:

- DOMPurify is exercised fully in the browser acceptance path, while Node unit tests inject a sanitizer to keep the existing test stack lightweight.
- The highlighter is included from `@highlightjs/cdn-assets`, not the base `highlight.js` package, because the CDN-assets package contains browser-ready files.
- If future work adds more markdown extensions, it must extend `markdown-renderer.js` and its tests, not `app.js`.
