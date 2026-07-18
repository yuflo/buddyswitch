(function (root, factory) {
  const exportsObject = factory(root);
  if (typeof module === 'object' && module.exports) {
    module.exports = exportsObject;
  }
  root.BuddySwitchWebManagement = exportsObject;
}(typeof globalThis !== 'undefined' ? globalThis : this, function (root) {
  'use strict';

  const ACTOR_CONSOLE_REFRESH_INTERVAL_MS = 3000;

  function computeCreateEnabled(options) {
    return Boolean(options && options.selectedRole);
  }

  function operationIsActive(operation) {
    return Boolean(operation && (operation.status === 'queued' || operation.status === 'running'));
  }

  function operationIsTerminal(operation) {
    return Boolean(operation && (operation.status === 'succeeded' || operation.status === 'failed'));
  }

  function lifecycleOperationList(state) {
    if (!state || !state.lifecycleOperations || typeof state.lifecycleOperations !== 'object') {
      return [];
    }
    return Object.keys(state.lifecycleOperations).map(function (operationId) {
      return state.lifecycleOperations[operationId];
    }).filter(Boolean);
  }

  function activeLifecycleOperationForActor(state, actorId) {
    if (!actorId) {
      return null;
    }
    return lifecycleOperationList(state).find(function (operation) {
      const target = operation && operation.target ? operation.target : {};
      const actor = actorById(state, actorId);
      const targetActorId = typeof target.actor_id === 'string' ? target.actor_id : '';
      const targetReplacementActorId = typeof target.replacement_actor_id === 'string'
        ? target.replacement_actor_id
        : '';
      const previousActorId = actor && typeof actor.previous_actor_id === 'string'
        ? actor.previous_actor_id
        : '';
      const replacementActorId = actor && typeof actor.replacement_actor_id === 'string'
        ? actor.replacement_actor_id
        : '';
      return operationIsActive(operation) && (
        targetActorId === actorId
        || (targetReplacementActorId && targetReplacementActorId === actorId)
        || (previousActorId && previousActorId === targetActorId)
        || (replacementActorId && replacementActorId === targetReplacementActorId)
      );
    }) || null;
  }

  function recordLifecycleOperation(state, operation) {
    if (!state || !operation || typeof operation.id !== 'string' || !operation.id) {
      return null;
    }
    state.lifecycleOperations[operation.id] = operation;
    return operation;
  }

  function forgetLifecycleOperation(state, operationOrId) {
    if (!state || !state.lifecycleOperations) {
      return;
    }
    const operationId = typeof operationOrId === 'string'
      ? operationOrId
      : operationOrId && operationOrId.id;
    if (operationId) {
      delete state.lifecycleOperations[operationId];
    }
  }

  function lifecycleOperationActorId(operation) {
    if (!operation) {
      return '';
    }
    const result = operation.result && typeof operation.result === 'object' ? operation.result : {};
    const target = operation.target && typeof operation.target === 'object' ? operation.target : {};
    return (typeof result.actor_id === 'string' && result.actor_id)
      || (result.instance && typeof result.instance.actor_id === 'string' && result.instance.actor_id)
      || (typeof target.actor_id === 'string' && target.actor_id)
      || '';
  }

  function lifecycleOperationRoleId(operation) {
    const target = operation && operation.target && typeof operation.target === 'object' ? operation.target : {};
    return typeof target.role === 'string' ? target.role : '';
  }

  function lifecycleActionVerb(action) {
    if (action === 'start') {
      return 'Starting';
    }
    if (action === 'stop') {
      return 'Stopping';
    }
    if (action === 'resume') {
      return 'Resuming';
    }
    if (action === 'clear') {
      return 'Clearing';
    }
    if (action === 'delete') {
      return 'Deleting';
    }
    if (action === 'retry') {
      return 'Retrying';
    }
    return 'Working';
  }

  function lifecycleActionName(action) {
    if (action === 'start') {
      return 'Start';
    }
    if (action === 'stop') {
      return 'Stop';
    }
    if (action === 'resume') {
      return 'Resume';
    }
    if (action === 'clear') {
      return 'Clear';
    }
    if (action === 'delete') {
      return 'Delete';
    }
    if (action === 'retry') {
      return 'Retry';
    }
    return 'Lifecycle operation';
  }

  function lifecycleOperationBadgeText(operation) {
    if (operation && operation.status === 'queued') {
      return 'queued';
    }
    const action = operation && operation.action;
    if (action === 'start') {
      return 'starting';
    }
    if (action === 'stop') {
      return 'stopping';
    }
    if (action === 'resume') {
      return 'resuming';
    }
    if (action === 'clear') {
      return 'clearing';
    }
    if (action === 'delete') {
      return 'deleting';
    }
    if (action === 'retry') {
      return 'retrying';
    }
    return 'initializing';
  }

  function lifecycleOperationLabel(operation) {
    if (!operation) {
      return '';
    }
    if (typeof operation.label === 'string' && operation.label) {
      return operation.label;
    }
    const actorId = lifecycleOperationActorId(operation);
    const roleId = lifecycleOperationRoleId(operation);
    const suffix = actorId || roleId;
    return lifecycleActionVerb(operation.action) + (suffix ? ' ' + suffix : '');
  }

  function lifecycleOperationStatusText(operation) {
    if (!operation) {
      return '';
    }
    const label = lifecycleOperationLabel(operation);
    if (operation.status === 'failed') {
      const message = operation.error && operation.error.message ? operation.error.message : 'Operation failed.';
      return label ? label + ' failed: ' + message : message;
    }
    if (operation.status === 'succeeded') {
      const result = operation.result && typeof operation.result === 'object' ? operation.result : {};
      const threadId = operation.action === 'clear' && typeof result.thread_id === 'string' && result.thread_id
        ? result.thread_id
        : '';
      const completed = label ? label + ' completed.' : 'Lifecycle operation completed.';
      return threadId ? completed + ' Thread ' + threadId + '.' : completed;
    }
    const detail = typeof operation.detail === 'string' && operation.detail ? operation.detail : 'Operation is running.';
    return label ? label + '. ' + detail : detail;
  }

  function lifecycleProtectionStatusText(operation) {
    if (!operationIsActive(operation)) {
      return '';
    }
    const name = lifecycleActionName(operation.action);
    const phase = operation.status === 'queued' ? 'queued' : 'in progress';
    if (operation.action === 'start') {
      return name + ' ' + phase + '. Actor actions are protected until ' + name + ' completes.';
    }
    return name + ' ' + phase + '. Other lifecycle actions are protected until ' + name + ' completes.';
  }

  function computeInstanceActionState(instance, options) {
    const draftText = options && typeof options.draftText === 'string' ? options.draftText.trim() : '';
    const sendPending = Boolean(options && options.sendPending);
    const lifecycleOperation = options && operationIsActive(options.lifecycleOperation)
      ? options.lifecycleOperation
      : null;
    const interruptPending = Boolean(options && options.interruptPending);
    if (!instance) {
      return {
        canSend: false,
        canInterrupt: false,
        canStop: false,
        canDelete: false,
        canClear: false,
        canResume: false,
        canRetry: false,
      };
    }

    const lifecycleState = typeof instance.lifecycle_state === 'string' ? instance.lifecycle_state : '';
    const status = instance.status || '';
    const threadStatus = instance.thread && typeof instance.thread.status === 'string'
      ? instance.thread.status
      : '';
    const appServerHealthy = instance.app_server_health === 'healthy'
      || Boolean(instance.app_server && instance.app_server.healthy);
    const isActive = lifecycleState === 'active';
    const isStopped = lifecycleState === 'stopped';
    const isStartFailed = lifecycleState === 'start_failed';
    const threadBusy = threadStatus === 'active' || threadStatus === 'in_progress';
    const lifecyclePending = Boolean(lifecycleOperation);

    return {
      canSend: isActive && appServerHealthy && draftText.length > 0 && !sendPending,
      canInterrupt: isActive && appServerHealthy && threadBusy && !lifecyclePending && !interruptPending,
      canStop: isActive && !lifecyclePending,
      canDelete: (isStopped || isStartFailed) && !lifecyclePending,
      canClear: isActive && appServerHealthy && !threadBusy && !lifecyclePending,
      canResume: isStopped && !lifecyclePending,
      canRetry: isStartFailed && !lifecyclePending,
    };
  }

  function lifecycleActionAllowed(state, action, actorId) {
    const lifecycleOperation = activeLifecycleOperationForActor(state, actorId);
    const actionState = computeInstanceActionState(actorRuntimeForId(state, actorId), {
      draftText: state.draftText,
      sendPending: state.sendPending,
      lifecycleOperation,
      interruptPending: state.interruptPending,
    });
    if (action === 'stop') {
      return actionState.canStop;
    }
    if (action === 'resume') {
      return actionState.canResume;
    }
    if (action === 'clear') {
      return actionState.canClear;
    }
    if (action === 'delete') {
      return actionState.canDelete;
    }
    if (action === 'retry') {
      return actionState.canRetry;
    }
    return false;
  }

  function describeInstanceActionState(instance, options) {
    const state = computeInstanceActionState(instance, options);
    const lifecycleOperation = options && operationIsActive(options.lifecycleOperation)
      ? options.lifecycleOperation
      : null;
    const status = instance && instance.status ? instance.status : '';
    const lifecycleState = instance && typeof instance.lifecycle_state === 'string'
      ? instance.lifecycle_state
      : '';
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
    } else if (lifecycleOperation) {
      clearReason = lifecycleOperationLabel(lifecycleOperation) + '.';
    } else if (lifecycleState === 'start_failed') {
      clearReason = 'Retry or delete this actor.';
    } else if (status !== 'active') {
      clearReason = 'Resume actor first.';
    } else if (!appServerHealthy) {
      clearReason = 'Runtime unhealthy.';
    } else if (threadBusy) {
      clearReason = 'Thread running.';
    }

    return Object.assign({}, state, {
      clearReason: state.canClear ? '' : clearReason,
      lifecycleStatus: lifecycleOperation ? lifecycleOperationStatusText(lifecycleOperation) : '',
      lifecycleProtectionStatus: lifecycleOperation ? lifecycleProtectionStatusText(lifecycleOperation) : '',
    });
  }

  function computeAttachActionState(instance) {
    if (!instance) {
      return {
        canAttach: false,
        message: '',
      };
    }

    const lifecycleState = typeof instance.lifecycle_state === 'string' ? instance.lifecycle_state : '';
    const status = instance.status || '';
    if (lifecycleState === 'start_failed') {
      return {
        canAttach: false,
        message: 'Retry or delete this actor.',
      };
    }
    if (lifecycleState === 'starting' || lifecycleState === 'retrying') {
      return {
        canAttach: false,
        message: 'Available after startup completes.',
      };
    }
    if (status !== 'active') {
      return {
        canAttach: false,
        message: 'Resume this actor first.',
      };
    }

    const appServerHealthy = instance.app_server_health === 'healthy'
      || Boolean(instance.app_server && instance.app_server.healthy);
    if (!appServerHealthy) {
      return {
        canAttach: false,
        message: 'Actor runtime is unhealthy.',
      };
    }

    const threadId = typeof instance.thread_id === 'string' ? instance.thread_id.trim() : '';
    if (!threadId) {
      return {
        canAttach: false,
        message: 'No thread to attach.',
      };
    }

    return {
      canAttach: true,
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
      actorTaskRecentExpanded: false,
      actorTaskOpenId: '',
      actorCapabilityActorId: '',
      actorCapabilitySaved: { parent: '', side: '' },
      actorCapabilityDraft: { parent: '', side: '' },
      actorCapabilityCatalog: [],
      actorCapabilityPanelOpen: false,
      actorCapabilitySaving: false,
      actorCapabilityStatus: '',
      actorCapabilityError: '',
      selectedTrackId: '',
      selectedTrackDetail: null,
      draftText: '',
      healthOk: false,
      message: '',
      sendPending: false,
      refreshPending: false,
      lifecycleOperations: {},
      lifecycleOperationPollTimer: null,
      lifecycleOperationPollInFlight: false,
      lifecycleOperationPollDelaysMs: null,
      interruptPending: false,
      openTuiPending: false,
      copyCommandPending: false,
      appBasicsLoading: false,
      appBasicsError: '',
      rosterLoading: false,
      rosterError: '',
      rosterStoppedExpanded: false,
      tracksListLoading: false,
      tracksError: '',
      selectedTrackDetailLoading: false,
      selectedTrackDetailError: '',
      actorCardLoading: false,
      actorCardError: '',
      conversationLoading: false,
      conversationError: '',
      actorConsoleAbortController: null,
      actorConversationAbortController: null,
      actorSelectionPendingId: '',
      trackSelectionPendingId: '',
      actorSelectionRequestId: 0,
      actorConsoleRequestId: 0,
      trackSelectionRequestId: 0,
      deleteConfirmationActorId: '',
      deleteConfirmationInput: '',
      deleteConfirmationTrigger: null,
      openTuiMessage: '',
      copyCommandMessage: '',
      imSessionReady: false,
      imConversationIdentityId: '',
      imConversation: [],
      imSeenMessageIds: {},
      imFreshMessageIds: {},
      imPolling: false,
      imPollTimer: null,
      actorRefreshTimer: null,
      actorRefreshInFlight: false,
    };
  }

  function createAbortController() {
    if (typeof AbortController === 'undefined') {
      return null;
    }
    return new AbortController();
  }

  function isAbortError(error) {
    return Boolean(error && (error.name === 'AbortError' || error.code === 'ABORT_ERR'));
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

  function createAppMarkdownRenderer() {
    const rendererFactory = root.BuddySwitchMarkdownRenderer
      && typeof root.BuddySwitchMarkdownRenderer.createMarkdownRenderer === 'function'
      ? root.BuddySwitchMarkdownRenderer.createMarkdownRenderer
      : null;
    return rendererFactory ? rendererFactory() : null;
  }

  const markdownRenderer = createAppMarkdownRenderer();

  function renderMessageContentHtml(content) {
    if (!markdownRenderer || typeof markdownRenderer.renderMarkdownMessageHtml !== 'function') {
      throw new Error('BuddySwitch markdown renderer is not loaded.');
    }
    return markdownRenderer.renderMarkdownMessageHtml(content);
  }

  function buildActorConsoleUrl(actorId) {
    return '/api/actors/' + encodeURIComponent(actorId) + '/console';
  }

  function buildActorCapabilitiesUrl(actorId) {
    return '/api/actors/' + encodeURIComponent(actorId) + '/capabilities';
  }

  function capabilitySelectionFromConsole(actorConsole) {
    const capabilities = actorConsole && actorConsole.capabilities;
    return {
      parent: capabilities && capabilities.parent && typeof capabilities.parent.level === 'string'
        ? capabilities.parent.level
        : '',
      side: capabilities && capabilities.side && typeof capabilities.side.level === 'string'
        ? capabilities.side.level
        : '',
    };
  }

  function sameCapabilitySelection(left, right) {
    return Boolean(left && right && left.parent === right.parent && left.side === right.side);
  }

  function capabilityPayloadIsComplete(payload) {
    function nonEmptyText(value) {
      return typeof value === 'string' && Boolean(value.trim());
    }
    function completeCatalogRow(row) {
      return row && nonEmptyText(row.id) && nonEmptyText(row.label)
        && nonEmptyText(row.description) && nonEmptyText(row.model) && nonEmptyText(row.effort);
    }
    function completeSelection(selection) {
      return selection && nonEmptyText(selection.level) && nonEmptyText(selection.model)
        && nonEmptyText(selection.effort) && nonEmptyText(selection.effect);
    }
    if (!payload || typeof payload !== 'object' || !Array.isArray(payload.levels)
        || payload.levels.length !== 4
        || !Number.isInteger(payload.catalog_version) || payload.catalog_version < 1
        || !payload.levels.every(completeCatalogRow)
        || !completeSelection(payload.parent) || !completeSelection(payload.side)) {
      return false;
    }
    const ids = payload.levels.map(function (row) {
      return row && typeof row.id === 'string' ? row.id : '';
    });
    return new Set(ids).size === 4
      && ids.every(Boolean)
      && typeof payload.parent.level === 'string'
      && typeof payload.side.level === 'string'
      && ids.includes(payload.parent.level)
      && ids.includes(payload.side.level);
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

  function clearAttachToolFeedback(state) {
    state.openTuiMessage = '';
    state.copyCommandMessage = '';
  }

  function selectSection(state, section) {
    state.selectedSection = section === 'tracks' ? 'tracks' : 'actors';
  }

  function applyActorsPayload(state, payload) {
    const previousActorId = state.selectedActorId;
    const previousSelectedActor = state.actors.find(function (actor) {
      return actor.actor_id === previousActorId;
    }) || null;
    const incomingActors = payload && Array.isArray(payload.actors) ? payload.actors : [];
    state.actors = incomingActors.slice();
    incomingActors.forEach(function (actor) {
      if (actor && operationIsActive(actor.lifecycle_operation)) {
        recordLifecycleOperation(state, actor.lifecycle_operation);
      }
    });
    const selectedActor = actorById(state, state.selectedActorId);
    const replacementActor = !selectedActor && previousActorId
      ? incomingActors.find(function (actor) {
          return actor && actor.previous_actor_id === previousActorId;
        }) || null
      : null;
    if (selectedActor && actorIsStopped(selectedActor) && (
      state.selectedActorId !== previousActorId
      || !previousSelectedActor
      || !actorIsStopped(previousSelectedActor)
    )) {
      state.rosterStoppedExpanded = true;
    }
    return {
      selectedActorPresent: Boolean(selectedActor),
      preferredActorId: preferredActorId(state.actors),
      replacementActorId: replacementActor && replacementActor.actor_id ? replacementActor.actor_id : '',
    };
  }

  function applyActorConsolePayload(state, payload) {
    const consolePayload = payload && payload.console && typeof payload.console === 'object'
      ? payload.console
      : null;
    state.actorConsole = consolePayload;
    syncActorCapabilitiesFromConsole(state);
  }

  function syncActorCapabilitiesFromConsole(state, options) {
    const force = Boolean(options && options.force);
    const actorId = state.actorConsole && state.actorConsole.actor
      && typeof state.actorConsole.actor.actor_id === 'string'
      ? state.actorConsole.actor.actor_id
      : state.selectedActorId;
    const actorChanged = state.actorCapabilityActorId !== actorId;
    if (!force && !actorChanged && state.actorCapabilityPanelOpen
        && !sameCapabilitySelection(state.actorCapabilityDraft, state.actorCapabilitySaved)) {
      return;
    }
    const selection = capabilitySelectionFromConsole(state.actorConsole);
    const capabilities = state.actorConsole && state.actorConsole.capabilities;
    state.actorCapabilityActorId = actorId || '';
    state.actorCapabilitySaved = { parent: selection.parent, side: selection.side };
    state.actorCapabilityDraft = { parent: selection.parent, side: selection.side };
    state.actorCapabilityCatalog = capabilities && Array.isArray(capabilities.levels)
      ? capabilities.levels.slice()
      : [];
    state.actorCapabilityError = '';
    state.actorCapabilityStatus = '';
    state.actorCapabilitySaving = false;
    if (force || actorChanged) {
      state.actorCapabilityPanelOpen = false;
    }
  }

  function selectActorCapability(state, role, level) {
    if (role !== 'parent' && role !== 'side') {
      return false;
    }
    const exists = state.actorCapabilityCatalog.some(function (row) {
      return row && row.id === level;
    });
    if (!exists) {
      return false;
    }
    state.actorCapabilityDraft = Object.assign({}, state.actorCapabilityDraft, { [role]: level });
    state.actorCapabilityError = '';
    state.actorCapabilityStatus = sameCapabilitySelection(state.actorCapabilityDraft, state.actorCapabilitySaved)
      ? ''
      : 'Unsaved changes.';
    return true;
  }

  function cancelActorCapabilityDraft(state) {
    state.actorCapabilityDraft = Object.assign({}, state.actorCapabilitySaved);
    state.actorCapabilityError = '';
    state.actorCapabilityStatus = '';
    state.actorCapabilityPanelOpen = false;
  }

  async function saveActorCapabilities(state) {
    if (!state.selectedActorId || state.actorCapabilityActorId !== state.selectedActorId
        || state.actorCapabilitySaving
        || sameCapabilitySelection(state.actorCapabilityDraft, state.actorCapabilitySaved)) {
      return null;
    }
    const actorId = state.selectedActorId;
    const requestId = state.actorSelectionRequestId;
    function requestOwnsState() {
      return state.selectedActorId === actorId
        && state.actorCapabilityActorId === actorId
        && state.actorSelectionRequestId === requestId;
    }
    const draft = {
      parent: state.actorCapabilityDraft.parent,
      side: state.actorCapabilityDraft.side,
    };
    state.actorCapabilitySaving = true;
    state.actorCapabilityStatus = 'Saving...';
    try {
      const response = await fetchJson(buildActorCapabilitiesUrl(actorId), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draft),
      });
      if (!requestOwnsState()) {
        return response;
      }
      const canonical = response && response.capabilities && typeof response.capabilities === 'object'
        ? response.capabilities
        : null;
      if (!response || response.actor_id !== actorId || !capabilityPayloadIsComplete(canonical)) {
        throw new Error('Capability response is invalid.');
      }
      if (state.actorConsole) {
        state.actorConsole.capabilities = canonical;
      }
      syncActorCapabilitiesFromConsole(state, { force: true });
      return response;
    } catch (error) {
      if (requestOwnsState()) {
        state.actorCapabilityError = error && error.message ? error.message : 'Request failed.';
        state.actorCapabilityStatus = state.actorCapabilityError;
      }
      return null;
    } finally {
      if (requestOwnsState()) {
        state.actorCapabilitySaving = false;
      }
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

  function actorLifecycleState(actor) {
    return actor && typeof actor.lifecycle_state === 'string' ? actor.lifecycle_state : '';
  }

  function actorIsStopped(actor) {
    return actorLifecycleState(actor) === 'stopped';
  }

  function actorIsStartupOnly(actor) {
    return ['starting', 'retrying', 'start_failed'].indexOf(actorLifecycleState(actor)) >= 0;
  }

  function actorIsInteractive(actor) {
    return ['active', 'stopped'].indexOf(actorLifecycleState(actor)) >= 0;
  }

  function preferredActorId(actors) {
    const rows = Array.isArray(actors) ? actors : [];
    const activeActor = rows.find(function (actor) {
      return actorLifecycleState(actor) === 'active';
    });
    const readyActor = rows.find(actorIsInteractive);
    const preferred = activeActor || readyActor || rows[0] || null;
    return preferred && typeof preferred.actor_id === 'string' ? preferred.actor_id : '';
  }

  function runtimeRowFromLifecycleInstance(instance, fallbackActorId, fallbackRole) {
    if (!instance || typeof instance !== 'object') {
      return null;
    }
    const actorId = typeof instance.actor_id === 'string' && instance.actor_id
      ? instance.actor_id
      : fallbackActorId;
    if (!actorId) {
      return null;
    }
    const thread = instance.thread && typeof instance.thread === 'object' ? instance.thread : {};
    const appServer = instance.app_server && typeof instance.app_server === 'object' ? instance.app_server : {};
    const threadStatus = typeof instance.thread_status === 'string'
      ? instance.thread_status
      : (typeof thread.status === 'string' ? thread.status : '');
    const appServerHealth = typeof instance.app_server_health === 'string'
      ? instance.app_server_health
      : (typeof appServer.healthy === 'boolean' ? (appServer.healthy ? 'healthy' : 'unhealthy') : '');
    const role = typeof instance.role === 'string' && instance.role ? instance.role : fallbackRole;
    const runtime = {
      status: instance.status,
      app_server_health: appServerHealth,
      thread_id: instance.thread_id,
      thread_status: threadStatus,
      browser_port: instance.browser_port,
      updated_at: instance.updated_at,
      workspace_dir: instance.workspace_dir,
    };
    return {
      actor_id: actorId,
      role,
      lifecycle_state: instance.lifecycle_state,
      last_failure: instance.last_failure || null,
      status: instance.status,
      app_server_health: appServerHealth,
      thread_id: instance.thread_id,
      browser_port: instance.browser_port,
      updated_at: instance.updated_at,
      workspace_dir: instance.workspace_dir,
      runtime,
    };
  }

  function applyLifecycleOperationInstanceResult(state, operation) {
    const result = operation && operation.result && typeof operation.result === 'object'
      ? operation.result
      : {};
    const instance = result.instance && typeof result.instance === 'object' ? result.instance : null;
    const actorId = lifecycleOperationActorId(operation);
    const existing = actorById(state, actorId);
    const fallbackRole = (existing && existing.role) || lifecycleOperationRoleId(operation);
    const actorRow = runtimeRowFromLifecycleInstance(instance, actorId, fallbackRole);
    if (!actorRow) {
      return;
    }
    const replaced = state.actors.some(function (actor, index) {
      if (actor.actor_id !== actorRow.actor_id) {
        return false;
      }
      state.actors[index] = Object.assign({}, actor, actorRow, {
        role: actorRow.role || actor.role,
        lifecycle_state: actorRow.lifecycle_state || actor.lifecycle_state,
        last_failure: actorRow.last_failure || actor.last_failure || null,
        runtime: Object.assign({}, actor.runtime || {}, actorRow.runtime),
      });
      return true;
    });
    if (!replaced) {
      state.actors = state.actors.concat([actorRow]);
    }
    if (state.selectedActorId === actorRow.actor_id && actorIsStopped(actorRow)) {
      state.rosterStoppedExpanded = true;
    }
    if (state.selectedActorId === actorRow.actor_id && state.actorConsole) {
      state.actorConsole = Object.assign({}, state.actorConsole, {
        actor: Object.assign({}, state.actorConsole.actor || {}, {
          actor_id: actorRow.actor_id,
          role: actorRow.role || (state.actorConsole.actor && state.actorConsole.actor.role),
        }),
        runtime: Object.assign({}, state.actorConsole.runtime || {}, actorRow.runtime),
      });
    }
  }

  function actorRuntimeForId(state, actorId) {
    const actor = actorById(state, actorId);
    const consoleActor = state.actorConsole && state.actorConsole.actor ? state.actorConsole.actor : null;
    const consoleActorId = consoleActor && typeof consoleActor.actor_id === 'string' ? consoleActor.actor_id : '';
    const consoleMatches = Boolean(state.actorConsole && (
      consoleActorId ? consoleActorId === actorId : state.selectedActorId === actorId
    ));
    const consoleRuntime = consoleMatches && state.actorConsole.runtime ? state.actorConsole.runtime : null;
    const runtime = consoleRuntime || (actor && actor.runtime) || actor || null;
    if (!runtime) {
      return null;
    }
    const threadStatus = runtime.thread_status || (runtime.thread && runtime.thread.status) || '';
    return {
      actor_id: actorId,
      role: consoleMatches && consoleActor ? consoleActor.role : actor && actor.role,
      lifecycle_state: actorLifecycleState(actor),
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

  function selectedActorRuntime(state) {
    return actorRuntimeForId(state, state.selectedActorId);
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
    state.imFreshMessageIds = {};
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
    const senderIdentity = message.sender_identity && typeof message.sender_identity === 'object' ? message.sender_identity : {};
    const senderIdentityId = typeof senderIdentity.id === 'string' ? senderIdentity.id : '';
    if (!senderIdentityId) {
      return false;
    }
    const sent = senderIdentityId.indexOf('ext-') === 0;
    return rememberImEntry(state, {
      id: typeof message.id === 'string' ? message.id : '',
      direction: sent ? 'sent' : 'reply',
      sender: sent ? 'you' : identityLabel(senderIdentityId),
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
    const senderIdentity = message.sender_identity && typeof message.sender_identity === 'object' ? message.sender_identity : {};
    const targetIdentity = message.target_identity && typeof message.target_identity === 'object' ? message.target_identity : {};
    return senderIdentity.id === identityId || targetIdentity.id === identityId;
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
    const recorded = recordImProjectedMessage(state, message);
    const senderIdentity = message.sender_identity && typeof message.sender_identity === 'object' ? message.sender_identity : {};
    const senderIdentityId = typeof senderIdentity.id === 'string' ? senderIdentity.id : '';
    const messageId = typeof message.id === 'string' ? message.id : '';
    if (recorded && messageId && senderIdentityId.indexOf('ext-') !== 0) {
      state.imFreshMessageIds[messageId] = true;
    }
    return recorded;
  }

  function resolveStatusTone(value) {
    if (value === 'active' || value === 'healthy' || value === 'idle' || value === 'none') {
      return 'healthy';
    }
    if (value === 'in_progress' || value === 'active_thread' || value === 'active turn' || value === 'blocked'
        || value === 'starting' || value === 'retrying') {
      return 'busy';
    }
    if (value === 'inactive' || value === 'unhealthy' || value === 'stopped' || value === 'interrupted'
        || value === 'start failed') {
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

  function skeletonLine(widthClass) {
    return '<span class="skeleton-line ' + escapeHtml(widthClass || '') + '" aria-hidden="true"></span>';
  }

  function renderMetricSkeletonHtml() {
    return [0, 1, 2, 3].map(function () {
      return '<div class="metric skeleton-card">' + skeletonLine('short') + skeletonLine('medium') + '</div>';
    }).join('');
  }

  function renderSummarySkeletonHtml(rowCount) {
    const count = rowCount || 3;
    return Array.from({ length: count }).map(function () {
      return '<div class="summary-line skeleton-card">' + skeletonLine('short') + skeletonLine('medium') + '</div>';
    }).join('');
  }

  function renderConversationSkeletonHtml() {
    return [
      '<div class="conversation-skeleton" aria-label="Loading direct thread">',
      '<div class="message reply skeleton-card">' + skeletonLine('short') + skeletonLine('long') + '</div>',
      '<div class="message you skeleton-card">' + skeletonLine('short') + skeletonLine('medium') + '</div>',
      '</div>',
    ].join('');
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

  function effectiveActorLifecycleState(state, actor) {
    const operation = activeLifecycleOperationForActor(state, actor && actor.actor_id);
    if (operation && operation.action === 'retry') {
      return 'retrying';
    }
    if (operation && operation.action === 'start') {
      return 'starting';
    }
    return actorLifecycleState(actor);
  }

  function lifecycleStateLabel(lifecycleState) {
    if (lifecycleState === 'start_failed') {
      return 'start failed';
    }
    return lifecycleState || 'unknown';
  }

  function renderActorRowHtml(state, actor) {
    const selected = actor.actor_id === state.selectedActorId;
    const loading = actor.actor_id === state.actorSelectionPendingId;
    const lifecycleOperation = activeLifecycleOperationForActor(state, actor.actor_id);
    const lifecycleState = effectiveActorLifecycleState(state, actor);
    const pending = Boolean(lifecycleOperation || lifecycleState === 'starting' || lifecycleState === 'retrying');
    const startupOnly = ['starting', 'retrying', 'start_failed'].indexOf(lifecycleState) >= 0;
    const runtime = actor.runtime || actor;
    const roleLabel = formatValue(roleLabelById(state, actor.role));
    const initials = actorInitials(actor.role, actor.actor_id);
    const tone = actorVisualTone(runtime);
    const status = lifecycleOperation && lifecycleOperation.action !== 'start' && lifecycleOperation.action !== 'retry'
      ? lifecycleOperationBadgeText(lifecycleOperation)
      : lifecycleStateLabel(lifecycleState);
    const accessibleLabel = roleLabel + ' actor ' + formatValue(actor.actor_id) + ', ' + status + (selected ? ', selected' : '');
    return [
      '<button class="person-row selectable-row actor-row' + (selected ? ' is-selected' : '') + (loading ? ' is-loading' : '') + (pending ? ' is-pending' : '') + '" type="button" data-actor-id="' + escapeHtml(actor.actor_id) + '" role="option" aria-selected="' + selected + '" aria-label="' + escapeHtml(accessibleLabel) + '">',
      '<span class="avatar ' + escapeHtml(tone) + '" aria-hidden="true">' + escapeHtml(initials) + '</span>',
      '<span>',
      '<strong>' + escapeHtml(roleLabel) + '</strong>',
      '<span class="micro mono">' + escapeHtml(formatValue(actor.actor_id)) + '</span>',
      '</span>',
      '<span class="row-status">',
      badge(status, pending ? 'busy' : undefined),
      startupOnly || pending ? '' : badge(runtime.app_server_health),
      startupOnly || pending ? '' : '<span class="' + escapeHtml(actorDotClass(runtime)) + '" aria-hidden="true"></span>',
      '</span>',
      '</button>',
    ].join('');
  }

  function renderRosterGroupHtml(group) {
    const rows = Array.isArray(group.rows) ? group.rows : [];
    const expanded = !group.collapsible || Boolean(group.expanded);
    const heading = group.collapsible
      ? [
          '<button class="roster-group-head roster-group-toggle" type="button" data-roster-toggle="' + escapeHtml(group.key) + '" aria-expanded="' + expanded + '">',
          '<span><span class="roster-group-chevron" aria-hidden="true">›</span>' + escapeHtml(group.title) + '</span>',
          '<span class="roster-group-count">' + rows.length + '</span>',
          '</button>',
        ].join('')
      : [
          '<div class="roster-group-head">',
          '<span>' + escapeHtml(group.title) + '</span>',
          '<span class="roster-group-count">' + rows.length + '</span>',
          '</div>',
        ].join('');
    const rowHtml = expanded
      ? '<div class="roster-group-rows" role="listbox" aria-label="' + escapeHtml(group.title) + '">' + rows.join('') + '</div>'
      : '';
    return '<section class="roster-group" data-roster-group="' + escapeHtml(group.key) + '">' + heading + rowHtml + '</section>';
  }

  function renderActorRowsHtml(state) {
    if (!state.actors.length) {
      return renderEmpty('No actors available.');
    }
    const startingRows = [];
    const activeRows = [];
    const attentionRows = [];
    const stoppedRows = [];
    state.actors.forEach(function (actor) {
      const rowHtml = renderActorRowHtml(state, actor);
      const lifecycleState = effectiveActorLifecycleState(state, actor);
      if (lifecycleState === 'starting' || lifecycleState === 'retrying') {
        startingRows.push(rowHtml);
      } else if (lifecycleState === 'start_failed') {
        attentionRows.push(rowHtml);
      } else if (lifecycleState === 'stopped') {
        stoppedRows.push(rowHtml);
      } else {
        activeRows.push(rowHtml);
      }
    });
    const groups = [];
    if (startingRows.length) {
      groups.push(renderRosterGroupHtml({
        key: 'starting',
        title: 'Starting',
        rows: startingRows,
      }));
    }
    groups.push(renderRosterGroupHtml({
      key: 'active',
      title: 'Active',
      rows: activeRows,
    }));
    if (attentionRows.length) {
      groups.push(renderRosterGroupHtml({
        key: 'needs-attention',
        title: 'Needs attention',
        rows: attentionRows,
      }));
    }
    groups.push(renderRosterGroupHtml({
      key: 'stopped',
      title: 'Stopped',
      rows: stoppedRows,
      collapsible: true,
      expanded: state.rosterStoppedExpanded,
    }));
    return groups.join('');
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

  function selectedStartupActor(state) {
    const actor = actorById(state, state.selectedActorId);
    if (!actor) {
      return null;
    }
    const lifecycleState = effectiveActorLifecycleState(state, actor);
    return ['starting', 'retrying', 'start_failed'].indexOf(lifecycleState) >= 0
      ? Object.assign({}, actor, { lifecycle_state: lifecycleState })
      : null;
  }

  function startupActorNoticeHtml(actor) {
    const lifecycleState = actorLifecycleState(actor);
    if (lifecycleState === 'start_failed') {
      const failure = actor && actor.last_failure && typeof actor.last_failure === 'object'
        ? actor.last_failure
        : {};
      const message = typeof failure.message === 'string' && failure.message
        ? failure.message
        : 'The actor did not finish starting.';
      return '<div class="empty-state"><strong>Start failed</strong><span>' + escapeHtml(message) + '</span></div>';
    }
    if (lifecycleState === 'retrying') {
      return '<div class="empty-state"><strong>Retrying actor</strong><span>A fresh actor is starting with the same role.</span></div>';
    }
    return '<div class="empty-state"><strong>Starting actor</strong><span>Runtime details will appear when startup completes.</span></div>';
  }

  function renderRuntimeDetailHtml(state) {
    if (state.actorCardLoading && !state.actorConsole) {
      return renderMetricSkeletonHtml();
    }
    if (state.actorCardError) {
      return renderEmpty(state.actorCardError);
    }
    const startupActor = selectedStartupActor(state);
    if (startupActor) {
      return startupActorNoticeHtml(startupActor);
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
    if (state.actorCardLoading && !state.actorConsole) {
      return renderSummarySkeletonHtml(4);
    }
    if (state.actorCardError) {
      return renderEmpty(state.actorCardError);
    }
    const startupActor = selectedStartupActor(state);
    if (startupActor) {
      return startupActorNoticeHtml(startupActor);
    }
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

  function formatTaskLedgerTime(value) {
    if (typeof value !== 'string' || !value) {
      return '—';
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return '—';
    }
    return parsed.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
  }

  function renderTaskLedgerRowHtml(task, options) {
    const current = options && options.current === true;
    const attention = options && options.attention === true;
    const rowClasses = ['task-ledger-row'];
    if (current) {
      rowClasses.push('is-current');
    }
    if (attention) {
      rowClasses.push('needs-attention');
    }
    const status = task && task.status ? String(task.status) : 'unknown';
    const context = current
      ? (attention ? 'Needs attention · ' : 'Now · ') + status
      : status;
    const taskId = task && task.task_id ? String(task.task_id) : '—';
    const updatedAt = task && task.updated_at ? String(task.updated_at) : '—';
    const open = Boolean(options && options.visible && options.openTaskId === taskId);
    return [
      '<details class="task-ledger-row-detail" name="actor-task-row-detail" data-task-ledger-task-id="' + escapeHtml(taskId) + '"' + (open ? ' open' : '') + '>',
      '<summary class="' + rowClasses.join(' ') + '" data-task-ledger-task-id="' + escapeHtml(taskId) + '" aria-expanded="' + String(open) + '">',
      '<span class="task-ledger-row-copy">',
      '<strong>' + escapeHtml(task && task.source_type ? task.source_type : 'Task') + '</strong>',
      '<span>' + escapeHtml(context) + '</span>',
      '</span>',
      '<time class="task-ledger-short-time" datetime="' + escapeHtml(updatedAt) + '">' + escapeHtml(formatTaskLedgerTime(updatedAt)) + '</time>',
      '</summary>',
      '<div class="task-ledger-detail">',
      '<span>Task ID</span><code>' + escapeHtml(taskId) + '</code>',
      '<span>Updated</span><time datetime="' + escapeHtml(updatedAt) + '">' + escapeHtml(updatedAt) + '</time>',
      '</div>',
      '</details>',
    ].join('');
  }

  function renderTaskLedgerRecentHtml(terminalTasks, state) {
    if (!terminalTasks.length) {
      return '';
    }
    const expanded = state.actorTaskRecentExpanded === true;
    const collapsedRows = terminalTasks.slice(0, 2).map(function (task) {
      return renderTaskLedgerRowHtml(task, {
        current: false,
        attention: false,
        visible: !expanded,
        openTaskId: state.actorTaskOpenId,
      });
    }).join('');
    const expandedRows = terminalTasks.map(function (task) {
      return renderTaskLedgerRowHtml(task, {
        current: false,
        attention: false,
        visible: expanded,
        openTaskId: state.actorTaskOpenId,
      });
    }).join('');
    const collapsedCount = Math.min(2, terminalTasks.length);
    return [
      '<div class="task-ledger-recent">',
      '<details class="task-ledger-recent-disclosure"' + (expanded ? ' open' : '') + '>',
      '<summary class="task-ledger-recent-toggle" data-task-ledger-recent-toggle aria-expanded="' + String(expanded) + '">',
      '<span>Recent</span>',
      '<span class="task-ledger-recent-show">' + escapeHtml(String(collapsedCount)) + ' of ' + escapeHtml(String(terminalTasks.length)) + ' · Show all</span>',
      '<span class="task-ledger-recent-hide">' + escapeHtml(String(terminalTasks.length)) + ' of ' + escapeHtml(String(terminalTasks.length)) + ' · Show fewer</span>',
      '</summary>',
      '<div class="task-ledger-recent-expanded">' + expandedRows + '</div>',
      '</details>',
      '<div class="task-ledger-recent-collapsed">' + collapsedRows + '</div>',
      '</div>',
    ].join('');
  }

  function renderTaskSummaryHtml(state) {
    if (state.actorCardLoading && !state.actorConsole) {
      return renderSummarySkeletonHtml(3);
    }
    if (state.actorCardError) {
      return renderEmpty(state.actorCardError);
    }
    const startupActor = selectedStartupActor(state);
    if (startupActor) {
      return renderEmpty(actorLifecycleState(startupActor) === 'start_failed'
        ? 'Tasks are unavailable because startup failed.'
        : 'Tasks will appear after startup completes.');
    }
    const taskSys = state.actorConsole && state.actorConsole.task_sys ? state.actorConsole.task_sys : null;
    if (!taskSys) {
      return renderEmpty('No Task Sys state loaded.');
    }
    if (
      !Array.isArray(taskSys.active_tasks)
      || !Array.isArray(taskSys.recoverable_tasks)
      || !Array.isArray(taskSys.terminal_tasks)
      || typeof taskSys.active_count !== 'number'
      || typeof taskSys.terminal_count !== 'number'
    ) {
      return renderEmpty('Task Sys response is missing required fields.');
    }
    const current = taskSys.recoverable_tasks[0] || taskSys.active_tasks[0] || null;
    const attention = taskSys.recoverable_tasks.length > 0;
    const terminalTasks = taskSys.terminal_tasks;
    const countHtml = '<span class="task-ledger-count">' + escapeHtml(String(taskSys.active_count)) + ' active · ' + escapeHtml(String(taskSys.terminal_count)) + ' recent</span>';
    if (!current && !terminalTasks.length) {
      return countHtml + '<div class="task-ledger-empty"><strong>No tasks yet</strong><span>Completed work will appear here</span></div>';
    }
    const currentHtml = current
      ? renderTaskLedgerRowHtml(current, {
        current: true,
        attention,
        visible: true,
        openTaskId: state.actorTaskOpenId,
      })
      : '<div class="task-ledger-idle"><strong>No active task</strong><span>Recent stays visible</span></div>';
    return [
      countHtml,
      currentHtml,
      renderTaskLedgerRecentHtml(terminalTasks, state),
    ].join('');
  }

  function renderActorTrackSummaryHtml(state) {
    if (state.actorCardLoading && !state.actorConsole) {
      return renderSummarySkeletonHtml(3);
    }
    if (state.actorCardError) {
      return renderEmpty(state.actorCardError);
    }
    const startupActor = selectedStartupActor(state);
    if (startupActor) {
      return renderEmpty(actorLifecycleState(startupActor) === 'start_failed'
        ? 'Tracks are unavailable because startup failed.'
        : 'Tracks will appear after startup completes.');
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

  function isConversationNearBottom(thread) {
    if (!thread || typeof thread.scrollHeight !== 'number' || typeof thread.scrollTop !== 'number' || typeof thread.clientHeight !== 'number') {
      return true;
    }
    return thread.scrollHeight - thread.scrollTop - thread.clientHeight <= 36;
  }

  function hideNewReplyChip(elements) {
    if (!elements || !elements.newReplyChip) {
      return;
    }
    elements.newReplyChip.hidden = true;
    if (elements.newReplyChip.classList && elements.newReplyChip.classList.remove) {
      elements.newReplyChip.classList.remove('is-chip-pop');
    }
  }

  function showNewReplyChip(elements) {
    if (!elements || !elements.newReplyChip) {
      return;
    }
    elements.newReplyChip.hidden = false;
    if (elements.newReplyChip.classList && elements.newReplyChip.classList.remove && elements.newReplyChip.classList.add) {
      elements.newReplyChip.classList.remove('is-chip-pop');
      void elements.newReplyChip.offsetWidth;
      elements.newReplyChip.classList.add('is-chip-pop');
    }
  }

  function scrollConversationToBottom(elements) {
    const thread = elements && elements.roomThread ? elements.roomThread : null;
    if (!thread) {
      return;
    }
    if (typeof thread.scrollTo === 'function') {
      thread.scrollTo({ top: thread.scrollHeight, behavior: 'smooth' });
      return;
    }
    thread.scrollTop = thread.scrollHeight;
  }

  function renderMessageMetaHtml(meta, entry) {
    const marker = entry.direction === 'sent'
      ? ''
      : '<span class="reply-mark" aria-hidden="true"></span>';
    return '<span class="meta">' + marker + escapeHtml(meta) + '</span>';
  }

  function renderImConversation(state, elements) {
    if (!elements.imConversation) {
      return;
    }
    setRegionBusy(elements.imConversation, state.conversationLoading);
    if (state.conversationLoading && !state.imConversation.length) {
      elements.imConversation.innerHTML = renderConversationSkeletonHtml();
      hideNewReplyChip(elements);
      return;
    }
    if (state.conversationError) {
      elements.imConversation.innerHTML = renderEmpty(state.conversationError);
      hideNewReplyChip(elements);
      return;
    }
    if (!state.imConversation.length) {
      elements.imConversation.innerHTML = state.selectedActorId
        ? renderEmpty('No direct messages yet.')
        : renderEmpty('Select a teammate to load the direct thread.');
      hideNewReplyChip(elements);
      return;
    }
    const wasNearBottom = isConversationNearBottom(elements.roomThread);
    const freshIdsToClear = [];
    let hasFreshReply = false;
    elements.imConversation.innerHTML = state.imConversation.map(function (entry) {
      const status = [entry.deliveryStatus, entry.wakeStatus].filter(Boolean).join(' / ');
      const classes = ['message', entry.direction === 'sent' ? 'you' : 'reply'];
      if (entry.deliveryStatus === 'sending') {
        classes.push('pending');
      } else if (entry.deliveryStatus === 'failed') {
        classes.push('failed');
      }
      if (entry.direction !== 'sent' && state.imFreshMessageIds && state.imFreshMessageIds[entry.id]) {
        classes.push('is-new');
        freshIdsToClear.push(entry.id);
        hasFreshReply = true;
      }
      const meta = [
        entry.direction === 'sent' ? 'sent' : 'reply',
        entry.sender,
        status,
        entry.replyTo ? 'reply_to ' + entry.replyTo : '',
      ].filter(Boolean).join(' · ');
      return [
        '<div class="' + classes.join(' ') + '">',
        renderMessageMetaHtml(meta, entry),
        '<div class="markdown-body">' + renderMessageContentHtml(entry.content) + '</div>',
        '</div>',
      ].join('');
    }).join('');
    freshIdsToClear.forEach(function (messageId) {
      delete state.imFreshMessageIds[messageId];
    });
    if (hasFreshReply) {
      if (wasNearBottom) {
        hideNewReplyChip(elements);
        scrollConversationToBottom(elements);
      } else {
        showNewReplyChip(elements);
      }
    } else if (isConversationNearBottom(elements.roomThread)) {
      hideNewReplyChip(elements);
    }
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

  function setRegionBusy(element, busy) {
    if (!element || !element.setAttribute) {
      return;
    }
    if (busy) {
      element.setAttribute('aria-busy', 'true');
    } else {
      element.removeAttribute('aria-busy');
    }
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
    });
    elements.createButton.textContent = 'Start';
    elements.createButton.classList.toggle('is-pending', false);
  }

  function roleSelectExpectedOptions(state) {
    return [{ value: '', text: 'Select role' }].concat(state.roles.map(function (role) {
      return {
        value: role.id,
        text: role.label + ' (' + role.id + ')',
      };
    }));
  }

  function roleSelectMatchesExpected(element, expectedOptions) {
    if (!element || !element.options || element.options.length !== expectedOptions.length) {
      return false;
    }
    return expectedOptions.every(function (expected, index) {
      const option = element.options[index];
      return option && option.value === expected.value && option.textContent === expected.text;
    });
  }

  function clearRoleSelectOptions(element) {
    if (!element || !element.options) {
      return;
    }
    while (element.options.length > 0) {
      if (typeof element.remove === 'function') {
        element.remove(0);
      } else if (typeof element.options.splice === 'function') {
        element.options.splice(0, 1);
      } else {
        element.options.length = 0;
      }
    }
  }

  function renderRoleSelect(state, elements) {
    const expectedOptions = roleSelectExpectedOptions(state);
    if (!roleSelectMatchesExpected(elements.roleSelect, expectedOptions)) {
      clearRoleSelectOptions(elements.roleSelect);
      expectedOptions.forEach(function (expected) {
        const option = document.createElement('option');
        option.value = expected.value;
        option.textContent = expected.text;
        elements.roleSelect.appendChild(option);
      });
    }
    elements.roleSelect.value = state.selectedRole;
  }

  function renderActorList(state, elements) {
    setRegionBusy(elements.actorsList, state.rosterLoading);
    elements.actorsList.innerHTML = renderActorRowsHtml(state);
  }

  function capabilityCatalogRow(state, level) {
    return state.actorCapabilityCatalog.find(function (row) {
      return row && row.id === level;
    }) || null;
  }

  function capabilityLabel(state, level) {
    const row = capabilityCatalogRow(state, level);
    return row && typeof row.label === 'string' ? row.label : 'Not set';
  }

  function renderCapabilityMatrixHtml(state) {
    return state.actorCapabilityCatalog.map(function (row) {
      const parentSelected = state.actorCapabilityDraft.parent === row.id;
      const sideSelected = state.actorCapabilityDraft.side === row.id;
      function cell(role, selected) {
        return [
          '<label data-capability-role="' + role + '" data-capability-level="' + escapeHtml(row.id) + '" class="capability-choice' + (selected ? ' is-selected' : '') + '">',
          '<input type="radio" name="capability-' + role + '" value="' + escapeHtml(row.id) + '"' + (selected ? ' checked' : '') + '>',
          '<span class="sr-only">' + escapeHtml(role + ' ' + row.label) + '</span>',
          '</label>',
        ].join('');
      }
      return [
        '<div class="capability-matrix-row">',
        '<div class="capability-level-copy"><strong>' + escapeHtml(row.label || row.id) + '</strong><span>' + escapeHtml(row.description || '') + '</span></div>',
        cell('parent', parentSelected),
        cell('side', sideSelected),
        '</div>',
      ].join('');
    }).join('');
  }

  function renderCapabilityDetailsHtml(state) {
    function row(role, level) {
      const roleId = role.toLowerCase();
      const savedSection = state.actorConsole && state.actorConsole.capabilities
        ? state.actorConsole.capabilities[roleId]
        : null;
      const usesSavedSnapshot = state.actorCapabilitySaved[roleId] === level;
      const selection = usesSavedSnapshot && savedSection ? savedSection : capabilityCatalogRow(state, level);
      return [
        '<div class="capability-detail-row">',
        '<span>' + escapeHtml(role) + '</span>',
        '<strong>' + escapeHtml(selection && selection.model ? selection.model : 'Not set') + '</strong>',
        '<span>' + escapeHtml(selection && selection.effort ? selection.effort : 'Not set') + '</span>',
        '</div>',
      ].join('');
    }
    return row('Parent', state.actorCapabilityDraft.parent)
      + row('Side', state.actorCapabilityDraft.side);
  }

  function renderActorCapabilities(state, elements) {
    if (!elements.actorCapabilityCard) {
      return;
    }
    if (state.actorCapabilityActorId !== state.selectedActorId) {
      syncActorCapabilitiesFromConsole(state, { force: true });
    }
    const editorAvailable = Boolean(
      state.selectedActorId
      && state.actorCapabilityActorId === state.selectedActorId
      && state.actorCapabilityCatalog.length === 4
    );
    if (!editorAvailable) {
      state.actorCapabilityPanelOpen = false;
    }
    const dirty = !sameCapabilitySelection(state.actorCapabilityDraft, state.actorCapabilitySaved);
    const errorMessage = state.actorCapabilityError;
    const message = errorMessage || state.actorCapabilityStatus;
    elements.actorCapabilityParentSummary.textContent = capabilityLabel(state, state.actorCapabilitySaved.parent);
    elements.actorCapabilitySideSummary.textContent = capabilityLabel(state, state.actorCapabilitySaved.side);
    elements.actorCapabilityPanel.hidden = !state.actorCapabilityPanelOpen;
    if (!state.actorCapabilityPanelOpen && elements.actorCapabilityDetails.parentElement) {
      elements.actorCapabilityDetails.parentElement.open = false;
    }
    elements.actorCapabilityMatrix.innerHTML = renderCapabilityMatrixHtml(state);
    elements.actorCapabilityDetails.innerHTML = renderCapabilityDetailsHtml(state);
    elements.actorCapabilitySave.disabled = !editorAvailable || !dirty || state.actorCapabilitySaving;
    elements.actorCapabilityCancel.disabled = !editorAvailable || state.actorCapabilitySaving;
    elements.actorCapabilitySave.textContent = state.actorCapabilitySaving ? 'Saving...' : 'Save config';
    elements.actorCapabilityStatus.textContent = !editorAvailable
      ? 'Unavailable'
      : (errorMessage ? 'Error' : (dirty ? 'Unsaved' : 'Saved'));
    elements.actorCapabilityStatus.className = 'status-badge ' + (
      !editorAvailable ? 'neutral' : (errorMessage ? 'danger' : (dirty ? 'busy' : 'healthy'))
    );
    elements.actorCapabilityToggle.disabled = !editorAvailable;
    elements.actorCapabilityToggle.textContent = state.actorCapabilityPanelOpen ? 'Close' : 'Configure';
    elements.actorCapabilityToggle.setAttribute('aria-expanded', state.actorCapabilityPanelOpen ? 'true' : 'false');
    elements.actorCapabilityMessage.textContent = message || '';
    elements.actorCapabilityMessage.hidden = !state.actorCapabilityPanelOpen || !message;
  }

  function renderActorDetail(state, elements) {
    setRegionBusy(elements.actorRuntimeDetail, state.actorCardLoading);
    setRegionBusy(elements.actorRuntimeSummary, state.actorCardLoading);
    setRegionBusy(elements.actorTaskSummary, state.actorCardLoading);
    setRegionBusy(elements.actorTrackSummary, state.actorCardLoading);
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
    renderActorCapabilities(state, elements);
  }

  function renderTrackList(state, elements) {
    setRegionBusy(elements.tracksList, state.tracksListLoading);
    elements.tracksList.innerHTML = renderTrackRowsHtml(state);
  }

  function renderTrackDetail(state, elements) {
    setRegionBusy(elements.trackDetail, state.selectedTrackDetailLoading);
    elements.trackDetail.innerHTML = state.trackSelectionPendingId && state.trackSelectionPendingId === state.selectedTrackId
      ? '<div class="empty-state inline-loading">Loading Track...</div>'
      : renderTrackDetailHtml(state.selectedTrackDetail);
  }

  function renderTrackStudioRail(state, elements) {
    if (!elements.trackStudioRail) {
      return;
    }
    setRegionBusy(elements.trackStudioRail, state.selectedTrackDetailLoading);
    elements.trackStudioRail.innerHTML = state.trackSelectionPendingId && state.trackSelectionPendingId === state.selectedTrackId
      ? '<div class="empty-state inline-loading">Loading Track context...</div>'
      : renderTrackStudioRailHtml(state.selectedTrackDetail);
  }

  function renderSelectedActorContext(state, elements) {
    const runtime = selectedActorRuntime(state);
    const lifecycleOperation = activeLifecycleOperationForActor(state, state.selectedActorId);
    const selectedActor = actorById(state, state.selectedActorId);
    const roleId = (runtime && runtime.role) || (selectedActor && selectedActor.role) || lifecycleOperationRoleId(lifecycleOperation);
    const hasActor = Boolean(state.selectedActorId && selectedActor);
    const roleLabel = roleId ? formatValue(roleLabelById(state, roleId)) : 'Direct thread';
    const contextId = hasActor ? state.selectedActorId : 'No teammate selected';
    const lifecycleValue = !hasActor
      ? ''
      : (lifecycleOperation && !['start', 'retry'].includes(lifecycleOperation.action)
          ? lifecycleOperationBadgeText(lifecycleOperation)
          : lifecycleStateLabel(effectiveActorLifecycleState(state, selectedActor)));
    const healthValue = hasActor && selectedActor && !actorIsStartupOnly(selectedActor) && runtime && runtime.app_server_health
      ? formatValue(runtime.app_server_health)
      : '';
    const initials = actorInitials(roleId, state.selectedActorId);

    elements.selectedContextAvatar.textContent = initials;
    elements.selectedContextAvatar.className = 'avatar ' + (hasActor ? actorVisualTone(runtime) : 'teal');
    elements.selectedContextAvatar.hidden = !hasActor;
    elements.selectedContextRole.textContent = roleLabel;
    elements.selectedContextId.textContent = contextId;
    elements.selectedContextRuntime.textContent = lifecycleValue;
    elements.selectedContextRuntime.className = 'status-badge ' + (lifecycleOperation ? 'busy' : resolveStatusTone(lifecycleValue));
    elements.selectedContextRuntime.hidden = !lifecycleValue;
    elements.selectedContextHealth.textContent = healthValue;
    elements.selectedContextHealth.className = 'status-badge ' + resolveStatusTone(healthValue);
    elements.selectedContextHealth.hidden = !healthValue;

    const actionState = describeInstanceActionState(runtime, {
      draftText: state.draftText,
      sendPending: state.sendPending,
      lifecycleOperation,
      interruptPending: state.interruptPending,
    });
    elements.stopButton.disabled = !actionState.canStop;
    elements.stopButton.hidden = !hasActor || actorLifecycleState(selectedActor) !== 'active';
    elements.stopButton.textContent = lifecycleOperation && lifecycleOperation.action === 'stop' ? 'Stopping...' : 'Stop';
    elements.stopButton.classList.toggle('is-pending', Boolean(lifecycleOperation && lifecycleOperation.action === 'stop'));
    elements.stopButton.setAttribute('aria-label', hasActor ? 'Stop actor ' + state.selectedActorId : 'Stop selected actor');
    elements.deleteButton.disabled = !actionState.canDelete;
    elements.deleteButton.hidden = !hasActor;
    elements.deleteButton.textContent = lifecycleOperation && lifecycleOperation.action === 'delete' ? 'Deleting...' : 'Delete';
    elements.deleteButton.classList.toggle('is-pending', Boolean(lifecycleOperation && lifecycleOperation.action === 'delete'));
    elements.deleteButton.setAttribute('aria-label', hasActor ? 'Delete actor ' + state.selectedActorId : 'Delete selected actor');
    elements.clearButton.disabled = !actionState.canClear;
    elements.clearButton.textContent = lifecycleOperation && lifecycleOperation.action === 'clear' ? 'Clearing...' : 'Clear';
    elements.clearButton.classList.toggle('is-pending', Boolean(lifecycleOperation && lifecycleOperation.action === 'clear'));
    elements.resumeButton.disabled = !actionState.canResume;
    elements.resumeButton.hidden = !hasActor || actorLifecycleState(selectedActor) !== 'stopped';
    elements.resumeButton.textContent = lifecycleOperation && lifecycleOperation.action === 'resume' ? 'Resuming...' : 'Resume';
    elements.resumeButton.classList.toggle('is-pending', Boolean(lifecycleOperation && lifecycleOperation.action === 'resume'));
    elements.resumeButton.setAttribute('aria-label', hasActor ? 'Resume actor ' + state.selectedActorId : 'Resume selected actor');
    elements.retryButton.disabled = !actionState.canRetry;
    elements.retryButton.hidden = !hasActor || actorLifecycleState(selectedActor) !== 'start_failed';
    elements.retryButton.textContent = lifecycleOperation && lifecycleOperation.action === 'retry' ? 'Retrying...' : 'Retry';
    elements.retryButton.classList.toggle('is-pending', Boolean(lifecycleOperation && lifecycleOperation.action === 'retry'));
    elements.retryButton.setAttribute('aria-label', hasActor ? 'Retry actor ' + state.selectedActorId : 'Retry selected actor');
    if (elements.lifecycleOperationStatus) {
      elements.lifecycleOperationStatus.textContent = actionState.lifecycleStatus;
    }
    elements.actionAvailabilityStatus.textContent = actionState.lifecycleProtectionStatus
      ? actionState.lifecycleProtectionStatus
      : !actionState.canClear && actionState.clearReason
      ? 'Clear disabled: ' + actionState.clearReason
      : '';
  }

  function renderComposer(state, elements) {
    elements.instructionInput.value = state.draftText;
    const runtime = selectedActorRuntime(state);
    const lifecycleOperation = activeLifecycleOperationForActor(state, state.selectedActorId);
    const actionState = describeInstanceActionState(runtime, {
      draftText: state.draftText,
      sendPending: state.sendPending,
      lifecycleOperation,
      interruptPending: state.interruptPending,
    });
    elements.sendButton.disabled = !actionState.canSend;
    elements.sendButton.textContent = state.sendPending ? 'Sending...' : 'Send';
    elements.sendButton.classList.toggle('is-pending', state.sendPending);
    elements.interruptButton.disabled = !actionState.canInterrupt;
    elements.interruptButton.textContent = state.interruptPending ? 'Interrupting...' : 'Interrupt';
    elements.interruptButton.classList.toggle('is-pending', state.interruptPending);
  }

  function renderActorInteractionRegions(state, elements) {
    renderSelectedActorContext(state, elements);
    return renderComposer(state, elements);
  }

  function deleteConfirmationMatches(state) {
    return Boolean(
      state
      && state.deleteConfirmationActorId
      && state.deleteConfirmationInput === state.deleteConfirmationActorId
    );
  }

  function renderDeleteConfirmation(state, elements) {
    const actorId = state.deleteConfirmationActorId;
    const actor = actorById(state, actorId);
    const runtime = actor && (actor.runtime || actor);
    const lifecycleOperation = activeLifecycleOperationForActor(state, actorId);
    const open = Boolean(actorId && actor);
    elements.deleteConfirmationBackdrop.hidden = !open;
    elements.deleteConfirmationTarget.textContent = open ? actorId : '';
    elements.deleteConfirmationRole.textContent = open
      ? formatValue(roleLabelById(state, actor.role))
      : '';
    elements.deleteConfirmationState.textContent = open
      ? formatValue(runtime && runtime.status)
      : '';
    elements.deleteConfirmationLabel.textContent = open
      ? 'Type ' + actorId + ' to confirm'
      : 'Type the actor id to confirm';
    elements.deleteConfirmationInput.value = state.deleteConfirmationInput;
    elements.deleteConfirmationConfirm.disabled = !open
      || !deleteConfirmationMatches(state)
      || Boolean(lifecycleOperation)
      || !lifecycleActionAllowed(state, 'delete', actorId);
  }

  function openDeleteConfirmation(state, elements, trigger) {
    const actorId = state.selectedActorId;
    const runtime = selectedActorRuntime(state);
    const lifecycleOperation = activeLifecycleOperationForActor(state, actorId);
    const actionState = computeInstanceActionState(runtime, {
      draftText: state.draftText,
      sendPending: state.sendPending,
      lifecycleOperation,
      interruptPending: state.interruptPending,
    });
    if (!actorId || !actorById(state, actorId) || !actionState.canDelete) {
      renderDeleteConfirmation(state, elements);
      return;
    }
    state.deleteConfirmationActorId = actorId;
    state.deleteConfirmationInput = '';
    state.deleteConfirmationTrigger = trigger || elements.deleteButton || null;
    renderDeleteConfirmation(state, elements);
    if (elements.deleteConfirmationInput && typeof elements.deleteConfirmationInput.focus === 'function') {
      elements.deleteConfirmationInput.focus();
    }
  }

  function closeDeleteConfirmation(state, elements, options) {
    const trigger = state.deleteConfirmationTrigger;
    const restoreFocus = !options || options.restoreFocus !== false;
    state.deleteConfirmationActorId = '';
    state.deleteConfirmationInput = '';
    state.deleteConfirmationTrigger = null;
    renderDeleteConfirmation(state, elements);
    if (restoreFocus && trigger && typeof trigger.focus === 'function') {
      trigger.focus();
    }
  }

  function updateDeleteConfirmationInput(state, elements, value) {
    state.deleteConfirmationInput = typeof value === 'string' ? value : '';
    renderDeleteConfirmation(state, elements);
  }

  async function confirmDelete(state, elements) {
    const actorId = state.deleteConfirmationActorId;
    if (!deleteConfirmationMatches(state)
      || !actorById(state, actorId)
      || !lifecycleActionAllowed(state, 'delete', actorId)) {
      renderDeleteConfirmation(state, elements);
      return;
    }
    closeDeleteConfirmation(state, elements, { restoreFocus: false });
    await runLifecycleAction(state, elements, 'delete', actorId);
  }

  function renderAttachTools(state, elements) {
    const runtime = selectedActorRuntime(state);
    const attachState = computeAttachActionState(runtime);
    elements.openTuiButton.disabled = !attachState.canAttach || state.openTuiPending;
    elements.openTuiButton.textContent = state.openTuiPending ? 'Opening...' : 'Open TUI';
    elements.openTuiButton.classList.toggle('is-pending', state.openTuiPending);
    elements.openTuiStatus.textContent = state.openTuiPending
      ? 'Opening...'
      : (attachState.canAttach ? state.openTuiMessage : attachState.message);
    elements.copyCommandButton.disabled = !attachState.canAttach || state.copyCommandPending;
    elements.copyCommandButton.textContent = state.copyCommandPending ? 'Copying...' : 'Copy command';
    elements.copyCommandButton.classList.toggle('is-pending', state.copyCommandPending);
    elements.copyCommandStatus.textContent = state.copyCommandPending
      ? 'Copying...'
      : (attachState.canAttach ? state.copyCommandMessage : attachState.message);
  }

  function renderVisibleRegions(state, elements) {
    renderShell(state, elements);
    renderRoleSelect(state, elements);
    renderActorList(state, elements);
    renderActorDetail(state, elements);
    renderTrackList(state, elements);
    renderTrackDetail(state, elements);
    renderTrackStudioRail(state, elements);
    renderActorInteractionRegions(state, elements);
    renderAttachTools(state, elements);
    renderImConversation(state, elements);
    renderDeleteConfirmation(state, elements);
  }

  async function refreshAppBasics(state, elements) {
    state.appBasicsLoading = true;
    state.appBasicsError = '';
    renderShell(state, elements);
    try {
      const [healthPayload, rolesPayload] = await Promise.all([
        fetchJson('/api/health'),
        fetchJson('/api/roles'),
      ]);
      state.healthOk = Boolean(healthPayload.ok);
      state.roles = rolesPayload.roles || [];
      if (!state.selectedRole && state.roles.length > 0) {
        state.selectedRole = state.roles[0].id;
      }
    } catch (error) {
      state.appBasicsError = error.message;
      state.message = error.message;
      throw error;
    } finally {
      state.appBasicsLoading = false;
      renderShell(state, elements);
      renderRoleSelect(state, elements);
    }
  }

  async function refreshRoster(state, elements) {
    state.rosterLoading = true;
    state.rosterError = '';
    renderActorList(state, elements);
    try {
      const payload = await fetchJson('/api/actors');
      const reconciliation = applyActorsPayload(state, payload);
      scheduleLifecycleOperationPolling(state, elements);
      return reconciliation;
    } catch (error) {
      state.rosterError = error.message;
      state.message = error.message;
      throw error;
    } finally {
      state.rosterLoading = false;
      renderShell(state, elements);
      renderActorList(state, elements);
    }
  }

  async function reconcileActorSelectionAfterRoster(state, elements, reconciliation) {
    if (reconciliation.selectedActorPresent) {
      return false;
    }
    if (reconciliation.replacementActorId) {
      await loadActorSelection(state, elements, reconciliation.replacementActorId);
      return true;
    }
    if (reconciliation.preferredActorId) {
      if (actorIsStopped(actorById(state, reconciliation.preferredActorId))) {
        state.rosterStoppedExpanded = true;
      }
      await loadActorSelection(state, elements, reconciliation.preferredActorId);
      return true;
    }
    if (state.selectedActorId || state.actorConsole || state.imConversationIdentityId) {
      await loadActorSelection(state, elements, '');
      return true;
    }
    return false;
  }

  async function refreshTracksList(state, elements) {
    state.tracksListLoading = true;
    state.tracksError = '';
    renderTrackList(state, elements);
    try {
      const payload = await fetchJson('/api/tracks');
      applyTracksPayload(state, payload);
    } catch (error) {
      state.tracksError = error.message;
      state.message = error.message;
      throw error;
    } finally {
      state.tracksListLoading = false;
      renderShell(state, elements);
      renderTrackList(state, elements);
    }
  }

  function isCurrentActorRequest(state, actorId, requestId) {
    return state.actorSelectionRequestId === requestId && state.selectedActorId === actorId;
  }

  function isCurrentActorConsoleRequest(state, actorId, selectionRequestId, consoleRequestId) {
    return isCurrentActorRequest(state, actorId, selectionRequestId)
      && state.actorConsoleRequestId === consoleRequestId;
  }

  function abortActorSelectionRequests(state) {
    if (state.actorConsoleAbortController) {
      state.actorConsoleAbortController.abort();
    }
    if (state.actorConversationAbortController) {
      state.actorConversationAbortController.abort();
    }
    state.actorConsoleAbortController = null;
    state.actorConversationAbortController = null;
  }

  function renderActorSelectionRegions(state, elements) {
    renderShell(state, elements);
    renderActorList(state, elements);
    renderActorDetail(state, elements);
    renderActorInteractionRegions(state, elements);
    renderAttachTools(state, elements);
    renderImConversation(state, elements);
  }

  function beginActorSelection(state, actorId) {
    abortActorSelectionRequests(state);
    const selectedActorId = actorId || '';
    const requestId = state.actorSelectionRequestId + 1;
    const consoleAbortController = selectedActorId ? createAbortController() : null;
    const conversationAbortController = selectedActorId ? createAbortController() : null;
    state.actorSelectionRequestId = requestId;
    state.actorConsoleRequestId += 1;
    state.selectedActorId = selectedActorId;
    state.actorConsole = null;
    state.actorTaskRecentExpanded = false;
    state.actorTaskOpenId = '';
    syncActorCapabilitiesFromConsole(state, { force: true });
    state.actorSelectionPendingId = selectedActorId;
    state.actorCardLoading = Boolean(selectedActorId);
    state.actorCardError = '';
    state.conversationLoading = Boolean(selectedActorId);
    state.conversationError = '';
    state.actorConsoleAbortController = consoleAbortController;
    state.actorConversationAbortController = conversationAbortController;
    clearImConversation(state, selectedActorId);
    state.sendPending = false;
    state.interruptPending = false;
    state.openTuiPending = false;
    state.copyCommandPending = false;
    clearAttachToolFeedback(state);
    return {
      actorId: selectedActorId,
      requestId,
      consoleAbortController,
      conversationAbortController,
    };
  }

  function settleActorSelection(state, elements, selection) {
    if (state.actorConsoleAbortController === selection.consoleAbortController) {
      state.actorConsoleAbortController = null;
    }
    if (state.actorConversationAbortController === selection.conversationAbortController) {
      state.actorConversationAbortController = null;
    }
    if (!isCurrentActorRequest(state, selection.actorId, selection.requestId)) {
      return false;
    }
    state.actorSelectionPendingId = '';
    state.actorCardLoading = false;
    state.conversationLoading = false;
    renderActorSelectionRegions(state, elements);
    scheduleActorConsoleRefresh(state, elements);
    return true;
  }

  async function refreshActorCard(state, elements, actorId, requestId, options) {
    if (!actorId) {
      state.actorConsole = null;
      syncActorCapabilitiesFromConsole(state, { force: true });
      state.actorCardLoading = false;
      state.actorCardError = '';
      renderActorDetail(state, elements);
      renderActorInteractionRegions(state, elements);
      renderAttachTools(state, elements);
      return;
    }
    const consoleRequestId = state.actorConsoleRequestId + 1;
    state.actorConsoleRequestId = consoleRequestId;
    state.actorCardLoading = true;
    state.actorCardError = '';
    renderActorDetail(state, elements);
    renderActorInteractionRegions(state, elements);
    renderAttachTools(state, elements);
    try {
      const payload = await fetchJson(buildActorConsoleUrl(actorId), options || undefined);
      const consoleActorId = payload
        && payload.console
        && payload.console.actor
        && typeof payload.console.actor.actor_id === 'string'
        ? payload.console.actor.actor_id
        : '';
      if (!isCurrentActorConsoleRequest(state, actorId, requestId, consoleRequestId)
          || (consoleActorId && consoleActorId !== actorId)) {
        return;
      }
      applyActorConsolePayload(state, payload);
      if (!isCurrentActorConsoleRequest(state, actorId, requestId, consoleRequestId)) {
        return;
      }
      state.actorCardLoading = false;
      state.actorCardError = '';
      renderActorDetail(state, elements);
      renderActorInteractionRegions(state, elements);
      renderAttachTools(state, elements);
    } catch (error) {
      if (isAbortError(error) || !isCurrentActorConsoleRequest(state, actorId, requestId, consoleRequestId)) {
        return;
      }
      state.actorCardLoading = false;
      state.actorCardError = error.message;
      state.message = error.message;
      renderShell(state, elements);
      renderActorDetail(state, elements);
      renderActorInteractionRegions(state, elements);
      renderAttachTools(state, elements);
      throw error;
    }
  }

  async function refreshConversation(state, elements, identityId, actorId, requestId, options) {
    const preserveExisting = Boolean(options && options.preserveExisting);
    const fetchOptions = options && options.fetchOptions
      ? options.fetchOptions
      : (options && options.signal ? { signal: options.signal } : undefined);
    state.conversationLoading = true;
    state.conversationError = '';
    if (!preserveExisting || state.imConversationIdentityId !== (identityId || '')) {
      clearImConversation(state, identityId || '');
    } else {
      state.imConversationIdentityId = identityId || '';
    }
    renderImConversation(state, elements);
    if (!identityId) {
      state.conversationLoading = false;
      renderImConversation(state, elements);
      return;
    }
    try {
      const payload = await fetchJson(buildImConversationUrl(identityId, 50), fetchOptions || undefined);
      if (!isCurrentActorRequest(state, actorId, requestId)) {
        return;
      }
      applyImConversationPayload(state, payload, identityId);
      state.conversationLoading = false;
      state.conversationError = '';
      renderImConversation(state, elements);
    } catch (error) {
      if (isAbortError(error) || !isCurrentActorRequest(state, actorId, requestId)) {
        return;
      }
      if (isImConversationNotFoundError(error)) {
        if (state.message === error.message) {
          state.message = '';
          renderShell(state, elements);
        }
        state.conversationLoading = false;
        state.conversationError = '';
        renderImConversation(state, elements);
        return;
      }
      state.conversationLoading = false;
      state.conversationError = error.message;
      renderImConversation(state, elements);
      throw error;
    }
  }

  async function loadActorSelection(state, elements, actorId) {
    const selection = beginActorSelection(state, actorId);
    renderActorSelectionRegions(state, elements);
    if (!selection.actorId || !actorIsInteractive(actorById(state, selection.actorId))) {
      settleActorSelection(state, elements, selection);
      return;
    }
    const target = selectedActorImTarget(state);
    const identityId = target && target.identity_id ? target.identity_id : selection.actorId;
    const actorCardPromise = refreshActorCard(
      state,
      elements,
      selection.actorId,
      selection.requestId,
      selection.consoleAbortController ? { signal: selection.consoleAbortController.signal } : undefined
    );
    const conversationPromise = refreshConversation(
      state,
      elements,
      identityId,
      selection.actorId,
      selection.requestId,
      selection.conversationAbortController ? { signal: selection.conversationAbortController.signal } : undefined
    );
    await Promise.allSettled([actorCardPromise, conversationPromise]);
    settleActorSelection(state, elements, selection);
  }

  async function refreshSelectedActorConsole(state) {
    const requestedActorId = state.selectedActorId;
    const requestId = state.actorSelectionRequestId;
    const consoleRequestId = state.actorConsoleRequestId + 1;
    state.actorConsoleRequestId = consoleRequestId;
    if (!requestedActorId || !actorIsInteractive(actorById(state, requestedActorId))) {
      state.actorConsole = null;
      syncActorCapabilitiesFromConsole(state, { force: true });
      clearImConversation(state, '');
      return;
    }
    const payload = await fetchJson(buildActorConsoleUrl(requestedActorId));
    const consoleActorId = payload
      && payload.console
      && payload.console.actor
      && typeof payload.console.actor.actor_id === 'string'
      ? payload.console.actor.actor_id
      : '';
    if (!isCurrentActorConsoleRequest(state, requestedActorId, requestId, consoleRequestId)
        || (consoleActorId && consoleActorId !== requestedActorId)) {
      return;
    }
    applyActorConsolePayload(state, payload);
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
      && actorIsInteractive(actorById(state, state.selectedActorId))
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
      renderActorInteractionRegions(state, elements);
      renderAttachTools(state, elements);
    } catch (error) {
      state.message = error.message;
      renderShell(state, elements);
    } finally {
      state.actorRefreshInFlight = false;
    }
  }

  function scheduleActorConsoleRefresh(state, elements) {
    if (typeof document === 'undefined' || !elements || state.actorRefreshTimer || !shouldRefreshSelectedActorConsole(state)) {
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

  async function refreshSelectedTrackDetailAndRender(state, elements) {
    if (!state.selectedTrackId) {
      state.selectedTrackDetail = null;
      renderTrackDetail(state, elements);
      renderTrackStudioRail(state, elements);
      return;
    }
    state.selectedTrackDetailLoading = true;
    state.selectedTrackDetailError = '';
    renderTrackDetail(state, elements);
    renderTrackStudioRail(state, elements);
    try {
      await refreshSelectedTrackDetail(state);
    } catch (error) {
      state.selectedTrackDetailError = error.message;
      state.message = error.message;
      throw error;
    } finally {
      state.selectedTrackDetailLoading = false;
      renderShell(state, elements);
      renderTrackDetail(state, elements);
      renderTrackStudioRail(state, elements);
    }
  }

  async function selectActor(state, elements, actorId) {
    if (!actorId || actorId === state.selectedActorId) {
      return;
    }
    if (state.deleteConfirmationActorId) {
      closeDeleteConfirmation(state, elements, { restoreFocus: false });
    }
    if (actorIsStopped(actorById(state, actorId))) {
      state.rosterStoppedExpanded = true;
    }
    state.message = '';
    await loadActorSelection(state, elements, actorId);
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

  async function runLifecycleAction(state, elements, action, actorId) {
    if (!action || ['stop', 'resume', 'clear', 'delete', 'retry'].indexOf(action) < 0 || !actorId || !actorById(state, actorId)) {
      return;
    }
    if (!lifecycleActionAllowed(state, action, actorId)) {
      return;
    }
    const requestId = state.actorSelectionRequestId;
    const requestOwnsSelection = function () {
      return isCurrentActorRequest(state, actorId, requestId);
    };
    state.message = '';
    renderActorInteractionRegions(state, elements);
    try {
      const payload = action === 'delete'
        ? await fetchJson('/api/instances/' + encodeURIComponent(actorId), { method: 'DELETE' })
        : await fetchJson(actorActionUrl(actorId, action), { method: 'POST' });
      const operation = payload && payload.operation ? payload.operation : null;
      if (!operation || typeof operation.id !== 'string' || operation.action !== action) {
        throw new Error('Lifecycle response did not include operation.');
      }
      recordLifecycleOperation(state, operation);
      if (actorIsStopped(actorById(state, actorId))) {
        state.rosterStoppedExpanded = true;
      }
      state.message = lifecycleOperationStatusText(operation);
      if (requestOwnsSelection()) {
        clearAttachToolFeedback(state);
      }
      renderShell(state, elements);
      renderActorList(state, elements);
      renderActorDetail(state, elements);
      renderActorInteractionRegions(state, elements);
      renderAttachTools(state, elements);
      if (operationIsTerminal(operation)) {
        await reconcileLifecycleOperation(state, elements, operation);
      } else {
        scheduleLifecycleOperationPolling(state, elements);
      }
    } catch (error) {
      state.message = error.message;
      renderShell(state, elements);
      renderActorInteractionRegions(state, elements);
      renderAttachTools(state, elements);
    }
  }

  async function runInterruptAction(state, elements) {
    if (!state.selectedActorId || state.interruptPending || activeLifecycleOperationForActor(state, state.selectedActorId)) {
      return;
    }
    const actorId = state.selectedActorId;
    const requestId = state.actorSelectionRequestId;
    const requestOwnsSelection = function () {
      return isCurrentActorRequest(state, actorId, requestId);
    };
    state.interruptPending = true;
    state.message = '';
    renderActorInteractionRegions(state, elements);
    try {
      const payload = await fetchJson(actorActionUrl(actorId, 'interrupt'), {
        method: 'POST',
      });
      if (!requestOwnsSelection()) {
        return;
      }
      state.message = payload && payload.turn_id
        ? 'Interrupted ' + actorId + ' (' + payload.turn_id + ').'
        : 'Interrupt sent.';
      clearAttachToolFeedback(state);
      await refreshSelectedActorConsole(state);
      if (requestOwnsSelection()) {
        renderActorDetail(state, elements);
      }
    } catch (error) {
      if (requestOwnsSelection()) {
        state.message = error.message;
      }
    } finally {
      if (requestOwnsSelection()) {
        state.interruptPending = false;
        renderShell(state, elements);
        renderActorInteractionRegions(state, elements);
        renderAttachTools(state, elements);
      }
    }
  }

  function lifecycleOperationPollDelays(state) {
    return Array.isArray(state.lifecycleOperationPollDelaysMs)
      ? state.lifecycleOperationPollDelaysMs
      : [150, 300, 600, 1000, 1500, 2500];
  }

  function activeLifecycleOperations(state) {
    return lifecycleOperationList(state).filter(operationIsActive);
  }

  function buildOperationUrl(operationId) {
    return '/api/operations/' + encodeURIComponent(operationId || '');
  }

  function scheduleLifecycleOperationPolling(state, elements) {
    if (!activeLifecycleOperations(state).length || state.lifecycleOperationPollTimer || state.lifecycleOperationPollInFlight) {
      return;
    }
    const delays = lifecycleOperationPollDelays(state);
    if (!delays.length) {
      return;
    }
    const delay = Number.isFinite(delays[0]) && delays[0] >= 0 ? delays[0] : 150;
    state.lifecycleOperationPollTimer = setTimeout(function () {
      state.lifecycleOperationPollTimer = null;
      pollLifecycleOperations(state, elements).catch(function (error) {
        state.message = error.message;
        renderShell(state, elements);
        renderActorList(state, elements);
        renderActorInteractionRegions(state, elements);
        renderAttachTools(state, elements);
        scheduleLifecycleOperationPolling(state, elements);
      });
    }, delay);
  }

  async function pollLifecycleOperations(state, elements) {
    if (state.lifecycleOperationPollInFlight) {
      return;
    }
    const operations = activeLifecycleOperations(state);
    if (!operations.length) {
      return;
    }
    state.lifecycleOperationPollInFlight = true;
    try {
      for (const operation of operations) {
        const payload = await fetchJson(buildOperationUrl(operation.id));
        const updatedOperation = payload && payload.operation ? payload.operation : null;
        if (!updatedOperation || typeof updatedOperation.id !== 'string') {
          throw new Error('Operation response did not include operation.');
        }
        recordLifecycleOperation(state, updatedOperation);
        if (operationIsTerminal(updatedOperation)) {
          await reconcileLifecycleOperation(state, elements, updatedOperation);
        } else {
          const reconciliation = await refreshRoster(state, elements);
          await reconcileActorSelectionAfterRoster(state, elements, reconciliation);
          state.message = lifecycleOperationStatusText(updatedOperation);
          renderShell(state, elements);
          renderActorList(state, elements);
          renderActorInteractionRegions(state, elements);
          renderAttachTools(state, elements);
        }
      }
    } finally {
      state.lifecycleOperationPollInFlight = false;
    }
    scheduleLifecycleOperationPolling(state, elements);
  }

  function nextActorIdAfterRemoval(actors, actorId) {
    const rows = Array.isArray(actors) ? actors : [];
    const index = rows.findIndex(function (actor) {
      return actor.actor_id === actorId;
    });
    if (index < 0) {
      return preferredActorId(rows);
    }
    const nextActor = rows[index + 1] || rows[index - 1] || null;
    return nextActor && typeof nextActor.actor_id === 'string' ? nextActor.actor_id : '';
  }

  function focusSelectedActorRow(state, elements) {
    if (!state.selectedActorId || !elements.actorsList || typeof elements.actorsList.querySelector !== 'function') {
      return;
    }
    const focusRow = function () {
      const row = elements.actorsList.querySelector('[data-actor-id="' + state.selectedActorId + '"]');
      if (row && typeof row.focus === 'function') {
        row.focus();
      }
    };
    if (typeof requestAnimationFrame === 'function') {
      requestAnimationFrame(focusRow);
    } else {
      focusRow();
    }
  }

  async function reconcileLifecycleOperation(state, elements, operation) {
    if (!operationIsTerminal(operation)) {
      return;
    }
    const completionMessage = lifecycleOperationStatusText(operation);
    const target = operation.target && typeof operation.target === 'object' ? operation.target : {};
    const previousActorId = typeof target.actor_id === 'string' ? target.actor_id : '';
    const replacementActorId = typeof target.replacement_actor_id === 'string' ? target.replacement_actor_id : '';
    const selectedBefore = state.selectedActorId;
    const selectionBelongsToOperation = selectedBefore === previousActorId || selectedBefore === replacementActorId;
    if (operation.action === 'delete') {
      const nextActorId = nextActorIdAfterRemoval(state.actors, previousActorId);
      forgetLifecycleOperation(state, operation);
      state.actors = state.actors.filter(function (actor) {
        return actor.actor_id !== previousActorId;
      });
      if (state.selectedActorId === previousActorId) {
        beginActorSelection(state, '');
      }
      renderActorSelectionRegions(state, elements);
      try {
        await refreshRoster(state, elements);
      } catch (_error) {
        return;
      }
      const currentSelectionStillExists = Boolean(actorById(state, state.selectedActorId));
      const selectedNextActorId = currentSelectionStillExists
        ? ''
        : (actorById(state, nextActorId) ? nextActorId : preferredActorId(state.actors));
      if (selectedNextActorId) {
        await selectActor(state, elements, selectedNextActorId);
        state.message = completionMessage;
        renderShell(state, elements);
        focusSelectedActorRow(state, elements);
      } else {
        renderActorList(state, elements);
      }
      state.message = completionMessage;
      renderShell(state, elements);
      return;
    }

    if (operation.status === 'succeeded' && operation.action !== 'start' && operation.action !== 'retry') {
      applyLifecycleOperationInstanceResult(state, operation);
    }
    forgetLifecycleOperation(state, operation);
    let reconciliation = null;
    try {
      reconciliation = await refreshRoster(state, elements);
    } catch (_error) {
      state.message = completionMessage;
      renderActorSelectionRegions(state, elements);
      return;
    }

    if (operation.action === 'start' || operation.action === 'retry') {
      const candidateActorId = replacementActorId && actorById(state, replacementActorId)
        ? replacementActorId
        : (previousActorId && actorById(state, previousActorId) ? previousActorId : '');
      if (selectionBelongsToOperation) {
        await loadActorSelection(state, elements, candidateActorId || preferredActorId(state.actors));
      } else if (reconciliation) {
        await reconcileActorSelectionAfterRoster(state, elements, reconciliation);
      }
    } else if (reconciliation) {
      await reconcileActorSelectionAfterRoster(state, elements, reconciliation);
      if (state.selectedActorId && actorIsInteractive(actorById(state, state.selectedActorId))) {
        try {
          await refreshSelectedActorConsole(state);
        } catch (_error) {
          // The operation result and roster remain authoritative even if the detail refresh fails.
        }
      }
    }
    state.message = completionMessage;
    renderActorSelectionRegions(state, elements);
  }

  async function createInstance(state, elements) {
    if (!state.selectedRole) {
      return;
    }
    state.message = '';
    renderShell(state, elements);
    try {
      const payload = await fetchJson('/api/instances', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: state.selectedRole }),
      });
      const operation = payload && payload.operation ? payload.operation : null;
      if (!operation || typeof operation.id !== 'string' || operation.action !== 'start') {
        throw new Error('Start response did not include operation.');
      }
      const actorId = lifecycleOperationActorId(operation);
      const roleId = lifecycleOperationRoleId(operation) || state.selectedRole;
      if (!actorId) {
        throw new Error('Start response did not include actor id.');
      }
      recordLifecycleOperation(state, operation);
      const startingActor = {
        actor_id: actorId,
        role: roleId,
        lifecycle_state: 'starting',
        last_failure: null,
        lifecycle_operation: operation,
        runtime: {
          status: 'inactive',
          app_server_health: '',
          thread_status: '',
        },
      };
      const existingIndex = state.actors.findIndex(function (actor) {
        return actor.actor_id === actorId;
      });
      if (existingIndex >= 0) {
        state.actors[existingIndex] = startingActor;
      } else {
        state.actors = state.actors.concat([startingActor]);
      }
      state.selectedSection = 'actors';
      await loadActorSelection(state, elements, actorId);
      state.message = lifecycleOperationStatusText(operation);
      renderShell(state, elements);
      renderActorList(state, elements);
      renderActorInteractionRegions(state, elements);
      if (operationIsTerminal(operation)) {
        await reconcileLifecycleOperation(state, elements, operation);
      } else {
        scheduleLifecycleOperationPolling(state, elements);
      }
    } catch (error) {
      state.message = error.message;
      renderShell(state, elements);
      renderActorList(state, elements);
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

  async function sendImDraft(state, elements, content, targetIdentityId) {
    await ensureImSession(state, elements);
    if (!targetIdentityId) {
      throw new Error('Select an actor first.');
    }
    const payload = await fetchJson('/api/im/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        target_identity_id: targetIdentityId,
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
    const actorId = state.selectedActorId;
    const requestId = state.actorSelectionRequestId;
    const target = selectedActorImTarget(state);
    const targetIdentityId = target && target.identity_id ? target.identity_id : '';
    if (!actorId || !targetIdentityId) {
      return;
    }
    const requestOwnsSelection = function () {
      return isCurrentActorRequest(state, actorId, requestId)
        && state.imConversationIdentityId === targetIdentityId;
    };
    const previousDraft = state.draftText;
    const pendingId = recordImPendingSend(state, content);
    state.draftText = '';
    state.sendPending = true;
    state.message = '';
    renderActorInteractionRegions(state, elements);
    renderImConversation(state, elements);
    try {
      const payload = await sendImDraft(state, elements, content, targetIdentityId);
      if (!requestOwnsSelection()) {
        return;
      }
      replaceImPendingSend(state, pendingId, payload, content);
      const imMessageId = payload && payload.message && payload.message.id ? payload.message.id : '';
      state.message = imMessageId
        ? 'Sent message ' + imMessageId + (payload.delivery_status ? ' (' + payload.delivery_status + ').' : '.')
        : 'Message sent.';
      await refreshSelectedActorConsole(state);
      renderActorDetail(state, elements);
    } catch (error) {
      if (requestOwnsSelection()) {
        removeImEntry(state, pendingId);
        state.draftText = previousDraft;
        state.message = error.message;
      }
    } finally {
      if (requestOwnsSelection()) {
        state.sendPending = false;
        renderShell(state, elements);
        renderActorInteractionRegions(state, elements);
        renderImConversation(state, elements);
      }
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
    const selectedActorId = state.selectedActorId;
    const requestId = state.actorSelectionRequestId;
    const selectedIdentityId = target.identity_id;
    const pollOwnsSelection = function () {
      return isCurrentActorRequest(state, selectedActorId, requestId)
        && state.selectedActorId === selectedIdentityId;
    };
    const payload = await fetchJson(buildImEventsUrl(15000));
    if (!pollOwnsSelection()) {
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
      if (message && pollOwnsSelection()
          && recordSelectedActorEventMessage(state, message, selectedIdentityId)) {
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
    if (selectedActorMessageProcessed && pollOwnsSelection()) {
      renderImConversation(state, elements);
      refreshActorCard(state, elements, state.selectedActorId, requestId, undefined).catch(function (error) {
        state.message = error.message;
        renderShell(state, elements);
      });
    }
    if (selectedActorMessageProcessed && pollOwnsSelection() && state.selectedSection === 'actors') {
      renderActorDetail(state, elements);
      renderActorInteractionRegions(state, elements);
      renderAttachTools(state, elements);
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

  async function openTui(state, elements) {
    const runtime = selectedActorRuntime(state);
    const attachState = computeAttachActionState(runtime);
    if (!attachState.canAttach) {
      state.openTuiMessage = attachState.message;
      renderAttachTools(state, elements);
      return;
    }
    if (state.openTuiPending) {
      return;
    }

    const actorId = state.selectedActorId;
    const requestId = state.actorSelectionRequestId;
    const requestOwnsSelection = function () {
      return isCurrentActorRequest(state, actorId, requestId);
    };
    state.openTuiPending = true;
    state.openTuiMessage = 'Opening...';
    renderAttachTools(state, elements);
    renderActorInteractionRegions(state, elements);
    try {
      await fetchJson('/api/instances/' + encodeURIComponent(actorId) + '/open-tui', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-BuddySwitch-Web': '1',
        },
        body: JSON.stringify({}),
      });
      if (requestOwnsSelection()) {
        state.openTuiMessage = 'Launch sent to Terminal.';
      }
    } catch (_error) {
      if (requestOwnsSelection()) {
        state.openTuiMessage = 'Could not launch Terminal.';
      }
    } finally {
      if (requestOwnsSelection()) {
        state.openTuiPending = false;
        renderAttachTools(state, elements);
        renderActorInteractionRegions(state, elements);
      }
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

  async function copyAttachCommand(state, elements) {
    const runtime = selectedActorRuntime(state);
    const attachState = computeAttachActionState(runtime);
    if (!attachState.canAttach) {
      state.copyCommandMessage = attachState.message;
      renderAttachTools(state, elements);
      return;
    }
    if (state.copyCommandPending) {
      return;
    }

    const actorId = state.selectedActorId;
    const requestId = state.actorSelectionRequestId;
    const requestOwnsSelection = function () {
      return isCurrentActorRequest(state, actorId, requestId);
    };
    state.copyCommandPending = true;
    state.copyCommandMessage = 'Copying...';
    renderAttachTools(state, elements);
    try {
      const payload = await fetchJson(
        '/api/instances/' + encodeURIComponent(actorId) + '/attach-command'
      );
      if (!requestOwnsSelection()) {
        return;
      }
      const command = payload && typeof payload.command === 'string' ? payload.command.trim() : '';
      if (!command) {
        throw new Error('missing attach command');
      }
      if (typeof navigator !== 'undefined' && navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(command);
      } else {
        fallbackCopyText(command);
      }
      if (requestOwnsSelection()) {
        state.copyCommandMessage = 'Command copied.';
      }
    } catch (_error) {
      if (requestOwnsSelection()) {
        state.copyCommandMessage = 'Copy failed.';
      }
    } finally {
      if (requestOwnsSelection()) {
        state.copyCommandPending = false;
        renderAttachTools(state, elements);
      }
    }
  }

  function actorActionUrl(actorId, action) {
    return '/api/instances/' + encodeURIComponent(actorId) + '/' + action;
  }

  async function refreshVisibleRegionsWithFeedback(state, elements) {
    if (state.refreshPending) {
      return;
    }
    state.refreshPending = true;
    state.message = '';
    renderShell(state, elements);
    const appBasicsPromise = refreshAppBasics(state, elements);
    const tracksPromise = refreshTracksList(state, elements);
    try {
      const rosterReconciliation = await refreshRoster(state, elements);
      let selectionChanged = await reconcileActorSelectionAfterRoster(state, elements, rosterReconciliation);
      if (!selectionChanged && state.actorSelectionPendingId
          && state.actorSelectionPendingId === state.selectedActorId) {
        await loadActorSelection(state, elements, state.selectedActorId);
        selectionChanged = true;
      }
      const refreshes = [appBasicsPromise, tracksPromise];
      if (!selectionChanged && state.selectedActorId
          && actorIsInteractive(actorById(state, state.selectedActorId))) {
        const actorId = state.selectedActorId;
        const requestId = state.actorSelectionRequestId;
        const target = selectedActorImTarget(state);
        const identityId = target && target.identity_id ? target.identity_id : actorId;
        refreshes.push(refreshActorCard(state, elements, actorId, requestId, undefined));
        refreshes.push(refreshConversation(state, elements, identityId, actorId, requestId, { preserveExisting: true }));
      }
      if (state.selectedTrackId) {
        refreshes.push(refreshSelectedTrackDetailAndRender(state, elements));
      }
      const results = await Promise.allSettled(refreshes);
      const rejected = results.find(function (result) {
        return result.status === 'rejected';
      });
      if (rejected) {
        throw rejected.reason;
      }
      state.message = 'Refreshed.';
    } catch (error) {
      await Promise.allSettled([appBasicsPromise, tracksPromise]);
      state.message = error.message;
    } finally {
      state.refreshPending = false;
      renderShell(state, elements);
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
      selectedContextAvatar: document.getElementById('selected-context-avatar'),
      selectedContextRole: document.getElementById('selected-context-role'),
      selectedContextId: document.getElementById('selected-context-id'),
      selectedContextRuntime: document.getElementById('selected-context-runtime'),
      selectedContextHealth: document.getElementById('selected-context-health'),
      selectedActorAvatar: document.getElementById('selected-actor-avatar'),
      selectedActorSubtitle: document.getElementById('selected-actor-subtitle'),
      actorRuntimeDetail: document.getElementById('actor-runtime-detail'),
      actorRuntimeSummary: document.getElementById('actor-runtime-summary'),
      actorTaskSummary: document.getElementById('actor-task-summary'),
      actorTrackSummary: document.getElementById('actor-track-summary'),
      actorCapabilityCard: document.getElementById('actor-capability-card'),
      actorCapabilityStatus: document.getElementById('actor-capability-status'),
      actorCapabilityToggle: document.getElementById('actor-capability-toggle'),
      actorCapabilityParentSummary: document.getElementById('actor-capability-parent-summary'),
      actorCapabilitySideSummary: document.getElementById('actor-capability-side-summary'),
      actorCapabilityPanel: document.getElementById('actor-capability-panel'),
      actorCapabilityMatrix: document.getElementById('actor-capability-matrix'),
      actorCapabilityDetails: document.getElementById('actor-capability-details'),
      actorCapabilitySave: document.getElementById('actor-capability-save'),
      actorCapabilityCancel: document.getElementById('actor-capability-cancel'),
      actorCapabilityMessage: document.getElementById('actor-capability-message'),
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
      retryButton: document.getElementById('retry-button'),
      openTuiButton: document.getElementById('open-tui-button'),
      openTuiStatus: document.getElementById('open-tui-status'),
      copyCommandButton: document.getElementById('copy-command-button'),
      copyCommandStatus: document.getElementById('copy-command-status'),
      messageBanner: document.getElementById('message-banner'),
      lifecycleOperationStatus: document.getElementById('lifecycle-operation-status'),
      actionAvailabilityStatus: document.getElementById('action-availability-status'),
      roomThread: document.getElementById('room-thread'),
      imConversation: document.getElementById('im-conversation'),
      newReplyChip: document.getElementById('new-reply-chip'),
      deleteConfirmationBackdrop: document.getElementById('delete-confirmation-backdrop'),
      deleteConfirmationTarget: document.getElementById('delete-confirmation-target'),
      deleteConfirmationRole: document.getElementById('delete-confirmation-role'),
      deleteConfirmationState: document.getElementById('delete-confirmation-state'),
      deleteConfirmationLabel: document.getElementById('delete-confirmation-label'),
      deleteConfirmationInput: document.getElementById('delete-confirmation-input'),
      deleteConfirmationConfirm: document.getElementById('delete-confirmation-confirm'),
      deleteConfirmationCancel: document.getElementById('delete-confirmation-cancel'),
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
      const rosterToggle = event.target && event.target.closest
        ? event.target.closest('[data-roster-toggle]')
        : null;
      if (rosterToggle) {
        if ((rosterToggle.getAttribute('data-roster-toggle') || '') === 'stopped') {
          state.rosterStoppedExpanded = !state.rosterStoppedExpanded;
          renderActorList(state, elements);
        }
        return;
      }
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
    elements.actorTaskSummary.addEventListener('click', function (event) {
      const recentToggle = event.target && event.target.closest
        ? event.target.closest('[data-task-ledger-recent-toggle]')
        : null;
      if (recentToggle) {
        const disclosure = recentToggle.parentElement;
        setTimeout(function () {
          state.actorTaskRecentExpanded = Boolean(disclosure && disclosure.open);
          recentToggle.setAttribute('aria-expanded', String(state.actorTaskRecentExpanded));
        }, 0);
        return;
      }
      const rowToggle = event.target && event.target.closest
        ? event.target.closest('summary[data-task-ledger-task-id]')
        : null;
      if (!rowToggle) {
        return;
      }
      setTimeout(function () {
        const openDetail = elements.actorTaskSummary.querySelector('details[data-task-ledger-task-id][open]');
        state.actorTaskOpenId = openDetail
          ? openDetail.getAttribute('data-task-ledger-task-id') || ''
          : '';
        elements.actorTaskSummary.querySelectorAll('summary[data-task-ledger-task-id]').forEach(function (summary) {
          summary.setAttribute('aria-expanded', String(Boolean(summary.parentElement && summary.parentElement.open)));
        });
      }, 0);
    });
    elements.actorTaskSummary.addEventListener('keydown', function (event) {
      if (event.key !== 'Enter' && event.key !== ' ') {
        return;
      }
      const taskToggle = event.target && event.target.closest
        ? event.target.closest('summary[data-task-ledger-task-id], summary[data-task-ledger-recent-toggle]')
        : null;
      if (!taskToggle) {
        return;
      }
      event.preventDefault();
      taskToggle.click();
    });
    if (elements.actorCapabilityToggle) {
      elements.actorCapabilityToggle.addEventListener('click', function () {
        state.actorCapabilityPanelOpen = !state.actorCapabilityPanelOpen;
        renderActorDetail(state, elements);
      });
    }
    if (elements.actorCapabilityMatrix) {
      elements.actorCapabilityMatrix.addEventListener('change', function (event) {
        const target = event.target;
        if (!target || target.type !== 'radio') {
          return;
        }
        const label = target.closest('[data-capability-role][data-capability-level]');
        if (!label) {
          return;
        }
        selectActorCapability(
          state,
          label.getAttribute('data-capability-role') || '',
          label.getAttribute('data-capability-level') || ''
        );
        renderActorDetail(state, elements);
      });
    }
    if (elements.actorCapabilityCancel) {
      elements.actorCapabilityCancel.addEventListener('click', function () {
        cancelActorCapabilityDraft(state);
        renderActorDetail(state, elements);
      });
    }
    if (elements.actorCapabilitySave) {
      elements.actorCapabilitySave.addEventListener('click', function () {
        saveActorCapabilities(state).then(function () {
          renderActorDetail(state, elements);
        });
        renderActorDetail(state, elements);
      });
    }
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
      renderActorInteractionRegions(state, elements);
    });
    elements.refreshButton.addEventListener('click', function () {
      refreshVisibleRegionsWithFeedback(state, elements).catch(function (error) {
        state.message = error.message;
        state.refreshPending = false;
        renderVisibleRegions(state, elements);
      });
    });
    elements.createButton.addEventListener('click', function () {
      createInstance(state, elements).catch(function (error) {
        state.message = error.message;
        renderVisibleRegions(state, elements);
      });
    });
    elements.sendButton.addEventListener('click', function () {
      sendCurrentDraft(state, elements).catch(function (error) {
        state.message = error.message;
        state.sendPending = false;
        renderShell(state, elements);
        renderActorInteractionRegions(state, elements);
      });
    });
    elements.interruptButton.addEventListener('click', function () {
      runInterruptAction(state, elements).catch(function (error) {
        state.message = error.message;
        state.interruptPending = false;
        renderShell(state, elements);
        renderActorInteractionRegions(state, elements);
      });
    });
    elements.stopButton.addEventListener('click', function () {
      runLifecycleAction(state, elements, 'stop', state.selectedActorId).catch(function (error) {
        state.message = error.message;
        renderShell(state, elements);
        renderActorInteractionRegions(state, elements);
      });
    });
    elements.clearButton.addEventListener('click', function () {
      runLifecycleAction(state, elements, 'clear', state.selectedActorId).catch(function (error) {
        state.message = error.message;
        renderShell(state, elements);
        renderActorInteractionRegions(state, elements);
      });
    });
    elements.resumeButton.addEventListener('click', function () {
      runLifecycleAction(state, elements, 'resume', state.selectedActorId).catch(function (error) {
        state.message = error.message;
        renderShell(state, elements);
        renderActorInteractionRegions(state, elements);
      });
    });
    elements.retryButton.addEventListener('click', function () {
      runLifecycleAction(state, elements, 'retry', state.selectedActorId).catch(function (error) {
        state.message = error.message;
        renderShell(state, elements);
        renderActorInteractionRegions(state, elements);
      });
    });
    elements.openTuiButton.addEventListener('click', function () {
      openTui(state, elements).catch(function (error) {
        state.openTuiMessage = error.message;
        state.openTuiPending = false;
        renderAttachTools(state, elements);
        renderActorInteractionRegions(state, elements);
      });
    });
    elements.copyCommandButton.addEventListener('click', function () {
      copyAttachCommand(state, elements).catch(function (error) {
        state.copyCommandMessage = error.message;
        state.copyCommandPending = false;
        renderAttachTools(state, elements);
      });
    });
    elements.deleteButton.addEventListener('click', function () {
      openDeleteConfirmation(state, elements, elements.deleteButton);
    });
    elements.deleteConfirmationInput.addEventListener('input', function (event) {
      updateDeleteConfirmationInput(state, elements, event.target.value);
    });
    elements.deleteConfirmationCancel.addEventListener('click', function () {
      closeDeleteConfirmation(state, elements);
    });
    elements.deleteConfirmationConfirm.addEventListener('click', function () {
      confirmDelete(state, elements).catch(function (error) {
        state.message = error.message;
        renderVisibleRegions(state, elements);
      });
    });
    elements.deleteConfirmationBackdrop.addEventListener('click', function (event) {
      if (event.target === elements.deleteConfirmationBackdrop) {
        closeDeleteConfirmation(state, elements);
      }
    });
    document.addEventListener('keydown', function (event) {
      if (elements.deleteConfirmationBackdrop.hidden) {
        return;
      }
      if (event.key === 'Escape') {
        event.preventDefault();
        closeDeleteConfirmation(state, elements);
        return;
      }
      if (event.key !== 'Tab') {
        return;
      }
      const focusable = Array.from(elements.deleteConfirmationBackdrop.querySelectorAll('input, button:not([disabled])'));
      if (!focusable.length) {
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });
    if (elements.newReplyChip) {
      elements.newReplyChip.addEventListener('click', function () {
        hideNewReplyChip(elements);
        scrollConversationToBottom(elements);
      });
    }
    if (elements.roomThread) {
      elements.roomThread.addEventListener('scroll', function () {
        if (isConversationNearBottom(elements.roomThread)) {
          hideNewReplyChip(elements);
        }
      });
    }

    renderVisibleRegions(state, elements);
    const appBasicsPromise = refreshAppBasics(state, elements);
    const tracksPromise = refreshTracksList(state, elements);
    try {
      const rosterReconciliation = await refreshRoster(state, elements);
      await reconcileActorSelectionAfterRoster(state, elements, rosterReconciliation);
      await Promise.allSettled([appBasicsPromise, tracksPromise]);
      if (state.selectedTrackId) {
        refreshSelectedTrackDetailAndRender(state, elements).catch(function (error) {
          state.message = error.message;
          renderShell(state, elements);
        });
      }
      ensureImSession(state, elements).catch(function (error) {
        state.message = error.message;
        renderShell(state, elements);
      });
      scheduleActorConsoleRefresh(state, elements);
    } catch (error) {
      await Promise.allSettled([appBasicsPromise, tracksPromise]);
      state.message = error.message;
      renderVisibleRegions(state, elements);
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
    capabilitySelectionFromConsole,
    actorInitials,
    applyImConversationPayload,
    applyTrackDetailPayload,
    applyTracksPayload,
    buildActorConsoleUrl,
    buildActorCapabilitiesUrl,
    buildImAckPayload,
    buildImEventsUrl,
    buildImConversationUrl,
    buildImMessageUrl,
    buildTrackDetailUrl,
    computeCreateEnabled,
    computeInstanceActionState,
    computeAttachActionState,
    confirmDelete,
    copyAttachCommand,
    closeDeleteConfirmation,
    createInstance,
    createState,
    clearImConversation,
    deleteConfirmationMatches,
    describeInstanceActionState,
    activeLifecycleOperationForActor,
    forgetLifecycleOperation,
    lifecycleOperationStatusText,
    operationIsActive,
    operationIsTerminal,
    pollLifecycleOperations,
    recordLifecycleOperation,
    recordImProjectedMessage,
    recordImPendingSend,
    recordImSent,
    recordSelectedActorEventMessage,
    removeImEntry,
    replaceImPendingSend,
    refreshSelectedActorConsoleAndRender,
    refreshVisibleRegionsWithFeedback,
    pollImEventsOnce,
    renderActorRowsHtml,
    renderActorCapabilities,
    renderImConversation,
    openDeleteConfirmation,
    openTui,
    renderRoleSelect,
    renderSelectedActorContext,
    renderTrackDetailHtml,
    renderTrackStudioRailHtml,
    renderComposer,
    runInterruptAction,
    runLifecycleAction,
    saveActorCapabilities,
    sendCurrentDraft,
    sectionCopy,
    selectActor,
    selectedActorRuntime,
    selectSection,
    sameCapabilitySelection,
    isConversationNearBottom,
    shouldRefreshSelectedActorConsole,
    syncActorCapabilitiesFromConsole,
    selectActorCapability,
    cancelActorCapabilityDraft,
    updateDeleteConfirmationInput,
  };
}));
