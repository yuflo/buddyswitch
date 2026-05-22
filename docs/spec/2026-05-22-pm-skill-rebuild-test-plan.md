# PM Skill Rebuild Test Plan

Date: 2026-05-22

## Approval Gate

This document is a planning artifact only. Do not implement tests, skill packages, manifest edits,
launcher edits, or code changes until the user explicitly approves the test plan and implementation
plan.

## Goal

Verify that the PM buddy is rebuilt from a single PRD-writing skill into a generic, richer
product-management skill surface that helps PM read context, make product judgments, produce durable
outputs, and close the product loop without adding scenario-specific prompt guidance.

The test plan must prove product behavior, not just check implementation strings. Static checks are
allowed only for mechanical contracts such as manifest registration, skill package validity,
runtime projection, and forbidden tool-schema duplication. Product-quality coverage comes from
pressure scenarios and rubrics that are independent of the exact wording inside each `SKILL.md`.

## Source Norms

- Repository guidance: `AGENTS.md` and SHARP forward development.
- Layering rule: `docs/bitter/2026-05-18-tool-skill-layering-principles.md`.
- Repo implementation surfaces: `buddyswitch/manifest.toml`, `tests/test_runtime_skills.py`,
  `tests/test_buddyswitch_launcher.py`, `framework/contracts/pm.md`,
  `tools/launcher/assets/buddies/pm/AGENTS.md`.
- Inventory input: `tmp/buddyswitch-real-startup-skill-inventory.html`.
- External format reference: Agent Skills specification at `https://agentskills.io/specification`
  for directory layout, required `SKILL.md`, `name`, `description`, progressive disclosure, and
  optional `scripts/`, `references/`, `assets/`.
- Local skill-authoring rule: skill descriptions are trigger metadata; they must not become shortcut
  workflow summaries that let the agent skip the skill body.

## Current Bottleneck

The PM buddy currently has one broad active skill, `write-prd`. That skill can create a brief or
decision, but it compresses too many PM responsibilities into one workflow: context reading,
evidence synthesis, product direction, scope cuts, requirements, acceptance criteria, decision
capture, track triage, and post-proof iteration. The observed landing-page collaboration looked
unclear because PM lacked durable product-work routines and context interpretation standards, not
because it needed a landing-page or Wukong-specific skill.

## Target PM Skill Surface

The planned PM product-work skill set is:

- `read-product-context`
- `synthesize-cross-functional-inputs`
- `frame-product-direction`
- `define-scope`
- `write-requirements`
- `write-acceptance-criteria`
- `make-product-decision`
- `decide-from-proof`
- `triage-track`
- `sequence-product-work`

This taxonomy is generic PM work, not a page-type taxonomy. The implementation plan must keep this
list pending user approval; no development may begin until approval.

## Taxonomy Rationale

| Skill | PM capability gap | Inventory / repo evidence | Why it is not scenario-specific |
| --- | --- | --- | --- |
| `read-product-context` | PM must understand track, task, artifact, request, proof, and message context before deciding. | Inventory calls out PM track context reading and stale summary risk. Current PM contract requires `track.open` and `artifact.get`. | Applies to any PM task with durable context. |
| `synthesize-cross-functional-inputs` | PM must convert market, design, dev, and test signals into decision impacts. | Inventory handoff map defines market -> PM, design -> dev, dev -> test, test -> PM loops. | Applies to cross-functional inputs, not a deliverable type. |
| `frame-product-direction` | PM needs audience, problem, value, evidence strength, constraints, and non-goals before downstream work. | Inventory has product intent translation and evidence-to-product-direction as P0/P1 PM abilities. | Applies to product direction regardless of surface. |
| `define-scope` | PM must cut to the smallest valuable iteration and state non-goals. | Inventory names scope definition as P0 and asks what to cut to ship in one week. | Applies to every scoped product iteration. |
| `write-requirements` | PM must turn goals into observable behavior without owning implementation. | Inventory names requirements definition and rejects requirements that test cannot inspect. | Applies to product behavior, not web-page layout. |
| `write-acceptance-criteria` | PM must make proof readable by test without subjective interpretation. | Inventory names acceptance criteria authoring as P0 and test -> PM proof loop. | Applies to any verifiable change. |
| `make-product-decision` | PM decisions need evidence, tradeoffs, rejected alternatives, and next owner/action. | Existing `write-prd` supports decision artifacts but mixes them with PRD drafting. | Applies whenever a durable decision is needed. |
| `decide-from-proof` | PM needs explicit continue, revise, send back, stop, or blocked decisions after proof. | Inventory marks post-proof loop closure and `pm/iteration-decision` as the top PM gap. | Applies to proof-based iteration across product work. |
| `triage-track` | PM needs to recover stale, cluttered, or blocked tracks without rewriting a PRD. | Inventory recommends `pm/track-triage`; current PM owns track lifecycle. | Applies to track state, not content format. |
| `sequence-product-work` | PM must order design/dev/test/market follow-up without building a project-management system. | Inventory names downstream handoff readiness and backlog/task sequencing as a real but bounded need. | Applies to owner/order decisions, not a launch checklist. |

## Functional Requirements

R1. The active PM runtime surface no longer contains `write-prd`.

R2. The active PM runtime surface contains the approved generic PM product-work skills and the
existing shared runtime tool skills.

R3. Every PM product-work skill is a valid Codex-native Agent Skill package:
`buddyswitch/skills/pm/<skill-id>/SKILL.md`, frontmatter `name` matching the directory, and a
non-empty `description`.

R4. Skill descriptions describe trigger conditions only. They must not enumerate workflow steps,
tool commands, or output sections that could be followed without reading the body.

R5. Skill bodies contain enough experienced PM SOP to guide the work: use cases, non-use cases,
inputs to inspect, product judgment pattern, output shape, quality bar, pressure scenario, and
counterexample.

R6. PM skills do not duplicate runtime tool schemas, action catalogs, payload tables, or response
schemas. Exact tool semantics stay in `context.get.tool_catalog`, `python3 scripts/turn_runtime.py
status`, and runtime response fields.

R7. PM skills use runtime context discipline: read `track.open` before mutating shared track state,
read full `artifact.get` bodies when artifact ids matter, and distinguish private buddybox drafts
from product-readable artifacts.

R8. PM skills are generic product-management skills. No Wukong-specific, landing-page-specific,
pricing-page-specific, launch-page-specific, or marketing-surface-specific PM skill is introduced.

R9. PM contract and PM runtime AGENTS guidance align with the new skill surface without becoming a
long SOP or a prose mirror of runtime tool behavior.

R10. Launcher projection materializes the same PM skill list into runtime `.agents/skills` and does
not leave stale `write-prd` runtime skill directories.

R11. Tests and validation are goal-directed. They must fail for a PM skill rebuild that looks
registered but cannot guide context intake, synthesis, scope, requirements, acceptance criteria,
decision-making, proof iteration, track triage, and sequencing.

## Test Strategy

### Layer A: Mechanical Active-Surface Tests

These tests are allowed to be deterministic file/manifest checks because the requirements are
mechanical.

- Manifest registration: PM buddy skill list includes every target PM product-work skill plus shared
  runtime tool skills.
- Active removal: manifest and PM runtime skill projection do not include `write-prd`.
- Package validity: every registered PM product-work skill path exists and has valid frontmatter.
- Launcher projection: PM instance start/open materializes the manifest skill set under
  `.agents/skills`.
- Source cleanup: `buddyswitch/skills/pm/write-prd/` is removed, not left as a dead active package.

### Layer B: Boundary And Skill-Quality Tests

These tests prevent the wrong layer from absorbing the problem.

- Description quality: descriptions begin with `Use when`, stay below 1024 characters, match
  directory name through `name`, and do not contain numbered workflow steps or env client commands.
- Tool boundary: PM skill bodies do not contain payload/action schema mirror terms such as
  `payload_fields`, `operation_semantics`, `**Payload:**`, `**Returns:**`, or implementation-private
  paths such as `scripts/env/tools/`.
- Runtime discovery: PM skills refer to runtime discovery surfaces for exact tool details:
  `context.get.tool_catalog`, `python3 scripts/turn_runtime.py status`, and runtime response fields.
- Publication discipline: PM skills describe the current publication model at the business-workflow
  level: draft artifact first, then `track.add_material` or `track.add_proof`; no direct
  `published_to_track` bypass.
- Scenario drift: PM skill ids and bodies do not add case-specific PM skills for Wukong, landing
  pages, pricing pages, launch pages, or marketing surfaces.

### Layer C: PM Pressure Scenarios

These scenarios test goals and PM behavior. They should be run after the skill rebuild in a fresh PM
runtime or a focused evaluation harness. Passing means the PM output satisfies the rubric; it does
not mean the output uses exact phrases from the skill files.

#### P1: Messy Track Context Intake

Input:
- A track has an old brief, two conflicting comments, one design artifact id, and one test proof id.
- The user asks PM to "continue this track".

Expected behavior:
- PM reads `track.open` and the full artifact bodies before deciding.
- PM separates facts, assumptions, decisions already made, blockers, and missing inputs.
- PM does not rewrite a PRD as the first move.
- PM states the next PM-owned action and any owner-specific request.

Coverage:
- `read-product-context`
- `triage-track`
- docs/bitter context discovery discipline

#### P2: Cross-Functional Signal Conflict

Input:
- Market says the user pain is credible but narrow.
- Design says first-screen complexity is high.
- Dev says reusable components exist but localization is risky.
- Test says prior proof did not cover mobile.

Expected behavior:
- PM synthesizes each signal into product decision impact.
- PM identifies which signal changes scope, which changes acceptance criteria, and which remains an
  open question.
- PM does not treat every signal as equal priority.

Coverage:
- `synthesize-cross-functional-inputs`
- `frame-product-direction`
- `define-scope`

#### P3: Broad Product Surface Request

Input:
- The user asks PM to coordinate a website, landing page, pricing page, or launch page.

Expected behavior:
- PM uses generic PM skills: audience, problem, value, scope, requirements, acceptance criteria,
  decision, and owner sequencing.
- PM does not invent a page-type PM skill or page-structure template as the PM capability.
- PM may produce surface-specific content only as an output of generic PM judgment.

Coverage:
- R8 scenario drift
- `frame-product-direction`
- `define-scope`
- `write-requirements`

#### P4: Ambiguous Requirements

Input:
- A request says "make onboarding easier and more premium".

Expected behavior:
- PM rewrites the request into observable user behavior and constraints.
- PM records what remains a design decision and what remains a dev implementation decision.
- PM adds acceptance criteria that test can verify without PM interpretation.

Coverage:
- `write-requirements`
- `write-acceptance-criteria`
- owner-boundary discipline

#### P5: Durable Decision Capture

Input:
- Two alternatives exist: ship a narrow feature this week or wait for a broader redesign.

Expected behavior:
- PM records decision, evidence, tradeoff, rejected alternative, residual risk, and next owner/action.
- PM publishes the decision as material or proof through the existing artifact/track path.
- PM does not leave the decision only in chat.

Coverage:
- `make-product-decision`
- publication discipline

#### P6: Proof-Based Iteration

Input:
- Test publishes a proof where desktop passes, mobile fails with repro steps, and one area is
  unverified.

Expected behavior:
- PM decides one of continue, revise, send back, stop, or blocked.
- PM names what evidence supports that decision and what residual risk remains.
- PM updates track/task state or creates owner-specific follow-up only through env tools.

Coverage:
- `decide-from-proof`
- `write-acceptance-criteria`
- test -> PM loop closure

#### P7: Stale Or Cluttered Track

Input:
- A track has several old materials, no current proof, a stale task, and unclear latest direction.

Expected behavior:
- PM identifies current truth, obsolete material, missing proof, blockers, and smallest next action.
- PM does not create a new PRD just to make progress look clean.
- PM updates track status/now only after reading current shared state.

Coverage:
- `triage-track`
- `read-product-context`
- track lifecycle ownership

#### P8: Product Work Sequencing

Input:
- A brief needs market follow-up, design shaping, dev implementation, and test proof, but the order
  is unclear.

Expected behavior:
- PM creates a short ordered sequence with owner, expected output, dependency, and stop condition.
- PM avoids building a workflow engine, scheduler, or broad project-management layer.
- PM keeps sequence tied to the current track outcome.

Coverage:
- `sequence-product-work`
- `synthesize-cross-functional-inputs`
- SHARP scope discipline

## Planned Automated Test Surfaces

| Test Area | File | Main Proof |
| --- | --- | --- |
| PM skill registration and `write-prd` removal | `tests/test_runtime_skills.py` | PM manifest skill set is exactly the approved product-work set plus shared runtime tools. |
| Agent Skill package validity | `tests/test_runtime_skills.py` | Each package has matching directory/name frontmatter and trigger-only description metadata. |
| PM skill content quality | `tests/test_runtime_skills.py` | Every skill has required operational sections and skill-specific quality markers. |
| docs/bitter boundary | `tests/test_runtime_skills.py` and existing repo consistency tests | PM skills do not mirror runtime schemas or action catalogs. |
| Launcher runtime projection | `tests/test_buddyswitch_launcher.py` | PM runtime `.agents/skills` equals PM buddy manifest list and excludes `write-prd`. |
| PM contract/AGENTS alignment | `tests/test_runtime_skills.py` | Active PM guidance references generic responsibilities and does not name deleted skill behavior. |
| Broad regression | `python3 -m pytest -q` | No skill/launcher/runtime regressions. |

## Specific Test Cases

### T1: PM Manifest Skill Set Is Generic And Complete

Setup:
- Load `buddyswitch/manifest.toml`.
- Select buddy with `id == "pm"`.

Assertions:
- PM skills include every approved PM product-work skill.
- PM skills include all shared runtime tool skills.
- PM skills do not include `write-prd`.
- No PM product-work skill id contains scenario vocabulary such as `wukong`, `landing`, `pricing`,
  `launch-page`, or `marketing-surface`.

Failure caught:
- A partial migration that keeps PM as one PRD-writing role.
- A scenario-specific skill added to satisfy a single task.
- A compatibility registration that keeps old and new skill surfaces side by side.

### T2: Old PM Skill Package Is Removed

Setup:
- Inspect `buddyswitch/skills/pm`.

Assertions:
- `buddyswitch/skills/pm/write-prd/SKILL.md` does not exist.
- `buddyswitch/skills/pm/write-prd/assets/prd-template.md` does not exist.
- No PM buddy launcher test expects `.agents/skills/write-prd`.

Failure caught:
- Leaving obsolete PM skill assets as hidden active or future baggage.

### T3: PM Skill Packages Are Valid Agent Skills

Setup:
- For each target PM skill id, open `buddyswitch/skills/pm/<skill-id>/SKILL.md`.

Assertions:
- File exists.
- YAML frontmatter includes `name: <skill-id>`.
- Parent directory name matches frontmatter `name`.
- Frontmatter includes a non-empty `description` within Agent Skills limits.
- Description starts with `Use when`.
- Description does not contain env commands, numbered steps, or output-section checklists.

Failure caught:
- Broken package layout.
- Skill descriptions becoming shortcut workflow prompts.

### T4: PM Skill Bodies Carry Product SOP, Not Prompt Restrictions

Setup:
- Read every PM product-work `SKILL.md`.

Assertions:
- Every skill has sections for use conditions, non-use conditions, inputs, product judgment steps,
  outputs, quality bar or verification, examples, and counterexamples.
- Every skill contains at least one pressure scenario or concrete input/output example.
- Skill-specific content matches the capability mapping in this document.

Failure caught:
- Thin skill files that only restate role names.
- Prompt-heavy "do not do X" restrictions without executable PM judgment.

### T5: PM Skills Follow Tool/Skill Layering

Setup:
- Read all PM product-work `SKILL.md` files and existing shared tool skills.

Assertions:
- PM skills do not contain full payload/action schema tables.
- PM skills do not mention private tool implementation paths.
- PM skills route exact payload and response field uncertainty to runtime discovery and runtime
  response fields.
- Shared runtime tool skills remain atomic and are not expanded with PM workflows.

Failure caught:
- Solving runtime/tool contract weakness through PM prompt bulk.

### T6: PM Skills Stay Generic Under Page-Type Requests

Setup:
- Read PM skill ids and bodies.
- Run pressure scenario P3 after implementation.

Assertions:
- No PM skill is named for Wukong, landing page, pricing page, launch page, or marketing surface.
- PM output for P3 uses generic PM framing, scope, requirements, criteria, and decision routines.
- Any page or website structure is treated as task-specific output, not as the skill taxonomy.

Failure caught:
- Case-specific PM skill drift.
- PM becoming a page/copy role instead of the product judgment owner.

### T7: Launcher Projection Uses Manifest Skill Set

Setup:
- Use existing launcher fake-codex tests that start/open PM runtime workspaces.

Assertions:
- Runtime `.agents/skills` contains every PM buddy skill declared in manifest.
- Runtime `.agents/skills/write-prd` does not exist.
- Stale runtime skill directories are removed on instance open/refresh.

Failure caught:
- Source manifest looks correct but active Codex runtime still receives stale skills.

### T8: PM Guidance Alignment

Setup:
- Read `framework/contracts/pm.md`.
- Read `tools/launcher/assets/buddies/pm/AGENTS.md`.

Assertions:
- No active guidance references `write-prd`.
- PM contract states generic PM responsibilities: context intake, direction, scope, requirements,
  acceptance criteria, decision capture, proof iteration, track triage, and sequencing.
- PM AGENTS remains short and points to runtime discovery instead of duplicating tool schemas.

Failure caught:
- Rebuilding skill files while active runtime guidance still tells PM to use deleted behavior.

### T9: Pressure Scenario Rubric Pass

Setup:
- Run P1-P8 after implementation in a fresh PM runtime or focused evaluation harness.
- Record the scenario prompt, produced output, and rubric pass/fail in a verification note.

Assertions:
- Each scenario passes the expected behavior bullets for the related capability.
- Failures are treated as skill-quality failures unless the runtime tool response proves a lower-layer
  contract defect.

Failure caught:
- A rebuild that passes static tests but still acts generic or confused in real PM work.

## Non-Goals

- Do not add a landing-page, page-type, marketing-surface, pricing-page, launch-page, or
  Wukong-specific PM skill.
- Do not add a workflow engine, scheduler, auto-router, relation tool, artifact search system,
  message/request/comment bridge, or loop-stability feature.
- Do not keep `write-prd` as a compatibility alias.
- Do not duplicate runtime tool schemas or action catalogs inside skills.
- Do not rewrite runtime tools for this task unless tests prove a lower-layer contract defect.

## Tool Gap Assessment

No new runtime tool is required for the PM skill rebuild plan. Existing runtime surfaces cover the
planned work:

- `context.summarize`, `context.get`, and `python3 scripts/turn_runtime.py status` for discovery.
- `track.open`, `track.update_now`, `track.add_material`, `track.add_proof`, and `track.archive` for
  track lifecycle.
- `artifact.get` and `artifact.create_revision` for full body reads and PM-authored durable outputs.
- `task.*`, `request.*`, `message.*`, `comment.*`, and `buddybox.*` for existing collaboration
  mechanics.

Possible future tool work should stay out of this task unless pressure scenarios prove a lower-layer
defect. Candidates to record separately, not implement here:

- A deterministic skill package validator if repo tests keep duplicating Agent Skills frontmatter
  checks.
- Better track/artifact summary fields if PM cannot determine current truth from `track.open` plus
  `artifact.get`.
- A relation/search tool only if repeated real tracks prove explicit ids and track materials are not
  enough.

## Verification Commands

Focused commands for the implementation phase:

```bash
python3 -m pytest tests/test_runtime_skills.py -q
python3 -m pytest tests/test_buddyswitch_launcher.py -q
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_skill_and_contract_texts_do_not_copy_payload_field_or_schema_tables -q
python3 -m pytest -q
```

Expected:
- Focused skill tests pass.
- Launcher projection tests pass.
- Existing prose boundary tests pass.
- Full suite passes, or any unrelated pre-existing failure is reported with exact evidence.

## Done Criteria

The rebuild is test-complete only when:

- the PM buddy exposes the approved generic PM skill set;
- `write-prd` is gone from source, manifest, and runtime projection;
- PM skill packages satisfy Agent Skills metadata and progressive-disclosure constraints;
- skill bodies contain product-work SOP for the pressure scenarios without copying tool schemas;
- PM contract and AGENTS guidance remain short and aligned;
- pressure scenarios P1-P8 pass by rubric;
- focused and broad verification pass.
