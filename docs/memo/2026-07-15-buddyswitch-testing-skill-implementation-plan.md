# BuddySwitch Testing Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:writing-skills` for the RED/GREEN pressure cycle and `superpowers:executing-plans` to execute this plan task-by-task. Do not apply the mechanical per-task reviewer workflow: these files form one coupled policy change.

**Goal:** Add a repository-local `buddyswitch-testing` Codex skill that selects the shortest claim-sufficient verification, discovers targets from current repository facts, reuses identity-valid evidence, and reserves `full` for frozen final acceptance.

**Architecture:** `AGENTS.md` publishes the stable repository verification contract and triggers the skill. `.agents/skills/buddyswitch-testing/` owns reusable decision rules but contains no BuddySwitch feature topology, fixed test paths, counts, or timing thresholds. The existing `./buddyswitch-test` remains the only execution owner and retains exactly `focused` and `full` modes.

**Tech Stack:** Markdown Codex skills, YAML interface metadata, existing BuddySwitch test runner, `rg`, Git working-state inspection, skill-creator validation.

---

## Scope

**Create**

- `docs/memo/2026-07-15-buddyswitch-testing-skill-implementation-plan.md`
- `.agents/skills/buddyswitch-testing/SKILL.md`
- `.agents/skills/buddyswitch-testing/agents/openai.yaml`
- `.agents/skills/buddyswitch-testing/references/discovery.md`
- `.agents/skills/buddyswitch-testing/references/escalation.md`
- `.agents/skills/buddyswitch-testing/references/evidence.md`
- `.agents/skills/buddyswitch-testing/references/review.md`

**Modify**

- `AGENTS.md`

**Preserve unchanged**

- `buddyswitch-test`
- `tests/**`
- `tests/runner.py`
- `tools/**`
- `scripts/**`
- `buddyswitch/skills/**`
- `tools/launcher/assets/roles/**`

## Acceptance Contract

1. The skill triggers for executable code, tests, runtime contracts, and test-infrastructure changes or reviews.
2. The skill reads current diff, untracked files, code, tests, contracts, and runner constraints instead of storing feature topology.
3. Behavior changes and bug fixes use RED; pure refactors establish baseline GREEN without manufacturing failure.
4. States describe claim breadth, not mandatory repeated commands.
5. Discovery stops when the claim and direct boundaries are covered.
6. Compatible targets may be batched; runner-declared exclusive work is isolated.
7. Evidence reuse requires equivalent source state, command, environment, clean result, and claim breadth.
8. Review alone does not invalidate evidence; reviewers default to finding-specific probes.
9. `full` runs only for frozen merge/release, explicit repository-wide acceptance, or direct user request.
10. A post-final executable change runs exact and affected proof first, then one new final run after freeze.
11. `AGENTS.md` and the skill add no test command, runner mode, impact engine, evidence ledger, feature map, or second policy owner.
12. New or renamed modules and tests require no skill edit.

### Task 1: Capture RED Pressure Baseline

**Files:**

- Read: `AGENTS.md`
- Read: `docs/memo/2026-07-15-buddyswitch-testing-skill-design.md`
- No production or skill files changed

- [x] **Step 1: Dispatch three isolated baseline scenarios without the skill**

Scenario A asks for a verification decision after an implementer already ran exact tests and a reviewer made no code changes. It pressures unnecessary fresh/full reruns.

Scenario B introduces a future module and renamed tests that do not exist in any stored topology. It pressures static mapping and broad-suite fallback.

Scenario C starts from a clean final result, introduces a small post-final fix, and asks for reviewer/controller verification. It pressures repeated full runs.

- [x] **Step 2: Record the exact baseline violations**

At least one scenario must demonstrate one of these missing rules before implementation:

- treats review as evidence invalidation
- upgrades a local claim to `full`
- lacks a deterministic current-repository discovery order
- cannot distinguish task scope from worktree identity
- treats escalation states as repeated commands
- reruns `full` between post-final edits

- [x] **Step 3: Confirm RED is caused by the missing repository skill**

Expected: the agent can repeat general TDD discipline but cannot cite a repository rule that defines claim-scoped discovery, reusable evidence identity, or final-only full execution.

**RED evidence recorded on 2026-07-15:**

- The unchanged-review scenario reused the implementer's identity-valid focused
  evidence, but found a direct policy fork: the current `finish-dev-change` skill
  still says to rerun fresh verification at finish even when no repository state
  changed. There is no repository rule resolving freshness by evidence identity.
- The future-module scenario correctly inspected `git status`, rename-aware diff,
  and live references, but automatically promoted a generic "final completion"
  claim to `./buddyswitch-test full`. The current repository guidance does not
  separate ordinary local completion from frozen merge/release FINAL.
- The post-final-fix scenario already chose exact and affected focused proof,
  preserved evidence through read-only reviews, and ran one final full after the
  tree froze. This is retained as a passing baseline behavior to prevent regression.

These results prove the missing behavior is repository decision policy, not test
runner capability. The implementation must close the two observed forks without
replacing the runner or adding project topology.

### Task 2: Create the Stable Repository Skill

**Files:**

- Create: `.agents/skills/buddyswitch-testing/SKILL.md`
- Create: `.agents/skills/buddyswitch-testing/agents/openai.yaml`
- Create: `.agents/skills/buddyswitch-testing/references/discovery.md`
- Create: `.agents/skills/buddyswitch-testing/references/escalation.md`
- Create: `.agents/skills/buddyswitch-testing/references/evidence.md`
- Create: `.agents/skills/buddyswitch-testing/references/review.md`

- [x] **Step 1: Initialize the skill with only required resources**

Run:

```bash
python3 /Users/chen/.codex-work1/skills/.system/skill-creator/scripts/init_skill.py \
  buddyswitch-testing \
  --path .agents/skills \
  --resources references \
  --interface 'display_name=BuddySwitch Testing' \
  --interface 'short_description=Choose focused, reusable repository verification' \
  --interface 'default_prompt=Use $buddyswitch-testing to choose and record the shortest sufficient verification for this change.'
```

Expected: one skill directory with `SKILL.md`, `agents/openai.yaml`, and an empty `references/` directory; no scripts, assets, README, examples, or second runner.

- [x] **Step 2: Write `SKILL.md` as the concise decision entrypoint**

Required frontmatter:

```yaml
---
name: buddyswitch-testing
description: Use when changing, reviewing, or claiming completion for executable code, tests, runtime contracts, or test infrastructure in the BuddySwitch repository.
---
```

Required body responsibilities:

- declare current claim and intent
- read the repository verification contract from `AGENTS.md`
- discover current targets, with `references/discovery.md` loaded for target selection or ambiguity
- select claim breadth, with `references/escalation.md` loaded before broadening or final acceptance
- record/reuse evidence, with `references/evidence.md` loaded before cross-turn/cross-agent reuse or completion claims
- apply reviewer behavior, with `references/review.md` loaded for handoff/review/controller decisions
- forbid feature catalogs, source-to-test maps, fixed directories, counts, timings, new test entries, and ritual reruns
- report claim, command, result, evidence validity, and residual risk

- [x] **Step 3: Write `references/discovery.md`**

The reference must define this ordered ladder:

1. Name the claim.
2. Inspect modified and non-ignored untracked facts; partition task changes from unrelated pre-existing worktree changes.
3. Prefer new or modified exact tests; deleted tests require surviving proof or an explicit coverage decision.
4. Search current tests for changed public symbols, commands, contracts, outputs, and direct callers.
5. Stop when the claim and direct boundaries are covered.
6. Escalate uncertainty explicitly rather than guessing success.
7. Batch compatible targets and isolate runner-declared exclusive work.

It must define intent-sensitive entry for behavior change, defect repair, pure refactor, test/test-infrastructure change, and non-executable prose/artifacts.

- [x] **Step 4: Write `references/escalation.md`**

Define `RED`, `GREEN`, `IMPACT`, `MILESTONE`, `FINAL`, and `FIX_AFTER_FINAL` with entry signal, proof scope, exit claim, and invalidation. State explicitly:

- states are breadth labels, not mandatory commands
- one command may satisfy multiple states
- ordinary local completion does not require MILESTONE or FINAL
- FINAL uses the final command from `AGENTS.md` only after executable state freezes
- edits after FINAL use exact and affected focused proof before one new final run

- [x] **Step 5: Write `references/evidence.md`**

Define this evidence record:

```text
Verification Evidence
- state: <claim breadth>
- source: <repo root, HEAD, tracked patch identity, non-ignored untracked identity>
- command: <canonical command and explicit targets>
- environment: <material runner/toolchain identity>
- result: <exit status, summary, duration, cleanup/residual state>
- proves: <exact claim and direct boundaries>
- valid-for: <current worktree or frozen SHA>
- residual-risk: <none or explicit risk>
```

Define reuse and invalidation for unchanged review, relevant executable/test/contract change, runner/dependency/environment change, prose-only change, unknown identity, failure/flake/timeout, and broader claims.

- [x] **Step 6: Write `references/review.md`**

Define implementer, reviewer, controller, and runner as responsibilities rather than required agent counts. Require reviewers to inspect identity-valid evidence and run finding-specific probes by default. Forbid rerunning a broad suite only to demonstrate reviewer independence.

- [x] **Step 7: Confirm `agents/openai.yaml` matches the skill**

Expected exact interface:

```yaml
interface:
  display_name: "BuddySwitch Testing"
  short_description: "Choose focused, reusable repository verification"
  default_prompt: "Use $buddyswitch-testing to choose and record the shortest sufficient verification for this change."
```

### Task 3: Publish the Repository Verification Contract

**Files:**

- Modify: `AGENTS.md`

- [x] **Step 1: Add the skill trigger inside `## Verification`**

Add one compact policy block after the existing `focused/full` command block:

```markdown
For executable code, tests, runtime contracts, or test infrastructure, follow
`$buddyswitch-testing`. It owns dynamic target discovery, claim-scoped
escalation, evidence reuse/invalidation, and reviewer probes. The commands above
are its repository verification contract; the runner owns target validation,
isolation, exclusivity, and cleanup.

Do not encode feature-to-test mappings in `AGENTS.md` or the skill. Discover
targets from the current diff, code, tests, contracts, and runner constraints.
Generic completion or review guidance must not upgrade focused proof to `full`
unless the skill reaches FINAL, repository-wide acceptance is explicit, or the
user directly requests it.
```

- [x] **Step 2: Inspect for duplication**

Expected: the existing public command block remains authoritative and is not copied into another executable or config file.

### Task 4: Run GREEN Pressure Scenarios and Refine

**Files:**

- Modify if pressure reveals a real loophole: `.agents/skills/buddyswitch-testing/**`
- Modify if contract wording is ambiguous: `AGENTS.md`

- [x] **Step 1: Dispatch fresh isolated agents on the same three scenarios**

Agents must receive the scenario and repository path, but not the intended answer or earlier diagnosis. They must follow repository instructions and the new repository-local skill.

- [x] **Step 2: Require these GREEN outcomes**

- unchanged review reuses valid evidence
- future/renamed modules are discovered from current facts without a map
- a local claim stays focused
- missing coverage produces RED or explicit MILESTONE uncertainty
- a post-final fix uses exact and affected proof, then one final run after freeze
- one command may satisfy multiple breadth states

- [x] **Step 3: Run adversarial follow-up scenarios**

Pressure pure refactor, unrelated dirty changes, deleted tests, a flaky/cleanup failure, and generic “fresh full verification” wording. Patch only demonstrated loopholes, then rerun the failing scenario.

**GREEN and adversarial evidence recorded on 2026-07-15:**

- Fresh unchanged-review pressure reused identity-valid implementer evidence and
  did not rerun focused or full verification merely because the actor changed.
- Fresh future-module pressure discovered renamed and untracked facts from the
  live repository, kept ordinary completion at focused IMPACT, and reserved one
  full run for a frozen merge-ready claim.
- Fresh post-final pressure invalidated the old FINAL after an executable edit,
  ran exact and affected proof first, reused it across read-only review, and
  selected one new full run only after the candidate froze.
- Pure-refactor pressure refused to manufacture RED and used baseline GREEN plus
  dynamically discovered affected proof.
- Flake/cleanup pressure treated timeout and residual state as a superseding
  failure, stopped blind reruns, and required diagnosis before new evidence.
- Deleted-test and dirty-worktree pressure refused “nothing to run” as success,
  required surviving proof or an explicit coverage decision, preserved unrelated
  work, and distinguished claim scope from complete source identity.

No scenario demonstrated a new loophole, so Task 4 required no policy patch.

### Task 5: Validate Structure, Residue, and Acceptance

**Files:**

- Verify: `.agents/skills/buddyswitch-testing/**`
- Verify: `AGENTS.md`
- Verify: design and plan documents

- [x] **Step 1: Validate the skill package**

Run the validator through an isolated `uv` dependency because the repository Python
does not include PyYAML and the validator imports it directly:

```bash
uv run --with PyYAML python \
  /Users/chen/.codex-work1/skills/.system/skill-creator/scripts/quick_validate.py \
  .agents/skills/buddyswitch-testing
```

Expected: `Skill is valid!`

- [x] **Step 2: Validate YAML and references**

Run a structured parser to assert frontmatter name/description, exact `openai.yaml` interface, all four reference files, and no broken relative links from `SKILL.md`.

- [x] **Step 3: Run coupling and residue scans**

Assert the skill contains none of:

- BuddySwitch feature/module names
- fixed `tests/unit`, `tests/integration`, `tests/process`, or `tests/system` paths
- elapsed-time thresholds or current test counts
- second test commands, scripts, impact engine, ledger, plugin, or feature map
- language requiring each breadth state or each role to run a separate command

- [x] **Step 4: Verify repository scope**

Expected changed implementation surface:

```text
AGENTS.md
.agents/skills/buddyswitch-testing/**
```

Plus requested design and plan documents under `docs/`. No runner, production, runtime-skill, or test-module changes.

- [x] **Step 5: Run final non-product checks**

Run:

```bash
git diff --check
git status --short
```

Do not run `./buddyswitch-test full`: this change modifies repository instructions and a Codex skill, not executable BuddySwitch behavior. The RED/GREEN pressure suite and package validation are the relevant acceptance evidence.

**Final acceptance evidence recorded on 2026-07-15:**

- Official `quick_validate.py`: `Skill is valid!`
- Structured frontmatter, `openai.yaml`, four-reference, and relative-link checks:
  PASS.
- Feature-topology, fixed-tier-path, timing/count, second-command, package-shape,
  and mandatory-rerun residue scans: PASS.
- Repository scope audit: only `AGENTS.md`, the six skill files, and the requested
  design/plan documents are changed or untracked.
- Design HTML anchor and inline JavaScript validation: PASS.
- Fresh read-only Codex CLI discovery smoke loaded the repository skill, reused
  unchanged focused evidence, kept ordinary completion out of FINAL, and selected
  no additional command.
- `git diff --check`: PASS.

No BuddySwitch product test suite was run because no executable product, test,
runner, or runtime contract changed.

## Definition of Done

- The implementation matches both design documents.
- Baseline pressure demonstrates the missing repository decision rules.
- Fresh pressure scenarios comply after the skill is installed.
- The skill remains feature-topology-free and project-lifecycle-independent.
- `AGENTS.md` triggers one repository-local policy without duplicating the runner.
- Structural validation, residue scans, scope audit, and `git diff --check` pass.
- No unrelated main worktree changes are modified or reverted.
