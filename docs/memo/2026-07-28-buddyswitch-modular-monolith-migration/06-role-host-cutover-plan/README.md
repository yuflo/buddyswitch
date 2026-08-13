# S6 RoleHost Cutover Plan

> State: `ACCEPTED`
> Acceptance: `S6-ACCEPTANCE.md`
> Packets: R1 and R2 consumed
> Merge unit: one atomic Role/Skill truth replacement

## Acceptance sentence

> A reviewed Role package is available by adding one valid packaged directory;
> invalid or duplicate Roles fail before Actor publication; only selected
> Role/Skill content reaches the Actor; central Role/Skill/profile/contract
> catalogs and their live path arguments are absent.

## Why this is one cutover

The current manifest is simultaneously consumed by Actor bootstrap, Tool
authority, Tool context, Search, Context, Artifact, CLI sandboxing, Host
Control, Broker, cleanup, diagnostics and packaging. Moving only the Role files
would leave a second semantic track. S6 therefore replaces the source,
selection and every manifest-shaped consumer together, while keeping product
modules and Foundation hosts otherwise behavior-equivalent.

The implementation may use coherent internal blocks, but none is an accepted
intermediate architecture.

## Read order

1. `../06-role-host-cutover.md`;
2. `S6-SOURCE-AND-CONSUMER-SNAPSHOT.md`;
3. `S6-BOUNDARY-DESIGN-AND-PREFLIGHT.md`;
4. `S6-IMPLEMENTATION-PLAN.md`;
5. `S6-READY-REVIEW.md`;
6. `S6-GOAL-PACKET.md`;
7. `S6-ACCEPTANCE.md`.

## Selected topology

```text
explicit module assemblies -> component SkillExport values
                                      |
                                      v
Application ----------------------> RoleHost
                                      |
reviewed buddyswitch.roles/*/role.py -+
                                      |
                 +--------------------+--------------------+
                 |                    |                    |
        Actor bootstrap       Role runtime facts     Role list/valid IDs
      AGENTS + selected       Tool authority and      Host/CLI/cleanup/
        Skills only           narrow capabilities       diagnostics
```

RoleHost is the only earned discovery exception. It scans one trusted packaged
Role root for exact descriptors. It does not discover product modules, install
remote packages, negotiate versions, register hosts or execute arbitrary Role
hooks.

## Stage boundary

S6 includes the first `secondary-market-investor` package as a meaningful
extension proof. Its Role content may guide long-horizon public-market analysis
through budget pools, player qualification, evidence, valuation and entry
odds. It does not add trading automation, a market-data service, a new product
module, a Daemon handler, Tool, Web route or host lifecycle.

The coordinating hub accepted the R2 candidate after closing R1's escaped
private-Skill, central-test and Foundation-contract defects. S7 source refresh
and READY preparation begin only from the committed and pushed S6 checkpoint.
