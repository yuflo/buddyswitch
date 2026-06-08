# Product Request Removal Phase 2 Prompt

Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`

Implement product request removal from:

- `docs/spec/2026-06-08-product-request-removal-test-plan.md`
- `docs/spec/2026-06-08-product-request-removal-development-plan.md`
- `docs/memo/2026-06-08-product-request-removal-task.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`

Rules:

1. Stay in the `fea-daemon` worktree; do not touch main.
2. Follow sharp-forward: delete the product request object/tool path directly. Do not add
   compatibility wrappers, tombstone tools, aliases, or an empty request object directory.
3. Use tests first. Update focused tests, run them, and verify they fail while product request still
   exists before production removal.
4. Preserve unrelated request-named surfaces: `search.request`, `task.switch_request`, HTTP/JSON-RPC
   and runtime broker requests, `request_id`, `request-payload`, and `request-dev-code-review`.
5. Remove product request from tool discovery, context outputs, artifact backlinks, task ref/origin
   schemas, role auth, env profiles, manifest skill wiring, role contracts, and tests.
6. Keep verification focused until the relevant contract suite is green. Do not run broad
   daemon/app-server/browser suites unless resource lifecycle cleanup is proven per
   `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.
7. Completion requires focused tests, profile validation, compile checks, residue scans, broad pytest,
   and a final review checklist to pass.

Required final verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py \
  tests/test_black_box_tool_runtime.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_router.py \
  tests/test_env_tool_package_independence.py \
  tests/test_env_tool_active_task_gate.py \
  tests/test_context_binding_env_tool.py \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_artifact_env_tool.py \
  tests/test_env_layer_end_to_end.py \
  tests/test_env_tool_response_contract.py \
  tests/test_runtime_skills.py \
  tests/test_env_manifest_v2.py \
  tests/test_buddy_env_profiles.py \
  tests/test_role_action_auth.py \
  tests/test_task_env_tool.py \
  tests/test_task_management_skill_architecture.py \
  -q
```

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/env_profiles.py validate-all
```

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile \
  scripts/env_legacy_store.py \
  scripts/env/repos/runtime_files.py \
  scripts/env/tool_runtime/context.py \
  scripts/env/tool_runtime/role_auth.py \
  scripts/env/tools/context/tool.py \
  scripts/env/tools/context/_impl.py \
  scripts/env/domain/artifact_relations.py \
  scripts/env/domain/artifact_visibility.py \
  scripts/env/domain/tasks.py \
  scripts/env/tools/task/tool.py \
  scripts/env_profiles.py
```

```bash
rg -n "request-tool|request\\.list|request\\.get|request\\.create|request\\.accept|request\\.block|request\\.complete|request\\.cancel|candidate_requests|request_effects|REQUESTS_DIR|target_ref_by_requests|result_ref_by_requests|target_request_count|result_request_count" scripts/env scripts/env_profiles.py buddyswitch framework tests README.md AGENTS.md tools/launcher/assets/roles -g '!tests/helpers/fake_codex.py'
```

Expected for the residue scan: no hits.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests -q
```

Final review:

- Confirm `request` is absent from `registry.supported_tools()`.
- Confirm request package/domain/repo/skill/test files no longer exist.
- Confirm runtime setup does not create `buddyswitch/objects/requests`.
- Confirm context outputs and source descriptions have no request/candidate request sections.
- Confirm artifact relation summaries have no request backlink or request count fields.
- Confirm task ref/origin schemas exclude product request refs while `task.switch_request` remains.
- Confirm role auth and env profiles have no `request.*` permissions or `request_effects`.
- Confirm manifest and runtime skill tests do not ship `request-tool` while dev keeps
  `request-dev-code-review`.
- Confirm role contracts no longer instruct actors to use request lifecycle tools.
- Confirm remaining request tokens are non-product request concepts.
- Confirm no service-starting broad suite was run without lifecycle proof.
