(function (root, factory) {
  const exportsObject = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = exportsObject;
  }
  root.BuddySwitchWebManagement = exportsObject;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function computeCreateEnabled(options) {
    return Boolean(options && options.selectedRole && !options.isCreating);
  }

  const IM_CONNECTION_KEY_STORAGE_KEY = 'buddyswitch.imConnectionKey';

  function readStoredImConnectionKey() {
    if (typeof localStorage === 'undefined') {
      return '';
    }
    try {
      const value = localStorage.getItem(IM_CONNECTION_KEY_STORAGE_KEY);
      return typeof value === 'string' ? value : '';
    } catch (_error) {
      return '';
    }
  }

  function writeStoredImConnectionKey(value) {
    if (typeof localStorage === 'undefined') {
      return;
    }
    try {
      localStorage.setItem(IM_CONNECTION_KEY_STORAGE_KEY, value);
    } catch (_error) {
      return;
    }
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
        message: 'Resume this instance first.',
      };
    }

    const appServerHealthy = instance.app_server_health === 'healthy'
      || Boolean(instance.app_server && instance.app_server.healthy);
    if (!appServerHealthy) {
      return {
        canOpenTui: false,
        message: 'Instance is unhealthy.',
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
      roles: [],
      instances: [],
      selectedRole: '',
      selectedInstanceId: '',
      selectedInstance: null,
      draftText: '',
      healthOk: false,
      message: '',
      createPending: false,
      mutationKey: '',
      openTuiMessage: '',
      openTuiCommand: '',
      imConnectionKey: readStoredImConnectionKey(),
      imConversation: [],
      imSeenMessageIds: {},
      imPolling: false,
      imPollTimer: null,
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

  function buildImEventsUrl(waitMs) {
    const normalizedWait = Number.isFinite(waitMs) && waitMs >= 0 ? Math.floor(waitMs) : 0;
    return '/api/im/events?wait_ms=' + encodeURIComponent(String(normalizedWait));
  }

  function participantLabel(participant) {
    if (!participant || typeof participant !== 'object') {
      return '';
    }
    if (participant.kind === 'actor' && participant.actor_address) {
      const roleId = participant.actor_address.role_id || '';
      const actorId = participant.actor_address.actor_id || '';
      return roleId && actorId ? roleId + '/' + actorId : '';
    }
    if (participant.kind === 'external') {
      return 'you';
    }
    return '';
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
      participant: 'you',
      content: typeof content === 'string' ? content : '',
      deliveryStatus: payload && payload.delivery_status ? payload.delivery_status : '',
      wakeStatus: payload && payload.wake_status ? payload.wake_status : '',
      replyTo: '',
    });
  }

  function recordImFetchedMessage(state, message) {
    if (!message || typeof message !== 'object') {
      return false;
    }
    const from = message.from && typeof message.from === 'object' ? message.from : {};
    if (from.kind !== 'actor') {
      return false;
    }
    return rememberImEntry(state, {
      id: typeof message.id === 'string' ? message.id : '',
      direction: 'reply',
      participant: participantLabel(from),
      content: typeof message.content === 'string' ? message.content : '',
      deliveryStatus: '',
      wakeStatus: '',
      replyTo: typeof message.reply_to === 'string' ? message.reply_to : '',
    });
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
        entry.participant,
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

  function renderTable(state, elements) {
    elements.instancesBody.innerHTML = '';
    if (state.instances.length === 0) {
      const row = document.createElement('tr');
      row.className = 'empty-row';
      row.innerHTML = '<td colspan="7"><span class="empty-state">No stored instances.</span></td>';
      elements.instancesBody.appendChild(row);
      return;
    }

    state.instances.forEach(function (instance) {
      const row = document.createElement('tr');
      if (instance.actor_id === state.selectedInstanceId) {
        row.className = 'is-selected';
        row.setAttribute('aria-current', 'true');
      }
      row.innerHTML = [
        '<td><span class="cell-strong mono-value long-value">' + escapeHtml(formatValue(instance.actor_id)) + '</span></td>',
        '<td>' + escapeHtml(formatValue(instance.role)) + '</td>',
        '<td>' + badge(instance.status) + '</td>',
        '<td>' + badge(resolveHealthLabel(instance)) + '</td>',
        '<td><span class="mono-value long-value">' + escapeHtml(formatValue(instance.thread_id)) + '</span></td>',
        '<td><span class="mono-value">' + escapeHtml(formatValue(instance.browser_port)) + '</span></td>',
        '<td><span class="cell-muted long-value">' + escapeHtml(formatValue(instance.updated_at)) + '</span></td>',
      ].join('');
      row.addEventListener('click', function () {
        selectInstance(state, elements, instance.actor_id);
      });
      elements.instancesBody.appendChild(row);
    });
  }

  function renderDetail(state, elements) {
    const instance = state.selectedInstance;
    const detailRows = [
      ['Instance', instance && instance.actor_id, 'mono-value long-value'],
      ['Role', instance && instance.role, ''],
      ['Status', instance && instance.status, ''],
      ['Health', instance && resolveHealthLabel(instance), ''],
      ['Thread', instance && instance.thread_id, 'mono-value long-value'],
      ['Thread State', instance && resolveThreadStatus(instance), ''],
      ['Browser Port', instance && instance.browser_port, 'mono-value'],
      ['Updated', instance && instance.updated_at, 'long-value'],
      ['Workspace', instance && instance.workspace_dir, 'mono-value long-value'],
    ];
    elements.instanceDetail.innerHTML = detailRows.map(function (entry) {
      const valueClass = entry[2] ? ' class="' + entry[2] + '"' : '';
      return '<dt>' + escapeHtml(entry[0]) + '</dt><dd' + valueClass + '>' + escapeHtml(formatValue(entry[1])) + '</dd>';
    }).join('');
  }

  function resolveHealthLabel(instance) {
    if (!instance) {
      return '';
    }
    if (instance.app_server_health) {
      return instance.app_server_health;
    }
    if (instance.app_server && typeof instance.app_server.healthy === 'boolean') {
      return instance.app_server.healthy ? 'healthy' : 'unhealthy';
    }
    return '';
  }

  function resolveThreadStatus(instance) {
    return instance && instance.thread && typeof instance.thread.status === 'string'
      ? instance.thread.status
      : '';
  }

  function resolveStatusTone(value) {
    if (value === 'active' || value === 'healthy' || value === 'idle') {
      return 'healthy';
    }
    if (value === 'in_progress' || value === 'active_thread' || value === 'active turn') {
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

  function render(state, elements) {
    elements.serverStatus.textContent = state.healthOk ? 'API Ready' : 'API Unavailable';
    elements.messageBanner.textContent = state.message;
    elements.instructionInput.value = state.draftText;
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

    renderTable(state, elements);
    renderDetail(state, elements);
    renderImConversation(state, elements);

    const actionState = computeInstanceActionState(state.selectedInstance, {
      draftText: state.draftText,
      isMutating: Boolean(state.mutationKey),
    });
    elements.sendButton.disabled = !actionState.canSend;
    elements.interruptButton.disabled = !actionState.canInterrupt;
    elements.stopButton.disabled = !actionState.canStop;
    elements.deleteButton.disabled = !actionState.canDelete;
    elements.clearButton.disabled = !actionState.canClear;
    elements.resumeButton.disabled = !actionState.canResume;

    const openTuiState = computeOpenTuiState(state.selectedInstance, {
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
  }

  function clearOpenTuiFeedback(state) {
    state.openTuiMessage = '';
    state.openTuiCommand = '';
  }

  async function refreshAll(state, elements) {
    const previousSelectedInstanceId = state.selectedInstanceId;
    const [healthPayload, rolesPayload, instancesPayload] = await Promise.all([
      fetchJson('/api/health'),
      fetchJson('/api/roles'),
      fetchJson('/api/instances'),
    ]);
    state.healthOk = Boolean(healthPayload.ok);
    state.roles = rolesPayload.roles || [];
    if (!state.selectedRole && state.roles.length > 0) {
      state.selectedRole = state.roles[0].id;
    }
    state.instances = instancesPayload.instances || [];
    if (state.selectedInstanceId) {
      const stillPresent = state.instances.some(function (instance) {
        return instance.actor_id === state.selectedInstanceId;
      });
      if (!stillPresent) {
        state.selectedInstanceId = '';
      }
    }
    if (!state.selectedInstanceId && state.instances.length > 0) {
      state.selectedInstanceId = state.instances[0].actor_id;
    }
    if (state.selectedInstanceId !== previousSelectedInstanceId) {
      clearOpenTuiFeedback(state);
    }
    await refreshSelectedInstance(state);
    render(state, elements);
  }

  async function refreshSelectedInstance(state) {
    if (!state.selectedInstanceId) {
      state.selectedInstance = null;
      return;
    }
    const payload = await fetchJson('/api/instances/' + encodeURIComponent(state.selectedInstanceId) + '/status');
    state.selectedInstance = payload.instance;
  }

  async function selectInstance(state, elements, instanceId) {
    state.selectedInstanceId = instanceId;
    clearOpenTuiFeedback(state);
    await refreshSelectedInstance(state);
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
        ? 'Action completed for ' + state.selectedInstanceId + ' (' + payload.turn_id + ').'
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
      state.selectedInstanceId = payload.actor_id;
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

  async function ensureImConnection(state, elements) {
    if (state.imConnectionKey) {
      startImPolling(state, elements);
      return;
    }
    const payload = await fetchJson('/api/im/connections', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        display_name: 'BuddySwitch Web',
      }),
    });
    state.imConnectionKey = payload.connection_key;
    writeStoredImConnectionKey(state.imConnectionKey);
    startImPolling(state, elements);
  }

  async function sendImDraft(state, elements) {
    await ensureImConnection(state, elements);
    const content = state.draftText;
    const payload = await fetchJson('/api/im/messages', {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer ' + state.imConnectionKey,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        to: {
          kind: 'actor',
          actor_address: {
            role_id: state.selectedInstance.role,
            actor_id: state.selectedInstanceId,
          },
        },
        content: state.draftText,
        reply_to: null,
      }),
    });
    recordImSent(state, payload, content);
    return payload;
  }

  async function pollImEventsOnce(state, elements) {
    if (!state.imConnectionKey) {
      return;
    }
    const payload = await fetchJson(buildImEventsUrl(15000), {
      headers: {
        'Authorization': 'Bearer ' + state.imConnectionKey,
      },
    });
    const events = Array.isArray(payload.events) ? payload.events : [];
    for (const event of events) {
      if (!event || event.type !== 'message.created' || typeof event.message_id !== 'string') {
        continue;
      }
      const messagePayload = await fetchJson('/api/im/messages/' + encodeURIComponent(event.message_id), {
        headers: {
          'Authorization': 'Bearer ' + state.imConnectionKey,
        },
      });
      recordImFetchedMessage(state, messagePayload.message);
    }
    render(state, elements);
  }

  function startImPolling(state, elements) {
    if (!elements || !state.imConnectionKey || state.imPolling || state.imPollTimer) {
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
        if (state.imConnectionKey) {
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
    const openTuiState = computeOpenTuiState(state.selectedInstance, {
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
      const payload = await fetchJson('/api/instances/' + encodeURIComponent(state.selectedInstanceId) + '/open-tui', {
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

  async function bootstrap() {
    if (typeof document === 'undefined') {
      return;
    }
    const elements = {
      roleSelect: document.getElementById('role-select'),
      createButton: document.getElementById('create-button'),
      refreshButton: document.getElementById('refresh-button'),
      serverStatus: document.getElementById('server-status'),
      instancesBody: document.getElementById('instances-body'),
      instanceDetail: document.getElementById('instance-detail'),
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
      imConversation: document.getElementById('im-conversation'),
    };

    const state = createState();

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
        return fetchJson('/api/instances/' + encodeURIComponent(state.selectedInstanceId) + '/interrupt', {
          method: 'POST',
        });
      });
    });
    elements.stopButton.addEventListener('click', function () {
      runMutation(state, elements, 'stop', function () {
        return fetchJson('/api/instances/' + encodeURIComponent(state.selectedInstanceId) + '/stop', {
          method: 'POST',
        });
      });
    });
    elements.clearButton.addEventListener('click', function () {
      runMutation(state, elements, 'clear', function () {
        return fetchJson('/api/instances/' + encodeURIComponent(state.selectedInstanceId) + '/clear', {
          method: 'POST',
        });
      });
    });
    elements.resumeButton.addEventListener('click', function () {
      runMutation(state, elements, 'resume', function () {
        return fetchJson('/api/instances/' + encodeURIComponent(state.selectedInstanceId) + '/resume', {
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
        return fetchJson('/api/instances/' + encodeURIComponent(state.selectedInstanceId), {
          method: 'DELETE',
        }).then(function (payload) {
          state.selectedInstanceId = '';
          state.selectedInstance = null;
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
    buildImEventsUrl,
    computeCreateEnabled,
    computeInstanceActionState,
    computeOpenTuiState,
    createState,
    recordImFetchedMessage,
    recordImSent,
  };
}));
