# S5 Foundation Convergence Charter

> Current state: C1–C5B ACCEPTED — C6 PREPARATION ONLY
> Entry prerequisite: S4 ACCEPTED
> Execution authority: none; C6 implementation awaits source-bound READY review
> Merge model: ordered owner-bounded checkpoints, then final S5 acceptance

The executable blueprint and current handoff live at
`05-foundation-convergence-plan/README.md`. The charter's acceptance sentence
still applies to the whole stage; C1 alone does not accept S5.

## Acceptance sentence

> Foundation imports no concrete component or Role and owns only product-neutral
> lifecycle, protocol, transport, identity, state and process behavior; every
> product meaning arrives through a typed contribution or Public operation.

## Exact convergence targets

- application imports component assemblies only;
- Daemon entrypoint names no product handler;
- ToolHost uses explicit complete registrations, not directory scanning;
- invalid Tools fail startup;
- ToolContext contains host facts/injected Public capabilities, not product
  repositories/domains;
- Web/Cli hosts contain no product route/projection switches;
- Browser has one Actor-resource lifecycle owner;
- cleanup host uses component cleanup contributions;
- no dynamic source/check-out loading or repository-root runtime dependency;
- foundation-to-component/Role imports are machine-forbidden.

## Entry gate

- accepted final component set;
- exact remaining shared hotspots and residues;
- component Public and contribution contracts frozen;
- no owner work deferred from S2–S4;
- foundation plan proves behavior preservation.

The stage entry gate is satisfied. Each later Foundation checkpoint still
requires its own current-source READY gate before execution.

## Proof

- generic architecture/import tests;
- application duplicate/invalid startup failure;
- Tool catalog completeness;
- Daemon/Web/CLI/cleanup behavior;
- Browser and process lifecycle;
- Actor lifecycle matrix;
- package/runtime identity;
- absence of scanners, dynamic loads, broad contexts and product tokens.

## Forbidden

- changing accepted product semantics/Public contracts;
- universal loader/plugin/container/event bus;
- service split;
- replacing one service locator with another;
- retaining old discovery as fallback.
