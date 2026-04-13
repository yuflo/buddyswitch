# BuddySwitch Object Model V2

## Status

- Date: 2026-04-14
- Status: Draft
- Scope: `track`, `task`, `artifact`, and `run` object semantics for BuddySwitch v2

## 1. Goal

BuddySwitch v2 keeps the same four canonical object types:

- `track`
- `task`
- `artifact`
- `run`

The refactor goal is not to invent more object types. The goal is to make existing objects carry explicit lifecycle semantics instead of relying on implicit conventions.

The most important change is the artifact lifecycle model.

## 2. Problems In The Current Model

The current model uses these conventions:

- `task.artifact_ids`
- `task.latest_artifact_id`
- new artifact creation on every write
- implicit versioning through id suffixes such as `-2`, `-3`

This is adequate for a low-volume MVP, but it breaks down as soon as the same task produces multiple revisions of the same artifact kind.

The current model cannot clearly answer:

- which artifact is the current PRD for this task
- whether a new artifact replaced an old one or sits next to it
- whether a consumer should read one artifact or multiple artifacts
- whether two artifacts are revisions of the same output slot or two distinct deliverables

## 3. Core Decision

BuddySwitch v2 moves to explicit artifact slot and revision semantics.

### 3.1 Artifact Slot

Each artifact belongs to exactly one `slot`.

A slot represents the role of the artifact inside a task. Typical slots:

- `prd`
- `design-spec`
- `implementation-report`
- `test-report`
- `research-report`

Slots are stable semantic buckets, not display labels.

### 3.2 Artifact Revision

Each artifact belongs to a revision chain inside its slot.

Each new write to the same slot creates a new revision, not a parallel artifact.

### 3.3 Current Artifact

For each `task + slot`, there must be exactly one current artifact.

That current artifact is the authoritative artifact for downstream reading and selection unless a workflow explicitly asks for historical comparison.

## 4. Target Object Semantics

## 4.1 Track

`track` remains the orchestration object.

It continues to own:

- cross-task progression
- current and next buddy semantics
- grouped product iteration scope

No artifact revision semantics should live on the track.

Track stays lightweight.

## 4.2 Task

`task` remains the execution container for one buddy-owned unit of work.

Task keeps:

- `id`
- `buddy`
- `title`
- `status`
- `track_id`
- `run_ids`
- `latest_run_id`
- `summary`
- `created_at`
- `updated_at`

Task changes:

- keep `artifact_ids`
- retire `latest_artifact_id`
- add `artifact_slots`

`artifact_slots` is the task-level index for current artifact authority.

Recommended shape:

```json
{
  "artifact_slots": {
    "prd": {
      "current_artifact_id": "art-task-pm-onboarding-prd-r3",
      "revision_count": 3
    },
    "design-spec": {
      "current_artifact_id": "art-task-design-onboarding-spec-r2",
      "revision_count": 2
    }
  }
}
```

This keeps current-by-slot lookup on the task object without inventing a new persistent object type.

## 4.3 Artifact

Artifact becomes the primary lifecycle object.

Required fields:

- `id`
- `task_id`
- `buddy`
- `skill_id`
- `title`
- `slot`
- `revision`
- `supersedes_artifact_id`
- `is_current`
- `source_run_id`
- `summary`
- `content`
- `created_at`
- `updated_at`

Rules:

1. `slot` is required.
2. `revision` is an integer and starts at `1`.
3. `supersedes_artifact_id` is null for the first revision and points to the previous revision otherwise.
4. `is_current` is true only for the newest revision in the slot.
5. Creating a new revision must flip the previous current artifact in the same slot to `is_current = false`.
6. Artifacts from different slots do not supersede each other.

Recommended shape:

```json
{
  "id": "art-task-pm-onboarding-prd-r3",
  "task_id": "task-pm-onboarding",
  "buddy": "pm",
  "skill_id": "write-prd",
  "title": "PM write-prd - onboarding revision 3",
  "slot": "prd",
  "revision": 3,
  "supersedes_artifact_id": "art-task-pm-onboarding-prd-r2",
  "is_current": true,
  "source_run_id": "run-pm-onboarding-003",
  "summary": "Current onboarding PRD with finalized scope and dev-ready acceptance criteria.",
  "content": {},
  "created_at": "2026-04-14T10:00:00+08:00",
  "updated_at": "2026-04-14T10:00:00+08:00"
}
```

## 4.4 Run

`run` remains the audit record for one execution.

Run keeps:

- invocation context
- selected `skill_id`
- execution summary
- open questions
- persisted task/track/artifact ids
- deterministic command templates from runtime

Run should not be the source of artifact lifecycle truth.

Run records what happened.
Artifact records what now exists.

## 5. Lifecycle Rules

## 5.1 New Task

When a new task is created:

- `artifact_ids` starts empty
- `artifact_slots` starts empty
- first artifact written to a slot becomes revision `1`

## 5.2 Revision Write

When a skill writes to a slot that already exists on the task:

1. read current artifact for that slot from `task.artifact_slots`
2. create a new artifact with `revision = previous.revision + 1`
3. set `supersedes_artifact_id = previous.id`
4. set previous `is_current = false`
5. set new artifact `is_current = true`
6. update task slot pointer to the new current artifact

## 5.3 Parallel Outputs

Parallel outputs are allowed only across different slots.

Examples:

- PRD and design spec may coexist
- implementation report and test report may coexist

Parallel outputs are not allowed within one slot.

If work is “another version of the PRD”, it must be a revision, not a new sibling artifact.

## 6. Naming

Artifact ids should stop using generic collision-based suffix semantics as the primary version signal.

Preferred direction:

- include slot in the id
- include revision in the id

Example:

- `art-task-pm-onboarding-prd-r1`
- `art-task-pm-onboarding-prd-r2`

The important rule is not the exact string format. The important rule is that revision must be an explicit field and not inferred only from the id.

## 7. Selection Consequences

This model changes downstream behavior:

- default read path becomes “read current artifact by slot”
- workflow can optionally request previous revision for comparison
- UI can group artifacts by slot and show revision chains explicitly
- handoff can point to slot authority instead of latest-created artifact

This is the key reason to do the refactor.

Without it, runtime and UI both keep paying interpretation costs.

## 8. Forward-Only Rules

- Do not preserve `latest_artifact_id`.
- Do not keep old and new artifact lifecycle semantics in parallel.
- Do not build migration scaffolding for historical suffix-based artifacts.
- Do not introduce a separate persistent artifact index object.

Historical artifacts may remain on disk, but BuddySwitch v2 runtime should only operate on the v2 semantics once the refactor lands.
