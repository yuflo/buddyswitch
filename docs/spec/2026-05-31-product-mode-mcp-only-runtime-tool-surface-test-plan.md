# Product-Mode MCP-Only Runtime Tool Surface Test Plan

Date: 2026-05-31
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`
Source memo: `docs/memo/2026-05-31-product-mode-mcp-only-runtime-tool-surface.md`

## Goal

Prove that BuddySwitch product-mode runtime actions are exposed to Codex through native BuddySwitch env MCP tools, not through env CLI action hints or env CLI fallback.

The verified end state is:

```text
Product-mode Codex host-visible runtime surface
  -> native BuddySwitch env MCP tools
  -> semantic runtime catalog and feedback
  -> no copyable scripts/env/client.py runtime action affordance
```

Diagnostic commands may remain when they repair or inspect runtime infrastructure, such as `python3 scripts/turn_runtime.py status` or `./buddyswitch-codex instance attach <instance-id>`. They must not become env object action fallbacks.

## Resource Lifecycle Guard

Follow `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.

- Prefer pure unit tests, direct Python module tests, and shell-function tests that do not start persistent services.
- Do not run broad launcher suites until focused launcher tests pass.
- Avoid tests that start real daemons, browsers, app-servers, or runtime brokers unless the helper already owns teardown.
- After any focused launcher or service-starting test, run:

```bash
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex|chrome_devtools_cockpit_proxy.py" || true
```

- If residual processes appear, stop and fix lifecycle before running broader verification.

## Functional Requirements

| ID | Requirement |
| --- | --- |
| FR1 | Native MCP projection still covers every registry action and remains generated from tool definitions, not a static manifest. |
| FR2 | Native MCP tool descriptions expose atomic capability semantics and do not contain copyable env CLI action commands. |
| FR3 | Runtime `context.get` / `context.summarize` / `turn_runtime.py status` product catalog output contains native MCP affordances and does not expose `command` or `cli_resource` env CLI metadata. |
| FR4 | `ToolDefinition` no longer requires or stores env CLI command metadata for shipped tools. |
| FR5 | Search status, request, rejection, and browser-open feedback does not return env CLI `command_hint`. |
| FR6 | Search feedback preserves semantic next-action options so Codex can choose native atomic tools without hardcoded workflow scripts. |
| FR7 | Product-mode env CLI execution is fail-closed by default and does not call the broker. |
| FR8 | Env CLI can still be used only under an explicit admin/debug environment override, preserving local diagnostics without product-mode action fallback. |
| FR9 | Runtime broker unavailable feedback may suggest launcher/runtime recovery, but not `scripts/env/client.py` object actions. |
| FR10 | Launcher native web search rejection points to native search MCP tools and runtime status diagnostics, not env CLI search commands. |
| FR11 | Active AGENTS, skills, role contracts, and message-available prompt remain free of env CLI action examples. |
| FR12 | Tool packages do not import or reason about MCP transport identity. Product-mode admission is not pushed down into per-tool services. |
| FR13 | App-server WebSocket close waits for peer close or timeout before closing the socket, preventing close-handshake reset noise. |
| FR14 | App-server close tests remain focused and leave no persistent service residue. |

## Test Groups

### T1: Native MCP Baseline

Files:

- `tests/test_env_native_mcp_projection.py`
- `tests/test_env_native_mcp_server.py`

Behavior:

- Projection covers every supported registry action.
- Projection loads public tool definitions only, not `_impl.py`, repos, domain ops, or launcher services.
- Projection supports dynamically discovered tool packages without central manifest edits.
- Projection descriptions contain no `scripts/env/client.py`.

Focused command:

```bash
python3 -m pytest tests/test_env_native_mcp_projection.py tests/test_env_native_mcp_server.py -q
```

Expected before implementation: existing tests should pass; the new no-CLI assertion may fail if CLI metadata leaks into native descriptions.

### T2: Runtime Catalog Native Affordance

Files:

- `tests/test_repo_consistency.py`
- `tests/test_runless_runtime_contract.py`
- `tests/test_env_tool_payload_contract.py`
- `tests/test_env_tool_schema_contract.py`

Behavior:

- `registry.env_tools_description()` and `turn_runtime.py status` do not include `command` or `cli_resource`.
- Each catalog row includes native MCP affordance data:
  - `native_mcp.tool_name_pattern`;
  - `native_mcp.actions[action] == "<tool>__<action>"`.
- Catalog rows still include semantic fields: `plain_description`, `use_when`, `do_not_use_when`, `capability_boundary`, `object_model`, `operations`, `payload_fields`, `input_schemas`, `action_semantics`, `authoritative_fields`.
- `compact_tool_affordances()` remains compact and does not expose schemas, payload fields, or CLI.
- `ToolDefinition` validation no longer requires CLI metadata.

Focused command:

```bash
python3 -m pytest \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_registry_semantic_projections_are_generated_from_definitions \
  tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_status_exposes_env_tools_catalog \
  tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_context_get_exposes_full_input_schemas \
  tests/test_env_tool_payload_contract.py::EnvToolPayloadContractTests::test_runtime_catalog_payload_fields_match_registry_order \
  tests/test_env_tool_schema_contract.py::EnvToolSchemaContractTests::test_valid_tool_definition_accepts_complete_schema -q
```

Expected before implementation: fail because catalog rows currently expose `command` and `cli_resource`, and temporary test definitions still pass CLI metadata.

### T3: Search Feedback Semantic Native Options

File:

- `tests/test_search_env_tool.py`

Behavior:

- `search.status` returns no `command_hint` and returns an `allowed_next_action_options` entry for `search.open_browser` with `native_tool == "search__open_browser"`.
- Query, engine, backend, search-api unavailable, and browser readiness rejections contain:
  - `state_changed == false`;
  - `durability == "none"`;
  - `correctable_fields` where applicable;
  - semantic `allowed_next_action_options`;
  - no `command_hint` containing `scripts/env/client.py`.
- `search.request` success returns target URL intent and a semantic `search__open_browser` option, without a CLI command.
- Browser-open success may instruct use of `chrome-devtools-cockpit`; that is an MCP continuation note, not env CLI fallback.

Focused command:

```bash
python3 -m pytest tests/test_search_env_tool.py -q
```

Expected before implementation: fail because tests currently expect `command_hint` and implementation returns env CLI command hints.

### T4: Product-Mode Env CLI Fail-Closed

File:

- `tests/test_env_client_payload_cli.py`

Behavior:

- With product-mode environment variables such as `BUDDYSWITCH_INSTANCE_ID`, `BUDDYSWITCH_ACTIVE_BUDDY`, or `BUDDYSWITCH_RUNTIME_BROKER_SOCKET`, `scripts/env/client.py message list --payload '{}'` fails before broker dispatch unless `BUDDYSWITCH_ALLOW_ENV_ADMIN_CLI=1`.
- Failure response contains:
  - `ok: false`;
  - `error.code == "E_ENV_CLI_PRODUCT_MODE_DISABLED"`;
  - `permission_boundary == "product-mode-native-mcp-only"`;
  - `state_changed == false`;
  - `durability == "none"`;
  - `allowed_next_actions` pointing to native BuddySwitch env MCP tools and runtime status diagnostics;
  - no `scripts/env/client.py` fallback.
- With `BUDDYSWITCH_ALLOW_ENV_ADMIN_CLI=1`, existing env CLI dispatch tests still pass.
- Outside product-mode environment, CLI tests remain valid for local debug/test harness.

Focused command:

```bash
python3 -m pytest tests/test_env_client_payload_cli.py -q
```

Expected before implementation: fail because the CLI currently dispatches to broker in product-mode env.

### T5: Launcher Native Web Search Rejection

Files:

- `tests/test_buddyswitch_launcher.py`
- optionally a new shell-function focused test if direct function coverage is cleaner.

Behavior:

- When product-mode `codex` args request native Codex web search, launcher rejects the args.
- Stderr contains:
  - `Native Codex web_search is disabled in BuddySwitch product sessions.`;
  - native search tool names `search__status` and `search__open_browser`;
  - runtime diagnostic `python3 scripts/turn_runtime.py status`.
- Stderr does not contain:
  - `python3 scripts/env/client.py`;
  - `search open-browser --query`;
  - `search open-browser --payload`.
- The rejection does not invoke Codex or mutate runtime state.

Focused command:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "native_web_search" -q
```

Expected before implementation: fail because `tools/launcher/env.sh` currently prints env CLI search commands.

### T6: Active Guidance Residual Governance

Files:

- `tests/test_repo_consistency.py`
- `tests/test_runtime_skills.py`
- `tests/test_message_available_handler.py`
- `tests/test_host_decision_surface_product_mode.py`
- `tests/test_buddyswitch_launcher.py`

Behavior:

- Active product guidance targets contain no env CLI action examples:
  - `buddyswitch/skills/shared`;
  - `buddyswitch/skills/market`;
  - selected `buddyswitch/skills/dev`, `design`, `test`;
  - `framework/contracts`;
  - `tools/launcher/assets/buddies`;
  - `tools/launcher/message_available_handler.py`.
- Historical docs under `docs/memo` and `docs/spec` are not product-mode active guidance and are excluded from this governance scan.

Focused command:

```bash
python3 -m pytest \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_product_guidance_has_no_env_client_cli_first_examples \
  tests/test_runtime_skills.py \
  tests/test_message_available_handler.py -q
```

Expected before implementation: should already mostly pass for the prior cleanup, and must stay green.

### T7: App-Server Close Handshake

Files:

- `tools/launcher/app_server.py`
- `tests/test_app_server_client.py`

Behavior:

- `AppServerClient.close()` sends a close frame, waits for peer close frame, and then closes the socket.
- It tolerates timeout or peer EOF without raising during cleanup.
- Test uses the existing in-process `FakeUnixWebSocketServer`, not a real app-server daemon.
- No persistent app-server process is started.

Focused command:

```bash
python3 -m pytest tests/test_app_server_client.py -q
```

Expected before implementation: new close-wait assertion fails because the client currently closes immediately after sending close.

## Broad Verification

Run focused groups first. After they pass, run:

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

Then run the residual process check:

```bash
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex|chrome_devtools_cockpit_proxy.py" || true
```

If the broad launcher test scope proves too heavy or starts persistent services unexpectedly, stop, inspect lifecycle ownership, and narrow verification to the focused tests plus the affected launcher cases.

## Review Checklist

- Requirements FR1-FR14 have direct test evidence.
- No test asserts a narrow implementation string merely to make a patch easy; each test checks host-visible product behavior.
- Tests do not require starting persistent services unless the existing harness owns cleanup.
- Historical docs can mention old CLI behavior; active product guidance cannot.
- Diagnostic commands are not confused with env runtime object action fallbacks.
