# Web Management Vendored Markdown Dependencies

This directory vendors browser-ready runtime assets for the BuddySwitch Web Management UI. The Web UI serves them from `/static/vendor/...` so the localhost page has one deterministic markdown rendering path and no CDN/build-step dependency.

## Packages

- `markdown-it@14.3.0`
  - Source: npm package `markdown-it`
  - Vendored files: `markdown-it/markdown-it.min.js`, `markdown-it/LICENSE`
  - Purpose: CommonMark-compatible markdown parser with table and strikethrough support.
- `dompurify@3.3.0`
  - Source: npm package `dompurify`
  - Vendored files: `dompurify/purify.min.js`, `dompurify/LICENSE`, `dompurify/LICENSE-MPL`
  - Purpose: HTML sanitization for rendered message content.
- `highlight.js@11.11.1`
  - Source: npm package `highlight.js`
  - Vendored files: `highlightjs/highlight.min.js`, `highlightjs/github.min.css`, `highlightjs/LICENSE`
  - Purpose: Syntax highlighting for explicitly fenced code blocks.

## Update Rule

Update these files by replacing the current vendored package version directly. Do not add a second renderer, CDN fallback, legacy parser, or compatibility shim.
