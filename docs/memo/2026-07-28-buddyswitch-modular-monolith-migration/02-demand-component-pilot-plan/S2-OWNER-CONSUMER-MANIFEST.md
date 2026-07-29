# S2 Demand Owner and Consumer Manifest

## Current owner

| Current path | Current responsibility | S2 disposition |
|---|---|---|
| `src/buddyswitch/env/domain/demand_sys.py` | only Demand mutation and lifecycle rule owner | move to `modules/demand/private/domain/demand_sys.py` |
| `src/buddyswitch/env/domain/demand_read.py` | external-safe CLI projection | move to `modules/demand/private/read_model.py` |
| `src/buddyswitch/env/repos/demands.py` | schema 5, lock, validation, atomic replacement | move to `modules/demand/private/state/demands.py` |
| `src/buddyswitch/env/tools/demand_sys/**` | four-action Tool definition and adapter | move to `modules/demand/private/adapters/tool/**` |
| `src/buddyswitch/launcher/demand_sys_daemon_adapter.py` | inbound daemon attention adapter | move behind Demand Public inbound operation |
| `src/buddyswitch/launcher/demand_triage_runtime.py` | capability-bound Side resolution | move to Demand private daemon adapter |
| `src/buddyswitch/launcher/demand_triage_handler.py` | triage lifecycle/recovery | move to Demand private daemon adapter |
| `src/buddyswitch/launcher/demand_orchestration_handler.py` | pool/Task orchestration | move to Demand private daemon adapter |
| `src/buddyswitch/skills/shared/demand-triage/**` | triage semantic execution | move to `modules/demand/skills/demand-triage/**` |
| `src/buddyswitch/skills/shared/demand-orchestration/**` | parent orchestration execution | move to `modules/demand/skills/demand-orchestration/**` |

## Canonical state

S2 does not move or translate data:

```text
state path:
  <state-root>/buddyswitch/objects/demand-sys/actors/<actor-id>-<role-id>.json
lock path:
  <state-root>/buddyswitch/local/locks/demand-sys/<actor-id>-<role-id>.lock
schema:
  5
write path:
  Demand domain -> demands.transact_actor_state -> write_json_object
```

`D-009` therefore remains ordinary Sharp mode: source changes directly;
canonical data remains current and needs no compatibility reader or dual
write.

## Real Public consumers

Only two Demand Public capabilities are earned:

| Public capability | Current consumer | Required call after S2 |
|---|---|---|
| `resolve_demand_ref(...)` | unmigrated Task Tool create adapter at `env/tools/task_sys/_impl.py:294` | import `modules.demand.public`; no Demand private or broad `ToolContext.rules.demand_sys` |
| `enqueue_inbound(...)` | IM and Track handlers at `launcher/im_wake_handler.py:114` and `launcher/track_comment_added_handler.py:124` | import `modules.demand.public`; no private daemon adapter import |

Demand CLI reads are private CLI adapter behavior, not a cross-component
Public facade. Demand Tool/Daemon/Skill/cleanup pieces are host contributions,
not Public operations.

The Demand orchestration adapter currently calls unmigrated Task domain
behavior. S2 records that existing transitional edge and does not invent a
Task facade. S3 owns Task/Goal physical aggregation and the final exact
cross-component direction.

## Host seams that must lose Demand-private knowledge

| Host/current path | Current Demand knowledge | Required S2 replacement |
|---|---|---|
| `launcher/instance_daemon.py` | imports and constructs two concrete Demand handlers | receives `DaemonHandlerRegistration` values from application |
| `launcher/cli.py` | imports Demand read model and branches on `demand` | receives one `CliCommandRegistration` |
| `env/tool_runtime/registry.py` | discovers `env.tools.demand_sys` | receives explicit `ToolRegistration`; old Tool package is deleted |
| `env/tool_runtime/context.py` | imports Demand domain and owns Demand ingress application type | remove both; Demand Tool uses its own private owner and generic invocation facts |
| `runtime_kernel/dispatcher.py` | imports Demand triage runtime and constructs Demand application access | remove; registry invokes the explicitly registered Demand adapter |
| `launcher/env_tool_mcp_server.py` | branches on `demand_sys.resolve_inbound` | derive the generic bound capability from Tool action metadata |
| `launcher/codex_config.py` | hard-codes parent Demand disabled Tool | derive disabled native actions from Tool visibility/capability metadata |
| `launcher/actor_environment.py` | hard-codes disabled `demand-triage` Skill | derive from assembled `SkillExport.enabled_by_default` |
| `catalog/manifest.toml` | owns Demand Skill paths | delete the two Skill rows; retain current Role selection IDs until S6 |
| `runtime_support/env_cleanup.py` | has no Demand state attribution | receive one typed Demand cleanup contribution |

Public Tool IDs, action names, permissions and help text are protected
consumer contracts, not private imports. They may remain as literals in policy
or proof surfaces where the public contract requires them.

## Web review

There is no current Demand Web route, Web DTO, panel or mutation. Web is
therefore explicitly inapplicable in S2:

- no speculative `WebRoute`;
- no empty Web plugin surface;
- no Demand Web feature;
- existing Web-visible Task/Artifact product flow remains a root system proof.

## Test ownership

Move with the module:

```text
tests/unit/demand_sys/**
  -> src/buddyswitch/modules/demand/tests/unit/**
tests/integration/demand_sys/**
  -> src/buddyswitch/modules/demand/tests/integration/**
```

Remain root-owned:

- architecture and package boundary tests;
- Task/Goal cross-component integration;
- env Tool wire and native MCP;
- public CLI/process tests;
- Actor lifecycle and system product flow;
- cleanup orchestration tests.

The runner accepts only:

```text
src/buddyswitch/modules/*/tests/unit
src/buddyswitch/modules/*/tests/contract
src/buddyswitch/modules/*/tests/integration
```

It does not accept arbitrary package tests or Role-local tests in S2.

## Current docs

Executable truth changes require:

- `docs/arch/demand-sys-architecture.md`;
- `docs/arch/daemon-service-architecture.md`;
- `docs/arch/task-sys-architecture.md` only for the exact Demand Public
  reference consumed by Task;
- no speculative final S5/S6 wording.
