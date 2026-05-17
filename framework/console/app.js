"use strict";

const emptyWorkspace = {
  generated_at: null,
  manifest_path: null,
  objects_root: null,
  buddies: [],
  tracks: [],
  standalone_tasks: [],
  tasks: [],
  artifacts: [],
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
  };
}

function applyWorkspaceData(nextWorkspace) {
  workspace = normalizeWorkspaceData(nextWorkspace);
  if (generatedAt) {
    generatedAt.textContent = workspace.generated_at || "";
  }
}

function deriveTrackOwnerState(trackPayload) {
  const track = trackPayload && typeof trackPayload === "object" ? trackPayload : {};
  return {
    trackId: typeof track.id === "string" ? track.id : "",
    ownerBuddy: typeof track.owner_buddy === "string" ? track.owner_buddy : "",
    status: typeof track.status === "string" ? track.status : "",
    summary: typeof track.summary === "string" ? track.summary : "",
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
    deriveTrackOwnerState,
    refreshWorkspaceData,
  };
}
