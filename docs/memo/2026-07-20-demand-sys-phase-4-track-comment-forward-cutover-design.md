# Demand Sys Phase 4 Track Comment Forward Cutover Design

**Date:** 2026-07-20

**Status:** implemented and accepted; product loop proved; live-data gate
resolved by user-side environment cleanup; cleanup incident documented

**Baseline:** `fea-daemon` at
`213d980c29cc1f6a247375ede06d7f74de676ea3`

**Scope:** replace the last need-bearing inbound-to-Task route with
Track-comment-to-Demand intake, then remove the retired external Task ingress
model completely

**2026-07-21 execution note:** The code cutover and focused automated proof are
complete. A real PM -> Track comment -> Test Demand -> actor-selected Task run
also passed twice. The production-state probe then found existing non-Demand
Task records and the planned role cleanup was not actor-scoped. The user has
since cleaned the actor environment: the public CLI now reports zero instances,
the live Task store contains zero records, the named actor Demand/Task lists are
empty, and the acceptance Track is absent. This resolves the live-data gate
without adding a compatibility path. Section 16 preserves the cleanup incident
and the exact limits of what the post-cleanup observation proves.

## 1. Goal and acceptance sentence

Phase 4 makes Demand the only intake owner for every currently implemented
need-bearing inbound source:

```text
IM message ────────┐
                   ├─> Demand capture -> actor Demand Check -> optional Task
Track comment ─────┘

actor self-demand ───> Demand action ───────────────────────> optional Task
```

The acceptance sentence is:

> A valid Track comment addressed to an active BuddySwitch actor durably creates
> or replays exactly one actor-owned Demand and requests Demand attention even
> while another Task is active; only the actor may subsequently create one
> Demand-backed Task through `task_sys.create`, while Track and Task code have no
> direct creation path, Demand Sys and Task Sys do not import or mutate each
> other, and the generic daemon remains product-neutral.

## 2. Current bottleneck

Phase 2 cut IM intake from Task to Demand. Phase 3 completed actor-mediated
Demand-to-Task coordination and one-active-Task lifecycle handling. One current
source still bypasses the Demand layer:

```text
track.comment.added
  -> TrackCommentAddedHandler
  -> task_sys_ingress.ingest_track_comment
  -> task_sys.ingest
  -> Task start_side
```

This path has three product defects:

1. a Track comment is forced into execution immediately instead of becoming a
   durable need that the actor can compare, absorb, structure, or defer;
2. a different active Task rejects the comment at the Task single-active gate,
   so the need itself is not durably accepted;
3. Task Sys retains a generic external `ingest` API and non-Demand behavior even
   though actor-created Demand-backed Tasks are now the intended current model.

The bottleneck is therefore one cutover, not a new scheduler, event bus, source
registry, or relation engine.

## 3. Repository facts

The design is grounded in the baseline implementation:

- `tools/launcher/track_comment_added_handler.py` validates the target, source
  payload, Track comment row, reply target, and active Track, then calls Task
  ingress directly.
- `tools/launcher/task_sys_ingress.py` has one remaining production consumer and
  one remaining function: `ingest_track_comment`.
- `scripts/env/domain/task_sys.py::ingest` still accepts a generic
  `source/actor_target/context` envelope. Current tests use it as a fixture API,
  which keeps the retired production model discoverable.
- `scripts/env/domain/task_sys.py::create` already owns the required actor path:
  exact DemandRef, self-contained execution brief, actor lock, source replay,
  one-active gate, and one side-first lifecycle.
- `tools/launcher/demand_sys_daemon_adapter.py::capture_inbound` already owns the
  source-neutral Demand capture plus pending-attention decision used by IM.
- `tools/launcher/im_wake_handler.py` is the accepted reference flow: the source
  handler validates and reads its source, maps one deterministic Demand input,
  and calls the Demand-owned adapter.
- `buddyswitch/skills/shared/task-management/SKILL.md` already owns the actor's
  two-pass Demand check, one-Task selection, and Task-outcome reconciliation.
- `tools/launcher/instance_daemon.py` explicitly composes the IM, Track, Browser,
  and Task handlers. No generic daemon module knows their product semantics.
- The live workspace contains zero Task, Demand, Track, or Track-comment object
  files at planning time. No runtime-data migration or compatibility read path
  is justified by the current baseline.

Historical memos may retain old names. Current code, tests, skills, and
`docs/arch` may not.

## 4. Alternatives

### 4.1 Full forward cutover — selected

Change Track comment handling to use the existing Demand capture adapter,
delete `task_sys_ingress.py`, delete `task_sys.ingest`, make Task creation
Demand-only, migrate tests to the current create contract, and mechanize the
absence of the retired route.

This is the smallest change that leaves one current truth.

### 4.2 Change only the Track handler — rejected

The product path would appear fixed, but the generic Task ingest entrypoint and
its tests would remain callable and taught as supported behavior. That is a
hidden dual track, not a completed replacement.

### 4.3 Add a generic inbound-to-Demand mapper or registry — rejected

IM and Track have different source validation and read rules. A generic mapper
would either duplicate those rules or become a source-type switch. Two real
source handlers already share one narrow Demand capture operation; no new
framework is needed.

## 5. Target architecture

```text
Track tool
  -> durable Track comment
  -> generic cross-actor signal: track.comment.added
      |
      v
TrackCommentAddedHandler                       [Track/source owner]
  - validate exact target and signal source
  - read exact comment/reply/Track
  - enforce intended-recipient and active-Track rules
  - map one deterministic Demand input
      |
      v
DemandSysDaemonAdapter.capture_inbound         [Demand intake adapter]
  - Demand domain create/replay
  - Demand domain check pending revisions
  - generic DaemonRuntime.input_actor([DEMAND CHECK]) when pending
      |
      v
parent Actor + task-management skill           [semantic bridge]
  - two-pass Demand matching
  - revise/absorb/relate/acknowledge as judged
  - inspect one-active Task state
  - optionally task_sys.create(DemandRef, execution brief)
      |
      v
Task Sys                                       [execution owner]
  - Demand-backed create/replay only
  - one active Task
  - side -> awaiting_parent -> parent lifecycle
  - terminal outcome attention to Actor
```

There is no Track-to-Task call, Demand-to-Task callback, automatic source
matching, or daemon product branch.

## 6. Ownership and boundaries

| Owner | Owns in Phase 4 | Must not own |
| --- | --- | --- |
| Track handler | signal validation, Track/comment reads, recipient check, deterministic Demand materialization | Demand lifecycle, Task creation, actor matching |
| Demand adapter | capture/replay, durable pending-attention policy, fixed Demand Check input | Track reads, Task calls, matching decisions |
| Demand Sys | need truth, revision, organization, check state, terminal lineage | Task lifecycle or selection |
| Actor + task-management skill | semantic matching, relation/action choice, one-Task selection, source reconciliation | canonical storage or copied lifecycle rules |
| Task Sys | Demand-backed Task creation, one-active gate, lifecycle, outcome receipt | inbound events, Track reads, Demand mutation |
| Generic daemon | signal/trigger dispatch and actor input mechanics | Track, Demand, or Task meaning |

Allowed dependency direction:

```text
Track handler -> Track domain/repositories + Demand daemon adapter
Demand daemon adapter -> Demand domain + DaemonRuntime.input_actor
Actor workflow -> independent Demand and Task actor actions
Task adapter -> Task domain/runtime + generic actor/runtime primitives
```

Forbidden dependency direction:

```text
Track handler -> Task Sys
need-bearing inbound handler -> task_sys.create/ingest/runtime
Demand implementation -> Track or Task implementation
Task implementation -> Track, inbound, or Demand implementation
generic daemon -> Track, Demand, or Task product tokens/rules
```

## 7. Exact Track comment Demand contract

After validating the event and reading the canonical comment row, the Track
handler maps exactly:

```json
{
  "intake_key": "track.comment.added:track-export-retry:comment-a12b34c56d78",
  "description": "Add CSV export retry guidance.",
  "detail": "Track comment on track-export-retry (comment comment-a12b34c56d78, thread comment-a12b34c56d78):\nAdd CSV export retry guidance.",
  "source_refs": [
    {
      "type": "track.comment.added",
      "ref": {
        "track_id": "track-export-retry",
        "comment_id": "comment-a12b34c56d78",
        "thread_id": "comment-a12b34c56d78"
      }
    }
  ]
}
```

The mapping deliberately excludes mutable Track title, outcome, state, and
`now` fields. Replaying the same immutable comment after a Track edit must not
turn a safe replay into `DemandIntakeConflict`.

The signal source identity must match `comment.by_identity_id`. The source role
is validated as part of the generic signal route but is not copied into Demand
content. The canonical comment remains the source of authorship truth.

`source_refs` are provenance and a route to optional source inspection. They do
not imply `parent_id`, `depends_on`, duplicate, absorption, or any other Demand
relation. The actor makes that judgment using the same two-pass check used for
IM and actor-created Demands.

When more thread context is required, the actor may use the exact Track id with
current Track tools. The inbound adapter does not copy a mutable Track snapshot
into Demand state.

## 8. Task creation after cutover

The only creation contract is:

```text
task_sys.create(
  demand_ref={demand_id, basis_revision},
  execution_brief={description, detail}
)
```

`task_sys.ingest` and `task_sys_ingress.py` are deleted. The private creation
owner receives only a normalized DemandRef and execution brief. It still stores
an explicit source snapshot:

```json
{
  "source_type": "demand",
  "source_ref": {"demand_id": "demand-a12b34c56d78", "basis_revision": 1}
}
```

These fields remain the one current source-snapshot contract used by Task
frames and outcome evidence. `source_type` is a fixed invariant, not a live
discriminator. Runtime and read projections reject malformed/non-Demand Task
records instead of returning a null compatibility projection or silently
executing another source type.

The following behavior is removed:

- generic source/context envelope ingestion;
- Track-sourced Task ids and records;
- non-Demand terminal Tasks that skip outcome attention;
- tests using production `ingest` as a fixture shortcut;
- Task runtime rendering of arbitrary source objects.

No replacement alias, internal compatibility wrapper, old-record fallback,
dual schema, feature flag, or one-time live migration is added. If nonzero
pre-cutover Task data appears before implementation, implementation pauses for
an explicit data decision instead of adding compatibility implicitly.

## 9. Actor workflow adjustment

The existing Demand Check and Task Selection Rule remain canonical. One source
reading clarification is added:

1. `demand_sys.check` returns pending descriptions and the live index;
2. plausible candidates are loaded with `demand_sys.get_many`;
3. a Track-comment source ref may be followed with Track reads only when the
   stored Demand detail is insufficient;
4. Track thread structure remains provenance/context, not an automatic Demand
   relation;
5. the actor applies necessary Demand actions and acknowledges exact revisions;
6. if no Task is active, it may create at most one Task from one live Demand.

No source priority or queue order is introduced.

## 10. Failure semantics

### 10.1 Demand persists, actor input fails

The handler reports failure, but the Demand remains pending. Replaying the same
signal returns the same Demand and retries attention while its revision remains
unchecked. No Task is created as fallback.

### 10.2 Same signal is delivered twice

The actor-scoped `intake_key` and exact content replay return the same Demand.
At most one attention input is requested per handler attempt; Task creation
remains an independent actor decision and is idempotent by DemandRef plus brief.

### 10.3 A Task is already active

Demand capture succeeds because it does not consult Task Sys. The actor checks
the new Demand, sees the active Task, and does not create another. The need
remains durable for later selection or may be absorbed/revised immediately.

### 10.4 Signal source does not match the comment author

The Track handler rejects before Demand capture. No Demand or Task state
changes.

### 10.5 Invalid target, missing/mismatched row, or archived Track

The Track handler rejects before Demand capture, preserving current source
authorization behavior.

### 10.6 Demand capture rejects or storage fails

The handler reports failure and creates no Task. The source comment remains the
durable source fact and normal signal retry may attempt the same intake again.

## 11. Forward-only replacement inventory

Delete:

- `tools/launcher/task_sys_ingress.py`;
- `scripts/env/domain/task_sys.py::ingest`;
- generic source/context normalization and ingest rejection helpers;
- non-Demand outcome skip behavior;
- tests that preserve Track/direct external Task creation;
- current architecture prose that says Track owns Task lifecycle requests or
  remains on a Task path.

Replace:

- Track handler Task execution with Demand capture and actor attention;
- generic Task test fixtures with exact Demand-backed `task_sys.create` fixtures;
- permissive runtime/read source handling with the exact Demand source contract;
- the old direct-input retirement test with an external Task-ingress absence
  guard.

Current negative guards may name retired terms only to prove absence. Historical
`docs/memo` files remain historical evidence and are excluded from residue
claims.

## 12. Verification design

The shortest sufficient evidence stack is:

1. **RED/GREEN Track owner proof:** valid mention/reply captures exact Demand,
   replay is idempotent, active Task does not block capture, source mismatch
   rejects, and no Task record is written by the handler.
2. **Demand adapter reuse proof:** pending Demand requests the fixed Demand Check;
   input failure leaves durable pending state; checked replay does not wake.
3. **Task owner proof:** create/replay/conflict/concurrency and every lifecycle
   transition use the Demand-backed create contract only.
4. **Runtime/contract proof:** side, parent, progress, outcome, actor tool, CLI,
   and Web projections accept one exact Demand source and no null non-Demand
   path.
5. **Architecture/replacement proof:** Track has no Task import/call, Task has no
   inbound/Track/Demand implementation dependency, generic daemon has no
   product branch, and the retired ingress file/API are absent.
6. **Affected focused batch:** run every test whose fixture changes from ingest
   to create, plus Track signal delivery, instance-daemon composition, Demand
   workflow guidance, and current public projections.
7. **Real actor milestone:** use public BuddySwitch CLI and installed Codex to
   create fresh actors, generate a real Track comment signal, observe Track ->
   Demand -> actor -> Task, add a supplemental comment, inspect organization and
   maximum active Task count, then clean only newly created resources.

`./buddyswitch-test full` is not planned. It remains reserved for an explicit
repository-wide or frozen release acceptance request.

## 13. Real actor acceptance boundary

The real run uses two fresh actors in roles that have no pre-existing instances
or role-owned data at the start of the run:

- a source PM actor creates one setup Demand/Task, then uses its parent frame to
  create one uniquely named Track and add a comment mentioning the target;
- a target Test actor receives the real `track.comment.added` signal and
  processes the resulting Demand with installed `task-management` guidance.

Required observations:

1. the source actor uses the installed real Codex runtime, not fake Codex or a
   repository override;
2. the target stores a Demand with the exact Track source ref before any Task
   creation attributed to that need;
3. no Task record has `source_type=track.comment.added`;
4. any target Task has `source_type=demand` and an exact DemandRef;
5. a second supplemental Track comment becomes another Demand and is available
   for actor absorption/revision judgment even if a Task is active;
6. actor logs show Demand Check and actor-selected Demand/Task actions; daemon
   logs contain no failed handler, traceback, or product-specific generic branch;
7. maximum target active Task count is one;
8. source/target actors, instances, role-owned Demand/Task data, and the unique
   Track/comment are removed through scoped public cleanup after verifying the
   pre-run snapshot is still otherwise unchanged.

If either chosen role has pre-existing owned data, do not run role cleanup in
the default environment. Use a clean isolated product root with the same public
CLI and installed Codex runtime, or choose an empty role pair. Never delete or
rewrite unrelated runtime objects directly.

## 14. Out of scope

- automatic Track comment thread resolution from Demand or Task completion;
- Track comment update/resolution events becoming new Demands;
- offline actor capture, startup recovery, or pending-work workers;
- generic inbound source registries, mappers, plugin systems, or event buses;
- automatic Demand relation inference or programmatic two-pass matching;
- Task queues, priorities, multiple active Tasks, or Task relations;
- automatic Demand-to-Task creation or Task-to-Demand terminalization;
- backfill of old Track comments;
- public mutation CLI or Web UI for Demand/Task/Track;
- direct TUI input becoming an inbound Demand.

## 15. Definition of done

Phase 4 is complete only when:

1. IM and Track are the two current need-bearing inbound sources and both create
   Demand before actor attention;
2. Track comment capture succeeds independently of active Task state;
3. `task_sys.create` is the only Task creation entrypoint;
4. every Task is Demand-backed and uses the existing single lifecycle;
5. Track, Demand, and Task ownership boundaries remain explicit and acyclic;
6. the generic daemon remains unaware of all three product semantics;
7. retired ingress code, tests, guidance, branches, and current-doc wording are
   absent rather than bypassed;
8. focused automated proof and the real CLI actor milestone pass with clean
   resource teardown;
9. the implementation, design, plan, and evidence are submitted together as one
   coherent change rather than fragmented plan-only commits.

## 16. Live acceptance finding and cutover gate

The repository-mounted planning paths contained zero objects, but the public
CLI actors use `/Users/chen/.codex-buddyswitch/state`. The real run proved that
this live root already contains retired Task records, including 20
`task-im-message-created-*` records. With the new one-truth read contract, a
bounded public probe now correctly rejects one such record with:

```text
task get task-im-message-created-b2f2cdf40697
-> INVALID_ARGUMENT: task.source_type must be demand
```

This is the intended forward-only behavior, but it means live cutover cannot be
accepted until those retired records receive an explicit protected data
decision. Adding a fallback reader would violate this design.

The acceptance cleanup plan also used `data cleanup --role pm/test` after
observing no active PM/Test instances. That inference was wrong: role cleanup
is historical-role-wide, not actor-scoped. It deleted 31 PM-linked and 16
Test-linked pre-existing IM message objects, while skipping the acceptance
Track comments and leaving Demand/Task/Track state untouched. The cleanup owner
performs direct deletion and exposes no transaction backup, so no unsupported
file reconstruction was attempted. This is recorded as an operational
acceptance failure, not hidden as successful cleanup.

The real product observations remain valid:

- source actor `act-pm-9744de708a81`, target actor
  `act-test-e22c5779c72e`, real `codex-cli 0.144.6`;
- Track `track-phase4-1784563031` and exact comments
  `comment-7f7fe11e152d` / `comment-a124b768152b`;
- target Demands `demand-9c63c8e133db` /
  `demand-d0140c52c3cc`, each with exact Track/comment/thread provenance;
- target Tasks `task-demand-b3332195d594` /
  `task-demand-df3ceab52686`, each with an exact DemandRef;
- every sampled target active count was at most one; both Demands ended at
  `revision=checked_revision=2` with Task evidence;
- both `track_comment_added` deliveries were handled and daemon errors remained
  null.

Both acceptance instances were stopped and deleted, with no matching process or
instance directory left. At the first acceptance boundary their durable product
evidence remained because no safe actor-scoped public cleanup existed.

The user subsequently cleaned the relevant actor environment. A read-only
post-cleanup probe observed:

- `instance list` and the PM/Test/Market role views each return zero instances;
- the authoritative live Task directory contains zero Task records, including
  zero retired non-Demand records;
- public Demand/Task lists for both acceptance actors and both former Market
  actors return empty lists;
- `track get track-phase4-1784563031` returns `NOT_FOUND`.

No Phase 4 code performed that cleanup, and no claim is made that it followed
the previously proposed exact-id archive procedure or preserved the former
live store byte-for-byte. The earlier 47-message role-cleanup incident remains
part of the acceptance record. The relevant current-state fact is narrower:
the live runtime no longer contains legacy Task data that would require a
compatibility read, migration path, or second Task model.
