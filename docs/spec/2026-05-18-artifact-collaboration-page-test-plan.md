# Artifact Collaboration Page Test Plan

## 1. Test Objective

Prove Artifact V1 behaves as a track-published Markdown content page with separate collaboration state:

- current shared materials on a track are current published artifacts;
- comments, replies, mentions, resolved threads, anchors, and optional revision references are independent collaboration objects;
- revisions carry accepted content changes;
- tasks remain active-buddy private execution management and do not bridge visibility;
- template is a soft writing/reading label, not a rule processor.

Tests must start from product requirements and externally observable runtime contracts. They must not preserve helper behavior, task-derived shortcuts, or `kind` vocabulary only because current implementation already has those shapes.

## 2. Functional Requirements From Memo

### Required Behavior

- `REQ-ART-001`: An artifact is a track-published Markdown content page.
- `REQ-ART-002`: Artifact fields are `id`, `title`, `summary`, `body`, `template`, `status`, `published_to_track`, `revision`, `is_current`, `supersedes_artifact_id`, `created_by`, `authors`, timestamps, and optional `source_refs`.
- `REQ-ART-003`: `body` is required Markdown content and is understandable without reading private tasks, messages, raw logs, or external files.
- `REQ-ART-004`: Persisted legacy `content.body` may load for compatibility, but runtime env-tool responses use `body`.
- `REQ-ART-005`: `template` is a soft label for writing and reading.
- `REQ-ART-006`: `template` does not decide permissions, visibility, body schema, comments, status transition, or workflow.
- `REQ-ART-007`: Valid V1 templates are `brief`, `proposal`, `design`, `decision`, `proof`, and `note`.
- `REQ-ART-008`: Artifact lifecycle is `draft -> published -> archived`.
- `REQ-ART-009`: Draft artifacts are not track shared materials and are readable only by authors.
- `REQ-ART-010`: Published artifacts on non-archived tracks are readable by all buddies.
- `REQ-ART-011`: Archived artifacts are not active collaboration material.
- `REQ-ART-012`: Body changes create a new revision and do not mutate old revision body.
- `REQ-ART-013`: The current revision is default-visible; old revisions are traceable by id or revision chain but do not pollute default shared materials.
- `REQ-ART-014`: `source_refs` and provenance are auxiliary and cannot be the required reading path.
- `REQ-TRK-001`: Track shared materials default to current published artifacts.
- `REQ-TRK-002`: The default read path is `track -> current published artifacts`, not `track -> task -> artifact`.
- `REQ-TRK-003`: `track.get` does not return full artifact body content.
- `REQ-TSK-001`: Tasks are active-buddy private execution management.
- `REQ-TSK-002`: Task `track_id` may be a private hint but does not mutate track shared state.
- `REQ-TSK-003`: Task ownership or track relation does not grant artifact visibility.
- `REQ-CMT-001`: Comments are stored independently from artifact body.
- `REQ-CMT-002`: Comments target `track`, `artifact`, or `artifact_section`.
- `REQ-CMT-003`: Comments support open/resolved thread state.
- `REQ-CMT-004`: Replies stay inside the same target/thread.
- `REQ-CMT-005`: Mentions store declared buddy ids as metadata.
- `REQ-CMT-006`: Artifact-section comments support an anchor and optional artifact revision reference.
- `REQ-CMT-007`: Discussion does not automatically become artifact truth.
- `REQ-DES-001`: Lightweight design artifacts are Markdown pages that can carry goal, flow, layout, states, interaction, copy, acceptance, and open questions.
- `REQ-DES-002`: Design support does not introduce artifact-local media, asset objects, material registries, Figma replacement, high-fidelity design hosting, reusable asset lifecycle, or block trees.
- `REQ-ENV-001`: Env-tool responses follow existing structured style: `ok`, `state_changed`, `durability`, `created_ids`, `updated_ids`, `state_changes`, `read_scope`, `permission_boundary`, `why_blocked`, and `allowed_next_actions`.
- `REQ-ENV-002`: `context`, `track`, `artifact`, and `comment` tools agree on ids, visibility, currentness, and comment counts.
- `REQ-COMPAT-001`: Legacy artifacts with `kind`, `content.body`, and `task_id` do not crash runtime and normalize to canonical V1 semantics.
- `REQ-DOC-001`: Active docs, skills, runtime contracts, schemas, and role guidance teach the V1 model and do not steer users toward old kind-first, task-bound, handoff-like, asset/material/media/block-tree directions.

### Explicit Non-Goals To Test Negatively

- `NON-001`: No asset objects.
- `NON-002`: No material registry.
- `NON-003`: No attachment lifecycle or artifact-local media.
- `NON-004`: No Notion-style block tree.
- `NON-005`: No Figma or design-file replacement behavior.
- `NON-006`: No per-template body schemas.
- `NON-007`: No one artifact kind per buddy or per skill.
- `NON-008`: No workflow engine driven by template.
- `NON-009`: No permissions driven by template.
- `NON-010`: No artifact visibility through private task chains.
- `NON-011`: No long-lived user-facing dual vocabulary between `kind` and `template`.
- `NON-012`: No comments stored inside artifact body.

## 3. Test Strategy

### Unit And Store Tests

Purpose: verify durable object validation and migration boundaries that are easier to prove directly at the store layer.

Stable internal boundaries:

- `scripts/env_store.py` validators and save/create helpers.
- `scripts/env/services/artifact_visibility.py` pure read-decision helpers.
- `scripts/runtime_store/projections.py` read-only projection builders.

Do not test whether a private helper was called. Test the resulting validated object, JSON file, or decision payload.

### Service And Contract Tests

Purpose: verify broker-routed env-tool behavior through public runtime request envelopes.

Primary files:

- `tests/test_artifact_env_tool.py`
- `tests/test_track_env_tool.py`
- `tests/test_comment_env_tool.py`
- `tests/test_task_env_tool.py`
- `tests/test_context_binding_env_tool.py`
- `tests/test_env_tool_router.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_env_tool_semantic_contract.py`

These are behavior tests. They dispatch `env.tool` requests and assert response JSON plus durable state.

### CLI And Env Tool Tests

Purpose: verify user-facing `scripts/env/client.py` commands map to the same contracts as broker calls.

Primary commands:

- `python3 scripts/env/client.py artifact list --track-id <track-id>`
- `python3 scripts/env/client.py artifact get --artifact-id <artifact-id>`
- `python3 scripts/env/client.py artifact publish --artifact-id <artifact-id> --track-id <track-id>`
- `python3 scripts/env/client.py artifact archive --artifact-id <artifact-id>`
- `python3 scripts/env/client.py track get --track-id <track-id>`
- `python3 scripts/env/client.py comment list --target-type artifact --target-id <artifact-id>`
- `python3 scripts/env/client.py comment resolve --comment-id <comment-id>`

### Integration Tests

Purpose: prove the main cross-buddy collaboration loop works without task relation.

Use runtime workspaces from `tests/runtime_root_test_helper.py` and dispatch through `runtime_kernel.broker.dispatch_runtime_request`.

### Semantic Docs Tests

Purpose: ensure active runtime guidance no longer teaches the retired model.

Scan only active surfaces:

- `scripts`
- `buddyswitch`
- `framework`
- `tools`
- `tests`
- `README.md`
- `AGENTS.md`

Exclude historical dated archives:

- `docs/memo/**`
- `docs/spec/**`

## 4. Requirement Coverage Matrix

| Requirement | Primary tests |
| --- | --- |
| `REQ-ART-001` to `REQ-ART-004` | `ACP-STORE-001`, `ACP-ART-001`, `ACP-ART-002`, `ACP-COMPAT-001` |
| `REQ-ART-005` to `REQ-ART-007` | `ACP-TEMPLATE-001` to `ACP-TEMPLATE-004`, `ACP-DOC-001` |
| `REQ-ART-008` to `REQ-ART-011` | `ACP-LIFE-001` to `ACP-LIFE-005` |
| `REQ-ART-012` to `REQ-ART-013` | `ACP-REV-001` to `ACP-REV-004` |
| `REQ-ART-014` | `ACP-PROV-001`, `ACP-PROV-002` |
| `REQ-TRK-001` to `REQ-TRK-003` | `ACP-TRACK-001` to `ACP-TRACK-004`, `ACP-CONTEXT-001` |
| `REQ-TSK-001` to `REQ-TSK-003` | `ACP-TASK-001` to `ACP-TASK-004` |
| `REQ-CMT-001` to `REQ-CMT-007` | `ACP-COMMENT-001` to `ACP-COMMENT-010` |
| `REQ-DES-001` to `REQ-DES-002` | `ACP-DESIGN-001`, `ACP-DESIGN-002`, `ACP-NEG-001` |
| `REQ-ENV-001` to `REQ-ENV-002` | `ACP-CONTRACT-001` to `ACP-CONTRACT-004`, `ACP-CONTEXT-001` |
| `REQ-COMPAT-001` | `ACP-COMPAT-001` to `ACP-COMPAT-004` |
| `REQ-DOC-001` | `ACP-DOC-001` to `ACP-DOC-005` |
| `NON-001` to `NON-012` | `ACP-NEG-001` to `ACP-NEG-007`, `ACP-DOC-002`, `ACP-DOC-003` |

## 5. Detailed Test Cases

### `ACP-STORE-001`: canonical artifact store shape

- **Type:** Internal unit/store test.
- **Purpose:** Prove persisted artifacts use V1 field names and Markdown body.
- **Preconditions:** Empty runtime test workspace.
- **Steps:** Call store artifact creation helper with `title`, `summary`, `body`, `template="brief"`, `status="draft"`, `published_to_track=null`, and `created_by="pm"`.
- **Expected:** Returned and stored JSON contain `body`, `template`, `status`, `published_to_track`, `revision`, `is_current`, `supersedes_artifact_id`, `created_by`, and `authors`. Stored JSON does not contain `kind`, `content`, `task_id`, `asset`, `media`, `material`, or `blocks`.
- **Failure means:** Store still persists the old task-bound or kind-first artifact model.
- **Suggested test:** `tests/test_env_store_v2.py::ArtifactStoreContractTests::test_create_artifact_uses_canonical_markdown_page_shape`.

### `ACP-STORE-002`: invalid artifact store fields reject

- **Type:** Internal unit/store negative test.
- **Purpose:** Prevent new writes from preserving retired fields.
- **Preconditions:** Empty runtime test workspace.
- **Steps:** Call `validate_artifact()` with payloads containing `task_id`, `kind`, `content`, `asset`, `media`, `material`, `blocks`, and `figma_file`.
- **Expected:** Each payload raises `ValueError` naming the unsupported field. No artifact file is written.
- **Failure means:** Retired concepts can enter durable state as new canonical data.
- **Suggested test:** `tests/test_env_store_v2.py::ArtifactStoreContractTests::test_new_artifact_shape_rejects_retired_fields`.

### `ACP-COMPAT-001`: legacy artifact fixture normalizes safely

- **Type:** Internal unit/store compatibility test.
- **Purpose:** Existing fixtures do not break runtime but do not keep old product semantics.
- **Preconditions:** Write a legacy artifact JSON file with `kind="design-handoff"`, `content={"body":"legacy body"}`, `task_id="task-design-old"`, `revision=1`, and `is_current=true`.
- **Steps:** Call `env_store.get_artifact(<id>)`, then `env_store.save_artifact()` on the returned object.
- **Expected:** Loaded object has `template="design"`, `body="legacy body"`, `status="draft"`, `published_to_track=null`, `authors` containing the legacy buddy. Saved JSON omits `kind`, `content`, and `task_id`.
- **Failure means:** Compatibility either crashes or preserves a long-lived user-facing dual path.
- **Suggested test:** `tests/test_env_store_v2.py::ArtifactCompatibilityTests::test_legacy_kind_content_task_artifact_normalizes_to_v1_draft`.

### `ACP-ART-001`: create private draft artifact

- **Type:** Black-box service/contract test.
- **Purpose:** Artifact creation no longer requires a task and draft is private.
- **Preconditions:** PM runtime instance; no task exists.
- **Steps:** Dispatch `artifact.create_revision` with `title`, `summary`, `body`, `template="brief"`, and no `published_to_track`.
- **Expected:** `ok=true`, `state_changed=true`, `created_ids` contains the artifact id, stored artifact has `status="draft"`, `published_to_track=null`, `created_by="pm"`, `authors=["pm"]`, and no task linkage.
- **Failure means:** Artifact creation is still task-bound or cannot represent draft pages.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_create_revision_creates_private_draft_without_task`.

### `ACP-ART-002`: publish directly to track at creation

- **Type:** Black-box service/contract test.
- **Purpose:** Main publish path is direct artifact-to-track publication.
- **Preconditions:** Active track `track-art-v1` exists; Design runtime instance has no task.
- **Steps:** Dispatch `artifact.create_revision` with `template="design"`, Markdown `body`, `status="published"`, and `published_to_track="track-art-v1"`.
- **Expected:** `ok=true`; artifact has `status="published"` and `published_to_track`; `track.get` returns the artifact in `shared_materials`; no task file is created and track JSON has no `task_ids`.
- **Failure means:** The implementation still needs `track -> task -> artifact` to publish shared content.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_create_revision_publishes_current_artifact_directly_to_track`.

### `ACP-ART-003`: publish owned draft to track

- **Type:** Black-box service/contract test.
- **Purpose:** Lifecycle supports draft review before publication.
- **Preconditions:** Dev owns draft artifact `art-dev-draft-r1`; active track exists.
- **Steps:** Dispatch `artifact.publish` with `artifact_id` and `track_id`.
- **Expected:** `ok=true`, `state_changed=true`, `updated_ids` includes artifact id, stored artifact has `status="published"` and `published_to_track=track_id`, and `artifact.list --track-id` includes it.
- **Failure means:** Draft lifecycle cannot advance to shared material.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_publish_owned_draft_to_track`.

### `ACP-ART-004`: non-author cannot publish draft

- **Type:** Black-box negative test.
- **Purpose:** Drafts stay private until an author publishes.
- **Preconditions:** PM owns draft artifact; Dev runtime instance; active track exists.
- **Steps:** Dev dispatches `artifact.publish`.
- **Expected:** `ok=false`, `permission_boundary="artifact.authors"`, `state_changed=false`, artifact remains draft.
- **Failure means:** Private drafts leak write authority.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_publish_rejects_non_author_draft`.

### `ACP-LIFE-001`: draft is not visible in track shared materials

- **Type:** Black-box behavior test.
- **Purpose:** Draft status controls default track visibility.
- **Preconditions:** Active track exists; PM owns draft with `published_to_track=null`.
- **Steps:** PM and Dev call `track.get` and `artifact.list --track-id`.
- **Expected:** Draft artifact id is absent from both responses. PM can still `artifact.get` the draft by id. Dev `artifact.get` rejects with no body leak.
- **Failure means:** Draft artifacts are being treated as collaboration material.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_draft_is_private_and_absent_from_shared_materials`.

### `ACP-LIFE-002`: published artifact is readable by every buddy

- **Type:** Black-box integration test.
- **Purpose:** Track publication grants collaboration readability without task relation.
- **Preconditions:** PM publishes `brief` artifact to active track. No Design, Dev, Market, or Test task exists.
- **Steps:** Dispatch `artifact.get` as `pm`, `design`, `dev`, `market`, and `test`.
- **Expected:** Every response has `ok=true`, `read_scope` says published track artifact, and artifact body equals seeded Markdown.
- **Failure means:** Visibility still depends on task relation, ownership, or buddy role.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_current_published_artifact_readable_by_all_buddies_without_task`.

### `ACP-LIFE-003`: archived artifact leaves default shared materials

- **Type:** Black-box lifecycle test.
- **Purpose:** Archived artifacts are not active collaboration material.
- **Preconditions:** Active track has two current published artifacts.
- **Steps:** Author dispatches `artifact.archive` for one artifact, then calls `track.get` and `artifact.list --track-id`.
- **Expected:** Archived artifact is absent from `shared_materials` and artifact list. `artifact.get` by id succeeds with `read_scope="archived artifact by id"`, `status="archived"`, `is_current=false`, and it never appears as current.
- **Failure means:** Archived content remains active shared material.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_archive_removes_artifact_from_default_shared_materials`.

### `ACP-LIFE-004`: archived track blocks publication and comments

- **Type:** Black-box negative test.
- **Purpose:** Track archive is a hard collaboration boundary.
- **Preconditions:** Track status is `archived`.
- **Steps:** Dispatch `artifact.create_revision` with `published_to_track`, `artifact.publish`, `comment.add` on track, and `comment.add` on a published artifact under the archived track.
- **Expected:** Each response has `ok=false`, `permission_boundary="track.lifecycle_status"`, `state_changed=false`.
- **Failure means:** Archived tracks can still receive active collaboration material.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_archived_track_rejects_publication_and_comments`.

### `ACP-REV-001`: new revision supersedes current revision

- **Type:** Black-box service test.
- **Purpose:** Body changes create a revision chain.
- **Preconditions:** PM has current published artifact `art-scope-r1`.
- **Steps:** Dispatch `artifact.create_revision` with `supersedes_artifact_id="art-scope-r1"` and revised Markdown body.
- **Expected:** New artifact has `revision=2`, `supersedes_artifact_id="art-scope-r1"`, `is_current=true`, same `published_to_track`; old artifact has `is_current=false` and unchanged body.
- **Failure means:** Accepted content changes mutate old truth or fail to mark currentness.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_create_revision_supersedes_current_artifact_without_mutating_old_body`.

### `ACP-REV-002`: old revision traceable but not default-visible

- **Type:** Black-box behavior test.
- **Purpose:** Preserve history without cluttering track shared materials.
- **Preconditions:** Track has artifact r1 superseded by r2.
- **Steps:** Dev calls `track.get`, `artifact.list --track-id`, `artifact.get r2`, and `artifact.get r1`.
- **Expected:** `track.get` and `artifact.list` show r2 only. `artifact.get r2` includes revision-chain summary referencing r1. `artifact.get r1` succeeds by id with `is_current=false` and old body.
- **Failure means:** History is either lost or pollutes default shared materials.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_old_revision_traceable_by_id_but_not_default_shared_material`.

### `ACP-REV-003`: cannot supersede non-current revision

- **Type:** Black-box negative test.
- **Purpose:** Currentness rules stay deterministic.
- **Preconditions:** r1 is superseded by r2.
- **Steps:** Author dispatches `artifact.create_revision` with `supersedes_artifact_id=r1`.
- **Expected:** `ok=false`, `permission_boundary="artifact.currentness"`, `state_changed=false`.
- **Failure means:** Revision chain can fork accidentally.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_create_revision_rejects_non_current_supersedes_target`.

### `ACP-TEMPLATE-001`: all templates share same visibility

- **Type:** Black-box parameterized behavior test.
- **Purpose:** Template is not a permission or visibility rule.
- **Preconditions:** Active track exists; no tasks exist.
- **Steps:** For each template `brief`, `proposal`, `design`, `decision`, `proof`, and `note`, publish an artifact and read it as every buddy.
- **Expected:** Read behavior is identical for every template.
- **Failure means:** Template values are driving permissions or visibility.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactTemplateSemanticsTests::test_template_values_do_not_change_published_visibility`.

### `ACP-TEMPLATE-002`: template does not enforce body schema

- **Type:** Black-box negative/positive behavior test.
- **Purpose:** No per-template schema.
- **Preconditions:** Active track exists.
- **Steps:** Publish a `design` artifact with compact Markdown lacking suggested headings; publish a `proof` artifact with prose body.
- **Expected:** Both succeed if body is non-empty Markdown string.
- **Failure means:** Runtime is enforcing template-specific sections.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactTemplateSemanticsTests::test_template_does_not_require_body_headings`.

### `ACP-TEMPLATE-003`: unsupported template rejects

- **Type:** Black-box payload validation test.
- **Purpose:** Keep the V1 template set small.
- **Preconditions:** Active track exists.
- **Steps:** Dispatch `artifact.validate_payload` and `artifact.create_revision` with `template="design-handoff"` and `template="prd"`.
- **Expected:** `ok=false`, `E_ARTIFACT_PAYLOAD`, `correctable_fields` includes `template`.
- **Failure means:** Old kind taxonomy remains active.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactTemplateSemanticsTests::test_unsupported_legacy_kind_values_reject_as_new_template_payload`.

### `ACP-TEMPLATE-004`: template does not drive workflow

- **Type:** Contract/semantic test.
- **Purpose:** No workflow engine by template.
- **Preconditions:** Tool registry and semantics loaded.
- **Steps:** Inspect `operation_semantics()` for artifact and track actions.
- **Expected:** No action row contains template-specific next action, permission, state transition, owner, or required sequence. Template appears only as label/writing guidance.
- **Failure means:** The runtime is drifting toward rule processing by template.
- **Suggested test:** `tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_template_is_soft_label_in_operation_semantics`.

### `ACP-TRACK-001`: track shared materials derive from current published artifacts

- **Type:** Black-box integration test.
- **Purpose:** Default track view uses the V1 shared material source.
- **Preconditions:** Track has current published artifacts r2 and design r1, plus draft, archived, and superseded artifacts.
- **Steps:** Dispatch `track.get`.
- **Expected:** `shared_materials` contains only current published non-archived artifacts r2 and design r1. It excludes draft, archived, and superseded artifacts.
- **Failure means:** Shared materials include wrong lifecycle/currentness states.
- **Suggested test:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_track_get_shared_materials_are_current_published_artifacts`.

### `ACP-TRACK-002`: track.get does not leak full body

- **Type:** Black-box no-leak test.
- **Purpose:** Track shared material summaries are not artifact body reads.
- **Preconditions:** Published artifact body contains unique string `FULL-BODY-ONLY`.
- **Steps:** Dispatch `track.get` and serialize response JSON.
- **Expected:** Response contains artifact id, title, summary, template, status, revision, and counts. It does not contain `FULL-BODY-ONLY` or a `body` key inside shared material rows.
- **Failure means:** Track orientation leaks full artifact content.
- **Suggested test:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_track_get_returns_summaries_without_artifact_body`.

### `ACP-TRACK-003`: artifact.list matches track.get shared materials

- **Type:** Black-box consistency test.
- **Purpose:** Track and artifact tools agree on default material set.
- **Preconditions:** Track has mixed artifact lifecycle states.
- **Steps:** Dispatch `track.get` and `artifact.list --track-id`.
- **Expected:** Artifact id sets and summary fields match exactly for current published artifacts.
- **Failure means:** Users see different shared material truth depending on entry point.
- **Suggested test:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_track_get_shared_materials_match_artifact_list`.

### `ACP-TRACK-004`: removed track relation actions are absent

- **Type:** Contract/CLI negative test.
- **Purpose:** Task relation is not an active collaboration path.
- **Preconditions:** Tool registry loaded.
- **Steps:** Inspect registry, dispatch handlers, CLI help, compact affordances, and runtime status for `track.join`, `track.attach_task`, and `track.detach_task`.
- **Expected:** Actions are absent. Broker dispatch rejects them with `E_ENV_TOOL`, `state_changed=false`.
- **Failure means:** The old task relation bridge remains user-visible.
- **Suggested test:** `tests/test_env_tool_router.py::EnvToolRouterTests::test_track_relation_actions_are_removed_from_active_surface`.

### `ACP-TASK-001`: tasks are private and list/get owner-only

- **Type:** Black-box service test.
- **Purpose:** Task tool remains active-buddy private.
- **Preconditions:** PM and Dev tasks exist, both with optional `track_id`.
- **Steps:** Dev dispatches `task.list` and `task.get` for PM task.
- **Expected:** Dev list returns only Dev tasks. PM task get rejects with `permission_boundary="task.buddy_scope"`.
- **Failure means:** Task privacy was weakened while removing task bridge.
- **Suggested test:** `tests/test_task_env_tool.py::TaskEnvToolTests::test_task_list_get_remain_active_buddy_private`.

### `ACP-TASK-002`: task track hint does not mutate track

- **Type:** Black-box state mutation test.
- **Purpose:** `task.track_id` is private organization metadata only.
- **Preconditions:** Active track exists with no shared materials.
- **Steps:** Dev creates task with `track_id`; compare track JSON before/after.
- **Expected:** Task stores `track_id`; track JSON is unchanged except no mutation at all; `track.get.shared_materials` remains empty.
- **Failure means:** Tasks still mutate track collaboration state.
- **Suggested test:** `tests/test_task_env_tool.py::TaskEnvToolTests::test_task_track_id_hint_does_not_mutate_track_state`.

### `ACP-TASK-003`: task relation does not grant draft read

- **Type:** Black-box negative test.
- **Purpose:** Task is not a visibility bridge.
- **Preconditions:** PM owns draft artifact; Dev has task with same `track_id`.
- **Steps:** Dev dispatches `artifact.get` for draft.
- **Expected:** `ok=false`, `permission_boundary="artifact.status"`, no body leak.
- **Failure means:** Task relation is still granting artifact reads.
- **Suggested test:** `tests/test_task_env_tool.py::TaskEnvToolTests::test_task_track_hint_does_not_grant_draft_artifact_read`.

### `ACP-TASK-004`: task response contains no artifact linkage fields

- **Type:** Contract test.
- **Purpose:** Task output does not teach old artifact slots.
- **Preconditions:** Dev task exists; legacy task fixture may contain `artifact_ids` and `artifact_slots`.
- **Steps:** Dispatch `task.get` and serialize response.
- **Expected:** Response has no `artifact_ids`, `artifact_slots`, `current_artifacts`, or `comment_ids`.
- **Failure means:** Task remains part of artifact collaboration surface.
- **Suggested test:** `tests/test_task_env_tool.py::TaskEnvToolTests::test_task_get_omits_artifact_linkage_fields`.

### `ACP-COMMENT-001`: add/list track comment

- **Type:** Black-box service test.
- **Purpose:** Track comments are independent objects.
- **Preconditions:** Active track exists.
- **Steps:** Dispatch `comment.add` for target track, then `comment.list`.
- **Expected:** Add returns `comment_id`, `thread_id`, `status="open"`, `by_buddy`, and `state_changes` with object type `comment`. Track JSON is unchanged. List returns the comment in flat and grouped thread output.
- **Failure means:** Comment relations are not independent or thread shape is missing.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_add_and_list_track_comment_thread_without_target_mutation`.

### `ACP-COMMENT-002`: add/list artifact comment

- **Type:** Black-box service test.
- **Purpose:** Artifact comments do not enter artifact body.
- **Preconditions:** Published artifact exists with body `Original body`.
- **Steps:** Add comment on artifact, list comments, then `artifact.get`.
- **Expected:** Comment appears in comment list and counts. `artifact.get.artifact.body == "Original body"` and does not contain comment text.
- **Failure means:** Discussion is being mixed into document truth.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_artifact_comment_is_separate_from_artifact_body`.

### `ACP-COMMENT-003`: artifact_section comment requires anchor

- **Type:** Black-box validation test.
- **Purpose:** Section comments are anchored, not implicit free-form artifact comments.
- **Preconditions:** Published artifact exists.
- **Steps:** Add `artifact_section` comment without `anchor`, then with `anchor="Current Conclusion"`.
- **Expected:** Missing anchor rejects with `E_COMMENT_PAYLOAD`; anchored comment succeeds and stores `anchor`.
- **Failure means:** Section target is ambiguous.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_artifact_section_comment_requires_anchor`.

### `ACP-COMMENT-004`: optional revision reference is validated

- **Type:** Black-box validation test.
- **Purpose:** Anchor can point to a concrete revision when needed.
- **Preconditions:** Artifact r1 and r2 exist in one chain; unrelated artifact exists.
- **Steps:** Add section comment on r2 with `artifact_revision_id=r1`, then with unrelated artifact id.
- **Expected:** Same-chain revision succeeds. Unrelated revision rejects with `permission_boundary="comment.artifact_revision_scope"`.
- **Failure means:** Revision anchors can point to irrelevant content.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_artifact_section_revision_reference_must_belong_to_same_chain`.

### `ACP-COMMENT-005`: replies stay in same target and thread

- **Type:** Black-box thread test.
- **Purpose:** Replies do not cross discussion targets.
- **Preconditions:** Track A and Track B each have a root comment.
- **Steps:** Add reply on Track A to Track A root; then add reply on Track A to Track B root.
- **Expected:** Same-target reply succeeds with same `thread_id`. Cross-target reply rejects with `permission_boundary="comment.reply_to_scope"`.
- **Failure means:** Thread structure can corrupt target discussions.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_reply_to_must_stay_on_same_target_thread`.

### `ACP-COMMENT-006`: resolve and reopen thread

- **Type:** Black-box mutation test.
- **Purpose:** Open/resolved state is effective.
- **Preconditions:** Root comment with one reply exists.
- **Steps:** Dispatch `comment.resolve` on reply id; list comments; dispatch `comment.reopen` on root id; list again.
- **Expected:** Resolve sets all comments in thread to `status="resolved"` and list status count reflects it. Reopen sets all comments in thread to `status="open"`.
- **Failure means:** Resolved threads are only decorative fields or do not apply to replies.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_resolve_and_reopen_thread_updates_thread_status`.

### `ACP-COMMENT-007`: mentions validate declared buddies

- **Type:** Black-box validation test.
- **Purpose:** Mentions are structured metadata.
- **Preconditions:** Active track exists.
- **Steps:** Add comment with `mentions=["pm","dev"]`, then with `mentions=["ops"]`.
- **Expected:** Known buddies succeed and persist mentions. Unknown buddy rejects with `E_COMMENT_PAYLOAD`.
- **Failure means:** Mentions are unvalidated strings or silently create unknown recipients.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_mentions_must_reference_manifest_buddies`.

### `ACP-COMMENT-008`: comment target read boundary matches artifact read boundary

- **Type:** Black-box negative test.
- **Purpose:** Comments cannot leak unreadable artifacts.
- **Preconditions:** PM draft artifact exists; Dev has no authorship.
- **Steps:** Dev dispatches `comment.add` and `comment.list` for that artifact.
- **Expected:** Both reject with same artifact read boundary as `artifact.get`, no body or comment leak.
- **Failure means:** Comment tool bypasses artifact visibility.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_tool_reuses_artifact_read_boundary_for_drafts`.

### `ACP-COMMENT-009`: archived artifact rejects new comments

- **Type:** Black-box negative test.
- **Purpose:** Archived artifacts are not active discussion material.
- **Preconditions:** Published artifact is archived.
- **Steps:** Dispatch `comment.add` on artifact and artifact section.
- **Expected:** Both reject with `permission_boundary="artifact.status"`.
- **Failure means:** Archived content remains active collaboration material.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_archived_artifact_rejects_comment_add`.

### `ACP-COMMENT-010`: decision changes require revision or decision artifact

- **Type:** Integration behavior test.
- **Purpose:** Comments do not become facts automatically.
- **Preconditions:** Artifact body says `Decision: A`; comment thread says `Change to B` and is resolved.
- **Steps:** Resolve comment; call `artifact.get`; then create new `decision` artifact or revision with `Decision: B`.
- **Expected:** After resolve alone, artifact body still says `Decision: A`. After revision or decision artifact creation, track shared materials include the new current published content.
- **Failure means:** Resolution mutates artifact truth implicitly.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_resolved_comment_does_not_mutate_artifact_truth_without_revision_or_decision_artifact`.

### `ACP-DESIGN-001`: lightweight design artifact supports Markdown design intent

- **Type:** Black-box positive test.
- **Purpose:** Design can publish sufficient Markdown without media or external files.
- **Preconditions:** Active track exists.
- **Steps:** Design publishes `template="design"` with Markdown sections `Goal`, `User Flow`, `Layout`, `States`, `Interaction`, `Copy`, `Acceptance`, and `Open Questions`.
- **Expected:** Artifact publishes and `artifact.get` returns exact Markdown body. Dev can read it without task relation.
- **Failure means:** Design artifact cannot serve as lightweight handoff page.
- **Suggested test:** `tests/test_artifact_env_tool.py::DesignArtifactTests::test_lightweight_design_markdown_artifact_is_readable_by_dev`.

### `ACP-DESIGN-002`: design artifact does not require external source

- **Type:** Black-box provenance test.
- **Purpose:** External design links are optional provenance, not required reading path.
- **Preconditions:** Active track exists.
- **Steps:** Publish one design artifact without source refs and one with external source ref.
- **Expected:** Both are readable. Body contains sufficient design conclusion. `source_refs` presence does not affect visibility or body validation.
- **Failure means:** Runtime makes external design tools required.
- **Suggested test:** `tests/test_artifact_env_tool.py::DesignArtifactTests::test_design_artifact_source_refs_are_optional_provenance`.

### `ACP-PROV-001`: source_refs do not grant read access

- **Type:** Black-box negative test.
- **Purpose:** Provenance is not visibility authority.
- **Preconditions:** PM draft artifact exists; Dev publishes artifact with `source_refs=[{"type":"artifact","id":<pm-draft>}]` without read claim.
- **Steps:** Dev and Test call `artifact.get` for PM draft and Dev artifact.
- **Expected:** Dev artifact follows its own publication status. PM draft remains unreadable to non-authors.
- **Failure means:** Source refs are acting as read grants.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactProvenanceTests::test_source_refs_do_not_grant_artifact_read_access`.

### `ACP-PROV-002`: body must stand alone without source_refs

- **Type:** Contract validation test.
- **Purpose:** Source refs are auxiliary.
- **Preconditions:** Active track exists.
- **Steps:** Try to publish artifact with empty body and only source refs; then publish artifact with non-empty body and source refs.
- **Expected:** Empty body rejects. Non-empty body succeeds. Response does not mark source refs as required reading.
- **Failure means:** Artifact can become a link-only shell.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactProvenanceTests::test_source_refs_cannot_replace_required_body`.

### `ACP-CONTRACT-001`: registry, semantics, dispatch, and CLI are aligned

- **Type:** Contract test.
- **Purpose:** Tool surface is coherent.
- **Preconditions:** No runtime state needed.
- **Steps:** Compare `TOOL_REGISTRY`, `operation_semantics()`, `dispatch_handler_actions()`, and CLI help.
- **Expected:** Artifact actions include `list`, `get`, `validate_payload`, `create_revision`, `publish`, `archive`, `update_metadata`; comment actions include `add`, `list`, `resolve`, `reopen`; removed track relation actions are absent.
- **Failure means:** Runtime surface drift creates commands that cannot execute.
- **Suggested test:** `tests/test_env_tool_router.py::EnvToolRouterTests::test_artifact_collaboration_page_actions_are_registry_dispatch_cli_aligned`.

### `ACP-CONTRACT-002`: artifact mutation response shape

- **Type:** Contract test.
- **Purpose:** Mutating tools expose state changes consistently.
- **Preconditions:** Active track exists.
- **Steps:** Dispatch successful `artifact.create_revision`, `artifact.publish`, `artifact.archive`, `comment.add`, `comment.resolve`.
- **Expected:** Each success has `ok=true`, `state_changed=true`, `durability="durable"`, and correct `created_ids`, `updated_ids`, and `state_changes`.
- **Failure means:** Env-tool response contract is not reliable for agents.
- **Suggested test:** `tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_artifact_comment_mutations_include_state_change_contract`.

### `ACP-CONTRACT-003`: rejection response shape and no leak

- **Type:** Contract/no-leak test.
- **Purpose:** Blocked reads explain boundary without leaking body.
- **Preconditions:** PM draft body contains `PRIVATE-DRAFT-BODY`; Dev instance exists.
- **Steps:** Dev dispatches `artifact.get`, `comment.add`, and `comment.list` on draft.
- **Expected:** Each rejection has `ok=false`, `state_changed=false`, `permission_boundary`, `why_blocked`, `allowed_next_actions`, and no `PRIVATE-DRAFT-BODY`.
- **Failure means:** Boundary failures are either unhelpful or leak content.
- **Suggested test:** `tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_blocked_artifact_and_comment_reads_include_boundary_without_body_leak`.

### `ACP-CONTRACT-004`: allowed_next_actions reference registered tools

- **Type:** Contract test.
- **Purpose:** Recovery guidance is executable.
- **Preconditions:** Collect success and rejection responses from artifact, track, comment, and task tools.
- **Steps:** Inspect `allowed_next_action_options` and string hints where present.
- **Expected:** Any structured tool/action pair exists in registry. Command hints use `python3 scripts/env/client.py ...` and never raw state paths.
- **Failure means:** Runtime feedback tells agents to use nonexistent tools or raw files.
- **Suggested test:** `tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_allowed_next_actions_reference_registered_tools_only`.

### `ACP-CONTEXT-001`: context agrees with track and artifact tools

- **Type:** Integration/contract test.
- **Purpose:** Orientation surface is consistent.
- **Preconditions:** Track has current published, draft, archived, and superseded artifacts plus comments.
- **Steps:** Dispatch `context.get`, `context.summarize`, `track.get`, `artifact.list`, and `comment.list`.
- **Expected:** Context artifact summaries match `artifact.list` current published set, contain no full body, expose comment counts consistently, and do not include task-derived artifact rows.
- **Failure means:** Context is teaching a different collaboration model from env tools.
- **Suggested test:** `tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_track_artifact_comment_surfaces_agree_on_current_shared_materials`.

### `ACP-NEG-001`: unsupported design/media payload fields reject

- **Type:** Black-box negative test.
- **Purpose:** No media, asset, material, block tree, or Figma replacement in V1.
- **Preconditions:** Active track exists.
- **Steps:** Dispatch `artifact.create_revision` with `media`, `asset_id`, `material_id`, `blocks`, `figma_file`, and `attachments`.
- **Expected:** Each rejects with `E_ARTIFACT_PAYLOAD`, `state_changed=false`, and `correctable_fields` naming the field.
- **Failure means:** V1 scope is drifting into an asset/design platform.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactNonGoalTests::test_media_asset_material_block_figma_payload_fields_reject`.

### `ACP-NEG-002`: unsupported asset/material/media tools absent

- **Type:** Router/CLI negative test.
- **Purpose:** Non-goal systems are not registered.
- **Preconditions:** No runtime state needed.
- **Steps:** Dispatch tools `asset`, `material`, `media`, `figma`, and `block`; inspect CLI help.
- **Expected:** Broker rejects unknown tools with `E_ENV_TOOL`; CLI help does not list them.
- **Failure means:** A non-goal tool surface exists.
- **Suggested test:** `tests/test_env_tool_router.py::EnvToolRouterTests::test_non_goal_asset_material_media_tools_are_absent`.

### `ACP-NEG-003`: per-template schema fields reject

- **Type:** Black-box negative test.
- **Purpose:** Template does not create schema-specific payloads.
- **Preconditions:** Active track exists.
- **Steps:** Publish `template="design"` with payload keys `layout`, `states`, `interaction` outside `body`; publish `template="proof"` with `verification_result` outside `body`.
- **Expected:** Unsupported keys reject. Same content succeeds when written inside Markdown `body`.
- **Failure means:** Runtime is building per-template body schemas.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactNonGoalTests::test_template_specific_payload_schema_fields_reject`.

### `ACP-NEG-004`: task-bound artifact payload rejects

- **Type:** Black-box negative test.
- **Purpose:** New artifact writes cannot use task as publication path.
- **Preconditions:** Dev task exists.
- **Steps:** Dispatch `artifact.create_revision` with `task_id` and no `published_to_track`.
- **Expected:** `ok=false`, `E_ARTIFACT_PAYLOAD`, no artifact created.
- **Failure means:** The old task-bound artifact write path remains active.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactNonGoalTests::test_create_revision_rejects_task_id_payload`.

### `ACP-NEG-005`: template cannot grant permission

- **Type:** Black-box negative test.
- **Purpose:** No permissions driven by template.
- **Preconditions:** PM draft artifact with `template="proof"` exists.
- **Steps:** Dev attempts `artifact.get` and `comment.add`.
- **Expected:** Both reject because artifact is draft, despite template value.
- **Failure means:** Template is influencing permission.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactNonGoalTests::test_template_does_not_grant_permission_to_draft`.

### `ACP-NEG-006`: no comment status inside artifact body

- **Type:** Black-box no-leak test.
- **Purpose:** Resolved/open comments do not alter body.
- **Preconditions:** Artifact body contains stable Markdown; open and resolved comments exist.
- **Steps:** `artifact.get`; serialize artifact body.
- **Expected:** Body does not include comment ids, comment content, `open`, or `resolved` status. Comment counts may appear outside body.
- **Failure means:** Comment collaboration state is embedded into document truth.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentNonGoalTests::test_comment_status_never_embeds_into_artifact_body`.

### `ACP-NEG-007`: source_refs cannot be media or material registry

- **Type:** Store/service negative test.
- **Purpose:** Provenance types stay narrow.
- **Preconditions:** Active track exists.
- **Steps:** Dispatch artifact create with `source_refs` types `asset`, `media`, `material`, `figma`, and `block`.
- **Expected:** Each rejects with `E_SOURCE_REFS`.
- **Failure means:** Source refs are being used to introduce non-goal systems.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactNonGoalTests::test_source_refs_reject_asset_media_material_figma_block_types`.

### `ACP-DOC-001`: active guidance uses template/body language

- **Type:** Semantic docs test.
- **Purpose:** Runtime docs teach V1 vocabulary.
- **Preconditions:** Repository checkout.
- **Steps:** Scan active docs/skills/contracts/schemas for artifact output examples.
- **Expected:** Examples use `template` and `body`. No active guidance instructs `kind` as product vocabulary.
- **Failure means:** Agents will keep creating old kind-first artifacts.
- **Suggested test:** `tests/test_runtime_skills.py::RuntimeSkillsTests::test_active_artifact_guidance_uses_template_body_language`.

### `ACP-DOC-002`: active guidance excludes task-bound artifact visibility

- **Type:** Semantic docs test.
- **Purpose:** Runtime docs do not teach old read bridge.
- **Preconditions:** Repository checkout.
- **Steps:** Run targeted scan over `scripts`, `buddyswitch`, `framework`, `tools`, `README.md`, and `AGENTS.md`, excluding `docs/memo/**` and `docs/spec/**`.
- **Expected:** No active surface instructs `track -> task -> artifact`, `track.join` for artifact visibility, task relation artifact read, or artifact visibility through private task chains.
- **Failure means:** Skills can reintroduce retired workflows even if code is correct.
- **Suggested test:** `tests/test_repo_consistency.py::RepoConsistencyTests::test_active_guidance_excludes_task_bound_artifact_visibility`.

### `ACP-DOC-003`: active guidance excludes non-goal platform wording

- **Type:** Semantic docs test.
- **Purpose:** Prevent scope drift.
- **Preconditions:** Repository checkout.
- **Steps:** Scan active surfaces for instructions to build or use asset registry, material registry, artifact-local media, block tree, Figma replacement, template workflow engine, or template permission.
- **Expected:** No hits except negative test definitions and explicit "do not" guidance.
- **Failure means:** Active docs contradict V1 non-goals.
- **Suggested test:** `tests/test_repo_consistency.py::RepoConsistencyTests::test_active_guidance_excludes_artifact_non_goal_platform_wording`.

### `ACP-DOC-004`: output schemas accept template/title/body

- **Type:** Schema contract test.
- **Purpose:** Role result schemas align with V1 artifact shape.
- **Preconditions:** Load `framework/schemas/{market,pm,design,dev,test}/*-result.json`.
- **Steps:** Validate sample role result with artifact `template/title/body`; validate sample with `kind/content`.
- **Expected:** `template/title/body` sample passes; `kind/content` sample rejects.
- **Failure means:** Role output layer still requests old artifact shape.
- **Suggested test:** `tests/test_output_schema_boundaries.py::OutputSchemaBoundaryTests::test_role_result_schemas_use_template_title_body_artifacts`.

### `ACP-DOC-005`: runtime AGENTS and skills describe task/comment/artifact boundaries

- **Type:** Semantic docs test.
- **Purpose:** Buddy-facing guidance matches object responsibilities.
- **Preconditions:** Materialize or read runtime skill templates.
- **Steps:** Inspect shared skills and buddy AGENTS templates.
- **Expected:** Artifact is durable shared track content, comment is discussion, task is private execution, message is temporary coordination. No file says comments are artifact body or tasks are visibility bridges.
- **Failure means:** Runtime instructions contradict object boundaries.
- **Suggested test:** `tests/test_runtime_skills.py::RuntimeSkillsTests::test_runtime_guidance_states_artifact_comment_task_message_boundaries`.

### `ACP-E2E-001`: full cross-buddy collaboration page loop

- **Type:** Black-box integration test.
- **Purpose:** Prove V1 works end to end.
- **Preconditions:** Runtime workspace supports PM, Design, Dev, Test; no tasks are required.
- **Steps:** PM creates track and publishes `brief`; Design reads track and artifact, comments on artifact section mentioning PM; PM resolves by creating new revision; Design publishes `design`; Dev reads current artifacts; Test publishes `proof`; PM archives the old proof or stale artifact.
- **Expected:** Every buddy reads current published artifacts without task relation. Comments remain separate. Default shared materials show only current published non-archived artifacts. Revision chain is traceable.
- **Failure means:** Main product loop is incomplete.
- **Suggested test:** `tests/test_env_layer_end_to_end.py::ArtifactCollaborationPageEndToEndTests::test_cross_buddy_artifact_collaboration_page_loop`.

## 6. Migration And Regression Tests

### `ACP-COMPAT-002`: legacy track task_ids do not create shared materials

- **Type:** Compatibility regression test.
- **Purpose:** Old track fixtures do not resurrect task-derived materials.
- **Preconditions:** Legacy track JSON includes `task_ids` pointing to tasks with artifacts.
- **Steps:** Load track and call `track.get`.
- **Expected:** Track loads without crash. `track.get.shared_materials` is empty until artifacts have canonical `published_to_track/status/is_current`.
- **Failure means:** Task-derived shared materials remain active.
- **Suggested test:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_legacy_track_task_ids_do_not_create_shared_materials`.

### `ACP-COMPAT-003`: legacy manifest artifact_kinds normalizes to artifact_templates

- **Type:** Manifest compatibility test.
- **Purpose:** Loader tolerates old key while checked-in manifest uses new key.
- **Preconditions:** Temporary manifest fixture with `artifact_kinds`.
- **Steps:** Load manifest fixture through `env_manifest.load_manifest()`.
- **Expected:** Loaded buddy rows expose `artifact_templates`; checked-in `buddyswitch/manifest.toml` contains `artifact_templates` and no `artifact_kinds`.
- **Failure means:** Compatibility breaks old fixtures or canonical manifest keeps old vocabulary.
- **Suggested test:** `tests/test_env_manifest_v2.py::EnvManifestV2Tests::test_legacy_artifact_kinds_manifest_key_normalizes_to_templates`.

### `ACP-COMPAT-004`: legacy comment author_buddy normalizes to by_buddy

- **Type:** Store compatibility test.
- **Purpose:** Existing comments survive V1 rename.
- **Preconditions:** Legacy comment file with `author_buddy`.
- **Steps:** Call `env_store.get_comment()` and `comment.list`.
- **Expected:** Returned comment has `by_buddy`, `thread_id`, `status`, and no `author_buddy` in env-tool response.
- **Failure means:** Comment migration breaks existing state or preserves user-facing dual fields.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_legacy_author_buddy_comment_normalizes_to_by_buddy`.

## 7. Final Verification Commands

Focused runtime behavior:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_store_v2.py \
  tests/test_artifact_env_tool.py \
  tests/test_track_env_tool.py \
  tests/test_task_env_tool.py \
  tests/test_comment_env_tool.py \
  -q
```

Expected result: all store, artifact, track, task, and comment V1 behavior tests pass.

Contract, context, projection, docs, and schema verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
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
  tests/test_repo_consistency.py \
  -q
```

Expected result: all contract, context, projection, schema, skill, and residue tests pass.

End-to-end verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_layer_end_to_end.py \
  tests/test_turn_integration.py \
  tests/test_runless_runtime_contract.py \
  -q
```

Expected result: full cross-buddy artifact collaboration page loop passes from `tests/test_env_layer_end_to_end.py`.

CLI smoke:

```bash
python3 scripts/env/client.py artifact --help
python3 scripts/env/client.py track --help
python3 scripts/env/client.py comment --help
python3 scripts/turn_runtime.py status
```

Expected result:

- `artifact` help exposes page lifecycle actions and no task-bound or media/asset/material/block commands.
- `track` help exposes `list/get/create/update/archive` and no `join/attach-task/detach-task`.
- `comment` help exposes `add/list/resolve/reopen`.
- Runtime status registry matches contract tests.

Active-surface semantic scan:

```bash
rg -n "artifact_kinds|artifact kind|track\\.join|attach-task|detach-task|task relation.*artifact|track -> task -> artifact|asset registry|material registry|block tree|Figma replacement|template.*permission|template.*workflow" \
  scripts buddyswitch framework tools tests README.md AGENTS.md \
  -g '!docs/memo/**' \
  -g '!docs/spec/**'
```

Expected result: no hits except tests that define the scan and explicit negative "do not" guidance.

## 8. Pass Criteria

The test plan is satisfied when:

- All behavior tests prove artifact V1 creation, publication, reading, listing, lifecycle, and revision currentness.
- Track shared materials are current published artifacts and are consistent across `track`, `artifact`, and `context`.
- Task tests prove tasks are private and cannot bridge artifact visibility.
- Comment tests prove independent storage, targets, threads, resolution, mentions, replies, anchors, and revision references.
- Negative tests prove no media/asset/material/block-tree/Figma replacement or template-driven rules.
- Compatibility tests prove old fixtures normalize without preserving old product semantics.
- Docs/skills/contracts/schema tests prove active guidance points to V1 and not the old direction.
- Final verification commands pass.
