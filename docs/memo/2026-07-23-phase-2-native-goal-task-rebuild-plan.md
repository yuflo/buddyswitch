# Phase 2 / Stage 2 — Native Goal Task Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans` to execute this plan block by block. Use `superpowers:test-driven-development` for every executable behavior change, `buddyswitch-testing` for all test selection and evidence, and `superpowers:verification-before-completion` before any completion claim.

**Status:** implementation and Phase 2 verification completed on 2026-07-23;
awaiting explicit user acceptance before any Phase 3 work.

**Phase boundary:** Phase 1 / Stage 1 is complete. This document is the complete plan for Phase 2 / Stage 2. The sections below are execution blocks inside one stage, not additional product stages or runtime modes.

**Goal:** replace BuddySwitch Task side/parent execution with one minimal Demand-bound Task and one Codex native Goal on the Actor main thread, then reconcile Goal completion back into Task and Demand orchestration through a separate parent turn.

**Architecture:** Demand triage remains entirely isolated-side. Task becomes a small canonical binding/result owner. Codex Goal becomes the only Task continuation loop. A product-owned Task–Goal handler maps native Goal state to Task state. A separate Demand orchestration handler reconciles terminal work and chooses the next live Demand. Daemon service supplies only generic process, notification, command, scheduling, and reconciliation capabilities.

**Primary technology:** Python domain/tool/launcher code, Codex App Server Goal protocol, BuddySwitch daemon handlers, shared runtime Skills, focused unit/integration/system tests, and one isolated real Web/Actor acceptance loop.

---

## 1. Authority and non-negotiable boundary

This plan is subordinate to:

1. root `AGENTS.md` and its Sharp Forward rules;
2. `docs/memo/2026-07-23-demand-ingress-goal-rebuild.md`;
3. the confirmed architecture captured in `docs/memo/2026-07-22-demand-goal-mode-forward-architecture.html`;
4. the repository's current executable contracts discovered before implementation.

Phase 2 is a direct rebuild, not a compatibility migration:

- no feature flag selecting Task frames versus Goal mode;
- no legacy Task reader or translator;
- no dual Task schema, dual write, fallback read, or compatibility alias;
- no Task side thread, parent handoff, outcome frame, Progress Check, lease, or processor state;
- no `task_sys.close` or `task_sys.need_parent`;
- no current Skill, role guidance, tool help, Web projection, architecture document, or active test teaching the retired model;
- old runtime data is not migrated during this stage; acceptance uses an isolated clean shared root;
- destructive rebuilding of the user's default shared state remains a separately authorized Phase 3 operation.

Commits may checkpoint coherent work. They do not create supported intermediate runtime modes. Phase 2 is accepted only after the whole current product path has one architecture.

## 2. The thread model — no `need_parent`

The target contains three deliberately separate activities:

```text
Inbound fact
  → isolated demand-triage side
  → Demand-owned atomic apply
  → live Demand pool

Idle pool attention
  → independent parent turn on the Actor main thread
  → reconcile latest terminal Task against its Demand
  → select exactly one live Demand when the Task slot is empty
  → create one minimal Task

Active Task
  → one native Goal on the same Actor main thread
  → Codex Goal continuation
  → Goal terminal observation
  → Task terminal record
  → new independent parent orchestration turn
```

The following interpretation is mandatory:

- Demand intake judgment is always completed in isolated side.
- Demand triage has no `needs_parent_judgment` result and no parent escalation.
- Task execution does not start or resume a side thread.
- Goal work runs on the Actor's existing main thread.
- Demand reconciliation runs in a later independent turn on that main thread.
- A later parent turn is scheduling context, not a `need_parent` transition.
- `need_parent` may appear only in this memo's retired-path inventory, deletion steps, negative assertions, or historical memos.

The remaining live `task_sys.need_parent` code exists only because Phase 1 deliberately left the old Task executor untouched. Removing it is part of this Phase 2 cutover.

## 3. FRAME

### 3.1 Exact bottleneck

BuddySwitch currently owns a second execution engine around Task:

- Task side threads perform work;
- Task states encode side/parent handoff;
- `task_sys.need_parent` escalates from side to parent;
- Task Progress Check attempts to continue incomplete work;
- outcome frames return terminal information to the parent;
- Task Skills, role prompts, tools, daemon adapters, projections, and tests preserve this engine.

This duplicates responsibility already owned more robustly by Codex native Goal continuation. It also leaves Demand orchestration coupled to Task frame completion and keeps message delivery dependent on a fragile frame handoff path.

### 3.2 Observable acceptance sentence

> From an isolated clean BuddySwitch root, a user can create a real Web Actor, send one request that becomes a Demand, observe exactly one minimal Task bind to exactly one native active Goal on the Actor main thread, receive the requested result after native Goal continuation, and observe a later independent parent turn reconcile the Task against the latest Demand—with no Task side/parent frame, `need_parent`, Progress Check, outcome frame, or second unfinished Task anywhere in the live path.

### 3.3 Consumer path

```text
Web message
  → Phase 1 Demand triage owner
  → canonical live Demand
  → DemandOrchestrationHandler parent attention
  → task_sys.create
  → Task owner
  → task_goal.reconcile application command
  → TaskGoalHandler
  → Codex App Server thread/goal/set
  → native Goal continuation on Actor main thread
  → thread/goal/updated or goal/get recovery
  → Task owner terminal transition
  → DemandOrchestrationHandler independent parent attention
  → Demand reconciliation and next selection
  → readable Web message delivery
```

## 4. Scope

### 4.1 In scope

- prove the installed Codex native Goal contract at the real App Server boundary;
- replace the Task canonical schema and state machine;
- reduce Actor-facing Task tools to `list`, `get`, `create`, and `cancel`;
- bind Task creation/cancellation to native Goal set/get/clear;
- recover Task–Goal convergence after process interruption or missed notification;
- map only matching Goal `complete` to Task `completed`;
- keep paused, blocked, usage-limited, and budget-limited Goals attached to the same active Task;
- split Demand ingress triage from Demand orchestration;
- trigger a separate parent turn after Task terminal persistence;
- update active Task gating, role authority, Skills, projections, Web consumers, and current architecture docs;
- delete every retired Task execution path and active test that preserves it;
- execute focused automated verification;
- perform one real isolated Web/Actor acceptance scenario and clean all created resources;
- stop for user review before Phase 3.

### 4.2 Explicitly out of scope

- more than one active Task;
- one Task binding multiple Demands;
- one Demand split across multiple concurrent Tasks;
- multi-thread Actor instances or parallel Goals;
- autonomous Goal prioritization across multiple tasks;
- the full four-question Market research scenario;
- the full Dev self-demand scenario;
- the daemon-offline acceptance matrix;
- destructive rebuilding of the user's default BuddySwitch state;
- a migration reader for retired Task records;
- broad Web/CLI error-product hardening for arbitrary malformed historical data;
- Phase 3 implementation.

The full Market, Dev, outage, default-root rebuild, and broad Web/CLI acceptance matrix remains Phase 3. Phase 2 still requires a narrow real Web/Actor product loop; automated component tests alone cannot satisfy its acceptance sentence.

## 5. TRACE — verified current repository facts

| Area | Current fact | Phase 2 consequence |
|---|---|---|
| Task owner | `scripts/env/domain/task_sys.py` owns side-processing, awaiting-parent, parent-processing, completed, and canceled states | replace with one minimal Task schema and three states |
| Actor Task tools | `scripts/env/tools/task_sys/tool.py` exposes create/list/get/close/cancel/need_parent | expose only list/get/create/cancel |
| Task execution | `tools/launcher/task_sys_runtime.py` renders side, parent, outcome, and Progress Check prompts | delete the executor |
| Daemon adapter | `tools/launcher/task_sys_daemon_adapter.py` binds old Task commands and progress handling | delete and replace with Task–Goal product handler |
| Runtime bridge | `task_sys_runtime_client.py`, `task_sys_runtime_protocol.py`, and `TaskSysRuntimeAccess` carry frame commands | replace with one small Task–Goal reconcile command |
| Demand handler | `tools/launcher/demand_triage_handler.py` currently mixes ingress triage and pool orchestration | keep triage responsibility; move orchestration to its own owner |
| Goal client | `tools/launcher/app_server.py` already wraps goal get/set/clear | retain as App Server adapter; strengthen exact protocol tests |
| Goal runtime | installed `codex-cli 0.144.6` reports `goals stable true` | real runtime proof is possible and is the first hard gate |
| Goal contract | Codex App Server persists Goal on a materialized thread and emits updated/cleared notifications | bind only to the persistent Actor main thread |
| Goal statuses | active, paused, blocked, usageLimited, budgetLimited, complete | only complete terminates Task successfully |
| Daemon core | generic source handlers, app commands, polling reconciliation, parent activity, and input submission already exist | do not add Demand/Task/Goal semantics to daemon core |
| Active-task gate | tool registry currently anchors mutations to an active Task but teaches frame recovery | retain Task as authority anchor; replace its wording and state assumptions |
| Role guidance | every active role AGENTS file teaches close/need_parent and Task side frames | update all roles in the same cutover |
| Projections | Task read/Web UI expose recoverable frame-oriented Task concepts | replace current projections now; do not defer live residue |
| Current docs | Task, Demand, daemon, and Web architecture docs still teach old Task frames | rewrite affected current architecture docs |
| System harness | existing launcher system helper uses fake Codex | add a focused real-Codex Goal harness with deterministic local model responses |

### 5.1 Corrected scope discovered by code audit

The earlier overall memo placed most Web/CLI projection work in Phase 3. The code audit shows that `recoverable_tasks`, frame statuses, and frame actions are live consumers of the retired Task schema. Leaving them active would violate Forward-Only REBUILD.

Therefore Phase 2 must update the live Task projection and its direct Web/CLI consumers enough to represent the minimal current Task model. Phase 3 still owns:

- explicit `REBUILD_REQUIRED` handling for historical/malformed default-state records;
- destructive default-root cleanup after fresh authorization;
- the broad end-to-end Market/Dev/outage matrix.

This is not Phase 3 work pulled forward. It is required residue removal for the Phase 2 replacement claim.

## 6. Target semantic ownership

| Rule or state | Sole owner |
|---|---|
| inbound receipt and isolated side recovery | `DemandTriageHandler` plus Demand receipt owner |
| Demand create/revise/merge/cancel validation and mutation | Demand domain |
| canonical Task record and one-active-Task invariant | Task domain |
| Task Actor intent contract | Task tool |
| Goal protocol calls | App Server adapter |
| Task ↔ Goal convergence and terminal mapping | `TaskGoalHandler` |
| terminal Demand reconciliation and next Demand selection | `DemandOrchestrationHandler` plus `$demand-orchestration` |
| process lifecycle, notification delivery, command transport, polling | daemon core |
| composition of concrete product handlers | `instance_daemon.py` |
| continuation of one Task objective | Codex native Goal |

Dependencies follow:

```text
Task/Demand domains
        ↑
product operations and contracts
        ↑
TaskGoalHandler / DemandOrchestrationHandler
        ↑
instance_daemon composition
        ↓
generic daemon and App Server adapters
```

Daemon core must not import Task, Demand, Goal, Skill, or selection semantics. `instance_daemon.py` may know concrete handlers because it is the composition root.

## 7. Exact target contracts

### 7.1 Canonical Task record

The only accepted live Task shape is:

```json
{
  "schema_version": 1,
  "id": "task-...",
  "actor_target": {
    "actor_id": "...",
    "role_id": "..."
  },
  "demand_ref": {
    "demand_id": "demand-...",
    "basis_revision": 7,
    "demand_ref": "dref-..."
  },
  "objective": "A self-contained Task completion objective.",
  "selection": {
    "reason": "Why this Demand is the next work item.",
    "selected_at": "2026-07-23T..."
  },
  "goal_binding": null,
  "status": "active",
  "result": null,
  "created_at": "2026-07-23T...",
  "updated_at": "2026-07-23T..."
}
```

After binding, `goal_binding` is:

```json
{
  "thread_id": "persistent-main-thread-id",
  "objective_hash": "sha256:...",
  "goal_created_at": 178...
}
```

Successful terminal `result` is host-authored:

```json
{
  "type": "goal_terminal",
  "goal_status": "complete",
  "thread_id": "persistent-main-thread-id",
  "objective_hash": "sha256:...",
  "goal_created_at": 178...,
  "goal_updated_at": 178...,
  "token_budget": null,
  "tokens_used": 1234,
  "time_used_seconds": 42,
  "recorded_at": "2026-07-23T..."
}
```

Canceled `result` is:

```json
{
  "type": "actor_canceled",
  "reason": "Explicit cancellation reason.",
  "recorded_at": "2026-07-23T..."
}
```

Rules:

- statuses are exactly `active`, `completed`, and `canceled`;
- `goal_binding` may be null only during the recoverable Task-write → Goal-set window;
- Actor inputs never include `basis_revision`, storage paths, hashes, thread IDs, timestamps, or result snapshots;
- Task owner resolves the opaque Demand ref and records its current basis revision;
- no events array, execution object, source type, inbound context, processor, lease, frame, handoff, progress, or recoverable-task field exists;
- a retired record is rejected; it is never translated.

### 7.2 Actor-facing Task tool

The complete Actor action set is:

| Action | Actor intent | Required Actor input |
|---|---|---|
| `list` | inspect active or terminal Tasks | `status: active|terminal|all` |
| `get` | inspect one Task | `task_id` |
| `create` | bind one selected live Demand to one objective | `demand_ref`, `objective`, `selection_reason` |
| `cancel` | explicitly stop the current Task | `task_id`, `reason` |

There is no Actor `complete` action. The Actor finishes work by calling the native Goal `update_goal(status=complete)`. There is no Actor Task outcome payload and no Actor Demand disposition inside Goal work.

There is no `close`, `need_parent`, side cleanup, handoff, interrupt parameter, frame instruction, or recoverable filter.

### 7.3 One-active-Task invariant

- An Actor instance has at most one `active` Task.
- Creating while any Task is active returns that existing conflict and writes nothing.
- Matching retry after Task write but before Goal binding returns the same Task and requests convergence; it does not create a second record.
- A terminal Task does not block a later Task.
- Blocked, paused, usage-limited, or budget-limited Goal leaves its Task active and blocks selection of a new Task.

### 7.4 Task creation handshake

The only live handshake is:

```text
1. Task owner validates opaque Demand ref and one-active invariant.
2. Task owner atomically writes active Task with goal_binding = null.
3. Task tool calls TaskGoalRuntimeAccess.reconcile_task(task_id).
4. Thin runtime client sends task_goal.reconcile_task to the instance daemon.
5. TaskGoalHandler rereads canonical Task and persistent Actor main-thread identity.
6. Handler obtains native Goal state.
7. No Goal: set one active Goal with the exact Task objective.
8. Matching Goal: bind the existing Goal.
9. Matching complete Goal: bind and complete Task atomically.
10. Handler persists exact binding/result through Task owner.
```

If step 3–9 fails:

- do not roll back or delete the Task;
- do not start a Task frame;
- do not fall back to direct parent execution;
- return the durable active Task with explicit reconciliation-pending information;
- daemon startup/poll reconciliation retries from canonical Task and native `goal/get`.

### 7.5 Goal ownership and conflicts

BuddySwitch is the sole initiator of native Goals used for Task execution:

- orchestration creates Task;
- TaskGoalHandler sets the matching Goal;
- Goal work may use native `get_goal` and `update_goal`;
- role/Skill guidance must not ask the Actor to call `create_goal` for Task work.

An unfinished native Goal with no matching active Task, or a mismatched unfinished Goal, is an invariant conflict:

- do not overwrite it;
- do not clear it silently;
- do not create a second Task/Goal;
- expose a precise conflict in handler/tool telemetry;
- keep Demand orchestration deferred until the conflict is resolved.

This protects one current execution slot without inventing adoption or migration behavior.

### 7.6 Goal status mapping

| Native Goal observation | Task effect | Scheduling effect |
|---|---|---|
| `active` | remain active | no new Task |
| `paused` | remain active | no new Task |
| `blocked` | remain active | no new Task |
| `usageLimited` | remain active | no new Task |
| `budgetLimited` | remain active | no new Task |
| matching `complete` | exactly-once transition to completed | durable orchestration attention |
| matching Goal cleared/missing after binding | transition Task to canceled with host reason | durable orchestration attention |
| duplicate complete notification | no second state transition | no duplicate durable attention |
| stale/mismatched notification | no mutation; record diagnostic | no scheduling |

Only a matching Goal on the bound persistent main thread with the exact objective hash can complete a Task.

### 7.7 Task cancellation

Cancellation is decoupled from Demand:

```text
task_sys.cancel
  → Task owner records canceled
  → task_goal.reconcile_task
  → TaskGoalHandler clears only the matching Goal
  → orchestration attention
  → later parent turn decides the Demand
```

If clearing fails, terminal Task state remains canonical and startup/poll reconciliation retries Goal clear. Demand remains unchanged.

### 7.8 Demand orchestration

`DemandOrchestrationHandler` owns when to request parent attention. `$demand-orchestration` owns the Actor judgment inside that turn.

At each independent parent turn:

1. reread any newly terminal Task;
2. reread that Task's latest Demand;
3. explicitly complete, cancel, revise, or keep the Demand live;
4. list active Tasks;
5. if one exists, stop;
6. list all live Demands;
7. if none exists, stop and persist observed attention;
8. if one or more exist, select exactly one by current judgment;
9. reread the selected Demand;
10. call `task_sys.create` with opaque `demand_ref`, self-contained objective, and selection reason.

When the Task slot is empty and live Demands exist, choosing none is not a supported steady-state outcome. Blocked work belongs to the selected Goal state, not to an unscheduled live pool.

The Task objective must:

- define an observable completion result;
- include user-facing delivery when the originating work requires it;
- require native `update_goal(complete)` only after that result is delivered;
- prohibit automatic Demand completion or next-Demand selection inside Goal work.

### 7.9 Attention and recovery semantics

- App Server notification is acceleration, not recovery truth.
- `goal/get`, canonical Task state, and canonical Demand state are recovery truth.
- Task terminal persistence happens before orchestration attention.
- `DemandOrchestrationHandler.reconcile()` recomputes pending attention on daemon startup and periodic generic reconciliation.
- A direct product callback from `TaskGoalHandler` may accelerate `DemandOrchestrationHandler` only after terminal persistence.
- Duplicate notifications and repeated reconciliation must converge on one Task transition and one durable pending attention key.
- A process crash may cause a later repeated parent turn after restart; that turn must reread one-active Task and current Demand state, making it harmless.
- Do not claim cross-process exactly-once parent-turn submission without an atomic external queue contract.

## 8. Target component layout

### 8.1 Create

- `tools/launcher/task_goal_handler.py`
- `tools/launcher/demand_orchestration_handler.py`
- `scripts/env/tool_runtime/task_goal_runtime_protocol.py`
- `scripts/env/tool_runtime/task_goal_runtime_client.py`
- `tests/system/goal_mode/support.py`
- `tests/system/goal_mode/test_native_goal_contract.py`
- `tests/system/goal_mode/test_product_flow.py`
- `tests/integration/goal_mode/test_task_goal_reconciliation.py`
- `tests/integration/goal_mode/test_demand_orchestration.py`
- `tests/integration/task_sys/test_goal_binding.py`

### 8.2 Replace or materially rewrite

- `scripts/env/domain/task_sys.py`
- `scripts/env/domain/task_read.py`
- `scripts/env/tools/task_sys/tool.py`
- `scripts/env/tools/task_sys/_impl.py`
- `tools/launcher/demand_triage_handler.py`
- `tools/launcher/instance_daemon.py`
- `buddyswitch/skills/shared/demand-orchestration/SKILL.md`
- `docs/arch/task-sys-architecture.md`
- affected Task projections in `tools/launcher/assets/web-management/app.js`

### 8.3 Modify direct consumers

- `scripts/env/tool_runtime/context.py`
- `scripts/env/tool_runtime/role_auth.py`
- `scripts/env/tool_runtime/registry.py`
- `scripts/env/tools/context/_impl.py`
- `scripts/env/tools/message/tool.py`
- `tools/launcher/app_server.py`
- `tools/launcher/assets/roles/market/AGENTS.md`
- `tools/launcher/assets/roles/pm/AGENTS.md`
- `tools/launcher/assets/roles/dev/AGENTS.md`
- `tools/launcher/assets/roles/design/AGENTS.md`
- `tools/launcher/assets/roles/test/AGENTS.md`
- `buddyswitch/manifest.toml`
- `docs/arch/demand-sys-architecture.md`
- `docs/arch/daemon-service-architecture.md`
- `docs/arch/web-interface-call-architecture.md`
- all tests directly asserting Task actions, states, schema, projections, permissions, Skills, or daemon composition

### 8.4 Delete

- `tools/launcher/task_sys_runtime.py`
- `tools/launcher/task_sys_daemon_adapter.py`
- `scripts/env/tool_runtime/task_sys_runtime_client.py`
- `scripts/env/tool_runtime/task_sys_runtime_protocol.py`
- `buddyswitch/skills/shared/task-management/SKILL.md`
- old Task frame/progress/side-processing tests after their replacement proofs exist

Deletion is required in the same Phase 2 change. Renaming old modules behind a Goal facade is not acceptable.

## 9. PROVE and BUILD — six coherent execution blocks

These are implementation blocks within Phase 2, not separately releasable product stages. Each block starts RED, becomes GREEN, and records source-bound evidence before the next block.

### Block A — prove the real native Goal boundary

**Claim:** the installed, runtime-selected Codex can persist and continue an active Goal on a materialized thread, report terminal/stopped state, and recover it through `goal/get`.

**Files:**

- Modify: `tests/integration/app_server/test_client.py`
- Create: `tests/system/goal_mode/support.py`
- Create: `tests/system/goal_mode/test_native_goal_contract.py`
- Modify only to satisfy exact protocol defects: `tools/launcher/app_server.py`

**RED:**

- [ ] Add exact wrapper tests for camelCase request payloads and returned Goal snapshots for get/set/clear.
- [ ] Add a system helper that resolves the installed runtime through `codex_runtime.resolve_codex_runtime()`.
- [ ] Start a deterministic local mock Responses endpoint under the system resource ledger.
- [ ] Create a temporary `CODEX_HOME` with Goals enabled and the model provider pointing at that endpoint.
- [ ] Materialize one persistent App Server thread.
- [ ] Prove `thread/goal/set(status=active)` starts Goal work.
- [ ] Make the first model response end without completion; prove native Goal continuation begins another turn.
- [ ] Make the next response call native `update_goal(status=complete)`; prove the ordered Goal update reports `complete`.
- [ ] Disconnect/reconnect the observer and prove `goal/get` returns the persisted complete snapshot.
- [ ] Drive one model/turn failure; prove the Goal becomes a stopped non-complete status and remains queryable.
- [ ] Prove clear removes the Goal and emits/returns the exact clear contract.
- [ ] Prove all process, socket, temporary-home, and mock-server resources are registered and cleaned.

Run:

```bash
./buddyswitch-test focused \
  tests/integration/app_server/test_client.py \
  tests/system/goal_mode/test_native_goal_contract.py
```

Expected RED: missing exact tests/helper behavior, or an exposed real runtime mismatch.

Expected GREEN: actual installed Codex—not a fake launcher—proves active continuation, complete notification, stopped state, query recovery, and clear.

**Hard stop:** if this real contract cannot be proved, stop Phase 2 before changing Task owner. Report the exact Codex/App Server capability gap. Do not create a BuddySwitch fallback executor.

### Block B — replace Task owner and Actor contract

**Claim:** one live Demand can create one minimal active Task, and every Task mutation uses the new schema and one-active invariant.

**Files:**

- Replace: `scripts/env/domain/task_sys.py`
- Rewrite: `scripts/env/domain/task_read.py`
- Rewrite: `scripts/env/tools/task_sys/tool.py`
- Rewrite: `scripts/env/tools/task_sys/_impl.py`
- Create: `scripts/env/tool_runtime/task_goal_runtime_protocol.py`
- Create: `scripts/env/tool_runtime/task_goal_runtime_client.py`
- Modify: `scripts/env/tool_runtime/context.py`
- Create: `tests/integration/task_sys/test_goal_binding.py`
- Replace: `tests/integration/task_sys/test_actor_create.py`
- Replace: `tests/integration/task_sys/test_substrate.py`
- Replace: `tests/integration/env_tool/test_response_task.py`
- Modify: `tests/integration/env_tool/test_context_binding.py`
- Modify: `tests/integration/env_tool/test_payload_contract.py`
- Modify: `tests/unit/architecture/test_task_sys_boundaries.py`
- Modify: `tests/unit/architecture/test_tool_runtime_contract.py`

**RED:**

- [ ] Assert exact Task record keys and exact status enum.
- [ ] Assert any old frame-shaped record is rejected, not projected or translated.
- [ ] Assert Actor action set is exactly `{list,get,create,cancel}`.
- [ ] Assert create accepts only opaque `demand_ref`, `objective`, and `selection_reason`.
- [ ] Assert Actor cannot provide revision, thread, hash, timestamps, binding, or result.
- [ ] Assert Task owner resolves the current Demand and records its basis revision.
- [ ] Assert one-active-Task conflict writes nothing.
- [ ] Assert matching retry returns the same unbound active Task.
- [ ] Assert cancel records terminal Task while leaving Demand unchanged.
- [ ] Assert Task result can be written only through a host-owned Goal terminal operation.
- [ ] Assert the runtime protocol contains one product command: `task_goal.reconcile_task`.

**GREEN:**

- [ ] Implement the new Task record and atomic owner operations.
- [ ] Implement the four Actor actions.
- [ ] Implement the thin TaskGoal runtime access/client.
- [ ] Remove Task execution instructions from tool responses.
- [ ] Keep active Task as the authority anchor for Task-bound product tools.
- [ ] Replace `recoverable` projection concepts with current active/terminal projection.

Run:

```bash
./buddyswitch-test focused \
  tests/integration/task_sys/test_goal_binding.py \
  tests/integration/task_sys/test_actor_create.py \
  tests/integration/task_sys/test_substrate.py \
  tests/integration/env_tool/test_response_task.py \
  tests/integration/env_tool/test_context_binding.py \
  tests/integration/env_tool/test_payload_contract.py \
  tests/unit/architecture/test_task_sys_boundaries.py \
  tests/unit/architecture/test_tool_runtime_contract.py
```

Expected GREEN: all Task state is minimal, one-active, Demand-bound, and contains no execution engine.

### Block C — bind native Goal and recover convergence

**Claim:** every active Task converges with exactly one matching native Goal, and only a matching terminal Goal mutates Task.

**Files:**

- Create: `tools/launcher/task_goal_handler.py`
- Modify: `tools/launcher/instance_daemon.py`
- Modify: `tools/launcher/app_server.py` only for exact adapter corrections proved in Block A/C
- Create: `tests/integration/goal_mode/test_task_goal_reconciliation.py`
- Modify: `tests/unit/daemon/test_instance_entrypoint.py`
- Modify: `tests/unit/env_tool/test_active_task_gate.py`

**RED:**

- [ ] Active unbound Task + no Goal → set Goal and persist binding.
- [ ] Active unbound Task + matching Goal → bind without setting a second Goal.
- [ ] Active unbound Task + already-complete matching Goal → bind and complete once.
- [ ] Bound active Task + active/paused/blocked/limited Goal → remain active.
- [ ] Bound active Task + matching complete Goal → store exact host snapshot once.
- [ ] Duplicate complete notification + startup reconciliation → no duplicate transition.
- [ ] Bound Task + cleared/missing Goal → cancel once.
- [ ] Canceled Task + matching Goal → clear the Goal; retry after failure converges.
- [ ] Unbound or mismatched unfinished Goal → explicit conflict, no overwrite, no second Task.
- [ ] Stale or wrong-thread notification → no mutation.
- [ ] Goal terminal while daemon is down → startup `goal/get` reconciliation repairs Task.
- [ ] Generic daemon code contains no Task, Demand, Goal, or selection import/branch.

**GREEN:**

- [ ] Implement `TaskGoalHandler` as the sole Task–Goal semantic adapter.
- [ ] Register its application command and source notifications at `instance_daemon.py`.
- [ ] Use notification for acceleration and `goal/get` for recovery.
- [ ] Persist Task before Goal set and terminal Task before downstream attention.
- [ ] Return explicit convergence/conflict telemetry to the Task tool.
- [ ] Update active-task gate wording for active Goal-bound Task; remove frame recovery advice.

Run:

```bash
./buddyswitch-test focused \
  tests/integration/goal_mode/test_task_goal_reconciliation.py \
  tests/unit/daemon/test_instance_entrypoint.py \
  tests/unit/env_tool/test_active_task_gate.py
```

Expected GREEN: Task and Goal converge across every named crash window without a fallback executor.

### Block D — split orchestration and start a separate parent turn

**Claim:** Goal terminal state produces durable Demand attention, and a later parent turn—not the Goal-completing turn—reconciles the Demand and fills an empty Task slot.

**Files:**

- Create: `tools/launcher/demand_orchestration_handler.py`
- Narrow: `tools/launcher/demand_triage_handler.py`
- Modify: `tools/launcher/instance_daemon.py`
- Rewrite: `buddyswitch/skills/shared/demand-orchestration/SKILL.md`
- Modify: `buddyswitch/manifest.toml`
- Create: `tests/integration/goal_mode/test_demand_orchestration.py`
- Modify: `tests/integration/demand_sys/test_side_triage_flow.py`
- Modify: `tests/unit/architecture/test_task_management_skill.py`
- Modify: `tests/unit/actor/test_runtime_skills.py`

**RED:**

- [ ] `DemandTriageHandler` imports/owns no Task selection or Goal terminal rule.
- [ ] Inbound triage completes in side with no `needs_parent_judgment`.
- [ ] Matching Task terminal state creates durable orchestration attention.
- [ ] Demand is unchanged until an independent parent turn runs.
- [ ] Parent-busy state defers submission without losing attention.
- [ ] Active Task defers selection.
- [ ] Empty Task slot + zero live Demands records consumed attention and creates nothing.
- [ ] Empty Task slot + one or more live Demands requires exactly one selection.
- [ ] Task create records the selection reason.
- [ ] Duplicate/restart reconciliation converges by rereading current Demand/Task truth.
- [ ] Actor-created Demand attention follows the same orchestration owner.
- [ ] `$demand-orchestration` owns terminal reconciliation and selection.
- [ ] No active Skill teaches `$task-management`, frame execution, `need_parent`, or outcome frames.

**GREEN:**

- [ ] Move orchestration prompt, pool revision, Task terminal attention, and parent submission out of `DemandTriageHandler`.
- [ ] Implement `DemandOrchestrationHandler.reconcile()` over canonical Task/Demand truth.
- [ ] Compose Task terminal acceleration without moving semantics into daemon core.
- [ ] Make parent workflow idempotent by requiring all canonical rereads.
- [ ] Rewrite `$demand-orchestration` around the exact ten-step rule in section 7.8.
- [ ] Remove `task-management` from manifest/runtime Skill projection.

Run:

```bash
./buddyswitch-test focused \
  tests/integration/goal_mode/test_demand_orchestration.py \
  tests/integration/demand_sys/test_side_triage_flow.py \
  tests/unit/architecture/test_task_management_skill.py \
  tests/unit/actor/test_runtime_skills.py \
  tests/unit/daemon/test_instance_entrypoint.py
```

Expected GREEN: triage is side-only; Goal completion and Demand selection occur in a new parent turn with one orchestration owner.

### Block E — replace every live consumer and delete retired execution

**Claim:** the repository has one live Task architecture and no discoverable retired execution path.

**Delete:**

- `tools/launcher/task_sys_runtime.py`
- `tools/launcher/task_sys_daemon_adapter.py`
- `scripts/env/tool_runtime/task_sys_runtime_client.py`
- `scripts/env/tool_runtime/task_sys_runtime_protocol.py`
- `buddyswitch/skills/shared/task-management/SKILL.md`
- retired Task frame/progress/side tests after current replacements are GREEN

**Modify:**

- `scripts/env/tool_runtime/role_auth.py`
- `scripts/env/tool_runtime/registry.py`
- `scripts/env/tools/context/_impl.py`
- `scripts/env/tools/message/tool.py`
- all five `tools/launcher/assets/roles/*/AGENTS.md`
- `tools/launcher/assets/web-management/app.js`
- `docs/arch/task-sys-architecture.md`
- `docs/arch/demand-sys-architecture.md`
- `docs/arch/daemon-service-architecture.md`
- `docs/arch/web-interface-call-architecture.md`
- direct unit/integration/process tests found by the residue scan

**REPLACE proof:**

- [ ] Remove close/need-parent permissions and tool catalog entries.
- [ ] Remove old alternatives from message/context/tool feedback.
- [ ] Remove side/parent frame language from all role bootstraps.
- [ ] Remove `recoverable_tasks` and `recoverable_count` from live projection/UI contracts.
- [ ] Project active versus terminal minimal Tasks without old status translation.
- [ ] Update Web/CLI direct consumers to the new current schema.
- [ ] Rewrite current architecture documents around one owner and native Goal.
- [ ] Convert old positive tests into current behavior tests or narrowly scoped negative residue guards.
- [ ] Delete old runtime modules after imports/callers are gone.
- [ ] Do not edit historical memos to erase history.

Run affected consumer tests discovered from the final call graph, including:

```bash
./buddyswitch-test focused \
  tests/unit/env_tool/test_native_mcp_server.py \
  tests/unit/env_tool/test_semantic_contract.py \
  tests/unit/env_tool/test_schema_contract.py \
  tests/unit/actor/test_role_action_auth.py \
  tests/unit/actor/test_runtime_skills.py \
  tests/unit/architecture/test_repo_contracts.py \
  tests/unit/architecture/test_task_management_skill.py \
  tests/unit/architecture/test_tool_runtime_contract.py \
  tests/unit/web/ui_state_task.test.js \
  tests/integration/im/test_external_query.py \
  tests/integration/web/test_management_product_api.py \
  tests/process/cli/test_black_box_tool_runtime.py
```

Expected GREEN: all current consumers understand only the minimal Goal-bound Task.

Run the retirement scan:

```bash
rg -n \
  "task_sys\\.side_frame|task_sys\\.parent_frame|task_sys\\.outcome_frame|TASK PROGRESS CHECK|task_sys\\.need_parent|record_task_close|record_side_|awaiting_parent|parent_processing|side_processing|TaskSysRuntimeAccess|task_sys_runtime|task-management|recoverable_tasks|recoverable_count" \
  scripts tools buddyswitch tests docs/arch
```

Expected: no live implementation, prompt, permission, projection, or positive behavior test. A narrowly scoped negative assertion may name a retired term solely to prove absence.

Run the Demand escalation scan:

```bash
rg -n \
  "needs_parent_judgment|parent_judgment|parent judgment" \
  scripts tools buddyswitch tests docs/arch
```

Expected: no Demand triage branch or guidance. Historical `docs/memo/**` is intentionally excluded.

Run the generic daemon ownership scan:

```bash
rg -n \
  "task_sys|demand_sys|TaskGoal|DemandOrchestration|goal_(get|set|clear)|thread/goal" \
  tools/launcher/daemon_core.py tools/launcher/daemon_runtime.py tools/launcher/daemon_triggers.py
```

Expected: no product semantic coupling. Generic source normalization may preserve opaque notification method names, but must not branch on product meaning.

### Block F — focused verification and real Web/Actor acceptance

**Claim:** the new product path works through the actual consumer boundary and leaves clean resources.

**Files:**

- Create: `tests/system/goal_mode/test_product_flow.py`
- Modify only for defects exposed by the real loop: the owning code and its nearest regression test
- Record evidence in the execution log section of this memo or a same-scope resumable execution record

#### Automated affected verification

- [ ] Freeze the candidate diff for Phase 2.
- [ ] Rediscover all affected tests from imports, contracts, callers, and consumers.
- [ ] Run focused owner, handler, Skill, tool, projection, daemon, and real Goal targets.
- [ ] Run the retirement and architecture scans from Block E.
- [ ] Confirm no process, socket, lock, temporary shared root, or mock service remains.

Do not run `./buddyswitch-test full` merely because Block F was reached. Under the repository test contract, full is reserved for the frozen final merge/release candidate, an explicit repository-wide acceptance request, or direct user instruction. Phase 2 focused evidence must still cover every affected boundary.

#### Repeatable isolated system flow

The system test must:

1. allocate an isolated shared root;
2. resolve the actual installed Codex runtime;
3. start the deterministic local model endpoint;
4. launch BuddySwitch Web and one real Actor through public launcher paths;
5. create/send one request whose completion needs at least two Goal turns;
6. observe one Demand;
7. observe one active minimal Task;
8. observe one matching native Goal on the Actor main thread;
9. prove a second Goal turn occurs without Task Progress Check;
10. prove the exact source `message_id` is preserved in the Task/Goal objective;
11. prove the Actor uses that id as `reply_to`, rereads the durable reply, and
    delivers it before Goal complete;
12. observe native Goal complete;
13. observe Task completed with host snapshot;
14. observe a later parent orchestration turn verify the reply and reconcile
    the Demand with Task and Message evidence;
15. prove no second active Task unless a live Demand remains;
16. stop/delete the Actor and Web runtime;
17. remove the isolated root and all mock resources.

Run:

```bash
./buddyswitch-test focused \
  tests/system/goal_mode/test_native_goal_contract.py \
  tests/system/goal_mode/test_product_flow.py
```

Expected: PASS using actual Codex App Server/Goal and public BuddySwitch runtime paths.

#### Manual browser observation

After automated system proof is GREEN:

- [ ] Start Web through BuddySwitch CLI with a fresh isolated root.
- [ ] Open the real Web UI.
- [ ] Create one Actor.
- [ ] Send the same bounded multi-turn request.
- [ ] Observe Web message delivery, Demand, Task, and available runtime/log projections.
- [ ] Correlate actor instance, main thread, Demand, Task, Goal updates, and reconciliation turn in data-link logs.
- [ ] Confirm there is no Task side thread, frame prompt, `need_parent`, Progress Check, or outcome frame.
- [ ] Stop/delete every created runtime and verify cleanup.

Manual observation supplements the repeatable system proof; it does not replace it.

#### Phase 2 stop gate

After presenting the exact automated and manual evidence:

- stop;
- report passed and omitted checks, cleanup, and residual risks;
- ask the user to review Phase 2 acceptance;
- do not start Phase 3 until the user explicitly confirms.

## 10. Test evidence identity

Every implementation block records:

| Field | Required value |
|---|---|
| Claim | one sentence from the block |
| Source identity | branch, commit/diff identity, runtime Codex path/version |
| Exact check | complete `./buddyswitch-test focused ...` or residue command |
| Result | pass/fail plus failed node when applicable |
| Product boundary | domain/tool/handler/App Server/Web path actually exercised |
| Cleanup | process/socket/lock/temp-root result |
| Residual risk | exact unproved behavior, or `none within block scope` |

Tests must prove semantic state effects and consumer results. Registration-only assertions, mocked `ok=true`, or field existence alone are insufficient.

## 11. Acceptance matrix

| Proof class | Required Phase 2 evidence |
|---|---|
| Product | real isolated Web Actor completes a multi-turn request, delivers a readable reply, and exposes Demand → Task → Goal → reconciliation |
| Contract | exact Task schema/actions, Goal wrapper protocol, status mapping, conflict behavior, cancellation, and recovery tests |
| Architecture | Task owner, TaskGoalHandler, DemandOrchestrationHandler, and daemon composition have one rule owner and inward dependencies |
| Replacement | retired modules deleted; Skills/roles/tools/projections/current docs and positive tests contain no retired model |
| Operations | startup recovery, missed notification, duplicate event, process failure, resource cleanup, and log correlation proved |

Phase 2 is incomplete if any material row lacks direct evidence, even if a broad test group is green.

## 12. Stop conditions and risk handling

### 12.1 Native Goal contract gap

If Block A fails against the actual installed runtime:

- do not modify Task Sys;
- preserve the exact failing transcript and runtime identity;
- state the missing Codex capability;
- decide separately whether Codex must be upgraded or fixed.

Do not compensate with a BuddySwitch continuation engine.

### 12.2 Retired runtime data encountered

If an acceptance root contains an old active Task, side thread, frame checkpoint, or legacy source ref:

- stop that run;
- discard/rebuild only the isolated test root;
- do not add a legacy reader;
- do not touch the user's default shared state.

Default-state rebuild belongs to Phase 3 and requires fresh explicit authorization immediately before destructive action.

### 12.3 Orphan or mismatched native Goal

If the persistent main thread has an unfinished Goal that does not match the canonical active Task:

- report a precise invariant conflict;
- do not overwrite, adopt, or silently clear it;
- prevent another Task selection;
- add a nearest-boundary regression if product code created the conflict.

### 12.4 Daemon capability gap

If current generic command/notification/reconciliation capability cannot support the product handler:

- name the exact generic lifecycle gap with a failing daemon contract test;
- add only a product-neutral capability to daemon core;
- keep all Task, Demand, Goal, Skill, and selection semantics in product handlers/composition.

No daemon business coupling is permitted.

### 12.5 Real message delivery failure

If Goal work completes internally but the Web user cannot read the result:

- Phase 2 product acceptance fails;
- trace message send, reply target, thread, Task, Goal, and artifact projections;
- fix the owning cause and add the nearest consumer-path regression;
- do not classify internal Task/Goal completion as sufficient.

This preserves the lesson from the earlier Market test: metadata without readable user delivery is not a successful outcome.

## 13. Final ACCEPT audit

Before reporting Phase 2 complete, answer every item with evidence:

- [x] Does the real user loop satisfy the acceptance sentence?
- [x] Is Demand triage entirely side-only?
- [x] Is there no Demand `needs_parent_judgment` branch?
- [x] Is Task execution entirely native Goal on the persistent main thread?
- [x] Is later Demand reconciliation a separate parent turn rather than a handoff state?
- [x] Is there at most one active Task and one unfinished matching Goal?
- [x] Can Task-write/Goal-set, missed-notification, duplicate-event, and restart windows converge?
- [x] Does only matching Goal `complete` complete Task?
- [x] Do blocked/paused/limited states keep the same Task active?
- [x] Does cancel leave Demand judgment to a later parent turn?
- [x] Are Actor Task actions exactly list/get/create/cancel?
- [x] Are all live old Task modules, fields, prompts, tools, permissions, Skills, projections, and current docs removed?
- [x] Is daemon core product-neutral?
- [x] Are real Web delivery and data-link logs readable?
- [x] Are all processes, sockets, locks, actors, and isolated roots clean?
- [x] Were unrelated user changes preserved?
- [x] Has execution stopped before Phase 3 for user confirmation?

No item may be marked complete from intention or code inspection alone.

## 14. Execution log template

Fill this section during implementation; do not pre-mark work complete.

### Block A — native Goal boundary

- Source identity: branch `fea-daemon`, HEAD `79bfb8055598`, working-tree
  Phase 2 diff.
- RED command/result: the Block A focused command above initially exposed
  missing exact Goal wrapper/system proof.
- GREEN command/result: Block A–D focused group passed `182` Python tests and
  `454` subtests; the final contract/orchestration/product group passed
  `18` tests in `50.86s`.
- Runtime path/version: runtime-selected installed `codex-cli 0.144.6`, real
  App Server and native Goal persistence/continuation.
- Cleanup: test process groups, sockets, mock endpoint, and temporary roots
  were removed; the process-group probe was corrected to inspect actual live
  members instead of treating macOS `killpg(..., 0)` `EPERM` as a result.
- Risk: repository-wide `full` was not run because this is not a frozen
  merge/release candidate and the user did not request it.

### Block B — minimal Task owner

- Source identity: same Phase 2 diff.
- RED command/result: the Block B focused command above rejected the old
  frame-shaped Task contract and required the exact minimal schema/actions.
- GREEN command/result: included in the `182`-test owner/handler group.
- Residue checked: old schemas are rejected rather than translated; Actor
  actions are exactly `list`, `get`, `create`, and `cancel`.
- Risk: historical default-root Task data remains intentionally outside this
  isolated Phase 2 acceptance and belongs to separately authorized Phase 3.

### Block C — Task–Goal convergence

- Source identity: same Phase 2 diff.
- RED command/result: the Block C focused command above required exact
  matching, terminal mapping, conflict, cancellation, and recovery behavior.
- GREEN command/result: included in the `182`-test owner/handler group and the
  final `18`-test native Goal group.
- Recovery cases: Task-write/Goal-set window, already matching Goal, complete
  while daemon is unavailable, duplicate terminal observation, missing Goal,
  cancellation cleanup, and mismatched unfinished Goal.
- Risk: multi-Task/multi-thread execution is explicitly outside Phase 2.

### Block D — Demand orchestration

- Source identity: same Phase 2 diff.
- RED command/result: real browser run 1 completed Task, Goal, and Demand but
  created no reply to source message `msg-650b55e1624b`; the Web user saw no
  result. The nearest Skill RED
  `test_orchestration_skill_makes_im_delivery_a_durable_completion_condition`
  then failed on the missing `im.message.created` delivery rules.
- GREEN command/result: `$demand-orchestration` now preserves the exact source
  `message_id`, requires `message.send` plus durable readback before Goal
  completion, and verifies matching reply evidence before Demand completion.
  The Skill test, Demand orchestration tests, legal Demand evidence schema
  tests, and the final product system test all pass.
- Independent-turn evidence: in real browser run 2, Goal/Task completed at
  `17:24:17`; a later parent turn started from terminal attention and completed
  Demand at `17:25:24` after reading Task, Demand, source Message, and full
  conversation state.
- Risk: agent judgment remains Skill-owned by design; the durable invariant is
  mechanized by the Skill contract test and consumer-path system test rather
  than duplicated inside daemon core.

### Block E — replacement cut

- Source identity: same Phase 2 diff.
- Focused command/result: affected consumer group passed `127` Python tests
  and `844` subtests; Task UI tests passed `6`; final Demand schema/response
  check passed `9`.
- Retirement scan: matches are limited to scoped negative assertions and one
  invalid old-record fixture; no retired implementation, prompt, permission,
  projection, or positive behavior remains.
- Architecture scan: generic daemon core contains no Task, Demand, Goal, or
  selection semantic branch; `git diff --check` is clean.
- Risk: none within the Phase 2 replacement boundary.

### Block F — product acceptance

- Source identity: same Phase 2 diff; real browser run used a fresh isolated
  root and a newly created Dev Actor.
- Automated system command/result:
  `./buddyswitch-test focused
  tests/unit/architecture/test_task_management_skill.py
  tests/integration/goal_mode/test_demand_orchestration.py
  tests/system/goal_mode/test_native_goal_contract.py
  tests/system/goal_mode/test_product_flow.py` → `18 passed in 50.86s`.
- Manual Web scenario: Actor `act-dev-a821dc087205`, main thread
  `019f8e47-3bef-7092-8036-0923ee9e0476`, source Message
  `msg-cfcd33049208`, Demand `demand-373a7cd89229`, Task
  `task-demand-777b7fcd8f65`, native Goal
  `c2099eb6-8617-43e5-82cf-e6a19d353899`, and reply
  `msg-33b5188cfe81`. The UI visibly showed the exact reply while the Task was
  still active, then showed `0 active · 1 recent` after Goal/Task completion.
- Data-link evidence: Goal persisted `complete` with the exact Task objective,
  Task stored the matching Goal terminal snapshot, Demand revision `2`
  completed with Task, artifact `art-5ff1aab503`, and
  `im.message.reply` evidence, and `side_threads` was empty.
- Cleanup: Actor was stopped and deleted in Web UI; Web was stopped; isolated
  root `/private/tmp/buddyswitch-phase2-browser-BHgjRx` was reset and removed;
  port `8878` and recorded Actor processes were absent.
- Omitted checks: `./buddyswitch-test full`, the Phase 3 Market/Dev multi-demand
  matrix, daemon-offline matrix, and destructive default-root rebuild.
- Residual risk: none within the Phase 2 acceptance sentence. Browser console
  still reports an expected `404` while no direct conversation exists and
  teardown-time `502`/empty long-poll responses after Actor/Web removal; these
  did not affect the accepted loop and are not Goal/Task semantics. Omitted
  checks remain explicit Phase 3 scope.
- User Phase 2 acceptance: pending explicit review; Phase 3 has not started.
