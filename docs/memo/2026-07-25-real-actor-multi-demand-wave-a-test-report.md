# Real Actor Multi-Demand Wave A Test Report

Status: Wave A failed; Wave B not authorized by the review gate

Date: 2026-07-25

Design under test:
[Real Actor Multi-Demand Scenario Test Design](./2026-07-25-real-actor-multi-demand-scenario-test-design.md)

Source identity:
`5a22aeec8a830c1a75f8913c9d725f7487daefbd`

## 1. Acceptance claim and verdict

The tested claim was:

> A real Web user can add, supplement, change, separate, and withdraw multiple
> needs while BuddySwitch maintains one correct canonical Demand pool, at most
> one active Task/native Goal, evidence-based Demand reconciliation, and a
> readable Web delivery whose meaning agrees with persisted state and runtime
> logs.

Verdict: **failed at the Demand relationship boundary**.

The one-active-Task/native-Goal invariant, Task-versus-Demand completion
decoupling, latest-revision reconciliation, user-facing replies, and Actor
self-Demand creation all produced positive evidence. The run nevertheless
found both directions of Demand organization error:

1. a supplement to the same deliverable was split into a duplicate Demand;
2. an explicitly independent deliverable was merged into an existing Demand;
3. a change referring to a completed Demand was applied to an unrelated live
   Demand.

These are product-semantic failures. State, Task, Goal, reply, and terminal
evidence can all remain internally consistent while the system completes the
wrong user obligation.

## 2. Execution identity and ownership

The run used:

- isolated shared root:
  `/private/tmp/buddyswitch-real-multidemand.a2isjg/.codex-buddyswitch`;
- real BuddySwitch WebUI at `http://127.0.0.1:8880/`;
- one fresh Actor per scenario;
- one primary Agent as the sole WebUI writer;
- one read-only log observer and one read-only state auditor;
- public CLI projections plus attributable runtime and App Server logs for
  observation;
- no direct runtime object mutation;
- UI capability configuration shown as Parent `Balanced`, Side `Fast`;
- observed triage-side sampling on `gpt-5.6-luna` with `xhigh` reasoning.

Sub-agents never sent product input, controlled Goals, mutated Demand/Task
state, started or stopped Actors, or performed cleanup.

## 3. Wave A summary

| Scenario | Executed boundary | Positive evidence | Hard-stop |
|---|---|---|---|
| M1 Market | M1-1 through M1-6 | create, merge, independent create, second merge, second independent create, serial Tasks, latest-revision reconciliation, Web replies | M1-6 revised unrelated live C instead of creating a correction Demand for terminal A |
| D1 Dev | D1-1 through D1-2; Goal completed before teardown | base Demand/Task, runnable delivery, Actor self-Demand with `actor.self_requested` provenance | D1-2 created a duplicate Demand instead of merging a same-tool supplement into A |
| G2 Design | G2-1 through G2-5 | create, merge, independent create, revise, serial Tasks, latest-revision reconciliation, readable Artifacts/replies | G2-5 merged an explicitly independent state-library deliverable into A instead of creating C |

Wave B was not run. Section 4.2 of the design permits Wave B only after Wave A
has no unresolved hard failure.

## 4. M1 — Market NVIDIA scenario

Actor:

- Actor id: `act-market-3902a91aa091`
- main thread: `019f977e-65bf-77c0-81d7-b3241f4cd2e1`

### 4.1 Observed steps

| Step | Message id | Expected | Observed | Verdict |
|---|---|---|---|---|
| M1-1 | `msg-341c165372c3` | create A | created `demand-22fdfdf193c8` rev1 | pass |
| M1-2 | `msg-0f3d4b82232a` | merge A | A rev1→rev2; later parent refreshed A to rev3 after old Task evidence proved incomplete | pass |
| M1-3 | `msg-7fc62e95f959` | create B | created `demand-b65669ddb313` rev1 | pass |
| M1-4 | `msg-ba463809dced` | merge B | B rev1→rev2 with Nemotron 3 official-only fields | pass |
| M1-5 | `msg-981c89d83a5d` | create C | created `demand-bd044d8f10a9` rev1 | pass |
| M1-6 | `msg-2271dc501fce` | original plan: revise active A | A was already terminal; actual result revised C rev1→rev2 | **hard fail** |

M1-7 was not sent after the hard-stop.

### 4.2 Serial Task and reconciliation evidence

The first Task `task-demand-1ff283ae833e` bound A rev1 and completed with:

- Goal status `complete`;
- `156437` tokens;
- `390` seconds;
- Web reply `msg-341c165372c3` received by the user.

The parent did not automatically complete latest A. It recognized that A had
advanced and that the first delivery did not explicitly satisfy capability
type and official-date requirements. It kept A live, refreshed it to rev3,
and created exactly one new Task:

- Task `task-demand-16d79fa5f85b`;
- bound A rev3;
- selection reason named the only live Demand and the missing fields;
- objective required a revised artifact and an exact reply to M1-2.

After the second A Task completed, independent reconciliation completed A with:

- Task evidence `task-demand-16d79fa5f85b`;
- reply evidence `msg-9dcc0724ce22`;
- Artifact `art-2cc798bfe0`.

The parent then selected B rev2 from the complete live pool and created the
only active Task `task-demand-dc28353ade01`. No observation found two active
Tasks.

This is direct positive evidence for:

- Task completion being decoupled from Demand completion;
- reconciliation using the latest Demand revision;
- evidence-based Demand terminalization;
- serialized selection from the complete live pool.

### 4.3 M1-6 hard failure

At M1-6, A had already completed. The current architecture correctly forbids
revising or reviving a terminal Demand. The correct adaptive result was
therefore a new self-contained correction Demand that could reference A's
prior delivery without mutating A.

Instead, triage:

- listed only live Demands B and C;
- did not read terminal A;
- did not call `message.conversation`;
- decided `revise`;
- targeted C `demand-bd044d8f10a9`;
- changed C from an enterprise-procurement implications page into a
  twelve-month, company-or-regulator-confirmed analysis;
- attached M1-6 as C's second source.

The resulting Task replied to M1-6 with an opportunity/risk/watchlist
procurement analysis. The user had asked to revise the first acquisition
brief. The system then completed C with that wrong reply as terminal evidence.

The contract and state were internally consistent but semantically wrong.

### 4.4 M1 root-cause boundary

The isolated triage contract explicitly asks the side to compare the inbound
fact only with current canonical **live** Demands:

- `tools/launcher/demand_triage_handler.py:32`
- `buddyswitch/skills/shared/demand-triage/SKILL.md:21`

The side is a fresh ephemeral thread, not a parent transcript fork. It can call
`message.conversation`, but the actual M1-6 turn did not. Because A was
terminal, the forced live-only candidate pool contained only B and C.

Three layers contributed:

1. **candidate projection gap:** a referential change to a terminal Demand had
   no source-linked terminal context;
2. **model judgment error:** the model misidentified procurement Demand C as
   the “first acquisition brief” despite C's source meaning;
3. **owner validation gap:** the owner checked capability, current live
   `demand_ref`, revision, and field structure, but did not validate semantic
   correspondence between inbound fact and target Demand.

## 5. D1 — Dev schedule-manager scenario

Actor:

- Actor id: `act-dev-7725bb8c9aed`
- main thread: `019f9796-8435-7610-a435-952750db6fb4`

### 5.1 Observed steps

| Step | Message id | Expected | Observed | Verdict |
|---|---|---|---|---|
| D1-1 | `msg-e1e40a2ac1b2` | create A | created `demand-1a2537ab17f3` rev1 and one Task/Goal | pass |
| D1-2 | `msg-ec49cdf71d9b` | merge A | created duplicate `demand-25950f2c5176` rev1 | **hard fail** |

D1-3 through D1-8 were not sent.

### 5.2 D1-2 evidence

The source message said:

> 同一个基础工具补充每周重复日程和本地时区显示。

The side:

1. listed the complete live pool;
2. found only A;
3. read A in full;
4. read the exact source Message;
5. did not read the full conversation;
6. intentionally called `create`.

Its reason was that A's canonical contract limited the current scope to base
CRUD and persistence, excluded independent enhancements, and required a later
independent improvement to become a separate Demand.

The new Demand copied A's CRUD and persistence assumptions and added weekly
recurrence and local-timezone display. This left two live Demands describing
two versions of the same local application rather than one updated desired
outcome.

This finding is not a missing-candidate defect. It exposes a Demand-granularity
policy conflict:

- D1-1 asked the Actor to propose one independent future improvement after the
  base version;
- triage generalized that constraint to a later user-requested supplement;
- the scenario expected explicit “same basic tool” user scope expansion to
  update A.

The product needs one clear precedence rule distinguishing:

- a user changing the same desired deliverable;
- an Actor proposing a genuinely independent later improvement.

### 5.3 Actor self-Demand positive evidence

The base Goal completed and created:

- Demand `demand-1fa48ba00bc0`;
- description: add search/filter for locally stored schedules;
- source type `actor.self_requested`;
- source main thread
  `019f9796-8435-7610-a435-952750db6fb4`;
- source turn `26308748-5e51-4f9d-addb-cff150f37e1d`;
- no ingress receipt;
- no second active Task.

The Goal delivered a Web reply for the base app and reported browser CRUD and
refresh-persistence verification. This proves that the Actor-visible
`demand_sys.create` path and self-requested provenance work independently of
inbound triage.

## 6. G2 — Design AI research-workspace scenario

Actor:

- Actor id: `act-design-3477b16b4653`
- main thread: `019f979e-5217-7af2-bb3b-02a116be5c74`

### 6.1 Observed steps

| Step | Message id | Expected | Observed | Verdict |
|---|---|---|---|---|
| G2-1 | `msg-6e37478e126d` | create A | created `demand-1560f5d93b75` rev1 | pass |
| G2-2 | `msg-18b49ff6154e` | merge A | A rev1→rev2 with evidence-card fields | pass |
| G2-3 | `msg-689e9aad4cfb` | create B | created `demand-8fd63909617e` rev1 | pass |
| G2-4 | `msg-9cd5d19f7706` | revise B | B rev1→rev2, tablet landscape, phone removed | pass |
| G2-5 | `msg-1f2348605f50` | create C | merged state-library deliverable into A rev3→rev4 | **hard fail** |

G2-6 through G2-8 were not sent.

### 6.2 Latest-revision reconciliation evidence

The first A Task `task-demand-0a3a8bb75faa` bound A rev1 and completed while A
was already rev2. Independent parent reconciliation did not complete A. It
recorded the missing evidence-card work, refreshed A to rev3, compared A with
waiting B, and selected A again because:

- an existing Artifact and runnable preview provided continuity;
- the evidence-card fields remained unmet;
- B had not started and had no deadline.

It created exactly one new active Task:
`task-demand-40e9f577a4eb`, bound to A rev3.

This is a second cross-role proof of correct Task/Demand decoupling and grounded
selection from the full live pool.

### 6.3 G2-5 hard failure

The source said:

> 另外单独整理加载、空数据、来源失效和生成失败的状态库。

The side read:

- both live Demands A and B in full;
- the exact source Message;
- the full conversation.

It nevertheless interpreted “单独整理” as a separate section within A rather
than an independently satisfiable state-library deliverable. It called
`merge_intake` on A and extended A's canonical contract with four system
states, their triggers, feedback, recovery actions, and flow impact.

No Demand C was created. B remained correct and unchanged.

This is the opposite failure direction from D1:

- D1 over-split a same-deliverable supplement;
- G2 under-split an explicitly independent deliverable.

The two together show an unstable Demand relationship judgment boundary, not
one role-specific vocabulary mistake.

### 6.4 G2 delivery and internal error observation

The WebUI exposed readable replies and design Artifact ids, including:

- Artifact `art-1ec744174b`;
- initial preview attachment `att-f2ea0b847a`;
- evidence-card preview attachment `att-5d19f464f3`.

The second A Goal encountered one App Server `apply_patch` verification error
because an expected CSS line was not found. The Goal recovered enough to
deliver the updated Artifact replies before the Actor was stopped. This error
did not create a Task/Goal terminal contradiction, but it is not evidence that
every preview behavior was visually accepted.

## 7. Cross-scenario findings

### 7.1 Primary product bottleneck

Demand triage does not yet provide stable, explainable granularity for:

- same deliverable versus independent deliverable;
- source-linked terminal correction versus unrelated live Demand;
- user scope change versus Actor-proposed future enhancement.

This is now the bottleneck. More Wave B examples would add cost without
changing the already reproduced failure class.

### 7.2 What is working

- Every observed point maintained at most one active Task/native Goal.
- Waiting Demands did not create a second active Task.
- Task/Goal completion did not automatically complete a Demand.
- Parent reconciliation read latest Demand meaning and durable delivery
  evidence.
- Parent selection reasons compared actual live-pool facts.
- Actor self-Demand creation produced correct Actor thread/turn provenance.
- Replies were readable in the real WebUI.
- Artifact identities were visible and usable in Task/Demand evidence.
- Triage receipts settled without retry or data corruption in the three
  scenarios.
- No broker/daemon terminal error contradicted persisted product state.

### 7.3 Semantic and validation gaps

- The triage side can choose a structurally valid but semantically wrong
  target.
- `reason` is required but not owner-validated beyond being non-empty.
- A current live `demand_ref` proves authority and freshness, not semantic
  correspondence.
- Source refs are merged after the choice; they do not protect against an
  unrelated choice.
- Referential language such as “first report” needs source-linked terminal
  context or a forced conversation/history resolution rule.
- The test design's “A Goal active” timing assumption is fragile under
  human-style checkpoint pacing. When A becomes terminal first, expected
  behavior must branch to a new correction Demand rather than attempt to
  revise terminal A.

### 7.4 Operational observations

Host side leases always eventually cleared, but capability-consumed-to-cleanup
latency ranged from about 17 seconds to 198 seconds:

| Observation | Cleanup latency |
|---|---:|
| M1-2 | ~198 s |
| M1-3 | ~28 s |
| M1-4 | ~88 s |
| M1-5 | ~101 s |
| M1-6 | ~173 s |
| D1-1 | ~18 s |
| D1-2 | ~18 s |
| G2-1 | ~20 s |
| G2-2 | ~18 s |
| G2-4 | ~131 s |
| G2-5 | ~21 s |

Long delays correlated with dense active Goal/App Server notification streams.
The daemon remained live and continued receiving notifications; this was
reconciliation latency rather than process outage.

Other operational gaps:

- runtime broker logs exposed lifecycle start/ready but no request-level
  success envelope, so persisted effect and final model output were the
  available contract evidence;
- App Server could still read/list idle ephemeral side-thread projections
  after host lease cleanup, even though host/owner lease state was empty;
- side-thread `thread/read(includeTurns=true)` is unsupported; `logs_2.sqlite`
  was required to recover actual tool-call arguments for diagnosis.

## 8. Acceptance matrix

| Proof class | Result | Evidence |
|---|---|---|
| Product | fail | M1 wrong user obligation delivered; D1 duplicate Demand; G2 independent deliverable absorbed |
| Contract | partial | receipts, Task/Goal terminal snapshots, replies, and state agreed; request-level broker envelope was not observable |
| Architecture | fail at triage semantics | authority and freshness have one owner, but Demand relationship judgment lacks a stable product rule |
| Replacement | not applicable | this run changed no product code or live contract |
| Operations | pass with risks | Actors deleted and leases cleared; cleanup latency and ephemeral read projections remain observations |

## 9. Required next owner/action

Do not continue Wave B before the Demand relationship contract is reviewed.
The next change should remain owner-correct and narrow:

1. define one explicit precedence model for `create`, `merge_intake`, and
   `revise`, including user changes to the same deliverable, independent
   deliverables, Actor self-improvements, and terminal corrections;
2. give referential terminal follow-ups enough source-linked context to create
   a new correction Demand without exposing all terminal history;
3. decide which part is enforceable by owner validation and which part remains
   model judgment;
4. add executable regression cases for the exact three escaped semantics
   before repeating Wave A;
5. rerun Wave A from fresh Actors; run Wave B only if all Wave A hard gates
   pass.

This report does not authorize or implement the repair.
