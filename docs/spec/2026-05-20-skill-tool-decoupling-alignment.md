# Skill Tool Decoupling Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make BuddySwitch skills consume env.tool capability through runtime catalog discovery only, while per-tool packages remain the source of truth for actions, payload fields, semantics, CLI registration, handler mapping, and service execution.

**Architecture:** Keep the completed per-tool rebuild as the runtime foundation. Add a thin documentation and test layer that defines runtime discovery and env.tool responses as the stable skill/tool interface. Shared tool skills should normally name `context.get.tool_catalog`, `context.summarize.tool_affordances`, runtime responses, and `python3 scripts/turn_runtime.py status`; `context.get.operation_semantics` remains a runtime catalog surface but must not be copied into prose tables. Do not introduce a second registry, prompt-side schema mirror, plugin framework, workflow engine, or compatibility surface.

**Tech Stack:** Markdown docs and skills, Python 3.9-compatible `unittest`/`pytest`, `rg`, existing `env.tools.catalog`, existing runtime skill/repo consistency tests.

---

## Source Inputs

- `docs/memo/buddyswitch-parallel-modular-architecture.md`
- `docs/spec/2026-05-20-per-tool-independence-rebuild-scope.md`
- `docs/spec/2026-05-20-per-tool-independence-rebuild-implementation-plan.md`
- `scripts/env/tools/catalog.py`
- `scripts/env/tools/*/contract.py`
- `scripts/env/tools/*/semantics.py`
- `buddyswitch/skills/shared/*-tool/SKILL.md`
- `tests/test_runtime_skills.py`
- `tests/test_repo_consistency.py`
- `tests/test_env_tool_response_contract.py`

## External Practice Summary

Use these as rationale, not runtime dependencies:

- MCP exposes tools through `tools/list` with schemas and annotations; prompts are a separate surface. See `https://modelcontextprotocol.io/specification/2025-06-18/server/tools`.
- OpenAI MCP/Apps SDK keeps tool descriptors and execution server-side; model-facing guidance consumes those descriptors. See `https://developers.openai.com/api/docs/guides/tools-connectors-mcp`.
- Claude/Agent Skills are instructions, workflows, and resources; they should not become tool registries or schema mirrors. See `https://claude.com/docs/skills/overview` and `https://agentskills.io/skill-creation/best-practices`.

## File Structure

- Modify `docs/memo/buddyswitch-parallel-modular-architecture.md`
  - Owns durable architecture guidance.
  - Add the precise skill/tool interface rule now that per-tool rebuild is complete.

- Modify `tests/test_runtime_skills.py`
  - Owns skill-specific runtime contract tests.
  - Add checks that shared runtime tool skills reference the stable discovery surfaces and do not import or mirror per-tool package internals.

- Modify `tests/test_repo_consistency.py`
  - Owns broad prose/document consistency checks.
  - Extend schema-copy checks so prose cannot reintroduce prompt-side action/payload/semantics tables.

- Optionally modify `buddyswitch/skills/shared/*-tool/SKILL.md`
  - Only if tests expose stale payload/action prose.
  - Keep examples minimal and workflow-oriented; do not add exhaustive action tables.

## Task 1: Document The Stable Skill/Tool Interface

**Files:**
- Modify: `docs/memo/buddyswitch-parallel-modular-architecture.md`

- [x] **Step 1: Add the architecture section**

Insert this section after the existing `分层边界` section and before `外部实践依据`:

```markdown
## SKILL / Tool Contract 衔接规则

`SKILL` 和 `tool` 的稳定衔接面只有 runtime discovery：

```text
context.get.tool_catalog
context.get.operation_semantics
context.summarize.tool_affordances
python3 scripts/turn_runtime.py status
runtime env.tool response fields
```

普通 shared tool skills 默认引用 `context.get.tool_catalog['<tool>']`、`context.summarize.tool_affordances`、`python3 scripts/turn_runtime.py status` 和 runtime response fields。`context.get.operation_semantics` 是 runtime 可暴露的机器语义投影，可用于 runtime verification 和高级诊断；不要在 skill prose 中复制或解释它的表结构。

`SKILL` 可以写：

- 什么时候使用某类 tool；
- 如何判断当前 workflow 需要哪种能力；
- 先查哪些 runtime discovery 面；
- 成功后如何验证 `ok`、`state_changed`、`state_changes`、returned ids；
- 失败后如何读取 `permission_boundary`、`why_blocked`、`retry_guidance`、`allowed_next_actions`、`alternative_capabilities`。

`SKILL` 不能写：

- action / payload / return schema 表；
- per-tool package 内部路径；
- dispatch、handler、service 入口；
- object repo 路径或 JSON 存储结构；
- 与 runtime catalog 不一致的 payload 示例。

每个 tool 的契约来源是：

```text
scripts/env/tools/<tool>/contract.py
scripts/env/tools/<tool>/semantics.py
scripts/env/tools/<tool>/cli.py
scripts/env/tools/<tool>/handlers.py
scripts/env/tools/<tool>/service.py
```

shared runtime 只负责发现、投影、路由、dispatch、response formatting。`SKILL` 通过 catalog 消费能力，不复制能力。
```

- [x] **Step 2: Replace the first-stage rollout wording**

Replace the old `第一阶段落地` section with:

```markdown
## 已落地基础

`per-tool independence rebuild` 完成后，tool-specific ownership 已收敛到：

```text
scripts/env/tools/<tool>/
  contract.py
  semantics.py
  cli.py
  handlers.py
  service.py
```

central `TOOL_REGISTRY`、central semantics table、central handler map、central per-tool CLI dispatch branch、`env.services` tool entrypoint 都不再是 runtime API。

接下来维护的边界是：

1. 新增或修改 tool action，只改对应 tool package 和该 tool 的 focused tests。
2. 修改 shared / buddy-specific `SKILL`，不改 Python runtime。
3. `SKILL` 通过 runtime discovery 获取精确 action、payload、semantics、response guidance；普通 shared tool skills 不复制或讲解 `operation_semantics` 表结构。
4. cross-object product coupling 仍然只允许在 explicit domain modules 中出现。
```

- [x] **Step 3: Update completion standard**

Replace the existing `完成标准` section with:

```markdown
## 完成标准

架构边界成立必须同时满足：

1. 新增或修改一个 tool action，不需要改 shared SKILL。
2. 修改一个 buddy-specific 或 shared SKILL，不需要改 Python runtime。
3. shared tool skills 都指向 `context.get.tool_catalog['<tool>']` 或 `python3 scripts/turn_runtime.py status` 获取精确 payload / action / response guidance。
4. prose 文档和 SKILL 不复制 `payload_fields`、`action_semantics`、`operation_semantics`、action/payload 表。
5. `context.get` 返回的 `tool_catalog` 和 `operation_semantics` 等于 `env.tools.catalog` 的投影；`operation_semantics` 只作为 runtime discovery/result surface，不作为 skill prose mirror。
6. catalog projection 不 import service、domain、repo。
7. selected dispatch 不 import sibling tool service。
8. object repo 没有 sibling repo import。
9. `track/artifact/comment` 的真实产品耦合保留在 explicit domain modules。
10. `python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py tests/test_env_tool_response_contract.py -q` 通过。
```

- [x] **Step 4: Verify the doc is concise**

Run:

```bash
rg -n "workflow engine|plugin system|event bus|SKILL / Tool Contract|runtime discovery|payload_fields|action_semantics" docs/memo/buddyswitch-parallel-modular-architecture.md
```

Expected:

- The memo still explicitly rejects workflow/plugin/event abstractions.
- The new section mentions runtime discovery.
- `payload_fields` and `action_semantics` appear only in the context of forbidding prose mirrors or describing verification.

## Task 2: Add Runtime Discovery Surface Tests For Shared Tool Skills

**Files:**
- Modify: `tests/test_runtime_skills.py`

- [x] **Step 1: Add shared helper constants near the top of the test class**

Add this inside `RuntimeSkillsTests`, before the first test method:

```python
    SHARED_TOOL_SKILLS = {
        "task": ROOT / "buddyswitch/skills/shared/task-tool/SKILL.md",
        "track": ROOT / "buddyswitch/skills/shared/track-tool/SKILL.md",
        "artifact": ROOT / "buddyswitch/skills/shared/artifact-tool/SKILL.md",
        "buddybox": ROOT / "buddyswitch/skills/shared/buddybox-tool/SKILL.md",
        "message": ROOT / "buddyswitch/skills/shared/message-tool/SKILL.md",
        "comment": ROOT / "buddyswitch/skills/shared/comment-tool/SKILL.md",
    }
```

- [x] **Step 2: Replace repeated local skill path lists where straightforward**

For tests that currently create the same six shared skill paths inline, replace the list with:

```python
        skill_paths = list(self.SHARED_TOOL_SKILLS.values())
```

Do not change tests whose expected set intentionally differs, such as message/comment-only tests.

- [x] **Step 3: Add the discovery-surface test**

Add this test after `test_shared_tool_skills_route_exact_fields_to_runtime_discovery`:

```python
    def test_shared_tool_skills_name_only_runtime_discovery_surfaces_for_exact_contracts(self) -> None:
        required_refs = (
            "context.get.tool_catalog",
            "python3 scripts/turn_runtime.py status",
        )
        accepted_contract_refs = (
            "context.get.tool_catalog",
            "context.summarize.tool_affordances",
            "python3 scripts/turn_runtime.py status",
            "runtime response fields",
        )
        forbidden_refs = (
            "scripts/env/tools/",
            "contract.py",
            "semantics.py",
            "handlers.py",
            "service.py",
            "payload_fields",
            "action_semantics",
            "TOOL_SPEC",
            "ACTION_SEMANTICS",
        )
        for tool, path in self.SHARED_TOOL_SKILLS.items():
            text = path.read_text(encoding="utf-8")
            lowered = text.lower()
            with self.subTest(tool=tool):
                for required in required_refs:
                    self.assertIn(required, text)
                self.assertTrue(
                    any(ref in text for ref in accepted_contract_refs),
                    msg=f"{path.relative_to(ROOT)} does not route exact contract knowledge to runtime discovery",
                )
                for forbidden in forbidden_refs:
                    self.assertNotIn(forbidden.lower(), lowered)
```

- [x] **Step 4: Run the focused test**

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_shared_tool_skills_name_only_runtime_discovery_surfaces_for_exact_contracts -q
```

Expected before any needed skill cleanup:

- PASS if all shared skills already obey the rule.
- FAIL naming the exact stale string if a skill still mirrors package internals or catalog field names.

## Task 3: Add Prose Mirror Guardrails For Runtime Docs And Skills

**Files:**
- Modify: `tests/test_repo_consistency.py`

- [x] **Step 1: Extend the schema-copy regex**

In `test_skill_and_contract_texts_do_not_copy_payload_field_or_schema_tables`, extend the regex expression to include per-tool package internals and common schema mirror headings:

```python
                (
                    "payload_fields"
                    + "|action_semantics"
                    + "|operation_semantics"
                    + "|TOOL_SPEC"
                    + "|ACTION_SEMANTICS"
                    + "|HANDLER_SPECS"
                    + "|scripts/env/tools/.*/contract\\.py"
                    + "|scripts/env/tools/.*/semantics\\.py"
                    + "|scripts/env/tools/.*/handlers\\.py"
                    + "|scripts/env/tools/.*/service\\.py"
                    + "|\\|\\s*tool\\s*\\|\\s*action\\s*\\|\\s*payload"
                    + "|\\|\\s*action\\s*\\|\\s*payload"
                    + "|\\*\\*payload:\\*\\*"
                    + "|\\*\\*returns:\\*\\*"
                    + "|##\\s*payload\\s+examples"
                    + "|##\\s*operations"
                ),
```

- [x] **Step 2: Add architecture memo exception handling if needed**

This test currently scans:

```python
targets = [
    "buddyswitch/skills",
    "framework/contracts",
    "tools/launcher/assets/buddies",
]
```

Do not add `docs/memo` to this broad test, because the architecture memo must be allowed to name implementation paths while describing boundaries.

- [x] **Step 3: Run the focused repo consistency test**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_skill_and_contract_texts_do_not_copy_payload_field_or_schema_tables -q
```

Expected:

- PASS if prose surfaces already avoid contract mirrors.
- FAIL with exact file/line hits if stale schema mirrors remain.

## Task 4: Clean Any Skill Prose That Fails The New Guardrails

**Files:**
- Modify only failing files under `buddyswitch/skills/shared/*-tool/SKILL.md`
- Do not modify Python runtime files in this task.

- [x] **Step 1: Inspect failing lines**

Run the failing test command again with full output:

```bash
python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py::RepoConsistencyTests::test_skill_and_contract_texts_do_not_copy_payload_field_or_schema_tables -q
```

Expected:

- If green, skip to Task 5.
- If red, use the file/line output to edit only the stale prose.

- [x] **Step 2: Apply this rewrite pattern**

For stale action/payload prose, use this pattern:

```markdown
- For exact operations, payload keys, optional keys, return fields, effects, and recovery guidance, inspect `context.get.tool_catalog['<tool>']` or `python3 scripts/turn_runtime.py status`.
```

For stale response schema prose, use this pattern:

```markdown
- Runtime response fields are authoritative. On success, verify `ok`, returned ids, `state_changed`, and `state_changes` where present. On rejection, follow `permission_boundary`, `why_blocked`, `retry_guidance`, `allowed_next_actions`, and `alternative_capabilities`.
```

For stale implementation-path prose, use this pattern:

```markdown
- Do not depend on implementation file paths; use runtime discovery and env.tool responses.
```

- [x] **Step 3: Verify no direct schema mirror remains**

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py::RepoConsistencyTests::test_skill_and_contract_texts_do_not_copy_payload_field_or_schema_tables -q
```

Expected: PASS.

## Task 5: Prove Catalog Is The Runtime Source For Skill Discovery

**Files:**
- Modify: `tests/test_env_tool_response_contract.py`
- Do not edit if the existing assertions already match the code below.

- [x] **Step 1: Confirm current context catalog equality test**

Run:

```bash
python3 -m pytest tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_context_get_and_summarize_catalog_scope -q
```

Expected: PASS.

- [x] **Step 2: Replace weak assertions directly if needed**

If Step 1 fails because the context catalog assertions are weaker or incomplete, replace that assertion block with exactly:

```python
        expected_tool_catalog = tool_catalog.env_tools_description()
        expected_operation_semantics = tool_catalog.operation_semantics()
        self.assertIn("tool_catalog", full)
        self.assertIn("operation_semantics", full)
        self.assertEqual(full.get("tool_catalog"), expected_tool_catalog)
        self.assertEqual(full.get("tool_catalog"), turn_runtime._build_env_tools_desc())
        self.assertEqual(full.get("operation_semantics"), expected_operation_semantics)
        self.assertNotIn("tool_catalog", summary)
        self.assertNotIn("operation_semantics", summary)
```

Do not add a second catalog path.

- [x] **Step 3: Run the focused response test**

Run:

```bash
python3 -m pytest tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_context_get_and_summarize_catalog_scope -q
```

Expected: PASS.

## Task 6: Run The Integration Gate

**Files:**
- No production edits expected.
- Fix only files directly implicated by failing tests.

- [x] **Step 1: Run skill and prose guardrails**

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

Expected: PASS.

- [x] **Step 2: Run catalog and response guardrails**

Run:

```bash
python3 -m pytest tests/test_env_tool_response_contract.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_payload_contract.py -q
```

Expected: PASS.

- [x] **Step 3: Run architecture independence guardrails**

Run:

```bash
python3 -m pytest tests/test_env_tool_package_independence.py tests/test_env_layer_boundaries.py -q
```

Expected: PASS.

- [x] **Step 4: Run full verification**

Run:

```bash
python3 -m pytest -q
git diff --check
```

Expected: PASS.

Do not claim completion if any skill/catalog/runtime response or architecture independence test remains red.

## Self-Review

- Spec coverage: The plan covers the community practice summary, BuddySwitch skill/tool boundary, per-tool package compatibility, runtime discovery as the stable interface, skill prose cleanup, and verification.
- Placeholder scan: No placeholder markers or open-ended “add tests” steps remain.
- Type consistency: Test names and imported modules use existing `RuntimeSkillsTests`, `RepoConsistencyTests`, `EnvToolResponseContractTests`, and `env.tools.catalog`.
