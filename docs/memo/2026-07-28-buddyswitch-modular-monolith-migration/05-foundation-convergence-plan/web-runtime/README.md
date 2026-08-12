# S5 C6E Web Runtime

> State: `ACCEPTED`
> Acceptance: `S5-C6E-ACCEPTANCE.md`
> Executable base: `cfcbf387726359d766889114eb87688c211f0276`

C6E converges the already product-neutral Web host, its passive contracts and
packaged UI assets under one `foundation/web_runtime/**` owner. The small
machine-first CLI envelope/contribution contract moves to
`foundation/cli_runtime/contracts.py` as the Web host's direct sibling
dependency and the stable input for the later CliHost cutover.

R1 completed the physical move but left one embedded
Foundation-to-Application executable dependency in the Open-TUI command
builder. R2 supplied that fact from Application, extended the bounded owner
proof and passed affected plus frozen repository acceptance. Both packets are
consumed. Read the completed chain in order:

1. `S5-C6E-R1-RETURN-REVIEW.md`;
2. `S5-C6E-R2-READY-REVIEW.md`;
3. `S5-C6E-R2-GOAL-PACKET.md`;
4. `S5-C6E-ACCEPTANCE.md`.

C6E changes no route, DTO, lifecycle, worker, static-asset, CLI envelope or
product semantics. It does not move the CLI host, remaining shell owners,
Codex config, Role assets, C7 or S6.
