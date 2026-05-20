# Skill Tool Decoupling Alignment Test Plan

Date: 2026-05-20

Implementation plan: `docs/superpowers/plans/2026-05-20-skill-tool-decoupling-alignment.md`

Related architecture memo: `docs/memo/buddyswitch-parallel-modular-architecture.md`

## Goal

Prove that BuddySwitch skills and tool runtime are decoupled through runtime discovery: skills guide when and how to use capabilities, while per-tool packages and `env.tools.catalog` remain the authoritative source for action names, payload fields, semantics, CLI registration, handler mapping, and service execution.

## Test Design Rules

- Tests must start from skill/tool product requirements and architecture boundaries, not from incidental implementation details.
- Tests must not pass merely because a string was added to satisfy a narrow assertion while the runtime discovery path is broken.
- Runtime discovery tests must exercise real catalog/context/status paths, not copied expected dictionaries in test code.
- Skill prose tests may inspect text because the requirement is explicitly about what skills must and must not teach.
- Text tests must avoid brittle wording checks. They should enforce durable boundaries: required discovery references, forbidden schema mirrors, forbidden implementation paths, and stale payload examples.
- Boundary tests must reject old compatibility surfaces directly. Do not allow legacy registry imports, fallback catalogs, prompt-side schema tables, or dual documentation paths.
- Positive tests must prove the intended public behavior: skills point to runtime discovery, `context.get` exposes catalog outputs from `env.tools.catalog`, and `context.summarize` stays lightweight.
- Negative tests must prove bad states are caught: skill text embedding payload/schema tables, operation semantics mirrors, per-tool package internals, or historical tool fields must fail.
- Tests should be broad enough to catch future drift across all shared runtime tool skills, not only the currently changed files.
- Do not use docs text as proof of runtime behavior. Runtime behavior must be verified through existing catalog/context/status tests.

## Functional Requirement Model

R1. Shared runtime tool skills consume exact tool capability through runtime discovery, not prose-owned action/payload/schema tables.

R2. Shared runtime tool skills identify the stable discovery entrypoints: `context.get.tool_catalog['<tool>']`, `python3 scripts/turn_runtime.py status`, and runtime response fields. They may mention `context.summarize.tool_affordances` as a lightweight discovery surface.

R3. `context.get.operation_semantics` remains a runtime machine-readable discovery/result surface, but ordinary skill prose must not copy, explain, or table its structure.

R4. Skill prose must not reference per-tool package internals such as `contract.py`, `semantics.py`, `handlers.py`, `service.py`, `TOOL_SPEC`, `ACTION_SEMANTICS`, or `HANDLER_SPECS`.

R5. Skill prose, framework contracts, and buddy host instructions must not copy payload/action/return schema tables or headings.

R6. Known stale runtime fields and removed workflow surfaces must not reappear in skill guidance.

R7. Runtime `context.get` must expose `tool_catalog` and `operation_semantics` directly from `env.tools.catalog`.

R8. Runtime `context.summarize` must stay lightweight: it must not include full `tool_catalog` or full `operation_semantics`.

R9. `python3 scripts/turn_runtime.py status` must continue to expose the same tool catalog projection used by runtime context.

R10. The architecture memo must state the durable boundary: skills own workflow guidance; per-tool packages own tool contracts; shared runtime discovers/projects/routes/dispatches/formats.

R11. The architecture memo must not preserve old-stage planning language as the active target now that per-tool rebuild is complete.

R12. Existing per-tool independence and runtime response contract tests must remain green, proving the skill/tool decoupling layer did not weaken runtime architecture guarantees.

## Risk Model

| Risk | Why it matters | Required coverage |
| --- | --- | --- |
| Skill becomes a hidden tool registry | Tool changes would require skill edits and drift | R1, R4, R5 |
| Skill copies payload fields that later change | Agents send stale or ignored fields | R1, R5, R6 |
| Skill teaches internal package paths | Refactors break guidance despite stable runtime catalog | R4 |
| `operation_semantics` becomes prose documentation | Machine-readable semantics drift from copied human text | R3, R5 |
| Runtime catalog and context diverge | Skills discover one contract while runtime executes another | R7, R9 |
| Context summary gets too heavy | Agents overuse large catalog output on ordinary orientation paths | R8 |
| Architecture memo preserves historical stage language | Future agents follow old phased migration instead of completed boundary | R10, R11 |
| Guardrail tests become implementation-cheating tests | Tests pass while real skill/runtime behavior regresses | Test Design Rules, R7, R12 |

## Test Matrix

| ID | Requirement | File | Scenario | Main assertions |
| --- | --- | --- | --- | --- |
| ST1 | R1/R2 | `tests/test_runtime_skills.py` | Shared tool skills route exact contracts to runtime discovery | each shared tool skill names `context.get.tool_catalog['<tool>']` and `python3 scripts/turn_runtime.py status` |
| ST2 | R3 | `tests/test_runtime_skills.py` | Skills do not mirror operation semantics | shared tool skill prose does not contain `operation_semantics`, except if explicitly scoped to "do not copy" in architecture docs outside skill files |
| ST3 | R4 | `tests/test_runtime_skills.py` | Skills do not reference per-tool internals | shared tool skills omit `scripts/env/tools/`, `contract.py`, `semantics.py`, `handlers.py`, `service.py`, `TOOL_SPEC`, `ACTION_SEMANTICS`, and `HANDLER_SPECS` |
| ST4 | R5 | `tests/test_runtime_skills.py` | Skills do not embed schema/table blocks | shared tool skills omit `**Payload:**`, `**Returns:**`, `## Payload Examples`, `## Operations`, action/payload markdown tables, `payload_fields`, and `action_semantics` |
| ST5 | R6 | `tests/test_runtime_skills.py` | Removed/stale tool fields do not reappear | task skill omits `buddy` and `active_buddy` payload guidance; track/artifact skills omit removed direct publication fields; message/comment skills omit non-goal surfaces outside "Do not" context |
| DOC1 | R10/R11 | `tests/test_repo_consistency.py` | Architecture memo states current boundary | memo includes runtime discovery as stable connection, per-tool package ownership, no prompt-side contract mirror, and no active old first-stage rollout section |
| DOC2 | R5/R10 | `tests/test_repo_consistency.py` | Broader prose surfaces do not copy schemas | `buddyswitch/skills`, `framework/contracts`, and buddy `AGENTS.md` omit schema mirrors and point users to runtime discovery |
| CAT1 | R7 | `tests/test_env_tool_response_contract.py` | `context.get` catalog equals runtime catalog | broker-routed `context.get` returns `tool_catalog == env.tools.catalog.env_tools_description()` and `operation_semantics == env.tools.catalog.operation_semantics()` |
| CAT2 | R8 | `tests/test_env_tool_response_contract.py` | `context.summarize` stays lightweight | broker-routed `context.summarize` omits full `tool_catalog` and full `operation_semantics` |
| CAT3 | R9 | `tests/test_turn_runtime.py` or existing response contract | Runtime status uses same catalog projection | `turn_runtime._build_env_tools_desc()` equals `env.tools.catalog.env_tools_description()` |
| CAT4 | R1/R7 | `tests/test_env_tool_semantic_contract.py` | Catalog remains sufficient for thin skills | every tool/action has payload fields and meaningful action semantics through catalog projection |
| ARCH1 | R12 | `tests/test_env_tool_package_independence.py` | Per-tool runtime independence remains intact | no central registry/semantics/handler maps, public imports are service-light, selected dispatch imports no sibling service |
| ARCH2 | R12 | `tests/test_env_layer_boundaries.py` | Product coupling remains explicit | cross-object behavior stays in approved domain modules; no old `env.services` tool entrypoints |
| REG1 | R1-R12 | Full focused gate | Skill/tool decoupling integration | runtime skill, repo consistency, response, semantic, payload, package independence, and boundary suites pass together |
| REG2 | R1-R12 | Full suite | Complete regression | `python3 -m pytest -q` and `git diff --check` pass |

## Detailed Test Designs

### ST1: Shared Tool Skills Route Exact Contracts To Runtime Discovery

Functional basis:

Skills may teach workflow judgment, but exact action and payload knowledge belongs to runtime discovery.

Test location:

`tests/test_runtime_skills.py`

Shared tool set:

```python
{
    "task": "buddyswitch/skills/shared/task-tool/SKILL.md",
    "track": "buddyswitch/skills/shared/track-tool/SKILL.md",
    "artifact": "buddyswitch/skills/shared/artifact-tool/SKILL.md",
    "buddybox": "buddyswitch/skills/shared/buddybox-tool/SKILL.md",
    "message": "buddyswitch/skills/shared/message-tool/SKILL.md",
    "comment": "buddyswitch/skills/shared/comment-tool/SKILL.md",
}
```

Assertions:

- each file contains `env.tool`;
- each file contains `context.get.tool_catalog['<tool>']`;
- each file contains `python3 scripts/turn_runtime.py status`;
- each file tells users that runtime response fields are authoritative for effects, recovery, or verification.

Focused command:

```bash
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_shared_tool_skills_route_exact_fields_to_runtime_discovery -q
```

Failure proves a skill can drift into standalone prompt knowledge or omit the discovery path.

### ST2: Shared Tool Skills Do Not Mirror Operation Semantics

Functional basis:

`operation_semantics` is a runtime machine-readable surface. Ordinary shared tool skills must not copy or explain that table because copied semantics drift.

Test location:

`tests/test_runtime_skills.py`

Assertions:

- shared tool skill files under `buddyswitch/skills/shared/*-tool/SKILL.md` do not contain `operation_semantics`;
- architecture docs may mention `operation_semantics` only to define the runtime/prose boundary, not as a skill instruction copied into skill files.

Focused command:

```bash
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_shared_tool_skills_name_only_runtime_discovery_surfaces_for_exact_contracts -q
```

This is a prose-boundary test, not a runtime behavior test. Runtime behavior for `operation_semantics` is covered by CAT1.

### ST3: Shared Tool Skills Do Not Reference Per-Tool Internals

Functional basis:

Skills should survive runtime refactors as long as runtime discovery surfaces remain stable.

Test location:

`tests/test_runtime_skills.py`

Forbidden strings in shared tool skill files:

```text
scripts/env/tools/
contract.py
semantics.py
handlers.py
service.py
TOOL_SPEC
ACTION_SEMANTICS
HANDLER_SPECS
payload_fields
action_semantics
```

Assertions:

- none of these strings appear in shared tool skill files;
- the test reports file and tool id on failure.

Focused command:

```bash
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_shared_tool_skills_name_only_runtime_discovery_surfaces_for_exact_contracts -q
```

### ST4: Shared Tool Skills Do Not Embed Schema Or Operation Blocks

Functional basis:

Skills can include minimal examples for usage, but they must not become API reference pages.

Test location:

`tests/test_runtime_skills.py`

Forbidden prose patterns:

```text
**Payload:**
**Returns:**
## Payload Examples
## Operations
|- action - payload style tables
payload_fields
action_semantics
```

Assertions:

- no shared tool skill contains schema/table headings;
- no shared tool skill contains action/payload markdown table patterns;
- minimal CLI examples remain allowed only as examples, not exhaustive schema copies.

Focused command:

```bash
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_shared_tool_skills_do_not_duplicate_runtime_action_catalogs -q
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_shared_tool_skills_do_not_embed_payload_or_return_schema_blocks -q
```

### ST5: Removed Or Stale Tool Fields Do Not Reappear

Functional basis:

The original drift problem included stale or ignored payload fields. Skill guidance must not reintroduce them after runtime repair.

Test location:

`tests/test_runtime_skills.py`

Assertions:

- `task-tool` does not contain task owner override guidance such as `"buddy"` or `"active_buddy"` in `task.create` examples;
- `track-tool` and `artifact-tool` do not contain `published_to_track`, `content.prd`, or `kind=prd`;
- shared tool skills do not teach `track.advance`;
- message/comment skills keep non-goals such as broadcast, read receipts, task comments, resolve/reopen, edit, and delete out of positive guidance.

Focused command:

```bash
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_runtime_contract_not_shared_skill_owns_inactive_actions -q
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_pm_and_shared_tool_skills_describe_single_publication_path -q
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_message_comment_shared_tool_skills_stay_atomic -q
```

### DOC1: Architecture Memo States Current Boundary

Functional basis:

The architecture memo is durable guidance. It must describe the post-rebuild state, not a historical migration phase.

Test location:

`tests/test_repo_consistency.py`

Assertions:

- `docs/memo/buddyswitch-parallel-modular-architecture.md` includes the stable connection rule that skills consume runtime discovery;
- the memo names `context.get.tool_catalog` and `python3 scripts/turn_runtime.py status`;
- the memo states that per-tool packages own tool-specific contract, semantics, CLI, handler, and service surfaces;
- the memo states that skills do not copy runtime contracts;
- the memo still rejects workflow engines, plugin systems, event buses, and generic object frameworks;
- the memo no longer presents the old "first stage" extraction order as the active plan.

Focused command:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_parallel_modular_architecture_memo_documents_current_skill_tool_boundary -q
```

This test is intentionally documentation-oriented because the requirement is durable guidance clarity.

### DOC2: Broader Prose Surfaces Do Not Copy Runtime Schemas

Functional basis:

Skills, role contracts, and buddy host instructions are all prompt surfaces. None should become schema mirrors.

Test location:

`tests/test_repo_consistency.py`

Scan targets:

```text
buddyswitch/skills
framework/contracts
tools/launcher/assets/buddies
```

Forbidden patterns:

```text
payload_fields
action_semantics
operation_semantics
TOOL_SPEC
ACTION_SEMANTICS
HANDLER_SPECS
scripts/env/tools/.*/contract.py
scripts/env/tools/.*/semantics.py
scripts/env/tools/.*/handlers.py
scripts/env/tools/.*/service.py
markdown action/payload tables
**Payload:**
**Returns:**
## Payload Examples
## Operations
```

Assertions:

- grep-style scan returns no hits;
- framework contracts and buddy `AGENTS.md` continue pointing users to `context summarize` and `context get`.

Focused command:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_skill_and_contract_texts_do_not_copy_payload_field_or_schema_tables -q
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_contracts_and_buddy_agents_point_to_runtime_discovery -q
```

### CAT1: `context.get` Catalog Equals Runtime Catalog

Functional basis:

If skills depend on runtime discovery, `context.get` must expose the same catalog projection as the runtime catalog source.

Test location:

`tests/test_env_tool_response_contract.py`

Scenario:

- create a runtime instance;
- broker-dispatch `context.get`;
- broker-dispatch `context.summarize`.

Assertions for `context.get`:

```python
full["tool_catalog"] == env.tools.catalog.env_tools_description()
full["operation_semantics"] == env.tools.catalog.operation_semantics()
full["tool_catalog"] == turn_runtime._build_env_tools_desc()
```

Assertions for `context.summarize`:

```python
"tool_catalog" not in summary
"operation_semantics" not in summary
```

Focused command:

```bash
python3 -m pytest tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_context_get_and_summarize_catalog_scope -q
```

This test must use broker-routed runtime calls, not direct context service helper calls.

### CAT2: `context.summarize` Stays Lightweight

Functional basis:

Skills may start with context summarize for orientation, but full action/payload knowledge must come from explicit runtime discovery.

Test location:

`tests/test_env_tool_response_contract.py`

Assertions:

- summary response succeeds;
- summary response contains compact orientation data, such as available sections or affordances when currently supported;
- summary response does not include full `tool_catalog`;
- summary response does not include full `operation_semantics`.

Focused command:

```bash
python3 -m pytest tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_context_get_and_summarize_catalog_scope -q
```

### CAT3: Runtime Status Uses The Same Catalog Projection

Functional basis:

Skills can use `python3 scripts/turn_runtime.py status` as an alternate discovery path, so it must not drift from `env.tools.catalog`.

Test location:

`tests/test_turn_runtime.py` or existing response contract coverage.

Assertions:

- status tool list equals `env.tools.catalog.supported_tools()`;
- status env tool description equals `env.tools.catalog.env_tools_description()`;
- removed surfaces such as handoff/memory/run remain absent.

Focused command:

```bash
python3 -m pytest tests/test_turn_runtime.py -q
```

### CAT4: Catalog Is Rich Enough For Thin Skills

Functional basis:

If skills are thin, catalog rows must contain enough machine-readable guidance for action selection, payload shaping, and recovery.

Test location:

`tests/test_env_tool_semantic_contract.py`

Assertions:

- every shipped tool appears in `catalog.env_tools_description()`;
- every action appears in `operations`;
- every action has payload fields from its per-tool contract;
- every action has semantic guidance fields: `use_when`, `do_not_use_when`, `inputs_explained`, `common_failures`, `success_means`, and `risk_hints`;
- `catalog.operation_semantics()` includes `kind`, `mutates`, `required_permission`, `authority`, `requires`, `returns`, and `risk_hints` for every action.

Focused command:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py -q
```

### ARCH1: Per-Tool Runtime Independence Remains Intact

Functional basis:

Skill/tool decoupling depends on per-tool packages being the runtime source of truth. The alignment work must not weaken the completed rebuild.

Test location:

`tests/test_env_tool_package_independence.py`

Assertions:

- shipped tool packages still own required files;
- no central ownership tables remain;
- public imports are service-light;
- catalog projection does not import services, repos, or domains;
- selected dispatch imports only selected tool service;
- broken non-selected metadata/service does not block unrelated healthy dispatch.

Focused command:

```bash
python3 -m pytest tests/test_env_tool_package_independence.py -q
```

### ARCH2: Product Coupling Remains Explicit

Functional basis:

Skill/tool decoupling must not accidentally hide real product coupling or reintroduce tool-to-tool imports.

Test location:

`tests/test_env_layer_boundaries.py`

Assertions:

- track/artifact publication coupling remains in explicit domain modules;
- comment target readability remains in explicit domain modules;
- tool packages do not import sibling tool packages;
- old `env.services` tool entrypoints remain removed;
- object repos do not import sibling object repos.

Focused command:

```bash
python3 -m pytest tests/test_env_layer_boundaries.py -q
```

## Coverage Analysis

| Requirement | Covered by | Coverage notes |
| --- | --- | --- |
| R1 | ST1, ST4, DOC2, CAT4 | Proves skills point to discovery and catalog has enough information to support thin skills |
| R2 | ST1, CAT3 | Proves both primary discovery paths are named and status remains catalog-backed |
| R3 | ST2, CAT1, DOC2 | Separates runtime machine semantics from prose mirrors |
| R4 | ST3, DOC2 | Prevents skill dependence on implementation file paths or symbols |
| R5 | ST4, DOC2 | Prevents action/payload/schema table drift across all prompt surfaces |
| R6 | ST5 | Protects known escaped stale-field defects |
| R7 | CAT1 | Uses broker-routed context path and real catalog source |
| R8 | CAT2 | Protects summarize as lightweight orientation |
| R9 | CAT3 | Protects `turn_runtime.py status` as a discovery route |
| R10 | DOC1 | Ensures durable architecture memo matches current design |
| R11 | DOC1 | Ensures historical rollout language is not active guidance |
| R12 | ARCH1, ARCH2, REG1, REG2 | Ensures alignment does not weaken per-tool rebuild boundaries |

No requirement relies on a single assertion. Requirements that touch prompt surfaces use text guardrails; requirements that touch runtime behavior use broker/catalog/status tests.

## Verification Commands

Focused skill/prose verification:

```bash
python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

Runtime discovery verification:

```bash
python3 -m pytest tests/test_env_tool_response_contract.py tests/test_turn_runtime.py tests/test_env_tool_semantic_contract.py -q
```

Architecture regression verification:

```bash
python3 -m pytest tests/test_env_tool_package_independence.py tests/test_env_layer_boundaries.py -q
```

Full verification:

```bash
python3 -m pytest -q
git diff --check
```

## Done Criteria

The test plan is satisfied only when:

1. every listed focused test exists or is already covered by an equivalent existing test;
2. every requirement R1-R12 maps to at least two meaningful assertions unless the requirement is purely documentation clarity;
3. shared tool skills cannot copy runtime contracts without a failing test;
4. runtime catalog/context/status cannot drift without a failing test;
5. per-tool independence tests remain green;
6. full `python3 -m pytest -q` passes;
7. `git diff --check` passes.
