# BuddySwitch Sharp Engineering Constitution Design

**Date:** 2026-07-15

**Status:** Proposed design approved in direction; written-spec review pending

## 1. Target Outcome

Replace the current root `AGENTS.md` with a high-density engineering constitution
that shapes how humans and coding agents make development decisions in BuddySwitch.

The constitution must make BuddySwitch's high-speed iteration style concrete:

- move the current product bottleneck;
- close the shortest meaningful feedback loop;
- rebuild forward to one current path;
- preserve strict product and dependency ownership;
- prove behavior, architecture, replacement, and operational cleanliness;
- turn repeated quality lessons into repository-enforced constraints.

The target is roughly 150-200 lines. It is a map and decision framework, not a
standalone engineering encyclopedia.

## 2. Current Bottleneck

The current `AGENTS.md` has the right direction but presents philosophy, testing,
execution, repository context, and completion as a mostly linear list. Five gaps
limit its effect:

1. `Sharp Forward` is expressed as preference, not as a decision system with named
   states and exit conditions.
2. `REBUILD` does not yet define what must disappear from code, contracts, tests,
   documentation, and runtime surfaces before replacement is complete.
3. Testing and acceptance are adjacent but not separated. A passing test can be
   mistaken for product, architecture, or replacement acceptance.
4. Architecture guidance does not give an agent a compact set of ownership,
   dependency, change-locality, and composition questions before it adds code.
5. Repeated review findings are not explicitly routed toward tests, linters,
   contracts, or skills, so prose can remain the only guardrail.

The rewrite must solve these gaps without duplicating the test skill, runtime
contracts, or detailed architecture documents.

## 3. Research Synthesis

The design combines established engineering principles with current coding-agent
harness practice.

### 3.1 Agent instructions should be a map

OpenAI reports that a monolithic `AGENTS.md` crowds out task context, decays quickly,
and is hard to verify. Its preferred pattern is a short root map, progressive
disclosure into repository-local sources, and mechanical enforcement of important
invariants.

BuddySwitch implication: keep universal decisions in `AGENTS.md`; route workflow
judgment to skills, current architecture to `docs/arch`, and executable truth to
code, contracts, and tests.

### 3.2 Architecture should hide change and expose purpose

Parnas's information-hiding criterion organizes modules around decisions likely to
change. Cockburn's ports-and-adapters model keeps product behavior independent from
UI, CLI, storage, and other delivery technologies.

BuddySwitch implication: product semantics belong to one owning domain. Interfaces
project that domain through purpose-named contracts. Technical adapters do not own
product rules, and repeated cross-module edits are evidence of a misplaced boundary.

### 3.3 Speed comes from small batches and independent proof

DORA links small batches, short-lived integration, loosely coupled architecture,
and on-demand independent testing to continuous-delivery performance. Google's
engineering guidance similarly favors one self-contained intent with its tests and
requires each change to improve overall code health rather than chase perfection.

BuddySwitch implication: optimize for the smallest coherent vertical change, not
the fewest changed lines. Keep one intent per change and make ordinary product slices
independently understandable and testable.

### 3.4 Evolution requires executable architectural feedback

Evolutionary architecture uses fitness functions to protect important qualities as
the system changes. YAGNI is sustainable only when refactoring, self-testing code,
and continuous feedback keep the system easy to change.

BuddySwitch implication: an important repeated rule should graduate from prose to a
test, structural check, linter, schema, or runtime rejection. `Sharp Forward` does
not trade away internal quality; it invests in the quality that preserves iteration
speed and rejects speculative capability.

### 3.5 Agent completion needs observable outcomes

Long-running coding-agent research identifies recurring failures: attempting too
much at once, leaving partial state, declaring completion from local evidence, and
testing internals without exercising the user path.

BuddySwitch implication: large work needs a resumable execution artifact; every
change needs a named acceptance claim; completion requires source-bound evidence and
an observable result, not an agent's confidence.

## 4. Design Decision

Use a **high-density constitution with progressive disclosure**.

The root file will contain only:

- the Sharp Forward decision order;
- default and protected change modes;
- architecture laws;
- the development state machine;
- the repository testing contract;
- the acceptance evidence model;
- coding-agent operating rules;
- knowledge-placement rules;
- the minimal BuddySwitch repository map;
- the definition of done.

It will not contain feature-to-test mappings, payload schemas, per-role workflows,
historical architecture explanations, style trivia, or command catalogs.

## 5. Sharp Forward Philosophy

`SHARP` becomes the memorable decision framework rather than a decorative label.

When tradeoffs conflict, use this order:

1. observable product capability and user outcome;
2. iteration speed through a validated feedback loop;
3. behavioral and architectural integrity that preserves future speed;
4. code and repository legibility;
5. implementation, compute, token, and infrastructure cost.

Do not buy short-term motion by weakening the first four. Do not spend on the last
two, or on unrelated quality polish, beyond what the current bottleneck can justify.
Quality work is in scope when it protects the live product path or preserves the
speed of the next change.

### S - Solve the current bottleneck

- Name the exact product or engineering constraint before acting.
- Prefer observable capability improvement over broad cleanup or platform work.
- Stop expanding scope once the bottleneck and acceptance claim are clear.

### H - Hit the shortest validated loop

- Choose the smallest coherent vertical slice that can produce real feedback.
- Keep the system runnable after each meaningful change block.
- Prefer direct repository evidence, executable artifacts, and user-path proof.

### A - Assign one owner and avoid speculative abstraction

- Every state transition and product rule has one semantic owner.
- Concrete first; abstract only after repeated current use reveals a stable pattern.
- Do not add engines, buses, plugin layers, registries, or distributed coordination
  for imagined future needs.

### R - Rebuild, replace, remove

- The new path becomes the only live path in the same change set.
- Delete retired implementations, aliases, fallbacks, dual reads/writes, schema
  fields, tests, docs, and discovery surfaces.
- Do not make active internal code remember retired shapes.
- Multiple intentional interfaces are not dual-track behavior when they project the
  same semantic owner without copying its rules.

### P - Prove the outcome

- Name the claim before selecting verification.
- Prove the behavior at the nearest meaningful boundary, then broaden only for
  affected or acceptance-level risk.
- No evidence means blocked or incomplete, never done.

## 6. Change Modes

### 6.1 Default: Sharp mode

Use for ordinary BuddySwitch product and internal architecture work.

- Internal contracts may break when the new model is clearer.
- Direct replacement is preferred over migration scaffolding.
- Historical compatibility, rollback comfort, and hypothetical production stability
  are not requirements.

### 6.2 Protected mode

Enter only when the task explicitly includes a real external API, real user data
migration, release/hotfix, security, privacy, payment, permission, or irreversible
operation.

Any compatibility path in protected mode must name:

- the contract or data it protects;
- the owner and observable risk;
- whether reads, writes, or both require coexistence;
- the removal trigger or permanent contractual reason;
- tests that distinguish the protected path from accidental residue.

Without this evidence, compatibility code is rejected.

## 7. Architecture Constitution

### 7.1 One semantic owner

A product behavior, state transition, or invariant has one owner. Other layers call
or project that owner; they do not reproduce its rules.

### 7.2 Product core, then interfaces

Use the shape:

```text
product/domain owner -> explicit contract -> adapter/projection -> consumer
```

UI, Web, CLI, tools, storage adapters, daemon transport, and skills do not become
alternate product implementations.

### 7.3 Dependencies point toward ownership

- Adapters may depend on public owner contracts.
- Owners do not depend on adapter DTOs or presentation concerns.
- Cross-domain behavior goes through an explicit domain operation or capability.
- A composition root may know concrete implementations; generic infrastructure may
  not discover or branch on product semantics.

### 7.4 Boundaries follow change

Modules should hide volatile decisions and keep one product slice locally
understandable. Repeated edits to a central router, registry, manager, global type,
or shared utility are architecture feedback: move the change boundary instead of
adding another case.

### 7.5 One truth and one write path

For current semantics, keep one canonical model, owner, state shape, and mutation
path. Derived projections may be many; competing sources of truth, dual writes,
fallback reads, and hidden synchronization are forbidden by default.

### 7.6 Monolith first, explicit boundaries always

Keep runtime coordination local until proven complexity requires distribution.
Clear module boundaries are mandatory; service boundaries are earned by real
independent lifecycle, scaling, isolation, or ownership needs.

### 7.7 Legibility over cleverness

Prefer explicit composition, direct calls, exact schemas, small public contracts,
and boring inspectable technology. Avoid implicit discovery, service locators,
metaprogrammed control flow, and configuration that hides product behavior.

### 7.8 Enforce invariants, allow local freedom

Enforce ownership, dependency direction, state shape, cleanup, and public contracts
centrally. Do not micromanage equivalent local implementation style. If an
architecture rule matters repeatedly, encode a fitness function.

## 8. Development State Machine

Every non-trivial change follows this state sequence. Small changes may compress the
notes, but not skip the reasoning.

### FRAME

Name the bottleneck, desired observable outcome, scope boundary, and protected
contracts. Exit when one acceptance sentence can describe success.

### TRACE

Locate the current semantic owner, call path, state path, tests, and live surfaces.
Identify retired names or structures that replacement must remove. Exit when the
change boundary is grounded in repository facts.

### PROVE

Select the exact behavior or baseline proof:

- behavior change: observe intended RED;
- defect: reproduce with the smallest regression;
- refactor: establish current behavior GREEN;
- prose/artifact: choose artifact-specific validation.

Exit when the proof can detect the intended change or preservation.

### BUILD

Implement the smallest direct owner-correct change. Keep interfaces thin, failure
semantics explicit, and unrelated cleanup out. Exit when the new path works through
the selected proof.

### REPLACE

Delete the old path and update all live contracts, tests, docs, fixtures, and
discovery surfaces. Exit when there is one live semantic path and scoped residue
checks find no unexplained old shape.

### VERIFY

Use `$buddyswitch-testing` for executable changes. Prove exact behavior and affected
boundaries, inspect cleanup/residual state, and broaden only when the claim requires
it. Exit with source-bound evidence, not assumed success.

### ACCEPT

Review the final diff against the original acceptance sentence and the relevant
proof classes. Exit only when product outcome, architecture, replacement, and
operational claims are either proved or explicitly inapplicable.

## 9. Testing and Acceptance Separation

### 9.1 Testing owns behavioral evidence

`$buddyswitch-testing` remains the single owner of target discovery, RED/GREEN and
refactor entry, evidence identity, escalation breadth, and reviewer probes.

The only public test entry remains:

```bash
./buddyswitch-test focused <file-or-nodeid>...
./buddyswitch-test full
```

The constitution states invariants; it does not duplicate target-selection logic.

### 9.2 Acceptance owns the complete claim

Select every proof class material to the change:

| Proof class | Question | Typical evidence |
|---|---|---|
| Product | Can the consumer complete the promised loop? | behavior or end-to-end path |
| Contract | Are success, failure, authority, and state effects exact? | boundary/integration tests |
| Architecture | Is behavior owned once with valid dependency direction? | structural tests and diff review |
| Replacement | Is the old live model absent rather than guarded? | deletion assertions and scoped no-hit scans |
| Operations | Are resources, cleanup, logs, and failure recovery correct? | lifecycle tests and residual inspection |

A broad passing suite does not substitute for a missing direct product or replacement
proof. A narrow behavior test does not prove repository-wide acceptance.

## 10. Codex Engineering Style

- Repository facts outrank memory, conventions from other projects, and plausible
  guesses. Inspect current code, contracts, tests, and git state first.
- Trace the owner and consumer-visible path before editing. Do not fix an interface
  symptom in the wrong layer.
- Use the smallest coherent change, not shotgun edits. Preserve unrelated user work
  and partition dirty-worktree evidence explicitly.
- Prefer code and contract clarity over explanatory prompt bulk. If a tool or API is
  hard to use correctly, fix its semantics or feedback at the owning layer.
- Treat failures, flakes, timeouts, and cleanup residue as evidence. Diagnose root
  cause; do not rerun until a pass hides the signal.
- Ask only when ambiguity changes product meaning, external contracts, irreversible
  data, or serious safety risk. Resolve local implementation ambiguity autonomously.
- Review generated code for guessed shapes, copied semantics, unnecessary helpers,
  broad utilities, hidden fallbacks, and unbounded context or runtime behavior.
- For long work, maintain a resumable execution artifact containing outcome, state,
  progress, decisions, verification, and remaining risk.
- Final reports state what changed, what exact evidence proves it, what was not run,
  and what risk remains.

## 11. Quality Ratchet

Every recurring lesson moves to the lowest enforceable owner:

```text
wrong runtime behavior     -> owning code/contract and regression test
repeated architecture drift -> structural test or linter
repeated workflow judgment  -> focused skill
durable architecture reason -> docs/arch decision record
task execution state        -> resumable plan
historical investigation    -> memo, never live policy
```

Do not add prose when a machine can enforce the rule. Do not add a machine framework
for a one-off judgment. Escaped defects receive the smallest test that would have
caught them; repeated hotspots trigger boundary repair.

## 12. Knowledge Placement

| Source | Owns | Must not own |
|---|---|---|
| Root `AGENTS.md` | durable philosophy, laws, workflow, commands, navigation | feature maps, schemas, long SOPs |
| Repository skill | repeated judgment and workflow | runtime truth or copied payload contracts |
| `docs/arch` | current boundaries and significant decisions | transient implementation diaries |
| Execution plan | large-task progress and decisions | permanent runtime policy |
| Code/schema/tool contract | executable current semantics | historical compatibility rationale |
| Tests/linters | behavior and architecture fitness | prose-only aspiration |
| Memo/evidence | investigation and historical proof | active source of truth |

## 13. Root Repository Map

The constitution keeps only stable navigation:

- product source mount: `projects/app/`;
- environment manifest: `buddyswitch/manifest.toml`;
- runtime launcher: `./buddyswitch-codex instance start --role <role>`;
- role bootstrap instructions: `tools/launcher/assets/roles/<role>/AGENTS.md`;
- current architecture: `docs/arch/`;
- repeated testing workflow: `$buddyswitch-testing`;
- runtime object projections under `buddyswitch/objects/**`, writable only through
  environment tools;
- private active-instance files under `$BUDDYSWITCH_ACTOR_PRIVATE_DIR`.

Detailed source maps remain in `README.md`, current contracts, and code.

## 14. Rejected Alternatives

### 14.1 Full standalone manual

Rejected because it would duplicate skills and runtime contracts, consume agent
context, and decay as product topology changes.

### 14.2 Minimal manifesto

Rejected because slogans without exit conditions do not control coding-agent
behavior or support objective review.

### 14.3 New universal architecture framework

Rejected because BuddySwitch already has concrete owner/domain/adapter/repository
patterns. The constitution should name decision laws and enforce current boundaries,
not introduce another generic architecture layer.

## 15. Rewrite and Review Passes

The final `AGENTS.md` rewrite will use three explicit passes:

1. **Structural rewrite:** replace the linear guide with the approved constitutional
   hierarchy and preserve valid repository commands and safety boundaries.
2. **Adversarial review:** pressure-test representative feature, bug, refactor,
   rebuild, protected-contract, dirty-worktree, and long-task scenarios for ambiguous
   or conflicting instructions.
3. **Compression and ownership review:** remove repetition, confirm the test skill
   remains the only test-selection owner, and keep the root file within the intended
   high-density size.

## 16. Acceptance Criteria

The upgraded constitution is accepted when:

1. `Sharp Forward` is visibly the parent philosophy of development, architecture,
   testing, replacement, and acceptance.
2. Every philosophical statement implies a decision, prohibition, exit condition,
   or evidence requirement.
3. REBUILD completion requires one live path plus deletion and scoped residue proof.
4. Default and protected change modes make compatibility exceptions explicit.
5. Architecture laws cover semantic ownership, adapter boundaries, dependency
   direction, change locality, single truth, composition, and mechanical fitness.
6. The development state machine distinguishes framing, tracing, proving, building,
   replacing, verification, and acceptance.
7. Testing and acceptance have separate owners and no duplicated target-selection
   policy.
8. The document tells agents where recurring knowledge and constraints belong.
9. Current BuddySwitch commands, paths, and runtime write prohibitions remain exact.
10. Scenario review finds no instruction that encourages speculative abstraction,
    dual-track compatibility, premature completion, or broad verification without a
    claim.
11. The document remains a high-density constitution rather than a feature catalog
    or engineering encyclopedia.

## 17. Sources

- OpenAI, [Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/)
- OpenAI, [Custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md)
- D. L. Parnas, [On the Criteria To Be Used in Decomposing Systems into Modules](https://sunnyday.mit.edu/16.355/parnas-criteria.html)
- Alistair Cockburn, [Hexagonal Architecture: Ports and Adapters](https://alistair.cockburn.us/hexagonal-architecture)
- DORA, [Continuous Delivery](https://dora.dev/capabilities/continuous-delivery/)
- DORA, [Loosely Coupled Teams](https://dora.dev/capabilities/loosely-coupled-teams/)
- Google Engineering Practices, [Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)
- Google Engineering Practices, [The Standard of Code Review](https://google.github.io/eng-practices/review/reviewer/standard.html)
- Martin Fowler, [Monolith First](https://martinfowler.com/bliki/MonolithFirst.html)
- Martin Fowler, [YAGNI](https://martinfowler.com/bliki/Yagni.html)
- Martin Fowler, [Foreword to Building Evolutionary Architectures](https://martinfowler.com/articles/evo-arch-forward.html)
- Thoughtworks, [Building Evolutionary Architectures, second edition free chapter](https://www.thoughtworks.com/content/dam/thoughtworks/documents/books/bk_building_evolutionary_architectures_second_edition_free_chapter.pdf)
- Martin Fowler, [The Practical Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html)
- Google SRE, [Testing for Reliability](https://sre.google/sre-book/testing-reliability/)
- Anthropic, [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
