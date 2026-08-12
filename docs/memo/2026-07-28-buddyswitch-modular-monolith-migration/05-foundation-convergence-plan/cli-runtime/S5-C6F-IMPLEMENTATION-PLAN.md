# S5 C6F CLI Runtime Implementation Plan

> For the independent executor: use the current repository, root `AGENTS.md`
> and `$buddyswitch-testing`. This plan freezes outcome and authority; path and
> signature examples are hypotheses, not transcription commands.

## Goal

Replace the remaining executable Launcher CLI/config/shell cluster with one
direct Foundation CLI Runtime owner while preserving every public outcome and
leaving current Role truth exclusively Application/S6-owned.

## Coherent block 1 — owner and Application input

- Extend the existing CLI Runtime package with the generic host, config adapter
  and three cooperating shell adapters.
- Define one small required immutable Application input for the exact concrete
  executable/manifest/Profile facts that Foundation currently embeds.
- Assemble that input once in Application and use it from both the public CLI
  entrypoint and Host-start configuration.
- Keep package roots inert. Do not add exports, factories, registries,
  providers, containers, locators or discovery.
- Do not run the public test runner while source and installed runtime identity
  intentionally diverge; complete the coherent source block first.

## Coherent block 2 — direct replacement

- Update every live import, path, package projection, shell source and current
  consumer to the new direct owners.
- Make all Foundation Python and shell executable representations consume the
  required Application input rather than name Application, Launcher, product,
  runtime-support or Role implementations.
- Preserve exact CLI command/envelope/exit/help, Web launch, config, MCP,
  Browser, cleanup, lock and Host-start behavior.
- Delete the five retired Launcher owner files and every zero-consumer helper.
- Leave only the inert Launcher package plus `assets/roles/**`; do not move or
  redesign those S6 inputs.

## Coherent block 3 — proof and current guidance

- Add or update one bounded owner-local architecture proof covering Python
  imports, embedded module/path strings, shell invocations and package
  projection for the complete CLI Runtime owner.
- The guard may scan stable forbidden roots recursively; it must not become a
  lexical scope engine, dependency framework or generalized static analyzer.
- Keep cross-owner tests in root test tiers. Tests do not move into the module
  merely because source moved.
- Update only current architecture/help/package guidance affected by the owner
  replacement. Migration master truth remains hub-owned.

## Verification sequence

1. Reproduce the clean entry commit/runtime identity and classify any drift.
2. Reuse the source-equivalent baseline evidence; do not manufacture a
   structural RED for this behavior-preserving refactor.
3. Complete all coherent `src/**`, tests, package and current-doc changes.
4. Build/install/activate/verify one non-editable runtime from that candidate.
5. Discover current exact and affected targets from changed tests/symbols and
   live consumers. Prove direct CLI/config/shell behavior, Application
   assembly, architecture/replacement, Process/package and real System loops.
6. Review every executable owner representation, freeze once and run one
   `./buddyswitch-test full` FINAL.
7. Any executable change after FINAL enters bounded FIX_AFTER_FINAL: exact and
   affected proof, reprovision if `src/**` changed, then one replacement FINAL
   after the candidate freezes.

## Stop/replan conditions

Stop only when repository facts require a product/Role semantic decision,
protected external contract change, irreversible data action, a second live
path, or later C7/S6 work to make C6F runnable. A stale path, constructor,
test target or package assertion inside the authorized boundary is executor
work, not a coordinator round trip.
