"use strict";

const emptyWorkspace = {
  generated_at: null,
  manifest_path: null,
  objects_root: null,
  buddies: [],
  tracks: [],
  artifacts: [],
  run_audits: [],
};

const generatedAt = document.getElementById("generatedAt");
const trackCount = document.getElementById("trackCount");
const runAuditCount = document.getElementById("runAuditCount");
const trackList = document.getElementById("trackList");
const runAuditList = document.getElementById("runAuditList");
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
    run_audits: Array.isArray(rawData?.run_audits) ? rawData.run_audits : [],
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
        "No tracks found. Create one with switch pm: create <track-id> track ...",
      ),
    );
    return;
  }

  workspace.tracks.forEach(renderTrackButton);
}

function renderRunAudits() {
  runAuditList.replaceChildren();
  runAuditCount.textContent = String(workspace.run_audits.length);

  if (workspace.run_audits.length === 0) {
    runAuditList.append(createEl("p", "note", "No run audits found."));
    return;
  }

  workspace.run_audits.slice(0, 8).forEach((audit) => {
    const item = createEl("div", "summary-item");
    const label = audit.track_action
      ? `${audit.skill_id || "unknown"} / ${audit.track_action}`
      : audit.skill_id || "unknown";
    item.append(
      createEl("strong", "", label),
      createEl("span", "", audit.task || audit.path || "No task"),
      createEl("span", "", audit.execution_summary || audit.status || "No summary"),
      createEl("span", "", audit.updated_at || "no timestamp"),
    );
    runAuditList.append(item);
  });
}

function formatArtifactPreview(artifact) {
  if (artifact.summary) {
    return artifact.summary;
  }
  try {
    return JSON.stringify(artifact.content || {}, null, 2);
  } catch {
    return "{}";
  }
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
      createEl("span", "role-tag", `${buddyLabel(artifact.buddy)} / ${artifact.skill_id}`),
    );
    artifactEl.append(
      row,
      createEl("code", "artifact-path", artifact.object_path),
      createEl("span", "artifact-path", artifact.updated_at || "no timestamp"),
      createEl("pre", "artifact-path", formatArtifactPreview(artifact)),
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
    if (artifact.buddy && !seen.has(artifact.buddy)) {
      seen.add(artifact.buddy);
      commands.push(`scripts/cleanup_buddyswitch.sh --agent ${artifact.buddy}`);
    }
  });
  commands.push("scripts/cleanup_buddyswitch.sh --all-agents");
  commands.push("scripts/cleanup_buddyswitch.sh --project app");
  commands.push("scripts/cleanup_buddyswitch.sh --all-storage");
  return commands;
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
  renderRunAudits();
  renderSelectedTrack();
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
