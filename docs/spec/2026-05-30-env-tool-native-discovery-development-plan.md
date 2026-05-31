# Env Tool Native Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` while implementing behavior changes. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement A+: expose BuddySwitch env actions as Codex-native action-level MCP tools from the existing registry, and govern prose layers so native tools are the primary discovery path.

**Architecture:** Keep `scripts/env/tools/<tool>/tool.py` as the owning source for action contracts. Add a pure projection module that converts `ActionDefinition` into MCP tool specs, add a generic stdio MCP server that maps native names back to `env.tool` broker calls, register that server in product-mode Codex config, and update skills/AGENTS/tips/tests so prose cannot drift into a second schema source.

**Tech Stack:** Python stdlib, existing `env.tool_runtime.registry`, existing runtime broker client, JSON-RPC line protocol for MCP stdio, pytest/unittest, existing launcher fake-Codex harness.

---

## Current Code Audit

- `scripts/env/tool_runtime/definition.py` already validates every action input schema, output schema, description, permission, mutation, durability, visibility, reads/writes, `use_when`, and `do_not_use_when`.
- `scripts/env/tool_runtime/registry.py` already discovers tools via `pkgutil.iter_modules(env.tools.__path__)` and loads `env.tools.<tool>.tool`.
- `registry.env_tools_description()`, `registry.operation_semantics()`, and `registry.compact_tool_affordances()` already project contract metadata without importing `_impl.py`.
- `scripts/env/client.py` dispatches through the runtime broker but exposes only generic `--payload JSON_OBJECT` CLI help.
- `tools/launcher/codex_config.py` patches MCP approval mode for existing MCP server sections.
- `tools/launcher/browser_cockpit.sh` shows the current pattern for idempotent MCP registration through `codex mcp add/remove`.
- There is no BuddySwitch env MCP server today.
- Current prose drift exists: AGENTS examples still include `task get`, while registry only supports `task.current`, `task.propose`, and `task.confirm`.
- Current message available tip gives a `message_id` while telling Codex to use `message.list`, whose schema does not accept `message_id`.

## File Structure

- Create `scripts/env/tool_runtime/native_mcp.py`
  - Pure conversion from registry definitions to MCP tool specs.
  - Native name encode/decode helpers.
  - No dispatch, no broker, no `_impl.py` import.
- Create `tools/launcher/env_tool_mcp_server.py`
  - Stdio JSON-RPC server for `initialize`, `tools/list`, `tools/call`.
  - Generic native name decode and broker dispatch.
  - Error conversion to MCP tool result.
- Modify `tools/launcher/env.sh`
  - Add env MCP defaults and registration helper.
  - Register/repair the env MCP server only in product-mode instance context after broker socket is known.
- Modify `tools/launcher/codex_config.py` only if approval patching needs new tests; otherwise reuse existing MCP section approval behavior.
- Modify `tools/launcher/message_available_handler.py`
  - Replace misleading `message_id`/`message.list` instruction with native-first inbox/conversation guidance.
- Modify `buddyswitch/skills/shared/*/SKILL.md`
  - Replace CLI-first wording with native-first wording plus context/CLI fallback.
- Modify `tools/launcher/assets/buddies/{pm,dev,design,market,test}/AGENTS.md`
  - Remove stale `task get`; shrink examples to registry-valid fallback examples.
  - Mention native BuddySwitch env tools as primary when available.
- Create/modify tests:
  - `tests/test_env_native_mcp_projection.py`
  - `tests/test_env_native_mcp_server.py`
  - `tests/test_buddyswitch_launcher.py`
  - `tests/test_runtime_skills.py`
  - `tests/test_repo_consistency.py`
  - `tests/test_message_available_handler.py`

## Task 1: Native Projection

- [ ] Create failing projection tests in `tests/test_env_native_mcp_projection.py`:

```python
def test_projection_covers_every_registry_action_with_matching_schema(self) -> None:
    specs = native_mcp.list_native_tool_specs()
    by_name = {spec["name"]: spec for spec in specs}
    for tool in sorted(registry.supported_tools()):
        definition = registry.get_definition(tool)
        for action in definition.actions:
            name = f"{tool}__{action.name}"
            self.assertIn(name, by_name)
            self.assertEqual(native_mcp.decode_native_tool_name(name), (tool, action.name))
            self.assertEqual(by_name[name]["inputSchema"], action.input_schema)
            description = by_name[name]["description"]
            self.assertIn(action.description, description)
            self.assertIn(action.required_permission, description)
            self.assertIn(action.mutates, description)
            self.assertIn(action.visibility, description)
            self.assertIn(action.durability, description)
            self.assertIn(action.success_effect, description)
            self.assertIn(action.failure_state_guarantee, description)
```

- [ ] Run:

```bash
python3 -m pytest tests/test_env_native_mcp_projection.py::EnvNativeMcpProjectionTests::test_projection_covers_every_registry_action_with_matching_schema -q
```

Expected: fail because `env.tool_runtime.native_mcp` does not exist.

- [ ] Implement `scripts/env/tool_runtime/native_mcp.py` with:
  - `NATIVE_TOOL_SEPARATOR = "__"`;
  - `encode_native_tool_name(tool, action)`;
  - `decode_native_tool_name(name)`;
  - `native_tool_spec(tool, definition, action)`;
  - `list_native_tool_specs(exclude_tools=None)`.

- [ ] Rerun the focused projection test until green.

## Task 2: Projection Boundary And Dynamic Discovery

- [ ] Add failing tests for no private imports and temporary probe action discovery.
- [ ] Run:

```bash
python3 -m pytest tests/test_env_native_mcp_projection.py -q
```

Expected: boundary/probe tests fail until projection exposes the needed helpers and stays generic.

- [ ] Adjust projection to rely only on `registry.supported_tools()` and `registry.get_definition()`.
- [ ] Ensure tests inspect source text so no shipped action table is introduced.
- [ ] Rerun projection tests until green.

## Task 3: Generic Stdio MCP Server

- [ ] Create failing tests in `tests/test_env_native_mcp_server.py` for `initialize`, `tools/list`, `tools/call`, unknown tool, and broker error mapping.
- [ ] Run:

```bash
python3 -m pytest tests/test_env_native_mcp_server.py -q
```

Expected: fail because `tools/launcher/env_tool_mcp_server.py` does not exist.

- [ ] Implement `tools/launcher/env_tool_mcp_server.py`:
  - insert repo `scripts` path into `sys.path`;
  - parse optional `--repo-root`, `--instance-id`, `--buddy`, `--broker-socket`;
  - handle JSON-RPC line messages;
  - `initialize` returns tools capability;
  - `tools/list` returns `{"tools": native_mcp.list_native_tool_specs()}`;
  - `tools/call` decodes the name and calls an injectable dispatcher;
  - default dispatcher calls `runtime_kernel.client.request_runtime_broker("env.tool", {"tool": tool, "action": action, "args": arguments})`;
  - return MCP content as compact JSON text.
- [ ] Rerun MCP server tests until green.

## Task 4: Product-Mode MCP Registration

- [ ] Add focused launcher tests using fake `codex` call capture:
  - bootstrap registers `buddyswitch-env`;
  - stale server args are repaired;
  - non-product local mode does not register it.
- [ ] Run only the focused launcher group:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "env_mcp or product_instance_start_registers_runtime_mcp" -q
```

Expected: fail because no env MCP registration exists.

- [ ] Modify `tools/launcher/env.sh`:
  - default `BUDDYSWITCH_ENV_MCP_NAME=buddyswitch-env`;
  - default `BUDDYSWITCH_ENV_MCP_SERVER=${BUDDYSWITCH_REPO_ROOT}/tools/launcher/env_tool_mcp_server.py`;
  - add `buddyswitch_env_mcp_has_server`, `buddyswitch_env_mcp_server_matches_instance`, `buddyswitch_env_mcp_add_server`, `buddyswitch_env_mcp_ensure`, `buddyswitch_env_mcp_disable`;
  - call `buddyswitch_env_mcp_ensure` in locked product bootstrap after `buddyswitch_runtime_broker_ensure` and after `buddyswitch_patch_codex_config`.
- [ ] Reuse existing `buddyswitch_run_codex mcp add/remove` pattern.
- [ ] Rerun focused launcher tests.
- [ ] Run residual process check if any focused launcher test starts services.

## Task 5: Native-First Prose Governance

- [ ] Add/modify tests:
  - parse active `python3 scripts/env/client.py <tool> <action>` examples and assert registry support;
  - update AGENTS tests to expect `task current` instead of `task get`;
  - update shared skill tests to allow native-first language and context/CLI fallback;
  - update message available handler test to reject `message_id` + unsupported `message.list` implication.
- [ ] Run focused prose tests and observe failures.
- [ ] Update AGENTS, shared runtime tool skills, and message available handler.
- [ ] Rerun focused prose tests until green.

## Task 6: Relevant Broad Verification

- [ ] Run pure/non-service verification:

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

- [ ] Run focused launcher verification only after pure tests pass:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "mcp or codex_config or product_instance" -q
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex|chrome_devtools_cockpit_proxy.py" || true
```

- [ ] If focused launcher tests leak resources, stop and fix lifecycle before running broader launcher tests.

## Task 7: Review Audit

- [ ] Inspect source for forbidden A+ shapes:

```bash
rg -n "SHIPPED_TOOLS|task__current|message__send|if .*message__|elif .*__|handler_map|native_manifest|tool_pack" scripts/env/tool_runtime tools/launcher tests -S
```

- [ ] Confirm `git status --short` contains only intended files.
- [ ] Confirm `docs/memo/2026-05-30-buddyswitch-env-tool-native-discovery-options.html` is tracked or ready to stage.
- [ ] Summarize tests, residual process checks, and remaining risks.
