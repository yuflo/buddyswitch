"use strict";

const emptyWorkspace = {
  generated_at: null,
  manifest_path: null,
  objects_root: null,
  content_root: null,
  buddies: [],
  tracks: [],
  standalone_tasks: [],
  tasks: [],
  artifacts: [],
  handoffs: [],
  buddybox_files: [],
};

const generatedAt = document.getElementById("generatedAt");
const dataStatus = document.getElementById("dataStatus");

let workspace = normalizeWorkspaceData(emptyWorkspace);

function normalizeWorkspaceData(rawData) {
  return {
    ...emptyWorkspace,
    ...(rawData || {}),
    buddies: Array.isArray(rawData?.buddies) ? rawData.buddies : [],
    tracks: Array.isArray(rawData?.tracks) ? rawData.tracks : [],
    standalone_tasks: Array.isArray(rawData?.standalone_tasks) ? rawData.standalone_tasks : [],
    tasks: Array.isArray(rawData?.tasks) ? rawData.tasks : [],
    artifacts: Array.isArray(rawData?.artifacts) ? rawData.artifacts : [],
    handoffs: Array.isArray(rawData?.handoffs) ? rawData.handoffs : [],
    buddybox_files: Array.isArray(rawData?.buddybox_files) ? rawData.buddybox_files : [],
  };
}

function applyWorkspaceData(nextWorkspace) {
  workspace = normalizeWorkspaceData(nextWorkspace);
  if (generatedAt) {
    generatedAt.textContent = workspace.generated_at || "";
  }
}

function _trackById(trackId) {
  return workspace.tracks.find((track) => track && track.id === trackId) || null;
}

function _taskById(taskId) {
  return workspace.tasks.find((task) => task && task.id === taskId) || null;
}

function _modeForBuddies(currentBuddy, nextBuddy) {
  if (typeof nextBuddy === "string" && nextBuddy && nextBuddy !== currentBuddy) {
    return "handoff";
  }
  return "continue_current_task";
}

function deriveNextStepStateForTrack(trackPayload) {
  const track = trackPayload && typeof trackPayload === "object" ? trackPayload : {};
  const trackId = typeof track.id === "string" ? track.id : "";
  const currentBuddy = typeof track.current_buddy === "string" && track.current_buddy ? track.current_buddy : "pm";
  const nextBuddy = typeof track.next_buddy === "string" && track.next_buddy ? track.next_buddy : currentBuddy;
  const mode = _modeForBuddies(currentBuddy, nextBuddy);
  const recommendedBuddy = nextBuddy || currentBuddy;
  return {
    trackId,
    currentBuddy,
    nextBuddy,
    recommendedBuddy,
    mode,
    summary:
      mode === "handoff"
        ? `Track ${trackId || "(unknown)"} should handoff from ${currentBuddy} to ${recommendedBuddy}.`
        : `Track ${trackId || "(unknown)"} should continue with ${currentBuddy}.`,
  };
}

function deriveNextStepStateForTask(taskPayload) {
  const task = taskPayload && typeof taskPayload === "object" ? taskPayload : {};
  const taskId = typeof task.id === "string" ? task.id : "";
  const currentBuddy = typeof task.buddy === "string" && task.buddy ? task.buddy : "pm";

  let recommendedBuddy = currentBuddy;
  let nextBuddy = currentBuddy;
  const trackId = typeof task.track_id === "string" && task.track_id ? task.track_id : null;
  if (trackId) {
    const track = _trackById(trackId);
    if (track && typeof track.next_buddy === "string" && track.next_buddy) {
      recommendedBuddy = track.next_buddy;
      nextBuddy = track.next_buddy;
    }
  }

  const mode = _modeForBuddies(currentBuddy, nextBuddy);
  return {
    taskId,
    currentBuddy,
    nextBuddy,
    recommendedBuddy,
    mode,
    summary:
      mode === "handoff"
        ? `Task ${taskId || "(unknown)"} should handoff from ${currentBuddy} to ${recommendedBuddy}.`
        : `Task ${taskId || "(unknown)"} should continue with ${currentBuddy}.`,
  };
}

function canFetchLiveWorkspace() {
  return window.location.protocol === "http:" || window.location.protocol === "https:";
}

function setDataStatus(message, state = "neutral") {
  if (!dataStatus) {
    return;
  }
  dataStatus.textContent = message;
  dataStatus.dataset.state = state;
}

async function refreshWorkspaceData() {
  if (!canFetchLiveWorkspace() || typeof fetch !== "function") {
    setDataStatus("Static mode", "neutral");
    return workspace;
  }
  try {
    const response = await fetch("/api/workspace", { cache: "no-store" });
    let payload = {};
    try {
      payload = await response.json();
    } catch {
      payload = {};
    }

    if (!response.ok) {
      const errorCode = typeof payload.error === "string" ? payload.error : "request_failed";
      if (errorCode === "runtime_snapshot_busy") {
        setDataStatus("Workspace snapshot is busy; keeping previous data.", "warning");
        return workspace;
      }
      setDataStatus(`Workspace request failed (${response.status}).`, "error");
      return workspace;
    }

    applyWorkspaceData(payload);
    setDataStatus("Workspace updated.", "ok");
    return workspace;
  } catch {
    setDataStatus("Workspace request failed; keeping previous data.", "error");
    return workspace;
  }
}

if (typeof window !== "undefined" && typeof window.addEventListener === "function") {
  window.addEventListener("load", () => {
    if (workspace.generated_at) {
      if (generatedAt) {
        generatedAt.textContent = workspace.generated_at;
      }
      return;
    }
    refreshWorkspaceData();
  });
}

if (typeof module !== "undefined") {
  module.exports = {
    normalizeWorkspaceData,
    applyWorkspaceData,
    deriveNextStepStateForTrack,
    deriveNextStepStateForTask,
    refreshWorkspaceData,
  };
}
