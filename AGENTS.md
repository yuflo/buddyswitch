# SHARP Forward AI Development Philosophy v1

> This file defines forward-moving AI-assisted product development.
> It is not a discussion memo. Unless a higher-priority instruction explicitly overrides it, this file should be treated as repository-level execution guidance for human developers, coding agents, and automation workflows.

## 1. North Star

The goal at this stage is not completeness, future-proof elegance, or architectural prestige.

The goal is:

**to push the core product capability forward in the clearest, shortest, and most verifiable way.**

Default priority order:

1. Real outcome improvement
2. Iteration speed
3. Structural clarity
4. Implementation cost

Do not sacrifice product effect or iteration speed merely to save model cost, token cost, or infrastructure cost unless cost has become a proven bottleneck.

---

## 2. What SHARP Means

### S - Solve the current bottleneck
Every meaningful iteration must answer:

- What is the current core problem?
- Why is it the most important one now?
- What verifiable improvement will solving it create?

If a change does not directly serve the current bottleneck, default to not doing it.

### H - Hit the shortest validated loop
Prioritize:

- the shortest runnable path
- the smallest testable system
- the quickest route to real feedback
- real artifacts over theoretical readiness

Close the loop first. Completeness comes later.

### A - Avoid speculative abstraction
Do not build for imagined futures.

Avoid introducing by default:

- plugin systems
- workflow engines
- rule engines
- event buses
- premature service splits
- generic DSLs
- large permission frameworks
- abstract platforms for hypothetical future products

Do not generalize before repeated real use proves the pattern.

### R - Replace, refactor, remove
When old structure blocks progress, prefer:

- direct refactoring
- direct replacement
- deletion

Do not default to layering more compatibility wrappers, adapters, indirection, or long-lived dual-track logic.

Compatibility is not a virtue by default. It is a cost, justified only by real users, irreversible data migration, rollback needs, or explicit contractual commitments.

### P - Prove with verification
A task is not done because code exists. It is done when the result is verified.

Verification may include:

- automated tests
- integration tests
- lint / typecheck / build
- manual main-path execution
- key log inspection
- screenshot comparison
- expected command output
- observable state or data change

No verification, no completion.

---

## 3. Forward Iteration Principles

### 3.1 Move forward, not burden-first
Assume old designs may be replaced.
Assume today's best solution should solve today's most important problem.
Assume code, prompts, docs, workflows, and skills may all be rewritten if doing so makes the system clearer and easier to advance.

**If you can cut through, do not route around.
If you can replace, do not stack.
If you can delete, do not preserve.**

### 3.2 Focus on one core problem at a time
Do not mix the main task with side upgrades, future conveniences, or unrelated cleanup.

### 3.3 Once the problem is clear, stop expanding it
After the target is defined, shift into execution.
Do not keep adding branches, reframing the scope, or inflating the task into a larger system redesign.

### 3.4 Clarity over cleverness
Prefer:

- fewer concepts
- shorter paths
- less hidden behavior
- fewer cross-layer jumps
- structures that a new agent or developer can quickly understand

Do not reward impressive complexity.

### 3.5 Monolith-first, boundaries-clear
Before real complexity forces distribution, prefer:

- monolith or near-monolith structures
- hard module responsibility boundaries
- low runtime coordination overhead
- minimal distributed state

Get module boundaries right before splitting service boundaries.

### 3.6 Concrete first, abstract later
On first occurrence, implement concretely.
Only abstract after the same pattern has appeared repeatedly and stabilizes enough to name.

### 3.7 Runtime complexity is more expensive than local verbosity
Be more afraid of:

- distributed truth
- hidden async coupling
- duplicated config drift
- long-lived dual logic
- multi-entry state mutation

Local code may be slightly blunt if the whole system becomes easier to reason about.

---

## 4. Coding Agent Execution Protocol

### 4.1 For non-trivial tasks: explore, plan, implement, verify
For multi-file work, architecture changes, unfamiliar code, or non-obvious bugs:

1. Explore the current state
2. Form a minimal sufficient plan
3. Implement
4. Verify

Do not jump straight into coding unless the task is truly small and unambiguous.

### 4.2 Find the current bottleneck first
Do not apply equal force everywhere.
Before acting, determine whether the biggest blocker is:

- unclear requirements
- broken main path
- architecture friction
- weak verification
- poor readability
- technical debt slowing iteration
- external dependency or environment blockage

Then attack the biggest blocker first.

### 4.3 Resolve local ambiguity autonomously when safe
If ambiguity does not alter product meaning, break external contracts, or create serious rework, make a grounded local decision and move forward.

Escalate only when the change affects:

- product semantics
- irreversible data shape
- external APIs or commitments
- security, privacy, payment, or permission risk

### 4.4 Preflight gate before analysis, planning, or implementation
For any non-trivial task, do not move from exploration into planning or implementation until the following are explicit:

- target outcome and current bottleneck
- confirmed facts with file, code, log, or command evidence
- open assumptions or invalidators that could change the approach
- tools, permissions, and boundary checks needed for the next action
- verification plan and stop condition

If a required tool, permission, or contract boundary is missing, stop and resolve that gap before execution.
Use `docs/templates/ai-task-preflight.md` for medium or large tasks.

### 4.5 Reviewer rubric for substantial changes
Before declaring completion on substantial work, review the result against a fixed rubric:

- is this fixing root cause or only symptoms
- does the change respect system boundaries and metadata contracts
- is a generic boundary fix being replaced by a local special case
- did the change replace baggage instead of adding wrappers or compatibility layers
- does verification prove the claimed outcome
- did scope stay aligned with the original bottleneck

Use `docs/templates/ai-reviewer-rubric.md` for self-review or reviewer-agent review.

### 4.6 Communication Contract
Use communication to move execution forward, not to perform process.

- Use short, factual, execution-oriented language.
- Lead with the answer, decision, or result.
- Skip filler, repetition, motivational language, performative politeness, and long preambles.
- Do not restate the prompt, narrate obvious actions, or repeat the same point in different words.
- If uncertainty matters, state it concretely and resolve it through inspection or verification. Do not use vague hedging.
- Make reasonable local decisions by default. Escalate only when product meaning, external contracts, irreversible data shape, or security, privacy, payment, or permission risk could change.
- Progress updates should state the current bottleneck, what is being done now, and what happens next.
- Final responses should lead with the result, then verification evidence, then remaining risk or one next recommendation.
- Be concise, but do not omit material facts such as changed scope, commands, file paths, assumptions, dates, or blockers when they matter.
- Use only enough summary to support the next action. Avoid generic recaps, methodology essays, and performative status narration.

### 4.6A Execution Focus Loop
After preflight, enter a single-task execution loop.

- Keep one active goal, one active action, and one active proof of success. If you are carrying multiple, reduce scope until only one remains.
- Maintain challenge-skill balance. If the task feels vague or too large, shrink the step size or gather one missing fact before continuing.
- Prefer immediate feedback. After each meaningful step, inspect the diff, command output, log, test, screenshot, or state change before planning further moves.
- Protect task-relevant attention. Do not open adjacent cleanup, redesign, or extra options unless current evidence shows they block the main path.
- Start with a clean, high-confidence move that creates traction on the bottleneck.
- When drift or confusion appears, stop and reset: restate the bottleneck, discard side paths, reduce scope, and resume with the next smallest verifiable step.
- Progress updates are execution cues, not narration. State only: current bottleneck, current action, next proof.
- Once the path is clear, reduce meta-process. Execute instead of repeatedly reframing the task.

### 4.7 Verify after each meaningful change block
Do not accumulate many risky changes and only test at the end when intermediate validation is feasible.

### 4.8 Fix root causes, not symptoms
Do not suppress, ignore, or hide errors just to make them disappear.
Do not add fallback branches that mask bad states without understanding them.

### 4.9 Long tasks must be resumable
For work likely to span multiple sessions, maintain a resumable execution document with:

- target outcome
- current state
- plan
- progress
- findings
- key decisions
- verification method

Do not rely on fragile hidden context.

---

## 5. Documentation and Knowledge Rules

### 5.1 Root guidance must be short, sharp, and executable
The repository's top-level instruction file should contain only durable, high-value guidance such as:

- project goal
- non-negotiable rules
- run / test / verify commands
- key directory conventions
- definition of done
- forbidden behaviors

Do not turn the root guidance file into a bloated encyclopedia.

### 5.2 Repeated workflows belong in skills
If a workflow repeats and has a stable decision pattern, steps, and outputs, package it as a skill instead of re-explaining it in prompts.

A skill should solve one clear problem, not become a universal toolbox.

### 5.3 Complex work deserves an execution plan
Large features, cross-module changes, or high-unknown work should have a resumable plan document.

### 5.4 Record decisions, not diaries
Persist only what will matter later:

- important architectural decisions
- key tradeoff reasons
- boundary definitions
- runbooks people will repeatedly need

Do not preserve stale speculation or abandoned drafts in primary documents.

---

## 6. Change Strategy

### 6.1 Prefer small batches
Smaller changes are easier to review, verify, revert, and integrate.

### 6.2 One change set, one main intent
Do not mix feature work with broad renames, style cleanup, unrelated refactors, and opportunistic restructuring unless they are inseparable.

### 6.3 Main path before polish
If the main path is unstable, do not spend heavily on peripheral elegance.

---

## 7. Quality Bar

### 7.1 No verification, no done
Completion requires proof.

### 7.2 Automate quality gates when possible
Anything that can be checked by machines should not rely purely on human memory.

Examples:

- lint
- tests
- type checks
- security checks
- protected path rules
- required validation hooks

### 7.3 Important architecture goals should be measurable
If a principle matters, encode it into checks, tests, hooks, or constraints where possible.

---

## 8. Allowed Exploration, Forbidden Drift

### 8.1 Allowed exploration
Fast spikes and throwaway prototypes are allowed when they reduce major uncertainty.

But they must be:

- time-boxed
- conclusion-oriented
- easy to discard
- kept out of the main path unless promoted intentionally

### 8.2 Forbidden drift
Do not drift:

- from a concrete task into platform design
- from a bug fix into total restructuring
- from a narrow skill into a giant system
- from real needs into imagined-future layering

---

## 9. Anti-Patterns

The following are default anti-patterns:

1. Adding layers to look professional
2. Building systems for users or cases that do not yet exist
3. Keeping dead logic because deleting feels risky
4. Abstracting before the second real use case
5. Hiding complexity behind config and implicit behavior
6. Using generic frameworks to avoid making decisions
7. Covering up structural issues with compatibility wrappers
8. Bundling several unrelated intentions into one change
9. Declaring success without verification
10. Continuing to diverge after the problem is already clear
11. Letting generation speed replace actual thinking
12. Writing slogan-heavy guidance instead of executable constraints

---

## 10. Default Workflow Sizes

### Small task
- implement directly
- verify immediately
- report result, verification, and remaining risk

### Medium task
- explore
- write a short plan
- implement
- verify
- report result, verification, and remaining risk

### Large task
- create an execution plan
- work in stages
- update progress and decisions
- produce visible results each stage
- close the loop fully

---

## 11. Definition of Done

A task is done only when:

1. the current core problem has been materially advanced
2. the change scope stays aligned with the task
3. the result has been verified appropriately
4. the code or structure is at least no less clear than before
5. new durable constraints are documented where needed
6. replaced legacy pieces are removed or explicitly queued for removal

---

## 12. One-Line Version

**Focus on the current bottleneck, cut the shortest validated path, avoid speculative abstraction, replace baggage when needed, and prove progress through verification.**

--- project-doc ---

# BuddySwitch Development Workspace

The SHARP guidance above is the default workflow for this repository. The notes below define BuddySwitch-specific working context and source-of-truth locations.

- Use `codex` here when you are editing BuddySwitch source, tests, docs, or launcher code.
- `./buddyswitch-codex start` does not run Codex from this checkout; it launches from a launcher-managed execution worktree under `${BUDDYSWITCH_SHARED_ROOT}/workspace`.
- The execution worktree carries the full runtime BuddySwitch contract in `tools/launcher/assets/runtime-AGENTS.md`.
- Runtime BuddySwitch state is not maintained as tracked skeleton directories in the main checkout.

## Canonical Sources

- Env manifest: `buddyswitch/manifest.toml`
- Runtime state paths inside the execution worktree:
  - `buddyswitch/objects/tracks/*.json`
  - `buddyswitch/objects/tasks/*.json`
  - `buddyswitch/objects/artifacts/*.json`
  - `buddyswitch/content/runs/*.json`
  - `runs/raw/`
  - `projects/app/.runtime/`
- Read-only context panel server: `python3 scripts/serve_context_panel.py`
- Main app code: `projects/app/`

## Development Notes

- Keep repo-root work focused on BuddySwitch source, tests, docs, launcher behavior, and framework contracts.
- Use `codex` in this checkout for development mode.
- Use `./buddyswitch-codex start` when you need a launcher-managed product-mode runtime session.
