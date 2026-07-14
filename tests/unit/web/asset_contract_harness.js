#!/usr/bin/env node
'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..', '..', '..');
const assetDir = path.join(root, 'tools', 'launcher', 'assets', 'web-management');
const indexHtml = fs.readFileSync(path.join(assetDir, 'index.html'), 'utf8');
const appJs = fs.readFileSync(path.join(assetDir, 'app.js'), 'utf8');
const markdownRendererPath = path.join(assetDir, 'markdown-renderer.js');
const markdownRendererJs = fs.existsSync(markdownRendererPath) ? fs.readFileSync(markdownRendererPath, 'utf8') : '';
const stylesCss = fs.readFileSync(path.join(assetDir, 'styles.css'), 'utf8');
const combinedAssets = [indexHtml, appJs, markdownRendererJs, stylesCss].join('\n');

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


module.exports = { assert, fs, path, root, assetDir, indexHtml, appJs, markdownRendererPath, markdownRendererJs, stylesCss, combinedAssets, assertIncludes, assertExcludes, assertNotMatches, collectCssDeclarations, assertCssDeclarations, assertCssDeclarationsExclude };
