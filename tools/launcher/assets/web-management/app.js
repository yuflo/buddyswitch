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
    const isMutating = Boolean(options && options.isMutating);
    if (!instance || isMutating) {
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

    return {
      canSend: isActive && appServerHealthy && draftText.length > 0,
      canInterrupt: isActive && appServerHealthy && threadBusy,
      canStop: isActive,
      canDelete: isInactive,
      canClear: isActive && appServerHealthy && !threadBusy,
      canResume: isInactive,
    };
  }

  function describeInstanceActionState(instance, options) {
    const state = computeInstanceActionState(instance, options);
    const isMutating = Boolean(options && options.isMutating);
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
    } else if (isMutating) {
      clearReason = 'Action running.';
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
    const isMutating = Boolean(options && options.isMutating);
    if (!instance || isMutating) {
      return {
        canOpenTui: false,
        message: '',
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
      mutationKey: '',
      openTuiMessage: '',
      openTuiCommand: '',
      imSessionReady: false,
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

  function buildImEventsUrl(identityId, waitMs) {
    const normalizedWait = Number.isFinite(waitMs) && waitMs >= 0 ? Math.floor(waitMs) : 0;
    return '/api/web/im/events?identity_id=' + encodeURIComponent(identityId || '')
      + '&wait_ms=' + encodeURIComponent(String(normalizedWait));
  }

  function buildWebImConversationUrl(identityId, limit) {
    const normalizedLimit = Number.isFinite(limit) && limit > 0 ? Math.floor(limit) : 20;
    return '/api/web/im/conversations/direct?identity_id=' + encodeURIComponent(identityId || '')
      + '&limit=' + encodeURIComponent(String(normalizedLimit));
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

  function applyImConversationPayload(state, payload) {
    state.imConversation = [];
    state.imSeenMessageIds = {};
    const messages = payload && Array.isArray(payload.messages) ? payload.messages : [];
    messages.forEach(function (message) {
      recordImProjectedMessage(state, message);
    });
  }

  function applyImEventsPayload(state, payload) {
    const messages = payload && Array.isArray(payload.messages) ? payload.messages : [];
    messages.forEach(function (message) {
      recordImProjectedMessage(state, message);
    });
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

  function renderActorRowsHtml(state) {
    if (!state.actors.length) {
      return renderEmpty('No actors available.');
    }
    return state.actors.map(function (actor) {
      const selected = actor.actor_id === state.selectedActorId;
      const runtime = actor.runtime || actor;
      return [
        '<button class="selectable-row actor-row' + (selected ? ' is-selected' : '') + '" type="button" data-actor-id="' + escapeHtml(actor.actor_id) + '">',
        '<span class="row-main">',
        '<span class="row-title mono-value">' + escapeHtml(formatValue(actor.actor_id)) + '</span>',
        '<span class="row-subtitle">' + escapeHtml(formatValue(actor.role)) + '</span>',
        '</span>',
        '<span class="row-meta">',
        badge(runtime.status),
        badge(runtime.app_server_health),
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
      const summary = track.comment_summary || {};
      return [
        '<button class="selectable-row track-row' + (selected ? ' is-selected' : '') + '" type="button" data-track-id="' + escapeHtml(track.id) + '">',
        '<span class="row-main">',
        '<span class="row-title">' + escapeHtml(formatValue(track.title)) + '</span>',
        '<span class="row-subtitle mono-value">' + escapeHtml(formatValue(track.id)) + '</span>',
        '</span>',
        '<span class="row-meta">',
        badge(track.state),
        '<span class="metric-chip">' + escapeHtml(formatValue(summary.open_thread_count || 0)) + ' open</span>',
        '</span>',
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
    const runtime = selectedActorRuntime(state);
    const rows = [
      ['Actor', state.selectedActorId, 'mono-value long-value'],
      ['Role', runtime && runtime.role, ''],
      ['Status', runtime && runtime.status, ''],
      ['Health', runtime && runtime.app_server_health, ''],
      ['Thread', runtime && runtime.thread_id, 'mono-value long-value'],
      ['Thread State', runtime && runtime.thread && runtime.thread.status, ''],
      ['Browser Port', runtime && runtime.browser_port, 'mono-value'],
      ['Updated', runtime && runtime.updated_at, 'long-value'],
      ['Workspace', runtime && runtime.workspace_dir, 'mono-value long-value'],
    ];
    return detailRowsHtml(rows);
  }

  function renderTaskSummaryHtml(state) {
    const taskSys = state.actorConsole && state.actorConsole.task_sys ? state.actorConsole.task_sys : null;
    if (!taskSys) {
      return renderEmpty('No Task Sys state loaded.');
    }
    const activeTasks = Array.isArray(taskSys.active_tasks) ? taskSys.active_tasks : [];
    const active = activeTasks[0] || null;
    return [
      '<div class="summary-line"><span>Active</span><strong>' + escapeHtml(String(taskSys.active_count || 0)) + '</strong></div>',
      active ? '<div class="summary-callout"><strong>' + escapeHtml(active.source_type || active.status || 'Task Sys') + '</strong><span class="mono-value">' + escapeHtml(active.task_id || '') + '</span></div>' : '',
      '<div class="summary-line"><span>Processor</span>' + badge(active && active.active_processor ? active.active_processor : 'none') + '</div>',
    ].join('');
  }

  function renderActorTrackSummaryHtml(state) {
    const tracks = state.actorConsole && state.actorConsole.tracks && Array.isArray(state.actorConsole.tracks.items)
      ? state.actorConsole.tracks.items
      : [];
    if (!tracks.length) {
      return renderEmpty('No active Track summaries for this actor.');
    }
    return tracks.slice(0, 6).map(function (track) {
      return [
        '<div class="compact-row">',
        '<span>',
        '<strong>' + escapeHtml(formatValue(track.title)) + '</strong>',
        '<span class="row-subtitle mono-value">' + escapeHtml(formatValue(track.id)) + '</span>',
        '</span>',
        badge(track.state),
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
      '<div class="track-header">',
      '<div><h3>' + escapeHtml(formatValue(track.title)) + '</h3><p>' + escapeHtml(formatValue(track.outcome)) + '</p></div>',
      badge(track.state),
      '</div>',
      '<dl class="detail-grid track-meta">' + detailRowsHtml([
        ['Track', track.id, 'mono-value long-value'],
        ['Next', track.now && track.now.next, ''],
        ['Blocker', track.now && track.now.blocker, ''],
        ['Updated', track.updated_at, 'long-value'],
      ]) + '</dl>',
      '<div class="track-columns">',
      '<section><h3>Materials</h3>' + renderArtifactRefs(materials) + '</section>',
      '<section><h3>Proofs</h3>' + renderArtifactRefs(proofs) + '</section>',
      '</div>',
      '<section class="track-section"><h3>Updates</h3>' + renderUpdates(updates) + '</section>',
      '<section class="track-section"><h3>Comments</h3>',
      '<div class="summary-line"><span>Total</span><strong>' + escapeHtml(String(commentSummary.comment_count || 0)) + '</strong></div>',
      renderComments(threads),
      '</section>',
    ].join('');
  }

  function renderArtifactRefs(rows) {
    if (!rows.length) {
      return renderEmpty('None.');
    }
    return rows.map(function (row) {
      return [
        '<div class="compact-row">',
        '<span>',
        '<strong>' + escapeHtml(formatValue(row.label)) + '</strong>',
        '<span class="row-subtitle mono-value">' + escapeHtml(formatValue(row.artifact_id)) + '</span>',
        '</span>',
        '<span class="row-subtitle">' + escapeHtml(formatValue(row.template)) + '</span>',
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
        '<div class="compact-row">',
        '<span>',
        '<strong>' + escapeHtml(formatValue(row.summary)) + '</strong>',
        '<span class="row-subtitle mono-value">' + escapeHtml(formatValue(row.id)) + '</span>',
        '</span>',
        badge(row.kind),
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
        '<div class="compact-row">',
        '<span><strong class="mono-value">' + escapeHtml(formatValue(thread.thread_id)) + '</strong><span class="row-subtitle">' + escapeHtml(formatValue(thread.latest_comment_preview)) + '</span></span>',
        badge(thread.status),
        '</div>',
        '<div class="row-subtitle">' + escapeHtml(String(thread.comment_count || 0)) + ' comments</div>',
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
      const meta = [
        entry.direction === 'sent' ? 'sent' : 'reply',
        entry.sender,
        status,
        entry.replyTo ? 'reply_to ' + entry.replyTo : '',
      ].filter(Boolean).join(' · ');
      return [
        '<div class="im-row ' + escapeHtml(entry.direction) + '">',
        '<div class="im-meta">' + escapeHtml(meta) + '</div>',
        '<div class="im-content">' + escapeHtml(entry.content) + '</div>',
        '</div>',
      ].join('');
    }).join('');
  }

  function render(state, elements) {
    elements.serverStatus.textContent = state.healthOk ? 'API Ready' : 'API Unavailable';
    elements.messageBanner.textContent = state.message;
    elements.instructionInput.value = state.draftText;
    elements.actorView.hidden = state.selectedSection !== 'actors';
    elements.trackView.hidden = state.selectedSection !== 'tracks';
    elements.actorNavButton.classList.toggle('is-active', state.selectedSection === 'actors');
    elements.tracksNavButton.classList.toggle('is-active', state.selectedSection === 'tracks');
    elements.createButton.disabled = !computeCreateEnabled({
      selectedRole: state.selectedRole,
      isCreating: state.createPending,
    });

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

    elements.actorsList.innerHTML = renderActorRowsHtml(state);
    elements.actorRuntimeDetail.innerHTML = renderRuntimeDetailHtml(state);
    elements.actorTaskSummary.innerHTML = renderTaskSummaryHtml(state);
    elements.actorTrackSummary.innerHTML = renderActorTrackSummaryHtml(state);
    elements.tracksList.innerHTML = renderTrackRowsHtml(state);
    elements.trackDetail.innerHTML = renderTrackDetailHtml(state.selectedTrackDetail);
    renderImConversation(state, elements);

    const runtime = selectedActorRuntime(state);
    const actionState = describeInstanceActionState(runtime, {
      draftText: state.draftText,
      isMutating: Boolean(state.mutationKey),
    });
    elements.sendButton.disabled = !actionState.canSend;
    elements.interruptButton.disabled = !actionState.canInterrupt;
    elements.stopButton.disabled = !actionState.canStop;
    elements.deleteButton.disabled = !actionState.canDelete;
    elements.clearButton.disabled = !actionState.canClear;
    elements.resumeButton.disabled = !actionState.canResume;
    elements.actionAvailabilityStatus.textContent = !actionState.canClear && actionState.clearReason
      ? 'Clear disabled: ' + actionState.clearReason
      : '';

    const openTuiState = computeOpenTuiState(runtime, {
      isMutating: Boolean(state.mutationKey),
    });
    const openingTui = state.mutationKey === 'open-tui';
    elements.openTuiButton.disabled = !openTuiState.canOpenTui;
    elements.openTuiButton.textContent = openingTui ? 'Opening...' : 'Open TUI';
    elements.openTuiStatus.textContent = openingTui
      ? 'Opening...'
      : (openTuiState.canOpenTui ? state.openTuiMessage : openTuiState.message);
    elements.openTuiCommand.textContent = state.openTuiCommand;
    elements.openTuiFallback.hidden = !state.openTuiCommand || !openTuiState.canOpenTui;
    elements.copyTuiCommandButton.disabled = !state.openTuiCommand || !openTuiState.canOpenTui;

    elements.actorsList.querySelectorAll('[data-actor-id]').forEach(function (button) {
      button.addEventListener('click', function () {
        selectActor(state, elements, button.getAttribute('data-actor-id') || '').catch(function (error) {
          state.message = error.message;
          render(state, elements);
        });
      });
    });
    elements.tracksList.querySelectorAll('[data-track-id]').forEach(function (button) {
      button.addEventListener('click', function () {
        selectTrack(state, elements, button.getAttribute('data-track-id') || '').catch(function (error) {
          state.message = error.message;
          render(state, elements);
        });
      });
    });
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
    await ensureWebImSession(state, elements);
    await refreshSelectedActorConversation(state);
    render(state, elements);
    scheduleActorConsoleRefresh(state, elements);
  }

  async function refreshSelectedActorConsole(state) {
    if (!state.selectedActorId) {
      state.actorConsole = null;
      return;
    }
    const payload = await fetchJson(buildActorConsoleUrl(state.selectedActorId));
    applyActorConsolePayload(state, payload);
  }

  async function refreshSelectedActorConversation(state) {
    const target = selectedActorImTarget(state);
    if (!target || !target.identity_id) {
      applyImConversationPayload(state, { messages: [] });
      return;
    }
    const payload = await fetchJson(
      buildWebImConversationUrl(target.identity_id, 50)
    );
    applyImConversationPayload(state, payload);
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
      && !state.mutationKey
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
      render(state, elements);
    } catch (error) {
      state.message = error.message;
      render(state, elements);
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
    state.selectedActorId = actorId;
    state.actorConsole = null;
    clearOpenTuiFeedback(state);
    await refreshSelectedActorConsole(state);
    await refreshSelectedActorConversation(state);
    render(state, elements);
    scheduleActorConsoleRefresh(state, elements);
  }

  async function selectTrack(state, elements, trackId) {
    if (!trackId || trackId === state.selectedTrackId) {
      return;
    }
    state.selectedTrackId = trackId;
    state.selectedTrackDetail = null;
    await refreshSelectedTrackDetail(state);
    render(state, elements);
  }

  async function runMutation(state, elements, key, requestFactory) {
    state.mutationKey = key;
    render(state, elements);
    try {
      const payload = await requestFactory();
      const imMessageId = payload && payload.message && payload.message.id ? payload.message.id : payload && payload.message_id;
      state.message = imMessageId
        ? 'Sent message ' + imMessageId + (payload.delivery_status ? ' (' + payload.delivery_status + ').' : '.')
        : payload && payload.turn_id
        ? 'Action completed for ' + state.selectedActorId + ' (' + payload.turn_id + ').'
        : 'Action completed.';
      clearOpenTuiFeedback(state);
      await refreshAll(state, elements);
    } catch (error) {
      state.message = error.message;
      render(state, elements);
    } finally {
      state.mutationKey = '';
      render(state, elements);
    }
  }

  async function createInstance(state, elements) {
    state.createPending = true;
    render(state, elements);
    try {
      const payload = await fetchJson('/api/instances', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: state.selectedRole }),
      });
      state.selectedActorId = payload.actor_id;
      state.selectedSection = 'actors';
      state.message = 'Created ' + payload.actor_id + '.';
      clearOpenTuiFeedback(state);
      await refreshAll(state, elements);
    } catch (error) {
      state.message = error.message;
      render(state, elements);
    } finally {
      state.createPending = false;
      render(state, elements);
    }
  }

  async function ensureWebImSession(state, elements) {
    if (state.imSessionReady) {
      startImPolling(state, elements);
      return;
    }
    await fetchJson('/api/web/im/session');
    state.imSessionReady = true;
    startImPolling(state, elements);
  }

  async function sendImDraft(state, elements) {
    await ensureWebImSession(state, elements);
    const target = selectedActorImTarget(state);
    if (!target) {
      throw new Error('Select an actor first.');
    }
    const content = state.draftText;
    const payload = await fetchJson('/api/web/im/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        target_identity_id: target.identity_id,
        content: state.draftText,
        reply_to: null,
      }),
    });
    recordImSent(state, payload, content);
    return payload;
  }

  async function pollImEventsOnce(state, elements) {
    if (!state.imSessionReady) {
      return;
    }
    const target = selectedActorImTarget(state);
    if (!target || !target.identity_id) {
      return;
    }
    const payload = await fetchJson(
      buildImEventsUrl(target.identity_id, 15000)
    );
    if (state.selectedActorId !== target.identity_id) {
      return;
    }
    const events = Array.isArray(payload.events) ? payload.events : [];
    applyImEventsPayload(state, payload);
    if (events.length) {
      await refreshSelectedActorConsoleAndRender(state, elements);
    }
    render(state, elements);
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
        render(state, elements);
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
      isMutating: Boolean(state.mutationKey),
    });
    if (!openTuiState.canOpenTui) {
      state.openTuiMessage = openTuiState.message;
      render(state, elements);
      return;
    }

    state.mutationKey = 'open-tui';
    state.openTuiMessage = 'Opening...';
    state.openTuiCommand = '';
    render(state, elements);
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
      state.mutationKey = '';
      render(state, elements);
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
    render(state, elements);
  }

  function actorActionUrl(state, action) {
    return '/api/instances/' + encodeURIComponent(state.selectedActorId) + '/' + action;
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
      actorRuntimeDetail: document.getElementById('actor-runtime-detail'),
      actorTaskSummary: document.getElementById('actor-task-summary'),
      actorTrackSummary: document.getElementById('actor-track-summary'),
      tracksList: document.getElementById('tracks-list'),
      trackDetail: document.getElementById('track-detail'),
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
      render(state, elements);
      scheduleActorConsoleRefresh(state, elements);
    });
    elements.tracksNavButton.addEventListener('click', function () {
      selectSection(state, 'tracks');
      render(state, elements);
    });
    elements.roleSelect.addEventListener('change', function (event) {
      state.selectedRole = event.target.value;
      render(state, elements);
    });
    elements.instructionInput.addEventListener('input', function (event) {
      state.draftText = event.target.value;
      render(state, elements);
    });
    elements.refreshButton.addEventListener('click', function () {
      refreshAll(state, elements).catch(function (error) {
        state.message = error.message;
        render(state, elements);
      });
    });
    elements.createButton.addEventListener('click', function () {
      createInstance(state, elements).catch(function (error) {
        state.message = error.message;
        render(state, elements);
      });
    });
    elements.sendButton.addEventListener('click', function () {
      runMutation(state, elements, 'messages', function () {
        return sendImDraft(state, elements);
      }).then(function () {
        state.draftText = '';
      });
    });
    elements.interruptButton.addEventListener('click', function () {
      runMutation(state, elements, 'interrupt', function () {
        return fetchJson(actorActionUrl(state, 'interrupt'), {
          method: 'POST',
        });
      });
    });
    elements.stopButton.addEventListener('click', function () {
      runMutation(state, elements, 'stop', function () {
        return fetchJson(actorActionUrl(state, 'stop'), {
          method: 'POST',
        });
      });
    });
    elements.clearButton.addEventListener('click', function () {
      runMutation(state, elements, 'clear', function () {
        return fetchJson(actorActionUrl(state, 'clear'), {
          method: 'POST',
        });
      });
    });
    elements.resumeButton.addEventListener('click', function () {
      runMutation(state, elements, 'resume', function () {
        return fetchJson(actorActionUrl(state, 'resume'), {
          method: 'POST',
        });
      });
    });
    elements.openTuiButton.addEventListener('click', function () {
      openTui(state, elements).catch(function (error) {
        state.openTuiMessage = error.message;
        render(state, elements);
      });
    });
    elements.copyTuiCommandButton.addEventListener('click', function () {
      copyOpenTuiCommand(state, elements).catch(function (error) {
        state.openTuiMessage = error.message;
        render(state, elements);
      });
    });
    elements.deleteButton.addEventListener('click', function () {
      runMutation(state, elements, 'delete', function () {
        return fetchJson('/api/instances/' + encodeURIComponent(state.selectedActorId), {
          method: 'DELETE',
        }).then(function (payload) {
          state.selectedActorId = '';
          state.actorConsole = null;
          clearOpenTuiFeedback(state);
          return payload;
        });
      });
    });

    try {
      await refreshAll(state, elements);
    } catch (error) {
      state.message = error.message;
      render(state, elements);
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
    applyImConversationPayload,
    applyImEventsPayload,
    applyTrackDetailPayload,
    applyTracksPayload,
    buildActorConsoleUrl,
    buildImEventsUrl,
    buildTrackDetailUrl,
    buildWebImConversationUrl,
    computeCreateEnabled,
    computeInstanceActionState,
    computeOpenTuiState,
    createState,
    describeInstanceActionState,
    recordImProjectedMessage,
    recordImSent,
    renderTrackDetailHtml,
    selectedActorRuntime,
    selectSection,
    shouldRefreshSelectedActorConsole,
  };
}));
