# Product-Mode MCP-Only Runtime Tool Surface Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` while implementing behavior changes. Use `superpowers:executing-plans` or a direct TDD loop to execute this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make BuddySwitch product-mode runtime actions MCP-only from Codex's default host-visible surface while preserving explicit diagnostics and admin/debug escape hatches.

**Architecture:** Keep env action semantics owned by per-tool definitions and responses. Generate native MCP affordances from the registry. Keep product-mode admission in CLI/launcher/broker-facing layers, not in tool packages. Replace env CLI action hints with semantic native next-action options.

**Tech Stack:** Python stdlib, pytest/unittest, BuddySwitch env tool registry, native MCP projection, launcher shell scripts, Markdown guidance assets.

---

## Current Code Findings

- `scripts/env/tool_runtime/native_mcp.py` already projects registry actions as native MCP tools.
- `tools/launcher/env_tool_mcp_server.py` already forwards MCP `tools/call` to broker `env.tool`.
- `scripts/env/tool_runtime/registry.py::env_tools_description()` still exposes `command` and `cli_resource`.
- `scripts/env/tool_runtime/definition.py::ToolDefinition` still requires `cli_resource` and `command`, so every shipped tool definition embeds env CLI action metadata.
- `scripts/env/tools/search/_impl.py` still returns env CLI `command_hint` for status, validation, search-api rejection, and request planning.
- `tools/launcher/env.sh::buddyswitch_reject_native_search_args()` still prints env CLI search commands.
- `scripts/env/client.py` still dispatches product-mode env actions through broker by default.
- `tools/launcher/app_server.py::AppServerClient.close()` sends a close frame and immediately closes the socket.

## File Structure

Modify tests first:

- `tests/test_env_native_mcp_projection.py`
- `tests/test_repo_consistency.py`
- `tests/test_runless_runtime_contract.py`
- `tests/test_env_tool_payload_contract.py`
- `tests/test_env_tool_schema_contract.py`
- `tests/test_search_env_tool.py`
- `tests/test_env_client_payload_cli.py`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_app_server_client.py`

Modify implementation:

- `scripts/env/tool_runtime/definition.py`
- `scripts/env/tool_runtime/registry.py`
- `scripts/env/tool_runtime/results.py`
- `scripts/env/tool_runtime/native_mcp.py`
- `scripts/env/tools/*/tool.py`
- `scripts/env/tools/search/_impl.py`
- `scripts/env/client.py`
- `tools/launcher/env.sh`
- `tools/launcher/app_server.py`

Do not modify per-tool `_impl.py` files to detect MCP vs CLI transport, except `search/_impl.py` for host-visible feedback semantics.

## Task 1: Establish Native MCP Baseline

- [ ] Run:

```bash
python3 -m pytest tests/test_env_native_mcp_projection.py tests/test_env_native_mcp_server.py -q
```

- [ ] Expected: pass before implementation except any newly added no-CLI assertion.
- [ ] If it fails unexpectedly, debug before continuing; do not change CLI or search behavior while native projection is unclear.

## Task 2: Remove CLI Metadata From Tool Definitions And Catalog

- [ ] Add failing tests:
  - `tests/test_repo_consistency.py::test_runtime_tool_catalog_exposes_native_affordances_not_env_cli_commands`
  - update `test_registry_semantic_projections_are_generated_from_definitions`
  - update `tests/test_env_tool_schema_contract.py` temporary `ToolDefinition` construction.

Required test assertions:

```python
desc = tool_catalog.env_tools_description()
for tool, row in desc.items():
    self.assertNotIn("command", row)
    self.assertNotIn("cli_resource", row)
    self.assertIn("native_mcp", row)
    native = row["native_mcp"]
    self.assertEqual(native["tool_name_pattern"], f"{tool}__<action>")
    for action in tool_catalog.supported_actions(tool):
        self.assertEqual(native["actions"][action], f"{tool}__{action}")
```

- [ ] Run RED:

```bash
python3 -m pytest \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_tool_catalog_exposes_native_affordances_not_env_cli_commands \
  tests/test_env_tool_schema_contract.py::EnvToolSchemaContractTests::test_valid_tool_definition_accepts_complete_schema -q
```

- [ ] Implement:
  - remove `cli_resource` and `command` fields from `ToolDefinition`;
  - remove validation for those fields;
  - update every `scripts/env/tools/*/tool.py` definition to omit those fields;
  - update temporary test tool definitions to omit those fields;
  - update `registry.env_tools_description()` to remove `command` and `cli_resource`;
  - add `native_mcp` row with `tool_name_pattern` and per-action native tool names.

- [ ] Run GREEN:

```bash
python3 -m pytest \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_tool_catalog_exposes_native_affordances_not_env_cli_commands \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_registry_semantic_projections_are_generated_from_definitions \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_payload_contract.py \
  tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_status_exposes_env_tools_catalog \
  tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_context_get_exposes_full_input_schemas -q
```

## Task 3: Add Native Tool Names To Semantic Next-Action Options

- [ ] Add or update tests in `tests/test_search_env_tool.py` and response contract tests so `allowed_next_action_options` entries include:

```python
self.assertEqual(option["native_tool"], f"{option['tool']}__{option['action']}")
```

- [ ] Run RED:

```bash
python3 -m pytest tests/test_search_env_tool.py -k "status or request" -q
```

- [ ] Implement in `scripts/env/tool_runtime/results.py::next_action_option()`:
  - include `native_tool: f"{tool}__{action}"`;
  - keep existing `tool`, `action`, `mutates`, `preconditions`, `reason`, and `source_refs`.

- [ ] Run GREEN:

```bash
python3 -m pytest tests/test_search_env_tool.py -k "status or request" -q
```

## Task 4: Replace Search CLI Command Hints With Semantic Feedback

- [ ] Update `tests/test_search_env_tool.py` before implementation:
  - remove expectations for `command_hint`;
  - assert no response contains `scripts/env/client.py`;
  - assert status/request/rejection responses contain native `search__open_browser` or `search__status` options as applicable;
  - keep URL-building, browser endpoint, and state-change assertions.

- [ ] Run RED:

```bash
python3 -m pytest tests/test_search_env_tool.py -q
```

- [ ] Implement in `scripts/env/tools/search/_impl.py`:
  - remove env CLI `command_hint` extras;
  - add `allowed_next_action_options` to `_engine_error`, `_query_error`, `_backend_error`, `_browser_unavailable`, `_browser_open_failed`, `_search_api_unavailable`, `status_for_active_instance`, and `request_for_active_instance`;
  - keep `chrome-devtools-cockpit` instruction for `open_browser` success as an MCP continuation note, not a CLI command;
  - keep browser ensure as prose inside `allowed_next_actions`, not a copyable command.

- [ ] Run GREEN:

```bash
python3 -m pytest tests/test_search_env_tool.py -q
```

## Task 5: Fail Closed Product-Mode Env CLI By Default

- [ ] Add failing tests in `tests/test_env_client_payload_cli.py`:

```python
def test_product_mode_env_cli_refuses_runtime_action_without_admin_override(self):
    stdout = io.StringIO()
    with mock.patch.dict(os.environ, {
        "BUDDYSWITCH_INSTANCE_ID": "inst-dev-test",
        "BUDDYSWITCH_ACTIVE_BUDDY": "dev",
        "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": "/tmp/runtime.sock",
    }, clear=False):
        with mock.patch.object(sys, "argv", ["client.py", "message", "list", "--payload", "{}"]):
            with mock.patch.object(self.client, "request_runtime_broker") as broker:
                with contextlib.redirect_stdout(stdout):
                    code = self.client.main()
    output = json.loads(stdout.getvalue())
    self.assertEqual(code, 1)
    self.assertEqual(output["error"]["code"], "E_ENV_CLI_PRODUCT_MODE_DISABLED")
    self.assertEqual(output["permission_boundary"], "product-mode-native-mcp-only")
    self.assertFalse(output["state_changed"])
    self.assertEqual(output["durability"], "none")
    self.assertNotIn("scripts/env/client.py", json.dumps(output))
    broker.assert_not_called()
```

- [ ] Add admin override test:

```python
with mock.patch.dict(os.environ, {
    "BUDDYSWITCH_INSTANCE_ID": "inst-dev-test",
    "BUDDYSWITCH_ACTIVE_BUDDY": "dev",
    "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": "/tmp/runtime.sock",
    "BUDDYSWITCH_ALLOW_ENV_ADMIN_CLI": "1",
}, clear=False):
    code, output, broker = self._run_client(["message", "list", "--payload", "{}"])
    self.assertEqual(code, 0)
    broker.assert_called_once()
```

- [ ] Run RED:

```bash
python3 -m pytest tests/test_env_client_payload_cli.py -q
```

- [ ] Implement in `scripts/env/client.py`:
  - detect product mode when any of `BUDDYSWITCH_INSTANCE_ID`, `BUDDYSWITCH_ACTIVE_BUDDY`, or `BUDDYSWITCH_RUNTIME_BROKER_SOCKET` is present;
  - allow only when `BUDDYSWITCH_ALLOW_ENV_ADMIN_CLI=1`;
  - reject before broker dispatch with structured error fields;
  - keep local non-product CLI behavior unchanged.

- [ ] Run GREEN:

```bash
python3 -m pytest tests/test_env_client_payload_cli.py tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_env_client_help_exposes_runless_resources -q
```

## Task 6: Replace Launcher Native Web Search Rejection Text

- [ ] Add or update launcher test:
  - product-mode native web search arg rejection contains `search__status`, `search__open_browser`, and `python3 scripts/turn_runtime.py status`;
  - rejection does not contain `scripts/env/client.py`.

- [ ] Run RED:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "native_web_search" -q
```

- [ ] Implement in `tools/launcher/env.sh::buddyswitch_reject_native_search_args()`:
  - replace repeated CLI text with one helper that prints native search MCP tool guidance;
  - preserve return code `2`;
  - keep rejection before `codex` invocation.

- [ ] Run GREEN:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "native_web_search" -q
```

## Task 7: App-Server Close Handshake

- [ ] Add focused test in `tests/test_app_server_client.py`:
  - fake server records receipt of client close and sends close back;
  - `AppServerClient.close()` waits until the close frame is consumed;
  - no exception on peer EOF or timeout.

- [ ] Run RED:

```bash
python3 -m pytest tests/test_app_server_client.py -q
```

- [ ] Implement in `tools/launcher/app_server.py`:
  - after `_send_frame(0x8, b"")`, read frames until close frame, EOF, socket error, or a short timeout;
  - do not process JSON messages during close;
  - always close socket in `finally`;
  - keep cleanup exceptions suppressed.

- [ ] Run GREEN:

```bash
python3 -m pytest tests/test_app_server_client.py -q
```

## Task 8: Active Guidance Governance Recheck

- [ ] Run:

```bash
python3 -m pytest \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_product_guidance_has_no_env_client_cli_first_examples \
  tests/test_runtime_skills.py \
  tests/test_message_available_handler.py \
  tests/test_host_decision_surface_product_mode.py -q
```

- [ ] If failures mention historical docs only, adjust test scope to active product guidance rather than changing history.
- [ ] If failures mention AGENTS, skills, role contracts, or handler prompts, remove env CLI action examples and rerun.

## Task 9: Broad Verification And Resource Check

- [ ] Run:

```bash
python3 -m pytest \
  tests/test_env_native_mcp_projection.py \
  tests/test_env_native_mcp_server.py \
  tests/test_repo_consistency.py \
  tests/test_runless_runtime_contract.py \
  tests/test_env_tool_payload_contract.py \
  tests/test_env_tool_schema_contract.py \
  tests/test_search_env_tool.py \
  tests/test_env_client_payload_cli.py \
  tests/test_buddyswitch_launcher.py \
  tests/test_runtime_skills.py \
  tests/test_message_available_handler.py \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_app_server_client.py -q
```

- [ ] Run residual process check:

```bash
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex|chrome_devtools_cockpit_proxy.py" || true
```

- [ ] If broad launcher scope is too heavy or lifecycle looks unsafe, stop and inspect with the resource lifecycle bitter note before retrying.

## Review Checklist

- [ ] Product-mode runtime action path is native MCP by default.
- [ ] Env CLI is not a default product-mode action fallback.
- [ ] Runtime catalog gives native affordances and semantic contracts, not copyable CLI commands.
- [ ] Search feedback gives semantic next-action options, not hard workflow scripts.
- [ ] Tool packages do not know whether transport is MCP or CLI.
- [ ] Diagnostics remain available without becoming env action fallbacks.
- [ ] App-server close handshake is fixed separately and covered by focused tests.
- [ ] All focused and broad relevant verification commands have current output.
