# Design Buddy Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single `ia-spec` design buddy with a multi-skill `design` catalog for functional AI products, while keeping `switch design: ...` stable for users and explicitly deferring protocol-level guided intake.

**Architecture:** Reuse the existing BuddySwitch multi-skill runtime rather than adding a new routing layer. Promote `design` to a manifest-driven multi-skill buddy with one broad entry skill (`product-design-spec`), focused specialist refinement skills, and one review skill (`design-critique`); keep guided intake text-only inside `SKILL.md` and do not add a new interaction contract in this iteration.

**Tech Stack:** TOML skill metadata, Markdown skill packages, JSON output schemas, Python runtime tests (`unittest`), BuddySwitch manifest/runtime/contracts/docs.

---

## Constitution Guardrails

This iteration is constrained by `framework/docs/buddyswitch-development-constitution.md`.

- Focus one core problem only: redesign the `design` skill system.
- Replace, do not layer: delete `ia-spec` instead of carrying a long-lived compatibility shell.
- Keep the loop short: use the existing multi-skill runtime; do not introduce a new routing subsystem.
- Defer speculative work: no protocol-level `interaction_contract`, no option UI, no global buddy-wide wizard behavior in this batch.
- Keep outputs execution-oriented: every new skill package must have a schema, template, tests, and clear artifact slot semantics.

## Target Skill Catalog

The redesign should land this exact manifest order for `design`:

1. `product-design-spec`
2. `experience-shaping`
3. `activation-and-first-value`
4. `initiative-and-intervention`
5. `execution-boundaries`
6. `memory-and-context`
7. `conversation-and-clarity`
8. `recovery-and-escalation`
9. `design-critique`

### Slot and Input Contract

| Skill | Output Slot | Input Slots |
| --- | --- | --- |
| `product-design-spec` | `design-spec` | `prd`, `positioning-brief`, `launch-prep`, `requirements`, `track` |
| `experience-shaping` | `design-brief` | `prd`, `requirements`, `track` |
| `activation-and-first-value` | `activation-spec` | `prd`, `positioning-brief`, `launch-prep`, `design-spec`, `requirements`, `track` |
| `initiative-and-intervention` | `initiative-spec` | `prd`, `design-spec`, `requirements`, `track` |
| `execution-boundaries` | `boundaries-spec` | `prd`, `design-spec`, `requirements`, `track` |
| `memory-and-context` | `memory-spec` | `prd`, `design-spec`, `requirements`, `track` |
| `conversation-and-clarity` | `conversation-spec` | `prd`, `design-spec`, `requirements`, `track` |
| `recovery-and-escalation` | `recovery-spec` | `prd`, `design-spec`, `requirements`, `track` |
| `design-critique` | `design-review` | `design-spec`, `prd`, `requirements`, `track` |

### Explicit Non-Goals For This Batch

- No new `resolve` fields such as `interaction_mode` or `interaction_spec`
- No host UI integration for `options + other`
- No new buddy-wide hidden/internal-only skill mechanism
- No downstream `dev` contract rewrite beyond consuming the existing `design-spec` slot

## File Map

### Modify

- `buddyswitch/manifest.toml`
- `framework/contracts/design.md`
- `tests/test_switch_runtime.py`
- `tests/test_repo_consistency.py`
- `tests/test_artifact_selection.py`

### Create

- `buddyswitch/skills/design/product-design-spec/skill.toml`
- `buddyswitch/skills/design/product-design-spec/SKILL.md`
- `buddyswitch/skills/design/product-design-spec/assets/design-spec-template.md`
- `buddyswitch/skills/design/experience-shaping/skill.toml`
- `buddyswitch/skills/design/experience-shaping/SKILL.md`
- `buddyswitch/skills/design/experience-shaping/assets/design-brief-template.md`
- `buddyswitch/skills/design/activation-and-first-value/skill.toml`
- `buddyswitch/skills/design/activation-and-first-value/SKILL.md`
- `buddyswitch/skills/design/activation-and-first-value/assets/activation-spec-template.md`
- `buddyswitch/skills/design/initiative-and-intervention/skill.toml`
- `buddyswitch/skills/design/initiative-and-intervention/SKILL.md`
- `buddyswitch/skills/design/initiative-and-intervention/assets/initiative-spec-template.md`
- `buddyswitch/skills/design/execution-boundaries/skill.toml`
- `buddyswitch/skills/design/execution-boundaries/SKILL.md`
- `buddyswitch/skills/design/execution-boundaries/assets/boundaries-spec-template.md`
- `buddyswitch/skills/design/memory-and-context/skill.toml`
- `buddyswitch/skills/design/memory-and-context/SKILL.md`
- `buddyswitch/skills/design/memory-and-context/assets/memory-spec-template.md`
- `buddyswitch/skills/design/conversation-and-clarity/skill.toml`
- `buddyswitch/skills/design/conversation-and-clarity/SKILL.md`
- `buddyswitch/skills/design/conversation-and-clarity/assets/conversation-spec-template.md`
- `buddyswitch/skills/design/recovery-and-escalation/skill.toml`
- `buddyswitch/skills/design/recovery-and-escalation/SKILL.md`
- `buddyswitch/skills/design/recovery-and-escalation/assets/recovery-spec-template.md`
- `buddyswitch/skills/design/design-critique/skill.toml`
- `buddyswitch/skills/design/design-critique/SKILL.md`
- `buddyswitch/skills/design/design-critique/assets/design-review-template.md`
- `framework/schemas/design/product-design-spec.json`
- `framework/schemas/design/experience-shaping.json`
- `framework/schemas/design/activation-and-first-value.json`
- `framework/schemas/design/initiative-and-intervention.json`
- `framework/schemas/design/execution-boundaries.json`
- `framework/schemas/design/memory-and-context.json`
- `framework/schemas/design/conversation-and-clarity.json`
- `framework/schemas/design/recovery-and-escalation.json`
- `framework/schemas/design/design-critique.json`

### Delete

- `buddyswitch/skills/design/ia-spec/skill.toml`
- `buddyswitch/skills/design/ia-spec/SKILL.md`
- `buddyswitch/skills/design/ia-spec/assets/design-spec-template.md`
- `framework/schemas/design/ia-spec.json`

### Inspect Only Unless Tests Prove Otherwise

- `scripts/switch_runtime.py`
- `scripts/env_manifest.py`

The goal is to prove that the current runtime already supports the redesign. Do not modify these files unless a failing regression test demonstrates a design-specific assumption that cannot be satisfied via manifest, package, contract, or schema changes.

### Task 1: Convert `design` Into a Multi-Skill Buddy In Tests And Manifest

**Files:**
- Modify: `buddyswitch/manifest.toml`
- Modify: `tests/test_switch_runtime.py`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Write the failing design-catalog tests**

Add a new `ResolveRuntimeTests` case in `tests/test_switch_runtime.py` that asserts `switch design: ...` now resolves like `market`:

```python
def test_multi_skill_design_buddy_returns_no_implicit_skill(self) -> None:
    payload = switch_runtime.resolve_switch(
        "switch design: Produce a first-pass design for an AI-first workflow tool"
    )

    self.assertTrue(payload["ok"])
    self.assertEqual(payload["invocation"]["buddy"], "design")
    self.assertIsNone(payload["implicit_skill_id"])
    self.assertEqual(
        payload["eligible_skills"],
        [
            "product-design-spec",
            "experience-shaping",
            "activation-and-first-value",
            "initiative-and-intervention",
            "execution-boundaries",
            "memory-and-context",
            "conversation-and-clarity",
            "recovery-and-escalation",
            "design-critique",
        ],
    )
```

In `tests/test_repo_consistency.py`, replace every hard-coded `ia-spec` package expectation with the full design package set.

- [ ] **Step 2: Run the targeted tests to verify they fail on the current single-skill design buddy**

Run:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0040-design-buddy-redesign
python3 -m unittest tests.test_switch_runtime.ResolveRuntimeTests.test_multi_skill_design_buddy_returns_no_implicit_skill -v
python3 -m unittest tests.test_repo_consistency.RepoConsistencyTests.test_skill_packages_include_skill_toml_and_instruction_markdown -v
```

Expected:

- the runtime test fails because `implicit_skill_id == "ia-spec"`
- the repo consistency test fails because the new design package directories do not exist yet

- [ ] **Step 3: Update the manifest to the final design skill order**

Replace the current `design` buddy entry in `buddyswitch/manifest.toml` with:

```toml
[[buddies]]
id = "design"
label = "Design"
scope = "Design functional AI product behavior, flows, boundaries, and critique artifacts."
skills = [
  "product-design-spec",
  "experience-shaping",
  "activation-and-first-value",
  "initiative-and-intervention",
  "execution-boundaries",
  "memory-and-context",
  "conversation-and-clarity",
  "recovery-and-escalation",
  "design-critique",
]
permissions = ["track.read", "task.read", "task.create", "task.update", "task.archive", "artifact.read", "artifact.create", "artifact.update"]
```

- [ ] **Step 4: Re-run the same tests to confirm the manifest is now correct and failures only point at missing packages**

Run:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0040-design-buddy-redesign
python3 -m unittest tests.test_switch_runtime.ResolveRuntimeTests.test_multi_skill_design_buddy_returns_no_implicit_skill -v
python3 -m unittest tests.test_repo_consistency.RepoConsistencyTests.test_skill_packages_include_skill_toml_and_instruction_markdown -v
```

Expected:

- the runtime test still fails until package files exist
- the failure message should now be about missing `skill.toml` / `SKILL.md`, not about manifest skill order

- [ ] **Step 5: Commit the catalog boundary change**

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0040-design-buddy-redesign
git add buddyswitch/manifest.toml tests/test_switch_runtime.py tests/test_repo_consistency.py
git commit -m "refactor: promote design buddy to a multi-skill catalog"
```

### Task 2: Create The Broad Entry Skill And The Review Skill

**Files:**
- Create: `buddyswitch/skills/design/product-design-spec/skill.toml`
- Create: `buddyswitch/skills/design/product-design-spec/SKILL.md`
- Create: `buddyswitch/skills/design/product-design-spec/assets/design-spec-template.md`
- Create: `buddyswitch/skills/design/design-critique/skill.toml`
- Create: `buddyswitch/skills/design/design-critique/SKILL.md`
- Create: `buddyswitch/skills/design/design-critique/assets/design-review-template.md`
- Create: `framework/schemas/design/product-design-spec.json`
- Create: `framework/schemas/design/design-critique.json`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add failing file-existence and asset checks for the broad entry and review packages**

Update the `expected_packages` and `expected_assets` tuples in `tests/test_repo_consistency.py` so they include:

```python
ROOT / "buddyswitch" / "skills" / "design" / "product-design-spec",
ROOT / "buddyswitch" / "skills" / "design" / "design-critique",
ROOT / "buddyswitch" / "skills" / "design" / "product-design-spec" / "assets" / "design-spec-template.md",
ROOT / "buddyswitch" / "skills" / "design" / "design-critique" / "assets" / "design-review-template.md",
```

- [ ] **Step 2: Run the repo consistency checks and verify the new package assertions fail before creation**

Run:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0040-design-buddy-redesign
python3 -m unittest tests.test_repo_consistency.RepoConsistencyTests.test_template_references_are_materialized_in_assets -v
```

Expected:

- FAIL with missing `product-design-spec` and `design-critique` asset paths

- [ ] **Step 3: Create the broad entry skill package with text-only guided intake instructions**

Write `buddyswitch/skills/design/product-design-spec/skill.toml` as:

```toml
id = "product-design-spec"
buddy = "design"
description = "Use when the task is creating a first-pass product design specification for a functional AI product."
objects = ["task", "artifact"]
produces_artifact = true
output_slot = "design-spec"
input_slots = ["prd", "positioning-brief", "launch-prep", "requirements", "track"]
output_schema = "framework/schemas/design/product-design-spec.json"
produces = ["design-spec", "interaction-spec"]
consumes = ["prd", "positioning-brief", "launch-prep", "requirements", "track"]
side_effect_level = "medium"
required_tools = []
required_env = []
allowed_task_kinds = ["design"]
```

The `SKILL.md` must explicitly say:

- ask at most 3 text-only clarification questions when information is materially missing
- do not ask the user to choose internal skill names
- do not imply the existence of option UI or a runtime interaction protocol

Use this opening block:

```md
# product-design-spec

## Purpose
- Produce a first-pass product design specification for a functional AI product.

## Use when
- The user wants a design draft, not code or PM scope work.
- The request is broad enough that the design buddy should produce a coherent first version.
- The prompt is expressed in product language rather than internal design jargon.
```

Use this template skeleton in `assets/design-spec-template.md`:

```md
# Design Spec

## Product Frame
- user_job:
- success_moment:
- ai_role:

## Experience Shape
- core_loop:
- main_entry_points:
- main_failure_modes:

## Interaction Structure
- ia:
- primary_flows:
- key_screens:

## Control And Trust
- initiative_rules:
- execution_boundaries:
- recovery_paths:

## Notes
- interaction_notes:
- open_questions:
```

- [ ] **Step 4: Create the review skill package**

Write `buddyswitch/skills/design/design-critique/skill.toml` as:

```toml
id = "design-critique"
buddy = "design"
description = "Use when the task is reviewing an existing design artifact, flow, or implementation from a functional AI product experience perspective."
objects = ["task", "artifact"]
produces_artifact = true
output_slot = "design-review"
input_slots = ["design-spec", "prd", "requirements", "track"]
output_schema = "framework/schemas/design/design-critique.json"
produces = ["design-review"]
consumes = ["design-spec", "prd", "requirements", "track"]
side_effect_level = "medium"
required_tools = []
required_env = []
allowed_task_kinds = ["design-review"]
```

Use this schema shape in `framework/schemas/design/design-critique.json`:

```json
{
  "type": "object",
  "required": ["execution_summary", "working_notes", "deliverables_or_changed_files", "artifact_content"],
  "additionalProperties": false,
  "properties": {
    "execution_summary": { "type": "string" },
    "working_notes": { "type": "array", "items": { "type": "string" } },
    "deliverables_or_changed_files": { "type": "array", "items": { "type": "string" } },
    "artifact_content": {
      "type": "object",
      "required": ["findings", "strengths", "open_questions", "recommended_next_moves"],
      "additionalProperties": false,
      "properties": {
        "findings": { "type": "array", "items": { "type": "string" } },
        "strengths": { "type": "array", "items": { "type": "string" } },
        "open_questions": { "type": "array", "items": { "type": "string" } },
        "recommended_next_moves": { "type": "array", "items": { "type": "string" } }
      }
    }
  }
}
```

- [ ] **Step 5: Re-run the broad-entry and review-package tests**

Run:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0040-design-buddy-redesign
python3 -m unittest tests.test_repo_consistency.RepoConsistencyTests.test_skill_packages_include_skill_toml_and_instruction_markdown -v
python3 -m unittest tests.test_repo_consistency.RepoConsistencyTests.test_template_references_are_materialized_in_assets -v
```

Expected:

- package checks now pass for `product-design-spec` and `design-critique`
- failures, if any, should only mention the still-missing specialist packages

- [ ] **Step 6: Commit the broad entry and review packages**

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0040-design-buddy-redesign
git add buddyswitch/skills/design/product-design-spec buddyswitch/skills/design/design-critique framework/schemas/design/product-design-spec.json framework/schemas/design/design-critique.json tests/test_repo_consistency.py
git commit -m "feat: add broad entry and critique design skills"
```

### Task 3: Add The Specialist Design Skill Packages

**Files:**
- Create: `buddyswitch/skills/design/experience-shaping/**`
- Create: `buddyswitch/skills/design/activation-and-first-value/**`
- Create: `buddyswitch/skills/design/initiative-and-intervention/**`
- Create: `buddyswitch/skills/design/execution-boundaries/**`
- Create: `buddyswitch/skills/design/memory-and-context/**`
- Create: `buddyswitch/skills/design/conversation-and-clarity/**`
- Create: `buddyswitch/skills/design/recovery-and-escalation/**`
- Create: `framework/schemas/design/experience-shaping.json`
- Create: `framework/schemas/design/activation-and-first-value.json`
- Create: `framework/schemas/design/initiative-and-intervention.json`
- Create: `framework/schemas/design/execution-boundaries.json`
- Create: `framework/schemas/design/memory-and-context.json`
- Create: `framework/schemas/design/conversation-and-clarity.json`
- Create: `framework/schemas/design/recovery-and-escalation.json`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Extend repo consistency expectations to the full specialist set**

Update `tests/test_repo_consistency.py` to include all specialist package roots and asset files:

```python
ROOT / "buddyswitch" / "skills" / "design" / "experience-shaping",
ROOT / "buddyswitch" / "skills" / "design" / "activation-and-first-value",
ROOT / "buddyswitch" / "skills" / "design" / "initiative-and-intervention",
ROOT / "buddyswitch" / "skills" / "design" / "execution-boundaries",
ROOT / "buddyswitch" / "skills" / "design" / "memory-and-context",
ROOT / "buddyswitch" / "skills" / "design" / "conversation-and-clarity",
ROOT / "buddyswitch" / "skills" / "design" / "recovery-and-escalation",
```

- [ ] **Step 2: Run the consistency checks to confirm all specialist packages are missing before creation**

Run:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0040-design-buddy-redesign
python3 -m unittest tests.test_repo_consistency.RepoConsistencyTests.test_skill_packages_include_skill_toml_and_instruction_markdown -v
```

Expected:

- FAIL for the seven missing specialist package directories

- [ ] **Step 3: Create the specialist skill metadata with the agreed slots and input contracts**

Use these exact `skill.toml` definitions:

```toml
# experience-shaping/skill.toml
id = "experience-shaping"
buddy = "design"
description = "Use when the task is clarifying the user job, success moment, and experience frame before detailed flow design."
objects = ["task", "artifact"]
produces_artifact = true
output_slot = "design-brief"
input_slots = ["prd", "requirements", "track"]
output_schema = "framework/schemas/design/experience-shaping.json"
produces = ["design-brief"]
consumes = ["prd", "requirements", "track"]
side_effect_level = "medium"
required_tools = []
required_env = []
allowed_task_kinds = ["design"]
```

```toml
# activation-and-first-value/skill.toml
id = "activation-and-first-value"
buddy = "design"
description = "Use when the task is improving first-run experience, onboarding, empty states, or time-to-value for a functional AI product."
objects = ["task", "artifact"]
produces_artifact = true
output_slot = "activation-spec"
input_slots = ["prd", "positioning-brief", "launch-prep", "design-spec", "requirements", "track"]
output_schema = "framework/schemas/design/activation-and-first-value.json"
produces = ["activation-spec"]
consumes = ["prd", "positioning-brief", "launch-prep", "design-spec", "requirements", "track"]
side_effect_level = "medium"
required_tools = []
required_env = []
allowed_task_kinds = ["design"]
```

```toml
# initiative-and-intervention/skill.toml
id = "initiative-and-intervention"
buddy = "design"
description = "Use when the task is defining when AI should intervene, suggest, act, or stay silent."
objects = ["task", "artifact"]
produces_artifact = true
output_slot = "initiative-spec"
input_slots = ["prd", "design-spec", "requirements", "track"]
output_schema = "framework/schemas/design/initiative-and-intervention.json"
produces = ["initiative-spec"]
consumes = ["prd", "design-spec", "requirements", "track"]
side_effect_level = "medium"
required_tools = []
required_env = []
allowed_task_kinds = ["design"]
```

```toml
# execution-boundaries/skill.toml
id = "execution-boundaries"
buddy = "design"
description = "Use when the task is defining permissions, confirmation points, and user control boundaries for AI actions."
objects = ["task", "artifact"]
produces_artifact = true
output_slot = "boundaries-spec"
input_slots = ["prd", "design-spec", "requirements", "track"]
output_schema = "framework/schemas/design/execution-boundaries.json"
produces = ["boundaries-spec"]
consumes = ["prd", "design-spec", "requirements", "track"]
side_effect_level = "medium"
required_tools = []
required_env = []
allowed_task_kinds = ["design"]
```

```toml
# memory-and-context/skill.toml
id = "memory-and-context"
buddy = "design"
description = "Use when the task is defining remembered context, visible context, and user control over AI memory."
objects = ["task", "artifact"]
produces_artifact = true
output_slot = "memory-spec"
input_slots = ["prd", "design-spec", "requirements", "track"]
output_schema = "framework/schemas/design/memory-and-context.json"
produces = ["memory-spec"]
consumes = ["prd", "design-spec", "requirements", "track"]
side_effect_level = "medium"
required_tools = []
required_env = []
allowed_task_kinds = ["design"]
```

```toml
# conversation-and-clarity/skill.toml
id = "conversation-and-clarity"
buddy = "design"
description = "Use when the task is improving prompts, clarifications, explanatory copy, and user-facing AI language."
objects = ["task", "artifact"]
produces_artifact = true
output_slot = "conversation-spec"
input_slots = ["prd", "design-spec", "requirements", "track"]
output_schema = "framework/schemas/design/conversation-and-clarity.json"
produces = ["conversation-spec"]
consumes = ["prd", "design-spec", "requirements", "track"]
side_effect_level = "medium"
required_tools = []
required_env = []
allowed_task_kinds = ["design"]
```

```toml
# recovery-and-escalation/skill.toml
id = "recovery-and-escalation"
buddy = "design"
description = "Use when the task is defining fallback, retry, rollback, escalation, and human handoff behavior."
objects = ["task", "artifact"]
produces_artifact = true
output_slot = "recovery-spec"
input_slots = ["prd", "design-spec", "requirements", "track"]
output_schema = "framework/schemas/design/recovery-and-escalation.json"
produces = ["recovery-spec"]
consumes = ["prd", "design-spec", "requirements", "track"]
side_effect_level = "medium"
required_tools = []
required_env = []
allowed_task_kinds = ["design"]
```

- [ ] **Step 4: Add minimal but complete schemas and templates for each specialist**

Use this schema pattern, replacing field names per focus:

```json
{
  "type": "object",
  "required": ["execution_summary", "working_notes", "deliverables_or_changed_files", "artifact_content"],
  "additionalProperties": false,
  "properties": {
    "execution_summary": { "type": "string" },
    "working_notes": { "type": "array", "items": { "type": "string" } },
    "deliverables_or_changed_files": { "type": "array", "items": { "type": "string" } },
    "artifact_content": {
      "type": "object",
      "required": ["objective", "recommendations", "edge_cases", "open_questions"],
      "additionalProperties": false,
      "properties": {
        "objective": { "type": "string" },
        "recommendations": { "type": "array", "items": { "type": "string" } },
        "edge_cases": { "type": "array", "items": { "type": "string" } },
        "open_questions": { "type": "array", "items": { "type": "string" } }
      }
    }
  }
}
```

Use these exact template names:

- `assets/design-brief-template.md`
- `assets/activation-spec-template.md`
- `assets/initiative-spec-template.md`
- `assets/boundaries-spec-template.md`
- `assets/memory-spec-template.md`
- `assets/conversation-spec-template.md`
- `assets/recovery-spec-template.md`

Each template must start with a top-level heading and include these tokens:

```md
# Template

## Objective
- objective:

## Recommendations
- recommendations:

## Edge Cases
- edge_cases:

## Open Questions
- open_questions:
```

- [ ] **Step 5: Re-run the specialist package consistency checks**

Run:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0040-design-buddy-redesign
python3 -m unittest tests.test_repo_consistency.RepoConsistencyTests.test_skill_packages_include_skill_toml_and_instruction_markdown -v
python3 -m unittest tests.test_repo_consistency.RepoConsistencyTests.test_template_references_are_materialized_in_assets -v
```

Expected:

- both tests pass for the complete design catalog

- [ ] **Step 6: Commit the specialist package set**

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0040-design-buddy-redesign
git add buddyswitch/skills/design framework/schemas/design tests/test_repo_consistency.py
git commit -m "feat: add specialist design skill packages"
```

### Task 4: Rewrite The Design Contract And Remove `ia-spec`

**Files:**
- Modify: `framework/contracts/design.md`
- Delete: `buddyswitch/skills/design/ia-spec/skill.toml`
- Delete: `buddyswitch/skills/design/ia-spec/SKILL.md`
- Delete: `buddyswitch/skills/design/ia-spec/assets/design-spec-template.md`
- Delete: `framework/schemas/design/ia-spec.json`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add failing contract assertions that remove the old IA-only framing**

Replace `test_design_docs_treat_market_context_as_explicit_upstream_inputs` with an assertion that the contract now describes a functional-AI-product design system and no longer hardcodes IA-only output fields:

```python
def test_design_contract_describes_functional_ai_product_design_system(self) -> None:
    text = (ROOT / "framework" / "contracts" / "design.md").read_text(encoding="utf-8").lower()
    self.assertIn("functional ai product", text)
    self.assertIn("design-spec", text)
    self.assertIn("design-review", text)
    self.assertNotIn("define information architecture (ia).", text)
```

- [ ] **Step 2: Run the contract test and confirm it fails before the rewrite**

Run:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0040-design-buddy-redesign
python3 -m unittest tests.test_repo_consistency.RepoConsistencyTests.test_design_contract_describes_functional_ai_product_design_system -v
```

Expected:

- FAIL because `framework/contracts/design.md` is still IA-only

- [ ] **Step 3: Rewrite the contract and delete the obsolete `ia-spec` package**

Use this opening block in `framework/contracts/design.md`:

```md
# Design Agent Contract (Env-Centric)

## Purpose

Produce structured design artifacts for functional AI products, including broad design specifications, focused refinement artifacts, and design reviews.

## Must Do

- Produce structured design artifacts that clarify behavior, control, flow, and user understanding.
- Keep user-facing requests in product language rather than requiring internal skill vocabulary.
- Use the selected skill schema as the source of truth for artifact structure.
```

Add these explicit guardrails:

- do not introduce a protocol-level interaction contract in this batch
- do not require option UI for clarification
- do not rewrite PM scope or implement product code

Then delete the old `ia-spec` files and schema entirely.

- [ ] **Step 4: Re-run the contract and file-existence checks**

Run:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0040-design-buddy-redesign
python3 -m unittest tests.test_repo_consistency.RepoConsistencyTests.test_design_contract_describes_functional_ai_product_design_system -v
python3 -m unittest tests.test_repo_consistency.RepoConsistencyTests.test_skill_packages_include_skill_toml_and_instruction_markdown -v
```

Expected:

- contract test passes
- package existence test passes without any `ia-spec` references

- [ ] **Step 5: Commit the contract rewrite and old-package removal**

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0040-design-buddy-redesign
git add framework/contracts/design.md tests/test_repo_consistency.py
git rm -r buddyswitch/skills/design/ia-spec framework/schemas/design/ia-spec.json
git commit -m "refactor: replace ia-spec with the new design contract"
```

### Task 5: Prove Runtime Resolution And Artifact Selection Work Without A New Protocol Layer

**Files:**
- Modify: `tests/test_switch_runtime.py`
- Modify: `tests/test_artifact_selection.py`
- Inspect only unless needed: `scripts/switch_runtime.py`

- [ ] **Step 1: Add failing runtime tests for the new design entry and specialist slot selection**

Add these three tests to `tests/test_switch_runtime.py`:

```python
def test_product_design_spec_uses_explicit_market_inputs(self) -> None:
    payload = switch_runtime.resolve_switch(
        "switch design: Draft the product design for an AI-first onboarding flow"
    )
    card = next(card for card in payload["skill_cards"] if card["id"] == "product-design-spec")
    self.assertEqual(
        card["input_slots"],
        ["prd", "positioning-brief", "launch-prep", "requirements", "track"],
    )

def test_design_critique_uses_design_spec_inputs(self) -> None:
    payload = switch_runtime.resolve_switch(
        "switch design: Review the current product design and call out the biggest issues"
    )
    card = next(card for card in payload["skill_cards"] if card["id"] == "design-critique")
    self.assertEqual(card["input_slots"], ["design-spec", "prd", "requirements", "track"])
```

Extend the existing track-bound design resolve test so `artifact_selection_by_skill["product-design-spec"]` and `run_instructions_by_skill["product-design-spec"]` are asserted directly instead of relying on the old top-level single-skill design fields.

- [ ] **Step 2: Add a failing artifact-selection regression for specialist follow-up work**

Add a `tests/test_artifact_selection.py` case that proves a follow-up design task with required slots `["prd", "design-spec", "activation-spec"]` prefers the current revision from each slot:

```python
selection = select_current_artifacts_for_slots(
    track_artifact_index=index,
    required_slots=["prd", "design-spec", "activation-spec"],
)
self.assertEqual(
    [(item["slot"], item["artifact_id"]) for item in selection],
    [
        ("prd", "art-task-pm-flow-prd-r2"),
        ("design-spec", "art-task-design-flow-design-spec-r3"),
        ("activation-spec", "art-task-design-flow-activation-spec-r1"),
    ],
)
```

- [ ] **Step 3: Run the focused runtime and artifact-selection tests to verify they fail before the final wiring is complete**

Run:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0040-design-buddy-redesign
python3 -m unittest tests.test_switch_runtime -k design -v
python3 -m unittest tests.test_artifact_selection -v
```

Expected:

- design-specific runtime assertions fail until all new package metadata is present
- artifact selection test fails until the fixture includes the new specialist slot

- [ ] **Step 4: Fix only the failing tests that can be satisfied through fixtures or assertions; do not modify runtime unless a real design-specific assumption is exposed**

Allowed changes:

- update fixtures to use `product-design-spec` instead of `ia-spec`
- update expected slot names and selected inputs
- update existing design-task summaries and artifact ids to match the new slots

Do not change `scripts/switch_runtime.py` unless one of the new tests proves that the current runtime cannot support a manifest-driven multi-skill design buddy.

- [ ] **Step 5: Run the full regression sweep for the redesigned design buddy**

Run:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0040-design-buddy-redesign
python3 -m unittest tests.test_switch_runtime -v
python3 -m unittest tests.test_repo_consistency -v
python3 -m unittest tests.test_artifact_selection -v
python3 scripts/parse_switch.py "switch design: Draft a first-pass design for an AI workflow tool"
python3 scripts/codex_router.py "switch design: Draft a first-pass design for an AI workflow tool"
python3 scripts/switch_runtime.py resolve "switch design: Draft a first-pass design for an AI workflow tool"
```

Expected:

- all three test modules pass
- `parse_switch.py` prints a canonical parsed switch
- `codex_router.py` resolves the `design` buddy without syntax errors
- `switch_runtime.py resolve` returns `eligible_skills` for the full design catalog and `implicit_skill_id: null`

- [ ] **Step 6: Commit the verified runtime/test sweep**

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0040-design-buddy-redesign
git add tests/test_switch_runtime.py tests/test_repo_consistency.py tests/test_artifact_selection.py
git commit -m "test: cover multi-skill design runtime and artifact selection"
```

## Plan Self-Review

### Spec coverage

- Replaces `ia-spec` rather than layering compatibility: covered in Tasks 1 and 4
- Promotes `design` to a multi-skill buddy: covered in Tasks 1, 2, and 3
- Preserves simple user entry and defers protocol/UI work: covered in Tasks 2 and 4 via `product-design-spec` guidance and contract guards
- Proves the existing runtime is sufficient: covered in Task 5

### Placeholder scan

- No placeholder markers remain
- Every created package path, schema path, and test command is explicit
- Non-goals are spelled out so the iteration does not drift into interaction-contract work

### Type and naming consistency

- Manifest skill names, package directory names, schema filenames, and output slots are aligned one-to-one
- `product-design-spec` remains the only skill producing `design-spec`
- `design-critique` is the only skill producing `design-review`

## Execution Handoff

Plan complete and saved to `docs/dev0040/design-buddy-redesign-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
