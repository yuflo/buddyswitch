# S5 C6F CLI Runtime

> State: `READY`
> Packet: `BS-MM-S5-CLI-RUNTIME-R1-20260812-01`
> Entry checkpoint: `01335be4232d9f7d96a099f22920d679b77a03fc`

C6F is the last implementation checkpoint in S5. It converges the generic
public CLI host, Codex configuration adapter and its three cooperating shell
adapters into direct Foundation CLI Runtime ownership. Application supplies
the concrete executable, manifest and current Role-profile facts; Foundation
owns parsing, projection, shell orchestration and config mechanics without an
upward implementation dependency.

Read in order:

1. `S5-C6F-SOURCE-AND-CONSUMER-SNAPSHOT.md`;
2. `S5-C6F-BOUNDARY-DESIGN-AND-PREFLIGHT.md`;
3. `S5-C6F-IMPLEMENTATION-PLAN.md`;
4. `S5-C6F-READY-REVIEW.md`;
5. `S5-C6F-GOAL-PACKET.md`.

C6F does not move or redesign Role assets, Role/Skill discovery, central
manifest/profile policy, C7 guidance or S6 RoleHost. No later implementation
is authorized by this packet.
