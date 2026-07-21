# Dev Landing Page Multi-Demand Real-Actor Acceptance Record

Date: 2026-07-21
Status: completed runtime experiment; relation change intentionally not implemented
Environment: default real BuddySwitch environment at `/Users/chen/.codex-buddyswitch`
Repository source identity: `213d980c29cc1f6a247375ede06d7f74de676ea3`

## Acceptance claim

A real PM actor can send a sequence of related product requests to a real Dev
actor, the Dev actor can organize live requests and execute only one active Task
at a time, and the resulting Demand/Task state is sufficient to distinguish what
currently works from what remains unexplained after a Demand is terminal.

## Runtime identities

| Role | Actor | Thread | Model profile |
|---|---|---|---|
| PM | `act-pm-bc3e48655266` | `019f82a4-09d9-7ff3-bd4f-bbdeb6af228f` | `fast` |
| Dev | `act-dev-c3325d035f6c` | `019f82a4-2728-7951-bbab-0f27b11deeed` | parent `balanced`, side `fast` |

Both actors were created through the formal `./buddyswitch-codex` CLI in the
default environment. The pre-run instance inventory was empty. The launcher
seeded the shared source root from the repository's README-only
`projects/app`.

## Scenario and resulting records

The fictional product was FluxOps AI, an AI data-operations SaaS landing page.

| Stage | IM | Demand | Task | Observed organization |
|---|---|---|---|---|
| A: initial page | `msg-7c28c8b2e291` | `demand-05a9d621b353` | `task-demand-a015188a4b58` | New live root |
| B: in-flight supplement | `msg-da4f70369d68` | `demand-d305358e7d11` | none of its own | Absorbed into live A; A revised |
| C: post-completion mobile correction | `msg-4318cb314989` | `demand-4369074c88ee` | `task-demand-e014c9052c94` | New live root; no link to terminal A |
| D: post-completion estimator capability | `msg-f7da799c3d33` | `demand-b9581dc231d4` | `task-demand-148e1fd21644` | New live root; no link to terminal A/C |

PM remained a dispatch-only actor: no PM Demand or Task was created.

## Chronology and state evidence

### A and B: live organization worked

1. A arrived at `11:08:17+08:00` and became
   `demand-05a9d621b353`.
2. Dev checked A and created `task-demand-a015188a4b58` at basis revision 1.
3. While that Task was `in_progress.parent_processing`, B arrived at
   `11:10:21+08:00` as `demand-d305358e7d11`.
4. B waited unchecked while the active parent frame was busy. The daemon did
   not create a parallel Task or synchronously mutate the current Task.
5. In the next Demand Check, Dev loaded A and B, judged B to be the same
   deliverable, and called `demand_sys.absorb_into`.
6. A became revision 2 with the incident-timeline requirements merged into its
   description/detail. B became terminal `absorbed`, with `ref` pointing to A.
7. The existing Task remained the only active Task and retained its original
   `basis_revision: 1`. Dev consciously reconciled the revised Demand scope
   inside the active parent frame.
8. The Task completed at `11:15:32+08:00`. The outcome frame then completed A
   at `11:15:42+08:00`, with Task evidence and report `art-5fa0fd1937`.

Maximum observed active Task count was one.

### C: terminal predecessor was not part of organization

Independent 390px browser QA found two real touch-target defects:

- header demo CTA: approximately 35px high;
- recovery-arrow control: approximately 29×29px.

C arrived only after A was completed. Its Demand Check saw C as the sole live
Demand. Terminal A was absent from the compact live index, so Dev made no Demand
organization change and created a new root-backed Task.

The Task reused the same source root, media query, verification script, and
visual system. It changed only the mobile rules and focused regression proof.
After completion:

- mobile header CTA: `112.148×44` CSS px;
- mobile recovery control: `44×44` CSS px;
- 390px viewport document width: 375px, with no horizontal overflow;
- 1440px desktop document width: 1425px, with no horizontal overflow;
- Demand C completed with Task evidence and report `art-3f594ccb55`.

C exposes an escaped acceptance gap in A's broad “mobile usable” claim. It does
not prove that every later improvement should reopen A; it proves that the
stored Demand view cannot explain a corrective successor once A is terminal.

### D: a fresh root was appropriate

D asked for a separately deliverable incident-cost estimator, explicitly not a
correction. It also arrived after all prior Demands were terminal. Dev made no
organization change and created a new root-backed Task.

The Task reused the existing page and visual system, added one bounded pure
calculation module and one in-page form, and did not add a backend, persistence,
framework, or second page. Independent verification proved:

- `2 incidents × 5 hours × $100 = $1,000` monthly scenario cost;
- 50% recovery proportion displays `$500` opportunity;
- zero inputs display `$0`;
- the 100% slider boundary displays 100%;
- all results say `Scenario estimate only · Not a savings guarantee`;
- at 390px, form width is 335px inside a 375px document;
- number controls are 295×46px and the range control is 295×44px;
- no horizontal overflow was introduced;
- Demand D completed with Task evidence and report `art-5113d52ced`.

For D, a fresh lifecycle root accurately represented a new deliverable. The
shared product/source context, not a Demand-to-Demand relation, provided the
implementation continuity.

## Current implementation answer: completed does not become live

The current code has one unambiguous behavior:

1. `demand_sys.complete` writes a terminal record.
2. There is no reopen action.
3. `revise`, `set_parent`, dependency mutations, absorption targets, duplicate
   targets, and supersede targets require live records.
4. `demand_sys.check` builds `live_index` only from records whose `terminal` is
   `None`.
5. Therefore a later inbound request always starts as a new live Demand. The
   actor cannot attach it to, absorb it into, or revise the completed Demand
   through the current organization actions.

Observed C and D followed exactly this path:

```text
terminal predecessor remains immutable
              +
new inbound IM -> new live root -> Demand Check -> new Task -> new terminal
```

There was no hidden transition that changed A or C back to live.

## Hypothesis results

### H1 — frozen terminal plus new root is operationally sufficient

Partially supported. C and D both executed correctly, reused the current source,
and completed without a cross-terminal relation.

### H2 — a correction reveals premature completion or reopen pressure

Supported as a distinction, not as a reopen decision. C showed that A's mobile
acceptance evidence was incomplete. Current state cannot say that C corrects A.
The experiment does not justify automatically reopening every completed Demand.

### H3 — a legitimate new deliverable needs historical lineage

Not supported as a lifecycle requirement. D was correctly modeled as a new
root. Its relationship to the existing landing page is primarily a shared
product/artifact relationship, not evidence that A's lifecycle should continue.

### H4 — live execution relations and historical relations are different jobs

Supported. B needed a live merge because it changed the active deliverable. C
would benefit from historical corrective lineage. D needed neither live merge
nor lifecycle continuation to execute correctly.

## Design judgment

The shortest owner-correct conclusion is:

- keep terminal Demand immutable by default;
- do not reopen a completed Demand merely because a later Demand is related;
- do not connect every request touching the same product with a Demand relation;
- retain live `parent_id` / `depends_on[]` / absorption for active organization;
- treat explicit revocation of an earlier completion as a separate product
  decision, not a side effect of matching descriptions.

The actual remaining gap is narrower: a corrective Demand like C has no durable
way to say “this later work corrects the outcome of A.” If that explanation is
needed for proactive prioritization, completion audit, or user-facing Demand
organization, it should be a terminal-aware historical lineage capability with
no lifecycle side effect. The experiment proves the value of a corrective link;
it does not yet prove a generic relation graph, automatic reopen, or a taxonomy
of many relation types.

A next design iteration should first decide whether one concrete historical
`corrects` link is valuable enough to add. It should not implement a general
relation engine or make terminal records mutable on this evidence alone.

## Verification evidence

Controller checks:

```text
npm test
  Landing page content and responsive hooks verified.
  Incident-cost estimator calculations verified.

node --check app.js
node --check estimator.js
```

Desktop and 390px mobile behavior were independently inspected in a browser,
including normal calculation, zero/boundary calculation, disclosure text,
touch-target dimensions, control dimensions, and horizontal overflow.

The final Dev recap was a direct, explicitly read-only control turn. It called
only `context.summarize`, `task_sys.list`, `artifact.list`, and read-only source
inspection. It created no Demand or Task and changed no source.

## Runtime observations and residual risk

- Daemon and broker remained healthy with no recorded handler error.
- B was queued while the parent frame was busy and checked at the next actor
  opportunity; Task state alone was too coarse to show internal progress.
- A had one recovered CSS patch-context mismatch and one rejected unsupported
  artifact template; Dev recovered without corrupting state.
- Each actor-owned preview server was later stopped; controller preview servers
  were also stopped after inspection.
- This run used one Dev actor and one-active-Task throughput. It does not prove
  multi-actor ownership transfer, competing priorities, or large historical
  candidate retrieval.
- The shared FluxOps source and Demand/Task projections are intentionally
  retained after exact actor cleanup for later inspection.

## Cleanup result

- Dev and PM were stopped and deleted by their exact actor ids.
- Final `instance list` returned an empty inventory.
- Browser release reported inactive ownership and no pending browser schedule.
- No preview listener remained on port 4173.
- No actor process or socket remained for either actor id.
- All four Dev Demand projections and all three completed Task projections
  remained queryable after actor deletion.
- The generated FluxOps source remained under
  `/Users/chen/.codex-buddyswitch/project/workspace/projects/app`.
- Repository `projects/app` and unrelated dirty worktree changes were not
  modified by the runtime actors.
