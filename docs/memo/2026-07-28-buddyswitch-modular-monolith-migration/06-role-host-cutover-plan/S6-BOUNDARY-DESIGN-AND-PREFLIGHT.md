# S6 Boundary Design and Preflight

## Bottleneck

Adding or changing a Role currently crosses one central manifest, central
profiles, central Skill paths, Launcher assets, Role contracts and multiple
host path arguments. The most frequently changed Role-private content therefore
cannot remain physically or semantically local.

## Selected boundary

### Role package

Each reviewed package under `src/buddyswitch/roles/<package_name>/` owns:

```text
role.py              exact ROLE descriptor; directory name is not identity
AGENTS.md            Actor bootstrap guidance
private/             Role-private implementation, never implicitly executed
skills/              Role-private Skill packages
assets/              Role-owned contracts/templates/data
tests/{unit,contract,integration}/
```

An absent subtree need not be manufactured. The public descriptor schema is
small and stable; private content may change locally. Role-private executable
code is permitted as reviewed package code, but S6 does not invent a generic
execution-hook contract where no current consumer exists.

### RoleHost

`foundation/role_host/**` owns:

- discovery only below the installed trusted `buddyswitch.roles` root;
- loading exact `role.py` entrypoints and exact `ROLE` descriptors;
- fail-closed descriptor, ID, duplicate, file, containment, symlink and selected
  Skill validation;
- combination of Role-private Skills with Application-supplied component
  `SkillExport` values;
- immutable Role list, selected runtime capability and Actor-bootstrap
  projections.

RoleHost imports no concrete Role and discovers no product module. Application
constructs it from the explicit component Skill exports and supplies its narrow
projections to Foundation hosts and product tool invocations.

### Authority

The current Role policy grants every known Role every permission declared by
current Tool registrations and denies unknown Roles/permissions. S6 preserves
that outcome without copying the permission names into every Role or a new
central list: Application/ToolHost derives the valid permission universe from
the explicit Tool registrations and combines it with RoleHost's validated Role
IDs. Any future Role restriction must be an explicit Role contract, not a
hidden central addition map.

### Runtime projection

The full descriptor and package paths do not become a generic ToolContext bag.
One immutable selected Role projection carries only earned current facts, such
as Role identity, Artifact template choices, source path/access and
Search/Browser boundary. Tool authority is configured separately. Product
modules may consume the projection's public contract; they do not load Role
files or depend on RoleHost private code.

### Actor projection

RoleHost resolves one `ResolvedActorBootstrap`-equivalent input for the existing
Foundation Actor publisher. The publisher remains atomic and product-neutral.
It copies only the selected Role's AGENTS and selected component/Role-private
Skills; descriptor, tests, assets unrelated to Actor guidance, private code and
other Roles remain outside the Actor workspace.

## Secondary-market-investor proof

The package directory is `secondary_market_investor` while its durable ID is
`secondary-market-investor`, directly proving that path name is not identity.
It is a read-only research/decision Role. Its guidance should analyze a public-
market bet through addressable budget pools, value capture, qualified players,
evidence quality, valuation/odds and entry conditions rather than short-horizon
news gambling. It may reuse existing component Skills and own focused
Role-private guidance. It must not introduce trading execution or a new host
capability.

## Runner mechanism

The existing `tests/runner.py` remains the only test owner. Its local-tier
discovery generalizes from module roots to the two approved local owners:

```text
modules/*/tests/{unit,contract,integration}
roles/*/tests/{unit,contract,integration}
```

Parent `tests` directories are not valid tier targets. Role process/system tests
remain forbidden and root-owned. Wheel/package correspondence still excludes
every local test.

## Representative final-topology preflight

Preflight `S6P-22d21453397022fd` passed 8/8 checks:

- Application explicitly depends on modules and RoleHost;
- RoleHost and reviewed Roles depend only on Foundation contracts;
- Foundation contracts import no concrete Role;
- RoleHost has no product-module activation edge;
- the projected graph is acyclic;
- one combined local-tier discovery finds representative module and Role
  unit/contract/integration roots exactly once;
- it does not admit Role process/system tiers;
- it does not mistake a parent test directory for a tier.

This is a mechanism probe, not implementation evidence.

## Entry preservation evidence

Run `e289d49da34a4e6c90adb9622a9bdcc3`:

```text
./buddyswitch-test focused \
  tests/unit/env_tool/test_manifest.py \
  tests/process/cli/test_buddy_env_profiles.py \
  tests/unit/actor/test_role_action_auth.py \
  tests/unit/actor/test_runtime_skills.py \
  tests/unit/architecture/test_output_schema_boundaries.py \
  tests/unit/architecture/test_actor_environment_foundation_owner.py \
  tests/unit/architecture/test_search_component_boundaries.py \
  tests/unit/architecture/test_context_component_boundaries.py \
  tests/process/launcher/test_bootstrap_config.py \
  tests/process/launcher/test_instance_commands.py \
  tests/process/launcher/test_public_cli.py \
  tests/process/cli/test_host_control.py \
  tests/integration/runtime_broker/test_broker.py \
  tests/process/package/test_distribution_install.py
216 passed, 517 subtests
```

Run `dde21cf252224a7e86a2d36a0afe6323`:

```text
./buddyswitch-test focused \
  tests/process/cli/test_env_tool_router.py \
  tests/process/cli/test_black_box_tool_runtime.py \
  tests/integration/runtime/test_turn_integration.py \
  tests/integration/runtime/test_tool_feedback.py \
  tests/unit/env_tool/test_active_task_gate.py \
  tests/integration/env_tool/test_layer_end_to_end.py \
  tests/unit/env_tool/test_identity.py \
  tests/integration/env_tool/test_payload_contract.py \
  tests/integration/env_tool/test_run.py \
  tests/integration/env_tool/test_host_decision_surface.py \
  tests/unit/env_tool/test_semantic_contract.py \
  src/buddyswitch/modules/search/tests/integration \
  src/buddyswitch/modules/track/tests/integration \
  tests/unit/architecture/test_tool_runtime_contract.py \
  tests/unit/architecture/test_demand_sys_boundaries.py \
  tests/unit/architecture/test_task_management_skill.py \
  tests/unit/architecture/test_foundation_final_boundary.py \
  tests/unit/architecture/test_cli_runtime_foundation_owner.py \
  tests/unit/architecture/test_host_control_foundation_owner.py \
  tests/unit/architecture/test_runtime_broker_boundaries.py \
  tests/unit/support/test_runner.py
148 passed, 631 subtests
```

Both used the activated runtime identity recorded in the snapshot and left no
test root or attributable process. Frozen S5 FINAL
`364f7e924501414a9ca48b3404645307` is source-equivalent and passed all tiers.

The executor owns exact current target rediscovery. These runs freeze the
assertion-level behavior groups; they are not immutable command transcripts.

## Rejected alternatives

- keep a generated or compatibility manifest: leaves two truths;
- use Python entry points or a general PluginHost: expands the trusted and
  lifecycle boundary without current need;
- have RoleHost discover product modules: violates explicit composition;
- retain full manifest/path in ToolContext: preserves the central coupling;
- copy every old profile field: turns duplicated advisory metadata into a new
  permanent contract;
- split source movement from consumer cutover: creates an unrunnable or dual-
  path intermediate product.
