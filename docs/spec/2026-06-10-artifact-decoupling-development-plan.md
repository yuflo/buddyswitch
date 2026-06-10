# Artifact Decoupling Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild Artifact as an independent content carrier and replace Track/Artifact publication
coupling with Track-owned Artifact relations.

**Architecture:** Keep the actor-facing `track.add_material` and `track.add_proof` actions, but
change them to write only Track-side relation rows plus the proof timeline update. Artifact rows
contain content, attachments, authorship, source refs, and artifact-local lineage/currentness only.

**Tech Stack:** Python 3, `unittest`, existing env.tool runtime, JSON object repositories under
`scripts/env/repos`, domain helpers under `scripts/env/domain`.

---

## Target Runtime Shape

Artifact row:

```python
{
    "id": "art-...",
    "title": "...",
    "summary": "...",
    "body": "...",
    "template": "brief|proposal|design|decision|proof|note",
    "revision": 1,
    "is_current": True,
    "supersedes_artifact_id": None,
    "created_by_actor": {"actor_id": "act-...", "role_id": "pm"},
    "author_actors": [{"actor_id": "act-...", "role_id": "pm"}],
    "source_refs": [{"type": "note", "label": "seed"}],
    "attachments": [],
    "created_at": "...",
    "updated_at": "...",
}
```

Track row relation field:

```python
"artifact_relations": [
    {
        "relation_id": "rel-...",
        "type": "artifact",
        "artifact_id": "art-...",
        "role": "material",
        "label": "Brief",
        "template": "brief",
        "from_actor": {"actor_id": "act-...", "role_id": "pm"},
        "summary": "Shared brief",
        "current": True,
        "created_at": "...",
    }
]
```

Removed live fields:

- Artifact: `status`, `published_to_track`, `publication_role`.
- Track: `shared_materials`, `close_proof`.
- Domain: old cross-object Artifact publication mutation.

## File Map

Create:

- `scripts/env/domain/track_artifact_relations.py`

Delete:

- `scripts/env/domain/publication.py`

Modify:

- `scripts/env/repos/artifacts.py` - independent Artifact row schema and artifact-local lineage.
- `scripts/env/repos/tracks.py` - `artifact_relations` schema and relation normalization.
- `scripts/env/domain/artifact_visibility.py` - readability from owner or Track relations.
- `scripts/env/domain/artifact_relations.py` - relation summaries from Track relations.
- `scripts/env/domain/source_refs.py` - use new visibility decisions.
- `scripts/env/domain/comment_targets.py` - keep Artifact target readability through new visibility.
- `scripts/env/tool_runtime/context.py` - replace `publication` domain access with relation domain.
- `scripts/env/tools/artifact/_impl.py` - remove status filters and publication wording.
- `scripts/env/tools/artifact/tool.py` - update schemas, semantics, and guidance.
- `scripts/env/tools/track/_impl.py` - call relation domain and project relation rows.
- `scripts/env/tools/track/tool.py` - update action descriptions and write semantics.
- `scripts/env/tools/context/_impl.py` - context summaries and track filters through relations.
- Role assets under `tools/launcher/assets/roles/**/AGENTS.md` only where tests prove stale wording.
- Tests listed in `docs/spec/2026-06-10-artifact-decoupling-test-plan.md`.

## Task 1: Artifact Repository Becomes Content-Only

**Files:**

- Modify: `tests/test_env_store_v2.py`
- Modify: `scripts/env/repos/artifacts.py`
- Check: `env_legacy_store.py`

- [ ] Step 1: Replace Artifact store shape tests with content-carrier expectations.
  - Test created rows have no `status` and no `published_to_track`.
  - Test validation rejects stale publication lifecycle fields.
  - Test superseding demotes previous Artifact currentness and keeps all Track fields absent.

- [ ] Step 2: Run the focused tests and verify they fail for the expected old-field reason.

```bash
python -m unittest tests.test_env_store_v2.ArtifactStoreContractTests
```

Expected before implementation: failures mention extra `status` / `published_to_track` or missing
content-only shape.

- [ ] Step 3: Update `scripts/env/repos/artifacts.py`.
  - Change `VALID_ARTIFACT_STATUS` use out of live schema.
  - Remove `published_to_track` and `status` from `create_artifact_revision`.
  - Remove `status` and `published_to_track` from `update_artifact` allowed fields.
  - Make `validate_artifact` reject `status`, `published_to_track`, and `publication_role`.
  - Keep `revision`, `is_current`, and `supersedes_artifact_id` as Artifact-local lineage.
  - When creating a revision with `supersedes_artifact_id`, require the target to be current,
    set previous `is_current=False`, and set new `is_current=True`.

- [ ] Step 4: Keep legacy compatibility only where it is already an explicit legacy store wrapper.
  - Do not preserve old fields in active Artifact rows.
  - If `env_legacy_store.py` passes old parameters, normalize by ignoring Track publication
    parameters instead of writing them.

- [ ] Step 5: Run focused Artifact repo tests until green.

```bash
python -m unittest tests.test_env_store_v2.ArtifactStoreContractTests
```

## Task 2: Track Repository Owns Artifact Relations

**Files:**

- Modify: `tests/test_env_store_v2.py`
- Modify: `scripts/env/repos/tracks.py`

- [ ] Step 1: Add Track store tests for `artifact_relations`.
  - New Tracks contain empty `artifact_relations`.
  - `shared_materials` and `close_proof` are rejected as stale fields.
  - Relation rows normalize required fields and reject invalid `role`.

- [ ] Step 2: Run the focused Track store tests and verify failure against old slot fields.

```bash
python -m unittest tests.test_env_store_v2.TrackStoreContractTests
```

- [ ] Step 3: Update `scripts/env/repos/tracks.py`.
  - Add valid Artifact relation roles: `material`, `proof`, `input`, `deliverable`.
  - Add `_normalize_artifact_relation`.
  - Change `create_track` to write `artifact_relations=[]`.
  - Change `update_track` allowed fields to accept `artifact_relations`.
  - Change `validate_track` to reject `shared_materials` and `close_proof`.
  - Return `artifact_relations` in normalized Track rows.
  - Keep `updates` and proof update refs unchanged.

- [ ] Step 4: Run focused tests until green.

```bash
python -m unittest tests.test_env_store_v2.TrackStoreContractTests
```

## Task 3: Replace Publication Domain With Relation Domain

**Files:**

- Create: `scripts/env/domain/track_artifact_relations.py`
- Delete: `scripts/env/domain/publication.py`
- Modify: `scripts/env/tool_runtime/context.py`
- Modify: `tests/test_track_env_tool.py`
- Modify: `tests/test_env_layer_boundaries.py`

- [ ] Step 1: Write failing Track tool tests for relation writes.
  - Material relation writes do not mutate Artifact.
  - Proof relation writes do not mutate Artifact and append proof timeline update.
  - Same Artifact can be related to multiple Tracks.
  - Replacement demotes only previous Track relation currentness for the same slot.
  - Save failure leaves Track and Artifact unchanged.

- [ ] Step 2: Run focused relation tests and verify they fail against old publication behavior.

```bash
python -m unittest \
  tests.test_track_env_tool.TrackEnvToolTests.test_add_material_creates_track_relation_without_artifact_mutation \
  tests.test_track_env_tool.TrackEnvToolTests.test_add_proof_creates_relation_and_timeline_update_without_artifact_mutation
```

- [ ] Step 3: Implement `scripts/env/domain/track_artifact_relations.py`.
  - `add_material_relation(track_id, artifact_id, label, from_actor, summary)`.
  - `add_proof_relation(track_id, artifact_id, label, from_actor, summary, update_summary)`.
  - Load Track and Artifact.
  - Reject archived Track.
  - Require Artifact exists and `created_by_actor` equals active actor for new shares.
  - Use Artifact `template` as relation `template`.
  - Build relation rows with `relation_id`, `type`, `artifact_id`, `role`, `label`,
    `template`, `from_actor`, `summary`, `current`, `created_at`.
  - Demote existing current relation for the same Track slot:
    same `role`, `label`, `template`, and `from_actor.actor_id`.
  - Save only Track.
  - For proof, append one proof update row through Track repo in the same operation.

- [ ] Step 4: Remove old publication access.
  - Delete `scripts/env/domain/publication.py`.
  - Remove `_publication_domain` import from `scripts/env/tool_runtime/context.py`.
  - Add `track_artifact_relations` to `DomainAccess`.
  - Update boundary allowlists to point to `track_artifact_relations.py`.

- [ ] Step 5: Update `scripts/env/tools/track/_impl.py`.
  - `add_material_to_track` calls `context.rules.track_artifact_relations.add_material_relation`.
  - `add_proof_to_track` calls `context.rules.track_artifact_relations.add_proof_relation`.
  - Success responses say `relation_added` / `proof_relation_added`.
  - `state_changes` contain Track relation changes and no Artifact publication changes.
  - `updated_ids` contain Track id and Artifact id only as related ids, not mutated ids.

- [ ] Step 6: Run focused Track relation tests until green.

```bash
python -m unittest tests.test_track_env_tool.TrackEnvToolTests
```

## Task 4: Rebuild Artifact Visibility From Relations

**Files:**

- Modify: `tests/test_artifact_env_tool.py`
- Modify: `scripts/env/domain/artifact_visibility.py`
- Modify: `scripts/env/domain/source_refs.py`
- Modify: `scripts/env/domain/comment_targets.py`

- [ ] Step 1: Replace old publication visibility tests.
  - Owner-only before relation.
  - All roles can read after non-archived Track relation.
  - Track filter uses Track relations.
  - Archived Track does not grant foreign reads.
  - Historical relation remains readable when superseded.

- [ ] Step 2: Run focused visibility tests and verify expected failures.

```bash
python -m unittest \
  tests.test_artifact_env_tool.ArtifactEnvToolTests.test_private_artifact_is_owner_only_before_track_relation \
  tests.test_artifact_env_tool.ArtifactEnvToolTests.test_track_relation_exposes_artifact_to_all_track_collaborators
```

- [ ] Step 3: Rewrite `scripts/env/domain/artifact_visibility.py`.
  - Owner read: `created_by_actor.actor_id == active_actor.actor_id`.
  - Relation read: scan non-archived Tracks for `artifact_relations` rows referencing the
    Artifact id.
  - Track-specific read helper: return relation only for the requested Track id.
  - Relation names: `owner`, `track_material`, `track_proof`, `track_history`, `none`.
  - Currentness: `current`, `proof`, `superseded`, `draft`.
  - `artifact_list_row` and `artifact_summary_row` expose `relation`, `relation_track_ids`,
    `currentness`, `revision`, `supersedes_artifact_id`, and no publication fields.
  - `artifact_ref_decision_for_track_update` allows refs only when the Artifact has a current
    material/proof relation on the same Track.

- [ ] Step 4: Update source refs and comment targets only where they consume visibility decisions.
  - Keep their public behavior unchanged except for the removed publication fields.

- [ ] Step 5: Run Artifact visibility tests until green.

```bash
python -m unittest tests.test_artifact_env_tool.ArtifactEnvToolTests
```

## Task 5: Rebuild Relation Summaries, Context, And Track Pages

**Files:**

- Modify: `scripts/env/domain/artifact_relations.py`
- Modify: `scripts/env/tools/track/_impl.py`
- Modify: `scripts/env/tools/context/_impl.py`
- Modify: `tests/test_context_binding_env_tool.py`
- Modify: `tests/test_track_env_tool.py`

- [ ] Step 1: Replace relation summary and context tests.
  - `artifact.get` relation summary has `track_relations`, `lineage`, and `incoming_refs`.
  - It does not use a `publication` object.
  - `context.summarize` candidate Artifacts use relation metadata.
  - `track.open` returns `artifact_relations` with attachment summaries.

- [ ] Step 2: Run focused tests and verify failures against old `publication` summary fields.

```bash
python -m unittest \
  tests.test_artifact_env_tool.ArtifactEnvToolTests.test_get_relation_summary_includes_track_relations_and_lineage \
  tests.test_context_binding_env_tool.ContextBindingEnvToolTests.test_context_summarize_describes_artifacts_as_content_carriers
```

- [ ] Step 3: Update `artifact_relations.py`.
  - Replace `publication` summary with `track_relations`.
  - Build relation rows by scanning Track `artifact_relations`.
  - Keep source ref backlinks, Track update refs, comments, and lineage.

- [ ] Step 4: Update `track._impl._track_page`.
  - Project `artifact_relations`.
  - Add attachment summary fields directly on relation rows.
  - Do not return `shared_materials` or `close_proof`.

- [ ] Step 5: Update `context._impl`.
  - Capability snapshot describes Artifact content and Track relation sharing.
  - Candidate Artifact filters use relation-aware visibility.
  - Remove `artifact_publication_path` naming and publication wording.

- [ ] Step 6: Run focused context and track page tests until green.

```bash
python -m unittest tests.test_context_binding_env_tool tests.test_track_env_tool
```

## Task 6: Update Tool Definitions, Role Guidance, And Semantic Contracts

**Files:**

- Modify: `scripts/env/tools/artifact/tool.py`
- Modify: `scripts/env/tools/track/tool.py`
- Modify: `scripts/env/tool_runtime/role_auth.py` only if permission names change.
- Modify: role assets under `tools/launcher/assets/roles/**/AGENTS.md` if residue tests identify stale wording.
- Modify: `tests/test_env_tool_response_contract.py`
- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_repo_consistency.py`

- [ ] Step 1: Replace semantic tests and residue scans.
  - Success responses describe Track relation changes.
  - Tool definitions do not say Artifact publication.
  - Active role assets do not mention `published_to_track`, `shared_materials`, or `close_proof`.
  - Runtime code has no old publication residue outside allowed docs/spec and docs/memo files.

- [ ] Step 2: Run semantic tests and verify failures.

```bash
python -m unittest tests.test_env_tool_response_contract tests.test_runtime_skills tests.test_repo_consistency
```

- [ ] Step 3: Update tool definitions.
  - Artifact tool scope: content, revisions, metadata, attachments, readable content.
  - Track tool scope: Track pages, timeline, Artifact relations.
  - Keep action names `track.add_material` and `track.add_proof`.
  - Change action descriptions from "publish" to "relate/share/reference".
  - Keep permissions unchanged unless tests prove a policy mismatch.

- [ ] Step 4: Update role guidance only for stale runtime-facing wording.
  - Do not copy schemas into role docs.
  - Point exact fields to runtime discovery.

- [ ] Step 5: Run semantic tests until green.

```bash
python -m unittest tests.test_env_tool_response_contract tests.test_runtime_skills tests.test_repo_consistency
```

## Task 7: End-To-End Runless Flow Replacement

**Files:**

- Modify: `tests/test_env_layer_end_to_end.py`
- Modify: `tests/test_turn_integration.py`

- [ ] Step 1: Replace old publication flow assertions.
  - Assert Track relation rows for PM, Design, Dev, and Test Artifacts.
  - Assert proof relation also appends proof timeline evidence.
  - Assert Artifact rows have content-carrier shape.

- [ ] Step 2: Run end-to-end tests and verify expected failures.

```bash
python -m unittest tests.test_env_layer_end_to_end tests.test_turn_integration
```

- [ ] Step 3: Update test fixtures and helper assertions to use `artifact_relations`.

- [ ] Step 4: Run end-to-end tests until green.

```bash
python -m unittest tests.test_env_layer_end_to_end tests.test_turn_integration
```

## Task 8: Residue Removal And Broad Verification

**Files:**

- Modify any remaining active-code or active-guidance files identified by tests.

- [ ] Step 1: Run direct residue scans.

```bash
rg -n 'published_to_track|shared_materials|close_proof|"status": "published"|publication metadata|published artifact|publishable draft' scripts tests tools buddyswitch README.md AGENTS.md
```

Expected after implementation: hits remain only in tests that construct forbidden patterns, docs, or
explicitly updated rejection messages that are not active guidance. Active runtime behavior should
not depend on old terms.

- [ ] Step 2: Run focused rebuild suites.

```bash
python -m unittest tests.test_env_store_v2 tests.test_track_env_tool tests.test_artifact_env_tool
python -m unittest tests.test_context_binding_env_tool tests.test_env_tool_response_contract tests.test_env_layer_boundaries tests.test_repo_consistency tests.test_runtime_skills
python -m unittest tests.test_env_layer_end_to_end tests.test_turn_integration
```

- [ ] Step 3: Check process residuals before broad suite.

```bash
ps -axo pid,ppid,pgid,command | rg 'buddyswitch-codex|runtime_broker|app-server|fake Codex|Chrom(e|ium)|Playwright' || true
```

Expected: no new long-lived test-owned processes.

- [ ] Step 4: Run broad verification.

```bash
python -m unittest discover tests
```

- [ ] Step 5: Check process residuals after broad suite.

```bash
ps -axo pid,ppid,pgid,command | rg 'buddyswitch-codex|runtime_broker|app-server|fake Codex|Chrom(e|ium)|Playwright' || true
```

Expected: no new long-lived test-owned processes.

## Review Checklist

- Artifact repo contains no Track publication or lifecycle field.
- Track relation writes do not mutate Artifact rows.
- `publication.py` is gone and not imported.
- Track repo and Artifact repo do not import each other.
- `track.add_material` and `track.add_proof` preserve user capability through Track relations.
- Proof relation still creates timeline evidence.
- Artifact visibility is owner-or-relation based.
- Attachments remain readable through relation-granted Artifact readability.
- Context and role guidance describe content carriers and Track relations.
- No actor-facing notification tools or NC wrapper events were added.
- No dual old/new fields are returned in live runtime output.

## Self-Review

- Spec coverage: Every acceptance criterion from the memo maps to one or more tasks above.
- Scope check: Notification center, `artifact.shared` handler registration, and Track-native
  comment work are excluded because the memo explicitly forbids them in this worktree.
- Type consistency: The plan uses one relation field name, `artifact_relations`, and one relation
  role field, `role`, across repo, domain, tool, context, and tests.
- Placeholder scan: The plan contains concrete files, commands, and expected behavior. It contains
  no deferred implementation placeholders.
