# S4 Context Owner and Consumer Manifest

> Packet: `BS-MM-S4-CONTEXT-R1-20260804-01`
> Manifest state: `FROZEN FOR READY`

## 1. Final owner

The final production owner is exactly:

```text
src/buddyswitch/modules/context/
├── __init__.py
├── module.py
└── private/
    ├── __init__.py
    └── adapters/
        ├── __init__.py
        └── tool/
            ├── __init__.py
            ├── tool.py
            └── _impl.py
```

There is no Context `public/`, state, Skill, CLI, Daemon, cleanup, Web,
inbound or module-local test surface.

## 2. Classified production writes

| Class | Paths | Required result |
|---|---|---|
| OWNER | `src/buddyswitch/modules/context/**` | one passive `context` Tool module |
| COMPOSITION | `src/buddyswitch/application/composition.py` | select Context once and last |
| HOST | `src/buddyswitch/env/tool_runtime/context.py` | remove Context-only accessors/method; retain generic facts |
| RETIRED | `src/buddyswitch/env/tools/context/**` | entire old package absent |
| CURRENT DOC | `README.md`, `docs/arch/context-capability-architecture.md` | teach only the current owner/boundary |

No other production path is classified.

## 3. Classified proof writes

| Path | Why a write may be required |
|---|---|
| `tests/unit/architecture/test_context_component_boundaries.py` | new owner/composition/dependency/residue proof |
| `tests/integration/env_tool/test_context_binding.py` | update old patch path and prove host residue absent |
| `tests/unit/architecture/test_communication_component_boundaries.py` | replace old Context path; localize component-order claim |
| `tests/unit/architecture/test_demand_sys_boundaries.py` | replace old Context path |
| `tests/unit/architecture/test_track_component_boundaries.py` | localize complete component-order claim |
| `tests/unit/architecture/test_evidence_component_boundaries.py` | localize complete component-order claim |
| `tests/unit/architecture/test_package_contract.py` | current README/Context architecture owner paths |

Equivalent proof-only repair inside these files is allowed when it preserves
the frozen claim. A required write to any other test path is unclassified and
stops execution unless it is purely mechanical current-path projection and
the executor can prove unchanged semantic breadth under D-051. Any doubt
returns to the hub.

## 4. Read/verify consumers, not pre-authorized writes

- `tests/unit/architecture/test_tool_runtime_contract.py`;
- `tests/unit/architecture/test_repo_contracts.py`;
- `tests/process/cli/test_env_layer_boundaries.py`;
- `tests/process/cli/test_env_tool_package_independence.py`;
- `tests/process/cli/test_black_box_tool_runtime.py`;
- `tests/process/cli/test_env_native_mcp_projection.py`;
- `tests/process/cli/test_env_tool_router.py`;
- `tests/process/package/test_distribution_install.py`;
- `tests/process/package/test_runtime_activation.py`;
- Context-focused root Integration and Process tests named in the snapshot.

These derive Tool/package/application truth from current owners and should not
need a Context exception.

## 5. Allowed dependency edges

Context Private may depend on:

- Track, Task, Artifact and Communication Public;
- `env.tool_runtime` definitions, results, registry and Role authorization;
- runtime profile facts;
- Python standard library;
- its own private adapter.

It may not import another component Private, a product repository/domain,
Browser lifecycle, Daemon/Web/CLI host, Runtime Kernel dispatcher, or migration
code.

Other product/foundation packages may import `modules.context.module` only
from application composition. No consumer may import Context Private.

## 6. Protected consumer contract

- Tool ID `context` and actions `get`, `summarize`, `list_sources`;
- action schemas, ToolResult semantics, Native MCP names and Role authority;
- filters and rejection mappings;
- all current projection keys and identity/visibility rules;
- source-workspace and writable-surface semantics;
- runless/no-state/no-resource behavior;
- accepted component Public results;
- existing Daemon order and every non-Context component contribution;
- installed source/wheel correspondence.

## 7. Forbidden scope

- Context Public/facade or compatibility imports;
- movement of root cross-component tests into the module;
- change to `ModuleAssembly`, registry discovery, Native MCP, ToolResult,
  component Public contracts or product schemas;
- S5 cleanup beyond the three Context-only `ToolContext` surfaces;
- plugin, DI container, event bus, service locator or dynamic component loader;
- migration master truth, commit, push, rebase or branch operations.
