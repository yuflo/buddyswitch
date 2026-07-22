'use strict';

const { test } = require('node:test');
const { assert, fs, path, rendererModule, MarkdownIt, app, identityRef, imMessage, deferred, okResponse, lifecycleOperation, imNotFoundResponse, waitFor, createRenderElements } = require('./ui_state_harness');

test('create button requires selected role and no start busy state', () => {
  assert.equal(app.computeCreateEnabled({ selectedRole: '' }), false);
  assert.equal(app.computeCreateEnabled({ selectedRole: 'pm' }), true);
});

test('state defaults to Team room as the primary section', () => {
  const state = app.createState();

  assert.equal(state.selectedSection, 'actors');
  assert.equal(state.selectedActorId, '');
  assert.equal(state.selectedTrackId, '');
  assert.deepEqual(state.actors, []);
  assert.deepEqual(state.tracks, []);
  assert.deepEqual(state.lifecycleOperations, {});
  assert.equal(Object.prototype.hasOwnProperty.call(state, 'createPending'), false);
  assert.equal(Object.prototype.hasOwnProperty.call(state, 'lifecycle' + 'PendingAction'), false);
  assert.equal(state.imConversationIdentityId, '');
});

test('actor roster payload exposes fallback facts without changing selection intent', () => {
  const state = app.createState();
  state.selectedActorId = 'act-missing';
  state.openTuiMessage = 'Launch sent to Terminal.';
  state.copyCommandMessage = 'Command copied.';
  app.recordImProjectedMessage(state, imMessage({
    id: 'msg-stale',
    sender: 'act-missing',
    target: 'ext-web',
    content: 'stale',
  }));

  const result = app.applyActorsPayload(state, {
    actors: [
      { actor_id: 'act-pm-demo', role: 'pm', lifecycle_state: 'active', runtime: { status: 'active' } },
      { actor_id: 'act-dev-demo', role: 'dev', lifecycle_state: 'stopped', runtime: { status: 'inactive' } },
    ],
  });

  assert.equal(state.selectedActorId, 'act-missing');
  assert.equal(state.openTuiMessage, 'Launch sent to Terminal.');
  assert.equal(state.copyCommandMessage, 'Command copied.');
  assert.equal(state.imConversationIdentityId, '');
  assert.equal(result.selectedActorPresent, false);
  assert.equal(result.preferredActorId, 'act-pm-demo');
  assert.deepEqual(state.actors.map((actor) => actor.actor_id), ['act-pm-demo', 'act-dev-demo']);
});

test('actor console payload cannot change selection intent', () => {
  const state = app.createState();
  state.selectedActorId = 'act-current';

  app.applyActorConsolePayload(state, {
    console: {
      actor: { actor_id: 'act-response', role: 'market' },
      runtime: { status: 'active', app_server_health: 'healthy' },
    },
  });

  assert.equal(state.selectedActorId, 'act-current');
  assert.equal(state.actorConsole.actor.actor_id, 'act-response');
});

test('teammate roster renders prototype person rows from supported actor facts', () => {
  const state = app.createState();
  state.roles = [{ id: 'dev', label: 'Developer', scope: 'product' }];
  state.selectedActorId = 'act-dev-demo';
  state.actors = [
    {
      actor_id: 'act-dev-demo',
      role: 'dev',
      lifecycle_state: 'active',
      runtime: { status: 'active', app_server_health: 'healthy' },
    },
  ];

  const html = app.renderActorRowsHtml(state);

  assert.match(html, /person-row/);
  assert.match(html, /avatar/);
  assert.match(html, />DV</);
  assert.match(html, /Developer/);
  assert.match(html, /act-dev-demo/);
  assert.match(html, /active/);
  assert.match(html, /healthy/);
  assert.doesNotMatch(html, /Dev Actor|PM Actor|72%|capacity|current focus|last proof/i);
});

test('actor roster groups starting active and stopped work with accurate counts', () => {
  const state = app.createState();
  state.roles = [
    { id: 'market', label: 'Market', scope: 'product' },
    { id: 'dev', label: 'Developer', scope: 'product' },
    { id: 'pm', label: 'PM', scope: 'product' },
  ];
  state.actors = [
    { actor_id: 'act-market-starting', role: 'market', lifecycle_state: 'starting', runtime: { status: 'inactive', app_server_health: '' } },
    { actor_id: 'act-dev-active', role: 'dev', lifecycle_state: 'active', runtime: { status: 'active', app_server_health: 'healthy' } },
    { actor_id: 'act-pm-stopped', role: 'pm', lifecycle_state: 'stopped', runtime: { status: 'inactive', app_server_health: 'unhealthy' } },
  ];
  state.selectedActorId = 'act-market-starting';

  const collapsedHtml = app.renderActorRowsHtml(state);

  assert.match(collapsedHtml, /data-roster-group="starting"/);
  assert.match(collapsedHtml, />Starting<[^]*>1</);
  assert.match(collapsedHtml, /data-roster-group="active"/);
  assert.match(collapsedHtml, />Active<[^]*>1</);
  assert.match(collapsedHtml, /data-roster-group="stopped"/);
  assert.match(collapsedHtml, />Stopped<[^]*>1</);
  assert.match(collapsedHtml, /act-dev-active/);
  assert.doesNotMatch(collapsedHtml, /act-pm-stopped/);
  assert.match(collapsedHtml, /data-actor-id="act-market-starting"[^>]*role="option"[^>]*aria-selected="true"/);
  assert.doesNotMatch(collapsedHtml, /data-operation-id|op-start-market/);
  assert.match(collapsedHtml, /data-roster-toggle="stopped"[^>]*aria-expanded="false"/);

  state.rosterStoppedExpanded = true;
  const expandedHtml = app.renderActorRowsHtml(state);

  assert.match(expandedHtml, /act-pm-stopped/);
  assert.match(expandedHtml, /data-actor-id="act-pm-stopped"[^>]*role="option"[^>]*aria-selected="false"/);
  assert.match(expandedHtml, /data-roster-toggle="stopped"[^>]*aria-expanded="true"/);
});

test('roster fallback facts prefer active actor over stopped inventory', () => {
  const state = app.createState();

  const result = app.applyActorsPayload(state, {
    actors: [
      { actor_id: 'act-stopped-first', role: 'pm', lifecycle_state: 'stopped', runtime: { status: 'inactive', app_server_health: 'unhealthy' } },
      { actor_id: 'act-active-second', role: 'dev', lifecycle_state: 'active', runtime: { status: 'active', app_server_health: 'healthy' } },
    ],
  });

  assert.equal(state.selectedActorId, '');
  assert.equal(result.selectedActorPresent, false);
  assert.equal(result.preferredActorId, 'act-active-second');
  assert.equal(state.rosterStoppedExpanded, false);
});

test('stopped-only roster exposes fallback without changing selection state', () => {
  const state = app.createState();

  const result = app.applyActorsPayload(state, {
    actors: [
      { actor_id: 'act-stopped-only', role: 'pm', lifecycle_state: 'stopped', runtime: { status: 'inactive', app_server_health: 'unhealthy' } },
    ],
  });

  assert.equal(state.selectedActorId, '');
  assert.equal(result.selectedActorPresent, false);
  assert.equal(result.preferredActorId, 'act-stopped-only');
  assert.equal(state.rosterStoppedExpanded, false);
});

test('role select repopulates role options after initial empty-shell render', () => {
  const originalDocument = globalThis.document;
  globalThis.document = {
    createElement(tagName) {
      return {
        tagName,
        value: '',
        textContent: '',
      };
    },
  };

  try {
    const state = app.createState();
    const appended = [];
    const elements = createRenderElements();
    elements.roleSelect = {
      options: [{ value: '', textContent: 'Select role' }],
      value: '',
      appendChild(option) {
        appended.push(option);
        this.options.push(option);
      },
    };
    state.roles = [
      { id: 'market', label: 'Market' },
      { id: 'dev', label: 'Dev' },
    ];
    state.selectedRole = 'market';

    app.renderRoleSelect(state, elements);

    assert.deepEqual(
      elements.roleSelect.options.map((option) => [option.value, option.textContent]),
      [
        ['', 'Select role'],
        ['market', 'Market (market)'],
        ['dev', 'Dev (dev)'],
      ]
    );
    assert.equal(elements.roleSelect.value, 'market');
  } finally {
    globalThis.document = originalDocument;
  }
});

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

test('direct thread renders markdown replies inside stable bubble boundaries', () => {
  const state = app.createState();
  const elements = createRenderElements();
  state.imConversation = [
    {
      id: 'msg-markdown',
      direction: 'reply',
      sender: 'market/act-market-demo',
      deliveryStatus: '',
      wakeStatus: '',
      replyTo: '',
      content: [
        '**Short answer:** launch is viable.',
        '',
        '- Keep actor health visible',
        '- Keep proof details in Track view',
        '',
        '> Decision: ship once send and reply are inspectable.',
        '',
        '```bash',
        'node tests/web_management_ui_state.test.js',
        '```',
        '',
        '| Area | Status |',
        '| --- | --- |',
        '| Message body | Markdown safe |',
        '',
        'Links stay low-key: [review](#proof) and `code`.',
      ].join('\n'),
    },
  ];

  app.renderImConversation(state, elements);

  assert.match(elements.imConversation.innerHTML, /class="markdown-body"/);
  assert.match(elements.imConversation.innerHTML, /<strong>Short answer:<\/strong>/);
  assert.match(elements.imConversation.innerHTML, /<li>Keep actor health visible<\/li>/);
  assert.match(elements.imConversation.innerHTML, /<li>Keep proof details in Track view<\/li>/);
  assert.match(elements.imConversation.innerHTML, /<blockquote>\s*<p>Decision: ship once send and reply are inspectable\.<\/p>\s*<\/blockquote>/);
  assert.match(elements.imConversation.innerHTML, /<pre><code class="[^"]*language-bash[^"]*">node tests\/web_management_ui_state\.test\.js\s*<\/code><\/pre>/);
  assert.match(elements.imConversation.innerHTML, /class="markdown-table-wrap"/);
  assert.match(elements.imConversation.innerHTML, /<th>Area<\/th>/);
  assert.match(elements.imConversation.innerHTML, /<td>Markdown safe<\/td>/);
  assert.match(elements.imConversation.innerHTML, /<a href="#proof">review<\/a>|<a href="#proof"[^>]*>review<\/a>/);
  assert.match(elements.imConversation.innerHTML, /<code>code<\/code>/);
});

test('new projected replies pop once and then settle into history', () => {
  const state = app.createState();
  const elements = createRenderElements();
  state.selectedActorId = 'act-market-demo';
  state.imConversationIdentityId = 'act-market-demo';

  const recorded = app.recordSelectedActorEventMessage(state, imMessage({
    id: 'msg-new-reply',
    sender: 'act-market-demo',
    target: 'ext-web',
    content: 'Fresh reply.',
  }), 'act-market-demo');

  assert.equal(recorded, true);

  app.renderImConversation(state, elements);

  assert.match(elements.imConversation.innerHTML, /message reply is-new/);
  assert.equal(state.imFreshMessageIds['msg-new-reply'], undefined);

  app.renderImConversation(state, elements);

  assert.doesNotMatch(elements.imConversation.innerHTML, /message reply is-new/);
  assert.match(elements.imConversation.innerHTML, /Fresh reply/);
});

test('web product route builders target coarse phase-two APIs only', () => {
  assert.equal(app.buildActorConsoleUrl('act-pm-demo'), '/api/actors/act-pm-demo/console');
  assert.equal(app.buildTrackDetailUrl('track-alpha'), '/api/tracks/track-alpha');
});

test('renderComposer updates the input and send button without actor list writes', () => {
  const state = app.createState();
  const elements = createRenderElements();
  state.draftText = 'ping';
  state.actors = [
    {
      actor_id: 'act-market-demo',
      role: 'market',
      lifecycle_state: 'active',
      runtime: { status: 'active', app_server_health: 'healthy' },
    },
  ];
  state.selectedActorId = 'act-market-demo';
  state.actorConsole = {
    actor: { actor_id: 'act-market-demo', role: 'market' },
    runtime: { status: 'active', app_server_health: 'healthy', thread_status: 'idle' },
  };
  elements.actorsList.innerHTML = 'unchanged';
  elements.stopButton.textContent = 'lifecycle-owned';

  app.renderComposer(state, elements);

  assert.equal(elements.instructionInput.value, 'ping');
  assert.equal(elements.sendButton.disabled, false);
  assert.equal(elements.actorsList.innerHTML, 'unchanged');
  assert.equal(elements.stopButton.textContent, 'lifecycle-owned');
});

test('no selection disables all instance actions', () => {
  assert.deepEqual(
    app.computeInstanceActionState(null, {
      draftText: 'Advance the brief',
      sendPending: false,
      lifecycleOperation: null,
    }),
    {
      canSend: false,
      canInterrupt: false,
      canStop: false,
      canDelete: false,
      canClear: false,
      canResume: false,
      canRetry: false,
    }
  );
});

test('send pending disables only send while preserving independent actor controls', () => {
  assert.deepEqual(
    app.computeInstanceActionState(
      {
        lifecycle_state: 'active',
        status: 'active',
        app_server_health: 'healthy',
        thread: { status: 'idle' },
      },
      {
        draftText: 'Advance the brief',
        sendPending: true,
        lifecycleOperation: null,
      }
    ),
    {
      canSend: false,
      canInterrupt: false,
      canStop: true,
      canDelete: false,
      canClear: true,
      canResume: false,
      canRetry: false,
    }
  );
});

test('attach action state is disabled without a selected instance', () => {
  assert.deepEqual(
    app.computeAttachActionState(null),
    {
      canAttach: false,
      message: '',
    }
  );
});

test('attach action state enables an active healthy instance with a thread', () => {
  assert.deepEqual(
    app.computeAttachActionState({
      status: 'active',
      app_server_health: 'healthy',
      thread_id: 'thread-main',
    }),
    {
      canAttach: true,
      message: '',
    }
  );
});

test('attach action state blocks an unhealthy instance', () => {
  assert.deepEqual(
    app.computeAttachActionState({
      status: 'active',
      app_server_health: 'unhealthy',
      thread_id: 'thread-main',
    }),
    {
      canAttach: false,
      message: 'Actor runtime is unhealthy.',
    }
  );
});

test('attach action state blocks an instance without a thread', () => {
  assert.deepEqual(
    app.computeAttachActionState({
      status: 'active',
      app_server_health: 'healthy',
      thread_id: null,
    }),
    {
      canAttach: false,
      message: 'No thread to attach.',
    }
  );
});

test('attach action state blocks an inactive instance', () => {
  assert.deepEqual(
    app.computeAttachActionState({
      status: 'inactive',
      app_server_health: 'healthy',
      thread_id: 'thread-main',
    }),
    {
      canAttach: false,
      message: 'Resume this actor first.',
    }
  );
});
