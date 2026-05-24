(function (root, factory) {
  const exportsObject = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = exportsObject;
  }
  root.BuddySwitchWebManagement = exportsObject;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function computeCreateEnabled(options) {
    return Boolean(options && options.selectedBuddy && !options.isCreating);
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

    return {
      canSend: isActive && appServerHealthy && draftText.length > 0,
      canInterrupt: isActive && appServerHealthy && (threadStatus === 'active' || threadStatus === 'in_progress'),
      canStop: isActive,
      canDelete: isInactive,
    };
  }

  function createState() {
    return {
      buddies: [],
      instances: [],
      selectedBuddy: '',
      selectedInstanceId: '',
      selectedInstance: null,
      draftText: '',
      healthOk: false,
      message: '',
      createPending: false,
      mutationKey: '',
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

  function renderTable(state, elements) {
    elements.instancesBody.innerHTML = '';
    if (state.instances.length === 0) {
      const row = document.createElement('tr');
      row.innerHTML = '<td colspan="7">No stored instances.</td>';
      elements.instancesBody.appendChild(row);
      return;
    }

    state.instances.forEach(function (instance) {
      const row = document.createElement('tr');
      if (instance.instance_id === state.selectedInstanceId) {
        row.className = 'is-selected';
      }
      row.innerHTML = [
        '<td>' + formatValue(instance.instance_id) + '</td>',
        '<td>' + formatValue(instance.buddy) + '</td>',
        '<td>' + formatValue(instance.status) + '</td>',
        '<td>' + formatValue(instance.app_server_health) + '</td>',
        '<td>' + formatValue(instance.thread_id) + '</td>',
        '<td>' + formatValue(instance.browser_port) + '</td>',
        '<td>' + formatValue(instance.updated_at) + '</td>',
      ].join('');
      row.addEventListener('click', function () {
        selectInstance(state, elements, instance.instance_id);
      });
      elements.instancesBody.appendChild(row);
    });
  }

  function renderDetail(state, elements) {
    const instance = state.selectedInstance;
    const detailRows = [
      ['Instance', instance && instance.instance_id],
      ['Buddy', instance && instance.buddy],
      ['Status', instance && instance.status],
      ['Health', instance && resolveHealthLabel(instance)],
      ['Thread', instance && instance.thread_id],
      ['Thread State', instance && instance.thread && instance.thread.status],
      ['Browser Port', instance && instance.browser_port],
      ['Updated', instance && instance.updated_at],
      ['Workspace', instance && instance.workspace_dir],
    ];
    elements.instanceDetail.innerHTML = detailRows.map(function (entry) {
      return '<dt>' + entry[0] + '</dt><dd>' + formatValue(entry[1]) + '</dd>';
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

  function render(state, elements) {
    elements.serverStatus.textContent = state.healthOk ? 'API Ready' : 'API Unavailable';
    elements.messageBanner.textContent = state.message;
    elements.instructionInput.value = state.draftText;
    elements.createButton.disabled = !computeCreateEnabled({
      selectedBuddy: state.selectedBuddy,
      isCreating: state.createPending,
    });

    if (elements.buddySelect.options.length === 0) {
      const placeholder = document.createElement('option');
      placeholder.value = '';
      placeholder.textContent = 'Select buddy';
      elements.buddySelect.appendChild(placeholder);
      state.buddies.forEach(function (buddy) {
        const option = document.createElement('option');
        option.value = buddy.id;
        option.textContent = buddy.label + ' (' + buddy.id + ')';
        elements.buddySelect.appendChild(option);
      });
    }
    elements.buddySelect.value = state.selectedBuddy;

    renderTable(state, elements);
    renderDetail(state, elements);

    const actionState = computeInstanceActionState(state.selectedInstance, {
      draftText: state.draftText,
      isMutating: Boolean(state.mutationKey),
    });
    elements.sendButton.disabled = !actionState.canSend;
    elements.interruptButton.disabled = !actionState.canInterrupt;
    elements.stopButton.disabled = !actionState.canStop;
    elements.deleteButton.disabled = !actionState.canDelete;
  }

  async function refreshAll(state, elements) {
    const [healthPayload, buddiesPayload, instancesPayload] = await Promise.all([
      fetchJson('/api/health'),
      fetchJson('/api/buddies'),
      fetchJson('/api/instances'),
    ]);
    state.healthOk = Boolean(healthPayload.ok);
    state.buddies = buddiesPayload.buddies || [];
    if (!state.selectedBuddy && state.buddies.length > 0) {
      state.selectedBuddy = state.buddies[0].id;
    }
    state.instances = instancesPayload.instances || [];
    if (state.selectedInstanceId) {
      const stillPresent = state.instances.some(function (instance) {
        return instance.instance_id === state.selectedInstanceId;
      });
      if (!stillPresent) {
        state.selectedInstanceId = '';
      }
    }
    if (!state.selectedInstanceId && state.instances.length > 0) {
      state.selectedInstanceId = state.instances[0].instance_id;
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
    await refreshSelectedInstance(state);
    render(state, elements);
  }

  async function runMutation(state, elements, key, requestFactory) {
    state.mutationKey = key;
    render(state, elements);
    try {
      const payload = await requestFactory();
      state.message = payload && payload.turn_id
        ? 'Action completed for ' + state.selectedInstanceId + ' (' + payload.turn_id + ').'
        : 'Action completed.';
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
        body: JSON.stringify({ buddy: state.selectedBuddy }),
      });
      state.selectedInstanceId = payload.instance_id;
      state.message = 'Created ' + payload.instance_id + '.';
      await refreshAll(state, elements);
    } catch (error) {
      state.message = error.message;
      render(state, elements);
    } finally {
      state.createPending = false;
      render(state, elements);
    }
  }

  async function bootstrap() {
    if (typeof document === 'undefined') {
      return;
    }
    const elements = {
      buddySelect: document.getElementById('buddy-select'),
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
      messageBanner: document.getElementById('message-banner'),
    };

    const state = createState();

    elements.buddySelect.addEventListener('change', function (event) {
      state.selectedBuddy = event.target.value;
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
      runMutation(state, elements, 'input', function () {
        return fetchJson('/api/instances/' + encodeURIComponent(state.selectedInstanceId) + '/input', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: state.draftText }),
        });
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
    elements.deleteButton.addEventListener('click', function () {
      runMutation(state, elements, 'delete', function () {
        return fetchJson('/api/instances/' + encodeURIComponent(state.selectedInstanceId), {
          method: 'DELETE',
        }).then(function (payload) {
          state.selectedInstanceId = '';
          state.selectedInstance = null;
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
    computeCreateEnabled,
    computeInstanceActionState,
  };
}));
