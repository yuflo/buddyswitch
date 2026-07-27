# Demand Triage Semantic REBUILD Acceptance

**Status:** accepted at the scoped automated and real-Actor boundaries

**Date:** 2026-07-25

**Source identity:** `5a22aeec8a830c1a75f8913c9d725f7487daefbd`

**Implementation plan:**
[Demand Triage Semantic REBUILD Implementation Plan](./2026-07-25-demand-triage-semantic-rebuild-implementation-plan.md)

## 1. Acceptance claim and result

Claim:

> A fresh real Web Actor merges an explicit same-deliverable supplement,
> creates an explicitly independent deliverable, and creates a new correction
> Demand for a terminal result without mutating an unrelated live Demand. The
> isolated side receives the one shared native Skill, commits exactly once,
> and canonical Demand state, Task/Goal state, Web delivery, and runtime
> feedback agree.

Result: **passed**.

The REBUILD keeps one architecture:

```text
inbound fact
  -> new ephemeral triage thread in the same Actor workspace
  -> native $demand-triage Skill selection
  -> exact Message + bounded conversation + all-state Demand reads
  -> one demand_triage.resolve
  -> deterministic Demand Sys validation and atomic write
  -> parent Demand orchestration
  -> at most one Task/native Goal
```

No second Skill, fallback prompt, parent triage branch, semantic Python
classifier, new Tool, Demand graph, Task/Goal change, or daemon-service
business rule was introduced.

## 2. TDD evidence

### 2.1 Automated RED

At the original source identity, the exact policy/contract targets failed
under run `4ecca1f...` because the live Skill and visible descriptions still
taught the retired live-only, under-specified relationship boundary. The real
App Server system target then failed at the new assertion that the selected
Skill content must be model-visible before the first triage sampling.

The failures were valid behavior/contract REDs rather than import, runner, or
setup failures.

### 2.2 First real-Actor RED

The first post-code Dev Actor, `act-dev-2f92887b8471`, exposed a remaining
semantic defect:

- D1-1 created the base schedule-tool Demand;
- D1-2 explicitly said “同一个基础工具”;
- the side read the exact source Message, the direct conversation with limit
  20, the all-state Demand pool, and full Demand A;
- it nevertheless treated technical separability and an earlier
  Actor-proposed future improvement as grounds to create duplicate
  `demand-c63dfbd81c49`.

The broker returned a truthful successful result; this was a semantic-policy
failure, not a runtime, schema, or persistence failure. Acceptance stopped.
The Actor was stopped and deleted through WebUI.

The Skill was then tightened in place:

- the user's current result/delivery grouping defines the acceptance unit;
- explicit current grouping outranks an earlier model-written boundary;
- technical separability alone does not create product independence;
- an earlier Actor-proposed improvement governs that proposal, not a later
  explicit user supplement to the same deliverable.

An exact architecture RED was added for these phrases before the Skill was
changed.

### 2.3 Final automated GREEN

| Run id | Scope | Result |
|---|---|---|
| `1e50290e86df438992db47725323de94` | exact Skill/handler/resolver contracts | 3 passed |
| `bb38d5a4e0834c3290409b2934b43427` | real App Server product flow and native Skill injection | 1 passed |
| `ddfe2f787b574a63ae71601415195bf6` | shared Skill installation and isolated `thread/start` identity | 3 passed, 5 subtests passed |
| `15f1ce89d7cd446fa1efcf7178822978` | deterministic Demand resolution, side flow, architecture boundaries | 34 passed, 8 subtests passed |

The residue scan found retired phrases only in explicit negative assertions.
`git diff --check` was clean.

## 3. Real Web Actor environment

- isolated shared root:
  `/private/tmp/buddyswitch-demand-rebuild.v0SWQw/.codex-buddyswitch`;
- WebUI: `http://127.0.0.1:8892/`;
- one fresh Actor at a time, in order Dev, Design, Market;
- WebUI was the sole writer for Actor creation, Messages, stop, and delete;
- UI capability projection showed Parent `Balanced`, Side `Fast`;
- each side used the Actor workspace's one installed
  `.agents/skills/demand-triage/SKILL.md`;
- live logs showed new ephemeral side threads, native Skill selection, bounded
  Message reads, all-state Demand reads, targeted full Demand reads, and one
  resolver commit;
- durable ingress receipts retain the exact source Message, attempt id,
  decision, Demand id, pool revision, and failure state;
- side leases were observed to disappear after completion, sometimes with
  visible cleanup latency rather than immediately at business commit.

The individual ephemeral side thread ids are intentionally not canonical
product state and disappeared with lease/Actor cleanup. The durable correlation
used below is Message id + ingress attempt + Demand revision.

## 4. D1 — Dev schedule manager

Actor `act-dev-d9c3ba347ef3`; main thread
`019f9825-bfd1-7d90-8833-de7e6bc3940d`.

| Step | Message id | Observed decision | Canonical result |
|---|---|---|---|
| D1-1 | `msg-f673345a2439` | create | A `demand-2d63666adb80` |
| D1-2 | `msg-dce973c87153` | merge_intake | A advanced; no duplicate |
| D1-3 | `msg-e2433a59c5d1` | create | export B `demand-5fcb2cfd3710` |
| D1-4 | `msg-b28507de0942` | revise | B changed CSV to ICS |
| D1-5 | `msg-f28ce51eaf7a` | create | conflict C `demand-7a107f813ccc` |
| D1-6 | `msg-a66128cdd00a` | merge_intake | recurrence conflict detail merged into C |
| D1-7 | `msg-3fdeeda60663` | cancel | C terminal canceled |
| D1-8 | `msg-b66ee8135d79` | create | terminal correction D `demand-3b90466a16db` |

The repaired D1-2 gate passed. A completed at revision 4 with durable
implementation and reply evidence. Its two serialized Tasks used the same
native Goal thread:

- `task-demand-b0a32701a57a`: complete, 81,229 tokens, 289 seconds;
- `task-demand-81d5b31c2988`: complete, 186,944 tokens, 241 seconds.

The next ICS Demand was then selected as the only active Task and completed.
D1-8 left terminal A unchanged and created a new unmet correction for the
delete-to-trash/undo behavior.

The Actor also created self-requested Demand `demand-99c504b7b332`. It
partially overlaps the user's export Demand. That path is direct
Actor `demand_sys.create`, not inbound triage, so it is recorded as a separate
future self-Demand coordination issue rather than hidden inside this REBUILD.

## 5. G2 — Design research workspace

Actor `act-design-0cae978fa8ac`; main thread
`019f983b-f3a6-78e1-a08d-64022db73a37`.

| Step | Message id | Observed decision | Canonical result |
|---|---|---|---|
| G2-1 | `msg-8854a0721fd3` | create | workspace A `demand-3a9e8ad4cd81` |
| G2-2 | `msg-a2776b5874b0` | merge_intake | evidence cards merged into A |
| G2-3 | `msg-9e92dea0c2f9` | create | review B `demand-13836699953e` |
| G2-4 | `msg-41f2a13ad9ab` | revise | B changed to tablet landscape |
| G2-5 | `msg-7be8deeece3b` | create | independent state library C `demand-d20c46cdf449` |
| G2-6 | `msg-9f75834ff80c` | merge_intake | accessible copy/actions merged into C |
| G2-7 | `msg-38cf09dcb157` | cancel | B terminal canceled |
| probe | `msg-3de4ebcc4557` | no_action_needed | pool revision unchanged |
| G2-8 | `msg-cf603cd9711d` | create | correction D `demand-f9f1def6e74f` |

The repaired G2-5 gate passed: the explicitly separate state library did not
merge into A. A completed at revision 4 with Artifact `art-4c049737a2`,
attachment `att-8c8fd9dbe5`, and two verified Web replies. G2-8 left terminal A
unchanged and created a correction Demand whose text names the completed
workspace and design artifact. After reconciliation, C became the only active
Task.

## 6. M1 — Market NVIDIA research

Actor `act-market-3c426b7ae4ca`; main thread
`019f9847-c1e9-7121-9bc0-d7e9d14c62cf`.

| Step | Message id | Observed decision | Canonical result |
|---|---|---|---|
| M1-1 | `msg-a4d99f9f538a` | create | acquisition brief A `demand-ab5d6e3551a4` |
| M1-2 | `msg-4b35c97f8313` | merge_intake | capability/date fields merged into A |
| M1-3 | `msg-c662cf96137b` | create | open-model timeline B `demand-87131edad87d` |
| M1-4 | `msg-e1198287499e` | merge_intake | Nemotron official-only scope merged into B |
| M1-5 | `msg-d3b4ac4d1f2f` | create | procurement page C `demand-32eb45eeb154` |
| probe | `msg-675dcf136936` | no_action_needed | pool revision unchanged |
| M1-6 | `msg-63a81b4a64a1` | create | terminal correction D `demand-a54f57029363` |
| M1-7 | `msg-9084682b784e` | cancel | C terminal canceled |

The acquisition Task `task-demand-ddf1a856880c` completed in 395 seconds with
181,683 tokens. Independent reconciliation then completed A at revision 3
using the 479-character brief, Artifact `art-e9292fffcb`, and verified reply
`msg-4e80c93fcb3b`.

The repaired M1-6 gate passed. The new D explicitly says it revises the
already-delivered first acquisition brief to a 12-month, company/regulator
confirmed scope. Terminal A, open-model B, and procurement C were not revised.
B was selected as the only active Task after A reconciliation. WebUI visibly
rendered the complete Market brief and its `reply_to` relation.

## 7. Cross-scenario verdict

| Proof | Result |
|---|---|
| Product | D1 same-deliverable merge, G2 independent create, and M1 terminal correction all passed; all remaining Wave A messages also passed |
| Contract | every receipt settled without contradiction; resolver success, Demand revision, Task/Goal state, and Web outcome agreed |
| Architecture | one native Skill owns semantic judgment; Demand Sys stayed deterministic; Task/Goal and daemon-service were unchanged |
| Replacement | no live-only guidance, duplicate SOP, second Skill, parent branch, fallback prompt, or intelligent Python path remains |
| Operations | one Actor at a time, at most one active Task, durable replies/Artifacts visible, Actor instances deleted through WebUI |

Wave B was not run because it is outside this scoped REBUILD acceptance.

## 8. Cleanup and residual observations

All three accepted Actors and the initial failed Dev Actor were stopped and
deleted through WebUI. Public `instance list` returned an empty list after
each scenario.

Final cleanup also passed:

- the Web process was stopped through its owning execution session;
- public `env reset --yes` returned
  `{"removed":true}` for the exact isolated shared root;
- port `8892` had no listener;
- no process command referenced the isolated root or Web port;
- the empty parent temporary directory was removed with exact `rmdir`;
- the in-app Browser acceptance tab was finalized after all browser work.

No attributable Actor, daemon, App Server, runtime broker, browser, socket,
lock, side lease, Web listener, shared root, or parent temporary root remained.

Residual observations that do not invalidate this acceptance:

1. side lease cleanup can lag business commit; no lease remained after Actor
   teardown;
2. direct Actor self-Demand creation can overlap a user Demand and requires a
   separate future coordination decision;
3. the real-model scenarios are expensive, so these semantic cases remain
   acceptance tests rather than ordinary focused automation.
