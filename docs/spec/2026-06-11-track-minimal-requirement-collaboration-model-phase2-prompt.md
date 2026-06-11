# Phase 2 Prompt: Track Minimal Requirement Collaboration Model

Work on `main` in `/Users/chen/Dev/buddyswitch`.

Objective: execute the test and development plans for the Track minimal requirement collaboration model until all required tests pass and final review accepts the result.

Read first:

```text
docs/memo/2026-06-11-track-minimal-requirement-collaboration-model.md
docs/bitter/2026-05-26-test-resource-lifecycle-principles.md
docs/spec/2026-06-11-track-minimal-requirement-collaboration-model-test-plan.md
docs/spec/2026-06-11-track-minimal-requirement-collaboration-model-development-plan.md
```

Execution rules:

1. Use test-first changes whenever behavior changes.
2. Replace old Track behavior directly. Do not keep compatibility aliases for `track.update_now`, `owner_role`, `created_by_actor`, `health`, `appetite`, or `review`.
3. Keep scope limited to the Track owner-actor rebuild and required tests.
4. Run focused tests before broad tests.
5. Be careful with service-starting tests. Do not run broad launcher suites before focused tests are green; if broad tests start services, verify cleanup and residual processes before completion.
6. Final completion requires tests passing and a requirement-by-requirement review against the memo and both spec plans.

Primary verification:

```bash
python -m pytest tests/test_track_env_tool.py -q
python -m pytest tests/test_track_comment_env_tool.py -q
python -m pytest tests/test_notification_center.py tests/test_track_comment_added_handler.py -q
python -m pytest tests/test_role_action_auth.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_context_binding_env_tool.py -q
python -m pytest tests/test_env_tool_router.py tests/test_env_tool_payload_contract.py tests/test_env_tool_response_contract.py tests/test_black_box_tool_runtime.py -q
```

Completion review:

```bash
rg "track\\.update_now|owner_role|created_by_actor|VALID_TRACK_HEALTH|health|appetite|state.*review|kind.*proof" scripts tools framework buddyswitch tests
```

Production code must not retain old Track contract references. Tests may mention retired names only when asserting rejection or absence.

