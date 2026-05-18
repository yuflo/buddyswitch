# Artifact Collaboration Page Code Implementation Plan

> **For agentic workers:** Implement this plan task-by-task with failing tests first. Do not implement a content platform, asset registry, media lifecycle, Figma replacement, block tree, workflow engine, permission engine, or template-driven automation.

**Goal:** Rebuild artifacts into track-published Markdown content pages with independent comments, resolved threads, revisions, and current published artifacts as the default track shared materials.

**Architecture:** Store artifacts as small durable Markdown page envelopes. Track shared materials are derived from current published artifacts, not from task relations. Tasks stay active-buddy private execution objects. Comments stay separate durable collaboration objects around tracks, artifacts, and artifact sections.

**Tech Stack:** Python env store/services/tools, broker-routed `env.tool`, Python CLI, TOML manifest, JSON schemas/contracts/projections, Markdown runtime skills/contracts, pytest/unittest.

---

## 1. Source Inputs

Read these before implementation:

- `AGENTS.md`
- `docs/memo/2026-05-18-artifact-mini-object-design-memo.md`
- Existing relevant plans:
  - `docs/spec/2026-05-14-track-task-artifact-tooling-upgrade-implementation-plan.md`
  - `docs/spec/2026-05-14-track-task-artifact-tooling-upgrade-test-plan.md`
  - `docs/spec/2026-05-17-track-collaboration-cleanup-code-implementation-plan.md`
  - `docs/spec/2026-05-17-track-collaboration-cleanup-test-plan.md`
  - `docs/spec/2026-05-17-buddy-collaboration-message-comment-code-implementation-plan.md`
  - `docs/spec/2026-05-17-buddy-collaboration-message-comment-test-plan.md`
  - `docs/spec/2026-05-17-comment-derived-relations-code-and-test-implementation-plan.md`
  - `docs/spec/2026-05-17-track-task-role-rebuild-implementation-plan.md`
  - `docs/spec/2026-05-17-track-task-role-rebuild-test-plan.md`

Current implementation to inspect and modify:

- Store/model: `scripts/env_store.py`, `scripts/env/services/source_refs.py`
- Env services: `scripts/env/services/artifacts.py`, `scripts/env/services/artifact_visibility.py`, `scripts/env/services/tracks.py`, `scripts/env/services/tasks.py`, `scripts/env/services/comments.py`, `scripts/env/services/context.py`
- Tool layer: `scripts/env/tools/contracts.py`, `scripts/env/tools/semantics.py`, `scripts/env/tools/dispatch.py`, `scripts/env/tools/router.py`, `scripts/env/tools/responses.py`, `scripts/env/client.py`
- Runtime/projection: `scripts/runtime_store/projections.py`, `framework/contracts/workspace-projection.json`, `scripts/artifact_selection.py`, `scripts/runtime_agents.py`
- Manifest/profiles/schemas: `buddyswitch/manifest.toml`, `scripts/env_manifest.py`, `scripts/env_profiles.py`, `framework/contracts/buddy-env-profile.json`, `buddyswitch/env-profiles/*.json`, `framework/schemas/{market,pm,design,dev,test}/*-result.json`
- Runtime guidance: `buddyswitch/skills/shared/{artifact-tool,track-tool,task-tool,comment-tool}/SKILL.md`, role skills under `buddyswitch/skills/{market,pm,design,dev,test}/`, `framework/contracts/{market,pm,design,dev,test}.md`, `tools/launcher/assets/buddies/{market,pm,design,dev,test}/AGENTS.md`
- Existing tests: `tests/test_env_store_v2.py`, `tests/test_artifact_env_tool.py`, `tests/test_track_env_tool.py`, `tests/test_task_env_tool.py`, `tests/test_comment_env_tool.py`, `tests/test_context_binding_env_tool.py`, `tests/test_env_tool_router.py`, `tests/test_env_tool_semantic_contract.py`, `tests/test_env_tool_response_contract.py`, `tests/test_runtime_skills.py`, `tests/test_output_schema_boundaries.py`, `tests/test_env_manifest_v2.py`, `tests/test_prepare_runtime_context.py`, `tests/test_parallel_contracts.py`, `tests/test_artifact_selection.py`, `tests/test_repo_consistency.py`

## 2. Current Core Problem

The current runtime still models artifact collaboration through task-owned deliverable slots:

- `scripts/env_store.py` requires `artifact.task_id`, `artifact.kind`, and object `content`, then stores currentness through `task.artifact_slots`.
- `scripts/env/services/artifact_visibility.py` grants non-owner artifact reads through active task relation on the source track.
- `scripts/env/services/tracks.py` exposes `track.get` as track metadata plus related tasks and current artifact summaries derived from tasks.
- `track.join`, `track.attach_task`, and `track.detach_task` make private tasks part of the shared collaboration path.
- `scripts/env/services/comments.py` only supports `track` and `artifact` targets, has no `open/resolved` status, no mentions, and no artifact-section anchor.
- Active skills, role contracts, manifest `artifact_kinds`, output schemas, and tests still teach `kind` and task-scoped artifact writes.

The bottleneck is product semantics: a new buddy should read current shared artifact pages on a track without first joining a task or understanding private execution state.

## 3. Target Runtime Contract

### Object Responsibilities

- `Track`: shared collaboration site with goal, progress, and current shared materials.
- `Artifact`: published lightweight Markdown content page on a track, with draft and archival states.
- `Comment`: separate discussion and resolution state around a track, artifact, or artifact section.
- `Task`: active-buddy private execution management; it can store a private `track_id` hint but never grants artifact visibility and never bridges shared material.
- `Message`: temporary buddy-to-buddy coordination, not durable product truth.

### Artifact Object

Canonical persisted artifact JSON:

```json
{
  "id": "art-pm-scope-r2",
  "title": "Artifact collaboration scope",
  "summary": "Current scope, non-goals, and next useful action.",
  "body": "## Context\n\n...",
  "template": "brief",
  "status": "published",
  "published_to_track": "track-artifacts-v1",
  "revision": 2,
  "is_current": true,
  "supersedes_artifact_id": "art-pm-scope-r1",
  "created_by": "pm",
  "authors": ["pm"],
  "source_refs": [{"type": "note", "label": "memo"}],
  "created_at": "2026-05-18T10:00:00+08:00",
  "updated_at": "2026-05-18T10:05:00+08:00"
}
```

Field rules:

- `body` is the Markdown page content. It is a string and is the required reading path.
- `template` is one of `brief`, `proposal`, `design`, `decision`, `proof`, or `note`.
- `template` is a soft usage label. It does not determine permissions, visibility, comment support, body schema, lifecycle, or workflow.
- `status` is one of `draft`, `published`, or `archived`.
- `published_to_track` is `null` for drafts and a track id for published or archived track artifacts.
- `revision` is a positive integer within a `supersedes_artifact_id` chain.
- `is_current=true` marks the current head of a revision chain.
- `supersedes_artifact_id` is `null` for first revision and references the immediately previous revision for later revisions.
- `created_by` is the first publishing buddy.
- `authors` is a de-duplicated ordered list of buddies that created revisions in the chain.
- `source_refs` is optional provenance only. It must not be required to understand the artifact.

Legacy read compatibility:

- Existing JSON with `kind` and no `template` loads as `template=<kind>`, then maps unsupported legacy values to `note` with `legacy_kind=<value>` only inside migration diagnostics.
- The legacy kind migration map is:
  - `prd`, `scope-brief`, `insight-brief`, `market-scan`, `pmf-report`, `customer-discovery`, `positioning-brief`, `channel-plan`, `launch-prep`, `track-note`, `prototype-brief`, and `implementation-report` -> `brief`
  - `solution-spec`, `technical-proposal`, and `proposal` -> `proposal`
  - `design-handoff` -> `design`
  - `pm-decision` and `decision` -> `decision`
  - `verification-proof`, `smoke-test`, and `test-report` -> `proof`
  - every other legacy value -> `note`
- Existing JSON with `content.body` and no `body` loads as `body=<content.body>`.
- Existing JSON with `task_id` and no `published_to_track` loads as `status="draft"` and `published_to_track=null`.
- Normalized saves write only canonical fields. Runtime env-tool responses expose `template` and `body`, not `kind` or `content`.
- Compatibility ends at parsing old fixtures and files. Do not keep a user-facing dual product vocabulary.

### Track Shared Materials

`track.get` and `artifact.list --track-id` derive shared materials from artifacts:

```text
all artifacts where:
  artifact.published_to_track == track.id
  artifact.status == "published"
  artifact.is_current == true
```

Rules:

- Default shared materials show only current published artifacts.
- Old revisions remain traceable through `artifact.get` by id and through revision-chain summaries on the current artifact.
- Archived artifacts are not active shared materials.
- Track JSON does not persist artifact refs, material registries, task ids, or task-derived artifact slots.

### Artifact Lifecycle

Supported env-tool actions:

- `artifact.validate_payload`: validate artifact create/revision/publish payload without mutation.
- `artifact.create_revision`: create a draft, create a direct published artifact, or create a new revision of an existing artifact.
- `artifact.publish`: publish an owned draft to a track.
- `artifact.archive`: archive an artifact revision chain head.
- `artifact.get`: read one artifact page by id.
- `artifact.list`: list current published artifact summaries for a track.
- `artifact.update_metadata`: update title, summary, template, and source_refs on an owned non-archived artifact without changing body.

Lifecycle rules:

- Draft artifacts are readable and writable only by their authors.
- Direct publish is `artifact.create_revision` with `status="published"` and `published_to_track`.
- Draft-to-published is `artifact.publish` with `artifact_id` and `track_id`.
- Published artifacts on non-archived tracks are readable by all buddies.
- Archived artifacts are omitted from default shared materials and reject new comments.
- Body changes create a new revision; they do not mutate the old artifact body.
- `artifact.update_metadata` never edits `body`, `revision`, `is_current`, `supersedes_artifact_id`, `published_to_track`, or `status`.
- Creating a new revision from a current artifact sets the previous head `is_current=false` and new revision `is_current=true`.
- Creating a revision from a non-current artifact rejects with `permission_boundary="artifact.currentness"`.
- If a discussion changes product truth, the caller creates a new revision or a separate `decision` artifact. Comments never automatically become artifact body facts.

### Comments

Canonical persisted comment JSON:

```json
{
  "id": "comment-abc123def456",
  "thread_id": "comment-abc123def456",
  "target_type": "artifact_section",
  "target_id": "art-pm-scope-r2",
  "artifact_revision_id": "art-pm-scope-r2",
  "anchor": "Current Conclusion",
  "content": "This conclusion needs one more constraint.",
  "by_buddy": "design",
  "mentions": ["pm"],
  "status": "open",
  "reply_to": null,
  "created_at": "2026-05-18T10:10:00+08:00",
  "updated_at": "2026-05-18T10:10:00+08:00"
}
```

Supported env-tool actions:

- `comment.add`
- `comment.list`
- `comment.resolve`
- `comment.reopen`

Rules:

- `target_type` is `track`, `artifact`, or `artifact_section`.
- `target_id` is a track id for `track`; it is an artifact id for `artifact` and `artifact_section`.
- `artifact_section` requires `anchor` and accepts optional `artifact_revision_id`.
- `artifact_revision_id`, when present, must reference a readable artifact in the same revision chain as `target_id`.
- `mentions` is a list of declared buddy ids. It is metadata only and does not send messages or notifications.
- Root comments create threads with `thread_id=id`, `status="open"`, and `reply_to=null`.
- Replies require an existing comment on the same target, reuse its `thread_id`, and do not change artifact body content.
- `comment.resolve` sets all comments in the thread to `status="resolved"`.
- `comment.reopen` sets all comments in the thread to `status="open"`.
- `comment.list` returns both flat `comments` and grouped `threads` so old add/list callers can migrate without losing V1 thread behavior.
- Comments are stored only in `buddyswitch/objects/comments/*.json`. Track and artifact objects do not persist `comment_ids`; projections may derive `comment_ids`.

### Lightweight Design Template

`template="design"` is a Markdown writing guide only. The runtime may suggest these headings in skills and examples:

```markdown
## Goal
## User Flow
## Layout
## States
## Interaction
## Copy
## Acceptance
## Open Questions
```

The runtime must not validate these headings as a schema and must not introduce media hosting, artifact-local media, reusable assets, design token management, a material registry, or Figma replacement behavior.

## 4. File-Level Change Map

### Store And Data Model

- Modify `scripts/env_store.py`
  - Replace `VALID_TRACK_STATUS` use for artifact lifecycle with new `VALID_ARTIFACT_STATUS = ("draft", "published", "archived")`.
  - Add `VALID_ARTIFACT_TEMPLATES = ("brief", "proposal", "design", "decision", "proof", "note")`.
  - Change `validate_artifact()` to canonical artifact fields listed in section 3.
  - Accept legacy `kind`, `content.body`, and `task_id` only in `validate_artifact()` normalization.
  - Replace `create_artifact(... task_id, kind, content ...)` with `create_artifact_revision(... template, body, status, published_to_track, supersedes_artifact_id ...)`.
  - Add `publish_artifact(artifact_id, track_id, active_buddy)` for draft publishing.
  - Add `archive_artifact(artifact_id, active_buddy)` for lifecycle archive.
  - Add `artifact_revision_chain(artifact_id)` returning summaries ordered newest to oldest.
  - Remove task linkage writes from artifact creation.
  - Keep `task.track_id` as a private hint but remove automatic track mutation from `create_task()` and `update_task()`.
  - Remove `_register_task_id()`, `_unregister_task_id()`, `register_task_to_track()`, `add_artifact_to_task()`, and `remove_artifact_from_task()`.
  - Change `validate_track()` to canonical track fields `id`, `title`, `status`, `owner_buddy`, `summary`, `updated_at`; accept and drop legacy `task_ids` on read.
  - Change `validate_task()` to remove `artifact_ids` and `artifact_slots`; accept and drop them on legacy reads.
  - Change `validate_comment()` to the V1 comment shape and accept legacy `author_buddy` as `by_buddy`.
  - Add `update_comment_thread_status(thread_id, status)` and `comments_for_target(target_type, target_id)`.

- Modify `scripts/env/services/source_refs.py`
  - Keep `artifact`, `track`, `task`, `buddybox`, `external`, and `note` as provenance refs.
  - Keep buddybox refs as private provenance with `read_grant=false`.
  - Add validation text: source refs are auxiliary provenance and never a required reading path.
  - Do not add `asset`, `media`, `material`, `figma`, or `block` ref types.

### Artifact Visibility And Shared Materials

- Modify `scripts/env/services/artifact_visibility.py`
  - Replace task-relation read logic with publication read logic.
  - Export:
    - `artifact_publication(artifact) -> dict[str, Any] | None`
    - `artifact_read_decision(artifact, active_buddy) -> dict[str, Any]`
    - `artifact_summary_row(artifact, active_buddy) -> dict[str, Any]`
    - `current_published_artifact_rows_for_track(track_id, active_buddy) -> list[dict[str, Any]]`
    - `revision_chain_summary(artifact_id) -> list[dict[str, Any]]`
    - `assert_track_readable(track_id, active_buddy, action) -> dict[str, Any]`
  - Read decision order:
    - Missing artifact id rejects.
    - Draft allows only authors.
    - Published or archived artifact requires `published_to_track` and existing non-archived track.
    - Published artifacts on active tracks allow all buddies.
    - Archived artifacts allow `artifact.get` by id but reject comment targets and default lists.
    - Non-current published revisions allow `artifact.get` by id and appear only in revision-chain summaries.
  - Summary rows return `template`, `status`, `published_to_track`, `revision`, `is_current`, `supersedes_artifact_id`, `created_by`, `authors`, `open_comment_count`, `resolved_comment_count`, and `last_discussed_at`.
  - Remove relation labels `track_task`, `source_task_id`, and task-derived readability.

### Artifact Service And CLI

- Modify `scripts/env/services/artifacts.py`
  - Change payload fields:
    - `artifact.validate_payload`: `artifact_id`, `title`, `summary`, `body`, `template`, `status`, `published_to_track`, `supersedes_artifact_id`, `source_refs`, `read_claim`
    - `artifact.create_revision`: same as validate.
    - `artifact.publish`: `artifact_id`, `track_id`
    - `artifact.archive`: `artifact_id`
    - `artifact.update_metadata`: `artifact_id`, `title`, `summary`, `template`, `source_refs`, `read_claim`
    - `artifact.list`: `track_id`
    - `artifact.get`: `artifact_id`
  - Reject `task_id`, `kind`, `content`, `asset`, `media`, `material`, `blocks`, `figma_file`, and template-specific schema fields in env-tool payloads with `E_ARTIFACT_PAYLOAD`.
  - In validation, accept `body` only as non-empty Markdown string.
  - For `template`, default to `note` when omitted; reject unsupported template values.
  - For `status`, default to `draft` when `published_to_track` is absent and `published` when `published_to_track` is present.
  - For `status="published"`, require a non-archived `published_to_track`.
  - For `status="draft"`, require `published_to_track` absent.
  - For `supersedes_artifact_id`, require readable owned-or-authored current artifact; inherit `published_to_track` and status unless explicitly publishing a draft as a new published revision.
  - Return success payloads with `ok`, `state_changed`, `created_ids`, `updated_ids`, `state_changes`, `read_scope`, and `allowed_next_actions`.
  - `artifact.get` returns `artifact` with full `body`, comment counts, and `revision_chain`; it never embeds comment content into `body`.
  - `artifact.list` returns current published summaries only, with no full body.
  - `artifact.publish` sets draft `status` to `published`, sets `published_to_track`, keeps `revision`, and makes the artifact visible in track shared materials.
  - `artifact.archive` sets `status="archived"` and `is_current=false`; if it archives the current head, no replacement is promoted automatically.

- Modify `scripts/env/client.py`
  - Keep `artifact list --track-id <track-id>`.
  - Keep `artifact get --artifact-id <artifact-id>`.
  - Keep `artifact validate-payload --payload <json>`.
  - Keep `artifact create-revision --payload <json>`.
  - Add `artifact publish --artifact-id <artifact-id> --track-id <track-id>`.
  - Add `artifact archive --artifact-id <artifact-id>`.
  - Keep `artifact update-metadata --payload <json>`.
  - Do not add media, upload, asset, material, or block commands.

### Track Service And Shared Materials

- Modify `scripts/env/services/tracks.py`
  - Keep actions: `list`, `get`, `create`, `update`, `archive`.
  - Remove actions: `join`, `attach_task`, `detach_task`.
  - `track.create` and `track.update` keep lifecycle metadata only: `track_id`, `title`, `status`, `summary`.
  - `track.get` response contains:
    - `track`
    - `shared_materials`: current published artifact summaries from `current_published_artifact_rows_for_track()`
    - `open_comment_count`
    - `resolved_comment_count`
    - `allowed_next_actions` pointing to `artifact.get`, `artifact.create_revision`, and `comment.list`
  - `track.get` does not include `tasks`, `task_ids`, `artifact_slots`, `source_task_id`, or artifact full body.
  - `track.list` default excludes archived tracks and includes `shared_material_count`.
  - Archived tracks reject `track.get`, `artifact.list`, publication, and comments.

### Task Service

- Modify `scripts/env/services/tasks.py`
  - Keep actions: `create`, `list`, `get`, `update`, `archive`.
  - `task.create/update` may store `track_id` as active-buddy private organization hint.
  - `task.create/update` must not mutate track JSON.
  - `task.list/get` return only active-buddy-owned tasks.
  - Task responses do not include artifact ids, artifact slots, comment ids, or shared-material next actions.
  - Allowed next actions point to private task updates and optional `artifact.create_revision` when the host decides to publish or draft content; wording must say artifact visibility comes from `published_to_track`, not task relation.

### Comment Service

- Modify `scripts/env/services/comments.py`
  - Add `_ADD_FIELDS = {"target_type", "target_id", "artifact_revision_id", "anchor", "content", "mentions", "reply_to"}`.
  - Add `_RESOLVE_FIELDS = {"comment_id", "reason"}` and `_REOPEN_FIELDS = {"comment_id", "reason"}`.
  - Support target types `track`, `artifact`, and `artifact_section`.
  - Reuse `artifact_visibility` for readable target checks.
  - Reject comments on draft artifacts by non-authors.
  - Reject comments on archived artifacts and archived tracks.
  - Validate mentions against manifest buddy ids.
  - Validate reply target and thread target equality.
  - `comment.list` returns flat `comments`, grouped `threads`, and counts by status.
  - `comment.resolve` and `comment.reopen` mutate comment objects only; they do not mutate track or artifact body.
  - All mutating comment actions return `state_changes` with `object_type="comment"`.

- Modify `scripts/env/client.py`
  - Add `comment resolve --comment-id <comment-id> [--reason <text>]`.
  - Add `comment reopen --comment-id <comment-id> [--reason <text>]`.
  - Add optional `--status open|resolved|all` to `comment list`; default `all`.
  - For `comment add`, continue using `--payload <json>` so `mentions`, `anchor`, and `artifact_revision_id` are passed without CLI flag sprawl.

### Tool Registry, Semantics, Router, Dispatch

- Modify `scripts/env/tools/contracts.py`
  - Change track scope to `track collaboration sites and current shared materials`.
  - Remove `track.join`, `track.attach_task`, and `track.detach_task`.
  - Change artifact scope to `track-published Markdown content pages`.
  - Change artifact action payload fields and returns as listed above.
  - Add `artifact.publish` and `artifact.archive`.
  - Change comment target preconditions to include `artifact_section` and add `resolve`/`reopen`.
  - Ensure mutating actions use `MUTATES_RUNTIME_OBJECTS`; read actions use `MUTATES_NONE`.

- Modify `scripts/env/tools/semantics.py`
  - Replace task-scoped artifact wording.
  - State `template` is a soft label and does not drive permissions, visibility, schema, or workflow.
  - State comments are separate from artifact body and resolved threads are discussion state.
  - State unsupported non-goals: media, asset registry, material registry, block tree, Figma replacement, workflow engine, template-driven permissions.

- Modify `scripts/env/tools/dispatch.py`
  - Remove track relation handlers.
  - Add artifact `publish` and `archive`.
  - Add comment `resolve` and `reopen`.
  - Keep handler coverage tests registry-derived.

- Modify `scripts/env/tools/router.py`
  - No special routing logic should be added.
  - Existing registry-backed validation must reject removed actions.

### Context, Projection, And Selection

- Modify `scripts/env/services/context.py`
  - Context `artifact_summaries` must come from current published artifacts on visible tracks.
  - `candidate_tracks` should show `shared_material_count` and no task-relation role.
  - `context.get/summarize` must not expose artifact full bodies.
  - Context source descriptions must say artifacts are track-published Markdown pages and comments are separate target discussions.

- Modify `scripts/runtime_store/projections.py`
  - Track view includes derived `shared_materials` summaries and derived `comment_ids`.
  - Artifact view includes `body`, `template`, `status`, `published_to_track`, `revision`, `is_current`, `supersedes_artifact_id`, `created_by`, `authors`, derived `comment_ids`, and object path metadata.
  - Task view removes `artifact_ids`, `artifact_slots`, and `current_artifacts`.
  - Projection does not expose top-level comment bodies and does not create material registries.

- Modify `framework/contracts/workspace-projection.json`
  - Replace track `task_ids/tasks/missing_task_ids` with `shared_materials` and `comment_ids`.
  - Replace artifact `task_id/kind/content` with `template/body/status/published_to_track/authors`.
  - Replace task artifact linkage fields with private task fields.
  - Keep `buddyswitch/objects/comments/*.json` in data sources for derived `comment_ids`.

- Modify `scripts/artifact_selection.py`
  - Replace task-bundle selection with current published artifact summaries.
  - Rename selection mode in `framework/config/artifact-selection-v2.json` from `kind-current-v2` to `template-current-v1`.
  - Inputs become `required_templates`, not `required_kinds`.
  - Selection chooses current published artifacts by `template`, then newest `updated_at`.

### Manifest, Profiles, Schemas, Skills, Contracts

- Modify `buddyswitch/manifest.toml`
  - Replace each buddy `artifact_kinds` with `artifact_templates`.
  - Use only V1 template values: `brief`, `proposal`, `design`, `decision`, `proof`, `note`.
  - Add permissions `artifact.publish` and `artifact.archive`.
  - Remove any permission or skill wording that suggests task relation is needed for artifact visibility.

- Modify `scripts/env_manifest.py`
  - Validate `artifact_templates`.
  - Accept legacy `artifact_kinds` only by normalizing to `artifact_templates` during manifest load, then update checked-in manifest to canonical `artifact_templates`.

- Modify `scripts/env_profiles.py`, `framework/contracts/buddy-env-profile.json`, and `buddyswitch/env-profiles/*.json`
  - Rename `state_capability.artifact_kinds` to `state_capability.artifact_templates`.
  - Keep values advisory; they must not grant or deny artifact actions.

- Modify `framework/schemas/{market,pm,design,dev,test}/*-result.json`
  - Replace artifact schema required fields `kind`, `title`, `content` with `template`, `title`, `body`.
  - Allow optional `summary`, `published_to_track`, `source_refs`, and `supersedes_artifact_id`.
  - Reject `asset`, `media`, `material`, `blocks`, and `figma_file`.

- Modify `buddyswitch/skills/shared/artifact-tool/SKILL.md`
  - Teach `Artifact V1 = track-published Markdown content page`.
  - Show `artifact.create_revision` payload with `template`, `body`, and optional `published_to_track`.
  - Teach draft, publish, archive, current revision, and `artifact.get` read path.
  - State template is a soft label and source_refs are provenance only.

- Modify `buddyswitch/skills/shared/track-tool/SKILL.md`
  - Teach `track.get -> shared_materials -> artifact.get`.
  - Remove `track.join`, `attach-task`, and `detach-task`.
  - State track shared materials are current published artifacts.

- Modify `buddyswitch/skills/shared/comment-tool/SKILL.md`
  - Teach `track`, `artifact`, and `artifact_section` targets.
  - Teach mentions, replies, open/resolved threads, and anchors.
  - State comments are not artifact body and do not become facts automatically.

- Modify `buddyswitch/skills/shared/task-tool/SKILL.md`
  - State tasks are active-buddy private execution management.
  - State task ids do not grant artifact visibility and task-track hints do not publish content.

- Modify role skills and contracts:
  - `buddyswitch/skills/pm/write-prd/SKILL.md`
  - `buddyswitch/skills/design/shape-prototype/SKILL.md`
  - `buddyswitch/skills/dev/implement-task/SKILL.md`
  - `buddyswitch/skills/test/smoke-test/SKILL.md`
  - Market skills under `buddyswitch/skills/market/`
  - `framework/contracts/{market,pm,design,dev,test}.md`
  - `tools/launcher/assets/buddies/{market,pm,design,dev,test}/AGENTS.md`
  - Replace `kind` examples with `template`.
  - Replace task-bound artifact instructions with track-published artifact instructions.
  - Add design template guidance as Markdown headings only.
  - Remove wording that instructs high-fidelity media, asset registries, material registries, Figma replacement, or block tree output.

### Cleanup And Repo Consistency

- Modify `scripts/env_cleanup.py`
  - Remove task artifact-slot cleanup paths.
  - Keep artifact object cleanup by owner/author and all-data cleanup.
  - Keep comment object cleanup and derived projection behavior.

- Modify `scripts/runtime_agents.py`
  - Replace validation phrase `artifact when content must become product-readable` with wording that artifacts are track-published Markdown pages when content must become shared track material.
  - Add forbidden runtime template checks for task-bound artifact visibility and `kind` as product vocabulary.

- Modify `scripts/skill_creator_importer.py`
  - Rename `artifact_kind` CLI/config to `artifact_template`.
  - Normalize legacy `--artifact-kind` as a CLI alias that writes `artifact_templates`.
  - Ensure imported skills cannot add template values outside V1 set.

## 5. Phased Implementation Plan

### Phase 0: Add Failing Contract Tests

**Goal:** Lock V1 behavior before changing runtime code.

**Modify tests:**

- `tests/test_env_store_v2.py`
- `tests/test_artifact_env_tool.py`
- `tests/test_track_env_tool.py`
- `tests/test_task_env_tool.py`
- `tests/test_comment_env_tool.py`
- `tests/test_context_binding_env_tool.py`
- `tests/test_env_tool_router.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_runtime_skills.py`
- `tests/test_output_schema_boundaries.py`
- `tests/test_env_manifest_v2.py`
- `tests/test_prepare_runtime_context.py`
- `tests/test_parallel_contracts.py`
- `tests/test_artifact_selection.py`
- `tests/test_repo_consistency.py`

**Required tests:**

1. Store accepts canonical artifact fields and rejects new writes with `task_id`, `kind`, or object `content`.
2. Store loads legacy `kind/content.body/task_id` as `template/body/draft` and saves canonical fields.
3. `artifact.create_revision` creates draft artifact without task.
4. `artifact.create_revision` publishes directly to track when `published_to_track` is present.
5. `artifact.publish` publishes an owned draft to track.
6. `artifact.archive` removes artifact from default shared materials.
7. `track.get` shared materials equal `artifact.list --track-id` current published artifacts.
8. Non-owner reads current published artifact without task relation.
9. Non-owner cannot read draft artifact.
10. Old revision is readable by id but absent from default shared materials.
11. Template does not affect visibility or permission.
12. Task create with `track_id` does not mutate track and does not grant artifact read access.
13. Removed `track.join`, `track.attach_task`, and `track.detach_task` are absent from registry, CLI, semantics, and dispatch.
14. Comment add/list/resolve/reopen works for `track`, `artifact`, and `artifact_section`.
15. Mentions validate buddy ids; replies stay in the same thread and target.
16. Comments are not embedded in artifact body.
17. Docs/skills/contracts do not teach old `kind-first`, `task-bound`, `handoff-like`, `asset/material`, media, Figma replacement, or block-tree directions.

**Acceptance command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_store_v2.py \
  tests/test_artifact_env_tool.py \
  tests/test_track_env_tool.py \
  tests/test_task_env_tool.py \
  tests/test_comment_env_tool.py \
  tests/test_env_tool_router.py \
  tests/test_env_tool_response_contract.py \
  -q
```

Expected before implementation: failures name missing canonical fields, old task-bound behavior, unsupported new actions, and missing comment V1 thread behavior.

### Phase 1: Store Canonical Artifact, Track, Task, And Comment Shapes

**Goal:** Make durable object validation express V1 semantics.

**Modify code:**

- `scripts/env_store.py`
- `scripts/env/services/source_refs.py`

**Modify tests:**

- `tests/test_env_store_v2.py`
- `tests/test_artifact_env_tool.py` fixture helpers
- `tests/test_track_env_tool.py` fixture helpers
- `tests/test_comment_env_tool.py` fixture helpers

**Implementation tasks:**

1. Add `VALID_ARTIFACT_STATUS` and `VALID_ARTIFACT_TEMPLATES`.
2. Replace `validate_artifact()` normalized return with canonical V1 artifact shape.
3. Add legacy normalization for `kind`, `content.body`, and `task_id`.
4. Replace artifact creation/update helpers with revision, publish, archive, and revision-chain helpers.
5. Remove task artifact linkage helpers and track task registration helpers.
6. Change `validate_track()` to drop legacy `task_ids` and persist no task relation field.
7. Change `create_track()` and `update_track()` to avoid task relation fields.
8. Change `validate_task()` to drop legacy `artifact_ids` and `artifact_slots`; keep `track_id` as private hint.
9. Change `create_task()` and `update_task()` so `track_id` never mutates track JSON.
10. Change `validate_comment()` to V1 fields and normalize legacy `author_buddy`.
11. Add comment thread status update helper.
12. Keep source refs as auxiliary provenance and reject unsupported provenance types.

**Acceptance command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_store_v2.py \
  tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_legacy_kind_fixture_loads_as_template_without_shared_publication \
  tests/test_task_env_tool.py::TaskEnvToolTests::test_task_track_id_hint_does_not_mutate_track \
  -q
```

Expected after Phase 1: store/model tests pass; service tests that depend on old service payloads still fail until later phases.

### Phase 2: Artifact Env Tool Becomes Markdown Page Lifecycle

**Goal:** Implement draft, direct publish, publish, archive, currentness, and revision reads through artifact service.

**Modify code:**

- `scripts/env/services/artifact_visibility.py`
- `scripts/env/services/artifacts.py`
- `scripts/env/tools/contracts.py`
- `scripts/env/tools/semantics.py`
- `scripts/env/tools/dispatch.py`
- `scripts/env/client.py`

**Modify tests:**

- `tests/test_artifact_env_tool.py`
- `tests/test_env_tool_router.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_env_tool_response_contract.py`

**Implementation tasks:**

1. Replace artifact visibility with publication-based read decisions.
2. Implement current published row derivation by `published_to_track/status/is_current`.
3. Implement `artifact.validate_payload` for `template/body/status/published_to_track/supersedes_artifact_id`.
4. Implement `artifact.create_revision` for drafts, direct publishes, and revisions.
5. Implement `artifact.publish` for owned drafts.
6. Implement `artifact.archive` for authored artifacts.
7. Update `artifact.get` to return full Markdown body plus revision chain and comment counts.
8. Update `artifact.list` to return current published summaries only.
9. Update CLI subcommands and registry/semantics/dispatch coverage.
10. Make all artifact rejection payloads include `permission_boundary`, `why_blocked`, `state_changed=false`, and safe `allowed_next_actions`.

**Acceptance command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_artifact_env_tool.py \
  tests/test_env_tool_router.py::EnvToolRouterTests::test_dispatch_handler_coverage_matches_registry_actions \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  -q
```

Expected after Phase 2: artifact lifecycle and contract tests pass; track/context/projection tests still fail where they expect shared materials.

### Phase 3: Track Shared Materials And Task Boundary

**Goal:** Make `track.get` and `artifact.list` show current published artifacts directly, while tasks remain private execution objects.

**Modify code:**

- `scripts/env/services/tracks.py`
- `scripts/env/services/tasks.py`
- `scripts/env/tools/contracts.py`
- `scripts/env/tools/semantics.py`
- `scripts/env/tools/dispatch.py`
- `scripts/env/client.py`

**Modify tests:**

- `tests/test_track_env_tool.py`
- `tests/test_task_env_tool.py`
- `tests/test_artifact_env_tool.py`
- `tests/test_env_tool_router.py`
- `tests/test_repo_consistency.py`

**Implementation tasks:**

1. Remove track relation actions from service, registry, dispatch, CLI, and semantics.
2. Rewrite `track.get` response to return `shared_materials`, comment counts, and no task/artifact body fields.
3. Rewrite `track.list` rows to include `shared_material_count`.
4. Keep PM-owned `track.create/update/archive`.
5. Rewrite `task.create/update` to store `track_id` as private hint without track mutation.
6. Rewrite task summaries to remove artifact ids and artifact slots.
7. Update rejection and next-action wording so task never appears as artifact visibility bridge.
8. Add repo consistency scan excluding dated `docs/memo/**` and `docs/spec/**` to ensure active runtime surfaces do not teach removed track relation actions.

**Acceptance command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_track_env_tool.py \
  tests/test_task_env_tool.py \
  tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_non_owner_reads_current_published_artifact_without_task_relation \
  tests/test_env_tool_router.py \
  tests/test_repo_consistency.py \
  -q
```

Expected after Phase 3: direct track shared materials work; removed task relation tool surface is absent.

### Phase 4: Comment Threads, Resolution, Mentions, And Anchors

**Goal:** Upgrade comments from plain add/list to independent V1 collaboration threads.

**Modify code:**

- `scripts/env_store.py`
- `scripts/env/services/comments.py`
- `scripts/env/tools/contracts.py`
- `scripts/env/tools/semantics.py`
- `scripts/env/tools/dispatch.py`
- `scripts/env/client.py`
- `scripts/runtime_store/projections.py`
- `framework/contracts/workspace-projection.json`

**Modify tests:**

- `tests/test_comment_env_tool.py`
- `tests/test_track_env_tool.py`
- `tests/test_artifact_env_tool.py`
- `tests/test_parallel_contracts.py`
- `tests/test_env_tool_router.py`
- `tests/test_env_tool_response_contract.py`

**Implementation tasks:**

1. Extend comment validation with `thread_id`, `by_buddy`, `mentions`, `status`, `artifact_revision_id`, `anchor`, and `updated_at`.
2. Support legacy `author_buddy` read compatibility.
3. Implement `artifact_section` target validation.
4. Add target readability checks for track, artifact, and artifact section.
5. Implement mention validation against manifest buddies.
6. Implement same-target reply validation and thread id inheritance.
7. Implement `comment.resolve` and `comment.reopen`.
8. Return grouped `threads` in `comment.list`.
9. Update derived `comment_ids` in projection from comment objects only.
10. Ensure comment body text never enters artifact `body`.

**Acceptance command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_comment_env_tool.py \
  tests/test_parallel_contracts.py \
  tests/test_env_tool_router.py::EnvToolRouterTests::test_dispatch_handler_coverage_matches_registry_actions \
  tests/test_env_tool_response_contract.py \
  -q
```

Expected after Phase 4: comment V1 behavior passes and target objects remain unmodified by comments.

### Phase 5: Context, Projection, And Artifact Selection

**Goal:** Align read-only runtime surfaces with current published artifact pages.

**Modify code:**

- `scripts/env/services/context.py`
- `scripts/runtime_store/projections.py`
- `framework/contracts/workspace-projection.json`
- `scripts/artifact_selection.py`
- `framework/config/artifact-selection-v2.json`

**Modify tests:**

- `tests/test_context_binding_env_tool.py`
- `tests/test_prepare_runtime_context.py`
- `tests/test_parallel_contracts.py`
- `tests/test_artifact_selection.py`
- `tests/test_console_app_contract.py`

**Implementation tasks:**

1. Make context `artifact_summaries` use current published artifact rows.
2. Make context candidates expose `shared_material_count` and no task relation role.
3. Ensure context never returns full artifact `body`.
4. Change workspace projection shapes for track, task, and artifact.
5. Keep derived `comment_ids` in track/artifact projection views.
6. Update artifact selection from `required_kinds` to `required_templates`.
7. Update selection output fields from `kind` to `template`.
8. Remove task bundle assumptions from artifact selection tests.

**Acceptance command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_context_binding_env_tool.py \
  tests/test_prepare_runtime_context.py \
  tests/test_parallel_contracts.py \
  tests/test_artifact_selection.py \
  tests/test_console_app_contract.py \
  -q
```

Expected after Phase 5: context and projection agree with `track.get` and `artifact.list`.

### Phase 6: Manifest, Profiles, Schemas, Skills, And Runtime Contracts

**Goal:** Make active runtime guidance teach the V1 artifact collaboration page model.

**Modify files:**

- `buddyswitch/manifest.toml`
- `scripts/env_manifest.py`
- `scripts/env_profiles.py`
- `framework/contracts/buddy-env-profile.json`
- `buddyswitch/env-profiles/*.json`
- `framework/schemas/{market,pm,design,dev,test}/*-result.json`
- `buddyswitch/skills/shared/{artifact-tool,track-tool,task-tool,comment-tool}/SKILL.md`
- `buddyswitch/skills/{market,pm,design,dev,test}/**/SKILL.md`
- `buddyswitch/skills/dev/implement-task/assets/implementation-report-template.md`
- `framework/contracts/{market,pm,design,dev,test}.md`
- `tools/launcher/assets/buddies/{market,pm,design,dev,test}/AGENTS.md`
- `scripts/runtime_agents.py`
- `scripts/skill_creator_importer.py`

**Modify tests:**

- `tests/test_env_manifest_v2.py`
- `tests/test_runtime_skills.py`
- `tests/test_output_schema_boundaries.py`
- `tests/test_task_management_skill_architecture.py`
- `tests/test_repo_consistency.py`

**Implementation tasks:**

1. Rename manifest/profile/schema vocabulary from artifact kinds to artifact templates.
2. Update output schemas to `template/title/body`.
3. Update skills with direct publish and shared materials workflows.
4. Update comment skill with resolved threads, mentions, and anchors.
5. Update task skill and role contracts to mark tasks private.
6. Update runtime AGENTS validation phrases.
7. Add semantic tests that fail on active guidance containing task-bound artifact visibility, `kind` product vocabulary, or unsupported asset/media/material/block-tree/Figma replacement directions.

**Acceptance command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_manifest_v2.py \
  tests/test_runtime_skills.py \
  tests/test_output_schema_boundaries.py \
  tests/test_task_management_skill_architecture.py \
  tests/test_repo_consistency.py \
  -q
```

Expected after Phase 6: active docs, skills, schemas, manifest, and profiles consistently expose V1 semantics.

### Phase 7: Migration And Compatibility Regression

**Goal:** Prove old fixtures do not crash runtime while the product surface is canonical V1.

**Modify tests:**

- `tests/test_env_store_v2.py`
- `tests/test_artifact_env_tool.py`
- `tests/test_track_env_tool.py`
- `tests/test_runtime_skills.py`
- `tests/test_repo_consistency.py`

**Implementation tasks:**

1. Add fixture with legacy artifact `kind`, `content.body`, `task_id`, `artifact_ids`, and `artifact_slots`.
2. Assert `env_store.get_artifact()` returns canonical `template`, `body`, `status="draft"`, and no user-facing `kind`.
3. Assert `artifact.list --track-id` does not expose legacy task-bound draft artifacts.
4. Assert `artifact.get` allows only owner read for migrated draft unless published through `artifact.publish`.
5. Add fixture with legacy track `task_ids`; assert `track.get` ignores it for shared materials.
6. Add fixture with legacy comment `author_buddy`; assert it loads as `by_buddy`.
7. Add fixture with manifest `artifact_kinds`; assert loader normalizes to `artifact_templates`, while checked-in manifest uses canonical key.
8. Add residue scan for active code/docs excluding dated memo/spec history.

**Acceptance command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_store_v2.py::ArtifactCompatibilityTests \
  tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_legacy_task_bound_artifact_is_draft_until_published \
  tests/test_track_env_tool.py::TrackEnvToolTests::test_legacy_track_task_ids_do_not_create_shared_materials \
  tests/test_repo_consistency.py \
  -q
```

Expected after Phase 7: legacy data loads safely but does not preserve old product semantics as an active collaboration path.

### Phase 8: End-To-End Runtime Loop Verification

**Goal:** Prove the whole collaboration path works without task-bound artifact visibility.

**Modify tests:**

- Add `tests/test_env_layer_end_to_end.py` when the file is absent; modify it when the file already exists.
- `tests/test_turn_integration.py`
- `tests/test_runless_runtime_contract.py`

**E2E scenario:**

1. PM creates active track.
2. PM publishes `brief` artifact directly to the track.
3. Design reads `track.get.shared_materials` and `artifact.get` without a task.
4. Design comments on artifact section with mention to PM.
5. PM resolves the thread by creating a new artifact revision.
6. Design publishes `design` artifact as Markdown body.
7. Dev reads current published artifacts without a task relation.
8. Test publishes `proof` artifact.
9. PM reads shared materials and archives stale artifact.
10. Default `track.get.shared_materials` shows only current published non-archived artifacts.

**Acceptance command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_layer_end_to_end.py \
  tests/test_turn_integration.py \
  tests/test_runless_runtime_contract.py \
  -q
```

Expected after Phase 8: the main V1 collaboration loop passes with no `track.join`, no task-derived read grant, and no comment text inside artifact body.

## 6. Final Verification Commands

Run all focused and broad checks:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_store_v2.py \
  tests/test_artifact_env_tool.py \
  tests/test_track_env_tool.py \
  tests/test_task_env_tool.py \
  tests/test_comment_env_tool.py \
  tests/test_context_binding_env_tool.py \
  tests/test_env_tool_router.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_runtime_skills.py \
  tests/test_output_schema_boundaries.py \
  tests/test_env_manifest_v2.py \
  tests/test_prepare_runtime_context.py \
  tests/test_parallel_contracts.py \
  tests/test_artifact_selection.py \
  tests/test_console_app_contract.py \
  tests/test_task_management_skill_architecture.py \
  tests/test_repo_consistency.py \
  -q
```

Expected result: all selected tests pass.

Run CLI help smoke:

```bash
python3 scripts/env/client.py artifact --help
python3 scripts/env/client.py track --help
python3 scripts/env/client.py comment --help
python3 scripts/turn_runtime.py status
```

Expected result:

- `artifact` help lists `list`, `get`, `validate-payload`, `create-revision`, `publish`, `archive`, `update-metadata`.
- `track` help lists `list`, `get`, `create`, `update`, `archive`; it does not list `join`, `attach-task`, or `detach-task`.
- `comment` help lists `add`, `list`, `resolve`, `reopen`.
- Runtime status exposes updated tool registry and no task-bound artifact visibility wording.

Run active-surface residue scan:

```bash
rg -n "track\\.join|attach-task|detach-task|artifact_kinds|artifact kind|task-bound|task relation.*artifact|asset registry|material registry|block tree|Figma replacement" \
  scripts buddyswitch framework tools tests README.md AGENTS.md \
  -g '!docs/memo/**' \
  -g '!docs/spec/**'
```

Expected result: no hits except tests that define the residue scan and explicit negative assertions.

## 7. Completion Criteria

The implementation is complete only when:

- Artifact persisted and env-tool response vocabulary is `template/body/status/published_to_track`, not active `kind/content/task_id`.
- Current track shared materials are exactly current published artifacts.
- A buddy can read current published artifacts from a non-archived track without a task relation.
- Tasks remain private execution management and cannot bridge artifact visibility.
- Comments support targets `track`, `artifact`, and `artifact_section`, plus open/resolved threads, replies, mentions, and optional anchor/revision metadata.
- Comment text is never stored in artifact body.
- Lightweight design artifacts are Markdown pages with writing guidance only.
- Source refs remain optional provenance, not required reading path.
- Legacy kind/task-bound fixtures load safely but do not remain an active product path.
- Active runtime guidance, schemas, skills, contracts, and tests no longer teach old kind-first, task-bound, handoff-like, asset/material/media/block-tree directions.
- Final verification commands pass.
