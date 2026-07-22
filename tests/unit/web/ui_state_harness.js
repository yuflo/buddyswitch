#!/usr/bin/env node
'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const rendererModule = require(path.join(
  __dirname,
  '..',
  '..',
  '..',
  'tools',
  'launcher',
  'assets',
  'web-management',
  'markdown-renderer.js'
));
const MarkdownIt = require(path.join(
  __dirname,
  '..',
  '..',
  '..',
  'tools',
  'launcher',
  'assets',
  'web-management',
  'vendor',
  'markdown-it',
  'markdown-it.min.js'
));

globalThis.BuddySwitchMarkdownRenderer = {
  createMarkdownRenderer() {
    return rendererModule.createMarkdownRenderer({
      markdownIt: MarkdownIt,
      DOMPurify: {
        sanitize(html) {
          return html;
        },
      },
      hljs: null,
    });
  },
};

const app = require(path.join(__dirname, '..', '..', '..', 'tools', 'launcher', 'assets', 'web-management', 'app.js'));

function identityRef(identityId) {
  return { id: identityId, type: identityId.indexOf('ext-') === 0 ? 'external' : 'actor' };
}

function imMessage({ id, sender, target, content, replyTo = null }) {
  return {
    id,
    sender_identity: identityRef(sender),
    target_identity: identityRef(target),
    content,
    reply_to: replyTo,
  };
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}

function okResponse(payload) {
  return {
    ok: true,
    json: async function () {
      return Object.assign({ ok: true }, payload || {});
    },
  };
}

function lifecycleOperation(overrides) {
  const operation = Object.assign({
    id: 'op-demo',
    action: 'clear',
    status: 'running',
    label: 'Clearing thread for act-market-demo',
    detail: 'Launcher command is running.',
    target: { actor_id: 'act-market-demo', role: 'market' },
    result: null,
    error: null,
  }, overrides || {});
  if (!operation.target) {
    operation.target = { actor_id: '', role: '' };
  }
  return operation;
}

function imNotFoundResponse() {
  return {
    ok: false,
    json: async function () {
      return {
        ok: false,
        error: { code: 'E_IM_NOT_FOUND', message: 'direct conversation not found' },
      };
    },
  };
}

async function waitFor(predicate, description, timeoutMs = 800) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (predicate()) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  throw new Error('Timed out waiting for ' + description);
}

function createRenderElements() {
  const node = () => {
    const attributes = {};
    const classes = new Set();
    return {
    textContent: '',
    value: '',
    hidden: false,
    disabled: false,
    innerHTML: '',
    className: '',
    classList: {
      toggle(name, force) {
        const shouldHave = force === undefined ? !classes.has(name) : Boolean(force);
        if (shouldHave) {
          classes.add(name);
        } else {
          classes.delete(name);
        }
      },
      contains(name) {
        return classes.has(name);
      },
    },
    querySelectorAll() { return []; },
      setAttribute(name, value) { attributes[name] = String(value); },
      getAttribute(name) {
        return Object.prototype.hasOwnProperty.call(attributes, name) ? attributes[name] : null;
      },
      removeAttribute(name) { delete attributes[name]; },
      focus() { this.focused = true; },
    };
  };
  return {
    serverStatus: node(),
    refreshButton: node(),
    messageBanner: node(),
    instructionInput: node(),
    actorView: node(),
    trackView: node(),
    actorNavButton: node(),
    tracksNavButton: node(),
    createButton: node(),
    roleSelect: Object.assign(node(), { options: [{}], appendChild() {} }),
    actorsList: node(),
    selectedContextAvatar: node(),
    selectedContextRole: node(),
    selectedContextId: node(),
    selectedContextRuntime: node(),
    selectedContextHealth: node(),
    actorRuntimeDetail: node(),
    actorTaskSummary: node(),
    actorTrackSummary: node(),
    actorCapabilityCard: node(),
    actorCapabilityStatus: node(),
    actorCapabilityToggle: node(),
    actorCapabilityParentSummary: node(),
    actorCapabilitySideSummary: node(),
    actorCapabilityPanel: node(),
    actorCapabilityMatrix: node(),
    actorCapabilityDetails: Object.assign(node(), { parentElement: { open: true } }),
    actorCapabilitySave: node(),
    actorCapabilityCancel: node(),
    actorCapabilityMessage: node(),
    tracksList: node(),
    trackDetail: node(),
    trackStudioRail: node(),
    imConversation: node(),
    roomThread: Object.assign(node(), { scrollTop: 0, scrollHeight: 0, clientHeight: 0, scrollTo(options) { this.lastScrollTo = options; } }),
    newReplyChip: Object.assign(node(), { classList: { add() {}, remove() {}, toggle() {} } }),
    sendButton: node(),
    interruptButton: node(),
    stopButton: node(),
    deleteButton: node(),
    clearButton: node(),
    resumeButton: node(),
    retryButton: node(),
    lifecycleOperationStatus: node(),
    actionAvailabilityStatus: node(),
    openTuiButton: node(),
    openTuiStatus: node(),
    copyCommandButton: node(),
    copyCommandStatus: node(),
    deleteConfirmationBackdrop: node(),
    deleteConfirmationTarget: node(),
    deleteConfirmationRole: node(),
    deleteConfirmationState: node(),
    deleteConfirmationLabel: node(),
    deleteConfirmationInput: node(),
    deleteConfirmationConfirm: node(),
    deleteConfirmationCancel: node(),
  };
}

function capabilityDto(parent = 'balanced', side = 'fast') {
  const levels = [
    { id: 'fast', label: 'Fast', description: 'Responsive, high-strength reasoning', model: 'gpt-5.6-luna', effort: 'xhigh' },
    { id: 'balanced', label: 'Balanced', description: 'Strong everyday work', model: 'gpt-5.6-terra', effort: 'high' },
    { id: 'deep', label: 'Deep', description: 'Complex reasoning and coding', model: 'gpt-5.6-sol', effort: 'xhigh' },
    { id: 'maximum', label: 'Maximum', description: 'Highest capability and cost', model: 'gpt-5.6-sol', effort: 'max' },
  ];
  const byId = Object.fromEntries(levels.map((row) => [row.id, row]));
  return {
    catalog_version: 1,
    levels,
    parent: { ...byId[parent], level: parent, effect: 'applies_before_next_parent_submit' },
    side: { ...byId[side], level: side, effect: 'applies_to_new_side_threads_only' },
  };
}

module.exports = { assert, fs, path, rendererModule, MarkdownIt, app, identityRef, imMessage, deferred, okResponse, lifecycleOperation, imNotFoundResponse, waitFor, createRenderElements, capabilityDto };
