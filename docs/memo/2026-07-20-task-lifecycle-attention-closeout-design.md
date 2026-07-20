# Task Lifecycle Attention Closeout Design

**Date:** 2026-07-20

**Status:** second-review repair accepted with focused and real-actor evidence

**Baseline:** `c54c65c3ccaae32f72e2b7f8aac1af20314e4d82`

**Evidence:** `docs/memo/2026-07-20-demand-task-real-actor-pressure-test-memo.md`

## 1. Goal

Close two escaped Task lifecycle attention gaps before Phase 4:

1. a side processor can become idle while leaving the same Task permanently
   `in_progress.side_processing` when the actor omitted `close`, `need_parent`,
   or `cancel`;
2. a canceled Demand-sourced Task receives no source reconciliation attention,
   so its source Demand and already checked waiting Demands can remain live with
   no active Task and no actor turn.

The accepted invariant is:

> Whenever Task execution yields control and another actor judgment is required,
> Task Sys must produce one bounded actor attention for the same canonical Task.

Task status never changes merely because a turn ended or attention was sent.
Demand state never changes without an actor action.

## 2. Alternatives

### 2.1 Add one side callback and one cancellation callback — rejected

This fixes the two observed examples but preserves separate completion,
cancellation, side, and parent concepts with no completeness rule. The same gap
can recur at the next lifecycle boundary.

### 2.2 Add a generic workflow/retry engine — rejected

The system has one concrete lifecycle and one actor. A scheduler, event bus,
retry worker, or generic policy engine would move business truth away from Task
Sys and violate the current SHARP boundary.

### 2.3 One Task lifecycle-attention contract with two concrete producers — selected

Task Sys directly handles two facts:

```text
processor yielded while Task remains active
  -> Task Progress Check

Demand-sourced Task became completed or canceled
  -> Task Outcome Check
```

Both checks are prompts for actor judgment. They do not introduce a new Task
status, Task object, queue, or automatic Demand transition.

## 3. Target behavior

### 3.1 Processor-aware Progress Check

The Task-owned daemon handler subscribes to the two generic App Server facts
that the installed runtime actually exposes for its processors:

```text
completed main-thread turn
  + actor-owned Task is parent_processing
  -> submit parent Task Progress Check

idle registered Task side thread
  + lease belongs to exact actor/main/task
  + Task is side_processing
  -> submit side Task Progress Check to the same side thread
```

The side check contains the same Task id, source snapshot, canonical status,
last lifecycle event, and the leased side turn identity. It requires the actor to
choose `close`, `need_parent`, `cancel`, or continue bounded side work.

For parent, the source and submitted turn ids are stored in an opaque generic
daemon handler checkpoint. A new handler process therefore ignores both replay
of the already-consumed source and completion of its own submitted check turn.
For side, the lease carries one current turn kind. Only `work` can atomically
claim `progress_check_pending`; successful submission advances it to
`progress_check`, which remains ineligible for another check across process
restart. This prevents an unbounded prompt loop. A repeated omission remains
visible as an unresolved active Task instead of being silently auto-mutated.

Unregistered side threads, wrong actor/task ownership, non-idle side states,
non-completed parent turns, and terminal or wrong-processor Tasks are ignored.
Generic daemon code projects only generic thread/turn fields; it does not read
Task state or side registries.

### 3.2 Isolated side-thread creation

Real Codex diagnostics established that an ephemeral side thread does not emit
`turn/started` or `turn/completed`; it exposes processor yield as
`thread/status/changed` with `status.type=idle`. They also established that
forking while the parent is inside `task_sys.create` copies the still-unmatched
custom tool call into the side history, which makes every side turn fail with
`Custom tool call output is missing`.

The single current side creation path is therefore:

```text
fresh ephemeral thread/start
  + isolated side developer instructions
  + explicit workspace, permission, model, and effort
  -> register starting lease before work begins
  -> turn/start self-contained side frame
  -> atomically bind exact work turn id
  -> read active/idle status once
```

The order is part of the contract. An idle notification that races ahead of the
work turn binding sees `starting` and cannot create a check. After binding, the
single status read observes a fast-idle turn and submits through the same
atomic check claim used by the daemon. No notification replay, polling loop, or
case-specific retry is required. If the side actor terminalizes or hands off
and consumes its lease before `turn/start` returns, creation reports the lease
as consumed instead of retrying an already-finished Task.

Side frames are already self-contained. Parent history, a boundary injection,
and `thread/fork` add no required product information and are removed from the
live code and test surfaces.

### 3.3 Terminal Outcome Check

Replace the Phase 3 completion-only contract:

```text
completion_instruction
task_sys.completion_frame
completion_attention
```

with one current contract:

```text
outcome_instruction
task_sys.outcome_frame
outcome_attention
```

The outcome frame is valid only for a terminal Demand-sourced Task and contains:

```json
{
  "kind": "task_sys.outcome_frame",
  "task_id": "task-demand-...",
  "status": "completed | canceled",
  "source": {
    "type": "demand",
    "ref": {"demand_id": "demand-...", "basis_revision": 1}
  },
  "evidence_ref": {
    "type": "task_sys.task",
    "ref": {"task_id": "task-demand-..."}
  },
  "outcome": {"type": "completion | cancellation", "...": "..."}
}
```

`completed` requires a completion result; `canceled` requires a cancellation
result. The frame never reads or copies current Demand state.

The parent actor rereads the latest Demand and decides:

- for completion, whether the latest Demand is satisfied and should complete;
- for cancellation, whether the Demand should cancel, revise for a later
  attempt, or remain live;
- after reconciliation, whether to select one other live Demand under the
  existing single-active rule.

Close and cancel persist Task terminal truth before outcome submission. Outcome
submission failure is explicit feedback and never rolls Task status back. A
retry of the same terminal action may resubmit the same idempotent outcome
attention. Non-Demand Tasks emit no outcome frame.

## 4. Ownership and dependencies

| Owner | Change | Must remain absent |
| --- | --- | --- |
| Task domain | validate terminal Task and construct opaque outcome instruction | Demand import/read/mutation |
| Task actor tool | submit outcome after `close` and `cancel`; expose exact feedback | copied Demand policy |
| Task runtime adapter | render/submit outcome and processor-aware checks | canonical Task/Demand state |
| Side lifecycle owner | create one fresh isolated ephemeral thread; own starting/work/check turn-kind lease transitions | inherited parent history, fork/boundary dual path |
| Task daemon adapter | map generic parent completion or side idle notifications to exact Task processor | generic-daemon product branching |
| Actor skill | explain outcome reconciliation and current selection rule | automatic decision or state truth |
| Generic daemon | deliver notifications and actor inputs; persist opaque per-handler checkpoints | Task status/source/frame semantics or checkpoint interpretation |

Demand Sys is unchanged. Generic daemon business boundaries, mailbox, and
client are unchanged. Its state contract gains only opaque per-handler
checkpoint storage; Task turn meaning remains entirely in the Task adapter.
Trigger normalization adds only the generic `thread_status` projection used by
any application-owned adapter.

## 5. Forward replacement

This is a direct cutover. Active code, contracts, tests, skills, and current
architecture docs retain no completion-only names or parent-only Progress Check
API. Historical memos may preserve prior evidence.

No aliases, dual payload fields, fallback frame readers, or compatibility
branches are permitted.

## 6. Error handling

- Missing or invalid side lease: ignore unrelated notification; do not guess a
  Task.
- Starting side lease: ignore idle notification until exact work binding; the
  creator's one post-start status read closes a fast-idle race.
- Progress-check submission failure: handler returns failed; Task remains in its
  canonical active status. A side claim rolls back only when submission is
  proven not attempted; uncertain submission remains `progress_check_pending`.
- Outcome submission failure: tool returns `outcome_attention.status=failed`;
  terminal Task remains durable.
- Side check self-yield: reject it durably because its current lease turn kind
  is `progress_check`.
- Parent check self-yield or notification replay: reject it durably through the
  opaque handler checkpoint. The checkpoint is written as `submitting` before
  external input and finalized with the receipt turn id afterward.
- Post-start side setup failure: retry only after exact-turn interruption and
  lease removal both succeed; otherwise record an observable non-retryable
  runtime failure.
- Missing starting lease after `turn/start`: accept only after canonical Task
  status has already left `side_processing`; otherwise interrupt the exact turn
  and record `side_lease_consumed` failure.
- Terminal replay: resubmit the same current outcome instruction without a new
  Task or state transition.

## 7. Verification

Automated RED/GREEN must directly prove:

1. a registered side idle signal submits a check for the exact
   side-processing Task without creating another Task;
2. wrong/unregistered/terminal side notifications are ignored;
3. side creation uses one fresh ephemeral `thread/start` without inherited
   history or a boundary injection, and the check returns to that same thread;
4. completed and canceled Demand Tasks construct the same strict outcome frame;
5. `close` and `cancel` both submit outcome attention; failure preserves their
   respective terminal status;
6. non-Demand terminal Tasks do not submit outcome attention;
7. completion-only and parent-only live terms are absent from current surfaces;
8. Demand/Task/daemon architecture boundaries remain enforced.
9. `awaiting_parent` cancellation records `processor=side` and still returns an
   explicit outcome-attention result;
10. a lease is visible as `starting` before side work begins, fast idle is
    reconciled once, and a newly constructed handler cannot resubmit its own
    parent or side check.

Real CLI acceptance uses fresh actors and the installed Codex runtime:

- side recovery: a bounded side-only queue must converge even when the first
  side turn omits its lifecycle action and the follow-up check is observed;
- cancellation continuation: while Task A is active, Demand B is captured and
  checked; after Task A cancels, an outcome frame must reconcile A and allow B
  to start, with maximum active count one;
- all created runtime resources are removed and pre-existing actors are
  unchanged.

## 8. Independent-review hardening

The first acceptance exposed the intended product loop but independent review
found three completeness gaps in the implementation boundary:

1. canceling a Task while `awaiting_parent` persisted `canceled` without an
   outcome processor, so outcome construction could fail after the durable
   write;
2. side work began before its lease existed, so a very fast idle notification
   could be ignored permanently;
3. parent/side check recursion suppression relied on one handler object's
   memory and did not survive daemon restart.

The repair is systemic and owner-correct: `awaiting_parent` cancellation is the
side-owned outcome before parent acceptance; side lease turn kinds plus an
atomic compare-and-set make the work/check claim singular; generic daemon state
persists an opaque parent checkpoint. The outcome helper also reports frame
construction failure explicitly instead of turning a durable terminal write
into an env-tool dispatch failure.

A second independent review then pressured failure atomicity rather than the
normal path. It found that a vanished starting lease was accepted without
checking Task ownership, that setup failure after a successful `turn/start`
could retry before stopping the returned turn, and that an external Progress
Check submit followed by local persistence failure could become retryable.

The second repair adds no case router. It establishes one cross-boundary rule:
local retry is legal only when the external effect is proven absent or has been
precisely reversed. The side lifecycle now returns explicit retry/cleanup and
submission facts; Task runtime rejects an unowned consumed lease using
canonical status; side uncertain submission stays durably pending; parent
writes `submitting` before input and records the receipt afterward. These are
the same invariants for every Task and input source.
