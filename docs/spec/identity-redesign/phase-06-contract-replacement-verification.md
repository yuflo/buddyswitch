# Phase 6: Contract Replacement Verification

## Goal

Close the identity redesign by removing remaining old public locator contracts and proving that live actor-facing, web-facing, and product-object surfaces use identity ids. Actor addresses may remain only as daemon/private routing projections or one-time migration input readers.

## Code Audit

Known remaining Phase 5 residue:

- `track.add_comment` still accepts public `mentioned_actors`.
- Several tests and fixtures still seed old actor payload fields as migration input.
- Repo/domain fallback readers still accept old rows.
- Daemon delivery and actor-private workspace code still use actor route payloads, which is allowed when not exposed as product identity.
- Historical/spec docs contain old terms as execution context.

## Plan

1. Add/activate residue verification for public contract surfaces.
2. Replace `track.add_comment.mentioned_actors` with `mentioned_identity_ids` in tool schema, implementation, tests, and docs/skills.
3. Keep daemon delivery route projection internal by resolving identity id to actor route only at the delivery boundary.
4. Run Phase 6 focused contract tests and full suite.
5. Record residue scan results and allowed remaining internal/fallback hits.

## Test Plan

```bash
python -m py_compile scripts/env/tools/context/_impl.py scripts/env/tools/track/_impl.py && python -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_response_contract.py tests/test_track_comment_env_tool.py tests/test_runtime_skills.py tests/test_context_binding_env_tool.py tests/test_evidence_env_tool.py -q
```

Then run:

```bash
python -m pytest -q
```

## Implementation

- Replaced the remaining public `track.add_comment.mentioned_actors` contract with `mentioned_identity_ids`.
- Added tool-side identity validation for comment mentions. Actor identity ids are projected to daemon actor routes only at the comment delivery boundary.
- Changed track comment delivery results from public `target_actor_address` rows to `target_identity_id` rows while keeping daemon calls internally routed with actor address payloads.
- Changed context summaries from public `actor_address` output to `current_identity`.
- Changed evidence token issuer output from `issued_by_actor` to `issued_by_identity_id`.
- Updated shared message tool guidance and runtime-skill tests so actor contact examples use `contact.identity_id` and `target_identity_id`.
- Renamed stale implementation helpers that still described identity ownership as actor ownership.
- Replaced `artifact.list.created_by_role` with `created_by_identity_id` and removed `from_role` from live artifact response projections.
- Removed remaining role-from-identity-id parsing helpers; Web Management resolves actor routes from instance rows, and Track comment delivery resolves mention routes from daemon contacts plus the active actor route.
- Updated live message tool metadata from participant wording to identity-based wording.

## Verification

Focused contract verification:

```bash
python -m py_compile scripts/env/tools/context/_impl.py scripts/env/tools/track/_impl.py && python -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_response_contract.py tests/test_track_comment_env_tool.py tests/test_runtime_skills.py tests/test_context_binding_env_tool.py tests/test_evidence_env_tool.py -q
```

Result:

```text
109 passed, 787 subtests passed in 3.15s
```

Focused pre-final full-suite verification:

```bash
python -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_response_contract.py tests/test_track_comment_env_tool.py tests/test_track_comments_repo.py tests/test_runtime_skills.py tests/test_context_binding_env_tool.py tests/test_evidence_env_tool.py -q
```

Result:

```text
114 passed, 791 subtests passed in 3.19s
```

Full repository verification:

```bash
python -m pytest -q
```

Result:

```text
1053 passed, 1732 subtests passed in 607.79s (0:10:07)
```

Focused identity contract verification after final residue cleanup:

```bash
python -m pytest tests/test_identity_product_ownership.py tests/test_track_comments_repo.py tests/test_message_tool_im_client.py tests/test_im_product_core.py tests/test_im_http_router.py tests/test_web_management.py tests/test_track_comment_env_tool.py tests/test_artifact_env_tool.py tests/test_context_binding_env_tool.py tests/test_evidence_env_tool.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_response_contract.py tests/test_runtime_skills.py -q
```

Result:

```text
230 passed, 883 subtests passed in 130.38s (0:02:10)
```

Web Management UI verification:

```bash
node tests/web_management_ui_state.test.js && node tests/web_management_ui_contract.test.js
```

Result:

```text
all checks ok
```

Residue scan:

```bash
rg -n "mentioned_actors|target_actor_address|owner_actor|created_by_actor|author_actors|issued_by_actor" scripts/env/tools buddyswitch/skills/shared tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_runtime_skills.py -S
rg -n "actor_address" scripts/env/tools buddyswitch/skills/shared tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_runtime_skills.py -S
rg -n "_role_id_from_actor_identity_id|actor identity id must contain a known role|act-<known-role>|created_by_role|from_role|split\\(\"-\", 2\\)|split\\('-', 2\\)" scripts/env tools/launcher buddyswitch/skills/shared tests/test_env_tool_schema_contract.py tests/test_artifact_env_tool.py tests/test_web_management.py tests/test_track_comment_env_tool.py tests/test_runtime_skills.py -S
```

Results:

- Negative assertions remain in schema/runtime-skill tests to prevent old public fields from returning.
- `created_by_actor`, `author_actors`, `owner_actor`, and `mentioned_actors` remain only as repository-facing migration/input calls or tool-to-repo adapter arguments where repos immediately normalize to identity fields.
- `target_actor_address` and `actor_address` remain only as daemon/private route projections and context fallback/migration readers.
- Prefix-derived role parsing has no implementation hits. Remaining `created_by_role`/`from_role` hits are negative assertions or legacy test fixture inputs.
- Public tool contracts now expose identity ids for mention targets, message targets, artifact creator filters, current context identity, evidence issuer, and comment delivery rows.

## Gate

Complete.

- Phase 6 focused command passed.
- Public actor-facing contracts use identity ids for the remaining replacement targets.
- Remaining actor-address terms are documented route projections, private daemon payloads, migration readers, or negative assertions.
- Actor route projections are resolver-backed; no live implementation derives role from identity-id text.
- No compatibility dual public locator contract was introduced.
