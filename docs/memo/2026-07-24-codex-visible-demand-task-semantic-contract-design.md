# Codex-Visible Demand / Task Semantic Contract Design

Status: **implemented; isolated real-Actor acceptance passed; pending commit**

Date: 2026-07-24

## 1. Outcome

This change makes the current Demand / Task architecture understandable and
usable from the exact information Codex sees at runtime. It does not redesign
that architecture.

Acceptance sentence:

> In the current isolated Demand-triage / parent Demand-orchestration /
> main-thread native-Goal path, Codex can determine from runtime-visible tool
> semantics, the selected Skill, the current event prompt, and tool feedback
> when each Demand or Task action is appropriate, what every Actor-supplied
> field means, what state the call changes, and what the call does not prove or
> trigger.

The consumer path to prove is:

```text
Actor receives an inbound or orchestration event
  → Codex reads the current runtime contract
  → Codex chooses and calls the correct public Actor tool
  → the owning product commits one canonical state transition
  → Codex receives feedback that agrees with persisted state
  → the Web Actor consumer can observe the intended result
```

## 2. Frozen architecture and scope

The current live path remains:

```text
Inbound
  → isolated demand-triage side
  → no_action_needed / handled / create / merge_intake / revise / cancel
  → canonical Demand pool
  → independent parent demand-orchestration turn
  → task_sys.create
  → persistent main-thread native Goal
  → Goal complete
  → Task complete
  → independent parent reconciliation / next-selection turn
```

The primary implementation scope is Codex-visible semantic content:

- role bootstrap guidance;
- `$demand-triage` and `$demand-orchestration`;
- the two current handler prompts;
- Demand Sys and Task Sys public tool catalog text;
- `demand_triage.resolve` description and input-field descriptions;
- Demand / Task tool success and rejection feedback;
- tests of the exact rendered content and the resulting consumer path.

Owner inspection during RED exposed two contradictions that must be repaired
with the same change because prose cannot honestly mask them:

- an invalid `handled` proposal could deliver a Message before Demand-owned
  proposal validation rejected it;
- invalid Task inputs or cross-Actor reads could escape as generic runtime
  dispatch failures instead of Task-owned rejections.

The narrow owner-correct repair therefore also permits:

- Demand-owned proposal validation before any handled Message effect;
- Task-owned payload/authority rejection mapping.

Neither repair changes a persisted schema or adds an Actor-facing action.

This design does not add or change:

- Demand or Task schemas and domain mutations;
- public action names or action counts;
- permissions, authority, triggers, schedules, or recovery;
- handler or daemon-service business behavior;
- side, parent, or Goal thread ownership;
- a result-reporting tool;
- Control Main / Work Thread architecture;
- programmatic semantic duplicate detection;
- structured priority, acceptance-criteria, execution-plan, or result fields.

No live wording may teach future Control/Work architecture before that
architecture replaces the current path.

## 3. DESC review against `docs/bitter`

This revision applies four existing repository principles:

- [`Tool, Skill, And Prompt Layering Principles`](../bitter/2026-05-18-tool-skill-layering-principles.md):
  the host decides from runtime-visible tool semantics and tool feedback;
  prompt bulk must not compensate for a weak tool contract.
- [`Built-In Product Interface Principles`](../bitter/2026-06-25-built-in-product-interface-principles.md):
  Demand Sys and Task Sys own product meaning; tools, prompts, Skills, CLI, and
  Web are projections, not alternate semantic owners.
- [`End-To-End Contract Slice Principles`](../bitter/2026-06-25-end-to-end-contract-slice-principles.md):
  isolated layer tests do not prove the Actor-visible loop.
- [`Residue Cleanup Principles`](../bitter/2026-06-02-residue-cleanup-principles.md):
  a semantic replacement is incomplete while any live Actor surface teaches
  the retired meaning.

### 3.1 DESC is a catalog, not one large paragraph

In this memo, “DESC” means the complete runtime tool catalog:

```text
ToolDefinition
  ├─ description
  ├─ scope
  ├─ capability_boundary
  ├─ object_model
  ├─ use_when / do_not_use_when
  └─ ActionDefinition
       ├─ description
       ├─ use_when / do_not_use_when
       ├─ reads / writes / does_not_write
       ├─ success_effect / failure_state_guarantee
       ├─ returns / authority / durability / visibility
       └─ inputSchema field descriptions
```

Each part has one job:

| Catalog element | Required meaning |
|---|---|
| Tool description/model | What product capability and object family exist |
| Action description | The one atomic capability and its direct state effect |
| Use / do not use | Eligibility boundary, not a multi-step workflow |
| Input description | What the Actor-supplied value semantically contains |
| Read/write/return metadata | Exact product effects and result level |
| Tool response | What happened in this call, including no-change outcomes |

An action description must not contain reusable instructions such as “first
list every Demand, then get each one, then compare.” That sequence belongs to a
Skill.

### 3.2 The other layers stay narrow

| Layer | Owns | Must not contain |
|---|---|---|
| Role `AGENTS.md` | Stable product orientation and non-bypassable boundaries | Tool encyclopedia, payload schema, long SOP |
| Skill | Repeated judgment and sequencing across atomic tools | Full schema copy, private implementation, alternate feedback |
| Handler prompt | This event’s facts, attention reason, required Skill | Reusable policy, field templates, decision tables |
| Tool catalog | Atomic capability, inputs, effects, use boundary | Business workflow sequence |
| Tool response | Actual effect of this invocation | New eligibility policy or aspirational state |

### 3.3 Actual runtime projection

Current source inspection establishes:

- `context.summarize` projects compact tool-level affordances;
- `context.get.tool_catalog` projects the full `ToolDefinition`,
  `ActionDefinition`, and input schemas;
- native MCP `tools/list` renders each action description together with its
  action metadata and input schema;
- `demand_triage.resolve` is a separate thread-scoped MCP tool and must carry
  its own complete atomic contract.

Therefore changing only prose in a Skill is insufficient, and putting every
rule into `action.description` would also be wrong.

### 3.4 Corrections made to the earlier draft

The earlier draft had three layering errors:

1. Some action descriptions embedded `list → get → compare → mutate`
   workflow. Those steps now live only in the relevant Skill.
2. Skills copied complete input-field contracts and nullable-field tables.
   Exact field meaning now lives only in the runtime tool schema.
3. Task objective construction and Goal completion ordering were fully taught
   in both Skill and tool fields. The tool field now owns objective content;
   the Skill owns when to construct it and when native Goal completion is
   allowed.

## 4. Semantic ownership and claim limit

The ownership chain is:

```text
Demand / Task product core
  → public ToolDefinition and result contract
  → native MCP / context projection
  → Skill workflow
  → current event prompt
  → Codex decision
```

The tool catalog projects product semantics. It must not invent semantics that
the owner contradicts.

Current Demand and Task domains mostly validate shape and non-empty strings.
This content-only change can guide Codex toward better semantic arguments, but
it cannot honestly claim that:

- duplicate Demands are mechanically impossible;
- Demand satisfaction is structurally complete;
- Task objectives are programmatically executable;
- selection reasons are programmatically grounded.

If implementation inspection finds a proposed description that disagrees with
actual state effects, the owning behavior/contract must be corrected or the
description must be narrowed. Prompt text must not hide the mismatch.

## 5. Canonical product terms

These meanings are stable across all Codex-visible surfaces:

- **Inbound fact**: source evidence awaiting isolated triage; not yet a
  canonical Demand.
- **Demand**: one durable Actor-owned unmet need that states what must become
  true and how satisfaction can be evidenced.
- **Task**: the Actor’s one current execution commitment, retaining the Demand
  snapshot reference that was current when selected.
- **Native Goal**: Codex’s execution-completeness mechanism for the current
  Task objective.
- **Task completion**: terminal proof that one execution commitment ended;
  evidence for Demand reconciliation, never automatic Demand completion.
- **Selection reason**: a grounded record of why one live Demand occupies the
  single current Task slot now.

## 6. Role bootstrap

Replace the current duplicated Demand/Task/Goal paragraph in each role
template with compact stable boundaries:

```markdown
- Raw inbound information is resolved only by its isolated Demand-triage
  side. Triage may handle it or change canonical Demand state; it never creates
  Task work.
- Only an independent parent Demand-orchestration turn may reconcile terminal
  Tasks, compare live Demands, and fill the single Task slot.
- A Task binds one current Demand reference to one native Goal objective.
  Task or Goal completion does not itself complete the Demand.
- Goal work completes only after its required result, durable user-facing
  delivery, and verification are complete. Goal work does not reconcile
  Demands or select later work.
```

Role guidance must not contain field templates, decision tables, source-
specific delivery procedures, or tool payload schemas.

## 7. Demand triage contract

### 7.1 Handler prompt

The handler carries the event and selects the workflow:

```text
[DEMAND TRIAGE — isolated side]

Use $demand-triage to resolve this one inbound fact against the Actor's current
canonical live Demands. Commit one final resolution through
`demand_triage.resolve` before ending this turn.

Inbound fact:
{fact}
```

The handler prompt must not copy decision definitions, field rules, or Demand
text templates.

### 7.2 `$demand-triage`

The Skill owns the repeated read/compare/decide sequence:

```markdown
---
name: demand-triage
description: Resolve one raw inbound fact against the complete current live
  Demand pool in an isolated triage side.
---

# Demand triage

This Skill runs only in an isolated Demand-triage side. The inbound fact is
source evidence, not a Demand. Do not create Task work, mutate Demand state
through ordinary Demand write tools, send a Message directly, or defer the
semantic judgment to the parent.

1. Read the exact inbound fact.
2. Call `demand_sys__list(state="live")`.
3. Before `create`, read every live Demand in full with `demand_sys__get`.
   Before targeting an existing Demand, reread that Demand in full.
4. Read the source Message when sender, conversation, exact wording, or reply
   relationship affects the judgment.
5. Choose exactly one resolution:
   - `no_action_needed`: no unmet obligation and no reply is required;
   - `handled`: one immediate verified reply fully satisfies the need;
   - `create`: a new independent unmet need;
   - `merge_intake`: compatible evidence/detail/constraint for one existing
     Demand without changing its intended outcome;
   - `revise`: the intended outcome, boundary, binding constraint, delivery,
     or satisfaction meaning changed;
   - `cancel`: the need was explicitly withdrawn or invalidated.
6. Construct arguments using the exact runtime field descriptions for
   `demand_triage.resolve`.
7. Call `demand_triage.resolve` exactly once and follow its feedback.

Do not decide from compact summaries, Task text, or memory of an earlier
Demand revision. Do not emit an uncommitted proposal as the final answer.
```

The Skill deliberately does not repeat the resolver’s six-field schema.

### 7.3 `demand_triage.resolve`

Action description:

```text
  Consume this isolated triage side's one-shot capability and attempt to commit
  its resolution for the bound inbound fact. The Demand owner atomically settles
  the receipt and applies any authorized Demand change, or returns a stale target
  to pending for a fresh side retry. `handled` also owns idempotent reply delivery
  and structural verification of the durable reply relationship and identities.
  Whether the content satisfies the need remains the Actor's judgment. This
  action never creates Task work.
```

Input-field descriptions:

| Field | Exact proposed description |
|---|---|
| `decision` | Resolution effect: `no_action_needed` leaves no obligation or reply; `handled` sends one reply that fully satisfies the need; `create` declares an independent unmet need; `merge_intake` adds compatible meaning to one live Demand; `revise` replaces changed Demand meaning; `cancel` withdraws or invalidates one live Demand. |
| `reason` | Grounded explanation of this inbound’s relationship to the current live Demand pool and why this resolution effect is correct. |
| `demand_ref` | Current opaque reference for the targeted live Demand. Required for `merge_intake`, `revise`, and `cancel`; otherwise null. |
| `description` | Complete post-resolution one-sentence canonical unmet need and desired outcome. Required for `create`, `merge_intake`, and `revise`; otherwise null. |
| `detail` | Complete post-resolution satisfaction contract: outcome, material boundaries, binding constraints, required delivery, and satisfaction evidence. Required for `create`, `merge_intake`, and `revise`; otherwise null. |
| `reply_content` | Complete reply that fully satisfies the bound inbound need with no remaining obligation. Required only for `handled`; otherwise null. |

The schema shape and decision enum do not change.

## 8. Demand Sys public Actor contract

The Actor-facing surface remains exactly:

```text
list / get / create / revise / complete / cancel
```

Host-owned intake ids, provenance derivation, revision counters, CAS details,
terminal-record layout, Task synchronization, and storage paths remain hidden.

### 8.1 Tool-level catalog

```text
description:
  Own the active Actor's canonical unmet needs independently of Task execution.

scope:
  Inspect or express Actor intent to create, replace, satisfy, or withdraw one
  canonical Demand.

capability boundary:
  Raw inbound triage, source-provenance derivation, idempotency, concurrency,
  storage, and Task/Goal coordination remain host-owned.

object model:
  A Demand is one durable Actor-owned unmet need whose canonical text states
  what must become true and how satisfaction can be evidenced. It is live
  until explicitly completed or canceled. It is not a Task, plan, progress
  message, or native Goal.
```

### 8.2 `demand_sys.list`

```text
action description:
  Return compact Actor-owned Demand summaries for the selected lifecycle set
  without changing state.

state:
  Lifecycle set to enumerate: `live`, `terminal`, or `all`; defaults to
  `live`.

use when:
  You need to discover or compare the canonical Demand pool.

do not use when:
  You need complete content or a mutation reference for one Demand; use
  `demand_sys.get`.
```

### 8.3 `demand_sys.get`

```text
action description:
  Return one complete current Actor-owned Demand and its opaque mutation
  reference without changing state.

demand_id:
  Exact Actor-owned Demand id returned by `demand_sys.list` or a successful
  Demand receipt.

use when:
  You need one Demand's full current meaning, provenance, lifecycle, or
  mutation reference.

do not use when:
  You only need to enumerate the pool; use `demand_sys.list`.
```

### 8.4 `demand_sys.create`

```text
action description:
  Create one durable independent canonical Demand. This action does not create
  Task work or a native Goal.

description:
  One durable sentence naming the unmet need and desired outcome. It remains
  meaningful across possible Tasks and is not an execution step,
  acknowledgement, status update, or solution plan.

detail:
  Complete satisfaction contract for the need: desired observable outcome,
  material boundaries, binding constraints, required user-facing delivery,
  and evidence that would justify Demand completion. Preserve material source
  meaning; exclude Task selection and Goal-lifecycle instructions.

use when:
  The Actor identifies one independent unmet need not represented by a live
  Demand.

do not use when:
  The input is untriaged, duplicates or supplements a live Demand, or changes
  a live Demand's canonical meaning.
```

### 8.5 `demand_sys.revise`

```text
action description:
  Replace the complete canonical meaning of one live Demand. This is a full
  replacement, not a text patch, and it does not change Task or Goal state.

demand_ref:
  Current opaque reference returned by `demand_sys.get` for the exact Demand
  revision. Never construct or decode it.

description:
  Complete replacement one-sentence unmet need and desired outcome.

detail:
  Complete replacement satisfaction contract, preserving every still-valid
  prior requirement and incorporating the changed outcome, boundary,
  constraint, delivery, or evidence condition.

reason:
  Grounded explanation of what canonical meaning changed and why replacement
  is correct. This explains the call; it is not promised as persisted Demand
  history.

use when:
  The live Demand's intended outcome, boundary, binding constraint, required
  delivery, or satisfaction meaning changed.

do not use when:
  New information changes no canonical meaning, belongs to an independent
  need, or remains raw inbound owned by triage.
```

### 8.6 `demand_sys.complete`

```text
action description:
  Terminalize one live Demand as satisfied with a concrete summary and durable
  evidence references. This action does not change Task or Goal state.

demand_ref:
  Current opaque reference for the exact live Demand whose latest satisfaction
  contract was evaluated.

summary:
  Concrete account of how the latest desired outcome, constraints, delivery,
  and satisfaction conditions were met. Name the delivered result rather than
  only Task or Goal status.

evidence_refs:
  Exact durable references that together prove the need and its required
  delivery are satisfied; exclude placeholders, inaccessible references, and
  status-only claims.

evidence item type:
  Owning evidence product or kind.

evidence item ref.task_id:
  Exact terminal Task id for `task_sys.task` evidence.

evidence item ref.id / ref.key:
  Exact stable identity or semantic key required by the owning evidence
  product.

use when:
  The latest complete need and every required delivery condition are
  satisfied by verified durable evidence.

do not use when:
  Only Task/Goal execution ended, delivery is missing, evidence is unverified,
  or any part of the Demand remains unmet.
```

### 8.7 `demand_sys.cancel`

```text
action description:
  Terminalize one live Demand as withdrawn, invalidated, or no longer
  required. This action does not change Task or Goal state.

demand_ref:
  Current opaque reference for the exact live Demand being withdrawn.

summary:
  Concrete withdrawal or invalidating fact explaining why satisfaction is no
  longer required; do not describe successful completion.

use when:
  The need itself was withdrawn, invalidated, or deliberately abandoned.

do not use when:
  The need was satisfied, remains valid but blocked or lower priority, or only
  its current Task stopped or failed.
```

## 9. Demand orchestration contract

### 9.1 Handler prompt

The handler carries only the attention facts and selects the Skill:

```text
[DEMAND ORCHESTRATION — independent parent turn]

Use $demand-orchestration to process the current canonical attention.

Attention:
- demand_pool_revision: {pool_revision}
- live_demand_count: {live_count}
- newly_terminal_task_ids: {terminal_task_ids}
```

Selection criteria, completion rules, field templates, and source-specific
verification do not belong in this prompt.

### 9.2 `$demand-orchestration`

The Skill owns the repeated multi-tool workflow:

```markdown
---
name: demand-orchestration
description: Reconcile newly terminal Tasks against their latest Demands and
  fill the single empty Task slot from the complete current live Demand pool.
---

# Demand orchestration

This Skill runs only in an independent parent Demand-orchestration turn. Task
completion is evidence, not Demand completion. Do not call native
`create_goal` or `update_goal`; Task Sys owns Goal reconciliation and Task Goal
work owns Goal completion.

## Reconcile newly terminal Tasks

For every listed terminal Task:

1. Read the exact Task with `task_sys__get`.
2. Read its latest canonical Demand with `demand_sys__get`.
3. Verify actual deliverables and required user-facing delivery through their
   owning products. Task or Goal status alone is not proof.
4. Complete the Demand only when its latest complete meaning is satisfied by
   exact durable evidence; cancel only for withdrawal/invalidation; revise
   only when the remaining canonical meaning changed; otherwise leave it live.

## Fill the Task slot

1. Read active Tasks with `task_sys__list(status="active")`.
2. If one Task is active, stop. If more than one is active, surface the
   invariant failure and create nothing.
3. If the slot is empty, list live Demands and read every candidate in full.
4. Compare only grounded facts: explicit urgency/deadline, user commitment,
   blocked downstream work, continuity, readiness, and staleness. Do not
   invent priority, deadlines, dependencies, or commitments.
5. When live Demands exist, select exactly one and state the decisive grounded
   comparison in `selection_reason`.
6. Convert that Demand into one Task-sized execution commitment using the
   exact runtime field contract of `task_sys__create`.
7. Call `task_sys__create` once and follow its feedback.

The Task objective must not perform Demand lifecycle reconciliation or select
later work. Native Goal completion is allowed only after the objective's
result, durable delivery, evidence, and checks are complete.

## IM-origin Demand

For an `im.message.created` source, reread the exact source Message. The Task
objective must require a durable reply to that exact Message and verification
of the returned reply identity, sender, target, content, and `reply_to`.
Terminal reconciliation must reread that durable reply. Missing delivery
leaves the Demand live.
```

The Skill deliberately does not copy the `task_sys.create` payload schema or
restate every objective subfield.

## 10. Task Sys public Actor contract

The Actor-facing surface remains exactly:

```text
list / get / create / cancel
```

Goal binding ids, reconciliation mechanics, Task store paths, and lifecycle
transition internals remain host-owned.

### 10.1 Tool-level catalog

```text
description:
  Own the Actor's single Demand-bound execution slot and its binding to one
  native Codex Goal.

scope:
  Inspect the current Task slot, create one Demand-bound Task, or explicitly
  cancel one active Task.

capability boundary:
  Task Sys owns Task records and native Goal binding/reconciliation. Native
  Goal completion owns successful Task completion. Task Sys never mutates a
  Demand.

object model:
  A Task records one Demand snapshot reference that was current when selected,
  one self-contained Goal objective, one grounded selection reason, at most one
  native Goal binding, and an active/completed/canceled lifecycle.
```

### 10.2 `task_sys.list`

```text
action description:
  Return Actor-owned Task summaries for the selected lifecycle set without
  changing state.

status:
  Task lifecycle set to enumerate: `active`, `terminal`, or `all`; defaults to
  `active`.

limit:
  Positive maximum number of summaries to return.

use when:
  You need to inspect the single Task slot or discover terminal Task ids.

do not use when:
  You need complete content for one known Task; use `task_sys.get`.
```

### 10.3 `task_sys.get`

```text
action description:
  Return one complete current Actor-owned Task without changing state.

task_id:
  Exact Actor-owned Task id returned by `task_sys.list`, `task_sys.create`, or
  orchestration attention.

use when:
  You need the exact Demand reference, objective, selection reason, Goal
  binding, status, or terminal result for one Task.

do not use when:
  You only need to inspect the Task slot; use `task_sys.list`.
```

### 10.4 `task_sys.create`

```text
action description:
  Create or idempotently replay one Task for one current Demand
  reference and request native Goal reconciliation. This action does not
  mutate, satisfy, or reprioritize a Demand.

demand_ref:
  Current opaque Demand reference returned by `demand_sys.get` for the
  selected live Demand. Never construct or decode it.

objective:
  Self-contained execution contract for one native Goal: required observable
  result, exact durable deliverables, material boundaries and constraints,
  completion checks, user-facing delivery, and evidence to retain. Exclude
  Demand lifecycle reconciliation and later-work selection.

selection_reason:
  Grounded decision record explaining why this Demand should occupy the single
  Task slot now after comparison with the current live pool. State the
  decisive facts and timing; do not use an unsupported generic priority claim.

use when:
  Parent Demand orchestration selected one current live Demand and the Actor's
  Task slot is empty.

do not use when:
  A Task is active, the selected Demand is not current/live, or the execution
  commitment remains ambiguous.
```

### 10.5 `task_sys.cancel`

```text
action description:
  Terminalize one active Task as canceled and request idempotent native Goal
  cleanup. This action does not cancel, complete, or revise its Demand.

task_id:
  Exact active Actor-owned Task id to stop.

reason:
  Concrete execution-level reason the Task must stop without successful Goal
  completion, such as an invalid objective, explicit stop decision, or
  unrecoverable execution condition.

use when:
  The Actor explicitly decides the current Task must terminate without
  successful Goal completion.

do not use when:
  Work completed successfully; the Demand itself should be canceled; or
  execution is only blocked, paused, usage-limited, or budget-limited.
```

## 11. Tool feedback contract

Tool feedback reports the observed call result. It does not repeat workflow
policy.

Every write response must expose:

- success or rejection;
- `state_changed`;
- affected durable object id;
- refreshed opaque ref when applicable;
- actual Task/Goal reconciliation state when applicable;
- the exact no-change guarantee on rejection;
- correctable fields or a safe atomic reread/retry action.

### 11.1 Demand success effects

```text
create:
  Created one live canonical Demand and returned its current demand_ref.
  No Task or Goal was created.

revise:
  Replaced the live Demand's canonical meaning and returned its refreshed
  demand_ref. No Task or Goal changed.

complete:
  Terminalized the Demand as completed with the supplied summary and evidence.
  No Task or Goal changed.

cancel:
  Terminalized the Demand as canceled with the supplied reason. No Task or
  Goal changed.
```

An idempotent replay must explicitly say no new mutation occurred.

A stale-ref rejection must say:

```text
The Demand changed after this ref was read. No mutation occurred. Read the
current Demand again and retry only after re-evaluating the intended action
against its latest complete meaning.
```

### 11.2 Task success effects

```text
new Task with Goal binding:
  Created one active Demand-bound Task, persisted its objective and selection
  reason, and reconciled its native Goal binding. The Demand did not change.

exact replay:
  The same Task selection already exists; no new Task was created. Returned
  the current Task and Goal reconciliation state. The Demand did not change.

durable Task pending Goal reconciliation:
  Created the active Task durably, but Goal reconciliation is pending or
  failed. Do not create another Task. The returned state identifies the
  recoverable reconciliation result.

Task cancel:
  Terminalized the Task as canceled and requested Goal cleanup. The Demand did
  not change.
```

## 12. One-owner consistency rules

The implementation must preserve:

1. Demand field meaning lives in Demand tool/resolver input descriptions.
   Skills reference it instead of copying it.
2. Task objective and selection-reason meaning lives in Task tool input
   descriptions. Orchestration teaches when and how to make the judgment.
3. A handler prompt selects a Skill and carries current facts only.
4. Role guidance states stable boundaries only.
5. Tool feedback reports actual effects and never introduces new eligibility
   rules.
6. Task complete and Goal complete are never automatic Demand completion.
7. A final assistant message is never durable Message, artifact, or Track
   delivery.
8. Current wording keeps isolated triage side, independent parent
   orchestration, and main-thread native Goal until a later replacement
   actually lands.

## 13. Implementation and acceptance

### Step 1 — prove the current semantic gap

Add claim-scoped RED tests against the actual consumer projections:

- render native MCP `tools/list`, not only internal dataclasses;
- inspect `context.summarize` and `context.get.tool_catalog`;
- inspect `demand_triage.resolve` `tools/list`;
- assert the Actor-visible field meanings and lifecycle boundaries;
- assert success/rejection feedback agrees with persisted effects.

These tests are contract guards, not claims that Codex understood the prose.
Schema-shape assertions and a small number of stable boundary-text assertions
are useful because `tools/list` and `context.get.tool_catalog` are the actual
Actor inputs. Broad word-presence checks are not acceptance evidence: wording
can be present while Codex still chooses the wrong action. Behavioral tests
therefore prove persisted effects and feedback, and the real Actor loop proves
the model-facing decision path.

### Step 2 — replace live content at its owning layers

Update only:

- `tools/launcher/assets/roles/*/AGENTS.md`;
- `buddyswitch/skills/shared/demand-triage/SKILL.md`;
- `buddyswitch/skills/shared/demand-orchestration/SKILL.md`;
- the two current handler prompt constants;
- `tools/launcher/demand_triage_mcp_server.py` descriptions;
- `tools/launcher/demand_triage_runtime.py` pre-effect validation ordering;
- `scripts/env/domain/demand_sys.py` public validation projection;
- `scripts/env/tools/demand_sys/tool.py` catalog text;
- `scripts/env/tools/task_sys/tool.py` catalog text;
- Task-owned read/payload rejection mapping;
- owning Demand/Task feedback builders where current feedback is generic;
- exact affected contract tests.

No second description registry, prose mirror, adapter, alias, or fallback is
allowed.

### Step 3 — verify the complete Actor loop

After focused automated GREEN, use a real Web Actor and logs to observe:

1. acknowledgement/FYI → `no_action_needed`, no Demand;
2. immediately answerable IM → `handled`, verified reply, no Demand;
3. supplemental fact → `merge_intake`, no duplicate Demand;
4. changed boundary → `revise`, complete replacement meaning;
5. independent obligation → `create`, self-contained Demand;
6. multiple live Demands → one grounded Task selection;
7. Task creation → persisted self-contained objective and selection reason;
8. terminal Task → explicit evidence-based Demand reconciliation rather than
   automatic completion.

Acceptance requires the actual tool name, actual arguments, actual result
envelope, persisted Demand/Task state, logs, and Web-visible delivery to agree.
A plausible final message or isolated unit GREEN is insufficient.

### Step 4 — observed real-Actor result

The acceptance run used an isolated shared root and one real Dev Actor:

```text
actor: act-dev-4d064823be15
main thread: 019f94e2-63af-7790-9786-ffedf8f5be9b
parent capability: Balanced
side capability: Fast
```

Observed outcomes:

| Inbound | Persisted resolution | Observable result |
|---|---|---|
| FYI with no reply/work requested | `no_action_needed` | no Demand, no Task, no reply |
| `7+5` immediate question | `handled` | durable Web reply `12`, no Demand |
| independent countdown delivery | `create` | Demand `demand-68a0b5a8476e` |
| independent acceptance-checklist delivery | `create` | separate Demand `demand-c8a987c0e9ab` while the first Task was active |
| compatible checklist format/date addition | `merge_intake` | same second Demand, revision 2, no duplicate |
| checklist scope changed from three to four sections | `revise` | same second Demand, revision 3, complete replacement meaning |

Single-slot execution then behaved as designed:

1. Only the countdown Demand became Task
   `task-demand-4390d64bd17a` while both Demands were live.
2. Its native Goal completed after 446 seconds and 88,146 tokens. Task
   completion did not change the Demand.
3. A later independent parent reconciliation verified the files, 4/4 tests,
   and durable reply `msg-4dbf10660ddf`, then completed the first Demand.
4. With the Task slot empty, the parent selected the only remaining live
   Demand at revision 3 and created Task `task-demand-59e0ca38643d`.
5. Its native Goal completed after 123 seconds and 29,777 tokens.
6. A later independent parent reconciliation verified the four-section
   artifact and durable reply `msg-521767e8eae3`, then completed the second
   Demand.

The final Web projection showed:

```text
thread state: idle
Task Sys: 0 active
recent Tasks: 2 completed
both durable replies visible in their source message relationships
```

The final stores agreed with the Web projection: two terminal Tasks, two
terminal completed Demands, and each Demand carried both its Task evidence and
its exact `im.message.reply` evidence. This proves the current Task-complete →
independent Demand-reconciliation → next-Demand-selection loop without
claiming that Task completion automatically satisfies a Demand.

### Step 5 — default shared-state residue discovered

The first attempt against the default shared root was blocked before Actor
acceptance by seven retired Task records containing the old
`source_ref` / `execution` / `events` / `inbound_context` shape. Current
`task_sys.list` correctly rejects those records; the Web Actor-console read
therefore fails rather than silently accepting the retired schema.

This is not fixed with a fallback parser, compatibility adapter, or selective
skip. The product implementation was accepted in an isolated current-schema
root. Cutting over the user's default shared state remains a separate,
explicitly authorized destructive rebuild operation after code freeze. Until
that cleanup occurs, default-root Web acceptance is blocked by known
historical data residue; this memo does not claim otherwise.

## 14. Replacement and residue proof

The content implementation must prove:

- Skills do not copy full tool schemas;
- handler prompts do not copy reusable decision rules;
- role files do not contain field templates;
- action descriptions contain no multi-tool workflow sequence;
- retired `task_sys.outcome_frame`, legacy Task frames, and `need_parent` do
  not appear on scoped current live surfaces;
- future Control/Work terminology does not enter current guidance;
- no separate description registry or compatibility wording remains.

Historical memos are excluded from residue scans.

## 15. Claims intentionally not made

Even after this content implementation passes, it will not prove:

- semantic completeness is mechanically enforced by the domain;
- duplicate Demands are programmatically impossible;
- Demand relationships or priorities are structurally represented;
- Task result content is durably recorded;
- fixed Control/Work threads exist;
- the current side/parent architecture has been replaced.

Those remain separate future product changes.

## 16. Verification record

Frozen claim-scoped automated evidence:

```text
63 passed, 98 subtests
  native MCP/context projections
  Demand/Task response contracts
  triage resolver and side flow
  orchestration prompt/Skill boundaries

95 passed, 486 subtests
  env-tool end-to-end path
  broker behavior and lifecycle
  Demand/Task architecture boundaries
  tool runtime and semantic contracts

52 passed, 294 subtests
  Actor environment build safety
  runtime Skill materialization
  role bootstrap environment
```

The repository-wide `./buddyswitch-test full` entry was also run. Its unit
stage stopped with 426 passing tests, 1,148 passing subtests, and seven
subfailures in
`ExternalControlArchitectureTests.test_durable_architecture_names_the_final_single_track_boundaries`.
Those subfailures require exact phrases that are absent from
`docs/arch/web-interface-call-architecture.md`. Both the test and document are
byte-identical to HEAD `8d559380b1df2a869d4e2313354894efcc8c6c1b`; this change does not touch them.
They remain an explicit pre-existing full-suite baseline failure rather than
being hidden by unrelated architecture-document edits.

Operational cleanup was verified after the real-Actor run:

- the test Actor was stopped and deleted;
- ports 8765 and 4173 had no remaining listeners;
- the isolated runtime root was moved to the system Trash;
- the user's default shared root and its known retired Task records were not
  modified.
