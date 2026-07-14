'use strict';

const { test } = require('node:test');
const { assert, fs, path, rendererModule, MarkdownIt, app, identityRef, imMessage, deferred, okResponse, lifecycleOperation, imNotFoundResponse, waitFor, createRenderElements } = require('./ui_state_harness');

test('direct thread renders final prototype message bubbles', () => {
  const state = app.createState();
  const elements = createRenderElements();
  state.imConversation = [
    { direction: 'reply', sender: 'dev/act-dev-demo', deliveryStatus: '', wakeStatus: '', replyTo: '', content: 'Ready.' },
    { direction: 'sent', sender: 'you', deliveryStatus: 'delivered', wakeStatus: 'submitted', replyTo: '', content: 'Continue.' },
  ];

  app.renderImConversation(state, elements);

  assert.match(elements.imConversation.innerHTML, /class="message reply/);
  assert.match(elements.imConversation.innerHTML, /class="message you/);
  assert.match(elements.imConversation.innerHTML, /reply · dev\/act-dev-demo/);
  assert.match(elements.imConversation.innerHTML, /sent · you · delivered \/ submitted/);
});

test('new reply auto-scroll uses the pre-render bottom position', () => {
  const state = app.createState();
  const elements = createRenderElements();
  state.selectedActorId = 'act-market-demo';
  state.imConversationIdentityId = 'act-market-demo';
  elements.roomThread.scrollTop = 300;
  elements.roomThread.clientHeight = 200;
  elements.roomThread.scrollHeight = 500;
  elements.roomThread.scrollTo = function (options) {
    this.lastScrollTo = options;
    this.scrollTop = options.top;
  };
  Object.defineProperty(elements.imConversation, 'innerHTML', {
    get() {
      return this.renderedHtml || '';
    },
    set(value) {
      this.renderedHtml = value;
      elements.roomThread.scrollHeight = 650;
    },
  });

  app.recordSelectedActorEventMessage(state, imMessage({
    id: 'msg-bottom-reply',
    sender: 'act-market-demo',
    target: 'ext-web',
    content: 'Fresh reply while already at bottom.',
  }), 'act-market-demo');

  app.renderImConversation(state, elements);

  assert.match(elements.imConversation.innerHTML, /message reply is-new/);
  assert.equal(elements.newReplyChip.hidden, true);
  assert.deepEqual(elements.roomThread.lastScrollTo, { top: 650, behavior: 'smooth' });
});

test('actor card renders as soon as console resolves before conversation', async () => {
  const originalFetch = globalThis.fetch;
  const conversation = deferred();
  const conversationStarted = deferred();
  let selection;
  let assertionError = null;

  globalThis.fetch = function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/actors/act-new/console') {
      return Promise.resolve(okResponse({
        console: {
          actor: { actor_id: 'act-new', role: 'market' },
          runtime: {
            status: 'active',
            app_server_health: 'healthy',
            thread_id: 'thread-new',
            browser_port: 8765,
            thread_status: 'idle',
          },
          task_sys: { active_count: 0, active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-new', role_id: 'market' } },
        },
      }));
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-new&limit=50') {
      conversationStarted.resolve();
      return conversation.promise;
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [
      { actor_id: 'act-old', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
      { actor_id: 'act-new', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];
    state.selectedActorId = 'act-old';

    selection = app.selectActor(state, elements, 'act-new');
    selection.catch(function () {});
    await conversationStarted.promise;
    await waitFor(
      () => /Status/.test(elements.actorRuntimeDetail.innerHTML),
      'actor card render before conversation resolves',
      200
    );

    try {
      assert.equal(state.selectedActorId, 'act-new');
      assert.equal(state.actorSelectionPendingId, 'act-new');
      assert.equal(state.actorCardLoading, false);
      assert.equal(state.conversationLoading, true);
      assert.match(elements.actorRuntimeDetail.innerHTML, /Status/);
      assert.match(elements.actorRuntimeDetail.innerHTML, /Health/);
      assert.match(elements.actorRuntimeDetail.innerHTML, /Task Sys/);
      assert.match(elements.actorRuntimeDetail.innerHTML, /Tracks/);
      assert.doesNotMatch(elements.actorRuntimeDetail.innerHTML, /Loading/);
      assert.match(elements.imConversation.innerHTML, /thread|conversation|skeleton|loading/i);
    } catch (error) {
      assertionError = error;
    }

    conversation.resolve(imNotFoundResponse());
    await selection;
    assert.equal(state.actorSelectionPendingId, '');
    assert.equal(state.actorCardLoading, false);
    assert.equal(state.conversationLoading, false);
    if (assertionError) {
      throw assertionError;
    }
    if (state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('slow conversation does not disable runtime actions after console loads', async () => {
  const originalFetch = globalThis.fetch;
  const conversation = deferred();
  const conversationStarted = deferred();
  let selection;
  let assertionError = null;

  globalThis.fetch = function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/actors/act-controls/console') {
      return Promise.resolve(okResponse({
        console: {
          actor: { actor_id: 'act-controls', role: 'market' },
          runtime: {
            status: 'active',
            app_server_health: 'healthy',
            thread_id: 'thread-controls',
            thread_status: 'idle',
          },
          task_sys: { active_count: 0, active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-controls', role_id: 'market' } },
        },
      }));
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-controls&limit=50') {
      conversationStarted.resolve();
      return conversation.promise;
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [
      { actor_id: 'act-controls', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];

    selection = app.selectActor(state, elements, 'act-controls');
    selection.catch(function () {});
    await conversationStarted.promise;
    await waitFor(
      () => elements.stopButton.disabled === false
        && elements.clearButton.disabled === false
        && elements.openTuiButton.disabled === false,
      'runtime controls after console before conversation resolves',
      200
    );

    try {
      assert.equal(elements.stopButton.disabled, false);
      assert.equal(elements.clearButton.disabled, false);
      assert.equal(elements.openTuiButton.disabled, false);
      assert.equal(elements.actionAvailabilityStatus.textContent, '');
    } catch (error) {
      assertionError = error;
    }

    conversation.resolve(imNotFoundResponse());
    await selection;
    if (assertionError) {
      throw assertionError;
    }
    if (state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('manual refresh renders roster before selected conversation completes', async () => {
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
          { actor_id: 'act-roster-new', role: 'market', runtime: { status: 'inactive', app_server_health: 'unhealthy' } },
        ],
      }));
    }
    if (requestUrl === '/api/tracks') {
      return Promise.resolve(okResponse({ tracks: [] }));
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
      () => /data-roster-group="stopped"/.test(elements.actorsList.innerHTML)
        && />Stopped<[^]*>1</.test(elements.actorsList.innerHTML)
        && /Status/.test(elements.actorRuntimeDetail.innerHTML),
      'progressive roster and card render before conversation resolves',
      200
    );

    try {
      assert.match(elements.actorsList.innerHTML, />Stopped<[^]*>1</);
      assert.doesNotMatch(elements.actorsList.innerHTML, /act-roster-new/);
      assert.match(elements.actorRuntimeDetail.innerHTML, /Status/);
      assert.match(elements.imConversation.innerHTML, /thread|conversation|skeleton|loading/i);
    } catch (error) {
      assertionError = error;
    }

    conversation.resolve(imNotFoundResponse());
    await refresh;
    if (assertionError) {
      throw assertionError;
    }
    if (state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('manual refresh preserves visible conversation while revalidating it', async () => {
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
      return Promise.resolve(okResponse({ tracks: [] }));
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
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.selectedActorId = 'act-old';
    state.actors = [
      { actor_id: 'act-old', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];
    state.imConversationIdentityId = 'act-old';
    state.imConversation = [
      { id: 'msg-old', direction: 'reply', sender: 'market/act-old', deliveryStatus: '', wakeStatus: '', replyTo: '', content: 'still visible' },
    ];
    state.imSeenMessageIds = { 'msg-old': true };
    app.renderImConversation(state, elements);

    refresh = app.refreshVisibleRegionsWithFeedback(state, elements);
    refresh.catch(function () {});
    await conversationStarted.promise;

    try {
      assert.match(elements.imConversation.innerHTML, /still visible/);
      assert.doesNotMatch(elements.imConversation.innerHTML, /conversation-skeleton/);
      assert.equal(elements.imConversation.getAttribute('aria-busy'), 'true');
    } catch (error) {
      assertionError = error;
    }

    conversation.resolve(okResponse({
      messages: [
        imMessage({
          id: 'msg-new',
          sender: 'act-old',
          target: 'ext-web',
          content: 'fresh reply',
        }),
      ],
    }));
    await refresh;
    if (assertionError) {
      throw assertionError;
    }
    assert.match(elements.imConversation.innerHTML, /fresh reply/);
    if (state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('rapid actor switching keeps stale conversation from overwriting latest selection', async () => {
  const originalFetch = globalThis.fetch;
  let resolveFirstConversation;
  let resolveSecondConversation;
  const firstConversation = new Promise((resolve) => { resolveFirstConversation = resolve; });
  const secondConversation = new Promise((resolve) => { resolveSecondConversation = resolve; });

  globalThis.fetch = function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/actors/act-first/console') {
      return Promise.resolve(okResponse({
        console: {
          actor: { actor_id: 'act-first', role: 'dev' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-first', thread_status: 'idle' },
          task_sys: { active_count: 0, active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-first', role_id: 'dev' } },
        },
      }));
    }
    if (requestUrl === '/api/actors/act-second/console') {
      return Promise.resolve(okResponse({
        console: {
          actor: { actor_id: 'act-second', role: 'pm' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-second', thread_status: 'idle' },
          task_sys: { active_count: 0, active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-second', role_id: 'pm' } },
        },
      }));
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-first&limit=50') {
      return firstConversation;
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-second&limit=50') {
      return secondConversation;
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [
      { actor_id: 'act-first', role: 'dev', runtime: { status: 'active', app_server_health: 'healthy' } },
      { actor_id: 'act-second', role: 'pm', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];
    state.selectedActorId = 'act-old';

    const firstSelection = app.selectActor(state, elements, 'act-first');
    firstSelection.catch(function () {});
    const secondSelection = app.selectActor(state, elements, 'act-second');
    secondSelection.catch(function () {});

    resolveSecondConversation(okResponse({
      messages: [
        imMessage({
          id: 'msg-second',
          sender: 'act-second',
          target: 'ext-web',
          content: 'second wins',
        }),
      ],
    }));
    await waitFor(
      () => /second wins/.test(elements.imConversation.innerHTML),
      'latest conversation render',
      300
    );

    resolveFirstConversation(okResponse({
      messages: [
        imMessage({
          id: 'msg-first',
          sender: 'act-first',
          target: 'ext-web',
          content: 'first stale',
        }),
      ],
    }));

    await Promise.allSettled([firstSelection, secondSelection]);

    assert.equal(state.selectedActorId, 'act-second');
    assert.equal(state.imConversationIdentityId, 'act-second');
    assert.match(elements.imConversation.innerHTML, /second wins/);
    assert.doesNotMatch(elements.imConversation.innerHTML, /first stale/);
    if (state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('im event URL is external-session-wide with bounded wait only', () => {
  assert.equal(
    app.buildImEventsUrl(15000),
    '/api/im/events?wait_ms=15000'
  );
});

test('im conversation URL targets selected actor through unified im route', () => {
  assert.equal(
    app.buildImConversationUrl('act-market demo', 20),
    '/api/im/conversations/direct?identity_id=act-market%20demo&limit=20'
  );
});

test('im message URL fetches an individual message through unified im route', () => {
  assert.equal(app.buildImMessageUrl('msg demo/1'), '/api/im/messages/msg%20demo%2F1');
});

test('im ack payload uses explicit event id only', () => {
  assert.deepEqual(app.buildImAckPayload('imev-1'), { event_id: 'imev-1' });
});

test('record sent IM message keeps compact delivery status', () => {
  const state = app.createState();
  app.recordImSent(state, {
    message: { id: 'msg-sent-1' },
    delivery_status: 'accepted',
    wake_status: 'submitted',
  }, 'ping');

  assert.deepEqual(state.imConversation, [
    {
      id: 'msg-sent-1',
      direction: 'sent',
      sender: 'you',
      content: 'ping',
      deliveryStatus: 'accepted',
      wakeStatus: 'submitted',
      replyTo: '',
    },
  ]);
});

test('pending sent IM message is replaced with accepted server message', () => {
  const state = app.createState();
  const pendingId = app.recordImPendingSend(state, 'ping');

  assert.equal(state.imConversation.length, 1);
  assert.equal(state.imConversation[0].id, pendingId);
  assert.equal(state.imConversation[0].deliveryStatus, 'sending');

  app.replaceImPendingSend(state, pendingId, {
    message: { id: 'msg-sent-1' },
    delivery_status: 'accepted',
    wake_status: 'submitted',
  }, 'ping');

  assert.deepEqual(state.imConversation, [
    {
      id: 'msg-sent-1',
      direction: 'sent',
      sender: 'you',
      content: 'ping',
      deliveryStatus: 'accepted',
      wakeStatus: 'submitted',
      replyTo: '',
    },
  ]);
  assert.equal(state.imSeenMessageIds['msg-sent-1'], true);
  assert.equal(state.imSeenMessageIds[pendingId], undefined);
});

test('failed pending send is removed and draft can be restored by caller', () => {
  const state = app.createState();
  const pendingId = app.recordImPendingSend(state, 'ping');

  app.removeImEntry(state, pendingId);

  assert.deepEqual(state.imConversation, []);
  assert.equal(state.imSeenMessageIds[pendingId], undefined);
});

test('send completion cannot append the prior actor message after selection changes', async () => {
  const originalFetch = globalThis.fetch;
  const sessionResponse = deferred();
  const sendResponse = deferred();
  let sentTargetIdentityId = '';
  globalThis.fetch = async function (url, options) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/im/session') return sessionResponse.promise;
    if (requestUrl === '/api/im/messages') {
      sentTargetIdentityId = JSON.parse(options.body).target_identity_id;
      return sendResponse.promise;
    }
    if (requestUrl === '/api/actors/act-b/console') {
      return okResponse({
        console: {
          actor: { actor_id: 'act-b', role: 'dev' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-b', thread_status: 'idle' },
          task_sys: { active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-b', role_id: 'dev' } },
        },
      });
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-b&limit=50') {
      return imNotFoundResponse();
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [
      { actor_id: 'act-a', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
      { actor_id: 'act-b', role: 'dev', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];
    state.selectedActorId = 'act-a';
    state.actorConsole = {
      actor: { actor_id: 'act-a', role: 'market' },
      im: { target: { identity_id: 'act-a', role_id: 'market' } },
    };
    state.imConversationIdentityId = 'act-a';
    state.draftText = 'message for A';
    state.imSessionReady = false;
    state.imPolling = true;

    const send = app.sendCurrentDraft(state, elements);
    await waitFor(() => state.sendPending, 'A send pending');
    await app.selectActor(state, elements, 'act-b');
    assert.equal(state.sendPending, false);
    state.draftText = 'draft for B';

    sessionResponse.resolve(okResponse({}));
    await waitFor(() => sentTargetIdentityId !== '', 'captured send target');

    sendResponse.resolve(okResponse({
      message: { id: 'msg-for-a' },
      delivery_status: 'accepted',
      wake_status: 'submitted',
    }));
    await send;

    assert.equal(sentTargetIdentityId, 'act-a');
    assert.equal(state.selectedActorId, 'act-b');
    assert.equal(state.imConversationIdentityId, 'act-b');
    assert.deepEqual(state.imConversation, []);
    assert.equal(state.draftText, 'draft for B');
    assert.equal(state.message, '');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('stale send completion cannot clear a newer actor send pending state', async () => {
  const originalFetch = globalThis.fetch;
  const sendAResponse = deferred();
  const sendBResponse = deferred();
  let sendCalls = 0;
  globalThis.fetch = async function (url, options) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/im/messages') {
      sendCalls += 1;
      const target = JSON.parse(options.body).target_identity_id;
      assert.equal(target, sendCalls === 1 ? 'act-send-a' : 'act-send-b');
      return sendCalls === 1 ? sendAResponse.promise : sendBResponse.promise;
    }
    if (requestUrl === '/api/actors/act-send-b/console') {
      return okResponse({
        console: {
          actor: { actor_id: 'act-send-b', role: 'dev' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-b', thread_status: 'idle' },
          task_sys: { active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-send-b', role_id: 'dev' } },
        },
      });
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-send-b&limit=50') {
      return imNotFoundResponse();
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.actors = [
      { actor_id: 'act-send-a', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
      { actor_id: 'act-send-b', role: 'dev', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];
    state.selectedActorId = 'act-send-a';
    state.actorConsole = {
      actor: { actor_id: 'act-send-a', role: 'market' },
      im: { target: { identity_id: 'act-send-a', role_id: 'market' } },
    };
    state.imConversationIdentityId = 'act-send-a';
    state.imSessionReady = true;
    state.imPolling = true;
    state.draftText = 'message A';

    const sendA = app.sendCurrentDraft(state, elements);
    await waitFor(() => sendCalls === 1, 'A send request');
    await app.selectActor(state, elements, 'act-send-b');
    state.draftText = 'message B';
    const sendB = app.sendCurrentDraft(state, elements);
    await waitFor(() => sendCalls === 2, 'B send request');
    assert.equal(state.sendPending, true);

    sendAResponse.resolve(okResponse({
      message: { id: 'msg-send-a' },
      delivery_status: 'accepted',
      wake_status: 'submitted',
    }));
    await sendA;
    assert.equal(state.sendPending, true);

    sendBResponse.resolve(okResponse({
      message: { id: 'msg-send-b' },
      delivery_status: 'accepted',
      wake_status: 'submitted',
    }));
    await sendB;
    assert.equal(state.sendPending, false);
    assert.equal(state.selectedActorId, 'act-send-b');
    assert.deepEqual(state.imConversation.map((entry) => entry.id), ['msg-send-b']);
    if (state.actorRefreshTimer) {
      clearTimeout(state.actorRefreshTimer);
      state.actorRefreshTimer = null;
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('record projected IM messages keeps sent and reply directions', () => {
  const state = app.createState();
  const sentEcho = app.recordImProjectedMessage(state, imMessage({
    id: 'msg-sent-1',
    sender: 'ext-1',
    target: 'act-market-1',
    content: 'ping',
  }));
  const actorReply = app.recordImProjectedMessage(state, imMessage({
    id: 'msg-reply-1',
    sender: 'act-market-1',
    target: 'ext-1',
    content: 'pong',
    replyTo: 'msg-sent-1',
  }));

  assert.equal(sentEcho, true);
  assert.equal(actorReply, true);
  assert.deepEqual(state.imConversation, [
    {
      id: 'msg-sent-1',
      direction: 'sent',
      sender: 'you',
      content: 'ping',
      deliveryStatus: '',
      wakeStatus: '',
      replyTo: '',
    },
    {
      id: 'msg-reply-1',
      direction: 'reply',
      sender: 'market/act-market-1',
      content: 'pong',
      deliveryStatus: '',
      wakeStatus: '',
      replyTo: 'msg-sent-1',
    },
  ]);
});

test('clearing im conversation records owner identity and removes stale rows', () => {
  const state = app.createState();
  app.recordImProjectedMessage(state, imMessage({
    id: 'msg-stale',
    sender: 'act-market-old',
    target: 'ext-web',
    content: 'stale',
  }));

  app.clearImConversation(state, 'act-market-new');

  assert.equal(state.imConversationIdentityId, 'act-market-new');
  assert.deepEqual(state.imConversation, []);
  assert.deepEqual(state.imSeenMessageIds, {});
});

test('direct conversation payload replaces local render cache with persisted history', () => {
  const state = app.createState();
  app.recordImSent(state, {
    message: { id: 'msg-stale' },
    delivery_status: 'accepted',
    wake_status: 'submitted',
  }, 'stale');

  app.applyImConversationPayload(state, {
    messages: [
      imMessage({
        id: 'msg-sent-1',
        sender: 'ext-web',
        target: 'act-market-1',
        content: 'ping',
      }),
      imMessage({
        id: 'msg-reply-1',
        sender: 'act-market-1',
        target: 'ext-web',
        content: 'pong',
        replyTo: 'msg-sent-1',
      }),
    ],
  }, 'act-market-1');

  assert.equal(state.imConversationIdentityId, 'act-market-1');
  assert.deepEqual(state.imConversation.map((entry) => [entry.id, entry.direction, entry.content]), [
    ['msg-sent-1', 'sent', 'ping'],
    ['msg-reply-1', 'reply', 'pong'],
  ]);
  assert.deepEqual(Object.keys(state.imSeenMessageIds).sort(), ['msg-reply-1', 'msg-sent-1']);
});

test('fetched im message appends projected reply without browser cursor state', () => {
  const state = app.createState();

  app.recordImProjectedMessage(state, imMessage({
    id: 'msg-reply-1',
    sender: 'act-market-1',
    target: 'ext-web',
    content: 'pong',
  }));

  assert.equal(Object.prototype.hasOwnProperty.call(state, 'imEventCursor'), false);
  assert.deepEqual(state.imConversation.map((entry) => [entry.id, entry.direction, entry.content]), [
    ['msg-reply-1', 'reply', 'pong'],
  ]);
});

test('external-session-wide fetched event messages only append when they touch selected actor', () => {
  const state = app.createState();
  state.selectedActorId = 'act-market-selected';
  state.imConversationIdentityId = 'act-market-selected';

  const offScopeRecorded = app.recordSelectedActorEventMessage(
    state,
    imMessage({
      id: 'msg-dev',
      sender: 'act-dev-other',
      target: 'ext-web',
      content: 'dev pong',
    }),
    'act-market-selected'
  );

  const selectedRecorded = app.recordSelectedActorEventMessage(
    state,
    imMessage({
      id: 'msg-market',
      sender: 'act-market-selected',
      target: 'ext-web',
      content: 'market pong',
    }),
    'act-market-selected'
  );

  assert.equal(offScopeRecorded, false);
  assert.equal(selectedRecorded, true);
  assert.deepEqual(state.imConversation.map((entry) => [entry.id, entry.content]), [
    ['msg-market', 'market pong'],
  ]);
});

test('polling external-session-wide events acks off-selected actor message without rendering it', async () => {
  const originalFetch = global.fetch;
  const calls = [];
  global.fetch = async function (url, options) {
    calls.push({ url, method: options && options.method ? options.method : 'GET' });
    if (url === '/api/im/events?wait_ms=15000') {
      return {
        ok: true,
        json: async function () {
          return {
            ok: true,
            events: [{ event_id: 'imev-dev', message_id: 'msg-dev' }],
          };
        },
      };
    }
    if (url === '/api/im/messages/msg-dev') {
      return {
        ok: true,
        json: async function () {
          return {
            ok: true,
            message: imMessage({
              id: 'msg-dev',
              sender: 'act-dev-other',
              target: 'ext-web',
              content: 'dev pong',
            }),
          };
        },
      };
    }
    if (url === '/api/im/events/ack') {
      return {
        ok: true,
        json: async function () {
          return { ok: true };
        },
      };
    }
    throw new Error('unexpected fetch ' + url);
  };

  try {
    const state = app.createState();
    state.imSessionReady = true;
    state.selectedActorId = 'act-market-selected';
    state.imConversationIdentityId = 'act-market-selected';
    state.actors = [
      {
        actor_id: 'act-market-selected',
        role: 'market',
        runtime: { status: 'active', app_server_health: 'healthy', thread: { status: 'idle' } },
      },
      {
        actor_id: 'act-dev-other',
        role: 'dev',
        runtime: { status: 'active', app_server_health: 'healthy', thread: { status: 'idle' } },
      },
    ];
    state.actorConsole = {
      actor: { actor_id: 'act-market-selected', role: 'market' },
      runtime: { status: 'active', app_server_health: 'healthy', thread: { status: 'idle' } },
      task_sys: { active_tasks: [] },
      tracks: { items: [] },
      im: { target: { identity_id: 'act-market-selected', role_id: 'market' } },
    };

    await app.pollImEventsOnce(state, createRenderElements());

    assert.deepEqual(calls, [
      { url: '/api/im/events?wait_ms=15000', method: 'GET' },
      { url: '/api/im/messages/msg-dev', method: 'GET' },
      { url: '/api/im/events/ack', method: 'POST' },
    ]);
    assert.equal(state.imConversationIdentityId, 'act-market-selected');
    assert.deepEqual(state.imConversation, []);
  } finally {
    global.fetch = originalFetch;
  }
});

test('IM event processing cannot restore a prior actor conversation after selection changes', async () => {
  const originalFetch = globalThis.fetch;
  const messageFetchStarted = deferred();
  const messageResponse = deferred();
  globalThis.fetch = async function (url) {
    const requestUrl = typeof url === 'string' ? url : url && url.url ? url.url : '';
    if (requestUrl === '/api/im/events?wait_ms=15000') {
      return okResponse({ events: [{ event_id: 'imev-a', message_id: 'msg-a' }] });
    }
    if (requestUrl === '/api/im/messages/msg-a') {
      messageFetchStarted.resolve();
      return messageResponse.promise;
    }
    if (requestUrl === '/api/im/events/ack') return okResponse({});
    if (requestUrl === '/api/actors/act-b/console') {
      return okResponse({
        console: {
          actor: { actor_id: 'act-b', role: 'dev' },
          runtime: { status: 'active', app_server_health: 'healthy', thread_id: 'thread-b', thread_status: 'idle' },
          task_sys: { active_tasks: [] },
          tracks: { items: [] },
          im: { target: { identity_id: 'act-b', role_id: 'dev' } },
        },
      });
    }
    if (requestUrl === '/api/im/conversations/direct?identity_id=act-b&limit=50') {
      return imNotFoundResponse();
    }
    throw new Error('unexpected fetch ' + requestUrl);
  };

  try {
    const state = app.createState();
    const elements = createRenderElements();
    state.imSessionReady = true;
    state.selectedActorId = 'act-a';
    state.imConversationIdentityId = 'act-a';
    state.actors = [
      { actor_id: 'act-a', role: 'market', runtime: { status: 'active', app_server_health: 'healthy' } },
      { actor_id: 'act-b', role: 'dev', runtime: { status: 'active', app_server_health: 'healthy' } },
    ];
    state.actorConsole = {
      actor: { actor_id: 'act-a', role: 'market' },
      im: { target: { identity_id: 'act-a', role_id: 'market' } },
    };

    const poll = app.pollImEventsOnce(state, elements);
    await messageFetchStarted.promise;
    await app.selectActor(state, elements, 'act-b');

    messageResponse.resolve(okResponse({
      message: imMessage({
        id: 'msg-a',
        sender: 'act-a',
        target: 'ext-web',
        content: 'late A reply',
      }),
    }));
    await poll;

    assert.equal(state.selectedActorId, 'act-b');
    assert.equal(state.imConversationIdentityId, 'act-b');
    assert.deepEqual(state.imConversation, []);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
