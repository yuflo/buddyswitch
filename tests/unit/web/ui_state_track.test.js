'use strict';

const { test } = require('node:test');
const { assert, fs, path, rendererModule, MarkdownIt, app, identityRef, imMessage, deferred, okResponse, lifecycleOperation, imNotFoundResponse, waitFor, createRenderElements } = require('./ui_state_harness');

test('track payload sync chooses first track and keeps comments inside detail state', () => {
  const state = app.createState();

  app.applyTracksPayload(state, {
    tracks: [
      { id: 'track-alpha', title: 'Actor console' },
      { id: 'track-beta', title: 'Follow up' },
    ],
  });
  app.applyTrackDetailPayload(state, {
    track: {
      id: 'track-alpha',
      comment_threads: [{ thread_id: 'thread-open', comments: [{ id: 'comment-1' }] }],
      comment_summary: { comment_count: 1, open_thread_count: 1, resolved_thread_count: 0 },
    },
  });

  assert.equal(state.selectedTrackId, 'track-alpha');
  assert.equal(state.selectedTrackDetail.id, 'track-alpha');
  assert.deepEqual(state.selectedTrackDetail.comment_threads[0].comments.map((row) => row.id), ['comment-1']);
});

test('Track Studio renders read-only materials proofs updates and comment threads', () => {
  const html = app.renderTrackDetailHtml({
    id: 'track-alpha',
    title: 'Team Room redesign',
    outcome: 'Ship the Team room shell',
    state: 'active',
    now: { next: 'Render Track Studio', blocker: null },
    updated_at: '2026-07-01T10:00:00Z',
    materials: [{ label: 'Brief', artifact_id: 'artifact-brief', template: 'markdown' }],
    proofs: [{ label: 'Proof', artifact_id: 'artifact-proof', template: 'markdown' }],
    updates: [{ id: 'upd-1', summary: 'Decision captured', kind: 'decision' }],
    comment_summary: { comment_count: 2, open_thread_count: 1 },
    comment_threads: [{ thread_id: 'thread-open', status: 'open', latest_comment_preview: 'Looks right', comment_count: 2 }],
  });

  assert.match(html, /Team Room redesign/);
  assert.match(html, /doc-title/);
  assert.match(html, /Current state/);
  assert.match(html, /Materials and proofs/);
  assert.match(html, /Brief/);
  assert.match(html, /Proof/);
  assert.match(html, /Decision captured/);
  assert.match(html, /Total comments/);
  assert.match(html, /Looks right/);
  assert.doesNotMatch(html, /<textarea|composer|submit|<button[^>]*>Resolve|collaborators/i);
});

test('Track Studio rail renders read-only comment context without write controls', () => {
  const html = app.renderTrackStudioRailHtml({
    id: 'track-alpha',
    state: 'active',
    outcome: 'Ship the Team room shell',
    now: { next: 'Render Track Studio', blocker: null },
    comment_summary: { comment_count: 2, open_thread_count: 1, resolved_thread_count: 1 },
    comment_threads: [
      {
        thread_id: 'thread-open',
        status: 'open',
        latest_comment_preview: 'Looks right',
        comment_count: 2,
      },
    ],
  });

  assert.match(html, /Context/);
  assert.match(html, /Comments/);
  assert.match(html, /thread-open/);
  assert.match(html, /Looks right/);
  assert.doesNotMatch(html, /<textarea|composer|submit|<button[^>]*>Resolve/i);
});

test('manual refresh renders tracks list before selected conversation completes', async () => {
  const originalFetch = globalThis.fetch;
  const conversation = deferred();
  const conversationStarted = deferred();
  let refresh;
  let assertionError = null;

  globalThis.fetch = function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/health') {
      return Promise.resolve(okResponse({}));
    }
    if (requestUrl === '/api/roles') {
      return Promise.resolve(okResponse({ roles: [{ id: 'market', label: 'Market' }] }));
    }
    if (requestUrl === '/api/actors') {
      return Promise.resolve(okResponse({
        actors: [
          { actor_id: 'act-old', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
        ],
      }));
    }
    if (requestUrl === '/api/tracks') {
      return Promise.resolve(okResponse({
        tracks: [
          { id: 'track-new', title: 'Progressive refresh', state: 'active', comment_summary: { open_thread_count: 2 } },
        ],
      }));
    }
    if (requestUrl === '/api/actors/act-old/console') {
      return Promise.resolve(okResponse({
        console: {
          actor: { actor_id: 'act-old', role: 'market' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-old', thread_status: 'idle' },
          task_sys: { active_count: 0, active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-old', role_id: 'market' } },
        },
      }));
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-old&limit=50') {
      conversationStarted.resolve();
      return conversation.promise;
    }
    if (requestUrl === '/api/tracks/track-new') {
      return Promise.resolve(okResponse({
        track: { id: 'track-new', title: 'Progressive refresh', state: 'active' },
      }));
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.selectedActorId = 'act-old';
    state.actors = [
      { actor_id: 'act-old', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];

    refresh = app.refreshVisibleRegionsWithFeedback(state, elements);
    refresh.catch(function () {});
    await conversationStarted.promise;
    await waitFor(
      () => /track-new/.test(elements.tracksList.innerHTML),
      'tracks list before conversation resolves',
      200
    );

    try {
      assert.match(elements.tracksList.innerHTML, /track-new/);
      assert.match(elements.tracksList.innerHTML, /Progressive refresh/);
      assert.match(elements.imConversation.innerHTML, /thread|conversation|skeleton|loading/i);
    } catch (error) {
      assertionError = error;
    }

    conversation.resolve(imNotFoundResponse());
    await refresh;
    if (assertionError) {
      throw assertionError;
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('section copy follows Team room and Tracks destinations', () => {
  assert.deepEqual(app.sectionCopy('actors'), {
    title: 'Team room',
    summary: 'Message teammates, inspect current runtime facts, and keep coordination in one room.',
  });
  assert.deepEqual(app.sectionCopy('tracks'), {
    title: 'Tracks',
    summary: 'Review Track outcomes, current state, materials, proofs, updates, and comments.',
  });
});
