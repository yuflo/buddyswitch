# Actor Task System Test Plan

Date: 2026-06-06
Source:
- `docs/memo/2026-06-06-actor-task-system-development-and-test-plan.md`
- `docs/memo/2026-06-06-actor-task-system-team-show-v2.html`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`

## Target

Prove BuddySwitch task management is one actor-used Task Management System:

- Task Core persists task facts and events in the instance-local taskbox.
- Task Operations define the only public task semantics.
- Task tools expose only `current`, `capture`, `select`, `switch_request`, `switch_confirm`, `progress`, `checkout`, and `review`.
- innerTUI renders actor-visible task state from TaskViewModel.
- live actor surfaces no longer teach `task.propose`, `task.confirm`, or `Task Handling Cue`.

The tests must be requirement-driven. Do not shape tests around implementation shortcuts or keep old behavior alive to make tests easier.

## Resource Lifecycle Guard

This plan uses focused unit/integration tests that route through the broker/tool runtime but do not start long-lived app-server, browser, runtime broker daemon, or watcher processes.

Do not run broad launcher, browser, app-server, or daemon suites unless their service-starting helpers have explicit registration, teardown, pid/process-group termination, temporary file cleanup, and residual checks as required by `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.

## Behavior Tests

Primary file: `tests/test_task_env_tool.py`

### `task.current`

Required cases:

- Empty taskbox returns a TaskViewModel with `task_state="none"`, `current_anchor=None`, empty `shelf`, empty `recent_events`, empty `available_actions` appropriate for no active anchor, and `state_changed=false`.
- Existing current task returns `current_anchor`, `task_state`, `recent_events`, `recent_evidence`, `available_actions`, and `checkout_cue`.
- `task.current` is read-only: task docs and `history.md` are byte-for-byte unchanged before and after the call.

### `task.capture`

Required cases:

- Captures a new task as `status="captured"` with title, body, summary, priority, origin, refs, timestamps, and `task.captured` history event.
- Does not change an existing active current anchor.
- Returns `state_changed=true`, `created_ids`, `state_changes`, and TaskViewModel with the captured task in `shelf`.
- Rejects publication-style fields such as `visibility`, `template`, `source_refs`, and `artifact_ids` with `state_changed=false` and no taskbox or sibling object mutation.

### `task.select`

Required cases:

- Selects a captured or blocked task as current only when there is no active current anchor.
- Updates selected task to `active` and appends `task.selected`.
- Rejects unknown, active, done, archived, or otherwise non-resumable task ids.
- Rejects selection while an active current anchor exists and keeps the taskbox unchanged.

### `task.switch_request`

Required cases:

- Requires an active current anchor.
- Accepts either an existing captured/blocked target id or a new task payload target.
- Creates one pending switch event and does not change current anchor.
- For new target payloads, does not create the target task until `switch_confirm(accept)`.
- Rejects duplicate pending switch with `state_changed=false`.

### `task.switch_confirm`

Required cases:

- Accepting an existing target changes current anchor, makes target `active`, shelves previous active task as `captured`, clears pending switch, and appends `task.switch.confirmed`.
- Accepting a new target creates it as `active`, shelves previous active task as `captured`, clears pending switch, and returns created/updated ids.
- Rejecting a pending switch keeps current anchor unchanged, clears pending switch, appends `task.switch.rejected`, and returns `state_changed=true` because history changed.
- Wrong confirmation id or malformed decision is rejected with no mutation.

### `task.progress`

Required cases:

- Requires an active current anchor.
- Requires non-empty evidence text or at least one ref.
- Appends progress evidence to the current task, updates `progress_summary`, `updated_at`, refs when supplied, and appends `task.progress.appended`.
- Rejects wrong task id or missing evidence/refs with no mutation.

### `task.checkout`

Required cases:

- `next="continue"` appends `task.checkout.continued`, updates progress summary when provided, keeps the current task active, and keeps `closed_at=None`.
- `next="finish"` requires evidence, marks current task `done`, sets `closed_at`, appends `task.finished`, and clears current anchor in the next TaskViewModel.
- `next="block"` requires reason, marks current task `blocked`, keeps `closed_at=None`, appends `task.blocked`, and clears active current anchor while making the blocked task visible for review.
- Wrong task id or missing required evidence/reason is rejected with no mutation.

### `task.review`

Required cases:

- Read-default review returns captured and blocked tasks, stale warnings, available actions, and recent events without mutation.
- Optional reviewed event, if implemented, appends only `task.reviewed` and does not alter task status.

## Surface Tests

Primary files:

- `tests/test_task_input_context.py`
- `tests/test_task_checkout_handler.py`
- `tests/test_task_management_skill_architecture.py`

Required cases:

- `task_management.current_view` returns TaskViewModel fields: `owner_actor`, `current_anchor`, `task_state`, `shelf`, `pending_switch`, `recent_events`, `recent_evidence`, `available_actions`, `checkout_cue`, and `warnings`.
- `task_tui.render_task_tui` renders current anchor, shelf, pending switch, recent evidence, available actions, checkout cue, and warnings from TaskViewModel only.
- `task_tui.render_stop_task_tui` renders checkout choices using `task.checkout` with `continue`, `finish`, and `block`.
- The checkout handler calls `task_management.current_view` and `task_tui.render_stop_task_tui`.
- The task-management skill names the new operation set, points actors to runtime tool catalog/context discovery for schemas, and does not copy JSON schemas.
- Live surface scan rejects old actor-facing wording in:
  - `scripts/env/domain/task_tui.py`
  - `buddyswitch/skills/shared/task-management/SKILL.md`
  - `scripts/env/tools/task/tool.py`
  - `scripts/env/tools/task/_impl.py`
  - `tools/launcher/input_wrappers/task_tui.py`
  - `scripts/env/tool_runtime/context.py`
  - `scripts/env/tool_runtime/role_auth.py`
  - `scripts/env/tools/context/_impl.py`
  - `scripts/env/tools/request/tool.py`

## Tool Contract Tests

Primary file: `tests/test_env_tool_semantic_contract.py`

Required cases:

- `env_tools_description()["task"]["operations"]` is exactly:
  `current`, `capture`, `select`, `switch_request`, `switch_confirm`, `progress`, `checkout`, `review`.
- Each action exposes source-of-truth semantic fields: reads, writes, does_not_write, visibility, durability, result content level, success effect, and failure-state guarantee.
- Mutation actions write only active actor taskbox task docs/history.
- Task refs are private context links and do not publish or mutate referenced track, artifact, message, comment, request, or actor private file contents.
- Role policy covers the new permissions and no longer requires old `task.propose` or `task.confirm` permissions.

## Focused Verification Commands

Run red/green focused tests:

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_task_env_tool.py \
  tests/test_task_input_context.py \
  tests/test_task_checkout_handler.py \
  tests/test_task_management_skill_architecture.py \
  tests/test_env_tool_semantic_contract.py \
  -q
```

Run compile verification:

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

Run live residue scan:

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

Expected: no matches.

## Acceptance

The test plan passes only when behavior tests prove state transitions and persistence, surface tests prove actor-visible content uses the new TaskViewModel/operation language, semantic tests prove tool contract completeness, compile checks pass, and live residue scan has no old actor-facing operation wording.
