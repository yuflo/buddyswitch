# Phase 5: Product Ownership

## Goal

Replace product-object ownership and authorship with identity ids. Tracks, tasks, artifacts, and comments should persist identity fields; owner checks compare identity ids; actor route/display data stays a projection.

## Code Audit

- `scripts/env/repos/tracks.py` persists `owner_actor`, update `by_actor`, and artifact relation `from_actor`.
- `scripts/env/repos/tasks.py` persists `owner_actor`.
- `scripts/env/repos/artifacts.py` persists `created_by_actor`, `author_actors`, and attachment `created_by_actor`.
- `scripts/env/repos/track_comments.py` persists `by_actor`, `mentioned_actors`, and `resolved_by_actor`.
- `scripts/env/tools/track/_impl.py`, `scripts/env/tools/task/_impl.py`, `scripts/env/tools/artifact/_impl.py`, and context projections compare or expose actor-address ownership fields.
- Comment delivery and daemon wake still need actor route projections at the delivery boundary.

## Plan

1. Add failing repo tests for new-write identity persistence on tracks, tasks, artifacts, and comments.
2. Replace repository normalization so new writes output identity fields:
   - `track.owner_identity_id`
   - `track.updates[].by_identity_id`
   - `track.artifact_relations[].from_identity_id`
   - `task.owner_identity_id`
   - `artifact.created_by_identity_id`
   - `artifact.author_identity_ids`
   - `artifact.attachments[].created_by_identity_id`
   - `comment.by_identity_id`
   - `comment.mentioned_identity_ids`
   - `comment.resolved_by_identity_id`
3. Update owner checks and visible context projections to compare identity ids.
4. Keep actor route resolution only at daemon/comment delivery boundaries.
5. Run focused product-object tests plus residue scans.

## Test Plan

Start with focused repository tests, then broaden:

```bash
python -m pytest tests/test_track_owner_actor_model.py tests/test_task_env_tool.py tests/test_artifact_env_tool.py tests/test_track_comments_repo.py tests/test_track_comment_env_tool.py tests/test_context_binding_env_tool.py -q
```

## Implementation

- Added `tests/test_identity_product_ownership.py` to lock new-write identity persistence for tracks, tasks, artifacts, and track comments.
- Replaced product object persisted ownership/authorship fields:
  - Tracks now normalize to `owner_identity_id`, `updates[].by_identity_id`, and `artifact_relations[].from_identity_id`.
  - Tasks now normalize to `owner_identity_id`.
  - Artifacts now normalize to `created_by_identity_id`, `author_identity_ids`, and attachment `created_by_identity_id`.
  - Track comments now normalize to `by_identity_id`, `mentioned_identity_ids`, and `resolved_by_identity_id`.
- Updated owner and author checks in track, artifact, evidence, artifact visibility, track artifact relations, context summaries, and shared track read projections to compare identity ids.
- Kept actor route projection only at current delivery/runtime boundaries:
  - Track comment mentions still accept existing actor route payloads at the tool boundary, but persisted comments store identity ids.
  - Track comment daemon delivery builds a transient identity-to-route map for the current request and otherwise resolves actor identity to route at delivery time.
- Updated contract/test expectations from `owner_actor`, `created_by_actor`, `author_actors`, `by_actor`, and `from_actor` to identity fields where the surface reads product objects.
- Kept migration-only fallback readers in repos for old rows; new writes return identity fields only.

## Verification

Focused product ownership verification:

```bash
python -m pytest tests/test_identity_product_ownership.py tests/test_track_owner_actor_model.py tests/test_track_comments_repo.py tests/test_track_comment_env_tool.py tests/test_task_env_tool.py tests/test_artifact_env_tool.py tests/test_env_store_v2.py tests/test_context_binding_env_tool.py -q
```

Result:

```text
102 passed, 89 subtests passed in 2.18s
```

Full repository verification:

```bash
python -m pytest -q
```

Result:

```text
1052 passed, 1732 subtests passed in 605.24s (0:10:05)
```

Residue scan:

```bash
rg -n "owner_actor|created_by_actor|author_actors|by_actor|mentioned_actors|resolved_by_actor" scripts/env/repos scripts/env/domain scripts/env/tools tests -S
```

Result: remaining hits are documented compatibility/fallback inputs, actor-private workspace ownership unrelated to product objects, test fixtures/assertions, and Phase 6 contract replacement candidates. New product-object writes verified above return identity fields only.

## Gate

Complete. Phase 6 can start.
