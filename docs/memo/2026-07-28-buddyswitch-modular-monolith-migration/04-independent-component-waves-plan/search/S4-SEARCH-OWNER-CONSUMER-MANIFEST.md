# S4 Search Owner and Consumer Manifest

> Packet scope owner: `BS-MM-S4-SEARCH-20260730-01`
> Rule: an unclassified required write stops execution.

## 1. Final owner paths

```text
src/buddyswitch/modules/search/
  __init__.py
  module.py
  private/
    __init__.py
    adapters/
      __init__.py
      tool/
        __init__.py
        tool.py
        _impl.py
  tests/
    __init__.py
    integration/
      __init__.py
      test_search.py
      test_response_search.py
```

Search has no `public.py` in this lane because no current cross-component
consumer needs a Search-owned operation. Adding an empty or speculative Public
surface is forbidden.

## 2. Classified writes

### OWNER — create/move

- `src/buddyswitch/modules/search/**` exactly as listed above.

### OWNER — delete retired path

- `src/buddyswitch/env/tools/search/__init__.py`
- `src/buddyswitch/env/tools/search/tool.py`
- `src/buddyswitch/env/tools/search/_impl.py`

No forwarding package, import alias or discovery exception may remain.

### COMPOSITION

- `src/buddyswitch/application/composition.py`
  - import the Search assembly;
  - select Search exactly once after Demand and Task;
  - leave Daemon order and active-Task probe unchanged.

### HOST

- `src/buddyswitch/env/tool_runtime/context.py`
  - delete only the unused Search-shaped `BrowserAccess.request(...)`;
  - do not redesign `ToolContext`, Browser or Evidence in this lane.

### PROOF — owner-local moves/updates

- delete/move `tests/integration/env_tool/test_search.py`;
- delete/move `tests/integration/env_tool/test_response_search.py`;
- create `tests/unit/architecture/test_search_component_boundaries.py`.

### PROOF — root consumers

- `tests/integration/env_tool/_response_case.py`
  - remove the stale Search-private import and dead browser-client setup;
- `tests/integration/env_tool/test_response_artifact.py`
  - remove its unused Search-private import;
- `tests/integration/env_tool/test_response_registry.py`
  - remove its unused Search-private import while preserving cross-tool proof;
- `tests/unit/architecture/test_demand_sys_boundaries.py`
  - stop asserting that Demand's local proof owns the complete component list;
- `tests/unit/architecture/test_task_sys_boundaries.py`
  - assert Task presence/uniqueness and exact Daemon order without owning the
    complete component list;
- `tests/unit/architecture/test_tool_runtime_contract.py`
  - derive explicit component Tool registrations from application composition
    rather than adding a Search exception;
- `tests/unit/architecture/test_package_contract.py`
  - update current-guidance proof for component-owned versus not-yet-migrated
    Tool paths.

### CURRENT DOC

- `README.md`;
- `docs/arch/daemon-service-architecture.md`;
- `docs/arch/demand-sys-architecture.md`;
- `docs/arch/task-sys-architecture.md`;
- create `docs/arch/search-capability-architecture.md`.

Demand/Task docs must describe their local owners and delegate the current
complete module list to application composition. They must not be repeatedly
edited for every later component.

## 3. Proof-only consumers

These files are exercised but are not authorized writes unless the hub issues
new scope:

- `tests/integration/env_tool/test_layer_end_to_end.py`;
- `tests/integration/env_tool/test_response_registry.py` beyond the classified
  import cleanup;
- `tests/integration/env_tool/test_host_decision_surface.py`;
- `tests/integration/env_tool/test_context_binding.py`;
- `tests/integration/runtime/test_runless_contract.py`;
- `tests/unit/env_tool/test_semantic_contract.py`;
- `tests/unit/env_tool/test_active_task_gate.py`;
- `tests/process/cli/test_search_cli.py`;
- `tests/process/cli/test_env_tool_package_independence.py`;
- `tests/process/cli/test_env_tool_router.py`;
- `tests/process/cli/test_black_box_tool_runtime.py`;
- `tests/process/cli/test_env_native_mcp_projection.py`;
- `tests/process/cli/test_buddy_env_profiles.py`;
- `tests/process/package/test_distribution_install.py`.

If one needs a source edit, stop and return the exact failure and proposed
ownership. Do not expand scope in place.

## 4. Representation-complete trace

| Representation | Disposition |
|---|---|
| direct Search private imports | move owner tests; remove three unused root imports and shared fixture import |
| literal old source path | update moved Search source-absence test |
| Tool ID/action tables | generic tables remain root proof; composition-derived explicit ownership |
| generated module/path names | process package/router tests remain proof-only and must pass |
| directory discovery | old Search package deleted atomically with explicit contribution |
| activation-dependent subprocess | reprovision after source mutation before all candidate tests |
| wheel/test projection | co-located tests excluded by existing package contract; distribution test proves it |
| current guidance | root README and current architecture docs updated |
| runtime state/data | inapplicable; Search is stateless |

## 5. Forbidden writes

- any Track, Artifact, Communication, Evidence or Context implementation;
- `ModuleAssembly`, application build or registry host contract;
- Browser lifecycle/manager/cockpit;
- profile/manifest schema or role configuration;
- package/build declaration;
- migration master truth or packet documents;
- compatibility, fallback, generic plugin/DI/bus/route/lifecycle framework;
- Git history or remote state.
