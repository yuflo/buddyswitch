(function (root, factory) {
  const exportsObject = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = exportsObject;
  }
  root.BuddySwitchWebManagement = exportsObject;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const ACTOR_CONSOLE_REFRESH_INTERVAL_MS = 3000;

  function computeCreateEnabled(options) {
    return Boolean(options && options.selectedRole && !options.isCreating);
  }

  function computeInstanceActionState(instance, options) {
    const draftText = options && typeof options.draftText === 'string' ? options.draftText.trim() : '';
    const sendPending = Boolean(options && options.sendPending);
    const lifecyclePendingAction = options && typeof options.lifecyclePendingAction === 'string'
      ? options.lifecyclePendingAction
      : '';
    if (!instance) {
      return {
        canSend: false,
        canInterrupt: false,
        canStop: false,
        canDelete: false,
        canClear: false,
        canResume: false,
      };
    }

    const status = instance.status || '';
    const threadStatus = instance.thread && typeof instance.thread.status === 'string'
      ? instance.thread.status
      : '';
    const appServerHealthy = instance.app_server_health === 'healthy'
      || Boolean(instance.app_server && instance.app_server.healthy);
    const isActive = status === 'active';
    const isInactive = status === 'inactive';
    const threadBusy = threadStatus === 'active' || threadStatus === 'in_progress';
    const lifecyclePending = Boolean(lifecyclePendingAction);

    return {
      canSend: isActive && appServerHealthy && draftText.length > 0 && !sendPending,
      canInterrupt: isActive && appServerHealthy && threadBusy && !lifecyclePending,
      canStop: isActive && !lifecyclePending,
      canDelete: isInactive && !lifecyclePending,
      canClear: isActive && appServerHealthy && !threadBusy && !lifecyclePending,
      canResume: isInactive && !lifecyclePending,
    };
  }

  function describeInstanceActionState(instance, options) {
    const state = computeInstanceActionState(instance, options);
    const lifecyclePendingAction = options && typeof options.lifecyclePendingAction === 'string'
      ? options.lifecyclePendingAction
      : '';
    const status = instance && instance.status ? instance.status : '';
    const threadStatus = instance && instance.thread && typeof instance.thread.status === 'string'
      ? instance.thread.status
      : '';
    const appServerHealthy = instance
      ? instance.app_server_health === 'healthy' || Boolean(instance.app_server && instance.app_server.healthy)
      : false;
    const threadBusy = threadStatus === 'active' || threadStatus === 'in_progress';

    let clearReason = '';
    if (!instance) {
      clearReason = 'Select an actor.';
    } else if (lifecyclePendingAction) {
      clearReason = lifecyclePendingAction + ' running.';
    } else if (status !== 'active') {
      clearReason = 'Resume actor first.';
    } else if (!appServerHealthy) {
      clearReason = 'Runtime unhealthy.';
    } else if (threadBusy) {
      clearReason = 'Thread running.';
    }

    return Object.assign({}, state, {
      clearReason: state.canClear ? '' : clearReason,
    });
  }

  function computeOpenTuiState(instance, options) {
    const openTuiPending = Boolean(options && options.openTuiPending);
    if (!instance) {
      return {
        canOpenTui: false,
        message: '',
      };
    }
    if (openTuiPending) {
      return {
        canOpenTui: false,
        message: 'Opening...',
      };
    }

    const status = instance.status || '';
    if (status !== 'active') {
      return {
        canOpenTui: false,
        message: 'Resume this actor first.',
      };
    }

    const appServerHealthy = instance.app_server_health === 'healthy'
      || Boolean(instance.app_server && instance.app_server.healthy);
    if (!appServerHealthy) {
      return {
        canOpenTui: false,
        message: 'Actor runtime is unhealthy.',
      };
    }

    const threadId = typeof instance.thread_id === 'string' ? instance.thread_id.trim() : '';
    if (!threadId) {
      return {
        canOpenTui: false,
        message: 'No thread to attach.',
      };
    }

    return {
      canOpenTui: true,
      message: '',
    };
  }

  function createState() {
    return {
      selectedSection: 'actors',
      roles: [],
      actors: [],
      tracks: [],
      selectedRole: '',
      selectedActorId: '',
      actorConsole: null,
      selectedTrackId: '',
      selectedTrackDetail: null,
      draftText: '',
      healthOk: false,
      message: '',
      createPending: false,
      sendPending: false,
      refreshPending: false,
      lifecyclePendingAction: '',
      openTuiPending: false,
      actorSelectionPendingId: '',
      trackSelectionPendingId: '',
      actorSelectionRequestId: 0,
      trackSelectionRequestId: 0,
      openTuiMessage: '',
      openTuiCommand: '',
      imSessionReady: false,
      imConversationIdentityId: '',
      imConversation: [],
      imSeenMessageIds: {},
      imPolling: false,
      imPollTimer: null,
      actorRefreshTimer: null,
      actorRefreshInFlight: false,
    };
  }

  async function fetchJson(url, options) {
    const response = await fetch(url, options);
    let payload;
    try {
      payload = await response.json();
    } catch (_error) {
      payload = { ok: false, error: { message: 'Invalid server response.' } };
    }
    if (!response.ok || !payload.ok) {
      const error = new Error(payload && payload.error && payload.error.message ? payload.error.message : 'Request failed.');
      error.payload = payload;
      throw error;
    }
    return payload;
  }

  function isImConversationNotFoundError(error) {
    const payload = error && error.payload && typeof error.payload === 'object' ? error.payload : null;
    const detail = payload && payload.error && typeof payload.error === 'object' ? payload.error : null;
    return Boolean(detail && detail.code === 'E_IM_NOT_FOUND');
  }

  function formatValue(value) {
    if (value === null || value === undefined || value === '') {
      return 'None';
    }
    return String(value);
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function buildActorConsoleUrl(actorId) {
    return '/api/actors/' + encodeURIComponent(actorId) + '/console';
  }

  function buildTrackDetailUrl(trackId) {
    return '/api/tracks/' + encodeURIComponent(trackId);
  }

  function buildImEventsUrl(waitMs) {
    const normalizedWait = Number.isFinite(waitMs) && waitMs >= 0 ? Math.floor(waitMs) : 0;
    return '/api/im/events?wait_ms=' + encodeURIComponent(String(normalizedWait));
  }

  function buildImConversationUrl(identityId, limit) {
    const normalizedLimit = Number.isFinite(limit) && limit > 0 ? Math.floor(limit) : 20;
    return '/api/im/conversations/direct?identity_id=' + encodeURIComponent(identityId || '')
      + '&limit=' + encodeURIComponent(String(normalizedLimit));
  }

  function buildImMessageUrl(messageId) {
    return '/api/im/messages/' + encodeURIComponent(messageId || '');
  }

  function buildImAckPayload(eventId) {
    return { event_id: eventId || '' };
  }

  function clearOpenTuiFeedback(state) {
    state.openTuiMessage = '';
    state.openTuiCommand = '';
  }

  function selectSection(state, section) {
    state.selectedSection = section === 'tracks' ? 'tracks' : 'actors';
  }

  function applyActorsPayload(state, payload) {
    const previousActorId = state.selectedActorId;
    state.actors = payload && Array.isArray(payload.actors) ? payload.actors : [];
    const stillPresent = state.actors.some(function (actor) {
      return actor.actor_id === state.selectedActorId;
    });
    if (!stillPresent) {
      state.selectedActorId = state.actors.length ? state.actors[0].actor_id : '';
      state.actorConsole = null;
    }
    if (state.selectedActorId !== previousActorId) {
      clearOpenTuiFeedback(state);
      clearImConversation(state, state.selectedActorId);
    }
  }

  function applyActorConsolePayload(state, payload) {
    const consolePayload = payload && payload.console && typeof payload.console === 'object'
      ? payload.console
      : null;
    state.actorConsole = consolePayload;
    if (consolePayload && consolePayload.actor && typeof consolePayload.actor.actor_id === 'string') {
      state.selectedActorId = consolePayload.actor.actor_id;
    }
  }

  function applyTracksPayload(state, payload) {
    const previousTrackId = state.selectedTrackId;
    state.tracks = payload && Array.isArray(payload.tracks) ? payload.tracks : [];
    const stillPresent = state.tracks.some(function (track) {
      return track.id === state.selectedTrackId;
    });
    if (!stillPresent) {
      state.selectedTrackId = state.tracks.length ? state.tracks[0].id : '';
      state.selectedTrackDetail = null;
    }
    if (state.selectedTrackId !== previousTrackId) {
      state.selectedTrackDetail = null;
    }
  }

  function applyTrackDetailPayload(state, payload) {
    const detail = payload && payload.track && typeof payload.track === 'object'
      ? payload.track
      : null;
    state.selectedTrackDetail = detail;
    if (detail && typeof detail.id === 'string') {
      state.selectedTrackId = detail.id;
    }
  }

  function actorById(state, actorId) {
    return state.actors.find(function (actor) {
      return actor.actor_id === actorId;
    }) || null;
  }

  function selectedActorRuntime(state) {
    const consoleRuntime = state.actorConsole && state.actorConsole.runtime ? state.actorConsole.runtime : null;
    const actor = actorById(state, state.selectedActorId);
    const runtime = consoleRuntime || (actor && actor.runtime) || actor || null;
    if (!runtime) {
      return null;
    }
    const threadStatus = runtime.thread_status || (runtime.thread && runtime.thread.status) || '';
    return {
      actor_id: state.selectedActorId,
      role: state.actorConsole && state.actorConsole.actor ? state.actorConsole.actor.role : actor && actor.role,
      status: runtime.status,
      app_server_health: runtime.app_server_health,
      thread_id: runtime.thread_id,
      browser_port: runtime.browser_port,
      updated_at: runtime.updated_at,
      workspace_dir: runtime.workspace_dir,
      thread: { status: threadStatus },
      app_server: { healthy: runtime.app_server_health === 'healthy' },
    };
  }

  function selectedActorImTarget(state) {
    if (state.actorConsole && state.actorConsole.im && state.actorConsole.im.target) {
      return state.actorConsole.im.target;
    }
    const actor = actorById(state, state.selectedActorId);
    if (!actor || !actor.role || !actor.actor_id) {
      return null;
    }
    return {
      identity: { id: state.selectedActorId, type: 'actor' },
      identity_id: state.selectedActorId,
      role_id: actor.role,
    };
  }

  function identityLabel(identityId) {
    if (typeof identityId !== 'string' || !identityId) {
      return '';
    }
    if (identityId.indexOf('act-') === 0) {
      const parts = identityId.split('-');
      const roleId = parts.length > 2 ? parts[1] : '';
      return roleId ? roleId + '/' + identityId : identityId;
    }
    if (identityId.indexOf('ext-') === 0) {
      return 'you';
    }
    return identityId;
  }

  function clearImConversation(state, identityId) {
    state.imConversationIdentityId = typeof identityId === 'string' ? identityId : '';
    state.imConversation = [];
    state.imSeenMessageIds = {};
  }

  function rememberImEntry(state, entry) {
    if (!entry.id || state.imSeenMessageIds[entry.id]) {
      return false;
    }
    state.imSeenMessageIds[entry.id] = true;
    state.imConversation.push(entry);
    if (state.imConversation.length > 50) {
      state.imConversation = state.imConversation.slice(-50);
    }
    return true;
  }

  function createPendingMessageId() {
    return 'pending-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8);
  }

  function recordImPendingSend(state, content) {
    const pendingId = createPendingMessageId();
    rememberImEntry(state, {
      id: pendingId,
      direction: 'sent',
      sender: 'you',
      content: typeof content === 'string' ? content : '',
      deliveryStatus: 'sending',
      wakeStatus: '',
      replyTo: '',
    });
    return pendingId;
  }

  function removeImEntry(state, messageId) {
    if (!messageId) {
      return false;
    }
    const beforeLength = state.imConversation.length;
    state.imConversation = state.imConversation.filter(function (entry) {
      return entry.id !== messageId;
    });
    delete state.imSeenMessageIds[messageId];
    return state.imConversation.length !== beforeLength;
  }

  function replaceImPendingSend(state, pendingId, payload, content) {
    const messageId = payload && payload.message && payload.message.id ? payload.message.id : '';
    const replacement = {
      id: messageId,
      direction: 'sent',
      sender: 'you',
      content: typeof content === 'string' ? content : '',
      deliveryStatus: payload && payload.delivery_status ? payload.delivery_status : '',
      wakeStatus: payload && payload.wake_status ? payload.wake_status : '',
      replyTo: '',
    };
    let replaced = false;
    state.imConversation = state.imConversation.map(function (entry) {
      if (entry.id !== pendingId) {
        return entry;
      }
      replaced = true;
      return replacement;
    });
    delete state.imSeenMessageIds[pendingId];
    if (messageId) {
      state.imSeenMessageIds[messageId] = true;
    }
    if (!replaced) {
      rememberImEntry(state, replacement);
    }
    return replaced;
  }

  function recordImSent(state, payload, content) {
    const messageId = payload && payload.message && payload.message.id ? payload.message.id : '';
    return rememberImEntry(state, {
      id: messageId,
      direction: 'sent',
      sender: 'you',
      content: typeof content === 'string' ? content : '',
      deliveryStatus: payload && payload.delivery_status ? payload.delivery_status : '',
      wakeStatus: payload && payload.wake_status ? payload.wake_status : '',
      replyTo: '',
    });
  }

  function recordImProjectedMessage(state, message) {
    if (!message || typeof message !== 'object') {
      return false;
    }
    const fromIdentityId = typeof message.from_identity_id === 'string' ? message.from_identity_id : '';
    if (!fromIdentityId) {
      return false;
    }
    const sent = fromIdentityId.indexOf('ext-') === 0;
    return rememberImEntry(state, {
      id: typeof message.id === 'string' ? message.id : '',
      direction: sent ? 'sent' : 'reply',
      sender: sent ? 'you' : identityLabel(fromIdentityId),
      content: typeof message.content === 'string' ? message.content : '',
      deliveryStatus: '',
      wakeStatus: '',
      replyTo: typeof message.reply_to === 'string' ? message.reply_to : '',
    });
  }

  function messageTouchesActor(message, identityId) {
    if (!message || typeof message !== 'object' || typeof identityId !== 'string' || !identityId) {
      return false;
    }
    return message.from_identity_id === identityId || message.to_identity_id === identityId;
  }

  function applyImConversationPayload(state, payload, identityId) {
    clearImConversation(state, identityId);
    const messages = payload && Array.isArray(payload.messages) ? payload.messages : [];
    messages.forEach(function (message) {
      recordImProjectedMessage(state, message);
    });
  }

  function recordSelectedActorEventMessage(state, message, selectedIdentityId) {
    if (!messageTouchesActor(message, selectedIdentityId)) {
      return false;
    }
    if (state.imConversationIdentityId !== selectedIdentityId) {
      clearImConversation(state, selectedIdentityId);
    }
    return recordImProjectedMessage(state, message);
  }

  function resolveStatusTone(value) {
    if (value === 'active' || value === 'healthy' || value === 'idle' || value === 'none') {
      return 'healthy';
    }
    if (value === 'in_progress' || value === 'active_thread' || value === 'active turn' || value === 'blocked') {
      return 'busy';
    }
    if (value === 'inactive' || value === 'unhealthy' || value === 'stopped' || value === 'interrupted') {
      return 'danger';
    }
    return 'neutral';
  }

  function badge(value, tone) {
    const displayValue = formatValue(value);
    return '<span class="status-badge ' + escapeHtml(tone || resolveStatusTone(displayValue)) + '">' + escapeHtml(displayValue) + '</span>';
  }

  function renderEmpty(message) {
    return '<div class="empty-state">' + escapeHtml(message) + '</div>';
  }

  function roleLabelById(state, roleId) {
    const role = state.roles.find(function (row) {
      return row.id === roleId;
    });
    return role && role.label ? role.label : roleId;
  }

  function actorInitials(roleId, actorId) {
    const normalizedRole = typeof roleId === 'string' ? roleId.trim().toLowerCase() : '';
    const fixedRoleInitials = {
      dev: 'DV',
      pm: 'PM',
      test: 'TS',
      market: 'MK',
      design: 'DS',
    };
    if (fixedRoleInitials[normalizedRole]) {
      return fixedRoleInitials[normalizedRole];
    }
    if (normalizedRole) {
      return normalizedRole.slice(0, 2).toUpperCase();
    }
    const normalizedActor = typeof actorId === 'string' ? actorId.replace(/^act-/, '') : '';
    return normalizedActor ? normalizedActor.slice(0, 2).toUpperCase() : 'BS';
  }

  function actorVisualTone(runtime) {
    if (!runtime || runtime.status === 'inactive') {
      return 'violet';
    }
    if (runtime.app_server_health && runtime.app_server_health !== 'healthy') {
      return 'green';
    }
    return 'teal';
  }

  function actorDotClass(runtime) {
    if (!runtime || runtime.status === 'inactive') {
      return 'dot off';
    }
    if (runtime.app_server_health && runtime.app_server_health !== 'healthy') {
      return 'dot warn';
    }
    return 'dot';
  }

  function renderActorRowsHtml(state) {
    if (!state.actors.length) {
      return renderEmpty('No actors available.');
    }
    return state.actors.map(function (actor) {
      const selected = actor.actor_id === state.selectedActorId;
      const loading = actor.actor_id === state.actorSelectionPendingId;
      const runtime = actor.runtime || actor;
      const roleLabel = formatValue(roleLabelById(state, actor.role));
      const initials = actorInitials(actor.role, actor.actor_id);
      const tone = actorVisualTone(runtime);
      return [
        '<button class="person-row selectable-row actor-row' + (selected ? ' is-selected' : '') + (loading ? ' is-loading' : '') + '" type="button" data-actor-id="' + escapeHtml(actor.actor_id) + '">',
        '<span class="avatar ' + escapeHtml(tone) + '" aria-hidden="true">' + escapeHtml(initials) + '</span>',
        '<span>',
        '<strong>' + escapeHtml(roleLabel) + '</strong>',
        '<span class="micro mono">' + escapeHtml(formatValue(actor.actor_id)) + '</span>',
        '</span>',
        '<span class="row-status">',
        badge(runtime.status),
        badge(runtime.app_server_health),
        '<span class="' + escapeHtml(actorDotClass(runtime)) + '" aria-hidden="true"></span>',
        '</span>',
        '</button>',
      ].join('');
    }).join('');
  }

  function renderTrackRowsHtml(state) {
    if (!state.tracks.length) {
      return renderEmpty('No active Tracks.');
    }
    return state.tracks.map(function (track) {
      const selected = track.id === state.selectedTrackId;
      const loading = track.id === state.trackSelectionPendingId;
      const summary = track.comment_summary || {};
      return [
        '<button class="track-row selectable-row' + (selected ? ' is-selected' : '') + (loading ? ' is-loading' : '') + '" type="button" data-track-id="' + escapeHtml(track.id) + '">',
        '<strong>' + escapeHtml(formatValue(track.title)) + '</strong>',
        '<span class="micro mono">' + escapeHtml(formatValue(track.id)) + ' · ' + escapeHtml(formatValue(track.state)) + ' · ' + escapeHtml(formatValue(summary.open_thread_count || 0)) + ' open threads</span>',
        '</button>',
      ].join('');
    }).join('');
  }

  function detailRowsHtml(rows) {
    return rows.map(function (entry) {
      const valueClass = entry[2] ? ' class="' + entry[2] + '"' : '';
      return '<dt>' + escapeHtml(entry[0]) + '</dt><dd' + valueClass + '>' + escapeHtml(formatValue(entry[1])) + '</dd>';
    }).join('');
  }

  function renderRuntimeDetailHtml(state) {
    if (state.actorSelectionPendingId && state.actorSelectionPendingId === state.selectedActorId && !state.actorConsole) {
      return '<div class="metric"><span class="micro">Actor</span><strong class="mono">' + escapeHtml(formatValue(state.selectedActorId)) + '</strong></div>'
        + '<div class="metric"><span class="micro">Status</span><strong class="inline-loading">Loading...</strong></div>';
    }
    const runtime = selectedActorRuntime(state);
    const taskSys = state.actorConsole && state.actorConsole.task_sys ? state.actorConsole.task_sys : null;
    const tracks = state.actorConsole && state.actorConsole.tracks && Array.isArray(state.actorConsole.tracks.items)
      ? state.actorConsole.tracks.items
      : [];
    const metrics = [
      ['Status', runtime && runtime.status],
      ['Health', runtime && runtime.app_server_health],
      ['Task Sys', String(taskSys && taskSys.active_count ? taskSys.active_count : 0) + ' active'],
      ['Tracks', String(tracks.length) + ' owned'],
    ];
    return metrics.map(function (entry) {
      return '<div class="metric"><span class="micro">' + escapeHtml(entry[0]) + '</span><strong>' + escapeHtml(formatValue(entry[1])) + '</strong></div>';
    }).join('');
  }

  function renderRuntimeSummaryHtml(state) {
    const runtime = selectedActorRuntime(state);
    if (!runtime) {
      return renderEmpty('No runtime selected.');
    }
    return [
      '<div class="summary-line"><span>Thread</span><strong class="mono-value long-value">' + escapeHtml(formatValue(runtime.thread_id)) + '</strong></div>',
      '<div class="summary-line"><span>Thread state</span><strong>' + escapeHtml(formatValue(runtime.thread && runtime.thread.status)) + '</strong></div>',
      '<div class="summary-line"><span>Browser port</span><strong class="mono-value">' + escapeHtml(formatValue(runtime.browser_port)) + '</strong></div>',
      '<div class="summary-line"><span>Updated</span><strong class="mono-value long-value">' + escapeHtml(formatValue(runtime.updated_at)) + '</strong></div>',
    ].join('');
  }

  function renderTaskSummaryHtml(state) {
    if (state.actorSelectionPendingId && state.actorSelectionPendingId === state.selectedActorId && !state.actorConsole) {
      return '<div class="inline-loading">Loading actor task state...</div>';
    }
    const taskSys = state.actorConsole && state.actorConsole.task_sys ? state.actorConsole.task_sys : null;
    if (!taskSys) {
      return renderEmpty('No Task Sys state loaded.');
    }
    const activeTasks = Array.isArray(taskSys.active_tasks) ? taskSys.active_tasks : [];
    const active = activeTasks[0] || null;
    return [
      '<div class="summary-line"><span>Active</span><strong>' + escapeHtml(String(taskSys.active_count || 0)) + '</strong></div>',
      active ? '<div class="task-row"><strong>' + escapeHtml(active.source_type || active.status || 'Task Sys') + '</strong><span class="micro mono">' + escapeHtml(active.task_id || '') + '</span></div>' : '',
      '<div class="summary-line"><span>Processor</span>' + badge(active && active.active_processor ? active.active_processor : 'none') + '</div>',
    ].join('');
  }

  function renderActorTrackSummaryHtml(state) {
    if (state.actorSelectionPendingId && state.actorSelectionPendingId === state.selectedActorId && !state.actorConsole) {
      return '<div class="inline-loading">Loading actor Track summaries...</div>';
    }
    const tracks = state.actorConsole && state.actorConsole.tracks && Array.isArray(state.actorConsole.tracks.items)
      ? state.actorConsole.tracks.items
      : [];
    if (!tracks.length) {
      return renderEmpty('No active Track summaries for this actor.');
    }
    return tracks.slice(0, 6).map(function (track) {
      return [
        '<div class="task-row">',
        '<strong>' + escapeHtml(formatValue(track.title)) + '</strong>',
        '<span class="micro mono">' + escapeHtml(formatValue(track.id)) + ' · ' + escapeHtml(formatValue(track.state)) + '</span>',
        '</div>',
      ].join('');
    }).join('');
  }

  function renderTrackDetailHtml(track) {
    if (!track) {
      return renderEmpty('Select a Track to inspect details.');
    }
    const commentSummary = track.comment_summary || {};
    const materials = Array.isArray(track.materials) ? track.materials : [];
    const proofs = Array.isArray(track.proofs) ? track.proofs : [];
    const updates = Array.isArray(track.updates) ? track.updates : [];
    const threads = Array.isArray(track.comment_threads) ? track.comment_threads : [];
    return [
      '<div class="pill-row left">',
      '<span class="tag blue">' + escapeHtml(formatValue(track.id)) + '</span>',
      badge(track.state),
      '<span class="tag">' + escapeHtml(formatValue(track.updated_at)) + '</span>',
      '</div>',
      '<h2 class="doc-title">' + escapeHtml(formatValue(track.title)) + '</h2>',
      '<p>' + escapeHtml(formatValue(track.outcome)) + '</p>',
      '<section class="doc-section"><h3>Current state</h3>',
      '<div class="doc-block"><span class="tag blue">Next</span><span>' + escapeHtml(formatValue(track.now && track.now.next)) + '</span><span class="mini-button">Read only</span></div>',
      '<div class="doc-block"><span class="tag">Blocker</span><span>' + escapeHtml(formatValue(track.now && track.now.blocker)) + '</span><span class="mini-button">Read only</span></div>',
      '</section>',
      '<section class="doc-section"><h3>Materials and proofs</h3><div class="list">',
      renderArtifactRefs(materials, 'Material', 'blue'),
      renderArtifactRefs(proofs, 'Proof', 'green'),
      '</div></section>',
      '<section class="doc-section"><h3>Updates</h3>' + renderUpdates(updates) + '</section>',
      '<section class="doc-section"><h3>Comments</h3>',
      '<div class="summary-line"><span>Total comments</span><strong>' + escapeHtml(String(commentSummary.comment_count || 0)) + '</strong></div>',
      '<div class="summary-line"><span>Open threads</span><strong>' + escapeHtml(String(commentSummary.open_thread_count || 0)) + '</strong></div>',
      renderComments(threads),
      '</section>',
    ].join('');
  }

  function renderTrackStudioRailHtml(track) {
    if (!track) {
      return renderEmpty('Select a Track to inspect comments and context.');
    }
    const commentSummary = track.comment_summary || {};
    const threads = Array.isArray(track.comment_threads) ? track.comment_threads : [];
    return [
      '<section class="studio-card">',
      '<h3>Context</h3>',
      '<div class="summary-line"><span>State</span>' + badge(track.state) + '</div>',
      '<div class="summary-line"><span>Next</span><strong>' + escapeHtml(formatValue(track.now && track.now.next)) + '</strong></div>',
      '<div class="summary-line"><span>Blocker</span><strong>' + escapeHtml(formatValue(track.now && track.now.blocker)) + '</strong></div>',
      '</section>',
      '<section class="studio-card">',
      '<h3>Comments</h3>',
      '<div class="summary-line"><span>Total</span><strong>' + escapeHtml(String(commentSummary.comment_count || 0)) + '</strong></div>',
      '<div class="summary-line"><span>Open</span><strong>' + escapeHtml(String(commentSummary.open_thread_count || 0)) + '</strong></div>',
      '<div class="summary-line"><span>Resolved</span><strong>' + escapeHtml(String(commentSummary.resolved_thread_count || 0)) + '</strong></div>',
      renderComments(threads),
      '</section>',
    ].join('');
  }

  function renderArtifactRefs(rows, label, tone) {
    if (!rows.length) {
      return '';
    }
    return rows.map(function (row) {
      return [
        '<div class="doc-block">',
        '<span class="tag ' + escapeHtml(tone || '') + '">' + escapeHtml(label || formatValue(row.role || 'Artifact')) + '</span>',
        '<span>',
        '<strong>' + escapeHtml(formatValue(row.label)) + '</strong>',
        '<span class="micro mono">' + escapeHtml(formatValue(row.artifact_id)) + ' · ' + escapeHtml(formatValue(row.template)) + '</span>',
        '</span>',
        '<span class="mini-button">Inspect</span>',
        '</div>',
      ].join('');
    }).join('');
  }

  function renderUpdates(rows) {
    if (!rows.length) {
      return renderEmpty('No updates.');
    }
    return rows.map(function (row) {
      return [
        '<div class="task-row">',
        '<strong>' + escapeHtml(formatValue(row.summary)) + '</strong>',
        '<span class="micro mono">' + escapeHtml(formatValue(row.id)) + ' · ' + escapeHtml(formatValue(row.kind)) + '</span>',
        '</div>',
      ].join('');
    }).join('');
  }

  function renderComments(rows) {
    if (!rows.length) {
      return renderEmpty('No comments.');
    }
    return rows.map(function (thread) {
      return [
        '<div class="comment-thread">',
        '<strong class="mono-value">' + escapeHtml(formatValue(thread.thread_id)) + '</strong>',
        '<span class="micro">' + escapeHtml(formatValue(thread.latest_comment_preview)) + '</span>',
        badge(thread.status),
        '<span class="micro">' + escapeHtml(String(thread.comment_count || 0)) + ' comments</span>',
        '</div>',
      ].join('');
    }).join('');
  }

  function renderImConversation(state, elements) {
    if (!elements.imConversation) {
      return;
    }
    if (!state.imConversation.length) {
      elements.imConversation.innerHTML = '';
      return;
    }
    elements.imConversation.innerHTML = state.imConversation.map(function (entry) {
      const status = [entry.deliveryStatus, entry.wakeStatus].filter(Boolean).join(' / ');
      const stateClass = entry.deliveryStatus === 'sending'
        ? ' pending'
        : entry.deliveryStatus === 'failed'
        ? ' failed'
        : '';
      const meta = [
        entry.direction === 'sent' ? 'sent' : 'reply',
        entry.sender,
        status,
        entry.replyTo ? 'reply_to ' + entry.replyTo : '',
      ].filter(Boolean).join(' · ');
      return [
        '<div class="message ' + (entry.direction === 'sent' ? 'you' : 'reply') + stateClass + '">',
        '<span class="meta">' + escapeHtml(meta) + '</span>',
        '<p>' + escapeHtml(entry.content) + '</p>',
        '</div>',
      ].join('');
    }).join('');
  }

  function sectionCopy(section) {
    if (section === 'tracks') {
      return {
        title: 'Tracks',
        summary: 'Review Track outcomes, current state, materials, proofs, updates, and comments.',
      };
    }
    return {
      title: 'Team room',
      summary: 'Message teammates, inspect current runtime facts, and keep coordination in one room.',
    };
  }

  function renderShell(state, elements) {
    elements.serverStatus.textContent = state.healthOk ? 'API Ready' : 'API Unavailable';
    elements.serverStatus.classList.toggle('is-loading', state.refreshPending);
    elements.refreshButton.textContent = state.refreshPending ? 'Refreshing...' : 'Refresh';
    elements.refreshButton.disabled = state.refreshPending;
    elements.refreshButton.classList.toggle('is-pending', state.refreshPending);
    elements.messageBanner.textContent = state.message;
    elements.actorView.hidden = state.selectedSection !== 'actors';
    elements.trackView.hidden = state.selectedSection !== 'tracks';
    elements.actorNavButton.classList.toggle('is-active', state.selectedSection === 'actors');
    elements.tracksNavButton.classList.toggle('is-active', state.selectedSection === 'tracks');
    elements.createButton.disabled = !computeCreateEnabled({
      selectedRole: state.selectedRole,
      isCreating: state.createPending,
    });
  }

  function renderRoleSelect(state, elements) {
    if (elements.roleSelect.options.length === 0) {
      const placeholder = document.createElement('option');
      placeholder.value = '';
      placeholder.textContent = 'Select role';
      elements.roleSelect.appendChild(placeholder);
      state.roles.forEach(function (role) {
        const option = document.createElement('option');
        option.value = role.id;
        option.textContent = role.label + ' (' + role.id + ')';
        elements.roleSelect.appendChild(option);
      });
    }
    elements.roleSelect.value = state.selectedRole;
  }

  function renderActorList(state, elements) {
    elements.actorsList.innerHTML = renderActorRowsHtml(state);
  }

  function renderActorDetail(state, elements) {
    const runtime = selectedActorRuntime(state);
    if (elements.selectedActorAvatar) {
      elements.selectedActorAvatar.textContent = actorInitials(runtime && runtime.role, state.selectedActorId);
      elements.selectedActorAvatar.className = 'avatar ' + actorVisualTone(runtime);
    }
    if (elements.selectedActorSubtitle) {
      elements.selectedActorSubtitle.textContent = state.selectedActorId
        ? formatValue(state.selectedActorId) + ' · role ' + formatValue(runtime && runtime.role)
        : 'No teammate selected';
    }
    elements.actorRuntimeDetail.innerHTML = renderRuntimeDetailHtml(state);
    if (elements.actorRuntimeSummary) {
      elements.actorRuntimeSummary.innerHTML = renderRuntimeSummaryHtml(state);
    }
    elements.actorTaskSummary.innerHTML = renderTaskSummaryHtml(state);
    elements.actorTrackSummary.innerHTML = renderActorTrackSummaryHtml(state);
  }

  function renderTrackList(state, elements) {
    elements.tracksList.innerHTML = renderTrackRowsHtml(state);
  }

  function renderTrackDetail(state, elements) {
    elements.trackDetail.innerHTML = state.trackSelectionPendingId && state.trackSelectionPendingId === state.selectedTrackId
      ? '<div class="empty-state inline-loading">Loading Track...</div>'
      : renderTrackDetailHtml(state.selectedTrackDetail);
  }

  function renderTrackStudioRail(state, elements) {
    if (!elements.trackStudioRail) {
      return;
    }
    elements.trackStudioRail.innerHTML = state.trackSelectionPendingId && state.trackSelectionPendingId === state.selectedTrackId
      ? '<div class="empty-state inline-loading">Loading Track context...</div>'
      : renderTrackStudioRailHtml(state.selectedTrackDetail);
  }

  function renderComposer(state, elements) {
    elements.instructionInput.value = state.draftText;
    const runtime = selectedActorRuntime(state);
    const actionState = describeInstanceActionState(runtime, {
      draftText: state.draftText,
      sendPending: state.sendPending,
      lifecyclePendingAction: state.lifecyclePendingAction,
    });
    elements.sendButton.disabled = !actionState.canSend;
    elements.sendButton.textContent = state.sendPending ? 'Sending...' : 'Send';
    elements.sendButton.classList.toggle('is-pending', state.sendPending);
    elements.interruptButton.disabled = !actionState.canInterrupt;
    elements.stopButton.disabled = !actionState.canStop;
    elements.deleteButton.disabled = !actionState.canDelete;
    elements.clearButton.disabled = !actionState.canClear;
    elements.resumeButton.disabled = !actionState.canResume;
    elements.actionAvailabilityStatus.textContent = !actionState.canClear && actionState.clearReason
      ? 'Clear disabled: ' + actionState.clearReason
      : '';
  }

  function renderOpenTui(state, elements) {
    const runtime = selectedActorRuntime(state);
    const openTuiState = computeOpenTuiState(runtime, {
      openTuiPending: state.openTuiPending,
    });
    elements.openTuiButton.disabled = !openTuiState.canOpenTui;
    elements.openTuiButton.textContent = state.openTuiPending ? 'Opening...' : 'Open TUI';
    elements.openTuiButton.classList.toggle('is-pending', state.openTuiPending);
    elements.openTuiStatus.textContent = state.openTuiPending
      ? 'Opening...'
      : (openTuiState.canOpenTui ? state.openTuiMessage : openTuiState.message);
    elements.openTuiCommand.textContent = state.openTuiCommand;
    elements.openTuiFallback.hidden = !state.openTuiCommand || !openTuiState.canOpenTui;
    elements.copyTuiCommandButton.disabled = !state.openTuiCommand || !openTuiState.canOpenTui;
  }

  function renderAll(state, elements) {
    renderShell(state, elements);
    renderRoleSelect(state, elements);
    renderActorList(state, elements);
    renderActorDetail(state, elements);
    renderTrackList(state, elements);
    renderTrackDetail(state, elements);
    renderTrackStudioRail(state, elements);
    renderComposer(state, elements);
    renderOpenTui(state, elements);
    renderImConversation(state, elements);
  }

  async function refreshAll(state, elements) {
    const [healthPayload, rolesPayload, actorsPayload, tracksPayload] = await Promise.all([
      fetchJson('/api/health'),
      fetchJson('/api/roles'),
      fetchJson('/api/actors'),
      fetchJson('/api/tracks'),
    ]);
    state.healthOk = Boolean(healthPayload.ok);
    state.roles = rolesPayload.roles || [];
    if (!state.selectedRole && state.roles.length > 0) {
      state.selectedRole = state.roles[0].id;
    }
    applyActorsPayload(state, actorsPayload);
    applyTracksPayload(state, tracksPayload);
    await Promise.all([
      refreshSelectedActorConsole(state),
      refreshSelectedTrackDetail(state),
    ]);
    await ensureImSession(state, elements);
    await refreshSelectedActorConversation(state);
    renderAll(state, elements);
    scheduleActorConsoleRefresh(state, elements);
  }

  async function refreshSelectedActorConsole(state) {
    if (!state.selectedActorId) {
      state.actorConsole = null;
      clearImConversation(state, '');
      return;
    }
    const payload = await fetchJson(buildActorConsoleUrl(state.selectedActorId));
    applyActorConsolePayload(state, payload);
  }

  async function refreshSelectedActorConversation(state) {
    const target = selectedActorImTarget(state);
    const identityId = target && target.identity_id ? target.identity_id : '';
    clearImConversation(state, identityId);
    if (!identityId) {
      return;
    }
    try {
      const payload = await fetchJson(
        buildImConversationUrl(identityId, 50)
      );
      applyImConversationPayload(state, payload, identityId);
    } catch (error) {
      if (isImConversationNotFoundError(error)) {
        if (state.message === error.message) {
          state.message = '';
        }
        return;
      }
      throw error;
    }
  }

  function currentDocumentHidden() {
    return typeof document !== 'undefined' && Boolean(document.hidden);
  }

  function shouldRefreshSelectedActorConsole(state, options) {
    const documentHidden = options && typeof options.documentHidden === 'boolean'
      ? options.documentHidden
      : currentDocumentHidden();
    return Boolean(
      state
      && state.selectedSection === 'actors'
      && state.selectedActorId
      && !documentHidden
      && !state.actorSelectionPendingId
      && !state.actorRefreshInFlight
    );
  }

  async function refreshSelectedActorConsoleAndRender(state, elements) {
    if (!shouldRefreshSelectedActorConsole(state)) {
      return;
    }
    state.actorRefreshInFlight = true;
    try {
      await refreshSelectedActorConsole(state);
      renderActorDetail(state, elements);
      renderComposer(state, elements);
      renderOpenTui(state, elements);
    } catch (error) {
      state.message = error.message;
      renderShell(state, elements);
    } finally {
      state.actorRefreshInFlight = false;
    }
  }

  function scheduleActorConsoleRefresh(state, elements) {
    if (!elements || state.actorRefreshTimer || !shouldRefreshSelectedActorConsole(state)) {
      return;
    }
    state.actorRefreshTimer = setTimeout(function () {
      state.actorRefreshTimer = null;
      refreshSelectedActorConsoleAndRender(state, elements).finally(function () {
        scheduleActorConsoleRefresh(state, elements);
      });
    }, ACTOR_CONSOLE_REFRESH_INTERVAL_MS);
  }

  function installActorRefreshListeners(state, elements) {
    if (typeof document === 'undefined') {
      return;
    }
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) {
        return;
      }
      refreshSelectedActorConsoleAndRender(state, elements).finally(function () {
        scheduleActorConsoleRefresh(state, elements);
      });
    });
  }

  async function refreshSelectedTrackDetail(state) {
    if (!state.selectedTrackId) {
      state.selectedTrackDetail = null;
      return;
    }
    const payload = await fetchJson(buildTrackDetailUrl(state.selectedTrackId));
    applyTrackDetailPayload(state, payload);
  }

  async function selectActor(state, elements, actorId) {
    if (!actorId || actorId === state.selectedActorId) {
      return;
    }
    const requestId = state.actorSelectionRequestId + 1;
    state.actorSelectionRequestId = requestId;
    state.selectedActorId = actorId;
    state.actorConsole = null;
    state.actorSelectionPendingId = actorId;
    state.message = '';
    clearImConversation(state, actorId);
    clearOpenTuiFeedback(state);
    renderShell(state, elements);
    renderActorList(state, elements);
    renderActorDetail(state, elements);
    renderComposer(state, elements);
    renderOpenTui(state, elements);
    renderImConversation(state, elements);
    try {
      const payload = await fetchJson(buildActorConsoleUrl(actorId));
      const consoleActorId = payload
        && payload.console
        && payload.console.actor
        && typeof payload.console.actor.actor_id === 'string'
        ? payload.console.actor.actor_id
        : '';
      if (
        state.actorSelectionRequestId !== requestId
        || state.selectedActorId !== actorId
        || (consoleActorId && consoleActorId !== actorId)
      ) {
        return;
      }
      applyActorConsolePayload(state, payload);
      if (state.actorSelectionRequestId !== requestId || state.selectedActorId !== actorId) {
        return;
      }

      const target = selectedActorImTarget(state);
      const identityId = target && target.identity_id ? target.identity_id : '';
      clearImConversation(state, identityId);
      if (identityId) {
        try {
          const conversationPayload = await fetchJson(buildImConversationUrl(identityId, 50));
          if (state.actorSelectionRequestId !== requestId || state.selectedActorId !== actorId) {
            return;
          }
          applyImConversationPayload(state, conversationPayload, identityId);
        } catch (error) {
          if (state.actorSelectionRequestId !== requestId || state.selectedActorId !== actorId) {
            return;
          }
          if (isImConversationNotFoundError(error)) {
            if (state.message === error.message) {
              state.message = '';
            }
            return;
          }
          throw error;
        }
      }
    } finally {
      if (state.actorSelectionRequestId === requestId && state.selectedActorId === actorId) {
        state.actorSelectionPendingId = '';
        renderActorList(state, elements);
        renderActorDetail(state, elements);
        renderComposer(state, elements);
        renderOpenTui(state, elements);
        renderImConversation(state, elements);
        scheduleActorConsoleRefresh(state, elements);
      }
    }
  }

  async function selectTrack(state, elements, trackId) {
    if (!trackId || trackId === state.selectedTrackId || state.trackSelectionPendingId) {
      return;
    }
    state.selectedTrackId = trackId;
    state.selectedTrackDetail = null;
    state.trackSelectionPendingId = trackId;
    renderTrackList(state, elements);
    renderTrackDetail(state, elements);
    renderTrackStudioRail(state, elements);
    try {
      await refreshSelectedTrackDetail(state);
    } finally {
      state.trackSelectionPendingId = '';
      renderTrackList(state, elements);
      renderTrackDetail(state, elements);
      renderTrackStudioRail(state, elements);
    }
  }

  async function runLifecycleAction(state, elements, action) {
    if (!action || state.lifecyclePendingAction) {
      return;
    }
    state.lifecyclePendingAction = action;
    state.message = '';
    renderComposer(state, elements);
    try {
      const payload = await fetchJson(actorActionUrl(state, action), {
        method: 'POST',
      });
      state.message = payload && payload.turn_id
        ? 'Action completed for ' + state.selectedActorId + ' (' + payload.turn_id + ').'
        : 'Action completed.';
      clearOpenTuiFeedback(state);
      await refreshSelectedActorConsole(state);
      renderActorDetail(state, elements);
    } catch (error) {
      state.message = error.message;
    } finally {
      state.lifecyclePendingAction = '';
      renderShell(state, elements);
      renderComposer(state, elements);
      renderOpenTui(state, elements);
    }
  }

  async function deleteSelectedActor(state, elements) {
    if (!state.selectedActorId || state.lifecyclePendingAction) {
      return;
    }
    const actorId = state.selectedActorId;
    state.lifecyclePendingAction = 'delete';
    state.message = '';
    renderComposer(state, elements);
    try {
      const payload = await fetchJson('/api/instances/' + encodeURIComponent(actorId), {
        method: 'DELETE',
      });
      state.message = payload && payload.ok ? 'Deleted ' + actorId + '.' : 'Deleted actor.';
      state.selectedActorId = '';
      state.actorConsole = null;
      clearImConversation(state, '');
      clearOpenTuiFeedback(state);
      await refreshAll(state, elements);
    } catch (error) {
      state.message = error.message;
      renderShell(state, elements);
    } finally {
      state.lifecyclePendingAction = '';
      renderAll(state, elements);
    }
  }

  async function createInstance(state, elements) {
    state.createPending = true;
    renderShell(state, elements);
    try {
      const payload = await fetchJson('/api/instances', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: state.selectedRole }),
      });
      state.selectedActorId = payload.actor_id;
      state.selectedSection = 'actors';
      state.message = 'Created ' + payload.actor_id + '.';
      clearImConversation(state, payload.actor_id);
      clearOpenTuiFeedback(state);
      await refreshAll(state, elements);
    } catch (error) {
      state.message = error.message;
      renderShell(state, elements);
    } finally {
      state.createPending = false;
      renderAll(state, elements);
    }
  }

  async function ensureImSession(state, elements) {
    if (state.imSessionReady) {
      startImPolling(state, elements);
      return;
    }
    await fetchJson('/api/im/session');
    state.imSessionReady = true;
    startImPolling(state, elements);
  }

  async function sendImDraft(state, elements, content) {
    await ensureImSession(state, elements);
    const target = selectedActorImTarget(state);
    if (!target) {
      throw new Error('Select an actor first.');
    }
    const payload = await fetchJson('/api/im/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        target_identity_id: target.identity_id,
        content: content,
        reply_to: null,
      }),
    });
    return payload;
  }

  async function sendCurrentDraft(state, elements) {
    const content = typeof state.draftText === 'string' ? state.draftText.trim() : '';
    if (!content || state.sendPending) {
      return;
    }
    const previousDraft = state.draftText;
    const pendingId = recordImPendingSend(state, content);
    state.draftText = '';
    state.sendPending = true;
    state.message = '';
    renderComposer(state, elements);
    renderImConversation(state, elements);
    try {
      const payload = await sendImDraft(state, elements, content);
      replaceImPendingSend(state, pendingId, payload, content);
      const imMessageId = payload && payload.message && payload.message.id ? payload.message.id : '';
      state.message = imMessageId
        ? 'Sent message ' + imMessageId + (payload.delivery_status ? ' (' + payload.delivery_status + ').' : '.')
        : 'Message sent.';
      await refreshSelectedActorConsole(state);
      renderActorDetail(state, elements);
    } catch (error) {
      removeImEntry(state, pendingId);
      state.draftText = previousDraft;
      state.message = error.message;
    } finally {
      state.sendPending = false;
      renderShell(state, elements);
      renderComposer(state, elements);
      renderImConversation(state, elements);
    }
  }

  async function pollImEventsOnce(state, elements) {
    if (!state.imSessionReady) {
      return;
    }
    const target = selectedActorImTarget(state);
    if (!target || !target.identity_id) {
      return;
    }
    const selectedIdentityId = target.identity_id;
    const payload = await fetchJson(buildImEventsUrl(15000));
    if (state.selectedActorId !== target.identity_id) {
      return;
    }
    const events = Array.isArray(payload.events) ? payload.events : [];
    let selectedActorMessageProcessed = false;
    for (const event of events) {
      if (!event || typeof event !== 'object' || typeof event.message_id !== 'string' || !event.message_id) {
        continue;
      }
      const fetched = await fetchJson(buildImMessageUrl(event.message_id));
      const message = fetched && fetched.message && typeof fetched.message === 'object' ? fetched.message : null;
      if (message && recordSelectedActorEventMessage(state, message, selectedIdentityId)) {
        selectedActorMessageProcessed = true;
      }
      await fetchJson('/api/im/events/ack', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(buildImAckPayload(event.event_id)),
      });
    }
    if (selectedActorMessageProcessed && state.selectedActorId === selectedIdentityId) {
      await refreshSelectedActorConsole(state);
      await refreshSelectedActorConversation(state);
    }
    if (selectedActorMessageProcessed && state.selectedSection === 'actors') {
      renderActorDetail(state, elements);
      renderComposer(state, elements);
      renderOpenTui(state, elements);
      renderImConversation(state, elements);
    }
  }

  function startImPolling(state, elements) {
    if (!elements || !state.imSessionReady || state.imPolling || state.imPollTimer) {
      return;
    }
    state.imPollTimer = setTimeout(function () {
      state.imPollTimer = null;
      state.imPolling = true;
      pollImEventsOnce(state, elements).catch(function (error) {
        state.message = error.message;
        renderShell(state, elements);
      }).finally(function () {
        state.imPolling = false;
        if (state.imSessionReady) {
          startImPolling(state, elements);
        }
      });
    }, 0);
  }

  function commandFromError(error) {
    return error
      && error.payload
      && error.payload.error
      && typeof error.payload.error.command === 'string'
      ? error.payload.error.command
      : '';
  }

  async function openTui(state, elements) {
    const runtime = selectedActorRuntime(state);
    const openTuiState = computeOpenTuiState(runtime, {
      openTuiPending: state.openTuiPending,
    });
    if (!openTuiState.canOpenTui) {
      state.openTuiMessage = openTuiState.message;
      renderOpenTui(state, elements);
      return;
    }

    state.openTuiPending = true;
    state.openTuiMessage = 'Opening...';
    state.openTuiCommand = '';
    renderOpenTui(state, elements);
    renderComposer(state, elements);
    try {
      const payload = await fetchJson('/api/instances/' + encodeURIComponent(state.selectedActorId) + '/open-tui', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-BuddySwitch-Web': '1',
        },
        body: JSON.stringify({}),
      });
      state.openTuiCommand = typeof payload.command === 'string' ? payload.command : '';
      state.openTuiMessage = 'Terminal opened.';
    } catch (error) {
      state.openTuiCommand = commandFromError(error);
      state.openTuiMessage = 'Could not open Terminal.';
    } finally {
      state.openTuiPending = false;
      renderOpenTui(state, elements);
      renderComposer(state, elements);
    }
  }

  function fallbackCopyText(value) {
    const textarea = document.createElement('textarea');
    textarea.value = value;
    textarea.setAttribute('readonly', 'readonly');
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand('copy');
    document.body.removeChild(textarea);
    if (!copied) {
      throw new Error('copy failed');
    }
  }

  async function copyOpenTuiCommand(state, elements) {
    if (!state.openTuiCommand) {
      return;
    }
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(state.openTuiCommand);
      } else {
        fallbackCopyText(state.openTuiCommand);
      }
      state.openTuiMessage = 'Command copied.';
    } catch (_error) {
      state.openTuiMessage = 'Copy failed.';
    }
    renderOpenTui(state, elements);
  }

  function actorActionUrl(state, action) {
    return '/api/instances/' + encodeURIComponent(state.selectedActorId) + '/' + action;
  }

  async function refreshAllWithFeedback(state, elements) {
    if (state.refreshPending) {
      return;
    }
    state.refreshPending = true;
    state.message = '';
    renderShell(state, elements);
    try {
      await refreshAll(state, elements);
      state.message = 'Refreshed.';
    } catch (error) {
      state.message = error.message;
    } finally {
      state.refreshPending = false;
      renderAll(state, elements);
    }
  }

  async function bootstrap() {
    if (typeof document === 'undefined') {
      return;
    }
    const elements = {
      actorNavButton: document.getElementById('actor-nav-button'),
      tracksNavButton: document.getElementById('tracks-nav-button'),
      actorView: document.getElementById('actor-view'),
      trackView: document.getElementById('track-view'),
      roleSelect: document.getElementById('role-select'),
      createButton: document.getElementById('create-button'),
      refreshButton: document.getElementById('refresh-button'),
      serverStatus: document.getElementById('server-status'),
      actorsList: document.getElementById('actors-list'),
      selectedActorAvatar: document.getElementById('selected-actor-avatar'),
      selectedActorSubtitle: document.getElementById('selected-actor-subtitle'),
      actorRuntimeDetail: document.getElementById('actor-runtime-detail'),
      actorRuntimeSummary: document.getElementById('actor-runtime-summary'),
      actorTaskSummary: document.getElementById('actor-task-summary'),
      actorTrackSummary: document.getElementById('actor-track-summary'),
      tracksList: document.getElementById('tracks-list'),
      trackDetail: document.getElementById('track-detail'),
      trackStudioRail: document.getElementById('track-studio-rail'),
      instructionInput: document.getElementById('instruction-input'),
      sendButton: document.getElementById('send-button'),
      interruptButton: document.getElementById('interrupt-button'),
      stopButton: document.getElementById('stop-button'),
      deleteButton: document.getElementById('delete-button'),
      clearButton: document.getElementById('clear-button'),
      resumeButton: document.getElementById('resume-button'),
      openTuiButton: document.getElementById('open-tui-button'),
      openTuiStatus: document.getElementById('open-tui-status'),
      openTuiFallback: document.getElementById('open-tui-fallback'),
      openTuiCommand: document.getElementById('open-tui-command'),
      copyTuiCommandButton: document.getElementById('copy-tui-command-button'),
      messageBanner: document.getElementById('message-banner'),
      actionAvailabilityStatus: document.getElementById('action-availability-status'),
      imConversation: document.getElementById('im-conversation'),
    };

    const state = createState();
    installActorRefreshListeners(state, elements);

    elements.actorNavButton.addEventListener('click', function () {
      selectSection(state, 'actors');
      renderShell(state, elements);
      scheduleActorConsoleRefresh(state, elements);
    });
    elements.tracksNavButton.addEventListener('click', function () {
      selectSection(state, 'tracks');
      renderShell(state, elements);
    });
    elements.actorsList.addEventListener('click', function (event) {
      const row = event.target && event.target.closest
        ? event.target.closest('[data-actor-id]')
        : null;
      if (!row) {
        return;
      }
      selectActor(state, elements, row.getAttribute('data-actor-id') || '').catch(function (error) {
        state.message = error.message;
        renderShell(state, elements);
      });
    });
    elements.tracksList.addEventListener('click', function (event) {
      const row = event.target && event.target.closest
        ? event.target.closest('[data-track-id]')
        : null;
      if (!row) {
        return;
      }
      selectTrack(state, elements, row.getAttribute('data-track-id') || '').catch(function (error) {
        state.message = error.message;
        renderShell(state, elements);
      });
    });
    elements.roleSelect.addEventListener('change', function (event) {
      state.selectedRole = event.target.value;
      renderShell(state, elements);
    });
    elements.instructionInput.addEventListener('input', function (event) {
      state.draftText = event.target.value;
      renderComposer(state, elements);
    });
    elements.refreshButton.addEventListener('click', function () {
      refreshAllWithFeedback(state, elements).catch(function (error) {
        state.message = error.message;
        state.refreshPending = false;
        renderAll(state, elements);
      });
    });
    elements.createButton.addEventListener('click', function () {
      createInstance(state, elements).catch(function (error) {
        state.message = error.message;
        state.createPending = false;
        renderAll(state, elements);
      });
    });
    elements.sendButton.addEventListener('click', function () {
      sendCurrentDraft(state, elements).catch(function (error) {
        state.message = error.message;
        state.sendPending = false;
        renderShell(state, elements);
        renderComposer(state, elements);
      });
    });
    elements.interruptButton.addEventListener('click', function () {
      runLifecycleAction(state, elements, 'interrupt').catch(function (error) {
        state.message = error.message;
        state.lifecyclePendingAction = '';
        renderShell(state, elements);
        renderComposer(state, elements);
      });
    });
    elements.stopButton.addEventListener('click', function () {
      runLifecycleAction(state, elements, 'stop').catch(function (error) {
        state.message = error.message;
        state.lifecyclePendingAction = '';
        renderShell(state, elements);
        renderComposer(state, elements);
      });
    });
    elements.clearButton.addEventListener('click', function () {
      runLifecycleAction(state, elements, 'clear').catch(function (error) {
        state.message = error.message;
        state.lifecyclePendingAction = '';
        renderShell(state, elements);
        renderComposer(state, elements);
      });
    });
    elements.resumeButton.addEventListener('click', function () {
      runLifecycleAction(state, elements, 'resume').catch(function (error) {
        state.message = error.message;
        state.lifecyclePendingAction = '';
        renderShell(state, elements);
        renderComposer(state, elements);
      });
    });
    elements.openTuiButton.addEventListener('click', function () {
      openTui(state, elements).catch(function (error) {
        state.openTuiMessage = error.message;
        state.openTuiPending = false;
        renderOpenTui(state, elements);
        renderComposer(state, elements);
      });
    });
    elements.copyTuiCommandButton.addEventListener('click', function () {
      copyOpenTuiCommand(state, elements).catch(function (error) {
        state.openTuiMessage = error.message;
        renderOpenTui(state, elements);
      });
    });
    elements.deleteButton.addEventListener('click', function () {
      deleteSelectedActor(state, elements).catch(function (error) {
        state.message = error.message;
        state.lifecyclePendingAction = '';
        renderAll(state, elements);
      });
    });

    try {
      await refreshAll(state, elements);
    } catch (error) {
      state.message = error.message;
      renderAll(state, elements);
    }
  }

  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', function () {
        bootstrap();
      });
    } else {
      bootstrap();
    }
  }

  return {
    applyActorConsolePayload,
    applyActorsPayload,
    actorInitials,
    applyImConversationPayload,
    applyTrackDetailPayload,
    applyTracksPayload,
    buildActorConsoleUrl,
    buildImAckPayload,
    buildImEventsUrl,
    buildImConversationUrl,
    buildImMessageUrl,
    buildTrackDetailUrl,
    computeCreateEnabled,
    computeInstanceActionState,
    computeOpenTuiState,
    createState,
    clearImConversation,
    describeInstanceActionState,
    recordImProjectedMessage,
    recordImPendingSend,
    recordImSent,
    recordSelectedActorEventMessage,
    removeImEntry,
    replaceImPendingSend,
    refreshSelectedActorConversation,
    pollImEventsOnce,
    renderActorRowsHtml,
    renderImConversation,
    renderTrackDetailHtml,
    renderTrackStudioRailHtml,
    renderComposer,
    sectionCopy,
    selectActor,
    selectedActorRuntime,
    selectSection,
    shouldRefreshSelectedActorConsole,
  };
}));
