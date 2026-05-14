#!/usr/bin/env python3
"""Runtime-projected semantic metadata for env.tool registry actions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

MUTATES_NONE = "none"
MUTATES_INSTANCE_BINDING = "instance_binding"
MUTATES_RUNTIME_OBJECTS = "runtime_objects"
MUTATES_RUNTIME_OBJECTS_AND_INSTANCE_BINDING = "runtime_objects+instance_binding"
MUTATES_RUN_COMMIT = "run_commit"
MUTATES_BROKER_TOKEN = "broker_token"
MUTATES_BROWSER_SESSION = "browser_session"

_REQUIRED_RISK_HINTS = {
    "read_only",
    "destructive",
    "idempotent",
    "open_world",
    "requires_human_approval",
    "external_effect",
}
_LOW_SIGNAL_TEXT = {"", "n/a", "na", "none", "use this tool", "use this action", "todo", "tbd"}


def _risk(
    *,
    read_only: bool,
    destructive: bool,
    idempotent: bool | str,
    open_world: bool = False,
    requires_human_approval: bool = False,
    external_effect: bool = False,
) -> dict[str, Any]:
    return {
        "read_only": read_only,
        "destructive": destructive,
        "idempotent": idempotent,
        "open_world": open_world,
        "requires_human_approval": requires_human_approval,
        "external_effect": external_effect,
    }


def _side_effects(
    *,
    mutates: str,
    writes: list[str],
    does_not_write: list[str],
    durability: str,
    idempotency: str,
) -> dict[str, Any]:
    return {
        "mutates": mutates,
        "writes": list(writes),
        "does_not_write": list(does_not_write),
        "durability": durability,
        "idempotency": idempotency,
    }


def _action(
    *,
    title: str,
    plain_description: str,
    use_when: list[str],
    do_not_use_when: list[str],
    inputs_explained: dict[str, str],
    side_effects: dict[str, Any],
    risk_hints: dict[str, Any],
    success_means: str,
    common_failures: list[str],
) -> dict[str, Any]:
    return {
        "title": title,
        "plain_description": plain_description,
        "use_when": list(use_when),
        "do_not_use_when": list(do_not_use_when),
        "inputs_explained": dict(inputs_explained),
        "side_effects": dict(side_effects),
        "risk_hints": dict(risk_hints),
        "success_means": success_means,
        "common_failures": list(common_failures),
    }


CAPABILITY_SEMANTICS: dict[str, dict[str, Any]] = {
    "task": {
        "title": "Task ownership work surface",
        "plain_description": "Manage active-buddy tasks, task selection, and task-level read or write actions inside runtime state.",
        "use_when": [
            "You need to read or update tasks owned by the active buddy.",
            "You need to choose the current task binding for the active instance.",
        ],
        "do_not_use_when": [
            "You need cross-buddy lifecycle control over the track itself.",
            "You need full artifact body reads without first identifying artifact ids.",
        ],
        "capability_boundary": {
            "identity_source": "runtime active buddy plus task ownership and relation checks",
            "authority_source": "manifest permissions and task track-relation checks",
            "raw_state_access": "not exposed; use broker-routed env.tool responses only",
        },
    },
    "track": {
        "title": "Track orientation and lifecycle surface",
        "plain_description": "Read track context, join work on a track, and run PM-owned lifecycle mutations for track coordination.",
        "use_when": [
            "You need to orient on track context, members, and current artifact summaries.",
            "You need to join a track before reading foreign full artifact bodies.",
        ],
        "do_not_use_when": [
            "You only need to mutate a task or artifact directly.",
            "A non-PM buddy tries to mutate PM lifecycle fields.",
        ],
        "capability_boundary": {
            "identity_source": "runtime active buddy and track relation evaluation",
            "authority_source": "manifest permissions plus PM lifecycle ownership enforcement",
            "raw_state_access": "track/task JSON writes stay in service code, not host raw file edits",
        },
    },
    "artifact": {
        "title": "Artifact read and revision surface",
        "plain_description": "List artifact summaries, read full artifact bodies when allowed, and create new artifact revisions for active work.",
        "use_when": [
            "You need full artifact content after relation or ownership checks pass.",
            "You need to validate or create a new artifact revision from prepared run work.",
        ],
        "do_not_use_when": [
            "You only need task or track orientation summaries.",
            "You want to mutate foreign buddy artifacts directly.",
        ],
        "capability_boundary": {
            "identity_source": "artifact ownership and track relation checks",
            "authority_source": "manifest artifact permissions plus source run validation",
            "raw_state_access": "artifact writes happen through env services only",
        },
    },
    "context": {
        "title": "Runtime context snapshot surface",
        "plain_description": "Read active instance context sections, summaries, and source descriptors for host decision making.",
        "use_when": [
            "You need current binding, task context, and track context in one snapshot.",
            "You need compact orientation before choosing the next mutation action.",
        ],
        "do_not_use_when": [
            "You need full foreign artifact body content directly.",
            "You need to mutate runtime state objects.",
        ],
        "capability_boundary": {
            "identity_source": "active launcher instance and active buddy context",
            "authority_source": "prepare context validation and active instance binding checks",
            "raw_state_access": "read-only context projection; no object writes",
        },
    },
    "binding": {
        "title": "Instance binding selector",
        "plain_description": "Read or mutate launcher instance current task and track bindings without editing task or track content.",
        "use_when": [
            "You need to set or clear current task and track pointers for the active instance.",
            "You need to inspect current binding state before other tool calls.",
        ],
        "do_not_use_when": [
            "You need to modify task or track fields themselves.",
            "You need PM lifecycle changes on tracks.",
        ],
        "capability_boundary": {
            "identity_source": "active launcher instance binding state",
            "authority_source": "task ownership checks and PM-only standalone track binding",
            "raw_state_access": "only instance json binding keys are mutated",
        },
    },
    "handoff": {
        "title": "Explicit handoff record surface",
        "plain_description": "List, validate, and create handoff records that document cross-buddy continuation intent and source artifacts.",
        "use_when": [
            "You need an explicit handoff record for downstream buddy discoverability.",
            "You need to validate handoff payload fields before commit.",
        ],
        "do_not_use_when": [
            "You need to mutate track lifecycle status directly.",
            "You need to write artifact revisions instead of handoff metadata.",
        ],
        "capability_boundary": {
            "identity_source": "active buddy source task ownership and target buddy manifest ids",
            "authority_source": "handoff payload validation plus task/track relation checks",
            "raw_state_access": "writes only handoff record objects, not lifecycle fields",
        },
    },
    "run": {
        "title": "Run audit validation and commit surface",
        "plain_description": "Validate persist payloads, commit durable run audits, and read committed run receipt or raw run content.",
        "use_when": [
            "You need to validate result payload before durable commit.",
            "You need committed run receipts or raw run audits for traceability.",
        ],
        "do_not_use_when": [
            "You need to mutate task, track, or artifact state directly.",
            "You need browser evidence token issuance.",
        ],
        "capability_boundary": {
            "identity_source": "prepared run context revision and active instance reservation",
            "authority_source": "persist context validation and run reservation checks",
            "raw_state_access": "writes run audit records only through commit service",
        },
    },
    "evidence": {
        "title": "Market evidence token issuance",
        "plain_description": "Issue broker-scoped browser evidence or approved downgrade tokens for artifact-producing market persist flows.",
        "use_when": [
            "You need browser cockpit evidence token before market artifact-producing commit.",
            "The user explicitly approves a non-browser downgrade with a reason.",
        ],
        "do_not_use_when": [
            "Prepared context is stale or mismatched with active instance.",
            "You only need run validation or commit without evidence requirements.",
        ],
        "capability_boundary": {
            "identity_source": "prepared context run identity and active instance/browser readiness",
            "authority_source": "market evidence profile and runtime preflight validation",
            "raw_state_access": "writes scoped token files only, never task/track/artifact objects",
        },
    },
    "search": {
        "title": "Search boundary and browser launch surface",
        "plain_description": "Expose search capability boundary, optional request planning, and browser session opening for open-world discovery.",
        "use_when": [
            "You need to inspect available search backends and browser readiness.",
            "You need to open a browser search page for open-world research.",
        ],
        "do_not_use_when": [
            "You need trusted BuddySwitch-owned state updates.",
            "You need native Codex web search directly inside this runtime.",
        ],
        "capability_boundary": {
            "identity_source": "active env profile search boundary and instance browser endpoint",
            "authority_source": "profile capability flags and backend/browser availability checks",
            "raw_state_access": "only browser session side effects; no BuddySwitch object writes",
        },
    },
}

ACTION_SEMANTICS: dict[str, dict[str, Any]] = {
    "task.create": _action(
        title="Create active-buddy task",
        plain_description="Create a new task object owned by the active buddy and return task summary plus current binding snapshot.",
        use_when=[
            "No existing active-buddy task matches the work you need to perform.",
            "You need a durable task object before creating artifacts or run audits.",
        ],
        do_not_use_when=[
            "You only need to read existing task context.",
            "You need to select an existing task as current binding without creating one.",
        ],
        inputs_explained={
            "title": "Required non-empty task title saved in the task object.",
            "summary": "Optional task summary text stored as task context.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_RUNTIME_OBJECTS,
            writes=["task object record"],
            does_not_write=["instance binding unless caller sets it later", "track lifecycle fields"],
            durability="runtime_object",
            idempotency="Not idempotent for auto ids; explicit duplicate task_id is rejected.",
        ),
        risk_hints=_risk(read_only=False, destructive=False, idempotent=False),
        success_means="A new active-buddy task record is persisted and returned as the next mutable work container.",
        common_failures=[
            "Missing task.create permission for the active buddy.",
            "title or explicit task_id payload fails validation.",
        ],
    ),
    "task.list": _action(
        title="List readable tasks",
        plain_description="Return task summaries readable by active buddy ownership or track relation without reading full artifact content.",
        use_when=[
            "You need candidate task ids before selecting or reading one task.",
            "You need relation-aware task orientation without state mutation.",
        ],
        do_not_use_when=[
            "You already know the task id and need one specific record.",
            "You need full artifact body content directly from an artifact id.",
        ],
        inputs_explained={},
        side_effects=_side_effects(
            mutates=MUTATES_NONE,
            writes=[],
            does_not_write=["task objects", "instance binding", "artifact content"],
            durability="none",
            idempotency="Idempotent read over current runtime snapshot.",
        ),
        risk_hints=_risk(read_only=True, destructive=False, idempotent=True),
        success_means="Readable task summaries are returned with relation context and no state mutation.",
        common_failures=[
            "Missing task.read permission for active buddy.",
            "Unexpected payload fields are rejected.",
        ],
    ),
    "task.get": _action(
        title="Read one task summary",
        plain_description="Read one task summary by task id when ownership or readable track relation allows access.",
        use_when=[
            "You need full task summary fields and relation flags for one task id.",
            "You need artifact ids from task summary before calling artifact.get.",
        ],
        do_not_use_when=[
            "You need to mutate task fields.",
            "You need full artifact body content instead of task summary.",
        ],
        inputs_explained={
            "task_id": "Required task id to load and relation-check before read.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_NONE,
            writes=[],
            does_not_write=["task objects", "instance binding", "artifact content"],
            durability="none",
            idempotency="Idempotent read for the same task id and unchanged state.",
        ),
        risk_hints=_risk(read_only=True, destructive=False, idempotent=True),
        success_means="Task summary is returned with relation context and guidance for artifact.get when full body is needed.",
        common_failures=[
            "task_id is missing, invalid, or not found.",
            "Active buddy lacks ownership or readable track relation.",
        ],
    ),
    "task.get_current": _action(
        title="Read current bound task",
        plain_description="Read the task currently selected in instance binding, or return no-current-binding state without mutation.",
        use_when=[
            "You need to know whether the instance currently points to an active-buddy task.",
            "You need the currently selected task before update or artifact actions.",
        ],
        do_not_use_when=[
            "You need to switch binding selection.",
            "You need to read another task id directly.",
        ],
        inputs_explained={},
        side_effects=_side_effects(
            mutates=MUTATES_NONE,
            writes=[],
            does_not_write=["task objects", "instance binding"],
            durability="none",
            idempotency="Idempotent read of instance binding plus task lookup.",
        ),
        risk_hints=_risk(read_only=True, destructive=False, idempotent=True),
        success_means="Current task summary or explicit unbound result is returned without changing runtime state.",
        common_failures=[
            "Missing task.read permission for active buddy.",
            "Binding points to missing or foreign task id.",
        ],
    ),
    "task.set_current": _action(
        title="Bind current task",
        plain_description="Set instance current task and derived track binding to an active-buddy owned task id.",
        use_when=[
            "You need to switch active instance focus to a specific owned task.",
            "Subsequent context or artifact actions should default to that task.",
        ],
        do_not_use_when=[
            "You need to mutate task title, summary, or status fields.",
            "The target task is not owned by active buddy.",
        ],
        inputs_explained={
            "task_id": "Required active-buddy task id that becomes current binding.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_INSTANCE_BINDING,
            writes=["instance binding current_task_id/current_track_id"],
            does_not_write=["task content fields", "track lifecycle fields"],
            durability="instance_binding",
            idempotency="Idempotent when binding already points to the same task id.",
        ),
        risk_hints=_risk(read_only=False, destructive=False, idempotent=True),
        success_means="Active instance binding now points to the selected task and its track reference.",
        common_failures=[
            "Missing task.update permission for active buddy.",
            "task_id is missing, invalid, missing, or foreign owned.",
        ],
    ),
    "task.update": _action(
        title="Update owned task fields",
        plain_description="Patch title, summary, or status on an active-buddy owned task object.",
        use_when=[
            "You need to change task metadata or status on owned work.",
            "You need to close or refine task context before handoff or run commit.",
        ],
        do_not_use_when=[
            "You only need to switch current binding.",
            "You need PM track lifecycle mutation rather than task metadata update.",
        ],
        inputs_explained={
            "task_id": "Required owned task id to update.",
            "title": "Optional non-empty replacement title.",
            "summary": "Optional replacement summary string.",
            "status": "Optional new status within allowed task lifecycle values.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_RUNTIME_OBJECTS,
            writes=["task object mutable fields"],
            does_not_write=["instance binding unless set_current is called", "artifact body content"],
            durability="runtime_object",
            idempotency="Idempotent when patch values equal persisted values.",
        ),
        risk_hints=_risk(read_only=False, destructive=False, idempotent=True),
        success_means="Owned task fields are persisted and returned with updated summary metadata.",
        common_failures=[
            "Missing task.update permission for active buddy.",
            "Patch payload lacks valid mutable fields or references foreign task.",
        ],
    ),
    "task.archive": _action(
        title="Archive owned task",
        plain_description="Mark an active-buddy owned task status as archived without deleting the task record.",
        use_when=[
            "The active buddy has completed or retired a task and needs closure.",
            "You need archived status for audit while preserving task history.",
        ],
        do_not_use_when=[
            "You need hard deletion of task data.",
            "Task ownership validation does not pass for active buddy.",
        ],
        inputs_explained={
            "task_id": "Required owned task id to archive.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_RUNTIME_OBJECTS,
            writes=["task status field set to archived"],
            does_not_write=["task record deletion", "instance binding unless changed elsewhere"],
            durability="runtime_object",
            idempotency="Idempotent when task status is already archived.",
        ),
        risk_hints=_risk(read_only=False, destructive=False, idempotent=True),
        success_means="Task status is archived in runtime object state while history remains readable.",
        common_failures=[
            "Missing task.archive permission for active buddy.",
            "task_id is invalid, missing, missing in state, or foreign owned.",
        ],
    ),
    "track.list": _action(
        title="List readable tracks",
        plain_description="Return readable track summaries, relation context, and deterministic candidate order for host orientation.",
        use_when=[
            "You need to discover candidate tracks before reading one in detail.",
            "You need relation-aware orientation for direct source intake decisions.",
        ],
        do_not_use_when=[
            "You already know the target track id for detailed context.",
            "You need to mutate track lifecycle or task linkage directly.",
        ],
        inputs_explained={},
        side_effects=_side_effects(
            mutates=MUTATES_NONE,
            writes=[],
            does_not_write=["track objects", "task objects", "instance binding"],
            durability="none",
            idempotency="Idempotent read over current track state.",
        ),
        risk_hints=_risk(read_only=True, destructive=False, idempotent=True),
        success_means="Track summaries and relation hints are returned without changing lifecycle or membership state.",
        common_failures=[
            "Missing track.read permission for active buddy.",
            "Unexpected payload fields are rejected.",
        ],
    ),
    "track.get": _action(
        title="Read one track context",
        plain_description="Read one track summary and context including current artifact summary rows and relation hints.",
        use_when=[
            "You need current artifact ids and relation context for a specific track.",
            "You need to decide whether track.join is required before artifact.get.",
        ],
        do_not_use_when=[
            "You need to mutate track lifecycle fields.",
            "You need full artifact body content directly without artifact.get.",
        ],
        inputs_explained={
            "track_id": "Required track id to inspect track context and readable artifacts.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_NONE,
            writes=[],
            does_not_write=["track lifecycle", "task membership", "artifact content"],
            durability="none",
            idempotency="Idempotent read of a specific track id.",
        ),
        risk_hints=_risk(read_only=True, destructive=False, idempotent=True),
        success_means="Track context summary is returned and points to follow-up actions for join or artifact full-body reads.",
        common_failures=[
            "track_id is missing, invalid, or not found.",
            "Missing track.read permission for active buddy.",
        ],
    ),
    "track.join": _action(
        title="Join track with active-buddy task",
        plain_description="Create or select one active-buddy task for a track, then bind instance current task and track to it.",
        use_when=[
            "artifact.get is blocked by missing relation and active buddy must join track first.",
            "You need active-buddy task linkage to continue work on a track.",
        ],
        do_not_use_when=[
            "Track is archived or lifecycle-closed.",
            "Multiple candidate tasks exist but task_id is omitted.",
        ],
        inputs_explained={
            "track_id": "Required track id to join for active-buddy participation.",
            "task_id": "Optional active-buddy task id to reuse instead of automatic creation.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_RUNTIME_OBJECTS_AND_INSTANCE_BINDING,
            writes=["task-track linkage", "instance binding current_task_id/current_track_id"],
            does_not_write=["track lifecycle status/current_buddy/next_buddy", "foreign task ownership"],
            durability="runtime_object+instance_binding",
            idempotency="Partially idempotent when same task relation and binding already exist.",
        ),
        risk_hints=_risk(read_only=False, destructive=False, idempotent=False),
        success_means="Active buddy is linked to the track through an owned task and current binding is updated for next actions.",
        common_failures=[
            "track_id is missing, invalid, not found, or archived.",
            "task_id is foreign, archived, or ambiguous join requires explicit selection.",
        ],
    ),
    "track.get_current": _action(
        title="Read current bound track",
        plain_description="Read track currently bound in instance state or return explicit unbound current-track result.",
        use_when=[
            "You need to verify whether a track is currently selected.",
            "You need current track details before relation-sensitive artifact actions.",
        ],
        do_not_use_when=[
            "You need to choose a different track binding.",
            "You need to mutate track lifecycle.",
        ],
        inputs_explained={},
        side_effects=_side_effects(
            mutates=MUTATES_NONE,
            writes=[],
            does_not_write=["instance binding", "track objects"],
            durability="none",
            idempotency="Idempotent read of current binding and track lookup.",
        ),
        risk_hints=_risk(read_only=True, destructive=False, idempotent=True),
        success_means="Current track details or unbound state is returned without mutating runtime state.",
        common_failures=[
            "Missing track.read permission for active buddy.",
            "Binding references missing track id.",
        ],
    ),
    "track.create": _action(
        title="Create track lifecycle record",
        plain_description="Create a new track object and initialize PM-managed lifecycle fields.",
        use_when=[
            "PM starts a new coordination track for cross-buddy work.",
            "No existing track id should be reused for the initiative.",
        ],
        do_not_use_when=[
            "Active buddy is not PM lifecycle authority.",
            "You only need to join an existing track.",
        ],
        inputs_explained={
            "track_id": "Optional explicit track id; auto-generated when omitted.",
            "title": "Required non-empty track title.",
            "status": "Optional lifecycle status constrained to valid track statuses.",
            "current_buddy": "Optional current owner buddy id, defaulting to pm.",
            "next_buddy": "Optional next buddy target in lifecycle direction.",
            "summary": "Optional track summary context text.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_RUNTIME_OBJECTS,
            writes=["track object lifecycle and metadata fields"],
            does_not_write=["task linkage unless join/attach actions are used", "instance binding"],
            durability="runtime_object",
            idempotency="Not idempotent for auto-generated ids; duplicate explicit track_id is rejected.",
        ),
        risk_hints=_risk(read_only=False, destructive=False, idempotent=False),
        success_means="A new PM-owned track lifecycle record is persisted and available for relation-based work.",
        common_failures=[
            "Active buddy is not PM or lacks track.create permission.",
            "Payload title, buddy refs, status, or explicit track_id fails validation.",
        ],
    ),
    "track.update": _action(
        title="Update track lifecycle fields",
        plain_description="Patch PM-managed track lifecycle fields such as status, owners, and summary metadata.",
        use_when=[
            "PM needs to revise track lifecycle metadata without advancing to a new track.",
            "Track exists and requires field-level updates.",
        ],
        do_not_use_when=[
            "Active buddy is non-PM and should only perform task/artifact work.",
            "You need task membership updates rather than lifecycle metadata updates.",
        ],
        inputs_explained={
            "track_id": "Required track id to mutate.",
            "title": "Optional new track title.",
            "status": "Optional lifecycle status update.",
            "current_buddy": "Optional lifecycle current buddy update.",
            "next_buddy": "Optional lifecycle next buddy update.",
            "summary": "Optional summary update.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_RUNTIME_OBJECTS,
            writes=["track lifecycle metadata fields"],
            does_not_write=["task objects", "instance binding", "artifact objects"],
            durability="runtime_object",
            idempotency="Idempotent when patch values match current persisted values.",
        ),
        risk_hints=_risk(read_only=False, destructive=False, idempotent=True),
        success_means="Track lifecycle fields are updated by PM authority and visible to all readers.",
        common_failures=[
            "Non-PM lifecycle authority or missing track.update permission.",
            "track_id missing/not found or patch fields invalid.",
        ],
    ),
    "track.advance": _action(
        title="Advance track lifecycle",
        plain_description="Advance PM-owned track lifecycle fields toward next step ownership and status progression.",
        use_when=[
            "PM needs to move a track to the next lifecycle phase or buddy.",
            "Lifecycle transition should be durable before downstream work.",
        ],
        do_not_use_when=[
            "Active buddy is not PM lifecycle authority.",
            "You only need to attach or detach tasks from a track.",
        ],
        inputs_explained={
            "track_id": "Required track id to advance.",
            "status": "Optional next lifecycle status value.",
            "current_buddy": "Optional new lifecycle owner buddy.",
            "next_buddy": "Optional next lifecycle target buddy.",
            "summary": "Optional transition summary note.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_RUNTIME_OBJECTS,
            writes=["track lifecycle transition fields"],
            does_not_write=["task membership", "instance binding"],
            durability="runtime_object",
            idempotency="Idempotent only when requested transition matches current persisted values.",
        ),
        risk_hints=_risk(read_only=False, destructive=False, idempotent=False),
        success_means="Track lifecycle transition is committed and next-buddy coordination context is updated.",
        common_failures=[
            "Non-PM lifecycle authority or missing track.advance permission.",
            "track_id missing/not found or transition fields invalid.",
        ],
    ),
    "track.archive": _action(
        title="Archive track lifecycle",
        plain_description="Set track lifecycle status to archived while keeping the track record readable for history.",
        use_when=[
            "PM closes a coordination track and preserves historical context.",
            "No further active lifecycle updates should occur on this track.",
        ],
        do_not_use_when=[
            "You need hard deletion of a track record.",
            "Active buddy is not PM lifecycle authority.",
        ],
        inputs_explained={
            "track_id": "Required track id to archive.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_RUNTIME_OBJECTS,
            writes=["track status field set to archived"],
            does_not_write=["track deletion", "task content and artifact content"],
            durability="runtime_object",
            idempotency="Idempotent when track already archived.",
        ),
        risk_hints=_risk(read_only=False, destructive=False, idempotent=True),
        success_means="Track is marked archived and remains available for read-only historical orientation.",
        common_failures=[
            "Non-PM lifecycle authority or missing track.archive permission.",
            "track_id is missing, invalid, or not found.",
        ],
    ),
    "track.attach_task": _action(
        title="Attach owned task to track",
        plain_description="Attach an active-buddy owned task to a track for participation without changing lifecycle ownership fields.",
        use_when=[
            "You need to link owned task membership to an existing track.",
            "A task currently has no track relation and should join track context.",
        ],
        do_not_use_when=[
            "Task already belongs to another track and detach flow was not completed.",
            "You need PM lifecycle updates rather than membership linkage.",
        ],
        inputs_explained={
            "track_id": "Required track id to attach the task to.",
            "task_id": "Required active-buddy task id to attach.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_RUNTIME_OBJECTS,
            writes=["task track_id linkage", "track task_ids membership list"],
            does_not_write=["track lifecycle current_buddy/next_buddy/status", "instance binding"],
            durability="runtime_object",
            idempotency="Idempotent when task is already attached to the same track.",
        ),
        risk_hints=_risk(read_only=False, destructive=False, idempotent=True),
        success_means="Task membership now includes the selected track while lifecycle ownership remains unchanged.",
        common_failures=[
            "task_id or track_id is missing/not found/foreign owned.",
            "Task is already bound to a different track.",
        ],
    ),
    "track.detach_task": _action(
        title="Detach owned task from track",
        plain_description="Detach an active-buddy owned task from a track membership relation without touching track lifecycle fields.",
        use_when=[
            "A task should no longer participate in a track.",
            "You need to free a task for relinking elsewhere.",
        ],
        do_not_use_when=[
            "You need to archive the entire track lifecycle.",
            "The task is foreign owned or not linked to target track.",
        ],
        inputs_explained={
            "track_id": "Required track id from which to detach.",
            "task_id": "Required active-buddy task id to detach.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_RUNTIME_OBJECTS,
            writes=["task track_id unlink or track task_ids membership removal"],
            does_not_write=["track lifecycle fields", "instance binding"],
            durability="runtime_object",
            idempotency="Idempotent when task is already detached from the specified track.",
        ),
        risk_hints=_risk(read_only=False, destructive=False, idempotent=True),
        success_means="Task membership relation is removed while track lifecycle state remains untouched.",
        common_failures=[
            "task_id or track_id is missing/not found/foreign owned.",
            "Task linkage points to another track and cannot be detached here.",
        ],
    ),
    "artifact.list": _action(
        title="List track current artifact summaries",
        plain_description="List summary rows for current artifacts in a track and include readability hints for active buddy.",
        use_when=[
            "You need candidate artifact ids before full-body artifact.get reads.",
            "You need summary-only orientation across track artifacts.",
        ],
        do_not_use_when=[
            "You need full artifact content body.",
            "track_id is unknown and should be discovered via track.list first.",
        ],
        inputs_explained={
            "track_id": "Required track id for summary artifact listing.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_NONE,
            writes=[],
            does_not_write=["artifact content", "track objects", "instance binding"],
            durability="none",
            idempotency="Idempotent read for the same track snapshot.",
        ),
        risk_hints=_risk(read_only=True, destructive=False, idempotent=True),
        success_means="Summary rows of track current artifacts are returned with no full-body leakage and no state mutation.",
        common_failures=[
            "track_id missing, invalid, or track not found.",
            "Missing artifact.read permission for active buddy.",
        ],
    ),
    "artifact.get": _action(
        title="Read full artifact body",
        plain_description="Read full artifact record and content only when ownership or readable track relation permits access.",
        use_when=[
            "You need full artifact content for downstream implementation or analysis.",
            "You already have an artifact id from track/task context.",
        ],
        do_not_use_when=[
            "Relation checks fail and track.join or handoff context is required.",
            "You only need artifact summary rows.",
        ],
        inputs_explained={
            "artifact_id": "Required artifact id to relation-check and read.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_NONE,
            writes=[],
            does_not_write=["artifact objects", "task objects", "instance binding"],
            durability="none",
            idempotency="Idempotent read when artifact and relation state are unchanged.",
        ),
        risk_hints=_risk(read_only=True, destructive=False, idempotent=True),
        success_means="Full artifact body is returned for allowed relation and no runtime state is changed.",
        common_failures=[
            "artifact_id missing/invalid/not found.",
            "Artifact relation is blocked and no-leak rejection guidance is returned.",
        ],
    ),
    "artifact.get_current": _action(
        title="Read current artifacts for bound task",
        plain_description="Read current artifact revisions for the active bound task, optionally filtered by artifact kind.",
        use_when=[
            "You need the current artifact set for the active bound task.",
            "You need quick task-local artifact inspection by kind.",
        ],
        do_not_use_when=[
            "No current task binding exists and task must be selected first.",
            "You need cross-track artifact discovery without task binding.",
        ],
        inputs_explained={
            "kind": "Optional artifact kind filter for current task artifact slots.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_NONE,
            writes=[],
            does_not_write=["artifact objects", "instance binding", "task fields"],
            durability="none",
            idempotency="Idempotent read from current task artifact slots.",
        ),
        risk_hints=_risk(read_only=True, destructive=False, idempotent=True),
        success_means="Current task artifact rows are returned or an explicit empty/binding-missing result appears without mutation.",
        common_failures=[
            "Missing artifact.read permission for active buddy.",
            "kind filter is invalid or current binding points to missing/foreign task.",
        ],
    ),
    "artifact.validate_payload": _action(
        title="Validate artifact create payload",
        plain_description="Validate and normalize artifact create payload fields without writing artifact revisions.",
        use_when=[
            "You want validation-only safety before artifact.create_revision.",
            "You need normalized ids and source_run checks before write.",
        ],
        do_not_use_when=[
            "You intend to persist a new artifact revision now.",
            "Active task ownership or source_run checks are unresolved.",
        ],
        inputs_explained={
            "artifact_id": "Optional explicit artifact id; autogenerated when omitted.",
            "task_id": "Required active-buddy task id for artifact ownership.",
            "kind": "Required allowed artifact kind for active buddy profile.",
            "title": "Required non-empty artifact title.",
            "summary": "Required summary string describing artifact revision.",
            "content": "Required object body for artifact content.",
            "source_run_id": "Required run id proving source run reservation or prior run lineage.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_NONE,
            writes=[],
            does_not_write=["artifact objects", "task slots", "instance binding"],
            durability="none",
            idempotency="Idempotent validation over identical payload and state.",
        ),
        risk_hints=_risk(read_only=True, destructive=False, idempotent=True),
        success_means="Payload is validated and normalized for artifact.create_revision with no state mutation.",
        common_failures=[
            "Payload fields fail id, type, or required checks.",
            "task ownership, artifact kind, or source_run validation fails.",
        ],
    ),
    "artifact.create_revision": _action(
        title="Create artifact revision",
        plain_description="Persist a new artifact revision and promote it as current for the target task and artifact kind.",
        use_when=[
            "Payload is validated and you are ready to write the artifact revision.",
            "You need durable artifact output linked to source run evidence.",
        ],
        do_not_use_when=[
            "You only need payload validation without writes.",
            "Source task ownership or source_run validation is not satisfied.",
        ],
        inputs_explained={
            "artifact_id": "Optional explicit artifact id; autogenerated when omitted.",
            "task_id": "Required active-buddy task id receiving the revision.",
            "kind": "Required allowed artifact kind for active buddy.",
            "title": "Required non-empty artifact title.",
            "summary": "Required artifact summary text.",
            "content": "Required artifact body object to persist.",
            "source_run_id": "Required run id referencing valid run lineage.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_RUNTIME_OBJECTS,
            writes=["artifact revision object", "task artifact slot current revision pointer"],
            does_not_write=["instance binding", "track lifecycle fields"],
            durability="runtime_object",
            idempotency="Not idempotent for generated artifact ids; duplicate explicit ids are rejected.",
        ),
        risk_hints=_risk(read_only=False, destructive=False, idempotent=False),
        success_means="New artifact revision is persisted and becomes current for its task kind slot.",
        common_failures=[
            "Payload normalization or source_run validation fails.",
            "Missing artifact.create permission or foreign task ownership.",
        ],
    ),
    "artifact.update_metadata": _action(
        title="Update artifact metadata only",
        plain_description="Update artifact title or summary metadata for an owned artifact while preserving artifact content body.",
        use_when=[
            "You need to refine metadata labels without creating new content revision.",
            "You need to update source_run linkage with metadata patch.",
        ],
        do_not_use_when=[
            "You need to replace artifact content body.",
            "Artifact is not owned by active buddy task scope.",
        ],
        inputs_explained={
            "artifact_id": "Required owned artifact id to patch.",
            "title": "Optional non-empty replacement title.",
            "summary": "Optional replacement summary string.",
            "source_run_id": "Required validated source run id for metadata update audit trail.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_RUNTIME_OBJECTS,
            writes=["artifact metadata fields"],
            does_not_write=["artifact content body", "task current slot pointers"],
            durability="runtime_object",
            idempotency="Idempotent when metadata patch values are unchanged.",
        ),
        risk_hints=_risk(read_only=False, destructive=False, idempotent=True),
        success_means="Artifact metadata fields are persisted while content body remains unchanged.",
        common_failures=[
            "artifact_id missing/not found/foreign owned.",
            "title or summary patch invalid, or source_run validation fails.",
        ],
    ),
    "context.get": _action(
        title="Read full runtime context snapshot",
        plain_description="Return current binding, task context, track context, and decision surface for active instance orientation.",
        use_when=[
            "You need complete active runtime context snapshot before mutations.",
            "You need to verify supplied prepare context matches active instance.",
        ],
        do_not_use_when=[
            "You only need compact summary output.",
            "You need direct full foreign artifact body reads.",
        ],
        inputs_explained={
            "context": "Optional prepare payload to validate against active instance before returning context.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_NONE,
            writes=[],
            does_not_write=["task/track/artifact objects", "instance binding"],
            durability="none",
            idempotency="Idempotent read for identical active runtime state.",
        ),
        risk_hints=_risk(read_only=True, destructive=False, idempotent=True),
        success_means="Full current context sections are returned and no runtime state is mutated.",
        common_failures=[
            "Supplied context payload shape is invalid.",
            "Supplied context revision or instance identity mismatches active runtime state.",
        ],
    ),
    "context.summarize": _action(
        title="Read compact context summary",
        plain_description="Return compact current context summary plus decision surface and candidate track hints.",
        use_when=[
            "You need quick orientation before selecting a next action.",
            "You need candidate tracks when binding is missing or relation is weak.",
        ],
        do_not_use_when=[
            "You need full task or track context sections.",
            "You need to mutate binding or object state.",
        ],
        inputs_explained={},
        side_effects=_side_effects(
            mutates=MUTATES_NONE,
            writes=[],
            does_not_write=["runtime objects", "instance binding"],
            durability="none",
            idempotency="Idempotent read projection of current runtime state.",
        ),
        risk_hints=_risk(read_only=True, destructive=False, idempotent=True),
        success_means="Compact summary is returned for host planning and no state mutation occurs.",
        common_failures=[
            "Unexpected payload fields are rejected.",
            "Context projection dependency fails due invalid runtime data.",
        ],
    ),
    "context.list_sources": _action(
        title="List context source descriptors",
        plain_description="Return source descriptor surface that explains where context sections and decisions come from.",
        use_when=[
            "You need to understand context section boundaries before reading full context.",
            "You need source-level hints for task, track, and artifact discovery.",
        ],
        do_not_use_when=[
            "You need full context values immediately.",
            "You need to modify runtime state.",
        ],
        inputs_explained={},
        side_effects=_side_effects(
            mutates=MUTATES_NONE,
            writes=[],
            does_not_write=["runtime objects", "instance binding"],
            durability="none",
            idempotency="Idempotent source descriptor read.",
        ),
        risk_hints=_risk(read_only=True, destructive=False, idempotent=True),
        success_means="Source descriptors for context sections are returned and no runtime state changes.",
        common_failures=[
            "Unexpected payload fields are rejected.",
            "Context descriptor construction fails due invalid runtime state.",
        ],
    ),
    "binding.get": _action(
        title="Read instance binding",
        plain_description="Read current task and track binding pointers for the active launcher instance.",
        use_when=[
            "You need to inspect current binding before task or track scoped actions.",
            "You need to verify a previous binding mutation effect.",
        ],
        do_not_use_when=[
            "You need to mutate task or track objects.",
            "You need to switch binding selection.",
        ],
        inputs_explained={},
        side_effects=_side_effects(
            mutates=MUTATES_NONE,
            writes=[],
            does_not_write=["instance binding", "task/track/artifact objects"],
            durability="none",
            idempotency="Idempotent read of instance binding pointers.",
        ),
        risk_hints=_risk(read_only=True, destructive=False, idempotent=True),
        success_means="Current instance binding pointers are returned without mutating runtime state.",
        common_failures=[
            "Unexpected payload fields are rejected.",
            "Runtime instance payload cannot be read.",
        ],
    ),
    "binding.set_task": _action(
        title="Bind instance to owned task",
        plain_description="Set current task and derived track binding in active instance using an active-buddy owned task id.",
        use_when=[
            "You need to focus active instance on one owned task.",
            "Context and artifact actions should default to that task.",
        ],
        do_not_use_when=[
            "Task is foreign owned or missing.",
            "You need to mutate task content fields.",
        ],
        inputs_explained={
            "task_id": "Required active-buddy owned task id for instance binding.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_INSTANCE_BINDING,
            writes=["instance binding current_task_id/current_track_id"],
            does_not_write=["task content fields", "track lifecycle fields"],
            durability="instance_binding",
            idempotency="Idempotent when binding already points to the same task.",
        ),
        risk_hints=_risk(read_only=False, destructive=False, idempotent=True),
        success_means="Instance binding now points to the selected owned task and its track relation.",
        common_failures=[
            "task_id missing, invalid, not found, or foreign owned.",
            "Unexpected payload fields are rejected.",
        ],
    ),
    "binding.set_track": _action(
        title="Bind instance to PM track",
        plain_description="Set standalone current track binding when active buddy is PM lifecycle authority.",
        use_when=[
            "PM needs track-only binding without selecting a task.",
            "Track context must be inspected before assigning task work.",
        ],
        do_not_use_when=[
            "Active buddy is non-PM and lacks track binding authority.",
            "You need task-bound track derivation via binding.set_task.",
        ],
        inputs_explained={
            "track_id": "Required track id to bind as current track.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_INSTANCE_BINDING,
            writes=["instance binding current_track_id and clear current_task_id"],
            does_not_write=["track lifecycle fields", "task objects"],
            durability="instance_binding",
            idempotency="Idempotent when current track binding already matches.",
        ),
        risk_hints=_risk(read_only=False, destructive=False, idempotent=True),
        success_means="Instance track binding is updated by PM authority and task pointer is cleared.",
        common_failures=[
            "track_id is missing, invalid, or not found.",
            "Active buddy is not PM lifecycle authority.",
        ],
    ),
    "binding.clear": _action(
        title="Clear instance binding",
        plain_description="Clear current task and track pointers from active instance binding without deleting any runtime objects.",
        use_when=[
            "You need to reset binding before selecting new work.",
            "Current binding is stale and should be explicitly cleared.",
        ],
        do_not_use_when=[
            "You need to archive or delete tasks and tracks.",
            "You only need to inspect current binding state.",
        ],
        inputs_explained={},
        side_effects=_side_effects(
            mutates=MUTATES_INSTANCE_BINDING,
            writes=["instance binding current_task_id/current_track_id set to null"],
            does_not_write=["task objects", "track objects", "artifact objects"],
            durability="instance_binding",
            idempotency="Idempotent when binding is already clear.",
        ),
        risk_hints=_risk(read_only=False, destructive=False, idempotent=True),
        success_means="Instance binding is cleared and runtime objects remain unchanged.",
        common_failures=[
            "Unexpected payload fields are rejected.",
            "Runtime instance payload write fails.",
        ],
    ),
    "handoff.list": _action(
        title="List handoff records",
        plain_description="List explicit handoff records and recent run-audit handoff signals for one track or all tracks.",
        use_when=[
            "You need to inspect handoff discoverability and recipient authorization context.",
            "You need to verify handoff visibility after create or run commit.",
        ],
        do_not_use_when=[
            "You need to create or validate a new handoff payload.",
            "You need to mutate track lifecycle state.",
        ],
        inputs_explained={
            "track_id": "Optional track filter for handoff records and recent run-audit handoff rows.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_NONE,
            writes=[],
            does_not_write=["handoff records", "track lifecycle", "instance binding"],
            durability="none",
            idempotency="Idempotent read over current handoff and run-audit state.",
        ),
        risk_hints=_risk(read_only=True, destructive=False, idempotent=True),
        success_means="Handoff discovery rows are returned and no runtime objects are mutated.",
        common_failures=[
            "track_id parse fails when provided.",
            "Unexpected payload fields are rejected.",
        ],
    ),
    "handoff.validate": _action(
        title="Validate handoff payload",
        plain_description="Validate a handoff payload for source ownership, target buddy, and artifact scope without writing handoff records.",
        use_when=[
            "You need a validation-only check before handoff.create.",
            "You need confidence that source task/run/artifact references are consistent.",
        ],
        do_not_use_when=[
            "You are ready to persist handoff record now.",
            "Payload includes forbidden lifecycle mutation fields.",
        ],
        inputs_explained={
            "track_id": "Optional when bound; required if binding lacks track id.",
            "source_task_id": "Required active-buddy source task id.",
            "source_run_id": "Required run id associated with source work.",
            "target_buddy": "Required manifest buddy id receiving the handoff.",
            "next_buddy": "Optional alias for target buddy when provided.",
            "artifact_ids": "Required list of source artifacts for recipient context.",
            "historical_artifact_ids": "Optional list marking artifact_ids that are not current revisions.",
            "reason": "Required non-empty handoff reason text.",
            "context": "Required non-empty handoff context text.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_NONE,
            writes=[],
            does_not_write=["handoff records", "track lifecycle fields", "artifact objects"],
            durability="none",
            idempotency="Idempotent validation for same payload and state.",
        ),
        risk_hints=_risk(read_only=True, destructive=False, idempotent=True),
        success_means="Handoff payload is validated and returned with alignment details, without writing state.",
        common_failures=[
            "Missing required handoff fields or invalid ids.",
            "Source task ownership, artifact scope, or target buddy validation fails.",
        ],
    ),
    "handoff.create": _action(
        title="Create handoff record",
        plain_description="Persist an explicit handoff record for downstream buddy discoverability without mutating track lifecycle status.",
        use_when=[
            "Validated handoff payload should become durable handoff record now.",
            "You need explicit handoff visibility independent from run commit metadata.",
        ],
        do_not_use_when=[
            "You only need validation-only checks.",
            "Payload attempts lifecycle mutation fields instead of handoff metadata.",
        ],
        inputs_explained={
            "track_id": "Optional when bound; otherwise required target track id.",
            "source_task_id": "Required active-buddy source task id.",
            "source_run_id": "Required source run id for handoff traceability.",
            "target_buddy": "Required manifest buddy id receiving handoff.",
            "next_buddy": "Optional alias for target buddy.",
            "artifact_ids": "Required source artifact id list owned by source task.",
            "historical_artifact_ids": "Optional marker list for superseded source artifacts.",
            "reason": "Required handoff reason text persisted in record.",
            "context": "Required context summary text persisted in record.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_RUNTIME_OBJECTS,
            writes=["handoff record object"],
            does_not_write=["track lifecycle status/current_buddy/next_buddy", "artifact content"],
            durability="runtime_object",
            idempotency="Not idempotent; each call writes a new handoff record id.",
        ),
        risk_hints=_risk(read_only=False, destructive=False, idempotent=False),
        success_means="A new explicit handoff record is persisted and discoverable via handoff/track surfaces.",
        common_failures=[
            "Validation rules from handoff.validate fail for payload or scope.",
            "Forbidden lifecycle mutation fields are present.",
        ],
    ),
    "run.commit": _action(
        title="Commit durable run audit",
        plain_description="Persist a durable run audit receipt from prepared context and result payload after validation passes.",
        use_when=[
            "You are ready to commit prepared result into durable run audit state.",
            "Validation checks have passed and artifact/handoff references are final.",
        ],
        do_not_use_when=[
            "You only need validation-only dry run.",
            "Prepared context is stale, mismatched, or reservation is already consumed.",
        ],
        inputs_explained={
            "context": "Required prepared context object including run identity and revision.",
            "result": "Required persist result payload for run audit commit.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_RUN_COMMIT,
            writes=["run audit content record", "run reservation clear side effect when present"],
            does_not_write=["raw task/track/artifact state directly outside sanctioned persist path"],
            durability="run_commit",
            idempotency="Idempotent only for same run_id plus matching idempotency key and result hash.",
        ),
        risk_hints=_risk(read_only=False, destructive=False, idempotent=False),
        success_means="Run audit receipt is durably committed and can be read through receipt/raw run endpoints.",
        common_failures=[
            "context or result payload is missing or malformed.",
            "Prepared context revision/reservation validation fails before commit.",
        ],
    ),
    "run.get_receipt": _action(
        title="Read committed run receipt",
        plain_description="Read receipt view of a committed run audit for active buddy run id scope.",
        use_when=[
            "You need compact run receipt fields rather than full raw run body.",
            "You need durable audit confirmation after run.commit.",
        ],
        do_not_use_when=[
            "You need full raw run payload.",
            "run_id belongs to another buddy scope.",
        ],
        inputs_explained={
            "run_id": "Required committed run id to load receipt fields.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_NONE,
            writes=[],
            does_not_write=["run audit records", "runtime objects"],
            durability="none",
            idempotency="Idempotent read for same committed run id.",
        ),
        risk_hints=_risk(read_only=True, destructive=False, idempotent=True),
        success_means="Run receipt fields are returned without mutating any runtime state.",
        common_failures=[
            "run_id missing, invalid, or not found.",
            "run belongs to different buddy and scope check fails.",
        ],
    ),
    "run.get_raw": _action(
        title="Read committed raw run",
        plain_description="Read full raw run audit content for a committed run id within active buddy ownership scope.",
        use_when=[
            "You need full run audit payload instead of compact receipt.",
            "You need to inspect detailed persisted fields for debugging or traceability.",
        ],
        do_not_use_when=[
            "A compact receipt is enough.",
            "run_id is unknown or owned by another buddy.",
        ],
        inputs_explained={
            "run_id": "Required committed run id to load full raw run payload.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_NONE,
            writes=[],
            does_not_write=["run audit records", "runtime objects"],
            durability="none",
            idempotency="Idempotent read for same committed run id.",
        ),
        risk_hints=_risk(read_only=True, destructive=False, idempotent=True),
        success_means="Full raw run audit content is returned and no state mutation occurs.",
        common_failures=[
            "run_id missing, invalid, or not found.",
            "run belongs to different buddy and scope check fails.",
        ],
    ),
    "run.validate_result": _action(
        title="Validate run result payload",
        plain_description="Validate prepared context and result payload semantics without committing run audit state.",
        use_when=[
            "You need pre-commit validation for run.persist semantics.",
            "You need assurance that handoff/artifact/metadata fields satisfy policy checks.",
        ],
        do_not_use_when=[
            "You are ready for durable commit now.",
            "Prepared context is stale and must be refreshed first.",
        ],
        inputs_explained={
            "context": "Required prepared context object for validation.",
            "result": "Required result object to validate against runtime rules.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_NONE,
            writes=[],
            does_not_write=["run audit records", "task/track/artifact objects"],
            durability="none",
            idempotency="Idempotent validation for same context and result.",
        ),
        risk_hints=_risk(read_only=True, destructive=False, idempotent=True),
        success_means="Run result payload is validated and ready for run.commit without any state write.",
        common_failures=[
            "context or result payload missing or malformed.",
            "prepared context, reservation, or boundary validation fails.",
        ],
    ),
    "evidence.issue_browser": _action(
        title="Issue browser evidence token",
        plain_description="Issue broker-backed browser cockpit evidence token for a validated market prepared context.",
        use_when=[
            "Market artifact-producing persist needs browser evidence token.",
            "Browser cockpit readiness and prepared context validation both pass.",
        ],
        do_not_use_when=[
            "Prepared context is stale or mismatched with active instance.",
            "Browser cockpit endpoint is unavailable or not ready.",
        ],
        inputs_explained={
            "context": "Required successful prepare payload matching active instance and buddy.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_BROKER_TOKEN,
            writes=["evidence token file scoped by run id and context revision"],
            does_not_write=["task/track/artifact runtime objects", "run commit records"],
            durability="broker_token",
            idempotency="Not idempotent; each issuance creates a distinct token id.",
        ),
        risk_hints=_risk(read_only=False, destructive=False, idempotent=False, external_effect=False),
        success_means="Browser evidence token is issued and can be attached to the next artifact-producing run commit payload.",
        common_failures=[
            "context payload missing or validation against active instance fails.",
            "Browser endpoint or ready-page preflight check fails.",
        ],
    ),
    "evidence.approve_downgrade": _action(
        title="Issue approved downgrade token",
        plain_description="Issue explicit approved-downgrade evidence token when user approves non-browser fallback with reason.",
        use_when=[
            "User explicitly approves downgrade path with clear reason.",
            "Market flow requires documented fallback token for persist.",
        ],
        do_not_use_when=[
            "Reason is missing or empty.",
            "Prepared context identity does not match active instance state.",
        ],
        inputs_explained={
            "context": "Required successful prepare payload matching active runtime identity.",
            "reason": "Required non-empty user-approved downgrade reason.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_BROKER_TOKEN,
            writes=["approved downgrade token file scoped by run identity"],
            does_not_write=["task/track/artifact runtime objects", "run commit records"],
            durability="broker_token",
            idempotency="Not idempotent; each approved downgrade issuance returns unique token.",
        ),
        risk_hints=_risk(
            read_only=False,
            destructive=False,
            idempotent=False,
            external_effect=False,
            requires_human_approval=True,
        ),
        success_means="Approved downgrade token is issued with explicit reason for controlled fallback persist usage.",
        common_failures=[
            "reason is missing or empty.",
            "context validation or market evidence profile checks fail.",
        ],
    ),
    "search.status": _action(
        title="Read search capability status",
        plain_description="Read search backend capability boundary, backend availability, and browser endpoint status without mutation.",
        use_when=[
            "You need to choose search backend before request or open_browser actions.",
            "You need visibility into browser and search_api availability boundaries.",
        ],
        do_not_use_when=[
            "You already know target query and need browser open action.",
            "You need to mutate BuddySwitch runtime objects.",
        ],
        inputs_explained={},
        side_effects=_side_effects(
            mutates=MUTATES_NONE,
            writes=[],
            does_not_write=["BuddySwitch runtime objects", "browser session pages"],
            durability="none",
            idempotency="Idempotent read of profile and backend status.",
        ),
        risk_hints=_risk(read_only=True, destructive=False, idempotent=True, open_world=False, external_effect=False),
        success_means="Search capability boundary and backend status are returned with no runtime state mutation.",
        common_failures=[
            "Search profile loading fails due invalid env profile configuration.",
            "Unexpected payload fields are rejected.",
        ],
    ),
    "search.request": _action(
        title="Plan search request boundary",
        plain_description="Validate explicit backend and query, then return browser/search_api request plan without opening browser page.",
        use_when=[
            "You need query planning and boundary validation before open_browser.",
            "You need explicit backend choice without hidden backend selection.",
        ],
        do_not_use_when=[
            "You need immediate browser page open side effect.",
            "Backend, query, or engine payload is missing or unsupported.",
        ],
        inputs_explained={
            "query": "Required non-empty search query string.",
            "backend": "Required explicit backend name from supported backend list.",
            "engine": "Optional search engine selector, defaulting to google.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_NONE,
            writes=[],
            does_not_write=["BuddySwitch runtime objects", "browser session pages"],
            durability="none",
            idempotency="Idempotent planning output for same inputs and boundary state.",
        ),
        risk_hints=_risk(read_only=True, destructive=False, idempotent=True, open_world=True, external_effect=True),
        success_means="Search request plan is returned with target URL and backend boundary, and no state is mutated.",
        common_failures=[
            "backend or engine is unsupported, or query is empty.",
            "search_api backend is unavailable or user-approved-only without approval path.",
        ],
    ),
    "search.open_browser": _action(
        title="Open browser search page",
        plain_description="Open a search result URL in launcher-managed browser session for open-world research and evidence capture.",
        use_when=[
            "You need browser session side effect to inspect web search results.",
            "Browser endpoint is available and query/engine payload is valid.",
        ],
        do_not_use_when=[
            "Browser endpoint is unavailable or readiness checks fail.",
            "You only need boundary planning without opening a page.",
        ],
        inputs_explained={
            "query": "Required non-empty search query string.",
            "engine": "Optional supported search engine, defaulting to google.",
        },
        side_effects=_side_effects(
            mutates=MUTATES_BROWSER_SESSION,
            writes=["browser session new page target"],
            does_not_write=["BuddySwitch runtime objects", "task/track/artifact state"],
            durability="browser_session",
            idempotency="Not idempotent; each call may open additional browser pages.",
        ),
        risk_hints=_risk(read_only=False, destructive=False, idempotent=False, open_world=True, external_effect=True),
        success_means="Search URL is opened in browser session and host can continue with cockpit page operations.",
        common_failures=[
            "query or engine payload is invalid.",
            "Browser endpoint unavailable or page-open call fails.",
        ],
    ),
}

def _is_low_signal_text(value: Any) -> bool:
    if not isinstance(value, str):
        return True
    stripped = value.strip()
    if not stripped:
        return True
    if stripped.lower() in _LOW_SIGNAL_TEXT:
        return True
    return False


def _append_text_error(errors: list[str], *, value: Any, field_label: str, min_len: int = 1) -> None:
    if _is_low_signal_text(value):
        errors.append(f"{field_label} must be non-empty and high-signal")
        return
    assert isinstance(value, str)
    if len(value.strip()) < min_len:
        errors.append(f"{field_label} must have at least {min_len} chars")


def semantic_coverage_errors(tool_registry: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    known_tools: set[str] = set()
    known_actions: dict[str, set[str]] = {}

    for tool_spec in tool_registry:
        tool = tool_spec.get("tool")
        if not isinstance(tool, str) or not tool:
            errors.append("registry contains tool with missing tool id")
            continue
        known_tools.add(tool)
        action_names: set[str] = set()
        for action_spec in tool_spec.get("actions", []):
            action = action_spec.get("name")
            if isinstance(action, str) and action:
                action_names.add(action)
        known_actions[tool] = action_names

    for tool in sorted(known_tools):
        cap = CAPABILITY_SEMANTICS.get(tool)
        if not isinstance(cap, dict):
            errors.append(f"missing capability semantics for tool {tool}")
            continue
        for field in ("title", "plain_description", "use_when", "do_not_use_when", "capability_boundary"):
            if field not in cap:
                errors.append(f"tool {tool} missing capability field {field}")
        _append_text_error(errors, value=cap.get("title"), field_label=f"{tool}.title")
        _append_text_error(errors, value=cap.get("plain_description"), field_label=f"{tool}.plain_description", min_len=12)
        if not isinstance(cap.get("use_when"), list) or not cap.get("use_when"):
            errors.append(f"tool {tool} use_when must be non-empty list")
        if not isinstance(cap.get("do_not_use_when"), list) or not cap.get("do_not_use_when"):
            errors.append(f"tool {tool} do_not_use_when must be non-empty list")
        boundary = cap.get("capability_boundary")
        if not isinstance(boundary, dict):
            errors.append(f"tool {tool} capability_boundary must be object")
        else:
            for key in ("identity_source", "authority_source", "raw_state_access"):
                _append_text_error(errors, value=boundary.get(key), field_label=f"{tool}.capability_boundary.{key}")

    for tool, actions in sorted(known_actions.items()):
        for action in sorted(actions):
            key = f"{tool}.{action}"
            action_spec = next(
                row
                for row in tool_registry
                if row.get("tool") == tool
                for candidate in row.get("actions", [])
                if candidate.get("name") == action
                for row in [candidate]
            )
            semantic = ACTION_SEMANTICS.get(key)
            if not isinstance(semantic, dict):
                errors.append(f"missing action semantics for {key}")
                continue
            for field in (
                "title",
                "plain_description",
                "use_when",
                "do_not_use_when",
                "inputs_explained",
                "side_effects",
                "risk_hints",
                "success_means",
                "common_failures",
            ):
                if field not in semantic:
                    errors.append(f"{key} missing field {field}")
            _append_text_error(errors, value=semantic.get("title"), field_label=f"{key}.title")
            _append_text_error(
                errors,
                value=semantic.get("plain_description"),
                field_label=f"{key}.plain_description",
                min_len=12,
            )
            _append_text_error(errors, value=semantic.get("success_means"), field_label=f"{key}.success_means", min_len=12)

            inputs = semantic.get("inputs_explained")
            if not isinstance(inputs, dict):
                errors.append(f"{key} inputs_explained must be object")
                inputs = {}
            payload_fields = action_spec.get("payload_fields") or []
            if not isinstance(payload_fields, list):
                payload_fields = []
            payload_field_set = {field for field in payload_fields if isinstance(field, str)}
            if set(inputs) != payload_field_set:
                errors.append(f"{key} inputs_explained keys must match payload_fields")
            for field_name, text in inputs.items():
                _append_text_error(errors, value=text, field_label=f"{key}.inputs_explained.{field_name}")
                if isinstance(text, str) and text.strip().lower() in {field_name.lower(), key.lower(), action.lower()}:
                    errors.append(f"{key}.inputs_explained.{field_name} must explain field meaning")

            side_effects = semantic.get("side_effects")
            if not isinstance(side_effects, dict):
                errors.append(f"{key} side_effects must be object")
                side_effects = {}
            writes = side_effects.get("writes")
            does_not_write = side_effects.get("does_not_write")
            if not isinstance(writes, list):
                errors.append(f"{key} side_effects.writes must be list")
                writes = []
            if not isinstance(does_not_write, list):
                errors.append(f"{key} side_effects.does_not_write must be list")
                does_not_write = []
            if side_effects.get("mutates") != action_spec.get("mutates"):
                errors.append(f"{key} side_effects.mutates must match registry mutates")
            if side_effects.get("mutates") == MUTATES_NONE:
                if writes:
                    errors.append(f"{key} read-only action cannot declare writes")
            else:
                if not writes:
                    errors.append(f"{key} mutating action must declare writes")
                if not does_not_write:
                    errors.append(f"{key} mutating action must declare does_not_write scope")

            risk = semantic.get("risk_hints")
            if not isinstance(risk, dict):
                errors.append(f"{key} risk_hints must be object")
                risk = {}
            missing_risk = _REQUIRED_RISK_HINTS - set(risk)
            if missing_risk:
                errors.append(f"{key} risk_hints missing keys: {', '.join(sorted(missing_risk))}")
            mutates = action_spec.get("mutates")
            read_only = risk.get("read_only")
            if mutates == MUTATES_NONE and read_only is not True:
                errors.append(f"{key} read action must set risk_hints.read_only=true")
            if mutates != MUTATES_NONE and read_only is not False:
                errors.append(f"{key} mutating action must set risk_hints.read_only=false")

            failures = semantic.get("common_failures")
            if not isinstance(failures, list) or not failures:
                errors.append(f"{key} common_failures must be non-empty list")
            elif any(_is_low_signal_text(row) for row in failures):
                errors.append(f"{key} common_failures entries must be high-signal")

    unknown_tools = sorted(set(CAPABILITY_SEMANTICS) - known_tools)
    for tool in unknown_tools:
        errors.append(f"capability semantics declared for unknown tool {tool}")

    known_action_keys = {f"{tool}.{action}" for tool, actions in known_actions.items() for action in actions}
    unknown_actions = sorted(set(ACTION_SEMANTICS) - known_action_keys)
    for key in unknown_actions:
        errors.append(f"action semantics declared for unknown action {key}")

    return errors


def capability_semantics(tool: str) -> dict[str, Any]:
    row = CAPABILITY_SEMANTICS.get(tool)
    return deepcopy(row) if isinstance(row, dict) else {}


def action_semantics(tool: str, action: str) -> dict[str, Any]:
    row = ACTION_SEMANTICS.get(f"{tool}.{action}")
    return deepcopy(row) if isinstance(row, dict) else {}
