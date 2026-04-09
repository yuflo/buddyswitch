"use strict";

const emptyWorkspace = {
  generated_at: null,
  manifest_path: null,
  objects_root: null,
  buddies: [],
  tracks: [],
  artifacts: [],
  untracked_artifacts: [],
  summaries: [],
};

const generatedAt = document.getElementById("generatedAt");
const trackCount = document.getElementById("trackCount");
const summaryCount = document.getElementById("summaryCount");
const untrackedCount = document.getElementById("untrackedCount");
const trackList = document.getElementById("trackList");
const summaryList = document.getElementById("summaryList");
const untrackedList = document.getElementById("untrackedList");
const selectedType = document.getElementById("selectedType");
const topicTitle = document.getElementById("topicTitle");
const topicSlug = document.getElementById("topicSlug");
const timeline = document.getElementById("timeline");
const switchCommands = document.getElementById("switchCommands");
const cleanupCommands = document.getElementById("cleanupCommands");
const refreshButton = document.getElementById("refreshButton");
const dataStatus = document.getElementById("dataStatus");

let workspace = normalizeWorkspaceData(emptyWorkspace);
let selectedTrack = null;

function normalizeWorkspaceData(rawData) {
  return {
    ...emptyWorkspace,
    ...(rawData || {}),
    buddies: Array.isArray(rawData?.buddies) ? rawData.buddies : [],
    tracks: Array.isArray(rawData?.tracks) ? rawData.tracks : [],
    artifacts: Array.isArray(rawData?.artifacts) ? rawData.artifacts : [],
    untracked_artifacts: Array.isArray(rawData?.untracked_artifacts) ? rawData.untracked_artifacts : [],
    summaries: Array.isArray(rawData?.summaries) ? rawData.summaries : [],
  };
}

function buddyLabelMap() {
  return new Map(workspace.buddies.map((buddy) => [buddy.id, buddy.label]));
}

function buddyLabel(buddyId) {
  const labels = buddyLabelMap();
  return labels.get(buddyId) || buddyId || "unknown";
}

function applyWorkspaceData(nextWorkspace) {
  const selectedTrackId = selectedTrack?.id || null;
  workspace = normalizeWorkspaceData(nextWorkspace);
  selectedTrack = workspace.tracks.find((track) => track.id === selectedTrackId) || workspace.tracks[0] || null;
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

function createEl(tag, className, text) {
  const el = document.createElement(tag);
  if (className) {
    el.className = className;
  }
  if (text) {
    el.textContent = text;
  }
  return el;
}

function setText(el, value) {
  if (el) {
    el.textContent = value;
  }
}

async function copyText(text, button) {
  try {
    await navigator.clipboard.writeText(text);
    button.textContent = "Copied";
    setTimeout(() => {
      button.textContent = "Copy";
    }, 1200);
  } catch {
    window.prompt("Copy command", text);
  }
}

function renderCommand(parent, command) {
  const row = createEl("div", "command-row");
  const code = createEl("code", "command", command);
  const button = createEl("button", "copy-button", "Copy");
  button.type = "button";
  button.addEventListener("click", () => copyText(command, button));
  row.append(code, button);
  parent.append(row);
}

function artifactCount(track) {
  return Array.isArray(track.artifacts) ? track.artifacts.length : 0;
}

function renderTrackButton(track) {
  const button = createEl("button", "topic-button");
  button.type = "button";
  button.classList.toggle("is-active", selectedTrack?.id === track.id);
  const flow = track.next_buddy
    ? `${buddyLabel(track.current_buddy)} -> ${buddyLabel(track.next_buddy)}`
    : `${buddyLabel(track.current_buddy)} -> (no next)`;
  button.append(
    createEl("strong", "", track.title),
    createEl("em", "", track.status || "active"),
    createEl("span", "", flow),
    createEl("span", "", `${artifactCount(track)} artifact(s)`),
    createEl("span", "", track.updated_at || "no timestamp"),
  );
  button.addEventListener("click", () => {
    selectedTrack = track;
    render();
  });
  trackList.append(button);
}

function renderTracks() {
  trackList.replaceChildren();
  trackCount.textContent = String(workspace.tracks.length);

  if (workspace.tracks.length === 0) {
    trackList.append(
      createEl(
        "p",
        "note",
        "No tracks found. PM can create one with scripts/env_tracks.py create <track-id> --title \"...\".",
      ),
    );
    return;
  }

  workspace.tracks.forEach(renderTrackButton);
}

function renderSummaries() {
  summaryList.replaceChildren();
  summaryCount.textContent = String(workspace.summaries.length);

  if (workspace.summaries.length === 0) {
    summaryList.append(createEl("p", "note", "No run summaries found."));
    return;
  }

  workspace.summaries.slice(0, 8).forEach((summary) => {
    const item = createEl("div", "summary-item");
    item.append(
      createEl("strong", "", summary.title),
      createEl("span", "", summary.path),
      createEl("span", "", summary.updated_at),
    );
    summaryList.append(item);
  });
}

function renderTimeline(track) {
  timeline.replaceChildren();
  const artifacts = Array.isArray(track.artifacts) ? track.artifacts : [];

  if (artifacts.length === 0) {
    timeline.append(createEl("p", "note", "No artifact objects attached to this track."));
  }

  artifacts.forEach((artifact) => {
    const artifactEl = createEl("div", artifact.missing ? "artifact missing" : "artifact");
    const row = createEl("div", "artifact-row");
    row.append(
      createEl("span", "artifact-title", artifact.title),
      createEl("span", "role-tag", `${buddyLabel(artifact.producer_buddy)} / ${artifact.kind}`),
    );
    artifactEl.append(
      row,
      createEl("code", "artifact-path", artifact.path),
      createEl("span", "artifact-path", artifact.missing ? "missing file" : artifact.updated_at),
    );
    timeline.append(artifactEl);
  });

  if (Array.isArray(track.missing_artifact_ids) && track.missing_artifact_ids.length > 0) {
    track.missing_artifact_ids.forEach((artifactId) => {
      const missing = createEl("div", "artifact missing");
      const row = createEl("div", "artifact-row");
      row.append(createEl("span", "artifact-title", artifactId), createEl("span", "role-tag", "object missing"));
      missing.append(
        row,
        createEl("code", "artifact-path", `missing artifact object: ${artifactId}`),
      );
      timeline.append(missing);
    });
  }
}

function suggestedTrackSwitches(track) {
  const suggestions = [];
  if (track.next_buddy) {
    suggestions.push(`switch ${track.next_buddy}: 继续 ${track.id} track，基于当前上下文推进并产出需要的 artifact`);
  } else if (track.status === "done" || track.status === "archived") {
    suggestions.push(`switch pm: 复核 ${track.id} track 是否需要 reopen 或拆分下一条 track`);
  } else {
    suggestions.push(`switch ${track.current_buddy}: 继续 ${track.id} track，补充当前阶段的交付`);
  }
  suggestions.push(`switch pm: 继续 ${track.id} track，更新 status/current_buddy/next_buddy 并收口`);
  return suggestions;
}

function cleanupSuggestions(track) {
  const seen = new Set();
  const commands = [];
  (track.artifacts || []).forEach((artifact) => {
    if (artifact.producer_buddy && !seen.has(artifact.producer_buddy)) {
      seen.add(artifact.producer_buddy);
      commands.push(`scripts/cleanup_buddyswitch.sh --agent ${artifact.producer_buddy}`);
    }
  });
  commands.push("scripts/cleanup_buddyswitch.sh --all-agents");
  commands.push("scripts/cleanup_buddyswitch.sh --project app");
  commands.push("scripts/cleanup_buddyswitch.sh --all-storage");
  return commands;
}

function registerCommand(artifact) {
  return `switch pm: 将 ${artifact.path} 关联到 <track-id>，并决定下一步 buddy`;
}

function renderUntrackedArtifacts() {
  untrackedList.replaceChildren();
  untrackedCount.textContent = String(workspace.untracked_artifacts.length);

  if (workspace.untracked_artifacts.length === 0) {
    untrackedList.append(createEl("p", "note", "No files waiting in artifact inbox."));
    return;
  }

  workspace.untracked_artifacts.forEach((artifact) => {
    const item = createEl("div", "summary-item");
    item.append(
      createEl("strong", "", artifact.title),
      createEl("code", "artifact-path", artifact.path),
      createEl("span", "", artifact.updated_at || "no timestamp"),
    );
    renderCommand(item, registerCommand(artifact));
    untrackedList.append(item);
  });
}

function renderSelectedTrack() {
  if (!selectedTrack) {
    setText(selectedType, "Selected track");
    setText(topicTitle, "No track");
    setText(topicSlug, "-");
    timeline.replaceChildren(createEl("p", "note", "No track data available."));
    switchCommands.replaceChildren();
    cleanupCommands.replaceChildren();
    return;
  }

  setText(selectedType, `Track (${selectedTrack.status})`);
  setText(topicTitle, selectedTrack.title);
  const flow = selectedTrack.next_buddy
    ? `${selectedTrack.id} | ${selectedTrack.current_buddy} -> ${selectedTrack.next_buddy}`
    : `${selectedTrack.id} | ${selectedTrack.current_buddy}`;
  setText(topicSlug, flow);
  renderTimeline(selectedTrack);

  switchCommands.replaceChildren();
  suggestedTrackSwitches(selectedTrack).forEach((command) => renderCommand(switchCommands, command));

  cleanupCommands.replaceChildren();
  cleanupSuggestions(selectedTrack).forEach((command) => renderCommand(cleanupCommands, command));
}

function render() {
  setText(generatedAt, workspace.generated_at || "not generated");
  renderTracks();
  renderSummaries();
  renderSelectedTrack();
  renderUntrackedArtifacts();
}

async function refreshWorkspaceData({ silent = false } = {}) {
  if (!canFetchLiveWorkspace()) {
    setDataStatus("Start local server: python3 scripts/serve_context_panel.py", "warning");
    return false;
  }

  if (refreshButton) {
    refreshButton.disabled = true;
    refreshButton.textContent = "Refreshing";
  }
  setDataStatus("Reading current workspace...", "loading");

  try {
    const response = await fetch(`/api/workspace?t=${Date.now()}`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      throw new Error(`Workspace API returned ${response.status}`);
    }
    applyWorkspaceData(await response.json());
    render();
    setDataStatus("Live workspace data", "live");
    return true;
  } catch (error) {
    if (!silent) {
      console.warn("Unable to refresh live workspace data.", error);
    }
    setDataStatus("Unable to read /api/workspace. Run python3 scripts/serve_context_panel.py.", "warning");
    return false;
  } finally {
    if (refreshButton) {
      refreshButton.disabled = false;
      refreshButton.textContent = "Refresh workspace";
    }
  }
}

if (refreshButton) {
  refreshButton.addEventListener("click", () => {
    refreshWorkspaceData();
  });
}

setDataStatus("Loading workspace data...", "loading");
render();
refreshWorkspaceData({ silent: true });
