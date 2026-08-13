# RoleHost Architecture

## Current boundary

Every reviewed Role is one physically aggregated installed package under
`src/buddyswitch/roles/<package_name>/`. It owns its exact `role.py` descriptor,
`AGENTS.md`, Role-private Skills, optional assets/private code, and local
unit/contract/integration tests. Directory name is not Role identity; the
`secondary_market_investor` package intentionally declares the durable ID
`secondary-market-investor`.

`src/buddyswitch/foundation/role_host/` is the only Role host. It scans exact
package directories below the trusted installed Roles root, loads only exact
`role.py` entrypoints, validates descriptors, AGENTS, the Role-local
`assets/result-schema.json` contract, containment and symlinks, and combines
Role-private Skills with Application-supplied component `SkillExport` values.
Any malformed or duplicate Role/Skill package fails activation before Actor
publication.

Each Role-private Skill namespace is local to its owning package. Two Roles may
use the same private Skill ID independently, but a Role may select only its own
private Skills plus public component Skills. A private/component ID collision
inside one Role fails activation; IDs are never qualified, aliased or resolved
through another Role.

## Dependency and projection rules

```text
reviewed Role package -> Foundation Role descriptor contract
product module        -> Foundation SkillExport + Artifact template vocabulary
Application           -> RoleHost.discover(component Skills, Artifact templates)
RoleHost              -> list | RoleRuntime | Actor bootstrap
```

RoleHost imports no concrete Role and activates no product module. Application
derives Tool authority from RoleHost's validated IDs and permissions declared
by live Tool registrations. Consumers receive only earned immutable facts:
Host Control receives Role summaries, CLI/ToolContext receive `RoleRuntime`,
cleanup receives valid IDs, and Actor publication receives exactly the selected
AGENTS and Skills.

Artifact Public owns the allowed Artifact-template vocabulary. Application
supplies that exact value during RoleHost activation, so Foundation validates a
Role selection without copying product policy. Descriptor/runtime fields are
limited to live list, Actor, source, CLI, Browser/Search and Artifact consumers;
retired advisory profile metadata is not retained.

There is no central manifest, Role profile, compatibility loader, generated
catalog, module discovery, entry-point loader, provider family, service locator,
or generic Role execution hook.

## Packaging and proof

The wheel includes Role code, AGENTS, selected Skill resources and assets, but
excludes every Role-local test. The single `./buddyswitch-test` runner discovers
the exact `modules/*/tests/{unit,contract,integration}` and
`roles/*/tests/{unit,contract,integration}` tiers; Role process/system tiers are
not valid local targets.
