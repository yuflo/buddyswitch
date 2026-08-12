# S5 C6E Web Runtime

> State: `R1 REJECTED; bounded R2 READY`
> Current packet: `BS-MM-S5-WEB-RUNTIME-R2-20260812-01`
> Executable base: `cfcbf387726359d766889114eb87688c211f0276`

C6E converges the already product-neutral Web host, its passive contracts and
packaged UI assets under one `foundation/web_runtime/**` owner. The small
machine-first CLI envelope/contribution contract moves to
`foundation/cli_runtime/contracts.py` as the Web host's direct sibling
dependency and the stable input for the later CliHost cutover.

R1 completed the physical move and passed its behavior evidence, but left one
embedded Foundation-to-Application executable dependency in the Open-TUI
command builder. Preserve that candidate and read the continuation in order:

1. `S5-C6E-R1-RETURN-REVIEW.md`;
2. `S5-C6E-R2-READY-REVIEW.md`;
3. `S5-C6E-R2-GOAL-PACKET.md`;
4. the original snapshot/design/plan for preserved C6E behavior.

C6E changes no route, DTO, lifecycle, worker, static-asset, CLI envelope or
product semantics. It does not move the CLI host, remaining shell owners,
Codex config, Role assets, C7 or S6.
