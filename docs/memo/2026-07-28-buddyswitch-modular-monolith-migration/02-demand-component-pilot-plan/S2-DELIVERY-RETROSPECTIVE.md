# S2 Delivery Retrospective and Quality-Ratchet Design

> Status: `ADOPTED`
> Scope: S2 delivery and verification process
> Product outcome: S2 remains `ACCEPTED`
> Policy authority: none; this is a historical root-cause and adoption design
> Source checkpoint: `0bb6e28d1e0a224cfd436206760262a58ea477a3`
> Date: 2026-07-29

## 1. Purpose

S2 ultimately delivered the intended Demand module boundary, but reaching
acceptance required several avoidable review and verification loops. This
record separates:

- the accepted product architecture;
- latent defects correctly exposed by broader proof;
- execution and coordination mistakes that should not recur;
- the smallest changes to existing durable owners and active plan projections
  that prevent recurrence.

This memo is historical evidence, not a second testing policy, lifecycle
state, packet validator or acceptance authority. Reusable testing judgment
moves into `$buddyswitch-testing`; the active migration plan projects durable
root `AGENTS.md` and skill rules into the execution surfaces named in section
8.

## 2. Outcome that did not fail

The Demand modularization itself did not require architecture replanning after
implementation:

```text
application composition
  -> one Demand assembly
    -> typed host contributions or Demand Public
      -> one Demand-private owner and state path
```

The accepted candidate has one physical Demand root, one application
selection, one state writer, no external Demand-private imports and no retired
Demand live path. The late failures did not require a compatibility path,
second component model, broader foundation redesign or change to Demand
ownership.

The correct conclusion is therefore not “S2 architecture failed.” The
delivery system failed to preserve and interpret operational evidence tightly
enough around an otherwise valid module cutover.

## 3. Evidence timeline

### 3.1 Initial candidate: green FINAL with unresolved contrary evidence

The first S2 return reported frozen FINAL
`8c3242c7b30d42858433c6413a4f963c` as green:

```text
Unit:        430 passed, 1,124 subtests
JavaScript:  147 passed
Integration: 759 passed, 438 subtests
Process:      262 passed, 379 subtests
System:       21 passed
```

However, the same result packet also reported:

- an earlier app-server startup timing failure treated as non-reproducing
  after three passes;
- `zstandard==0.25.0` installed outside `requirements-test.txt`.

Those facts already contradicted acceptance. A later pass did not explain the
earlier failure, and an ad hoc package install meant the declared test
environment did not reproduce the candidate.

### 3.2 Cleanup and dependency repair

Review found a live central daemon left from the failed run. The system fixture
deleted its test root after `env reset` failed, destroying PID/start identity
before the existing owner could stop the detached process.

The repair:

- stopped the central daemon through its identity-safe owner before root
  deletion;
- added a failure-path regression;
- declared `zstandard==0.25.0` in `requirements-test.txt`;
- reconstructed the runtime from declared inputs only.

The direct failure-path and product-flow run
`9cd7ebb75d8e42a3b7880f43ba888b8e` passed. The next frozen FINAL
`c8ec462fd5c74a529dc34a92167d05d4` then failed a Browser process test.

### 3.3 F001: child-authored observation race

`test_browser_not_ready_failure_reaps_process_and_removes_identity` expected a
fake Chrome child to write `fake-chrome.pid` during one 10ms readiness attempt.
The test was observing scheduler timing rather than the product contract.

The accepted repair captures the real child `Popen` synchronously at the
parent launch boundary. Exact run
`23e5c28a819640c2affefde89682c61e` passed.

The next frozen FINAL `85a5a913d5c64981a8c8351a97c2b7c3`
found a neighboring app-server early-exit race.

### 3.4 F002: terminal state authored outside the observer

The fake Codex child was not guaranteed to become observable as exited inside
the one-second product timeout. The test expected
`AppServerUnavailableError` but observed `AppServerTimeoutError`.

The accepted repair places real child creation and identity under parent
control before termination. Exact run
`fff09b42c52e43ed8719af14d608dd2b` and complete Process run
`6f72e37b3a66442ca851869c08eed516` passed.

The next frozen FINAL `4ca6ae44008d4387aedd13c2c265d566`
then exposed a real Browser lifecycle owner defect.

### 3.5 F003: branch-local cleanup instead of an owner postcondition

`_terminate_owned_record` had several terminal returns. Selected branches
called `_reap_child_pid`, while other terminal branches returned without
reconciling the tracked child. A historical commit had already repaired the
same invariant in one branch.

Another branch-local call would have been patch-on-patch. The accepted repair
uses one function-level postcondition:

```text
every terminal return
  -> exactly one tracked-child reconciliation attempt
    -> terminal child absent
    -> live child retained
```

The exact RED `d871368dee4640acb8bd03e9f59aba51` covered three terminal
branches and the protected live-child case.

### 3.6 Coordinator-authored execution deadlock

The first F003 Goal Packet ordered:

```text
edit src/buddyswitch
  -> run exact GREEN
    -> reprovision installed runtime
```

That contradicted the accepted installed-runtime contract. The public runner
correctly returned `RUNTIME_MISMATCH` before creating a run. This was not an
implementation failure; it was a Goal Packet specification failure.

D-044 now freezes the correct ordering:

```text
coherent src/buddyswitch mutation
  -> rebuild/install/activate/verify
    -> public runner proof
```

R1 performed no repository edit and completed the proof chain:

```text
exact GREEN:      090399c8d6e74e888f7df159cd41b1b9
Browser file:     e669bde115ae4c67af2ebfb5674d9ad7
Integration:      5571fa5053b048e5b8b006a96e745a66
Process:          ac14e92bf10a46f1817bda50a2e07beb
FINAL:            865b88ce29d34c25aef70c122b41768c
FINAL result:     PASS
```

## 4. Root-cause classification

| Class | S2 evidence | Meaning |
|---|---|---|
| Product architecture | Demand owner/Public/state/composition remained stable | accepted design was coherent |
| Declared environment | ad hoc `zstandard` install | acceptance did not prove reproduction from declared inputs |
| Failure truth | earlier timing failure overwritten by later passes | pass history was favored over unresolved contrary evidence |
| Resource ownership | root deleted before daemon owner stopped process | cleanup proof destroyed its own attribution evidence |
| Process observation | child-authored PID/exit timing | tests observed scheduling rather than parent-known process identity |
| Repair granularity | reap calls repeated in selected branches | lifecycle invariant lacked one owner-level terminal postcondition |
| Packet sequencing | GREEN scheduled before runtime reprovision | active template and accepted runtime contract disagreed |

## 5. What worked

The process did contain the damage:

- the runtime guard rejected stale installed/source correspondence;
- revised packets stopped after frozen FINAL failures instead of hiding them;
- no compatibility or fallback was introduced;
- the patch-on-patch loop breaker forced F003 back to the owner invariant;
- the final repair stayed one `try/finally`, not a lifecycle framework;
- exact run identities and cleanup evidence allowed the hub to reuse valid
  proof rather than rerun everything after every handoff.

These mechanisms should remain. The goal is to close the gaps around them, not
replace them with more process.

## 6. General lessons

### 6.1 A green run cannot erase an unresolved failure

Any failure, timeout, flake or cleanup residue after candidate freeze
supersedes earlier and later passing evidence until its owning cause is
explained. “Passed three times afterwards” is not a diagnosis.

Every return and acceptance record must disclose all failed attempts since the
candidate froze, their root cause, repair or explicit blocker.

### 6.2 Declared environment is part of source identity

A candidate that needs an ad hoc dependency install is not reproducible and
cannot enter FINAL acceptance. Runtime and test dependencies must come from
the committed declarations used to build the recorded environment.

### 6.3 Resource identity must outlive cleanup decisions

The parent or runner must capture the real process identity before waiting.
Cleanup must stop the owner before deleting PID, start-identity, socket, lock
or root evidence. A child-authored helper marker may be diagnostic output; it
cannot be the sole proof that the child existed or terminated.

### 6.4 Lifecycle fixes target terminal invariants, not observed branches

When a defect appears on one early return, exception path or cleanup branch,
review every terminal exit and search current history for the same invariant.
A prior branch-local repair is architecture feedback: select one owner-level
postcondition and prove every material exit.

### 6.5 Execution ordering is part of the packet contract

A packet is not READY merely because it names the correct tests. It must order
environment construction and verification before the command that consumes
that environment. For BuddySwitch package source:

```text
source mutation -> runtime reprovision -> activation verify -> test
```

At the start of this review, the implementation-plan template still taught
“implementation -> GREEN” without this mandatory boundary. D-044 is therefore
the accepted policy projected by the adoption recorded below.

### 6.6 Read-only pressure baseline

A separate read-only Codex worker reviewed the pre-adoption instructions
against five S2-derived scenarios and made no repository edits:

| Scenario | Pre-adoption decision | Demonstrated gap |
|---|---|---|
| timeout followed by three passes | STOP; existing testing skill already superseded the pass | owning-diagnosis closure and execution-handoff visibility were not explicit |
| manually installed undeclared package | REPAIR the declared owner | manual install prohibition and canonical declaration provenance were not prominent |
| package-source mutation followed by GREEN before reprovision | reorder after reprovision | implementation-plan template lacked the mandatory gate |
| child asynchronously writes the only PID marker | STOP and redesign the proof | parent-known real-process identity was not an explicit reviewer probe |
| another branch-local cleanup patch for a repeated invariant | STOP and repair the owner boundary | all-terminal-exit and relevant-history review were absent from action-time guidance |

The pressure result also identified `executor-handoff-card.md` as the most
likely action-time surface and found that its read order omitted
`$buddyswitch-testing`. The adoption therefore changes that existing handoff
instead of creating a new policy layer.

The same worker repeated the review after adoption. It confirmed that root
`AGENTS.md` and `$buddyswitch-testing` are the durable authorities,
`00-execution-governance.md` is only the active migration-plan projection,
the handoff stops on a contradicted READY mechanism or inadequate direct
proof, and no duplicate-policy-owner contradiction remains.

## 7. Considered approaches

### A. Historical retrospective only

This preserves context but relies on future coordinators remembering a memo.
It does not change the live handoff path and is insufficient.

### B. Historical retrospective plus existing-owner ratchets — selected

Keep this memo as history, then project only reusable rules into the existing
governance, packet templates and testing skill references. This changes the
path future executors actually use without creating another owner.

### C. New Goal Packet validator, state or evidence service

This could mechanize more checks but would introduce a second policy engine
before repeated evidence justifies it. The public runner already enforces
runtime mismatch. A new validator is rejected as speculative complexity.

## 8. Selected adoption surfaces

The implementation is deliberately limited to existing durable owners and
active migration-plan projections.

### 8.1 Execution governance

Modify:

```text
docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/
  00-execution-governance.md
```

Add:

- declared dependency/runtime construction to READY evidence when material;
- complete post-freeze failure disclosure to checkpoint and acceptance;
- source mutation/reprovision/test ordering as a packet coherence requirement;
- resource identity preservation before cleanup deletion.

### 8.2 Goal Packet template

Modify:

```text
docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/
  stage-goal-packet-template.md
```

Require:

- declared environment provenance and prohibition on ad hoc installs;
- exact runtime reprovision boundary after package-source mutation;
- all failed/timeout/flaky attempts since freeze in the return packet;
- stop instead of rerun when a failure has no owning diagnosis.

### 8.3 Implementation Plan template

Modify:

```text
docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/
  stage-implementation-plan-template.md
```

Insert between implementation and GREEN:

```text
if src/buddyswitch changed:
  rebuild/install/activate/verify
else:
  record exact inapplicability
```

No plan may defer this boundary until after a public-runner command.

### 8.4 Acceptance template

Modify:

```text
docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/
  stage-acceptance-template.md
```

Require:

- declared dependency and runtime identity;
- a complete table of every post-freeze failure/timeout/flake and disposition;
- rejection when any failure is unresolved, even if a later FINAL passes;
- cleanup identities captured before resource-root deletion.

### 8.5 Existing BuddySwitch testing skill references

Modify only:

```text
.agents/skills/buddyswitch-testing/references/evidence.md
.agents/skills/buddyswitch-testing/references/review.md
```

`evidence.md` will state that undeclared environment mutation and unresolved
failure history invalidate reuse. `review.md` will state the process-lifecycle
and all-terminal-exit review rules.

The core skill already owns failure supersession, clean resource proof and the
rule that fakes must not author success. Those rules will not be duplicated in
a new skill or policy.

### 8.6 Coordination hub projection

Modify:

```text
docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/
  00-coordination-hub.md
```

Add the declared environment, execution ordering and complete failure history
to just-in-time Goal Packet and hub acceptance responsibilities. It remains a
projection of the active migration plan, not a durable policy owner.

## 9. Explicit non-goals

This adoption will not add:

- a new migration state;
- a Goal Packet parser, validator or linter;
- a second test runner or evidence ledger;
- another required reviewer or agent;
- additional full-suite runs;
- generalized process supervision infrastructure;
- product, runtime or S3 implementation changes.

## 10. Acceptance criteria for the ratchet

The governance update is complete only when:

1. no active template schedules a public test after package-source mutation
   but before runtime reprovision and activation verification;
2. no active packet or acceptance template permits ad hoc dependencies;
3. acceptance requires every post-freeze failure to have an owning
   disposition;
4. process-lifecycle review requires parent-known identity and identity-safe
   cleanup ordering;
5. lifecycle branch repair review requires all-terminal-exit and relevant
   history inspection;
6. root `AGENTS.md` and `$buddyswitch-testing` remain the durable policy
   owners, while `00-execution-governance.md` remains this migration's active
   plan owner;
7. artifact checks pass and no executable source, test or runtime changes.

## 11. S3 admission effect

S3 source refresh may begin only after this ratchet is adopted and committed.
The refresh uses checkpoint
`0bb6e28d1e0a224cfd436206760262a58ea477a3` or its documentation-only
successor and must apply the new rules while preparing:

- the declared test/runtime environment;
- the complete affected preservation baseline;
- the Task/Goal owner and Public dependency trace;
- Daemon ordering
  `demand_triage -> task_goal -> demand_orchestration`;
- mutation/reprovision/test ordering;
- all failure and cleanup evidence;
- one source-bound S3 Goal Packet and READY review.

S3 implementation remains unauthorized until that packet is reviewed and
declared READY by the coordinating hub.

## 12. Adoption record

The accepted lessons are now projected through these durable owners, active
migration plan and execution-facing views:

```text
durable policy owners:
  root AGENTS.md
  .agents/skills/buddyswitch-testing/references/evidence.md
  .agents/skills/buddyswitch-testing/references/review.md

active migration-plan projection:
  00-execution-governance.md

execution projections:
  00-coordination-hub.md
  executor-handoff-card.md
  stage-goal-packet-template.md
  stage-implementation-plan-template.md
  stage-acceptance-template.md
```

The Goal Packet and handoff card provide the action-time reminder and cite
the durable owners, active migration plan, D-037 and D-044. An S3 packet must
additionally link this retrospective only as historical rationale.

No new migration state, packet validator, runner, evidence service, policy
owner, executable source, test, dependency declaration or runtime path was
added. The adoption implementation is recorded in
`S2-QUALITY-RATCHET-ADOPTION-PLAN.md`.
