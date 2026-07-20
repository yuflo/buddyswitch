# Demand / Task Phase 3 Actor Coordination Implementation Plan

> Execute through the repository's public test runner only. Keep this memo
> updated with exact RED/GREEN evidence and the real-actor receipt. Do not make a
> plan-only commit; commit this memo together with the completed implementation.

**Goal:** Let the Actor independently consume canonical Demands through one
active Task, then reconcile Task completion against the latest Demand revision,
without any Demand/Task domain coupling or generic-daemon business logic.

**Architecture:** Actor guidance is the semantic composition owner. Demand Sys
and Task Sys remain independent product owners. `task_sys.create` accepts an
opaque DemandRef snapshot, Task Sys atomically owns idempotency and the
single-active invariant, the existing side-first lifecycle executes the work,
and a Task-owned completion frame returns evidence to the parent Actor. Only the
Actor may decide whether to complete the latest Demand.

**Design:**
`docs/memo/2026-07-20-demand-task-phase-3-actor-coordination-design.md`

**Baseline:** `d5959e41d9cdc713f6ea3429996491aa423c8cc5`

**Status:** implemented; automated and real-actor acceptance passed

## 1. FRAME

### 1.1 Acceptance sentence

> A fresh real BuddySwitch actor receives two real IM needs, creates exactly one
> Task per selected Demand revision, never has more than one active Task, closes
> each Task through the existing lifecycle, receives a completion check, rereads
> the latest Demand, and explicitly completes each satisfied Demand with Task
> evidence; no Demand/Task domain imports or automatic cross-owner state changes
> exist, and generic daemon code remains product-neutral.

### 1.2 Protected contracts

- the five concrete Task statuses and legal transitions;
- direct TUI input remains outside Demand and Task intake;
- Phase 2 IM capture remains `IM -> Demand`, with no IM-to-Task path;
- Track comment ingress remains current until Phase 4, but must use the same
  Task creation gate and idempotency owner;
- public test entry remains `./buddyswitch-test`;
- generic daemon contracts/core/state/runtime/mailbox/client remain free of
  Demand and Task business semantics;
- existing unrelated runtime actors and `.superpowers/` remain untouched.

### 1.3 Explicit non-goals

Do not add queue, priority, scheduler, multi-Task relation, Task alignment state,
Demand callback, shared transaction, retry worker, feature flag, compatibility
action, Track cutover, offline capture, Web mutation, or direct-input intake.

## 2. TRACE

### 2.1 Current owner and call paths

```text
IM -> im_wake_handler
   -> demand_sys_daemon_adapter.capture_inbound
   -> demand_sys.create/check
   -> DaemonRuntime.input_actor([DEMAND CHECK])

Track -> track_comment_added_handler
      -> task_sys_ingress.ingest_track_comment
      -> task_sys.ingest
      -> task_sys_daemon_adapter.execute_instruction
      -> task_sys_runtime.start_side

Actor Task actions
  -> env.tool registry
  -> env.tools.task_sys._impl
  -> env.domain.task_sys
  -> TaskSysRuntimeAccess when runtime work is required

main turn completed
  -> TaskSysProgressCheckHandler
  -> existing parent Task Progress Check
```

### 2.2 Confirmed gaps to detect with RED

1. `task_sys.create` is absent from schema, authorization, runtime context,
   skills, roles, and responses.
2. `task_sys.ingest` can create multiple active Tasks and duplicates a replayed
   source.
3. Task creation is not actor-lock serialized.
4. a side Task can close without waking the parent Actor to reconcile Demand.
5. `task_sys.close` and `task_sys.need_parent` do not validate actor ownership.
6. the Demand Check prompt forbids the Phase 3 action.
7. actor guidance still teaches retired IM Task frames.
8. public Task projection cannot show the safe DemandRef needed for acceptance.
9. `scripts/env/domain/tasks.py` is dead pre-Task-Sys source in a live domain
   directory.

## 3. Target contracts

### 3.1 Domain create contract

Add one public domain operation in `scripts/env/domain/task_sys.py`:

```python
def create(
    *,
    actor_target: Mapping[str, Any],
    demand_ref: Mapping[str, Any],
    execution_brief: Mapping[str, Any],
) -> dict[str, Any]:
    """Create or replay one Demand-sourced Task through the canonical gate."""
```

Exact normalized inputs:

```python
demand_ref = {
    "demand_id": runtime_files.require_id(...),
    "basis_revision": positive_int,
}
execution_brief = {
    "description": non_empty_text,
    "detail": non_empty_text,
}
```

The domain maps these to existing Task fields:

```python
source = {"type": "demand", "ref": demand_ref}
context = {"execution_brief": execution_brief}
```

The return shape is:

```python
{
    "ok": True,
    "outcome": "created" | "existing",
    "state_changed": bool,
    "task_id": str,
    "task": dict,
    "instruction": dict | None,
}
```

Only `created` returns `start_side`. `existing` never starts another side turn.

### 3.2 Creation invariant

The domain owns one private creation primitive used by both `create` and
`ingest`:

```text
normalize source + target + context
  -> take actor-scoped Task creation lock
  -> find exact actor/source identity
      exact context match      -> existing
      different context        -> source conflict
  -> find any active actor Task
      found                    -> active conflict
  -> persist one side_processing Task
  -> return one start_side instruction
```

Lock path:

```text
buddyswitch/local/locks/task-sys/<actor-id>-<role-id>.lock
```

The lock is a local coordination fact, not canonical state. It is obtained with
`fcntl.flock(LOCK_EX)` and released in `finally`. No lock file content is a
product truth.

Add exact domain exceptions:

```python
TaskSysError
TaskSourceConflict
TaskActiveConflict
```

Each exception carries enough current Task identity for the actor tool to return
a structured rejection. Do not add error aliases or convert conflicts to
success.

### 3.3 Actor tool contract

Add one `ActionDefinition(name="create")` to
`scripts/env/tools/task_sys/tool.py`:

```json
{
  "demand_ref": {
    "demand_id": "demand-...",
    "basis_revision": 1
  },
  "execution_brief": {
    "description": "...",
    "detail": "..."
  }
}
```

Contract properties:

- exact fields; `additionalProperties: false` at every level;
- write action, `MUTATES_RUNTIME_OBJECTS`;
- `TASK_REQUIREMENT_FREE`, because this action establishes the active Task;
- permission `task_sys.create` for every manifest role;
- writes Task record and, only for `created`, a side turn through the existing
  Task runtime instruction;
- explicitly does not write Demand, Track, Message, Artifact, or parent Task
  state.

The tool adapter derives the actor target from `ToolContext`; callers cannot
supply one. It calls `context.rules.task_sys.create`, executes `start_side` only
for `created`, reloads current Task state after runtime execution, and returns:

```text
outcome, task_id, task_status, demand_ref, execution, runtime, state_changed
```

Targeted rejection codes:

```text
E_TASK_SYS_ACTIVE_CONFLICT
E_TASK_SYS_SOURCE_CONFLICT
E_TASK_SYS_PAYLOAD
```

### 3.4 Completion check contract

Add strict domain/runtime helpers:

```python
task_sys.completion_instruction(task_id)
task_sys_runtime.render_completion_frame(frame)
```

The existing `submit_parent` runtime instruction is reused. No new mailbox
command or generic daemon event is introduced.

Frame shape:

```json
{
  "kind": "task_sys.completion_frame",
  "task_id": "task-demand-...",
  "source": {
    "type": "demand",
    "ref": {
      "demand_id": "demand-...",
      "basis_revision": 3
    }
  },
  "evidence_ref": {
    "type": "task_sys.task",
    "ref": {"task_id": "task-demand-..."}
  },
  "completion": {
    "type": "completion",
    "processor": "side|parent",
    "summary": "...",
    "updated_at": "..."
  }
}
```

`render_submit_parent_frame` accepts exactly current parent handoff frames and
the new completion frame. The completion prompt says that the Task is already
terminal, presents only the receipt, asks the Actor to reconcile the source-owned
obligation through actor tools, and forbids reopening or replacing the same
terminal Task. It supplies the exact Task evidence reference and permits the
Actor to apply the shared selection rule to one other live Demand afterward. It
contains no Demand schema or lifecycle rule.

After `task_sys.close` persists and performs side cleanup, the tool submits this
frame only when the Task source is the actor `demand` collaboration source. A
submission failure is returned as explicit `completion_attention` failure while
the Task remains completed. It must not be converted to a false no-change
rejection.

### 3.5 Actor workflow contract

`buddyswitch/skills/shared/task-management/SKILL.md` remains the one installed
workflow owner. Extend its trigger/steps to cover `[DEMAND CHECK]` and
`task_sys.completion_frame`.

It must teach:

```text
Demand Check
  organize + complete_check
  -> list active Task
  -> create at most one from one exact current Demand revision

Task completion check
  -> read latest Demand
  -> complete with task_sys.task evidence OR keep live
  -> acknowledge a newly completed revision
  -> immediately apply the same at-most-one Task selection rule
```

Delete all IM Task frame/message disposition guidance. Do not create a second
Demand-management skill or copy this workflow into five role files. Role files
only list the available `task_sys__create` capability.

The Demand adapter prompt remains Demand-owned and contains no `task_sys` token.
Remove only the Phase 2 prohibition and keep its two-pass Demand check contract.

## 4. BUILD tasks

### Task 1: RED — canonical creation, replay, and single-active gate

**Files:**

- Create: `tests/integration/task_sys/test_actor_create.py`
- Modify: `tests/integration/task_sys/test_substrate.py`
- Modify: `tests/unit/task_sys/test_direct_input_retirement.py`

- [x] Add `test_actor_create_persists_exact_demand_snapshot_and_start_side`.
- [x] Add `test_exact_create_replay_returns_same_task_without_instruction`.
- [x] Add `test_same_demand_ref_with_changed_brief_rejects_without_write`.
- [x] Add `test_different_demand_ref_rejects_while_any_actor_task_is_active`.
- [x] Add `test_new_demand_revision_can_create_after_previous_task_is_terminal`.
- [x] Add `test_track_ingest_replay_is_idempotent`.
- [x] Add a process-concurrency case where two different Task sources race for
  one actor and exactly one creates; final active count is one and no partial
  Task file exists.
- [x] Replace any fixture that creates two simultaneous same-actor Tasks as
  supported behavior. Preserve synthetic projection tests only when they test
  classification of corrupt/external input, not creation behavior.

Run RED:

```bash
./buddyswitch-test focused \
  tests/integration/task_sys/test_actor_create.py \
  tests/integration/task_sys/test_substrate.py \
  tests/unit/task_sys/test_direct_input_retirement.py
```

Expected RED: `task_sys.create`, idempotent replay, active conflict, and creation
serialization are absent.

### Task 2: GREEN — implement one Task creation owner

**Files:**

- Modify: `scripts/env/domain/task_sys.py`
- Modify: `tools/launcher/task_sys_ingress.py`
- Modify: `tools/launcher/track_comment_added_handler.py`

- [x] Add exact DemandRef/brief normalization and targeted exceptions.
- [x] Add the actor-scoped creation lock.
- [x] Refactor `ingest` and actor `create` through one private create primitive.
- [x] Return `created|existing`, `state_changed`, and optional instruction from
  both callers.
- [x] Make Track ingress execute runtime only for `created`; an exact replay is
  handled without a duplicate side thread.
- [x] Let a different-source active conflict remain an explicit handler failure.
- [x] Do not add a queue, retry, alias, feature flag, or source-specific second
  write path.

Run GREEN and refactor while green:

```bash
./buddyswitch-test focused \
  tests/integration/task_sys/test_actor_create.py \
  tests/integration/task_sys/test_substrate.py \
  tests/integration/task_sys/test_side_processing.py \
  tests/unit/task_sys/test_direct_input_retirement.py
```

### Task 3: RED/GREEN — actor tool, authority, and actor ownership

**Files:**

- Modify: `scripts/env/tools/task_sys/tool.py`
- Modify: `scripts/env/tools/task_sys/_impl.py`
- Modify: `scripts/env/tool_runtime/role_auth.py`
- Modify: `scripts/env/tool_runtime/context.py`
- Modify: `tests/unit/env_tool/test_schema_contract.py`
- Modify: `tests/unit/env_tool/test_semantic_contract.py`
- Modify: `tests/unit/actor/test_role_action_auth.py`
- Modify: `tests/integration/env_tool/test_response_task.py`

- [x] Write schema assertions for exact nested fields, permission, free task
  requirement, writes/does-not-write, returns, and no aliases.
- [x] Add broker response cases for created, exact existing replay, active
  conflict, source conflict, and side runtime failure.
- [x] Add cross-actor `close` and `need_parent` cases that snapshot bytes and
  prove no mutation/runtime call.
- [x] Run the exact RED files.
- [x] Implement `task_sys.create`, add `task_sys.create` to common role
  permissions, and update runtime source/help descriptions.
- [x] Rename `_execute_parent_instruction` to the accurate
  `_execute_runtime_instruction`; update the one current caller directly and
  leave no alias.
- [x] Centralize actor-owned Task lookup in `_impl.py` and use it for `get`,
  `close`, `cancel`, and `need_parent`.
- [x] Run GREEN.

Commands:

```bash
./buddyswitch-test focused \
  tests/unit/env_tool/test_schema_contract.py \
  tests/unit/env_tool/test_semantic_contract.py \
  tests/unit/actor/test_role_action_auth.py \
  tests/integration/env_tool/test_response_task.py
```

### Task 4: RED/GREEN — Task completion receipt to parent Actor

**Files:**

- Modify: `scripts/env/domain/task_sys.py`
- Modify: `tools/launcher/task_sys_runtime.py`
- Modify: `scripts/env/tools/task_sys/_impl.py`
- Modify: `tests/unit/task_sys/test_runtime_executor.py`
- Modify: `tests/integration/task_sys/test_progress_check.py`
- Modify: `tests/integration/env_tool/test_response_task.py`

- [x] Add strict frame-render tests: Task id, safe DemandRef, completion result,
  already-terminal wording, source reconciliation, and no Demand schema/rules.
- [x] Add side-close and parent-close tests proving a Demand-sourced Task submits
  the completion frame after terminal persistence.
- [x] Add a non-Demand close case proving current Track/generic Tasks do not gain
  a Demand completion frame.
- [x] Add submit-failure proof: Task remains `completed`, no Demand state changes,
  and response exposes the failure.
- [x] Add replay proof: no new Task is created; duplicate completion attention is
  safe and bound to the same Task id.
- [x] Run RED.
- [x] Implement strict `completion_instruction`, frame renderer, and close-tool
  submission through existing TaskSysRuntimeAccess.
- [x] Do not add a daemon handler, mailbox command, trigger type, persisted
  ChangeSet, or Demand import.
- [x] Run GREEN.

Commands:

```bash
./buddyswitch-test focused \
  tests/unit/task_sys/test_runtime_executor.py \
  tests/integration/task_sys/test_progress_check.py \
  tests/integration/env_tool/test_response_task.py
```

### Task 5: RED/GREEN — Actor coordination guidance and Demand attention boundary

**Files:**

- Modify: `buddyswitch/skills/shared/task-management/SKILL.md`
- Modify: `tools/launcher/assets/roles/market/AGENTS.md`
- Modify: `tools/launcher/assets/roles/pm/AGENTS.md`
- Modify: `tools/launcher/assets/roles/design/AGENTS.md`
- Modify: `tools/launcher/assets/roles/dev/AGENTS.md`
- Modify: `tools/launcher/assets/roles/test/AGENTS.md`
- Modify: `tools/launcher/demand_sys_daemon_adapter.py`
- Modify: `tests/unit/architecture/test_task_management_skill.py`
- Modify: `tests/unit/demand_sys/test_daemon_adapter.py`
- Modify: `tests/unit/architecture/test_demand_sys_boundaries.py`

- [x] Change `TASK_SYS_OPERATIONS` expectations to include exactly `create` plus
  the five current actions.
- [x] Assert the skill owns Demand Check, create-at-most-one, completion
  reconciliation, latest revision, and Task evidence guidance.
- [x] Assert the skill contains no retired IM Task frame/message instructions,
  queue, scheduler, automatic completion, or copied payload table.
- [x] Assert every role lists `task_sys__create` but does not copy coordination
  steps.
- [x] Assert the Demand adapter prompt contains no `task_sys`, Task lifecycle, or
  Task selection token after removing the prohibition.
- [x] Run RED.
- [x] Update the existing skill, role capability lists, and fixed Demand prompt.
- [x] Run GREEN.

Commands:

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_task_management_skill.py \
  tests/unit/demand_sys/test_daemon_adapter.py \
  tests/unit/architecture/test_demand_sys_boundaries.py
```

### Task 6: RED/GREEN — safe external projection and residue deletion

**Files:**

- Modify: `scripts/env/domain/task_read.py`
- Modify: `tests/integration/im/test_external_query.py`
- Modify: `tests/unit/architecture/test_external_control.py`
- Modify: `tests/unit/architecture/test_task_management_skill.py`
- Modify: `tests/process/cli/test_env_layer_boundaries.py`
- Delete: `scripts/env/domain/tasks.py`

- [x] Add a safe `demand_ref` field to external Task projection: exact object for
  `source_type=demand`, otherwise `null`.
- [x] Prove list/get never expose arbitrary source refs, execution brief, events,
  runtime instruction, repository path, or Demand detail.
- [x] Delete `scripts/env/domain/tasks.py`; remove the allowlist entry that treats
  its retired publication fields as current.
- [x] Add negative scans for `env.domain.tasks`, `env.repos.tasks`, Taskbox-era
  fields, and retired IM Task guidance in live Task surfaces.
- [x] Run RED, implement, and run GREEN.

Commands:

```bash
./buddyswitch-test focused \
  tests/integration/im/test_external_query.py \
  tests/unit/architecture/test_external_control.py \
  tests/process/cli/test_env_layer_boundaries.py \
  tests/unit/architecture/test_task_management_skill.py
```

### Task 7: Current architecture documentation and machine boundaries

**Files:**

- Create: `docs/arch/task-sys-architecture.md`
- Modify: `docs/arch/demand-sys-architecture.md`
- Modify: `docs/arch/daemon-service-architecture.md`
- Modify: `tests/unit/architecture/test_demand_sys_boundaries.py`
- Create: `tests/unit/architecture/test_task_sys_boundaries.py`

- [x] Document Task Sys as owner of source idempotency, actor-scoped single
  active, five statuses, frames, completion receipt, and Task projections.
- [x] Document the Actor + installed skill as the only Demand/Task semantic
  composition boundary.
- [x] Replace the Phase 2 blanket statement `Task Sys -> Demand` with the exact
  current law: Task may persist/project an opaque DemandRef and return it to the
  Actor, but Task implementation may not import, read, validate against, call,
  subscribe to, or mutate Demand.
- [x] Keep generic daemon wording unchanged in meaning: transport and host
  mechanics only.
- [x] Add AST/source assertions for forbidden dependency direction and one
  actor-facing create action.
- [x] Do not turn historical memos into current policy or copy action schemas
  into architecture prose.

Run:

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_demand_sys_boundaries.py \
  tests/unit/architecture/test_task_sys_boundaries.py \
  tests/unit/architecture/test_task_management_skill.py
```

### Task 8: IMPACT verification and replacement audit

Run the focused owner/consumer batch in one invocation:

```bash
./buddyswitch-test focused \
  tests/integration/task_sys/test_actor_create.py \
  tests/integration/task_sys/test_substrate.py \
  tests/integration/task_sys/test_side_processing.py \
  tests/integration/task_sys/test_progress_check.py \
  tests/unit/task_sys/test_runtime_executor.py \
  tests/unit/task_sys/test_daemon_adapter.py \
  tests/unit/task_sys/test_direct_input_retirement.py \
  tests/unit/env_tool/test_schema_contract.py \
  tests/unit/env_tool/test_semantic_contract.py \
  tests/unit/env_tool/test_active_task_gate.py \
  tests/unit/actor/test_role_action_auth.py \
  tests/integration/env_tool/test_response_task.py \
  tests/integration/im/test_external_query.py \
  tests/unit/architecture/test_external_control.py \
  tests/process/cli/test_env_layer_boundaries.py \
  tests/unit/demand_sys/test_daemon_adapter.py \
  tests/unit/demand_sys/test_capture_and_check.py \
  tests/unit/demand_sys/test_organization.py \
  tests/unit/im/test_wake_handler.py \
  tests/unit/architecture/test_demand_sys_boundaries.py \
  tests/unit/architecture/test_task_sys_boundaries.py \
  tests/unit/architecture/test_task_management_skill.py
```

Run residue scans:

```bash
rg -uuu -n \
  'task_sys\.(start|begin)|task_sys__(start|begin)|env\.domain\.tasks|env\.repos\.tasks|For IM source frames|Do not create or modify Task Sys' \
  scripts tools buddyswitch tests docs/arch

rg -n \
  'from env\.domain import demand_sys|import env\.domain\.demand_sys|from env\.domain import task_sys|import env\.domain\.task_sys' \
  scripts/env/domain scripts/env/repos scripts/env/tools tools/launcher
```

Interpret the second scan by owner: ToolContext and product adapters may import
their own owner; Demand implementation may not import Task, Task implementation
may not import Demand, and generic daemon modules may import neither product.

Do not run `./buddyswitch-test full`; the user did not request repository-wide
acceptance.

### Task 9: Real BuddySwitch CLI / real Codex actor MILESTONE

**Environment:** default BuddySwitch product environment, not fake Codex.

**Safety:** snapshot existing instances first. Do not stop, delete, interrupt,
reset, or otherwise mutate pre-existing actors. Create one new PM actor, and
scope cleanup to that actor and any Web process started by this run. Do not run
`env reset` in the default environment.

- [x] Confirm the resolved runtime is the installed real Codex binary; reject
  `tests/support/fake_codex`, `BUDDYSWITCH_CODEX_BIN` overrides pointing into the
  repository, or a fake runtime receipt.
- [x] Capture `instance list`, existing instance ids, relevant pids/sockets, and
  git source identity before the run.
- [x] Start a fresh actor only through:

```bash
./buddyswitch-codex instance start --role pm
```

- [x] Start the public Web/IM surface on a free localhost port and create an
  external IM session.
- [x] Send two unrelated real IM messages back-to-back. Use bounded, read-only
  repository work that makes side scope hand off to parent, for example:

```text
A: Read the repository root AGENTS.md and report the first North Star priority.
B: Read buddyswitch/manifest.toml and report the exact configured role ids.
```

The messages must not tell the model exact tool payloads or manually correct it
afterward. The installed actor guidance must drive the behavior.

- [x] Poll public projections and record every observed active Task count:

```bash
./buddyswitch-codex demand list --actor <actor-id>
./buddyswitch-codex task list --actor <actor-id>
```

- [x] Wait for two terminal completed Demands and two terminal completed Tasks.
- [x] Read each exact public Task and Demand; then use owner reads only in the
  acceptance harness to prove details omitted by the public projection.
- [x] Assert:

```text
two IM messages -> exactly two intake keys -> exactly two Demands
each selected Demand revision -> exactly one Task DemandRef
max observed active_count == 1
canonical create outcomes and ordered runtime evidence show no second active Task
each Task lifecycle starts side_processing
parent-required work uses the same task id through awaiting_parent/parent_processing
each Task ends completed
each completed Demand evidence_refs contains its exact task_sys.task id
every final Demand checked_revision == revision
no third/checkpoint/replay Task exists
no Task imports/calls/mutations appear in Demand owner logs or state
```

- [x] Capture main-thread turns, Task side/parent frame evidence, completion
  frames, daemon trigger results, and Task runtime results.
- [x] Stop and delete only the newly created actor. Stop only the Web process
  started by this run.
- [x] Prove the new actor's app server, daemon, broker, side processes, sockets,
  and leases are gone. Prove all baseline instances are still present and their
  status was not changed.
- [x] Keep the resulting default-environment Demand/Task records as explicit
  production-style acceptance evidence; there is no scoped public purge action,
  and direct storage deletion or global reset is forbidden.

Implement the milestone as a one-shot here-document or temporary file outside
the repository. Do not add a permanent acceptance script. Use the accepted Phase
2 harness pattern for JSON CLI calls, external IM HTTP calls, bounded polling,
thread reads, process identity checks, and `finally` cleanup.

If real model behavior exposes a bug, stop claiming acceptance, record the exact
state/log evidence here, fix the owner through a new RED test, rerun the focused
batch, and repeat the milestone with a fresh actor. Do not add an
acceptance-specific prompt workaround.

## 5. REPLACE checklist

- [x] one actor action name: `task_sys.create`;
- [x] no start/begin/create alias or old payload;
- [x] `create` and current `ingest` share one creation primitive and lock;
- [x] no same-source duplicate Task path;
- [x] no second active-gate rule in tool, skill, handler, or daemon;
- [x] no Task operation in Demand adapter/domain;
- [x] no Demand operation in Task domain/runtime adapter;
- [x] no cross-owner callback, subscription, or shared transaction;
- [x] no retired IM Task skill text/tests;
- [x] no `scripts/env/domain/tasks.py` or missing-repository import;
- [x] no direct input intake;
- [x] no generic daemon product token or branch;
- [x] Track remains one explicit current path pending Phase 4, with no fallback
  or duplicate gate.

## 6. ACCEPT evidence record

Update this section during implementation. Do not mark an item complete without
source-bound output.

### RED

- status: passed as intentional pre-implementation and real-runtime failure proof
- run ids: `78bfcce9d48144c596cecf6c50bcdd03`,
  `7aacb682a5464ce28501458f43ba7289`,
  `89c6d4563e3b48d28867e817e5b44c74`,
  `c14362a40cfb42028bd37cbd04dc1ea1`,
  `b6a7a9704f014eb7bfd968adfa64b4d5`,
  `8f064dd9fd2341e6b1f68b725135acf1`,
  `9f0954f2eda9456cb628fa6ec96267c0`,
  `12bd8204d2b245dd999ea20abb4b8721`, and
  `1acb9535b99d43128a31577582f11a1`
- exact missing behavior: canonical create/gate, actor action/authority,
  completion attention, actor workflow, safe projection, architecture laws,
  exact completion evidence, immediate next-Demand selection, and an
  unambiguous side filesystem boundary were each absent before their owner
  change.

### GREEN / focused owner proof

- status: passed
- run ids: `2aa5d6e520fa4e3aaeece67fa70e4407`,
  `4c95169b1c974944a840792a324b3a8b`,
  `83a38cae018a4d13b8e293902549cc3b`,
  `06d60063d58e4320b13ca545cfc3ff8f`,
  `68d58b88c86146f99f7e7affecc817c8`,
  `c6766f43ea794e2ea0bc792bc0d59948`,
  `3b572b08081249dba1256e033f34dfd0`,
  `06f05f0825594568a8c93a12619f0671`, and
  `3d01b236d77f4a2d902bff33886ee021`
- result: all direct domain, tool, runtime, workflow, projection, ownership,
  cleanup, and architecture proofs passed through the public focused runner.

### IMPACT batch

- status: final candidate passed
- final run ids: `b0484664a3c14db1aa9d67a699aee9c7` and
  `15f9054c0bfd47fbb65417fa0842920a`
- earlier post-fix run ids: `12d4f901b1f24f948ea066e828ad773c`
  and `74ddf041f5f74987a317c338b44ad78a`
- result: 226 tests / 987 subtests plus the separately collected Demand daemon
  adapter 4 tests / 3 subtests passed. The split avoids pytest's two-module
  basename collision and does not change product evidence.

### Replacement scan

- status: passed
- result: no live `start`/`begin` aliases, retired Task domain import, retired
  IM Task workflow, Demand-to-Task implementation dependency, Task-to-Demand
  implementation dependency, or generic-daemon product branch. Matches are
  limited to scoped negative assertions proving absence.

### Real actor MILESTONE

- status: passed
- accepted actor/thread: `act-pm-3b2dfa3ee76c` /
  `019f7ebc-9993-7bc2-86db-055cce088060`
- Codex runtime identity: `/Users/chen/.npm-global/bin/codex`, installed
  `codex-cli 0.144.6`; actor descriptor resolved the installed package runtime,
  with no fake or repository override.
- Demand ids/revisions: `demand-2e8dc098280c` and
  `demand-eda014efbf8d`; both terminal `completed` at revision 2 with
  `checked_revision=2`.
- Task ids/lifecycles: `task-demand-be3b94669d46` and
  `task-demand-48a959b3afc9`; each recorded `created`, `side_frame_started`,
  `side_parent_requested`, `parent_handoff_started`, `side_cleanup_recorded`,
  and `closed`, with a parent completion result.
- maximum active count: `1`, sampled across both sequential loops.
- completion evidence: each Demand stores one exact
  `{"type":"task_sys.task","ref":{"task_id":...}}` reference to its matching
  Task; main thread observed two parent frames and two completion frames.
- real-run findings: `act-pm-8037d787b1ef` exposed guessed `ref.id` evidence and
  deferred next selection; `act-pm-87203d2a476c` proved their fix and exposed
  the contradictory side read boundary; `act-pm-f0f7adb52288` proved the new
  handoff boundary but correctly canceled an invalid source path. Each finding
  was corrected at the owning contract or acceptance input, never by steering
  the running actor.
- cleanup evidence: accepted actor, App Server, instance daemon, runtime broker,
  side leases, Web process, sockets, and temporary root were absent after scoped
  stop/delete; failed probes were cleaned to the same standard.
- pre-existing instance preservation: `act-market-645c3ea1fe37` and
  `act-market-8164b055c113` remained present with the same status, health, and
  thread ids. No default-environment reset or direct runtime-state deletion was
  used.

## 7. Definition of done

Phase 3 is complete only when:

1. `task_sys.create` is the only actor Task creation action;
2. all Task sources share one idempotent, actor-serialized, single-active owner;
3. the existing side-first lifecycle remains the only lifecycle;
4. Task completion produces Actor attention but never mutates Demand;
5. Actor rereads latest Demand and explicitly completes or keeps it live;
6. Task mutation actions enforce actor ownership;
7. Demand and Task implementations have no cross-domain imports/calls;
8. generic daemon code remains product-neutral;
9. retired Task source/guidance and aliases are absent;
10. focused automated evidence passes through `./buddyswitch-test`;
11. a fresh real CLI-created actor and real Codex runtime prove two sequential
    Demand-to-Task loops with maximum active count one;
12. new runtime resources are cleaned while unrelated actors and work remain
    untouched;
13. this memo records exact evidence and is committed only with the completed
    implementation.
