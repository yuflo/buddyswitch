# S5 C2 WebHost and Cleanup Cutover

> State: `READY`
> Packet: `BS-MM-S5-WEB-CLEANUP-R1-20260804-01`
> Executable base: `e687fa264408de0bf70f7f7411194e78d044dad9`

C2 removes the two remaining product-enumerated decisions in the current Web
and cleanup hosts without moving those hosts prematurely:

- Track contributes its existing external read routes through the typed Web
  contribution boundary;
- WebHost dispatches validated exact and prefix matchers and imports no
  concrete product module;
- cleanup plan/result projection fields are created and reconciled from the
  selected typed cleanup contributions, not from a host-owned product list;
- all current Web routes, payloads, errors, cleanup paths, warnings, deletion
  effects, output fields and CLI behavior remain observable as before.

Read in order:

1. `S5-C2-SOURCE-AND-CONSUMER-SNAPSHOT.md`;
2. `S5-C2-BOUNDARY-DESIGN-AND-PREFLIGHT.md`;
3. `S5-C2-PREFLIGHT-COMMAND.md` for reproducibility evidence;
4. `S5-C2-IMPLEMENTATION-PLAN.md`;
5. `S5-C2-READY-REVIEW.md`;
6. `S5-C2-GOAL-PACKET.md`.

The packet authorizes C2 only. C3–C7 and S6 remain blocked.
