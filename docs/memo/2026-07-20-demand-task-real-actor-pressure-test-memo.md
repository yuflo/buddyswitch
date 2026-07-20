# Demand / Task Real Actor Pressure Test Memo

**Date:** 2026-07-20

**Status:** Phase 3 second-review repair accepted; Phase 4 entry unblocked

**Source identity:** `fea-daemon` at
`c54c65c3ccaae32f72e2b7f8aac1af20314e4d82`

**Runtime identity:** installed real Codex, `codex-cli 0.144.6`; no fake Codex
and no `BUDDYSWITCH_CODEX_BIN` override

## 1. Purpose

Before Phase 4, pressure-test the Phase 2/3 product loop with fresh actors and
real model behavior:

```text
external IM
  -> daemon delivery
  -> Demand creation and organization
  -> actor selection
  -> at most one active Task
  -> side or parent lifecycle
  -> Task terminal outcome receipt
  -> latest Demand reconciliation
```

This is a diagnostic milestone, not an implementation phase. Do not steer a
running actor around a failure and do not change code until the failure pattern
and owning cause are grounded. Every created actor and Web process is scoped to
its run; pre-existing actors and default-environment state must not be reset or
deleted.

## 2. Acceptance claims

The expanded run separates five claims that a single happy path cannot prove:

1. inbound IM facts become actor-owned Demands and are acknowledged;
2. related Demands are organized without duplicate Task consumption;
3. independent live Demands drain sequentially with maximum active Task count
   one;
4. both legal execution branches converge:
   `side_processing -> completed` and
   `side_processing -> awaiting_parent -> parent_processing -> completed`;
5. a Demand revision arriving during Task execution is reconciled against the
   Task's exact `basis_revision`, without automatic cross-owner mutation.

The milestone is not accepted when any Task remains active after its processor
turn is terminal and no deliberate actor work remains.

## 3. First pressure run: relation plus mixed Task queue

### 3.1 Inputs

A fresh PM actor `act-pm-323507901965`, main thread
`019f7edb-1a62-79f2-95f7-d0d13da6a898`, received three external IM messages:

- A: create a concise customer-data CSV export specification containing name
  and email;
- B: create a concise checkout payment-request timeout diagnosis checklist;
- C: supplement the same CSV export specification with timezone.

The run used the public Web/IM surface and public BuddySwitch CLI projections.
It observed state for 600 seconds without corrective input.

### 3.2 Confirmed behavior

- all three `im.message.created` notifications were handled by the generic
  daemon adapter;
- exactly three Demands were created;
- C (`demand-ea0c1965bd53`) was absorbed into A
  (`demand-324a3a4e7ff8`);
- A was revised to contain name, email, and timezone, then checked and completed
  with Task evidence;
- B (`demand-b4332b250de6`) remained independent;
- C created no Task;
- A and B created exactly two Tasks, sequentially; maximum observed active
  count was one;
- A's Task `task-demand-ad71b1dcb61d` traversed side, parent handoff, and
  completion successfully.

Observed timeline, relative to the first sample:

| Elapsed | Observable state |
| ---: | --- |
| 0.2 s | three new Demands, none checked |
| 26.4 s | C absorbed into A; A revised |
| 33.0 s | all observed revisions checked |
| 48.3 s | A Task in `in_progress.side_processing` |
| 74.5 s | same A Task in `in_progress.parent_processing` |
| 116.0 s | A Task completed |
| 137.8 s | A Demand completed and checked at revision 3 |
| 150.9 s | B Task entered `in_progress.side_processing` |
| 598.5 s | B Task still in the same status; run timed out |

### 3.3 Escaped lifecycle failure and corrected runtime root cause

B's Task `task-demand-8992676772c2` remained
`in_progress.side_processing`. Its side thread was already ephemeral and idle,
while the Task had recorded only creation and side-frame start: no `close`,
`need_parent`, or `cancel` action was persisted.

The first log reading incorrectly attributed a main-thread
`app_server.turn_completed` notification to the side thread. Two later fresh
real actors and a raw App Server subscriber corrected the event picture:

- ephemeral side threads emit `thread/status/changed` (`active -> idle`) but no
  `turn/started` or `turn/completed` notification;
- the old Task handler accepted only main `turn_completed`, so side yield had no
  Task-owned interpretation;
- more fundamentally, the side thread was created by `thread/fork` while the
  parent was still inside the `task_sys.create` custom tool call. Its inherited
  history therefore contained that unmatched custom call, and the side failed
  with `Custom tool call output is missing for call id ...` before it could
  perform a Task lifecycle action.

The reproductions were `act-test-4fb7ec2ce707` and
`act-test-86d101ccfaf9` on real `codex-cli 0.144.6`. Re-submitting a turn to the
same broken side reproduced the same protocol failure; the raw subscriber saw
only exact-thread active/idle status transitions.

Root-cause boundary:

```text
Immediate runtime failure
  fork inherits an unmatched parent custom tool call
  -> side turn cannot execute normally

Structural persistence failure
  ephemeral side yield is exposed only as thread idle
  + Task adapter listens only to main turn_completed
  -> no prompt-driven progress check
  -> canonical Task remains side_processing indefinitely
```

This does not show that Task status should be changed automatically. It shows
both a pre-existing side lifecycle construction defect and incomplete
prompt-driven progress-check coverage for the side processor branch.

### 3.4 Cleanup evidence

- the acceptance PM actor, App Server, daemon, runtime broker, side resources,
  sockets, and temporary run root were removed;
- no actor-scoped process remained;
- the two pre-existing market actors remained active and healthy with their
  original thread ids;
- canonical Demand/Task projections were intentionally retained as diagnostic
  evidence; no direct state deletion or environment reset was used;
- unrelated `.superpowers/` worktree content was untouched.

## 4. Expanded real-actor matrix

Run fresh actors independently so one stuck Task does not hide another branch.

| Run | Inputs and timing | Main boundary | Result |
| --- | --- | --- | --- |
| P — parent queue | three unrelated bounded repository-read needs, sent together | longer single-active drain through parent handoff | partial: two completed; one correctly canceled but its Demand remained live |
| S — side queue and semantic duplicate | two equivalent bounded text-only needs plus one unrelated text-only need | side-only terminal action and duplicate organization | passed: one duplicate, two completed side Tasks, max active one |
| R — revision during execution | send a repository-read need; after its Task becomes active, send a supplement to the same need | latest-revision reconciliation | passed: supplement absorbed; one basis-revision-1 Task satisfied latest revision 2 |
| Q — waiting after completion | send a second Demand while the first Task is active | completion attention continues the queue | passed: second Task started only after the first completion |
| X — waiting after cancellation | send a second Demand while an unfulfillable first Task is active | cancellation attention continues or reconciles work | failed: both Demands remained live and no Task followed cancellation |

For every run collect:

- actor/thread and Codex runtime identity;
- IM message ids and daemon handler results;
- Demand ids, descriptions, relation/terminal changes, revision and
  `checked_revision`;
- Task ids, DemandRefs, sampled statuses, maximum active count, and exact event
  sequence through owner reads;
- main/side thread terminal state and relevant daemon `turn_completed` results;
- scoped runtime cleanup and preservation of baseline actors.

## 5. Repair decision

Phase 4 entry remains paused until the two escaped boundaries pass focused and
fresh real-actor acceptance. The selected repair is systemic but bounded:

1. replace the single generic side creation path with fresh isolated ephemeral
   `thread/start`; delete fork and boundary-injection behavior;
2. use parent `turn_completed` and exact leased side `thread idle` as the two
   processor yield facts for one Task Progress Check owner;
3. replace completion-only attention with one terminal outcome contract shared
   by completed and canceled Demand-sourced Tasks.

No retry worker, polling loop, automatic lifecycle mutation, Demand/Task import,
or generic-daemon business branch is introduced.

## 6. Evidence log

### MILESTONE-1

- **State:** failed MILESTONE; diagnostic evidence retained
- **Source:** repository and commit named above; only unrelated untracked
  `.superpowers/` was present
- **Command surface:** real `./buddyswitch-codex instance start --role pm`,
  public Web/IM requests, `demand list/get`, `task list/get`, bounded polling,
  owner reads, App Server thread reads, and scoped instance stop/delete
- **Result:** Demand organization and single-active sequencing passed; the
  second side-processing Task failed to converge within 600 seconds
- **Residual risk:** side-only failure frequency and late-revision behavior are
  not yet known

Further run receipts are appended below without rewriting the evidence above.

### MILESTONE-2 — parent queue and side/duplicate queue

- **Actors:** PM `act-pm-13c4c3587295`, main thread
  `019f7efd-46e8-7fc0-80b0-a9a057e42932`; dev
  `act-dev-085fbf151427`, main thread
  `019f7efd-5df7-7311-b0ef-cfc5f37da5dc`
- **Runtime:** real installed `codex-cli 0.144.6`
- **Concurrent isolation:** both actor-scoped runs shared the public Web entry but
  had independent daemon, Task, Demand, thread, and cleanup state.
- **Maximum active Tasks:** one for each actor.

Side/duplicate result:

```text
3 IM -> 3 Demands
equivalent pair -> one Demand marked duplicate_of the other
2 live obligations -> 2 sequential Tasks
both Tasks: side_processing -> completed
both source Demands -> completed with exact Task evidence
```

The exact uppercase Task and word-count Task each recorded `created`,
`side_frame_started`, `closed`, and `side_cleanup_recorded`. No parent handoff
was used and no side lease remained. This proves side-only completion can work;
it does not remove MILESTONE-1 because there is still no recovery when the actor
omits the required terminal action.

Parent queue result:

- README and manifest Demands each used one Task and completed through
  `side_processing -> parent_processing -> completed`;
- each Task retained its id across handoff and cleaned its side lease;
- the root-AGENTS Demand used one Task that correctly reached `canceled` after
  the parent verified that the readable runtime root did not contain the
  requested North Star list;
- the canceled Task's source Demand remained live at revision 1,
  `checked_revision=1`, with no active Task and an idle main thread.

The cancellation was a valid actor outcome for the acceptance input. The
problem is the missing post-cancellation source attention, not the decision to
cancel.

### MILESTONE-3 — supplement during active Task

- **Actor/thread:** test `act-test-4be72808534c` /
  `019f7f02-fa4c-71f1-8e63-76b17ae49309`
- **Messages:** base `msg-b74d6d17d100`; supplement
  `msg-eee8869c2015`
- **Maximum active Tasks:** one

Observed order:

```text
base Demand revision 1 checked
-> Task created with basis_revision 1
-> Task enters side_processing
-> supplement IM arrives
-> supplement Demand absorbed into base
-> base description/revision 2 checked
-> same Task hands off to parent
-> parent output includes role ids plus new schema_version and env.id fields
-> Task completes
-> actor completes latest base Demand with exact Task evidence
```

The terminal Demand description contained both source refs. Task Sys never
mutated Demand, and Demand Sys never mutated Task. Actor judgment legitimately
accepted a basis-revision-1 Task as evidence for revision 2 because the actual
parent result explicitly satisfied the added fields.

The receipt was captured immediately after terminalization, at Demand revision
3 and `checked_revision=2`. The actor was cleaned before a quiescent follow-up
could be observed, so this is a harness stop-condition race, not evidence of a
product failure. Future real-actor acceptance must wait for both
`checked_revision == revision` and main-thread idle before teardown.

### MILESTONE-4 — waiting Demand after normal completion

- **Actor/thread:** design `act-design-6a891c892223` /
  `019f7f05-d45c-7800-a5c0-bee6e65bf345`
- **Maximum active Tasks:** one

A second text-only Demand arrived while a repository-read Task was active. The
first Task completed through parent; its completion frame then caused the actor
to select the waiting Demand. The second Task completed entirely in side. This
is the working control for MILESTONE-5:

```text
Task A completed -> completion attention -> Task B created -> Task B completed
```

As in MILESTONE-3, the receipt was taken while the main thread was still active,
so the second terminal Demand had not yet acknowledged its new terminal
revision. The state was not used to claim final checked-revision acceptance.

### MILESTONE-5 — waiting Demand after cancellation

- **Actor/thread:** PM `act-pm-cdcd10006b59` /
  `019f7f08-221f-7b60-a251-dcf49447c655`
- **Messages:** unfulfillable repository read `msg-770169226581`; bounded
  waiting Demand `msg-1bbff4e176b6`
- **Maximum active Tasks:** one
- **Observation window after cancellation:** 102 seconds, no corrective input

Exact result:

```text
Demand A revision 1 checked
-> Task A side_processing
-> Demand B arrives and is checked while Task A is active
-> Task A parent_processing
-> Task A canceled: required file verified absent
-> no completion/cancellation source frame
-> main thread idle
-> Demand A remains live
-> Demand B remains live
-> no Task B exists
```

Task A `task-demand-900bfed0b397` recorded the complete legal cancellation
lifecycle and cleaned its side lease. Both Demands remained revision 1,
`checked_revision=1`, `terminal=null`. Daemon had no error; the later
`task_sys_progress_check` result was `ignored`.

The baseline source at the time matched the runtime evidence: `completion_instruction` accepts
only `status == completed` and emits only a `task_sys.completion_frame`. A
canonical cancellation has no Task-owned parent attention and therefore cannot
ask the actor to reconcile the canceled source or select another already
checked live Demand.

### Cleanup

Every expanded-run actor was stopped and deleted. Actor directories, App Server,
daemon, broker, side leases, and sockets were absent afterward. The two
pre-existing market actors retained the same status, health, and main thread
ids. The one manually started Web process was stopped after the matrix. No
environment reset or direct canonical-state deletion was used.

The first harness attempt never created an actor because Python's HTTP client
routed localhost through the configured proxy and received 502. Setting
`NO_PROXY/no_proxy` for `127.0.0.1,localhost` corrected the acceptance harness.
This was an orchestration failure, not product evidence.

## 7. Consolidated system picture

The pressure runs now distinguish working behavior from missing lifecycle
attention:

| Task exit or transition | Runtime result | Source/queue attention |
| --- | --- | --- |
| side calls `close` | works; completion and cleanup recorded | works through completion frame |
| side calls `need_parent`, parent calls `close` | works; same Task id and clean handoff | works through completion frame |
| parent turn ends while Task remains parent-processing | covered by current parent Progress Check | prompt-driven decision available |
| side thread becomes idle without lifecycle action | Task remains side-processing indefinitely | missing in baseline |
| side or parent calls `cancel` | canonical Task cancellation and cleanup work | missing in baseline |

Demand behavior under the working exits is healthy in this matrix:

- independent Demands remain independent;
- an explicit supplement is absorbed and provenance is preserved;
- an equivalent Demand is marked duplicate without duplicate execution;
- Task creation is actor-scoped and sequential, with maximum active count one;
- a supplement arriving after Task creation is not hidden by the Task snapshot;
- normal Task completion can continue with an already checked waiting Demand.

The two failures share one lifecycle-attention problem statement, while the
side failure also exposed an older thread-construction defect:

> Task Sys does not provide actor attention for every lifecycle boundary that
> requires a semantic next decision, and the old side lifecycle can prevent the
> side actor from running at all by inheriting unfinished parent protocol state.

This remains compatible with prompt-driven lifecycle management. The missing
behavior is attention/check coverage, not automatic program-rule completion or
automatic Demand mutation.

## 8. Phase 4 entry decision

Do not begin Phase 4 implementation yet. First close these two Phase 3 runtime
gaps with the smallest owner-correct design and RED proof:

1. a fresh isolated side thread that becomes idle while its Task remains
   `side_processing` must produce a bounded prompt-driven progress decision for
   that same Task;
2. a terminal canceled Demand-sourced Task must produce actor attention that
   reconciles its source Demand and may select one already checked live Demand.

The repair must not add automatic Task status changes, automatic Demand
terminalization, a scheduler, a retry worker, Demand/Task imports, or business
logic to the generic daemon. After focused proof, rerun MILESTONE-1 side omission
and MILESTONE-5 cancellation/waiting scenarios with fresh real actors. Phase 4
can proceed when both converge with maximum active count one and clean runtime
teardown.

## 9. Repair acceptance

The closeout repair replaced the pre-existing side fork path with one fresh
isolated ephemeral `thread/start`, mapped exact leased side `idle` and main
`turn_completed` to the same processor-aware Task Progress Check owner, and
replaced completion-only attention with one completed/canceled Task outcome
frame. Demand Sys and Task Sys remain independently owned; only the actor skill
composes their actions, while generic daemon code projects generic thread
status without product semantics.

### 9.1 Side omission recovery

- **Actor/main:** `act-test-106f08fa528f` /
  `019f7f5e-3362-79e1-ab5d-f199a78dd7ee`
- **IM/Demand/Task:** `msg-2634a1971558` /
  `demand-0645a210d719` / `task-demand-451ec99a9a31`
- **Side thread:** `019f7f5e-d5df-7c13-a404-bb829df94023`
- **Runtime:** installed real `codex-cli 0.144.6`

The first side frame deliberately yielded without `close`, `need_parent`, or
`cancel`. The daemon observed exact-side `thread/status/changed: idle`; the Task
handler returned `handled`, submitted one Progress Check to the same side
thread, and updated the lease turn id. The actor then closed the same Task. The
Task completed, its source Demand reached completed revision/check 2/2, the side
lease disappeared, and the main thread became idle. App Server logs contained
no unmatched custom-tool-call failure.

### 9.2 Cancellation continues an already checked waiting Demand

- **Actor:** `act-test-d6b1f6d02993`
- **Inputs:** A `msg-0395d15c7851`; B `msg-e9e5e7c8954c`
- **A:** Demand `demand-f1fd92da58e9`; Task
  `task-demand-6a435f828b16`
- **B:** Demand `demand-7494d47f4491`; Task
  `task-demand-f8ecfea2ffdd`

Observed order:

```text
Task A side_processing
-> Demand B captured and checked, no Task B
-> Task A parent_processing
-> Task A canceled
-> Demand A canceled and acknowledged at revision 2
-> Task B side_processing
-> Task B completed
-> Demand B completed and acknowledged at revision 2
-> main idle, no side lease
```

Maximum active Task count was one. Demand B's terminal evidence preserved the
outcome frame exactly:

```json
{"type":"task_sys.task","ref":{"task_id":"task-demand-f8ecfea2ffdd"}}
```

The expanded acceptance first exposed two additional composition-contract
gaps: canceled Demand revision 2 was not always acknowledged, and the Demand
complete tool schema advertised only `ref.id|key`, causing the actor to rewrite
`ref.task_id`. Both were closed systemically: every source-owner mutation must
acknowledge its exact returned revision, and Demand completion now exposes the
current Task evidence identity without adding a runtime Demand-to-Task import.

### 9.3 Cleanup and decision

All diagnostic and acceptance actors created by this work were stopped and
deleted. Their instance directories, processes, sockets, and side leases were
absent. The pre-existing market actors `act-market-645c3ea1fe37` and
`act-market-8164b055c113` remained active and healthy on their original main
thread ids. The already-running Web process was reused and left unchanged.

Both formerly failing lifecycle boundaries now converge under real IM input and
real actor execution. A final-code smoke after removing the concrete Demand API
name from the Task runtime prompt used actor `act-test-9d5b060248da`, Demand
`demand-1cefe256f4ee`, and Task `task-demand-c1dae3cdf791`; it reached completed
revision/check 2/2 with exact `ref.task_id`, main idle, and no daemon error.
Phase 4 entry is unblocked.

### 9.4 Independent-review hardening and reacceptance

Independent code review after the first repair acceptance found three
implementation gaps that the prior real scenarios had not forced:

- `awaiting_parent` was a legal cancel state but recorded no outcome processor,
  so the Task could be durably canceled before outcome construction failed;
- side `turn/start` preceded lease registration, leaving a fast-idle
  notification window;
- Progress Check self-turn suppression lived only in one handler object's
  memory and disappeared on daemon restart.

These were systemic boundary gaps, not input-specific failures. The repaired
model now makes `awaiting_parent` cancellation side-owned until parent
acceptance, makes the lease visible as `starting` before work begins, atomically
claims `work -> progress_check_pending -> progress_check`, and stores the
parent source/submitted turn pair as an opaque daemon handler checkpoint. The
creator's single post-start status read uses the same side claim when the first
work turn already became idle. There is no polling loop, retry worker, or
generic-daemon Task branch.

Fresh real acceptance:

- **Actor/main:** `act-test-a80d1f6a2299` /
  `019f7f88-b171-7271-805e-026769de0c6a`
- **IM:** `msg-41a0e2b6ca3d`
- **Demand:** `demand-55e9021dc904`
- **Task:** `task-demand-df7ed57f4653`
- **Side:** `019f7f89-c0ed-7281-9302-96eab964d3ae`
- **Runtime:** installed `codex-cli 0.144.6`

The IM explicitly required the first side work turn to yield without a Task
action. The side lease appeared with `turn_kind=work`; the resulting idle event
produced exactly one `task_sys_progress_check: handled` and advanced the lease
to `turn_kind=progress_check`. Subsequent check-turn idle events were
`ignored`. The same Task completed, the Demand reached terminal revision 2 and
`checked_revision=2`, and its evidence remained exactly:

```json
{"type":"task_sys.task","ref":{"task_id":"task-demand-df7ed57f4653"}}
```

At quiescence the main thread was idle, daemon `last_error` was null, and
`side_threads` was empty. The actor was stopped and deleted; its instance path
and Web cookie were removed. The two baseline market actors remained active,
healthy, and on their original thread ids. This reacceptance keeps Phase 4
entry unblocked.

### 9.5 Second-review failure atomicity

A second independent review accepted the normal lifecycle path but found three
exceptional transitions where external App Server effects and local persistence
were not failure-atomic:

- a missing starting lease was treated as completed consumption without
  rereading canonical Task ownership;
- setup failure after a returned side turn id removed the lease and retried
  without first proving the exact processor had stopped;
- side and parent Progress Check receipt-persistence failures could lose the
  durable fact needed to prevent a second external submit.

These are again systemic boundary problems, not Demand- or input-specific
cases. The repair uses one rule: retry only after the external effect is proven
absent or precisely reversed. It records no new Task status and adds no retry
worker. The lifecycle owner exposes exact effect facts, Task Sys interprets
them, and generic daemon state remains an opaque checkpoint store.

The direct repair suite passed 59 tests / 9 subtests. The affected changed-test
batch passed 233 tests / 750 subtests, run id
`a2ac7b92d0cd4e4aadf4aa675534676e`. A broader actor/daemon/Task neighbor batch
passed 347 tests / 536 subtests, run id
`91efd0c14286456f87a581dbb6e77356`. The final all-changed-test batch passed
272 tests / 1041 subtests, run id `6ec77edfe8f14708ad9dc5b55635f014`.

Fresh real acceptance used actor `act-test-0e701ecd5ae7`, main thread
`019f7fa1-a071-7ef3-b5a1-6574dda97872`, and installed `codex-cli 0.144.6`.
Initial IM `msg-9e5f95f3d76a` produced Demand `demand-7e9811bcedfd`, Task
`task-demand-93f5ad573c36`, and exactly one handled side Progress Check after the
first side turn deliberately omitted a lifecycle action. The first parent
frame legitimately closed after its work completed; the actor correctly kept
the Demand live because that run had not met the requested parent-check
cadence.

Supplemental IM `msg-00234c7d3d8d` was then absorbed into the same live Demand,
which advanced to revision 2. Exactly one new Task
`task-demand-5a03f0a5385f` handled the remaining two-phase work. Its first
parent turn retained `in_progress.parent_processing`; daemon handler state was
persisted as:

```json
{
  "processor": "parent",
  "task_id": "task-demand-5a03f0a5385f",
  "source_turn_id": "019f7fa6-d78d-7f92-a522-4e603f234d26",
  "status": "submitted",
  "submitted_turn_id": "019f7fa7-0ff2-7512-ba7e-a5a207776e7a"
}
```

The submitted check turn closed the same Task in parent. Its own completed
notification was ignored, not resubmitted. The source Demand completed at
revision/check 3/3 with exact evidence
`{"type":"task_sys.task","ref":{"task_id":"task-demand-5a03f0a5385f"}}`.
At quiescence the main thread was idle, `side_threads` was empty, daemon
`last_error` was null, and runtime logs had no failed handler, unmatched tool
call, traceback, or exception. The actor was stopped/deleted, its instance
directory disappeared, the temporary Web listener was stopped, and the two
baseline market actors remained healthy on their original main thread ids.
Final independent static re-review returned **APPROVE** with no Critical,
Important, dual-track, generic-daemon business coupling, or retired live-path
finding. Phase 4 entry is unblocked.
