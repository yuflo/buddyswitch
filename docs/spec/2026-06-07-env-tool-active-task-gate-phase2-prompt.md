# Env Tool Active Task Gate Phase 2 Prompt

Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`

Implement the env.tool active-task gate from:

- `docs/spec/2026-06-07-env-tool-active-task-gate-test-plan.md`
- `docs/spec/2026-06-07-env-tool-active-task-gate-development-plan.md`
- `docs/memo/2026-06-07-env-tool-active-task-gate-task.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`

Rules:

1. Stay in the `fea-daemon` worktree; do not touch main.
2. Follow sharp-forward: add one required action contract, `task_requirement = free | active_task_required`, and one central registry gate. Do not add handler-level active-task checks or compatibility wrappers.
3. Use tests first. Write/update focused tests, run them, and verify they fail for the missing behavior before production implementation.
4. The gate order is fixed: resolve tool/action, role authorization, args shape validation, active task gate, then handler dispatch.
5. Rejection must use canonical `tool_results.rejection(...)` with `E_ACTIVE_TASK_REQUIRED`, `permission_boundary="task.active_anchor"`, `state_changed=false`, `durability="none"`, and guidance through `task.current`, `task.capture`, and `task.select`.
6. Keep verification focused. Do not run broad daemon/app-server/browser suites unless service lifecycle cleanup is proven per `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.
7. Completion requires all focused tests, relevant contract tests, compile checks, and review checklist to pass.

Required final verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_active_task_gate.py -q
```

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_runtime_tool_feedback.py \
  -q
```

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile \
  scripts/env/tool_runtime/definition.py \
  scripts/env/tool_runtime/registry.py \
  scripts/env/tools/artifact/tool.py \
  scripts/env/tools/comment/tool.py \
  scripts/env/tools/context/tool.py \
  scripts/env/tools/evidence/tool.py \
  scripts/env/tools/message/tool.py \
  scripts/env/tools/request/tool.py \
  scripts/env/tools/search/tool.py \
  scripts/env/tools/task/tool.py \
  scripts/env/tools/track/tool.py
```

Final review:

- Confirm every registered action declares `task_requirement`.
- Confirm all values are exactly `free` or `active_task_required`.
- Confirm the classification table in the test plan matches current registered actions.
- Confirm `operation_semantics` and tool catalog action semantics expose `task_requirement`.
- Confirm gated actions reject without active anchor before handler invocation.
- Confirm gated actions dispatch with an active anchor.
- Confirm free actions dispatch without active anchor.
- Confirm ordering: unsupported tool/action, role auth, and non-object args reject before the active-task gate.
- Confirm rejected gated actions leave runtime state unchanged.
- Confirm no service-starting broad suite was run without lifecycle proof.
