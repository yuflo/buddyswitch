# Demand Sys Relation-Free Forward Rebuild Design

**Date:** 2026-07-21

**Status:** implemented and acceptance-proven; frozen-commit FINAL pending

**Baseline:** `fea-daemon` at
`bfbd4f39e7f8f41c14ad728b35929289a8bdf014`

**Scope:** rebuild the Phase 1–3 Demand model to one relation-free canonical
Demand system, preserve the accepted inbound and Task collaboration loop, and
remove every current surface that stores, exposes, teaches, or protects the
retired Demand relation model

## 1. Goal and acceptance sentence

The current bottleneck is not missing relation coverage. It is that Demand Sys
persists a relation model that has no current behavioral consumer while forcing
lifecycle, schema, action, prompt, and test complexity across the whole module.

The rebuild establishes this one product model:

```text
source fact or actor self-demand
  -> actor-owned live Demand
  -> actor canonicalization judgment
       -> revise the same Demand
       -> absorb two rows into one canonical Demand
       -> keep distinct Demands independent
       -> cancel an invalid or withdrawn Demand
  -> actor selects at most one live Demand
  -> Task Sys executes one opaque Demand revision
  -> actor reconciles Task outcome against the latest Demand
  -> complete, revise/keep live, or cancel the Demand
```

The acceptance sentence is:

> Any implemented source can durably capture one actor-owned need; the actor can
> reduce separately captured rows that express the same canonical need through
> `revise` or `absorb_into`, keep distinct needs independently live, select at
> most one for Task execution, and explicitly terminalize the need as completed,
> canceled, or absorbed, while Demand Sys contains no cross-Demand organization
> graph, Task Sys holds only an opaque DemandRef, daemon infrastructure remains
> product-neutral, and no active code, schema, tool, permission, prompt, skill,
> test, current architecture document, or runtime aggregate preserves the
> retired relation model.

## 2. Evidence behind the rebuild

### 2.1 Real actor evidence

The FluxOps multi-demand acceptance produced four Demands:

- A was the active landing-page need;
- B supplemented A and was absorbed into A;
- C was a later mobile correction and executed as a new Demand;
- D was a later independent feature and executed as a new Demand.

Only `absorb_into` changed the Demand organization in a way required for the
product loop. All four records had `parent_id: null` and empty `depends_on`.
C and D executed correctly without a cross-terminal relation. The experiment
did not prove a scheduler, parent completion rollup, dependency blocker, history
graph, correction edge, or reopen rule.

### 2.2 Current implementation evidence

The relation model is not isolated behind one optional layer. It currently
affects:

- record fields and exact record validation;
- creation defaults and public projection;
- terminal types and terminal validation;
- parent/dependency cycle traversal;
- live-child terminalization restrictions;
- seven actor actions beyond the minimal model;
- tool descriptions, schemas, permissions, handlers, and responses;
- daemon prompt and installed actor guidance;
- domain, tool, architecture, CLI, and process tests;
- current `docs/arch` and ignored visual specs.

Hiding actions while retaining this state would be a dual track, not a rebuild.

### 2.3 Boundary evidence

Task Sys already stores only:

```json
{
  "demand_id": "demand-a12b34c56d78",
  "basis_revision": 3
}
```

It does not import, read, validate against, call, subscribe to, or mutate Demand
state. The generic daemon likewise contains no Demand business rules. The
rebuild therefore changes Demand Sys and its direct actor/public projections;
it does not redesign Task lifecycle or daemon infrastructure.

## 3. Phase boundary

### 3.1 In scope

- Demand aggregate schema version 2;
- one minimal Demand record and one terminal tagged union;
- capture, content revision, attention, canonicalization, and lifecycle actions;
- source provenance ownership;
- actor two-pass canonicalization guidance;
- active-Task-aware absorption target choice in actor guidance;
- public Demand projection;
- actor permissions and native tool catalog;
- Demand-owned daemon prompt;
- current Demand, Task, and daemon architecture documents;
- direct unit, integration, process, architecture, and real actor proof;
- exact one-time cutover of the one known schema-v1 Demand aggregate;
- removal/replacement of ignored current visual specs that teach retired models.

### 3.2 Out of scope

- parent/child Demand structure;
- Demand dependencies or programmatic prerequisite blocking;
- split/group completion semantics;
- duplicate or supersede terminal outcomes;
- correction, replacement, history, or general relation graphs;
- priority fields, queues, schedulers, or automatic Task selection;
- multiple active Tasks;
- Demand-owned Task creation or automatic Demand completion;
- Task-owned Demand lookup or completion;
- terminal Demand reopen;
- offline inbound capture or pending-work workers;
- a generic event bus, workflow engine, rule engine, migration framework, or
  source plugin system.

If a later repeated product failure proves one of these behaviors necessary, it
must be designed from that exact failed behavior. This rebuild leaves no dormant
field, action, adapter, or extension point for it.

## 4. Target architecture

```text
IM handler --------------------\
                                \
Track comment handler ----------> Demand capture adapter
                                  - call Demand domain create/replay
                                  - read durable pending count
                                  - request generic actor input when pending
actor self-demand --------------> demand_sys.create
                                             |
                                             v
                                  Demand domain owner
                                  - schema and lifecycle
                                  - revision/check cursor
                                  - absorb canonicalization
                                  - atomic actor aggregate mutation
                                             |
                                             v
                                  Demand aggregate repository

generic daemon
  - dispatch source handlers
  - provide input_actor(text)
  - persist product-neutral host state only

parent Actor + task-management skill
  - read Demand attention and live summaries
  - decide revise / absorb / independent / cancel
  - acknowledge exact observed revisions
  - inspect Task state
  - select at most one live Demand
  - call task_sys.create with an opaque DemandRef

Task Sys
  - own one Task lifecycle and execution result
  - return one terminal outcome frame to the actor
  - never read or mutate Demand
```

There is no Demand-to-Task trigger, callback, shared repository, shared
transaction, copied status, or programmatic satisfaction rule. The actor remains
the semantic composition boundary.

## 5. Ownership

| Owner | Owns | Must not own |
| --- | --- | --- |
| Demand domain | record validation, revision, checked cursor, canonicalization, terminal state, atomic mutation decisions | Task state, source-specific reads, daemon delivery |
| Demand repository | actor aggregate path, schema version, lock, atomic read/write | Demand semantic transitions |
| Source handler | exact source validation/read and deterministic Demand intake payload | matching, absorption, Task creation |
| Demand daemon adapter | create/replay coordination, durable pending-attention policy, fixed Demand Check text | Task calls, semantic matching, lifecycle |
| Actor + task-management skill | semantic comparison, canonical target choice, Task selection, Task/Demand reconciliation | direct storage writes or duplicated domain invariants |
| Task Sys | DemandRef shape, one-active gate, Task lifecycle, runtime frames, outcome receipt | Demand lookup, revision truth, matching, terminalization |
| Generic daemon | process, trigger, mailbox, handler dispatch, actor input mechanics | Demand or Task product semantics |
| Public Demand read model | exact safe projection from Demand owner | mutation or raw aggregate access |

## 6. Canonical aggregate schema v2

The actor target is aggregate identity and appears exactly once:

```json
{
  "schema_version": 2,
  "actor_target": {
    "actor_id": "act-dev-a12b34c56d78",
    "role_id": "dev"
  },
  "demands": {
    "demand-a12b34c56d78": {
      "id": "demand-a12b34c56d78",
      "intake_key": "im.message.created:msg-a12b34c56d78",
      "description": "Support CSV export with the user's timezone.",
      "detail": "Users can export CSV and every row includes the user's timezone.",
      "source_refs": [
        {
          "type": "im.message.created",
          "ref": {
            "message_id": "msg-a12b34c56d78",
            "conversation_id": "conv-a12b34c56d78",
            "event_id": "imev-a12b34c56d78"
          }
        }
      ],
      "revision": 2,
      "checked_revision": 2,
      "terminal": null,
      "created_at": "2026-07-21T10:00:00+08:00",
      "updated_at": "2026-07-21T10:05:00+08:00"
    }
  }
}
```

Demand records do not copy `actor_target`. Domain reads remain actor-scoped by
their required actor-target argument. The public read model derives its safe
`actor` field from that exact requested aggregate target.

The exact record fields are:

```text
id
intake_key
description
detail
source_refs
revision
checked_revision
terminal
created_at
updated_at
```

Unknown, missing, or retired fields are invalid. Version 1 is rejected; it is
not translated during normal read or write.

## 7. Lifecycle

Demand lifecycle is one nullable terminal tagged union. It is not a top-level
status combined with separate execution facts.

```text
terminal == null
  -> live

terminal.type == completed
  -> completed

terminal.type == canceled
  -> canceled

terminal.type == absorbed
  -> absorbed
```

Exact terminal shapes are:

```json
{
  "type": "completed",
  "at": "2026-07-21T10:10:00+08:00",
  "summary": "The need is satisfied.",
  "evidence_refs": [
    {
      "type": "task_sys.task",
      "ref": {"task_id": "task-demand-a12b34c56d78"}
    }
  ]
}
```

```json
{
  "type": "canceled",
  "at": "2026-07-21T10:10:00+08:00",
  "summary": "The requester withdrew the need."
}
```

```json
{
  "type": "absorbed",
  "at": "2026-07-21T10:10:00+08:00",
  "summary": "This row described the same canonical CSV export need.",
  "target_demand_id": "demand-a12b34c56d78"
}
```

`target_demand_id` records the immediate target of the completed absorption
action. It is not a generic relation, an automatically resolved canonical
pointer, or permission to mutate either terminal record later.

Terminal state is immutable. An exact replay of the same terminal action is a
no-op; a different action is rejected.

## 8. Source provenance

`source_refs` records where the Demand content entered the system.

- `create` establishes source refs;
- source handlers create refs from exact source facts;
- actor-created Demands use actor-originated refs;
- `revise` changes only `description` and `detail`;
- `absorb_into` builds one target-first, duplicate-free union of target and
  source refs inside the Demand domain transaction;
- no actor action directly rewrites source refs after creation.

This makes provenance a domain-owned fact rather than actor-authored mutable
content.

## 9. Public action vocabulary

The actor-facing tool exposes exactly ten actions.

### 9.1 Capture and content

```text
create(intake_key, description, detail, source_refs)
```

- creates one revision-1 unchecked live Demand;
- exact replay returns the existing id/revision without mutation;
- same intake key with different input rejects without mutation.

```text
revise(demand_id, expected_revision, description, detail)
```

- requires one live Demand and exact revision;
- changes description/detail only;
- no semantic change is a no-op;
- it cannot alter provenance or lifecycle.

### 9.2 Reads and attention

```text
list(state=live|terminal|all)
get(demand_id)
get_many(demand_ids)
check()
complete_check(observed=[{demand_id, revision}])
```

`check` remains read-only and returns:

- all records whose revision is newer than checked revision;
- one compact id/description index of every live Demand;
- pending count.

`complete_check` is an attention mutation, not a lifecycle action. It advances
only checked revisions that the actor explicitly observed and never hides a
newer concurrent revision.

### 9.3 Canonicalization

```text
absorb_into(
  source_id,
  source_revision,
  target_id,
  target_revision,
  merged_target={description, detail},
  summary
)
```

- both source and target must be distinct live Demands at exact revisions;
- the target receives the actor-provided merged content and domain-owned source
  ref union;
- the source becomes terminal `absorbed` with `target_demand_id`;
- both mutations commit atomically;
- exact replay is a no-op;
- semantic duplicate and semantic supplement use the same action;
- the action does not create or update a Task.

### 9.4 Lifecycle decisions

```text
complete(demand_id, expected_revision, summary, evidence_refs)
cancel(demand_id, expected_revision, summary)
```

- both require one live Demand at an exact revision;
- completion requires actor-provided evidence refs;
- cancellation means satisfaction is no longer required;
- Task completion never calls either action automatically.

## 10. Demand management flow

### 10.1 Capture and check

```text
source handler or actor
  -> demand_sys.create
  -> atomic live Demand revision 1
  -> Demand adapter sees pending_count > 0
  -> generic input_actor([DEMAND CHECK])
  -> actor calls demand_sys.check
```

The actor performs two passes:

1. compare pending descriptions with the compact live index and exclude the
   same Demand id;
2. load only plausible candidates through `get_many` and compare full content.

For each pending Demand the actor decides:

```text
same existing canonical need
  -> absorb_into, or revise when only one record exists

distinct need
  -> keep independently live

invalid or withdrawn need
  -> cancel
```

The actor then acknowledges the exact resulting revisions through
`complete_check`.

### 10.2 Active Task coordination

Before absorbing two live Demands, the installed actor workflow reads the
active Task set.

- if neither Demand has an active Task, the actor chooses the canonical target
  by semantic judgment;
- if exactly one Demand is the source of the active Task, that Demand must be
  the absorption target;
- the one-active-Task invariant makes two active matching Demands impossible;
- Demand Sys does not query Task Sys to enforce this rule.

If an absorption revises the Demand behind an active Task, the Task retains its
original basis revision. The actor reconciles the latest Demand during progress
and outcome checks; Task Sys is not mutated to copy the new revision.

### 10.3 Task selection

After Demand Check:

```text
task_sys.list(status=active)
  -> active Task exists: create nothing
  -> no active Task:
       demand_sys.list(state=live)
       -> actor selects at most one
       -> reread exact Demand
       -> task_sys.create(DemandRef, execution_brief)
```

The live Demand set is a durable set of unresolved needs, not a program-owned
queue. No priority, dependency, or automatic selection field is introduced.

### 10.4 Task outcome reconciliation

```text
Task becomes completed or canceled
  -> Task Sys persists terminal Task
  -> Task outcome frame returns opaque DemandRef and Task evidence
  -> actor rereads latest Demand
       -> already terminal: no mutation
       -> latest need satisfied: demand_sys.complete
       -> still requires work: revise or keep live
       -> no longer required: demand_sys.cancel
  -> acknowledge any exact Demand revision changed by reconciliation
  -> apply the same one-Task selection rule
```

Task completion and Demand completion may be judged at the same check point,
but remain independent state transitions owned by different systems.

## 11. Scenario decisions

| Scenario | Actor judgment | Persistent Demand result |
| --- | --- | --- |
| B supplements active A | same canonical need | B absorbed into A; A revised |
| two sources repeat the same need | same canonical need | source row absorbed; provenance merged |
| B is independent from active A | distinct need | A and B remain separate live Demands |
| B should be executed before A | consumption order only | both remain independent; actor selects B first |
| one Demand requires several implementation steps | one satisfaction result | one Demand; Task plans the steps |
| one source asks for several independently desired outcomes | current model has no group lifecycle | keep one Demand unless actor explicitly creates another independent self-demand |
| user clarifies A | same need changed | revise A |
| user replaces A with a different need B | old need no longer required | cancel A; create/keep B |
| completed A later reveals defect C | new unresolved need | A stays immutable; C is a new live Demand |
| completed A later receives feature D | new deliverable | D is a new live Demand |

The model deliberately does not persist explanatory relationships that do not
change current behavior.

## 12. Error, concurrency, and idempotency semantics

- every existing-Demand mutation is exact-revision guarded;
- stale revisions reject without any write;
- aggregate mutation remains protected by one actor-scoped exclusive lock;
- absorb validates source and target before one atomic write;
- self-absorption is a payload error because source and target must differ;
- terminal mutation replay is a no-op only when semantic fields match exactly;
- conflicting terminal replay is rejected;
- source-specific capture failure after Demand persistence leaves the Demand
  pending for later retry;
- actor-input delivery failure does not roll back durable Demand capture;
- Demand action failure never writes Task, inbound, daemon, Track, Message, or
  Artifact state.

There is no relation-specific error class or error code.

## 13. Forward-only schema cutover

### 13.1 Pre-cutover runtime inventory

The authoritative state root currently contains one Demand aggregate:

```text
/Users/chen/.codex-buddyswitch/state/buddyswitch/objects/demand-sys/actors/
  act-dev-c3325d035f6c-dev.json
```

Observed identity:

```text
schema_version: 1
aggregate SHA-256: fe4b8c5e97d17b101a3b0336a4b0fc6bed2eaf43e84ff4ae31ee5b9beef607a5
actor instances: none active
Demand records: 4
parent_id values: all null
depends_on values: all empty
terminal types: 3 completed, 1 absorbed
```

The same root also contains three Task and three Artifact records. An
environment-wide reset would destroy unrelated retained evidence and is not an
acceptable cutover.

### 13.2 Exact transformation

The one aggregate can be transformed without semantic inference:

```text
aggregate.schema_version: 1 -> 2
each record.actor_target: remove; aggregate actor_target remains authoritative
each record.parent_id: remove after asserting null
each record.depends_on: remove after asserting []
terminal absorbed.ref: rename to target_demand_id
all other values: preserve
```

Execution requirements:

1. obtain explicit user authorization immediately before runtime mutation;
2. assert there are no active instances;
3. assert exact path, actor target, SHA-256, record count, empty retired fields,
   and supported terminal types;
4. write through a bounded, reviewed one-time environment operation;
5. prove the aggregate matches schema v2 and semantic before/after values;
6. prove Task, Artifact, identity, message, Track, and other runtime files are
   byte-identical;
7. remove the one-time operation from the live repository before acceptance.

Normal product code will accept only schema v2. It contains no v1 reader,
fallback, translation, dual write, compatibility alias, migration command, or
runtime branch.

### 13.3 Cutover outcome

The user separately authorized the default-runtime mutation on 2026-07-21. The
bounded operation transformed the exact four-row aggregate from the recorded
schema-1 SHA-256 to schema-v2 SHA-256
`eebd9f1c638c10087b36f98ea5ae84c21be8753257bf18dd99f876825913e973`.
Normal schema-v2 reads and public CLI projection succeeded, and the 33-file
non-target state manifest stayed byte-identical. The one-time operation and its
test were then deleted; no migration or compatibility entrypoint remains.

## 14. Product file rebuild map

### 14.1 Canonical product owner

| File | Rebuild action |
| --- | --- |
| `scripts/env/domain/demand_sys.py` | remove relation fields, traversals, actions, terminal types, live-child rules, and relation errors; remove mutable source refs from revise; retain and simplify capture/check/absorb/complete/cancel |
| `scripts/env/repos/demands.py` | set schema version 2; retain exact aggregate validation, lock, and atomic write path |
| `scripts/env/domain/demand_read.py` | remove relation fields; derive actor from requested aggregate target instead of record copy |

The domain remains one concrete module. Removing relation code materially
shrinks it; splitting lifecycle into new internal services would distribute the
semantic owner without a demonstrated need.

### 14.2 Actor action contract

| File | Rebuild action |
| --- | --- |
| `scripts/env/tools/demand_sys/tool.py` | replace sixteen actions with the exact ten-action catalog; remove relation and lineage vocabulary; remove source refs from revise |
| `scripts/env/tools/demand_sys/_impl.py` | delete retired handlers and relation-oriented guidance; keep one domain adapter |
| `scripts/env/tool_runtime/role_auth.py` | remove six retired permissions and retain exact current action permissions |
| `scripts/env/tools/context/_impl.py` | describe canonical live Demand state, not organization state |

### 14.3 Attention and actor coordination

| File | Rebuild action |
| --- | --- |
| `tools/launcher/demand_sys_daemon_adapter.py` | replace organization wording with canonicalization wording; remain Task-free |
| `buddyswitch/skills/shared/task-management/SKILL.md` | teach two-pass revise/absorb/independent/cancel decisions and active-Task target preference; remove relation taxonomy |

No generic daemon file changes its contract or learns a Demand token.

### 14.4 Current architecture and visual artifacts

| File/surface | Rebuild action |
| --- | --- |
| `docs/arch/demand-sys-architecture.md` | rewrite around canonical Demand set, schema v2, provenance, attention, and actor coordination |
| `docs/arch/task-sys-architecture.md` | remove the remaining relation/organization wording; preserve opaque DemandRef boundary |
| `docs/arch/daemon-service-architecture.md` | describe Demand canonicalization and attention, not organization policy |
| `docs/spec/2026-07-18-demand-task-system-interface-design.html` | remove ignored retired visual artifact |
| `docs/spec/2026-07-19-demand-sys-proactive-prototype-flow.html` | remove ignored constrained-hybrid visual artifact |
| `docs/spec/2026-07-21-demand-sys-three-scenario-flow.html` | replace with one relation-free current scenario flow artifact |

Historical dated memos remain historical evidence. They are not active policy
and are not rewritten to pretend the earlier design did not exist.

## 15. Test rebuild map

### 15.1 Domain proof

- `tests/unit/demand_sys/test_capture_and_check.py`
  proves schema-v2 records, immutable provenance on revise, revision/check
  cursor, intake replay, and actor isolation;
- replace `tests/unit/demand_sys/test_organization.py` with focused
  canonicalization and lifecycle tests;
- canonicalization tests prove supplementation, semantic duplicate with
  unchanged descriptive content, source-ref union, atomic stale-revision
  rejection, self-absorption rejection, exact replay, and terminal source;
- lifecycle tests prove completed/canceled/absorbed tagged unions, evidence,
  terminal immutability, and exact replay.

### 15.2 Storage and projection proof

- `tests/integration/demand_sys/test_repository_atomicity.py` proves exact
  schema v2, serialization, concurrent writers, and v1 rejection without
  rewrite;
- `tests/process/launcher/test_demand_commands.py` proves the exact relation-free
  public projection and read-only CLI;
- `tests/integration/env_tool/test_response_demand.py` proves the ten action
  responses, task-state non-impact, and retired action rejection.

### 15.3 Architecture and replacement proof

- `tests/unit/architecture/test_demand_sys_boundaries.py` proves one domain
  owner, one repository write path, Task/daemon decoupling, one tool/read path,
  and absence of retired Demand schema/action tokens on current surfaces;
- `tests/unit/architecture/test_task_management_skill.py` proves current actor
  canonicalization and active-Task target guidance;
- `tests/unit/actor/test_role_action_auth.py` and
  `tests/unit/env_tool/test_semantic_contract.py` prove the exact ten-action
  catalog and permissions;
- current tests use behavior names, not Phase 1/2 labels, when they prove the
  live architecture.

### 15.4 Inbound and Task boundary proof

- Demand daemon adapter tests prove capture, retryable attention, no Task call,
  and the relation-free prompt;
- IM and Track handler focused tests prove exact source capture still reaches
  Demand and never Task;
- Task architecture tests prove Demand remains opaque and no Task core change
  introduces Demand imports or satisfaction logic.

## 16. Verification strategy

### 16.1 RED

Before production implementation, change direct tests to assert:

- schema version 2 and exact new record fields;
- terminal types completed/canceled/absorbed only;
- absorbed terminal uses `target_demand_id`;
- revise rejects `source_refs` as an unsupported actor payload;
- tool catalog and permissions expose exactly ten actions;
- retired actions are unsupported;
- relation fields and old terminal types are rejected;
- v1 aggregate read fails without rewrite;
- current guidance contains no retired Demand relation model.

The exact focused runner targets must fail for the intended missing schema and
action behavior, not for setup or import errors.

### 16.2 GREEN and IMPACT

Use the one public runner:

```bash
./buddyswitch-test focused \
  tests/unit/demand_sys/test_capture_and_check.py \
  tests/unit/demand_sys/test_canonicalization.py \
  tests/unit/demand_sys/test_lifecycle.py \
  tests/integration/demand_sys/test_repository_atomicity.py \
  tests/integration/env_tool/test_response_demand.py \
  tests/process/launcher/test_demand_commands.py \
  tests/unit/demand_sys/test_daemon_adapter.py \
  tests/unit/architecture/test_demand_sys_boundaries.py \
  tests/unit/architecture/test_task_management_skill.py \
  tests/unit/actor/test_role_action_auth.py \
  tests/unit/env_tool/test_semantic_contract.py
```

Add only exact IM, Track, Task, or context targets discovered from actual
changed symbols. Do not run the full repository between implementation blocks.

### 16.3 Real actor acceptance

Use the formal `buddyswitch-codex` CLI and real Codex actor instances in an
isolated shared/state root. Do not use fake Codex.

The acceptance scenario is:

1. create one real Dev actor with a latency-conscious model/depth setting;
2. capture Demand A through a real implemented inbound source;
3. let the actor check A and create one Task;
4. while A's Task is active, capture B as a supplement to A;
5. observe B remain durable until actor attention is available;
6. observe the actor choose active A as absorption target;
7. observe A revision advance, B become absorbed with
   `target_demand_id=A`, and maximum active Task count remain one;
8. complete the Task and observe the actor reread the latest A revision;
9. observe A complete with exact Task evidence;
10. capture independent Demand C and observe a new Task only after no Task is
    active;
11. inspect Demand/Task projections, actor transcript, daemon/runtime logs, and
    cleanup state;
12. stop/delete exact actors and prove no process, socket, listener, lock, or
    isolated state root remains.

Manual evidence supplements the repeatable automated contract; it does not
replace it.

### 16.4 Final replacement audit

Search current code, schemas, tools, permissions, skills, architecture docs,
tests, and ignored current visual specs for exact retired Demand tokens. Generic
uses of words such as “dependency” or “superseded” in unrelated Artifact,
testing, or repository policy domains are not Demand residue.

The audit must prove absence of:

```text
demand.parent_id
demand.depends_on
demand_sys.set_parent
demand_sys.add_dependency
demand_sys.remove_dependency
demand_sys.split
demand_sys.mark_duplicate
demand_sys.supersede
DemandRelationConflict
E_DEMAND_RELATION
Demand terminal duplicate
Demand terminal superseded
```

Scoped negative tests may name these tokens only to forbid their return.

### 16.5 Observed acceptance outcome

The implementation followed the architecture without adding a repair path:

- the coherent focused milestone passed with 108 tests and 766 subtests;
- real Track comments created separate Dev Demands through the generic daemon
  delivery path;
- the actor's two-pass check absorbed a supplement into the active Task's
  Demand, merged both provenance refs, and left Task `basis_revision=1`;
- Task completion did not automatically complete Demand; the actor reread the
  latest Demand and explicitly completed it with the exact Task evidence;
- a later independent Demand remained separate and created a new Task only
  after the first Task was terminal;
- both real actors were stopped and deleted, their processes and sockets were
  absent, and the exact isolated acceptance root was removed;
- the default four-row aggregate is schema v2, its 33 non-target sibling files
  were unchanged during cutover, and no cutover entrypoint remains;
- the current-surface replacement audit returned no retired Demand relation or
  migration token;
- review-driven fault injection proved missing completed evidence previously
  could persist an invalid terminal; the Domain owner now rejects omitted or
  null evidence before transaction, and exact focused regressions prove the
  aggregate remains byte-identical and readable.

## 17. Rejected alternatives

### 17.1 Remove only actor actions

Rejected because record fields, loader behavior, permissions, tests, and current
documentation would preserve a hidden supported relation model.

### 17.2 Keep schema v1 with optional ignored fields

Rejected because optional retired fields are compatibility state and allow
future code to accidentally revive the old model.

### 17.3 Retain duplicate and superseded as convenient terminal outcomes

Rejected because semantic duplicate is canonicalization through
`absorb_into`; replacement is either revision of the same need or explicit
cancel-plus-new-Demand. Separate terminal outcomes add explanation without a
new current behavior.

### 17.4 Add correction or historical relation support

Rejected because real actor evidence proved execution without it. Shared
product, source, Track, Task, and Artifact context remain available through
their owning systems.

### 17.5 Put canonicalization into Task Sys or daemon

Rejected because Task Sys owns execution and daemon owns delivery. Either move
would duplicate Demand semantics and create cross-product state ownership.

### 17.6 Split Demand domain into a framework of lifecycle and matching services

Rejected because deletion makes the concrete owner smaller. No repeated
independent implementation has earned a framework or service split.

## 18. Completion conditions

The rebuild is complete only when:

1. schema v2 is the only normal reader/writer;
2. every current Demand record has the exact minimal field set;
3. the actor catalog and permissions expose exactly ten actions;
4. terminal lifecycle has exactly completed, canceled, and absorbed outcomes;
5. source provenance cannot be rewritten through revise;
6. actor guidance performs two-pass canonicalization and preserves the active
   Task's Demand as absorption target;
7. Task Sys and daemon boundaries remain unchanged and mechanically enforced;
8. all retired relation code, schemas, prompts, skills, tests, architecture
   text, and current visual artifacts are absent;
9. the one known runtime aggregate is explicitly cut over without touching
   unrelated retained state;
10. focused automated proof, real actor acceptance, residue audit, and cleanup
    proof all pass on the recorded source identity;
11. the final implementation and documentation are committed together rather
    than as fragmented plan-only commits.

No relation compatibility, no v1 fallback, no dual schema, no dormant action,
and no completed replacement claim before verification.
