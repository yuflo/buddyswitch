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
3. complete affected pre-mutation preservation evidence;
4. material boundary-contract matrix and representative final-topology
   preflight identities;
5. read order and governing decisions;
6. exact allowed, shared and forbidden scope;
7. frozen behavior and protected contracts;
8. task/checkpoint order and first direct proof;
9. residue and current-guidance obligations;
10. verification commands and cleanup;
11. stop/replan conditions;
12. exact asynchronous return packet.

The stage remains `PROPOSED` until the hub proves every required field exact
and no boundary decision remains for the executor. A plan that delegates
package completeness, correspondence, ownership or another architecture
question to implementation is not READY. Stop conditions cannot substitute
for missing preflight evidence. Only then does the hub transition the stage to
`READY`.

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
6. checks residue, current guidance and cleanup;
7. writes the acceptance record;
8. transitions the ledger or reopens the owning checkpoint.

Only an accepted stage unlocks preparation of its successor.

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
