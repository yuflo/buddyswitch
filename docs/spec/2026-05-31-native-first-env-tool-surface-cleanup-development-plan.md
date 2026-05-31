# Native-First Env Tool Surface Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` while implementing behavior changes. Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` to execute this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the native-first env tool cleanup by replacing active CLI-first guidance with native BuddySwitch env MCP guidance, while preserving the registry-owned 9-tool / 40-action runtime contract.

**Architecture:** Keep `scripts/env/tool_runtime/native_mcp.py`, `tools/launcher/env_tool_mcp_server.py`, and launcher MCP registration as the product tool path. Change tests into governance checks, then directly replace active runtime tips, shared skills, role contracts, buddy AGENTS, and market/search skill wording. Do not add wrappers, aliases, dual paths, or generated prose catalogs.

**Tech Stack:** Python stdlib, pytest/unittest, existing BuddySwitch env registry/native MCP server, Markdown skill/contract/AGENTS assets, existing fake-Codex launcher tests.

---

## Current Code Audit

- Native projection exists in `scripts/env/tool_runtime/native_mcp.py`.
- Stdio MCP server exists in `tools/launcher/env_tool_mcp_server.py`.
- Registry currently exposes 9 tools / 40 actions:
  - `artifact`: `attach_file`, `get_attachment`, `list`, `create_revision`, `list_attachments`, `get`, `update_metadata`
  - `comment`: `list`, `resolve`, `add`
  - `context`: `summarize`, `list_sources`, `get`
  - `evidence`: `issue_browser`, `approve_downgrade`
  - `message`: `list`, `send`, `contacts`, `conversation`
  - `request`: `cancel`, `complete`, `list`, `block`, `accept`, `create`, `get`
  - `search`: `request`, `status`, `open_browser`
  - `task`: `confirm`, `current`, `propose`
  - `track`: `add_proof`, `add_material`, `archive`, `update_now`, `open`, `list`, `add_update`, `create`
- Current failure surface is active guidance:
  - `tools/launcher/message_available_handler.py` still includes `Fallback CLI`.
  - Six shared runtime skills still include `CLI Payload Rule` and copyable env client commands.
  - Five role contracts still define env client CLI as runtime boundary.
  - Five buddy AGENTS still start with `python3 scripts/env/client.py context summarize --payload '{}'` and include command examples.
  - Market P0 skills still teach `python3 scripts/env/client.py search open-browser --payload ...`.
  - Tests still assert CLI-first content in several places.

## File Structure

Modify tests first:

- `tests/test_message_available_handler.py`
- `tests/test_runtime_skills.py`
- `tests/test_repo_consistency.py`
- `tests/test_host_decision_surface_product_mode.py`
- `tests/test_buddyswitch_launcher.py`

Modify active guidance:

- `tools/launcher/message_available_handler.py`
- `buddyswitch/skills/shared/artifact-tool/SKILL.md`
- `buddyswitch/skills/shared/comment-tool/SKILL.md`
- `buddyswitch/skills/shared/message-tool/SKILL.md`
- `buddyswitch/skills/shared/request-tool/SKILL.md`
- `buddyswitch/skills/shared/task-management/SKILL.md`
- `buddyswitch/skills/shared/track-tool/SKILL.md`
- `framework/contracts/{pm,market,design,dev,test}.md`
- `tools/launcher/assets/buddies/{pm,market,design,dev,test}/AGENTS.md`
- `buddyswitch/skills/market/*/SKILL.md`
- `buddyswitch/skills/dev/enter-dev-workspace/SKILL.md`
- `buddyswitch/skills/design/shape-prototype/SKILL.md`
- `buddyswitch/skills/test/smoke-test/SKILL.md`

## Task 1: Protect Native MCP Baseline

- [ ] Run the baseline native projection/server tests:

```bash
python3 -m pytest tests/test_env_native_mcp_projection.py tests/test_env_native_mcp_server.py -q
```

- [ ] Expected: pass. If this fails, use `superpowers:systematic-debugging`; do not change prose until the native foundation is understood.

## Task 2: Make Message Runtime Tip Native-Only

- [ ] Update `tests/test_message_available_handler.py::test_message_available_handler_submits_read_prompt_through_action_gateway` before production changes.

Required assertions:

```python
self.assertIn("[MESSAGE AVAILABLE]", prompt)
self.assertIn("native", prompt.lower())
self.assertIn("message__list", prompt)
self.assertIn("message__conversation", prompt)
self.assertNotIn("Fallback CLI", prompt)
self.assertNotIn("python3 scripts/env/client.py", prompt)
self.assertNotIn("message list --payload", prompt)
self.assertNotIn("message_id: msg-readable", prompt)
self.assertNotIn("message.list", prompt)
self.assertNotIn("content", prompt)
self.assertNotIn("message body", prompt.lower())
```

- [ ] Run focused RED:

```bash
python3 -m pytest tests/test_message_available_handler.py::MessageAvailableHandlerTests::test_message_available_handler_submits_read_prompt_through_action_gateway -q
```

Expected: fail because the handler currently emits `Fallback CLI`.

- [ ] Modify `tools/launcher/message_available_handler.py` prompt to:

```text
[MESSAGE AVAILABLE]
A direct message is available for this actor.
Use the native BuddySwitch env message inbox tool to read unread inbox rows.
Use the native BuddySwitch env message conversation tool when bidirectional context is needed.
```

- [ ] Run focused GREEN:

```bash
python3 -m pytest tests/test_message_available_handler.py -q
```

## Task 3: Convert Shared Tool Skill Tests To Native-First Governance

- [ ] Replace `test_shared_tool_skills_teach_inline_json_payloads` with a test that rejects copyable CLI guidance in `SHARED_TOOL_SKILLS`.

Required behavior:

```python
for path in self.SHARED_TOOL_SKILLS.values():
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()
    self.assertIn("native buddyswitch env mcp tools", lowered)
    self.assertIn("context.get.tool_catalog", text)
    self.assertIn("python3 scripts/turn_runtime.py status", text)
    self.assertNotIn("python3 scripts/env/client.py", text)
    self.assertNotIn("CLI Payload Rule", text)
    self.assertNotIn("--payload", text)
```

- [ ] Replace `test_shared_tool_skill_env_client_examples_use_payload` with a no-copyable-CLI test using the same shared skill file set.

- [ ] Update `test_shared_message_skill_prevents_observed_invalid_calls` to expect native names:

```python
self.assertIn("message__contacts", message_skill)
self.assertIn("target_actor_address", message_skill)
self.assertIn("contact.actor_address", message_skill)
self.assertIn("message__send", message_skill)
self.assertIn("message__conversation", message_skill)
self.assertIn("message__list", message_skill)
self.assertIn("does not accept `box`", message_skill)
self.assertIn("request__list", message_skill)
self.assertIn("context.get.tool_catalog['message']", message_skill)
self.assertNotIn("message contacts --payload", message_skill)
self.assertNotIn("message send --payload", message_skill)
self.assertNotIn("message conversation --payload", message_skill)
self.assertNotIn("message list --payload", message_skill)
```

- [ ] Run focused RED:

```bash
python3 -m pytest tests/test_runtime_skills.py -k "shared_tool or shared_message" -q
```

Expected: fail on current CLI payload rules and examples.

## Task 4: Rewrite Shared Runtime Tool Skills

- [ ] Replace the six shared skills with native-first workflow notes.

Required shared structure:

```markdown
## Runtime Route
- Primary: use native BuddySwitch env MCP tools for this tool's actions.
- Exact payload schemas, allowed fields, and response meanings come from the native tool schema and `context.get.tool_catalog['<tool>']`.
- Diagnostic fallback: `python3 scripts/turn_runtime.py status`.
- Broker method remains `env.tool`; do not edit runtime state files directly.
```

- [ ] For `message-tool`, keep a workflow sequence with native action names:
  - `message__contacts` to find current online targets;
  - copy `contact.actor_address` into `target_actor_address`;
  - `message__send` for direct messages;
  - `message__list` for active actor inbox;
  - `message__conversation` for bidirectional context;
  - `request__list` for request filtering.

- [ ] For `task-management`, keep task flow names:
  - `task__current`;
  - `task__propose`;
  - `task__confirm`.

- [ ] For `track-tool`, keep publication flow names:
  - `track__open`;
  - `artifact__get`;
  - `track__add_material`;
  - `track__add_proof`;
  - `track__add_update`;
  - `track__update_now`.

- [ ] Run GREEN:

```bash
python3 -m pytest tests/test_runtime_skills.py -k "shared_tool or shared_message" -q
```

## Task 5: Convert Buddy AGENTS And Role Contract Tests

- [ ] Update AGENTS/contract tests before editing guidance:
  - `tests/test_runtime_skills.py::test_buddy_agents_do_not_present_authoritative_hardcoded_tool_lists`
  - `tests/test_repo_consistency.py::test_runtime_buddy_agents_use_payload_env_client_guidance`
  - `tests/test_repo_consistency.py::test_runtime_buddy_agents_do_not_embed_project_source_facts`
  - `tests/test_repo_consistency.py::test_contracts_and_buddy_agents_point_to_runtime_discovery`
  - `tests/test_host_decision_surface_product_mode.py::test_pm_page_prototype_decision_surface_prefers_direct_private_buddybox_directory_without_phrase_rule`
  - `tests/test_buddyswitch_launcher.py` copied-AGENTS assertions around product instance startup.

Required native AGENTS assertions:

```python
self.assertIn("start with the native buddyswitch env context summary tool", text)
self.assertIn("prefer native buddyswitch env mcp tools", text)
self.assertIn("context.get.tool_catalog", text)
self.assertIn("python3 scripts/turn_runtime.py status", text)
self.assertIn("do not bypass runtime", text)
self.assertNotIn("python3 scripts/env/client.py", text)
self.assertNotIn("context summarize --payload", text)
self.assertNotIn("search open-browser --payload", text)
```

Required contract assertions:

```python
self.assertIn("native buddyswitch env mcp tools", text)
self.assertIn("context.get.tool_catalog", text)
self.assertIn("python3 scripts/turn_runtime.py status", text)
self.assertNotIn("python3 scripts/env/client.py", text)
```

- [ ] Run focused RED:

```bash
python3 -m pytest \
  tests/test_runtime_skills.py::RuntimeSkillsTests::test_buddy_agents_do_not_present_authoritative_hardcoded_tool_lists \
  tests/test_repo_consistency.py -k "runtime_buddy_agents or contracts_and_buddy_agents_point_to_runtime_discovery" \
  tests/test_host_decision_surface_product_mode.py::HostDecisionSurfaceProductModeTests::test_pm_page_prototype_decision_surface_prefers_direct_private_buddybox_directory_without_phrase_rule \
  tests/test_buddyswitch_launcher.py -k "start_with_required_buddy_creates_product_instance" \
  -q
```

Expected: fail on current CLI-first AGENTS/contracts.

## Task 6: Rewrite Buddy AGENTS And Role Contracts

- [ ] For every `tools/launcher/assets/buddies/<buddy>/AGENTS.md`, replace the CLI command list with:

```markdown
- Start with the native BuddySwitch env context summary tool when runtime context is needed.
- Prefer native BuddySwitch env MCP tools for durable runtime state: `context__summarize`, `context__get`, `track__open`, `task__current`, `artifact__get`, `request__get`, `request__list`, `comment__resolve`, `search__status`, and `search__open_browser` as role authority allows.
- Use `context.get.tool_catalog` or `python3 scripts/turn_runtime.py status` only when exact schema or diagnostic fallback is needed.
- Do not edit projected runtime storage paths directly; use env tools.
```

- [ ] Keep role-specific output rules and boundary constraints.
- [ ] Remove the obsolete “buddybox env tools with `logical_name`” wording because buddybox is now direct `$BUDDYSWITCH_BUDDYBOX_DIR`.
- [ ] For every `framework/contracts/<role>.md`, replace runtime boundary/discovery with native-first wording and keep role action names as concepts, not commands.
- [ ] Run GREEN focused commands from Task 5.

## Task 7: Convert Market/Search Skill Tests And Skills

- [ ] Update market tests:
  - Rename/adjust `test_market_skills_use_payload_browser_entry` to require `search__open_browser`.
  - Update `test_market_p0_skills_preserve_runtime_evidence_boundaries` to require `search__open_browser` instead of `search open-browser --payload`.
  - Reject `python3 scripts/env/client.py` and `search open-browser --payload`.

- [ ] Run focused RED:

```bash
python3 -m pytest tests/test_runtime_skills.py -k "market_skills_use_native_browser_entry or market_p0_skills_preserve_runtime_evidence_boundaries" -q
```

- [ ] Replace each Market P0 skill search step:

```markdown
1. Before forming external market claims, use native `search__open_browser` with a focused query, then continue discovery in `chrome-devtools-cockpit` and keep the workflow browser-native.
```

- [ ] Replace each “Runtime execution uses env.tool through `python3 scripts/env/client.py ...`” line with:

```markdown
- Runtime execution uses native BuddySwitch env MCP tools through env.tool; use runtime discovery for exact schemas.
```

- [ ] Update `buddyswitch/skills/dev/enter-dev-workspace/SKILL.md`, `buddyswitch/skills/design/shape-prototype/SKILL.md`, and `buddyswitch/skills/test/smoke-test/SKILL.md` to use native-first wording.
- [ ] Run GREEN focused market tests.

## Task 8: Add Active Guidance Residual Scan

- [ ] Add `tests/test_repo_consistency.py::test_active_product_guidance_has_no_env_client_cli_first_examples`.
- [ ] Scan only active guidance paths, not CLI implementation/tests/history docs.
- [ ] Reject:
  - `python3 scripts/env/client.py`
  - `Fallback CLI`
  - `CLI Payload Rule`
  - `search open-browser --payload`
  - `context summarize --payload`
  - `context get --payload`
  - `message list --payload`

- [ ] Run focused RED before guidance edits are complete, or GREEN after Tasks 2/4/6/7 if already edited:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_active_product_guidance_has_no_env_client_cli_first_examples -q
```

## Task 9: Focused Verification

- [ ] Run pure/focused verification:

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

- [ ] Run launcher focused verification:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "mcp or codex_config or product_instance or start_with_required_buddy_creates_product_instance" -q
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex|chrome_devtools_cockpit_proxy.py" || true
```

## Task 10: Review And Completion Audit

- [ ] Run residual scan:

```bash
rg -n "python3 scripts/env/client.py|Fallback CLI|CLI Payload Rule|search open-browser --payload|context summarize --payload|context get --payload|message list --payload" \
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

- [ ] Inspect git status:

```bash
git status --short
```

- [ ] Confirm no changes were made on `main`.
- [ ] Confirm all tests/commands in Task 9 passed.
- [ ] Summarize remaining risk. If real product-message log validation is not run, state that as residual risk rather than claiming it.

## Phase 1 Self-Review

- Spec coverage: every memo task maps to Task 1-10; all active guidance surfaces listed in the memo are included.
- No transition compromise: active CLI-first examples are removed rather than allowlisted as co-primary fallback.
- Test integrity: tests assert product-facing behavior and residual scans, not implementation-specific string hacks.
- Resource safety: service-heavy verification is explicitly isolated and requires residual process checks.
- Executability: every task names files, required assertions/edits, exact commands, and expected red/green state.
