# Track Minimal Requirement Collaboration Model Development Plan

Date: 2026-06-11
Source: `docs/memo/2026-06-11-track-minimal-requirement-collaboration-model.md`
Status: Phase 1 reviewed plan, ready for Phase 3 execution

## Goal

Directly replace the old PM-owned Track model with the minimal owner-actor requirement collaboration model.

## Architecture

Track ownership becomes one exact actor address: `owner_actor = {actor_id, role_id}`. Requirement facts and lifecycle are owner-only. Collaboration facts remain shared writes: material, update, proof, and comment. Actor attention remains comments only through `track.comment.added`; state/proof/blocker changes are read signals, not notifications.

## Files

Modify:

- `scripts/env/repos/tracks.py`: persistent row validation, creation, update boundaries, state invariants, update kinds.
- `scripts/env/domain/track_artifact_relations.py`: proof relation writes proof only and no longer appends proof update rows.
- `scripts/env/tools/track/tool.py`: public Track tool surface and schemas.
- `scripts/env/tools/track/_impl.py`: create/update/status/owner checks, summaries, open projections, comment cues, archive/resolve authority.
- `scripts/env/tool_runtime/role_auth.py`: role policy makes Track lifecycle actions available to all manifest roles and removes `track.update_now`.
- `scripts/env/tools/context/_impl.py`: context projections use `owner_actor` and remove PM-only Track lifecycle preview language.
- `tools/launcher/track_comment_added_handler.py`: prompt wording says owner authority, not PM authority.

Test:

- `tests/test_track_env_tool.py`
- `tests/test_track_comment_env_tool.py`
- `tests/test_notification_center.py`
- `tests/test_track_comment_added_handler.py`
- `tests/test_role_action_auth.py`
- `tests/test_env_tool_schema_contract.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_context_binding_env_tool.py`

## Implementation Tasks

### Task 1: Replace old Track contract tests with owner-actor red tests

Edit `tests/test_track_env_tool.py` so creation tests prove:

- every role can create a Track;
- `owner_actor` equals the active actor address;
- create rejects `appetite`, `health`, `owner_role`, `created_by_actor`, and `state=review`;
- responses do not return old fields.

Run:

```bash
python -m pytest tests/test_track_env_tool.py -q
```

Expected before implementation: failures showing current PM-only auth, old fields, and `review`/`health`/`appetite` support.

### Task 2: Replace repository shape

Edit `scripts/env/repos/tracks.py`:

- set `VALID_TRACK_STATE = ("active", "blocked", "done")`;
- set `VALID_UPDATE_KIND = ("progress", "decision", "blocker")`;
- remove `VALID_TRACK_HEALTH`;
- require and normalize `owner_actor`;
- add `acceptance_criteria` and `non_goals` list normalization;
- reject `owner_role`, `created_by_actor`, `health`, and `appetite`;
- enforce `active`, `blocked`, and `done` invariants;
- require a current proof relation before `done`;
- make `create_track` accept `owner_actor`, `outcome`, `now`, optional `acceptance_criteria`, and optional `non_goals`;
- make `update_track` reject unsupported fields and rely on higher-level owner-specific patch functions.

Run:

```bash
python -m pytest tests/test_track_env_tool.py -q
```

Expected after this task: repository-shaped failures move to tool schema/implementation instead of row validation accepting old fields.

### Task 3: Replace Track public tool definition

Edit `scripts/env/tools/track/tool.py`:

- remove `track.update_now`;
- add `track.update_requirements`;
- add `track.update_status`;
- make `track.create` actor-owned and remove old payload fields;
- remove `review` from state filters and status schemas;
- remove `health` everywhere;
- update capability/object wording from PM lifecycle to owner actor;
- update archive and resolve wording to owner-only;
- update `add_update` kind enum to `progress`, `decision`, `blocker`;
- update `add_proof` wording so proof is relation evidence and owner acceptance happens through `track.update_status`.

Run:

```bash
python -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py -q
```

Expected before matching implementation: schema tests may pass while dispatch tests still fail on missing handlers.

### Task 4: Replace role policy boundary

Edit `scripts/env/tool_runtime/role_auth.py`:

- remove `track.update_now` from common permissions;
- add `track.create`, `track.update_requirements`, `track.update_status`, `track.archive`, and `track.resolve_comment_thread` to common permissions;
- remove PM-only Track lifecycle additions.

Run:

```bash
python -m pytest tests/test_role_action_auth.py -q
```

Expected: role-policy tests prove all manifest roles pass the policy layer for Track lifecycle actions. Owner-only denial happens later inside Track implementation.

### Task 5: Replace Track implementation handlers

Edit `scripts/env/tools/track/_impl.py`:

- rename create path to active actor ownership and remove role check;
- add exact owner comparison helper using full `{actor_id, role_id}`;
- add owner-only rejection with owner authority wording;
- add `update_requirements_for_owner`;
- add `update_status_for_owner`;
- remove `update_now_for_active_role`;
- update action handler map;
- update `_track_summary` to return `owner_actor`, not old fields;
- update `_track_page` to expose `materials` and `proofs` projections;
- update allowed next actions to reference `track.update_status`, not `track.update_now`;
- ensure add material/update/proof/status operations do not call comment delivery or Notification Center delivery.

Run:

```bash
python -m pytest tests/test_track_env_tool.py -q
```

Expected after this task: core owner/lifecycle tests pass or expose remaining relation/comment cue gaps.

### Task 6: Replace proof relation semantics

Edit `scripts/env/domain/track_artifact_relations.py`:

- remove the proof update row from `add_proof_relation`;
- remove `update` from `ProofRelationResult`;
- keep proof relation currentness replacement behavior;
- compare relation slots by full actor address rather than actor id only.

Edit `scripts/env/tools/track/_impl.py` accordingly:

- remove proof update state change;
- remove `update_id` from `track.add_proof` output;
- keep `state` unchanged after proof.

Run:

```bash
python -m pytest tests/test_track_env_tool.py -q
```

Expected: `add_proof` tests prove proof does not change state and does not append a timeline update.

### Task 7: Replace comment cues with full actor matching

Edit `scripts/env/tools/track/_impl.py`:

- compute `mentions_to_me` and `replies_to_me` by exact actor address;
- include `open_threads` with required summary fields;
- keep `source_of_truth = "track.list_comments"`;
- remove `mentioned_comment_ids` if it is not part of the target read model.

Run:

```bash
python -m pytest tests/test_track_comment_env_tool.py tests/test_track_env_tool.py -q
```

Expected: comment cue tests prove same actor id with different role id does not match.

### Task 8: Replace context projection

Edit `scripts/env/tools/context/_impl.py`:

- compute `active_actor_relation` as `owner` only when active actor payload equals `owner_actor`;
- return `owner_actor`;
- remove `owner_role`, `created_by_actor`, `health`, and `appetite`;
- ensure runtime policy preview no longer surfaces PM-only Track lifecycle restrictions after role policy replacement.

Run:

```bash
python -m pytest tests/test_context_binding_env_tool.py tests/test_role_action_auth.py -q
```

Expected: context tests show exact owner matching and no old Track fields.

### Task 9: Preserve Notification Center boundary

Edit only if tests show wording or registration drift:

- `tools/launcher/track_comment_added_handler.py`: replace PM authority wording with owner authority wording.
- Keep `track.comment.added` as the only Track attention event.

Run:

```bash
python -m pytest tests/test_notification_center.py tests/test_track_comment_added_handler.py tests/test_track_comment_env_tool.py -q
```

Expected: comments deliver attention; status/proof/blocker/material/update writes do not.

### Task 10: Broad verification and cleanup

Search for old production references:

```bash
rg "track\\.update_now|owner_role|created_by_actor|health|appetite|review|VALID_TRACK_HEALTH|kind.*proof" scripts tools framework buddyswitch tests
```

For each match, decide whether it is an intentional historical doc/test reference or production residue. Production residue must be removed.

Run focused verification:

```bash
python -m pytest tests/test_track_env_tool.py -q
python -m pytest tests/test_track_comment_env_tool.py -q
python -m pytest tests/test_notification_center.py tests/test_track_comment_added_handler.py -q
python -m pytest tests/test_role_action_auth.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_context_binding_env_tool.py -q
```

Run broader contract verification:

```bash
python -m pytest tests/test_env_tool_router.py tests/test_env_tool_payload_contract.py tests/test_env_tool_response_contract.py tests/test_black_box_tool_runtime.py -q
```

Only run the full suite after focused and contract tests pass:

```bash
python -m pytest tests -q
```

If service-starting tests run, check resource residue before declaring completion.

## Phase 1 Review

Spec coverage:

- The tasks cover every replacement point named in the memo.
- The plan removes old behavior directly and does not introduce compatibility aliases.
- Owner-only authority is enforced in implementation, not role policy.
- Notification Center remains outside Track business semantics.

Execution clarity:

- Each task names exact files, expected code-level changes, and verification commands.
- The plan uses focused verification before broader verification to avoid resource exhaustion.

