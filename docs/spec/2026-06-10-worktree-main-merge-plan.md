# Worktree Main Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans style execution: follow this plan step-by-step, verify after each meaningful block, and keep conflict resolution focused on the requested merge.

**Goal:** Merge `nc`, `artifacts`, and `comment` into `main` through a tested integration branch.

**Architecture:** Use a temporary integration branch from current `main`, merge independent work first, then resolve the known `artifacts`/`comment` conflict once. Preserve the forward rebuilt runtime shape: track-owned artifact relations, track-native comments, and notification-center inbound registrations.

**Tech Stack:** Git worktrees, Python env runtime modules under `scripts/env`, pytest.

---

## Current Evidence

- Base branch: `main` at `d8780b0 docs: add rebuild task memos`.
- `artifacts`: `2d60ee6 refactor: decouple artifact relations from artifacts`.
- `comment`: `8c9c8e2 refactor: rebuild track-native comments`.
- `nc`: `d303efd Add notification center inbound registrations`.
- All four worktrees were clean before integration.
- Dry-run merge showed `nc` merges cleanly in any order.
- Dry-run merge showed `artifacts` and `comment` conflict in these files:
  - `scripts/env/domain/artifact_relations.py`
  - `scripts/env/domain/comment_targets.py`
  - `scripts/env/tools/track/_impl.py`
  - `scripts/env_legacy_store.py`
  - `tests/test_comment_env_tool.py`

## Merge Order

1. Create an isolated integration worktree from `main`.
2. Merge `nc`.
3. Merge `artifacts`.
4. Merge `comment`.
5. Resolve the five known conflicts using the runtime ownership rules below.
6. Run focused env/tool tests.
7. Run broader relevant tests.
8. Merge the integration branch back into local `main`.
9. Push `main` after verification.

## Conflict Resolution Rules

- Keep `comment` branch's deletion of the generic comment tool/repo path. Track comments are now owned by `track.*` actions and `scripts/env/repos/track_comments.py`.
- Keep `comment` branch's deletion of:
  - `scripts/env/domain/comment_targets.py`
  - `tests/test_comment_env_tool.py`
- Keep `artifacts` branch's relation model: artifacts stay content-only, track artifact relations live on tracks and are managed by `scripts/env/domain/track_artifact_relations.py`.
- In `scripts/env/domain/artifact_relations.py`, keep source-ref and track-update backlink behavior from `artifacts`, but do not reintroduce artifact-target comment backlinks or `comment_ids`.
- In `scripts/env/tools/track/_impl.py`, combine both branches:
  - keep `track.add_comment`, `track.list_comments`, and `track.resolve_comment_thread` from `comment`;
  - keep `track.add_material` and `track.add_proof` calling `context.rules.track_artifact_relations.add_material_relation` / `add_proof_relation` from `artifacts`;
  - do not restore publication-domain calls.
- In `scripts/env_legacy_store.py`, expose track comment repository helpers and track artifact relation helpers; do not restore old generic comment helper exports.

## Verification Commands

Run focused checks first:

```bash
python -m pytest \
  tests/test_track_comment_env_tool.py \
  tests/test_track_comments_repo.py \
  tests/test_track_env_tool.py \
  tests/test_artifact_env_tool.py \
  tests/test_env_store_v2.py \
  tests/test_env_layer_boundaries.py \
  tests/test_env_tool_response_*.py \
  tests/test_env_tool_schema_*.py \
  tests/test_env_tool_semantic_*.py
```

Then run integration-adjacent checks:

```bash
python -m pytest \
  tests/test_env_layer_end_to_end.py \
  tests/test_context_binding_env_tool.py \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_turn_integration.py \
  tests/test_notification_center.py \
  tests/test_daemon_communication_boundary.py \
  tests/test_daemon_core_decoupling.py \
  tests/test_instance_daemon_entrypoint.py
```

If the focused and integration-adjacent checks pass, run the full suite:

```bash
python -m pytest
```

## Completion Criteria

- Integration branch contains all three branch commits plus one conflict-resolution commit if needed.
- No unresolved merge conflicts remain.
- Focused and broad pytest verification passes.
- Local `main` contains the integrated result.
- `origin/main` is updated only after local `main` verifies cleanly.
- Final review reports changed merge shape, verification commands, and residual risk.
