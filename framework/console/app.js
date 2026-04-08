"use strict";

const data = window.BUDDYSWITCH_WORKSPACE || {
  generated_at: null,
  tracks: [],
  untracked_artifacts: [],
  summaries: [],
};

const tracks = Array.isArray(data.tracks) ? data.tracks : [];
const untrackedArtifacts = Array.isArray(data.untracked_artifacts) ? data.untracked_artifacts : [];
const summaries = Array.isArray(data.summaries) ? data.summaries : [];

const roles = [
  { key: "market", label: "Market" },
  { key: "pm", label: "PM" },
  { key: "design", label: "Design" },
  { key: "dev", label: "Dev" },
  { key: "test", label: "Test" },
];

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

let selectedTrack = tracks[0] || null;

function latestExistingArtifact(track, role) {
  const artifacts = track.artifacts?.[role] || [];
  return artifacts.find((artifact) => !artifact.missing) || null;
}

function artifactPath(track, role) {
  return latestExistingArtifact(track, role)?.path || null;
}

function artifactCount(track) {
  return roles.reduce((total, role) => total + (track.artifacts?.[role.key]?.length || 0), 0);
}

function setText(el, value) {
  el.textContent = value;
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

function suggestedTrackSwitches(track) {
  const trackId = track.id;
  const market = artifactPath(track, "market");
  const prd = artifactPath(track, "pm");
  const design = artifactPath(track, "design");
  const build = artifactPath(track, "dev");
  const suggestions = [];

  if (!market) {
    suggestions.push(`switch market: 为 ${trackId} track 补充调研，并通过 registry adapter 登记`);
  }

  if (!prd) {
    const source = market ? `，基于 ${market}` : "";
    suggestions.push(`switch pm: 继续 ${trackId} track${source}，写 MVP PRD 并登记到 registry`);
  }

  if (prd && !design) {
    suggestions.push(`switch design: 继续 ${trackId} track，基于 ${prd} 做 IA 和交互 spec 并登记到 registry`);
  }

  if (prd && design && !build) {
    suggestions.push(`switch dev: 继续 ${trackId} track，基于 ${prd} 和 ${design} 在 projects/app 实现最小版本并登记到 registry`);
  }

  if ((build || design) && !artifactPath(track, "test")) {
    suggestions.push(`switch test: 继续 ${trackId} track，对 projects/app 的改动做 smoke test 并登记到 registry`);
  }

  if (suggestions.length === 0) {
    suggestions.push(`switch pm: 继续 ${trackId} track，检查是否需要更新 PRD 或拆分下一轮需求`);
  }

  return suggestions;
}

function cleanupSuggestions(track) {
  const presentAgents = roles
    .filter((role) => (track.artifacts?.[role.key] || []).some((artifact) => !artifact.missing))
    .map((role) => role.key);

  const commands = [...new Set(presentAgents)].map((agent) => `scripts/cleanup_buddyswitch.sh --agent ${agent}`);
  commands.push("scripts/cleanup_buddyswitch.sh --all-agents");
  commands.push("scripts/cleanup_buddyswitch.sh --project app");
  commands.push("scripts/cleanup_buddyswitch.sh --all-storage");
  return commands;
}

function renderTrackButton(track) {
  const button = createEl("button", "topic-button");
  button.type = "button";
  button.classList.toggle("is-active", selectedTrack?.id === track.id);
  button.append(
    createEl("strong", "", track.title),
    createEl("em", "", track.state || "active"),
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
  trackCount.textContent = String(tracks.length);

  if (tracks.length === 0) {
    trackList.append(createEl("p", "note", "No tracks found. Register a product iteration with scripts/registry.py."));
    return;
  }

  tracks.forEach(renderTrackButton);
}

function renderSummaries() {
  summaryList.replaceChildren();
  summaryCount.textContent = String(summaries.length);

  if (summaries.length === 0) {
    summaryList.append(createEl("p", "note", "No run summaries found."));
    return;
  }

  summaries.slice(0, 8).forEach((summary) => {
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

  roles.forEach((role) => {
    const artifacts = track.artifacts?.[role.key] || [];
    if (artifacts.length === 0) {
      const missing = createEl("div", "artifact missing");
      const row = createEl("div", "artifact-row");
      row.append(createEl("strong", "", role.label), createEl("span", "role-tag", "not registered"));
      missing.append(row);
      timeline.append(missing);
      return;
    }

    artifacts.forEach((artifact) => {
      const artifactEl = createEl("div", artifact.missing ? "artifact missing" : "artifact");
      const row = createEl("div", "artifact-row");
      row.append(
        createEl("span", "artifact-title", artifact.title),
        createEl("span", "role-tag", `${role.label} / ${artifact.type}`),
      );
      artifactEl.append(
        row,
        createEl("code", "artifact-path", artifact.path),
        createEl("span", "artifact-path", artifact.missing ? "missing file" : artifact.updated_at),
      );
      timeline.append(artifactEl);
    });
  });
}

function registerCommand(artifact) {
  return `switch ${artifact.role}: 将 ${artifact.path} 显式登记到 <track-id> track，并说明下一步处理`;
}

function renderUntrackedArtifacts() {
  untrackedList.replaceChildren();
  untrackedCount.textContent = String(untrackedArtifacts.length);

  if (untrackedArtifacts.length === 0) {
    untrackedList.append(createEl("p", "note", "No untracked artifacts found."));
    return;
  }

  untrackedArtifacts.forEach((artifact) => {
    const item = createEl("div", "summary-item");
    item.append(
      createEl("strong", "", artifact.title),
      createEl("span", "", `${artifact.role} / ${artifact.type}`),
      createEl("code", "artifact-path", artifact.path),
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

  setText(selectedType, "Selected track");
  setText(topicTitle, selectedTrack.title);
  setText(topicSlug, selectedTrack.id);
  renderTimeline(selectedTrack);

  switchCommands.replaceChildren();
  suggestedTrackSwitches(selectedTrack).forEach((command) => renderCommand(switchCommands, command));

  cleanupCommands.replaceChildren();
  cleanupSuggestions(selectedTrack).forEach((command) => renderCommand(cleanupCommands, command));
}

function render() {
  generatedAt.textContent = data.generated_at || "not generated";
  renderTracks();
  renderSummaries();
  renderSelectedTrack();
  renderUntrackedArtifacts();
}

if (refreshButton) {
  refreshButton.addEventListener("click", () => {
    window.location.reload();
  });
}

render();
