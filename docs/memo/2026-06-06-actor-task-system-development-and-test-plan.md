# Actor Task System Development And Test Plan

Date: 2026-06-06
Status: development memo for the actor-task-system rebuild
Related show page: `docs/memo/2026-06-06-actor-task-system-team-show-v2.html`

## One-Line Decision

Rebuild BuddySwitch task management as one actor-used Task Management System: Task Core owns truth, Task Operations own semantics, taskbox stores facts, task tools expose operations, and innerTUI renders every task surface visible to the actor.

## Current Bottleneck

The current task path is functional but not yet a coherent product system:

- `scripts/env/repos/tasks.py` already provides instance-local taskbox persistence.
- `scripts/env/domain/task_management.py` currently behaves like a canonical snapshot plus `propose/confirm` mutation service.
- `scripts/env/tools/task/tool.py` exposes `task.current`, `task.propose`, and `task.confirm`.
- `scripts/env/domain/task_tui.py` still renders actor-facing cues such as `task.propose(start)`, `task.propose(switch)`, and `task.confirm`.
- `buddyswitch/skills/shared/task-management/SKILL.md` still teaches the old propose/confirm workflow.

The bottleneck is not a missing helper. The bottleneck is that product semantics are split across tools, domain service, skill text, and innerTUI text. The rebuild should replace that split with one task system.

## Product Boundary

Actor is the user.

Task Management System is the actor's workbench, not a controller that manages the actor from above. The actor understands input meaning, chooses the task action, does the work, and submits evidence. The system preserves state, exposes legal operations, records evidence, and renders task context through innerTUI.

Layering:

```text
actor
  -> innerTUI
  -> task tools
  -> Task Management System
  -> taskbox
```

Do not route actor, tools, or innerTUI directly to taskbox as a product API. `taskbox` remains the storage backend for Task Core.

## Non-Negotiable Rules

- No long-lived dual path: do not keep `task.propose` / `task.confirm` as actor-facing compatibility operations after the new system lands.
- No scattered tool semantics: tools must expose Task Operations, not define independent meanings for start, switch, finish, or block.
- No prompt compensation: do not use skill or AGENTS text to cover unclear tool contracts or weak tool feedback.
- No shared-object mutation leak: task refs may point to track/artifact/message/comment/request, but task operations do not mutate those sibling object states.
- No live surface residue: every live actor-visible task surface must teach the new operations only.
- No direct runtime object edits: do not edit `buddyswitch/objects/**` or old private runtime paths directly.

## Target Model

### Task Core

Task Core owns the persistent facts:

- `Task`: `id`, `owner_actor`, `title`, `summary`, `body`, `status`, `priority`, `origin`, `refs`, `progress_summary`, `created_at`, `updated_at`, `closed_at`.
- `TaskEvent`: append-only event records for state and evidence changes.
- `CurrentPointer`: the one active task anchor, derived from events or stored as a taskbox-owned fact.
- `TaskViewModel`: actor-facing projection rendered by innerTUI and returned by task tools.

Target task statuses:

```text
captured -> active -> blocked
captured -> active -> done
blocked -> active
```

`captured` means the actor saved work to the shelf. It must not become current automatically.

### Task Events

Use explicit event names. Do not keep ambiguous proposal events as the final model.

Target event set:

- `task.captured`
- `task.selected`
- `task.switch.requested`
- `task.switch.confirmed`
- `task.switch.rejected`
- `task.progress.appended`
- `task.checkout.continued`
- `task.blocked`
- `task.finished`
- `task.reviewed`

Every mutation event should record actor-visible `reason` or `evidence` where required, plus changed ids and refs when relevant.

### TaskViewModel

TaskViewModel is the only source for actor-visible task state.

Required fields:

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

innerTUI renders this model. Tool responses may return this model. Skills should reference the model conceptually but should not copy schemas.

## Target Operations

All public task tools are adapters over these operations:

| Operation | Meaning | Mutation |
| --- | --- | --- |
| `current` | Return TaskViewModel. | none |
| `capture` | Create a captured task from a work demand. | creates task + `task.captured` |
| `select` | Make a captured task the current anchor when no active anchor exists. | updates task + `task.selected` |
| `switch_request` | Ask to switch away from an active anchor. | creates pending switch event only |
| `switch_confirm` | Accept or reject one pending switch. | accept changes current; reject keeps current |
| `progress` | Append progress summary, evidence, and refs to current task. | updates current task + event |
| `checkout` | End a work block as continue, finish, or block. | continue event, done, or blocked |
| `review` | Show captured, blocked, or stale work cues. | read by default; may append reviewed event |

## Implementation Plan

### Step 1: Lock the failing tests first

Modify or add tests before implementation:

- `tests/test_task_env_tool.py`
- `tests/test_task_input_context.py`
- `tests/test_task_checkout_handler.py`
- `tests/test_task_management_skill_architecture.py`
- `tests/test_env_tool_semantic_contract.py`

The first test batch should fail because the repo currently exposes `propose/confirm` and lacks `capture/select/progress/checkout/review`.

### Step 2: Rebuild Task Core in `scripts/env/repos/tasks.py`

Keep this file as the taskbox backend only.

Required changes:

- Add `captured` to valid task statuses.
- Retain `active`, `blocked`, `done`, and `archived` only if `archived` is still used by existing taskbox cleanup.
- Add helpers for listing shelf tasks and active/blockable tasks.
- Add event append/read helpers for the target event names.
- Keep validation strict: reject retired fields and publication-style payloads.

This layer should not know about innerTUI wording or tool response formats.

### Step 3: Rebuild Task Management System in `scripts/env/domain/task_management.py`

This becomes the system owner, not a propose helper.

Required public functions:

- `current_view(...)`
- `capture_task(...)`
- `select_task(...)`
- `request_task_switch(...)`
- `confirm_task_switch(...)`
- `append_task_progress(...)`
- `checkout_task(...)`
- `review_tasks(...)`

Required behavior:

- `current_view` returns TaskViewModel and never mutates taskbox.
- `capture_task` creates `captured` tasks and never changes current anchor.
- `select_task` only succeeds when there is no active current anchor.
- `request_task_switch` requires an active current anchor and creates only a pending switch.
- `confirm_task_switch` accepts or rejects a pending switch; accept changes current, reject keeps current.
- `append_task_progress` requires current active task and evidence text or refs.
- `checkout_task` supports `continue`, `finish`, and `block`.
- `finish` requires evidence.
- `block` requires reason.
- Rejections must return `state_changed=false` and leave taskbox unchanged.

### Step 4: Replace task tool surface

Modify:

- `scripts/env/tools/task/tool.py`
- `scripts/env/tools/task/_impl.py`

Target public actions:

- `current`
- `capture`
- `select`
- `switch_request`
- `switch_confirm`
- `progress`
- `checkout`
- `review`

Tool catalog requirements:

- Describe each operation's reads, writes, durability, and failure-state guarantee.
- State that task refs are private context links and do not publish or mutate referenced objects.
- Remove actor-facing `task.propose` and `task.confirm` actions.
- Do not add compatibility aliases for the old actions.

Tool response requirements:

- Always include `state_changed`.
- Include `created_ids`, `updated_ids`, and `state_changes` for mutations.
- Include TaskViewModel after successful reads and writes.
- For rejection, include `why_blocked`, `correctable_fields`, retry guidance, and a state-unchanged impact statement.

### Step 5: Replace innerTUI task surface

Modify:

- `scripts/env/domain/task_tui.py`

Required render behavior:

- Render from TaskViewModel only.
- Show current anchor, shelf, pending switch, recent evidence, available actions, checkout cue, and warnings.
- Remove `Task Handling Cue`.
- Remove `task.propose(start)`, `task.propose(switch)`, `task.propose(finish)`, `task.propose(block)`, and `task.confirm` wording.
- Checkout surface should show `task.checkout` choices only: `continue`, `finish`, `block`.

### Step 6: Replace skill guidance

Modify:

- `buddyswitch/skills/shared/task-management/SKILL.md`

Required guidance:

- Actor judges input relation.
- Task tools expose Task Operations.
- Exact payload schemas come from tool catalog and context discovery.
- Skill does not duplicate schemas.
- Skill does not mention old propose/confirm operations.

### Step 7: Clean live surfaces

Run scoped residue scans only on live surfaces:

```bash
rg -n "task\\.propose|task\\.confirm|Task Handling Cue" \
  scripts/env/domain/task_tui.py \
  buddyswitch/skills/shared/task-management/SKILL.md \
  scripts/env/tools/task/tool.py \
  scripts/env/tools/task/_impl.py
```

Expected result: no hits.

Do not scan old memos as cleanup targets. Historical notes are allowed to preserve old terms.

## Test Plan

### Behavior Tests

Add focused black-box tests in `tests/test_task_env_tool.py`.

Required cases:

- `task.current` returns TaskViewModel and does not mutate history or task docs.
- `task.capture` creates a captured task and does not change active current anchor.
- `task.select` selects a captured task only when no active current anchor exists.
- `task.select` is rejected when an active current anchor exists.
- `task.switch_request` creates a pending switch and does not change current anchor.
- `task.switch_confirm` accept changes current anchor.
- `task.switch_confirm` reject keeps current anchor.
- `task.progress` appends evidence and refs to the current task.
- `task.checkout` with `continue` records a continue event without closing the task.
- `task.checkout` with `finish` marks current task `done` and requires evidence.
- `task.checkout` with `block` marks current task `blocked` and requires reason.
- Invalid payloads and wrong task ids return `state_changed=false`.

Each mutation test must inspect both:

- tool response fields;
- persisted taskbox task docs and history.

### Surface Tests

Add or update tests around:

- `tests/test_task_input_context.py`
- `tests/test_task_checkout_handler.py`
- `tests/test_task_management_skill_architecture.py`

Required cases:

- innerTUI task context renders anchor, shelf, pending switch, evidence, available actions, and warnings.
- checkout renderer uses `task.checkout`, not old propose/confirm wording.
- task-management skill names the new operation set and does not copy runtime schemas.
- live surface scan rejects `task.propose`, `task.confirm`, and `Task Handling Cue` in active task surfaces.

### Tool Contract Tests

Update `tests/test_env_tool_semantic_contract.py` or the nearest existing tool contract test.

Required cases:

- task tool definition exposes exactly the target operation names.
- each operation declares reads, writes, mutates, durability, visibility, result content level, and failure-state guarantee.
- mutation actions say they only write active actor taskbox files/history.
- task operations declare they do not mutate track, artifact, message, comment, request, or actor_private file contents.

### Lifecycle And Integration Tests

Keep daemon-related verification focused unless process lifecycle is proven clean.

Use:

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
  scripts/env/domain/task_tui.py
```

Run residue scan:

```bash
rg -n "task\\.propose|task\\.confirm|Task Handling Cue" \
  scripts/env/domain/task_tui.py \
  buddyswitch/skills/shared/task-management/SKILL.md \
  scripts/env/tools/task/tool.py \
  scripts/env/tools/task/_impl.py
```

Expected result: no hits.

If broader daemon/app-server/browser tests are added, follow `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`: run focused tests first, check residual processes and sockets, then broaden.

## Acceptance Criteria

The development task is complete only when all criteria are true:

- Actor-visible task management is expressed through innerTUI TaskViewModel surfaces.
- Task tools expose the target operation set and no actor-facing propose/confirm path remains.
- Task Management System is the only owner of state transitions and evidence rules.
- taskbox remains the storage backend and is not exposed as the product API.
- `capture` does not auto-select.
- switch requires request plus confirm.
- progress and checkout record evidence-backed events.
- rejection paths prove no taskbox or sibling runtime state changed.
- live surface scans show no old task operation wording.
- focused tests and compile checks pass.

## Implementation Order

Use this order to keep the rebuild sharp:

1. Write failing behavior and surface tests.
2. Rebuild taskbox-backed core facts and event helpers.
3. Replace Task Management System operations.
4. Replace tool catalog and tool adapters.
5. Replace innerTUI task renderer.
6. Replace task-management skill wording.
7. Run focused tests.
8. Run compile check.
9. Run live surface residue scan.

Do not expand this task into message/request/artifact lifecycle ownership. Those objects only feed task origin, refs, or relation input in this rebuild.
