# S5 C1 ToolHost Consumer Manifest

## Manifest rule

The cutover is atomic across every live representation, not just Python import
statements. The refresh found 93 source/test/guidance paths containing a direct
ToolHost import, dynamic import, literal old path or retired package assertion.
The executor must refresh the set at its starting identity and classify any
delta before changing source.

## Production consumers

### Composition and host entrypoints

- `src/buddyswitch/application/build.py`;
- `src/buddyswitch/application/entrypoints/env_client.py`;
- `src/buddyswitch/application/entrypoints/env_mcp.py`;
- `src/buddyswitch/foundation/composition/__init__.py`;
- `src/buddyswitch/runtime_kernel/{client,coordinator,dispatcher}.py`;
- `src/buddyswitch/runtime_support/turn_runtime.py`.

The entrypoints must call the final Foundation client/MCP host directly.
Application activation configures registrations, active-Task probe and Role
authorizer exactly once.

### Component assembly and Tool adapters

Every accepted module assembly imports `ToolRegistration` from the final
Foundation contract. Every Tool adapter imports Tool definitions, context and
results from Foundation:

- Demand;
- Task;
- Search;
- Track;
- Artifact;
- Evidence;
- Communication;
- Context.

The two permitted mechanical adapter changes are:

- Artifact consumes `context.actor_private_root` rather than a repository bag;
- Evidence consumes `context.now()` rather than a runtime-files repository bag.

No component semantic or Public operation changes.

### Daemon-client consumers

These current consumers move directly to `foundation.daemon.client`:

- central/instance Daemon and mailbox hosts;
- Browser lifecycle transport;
- Task Goal client;
- Communication Actor delivery and Web registration.

They preserve request/response and failure behavior. C1 relocates only the
client transport; Daemon host convergence remains C5.

### Role-policy consumers

- ToolHost registry/authorization feedback receives an injected authorizer;
- Context projection imports the current policy from `runtime_support`;
- Role policy/Skill tests import its current owner.

No Foundation module may import `runtime_support.role_auth` directly except
application composition passing the capability value; Foundation must not name
Role or product permission tables.

## Test consumer classes

### Direct unit/integration behavior

- `tests/unit/env_tool/**`;
- `tests/integration/env_tool/**`;
- affected runtime, IM, Daemon and module integration tests.

These move imports and preserve semantic assertions. Tests that only keep
`ActorPrivateAccess`, `BrowserAccess`, `DomainAccess` or `RepoAccess` alive are
rewritten around the narrow final context or removed if no current consumer
claim remains.

### Architecture and package structure

- `tests/unit/architecture/test_tool_runtime_contract.py` becomes the generic
  explicit-catalog/narrow-context/absence owner;
- component boundary tests stop individually consulting
  `discover_tool_ids()` and instead prove their own explicit contribution plus
  the generic composition invariant;
- package/repository contracts name the final Foundation paths;
- old roots may appear only in scoped negative absence assertions.

Do not replace eight discovery exceptions with eight Foundation exceptions.
The invariant is one composition-derived catalog completeness proof.

### Process and generated representations

The following representation classes are mandatory:

- direct and parent imports;
- dynamic `importlib.import_module` strings;
- literal source paths;
- package/discovery directory assertions;
- embedded subprocess scripts;
- native MCP projection and process catalog enumeration;
- installed package/runtime projection;
- current README/guidance.

Known non-obvious consumers include:

- `tests/unit/env_tool/test_native_mcp_server.py` dynamic MCP-server import;
- `tests/process/cli/test_env_native_mcp_projection.py` dynamic package probe
  and literal source inspection;
- `tests/process/cli/test_env_tool_package_independence.py` temporary discovered
  Tool package behavior, which must become explicit-registration behavior;
- `tests/process/cli/test_black_box_tool_runtime.py` package add/delete probes;
- `tests/process/cli/test_env_tool_router.py` embedded subprocess imports;
- `tests/unit/architecture/test_demand_sys_boundaries.py` host path tuples;
- `README.md` current ToolHost owner descriptions.

`tests/process/launcher/test_bootstrap_config.py` contains an arbitrary existing
configuration fixture ending in `runtime/env_tool_mcp_server.py`; it is not
automatically an active source-owner claim. The executor must inspect its
semantic purpose before changing it.

## Final allowed old-term policy

After C1, live source/guidance contains no old Tool runtime/package owner.
Historical memos may retain it. Current tests may name the old path only in a
bounded negative assertion proving absence or forbidden import.

## Consumer completion proof

Acceptance requires a regenerated representation-complete manifest showing:

1. every production import points to the final owner;
2. no dynamic Tool package discovery/load remains;
3. every current Tool appears exactly once in application composition;
4. no old path is executable, importable or taught as current;
5. native MCP, admin CLI, Broker dispatch and direct test adapters observe the
   same catalog/actions/results;
6. installed runtime identity matches candidate source.
