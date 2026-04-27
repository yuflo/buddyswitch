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
  run_audits: [],
};

const buddyOrder = ["pm", "market", "design", "dev", "test"];
const projectCodePath = "projects/app";

const generatedAt = document.getElementById("generatedAt");
const workspaceCounts = document.getElementById("workspaceCounts");
const projectCode = document.getElementById("projectCode");
const trackCount = document.getElementById("trackCount");
const runAuditCount = document.getElementById("runAuditCount");
const selectedTaskCount = document.getElementById("selectedTaskCount");
const trackList = document.getElementById("trackList");
const taskList = document.getElementById("taskList");
const taskMaterials = document.getElementById("taskMaterials");
const trackSummary = document.getElementById("trackSummary");
const trackProgress = document.getElementById("trackProgress");
const runAuditList = document.getElementById("runAuditList");
const selectedType = document.getElementById("selectedType");
const topicTitle = document.getElementById("topicTitle");
const topicSlug = document.getElementById("topicSlug");
const switchCommands = document.getElementById("switchCommands");
const sourceDetails = document.getElementById("sourceDetails");
const refreshButton = document.getElementById("refreshButton");
const dataStatus = document.getElementById("dataStatus");

let workspace = normalizeWorkspaceData(emptyWorkspace);
let selectedTrack = null;
let selectedTaskId = null;
let selectedStandalone = false;

function normalizeWorkspaceData(rawData) {
  return {
    ...emptyWorkspace,
    ...(rawData || {}),
    buddies: Array.isArray(rawData?.buddies) ? rawData.buddies : [],
    tracks: Array.isArray(rawData?.tracks) ? rawData.tracks : [],
    standalone_tasks: Array.isArray(rawData?.standalone_tasks) ? rawData.standalone_tasks : [],
    tasks: Array.isArray(rawData?.tasks) ? rawData.tasks : [],
    artifacts: Array.isArray(rawData?.artifacts) ? rawData.artifacts : [],
    run_audits: Array.isArray(rawData?.run_audits) ? rawData.run_audits : [],
  };
}

function createEl(tag, className, text) {
  const el = document.createElement(tag);
  if (className) {
    el.className = className;
  }
  if (text !== undefined && text !== null) {
    el.textContent = String(text);
  }
  return el;
}

function setText(el, value) {
  if (el) {
    el.textContent = value || "";
  }
}

function clampText(value, maxLength = 220) {
  const text = typeof value === "string" ? value.trim() : "";
  if (!text) {
    return "";
  }
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength - 1)}...`;
}

function safeJson(value) {
  try {
    return JSON.stringify(value || {}, null, 2);
  } catch {
    return "{}";
  }
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function isObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function artifactMap() {
  return new Map(workspace.artifacts.map((artifact) => [artifact.id, artifact]));
}

function runMap() {
  return new Map(workspace.run_audits.map((run) => [run.run_id, run]));
}

function buddyLabelMap() {
  return new Map(workspace.buddies.map((buddy) => [buddy.id, buddy.label]));
}

function buddyLabel(buddyId) {
  const labels = buddyLabelMap();
  return labels.get(buddyId) || buddyId || "unknown";
}

function sortByLatest(items) {
  return [...items].sort((a, b) => {
    const left = a?.updated_at || a?.created_at || "";
    const right = b?.updated_at || b?.created_at || "";
    return right.localeCompare(left) || String(a?.id || "").localeCompare(String(b?.id || ""));
  });
}

function orderedTrackTasks(track) {
  const tasks = asArray(track?.tasks);
  if (tasks.length === 0) {
    return [];
  }
  const position = new Map(asArray(track.task_ids).map((taskId, index) => [taskId, index]));
  return [...tasks].sort((a, b) => {
    const buddyDelta = buddyOrder.indexOf(a.buddy) - buddyOrder.indexOf(b.buddy);
    const knownBuddyDelta = (buddyOrder.includes(a.buddy) ? 0 : 1) - (buddyOrder.includes(b.buddy) ? 0 : 1);
    if (knownBuddyDelta !== 0) {
      return knownBuddyDelta;
    }
    if (buddyDelta !== 0) {
      return buddyDelta;
    }
    return (position.get(a.id) ?? 9999) - (position.get(b.id) ?? 9999);
  });
}

function standaloneTasks() {
  if (workspace.standalone_tasks.length > 0) {
    return sortByLatest(workspace.standalone_tasks);
  }
  const trackedTaskIds = new Set(workspace.tracks.flatMap((track) => asArray(track?.task_ids)));
  return sortByLatest(
    workspace.tasks.filter((task) => !task?.track_id && !trackedTaskIds.has(task.id)),
  );
}

function getTaskArtifacts(task) {
  const artifactsById = artifactMap();
  const seen = new Set();
  const artifacts = [];
  asArray(task?.artifact_ids).forEach((artifactId) => {
    const artifact = artifactsById.get(artifactId);
    if (artifact && !seen.has(artifact.id)) {
      seen.add(artifact.id);
      artifacts.push(artifact);
    }
  });
  if (task?.latest_artifact && !seen.has(task.latest_artifact.id)) {
    artifacts.push(task.latest_artifact);
  }
  return sortByLatest(artifacts);
}

function getTrackArtifacts(track) {
  const seen = new Set();
  const artifacts = [];
  orderedTrackTasks(track).forEach((task) => {
    getTaskArtifacts(task).forEach((artifact) => {
      if (!seen.has(artifact.id)) {
        seen.add(artifact.id);
        artifacts.push(artifact);
      }
    });
  });
  return sortByLatest(artifacts);
}

function getTaskRuns(task) {
  const runsById = runMap();
  const runIds = new Set(asArray(task?.run_ids));
  const runs = workspace.run_audits.filter((run) => run.task_id === task?.id || runIds.has(run.run_id));
  asArray(task?.run_ids).forEach((runId) => {
    const run = runsById.get(runId);
    if (run && !runs.some((item) => item.run_id === runId)) {
      runs.push(run);
    }
  });
  return sortByLatest(runs);
}

function getTrackRuns(track) {
  const taskIds = new Set(orderedTrackTasks(track).map((task) => task.id));
  const runs = workspace.run_audits.filter((run) => run.track_id === track?.id || taskIds.has(run.task_id));
  return sortByLatest(runs);
}

function latestTaskForTrack(track) {
  return sortByLatest(orderedTrackTasks(track))[0] || null;
}

function latestArtifactForTrack(track) {
  return getTrackArtifacts(track)[0] || null;
}

function latestRunForTask(task) {
  return getTaskRuns(task)[0] || null;
}

function latestRunForTrack(track) {
  return getTrackRuns(track)[0] || null;
}

function selectedTaskForTrack(track) {
  const tasks = orderedTrackTasks(track);
  if (tasks.length === 0) {
    return null;
  }
  return tasks.find((task) => task.id === selectedTaskId) || latestTaskForTrack(track) || tasks[0];
}

function selectedStandaloneTask() {
  const tasks = standaloneTasks();
  if (tasks.length === 0) {
    return null;
  }
  return tasks.find((task) => task.id === selectedTaskId) || tasks[0];
}

function chooseDefaultTask(track) {
  const task = latestTaskForTrack(track) || orderedTrackTasks(track)[0] || null;
  selectedTaskId = task?.id || null;
}

function chooseDefaultStandaloneTask() {
  selectedTaskId = standaloneTasks()[0]?.id || null;
}

function applyWorkspaceData(nextWorkspace) {
  const selectedTrackId = selectedStandalone ? null : selectedTrack?.id || null;
  const previousTaskId = selectedTaskId;
  const preserveStandaloneSelection = selectedStandalone;
  workspace = normalizeWorkspaceData(nextWorkspace);
  if (preserveStandaloneSelection) {
    const nextStandaloneTask = standaloneTasks().find((task) => task.id === previousTaskId) || standaloneTasks()[0] || null;
    if (nextStandaloneTask) {
      selectedStandalone = true;
      selectedTrack = null;
      selectedTaskId = nextStandaloneTask.id;
      return;
    }
  }

  selectedTrack = workspace.tracks.find((track) => track.id === selectedTrackId) || workspace.tracks[0] || null;
  selectedStandalone = false;

  if (selectedTrack) {
    const tasks = orderedTrackTasks(selectedTrack);
    selectedTaskId = tasks.some((task) => task.id === previousTaskId) ? previousTaskId : null;
    if (!selectedTaskId) {
      chooseDefaultTask(selectedTrack);
    }
    return;
  }

  const availableStandaloneTasks = standaloneTasks();
  selectedTaskId = availableStandaloneTasks.some((task) => task.id === previousTaskId) ? previousTaskId : null;
  if (!selectedTaskId) {
    chooseDefaultStandaloneTask();
  }
  selectedStandalone = Boolean(selectedTaskId);
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

function renderCommand(parent, command, emphasis = false) {
  if (!command) {
    return;
  }
  const row = createEl("div", emphasis ? "command-row is-primary" : "command-row");
  const code = createEl("code", "command", command);
  const button = createEl("button", "copy-button", "Copy");
  button.type = "button";
  button.addEventListener("click", () => copyText(command, button));
  row.append(code, button);
  parent.append(row);
}

function renderLabeledCommand(parent, label, command, emphasis = false) {
  if (!command) {
    return;
  }
  const block = createEl("div", emphasis ? "named-command is-primary" : "named-command");
  block.append(createEl("span", "command-label", label));
  renderCommand(block, command, emphasis);
  parent.append(block);
}

function renderReadOnlyCommand(parent, label, command) {
  if (!command) {
    return;
  }
  const block = createEl("div", "named-command");
  block.append(createEl("span", "command-label", label), createEl("code", "command", command));
  parent.append(block);
}

function normalizeReferenceSwitches(audit) {
  return audit?.reference_switches && typeof audit.reference_switches === "object"
    ? audit.reference_switches
    : {};
}

function deriveTemplateSwitch(audit, references) {
  if (typeof references.continue_current_task_in_track === "string" && references.continue_current_task_in_track) {
    return references.continue_current_task_in_track;
  }
  if (typeof references.continue_current_task === "string" && references.continue_current_task) {
    return references.continue_current_task;
  }
  const buddy = audit?.buddy || "pm";
  const taskId = audit?.task_id || "task-id";
  if (audit?.track_id) {
    return `switch ${buddy}(${taskId}) -> ${audit.track_id}: <demand>`;
  }
  return `switch ${buddy}(${taskId}): <demand>`;
}

function deriveRecommendedSwitch(audit, references, templateCommand, track) {
  if (typeof audit?.recommended_switch === "string" && audit.recommended_switch.trim()) {
    return audit.recommended_switch.trim();
  }
  const fallbackOrder = [
    references.handoff_to_next_buddy,
    references.continue_current_task_in_track,
    references.continue_current_task,
  ];
  const fromReference = fallbackOrder.find((item) => typeof item === "string" && item);
  if (fromReference) {
    return fromReference;
  }
  if (track?.next_buddy) {
    return `switch ${track.next_buddy} -> ${track.id}: <demand>`;
  }
  if (track?.current_buddy) {
    return `switch ${track.current_buddy} -> ${track.id}: <demand>`;
  }
  return templateCommand || "";
}

function deriveSwitchCommandsForTrack(track) {
  const latestRun = latestRunForTrack(track);
  const references = normalizeReferenceSwitches(latestRun);
  const template = deriveTemplateSwitch(latestRun, references);
  const testCommand = trackNeedsTest(track)
    ? `switch test -> ${track.id}: Run smoke checks for latest implementation`
    : "";
  const recommended = deriveRecommendedSwitch(latestRun, references, template, track);
  return {
    recommended,
    template,
    continueTask: references.continue_current_task || "",
    continueTaskInTrack: references.continue_current_task_in_track || template,
    handoff: references.handoff_to_next_buddy || testCommand || (track?.next_buddy ? `switch ${track.next_buddy} -> ${track.id}: <demand>` : ""),
  };
}

function deriveSwitchCommandsForTask(task) {
  const latestRun = latestRunForTask(task);
  const references = normalizeReferenceSwitches(latestRun);
  const template = deriveTemplateSwitch(latestRun, references);
  return {
    recommended: deriveRecommendedSwitch(latestRun, references, template, null),
    template,
    continueTask: references.continue_current_task || template,
    continueTaskInTrack: references.continue_current_task_in_track || "",
    handoff: references.handoff_to_next_buddy || "",
  };
}

function artifactTitle(artifact) {
  return artifact?.title || artifact?.id || "No material";
}

function artifactSummary(artifact, fallback = "No material summary") {
  return clampText(artifact?.summary || artifact?.content?.task_summary || fallback, 260);
}

function taskArtifactCount(task) {
  return getTaskArtifacts(task).length;
}

function taskRunLabel(task) {
  const latest = getTaskRuns(task)[0];
  return latest?.run_id || task?.latest_run_id || "none";
}

function collectFieldLines(value, prefix = "") {
  if (value === null || value === undefined || value === "") {
    return [];
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return [prefix ? `${prefix}: ${value}` : String(value)];
  }
  if (Array.isArray(value)) {
    return value.flatMap((item) => collectFieldLines(item, prefix));
  }
  if (isObject(value)) {
    if ("command" in value || "result" in value || "notes" in value) {
      const command = value.command ? `${value.command}: ` : "";
      const result = value.result || "";
      const notes = value.notes ? ` - ${value.notes}` : "";
      return [`${prefix ? `${prefix}: ` : ""}${command}${result}${notes}`.trim()];
    }
    if ("title" in value || "summary" in value) {
      const title = value.title || "";
      const summary = value.summary || "";
      return [`${prefix ? `${prefix}: ` : ""}${[title, summary].filter(Boolean).join(" - ")}`.trim()];
    }
    return Object.entries(value).flatMap(([key, item]) => collectFieldLines(item, humanizeKey(key)));
  }
  return [prefix ? `${prefix}: ${safeJson(value)}` : safeJson(value)];
}

function humanizeKey(key) {
  return String(key)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function contentLines(content, keys) {
  return keys.flatMap((key) => collectFieldLines(content?.[key]));
}

function collectKnownLimitations(artifacts) {
  return artifacts.flatMap((artifact) => contentLines(artifact.content || {}, ["known_limitations", "risks", "risks_and_caveats"]));
}

function trackNeedsTest(track) {
  const artifacts = getTrackArtifacts(track);
  const hasDevMaterial = artifacts.some((artifact) => artifact.buddy === "dev");
  const hasTestMaterial = artifacts.some((artifact) => artifact.buddy === "test");
  return hasDevMaterial && !hasTestMaterial;
}

function missingArtifactIds(task) {
  const artifactsById = artifactMap();
  return asArray(task?.artifact_ids).filter((artifactId) => !artifactsById.has(artifactId));
}

function statusNoteForTrack(track) {
  const artifacts = getTrackArtifacts(track);
  if (asArray(track?.missing_task_ids).length > 0) {
    return "missing task reference";
  }
  if (artifacts.length === 0) {
    return "no material yet";
  }
  if (trackNeedsTest(track)) {
    return "needs test";
  }
  if (collectKnownLimitations(artifacts).length > 0) {
    return "has limitations";
  }
  return "ready";
}

function renderKeyValue(parent, key, value) {
  const row = createEl("div", "kv-row");
  row.append(createEl("span", "kv-key", key), createEl("span", "kv-value", value || "none"));
  parent.append(row);
}

function renderPillList(parent, items) {
  const row = createEl("div", "pill-list");
  items.filter(Boolean).forEach((item) => row.append(createEl("span", "pill", item)));
  parent.append(row);
}

function renderTrackButton(track) {
  const button = createEl("button", "topic-button");
  button.type = "button";
  button.classList.toggle("is-active", !selectedStandalone && selectedTrack?.id === track.id);

  const tasks = orderedTrackTasks(track);
  const artifacts = getTrackArtifacts(track);
  const latestTask = latestTaskForTrack(track);
  const latestArtifact = latestArtifactForTrack(track);
  const flow = track.next_buddy
    ? `${buddyLabel(track.current_buddy)} -> ${buddyLabel(track.next_buddy)}`
    : `${buddyLabel(track.current_buddy)} -> no next`;

  button.append(
    createEl("strong", "", track.title || track.id),
    createEl("span", "topic-summary", clampText(track.summary || "No track summary", 110)),
    createEl("span", "topic-meta", `${track.status || "active"} | ${flow} | tasks ${tasks.length} | materials ${artifacts.length}`),
    createEl("span", "topic-meta", `Latest task: ${clampText(latestTask?.title || "none", 90)}`),
    createEl("span", "topic-meta", `Latest material: ${clampText(artifactTitle(latestArtifact), 90)}`),
  );
  renderPillList(button, [statusNoteForTrack(track), track.updated_at || "no timestamp"]);

  button.addEventListener("click", () => {
    selectedStandalone = false;
    selectedTrack = track;
    chooseDefaultTask(track);
    render();
  });
  trackList.append(button);
}

function renderStandaloneTaskButton(task) {
  const button = createEl("button", "topic-button");
  button.type = "button";
  button.classList.toggle("is-active", selectedStandalone && selectedTaskId === task.id);

  const latestRun = latestRunForTask(task);
  const latestArtifact = getTaskArtifacts(task)[0] || null;
  button.append(
    createEl("strong", "", task.title || task.id),
    createEl("span", "topic-summary", clampText(task.summary || "No task summary", 110)),
    createEl("span", "topic-meta", `${buddyLabel(task.buddy)} | ${task.status || "active"} | standalone`),
    createEl("span", "topic-meta", `Latest run: ${latestRun?.run_id || task.latest_run_id || "none"}`),
    createEl("span", "topic-meta", `Latest material: ${clampText(artifactTitle(latestArtifact), 90)}`),
  );
  renderPillList(button, [latestRun?.updated_at || task.updated_at || "no timestamp"]);

  button.addEventListener("click", () => {
    selectedStandalone = true;
    selectedTrack = null;
    selectedTaskId = task.id;
    render();
  });
  trackList.append(button);
}

function renderTracks() {
  trackList.replaceChildren();
  const tracks = workspace.tracks;
  const looseTasks = standaloneTasks();
  setText(trackCount, String(tracks.length + looseTasks.length));

  if (tracks.length === 0 && looseTasks.length === 0) {
    trackList.append(createEl("p", "note", "No work items found. Start with: switch pm: create a track for <project goal>"));
    return;
  }

  if (tracks.length > 0) {
    if (looseTasks.length > 0) {
      trackList.append(createEl("p", "note", "Tracks"));
    }
    tracks.forEach(renderTrackButton);
  } else {
    trackList.append(createEl("p", "note", "No tracks found. Showing standalone tasks below."));
  }

  if (looseTasks.length > 0) {
    if (tracks.length > 0) {
      trackList.append(createEl("p", "note", "Standalone tasks"));
    }
    looseTasks.forEach(renderStandaloneTaskButton);
  }
}

function renderTrackSummary(track) {
  trackSummary.replaceChildren();
  if (!track) {
    trackSummary.append(createEl("p", "note", "No track selected."));
    return;
  }

  const tasks = orderedTrackTasks(track);
  const artifacts = getTrackArtifacts(track);
  const latestRun = latestRunForTrack(track);
  const latestArtifact = latestArtifactForTrack(track);
  const commands = deriveSwitchCommandsForTrack(track);

  renderKeyValue(trackSummary, "Goal", track.summary || "No track summary");
  renderKeyValue(trackSummary, "State", track.status || "active");
  renderKeyValue(trackSummary, "Flow", track.next_buddy ? `${track.current_buddy} -> ${track.next_buddy}` : track.current_buddy);
  renderKeyValue(trackSummary, "Tasks", String(tasks.length));
  renderKeyValue(trackSummary, "Materials", String(artifacts.length));
  renderKeyValue(trackSummary, "Latest run", latestRun?.run_id || "none");
  renderKeyValue(trackSummary, "Latest material", artifactTitle(latestArtifact));
  renderKeyValue(trackSummary, "Next", commands.recommended || "No recommended command available");
}

function renderStandaloneSummary(task) {
  trackSummary.replaceChildren();
  if (!task) {
    trackSummary.append(createEl("p", "note", "No standalone task selected."));
    return;
  }

  const artifacts = getTaskArtifacts(task);
  const latestRun = latestRunForTask(task);
  const latestArtifact = artifacts[0] || null;
  const commands = deriveSwitchCommandsForTask(task);

  renderKeyValue(trackSummary, "Task", task.title || task.id);
  renderKeyValue(trackSummary, "Buddy", buddyLabel(task.buddy));
  renderKeyValue(trackSummary, "State", task.status || "active");
  renderKeyValue(trackSummary, "Materials", String(artifacts.length));
  renderKeyValue(trackSummary, "Latest run", latestRun?.run_id || task.latest_run_id || "none");
  renderKeyValue(trackSummary, "Latest material", artifactTitle(latestArtifact));
  renderKeyValue(trackSummary, "Next", commands.recommended || "No recommended command available");
}

function renderTasks(track) {
  taskList.replaceChildren();
  const tasks = orderedTrackTasks(track);
  setText(selectedTaskCount, String(tasks.length));

  if (!track) {
    taskList.append(createEl("p", "note", "No track selected."));
    return;
  }
  if (tasks.length === 0) {
    taskList.append(createEl("p", "note", "No task objects attached to this track."));
  }

  tasks.forEach((task) => {
    const artifact = getTaskArtifacts(task)[0] || task.latest_artifact || null;
    const button = createEl("button", "task-card");
    button.type = "button";
    button.classList.toggle("is-active", selectedTaskId === task.id);
    button.append(
      createEl("span", "task-eyebrow", `${buddyLabel(task.buddy)} | ${task.status || "active"}`),
      createEl("strong", "", task.title || task.id),
      createEl("code", "task-id", task.id),
      createEl("span", "task-meta", `Updated: ${task.updated_at || "no timestamp"} | Artifacts: ${taskArtifactCount(task)} | Latest run: ${taskRunLabel(task)}`),
      createEl("p", "task-summary line-clamp-2", clampText(task.summary || "No task summary", 220)),
      createEl("span", "task-material", `Latest material: ${artifactTitle(artifact)}`),
      createEl("p", "task-summary line-clamp-2", artifactSummary(artifact, "No material has been persisted for this task yet")),
    );
    button.addEventListener("click", () => {
      selectedStandalone = false;
      selectedTaskId = task.id;
      render();
    });
    taskList.append(button);
  });

  asArray(track.missing_task_ids).forEach((taskId) => {
    const missing = createEl("div", "task-card is-missing");
    missing.append(
      createEl("span", "task-eyebrow", "missing task reference"),
      createEl("strong", "", taskId),
      createEl("p", "task-summary", "This task id is referenced by the track but no task object was found."),
    );
    taskList.append(missing);
  });
}

function renderStandaloneTasks() {
  taskList.replaceChildren();
  const tasks = standaloneTasks();
  setText(selectedTaskCount, String(tasks.length));

  if (tasks.length === 0) {
    taskList.append(createEl("p", "note", "No standalone tasks found."));
    return;
  }

  tasks.forEach((task) => {
    const artifact = getTaskArtifacts(task)[0] || task.latest_artifact || null;
    const button = createEl("button", "task-card");
    button.type = "button";
    button.classList.toggle("is-active", selectedTaskId === task.id);
    button.append(
      createEl("span", "task-eyebrow", `${buddyLabel(task.buddy)} | ${task.status || "active"} | standalone`),
      createEl("strong", "", task.title || task.id),
      createEl("code", "task-id", task.id),
      createEl("span", "task-meta", `Updated: ${task.updated_at || "no timestamp"} | Artifacts: ${taskArtifactCount(task)} | Latest run: ${taskRunLabel(task)}`),
      createEl("p", "task-summary line-clamp-2", clampText(task.summary || "No task summary", 220)),
      createEl("span", "task-material", `Latest material: ${artifactTitle(artifact)}`),
      createEl("p", "task-summary line-clamp-2", artifactSummary(artifact, "No material has been persisted for this task yet")),
    );
    button.addEventListener("click", () => {
      selectedStandalone = true;
      selectedTrack = null;
      selectedTaskId = task.id;
      render();
    });
    taskList.append(button);
  });
}

function appendListSection(parent, title, lines, maxItems = 6) {
  const cleanLines = lines.map((line) => clampText(line, 280)).filter(Boolean);
  if (cleanLines.length === 0) {
    return;
  }
  const section = createEl("section", "material-section");
  section.append(createEl("h4", "", title));
  const list = createEl("ul", "material-list");
  cleanLines.slice(0, maxItems).forEach((line) => list.append(createEl("li", "", line)));
  if (cleanLines.length > maxItems) {
    list.append(createEl("li", "muted-item", `${cleanLines.length - maxItems} more item(s) in source details`));
  }
  section.append(list);
  parent.append(section);
}

function renderArtifactHistory(parent, artifacts) {
  if (artifacts.length === 0) {
    return;
  }
  const section = createEl("section", "material-section");
  section.append(createEl("h4", "", "Artifact History"));
  const list = createEl("div", "compact-stack");
  artifacts.forEach((artifact) => {
    const item = createEl("div", "history-row");
    item.append(
      createEl("strong", "", artifactTitle(artifact)),
      createEl("span", "", `${artifact.skill_id || "unknown skill"} | ${artifact.updated_at || "no timestamp"}`),
    );
    list.append(item);
  });
  section.append(list);
  parent.append(section);
}

function renderRelatedRuns(parent, runs) {
  if (runs.length === 0) {
    return;
  }
  const section = createEl("section", "material-section");
  section.append(createEl("h4", "", "Related Runs"));
  const list = createEl("div", "compact-stack");
  runs.slice(0, 5).forEach((run) => {
    const item = createEl("div", "history-row");
    item.append(
      createEl("strong", "", run.run_id || "run-unknown"),
      createEl("span", "", `${run.buddy || "unknown"} / ${run.skill_id || "unknown"} | ${run.updated_at || "no timestamp"}`),
      createEl("p", "task-summary line-clamp-2", clampText(run.execution_summary || run.demand || "No summary", 180)),
    );
    list.append(item);
  });
  section.append(list);
  parent.append(section);
}

function renderMaterialHighlights(parent, artifact) {
  const content = artifact?.content || {};
  appendListSection(parent, "Problem / Goal", contentLines(content, ["problem", "goals", "research_question", "task_summary"]));
  appendListSection(parent, "Scope / Acceptance", contentLines(content, ["scope_p0_p1", "acceptance_criteria", "non_goals"]));
  appendListSection(parent, "Research", contentLines(content, ["conclusion", "patterns_and_insights", "evidence", "source_traceability", "risks_and_caveats"]));
  appendListSection(parent, "Design", contentLines(content, ["ia", "primary_flows", "key_screens", "state_coverage", "interaction_notes", "open_questions"]));
  appendListSection(parent, "Changed Files", contentLines(content, ["changed_files"]), 12);
  appendListSection(parent, "Implementation Notes", contentLines(content, ["implementation_notes"]));
  appendListSection(parent, "Verification", contentLines(content, ["verification_runs"]));
  appendListSection(parent, "Known Limitations / Risks", contentLines(content, ["known_limitations", "risks"]));
  appendListSection(parent, "Open Questions", contentLines(content, ["open_questions"]));
}

function renderTaskMaterialsForTask(task) {
  taskMaterials.replaceChildren();
  if (!task) {
    taskMaterials.append(createEl("p", "note", "Select a task to inspect its core materials."));
    return;
  }

  const artifacts = getTaskArtifacts(task);
  const latestArtifact = artifacts[0] || null;
  const runs = getTaskRuns(task);

  const header = createEl("div", "material-header");
  header.append(
    createEl("span", "task-eyebrow", `${buddyLabel(task.buddy)} | ${task.status || "active"}`),
    createEl("h4", "", task.title || task.id),
    createEl("code", "task-id", task.id),
    createEl("p", "task-summary", clampText(task.summary || "No task summary", 260)),
  );
  taskMaterials.append(header);

  if (!latestArtifact) {
    taskMaterials.append(createEl("p", "note", "No material has been persisted for this task yet."));
    renderRelatedRuns(taskMaterials, runs);
    return;
  }

  const latest = createEl("section", "material-section is-latest");
  latest.append(
    createEl("h4", "", "Latest Material"),
    createEl("strong", "", artifactTitle(latestArtifact)),
    createEl("p", "task-summary", artifactSummary(latestArtifact)),
    createEl("span", "task-meta", `Source run: ${latestArtifact.source_run_id || "none"}`),
  );
  taskMaterials.append(latest);
  renderMaterialHighlights(taskMaterials, latestArtifact);
  renderArtifactHistory(taskMaterials, artifacts);
  renderRelatedRuns(taskMaterials, runs);
}

function renderTaskMaterials(track) {
  renderTaskMaterialsForTask(selectedTaskForTrack(track));
}

function renderTrackProgress(track) {
  trackProgress.replaceChildren();
  if (!track) {
    trackProgress.append(createEl("p", "note", "No track selected."));
    return;
  }

  const tasks = orderedTrackTasks(track);
  const artifacts = getTrackArtifacts(track);
  const presentBuddies = new Set(tasks.map((task) => task.buddy).filter(Boolean));
  const materialBuddies = new Set(artifacts.map((artifact) => artifact.buddy).filter(Boolean));
  const latestRun = latestRunForTrack(track);
  const limitations = collectKnownLimitations(artifacts);
  const tasksWithoutMaterials = tasks.filter((task) => taskArtifactCount(task) === 0);
  const hasDevMaterial = artifacts.some((artifact) => artifact.buddy === "dev");
  const hasTestMaterial = artifacts.some((artifact) => artifact.buddy === "test");
  const missingMaterials = [];
  const dataIssues = [];

  tasksWithoutMaterials.forEach((task) => missingMaterials.push(`${buddyLabel(task.buddy)} task has no material: ${task.title || task.id}`));
  if (hasDevMaterial && !hasTestMaterial) {
    missingMaterials.push("Latest implementation has not been validated by a test material.");
  }
  asArray(track.missing_task_ids).forEach((taskId) => dataIssues.push(`Missing task object: ${taskId}`));
  tasks.forEach((task) => missingArtifactIds(task).forEach((artifactId) => dataIssues.push(`Missing artifact object: ${artifactId}`)));

  appendListSection(trackProgress, "Buddy Coverage", buddyOrder.map((buddy) => {
    if (presentBuddies.has(buddy) && materialBuddies.has(buddy)) {
      return `${buddyLabel(buddy)}: task and material exist`;
    }
    if (presentBuddies.has(buddy)) {
      return `${buddyLabel(buddy)}: task exists, no material yet`;
    }
    return "";
  }).filter(Boolean), 8);
  appendListSection(trackProgress, "Latest Action", [latestRun?.execution_summary || latestRun?.demand || artifactSummary(latestArtifactForTrack(track), "")]);
  appendListSection(trackProgress, "Needs Attention", missingMaterials);
  appendListSection(trackProgress, "Visible Limitations", limitations);
  appendListSection(trackProgress, "Data Issues", dataIssues);

  if (!trackProgress.children.length) {
    trackProgress.append(createEl("p", "note", "No progress notes available yet."));
  }
}

function renderStandaloneProgress(task) {
  trackProgress.replaceChildren();
  if (!task) {
    trackProgress.append(createEl("p", "note", "No standalone task selected."));
    return;
  }

  const artifacts = getTaskArtifacts(task);
  const latestRun = latestRunForTask(task);
  const latestArtifact = artifacts[0] || null;

  appendListSection(trackProgress, "Latest Action", [latestRun?.execution_summary || latestRun?.demand || task.summary || ""]);
  appendListSection(trackProgress, "Material Snapshot", [artifactSummary(latestArtifact, "No material has been persisted for this task yet")]);
  appendListSection(trackProgress, "Visible Limitations", collectKnownLimitations(artifacts));
  appendListSection(trackProgress, "Data Issues", missingArtifactIds(task).map((artifactId) => `Missing artifact object: ${artifactId}`));

  if (!trackProgress.children.length) {
    trackProgress.append(createEl("p", "note", "No progress notes available yet."));
  }
}

function renderNextCommands(track) {
  switchCommands.replaceChildren();
  if (!track) {
    switchCommands.append(createEl("p", "note", "No track selected."));
    return;
  }

  const commands = deriveSwitchCommandsForTrack(track);
  renderLabeledCommand(switchCommands, "Recommended", commands.recommended, true);
  renderLabeledCommand(switchCommands, "Template", commands.template);
  if (commands.continueTask && commands.continueTask !== commands.template) {
    renderLabeledCommand(switchCommands, "Continue current task", commands.continueTask);
  }
  if (commands.continueTaskInTrack && commands.continueTaskInTrack !== commands.template) {
    renderLabeledCommand(switchCommands, "Continue task in track", commands.continueTaskInTrack);
  }
  if (commands.handoff && commands.handoff !== commands.recommended) {
    renderLabeledCommand(switchCommands, "Handoff", commands.handoff);
  }
}

function renderStandaloneCommands(task) {
  switchCommands.replaceChildren();
  if (!task) {
    switchCommands.append(createEl("p", "note", "No standalone task selected."));
    return;
  }

  const commands = deriveSwitchCommandsForTask(task);
  renderLabeledCommand(switchCommands, "Recommended", commands.recommended, true);
  renderLabeledCommand(switchCommands, "Template", commands.template);
  if (commands.continueTask && commands.continueTask !== commands.template) {
    renderLabeledCommand(switchCommands, "Continue current task", commands.continueTask);
  }
  if (commands.continueTaskInTrack && commands.continueTaskInTrack !== commands.template) {
    renderLabeledCommand(switchCommands, "Continue task in track", commands.continueTaskInTrack);
  }
  if (commands.handoff && commands.handoff !== commands.recommended) {
    renderLabeledCommand(switchCommands, "Handoff", commands.handoff);
  }
}

function formatTaskLabel(audit) {
  const taskId = audit.task_id || "task-unknown";
  const title = clampText(audit.task_title, 80);
  return title ? `${title} [${taskId}]` : `[${taskId}]`;
}

function formatArtifactLabel(audit) {
  const artifactIds = asArray(audit.artifact_ids).filter((item) => typeof item === "string" && item);
  if (artifactIds.length === 0) {
    return "none";
  }
  if (artifactIds.length === 1) {
    return artifactIds[0];
  }
  return `${artifactIds[0]} (+${artifactIds.length - 1} more)`;
}

function renderRunHistory(track) {
  runAuditList.replaceChildren();
  const runs = getTrackRuns(track);
  setText(runAuditCount, String(runs.length));

  if (!track) {
    runAuditList.append(createEl("p", "note", "No track selected."));
    return;
  }
  if (runs.length === 0) {
    runAuditList.append(createEl("p", "note", "No run history for this track."));
    return;
  }

  runs.slice(0, 8).forEach((audit) => {
    const item = createEl("article", "summary-item run-card");
    const references = normalizeReferenceSwitches(audit);
    const template = deriveTemplateSwitch(audit, references);
    const recommended = deriveRecommendedSwitch(audit, references, template, track);
    const header = createEl("div", "run-header");
    header.append(
      createEl("strong", "", `${audit.buddy || "unknown"} / ${audit.skill_id || "unknown"}`),
      createEl("span", "run-time", audit.updated_at || "no timestamp"),
    );
    item.append(
      header,
      createEl("p", "summary-line line-clamp-2", `Demand: ${clampText(audit.demand || "No demand", 180)}`),
      createEl("p", "summary-line line-clamp-2", `Result: ${clampText(audit.execution_summary || audit.status || "No summary", 180)}`),
    );
    const grid = createEl("div", "receipt-grid");
    renderKeyValue(grid, "Persisted", audit.status === "ok" ? "ok" : "failed");
    renderKeyValue(grid, "Task", formatTaskLabel(audit));
    renderKeyValue(grid, "Artifact", formatArtifactLabel(audit));
    renderKeyValue(grid, "Run", audit.run_id || "run-unknown");
    item.append(grid);
    if (recommended) {
      const commandList = createEl("div", "command-list compact-command");
      renderReadOnlyCommand(commandList, "Recommended then", recommended);
      item.append(commandList);
    }
    runAuditList.append(item);
  });
}

function renderRunHistoryForTask(task) {
  runAuditList.replaceChildren();
  const runs = getTaskRuns(task);
  setText(runAuditCount, String(runs.length));

  if (!task) {
    runAuditList.append(createEl("p", "note", "No standalone task selected."));
    return;
  }
  if (runs.length === 0) {
    runAuditList.append(createEl("p", "note", "No run history for this task."));
    return;
  }

  runs.slice(0, 8).forEach((audit) => {
    const item = createEl("article", "summary-item run-card");
    const references = normalizeReferenceSwitches(audit);
    const template = deriveTemplateSwitch(audit, references);
    const recommended = deriveRecommendedSwitch(audit, references, template, null);
    const header = createEl("div", "run-header");
    header.append(
      createEl("strong", "", `${audit.buddy || "unknown"} / ${audit.skill_id || "unknown"}`),
      createEl("span", "run-time", audit.updated_at || "no timestamp"),
    );
    item.append(
      header,
      createEl("p", "summary-line line-clamp-2", `Demand: ${clampText(audit.demand || "No demand", 180)}`),
      createEl("p", "summary-line line-clamp-2", `Result: ${clampText(audit.execution_summary || audit.status || "No summary", 180)}`),
    );
    const grid = createEl("div", "receipt-grid");
    renderKeyValue(grid, "Persisted", audit.status === "ok" ? "ok" : "failed");
    renderKeyValue(grid, "Task", formatTaskLabel(audit));
    renderKeyValue(grid, "Artifact", formatArtifactLabel(audit));
    renderKeyValue(grid, "Run", audit.run_id || "run-unknown");
    item.append(grid);
    if (recommended) {
      const commandList = createEl("div", "command-list compact-command");
      renderReadOnlyCommand(commandList, "Recommended then", recommended);
      item.append(commandList);
    }
    runAuditList.append(item);
  });
}

function cleanupSuggestions(track) {
  const seen = new Set();
  const commands = [];
  orderedTrackTasks(track).forEach((task) => {
    if (task.buddy && !seen.has(task.buddy)) {
      seen.add(task.buddy);
      commands.push(`./buddyswitch-codex data cleanup --buddy ${task.buddy}`);
    }
  });
  commands.push("./buddyswitch-codex data cleanup --all-data");
  commands.push("./buddyswitch-codex data cleanup --app-runtime");
  return commands;
}

function renderSourceDetails(track) {
  sourceDetails.replaceChildren();
  const summary = createEl("summary", "", "Object paths and raw source");
  sourceDetails.append(summary);

  if (!track) {
    sourceDetails.append(createEl("p", "note", "No source details available."));
    return;
  }

  const selectedTask = selectedTaskForTrack(track);
  const selectedArtifacts = selectedTask ? getTaskArtifacts(selectedTask) : [];
  const selectedRuns = selectedTask ? getTaskRuns(selectedTask) : [];
  const sourceGrid = createEl("div", "source-grid");
  renderKeyValue(sourceGrid, "Manifest", workspace.manifest_path || "none");
  renderKeyValue(sourceGrid, "Objects root", workspace.objects_root || "none");
  if (selectedTask) {
    renderKeyValue(sourceGrid, "Task", selectedTask.object_path || "none");
  }
  selectedArtifacts.slice(0, 4).forEach((artifact, index) => {
    renderKeyValue(sourceGrid, `Artifact ${index + 1}`, artifact.object_path || "none");
  });
  selectedRuns.slice(0, 4).forEach((run, index) => {
    renderKeyValue(sourceGrid, `Run ${index + 1}`, run.path || "none");
  });
  sourceDetails.append(sourceGrid);

  const cleanup = createEl("section", "material-section");
  cleanup.append(createEl("h4", "", "Cleanup preview commands"));
  const commandList = createEl("div", "command-list");
  cleanupSuggestions(track).forEach((command) => renderCommand(commandList, command));
  cleanup.append(commandList);
  sourceDetails.append(cleanup);

  const raw = createEl("details", "nested-details");
  raw.append(createEl("summary", "", "Raw selected task material JSON"));
  raw.append(createEl("pre", "artifact-path", safeJson(selectedArtifacts[0]?.content || {})));
  sourceDetails.append(raw);
}

function renderStandaloneSourceDetails(task) {
  sourceDetails.replaceChildren();
  const summary = createEl("summary", "", "Object paths and raw source");
  sourceDetails.append(summary);

  if (!task) {
    sourceDetails.append(createEl("p", "note", "No source details available."));
    return;
  }

  const selectedArtifacts = getTaskArtifacts(task);
  const selectedRuns = getTaskRuns(task);
  const sourceGrid = createEl("div", "source-grid");
  renderKeyValue(sourceGrid, "Manifest", workspace.manifest_path || "none");
  renderKeyValue(sourceGrid, "Objects root", workspace.objects_root || "none");
  renderKeyValue(sourceGrid, "Task", task.object_path || "none");
  selectedArtifacts.slice(0, 4).forEach((artifact, index) => {
    renderKeyValue(sourceGrid, `Artifact ${index + 1}`, artifact.object_path || "none");
  });
  selectedRuns.slice(0, 4).forEach((run, index) => {
    renderKeyValue(sourceGrid, `Run ${index + 1}`, run.path || "none");
  });
  sourceDetails.append(sourceGrid);

  const cleanup = createEl("section", "material-section");
  cleanup.append(createEl("h4", "", "Cleanup preview commands"));
  const commandList = createEl("div", "command-list");
  [
    `./buddyswitch-codex data cleanup --buddy ${task.buddy}`,
    "./buddyswitch-codex data cleanup --all-data",
    "./buddyswitch-codex data cleanup --app-runtime",
  ].forEach((command) => renderCommand(commandList, command));
  cleanup.append(commandList);
  sourceDetails.append(cleanup);

  const raw = createEl("details", "nested-details");
  raw.append(createEl("summary", "", "Raw selected task material JSON"));
  raw.append(createEl("pre", "artifact-path", safeJson(selectedArtifacts[0]?.content || {})));
  sourceDetails.append(raw);
}

function renderSelectedTrack() {
  if (!selectedTrack && !selectedStandaloneTask()) {
    setText(selectedType, "Selected work item");
    setText(topicTitle, "No item");
    setText(topicSlug, "-");
    trackSummary.replaceChildren(createEl("p", "note", "No track or standalone task data available."));
    taskList.replaceChildren(createEl("p", "note", "No task data available."));
    taskMaterials.replaceChildren(createEl("p", "note", "No task selected."));
    trackProgress.replaceChildren(createEl("p", "note", "No progress notes available."));
    switchCommands.replaceChildren();
    runAuditList.replaceChildren(createEl("p", "note", "No run history available."));
    sourceDetails.replaceChildren(createEl("summary", "", "Object paths and raw source"));
    return;
  }

  if (!selectedTrack) {
    const task = selectedStandaloneTask();
    selectedStandalone = Boolean(task);
    selectedTaskId = task?.id || null;
    setText(selectedType, `Standalone Task (${task?.status || "active"})`);
    setText(topicTitle, task?.title || task?.id || "No item");
    setText(topicSlug, task?.id || "-");
    renderStandaloneSummary(task);
    renderStandaloneTasks();
    renderTaskMaterialsForTask(task);
    renderStandaloneProgress(task);
    renderStandaloneCommands(task);
    renderRunHistoryForTask(task);
    renderStandaloneSourceDetails(task);
    return;
  }

  const selectedTask = selectedTaskForTrack(selectedTrack);
  selectedStandalone = false;
  selectedTaskId = selectedTask?.id || null;
  setText(selectedType, `Track (${selectedTrack.status || "active"})`);
  setText(topicTitle, selectedTrack.title || selectedTrack.id);
  setText(topicSlug, selectedTrack.id);
  renderTrackSummary(selectedTrack);
  renderTasks(selectedTrack);
  renderTaskMaterials(selectedTrack);
  renderTrackProgress(selectedTrack);
  renderNextCommands(selectedTrack);
  renderRunHistory(selectedTrack);
  renderSourceDetails(selectedTrack);
}

function renderWorkspaceOverview() {
  setText(generatedAt, workspace.generated_at || "not generated");
  const looseTasks = standaloneTasks().length;
  setText(
    workspaceCounts,
    `Tracks ${workspace.tracks.length} | Standalone ${looseTasks} | Tasks ${workspace.tasks.length} | Artifacts ${workspace.artifacts.length} | Runs ${workspace.run_audits.length}`,
  );
  setText(projectCode, projectCodePath);
}

function render() {
  renderWorkspaceOverview();
  renderTracks();
  renderSelectedTrack();
}

async function workspaceApiError(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
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
      const payload = await workspaceApiError(response);
      if (response.status === 503 && payload?.error === "runtime_snapshot_busy") {
        setDataStatus(payload.message || "Workspace is updating. Retry shortly.", "warning");
        return false;
      }
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
