# S4 Context Source and Consumer Snapshot

> Snapshot source: `84734395f7b9088ad130ae8ace310cb55220865f`
> Source tree: `61c8d902547878b980b3eb0f18a403c5e239986f`
> Identity authority: exact commit/tree and explicit inventories below

## 1. Current owner shape

Context currently lives under the dynamic Tool root:

```text
src/buddyswitch/env/tools/context/
├── __init__.py
├── tool.py
└── _impl.py
```

`tool.py` owns the stable `context` Tool definition and its three read-only
actions: `get`, `summarize`, and `list_sources`. `_impl.py` owns the application
projection and already reads product state through:

- `track_public.context_snapshot`;
- `task_public.actor_task_projection`;
- `artifact_public.list_readable_summaries`;
- `communication_public.list_im_events_for_identity`.

It does not currently import any accepted component Private module. Context is
therefore ready to move without creating a new Public surface or changing an
accepted Public contract.

## 2. Projection inputs and observable outputs

The projection combines:

- current identity and Role facts;
- Track candidates, comments and updates;
- actor-visible Tasks and terminal Task facts;
- readable Artifact summaries;
- identity-visible Message cues;
- generated Tool catalog, action semantics and compact affordances;
- source-workspace and writable-surface facts;
- the Role action-policy preview.

It returns the current ToolResult success/rejection contract and remains
runless, read-only and non-durable. The Context lane changes ownership and
dependency placement, not those outputs.

## 3. Shared-host residue owned by this lane

`src/buddyswitch/env/tool_runtime/context.py` still contains three Context-only
surfaces:

- `RuntimeObjectAccess` and `ToolContext.objects`;
- `RegistryCatalogAccess` and `ToolContext.catalog`;
- `ToolContext.runtime_policy_preview(...)`.

Repository-wide use tracing found no consumer of `objects` or `catalog`, and
only the Context Tool calls `runtime_policy_preview`. Context Private can call
the generic `role_auth.role_action_summary(...)` contract directly from the
same host facts. These surfaces therefore leave `ToolContext` in the same
atomic cutover.

The following remain outside this lane and are S5 inputs:

- ActorPrivate access;
- Browser status;
- Actor directory and signal delivery;
- remaining generic identity, invocation, repo and domain facts;
- the global Tool package scanner itself.

## 4. Representations and consumers

The refresh covered:

- direct and relative imports of the old Tool package;
- literal source paths and patch targets;
- Tool ID/action names and Native MCP projections;
- package-directory discovery and explicit registration;
- application component ordering and duplicate checks;
- subprocesses that activate the application before dispatch;
- source/wheel package projection;
- current README and architecture path guidance;
- root-owned cross-component tests.

Direct old-path consumers are:

- `tests/integration/env_tool/test_context_binding.py` patch target;
- `tests/unit/architecture/test_communication_component_boundaries.py`;
- `tests/unit/architecture/test_demand_sys_boundaries.py`.

Complete-list component assertions that would otherwise require another
product exception live in the Communication, Track and Evidence architecture
tests. Context becomes the single owner of the “Context is last” assertion;
those component tests retain only their own selection/contribution claims.

## 5. Test ownership

No current Context behavior test is module-private. Context projection tests
seed and observe Track, Task, Artifact, Communication, Runtime Broker,
profiles, package activation or process surfaces. Under D-020 they remain in
root `tests/integration`, `tests/process` and `tests/unit/architecture`.

The final Context module intentionally has no `tests/` directory. Creating one
would falsely claim another component's Private fixture as Context-owned.

## 6. Protected assertion inventory

The pre-handoff review inspected assertion bodies rather than inferring
coverage from filenames or pass counts.

| Observable | Current assertion boundary | Broken path it detects |
|---|---|---|
| `context.get` success, filters and full catalog/schema | `test_context_get_metadata_and_source_workspace_semantics`, `test_context_get_applies_filters`, `test_context_get_exposes_full_input_schemas` | missing projection keys, filter drift, incomplete generated schema |
| `context.summarize` identity, decision, candidate and source facts | complete `test_context_binding.py` plus the four selected Host Decision cases | changed Public-read composition, visibility, policy or workspace projection |
| `context.list_sources` success and source descriptors | `test_context_list_sources_excludes_handoffs`, `test_context_list_sources_includes_source_workspace_descriptor`, router/black-box selected dispatch | missing action, changed descriptors or explicit-registration dispatch failure |
| payload/profile rejection | `test_context_rejects_unknown_payload_field`, `test_context_source_workspace_uses_profile_not_agents_text_and_profile_failure_is_explicit` | success-shaped invalid input or swallowed profile failure |
| runless/no-state contract | three selected `test_runless_contract.py` cases | run reservation/content writes or catalog/input-schema drift |
| package/application/native projection | affected architecture/package group | duplicate/missing registration, stale dynamic package, private eager load, wheel/activation drift |

Context has no transport, resource or durable-state owner. Runtime/process
error proof is therefore the existing generic registry/activation boundary;
no Context-specific cleanup or recovery contract is invented.

## 7. Preserved source/runtime identity

At refresh time:

```text
HEAD/origin:           84734395f7b9088ad130ae8ace310cb55220865f
tracked/index patch:   empty
untracked state:       empty
runtime source digest: abfc94c8fb824a0be42884687423316f92f2e8311037f4eeb11a8e57c163ae0c
distribution digest:   754c20fb6d2d0b9b6b445807765422db0415727d918363ca32710d9721372499
runtime.verify:        ok=true
```

Valid preservation evidence:

- direct Context behavior:

  ```text
  command:
    ./buddyswitch-test focused
      tests/integration/env_tool/test_context_binding.py
      tests/integration/env_tool/test_host_decision_surface.py::HostDecisionSurfaceProductModeTests::test_context_summarize_projects_runless_decision_surface
      tests/integration/env_tool/test_host_decision_surface.py::HostDecisionSurfaceProductModeTests::test_context_summarize_includes_compact_artifacts_comments_and_updates
      tests/integration/env_tool/test_host_decision_surface.py::HostDecisionSurfaceProductModeTests::test_context_summarize_track_filter_narrows_artifacts_comments_and_updates
      tests/integration/env_tool/test_host_decision_surface.py::HostDecisionSurfaceProductModeTests::test_pm_page_prototype_decision_surface_prefers_direct_private_actor_private_directory_without_phrase_rule
      tests/integration/env_tool/test_response_registry.py::EnvToolResponseRegistryTests::test_context_get_and_summarize_catalog_scope
      tests/integration/env_tool/test_response_registry.py::EnvToolResponseRegistryTests::test_context_projections_explain_demand_and_task_product_boundaries
      tests/integration/runtime/test_runless_contract.py::RunlessRuntimeContractTests::test_context_discovery_writes_no_run_reservation_or_run_content
      tests/integration/runtime/test_runless_contract.py::RunlessRuntimeContractTests::test_tool_registry_exposes_runless_tools_and_excludes_memory_run_and_binding
      tests/integration/runtime/test_runless_contract.py::RunlessRuntimeContractTests::test_context_get_exposes_full_input_schemas
      tests/process/cli/test_prepare_runtime_context.py
  run: ec4ae6b40a3d4fcaa8494049c609d35c
  result: 34 passed, 23 subtests; 0.54s pytest / 0.75s runner
  cleanup: run root absent; no attributable Context resource exists
  ```

- architecture/package/discovery affected group:

  ```text
  command:
    ./buddyswitch-test focused
      tests/unit/architecture/test_tool_runtime_contract.py
      tests/unit/architecture/test_package_contract.py
      tests/unit/architecture/test_communication_component_boundaries.py
      tests/unit/architecture/test_demand_sys_boundaries.py
      tests/process/cli/test_env_layer_boundaries.py
      tests/process/cli/test_env_tool_package_independence.py
      tests/process/cli/test_black_box_tool_runtime.py
      tests/process/cli/test_env_native_mcp_projection.py
      tests/process/package/test_distribution_install.py
      tests/process/package/test_runtime_activation.py
  run: 58658371b1244b428ea3cccfb24eb393
  result: 68 passed, 41 subtests; 24.48s pytest / 24.64s runner
  cleanup: run root absent; no attributable process/resource remains
  ```

Both commands ran through the activated non-editable runtime identified above
with no ad hoc dependency or environment mutation. They remain entry
preservation evidence only; the executor must prove identity equivalence or
rerun the narrowest missing group.

Run `3890727eaa5a41d7bc30da0fc8611f3e` selected wrong class node IDs and
collected zero tests. It is retained as non-evidence and its run root was
cleaned; no Goal Packet command depends on it.

During the second pre-handoff audit, an exploratory
`./buddyswitch-codex runtime verify` invocation returned `UNKNOWN_COMMAND`
before touching runtime state. The canonical installed entrypoint was then
used:

```text
BUDDYSWITCH_RUNTIME_DIR="$PWD/.buddyswitch-runtime" \
  .buddyswitch-runtime/venv/bin/python \
  -m buddyswitch.application.entrypoints.runtime_activation verify
result: kind=runtime.verify; ok=true; source/distribution identities above
```

The unsupported invocation is diagnostic non-evidence and is not taught to
the executor.
