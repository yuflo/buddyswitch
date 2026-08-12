# S5 C6E R1 Return Review

> Packet: `BS-MM-S5-WEB-RUNTIME-R1-20260812-01`
> Disposition: `REJECTED — BOUNDED R2 CONTINUATION REQUIRED`
> Candidate: HEAD `29bed25bc8f07600b350042061a64eb2f7a013cd`, tracked patch `a3363d378fc29a13338ca82fcabd7507c141084b53fdbada7f17cca591c3ebec`

## Accepted candidate facts

- the returned tracked patch and 20-file untracked manifest reproduce exactly;
- Web runtime/contracts/assets and the shared CLI contract have moved to their
  selected direct Foundation owners, with inert package roots;
- application, component, test/support, package and current-doc consumers use
  the new owners, while all retired Launcher modules and assets are absent;
- the three moved Python owners/contracts and all 13 assets preserve the R1
  behavior and byte identity except for the intended import/owner rewrites;
- direct, affected, package, JavaScript, real-Web and repository FINAL evidence
  is source-bound; FINAL `95a1b1fbba504313854017baefeb8768`
  passed every tier;
- the activated non-editable runtime verifies with source digest
  `0ed1c8af30aace895d782f44e874326f64f4d266e93e328260e6cc0915bae8b8`
  and distribution digest
  `d69fa3ada5b98fcff122f7d7ae9665ed32e648cf25ad404b2be2da5edebd4987`;
- no attributable process, socket, test root or generated build residue remains.

These facts remain reusable while the preserved R1 candidate identity is
unchanged.

## Blocking finding

The claimed Foundation boundary is not yet true. The moved owner still embeds
one concrete Application entrypoint:

```text
foundation/web_runtime/runtime.py
  build_attach_cli_command(...)
    -> buddyswitch.application.entrypoints.cli
```

This string is executed by Terminal through `python -m`; it is therefore a
real Foundation-to-Application runtime dependency even though it is not a
Python import. An Application entrypoint rename would still require editing
Foundation. That contradicts both the C6E acceptance sentence and the Result
Packet claim that Foundation Web/CLI has no Application dependency.

The new architecture test checks AST imports only, so it cannot detect this
class of executable edge.

## Responsibility and quality ratchet

The primary cause is preparation-side proof incompleteness. The C6E preflight
used a projected Python import graph and declared the upward-dependency gate
clean without checking executable module strings. This also failed to apply
the already recorded C6D lesson that dependency proof must cover imports,
shell/module invocations, embedded paths and package projections. The executor
and its reviewers had secondary responsibility for accepting the same blind
spot.

The durable reviewer rule now lives in
`.agents/skills/buddyswitch-testing/references/review.md`. The lowest executable
owner remains the small C6E architecture assertion; R2 must expand it only
across this owner and stable forbidden roots, not create a static-analysis
framework.

## Continuation decision

R1 is consumed and may not resume. Preserve its coherent dirty candidate; do
not roll back, replay or reimplement the move. R2 changes only the escaped
Open-TUI executable dependency, its Application assembly input and the nearest
proof/current prose. Every accepted Web/CLI behavior and all later C6F/C7/S6
boundaries remain protected.
