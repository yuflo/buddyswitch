# Modular Monolith Migration Coordination Hub

> Status: ACCEPTED
> Authority: current coordinating Codex session
> Thread identity: `019f8ddd-bfd2-7b71-bfe7-c1aba4de7f4b`
> Execution model: independent stage sessions, asynchronous return

## 1. Purpose

This session is the program-control owner for S0–S7. It does not become a
long-running executor or polling supervisor. It keeps one program truth,
prepares one stage at a time, and resumes only when the user brings back a
stage result or asks for a status/decision.

## 2. Exclusive hub authority

Only the coordinating session may:

- transition the master stage ledger;
- accept, reject, reopen or replan a stage;
- change accepted architecture decisions;
- open or close architecture findings;
- assign, reassign or close residue rows;
- approve shared write surfaces and integration ownership;
- declare a Goal Packet READY;
- authorize the next stage or S4 lane.

The hub verifies repository facts directly. It never accepts a stage merely
because an execution session says it is complete.

## 3. Independent execution-session authority

An execution session receives exactly one READY Goal Packet. It may:

- create the packet's stated active goal;
- modify only its classified owner, consumer, proof and current-doc scope;
- select and correct exact execution commands from current repository and
  runner facts when the acceptance claim and proof breadth do not change;
- execute the packet's RED/GREEN/refactor tasks;
- commit coherent checkpoints if the packet authorizes commits;
- record test/run evidence and cleanup;
- submit a proposed stage acceptance record.

It may not:

- edit the master migration ledger, decision log or finding statuses;
- close residue rows as program truth;
- alter another stage or lane;
- reinterpret an accepted target decision;
- declare its own stage accepted;
- begin the next stage;
- solve a stop condition with compatibility, fallback or broader abstraction.

New findings and residue are returned as proposals. The hub owns registration
and stage impact.

## 4. Just-in-time Goal Packets

A future stage does not receive an executable Goal Packet before its
predecessor is accepted. The hub generates the packet against the then-current
source and includes:

1. exact stage goal and acceptance sentence;
2. source commit, tracked patch and non-ignored untracked identity;
3. complete affected pre-mutation preservation evidence and a
   representation-complete consumer audit covering imports, literals,
   data-driven IDs, generated names/paths, discovery, activation-dependent
   subprocesses and package/test projection;
4. material boundary-contract matrix and representative final-topology
   preflight identities;
5. declared dependency, build, test and runtime environment identity;
6. source-mutation to rebuild/install/activate/verify to proof ordering;
7. read order and governing decisions;
8. exact allowed, shared and forbidden scope;
9. frozen behavior and protected contracts;
10. task/checkpoint order, first direct proof claim and known current targets;
11. residue and current-guidance obligations;
12. verification responsibilities, complete contrary-evidence reporting and
    identity-safe cleanup;
13. stop/replan conditions;
14. exact asynchronous return packet.

The stage remains `PROPOSED` until the hub proves every required field exact
and no boundary decision remains for the executor. A plan that delegates
package completeness, correspondence, ownership or another architecture
question to implementation is not READY. Stop conditions cannot substitute
for missing preflight evidence. Only then does the hub transition the stage to
`READY`.

The hub does not freeze local shell spelling, test grouping or mechanically
equivalent target paths as architectural truth. The capable executor owns
those decisions through the current runner and `$buddyswitch-testing`; it
records material deviations and stops only when equivalence or scope is
uncertain.

## 5. Stage-session lifecycle

```text
hub PREPARE
  -> hub READY review
    -> hub marks stage READY
      -> user starts independent execution session with Goal Packet
        -> execution session marks its work IN_PROGRESS locally
          -> execution session implements and returns evidence
            -> user returns result to hub
              -> hub inspects repository and evidence
                -> ACCEPTED | REPLANNING | REJECTED
```

The execution session's local progress language does not change the master
ledger. The hub records master `IN_PROGRESS` only after the user identifies
the execution session or reports that execution started.

## 6. Asynchronous no-polling rule

After handoff, the hub ends its active turn. It does not:

- poll the execution session;
- repeatedly read thread state;
- hold a wait call open;
- infer completion from elapsed time;
- consume turns merely to report unchanged state.

The user returns with the execution result, thread link/ID, commit/diff,
acceptance proposal or blocker. The hub then resumes from the recorded
checkpoint.

If the user explicitly asks the hub to inspect or coordinate a named thread,
the hub may perform one bounded read or action. This is an exception requested
by the user, not the default operating mode.

## 7. Required execution return

Every execution session returns:

```text
Stage and Goal Packet identity:
Source commit and exact final diff:
Completed checkpoints:
Changed/created/deleted files:
Focused and final test commands:
Run IDs, results, duration and cleanup:
Declared dependency/runtime identity:
Every failure/timeout/flake/residue signal since candidate freeze and owning disposition:
Process/resource identity captured before cleanup deletion:
Consumer-observed proof:
Proposed residue closures/new residue:
Current docs changed:
Omitted checks and residual risk:
Stop/replan discoveries:
Proposed acceptance result:
```

Missing material evidence means the hub cannot accept the stage.

## 8. Hub acceptance procedure

On return, the hub:

1. verifies the current repository/branch/diff identity;
2. checks packet scope and unrelated work preservation;
3. inspects executable ownership and replacement;
4. validates supplied tests against the current candidate;
5. runs only missing or invalidated claim-scoped probes;
6. rejects ad hoc dependencies, stale runtime ordering and any unresolved
   failure, timeout, flake or residue signal, even after a later pass;
7. checks that cleanup preserved parent-known process/resource identity until
   the owning resource stopped;
8. checks residue, current guidance and cleanup;
9. writes the acceptance record;
10. transitions the ledger or reopens the owning checkpoint.

Only an accepted stage unlocks preparation of its successor.

Stage-specific retrospectives may be linked as historical rationale. They do
not become execution-policy owners. Root `AGENTS.md` and
`$buddyswitch-testing` remain the durable authorities;
`00-execution-governance.md` remains this migration's active plan projection.

If the return contradicts the packet specification, the hub also applies
D-037: retire the packet, identify the missing pre-READY proof and revalidate
the boundary before any successor plan. A second specification invalidation
at the same boundary forbids another patch-on-patch packet and reopens the
architecture.

## 9. Pause record

When waiting for the user, the hub records:

```text
Stage:
Master state:
Goal Packet:
Execution session: unknown until user supplies it
Last hub checkpoint:
Expected return:
No-polling state: PAUSED_FOR_USER_RESULT
```

This is a normal asynchronous state, not a blocker.
