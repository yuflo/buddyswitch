# S4 Context Source and Consumer Snapshot

> Snapshot source: `84734395f7b9088ad130ae8ace310cb55220865f`
> Source tree: `61c8d902547878b980b3eb0f18a403c5e239986f`
> Source/host manifest: `7e9fbf6dd410bac484e070c0aebcf33096b8904d60036485ccbffcbf5e8f1b6f`
> Proof-input manifest: `0c91870963a88a45094cff12e8428ae736e2d017f1e71632b6abf75d3d1b3808`

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

## 6. Preserved source/runtime identity

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

- direct Context behavior: run `f905a017ab6f455b9efd04dda9c2bcb3`,
  34 passed and 23 subtests;
- architecture/package/discovery affected group: run
  `0b6cafba442b403ea441df38b6393241`, 68 passed and 41 subtests.

Run `3890727eaa5a41d7bc30da0fc8611f3e` selected wrong class node IDs and
collected zero tests. It is retained as non-evidence and its run root was
cleaned; no Goal Packet command depends on it.
