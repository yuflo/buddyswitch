# Task Lifecycle Attention Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:test-driven-development` for every behavior change and
> `.agents/skills/buddyswitch-testing` for target selection and evidence. This
> plan is executed inline because repository instructions do not authorize
> subagent dispatch. Do not make a plan-only commit.

**Goal:** Make every currently required Task lifecycle judgment reachable by
prompt-driven actor attention after unresolved side turns and Demand-sourced
Task completion or cancellation.

**Architecture:** Task Sys remains the single semantic owner. Its daemon adapter
maps generic main-turn completion and side-thread idle facts to processor-aware
Progress Checks; the generic side lifecycle uses one fresh isolated ephemeral
thread; Task domain, tool, and runtime replace completion-only attention with
one strict terminal outcome frame. Demand Sys remains independent and the
generic daemon remains product-neutral.

**Tech Stack:** Python domain/tool/runtime modules, JSON Task records, Codex App
Server thread notifications, BuddySwitch env tools, `unittest`/pytest through
`./buddyswitch-test`, real `./buddyswitch-codex` CLI acceptance.

**Design:**
`docs/memo/2026-07-20-task-lifecycle-attention-closeout-design.md`

**Baseline:** `c54c65c3ccaae32f72e2b7f8aac1af20314e4d82`

---

### Task 1: RED — terminal outcome contract

**Files:**

- Modify: `tests/integration/task_sys/test_actor_create.py`
- Modify: `tests/unit/task_sys/test_runtime_executor.py`
- Modify: `tests/integration/env_tool/test_response_task.py`

- [x] Replace the completed-only domain expectation with
  `outcome_instruction(task_id)` and exact `task_sys.outcome_frame` assertions.
- [x] Add a canceled Demand Task case asserting the same frame shape with
  `status="canceled"` and `outcome.type="cancellation"`.
- [x] Rename tool response assertions from `completion_attention` to
  `outcome_attention` and add a Demand-sourced cancel case that must submit the
  same Task id to parent runtime.
- [x] Add runtime rendering cases for completed and canceled outcome frames and
  reject mismatched status/result pairs.
- [x] Run exact RED:

```bash
./buddyswitch-test focused \
  tests/integration/task_sys/test_actor_create.py \
  tests/unit/task_sys/test_runtime_executor.py \
  tests/integration/env_tool/test_response_task.py
```

Expected failure: `outcome_instruction`, `task_sys.outcome_frame`, and
`outcome_attention` do not exist; canceled Tasks submit no parent attention.

### Task 2: GREEN — forward-replace completion attention

**Files:**

- Modify: `scripts/env/domain/task_sys.py`
- Modify: `scripts/env/tools/task_sys/_impl.py`
- Modify: `scripts/env/tools/task_sys/tool.py`
- Modify: `tools/launcher/task_sys_runtime.py`

- [x] Replace `completion_instruction` with `outcome_instruction`. Accept only
  Demand-sourced `completed` or `canceled` Tasks and validate the exact matching
  execution result.
- [x] Replace `render_completion_frame` with `render_outcome_frame`; route only
  `task_sys.outcome_frame` through `render_submit_parent_frame`.
- [x] Extract one private tool helper that submits current outcome attention.
  Call it after both `close` and `cancel`, after side cleanup has been persisted.
- [x] Replace public response field `completion_attention` with
  `outcome_attention`; update close and cancel action schemas/descriptions so
  both declare parent outcome submission and explicit failure behavior.
- [x] Run the Task 1 command GREEN. Refactor only duplication introduced by the
  outcome helper, then rerun the same command.

### Task 3: RED — isolated side lifecycle and processor-aware Progress Check

**Files:**

- Modify: `tests/integration/task_sys/test_progress_check.py`
- Modify: `tests/unit/task_sys/test_runtime_executor.py`
- Modify: `tests/unit/task_sys/test_daemon_adapter.py`
- Modify: `tests/integration/actor/test_side_thread_lifecycle.py`
- Modify: `tests/integration/app_server/test_client.py`
- Modify: `tests/integration/daemon/test_trigger_router.py`

- [x] Require all side creation to use fresh ephemeral `thread/start` with
  isolated developer instructions, explicit runtime context, and no fork or
  boundary injection.
- [x] Replace parent-only submit seams with
  `submit_task_progress_check(context, task, previous_turn, processor=...)`.
- [x] Project generic App Server `thread/status/changed` into
  `source_context.thread_status` without Task knowledge.
- [x] Register a real side-thread lease in isolated instance JSON and assert an
  idle signal selects only its exact side-processing Task and current turn id.
- [x] Assert the submitted side check can close, cancel, or hand off the same
  Task without creating a checkpoint Task.
- [x] Assert unregistered side threads, wrong-purpose leases, wrong Task status,
  non-idle signals, and the check's own idle signal are ignored.
- [x] Add runtime prompt assertions for side and parent processor wording and a
  side submit assertion that calls `send_to_side_thread` with the exact
  registered thread.
- [x] Run exact RED through the public focused runner.

```bash
./buddyswitch-test focused \
  tests/integration/task_sys/test_progress_check.py \
  tests/unit/task_sys/test_runtime_executor.py \
  tests/unit/task_sys/test_daemon_adapter.py
```

Observed failure: old lifecycle called forbidden `thread_fork`; `thread_start`
lacked isolated-side parameters; generic normalization omitted thread status;
the Task handler rejected side status notifications; capability metadata still
named fork durability.

### Task 4: GREEN — replace forked side runtime and close Progress Check owner

**Files:**

- Modify: `tools/launcher/task_sys_daemon_adapter.py`
- Modify: `tools/launcher/task_sys_runtime.py`
- Modify: `tools/launcher/app_server.py`
- Modify: `tools/launcher/side_thread_lifecycle.py`
- Modify: `tools/launcher/daemon_triggers.py`
- Modify: `tools/launcher/actor_capability.py`
- Modify: `tests/support/fake_codex/rpc.py`

- [x] Extend the generic `thread_start` client with optional developer
  instructions, ephemeral, model, and effort parameters; delete the retired
  fork helper and boundary prompt.
- [x] Create every side from a fresh isolated thread and keep one lease/write
  path for both host-control and Task side consumers.
- [x] Normalize generic thread status without moving Task semantics into daemon
  infrastructure.
- [x] Resolve main completed turns to the current actor-owned parent-processing
  Task.
- [x] Resolve side idle signals only through an open `task_sys.side_frame` registry
  lease whose exact Task is actor-owned and `side_processing`.
- [x] Replace parent-only render/submit functions with processor-aware Task
  Progress Check functions. Parent submits to the main actor thread; side sends
  to the same registered side thread.
- [x] Preserve one-turn recursion suppression for both processors and return
  failed without mutating Task state when submission fails.
- [x] Run the expanded Task 3 command GREEN, refactor, and rerun it.

### Task 5: REPLACE current contracts and guidance

**Files:**

- Modify: `buddyswitch/skills/shared/task-management/SKILL.md`
- Modify: `docs/arch/task-sys-architecture.md`
- Modify: `tests/unit/architecture/test_task_management_skill.py`
- Modify: `tests/unit/architecture/test_task_sys_boundaries.py`
- Modify: affected schema/semantic tests discovered by exact live-reference scan

- [x] Teach one processor-aware Task Progress Check and one terminal Task
  Outcome Check. For canceled outcomes, require latest Demand reread and actor
  choice to cancel, revise, or keep it live before applying the existing Task
  Selection Rule.
- [x] Replace current architecture frame names and error semantics. Keep Demand
  and generic-daemon boundaries unchanged.
- [x] Update exact architecture/schema tests to require only current names.
- [x] Run residue scan:

```bash
rg -n \
  'completion_instruction|task_sys\.completion_frame|completion_attention|render_parent_progress_check|submit_parent_progress_check' \
  scripts tools buddyswitch docs/arch tests \
  -g '!**/.git/**'
```

Expected result: no live matches except scoped negative assertions proving
absence. Historical `docs/memo` matches are allowed.

### Task 6: focused IMPACT verification

**Files:** all changed executable contracts and direct architecture boundaries.

- [x] Rediscover targets from `git diff --name-status`, changed symbols, and
  current test references.
- [x] Run compatible focused batches through the only public runner. Include
  direct Task domain/tool/runtime/daemon/skill tests plus Demand/Task and generic
  daemon decoupling tests that the diff actually reaches.
- [x] Record source identity, exact command, runner result, cleanup, and residual
  risk in this memo and the pressure-test memo.
- [x] Do not run `./buddyswitch-test full`; this is not repository-wide FINAL.

### Task 7: real BuddySwitch CLI MILESTONE

**Files:**

- Modify: `docs/memo/2026-07-20-demand-task-real-actor-pressure-test-memo.md`
- Modify: this plan's evidence section

- [x] Snapshot existing actor ids/status/thread ids, source identity, runtime
  binary/version, processes, sockets, and worktree state.
- [x] Start fresh actors only through
  `./buddyswitch-codex instance start --role <role>` and send inbound needs only
  through public Web/IM.
- [x] Side recovery run: observe a side thread become idle while the same Task remains
  side-processing, then observe one side Progress Check and terminal convergence.
  Do not manually steer the actor.
- [x] Cancellation/waiting run: send Demand B after Task A becomes active; make A
  unfulfillable; assert Task A cancels, outcome attention reconciles A, and B
  receives a Task afterward. Require maximum active count one.
- [x] Wait for final `checked_revision == revision` and main-thread idle before
  declaring each run quiescent.
- [x] Capture public projections, owner event sequences, daemon handler results,
  side/main thread state, outcome/check frames, and exact cleanup.
- [x] Stop/delete only created actors. The already-running Web process was reused
  and left unchanged. Prove no created actor process/socket/lease/directory
  remains and every baseline actor is unchanged.

### Task 8: independent-review repair and reacceptance

**Files:**

- Modify: `scripts/env/domain/task_sys.py`
- Modify: `scripts/env/tools/task_sys/_impl.py`
- Modify: `tools/launcher/daemon_state.py`
- Modify: `tools/launcher/side_thread_registry.py`
- Modify: `tools/launcher/side_thread_lifecycle.py`
- Modify: `tools/launcher/task_sys_daemon_adapter.py`
- Modify: `tools/launcher/task_sys_runtime.py`
- Modify: exact adjacent tests and current architecture/memo surfaces

- [x] Add RED for canceling a Demand Task from `awaiting_parent`: the durable
  canceled Task must retain `processor=side` and submit one outcome attention.
- [x] Add RED proving a `starting` side lease exists before `turn/start`, a
  fast-idle work turn receives immediate reconciliation, and a lease consumed
  by fast terminal/handoff completion does not trigger a duplicate side retry.
- [x] Add an atomic side-turn compare-and-set and serialize in-process plus
  cross-process registry writes. Only `work` can claim
  `progress_check_pending`; successful submission records `progress_check`.
- [x] Add opaque generic daemon handler checkpoints and prove a newly loaded
  handler/state pair ignores its own submitted parent check turn.
- [x] Remove process-local Progress Check suppression and the remaining live
  `side_fork` failure-stage fixture.
- [x] Preserve the original Progress Check submission error when concurrent
  terminal cleanup has already removed the side lease.
- [x] Run focused direct and affected-consumer verification, then rerun the
  real side-omission path through a fresh CLI-created actor and public Web/IM.

### Task 9: second-review failure-atomicity repair

- [x] Add RED proving a vanished starting lease is not success while canonical
  Task status remains `side_processing`, but remains valid after terminal or
  parent handoff transition.
- [x] Add RED proving post-`turn/start` setup failure interrupts the exact turn
  before retry and becomes non-retryable when that stop cannot be proved.
- [x] Add RED proving side Progress Check keeps its pending claim when external
  submit may have succeeded and releases it only before an external attempt.
- [x] Add RED proving parent Progress Check persists `submitting` before actor
  input and suppresses resubmission if receipt persistence fails.
- [x] Implement the failure facts in the side lifecycle owner and interpret
  them only in Task runtime/adapter; keep generic daemon checkpoint storage
  product-neutral.
- [x] Run direct and affected focused automated verification.
- [x] Rerun fresh real CLI actor acceptance after the second-review repair and
  audit cleanup/baseline actors.

## Evidence record

### RED

- Terminal outcome RED: 10 failed / 42 passed; canceled Tasks had no outcome
  contract and completion-only names were still live.
- Processor Progress Check RED: 13 failed / 25 passed; only parent submit/render
  seams existed.
- Real-runtime correction RED: 10 failed / 74 passed / 16 subtests; the old
  lifecycle called forbidden fork/boundary helpers, side status was not
  normalized, and the Task handler rejected side idle.
- Outcome acknowledgement RED: 3 failed / 36 passed / 81 subtests; cancellation
  reconciliation did not require acknowledgement of its returned revision.
- Evidence contract RED: 1 failed / 23 passed / 10 subtests; the Demand complete
  schema exposed only `ref.id|key`, contradicting the exact Task evidence frame.
- Independent-review RED: 7 failed / 79 passed / 36 subtests. It directly
  reproduced missing `awaiting_parent` outcome ownership, lease-after-turn
  ordering, missing fast-idle reconciliation, and process-local parent/side
  suppression. A separate fast-terminal RED proved creation retried after a
  consumer had already removed the starting lease; a concurrent-cleanup RED
  proved release cleanup could mask the actual submission error.
- Second-review failure-atomicity RED: 8 failed. It directly reproduced unsafe
  retry after an unstopped side turn, false success on a consumed lease while
  Task ownership remained in side, side uncertain-submit rollback, and parent
  submit-before-checkpoint ordering.

### GREEN / IMPACT

- Terminal outcome GREEN: 52 passed / 30 subtests.
- Isolated side lifecycle and processor signal GREEN: 114 passed / 21 subtests.
- Final direct owner/contract/architecture batch:
  196 passed / 750 subtests, run id
  `5f2bcd2bf4fd4a4da1e1f82e94841e2f`.
- Wider consumer batch: 155 passed / 238 subtests with one baseline fixture
  failure in
  `test_actor_console_api_composes_runtime_task_sys_track_and_im_projection`.
  That fixture creates two active Tasks sequentially against the pre-existing
  single-active gate; this change does not touch `_create_task` and did not
  weaken the invariant.
- Residue: no retired executable fork/boundary or completion-only symbol remains;
  remaining search matches are scoped negative assertions or historical memos.
- `./buddyswitch-test full` was intentionally not run because this is a focused
  feature acceptance, not a frozen repository-wide candidate.

### Real actor MILESTONE

- Runtime: installed real `codex-cli 0.144.6`; no fake binary or override.
- Side omission acceptance: actor `act-test-106f08fa528f`, Demand
  `demand-0645a210d719`, Task `task-demand-451ec99a9a31`. Exact leased side idle
  produced one handled Progress Check; the same Task completed, Demand reached
  revision/check 2/2, side lease cleared, main became idle, and App Server logged
  no unmatched custom-tool error.
- Final cancellation/waiting acceptance: actor `act-test-d6b1f6d02993`. Demand B
  was captured and checked while Task A was active. Task A
  `task-demand-6a435f828b16` canceled and its Demand
  `demand-f1fd92da58e9` reached canceled revision/check 2/2. Only afterward Task B
  `task-demand-f8ecfea2ffdd` started and completed; Demand B
  `demand-7494d47f4491` reached completed revision/check 2/2 with exact evidence
  `ref.task_id`. Maximum active Task count was one.
- The run also caught and closed two contract gaps before final acceptance:
  acknowledge every source-owner mutation revision, and expose `task_id` in the
  Demand completion evidence schema without adding a Demand-to-Task dependency.
- Final-code smoke after removing the concrete Demand API name from the Task
  runtime prompt: actor `act-test-9d5b060248da`, Demand
  `demand-1cefe256f4ee`, Task `task-demand-c1dae3cdf791`; completed
  revision/check 2/2 with exact `ref.task_id`, main idle, no runtime error.
- Independent-review repair direct GREEN: 87 passed / 36 subtests. Expanded
  affected owners and consumers passed 222 tests / 750 subtests; daemon-state
  and adjacent session consumers passed 48 tests / 7 subtests. The final
  combined affected-owner/consumer batch passed 299 tests / 850 subtests, run
  id `c12c7f36dacb4caaa6cf41ea9d18607c`.
- Repair reacceptance used real CLI actor `act-test-a80d1f6a2299`, IM
  `msg-41a0e2b6ca3d`, Demand `demand-55e9021dc904`, Task
  `task-demand-df7ed57f4653`, and side thread
  `019f7f89-c0ed-7281-9302-96eab964d3ae`. The deliberate first side omission
  produced one handled check; check-turn idle notifications were ignored; the
  same Task completed; the Demand reached revision/check 2/2 with exact
  `ref.task_id`; main became idle and the side lease cleared.
- Second-review direct GREEN: 59 passed / 9 subtests. The changed-test affected
  batch passed 233 tests / 750 subtests, run id
  `a2ac7b92d0cd4e4aadf4aa675534676e`.
- Broader actor/daemon/Task neighbor verification passed 347 tests / 536
  subtests, run id `91efd0c14286456f87a581dbb6e77356`.
- Final all-changed-test batch passed 272 tests / 1041 subtests, run id
  `6ec77edfe8f14708ad9dc5b55635f014`.
- Second-review real acceptance used actor `act-test-0e701ecd5ae7`, main thread
  `019f7fa1-a071-7ef3-b5a1-6574dda97872`, and real `codex-cli 0.144.6`. IM
  `msg-9e5f95f3d76a` first proved one side Progress Check. Supplemental IM
  `msg-00234c7d3d8d` was absorbed into Demand `demand-7e9811bcedfd`, revision 2,
  and Task `task-demand-5a03f0a5385f` then proved parent Progress Check. The
  daemon durably recorded source turn `019f7fa6-d78d-7f92-a522-4e603f234d26`
  and submitted turn `019f7fa7-0ff2-7512-ba7e-a5a207776e7a`; the latter's
  completion was ignored. The Task completed in parent, the Demand completed
  at revision/check 3/3 with its exact Task evidence, main became idle, side
  leases were empty, and daemon `last_error` remained null.
- The created actor was stopped/deleted, its instance directory disappeared,
  the temporary Web listener was stopped, and both baseline market actors
  remained healthy on their original main thread ids.
- Final independent static re-review: **APPROVE**. It found no Critical,
  Important, dual-track, generic-daemon business coupling, or retired live
  Progress Check/fork/outcome-path issue.
- All diagnostic and acceptance actors were stopped/deleted. No created actor
  directory, process, socket, or side lease remained. Baseline market actors
  `act-market-645c3ea1fe37` and `act-market-8164b055c113` remained active,
  healthy, and on their original main thread ids.
