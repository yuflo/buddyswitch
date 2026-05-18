# Track/Artifact PM Runtime Repair Test Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the repaired runtime-visible publication contract from user requirements and collaboration risks, not from current implementation shortcuts.

**Architecture:** Tests exercise broker-routed env.tool calls, persisted JSON, runtime tool catalog/semantics, skill/contract text, and one PM-to-Test main path. Rejections assert no state mutation. Positive paths assert both object mutations and downstream readability through `track.open -> artifact.get`.

**Tech Stack:** `pytest`, Python `unittest`, runtime test workspaces through `RuntimeWorkspaceTestMixin`, `env.tool` router/broker, persisted JSON under temporary `buddyswitch/objects/**`.

---

## Requirements Model

R1. Shared publication has one active route:

```text
artifact.create_revision -> private draft/revision artifact
track.add_material       -> publish existing artifact as current shared material
track.add_proof          -> publish existing artifact as current close proof
track.open               -> read current shared refs
artifact.get             -> read full body for readable artifact id
```

R2. `artifact.create_revision` cannot directly publish to a track. `published_to_track` is set by track publication only.

R3. A draft revision cannot replace current shared material or proof. Current shared refs change only after successful `track.add_material` or `track.add_proof`.

R4. A successful material publication updates both the artifact JSON and track JSON, and `track.open.shared_materials` exposes the current artifact ref.

R5. A successful proof publication updates artifact JSON, `track.close_proof`, and a proof update row.

R6. Superseded artifacts remain traceable and readable by explicit id on non-archived tracks, while `track.open` exposes only current refs.

R7. Archived tracks reject read and publish actions without mutating artifacts or tracks.

R8. Duplicate, already-bound, wrong-owner, legacy inline payload, and cross-track publication attempts reject with actionable feedback and no state mutation.

R9. Design, Dev, and Test can use `track.open -> artifact.get` to read shared artifact bodies without task relation machinery.

R10. PM runtime behavior is not repaired through prompt bulk. PM should produce product-definition output through track/artifact env tools and should not treat read-only `projects/app` as the implementation target.

R11. Runtime-visible tool semantics are specific enough for host choice and recovery. Critical actions cannot have placeholder action semantics.

R12. PM contract, PM skill, `track-tool`, and `artifact-tool` describe the same publication route.

R13. Forbidden stale vocabulary is absent from active runtime guidance. It appears only in explicit legacy normalization tests, negative tests, or repair-context docs.

## Risk Model

Primary regression risks:

- Orphan publication: artifact state says published but the track page does not expose it.
- Dead-end feedback: a successful response points the host to a call that will reject.
- Silent no-op: duplicate publication returns `ok=true` and hides that nothing changed.
- Premature currentness mutation: draft revision marks the current shared artifact non-current before publication.
- Partial mutation: artifact is published but track refs are not updated, or track refs are updated without artifact state.
- Historical loss: superseded material disappears from track JSON or becomes unreadable by explicit id.
- Archived-track leak: archived tracks can still be read or receive new publication.
- Legacy payload drift: active guidance still teaches `kind/content/content.prd`.
- Semantics placeholder drift: action rows exist but do not explain use, inputs, side effects, success, or failures.
- Prompt-layer workaround: PM behavior is fixed by AGENTS/manual text instead of runtime contract and skills.

Testing rules:

- Positive tests assert env.tool response fields and persisted JSON.
- Negative tests capture JSON before the rejected call and compare after the call.
- Tests do not pass by checking only `ok=true`, action names, or field existence.
- Tests start from user-visible requirements and runtime contracts, not from current helper internals.

## Test Matrix

| ID | Level | Requirement | File | Main assertion |
| --- | --- | --- | --- | --- |
| A1 | Integration | R2 | `tests/test_artifact_env_tool.py` | Direct publish input rejects and creates no orphan artifact |
| A2 | Integration | R2 | `tests/test_artifact_env_tool.py` | `status="published"` rejects with no mutation |
| A3 | Integration | R3 | `tests/test_artifact_env_tool.py` | Draft revision does not replace current material |
| A4 | Integration | R6 | `tests/test_artifact_env_tool.py` | Superseded artifact stays readable/traceable with currentness |
| T1 | Integration | R4 | `tests/test_track_env_tool.py` | Material publication updates artifact and track JSON |
| T2 | Integration | R3/R6 | `tests/test_track_env_tool.py` | Replacement happens only after successful material publish |
| T3 | Integration | R5 | `tests/test_track_env_tool.py` | Proof publication updates artifact, close proof, and proof update |
| T4 | Integration | R7 | `tests/test_track_env_tool.py` | Archived track rejects open/publish with no mutation |
| T5 | Integration | R8 | `tests/test_track_env_tool.py` | Duplicate/already-bound/cross-track/wrong-owner reject with no mutation |
| T6 | Integration | R13 | `tests/test_track_env_tool.py` | Legacy inline `kind/content` publish payload rejects |
| E1 | End-to-end | R1/R9 | `tests/test_env_layer_end_to_end.py` | PM -> Design -> Dev -> Test path uses track refs and artifact bodies |
| E2 | End-to-end | R10 | `tests/test_turn_integration.py` | PM product request produces product-definition publication, not project implementation |
| S1 | Contract | R11 | `tests/test_env_tool_semantic_contract.py` | Critical action semantics are non-placeholder |
| S2 | Contract | R1/R11 | `tests/test_env_tool_semantic_contract.py` | Registry payload fields match single publication path |
| R1 | Contract | R4/R5/R8 | `tests/test_env_tool_response_contract.py` | Success/rejection responses expose real state effects |
| F1 | Feedback | R8 | `tests/test_runtime_tool_feedback.py` | Rejections expose boundary, why, correction, durability, no mutation |
| K1 | Skill/contract | R12/R13 | `tests/test_runtime_skills.py` | Skills describe one path and no stale active route |
| C1 | Repo scan | R12/R13 | `tests/test_repo_consistency.py` | Active runtime guidance has no forbidden vocabulary |
| P1 | Profile | R10 | `tests/test_buddy_env_profiles.py` | PM project access remains read-only and track effects are correct |
| M1 | Manual | R10/R15 memo item | Manual verification | PM runtime produces track/artifact state through env tools |

## Detailed Tests

### A1: Direct Publication Input Cannot Create an Orphan

**Level:** Integration

**File:** `tests/test_artifact_env_tool.py`

**Functional requirement:** `artifact.create_revision` cannot create an artifact that claims `published_to_track` while `track.open.shared_materials` or `track.open.close_proof` lacks the ref.

**Initial state:**

- Runtime workspace is empty.
- PM creates `track-orphan-guard` through `track.create`.
- Capture object paths for `art-orphan-r1` and `track-orphan-guard`.

**Operation steps:**

1. PM calls `artifact.create_revision` with:

```json
{
  "artifact_id": "art-orphan-r1",
  "title": "Orphan attempt",
  "summary": "should reject",
  "template": "brief",
  "body": "# Body",
  "published_to_track": "track-orphan-guard"
}
```

2. PM opens `track-orphan-guard`.
3. Read persisted JSON files from the runtime test root.

**Assertions:**

- Env.tool response:
  - `ok=false`
  - `error.code="E_ARTIFACT_PUBLICATION_PATH"`
  - `permission_boundary="artifact.publication_path"`
  - `state_changed=false`
  - `durability="none"`
  - `why_blocked` says `artifact.create_revision` does not publish
  - `correctable_fields` contains `published_to_track`
  - `allowed_next_actions` includes creating a draft and publishing with `track.add_material` or `track.add_proof`
- Persisted JSON:
  - `buddyswitch/objects/artifacts/art-orphan-r1.json` does not exist
  - `track-orphan-guard.json` still has `shared_materials=[]` and `close_proof=[]`
- `track.open` response:
  - `ok=true`
  - `shared_materials=[]`
  - `close_proof=[]`

**Regression value:** Catches the exact orphan-published artifact path described in the memo.

### A2: `status="published"` Is Rejected Before Mutation

**Level:** Integration

**File:** `tests/test_artifact_env_tool.py`

**Functional requirement:** `artifact.create_revision` creates drafts only; callers cannot publish by setting status.

**Initial state:**

- Runtime workspace is empty.
- No track is required.

**Operation steps:**

1. PM calls `artifact.create_revision` with `status="published"` and no `published_to_track`.
2. Capture artifact file existence before and after.

**Assertions:**

- Env.tool response:
  - `ok=false`
  - `error.code="E_ARTIFACT_PUBLICATION_PATH"`
  - `state_changed=false`
  - `durability="none"`
  - `correctable_fields=["status"]`
  - `impact` names no artifact and no track mutation
- Persisted JSON:
  - No artifact file is created.
  - Track directory is unchanged.

**Regression value:** Prevents a second direct-publish route through status alone.

### A3: Draft Revision Does Not Replace Current Shared Material

**Level:** Integration

**File:** `tests/test_artifact_env_tool.py`

**Functional requirement:** Creating a draft revision with `supersedes_artifact_id` must not change current shared material until `track.add_material` succeeds.

**Initial state:**

- PM creates `track-revision-draft`.
- PM creates `art-revision-r1` via `artifact.create_revision(template="brief", body="v1")`.
- PM publishes `art-revision-r1` via `track.add_material(track_id="track-revision-draft", artifact_id="art-revision-r1", label="Brief", summary="v1")`.
- Capture persisted artifact and track JSON.

**Operation steps:**

1. PM calls `artifact.create_revision` for `art-revision-r2` with `supersedes_artifact_id="art-revision-r1"` and body `v2`.
2. PM opens `track-revision-draft`.
3. PM reads `art-revision-r1` and `art-revision-r2`.
4. Dev attempts to read `art-revision-r2`.

**Assertions:**

- Draft creation response:
  - `ok=true`
  - `state_changed=true`
  - `durability="durable"`
  - `state_changes` contains only a draft artifact creation change
  - `artifact.status="draft"`
  - `artifact.published_to_track=null`
  - `artifact.supersedes_artifact_id="art-revision-r1"`
- Persisted JSON:
  - `art-revision-r1.status="published"`
  - `art-revision-r1.published_to_track="track-revision-draft"`
  - `art-revision-r1.is_current=true`
  - `track-revision-draft.shared_materials` current row still references `art-revision-r1`
  - `art-revision-r2.status="draft"`
  - `art-revision-r2.published_to_track=null`
- `track.open`:
  - `shared_materials` contains only `art-revision-r1`
- `artifact.get`:
  - PM can read both bodies
  - Dev cannot read draft `art-revision-r2`

**Regression value:** Prevents the current shared source from disappearing before the replacement is published.

### A4: Superseded Published Artifact Remains Traceable and Readable

**Level:** Integration

**File:** `tests/test_artifact_env_tool.py`

**Functional requirement:** After replacement, the old artifact is no longer current but remains readable by explicit id on the non-archived track.

**Initial state:**

- Use the A3 setup.
- PM publishes `art-revision-r2` with `track.add_material`.

**Operation steps:**

1. Dev opens `track-revision-draft`.
2. Dev reads `art-revision-r1` by id.
3. Dev reads `art-revision-r2` by id.
4. Inspect persisted track JSON.

**Assertions:**

- `track.add_material` response for R2:
  - `ok=true`
  - `state_changes` includes publishing R2 and superseding R1
- Persisted JSON:
  - `track.shared_materials` has R1 with `current=false`
  - `track.shared_materials` has R2 with `current=true`
  - `art-revision-r1.is_current=false`
  - `art-revision-r2.is_current=true`
  - `art-revision-r2.supersedes_artifact_id="art-revision-r1"`
- `track.open`:
  - `shared_materials` exposes only R2
- `artifact.get`:
  - Dev read of R1 succeeds and returns `body="v1"` and `currentness="superseded"`
  - Dev read of R2 succeeds and returns `body="v2"` and `currentness="current"`

**Regression value:** Protects auditability and body readability of replaced shared material.

### T1: Material Publication Updates Artifact and Track JSON

**Level:** Integration

**File:** `tests/test_track_env_tool.py`

**Functional requirement:** `track.add_material` publishes an existing draft artifact as current shared material and mutates both objects.

**Initial state:**

- PM creates `track-material-publish`.
- PM creates `art-material-r1` with `artifact.create_revision(template="brief", body="material body")`.
- Capture persisted track JSON and artifact JSON.

**Operation steps:**

1. PM calls `track.add_material`:

```json
{
  "track_id": "track-material-publish",
  "artifact_id": "art-material-r1",
  "label": "Brief",
  "summary": "Published PM brief"
}
```

2. PM opens the track.
3. Dev reads `art-material-r1`.
4. Inspect persisted JSON.

**Assertions:**

- Env.tool response:
  - `ok=true`
  - `effect_summary` names artifact publication and track material row
  - `state_changed=true`
  - `durability="durable"`
  - `updated_ids` contains both ids
  - `state_changes` includes `published_material` and `material_added`
  - `allowed_next_actions` includes `track.open` and `artifact.get`
- Persisted artifact:
  - `status="published"`
  - `published_to_track="track-material-publish"`
  - `template="brief"`
  - `body="material body"`
  - `is_current=true`
- Persisted track:
  - `shared_materials` has one row with `artifact_id="art-material-r1"`, `kind="brief"`, `label="Brief"`, `from_buddy="pm"`, `summary="Published PM brief"`, `current=true`
  - `close_proof=[]`
- `track.open`:
  - `shared_materials` exposes the same current row
  - body text is not embedded in track response
- `artifact.get` as Dev:
  - returns full body
  - `relation="track_material"`
  - `readable_by_active_buddy=true`

**Regression value:** Catches partial artifact-only or track-only publication.

### T2: Material Replacement Happens Only After Successful Publish

**Level:** Integration

**File:** `tests/test_track_env_tool.py`

**Functional requirement:** Replacement of current material is tied to successful `track.add_material`.

**Initial state:**

- PM creates track.
- PM creates and publishes R1.
- PM creates R2 draft with `supersedes_artifact_id=R1`.
- Capture persisted JSON after R2 draft creation.

**Operation steps:**

1. Attempt to publish R2 to a different track.
2. Attempt to publish R2 to an archived track.
3. Publish R2 to the original track with the same label.
4. Inspect JSON after each operation.

**Assertions:**

- Cross-track rejection:
  - `ok=false`
  - `state_changed=false`
  - `durability="none"`
  - original track JSON equals baseline
  - R1 and R2 artifact JSON equal baseline
- Archived-track rejection:
  - `ok=false`
  - `permission_boundary="track.lifecycle_status"`
  - no artifact mutation
- Successful original-track publish:
  - R1 current ref becomes `current=false`
  - R1 artifact `is_current=false`
  - R2 track ref becomes `current=true`
  - R2 artifact `status="published"`, `published_to_track` original track id, `is_current=true`
  - `track.open.shared_materials` exposes R2 only

**Regression value:** Guards against premature draft currentness mutation and partial failed-publish mutation.

### T3: Proof Publication Updates Artifact, Close Proof, and Proof Update

**Level:** Integration

**File:** `tests/test_track_env_tool.py`

**Functional requirement:** `track.add_proof` publishes an existing proof draft and writes a close proof ref plus a proof update row.

**Initial state:**

- PM creates `track-proof-publish`.
- Test buddy creates `art-proof-r1` with `template="proof"` and body `pass`.

**Operation steps:**

1. Test buddy calls `track.add_proof(track_id, artifact_id, label="Smoke", summary="Pass")`.
2. PM opens the track.
3. Dev reads the proof artifact body.
4. Inspect persisted JSON.

**Assertions:**

- Env.tool response:
  - `ok=true`
  - `effect_summary` names artifact publication, close proof, and proof update
  - `state_changed=true`
  - `durability="durable"`
  - `state_changes` includes `published_proof`, `proof_added`, and update id
- Persisted artifact:
  - `status="published"`
  - `published_to_track="track-proof-publish"`
  - `template="proof"`
  - `is_current=true`
- Persisted track:
  - `close_proof` has current proof ref for `art-proof-r1`
  - `updates` has one `kind="proof"` row whose refs include `art-proof-r1`
- `track.open`:
  - `close_proof` exposes `art-proof-r1`
- `artifact.get`:
  - Dev can read full proof body
  - `relation="track_proof"`

**Regression value:** Catches proof publication paths that update only close proof or only updates.

### T4: Archived Track Rejects Read and Publish Without Mutation

**Level:** Integration

**File:** `tests/test_track_env_tool.py`

**Functional requirement:** Archived tracks are hard read/write boundaries for track publication and artifact reads through that track.

**Initial state:**

- PM creates `track-archived-publication`.
- PM creates and publishes `art-archived-r1`.
- PM archives the track.
- PM creates `art-archived-r2` draft after archive.
- Capture persisted track and artifact JSON after archive.

**Operation steps:**

1. PM calls `track.open(track-archived-publication)`.
2. PM calls `track.add_material` with R2.
3. Test calls `track.add_proof` with a proof draft.
4. Dev calls `artifact.get(art-archived-r1)`.
5. Inspect JSON after every rejection.

**Assertions:**

- Each rejection:
  - `ok=false`
  - `error.code="E_TRACK_ARCHIVED"` for track actions or `permission_boundary="track.lifecycle_status"` for artifact read
  - `state_changed=false`
  - `durability="none"` for env.tool rejections
  - `impact` names no state mutation for publish attempts
- Persisted JSON:
  - Archived track unchanged
  - R2 remains draft and unpublished
  - Existing R1 remains unchanged

**Regression value:** Prevents writes and reads from bypassing lifecycle closure.

### T5: Duplicate, Already-Bound, Cross-Track, and Wrong-Owner Publication Reject

**Level:** Integration

**File:** `tests/test_track_env_tool.py`

**Functional requirement:** Invalid publication attempts give actionable feedback and leave state unchanged.

**Initial state:**

- PM creates `track-publish-a` and `track-publish-b`.
- PM creates and publishes `art-bound-r1` to track A as material.
- Design creates `art-design-owned-r1` as private draft.
- Capture persisted JSON for both tracks and both artifacts.

**Operation steps and assertions:**

1. Duplicate material publish of `art-bound-r1` to track A:
   - `ok=false`
   - `why_blocked` includes already current or duplicate
   - `correctable_fields` includes `artifact_id`
   - track A and artifact unchanged
2. Cross-track publish of `art-bound-r1` to track B:
   - `ok=false`
   - `why_blocked` names existing track A
   - track B `shared_materials=[]`
   - artifact still points at track A
3. PM publishes Design-owned draft:
   - `ok=false`
   - `permission_boundary="artifact.buddy_scope"`
   - no track or artifact mutation
4. Publish material-bound artifact as proof on the same track:
   - `ok=false`
   - `why_blocked` names wrong existing publication kind
   - no close proof row is added

**Regression value:** Prevents hidden state pollution and teaches the host the real correction.

### T6: Legacy Inline Publish Payload Is Rejected

**Level:** Integration

**File:** `tests/test_track_env_tool.py`

**Functional requirement:** Active track publication no longer accepts inline `kind/content` artifact creation.

**Initial state:**

- PM creates `track-legacy-inline`.
- Capture track JSON.

**Operation steps:**

1. PM calls `track.add_material` with `kind`, `title`, and `content`.
2. PM calls `track.add_proof` with `kind`, `title`, and `content`.
3. Inspect track and artifact directories.

**Assertions:**

- Each response:
  - `ok=false`
  - `error.code="E_TRACK_PAYLOAD"`
  - `state_changed=false`
  - `durability="none"`
  - `correctable_fields` includes the unsupported active fields
  - `allowed_next_actions` points to `artifact.create_revision` then track publication by `artifact_id`
- Persisted JSON:
  - Track JSON unchanged
  - No new artifact files created

**Regression value:** Prevents legacy `kind/content` from remaining a parallel active path.

### E1: PM -> Design -> Dev -> Test Runtime Path

**Level:** End-to-end

**File:** `tests/test_env_layer_end_to_end.py`

**Functional requirement:** All buddies collaborate through `track.open -> artifact.get` without task relation machinery.

**Initial state:**

- Runtime test workspace has no track, task, or artifact objects.

**Operation steps:**

1. PM creates `track-e2e-publication`.
2. PM creates `art-e2e-pm-brief-r1` draft with `template="brief"` and product-direction body.
3. PM publishes it with `track.add_material`.
4. Design opens the track, extracts PM artifact id, reads body with `artifact.get`.
5. Design creates `art-e2e-design-r1` draft with `template="design"` and publishes it with `track.add_material`.
6. Dev opens the track, reads PM and Design bodies with `artifact.get`.
7. Dev creates `art-e2e-dev-r1` draft with `template="proposal"` and publishes it with `track.add_material`.
8. Test opens the track, reads needed bodies, creates `art-e2e-proof-r1` draft with `template="proof"`, publishes with `track.add_proof`.
9. PM opens the track and updates now-state with `track.update_now`.

**Assertions:**

- Every write response has `state_changed=true`, `durability="durable"`, and meaningful `state_changes`.
- `track.open.shared_materials` exposes current PM, Design, and Dev refs.
- `track.open.close_proof` exposes current Test proof ref.
- Each body read through `artifact.get` returns exact body text.
- No request uses `track.join`, `track.attach_task`, `track.detach_task`, task artifact slots, raw object edits, or direct `published_to_track`.
- Persisted JSON contains tracks and artifacts only for product collaboration; task relation state is not required.

**Regression value:** Proves the intended collaboration main path works for all roles.

### E2: PM Product Request Does Not Become Project Implementation

**Level:** End-to-end/turn integration

**File:** `tests/test_turn_integration.py`

**Functional requirement:** PM behavior for product-definition requests is not repaired through PM prompt bulk and does not treat `projects/app` as a PM implementation target.

**Initial state:**

- PM runtime profile has project access read-only.
- Runtime skill set includes `write-prd`, `track-tool`, and `artifact-tool`.
- Test harness issues a product-definition request such as a landing-page product brief without hardcoding a phrase-to-tool rule.

**Operation steps:**

1. Run the turn integration harness for PM with the product-definition request.
2. Capture env.tool calls or projected runtime state.
3. Inspect final durable state.

**Assertions:**

- PM creates or opens a track.
- PM creates a draft artifact with `template="brief"` or `template="decision"` and markdown body.
- PM publishes through `track.add_material` or `track.add_proof`.
- `track.open` exposes the published artifact id.
- `artifact.get` returns full PM body.
- No write to `projects/app` is attempted by PM.
- AGENTS text is not the source of a long PM workflow manual; guidance comes from skills/tool semantics.

**Regression value:** Confirms the PM regression is repaired at runtime contract and skill layers, not by turning PM into a generic implementation agent or adding phrase routing.

### S1: Critical Tool Semantics Are Not Placeholders

**Level:** Contract

**File:** `tests/test_env_tool_semantic_contract.py`

**Functional requirement:** Runtime-visible semantics must explain atomic capability meaning and effects for critical track/artifact actions.

**Initial state:**

- Load `contracts.env_tools_description()` and `contracts.operation_semantics()`.

**Operation steps:**

1. For `track.create`, `track.open`, `track.add_material`, `track.add_proof`, `artifact.create_revision`, and `artifact.get`, read action semantics.

**Assertions for each action:**

- `use_when` is a non-empty list with action-specific text.
- `do_not_use_when` is a non-empty list.
- `inputs_explained` is a non-empty dict and includes every active payload field.
- `side_effects.writes` and `side_effects.does_not_write` distinguish artifact, track, runtime files, and no body reads.
- `success_means` is not the generic placeholder text.
- `common_failures` is a non-empty list and includes real rejection cases.
- No row contains phrase routing such as `if the user says`.

**Regression value:** Prevents tool semantics from becoming a shell around action names.

### S2: Registry Payload Fields Match the Single Publication Path

**Level:** Contract

**File:** `tests/test_env_tool_semantic_contract.py`

**Functional requirement:** The runtime catalog must not advertise stale or direct-publish payloads.

**Initial state:** Load `contracts.TOOL_REGISTRY`.

**Operation steps:** Inspect action specs for `track.add_material`, `track.add_proof`, and `artifact.create_revision`.

**Assertions:**

- `track.add_material.payload_fields == ["track_id", "artifact_id", "label", "summary"]`
- `track.add_proof.payload_fields == ["track_id", "artifact_id", "label", "summary"]`
- `artifact.create_revision.payload_fields` includes `template` and `body`
- `artifact.create_revision.payload_fields` does not include `status` or `published_to_track`
- No active payload fields include `kind` or `content`

**Regression value:** Prevents runtime catalog drift from reintroducing hidden alternate paths.

### R1: Response Contract Describes Real State Effects

**Level:** Contract

**File:** `tests/test_env_tool_response_contract.py`

**Functional requirement:** Success and rejection responses must be enough for the host to understand effects and recover.

**Initial state:**

- PM track and draft artifact exist for positive path.
- Additional invalid payloads exist for rejection path.

**Operation steps:**

1. Call `artifact.create_revision` for a draft.
2. Call `track.add_material` for that draft.
3. Call `track.add_proof` for a proof draft.
4. Call direct-publish rejection and duplicate-publish rejection.

**Assertions:**

- Success responses:
  - `effect_summary` is non-empty and action-specific
  - `state_changed` is correct
  - `durability="durable"`
  - `state_changes` names object types and ids changed
  - `allowed_next_actions` contains only valid atomic capabilities
- Rejection responses:
  - `permission_boundary`, `why_blocked`, `impact`, `retryable`, `retry_guidance`, `allowed_next_actions`, `correctable_fields`, `state_changed=false`, and `durability="none"`
  - persisted JSON unchanged

**Regression value:** Prevents `ok=true` or generic errors from being the only host feedback.

### F1: Publish Rejections Have Actionable Feedback and No Mutation

**Level:** Feedback integration

**File:** `tests/test_runtime_tool_feedback.py`

**Functional requirement:** Publication failure modes expose the precise correction and preserve state.

**Initial state:**

- Prepare cases for archived track, missing artifact id, wrong owner, cross-track, duplicate current material, already material-bound proof attempt, and direct artifact publication.
- Capture all relevant JSON before each call.

**Operation steps:** Dispatch each invalid env.tool call.

**Assertions:**

- Each response has:
  - `ok=false`
  - `state_changed=false`
  - `durability="none"`
  - `permission_boundary`
  - `why_blocked`
  - `impact`
  - `correctable_fields` or `alternative_capabilities`
  - `allowed_next_actions` that do not point to a guaranteed rejection
- Persisted JSON equals baseline for every object that existed before the call.
- Missing target calls create no new files.

**Regression value:** Catches both bad feedback and accidental partial mutation.

### K1: PM and Shared Skills Describe One Publication Route

**Level:** Skill/contract

**File:** `tests/test_runtime_skills.py`

**Functional requirement:** Skills must guide repeated workflows while deferring action details to runtime catalog and response feedback.

**Initial state:** Read skill files and PM contract.

**Operation steps:**

1. Inspect `framework/contracts/pm.md`.
2. Inspect `buddyswitch/skills/pm/write-prd/SKILL.md`.
3. Inspect `buddyswitch/skills/shared/artifact-tool/SKILL.md`.
4. Inspect `buddyswitch/skills/shared/track-tool/SKILL.md`.

**Assertions:**

- PM contract contains `artifact.create_revision`, `track.add_material`, `track.add_proof`, `track.open`, and `artifact.get`.
- PM contract does not say to publish via `published_to_track`.
- PM skill covers product brief/product direction/scope/acceptance output, not only narrow PRD wording.
- PM skill describes draft creation then track publication then verification.
- PM skill does not contain phrase routing such as a landing-page trigger rule.
- `artifact-tool` says `create-revision` creates private drafts/revisions and does not directly publish.
- `track-tool` says publication is a track action using existing artifact ids.
- Both shared skills defer details to `context.get.tool_catalog` and response fields.

**Regression value:** Prevents contradictory skill guidance from reappearing after service repair.

### C1: Active Runtime Guidance Has No Forbidden Vocabulary

**Level:** Repo scan

**File:** `tests/test_repo_consistency.py`

**Functional requirement:** Stale vocabulary must not appear in active runtime guidance.

**Initial state:** Define scan targets:

- `AGENTS.md`
- `scripts`
- `buddyswitch`
- `tools/launcher/assets/buddies`
- `framework/contracts`
- `framework/schemas`
- `framework/console/app.js`
- `tests`

**Operation steps:** Search for:

- `kind=prd`
- `content.prd`
- `artifact.create_revision` near `published_to_track`
- `track.join`
- `attach_task`
- `detach_task`
- `attach-task`
- `detach-task`
- task-derived artifact visibility wording

**Assertions:**

- Disallowed hits list is empty.
- Allowed hits are limited to:
  - explicit legacy normalization tests
  - explicit negative tests
  - persisted schema/store field names where `published_to_track` is set by track publication
  - repair context docs under `docs/memo/**`, `docs/bitter/**`, and `docs/spec/**`
- AGENTS files do not contain a PM workflow manual, payload schema catalog, or phrase-to-tool router.

**Regression value:** Blocks stale active guidance even if service tests pass.

### P1: Buddy Profiles Preserve PM Runtime Boundary

**Level:** Profile contract

**File:** `tests/test_buddy_env_profiles.py`

**Functional requirement:** PM can own track lifecycle but cannot treat project source as implementation target.

**Initial state:** Load every buddy env profile.

**Operation steps:** Validate profiles through `env_profiles.require_env_profile`.

**Assertions:**

- PM profile:
  - `project.access="read-only"`
  - `filesystem_capability.project_workspace="read-only"`
  - `state_capability.track_effects` includes `create`, `update_now`, `add_material`, `add_update`, `add_proof`, `archive`
- Dev profile remains the only project-write profile.
- Other buddies can publish/update tracks as already allowed by profile matrix.

**Regression value:** Ensures PM product-definition runtime behavior does not become source implementation behavior.

### M1: Manual PM Runtime Verification

**Level:** Manual runtime

**Functional requirement:** After automated tests pass, a real PM instance follows the unified publication path for a product/landing-page PM output.

**Initial state:** Source checkout is clean except intended repair changes. Automated tests pass.

**Operation steps:**

1. Start a PM instance:

```bash
./buddyswitch-codex instance start --buddy pm
```

2. Ask PM for a product/landing-page PM output.
3. Inspect runtime output and env.tool call feedback.
4. Open the resulting track through env.tool.
5. Read the PM artifact body through env.tool.
6. Start or simulate Design/Dev read if the launcher supports it in the session.

**Assertions:**

- PM does not edit `projects/app`.
- PM creates or opens a track.
- PM writes a draft artifact through `artifact.create_revision`.
- PM publishes through `track.add_material` or `track.add_proof`.
- `track.open.shared_materials` or `track.open.close_proof` exposes the artifact id.
- `artifact.get` returns the full PM body.
- The response feedback is enough to understand what changed.

**Regression value:** Confirms the host-visible runtime behavior is repaired outside the test harness.

## Recommended Execution Order

1. Add A1, A2, T1, S2, and R1 first. These define the core contract and should fail on current main.
2. Implement draft-only artifact creation and run A1, A2, A3.
3. Implement track material/proof publication by existing artifact id and run T1, T2, T3, T4, T5, T6.
4. Strengthen response helper and service feedback, then run R1 and F1.
5. Align registry, semantics, client, contracts, and skills, then run S1, S2, K1, C1, P1.
6. Add and run E1 and E2.
7. Run full verification and manual M1.

## Full Verification Commands

Focused runtime publication suite:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_artifact_env_tool.py tests/test_track_env_tool.py -q
```

Expected result: all artifact and track env.tool publication tests pass.

Contract and feedback suite:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_semantic_contract.py tests/test_env_tool_response_contract.py tests/test_runtime_tool_feedback.py tests/test_runtime_skills.py tests/test_repo_consistency.py tests/test_buddy_env_profiles.py -q
```

Expected result: semantics, responses, skills, residue, and profile boundary tests pass.

End-to-end suite:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_layer_end_to_end.py tests/test_turn_integration.py -q
```

Expected result: PM-to-Test publication path passes and PM does not write project source.

Full repair verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_env_layer_end_to_end.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_response_contract.py tests/test_runtime_tool_feedback.py tests/test_runtime_skills.py tests/test_repo_consistency.py tests/test_buddy_env_profiles.py tests/test_turn_integration.py -q
```

Expected result: all selected tests pass.

Python syntax verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/env/services/artifacts.py scripts/env/services/tracks.py scripts/env/services/artifact_visibility.py scripts/env_store.py scripts/env/tools/contracts.py scripts/env/tools/semantics.py scripts/env/tools/responses.py scripts/env/client.py
```

Expected result: command exits 0.

Manual PM verification:

```bash
./buddyswitch-codex instance start --buddy pm
```

Expected result: PM creates product-definition track/artifact state through env.tool and does not treat `projects/app` as an implementation target.

## Acceptance Criteria

- Every automated case in the matrix except M1 is implemented, and M1 manual verification is executed after automated tests pass.
- Tests fail against the known broken contract before the corresponding runtime fix and pass after the fix.
- Positive tests assert response fields and persisted JSON, including object ids and state transitions.
- Negative tests assert no state mutation by comparing persisted JSON before and after.
- No test relies only on `ok=true`, field existence, or action registration.
- Tests prove the user-visible runtime path: `track.open -> artifact.get`.
- Tests prove PM behavior is not prompt-bulk or AGENTS-manual based.
- Tests prove forbidden vocabulary is absent from active runtime guidance except explicit legacy/negative contexts.
