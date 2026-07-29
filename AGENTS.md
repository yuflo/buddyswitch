# BuddySwitch Sharp Forward Engineering Constitution

BuddySwitch uses **Sharp Forward** development: move the current product bottleneck through the shortest validated path, keep one clear architecture, and remove history that no longer belongs in the live system.

Core rule: **rebuild forward to one current truth.** Historical burden belongs in Git and historical memos, not in active code, schemas, interfaces, tests, guidance, or runtime paths.

## North Star

When tradeoffs conflict, use this order:

1. observable product capability and user outcome;
2. iteration speed through a validated feedback loop;
3. behavioral and architectural integrity that preserves future speed;
4. code and repository legibility;
5. implementation, compute, token, and infrastructure cost.

Do not buy short-term motion by weakening the first four. Quality work is in scope when it protects the live path or keeps the next change fast; unrelated polish is not.

## SHARP

| Law | Required behavior |
|---|---|
| **S — Solve the bottleneck** | Name the exact constraint; prefer observable capability improvement; stop expanding scope once the claim is clear. |
| **H — Hit the shortest validated loop** | Choose the smallest coherent vertical slice; keep it runnable; prefer executable artifacts and consumer-path feedback. |
| **A — Assign one owner; avoid speculative abstraction** | Give every rule, transition, and truth one owner; build concretely first; reject imagined-future engines, buses, plugins, registries, service splits, and coordination. |
| **R — Rebuild, replace, remove** | Make the current model the only live model; delete the retired path and every live surface that teaches or preserves it. |
| **P — Prove the outcome** | Name the claim first; prove it at the nearest meaningful boundary; broaden only for affected risk; no evidence means incomplete. |

## Forward-Only REBUILD

A replacement is unfinished while the retired model remains reachable, discoverable, writable, readable as fallback, taught by current guidance, or protected as supported behavior by active tests.

Default forbidden residue:

- compatibility aliases, adapters, translation layers, and deprecated entrypoints;
- fallback reads, dual writes, shadow state, old/new config, and parallel schemas;
- old payload fields, command names, environment variables, skills, and help text;
- tests that preserve retired behavior instead of proving current behavior;
- comments or current architecture docs that teach the old path.

Scoped residue assertions and negative safety guards may name retired terms only to prove absence or forbid use. Historical memos may preserve context but are never active policy. Git preserves history. Live code preserves only current truth. Multiple intentional interfaces are not dual tracks only when they are independently current, consumer-required interfaces that project one owner without copying rules; former names and entrypoints remain residue. Do not route around baggage: replace it, update every live consumer, and delete it.

## Change Modes

**Sharp mode is the default** for ordinary product and internal architecture work. Internal contracts may break when the current model becomes clearer; prefer direct cutover over migration scaffolding. Rollback comfort, historical compatibility, and hypothetical production stability are not requirements.

**Protected mode is exceptional.** Enter only for an explicit real external API, user-data migration, release/hotfix, security, privacy, payment, permission, or irreversible operation. Compatibility must name the protected contract/data, owner and risk, read/write coexistence need, removal trigger, and distinguishing tests. A permanent external obligation is a current supported interface, not retired compatibility. Protected coexistence may complete a bounded migration phase but never a completed replacement claim. Without this evidence, compatibility code is residue.

## Architecture Laws

1. **One semantic owner.** Other layers call or project the owner; they do not reproduce its rules.
2. **Product core before interfaces.** Use `owner -> contract -> adapter/projection -> consumer`. UI, Web, CLI, tools, storage, daemon transport, and skills are not alternate products.
3. **Dependencies point toward ownership.** Adapters depend on public owner contracts; owners do not depend on adapter DTOs or presentation. Cross-domain behavior uses an explicit operation or capability.
4. **Boundaries follow change.** Repeated edits to a router, registry, manager, global type, or shared utility are architecture feedback. Move the boundary instead of adding another case.
5. **One truth and one write path.** Derived projections may be many; canonical state, owner, schema, and mutation path are singular.
6. **Monolith first, boundaries always.** Keep coordination local until real lifecycle, scaling, isolation, or ownership pressure earns distribution.
7. **Composition is explicit.** A composition root may know concrete implementations; generic infrastructure may not discover or branch on product semantics.
8. **Legibility over cleverness.** Prefer direct calls, exact schemas, small public contracts, boring inspectable technology, and bounded behavior.
9. **Enforce invariants, allow local freedom.** Mechanize ownership, dependency, state, cleanup, and public-contract rules; do not micromanage equivalent local style.

## Development Framework

Every non-trivial change follows this state sequence. Small work may compress notes, but not skip reasoning.

| State | Required action | Exit condition |
|---|---|---|
| FRAME | Name bottleneck, relevant observable outcome, scope, and protected contracts | One relevant observable acceptance sentence; product paths state `consumer action -> owning path -> observable result` |
| TRACE | Locate semantic or artifact owner, affected call/state/artifact path, tests/proofs, live surfaces, and retired residue | Owner and affected path are grounded in current repository facts |
| PROVE | Select exact RED, regression, refactor baseline, or artifact proof | Evidence can detect the intended change or preservation |
| BUILD | Make the smallest direct owner-correct change | Changed behavior, preserved behavior, or artifact satisfies exact proof; applicable failures are explicit |
| REPLACE | Remove every superseded live path and update every live consumer, contract, test, fixture, and doc; if nothing is superseded, prove this state inapplicable | No unexplained duplicate or retired path; actual replacement claims have one live path |
| VERIFY | Prove exact behavior and affected boundaries; inspect cleanup | Source-bound evidence is clean and sufficient for the claim |
| ACCEPT | Audit final diff against acceptance sentence and proof classes | Every material claim is proved or explicitly inapplicable |

For multi-file, unfamiliar, cross-boundary, or high-unknown work: explore, write the smallest sufficient plan, implement coherent blocks, and verify each block. Long work keeps a resumable artifact with outcome, state, progress, decisions, commands, and risk.

## Testing Contract

For executable code, tests, runtime contracts, or test infrastructure, follow `$buddyswitch-testing`. It alone owns dynamic target discovery, RED/GREEN and refactor entry, evidence identity, escalation breadth, and reviewer probes.

The only public test entry is:

```bash
./buddyswitch-test focused <file-or-nodeid>...
./buddyswitch-test full
```

- Use `focused` for ordinary claim-scoped proof.
- Use `full` only for a frozen merge/release candidate, explicit repository-wide acceptance, or direct user request.
- Tests prove semantic behavior, persisted state, failure effects, and consumer results—not only fields, mocks, registration, or `ok=true`.
- Mutating operations have one end-to-end terminal truth: persisted effects, protocol results, consumer-observed status, and attributable runtime errors agree. Any contradiction invalidates acceptance even when state eventually converges.
- Resource-owning tests prove cleanup and leave no process, socket, lock, or temporary-state residue.
- Manual checks supplement repeatable automated proof; they do not replace it.

Do not add a second test entry, policy owner, impact engine, or evidence ledger.

## Acceptance Framework

Testing answers whether selected behavior passed. Acceptance answers whether the whole claim is true. Select every material proof class:

| Proof | Acceptance question |
|---|---|
| Product | Can the consumer complete the promised loop and observe the result? |
| Contract | Are success, failure, authority, and state effects exact? |
| Architecture | Is behavior owned once with valid dependencies and change locality? |
| Replacement | Is the retired live model absent rather than guarded or bypassed? |
| Operations | Are resources, cleanup, logs, and failure recovery correct? |

A broad suite does not replace missing direct product or residue proof; a narrow test does not prove repository-wide acceptance. Evidence records claim, source identity, exact check, result, cleanup, and risk. If material proof is blocked, report it and do not claim completion.

## Codex Engineering Style

- Repository facts outrank memory, other-project conventions, and plausible guesses. Inspect code, contracts, tests, instructions, and git state first.
- Trace the semantic owner and consumer path before editing. Fix the owning cause, not an interface symptom.
- Keep one intent per change. Do not mix features, broad renames, formatting, unrelated cleanup, test-framework work, or architecture migration.
- Preserve unrelated user work. Partition dirty scope; never stage, revert, or rewrite it for convenience.
- Prefer code and contract clarity over prompt bulk. If a tool/API is hard to use correctly, fix its semantics, schema, response, or feedback.
- Resolve local implementation ambiguity; escalate only for product meaning, external contracts, irreversible data or operations, security, privacy, payment, or permission risk.
- Review generated code for guessed shapes, copied rules, unnecessary helpers, shared grab bags, hidden fallbacks, unbounded behavior, and speculative layers.
- Do not suppress errors, weaken assertions, or add fallbacks that hide bad state.
- Optimize team/repository throughput, not generated volume. The diff must be understandable without reconstructing agent reasoning.

## Quality Ratchet

Move every recurring lesson to the lowest enforceable owner:

```text
wrong runtime behavior      -> owning code/contract + regression test
repeated architecture drift -> structural test or linter
repeated workflow judgment  -> focused skill
durable architecture reason -> docs/arch
long-task execution state   -> resumable plan
historical investigation    -> memo, never live policy
```

Do not add prose when a machine can enforce the rule, and do not build a framework for a one-off judgment. Repeated hotspots trigger boundary repair; escaped defects receive the smallest test that would have caught them.

## Repository Contract

- Root `AGENTS.md` owns durable philosophy, laws, workflow, commands, and navigation; skills own repeated judgment; `docs/arch/` owns current boundaries; plans own active multi-stage state; code, contracts, tools, and tests own executable truth; memos preserve history only.

Stable BuddySwitch paths:

- product source mount: `projects/app/`;
- environment manifest: `src/buddyswitch/catalog/manifest.toml`;
- product launcher: `./buddyswitch-codex instance start --role <role>`;
- role bootstrap guidance: `src/buddyswitch/launcher/assets/roles/<role>/AGENTS.md`;
- runtime track projections: `buddyswitch/objects/tracks/*.json`;
- runtime task projections: `buddyswitch/objects/task-sys/tasks/*.json`;
- runtime artifact projections: `buddyswitch/objects/artifacts/*.json`;
- active-instance private files: `$BUDDYSWITCH_ACTOR_PRIVATE_DIR`, which resolves to the active instance `workspace/private`.

Use environment tools for product-mode state. Do not edit `buddyswitch/objects/**`, `buddyswitch/local/private/**`, or old private runtime paths directly. Runtime contracts belong to code, JSON contracts, role contracts, and tests; do not create prose mirrors.

## Definition of Done

A task is done only when:

1. the named bottleneck materially moved and the acceptance sentence is true;
2. the change is owner-correct, direct, and no more abstract than current need;
3. relevant product, contract, architecture, replacement, and operational claims have sufficient evidence;
4. retired residue is absent; if protected coexistence remains, the task is accepted only as a bounded migration phase with a named removal trigger, never as a completed replacement;
5. tests/checks pass at claim-appropriate breadth with clean residual state;
6. scope stayed focused, unrelated work stayed intact, and the repository is at least as legible as before;
7. the final report names changed behavior/files, exact verification, omitted checks, residual risk, and next owner/action.

No verification, no acceptance. No completed replacement with historical baggage.
