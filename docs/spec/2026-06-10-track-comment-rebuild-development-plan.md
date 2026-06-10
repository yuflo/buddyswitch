# Track-Native Comment Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild comments as Track-owned collaboration rows and remove the standalone target-scoped `comment` system.

**Architecture:** Add a Track-specific repository and Track-specific domain rules, then expose add/list/resolve through the existing Track tool. Delete the generic comment tool path and update context/catalog/auth/tests so Track comments are the only actor-facing comment capability.

**Tech Stack:** Python runtime env tools, file-backed JSON repositories under `buddyswitch/objects`, pytest/unittest tests with `RuntimeWorkspaceTestMixin`.

---

## File Map

- Create `scripts/env/repos/track_comments.py`: file-backed Track comment repository using `buddyswitch/objects/track-comments/<track_id>/<comment_id>.json`.
- Create `scripts/env/domain/track_comments.py`: Track existence/lifecycle checks, reply Track-scope checks, mention validation helpers.
- Modify `scripts/env/repos/runtime_files.py`: replace `COMMENTS_DIR` with `TRACK_COMMENTS_DIR` and ensure runtime dirs create the new path.
- Modify `scripts/env/tool_runtime/context.py`: bind `RepoAccess.track_comment` and `DomainAccess.track_comment`; update legacy object facade methods to Track comment names only.
- Modify `scripts/env/tools/track/tool.py`: add `track.add_comment`, `track.list_comments`, and `track.resolve_comment_thread` action definitions.
- Modify `scripts/env/tools/track/_impl.py`: implement Track comment actions and compact `track.open` comment cues.
- Delete `scripts/env/tools/comment/__init__.py`, `scripts/env/tools/comment/tool.py`, and `scripts/env/tools/comment/_impl.py`.
- Delete or stop importing `scripts/env/domain/comment_targets.py`.
- Delete or stop importing `scripts/env/repos/comments.py`.
- Modify `scripts/env/tools/context/_impl.py`: build `open_comment_threads` from Track comments only; update descriptors and capability snapshot.
- Modify `scripts/env/domain/artifact_relations.py` and artifact projections: remove generic comment count/backlink behavior.
- Modify `scripts/env/tool_runtime/role_auth.py`: replace `comment.add/list/resolve` permissions with `track.add_comment`, `track.list_comments`, and PM-only `track.resolve_comment_thread`.
- Modify `scripts/env_store.py` and `scripts/env_legacy_store.py`: expose Track comment test helpers; remove generic target comment exports.
- Modify `scripts/env_cleanup.py`: discover and clean Track comment object paths.
- Modify role/shared docs and skills that mention standalone `comment.*`.
- Replace old tests with the files and cases in `docs/spec/2026-06-10-track-comment-rebuild-test-plan.md`.

## Task 1: Add Track Comment Repository Tests

**Files:**
- Create: `tests/test_track_comments_repo.py`
- Test target: `scripts/env/repos/track_comments.py`

- [ ] Write failing tests for storage path, row shape, same-Track reply inheritance, cross-Track reply rejection, same-thread cross-Track isolation, and Track-local resolution.
- [ ] Run:

```bash
python -m pytest tests/test_track_comments_repo.py -q
```

Expected before implementation: import failure or missing function failure for `env.repos.track_comments`.

## Task 2: Implement Track Comment Repository

**Files:**
- Modify: `scripts/env/repos/runtime_files.py`
- Create: `scripts/env/repos/track_comments.py`

- [ ] Add `TRACK_COMMENTS_DIR = OBJECTS_ROOT / "track-comments"` and include it in `ensure_runtime_dirs()`.
- [ ] Implement public functions:
  - `track_comment_file(track_id, comment_id)`
  - `validate_track_comment(comment)`
  - `list_track_comments()`
  - `get_track_comment(track_id, comment_id)`
  - `save_track_comment(comment)`
  - `create_track_comment(track_id, by_actor, content, reply_to=None, mentioned_actors=None, thread_id=None, status="open")`
  - `reply_to_track_comment(track_id, reply_to, by_actor, content, mentioned_actors=None)`
  - `comments_for_track(track_id)`
  - `comments_for_track_thread(track_id, thread_id)`
  - `resolve_track_comment_thread(track_id, comment_id, resolved_by_actor, resolution_summary)`
- [ ] Reject legacy fields `target_type`, `target_id`, `anchor`, and `artifact_revision_id`.
- [ ] Run:

```bash
python -m pytest tests/test_track_comments_repo.py -q
```

Expected after implementation: pass.

## Task 3: Add Track Tool Behavior Tests

**Files:**
- Replace: `tests/test_comment_env_tool.py` with `tests/test_track_comment_env_tool.py`

- [ ] Write failing env-tool tests for:
  - root Track comment add/list;
  - replies and cross-Track reply rejection;
  - PM-only resolution and repeat-resolution state rejection;
  - cross-Track resolve rejection;
  - archived Track rejection;
  - mention validation;
  - old `comment.*` dispatch rejection;
  - unsupported old payload fields on `track.add_comment`.
- [ ] Run:

```bash
python -m pytest tests/test_track_comment_env_tool.py -q
```

Expected before implementation: missing Track actions and old `comment` tool still accepted.

## Task 4: Implement Track Tool Actions

**Files:**
- Modify: `scripts/env/domain/track_comments.py`
- Modify: `scripts/env/tool_runtime/context.py`
- Modify: `scripts/env/tools/track/tool.py`
- Modify: `scripts/env/tools/track/_impl.py`
- Delete: `scripts/env/tools/comment/__init__.py`
- Delete: `scripts/env/tools/comment/tool.py`
- Delete: `scripts/env/tools/comment/_impl.py`

- [ ] Add Track comment action schemas with no target fields.
- [ ] Implement payload rejection helper with code `E_TRACK_COMMENT_PAYLOAD`.
- [ ] Add Track lifecycle checks through the existing Track repo and archived Track rejection helper.
- [ ] Add `track.add_comment`.
- [ ] Add `track.list_comments`.
- [ ] Add `track.resolve_comment_thread`.
- [ ] Add compact `comment_cues` into `_track_page`.
- [ ] Delete the standalone comment tool package so registry discovery cannot load `comment`.
- [ ] Run:

```bash
python -m pytest tests/test_track_comment_env_tool.py -q
```

Expected after implementation: pass.

## Task 5: Update Catalog, Auth, Context, and Skill Contract Tests

**Files:**
- Modify: `tests/test_env_tool_schema_contract.py`
- Modify: `tests/test_env_tool_response_contract.py`
- Modify: `tests/test_env_tool_semantic_contract.py`
- Modify: `tests/test_role_action_auth.py`
- Modify: `tests/test_env_manifest_v2.py`
- Modify: `tests/test_runtime_skills.py`
- Modify: `scripts/env/tool_runtime/role_auth.py`
- Modify: `scripts/env/tools/context/_impl.py`
- Modify: `scripts/env/tools/context/tool.py` if text mentions `comment.list`.
- Modify role/shared skill docs under `tools/launcher/assets` and manifest skill references as needed.

- [ ] Add failing assertions that `comment` is not supported and `track.resolve_comment_thread` is PM-only.
- [ ] Update role policy permissions.
- [ ] Update context capability snapshots and source descriptors to Track comments.
- [ ] Update manifest/skill expectations so roles no longer require `comment-tool`.
- [ ] Run:

```bash
python -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_response_contract.py tests/test_env_tool_semantic_contract.py tests/test_role_action_auth.py tests/test_env_manifest_v2.py tests/test_runtime_skills.py -q
```

Expected after implementation: pass.

## Task 6: Remove Artifact Comment Coupling

**Files:**
- Modify: `scripts/env/domain/artifact_relations.py`
- Modify: `scripts/env/tools/artifact/_impl.py`
- Modify: affected artifact tests, especially `tests/test_artifact_env_tool.py`

- [ ] Add/update failing tests proving Artifact summaries do not include generic comment counts/backlinks.
- [ ] Remove `comment_counts_for_artifact` and comment backlink projection from artifact relation summaries.
- [ ] Remove Artifact comment scenarios that used `comment.add` on `artifact` or `artifact_section`.
- [ ] Run:

```bash
python -m pytest tests/test_artifact_env_tool.py -q
```

Expected after implementation: pass.

## Task 7: Update Cleanup and Env Store Test Helpers

**Files:**
- Modify: `scripts/env_cleanup.py`
- Modify: `scripts/env_store.py`
- Modify: `scripts/env_legacy_store.py`
- Modify: `tests/test_cleanup_system.py`
- Modify: `tests/test_env_store_v2.py`

- [ ] Add failing tests for `track-comments/<track_id>/<comment_id>.json` cleanup discovery and role-authored deletion.
- [ ] Update cleanup category path and report fields while preserving `comment_object_ids` only if tests need stable category naming; prefer `track_comment_object_ids` if no external contract exists.
- [ ] Replace generic env store comment helpers with Track comment helpers.
- [ ] Run:

```bash
python -m pytest tests/test_cleanup_system.py tests/test_env_store_v2.py -q
```

Expected after implementation: pass.

## Task 8: Static Removal Sweep

**Files:**
- Production and test files touched above.

- [ ] Run:

```bash
rg -n "comment\\.(add|list|resolve)|comments_for_target|target-scoped comments|artifact_section.*comment|comment_targets|env\\.repos import comments|repos\\.comment|rules\\.comment_target" scripts tests tools buddyswitch docs/spec -S
```

- [ ] For every hit, either remove/update it or confirm it is an intentional historical memo/spec reference outside active runtime behavior.
- [ ] Run:

```bash
python -m pytest tests/test_track_comments_repo.py tests/test_track_comment_env_tool.py tests/test_env_tool_schema_contract.py tests/test_env_tool_response_contract.py tests/test_env_tool_semantic_contract.py tests/test_role_action_auth.py tests/test_env_manifest_v2.py tests/test_runtime_skills.py tests/test_context_binding_env_tool.py tests/test_host_decision_surface_product_mode.py tests/test_cleanup_system.py tests/test_env_store_v2.py -q
```

Expected: pass.

## Task 9: Phase 1 Plan Review Checklist

- [x] Spec coverage: every acceptance criterion in `docs/memo/2026-06-09-track-comment-rebuild-task.md` maps to a task above.
- [x] No compatibility-forward path: no task preserves actor-facing `comment.*`, Artifact comments, or target-scoped storage.
- [x] Test-first loop: every implementation task begins with failing tests or existing failing contract tests.
- [x] Resource lifecycle: verification avoids launcher service startup and broad suites are delayed until focused isolated tests pass.
- [x] Ambiguity resolved locally: resolve authority remains PM-only per existing semantics; broader Track permissions are out of scope.

## Final Verification

After focused groups pass, run the broad non-service test set:

```bash
python -m pytest tests/test_track_comments_repo.py tests/test_track_comment_env_tool.py tests/test_env_tool_schema_contract.py tests/test_env_tool_response_contract.py tests/test_env_tool_semantic_contract.py tests/test_role_action_auth.py tests/test_env_manifest_v2.py tests/test_runtime_skills.py tests/test_context_binding_env_tool.py tests/test_host_decision_surface_product_mode.py tests/test_cleanup_system.py tests/test_env_store_v2.py -q
```

Then run the static removal sweep from Task 8 and inspect remaining hits.
