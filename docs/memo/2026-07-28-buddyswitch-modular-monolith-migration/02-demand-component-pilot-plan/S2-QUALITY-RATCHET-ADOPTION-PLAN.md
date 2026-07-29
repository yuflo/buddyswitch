# S2 Quality-Ratchet Adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` or `superpowers:executing-plans`
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for
> tracking.

**Goal:** Project the accepted S2 delivery lessons into the existing execution
governance, handoff templates and BuddySwitch testing references so future
Codex executors see the rules at the moment they act.

**Architecture:** Keep root `AGENTS.md` and `$buddyswitch-testing` as the
durable judgment owners. `00-execution-governance.md` owns the active
migration-plan projection; Goal Packets, the executor handoff card and the
coordination hub project it into execution context. The S2 retrospective
remains historical rationale only.

**Tech Stack:** Markdown governance artifacts, BuddySwitch repository skills,
`rg`, Git artifact checks.

---

## 1. Source and scope

```text
Worktree:
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool

Starting commit:
3f53fc33625f9d5e1215eefcfeba77a8d086192a

Starting branch:
fea-tool

Starting upstream:
origin/fea-tool

Executable source/test/runtime changes:
forbidden
```

Allowed files:

```text
.agents/skills/buddyswitch-testing/references/evidence.md
.agents/skills/buddyswitch-testing/references/review.md
docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/
  00-coordination-hub.md
  00-execution-governance.md
  executor-handoff-card.md
  stage-acceptance-template.md
  stage-goal-packet-template.md
  stage-implementation-plan-template.md
  02-demand-component-pilot-plan/README.md
  02-demand-component-pilot-plan/S2-DELIVERY-RETROSPECTIVE.md
  02-demand-component-pilot-plan/S2-QUALITY-RATCHET-ADOPTION-PLAN.md
```

No other file may change.

## 2. Task 1 — Run the skill pressure baseline

**Files**

- Read:
  `.agents/skills/buddyswitch-testing/SKILL.md`
- Read:
  `.agents/skills/buddyswitch-testing/references/evidence.md`
- Read:
  `.agents/skills/buddyswitch-testing/references/review.md`
- Record:
  `docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/02-demand-component-pilot-plan/S2-DELIVERY-RETROSPECTIVE.md`

- [x] **Step 1: Give a read-only Codex worker the current pressure scenario**

Use this exact scenario:

```text
You are reviewing a frozen BuddySwitch stage candidate under the current root
AGENTS.md, current stage templates and $buddyswitch-testing. The candidate:

1. had one timeout, then passed the same test three times without a diagnosed
   owner;
2. required a manually installed package absent from requirements-test.txt;
3. edits src/buddyswitch, while its plan schedules GREEN before runtime
   reprovision;
4. tests process cleanup using a PID marker written asynchronously by the
   child;
5. proposes adding one cleanup call to another early-return branch although
   Git history contains a prior branch-local fix for the same invariant.

Do not edit files. State whether you would accept, rerun, repair or stop each
item, which current instruction made the decision obvious, and which decision
was ambiguous or easy to miss.
```

Expected baseline:

- existing skill rejects blind reruns;
- active templates make runtime ordering easy to miss or contradictory;
- declared dependency provenance is not prominent in the handoff;
- process-identity and all-terminal-exit review are not explicit enough.

- [x] **Step 2: Record only demonstrated instruction gaps**

Add a compact pressure-baseline section to the retrospective. Do not add a
rule that the current worker already found clear unless a Goal Packet must
project it at execution time.

## 3. Task 2 — Tighten the live execution owner

**Files**

- Modify:
  `docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/00-execution-governance.md`
- Modify:
  `docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/00-coordination-hub.md`

- [x] **Step 1: Add the READY environment and ordering gates**

Extend the existing READY evidence table with:

```text
Declared environment:
the recorded build/test/runtime environment is reproducible from committed
declarations; no ad hoc package or hidden local state is required.

Execution order:
every environment-consuming proof is ordered after the mutation and
reprovision/verification that makes the environment current.
```

- [x] **Step 2: Add failure-history and cleanup-attribution gates**

Require every checkpoint/acceptance return to disclose all
failure/timeout/flake/residue signals since freeze and their owning
disposition. Require process/resource identity to be captured before cleanup
deletes its attribution files or root.

- [x] **Step 3: Project the same requirements through the hub**

Add declared environment, mutation-to-proof ordering, complete failure history
and identity-safe cleanup to the just-in-time packet and hub acceptance lists.
State that the hub links the S2 retrospective only as historical rationale;
root `AGENTS.md` and the testing skill remain durable authorities, while
execution governance remains the current migration-plan projection.

## 4. Task 3 — Put a visible reminder in every execution handoff

**Files**

- Modify:
  `docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/stage-goal-packet-template.md`
- Modify:
  `docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/stage-implementation-plan-template.md`
- Modify:
  `docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/stage-acceptance-template.md`
- Modify:
  `docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/executor-handoff-card.md`

- [x] **Step 1: Add one projected execution reminder**

Add this compact block to the Goal Packet and handoff card:

```text
Before acting:
- unresolved failure/timeout/flake/residue => diagnose and stop; a later pass
  does not erase it;
- undeclared dependency or hidden environment mutation => stop;
- src/buddyswitch mutation => rebuild/install/activate/verify before the next
  ./buddyswitch-test command;
- resource cleanup => capture parent-known identity and stop the owner before
  deleting attribution;
- repeated branch-local lifecycle repair => inspect all terminal exits and
  relevant history before editing.
```

The block explicitly cites root `AGENTS.md`, `$buddyswitch-testing`,
`00-execution-governance.md`, D-037/D-044 and, for S3, the S2 retrospective
as historical rationale.

- [x] **Step 2: Correct the implementation-plan task order**

Between implementation and GREEN insert:

```text
If src/buddyswitch/** changed, rebuild/install/activate/verify the declared
runtime. If it did not, record exact inapplicability. No public-runner command
may precede this gate.
```

- [x] **Step 3: Make acceptance disclose contrary evidence**

Add exact fields for:

- declared dependency/runtime identity;
- every failure/timeout/flake/residue since freeze;
- owner and disposition;
- process/resource identity captured before deletion;
- rejection when any material signal remains unresolved.

## 5. Task 4 — Close only demonstrated testing-skill gaps

**Files**

- Modify:
  `.agents/skills/buddyswitch-testing/references/evidence.md`
- Modify:
  `.agents/skills/buddyswitch-testing/references/review.md`

- [x] **Step 1: Extend evidence identity**

Add:

- declared dependency inputs and ad hoc environment mutation;
- complete superseding failure history since freeze;
- rule that a later pass cannot restore validity without owning diagnosis;
- cleanup identity captured before destructive teardown.

- [x] **Step 2: Extend reviewer probes**

Add:

- parent-known real process identity instead of child-authored timing markers;
- owner stop before root/identity deletion;
- all-terminal-exit and relevant-history review before another branch-local
  lifecycle patch.

Do not repeat test-selection rules or create another skill.

## 6. Task 5 — Record adoption without creating a new owner

**Files**

- Modify:
  `docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/02-demand-component-pilot-plan/S2-DELIVERY-RETROSPECTIVE.md`
- Modify:
  `docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/02-demand-component-pilot-plan/README.md`

- [x] **Step 1: Record the pressure baseline and final projection**

Change retrospective status to `ADOPTED`, record:

- baseline findings;
- exact durable owners and active plan projections changed;
- no new state, validator, runner, policy owner or executable change;
- S3 must cite the live rules and the retrospective rationale.

- [x] **Step 2: Add the adoption plan to the S2 pack index**

List this plan after the retrospective and mark both historical/non-executable.

## 7. Task 6 — Verify and checkpoint the governance ratchet

**Files**

- Verify every allowed file above.

- [x] **Step 1: Verify scope**

Run:

```bash
git status --short
git diff --name-only
```

Expected: only the allowed Markdown files changed; no
`src/buddyswitch/**`, `tests/**`, dependency declaration or runtime file.

- [x] **Step 2: Verify the projected rules**

Run:

```bash
rg -n \
  'unresolved failure|undeclared dependency|rebuild/install/activate/verify|parent-known|terminal exits' \
  docs/memo/2026-07-28-buddyswitch-modular-monolith-migration \
  .agents/skills/buddyswitch-testing/references
```

Expected: durable governance owns the rules, the active migration plan and
execution-facing templates project them, and the retrospective records
historical rationale.

- [x] **Step 3: Verify no competing machinery**

Run:

```bash
rg -n \
  'new migration state|packet validator|second test runner|evidence service' \
  docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/02-demand-component-pilot-plan/S2-DELIVERY-RETROSPECTIVE.md
git diff --check
```

Expected: those terms occur only as rejected non-goals; diff check passes.

- [x] **Step 4: Commit and push**

Run:

```bash
git add \
  .agents/skills/buddyswitch-testing/references/evidence.md \
  .agents/skills/buddyswitch-testing/references/review.md \
  docs/memo/2026-07-28-buddyswitch-modular-monolith-migration
git commit -m "docs: ratchet S2 delivery lessons"
git push origin fea-tool
```

Expected: one documentation-only commit, clean worktree and local/remote
identity match.
