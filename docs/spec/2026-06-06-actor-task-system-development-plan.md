# Actor Task System Development Plan

Date: 2026-06-06
Source:
- `docs/spec/2026-06-06-actor-task-system-test-plan.md`
- `docs/memo/2026-06-06-actor-task-system-development-and-test-plan.md`
- `docs/memo/2026-06-06-actor-task-system-team-show-v2.html`

## Goal

Replace the old task `propose/confirm` actor-facing workflow with one Task Management System backed by taskbox, exposed through explicit Task Operations, and rendered through innerTUI TaskViewModel surfaces.

## Non-Negotiables

- Work only in `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`.
- Do not preserve old actor-facing `task.propose` / `task.confirm` compatibility aliases.
- Do not edit `buddyswitch/objects/**` or old private runtime state directly.
- Do not mutate track, artifact, message, comment, request, or actor private files from task operations.
- Use tests first for behavior changes and verify red before implementation.
- Keep verification focused; do not run broad service-starting suites unless lifecycle cleanup is proven.

## File Responsibilities

- `scripts/env/repos/tasks.py`: taskbox storage backend, strict task validation, id helpers, history/event append/read helpers.
- `scripts/env/domain/task_management.py`: Task Management System operations, transition rules, evidence rules, TaskViewModel projection.
- `scripts/env/tools/task/tool.py`: task tool catalog and action schemas for explicit Task Operations.
- `scripts/env/tools/task/_impl.py`: broker adapter from env.tool actions to Task Management System operations and tool result formatting.
- `scripts/env/domain/task_tui.py`: innerTUI rendering from TaskViewModel only.
- `buddyswitch/skills/shared/task-management/SKILL.md`: actor guidance for judging task relation and using task operations without duplicating schemas.
- `scripts/env/tool_runtime/role_auth.py`: role permissions for new task actions.
- `scripts/env/tool_runtime/context.py`: context source descriptions using new task actions.
- `scripts/env/tools/context/_impl.py`: context source-of-truth descriptions using new task actions.
- `scripts/env/tools/request/tool.py`: adjacent request tool guidance that points private planning to new task operations.
- `tools/launcher/input_wrappers/task_tui.py`: launcher input wrapper using TaskViewModel rendering.
- `tests/test_task_env_tool.py`: behavior and persistence tests.
- `tests/test_task_input_context.py`: TaskViewModel and innerTUI context tests.
- `tests/test_task_checkout_handler.py`: checkout handler integration with new render function inputs.
- `tests/test_task_management_skill_architecture.py`: skill/catalog/live surface architecture tests.
- `tests/test_env_tool_semantic_contract.py`: global tool semantic contract updates.

## Implementation Sequence

### Task 1: Replace Tests First

Edit tests before production code:

- Update `tests/test_task_env_tool.py` from `current/propose/confirm` to `current/capture/select/switch_request/switch_confirm/progress/checkout/review`.
- Update helper history events from `task.create`, `task.close`, and `task.block` to target event names.
- Update `tests/test_task_input_context.py` to assert TaskViewModel fields and new TUI text.
- Update `tests/test_task_checkout_handler.py` mocks from `current_snapshot` to `current_view` and checkout text to `task.checkout`.
- Update `tests/test_task_management_skill_architecture.py` to assert new tool operations and skill wording.
- Update `tests/test_env_tool_semantic_contract.py` expected task actions, adjacent action checks, role permissions, and task mutation contract.

Run:

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_task_env_tool.py \
  tests/test_task_input_context.py \
  tests/test_task_checkout_handler.py \
  tests/test_task_management_skill_architecture.py \
  tests/test_env_tool_semantic_contract.py \
  -q
```

Expected: fail because production code still exposes old task actions and old model fields.

### Task 2: Rebuild Task Core

Modify `scripts/env/repos/tasks.py`:

- Add `captured` to `VALID_TASK_STATUS`.
- Keep `archived` only as existing cleanup compatibility in storage validation; do not expose it as an actor operation.
- Preserve strict rejection of retired lineage and publication-style fields.
- Add focused helpers if useful:
  - `list_shelf_tasks(...)`
  - `list_reviewable_tasks(...)`
  - `append_event(...)` as a clearer wrapper over history append, or keep `append_history` if tests use parsed events.
- Keep `next_task_id` and `next_confirmation_id`; confirmation ids may still be used for pending switch ids.
- Ensure `create_task(...)` can create `captured` tasks and records explicit target event names when called directly.

Run focused repo-related tests from Task 1 until core validation failures are resolved.

### Task 3: Rebuild Task Management System

Replace old public domain functions with explicit operations in `scripts/env/domain/task_management.py`:

- `current_view(...)`
- `capture_task(...)`
- `select_task(...)`
- `request_task_switch(...)`
- `confirm_task_switch(...)`
- `append_task_progress(...)`
- `checkout_task(...)`
- `review_tasks(...)`

Required TaskViewModel fields:

- `owner_actor`
- `current_anchor`
- `task_state`
- `shelf`
- `pending_switch`
- `recent_events`
- `recent_evidence`
- `available_actions`
- `checkout_cue`
- `warnings`

State rules:

- `capture_task` creates `captured` and never changes current.
- `select_task` requires no active current and target status `captured` or `blocked`.
- `request_task_switch` requires active current and creates pending switch only.
- `confirm_task_switch(accept)` changes current; `reject` keeps current and clears pending.
- `append_task_progress` requires active current and evidence text or refs.
- `checkout_task(continue)` records a continue event without closing.
- `checkout_task(finish)` requires evidence and marks done.
- `checkout_task(block)` requires reason and marks blocked.
- Rejections return `state_changed=false` and do not write taskbox.

Run focused behavior tests until the domain rules are green through direct calls and tool dispatch.

### Task 4: Replace Task Tool Surface

Modify `scripts/env/tools/task/tool.py`:

- Expose exactly `current`, `capture`, `select`, `switch_request`, `switch_confirm`, `progress`, `checkout`, `review`.
- Remove old `propose` and `confirm` actions.
- For each action, define reads/writes/durability/visibility/result content/failure-state guarantee.
- State that task refs are private context links and do not mutate sibling runtime objects.
- Use required permissions:
  - `task.read`
  - `task.capture`
  - `task.select`
  - `task.switch_request`
  - `task.switch_confirm`
  - `task.progress`
  - `task.checkout`
  - `task.review`

Modify `scripts/env/tools/task/_impl.py`:

- Map each action to the corresponding Task Management System function.
- Success responses include `state_changed`, `created_ids`, `updated_ids`, `state_changes`, and `view`.
- Rejections include `why_blocked`, `correctable_fields`, retry guidance, and an impact statement that state did not change.

Modify `scripts/env/tool_runtime/role_auth.py` and `scripts/env/tool_runtime/context.py` for new action names.

Run semantic and behavior tests.

### Task 5: Replace innerTUI Surface

Modify `scripts/env/domain/task_tui.py`:

- Render from TaskViewModel field names only.
- Main context must include current anchor, shelf, pending switch, recent evidence, available actions, checkout cue, and warnings.
- Checkout context must show `task.checkout` choices: `continue`, `finish`, `block`.
- Remove `Task Handling Cue` and all `task.propose`/`task.confirm` wording.

Modify checkout handler only if the function name or field names changed.

Run `tests/test_task_input_context.py` and `tests/test_task_checkout_handler.py`.

### Task 6: Replace Skill Guidance

Modify `buddyswitch/skills/shared/task-management/SKILL.md`:

- Describe actor judgment: continue, capture, select, switch request/confirm, progress, checkout, review.
- Point exact schemas to runtime tool catalog and context discovery.
- Do not copy JSON schemas or implementation state machine details.
- Remove old `task__propose`, `task__confirm`, `task.propose`, and `task.confirm` text.

Run `tests/test_task_management_skill_architecture.py` and the live residue scan.

### Task 7: Focused Verification And Review

Run:

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_task_env_tool.py \
  tests/test_task_input_context.py \
  tests/test_task_checkout_handler.py \
  tests/test_task_management_skill_architecture.py \
  tests/test_env_tool_semantic_contract.py \
  -q
```

Run:

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

Run:

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

Expected: pytest and compile pass; residue scan has no matches.

Review checklist:

- Test plan requirements map to tests.
- No actor-facing old operation names remain in live surfaces.
- Rejections are state-unchanged where required.
- Task operations do not mutate sibling runtime objects.
- No broad service-starting verification was run without lifecycle proof.

## Acceptance

Implementation is complete only when Task 7 passes and the review checklist has no gaps.
