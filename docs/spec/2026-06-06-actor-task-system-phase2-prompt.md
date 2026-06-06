# Actor Task System Phase 2 Prompt

Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`

Implement the actor task system rebuild from:

- `docs/spec/2026-06-06-actor-task-system-test-plan.md`
- `docs/spec/2026-06-06-actor-task-system-development-plan.md`
- `docs/memo/2026-06-06-actor-task-system-development-and-test-plan.md`
- `docs/memo/2026-06-06-actor-task-system-team-show-v2.html`

Rules:

1. Stay in the `fea-daemon` worktree; do not touch main.
2. Follow sharp-forward: replace the old actor-facing `task.propose` / `task.confirm` path; do not add compatibility aliases or dual task workflows.
3. Use tests first. Write or update the focused tests, run them, and verify they fail for the missing new behavior before changing production code.
4. Keep verification focused. Do not run broad daemon/app-server/browser suites unless service lifecycle cleanup is proven per `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.
5. Implement only the actor task system slice. Do not redesign message/request/artifact/track lifecycle.
6. Task operations must not mutate sibling runtime objects or actor private files.
7. Completion requires all focused tests, compile checks, residue scan, and review checklist to pass.

Required final verification:

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_task_env_tool.py \
  tests/test_task_input_context.py \
  tests/test_task_checkout_handler.py \
  tests/test_task_management_skill_architecture.py \
  tests/test_env_tool_semantic_contract.py \
  -q
```

```bash
python3 -m py_compile \
  scripts/env/repos/tasks.py \
  scripts/env/domain/task_management.py \
  scripts/env/tools/task/tool.py \
  scripts/env/tools/task/_impl.py \
  scripts/env/domain/task_tui.py \
  tools/launcher/input_wrappers/task_tui.py \
  tools/launcher/task_checkout_handler.py \
  scripts/env/tool_runtime/role_auth.py \
  scripts/env/tool_runtime/context.py \
  scripts/env/tools/context/_impl.py \
  scripts/env/tools/request/tool.py
```

```bash
rg -n "task\\.propose|task\\.confirm|task__propose|task__confirm|Task Handling Cue" \
  scripts/env/domain/task_tui.py \
  buddyswitch/skills/shared/task-management/SKILL.md \
  scripts/env/tools/task/tool.py \
  scripts/env/tools/task/_impl.py \
  tools/launcher/input_wrappers/task_tui.py \
  tools/launcher/task_checkout_handler.py \
  scripts/env/tool_runtime/context.py \
  scripts/env/tool_runtime/role_auth.py \
  scripts/env/tools/context/_impl.py \
  scripts/env/tools/request/tool.py
```

Expected residue scan: no matches.

Final review:

- Confirm task tool operations are exactly `current`, `capture`, `select`, `switch_request`, `switch_confirm`, `progress`, `checkout`, and `review`.
- Confirm TaskViewModel is the only source for innerTUI task rendering.
- Confirm capture does not auto-select.
- Confirm switch uses request plus confirm.
- Confirm progress and checkout write evidence-backed events.
- Confirm rejected invalid payloads and wrong task ids leave taskbox and sibling runtime state unchanged.
- Confirm live actor-visible surfaces no longer mention old task operation wording.
