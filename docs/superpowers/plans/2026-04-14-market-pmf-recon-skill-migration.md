# Market PMF Recon Skill Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port `tmp/pmf-recon-skill-v1` into a BuddySwitch-native `market` skill package named `pmf-recon`, register it with the runtime, and verify that `switch market: ...` now resolves a two-skill market buddy without breaking existing market research behavior.

**Architecture:** Keep the migration purely package- and contract-level. Add a new `buddyswitch/skills/market/pmf-recon/` skill package plus a dedicated `framework/schemas/market/pmf-recon.json`, register it in `buddyswitch/manifest.toml`, and update tests/docs to reflect that `market` is now a multi-skill buddy. Do not introduce scaffolding, runtime routing changes, or new authoring infrastructure in this change.

**Tech Stack:** Python 3.11 stdlib CLI scripts, BuddySwitch TOML/JSON metadata, Markdown skill packages, `unittest`

---

## File Structure

### New skill package

- Create: `buddyswitch/skills/market/pmf-recon/skill.toml`
  - BuddySwitch runtime metadata for the new market skill
- Create: `buddyswitch/skills/market/pmf-recon/SKILL.md`
  - BuddySwitch-native instructions with required section headings
- Create: `buddyswitch/skills/market/pmf-recon/assets/pmf-report-template.md`
  - Reusable PMF report template
- Create: `buddyswitch/skills/market/pmf-recon/assets/evidence-log-template.md`
  - Reusable evidence capture template
- Create: `buddyswitch/skills/market/pmf-recon/references/framework.md`
  - PMF framing reference
- Create: `buddyswitch/skills/market/pmf-recon/references/source-map.md`
  - Source category guidance
- Create: `buddyswitch/skills/market/pmf-recon/references/evidence-rubric.md`
  - Evidence quality rubric
- Create: `buddyswitch/skills/market/pmf-recon/references/interview-prompts.md`
  - Follow-up interview prompts
- Create: `buddyswitch/skills/market/pmf-recon/examples/saas-b2b-example.md`
  - Example prompt/output framing
- Create: `buddyswitch/skills/market/pmf-recon/examples/ai-tool-example.md`
  - Example prompt/output framing

### New schema

- Create: `framework/schemas/market/pmf-recon.json`
  - Structure-only schema for PMF-specific artifact content

### Runtime registration

- Modify: `buddyswitch/manifest.toml:12-41`
  - Add the new `[[skills]]` entry
  - Expand `market.skills` from `["research-scan"]` to `["research-scan", "pmf-recon"]`

### Runtime and consistency tests

- Modify: `tests/test_switch_routing.py:69-85`
  - Assert `pmf-recon` is present in market routing skills
- Modify: `tests/test_switch_runtime.py:100-108`
  - Add a market multi-skill resolve test with `implicit_skill_id is None`
- Modify: `tests/test_repo_consistency.py:20-34`
  - Add the new skill package paths to consistency tuples
- Modify: `tests/test_repo_consistency.py:201-239`
  - Add the new package and required asset checks

### Contract documentation

- Modify: `framework/contracts/market.md:1-117`
  - Generalize the market contract so it covers both `research-scan` and `pmf-recon`
  - Keep shared evidence and traceability requirements, but stop claiming a single fixed artifact shape for all market skills

## Task 1: Add The PMF Recon Skill Package And Schema

**Files:**
- Modify: `tests/test_repo_consistency.py:20-34`
- Modify: `tests/test_repo_consistency.py:201-239`
- Create: `buddyswitch/skills/market/pmf-recon/skill.toml`
- Create: `buddyswitch/skills/market/pmf-recon/SKILL.md`
- Create: `buddyswitch/skills/market/pmf-recon/assets/pmf-report-template.md`
- Create: `buddyswitch/skills/market/pmf-recon/assets/evidence-log-template.md`
- Create: `buddyswitch/skills/market/pmf-recon/references/framework.md`
- Create: `buddyswitch/skills/market/pmf-recon/references/source-map.md`
- Create: `buddyswitch/skills/market/pmf-recon/references/evidence-rubric.md`
- Create: `buddyswitch/skills/market/pmf-recon/references/interview-prompts.md`
- Create: `buddyswitch/skills/market/pmf-recon/examples/saas-b2b-example.md`
- Create: `buddyswitch/skills/market/pmf-recon/examples/ai-tool-example.md`
- Create: `framework/schemas/market/pmf-recon.json`

- [ ] **Step 1: Write the failing repo consistency expectations**

Update `tests/test_repo_consistency.py` so the repo now expects the new market skill package and its template asset.

```python
ARTIFACT_SKILL_DOCS = (
    ROOT / "buddyswitch" / "skills" / "market" / "research-scan" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "market" / "pmf-recon" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "pm" / "write-prd" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "design" / "ia-spec" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "dev" / "implement-task" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "test" / "smoke-test" / "SKILL.md",
)

SKILL_TOMLS = (
    ROOT / "buddyswitch" / "skills" / "market" / "research-scan" / "skill.toml",
    ROOT / "buddyswitch" / "skills" / "market" / "pmf-recon" / "skill.toml",
    ROOT / "buddyswitch" / "skills" / "pm" / "write-prd" / "skill.toml",
    ROOT / "buddyswitch" / "skills" / "pm" / "track-manager" / "skill.toml",
    ROOT / "buddyswitch" / "skills" / "design" / "ia-spec" / "skill.toml",
    ROOT / "buddyswitch" / "skills" / "dev" / "implement-task" / "skill.toml",
    ROOT / "buddyswitch" / "skills" / "test" / "smoke-test" / "skill.toml",
)
```

Also add the package path and asset expectations:

```python
expected_packages = (
    ROOT / "buddyswitch" / "skills" / "market" / "research-scan",
    ROOT / "buddyswitch" / "skills" / "market" / "pmf-recon",
    ROOT / "buddyswitch" / "skills" / "pm" / "write-prd",
    ROOT / "buddyswitch" / "skills" / "pm" / "track-manager",
    ROOT / "buddyswitch" / "skills" / "design" / "ia-spec",
    ROOT / "buddyswitch" / "skills" / "dev" / "implement-task",
    ROOT / "buddyswitch" / "skills" / "test" / "smoke-test",
)

expected_assets = (
    ROOT / "buddyswitch" / "skills" / "market" / "research-scan" / "assets" / "research-report-template.md",
    ROOT / "buddyswitch" / "skills" / "market" / "pmf-recon" / "assets" / "pmf-report-template.md",
    ROOT / "buddyswitch" / "skills" / "pm" / "write-prd" / "assets" / "prd-template.md",
    ROOT / "buddyswitch" / "skills" / "design" / "ia-spec" / "assets" / "design-spec-template.md",
    ROOT / "buddyswitch" / "skills" / "dev" / "implement-task" / "assets" / "implementation-report-template.md",
    ROOT / "buddyswitch" / "skills" / "test" / "smoke-test" / "assets" / "test-report-template.md",
)
```

- [ ] **Step 2: Run the consistency checks to confirm they fail**

Run:

```bash
python3 -m unittest \
  tests.test_repo_consistency.RepoConsistencyTests.test_every_skill_package_has_metadata_and_instruction_files \
  tests.test_repo_consistency.RepoConsistencyTests.test_template_references_are_materialized_in_assets \
  -v
```

Expected: FAIL with missing `buddyswitch/skills/market/pmf-recon/...` paths.

- [ ] **Step 3: Write the new `skill.toml`**

Create `buddyswitch/skills/market/pmf-recon/skill.toml` with this exact content:

```toml
id = "pmf-recon"
buddy = "market"
description = "Use when the task is validating a startup or product idea, narrowing an ICP, comparing alternatives, or collecting evidence to decide whether a market is worth pursuing."
objects = ["task", "artifact"]
produces_artifact = true
output_slot = "research"
input_slots = ["research-question", "links", "prior-artifacts"]
output_schema = "framework/schemas/market/pmf-recon.json"
produces = ["pmf-report", "evidence-log", "interview-plan"]
consumes = ["research-question", "links", "prior-artifacts"]
side_effect_level = "medium"
required_tools = []
required_env = []
allowed_task_kinds = ["research"]
```

- [ ] **Step 4: Write the BuddySwitch-native `SKILL.md`**

Create `buddyswitch/skills/market/pmf-recon/SKILL.md` with BuddySwitch section headings and PMF-specific guidance:

```markdown
# pmf-recon

## Purpose
- Produce evidence-backed PMF research that identifies the sharpest ICP, strongest pain signals, current alternatives, and the next validation move.

## Use when
- The task is about validating a startup or product idea, narrowing an ICP, comparing alternatives, or deciding whether a market is worth pursuing.
- The user wants PMF-oriented research rather than a broad category scan.
- The prompt references pain intensity, adoption likelihood, willingness to pay, wedge segments, or next-step validation tests.

## Do not use when
- The task is mainly a broad market/category scan without a concrete idea or user hypothesis; use `research-scan` instead.
- The main outcome should be a PRD, design spec, implementation change, or smoke-test report.
- The user wants unsupported opinion or product strategy without source-backed research.

## Inputs
- Product idea in one or two sentences.
- Target user and workflow hypothesis.
- Optional alternatives, competitors, price band, geography, or channel constraints.
- Optional links, prior artifacts, or track context.

## Outputs
- A research artifact object with PMF evidence, ICP synthesis, alternatives analysis, confidence, and recommended next step.
- A run audit in `buddyswitch/content/runs/` when default runtime persistence is used.
- Explicit notes when login, paywall, or anti-bot constraints degrade evidence quality.

## Research Defaults

- Collection mode: `browser-first + search-assist`.
- Start with user-language sources before polished market messaging.
- Prefer public sources first and log any access downgrade in the artifact.
- Read `references/source-map.md`, `references/evidence-rubric.md`, and `references/interview-prompts.md` as needed.

## Source Strategy

- Cover at least one user-language community source, one review/comparison source, and one official or competitor source when feasible.
- Begin with public communities and review sites that expose pain in the user's own words.
- Use `x.com` only when the category is fast-moving or the user explicitly wants it.

## Access And Blocking Rules

- If a valuable source requires login, stop and ask the user to log in before continuing.
- If blocked by paywall, rate-limit, region lock, or anti-bot controls, record the blockage, switch to public alternatives, and mark the evidence downgrade.

## Steps

1. Restate the idea, user, workflow, and research depth.
2. Build the initial hypothesis frame and source plan.
3. Scan user-language communities for repeated pain and workarounds.
4. Scan review/comparison and official sources for alternative gaps and switching triggers.
5. Capture explicit evidence and trace it back to source IDs.
6. Synthesize the strongest ICPs, PMF confidence, and one next validation move.
7. Write the final report using the PMF report template.

## Verification
- Confirm every material conclusion can be traced back to captured evidence.
- Confirm the strongest ICP and pain signals are grounded in repeated or concrete evidence.
- Confirm the output separates observed evidence from inference and clearly labels assumptions.

## Shared Runtime Rules

- See `framework/docs/skill-runtime-shared-rules.md` for execution summary persistence, task/artifact boundaries, and durable output path rules.

## Required Output Fields

- `research_question`
- `research_strategy`
- `channel_plan`
- `iteration_log`
- `evidence`
- `source_traceability`
- `assumptions_used`
- `candidate_icps`
- `strongest_pain_signals`
- `existing_alternatives`
- `why_current_solutions_fall_short`
- `pmf_confidence`
- `recommended_next_step`
- `suggested_interview_angles`
- `risks_and_unknowns`
- `conclusion`

## Guardrails

- Do not write PRD content.
- Do not turn PMF research into implementation advice.
- Do not invent commitment signals, buyer intent, or willingness-to-pay evidence.
- Do not continue past login-required sources without user confirmation.

## Examples
- `switch market: Validate whether an AI note-taking tool for consultants has enough PMF signal to test`
- `switch market: Narrow the best ICP for a lightweight CRM aimed at solo founders`
- `switch market: Compare current alternatives and pain signals for a devtool onboarding assistant`

## Counterexamples
- `switch market: Research the creator analytics category broadly and summarize competitors`
- `switch pm: Draft the MVP PRD for a consultant note-taking tool`
- `switch dev: Implement the onboarding assistant in projects/app`

## Gotchas
- A PMF-shaped research request can still mention competitors, but the output should stay focused on pain, alternatives, and next validation action.
- Keep the final recommendation to one primary next move instead of a vague menu of options.
```

- [ ] **Step 5: Copy the reference, asset, and example files from the tmp bundle**

Run:

```bash
mkdir -p \
  buddyswitch/skills/market/pmf-recon/assets \
  buddyswitch/skills/market/pmf-recon/references \
  buddyswitch/skills/market/pmf-recon/examples

cp tmp/pmf-recon-skill-v1/assets/evidence-log-template.md \
  buddyswitch/skills/market/pmf-recon/assets/evidence-log-template.md
cp tmp/pmf-recon-skill-v1/assets/pmf-report-template.md \
  buddyswitch/skills/market/pmf-recon/assets/pmf-report-template.md

cp tmp/pmf-recon-skill-v1/references/framework.md \
  buddyswitch/skills/market/pmf-recon/references/framework.md
cp tmp/pmf-recon-skill-v1/references/source-map.md \
  buddyswitch/skills/market/pmf-recon/references/source-map.md
cp tmp/pmf-recon-skill-v1/references/evidence-rubric.md \
  buddyswitch/skills/market/pmf-recon/references/evidence-rubric.md
cp tmp/pmf-recon-skill-v1/references/interview-prompts.md \
  buddyswitch/skills/market/pmf-recon/references/interview-prompts.md

cp tmp/pmf-recon-skill-v1/examples/saas-b2b-example.md \
  buddyswitch/skills/market/pmf-recon/examples/saas-b2b-example.md
cp tmp/pmf-recon-skill-v1/examples/ai-tool-example.md \
  buddyswitch/skills/market/pmf-recon/examples/ai-tool-example.md
```

- [ ] **Step 6: Write the PMF-specific output schema**

Create `framework/schemas/market/pmf-recon.json` with this exact content:

```json
{
  "type": "object",
  "required": [
    "execution_summary",
    "working_notes",
    "deliverables_or_changed_files",
    "artifact_content"
  ],
  "additionalProperties": false,
  "properties": {
    "execution_summary": { "type": "string" },
    "working_notes": { "type": "array", "items": { "type": "string" } },
    "deliverables_or_changed_files": { "type": "array", "items": { "type": "string" } },
    "artifact_content": {
      "type": "object",
      "required": [
        "research_question",
        "research_strategy",
        "channel_plan",
        "iteration_log",
        "evidence",
        "source_traceability",
        "assumptions_used",
        "candidate_icps",
        "strongest_pain_signals",
        "existing_alternatives",
        "why_current_solutions_fall_short",
        "pmf_confidence",
        "recommended_next_step",
        "suggested_interview_angles",
        "risks_and_unknowns",
        "conclusion"
      ],
      "additionalProperties": false,
      "properties": {
        "research_question": { "type": "string" },
        "research_strategy": {
          "type": "object",
          "required": ["depth", "rationale", "collection_mode", "initial_hypotheses", "source_category_targets"],
          "additionalProperties": false,
          "properties": {
            "depth": { "type": "string", "enum": ["quick", "standard", "deep"] },
            "rationale": { "type": "string" },
            "collection_mode": { "type": "string" },
            "initial_hypotheses": { "type": "array", "items": { "type": "string" } },
            "source_category_targets": { "type": "array", "items": { "type": "string" } }
          }
        },
        "channel_plan": { "type": "array", "items": { "type": "string" } },
        "iteration_log": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["round", "focus", "sources_checked", "evidence_captured", "synthesis", "next_adjustment"],
            "additionalProperties": false,
            "properties": {
              "round": { "type": "integer" },
              "focus": { "type": "string" },
              "sources_checked": { "type": "array", "items": { "type": "string" } },
              "evidence_captured": { "type": "string" },
              "synthesis": { "type": "string" },
              "next_adjustment": { "type": "string" }
            }
          }
        },
        "evidence": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["source_id", "url", "source_type", "accessed_at", "claim_excerpt", "segment", "pain_category"],
            "additionalProperties": false,
            "properties": {
              "source_id": { "type": "string" },
              "url": { "type": "string" },
              "source_type": { "type": "string" },
              "accessed_at": { "type": "string" },
              "claim_excerpt": { "type": "string" },
              "segment": { "type": "string" },
              "pain_category": { "type": "string" },
              "alternative": { "type": "string" },
              "commitment_signal": { "type": "string" },
              "confidence": { "type": "string", "enum": ["low", "medium", "high"] }
            }
          }
        },
        "source_traceability": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["conclusion", "source_ids"],
            "additionalProperties": false,
            "properties": {
              "conclusion": { "type": "string" },
              "source_ids": { "type": "array", "items": { "type": "string" } }
            }
          }
        },
        "assumptions_used": { "type": "array", "items": { "type": "string" } },
        "candidate_icps": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["segment", "pain_summary", "why_now_or_why_this_segment"],
            "additionalProperties": false,
            "properties": {
              "segment": { "type": "string" },
              "pain_summary": { "type": "string" },
              "why_now_or_why_this_segment": { "type": "string" },
              "buying_signal": { "type": "string" },
              "reachability": { "type": "string" }
            }
          }
        },
        "strongest_pain_signals": { "type": "array", "items": { "type": "string" } },
        "existing_alternatives": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["name", "type", "gaps"],
            "additionalProperties": false,
            "properties": {
              "name": { "type": "string" },
              "type": { "type": "string" },
              "gaps": { "type": "array", "items": { "type": "string" } }
            }
          }
        },
        "why_current_solutions_fall_short": { "type": "array", "items": { "type": "string" } },
        "pmf_confidence": {
          "type": "object",
          "required": ["level", "rationale"],
          "additionalProperties": false,
          "properties": {
            "level": { "type": "string", "enum": ["low", "medium", "high"] },
            "rationale": { "type": "string" }
          }
        },
        "recommended_next_step": {
          "type": "object",
          "required": ["action", "rationale"],
          "additionalProperties": false,
          "properties": {
            "action": {
              "type": "string",
              "enum": ["interviews", "concierge", "landing-page", "mvp", "pricing-test", "stop-or-reposition"]
            },
            "rationale": { "type": "string" }
          }
        },
        "suggested_interview_angles": { "type": "array", "items": { "type": "string" } },
        "risks_and_unknowns": { "type": "array", "items": { "type": "string" } },
        "conclusion": { "type": "string" }
      }
    }
  }
}
```

- [ ] **Step 7: Run the package-focused tests again and make sure they pass**

Run:

```bash
python3 -m unittest \
  tests.test_repo_consistency.RepoConsistencyTests.test_every_skill_package_has_metadata_and_instruction_files \
  tests.test_repo_consistency.RepoConsistencyTests.test_skill_instructions_are_markdown_only_without_frontmatter_metadata \
  tests.test_repo_consistency.RepoConsistencyTests.test_template_references_are_materialized_in_assets \
  -v
```

Expected: PASS.

- [ ] **Step 8: Commit the new package files**

```bash
git add \
  buddyswitch/skills/market/pmf-recon \
  framework/schemas/market/pmf-recon.json \
  tests/test_repo_consistency.py
git commit -m "feat: add pmf-recon market skill package"
```

## Task 2: Register The Skill And Codify Multi-Skill Market Resolution

**Files:**
- Modify: `tests/test_switch_routing.py:69-85`
- Modify: `tests/test_switch_runtime.py:100-108`
- Modify: `buddyswitch/manifest.toml:12-41`
- Modify: `framework/contracts/market.md:1-117`

- [ ] **Step 1: Add the failing routing and runtime tests**

Update `tests/test_switch_routing.py` so market routing now exposes both market skills:

```python
self.assertIn("research-scan", payload["profile"]["authority"]["routing_skills"])
self.assertIn("pmf-recon", payload["profile"]["authority"]["routing_skills"])
self.assertTrue(payload["profile"]["skills"])
```

Add a new runtime test to `tests/test_switch_runtime.py` right after `test_track_manager_skill_card_omits_output_slot_and_compat_fields`:

```python
def test_multi_skill_market_buddy_returns_no_implicit_skill(self) -> None:
    payload = switch_runtime.resolve_switch(
        "switch market: Validate an AI tool idea for indie developers"
    )

    self.assertTrue(payload["ok"])
    self.assertEqual(payload["invocation"]["buddy"], "market")
    self.assertEqual(payload["eligible_skills"], ["research-scan", "pmf-recon"])
    self.assertIsNone(payload["implicit_skill_id"])

    ids = [card["id"] for card in payload["skill_cards"]]
    self.assertEqual(ids, ["research-scan", "pmf-recon"])

    pmf_card = next(card for card in payload["skill_cards"] if card["id"] == "pmf-recon")
    self.assertEqual(
        pmf_card["instruction_path"],
        "buddyswitch/skills/market/pmf-recon/SKILL.md",
    )
    self.assertEqual(pmf_card["output_slot"], "research")
    self.assertEqual(
        pmf_card["input_slots"],
        ["research-question", "links", "prior-artifacts"],
    )
```

- [ ] **Step 2: Run the focused runtime tests to confirm they fail**

Run:

```bash
python3 -m unittest \
  tests.test_switch_routing.RouterTests.test_router_exposes_invocation_and_profile \
  tests.test_switch_runtime.ResolveRuntimeTests.test_multi_skill_market_buddy_returns_no_implicit_skill \
  -v
```

Expected: FAIL because `pmf-recon` is not yet registered in `buddyswitch/manifest.toml`.

- [ ] **Step 3: Register `pmf-recon` in the manifest**

Modify `buddyswitch/manifest.toml` like this:

```toml
[[skills]]
id = "research-scan"
path = "buddyswitch/skills/market/research-scan"

[[skills]]
id = "pmf-recon"
path = "buddyswitch/skills/market/pmf-recon"

[[skills]]
id = "write-prd"
path = "buddyswitch/skills/pm/write-prd"
```

And update the market buddy:

```toml
[[buddies]]
id = "market"
label = "Market"
scope = "Research demand, users, and competition."
skills = ["research-scan", "pmf-recon"]
permissions = ["track.read", "task.read", "task.create", "task.update", "task.archive", "artifact.read", "artifact.create", "artifact.update"]
```

- [ ] **Step 4: Update the market contract so it describes the skill family accurately**

Replace the fixed single-shape output section in `framework/contracts/market.md` with a common-structure contract that still preserves evidence requirements:

```markdown
## Required Output Structure

The selected market skill schema defines the exact synthesis fields.
All market artifacts must include at least:

1. `research_question`
2. `research_strategy`
3. `channel_plan`
4. `iteration_log`
5. `evidence`
6. `source_traceability`
7. `conclusion`

Typical skill-specific synthesis fields include:
- `research-scan`: `patterns_and_insights`, `risks_and_caveats`
- `pmf-recon`: `assumptions_used`, `candidate_icps`, `strongest_pain_signals`, `existing_alternatives`, `pmf_confidence`, `recommended_next_step`
```

Also relax the channel default language so it fits both market skills:

```markdown
## Must Do

- Clarify the research question and scope.
- Select the market skill flow that matches the question: broad category scan or PMF validation.
- Use browser-first evidence collection with search-assisted discovery.
- Choose channels based on the question type and constraints.
- Collect and synthesize evidence from browsed sources.
- Highlight caveats and uncertainty.
- Provide a conclusion that is traceable to evidence.
```

- [ ] **Step 5: Run the focused tests again and make sure they pass**

Run:

```bash
python3 -m unittest \
  tests.test_switch_routing.RouterTests.test_router_exposes_invocation_and_profile \
  tests.test_switch_runtime.ResolveRuntimeTests.test_multi_skill_market_buddy_returns_no_implicit_skill \
  -v
```

Expected: PASS.

- [ ] **Step 6: Commit the runtime wiring**

```bash
git add \
  buddyswitch/manifest.toml \
  framework/contracts/market.md \
  tests/test_switch_routing.py \
  tests/test_switch_runtime.py
git commit -m "feat: register pmf-recon as a market skill"
```

## Task 3: Verify BuddySwitch Compatibility End-To-End

**Files:**
- Modify: none expected
- Test: `tests/test_env_manifest_v2.py`
- Test: `tests/test_repo_consistency.py`
- Test: `tests/test_switch_routing.py`
- Test: `tests/test_switch_runtime.py`

- [ ] **Step 1: Validate the manifest loads cleanly**

Run:

```bash
python3 scripts/env_manifest.py print >/tmp/buddyswitch-manifest.json
```

Expected: exit code `0`, and `/tmp/buddyswitch-manifest.json` contains a market buddy whose `skills` array includes both `research-scan` and `pmf-recon`.

- [ ] **Step 2: Resolve a market PMF request and inspect the runtime payload**

Run:

```bash
python3 scripts/switch_runtime.py resolve \
  "switch market: Validate whether an AI tool for indie developers has enough PMF signal to test" \
  >/tmp/buddyswitch-market-resolved.json
```

Expected:
- `eligible_skills` equals `["research-scan", "pmf-recon"]`
- `implicit_skill_id` is `null`
- one skill card has `"id": "pmf-recon"` and `"output_slot": "research"`

- [ ] **Step 3: Run the full targeted regression suite**

Run:

```bash
python3 -m unittest \
  tests.test_env_manifest_v2 \
  tests.test_repo_consistency \
  tests.test_switch_routing \
  tests.test_switch_runtime \
  -v
```

Expected: PASS.

- [ ] **Step 4: Do a final diff review before handing off**

Run:

```bash
git diff --stat HEAD~2..HEAD
git status --short
```

Expected:
- only the new market skill package, schema, manifest, contract, and targeted tests changed
- no runtime code changes in `scripts/switch_runtime.py` or `scripts/codex_router.py`
- working tree is clean or only contains intentional follow-up edits

## Self-Review

- Spec coverage:
  - Add a BuddySwitch-native `market/pmf-recon` skill package: covered by Task 1.
  - Ensure CLI/runtime compatibility with BuddySwitch skill requirements: covered by Tasks 1-3.
  - Register the skill under `market`: covered by Task 2.
  - Avoid expanding into scaffolding/authoring work: enforced in Goal/Architecture and Task scope.

- Placeholder scan:
  - No `TBD`, `TODO`, “similar to”, or deferred implementation language remains.
  - Each code-changing step contains concrete file content or exact copy commands.

- Type consistency:
  - `skill_id` is consistently `pmf-recon`.
  - `output_slot` is consistently `research`.
  - Schema and `SKILL.md` required fields align.
  - Runtime expectations consistently assume `market` becomes a multi-skill buddy with `implicit_skill_id = None`.
