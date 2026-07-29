# S3 R1 Complete Consumer and Candidate Audit

> Status: `REVIEWED`
> Candidate base: dirty S3 product candidate on
> `1c99816c57196e47ddbff38bdd0d143bf5084e24`
> Audit mode: source-read-only; no public test

## 1. Audit method

R1 classifies every affected representation, not only imports:

| Representation | Search/proof |
|---|---|
| direct dependency | AST imports and exact module prefixes |
| literal path/name | retired/current dotted modules and source/test paths |
| data-driven identifier | `task_sys`, shipped/expected/discovered Tool sets |
| generated reference | formatted module names and package-directory paths |
| activation-dependent consumer | subprocess scripts with and without `activate_application()` |
| package projection | runner discovery, wheel exclusion and installed runtime paths |
| mutation/proof adapter | root fixtures, cleanup attribution and source assertions |

This is the D-049 representation-complete consumer audit for S3.

## 2. Required R1 edits not authorized by the old manifest

| File | Why it must change | Required owner-correct result |
|---|---|---|
| `tests/process/cli/test_env_tool_package_independence.py` | hard-coded `task_sys` directory and discovered registry expectation | derive dynamic packages from the actual generic package root; no Demand/Task special case |
| `tests/process/cli/test_env_tool_router.py` | generated old `_impl` path and private-module scan omit Task component Tool | derive the expected selected private implementation from the selected registration/module; scan component Tool roots generically |

These are the only newly discovered executable consumers that must change.

## 3. Existing candidate files requiring proof-quality correction

| File | Correction |
|---|---|
| `tests/unit/architecture/test_tool_runtime_contract.py` | derive explicit component Tool IDs from application composition rather than maintaining a growing migrated-ID subtraction list |
| `tests/support/task_fixtures.py` | reference Task-owned lifecycle constants; do not copy status values or business rules |
| `tests/integration/web/test_management_product_api.py` | remove mechanically meaningless `task_fixtures.*` source-string assertions and prove the actual Web-host/private-boundary condition |
| `tests/integration/env_tool/test_cleanup.py` | retain and run the already-added Task cleanup attribution and malformed-record proof; file is now explicitly classified |

These files are already inside the preserved candidate. The correction does
not authorize a new framework or new product behavior.

## 4. Proof-only neighboring consumers

The following files were inspected and remain unchanged unless a direct
focused failure identifies an in-scope implementation defect:

```text
tests/process/cli/test_env_native_mcp_projection.py
tests/process/cli/test_env_client_payload.py
tests/process/cli/test_black_box_tool_runtime.py
tests/integration/env_tool/test_run.py
tests/unit/env_tool/test_schema_contract.py
tests/unit/env_tool/test_semantic_contract.py
tests/unit/architecture/test_repo_contracts.py
tests/integration/runtime/test_runless_contract.py
tests/process/launcher/test_public_cli.py
tests/process/package/test_distribution_install.py
tests/process/package/test_runtime_activation.py
tests/system/goal_mode/test_product_flow.py
tests/system/instance_lifecycle/test_interaction.py
```

Reasons:

- root test processes load `tests/conftest.py`, which activates the selected
  application and therefore sees explicit Demand/Task registrations;
- installed application entrypoints call `activate_application()` before
  projecting or dispatching Tools;
- the native-MCP private-load subprocess deliberately does not activate the
  application and correctly proves that generic package discovery loads no
  private component implementation;
- probe-package tests exercise the remaining dynamic package mechanism and do
  not promise that Task is dynamic;
- package/runner patterns already discover module-local tests and exclude
  them from the wheel.

Any required mutation to a proof-only file is a new finding and stop unless it
is first returned to the hub for classification.

## 5. Preserved dirty candidate scope

The executor may continue editing the exact already-dirty product candidate:

```text
src/buddyswitch/application/{build.py,composition.py}
src/buddyswitch/env/domain/{task_read.py,task_sys.py}                  [delete]
src/buddyswitch/env/tool_runtime/{context.py,registry.py}
src/buddyswitch/env/tool_runtime/task_goal_runtime_{client,protocol}.py [delete]
src/buddyswitch/env/tools/context/_impl.py
src/buddyswitch/env/tools/task_sys/**                                 [delete]
src/buddyswitch/foundation/composition/__init__.py
src/buddyswitch/launcher/{cli.py,daemon_contracts.py,instance_daemon.py,web_management.py}
src/buddyswitch/launcher/task_goal_handler.py                         [delete]
src/buddyswitch/launcher/web_contracts.py                             [create]
src/buddyswitch/modules/demand/private/adapters/daemon/demand_orchestration_handler.py
src/buddyswitch/modules/demand/private/adapters/tool/_impl.py
src/buddyswitch/modules/task/**                                       [create]
tests/support/runtime.py
tests/support/task_fixtures.py                                       [create]
tests/integration/env_tool/**
tests/integration/goal_mode/test_demand_orchestration.py
tests/integration/goal_mode/test_task_goal_reconciliation.py          [delete]
tests/integration/im/{test_external_query.py,test_identity_product_ownership.py}
tests/integration/runtime/{test_runless_contract.py,test_tool_feedback.py}
tests/integration/task_sys/**                                         [delete]
tests/integration/track/test_comment_added_handler.py
tests/integration/web/test_management_product_api.py
tests/process/cli/test_env_layer_boundaries.py
tests/system/browser_lifecycle/test_lazy_release.py
tests/unit/actor/test_session.py
tests/unit/architecture/{test_demand_sys_boundaries.py,test_external_control.py,test_package_contract.py,test_repo_contracts.py,test_task_management_skill.py,test_task_sys_boundaries.py,test_tool_runtime_contract.py}
tests/unit/daemon/{test_communication_boundary.py,test_decoupling.py,test_instance_entrypoint.py}
tests/unit/env_tool/test_active_task_gate.py
```

The `tests/integration/env_tool/**` allowance in this block is limited to the
files already dirty at the R1 source identity:

```text
_response_case.py
test_cleanup.py
test_context_binding.py
test_host_decision_surface.py
test_payload_contract.py
test_response_artifact.py
test_response_demand.py
test_response_registry.py
test_response_search.py
test_response_task.py
test_store.py
test_track_comment.py
```

The only additional executable write paths are the two files in section 2.
The four current architecture documents remain required C5 writes:

```text
docs/arch/task-sys-architecture.md
docs/arch/demand-sys-architecture.md
docs/arch/daemon-service-architecture.md
docs/arch/web-interface-call-architecture.md
```

No other executable, test, current-doc, build or package path is authorized.

## 6. Static candidate evidence

At audit time:

```text
changed/untracked Python parsed: 76
syntax failures: 0
Task-private imports outside Task root:
  tests/support/task_fixtures.py only
Task source imports of Demand: 0
Demand private imports of Task private: 0
generic host imports of Task private/retired Task owner: 0
retired exact source paths outside negative absence guards/current stale docs: 0
git diff --check: PASS
```

The old Task domain is byte-identical at its new physical owner. The read
model, Goal protocol/handler and moved local tests differ only by owner-path
imports, except for the explicitly designed Goal client object and injected
Task Tool dependencies.

## 7. Candidate architecture determination

No redesign is required. R1 keeps D-045–D-048 exactly:

```text
Task private owner
  -> Task Public
    -> Demand consumers / generic Context consumer

Task-owned DemandSelectionResolver port
  <- application composition supplies Demand Public resolver

selected modules
  -> typed Tool / CLI / Daemon / Actor Console / cleanup contributions
    -> generic hosts
```

The open work is scope closure, proof correction, current documentation and
runtime verification—not another architecture.
