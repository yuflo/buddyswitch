# S5 C6E Web Runtime

> State: `READY`
> Packet: `BS-MM-S5-WEB-RUNTIME-R1-20260812-01`
> Executable base: `cfcbf387726359d766889114eb87688c211f0276`

C6E converges the already product-neutral Web host, its passive contracts and
packaged UI assets under one `foundation/web_runtime/**` owner. The small
machine-first CLI envelope/contribution contract moves to
`foundation/cli_runtime/contracts.py` as the Web host's direct sibling
dependency and the stable input for the later CliHost cutover.

Read in order:

1. `S5-C6E-SOURCE-AND-CONSUMER-SNAPSHOT.md`;
2. `S5-C6E-BOUNDARY-DESIGN-AND-PREFLIGHT.md`;
3. `S5-C6E-IMPLEMENTATION-PLAN.md`;
4. `S5-C6E-READY-REVIEW.md`;
5. `S5-C6E-GOAL-PACKET.md`.

C6E changes no route, DTO, lifecycle, worker, static-asset, CLI envelope or
product semantics. It does not move the CLI host, remaining shell owners,
Codex config, Role assets, C7 or S6.
