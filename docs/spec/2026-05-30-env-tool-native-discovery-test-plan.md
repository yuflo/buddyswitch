# Env Tool Native Discovery Test Plan

Date: 2026-05-30
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`

## Goal

Prove BuddySwitch env tools are exposed as Codex-native action-level MCP tools from the existing runtime registry, and prove prose layers no longer act as stale tool schema mirrors.

The verified product path is:

```text
scripts/env/tools/<tool>/tool.py ActionDefinition
-> env.tool_runtime.registry discovery
-> native MCP tool projection
-> tools/list search-quality metadata
-> tools/call dispatch through runtime broker env.tool
-> AGENTS / skills / tips point to native tools first and context/CLI only as fallback
```

## Resource Lifecycle Guard

Follow `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.

- Projection, schema, prose, and stdio MCP tests must be pure subprocess/unit tests. They must not start daemon, app-server, browser, broker, fake Codex, or detached services.
- Launcher config tests may exercise shell code with fake `codex` binaries only. They must not start real Codex or runtime services.
- Do not run broad instance/browser/app-server suites until focused non-service tests pass.
- After any service-starting verification, run:

```bash
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex|chrome_devtools_cockpit_proxy.py" || true
```

- A leaked test-owned process is a verification failure even if assertions passed.

## Functional Requirements

| ID | Requirement |
| --- | --- |
| FR1 | Every supported env action is projected to exactly one native MCP tool spec. |
| FR2 | Native tool specs are generated from `ToolDefinition.actions` and `ActionDefinition`; no manual shipped-action list is introduced. |
| FR3 | Native tool names are stable, action-level, and reversible to `tool` + `action`. |
| FR4 | Native input schemas deep-equal the registry action input schemas. |
| FR5 | Native descriptions include tool/action meaning plus `use_when`, `do_not_use_when`, permission, mutation, visibility, durability, reads/writes, success effect, and failure guarantee. |
| FR6 | Projection does not import `env.tools.*._impl`, `env.domain`, `env.repos`, or runtime service internals. |
| FR7 | A temporary tool/action package added under `scripts/env/tools` is discovered by projection without editing projection code, MCP server code, AGENTS, skills, or a central action manifest. |
| FR8 | The stdio MCP server responds to `initialize`, `tools/list`, and `tools/call` using JSON-RPC line messages. |
| FR9 | `tools/list` returns the registry-projected native tools and no stale actions such as `task.get`. |
| FR10 | `tools/call` reverses the native tool name and dispatches through the existing broker client as `env.tool` with `{tool, action, args}`. |
| FR11 | `tools/call` rejects unknown native tool names before broker dispatch with an MCP tool error result. |
| FR12 | Broker errors are returned as MCP tool error content without hiding structured feedback. |
| FR13 | Product-mode Codex config registers one BuddySwitch env MCP server for the active instance. |
| FR14 | Env MCP registration uses the active instance id, active buddy, repo root, and runtime broker socket; it does not require per-action launcher changes. |
| FR15 | Skills and AGENTS no longer teach CLI as the primary env tool discovery path once native tools are available. |
| FR16 | Active prose examples that still mention `python3 scripts/env/client.py <tool> <action>` must match the runtime registry. |
| FR17 | Runtime tips for message availability do not imply unsupported payload fields or exact `message_id` lookup through `message.list`. |
| FR18 | The existing context discovery surfaces remain valid fallback/diagnostic surfaces and are not removed. |
| FR19 | Tests encode the A+ parallel-boundary rule: no handwritten native action manifest, no MCP action switch, no per-role tool pack, no checked-in generated action catalog. |
| FR20 | Focused and broader verification complete without resource leaks. |

## Test Groups

### T1: Native Projection Completeness And Schema Fidelity

File: `tests/test_env_native_mcp_projection.py`

Test behavior:

- Import `env.tool_runtime.native_mcp`.
- Build native tool specs from the current registry.
- Assert the projected tool count equals the sum of `len(definition.actions)` for every supported tool.
- For each action, assert:
  - native name is `tool__action`;
  - `decode_native_tool_name(name)` returns `(tool, action)`;
  - `inputSchema` equals `action.input_schema`;
  - description contains action title, action description, permission, mutation, visibility, durability, success effect, failure guarantee, and at least one `use_when` / `do_not_use_when` row.
- Assert no projected name equals `task__get`.

Focused command:

```bash
python3 -m pytest tests/test_env_native_mcp_projection.py::EnvNativeMcpProjectionTests::test_projection_covers_every_registry_action_with_matching_schema -q
```

### T2: Projection Boundary Guard

File: `tests/test_env_native_mcp_projection.py`

Test behavior:

- Run a subprocess that imports only `env.tool_runtime.native_mcp`, builds specs, and prints loaded modules.
- Assert no loaded module name contains `._impl`.
- Assert no loaded module starts with `env.domain.` or `env.repos.`.
- Assert no loaded module starts with `runtime_kernel.server`, `runtime_kernel.broker`, or `tools.launcher`.

Focused command:

```bash
python3 -m pytest tests/test_env_native_mcp_projection.py::EnvNativeMcpProjectionTests::test_projection_loads_no_private_tool_implementations_or_services -q
```

### T3: Dynamic Discovery Probe

File: `tests/test_env_native_mcp_projection.py`

Test behavior:

- In a temporary copied `env.tools` package path, create a synthetic package `probe/tool.py` with one valid `ToolDefinition` action named `inspect`.
- Put that temporary scripts root first on `sys.path`.
- Clear registry cache.
- Assert projection includes `probe__inspect`.
- Assert no native projection source file or MCP server source contains `SHIPPED_TOOLS`, `task__current`, `message__send`, or a dict/list literal that enumerates shipped action names.

Focused command:

```bash
python3 -m pytest tests/test_env_native_mcp_projection.py::EnvNativeMcpProjectionTests::test_projection_discovers_new_tool_package_without_central_manifest -q
```

### T4: Stdio MCP List And Call

File: `tests/test_env_native_mcp_server.py`

Test behavior:

- Use direct function tests for the MCP server message handler where possible.
- `initialize` returns protocol capabilities for tools.
- `tools/list` returns native tools from projection.
- `tools/call` with `message__list` and `{}` calls an injected dispatcher with `tool=message`, `action=list`, `args={}`.
- The result is returned as MCP content with JSON text.
- `tools/call` with `task__get` returns `isError: true` and does not dispatch.
- A dispatcher exception with structured feedback is returned as `isError: true` and includes the original error object in JSON text.

Focused command:

```bash
python3 -m pytest tests/test_env_native_mcp_server.py -q
```

### T5: Launcher Registration

File: `tests/test_buddyswitch_launcher.py`

Add focused tests using the existing fake `codex` command harness:

- Product instance bootstrap calls `codex mcp add buddyswitch-env -- python3 <repo>/tools/launcher/env_tool_mcp_server.py --instance-id <id> --buddy <buddy> --repo-root <repo> --broker-socket <socket>`.
- Config contains `[mcp_servers.buddyswitch-env]` and `default_tools_approval_mode = "approve"`.
- Re-running bootstrap repairs a stale `buddyswitch-env` server entry when args no longer match the active instance.
- Non-product/local mode does not register the env MCP server.

Focused commands:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "env_mcp or product_instance_start_registers_runtime_mcp" -q
```

### T6: Native-First Prose Governance

Files:

- `tests/test_runtime_skills.py`
- `tests/test_repo_consistency.py`
- `tests/test_message_available_handler.py`

Test behavior:

- Shared tool skills and buddy AGENTS mention native BuddySwitch env tools as the primary path.
- They may reference `context.get.tool_catalog`, `context.summarize.tool_affordances`, `turn_runtime.py status`, and CLI as fallback/diagnostic paths.
- Active prose command examples are parsed and every `<tool> <action>` pair is checked against the registry.
- The stale `task get` example fails until replaced with `task current`.
- The message available handler prompt no longer says a `message_id` can be read by `message.list`; it points to native `message__list` / `message__conversation` or fallback `message list --payload '{}'`.

Focused commands:

```bash
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_buddy_agents_do_not_present_authoritative_hardcoded_tool_lists -q
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_active_env_client_examples_match_runtime_registry -q
python3 -m pytest tests/test_message_available_handler.py -q
```

### T7: Relevant Broad Verification

Run after focused tests pass:

```bash
python3 -m pytest \
  tests/test_env_native_mcp_projection.py \
  tests/test_env_native_mcp_server.py \
  tests/test_black_box_tool_runtime.py \
  tests/test_env_tool_response_contract.py \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  tests/test_message_available_handler.py \
  -q
```

If launcher registration is changed, also run the focused launcher group before any broad launcher suite:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "mcp or codex_config or product_instance" -q
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex|chrome_devtools_cockpit_proxy.py" || true
```

Do not run broader service-starting suites until the focused launcher group returns the host to baseline.

## Review Checklist

- Native specs are derived, not hand maintained.
- MCP server contains only generic list/call routing, not per-action logic.
- Env broker remains the authorization and mutation boundary.
- Context discovery remains fallback/diagnostic.
- CLI remains human/debug fallback.
- Prose examples are registry-checked.
- No test starts persistent services without lifecycle proof.
