# Native-First Env Tool Surface Cleanup Test Plan

Date: 2026-05-31
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`

## Goal

Prove BuddySwitch product-mode env tools are native-first across the whole active tool surface:

```text
runtime registry owns 9 tools / 40 actions
-> native MCP projects every action
-> product-mode launcher registers buddyswitch-env
-> active runtime tips, skills, role contracts, and buddy AGENTS teach native BuddySwitch env MCP tools first
-> CLI remains only debug/test harness, not product workflow guidance
```

This is a governance and behavior cleanup on top of the already implemented native projection/server path. It must cover every registry tool: `artifact`, `comment`, `context`, `evidence`, `message`, `request`, `search`, `task`, and `track`.

## Resource Lifecycle Guard

Follow `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.

- Prefer pure unit/subprocess/prose tests first.
- Do not start real daemons, app-server, browser, broker, fake Codex, or detached services for prose governance.
- Launcher tests must use the existing fake Codex harness and focused `-k` selection.
- After any service-starting or launcher verification, run:

```bash
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex|chrome_devtools_cockpit_proxy.py" || true
```

- If residual test-owned processes appear, stop and fix lifecycle before broader verification.

## Functional Requirements

| ID | Requirement |
| --- | --- |
| FR1 | Native MCP projection still covers exactly the registry action set: 9 tools / 40 actions. |
| FR2 | MCP server `tools/list` exposes registry-projected native tools and no stale action such as `task__get`. |
| FR3 | Product-mode launcher config still registers exactly one `buddyswitch-env` MCP server for the active instance. |
| FR4 | `message.available` runtime tip is a single native-first instruction and contains no `Fallback CLI` or copyable env client command. |
| FR5 | Shared runtime tool skills are workflow notes for native BuddySwitch env MCP tools, not CLI payload tutorials. |
| FR6 | Shared skills do not contain `CLI Payload Rule`, copyable `python3 scripts/env/client.py ...` examples, or `--payload` command recipes. |
| FR7 | Shared skills still preserve important workflow/boundary knowledge and route exact payload/schema details to runtime discovery surfaces. |
| FR8 | Buddy AGENTS templates start with native context summary guidance, not `python3 scripts/env/client.py context summarize`. |
| FR9 | Buddy AGENTS templates contain no copyable env client commands for track/task/artifact/request/comment/search. |
| FR10 | Role contracts describe native BuddySwitch env MCP tools as the durable runtime path. |
| FR11 | Role contracts contain no copyable env client commands and no `python3 scripts/env/client.py ...` default path. |
| FR12 | Market/search skills use native `search__open_browser` guidance and keep browser-cockpit continuation. |
| FR13 | Non-market role skills that mention runtime execution use native-first wording, not env client CLI. |
| FR14 | Active guidance does not reference unsupported stale actions such as `task get`, `message.list`, or CLI kebab examples as primary workflow. |
| FR15 | Active guidance residual scan is clean for `python3 scripts/env/client.py`, `Fallback CLI`, and `CLI Payload Rule`. |
| FR16 | Tests that previously required CLI-first prose are rewritten into native-first governance tests. |
| FR17 | CLI implementation and CLI tests remain valid as debug/test harness and are not deleted. |
| FR18 | Relevant focused tests and residual scans pass without resource leakage. |

## Test Groups

### T1: Native Projection And Server Regression

Files:

- `tests/test_env_native_mcp_projection.py`
- `tests/test_env_native_mcp_server.py`

Behavior:

- Assert projected native specs equal the registry action count.
- Assert `artifact__*`, `comment__*`, `context__*`, `evidence__*`, `message__*`, `request__*`, `search__*`, `task__*`, and `track__*` exist for current registry actions.
- Assert `task__get` does not exist.
- Assert `tools/list` returns native specs.
- Assert `tools/call` dispatches by decoded tool/action through generic env.tool routing.

Focused command:

```bash
python3 -m pytest tests/test_env_native_mcp_projection.py tests/test_env_native_mcp_server.py -q
```

Expected: pass before and after cleanup; this protects the underlying native surface while prose changes.

### T2: Message Available Native-Only Tip

File: `tests/test_message_available_handler.py`

Test updates:

- In `test_message_available_handler_submits_read_prompt_through_action_gateway`, assert:
  - prompt includes `[MESSAGE AVAILABLE]`;
  - prompt includes native message inbox/conversation language;
  - prompt does not include `Fallback CLI`;
  - prompt does not include `python3 scripts/env/client.py`;
  - prompt does not include `message list --payload`;
  - prompt does not imply `message_id` can be passed into `message.list`;
  - prompt does not include message content/body.

Focused command:

```bash
python3 -m pytest tests/test_message_available_handler.py::MessageAvailableHandlerTests::test_message_available_handler_submits_read_prompt_through_action_gateway -q
```

Expected before implementation: fail because the handler currently contains a copyable fallback CLI command.

### T3: Shared Runtime Skill Native-First Governance

File: `tests/test_runtime_skills.py`

Test updates:

- Replace CLI-payload tutorial tests with native-first tests.
- For all shared tool skills:
  - assert `native BuddySwitch env MCP tools` appears;
  - assert `context.get.tool_catalog` appears for exact contract discovery;
  - assert `python3 scripts/turn_runtime.py status` appears as diagnostic fallback;
  - assert `python3 scripts/env/client.py`, `CLI Payload Rule`, and `--payload` do not appear.
- For `message-tool`, assert it still teaches:
  - `message__contacts`, `message__send`, `message__list`, `message__conversation`;
  - `target_actor_address`;
  - `contact.actor_address`;
  - `message__list` does not accept `box`;
  - use `request__list` for request filtering;
  - no `to_buddy`, `from_buddy`, `"actor_address":`, or `"message":` payload aliases.

Focused command:

```bash
python3 -m pytest tests/test_runtime_skills.py -k "shared_tool or shared_message" -q
```

Expected before implementation: fail on current shared skills because they still contain CLI payload rules and copyable env client commands.

### T4: Buddy AGENTS Native-First Governance

Files:

- `tests/test_runtime_skills.py`
- `tests/test_repo_consistency.py`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_host_decision_surface_product_mode.py`

Test updates:

- AGENTS assertions must require:
  - `Start with the native BuddySwitch env context summary tool when runtime context is needed.`
  - `Prefer native BuddySwitch env MCP tools`
  - `context.get.tool_catalog`
  - `python3 scripts/turn_runtime.py status`
  - `do not bypass runtime`
- AGENTS assertions must reject:
  - `python3 scripts/env/client.py`;
  - `context summarize --payload`;
  - `context get --payload`;
  - `track open --payload`;
  - `task current --payload`;
  - `artifact get --payload`;
  - `request get --payload`;
  - `search open-browser --payload`.

Focused commands:

```bash
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_buddy_agents_do_not_present_authoritative_hardcoded_tool_lists -q
python3 -m pytest tests/test_repo_consistency.py -k "runtime_buddy_agents or contracts_and_buddy_agents_point_to_runtime_discovery" -q
python3 -m pytest tests/test_host_decision_surface_product_mode.py::HostDecisionSurfaceProductModeTests::test_pm_page_prototype_decision_surface_prefers_direct_private_buddybox_directory_without_phrase_rule -q
python3 -m pytest tests/test_buddyswitch_launcher.py -k "start_with_required_buddy_creates_product_instance" -q
```

Expected before implementation: fail because AGENTS currently start with `python3 scripts/env/client.py context summarize --payload '{}'` and contain copyable CLI examples.

### T5: Role Contract Native-First Governance

Files:

- `tests/test_repo_consistency.py`
- `tests/test_runtime_skills.py`

Test updates:

- For `framework/contracts/{pm,market,design,dev,test}.md`, assert:
  - native BuddySwitch env MCP tools are the durable runtime path;
  - exact schema is discovered through native tool schema, `context.get.tool_catalog`, or `python3 scripts/turn_runtime.py status`;
  - no `python3 scripts/env/client.py`;
  - no `context summarize` CLI-first start instruction.
- Preserve role-specific tokens such as `track.open`, `artifact.create_revision`, `track.add_material`, `track.add_proof`, `request.get`, and `comment.resolve` where they are boundary concepts, not command recipes.

Focused command:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_contracts_and_buddy_agents_point_to_runtime_discovery tests/test_runtime_skills.py::RuntimeSkillsTests::test_pm_contract_and_agents_align_with_generic_skill_surface -q
```

Expected before implementation: fail because contracts still define env client CLI as the runtime boundary.

### T6: Market/Search Skill Native Search Entry

File: `tests/test_runtime_skills.py`

Test updates:

- Rename `test_market_skills_use_payload_browser_entry` to native-first behavior.
- For every Market P0 skill:
  - assert `search__open_browser`;
  - assert `chrome-devtools-cockpit`;
  - assert no `python3 scripts/env/client.py`;
  - assert no `search open-browser --payload`;
  - assert no old flag forms.
- Update evidence boundary tests to require `search__open_browser`, not CLI command text.

Focused command:

```bash
python3 -m pytest tests/test_runtime_skills.py -k "market_skills_use_native_browser_entry or market_p0_skills_preserve_runtime_evidence_boundaries" -q
```

Expected before implementation: fail because current market skills tell agents to call env client CLI.

### T7: Active Guidance Residual Scan

File: `tests/test_repo_consistency.py`

Add or update repository-level scan:

```python
targets = [
    "buddyswitch/skills/shared",
    "buddyswitch/skills/market",
    "buddyswitch/skills/dev/enter-dev-workspace/SKILL.md",
    "buddyswitch/skills/design/shape-prototype/SKILL.md",
    "buddyswitch/skills/test/smoke-test/SKILL.md",
    "framework/contracts",
    "tools/launcher/assets/buddies",
    "tools/launcher/message_available_handler.py",
]
for forbidden in (
    "python3 scripts/env/client.py",
    "Fallback CLI",
    "CLI Payload Rule",
    "search open-browser --payload",
    "context summarize --payload",
    "message list --payload",
):
    assert rg over targets has no hits
```

Focused command:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_active_product_guidance_has_no_env_client_cli_first_examples -q
```

Expected before implementation: fail on current active guidance.

### T8: Focused And Broad Verification

Run after focused red/green loops:

```bash
python3 -m pytest \
  tests/test_env_native_mcp_projection.py \
  tests/test_env_native_mcp_server.py \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  tests/test_message_available_handler.py \
  tests/test_host_decision_surface_product_mode.py \
  -q
```

Launcher focused verification:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "mcp or codex_config or product_instance or start_with_required_buddy_creates_product_instance" -q
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex|chrome_devtools_cockpit_proxy.py" || true
```

Residual shell scans:

```bash
rg -n "python3 scripts/env/client.py|Fallback CLI|CLI Payload Rule|search open-browser --payload|context summarize --payload|message list --payload" \
  buddyswitch/skills/shared \
  buddyswitch/skills/market \
  buddyswitch/skills/dev/enter-dev-workspace/SKILL.md \
  buddyswitch/skills/design/shape-prototype/SKILL.md \
  buddyswitch/skills/test/smoke-test/SKILL.md \
  framework/contracts \
  tools/launcher/assets/buddies \
  tools/launcher/message_available_handler.py
```

Expected: no hits.

## Review Checklist

- Tests start from product requirements, not implementation shortcuts.
- Native projection/server/launcher paths remain protected.
- Active runtime guidance no longer gives shell CLI as primary or co-primary path.
- Shared skills keep workflow boundaries but do not duplicate schema or payload recipes.
- Role contracts and buddy AGENTS are native-first and concise.
- Search guidance uses native `search__open_browser` plus browser-cockpit continuation.
- CLI remains available in implementation/tests as debug harness.
- Verification avoids resource blowups and includes residual process checks after launcher tests.

## Phase 1 Self-Review

- Coverage: FR1-FR18 map to T1-T8; all 9 registry tools are covered through native projection plus active guidance scans.
- No transition path: the plan removes active CLI-first guidance instead of allowing dual primary paths.
- No speculative abstraction: no new gateway, plugin engine, tool pack, or compatibility alias is introduced.
- Resource risk: broad service-starting tests are deferred until pure/focused tests pass, with required residual checks.
