# S3 Owner and Consumer Manifest

> Historical initial manifest. Incomplete for execution because it omitted
> indirect generated/discovery consumers. Current scope:
> `S3-R1-CONSUMER-AUDIT.md`.

## 1. Final physical owner

```text
src/buddyswitch/modules/task/
  __init__.py
  module.py
  public/
    __init__.py
    contracts.py
    operations.py
  private/
    domain/task_sys.py
    read_model.py
    adapters/
      tool/{__init__.py,tool.py,_impl.py}
      goal/{__init__.py,handler.py,client.py,protocol.py}
      cli.py
      web.py
      cleanup.py
  tests/
    unit/**
    integration/**
```

The exact private subdivision may omit empty `__init__.py` files only when
Python packaging does not require them. It may not split Task or native Goal
convergence into a second component.

## 2. Atomic owner movement

| Current live path | Final disposition |
|---|---|
| `src/buddyswitch/env/domain/task_sys.py` | move to Task private domain; delete old path |
| `src/buddyswitch/env/domain/task_read.py` | move to Task private read model; delete old path |
| `src/buddyswitch/env/tools/task_sys/**` | move to Task private Tool adapter; delete old package |
| `src/buddyswitch/launcher/task_goal_handler.py` | move to Task private Goal adapter; delete old path |
| `src/buddyswitch/env/tool_runtime/task_goal_runtime_client.py` | move beside Task Goal adapter; delete old path |
| `src/buddyswitch/env/tool_runtime/task_goal_runtime_protocol.py` | move beside Task Goal adapter; delete old path |
| `tests/integration/task_sys/**` | move to Task local integration tests |
| `tests/integration/goal_mode/test_task_goal_reconciliation.py` | move to Task local integration tests |

No forwarding import, alias, fallback, copied implementation, old package, or
dual Tool registration may remain.

The `tests/integration/task_sys/**` move sources are exactly:

```text
tests/integration/task_sys/test_actor_create.py
tests/integration/task_sys/test_checkpoint.py
tests/integration/task_sys/test_goal_binding.py
tests/integration/task_sys/test_substrate.py
```

## 3. Exact Public contracts earned by current consumers

Task Public exposes only:

- `DemandSelectionResolver`: the Task-owned input-port shape needed by
  `task_sys.create`;
- `actor_task_projection(actor_profile)`: current Context Tool read;
- `has_active_task(actor_profile)`: injected active-Task gate probe;
- `demand_attention(actor_target)`: exact active Task id plus terminal Task ids
  needed by Demand orchestration;
- `require_completed_task_for_demand(...)`: exact completed evidence check and
  its public failure type.

It does not expose repositories, file paths, locks, raw records, daemon
context, App Server DTOs, ToolContext, Web DTOs, or mutation methods.

## 4. Current consumers and final edge

| Consumer | Current coupling | Final edge |
|---|---|---|
| Task Tool create | imports Demand Public directly | Task-owned resolver port injected by application composition from Demand module Public capability |
| Demand orchestration | imports private Task domain | Task Public `demand_attention` |
| Demand completion adapter | reads `context.rules.task_sys` | Task Public completed-evidence operation |
| Tool active-Task gate | registry imports private Task domain | application-injected Task Public probe |
| Context Tool tasks section | `ToolContext.rules.task_sys` | direct Task Public projection |
| Task Tool Goal reconcile | broad `ToolContext.task_goal_runtime` | Task-private Goal client built from generic `instance_json` fact |
| public CLI | central `task` switch plus private read import | Task private CLI registration |
| Actor Console | central Task read import and branch | Task `task_sys` Actor Console section contribution |
| instance daemon | central Task import/insertion/command list | Task handler registration in exact application order with its command factory |
| cleanup | Task state unattributed | Task cleanup contribution; host validates/deletes paths |

Cross-component source dependencies after cutover are one-way:

```text
Demand private -> Task Public
Task source -> Task-owned resolver contract
application composition -> Demand module + Task module + concrete wiring
```

The reverse runtime call used during Task create is a resolver implementation
supplied at composition; Task source does not import Demand.

## 5. Host contract changes

### Foundation/application

- add exact `actor_console_sections` to `ModuleAssembly`;
- flatten and validate unique section names in `ApplicationAssembly`;
- select `(DEMAND, TASK)` once;
- explicitly declare component daemon order
  `demand_triage -> task_goal -> demand_orchestration`;
- inject Demand resolver into Task construction;
- inject Task active probe into Tool runtime activation.

### Daemon

- extend `DaemonHandlerRegistration` with one optional typed application
  command factory;
- remove central Task import, central Task insertion, and central Task command
  list;
- instantiate product handlers only from already ordered registrations.

### Web

- add one narrow `ActorConsoleSectionRegistration`;
- Web accepts and composes sections into the existing Actor Console DTO;
- do not add route discovery, a general Web plugin, or product routing DSL.

### Tool host

- accept a configured active-Task probe and fail closed when a required probe
  is absent;
- remove Task private imports and Task objects from `ToolContext`;
- keep current ActionDefinition task requirement and response semantics.

## 6. Test disposition

Move Task-owned domain and Goal adapter tests local. Keep root tests only when
they prove cross-component, host, process, package, lifecycle, or external
consumer behavior. `tests/runner.py` and `pyproject.toml` require no behavior
change: their accepted generic patterns already discover module-local test
tiers and exclude `buddyswitch.*.tests*` from the wheel.

`tests/integration/goal_mode/test_demand_orchestration.py` remains a root
cross-component proof in S3. A later Demand-local move is not required for the
Task acceptance sentence and must not enlarge this packet.

Create `tests/support/task_fixtures.py` as the sole root-test adapter allowed
to import Task private mutation/state helpers. It contains fixture calls, not
copied Task rules. Task-local tests may import Task private directly. Root
cross-component tests use Task Public for observations and the test fixture
adapter only for state setup. No other root test imports Task private.

Exact root test/support consumers allowed for import/path/proof updates:

```text
tests/integration/daemon/test_mailbox.py
tests/integration/env_tool/_response_case.py
tests/integration/env_tool/test_context_binding.py
tests/integration/env_tool/test_host_decision_surface.py
tests/integration/env_tool/test_payload_contract.py
tests/integration/env_tool/test_response_artifact.py
tests/integration/env_tool/test_response_demand.py
tests/integration/env_tool/test_response_registry.py
tests/integration/env_tool/test_response_search.py
tests/integration/env_tool/test_response_task.py
tests/integration/env_tool/test_store.py
tests/integration/env_tool/test_track_comment.py
tests/integration/goal_mode/test_demand_orchestration.py
tests/integration/im/test_external_query.py
tests/integration/im/test_identity_product_ownership.py
tests/integration/runtime/test_runless_contract.py
tests/integration/runtime/test_tool_feedback.py
tests/integration/track/test_comment_added_handler.py
tests/integration/web/test_management_product_api.py
tests/process/cli/test_black_box_tool_runtime.py
tests/process/cli/test_env_layer_boundaries.py
tests/process/launcher/test_public_cli.py
tests/process/package/test_distribution_install.py
tests/process/package/test_runtime_activation.py
tests/support/runtime.py
tests/system/browser_lifecycle/test_lazy_release.py
tests/system/goal_mode/test_product_flow.py
tests/system/instance_lifecycle/test_interaction.py
tests/unit/actor/test_session.py
tests/unit/architecture/test_demand_sys_boundaries.py
tests/unit/architecture/test_external_control.py
tests/unit/architecture/test_package_contract.py
tests/unit/architecture/test_repo_contracts.py
tests/unit/architecture/test_task_management_skill.py
tests/unit/architecture/test_task_sys_boundaries.py
tests/unit/architecture/test_tool_runtime_contract.py
tests/unit/daemon/test_communication_boundary.py
tests/unit/daemon/test_decoupling.py
tests/unit/daemon/test_instance_entrypoint.py
tests/unit/env_tool/test_active_task_gate.py
```

The four exact `tests/integration/task_sys/*.py` files listed above and
`tests/integration/goal_mode/test_task_goal_reconciliation.py` are move
sources, not additional root consumers after cutover.

## 7. Current documentation

The implementation updates exactly:

- `docs/arch/task-sys-architecture.md`;
- `docs/arch/demand-sys-architecture.md`;
- `docs/arch/daemon-service-architecture.md`;
- `docs/arch/web-interface-call-architecture.md`.

Historical memos remain history. They are not rewritten as current policy.
