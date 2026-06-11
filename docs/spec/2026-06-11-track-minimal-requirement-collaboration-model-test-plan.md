# Track Minimal Requirement Collaboration Model Test Plan

Date: 2026-06-11
Source: `docs/memo/2026-06-11-track-minimal-requirement-collaboration-model.md`
Status: Phase 1 reviewed plan, ready for Phase 3 execution

## Goal

Prove the Track rebuild replaces the old PM-owned Track lifecycle with the owner-actor requirement collaboration model.

The tests must prove product behavior from the memo, not preserve old compatibility. Old expectations for `owner_role`, `created_by_actor`, `health`, `appetite`, `review`, and `track.update_now` must be rewritten or deleted.

## Resource Safety

Follow `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.

Default validation starts with non-service unit and broker dispatch tests:

```bash
python -m pytest tests/test_track_env_tool.py -q
python -m pytest tests/test_track_comment_env_tool.py tests/test_notification_center.py tests/test_track_comment_added_handler.py -q
python -m pytest tests/test_role_action_auth.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_context_binding_env_tool.py -q
```

Do not run broad service-starting launcher suites until focused tests are green. If a broad command is needed, run it only after checking for residual runtime processes and be prepared to inspect cleanup immediately afterward.

## Functional Requirements To Prove

1. Track rows persist only `active`, `blocked`, and `done`.
2. Track rows use `owner_actor` as the only ownership source.
3. `track.create` is available to every manifest role and sets `owner_actor` to the active actor address.
4. `track.create` rejects `owner_role`, `created_by_actor`, `health`, `appetite`, and `review`.
5. Track requirement facts are owner-only through `track.update_requirements`.
6. Track lifecycle state is owner-only through `track.update_status`.
7. `track.resolve_comment_thread` and `track.archive` are owner-only.
8. `track.update_now` is absent from schema, runtime policy, and handler dispatch.
9. `active` requires `now.next` non-empty and `now.blocker = null`.
10. `blocked` requires `now.next` non-empty and non-empty `now.blocker`.
11. `done` requires `now.next` non-empty, `now.blocker = null`, and at least one current proof relation.
12. `track.add_update(kind=blocker)` records a fact but does not change state.
13. `track.add_update(kind=proof)` is rejected.
14. `track.add_proof` adds a current proof relation but does not change state and does not append a proof update row.
15. Status, proof, blocker, material, and update writes do not emit notification events.
16. Track comments remain the only attention event and emit `track.comment.added` for mentions and replies.
17. Comment mention/reply targeting and `track.open` actor-relative cues match full `{actor_id, role_id}`, not `actor_id` only.
18. `track.open` returns `materials`, `proofs`, `updates`, `comment_cues`, `owner_actor`, `state`, `now`, `acceptance_criteria`, `non_goals`, and archive metadata.
19. Notification Center remains business-semantic-free and does not register Track state/proof/blocker events.
20. Context projection summarizes tracks with `owner_actor`, excludes old fields, and treats the active actor as owner only on exact full-address match.

## Test Matrix

### Repository Model Tests

Target file: `tests/test_track_env_tool.py` or a new focused repository test if the existing file becomes too large.

Cases:

- `validate_track` rejects rows containing `owner_role`, `created_by_actor`, `health`, or `appetite`.
- `validate_track` rejects `state = review`.
- `validate_track` rejects `updates[].kind = proof`.
- `validate_track` rejects `active` with non-null blocker.
- `validate_track` rejects `blocked` with empty blocker.
- `validate_track` rejects `done` without a current proof relation.
- `create_track` requires `owner_actor` and defaults `acceptance_criteria` and `non_goals` to empty lists.
- `update_track` rejects requirement/lifecycle fields outside the chosen operation boundary.

### Tool Definition And Runtime Policy Tests

Target files:

- `tests/test_env_tool_schema_contract.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_role_action_auth.py`
- `tests/test_context_binding_env_tool.py`

Cases:

- Track action names are exactly `create`, `list`, `open`, `update_requirements`, `update_status`, `add_material`, `add_update`, `add_proof`, `add_comment`, `list_comments`, `resolve_comment_thread`, and `archive`.
- No schema or operation semantics contains `track.update_now`.
- Create/list/update status schemas do not expose `review`, `health`, `appetite`, `owner_role`, or `created_by_actor`.
- `track.create`, `track.update_requirements`, `track.update_status`, `track.archive`, and `track.resolve_comment_thread` are permitted at role-policy level for every manifest role.
- Runtime policy preview no longer reports PM-only Track lifecycle restrictions.

### Tool Behavior Tests

Target file: `tests/test_track_env_tool.py`.

Cases:

- Every manifest role can create a Track and receives a row whose `owner_actor` equals the active actor address.
- Non-owner exact actor address cannot call `update_requirements`, `update_status`, `archive`, or `resolve_comment_thread`.
- Same `actor_id` with a different `role_id` is not owner.
- Owner can patch only title/outcome/acceptance criteria/non-goals through `update_requirements`.
- `update_requirements` rejects state/now/material/update/proof/comment payload fields.
- Owner can change to `blocked` only with a non-empty blocker.
- Owner can change from blocked back to `active` only with `now.blocker = null`.
- Owner cannot change to `done` until a current proof relation exists.
- `add_update(kind=blocker)` leaves state unchanged.
- `add_update(kind=proof)` rejects without mutation.
- `add_proof` leaves state unchanged and leaves `updates` unchanged.
- After proof exists, owner can call `update_status(state=done)` and the row remains `done` with blocker null.
- Archived tracks reject normal future writes.

### Track Open And Comment Cue Tests

Target files:

- `tests/test_track_env_tool.py`
- `tests/test_track_comment_env_tool.py`

Cases:

- `track.open` exposes `materials` and `proofs` projections separately from raw `artifact_relations`.
- `track.open.comment_cues` includes `open_thread_count`, `recent_comments`, `open_threads`, `mentions_to_me`, `replies_to_me`, and `source_of_truth`.
- Mentions match exact actor address; same `actor_id` with another `role_id` is not counted.
- Replies match exact parent author address; same `actor_id` with another `role_id` is not counted.
- Open thread summaries include `thread_id`, `latest_comment_id`, `latest_comment_preview`, `latest_by_actor`, `comment_count`, `status`, `mentions_me`, and `replies_to_me`.
- Comment cues do not classify requirement changes, blockers, proof review, or owner decision items.

### Notification Boundary Tests

Target files:

- `tests/test_notification_center.py`
- `tests/test_track_comment_added_handler.py`
- `tests/test_track_comment_env_tool.py`

Cases:

- `track.comment.added` remains registered and dispatchable.
- Mentions and replies deliver `track.comment.added`.
- Status updates, proof additions, blocker updates, and material additions do not call Track comment delivery.
- Notification Center event registrations do not contain `track.status.changed`, `track.proof.added`, or `track.blocker.reported`.
- Track comment handler prompts say owner authority, not PM authority.

## Verification Commands

Run focused tests first:

```bash
python -m pytest tests/test_track_env_tool.py -q
python -m pytest tests/test_track_comment_env_tool.py -q
python -m pytest tests/test_notification_center.py tests/test_track_comment_added_handler.py -q
python -m pytest tests/test_role_action_auth.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_context_binding_env_tool.py -q
```

Run broader non-service contract tests after focused tests pass:

```bash
python -m pytest tests/test_env_tool_router.py tests/test_env_tool_payload_contract.py tests/test_env_tool_response_contract.py tests/test_black_box_tool_runtime.py -q
```

Only after focused and contract tests pass, run a broader suite with resource awareness:

```bash
python -m pytest tests -q
```

If broad verification starts persistent services, check residual runtime processes and sockets before claiming completion.

## Phase 1 Review

Coverage check:

- The matrix covers model shape, tool schema, role auth, owner authority, lifecycle invariants, relation semantics, comment attention, Notification Center boundary, and context projection.
- Old compatibility behavior is intentionally removed rather than tested as alternate behavior.
- Tests are derived from memo requirements and product invariants, not from current implementation details.

Resource check:

- The plan starts with focused non-service tests and delays broad suite execution until after focused proof.
- The plan explicitly requires post-run resource awareness for any broad or service-starting verification.

