"use strict";

const data = window.BUDDYSWITCH_WORKSPACE || {
  generated_at: null,
  tracks: [],
  research_inbox: [],
  summaries: [],
};

const tracks = Array.isArray(data.tracks) ? data.tracks : [];
const researchInbox = Array.isArray(data.research_inbox) ? data.research_inbox : [];
const summaries = Array.isArray(data.summaries) ? data.summaries : [];

const roles = [
  { key: "research", label: "Research", agent: "market" },
  { key: "prd", label: "PRD", agent: "pm" },
  { key: "design", label: "Design", agent: "design" },
  { key: "build", label: "Build", agent: "dev" },
  { key: "test", label: "Test", agent: "test" },
];

const generatedAt = document.getElementById("generatedAt");
const trackCount = document.getElementById("trackCount");
const researchInboxCount = document.getElementById("researchInboxCount");
const summaryCount = document.getElementById("summaryCount");
const trackList = document.getElementById("trackList");
const researchInboxList = document.getElementById("researchInboxList");
const summaryList = document.getElementById("summaryList");
const selectedType = document.getElementById("selectedType");
const topicTitle = document.getElementById("topicTitle");
const topicSlug = document.getElementById("topicSlug");
const timeline = document.getElementById("timeline");
const switchCommands = document.getElementById("switchCommands");
const cleanupCommands = document.getElementById("cleanupCommands");

let selectedItem = tracks[0] || researchInbox[0] || null;

function selectedKey(item) {
  return item ? `${item.classification}:${item.slug}` : "";
}

function latestArtifact(item, role) {
  const artifacts = item.artifacts?.[role] || [];
  return artifacts[0] || null;
}

function artifactPath(item, role) {
  return latestArtifact(item, role)?.path || null;
}

function artifactCount(item) {
  return roles.reduce((total, role) => total + (item.artifacts?.[role.key]?.length || 0), 0);
}

function researchArtifactCount(item) {
  return item.artifacts?.research?.length || 0;
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

function suggestedTrackSwitches(item) {
  const slug = item.slug;
  const research = artifactPath(item, "research");
  const prd = artifactPath(item, "prd");
  const design = artifactPath(item, "design");
  const build = artifactPath(item, "build");
  const suggestions = [];

  if (!research) {
    suggestions.push(`switch market: 调研 ${slug} 并写入 artifacts/research/${slug}-market-research.md`);
  }

  if (research && !prd) {
    suggestions.push(`switch pm: 继续 ${slug}，基于 ${research} 写 MVP PRD`);
  }

  if (prd && !design) {
    suggestions.push(`switch design: 继续 ${slug}，基于 ${prd} 做 IA 和交互 spec`);
  }

  if (prd && design && !build) {
    suggestions.push(`switch dev: 继续 ${slug}，基于 ${prd} 和 ${design} 在 projects/app 实现最小版本`);
  }

  if ((build || design) && !artifactPath(item, "test")) {
    suggestions.push(`switch test: 继续 ${slug}，对 projects/app 的 ${slug} 改动做 smoke test`);
  }

  if (suggestions.length === 0) {
    suggestions.push(`switch pm: 继续 ${slug}，检查是否需要更新 PRD 或拆分下一轮需求`);
  }

  return suggestions;
}

function suggestedResearchInboxSwitches(item) {
  const slug = item.slug;
  const research = artifactPath(item, "research");
  if (research) {
    return [`switch pm: 基于 ${research} 写 ${slug} 的 MVP PRD`];
  }
  return [`switch market: 调研 ${slug} 并写入 artifacts/research/${slug}-market-research.md`];
}

function suggestedSwitches(item) {
  if (item.classification === "research_inbox") {
    return suggestedResearchInboxSwitches(item);
  }
  return suggestedTrackSwitches(item);
}

function cleanupSuggestions(item) {
  const presentAgents = roles
    .filter((role) => (item.artifacts?.[role.key]?.length || 0) > 0)
    .map((role) => role.agent);

  const commands = [...new Set(presentAgents)].map((agent) => `scripts/cleanup_buddyswitch.sh --agent ${agent}`);
  commands.push("scripts/cleanup_buddyswitch.sh --all-agents");
  commands.push("scripts/cleanup_buddyswitch.sh --project app");
  commands.push("scripts/cleanup_buddyswitch.sh --all-storage");
  return commands;
}

function renderGroupButton(parent, item, metaText) {
  const button = createEl("button", "topic-button");
  button.type = "button";
  button.classList.toggle("is-active", selectedKey(selectedItem) === selectedKey(item));
  button.append(
    createEl("strong", "", item.label),
    createEl("em", "", item.inferred ? "filename inferred" : "explicit"),
    createEl("span", "", metaText),
    createEl("span", "", item.updated_at || "no timestamp"),
  );
  button.addEventListener("click", () => {
    selectedItem = item;
    render();
  });
  parent.append(button);
}

function renderWorkspaceGroups() {
  trackList.replaceChildren();
  researchInboxList.replaceChildren();
  trackCount.textContent = String(tracks.length);
  researchInboxCount.textContent = String(researchInbox.length);

  if (tracks.length === 0) {
    trackList.append(createEl("p", "note", "No tracks found. A track needs at least one PRD, design, build, or test artifact."));
  } else {
    tracks.forEach((track) => {
      renderGroupButton(trackList, track, `${artifactCount(track)} artifact(s)`);
    });
  }

  if (researchInbox.length === 0) {
    researchInboxList.append(createEl("p", "note", "No market-only research artifacts found."));
  } else {
    researchInbox.forEach((item) => {
      renderGroupButton(researchInboxList, item, `${researchArtifactCount(item)} research artifact(s)`);
    });
  }
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

function renderTimeline(item) {
  timeline.replaceChildren();
  const timelineRoles = item.classification === "research_inbox"
    ? roles.filter((role) => role.key === "research")
    : roles;

  timelineRoles.forEach((role) => {
    const artifacts = item.artifacts?.[role.key] || [];
    if (artifacts.length === 0) {
      const missing = createEl("div", "artifact missing");
      const row = createEl("div", "artifact-row");
      row.append(createEl("strong", "", role.label), createEl("span", "role-tag", "missing"));
      missing.append(row);
      timeline.append(missing);
      return;
    }

    artifacts.forEach((artifact) => {
      const artifactEl = createEl("div", "artifact");
      const row = createEl("div", "artifact-row");
      row.append(
        createEl("span", "artifact-title", artifact.title),
        createEl("span", "role-tag", `${role.label} / ${artifact.agent}`),
      );
      artifactEl.append(
        row,
        createEl("code", "artifact-path", artifact.path),
        createEl("span", "artifact-path", artifact.updated_at),
      );
      timeline.append(artifactEl);
    });
  });
}

function renderSelectedItem() {
  if (!selectedItem) {
    setText(selectedType, "Selected item");
    setText(topicTitle, "No item");
    setText(topicSlug, "-");
    timeline.replaceChildren(createEl("p", "note", "No track or research inbox data available."));
    switchCommands.replaceChildren();
    cleanupCommands.replaceChildren();
    return;
  }

  setText(selectedType, selectedItem.classification === "research_inbox" ? "Research Inbox Item" : "Track");
  setText(topicTitle, selectedItem.label);
  setText(topicSlug, selectedItem.slug);
  renderTimeline(selectedItem);

  switchCommands.replaceChildren();
  suggestedSwitches(selectedItem).forEach((command) => renderCommand(switchCommands, command));

  cleanupCommands.replaceChildren();
  cleanupSuggestions(selectedItem).forEach((command) => renderCommand(cleanupCommands, command));
}

function render() {
  generatedAt.textContent = data.generated_at || "not generated";
  renderWorkspaceGroups();
  renderSummaries();
  renderSelectedItem();
}

render();
