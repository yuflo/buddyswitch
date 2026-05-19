# Env Legacy Store Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` when executing this plan. This document is an implementation handoff only; it does not implement runtime code.

**Goal:** Remove active runtime dependence on `scripts/env_legacy_store.py` from `source_refs`, artifact visibility, context discovery, and evidence services, then guard active runtime imports so the dependency cannot return.

**Architecture:** Keep the current thin runtime chain: `Tool Contract -> Service -> Domain Ops -> Object Repo -> runtime_files`. Services adapt env.tool requests and responses; domain modules own readability and cross-object rules; object repos own concrete runtime object reads and writes. This cleanup directly replaces the active legacy-store path and does not keep a compatibility wrapper, dual path, generic object framework, workflow engine, plugin system, or event bus.

**Tech Stack:** Python env.tool runtime, `scripts/env/services/**`, `scripts/env/domain/**`, `scripts/env/repos/**`, broker-routed tests with `pytest`/`unittest`, static import guards with AST and `rg`.

---

## Source Inputs

Read these before editing code:

- `AGENTS.md`
- `docs/memo/2026-05-19-env-legacy-store-cleanup-memo.md`
- `docs/memo/buddyswitch-parallel-modular-architecture.md`
- `scripts/env/services/source_refs.py`
- `scripts/env/services/artifact_visibility.py`
- `scripts/env/services/context.py`
- `scripts/env/services/evidence.py`
- `scripts/env/services/artifacts.py`
- `scripts/env/services/tracks.py`
- `scripts/env/domain/artifact_visibility.py`
- `scripts/env/domain/publication.py`
- `scripts/env/repos/runtime_files.py`
- `scripts/env/repos/artifacts.py`
- `scripts/env/repos/tracks.py`
- `scripts/env/repos/tasks.py`
- `tests/test_artifact_env_tool.py`
- `tests/test_context_binding_env_tool.py`
- `tests/test_evidence_env_tool.py`
- `tests/test_market_browser_evidence.py`
- `tests/test_env_layer_boundaries.py`
- `tests/test_repo_consistency.py`
- `tests/test_parallel_contracts.py`

Implementation and test work must ignore `docs/**`. Do not change any docs file while executing this plan.

## Current Bottleneck

The first-phase parallel modular architecture is already verified. The remaining bottleneck is narrower: active runtime code still imports `env_legacy_store` in these files:

- `scripts/env/services/source_refs.py`
- `scripts/env/services/artifact_visibility.py`
- `scripts/env/services/context.py`
- `scripts/env/services/evidence.py`

That leaves active reads, validation, timestamps, and target-scope checks tied to the old monolithic helper. The cleanup is complete only when active runtime code under `scripts/env/services`, `scripts/env/domain`, `scripts/env/repos`, and `scripts/env/tools` has no direct `env_legacy_store` import.

Tests may continue importing `env_legacy_store` for fixture setup and persisted-state assertions. Fixture cleanup is outside this work.

## Final Runtime Shape

Target active paths:

```text
artifact.create_revision/update_metadata
  -> env.services.source_refs
  -> env.repos.runtime_files.require_id
  -> env.repos.artifacts.get_artifact
  -> env.domain.artifact_visibility.artifact_read_decision

context.get/summarize
  -> env.repos.tracks.list_tracks
  -> env.repos.tasks.list_tasks
  -> env.domain.artifact_visibility.current_material_rows_for_track

artifact.get, track refs, comment targets
  -> env.domain.artifact_visibility
  -> env.repos.artifacts / env.repos.tracks

evidence.issue_browser/approve_downgrade
  -> env.repos.artifacts.get_artifact
  -> env.repos.runtime_files.now_iso
```

`scripts/env/services/artifact_visibility.py` is deleted because the repo-backed domain module already owns those decisions.

## File Change Map

- Modify `scripts/env/services/source_refs.py`
  - Remove `import env_legacy_store as env_store`.
  - Import `env.repos.runtime_files` for `require_id`.
  - Import `env.repos.artifacts` for artifact reads.
  - Import `env.domain.artifact_visibility` for read-claim readability decisions.
  - Keep normalization output shape and error strings stable unless a test below requires the clearer repo/domain behavior.

- Delete `scripts/env/services/artifact_visibility.py`
  - Remove the duplicate legacy-store-backed visibility helper.
  - Do not leave a re-export, shim, or compatibility service module.

- Modify `scripts/env/services/context.py`
  - Remove `import env_legacy_store as env_store`.
  - Replace `from env.services import artifact_visibility` with `from env.domain import artifact_visibility as artifact_visibility_domain`.
  - Import `env.repos.tracks` and `env.repos.tasks`.
  - Replace `_visible_tracks` and `_visible_tasks` legacy reads with repo reads.
  - Route current material summary rows through `artifact_visibility_domain.current_material_rows_for_track`.
  - Preserve current response sections: `tool_catalog`, `operation_semantics`, `tracks`, `tasks`, `artifact_summaries`, `buddybox_desc`, `candidate_tracks`, `decision_surface`, and `current_context_summary`.

- Modify `scripts/env/services/evidence.py`
  - Remove `import env_legacy_store as env_store`.
  - Import `env.repos.artifacts` for target artifact lookup.
  - Import `env.repos.runtime_files` for token timestamps.
  - Preserve target type semantics: only `target_type="artifact"` is valid.
  - Preserve target scope semantics: active buddy must be one of the target artifact authors to issue browser evidence or approve downgrade.
  - Preserve transient token shape and `mutates_product_state=False`.

- Modify `scripts/env/services/artifacts.py`
  - No behavioral rewrite is expected.
  - Adjust imports only if `source_refs` cleanup changes public helper names. Keep artifact service calls concrete and do not inline source-ref logic into artifact service.

- Modify `tests/test_artifact_env_tool.py`
  - Add focused behavior coverage for source refs and readability claims.
  - Existing fixture setup may continue using `env_legacy_store`.

- Modify `tests/test_context_binding_env_tool.py`
  - Add focused behavior coverage for context discovery after repo-backed reads.
  - Existing fixture setup may continue using `env_legacy_store`.

- Modify `tests/test_evidence_env_tool.py`
  - Add focused behavior coverage for missing targets and readable-but-not-authored artifact targets.
  - Existing fixture setup may continue using `env_legacy_store`.

- Modify `tests/test_market_browser_evidence.py`
  - Keep existing market browser evidence regression coverage.
  - Add a test here only if the evidence-service changes affect the browser evidence CLI/runtime path beyond the focused service behavior in `tests/test_evidence_env_tool.py`.

- Modify `tests/test_env_layer_boundaries.py`
  - Add an active-runtime import guard that scans `scripts/env/services`, `scripts/env/domain`, `scripts/env/repos`, and `scripts/env/tools` for AST imports of `env_legacy_store`.
  - Keep tests excluded from this guard.
  - Remove `scripts/env/services/artifact_visibility.py` from any allowlist once the file is deleted.

- Modify `tests/test_repo_consistency.py`
  - Keep existing parallel architecture residue tests passing.
  - Add a high-level active runtime direct-import residue check only if the boundary guard is not enough to cover `scripts/env/tools`.

## Phase 1: Source Refs Cleanup

**Objective:** `source_refs` validation and read-claim checks stop reading through `env_legacy_store`.

**Files:**

- Modify `tests/test_artifact_env_tool.py`
- Modify `scripts/env/services/source_refs.py`

**Required test intent:**

- Add a test that creates and publishes a PM artifact to a non-archived track, then has another buddy create a new artifact with:
  - `source_refs=[{"type": "artifact", "id": "<published-artifact-id>"}]`
  - `read_claim="summarized-full-content"`
  - Expected result: success, stored source ref keeps the artifact id, no legacy run lineage fields appear.
- Add a test that creates a private PM draft artifact, then has another buddy create an artifact with a full-content read claim against that draft.
  - Expected result: rejection with `E_SOURCE_REFS_READ_SCOPE`, `permission_boundary="source_refs.read_scope"`, no new artifact file created.
- Add a test that passes an invalid `source_refs` artifact id such as uppercase or punctuation.
  - Expected result: rejection with `E_SOURCE_REFS`, `permission_boundary="source_refs.required_fields"`, no new artifact file created.

**Implementation intent:**

- Replace `env_store.require_id` with `runtime_files.require_id`.
- Replace `env_store.get_artifact` with `artifact_repo.get_artifact`.
- For `read_claim == "summarized-full-content"` and artifact refs:
  - Load the artifact by id through `artifact_repo.get_artifact`.
  - Reject missing artifacts with the existing provenance-only read-scope message.
  - Call `artifact_visibility_domain.artifact_read_decision(artifact, active_buddy)`.
  - Accept only when `allowed` is true.
  - Reject unreadable artifacts with `permission_boundary="source_refs.read_scope"`.
- Do not move source-ref normalization into the artifact repo during this cleanup; keep the active service helper concrete and bounded.

**Focused validation:**

```bash
python3 -m pytest tests/test_artifact_env_tool.py -q
python3 -m pytest tests/test_artifact_env_tool.py tests/test_buddybox_env_tool.py tests/test_runtime_tool_feedback.py -q
```

**Completion standard:**

- `scripts/env/services/source_refs.py` has no direct `env_legacy_store` import.
- Source refs still normalize `artifact`, `track`, `task`, `buddybox`, `external`, and `note` refs.
- Full-content read claims are based on active runtime artifact readability, not artifact authorship alone.

## Phase 2: Artifact Visibility Service Removal

**Objective:** Active callers use `env.domain.artifact_visibility` directly, and the duplicate legacy-store-backed service file is removed.

**Files:**

- Modify `scripts/env/services/context.py`
- Delete `scripts/env/services/artifact_visibility.py`
- Modify `tests/test_env_layer_boundaries.py`

**Implementation intent:**

- Replace `from env.services import artifact_visibility` in `context.py` with `from env.domain import artifact_visibility as artifact_visibility_domain`.
- Replace `artifact_visibility.current_material_rows_for_track(...)` with `artifact_visibility_domain.current_material_rows_for_track(...)`.
- Delete `scripts/env/services/artifact_visibility.py`.
- In `tests/test_env_layer_boundaries.py`, remove the deleted service path from the publication-write allowlist.
- Confirm no active import references remain for the deleted service.

**Focused validation:**

```bash
rg -n "env\\.services import artifact_visibility|services\\.artifact_visibility|scripts/env/services/artifact_visibility.py" scripts/env tests
python3 -m pytest tests/test_artifact_env_tool.py tests/test_track_env_tool.py tests/test_comment_env_tool.py -q
```

Expected `rg` result after code changes: exit code 1 with no matches, except no scan requirement for this plan document.

**Completion standard:**

- `scripts/env/services/artifact_visibility.py` is absent.
- Artifact readability/currentness behavior is owned by `scripts/env/domain/artifact_visibility.py`.
- Artifact, track, and comment readability tests still pass.

## Phase 3: Context Repo-Backed Reads

**Objective:** `context.get`, `context.summarize`, and `context.list_sources` keep the same runtime response semantics while reading active state through repos/domain.

**Files:**

- Modify `tests/test_context_binding_env_tool.py`
- Modify `scripts/env/services/context.py`

**Required test intent:**

- Extend context discovery tests so `context.get` with seeded active and archived tracks asserts:
  - active non-archived track is present in `tracks`;
  - archived track is absent from `tracks` and `candidate_tracks`;
  - tasks bound to archived tracks are absent from active context;
  - active buddy tasks bound to visible tracks are present;
  - current artifact summary includes only current published material and excludes superseded or archived-track artifacts.
- Keep `context.summarize` assertions for compact tool affordances and candidate tracks.
- Keep `context.list_sources` assertions independent of docs content.

**Implementation intent:**

- Import `tracks as track_repo` and `tasks as task_repo`.
- Replace `env_store.list_tracks()` with `track_repo.list_tracks()`.
- Replace `env_store.list_tasks()` with `task_repo.list_tasks()`.
- Preserve the current filter behavior:
  - `track_id` narrows visible tracks by exact id after trimming only when the argument is a string.
  - `task_id` narrows active-buddy tasks by exact id after trimming only when the argument is a string.
  - `limit` defaults to 20 and applies to visible tracks, visible tasks, and artifact summaries.
- Preserve archived-track exclusion and task visibility based on visible track ids.
- Do not add comments to context sections unless the active tool contract already exposes them there.

**Focused validation:**

```bash
python3 -m pytest tests/test_context_binding_env_tool.py tests/test_host_decision_surface_product_mode.py tests/test_turn_integration.py -q
```

**Completion standard:**

- `scripts/env/services/context.py` has no direct `env_legacy_store` import.
- Context discovery still exposes the same sections and compact summary keys.
- Context does not expose archived tracks, tasks scoped to archived tracks, or superseded material as current context.

## Phase 4: Evidence Repo-Backed Target Scope

**Objective:** Evidence target resolution and token timestamps stop reading through `env_legacy_store`.

**Files:**

- Modify `tests/test_evidence_env_tool.py`
- Modify `tests/test_market_browser_evidence.py` only if the browser path needs an added regression.
- Modify `scripts/env/services/evidence.py`

**Required test intent:**

- Add a missing-target test:
  - `target_type="artifact"` and a syntactically valid missing artifact id.
  - Expected result: rejection with `E_EVIDENCE_PAYLOAD`, no `tool_evidence`, no product state mutation.
- Add a readable-but-not-authored target test:
  - Publish an artifact to a readable track from `market`.
  - Dispatch `evidence.issue_browser` as `design` for that artifact.
  - Expected result: rejection with `E_EVIDENCE_TARGET_SCOPE`, `permission_boundary="artifact.authors"`, no `tool_evidence`.
- Keep existing positive tests for market-owned target, downgrade reason, artifact-only target type, runless token shape, and no `run_id`.

**Implementation intent:**

- Replace `env_store.get_artifact` with `artifact_repo.get_artifact`.
- Replace `env_store.now_iso()` with `runtime_files.now_iso()`.
- Keep `_resolve_target` scoped to artifact targets and author ownership.
- Do not broaden evidence issuance to all readable published artifacts. Evidence tokens remain author-scoped target metadata.
- Keep token metadata transient. Do not write evidence token files or product object state.

**Focused validation:**

```bash
python3 -m pytest tests/test_evidence_env_tool.py tests/test_market_browser_evidence.py -q
```

**Completion standard:**

- `scripts/env/services/evidence.py` has no direct `env_legacy_store` import.
- Evidence accepts active-buddy-authored artifact targets.
- Evidence rejects missing, wrong-type, and readable-but-not-authored artifact targets.
- Evidence tokens remain transient metadata and omit `run_id`.

## Phase 5: Active Runtime Import Guard

**Objective:** Prevent active runtime code from importing `env_legacy_store` again.

**Files:**

- Modify `tests/test_env_layer_boundaries.py`
- Modify `tests/test_repo_consistency.py` only if a second high-level residue test is needed.

**Implementation intent:**

- Add a helper in `tests/test_env_layer_boundaries.py` that parses Python files with `ast.parse`.
- Scan these roots:
  - `scripts/env/services`
  - `scripts/env/domain`
  - `scripts/env/repos`
  - `scripts/env/tools`
- Fail on:
  - `import env_legacy_store`
  - `import env_legacy_store as ...`
  - `from env_legacy_store import ...`
- Do not fail on tests importing `env_legacy_store`.
- Do not fail on strings that are not imports. The guard should target active imports, not fixture helper strings.

**Focused validation:**

```bash
python3 -m pytest tests/test_env_layer_boundaries.py tests/test_repo_consistency.py -q
rg -n "import env_legacy_store|from env_legacy_store import" scripts/env/services scripts/env/domain scripts/env/repos scripts/env/tools
```

Expected `rg` result after code changes: exit code 1 with no matches.

**Completion standard:**

- The import guard fails if any active runtime module imports `env_legacy_store`.
- Existing object repo sibling import and publication-domain boundary tests still pass.
- Tests can still use `env_legacy_store` fixtures until the separate fixture cleanup.

## Phase 6: Parallel Architecture Regression

**Objective:** Prove this cleanup did not weaken the already accepted parallel modular architecture.

**Files:**

- No planned production edits in this phase.
- Fix only files touched in earlier phases if a regression points to them.
- Do not edit `docs/**`.

**Focused validation:**

```bash
python3 -m pytest tests/test_runtime_skills.py tests/test_env_layer_boundaries.py tests/test_repo_consistency.py tests/test_parallel_contracts.py -q
python3 -m pytest tests/test_message_env_tool.py tests/test_comment_env_tool.py tests/test_buddybox_env_tool.py -q
python3 -m pytest tests/test_artifact_env_tool.py tests/test_track_env_tool.py tests/test_context_binding_env_tool.py tests/test_evidence_env_tool.py tests/test_market_browser_evidence.py -q
```

**Completion standard:**

- Shared tool SKILL files still do not copy runtime payload schema.
- Message, comment, and buddybox focused tests still run independently.
- Object repos still do not import sibling repos.
- Track/artifact publication remains routed through the publication domain.
- Context and evidence focused tests pass after the active legacy import cleanup.

## Final Verification

Run these commands from the worktree root:

```bash
rg -n "import env_legacy_store|from env_legacy_store import" scripts/env/services scripts/env/domain scripts/env/repos scripts/env/tools
python3 -m pytest tests/test_artifact_env_tool.py tests/test_buddybox_env_tool.py tests/test_runtime_tool_feedback.py -q
python3 -m pytest tests/test_artifact_env_tool.py tests/test_track_env_tool.py tests/test_comment_env_tool.py -q
python3 -m pytest tests/test_context_binding_env_tool.py tests/test_host_decision_surface_product_mode.py tests/test_turn_integration.py -q
python3 -m pytest tests/test_evidence_env_tool.py tests/test_market_browser_evidence.py -q
python3 -m pytest tests/test_runtime_skills.py tests/test_env_layer_boundaries.py tests/test_repo_consistency.py tests/test_parallel_contracts.py -q
python3 -m pytest tests/test_message_env_tool.py tests/test_comment_env_tool.py tests/test_buddybox_env_tool.py -q
python3 -m pytest -q
```

Expected result:

- The `rg` command has no matches.
- All focused commands pass.
- The full suite passes.

## Definition of Done

The cleanup is complete when all of these are true:

- `scripts/env/services/source_refs.py`, `scripts/env/services/context.py`, and `scripts/env/services/evidence.py` do not import `env_legacy_store`.
- `scripts/env/services/artifact_visibility.py` is deleted and no active caller imports it.
- Active runtime code under `scripts/env/services`, `scripts/env/domain`, `scripts/env/repos`, and `scripts/env/tools` has no direct `env_legacy_store` import.
- Source refs validate ids through `runtime_files`, resolve artifact refs through `artifact_repo`, and evaluate full-content read claims through `artifact_visibility_domain`.
- Context discovery reads tracks/tasks through object repos and current material rows through the artifact visibility domain.
- Evidence target resolution reads artifacts through `artifact_repo` and timestamps through `runtime_files`.
- No compatibility wrapper, transition service, or dual active path remains.
- The focused and full verification commands above pass.
