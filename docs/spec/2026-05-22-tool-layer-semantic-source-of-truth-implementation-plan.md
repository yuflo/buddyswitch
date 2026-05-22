# Tool Layer Semantic Source Of Truth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** End repeated tool-layer semantic drift by creating one runtime contract source and making context, responses, AGENTS, skills, tests, and docs align with it.

**Architecture:** Treat `ToolDefinition` as the source for static atomic tool semantics, `env.tool` responses as the source for actual call effects, `context` as generated/progressive discovery, shared skills as workflow guidance, and AGENTS as short runtime orientation. Remove prose mirrors and add drift gates instead of adding another semantic layer.

**Tech Stack:** Python env.tool runtime, JSON-compatible dataclass projections, existing BuddySwitch launcher/assets, markdown skills, `unittest`/`pytest`, `rg`-based drift scans.

---

## Current Bottleneck

The current issue is not that PM lacks one more instruction. The issue is that semantics are repeated
across several layers:

- `ToolDefinition` owns most current static tool/action wording.
- `registry.env_tools_description()` and `operation_semantics()` project some of it, but still fill
  important fields with generic defaults.
- `context.summarize` adds compact guidance and candidate ids, but has its own wording and can drift.
- env.tool responses explain actual effects, but tests do not yet compare them to declared action
  semantics.
- AGENTS and shared skills name tools, ids, target support, and workflow rules in prose.
- historical docs/memos preserve stale surfaces and can look authoritative.

The forward repair is to decide what each layer owns, then make the code enforce that ownership.

## Ownership Model

| Layer | Owns | Must Not Own |
| --- | --- | --- |
| `ToolDefinition` | Static atomic semantics: object model, action reads/writes, visibility, durability, success meaning, common failure guarantees, input descriptions. | Business workflow sequencing or phrase routing. |
| `registry` projections | Generated views of `ToolDefinition`: full catalog, operation semantics, compact affordances, status payload. | Handwritten per-tool semantic logic. |
| env.tool response | Actual effect of this call: changed ids, state_changed, durability, rejection reason, next atomic options. | Static tool encyclopedia or hidden success assumptions. |
| `context` | Progressive read-only discovery: candidate ids, current state cues, generated affordances, capability snapshot. | Full schema mirror or workflow script. |
| shared tool skills | How to invoke/discover the tool family and broad boundary reminders. | Full payload/action tables or stale runtime target enums. |
| PM/product skills | Repeated role judgment and workflow heuristics. | Tool schema, exact action fields, or deterministic phrase-to-tool rules. |
| AGENTS | Short startup commands, active-buddy boundary, safety, discovery entrypoints. | Authoritative tool lists, payload docs, long SOPs. |
| docs/spec | Execution plans and historical implementation records. | Runtime authority after code/tests define the contract. |

## Task Overview

This plan is deliberately split into independently verifiable stages. Task 1 is the example the user
named, but it is only the foundation.

1. Baseline and remove memo noise.
2. Add ToolDefinition semantic fields and generated projections.
3. Align context summarize and capability discovery.
4. Align runtime response contracts with declared semantics.
5. Clean AGENTS and shared tool skill drift.
6. Add PM workflow guidance after tool semantics are stable.
7. Add drift gates and repo consistency checks.
8. Final documentation cleanup and verification.

## Task 0: Baseline And Memo Cleanup

**Files:**

- Delete: stale semantic supplement memo under `docs/memo`
- Read: `docs/bitter/2026-05-18-tool-skill-layering-principles.md`
- Read: `docs/spec/2026-05-22-tool-layer-semantic-source-of-truth-task-split.md`

- [ ] **Step 1: Confirm worktree**

Run:

```bash
pwd
git status --short --branch
git rev-parse --show-toplevel
```

Expected:

- all paths point to `/Users/chen/Dev/buddyswitch/.worktrees/clean-runtime-env`;
- branch is `clean-runtime-env`;
- no command touches `/Users/chen/Dev/buddyswitch` main worktree.

- [ ] **Step 2: Delete the stale memo**

Reason:

- It mixes current facts, stale facts, and future checklist items.
- It should be replaced by the task split, this implementation plan, and focused appendices.

- [ ] **Step 3: Confirm no stale memo remains in `docs/memo`**

Run:

```bash
ls docs/memo
```

Expected:

- the stale semantic supplement memo is absent.

## Task 1: ToolDefinition Semantic Fields And Generated Projections

**Detailed plan:**

- `docs/spec/2026-05-22-tool-definition-semantic-fields-projection-implementation-plan.md`
- `docs/spec/2026-05-22-tool-definition-semantic-fields-projection-appendix.md`

**Files:**

- Modify: `scripts/env/tool_runtime/definition.py`
- Modify: `scripts/env/tool_runtime/registry.py`
- Modify: `scripts/env/tools/*/tool.py`
- Modify: `tests/test_env_tool_semantic_contract.py`
- Modify: `tests/test_context_binding_env_tool.py`
- Modify: `tests/test_turn_runtime.py`

- [ ] **Step 1: Add tests that prove missing source-of-truth fields fail**

Add tests requiring:

- tool-level `object_model`;
- action-level `reads`, `writes`, `does_not_write`;
- action-level `visibility`, `durability`, `result_content_level`;
- concrete `success_means`;
- `failure_state_guarantee`;
- absence of generic `"completed under declared capability boundary"`.

Run:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py -q
```

Expected before implementation:

- tests fail because those fields are not projected yet.

- [ ] **Step 2: Extend dataclasses and validation**

Add the required fields to `ToolDefinition` and `ActionDefinition`.

Validation must reject:

- empty `object_model`;
- empty `visibility`, `result_content_level`, `success_effect`, or `failure_state_guarantee`;
- durability outside `none`, `transient`, `durable`;
- actions with no declared read/write/non-write boundary.

- [ ] **Step 3: Populate every shipped tool/action**

Populate all supported tools:

```text
artifact, buddybox, comment, context, evidence, message, request, search, task, track
```

Populate all supported actions listed in the appendix. Keep wording atomic:

- include object boundary and effects;
- include explicit non-write guarantees;
- do not include PM workflow sequencing;
- do not encode one-track-per-feature or phrase triggers.

- [ ] **Step 4: Generate projections from the new fields**

Update `registry.py` so:

- `env_tools_description()` exposes `object_model` and full action semantics;
- `_action_semantic_row()` uses action fields for side effects and success meaning;
- `operation_semantics()` includes read/write/visibility/durability fields;
- `compact_tool_affordances()` includes only compact derived fields and no schemas.

- [ ] **Step 5: Verify Task 1**

Run:

```bash
python3 -m pytest \
  tests/test_env_tool_semantic_contract.py \
  tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_get_metadata_and_source_workspace_semantics \
  tests/test_turn_runtime.py \
  -q
```

Expected:

- all tests pass;
- no projection uses generic success text;
- full catalog has the detailed fields;
- compact affordances remain compact.

## Task 2: Context Summary And Capability Discovery Alignment

**Files:**

- Modify: `scripts/env/tools/context/_impl.py`
- Modify: `scripts/env/tools/context/tool.py`
- Modify: `tests/test_context_binding_env_tool.py`
- Modify: `tests/test_env_tool_response_contract.py`

- [ ] **Step 1: Add tests from user-visible requirements**

Tests should prove:

- `context.summarize` only names candidate id groups it actually returns;
- if summary says tasks are candidate ids, it returns active-buddy task candidates;
- `candidate_tracks`, `candidate_requests`, `candidate_artifacts`, and optional `candidate_tasks`
  have stable id keys and do not include full artifact bodies;
- `tool_affordances` derive from registry compact affordances;
- full schema fields are absent from `context.summarize`;
- `context.get` remains the full catalog path.

Run:

```bash
python3 -m pytest tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_exposes_compact_tool_affordances -q
```

Expected before implementation:

- tests fail if current next-action wording mentions `tasks` without returned task candidates or if
  compact affordances diverge from registry output.

- [ ] **Step 2: Fix summary candidate wording or add task candidates**

Choose the smaller correct change:

- if task candidates are needed for host operation, add `candidate_tasks` with active-buddy task
  summary ids only;
- if task candidates are not needed, remove `tasks` from summary next-action wording.

Do not add full task bodies or turn `summarize` into a workflow plan.

- [ ] **Step 3: Add generated capability snapshot**

Add a compact `capability_snapshot` derived from manifest permissions and registry semantics:

```text
active_buddy
track_lifecycle_authority
task_visibility
artifact_publication_path
comment_target_support
request_lifecycle_visibility
search_boundary
evidence_boundary
buddybox_visibility
```

This snapshot should guide the host without duplicating action schemas.

- [ ] **Step 4: Verify Task 2**

Run:

```bash
python3 -m pytest \
  tests/test_context_binding_env_tool.py \
  tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_context_get_and_summarize_catalog_scope \
  -q
```

Expected:

- context summary is compact, accurate, and generated where possible;
- no full schemas appear in `context.summarize`;
- full catalog remains available through `context.get`.

## Task 3: Runtime Response Contract Alignment

**Files:**

- Modify: `scripts/env/tool_runtime/results.py`
- Modify: selected `scripts/env/tools/*/_impl.py` only where responses contradict actual effects
- Modify: `tests/test_env_tool_response_contract.py`
- Modify: `tests/test_runtime_tool_feedback.py`

- [ ] **Step 1: Add representative response-vs-definition tests**

Tests should dispatch representative actions and compare response facts with declared semantics:

- read actions declare no mutation and return `state_changed=False`, `durability="none"`;
- durable runtime-object writes return changed ids or state_changes;
- buddybox writes declare runtime file mutation and return private file effect;
- evidence actions declare transient token effect and do not claim product mutation;
- search open declares browser session effect and does not claim product mutation;
- rejected calls return `state_changed=False`, `durability="none"`, and useful field/recovery info.

Run:

```bash
python3 -m pytest tests/test_env_tool_response_contract.py -q
```

Expected before implementation:

- failures identify responses whose effect summary, durability, or next-action fields are too weak or
  inconsistent with declared semantics.

- [ ] **Step 2: Keep response ownership narrow**

Do not copy full static tool semantics into responses. Responses should state:

- what happened in this call;
- what ids changed;
- whether the result is durable, transient, private, or read-only;
- why rejection happened;
- which atomic next actions are plausible.

- [ ] **Step 3: Fix inconsistent responses**

Only edit `_impl.py` files when a test proves a real contradiction. Examples of valid fixes:

- a write response missing `state_changes`;
- a rejection missing field-level recovery;
- an action claiming durable product mutation when it only issued a token or opened a browser.

- [ ] **Step 4: Verify Task 3**

Run:

```bash
python3 -m pytest tests/test_env_tool_response_contract.py tests/test_runtime_tool_feedback.py -q
```

Expected:

- responses remain concise but no longer leave the host guessing about state impact.

## Task 4: AGENTS And Shared Tool Skill Drift Cleanup

**Files:**

- Modify: `tools/launcher/assets/buddies/pm/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/dev/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/market/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/design/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/test/AGENTS.md`
- Modify: `buddyswitch/skills/shared/comment-tool/SKILL.md`
- Modify: other `buddyswitch/skills/shared/*-tool/SKILL.md` only when tests prove drift
- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add drift tests before editing prose**

Tests should catch:

- AGENTS claiming an authoritative tool list that omits supported runtime tools;
- shared skills contradicting runtime target enums, such as comment `artifact_section`;
- shared skills naming nonexistent actions like `track.get` or `comment.reopen`;
- shared skills pointing to internal `scripts/env/tools/<tool>/contract.py` or `semantics.py`;
- shared skills copying full payload/action tables.

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py -q
```

Expected before implementation:

- tests fail on any stale prose that contradicts runtime definitions.

- [ ] **Step 2: Shorten AGENTS tool wording**

Replace authoritative hardcoded tool lists with discovery-first wording:

```text
Use context.get or python3 scripts/turn_runtime.py status for the authoritative runtime tool list.
Common runtime tools include task, track, artifact, request, comment, message, buddybox, context,
evidence, and search when available to the active buddy.
```

Keep AGENTS focused on:

- active buddy is fixed;
- start with context summarize;
- use context get/status for exact tools and payloads;
- use env tools for product runtime state;
- do not bypass runtime storage;
- follow structured tool feedback.

- [ ] **Step 3: Fix shared tool skills without schema copying**

For each shared skill:

- keep purpose and runtime route;
- keep discovery references to `context.get.tool_catalog` and `turn_runtime.py status`;
- remove stale exact target/action claims unless they are stable boundary reminders;
- fix comment wording to include `track`, `artifact`, and `artifact_section`;
- avoid full payload schema tables.

- [ ] **Step 4: Verify Task 4**

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py tests/test_buddyswitch_launcher.py -q
```

Expected:

- launcher still materializes expected AGENTS and skills;
- prose no longer drifts from runtime tool/action support.

## Task 5: PM Workflow Guidance After Tool Semantics Are Stable

**Files:**

- Modify: selected `buddyswitch/skills/pm/*/SKILL.md`
- Modify: `tests/test_runtime_skills.py`

- [ ] **Step 1: Identify the narrow PM skill location**

Prefer updating an existing PM skill rather than creating a new large SOP. Candidate locations:

- `buddyswitch/skills/pm/read-product-context/SKILL.md` for first-pass object reading;
- `buddyswitch/skills/pm/define-scope/SKILL.md` for deciding track boundary;
- `buddyswitch/skills/pm/sequence-product-work/SKILL.md` for ordering cross-buddy work.

Choose the smallest location that teaches track reuse/split/create judgment.

- [ ] **Step 2: Add PM heuristics, not routing rules**

The skill should say:

```text
Use a track as a shared product outcome thread.
Reuse an active track when the work advances the same outcome, lifecycle, and proof path.
Create a new track when the outcome, lifecycle, collaborators, or proof path should be tracked
independently.
Use private tasks for active-buddy work management under or outside a track.
Use requests for durable cross-buddy asks.
Use comments/messages for discussion, not product lifecycle state.
```

Do not say:

```text
Every feature phrase creates a track.
Every user request maps to exactly one track.
Always create a task after creating a track.
Always ask Design/Dev/Test after PM writes requirements.
```

- [ ] **Step 3: Add skill tests for overfitting prevention**

Tests should assert:

- PM skills mention runtime discovery for exact action fields;
- PM skills include track reuse/split/create heuristics;
- PM skills do not include deterministic phrase triggers;
- PM skills do not copy payload schema tables;
- PM skills do not claim exact one-track-per-feature behavior.

- [ ] **Step 4: Verify Task 5**

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py -q
```

Expected:

- PM has role guidance only after tool semantics are runtime-visible;
- skills remain short and operational.

## Task 6: Drift Gates And Repo Consistency

**Files:**

- Modify: `tests/test_env_tool_semantic_contract.py`
- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_buddyswitch_launcher.py` if AGENTS materialization checks need updating

- [ ] **Step 1: Add new-tool/new-action gates**

Tests must fail when a new tool/action is added without:

- full semantic fields in `ToolDefinition`;
- generated operation semantics;
- compact affordance projection;
- response contract coverage where the action mutates state or has non-obvious effects.

- [ ] **Step 2: Add prose drift gates**

Tests must fail when stable AGENTS/skills:

- claim internal implementation files are runtime contracts;
- copy full payload/action schema tables;
- name nonexistent actions;
- contradict runtime target enums;
- present hardcoded tool lists as authoritative.

- [ ] **Step 3: Add docs drift scan**

Use `rg` inside tests or repo consistency checks for stable paths:

```text
tools/launcher/assets
buddyswitch/skills
docs/bitter
docs/spec
```

Historical docs may mention removed surfaces only when clearly framed as history. Durable guidance
must point to runtime discovery.

- [ ] **Step 4: Verify Task 6**

Run:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

Expected:

- repeated semantic drift becomes a test failure, not a later memo task.

## Task 7: Final Documentation Cleanup

**Files:**

- Modify: `docs/spec/2026-05-22-tool-layer-semantic-source-of-truth-task-split.md` only if actual
  execution deviates from the split.
- Modify: `docs/bitter/2026-05-18-tool-skill-layering-principles.md` only if a durable principle needs
  a short correction.
- Do not recreate the stale semantic supplement memo.

- [ ] **Step 1: Keep docs/spec as execution record**

After implementation, update specs only with material deviations:

- fields added/renamed;
- tasks merged/split;
- tests added/removed;
- known residual risks.

- [ ] **Step 2: Keep docs/bitter short**

Only update `docs/bitter` if the layer ownership principle changed. Do not add the full plan there.

- [ ] **Step 3: Run final verification**

Run:

```bash
python3 -m pytest \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_context_binding_env_tool.py \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  -q
```

Run drift scan:

```bash
rg -n "completed under declared capability boundary|scripts/env/tools/.*/(contract|semantics)\\.py|TOOL_SPEC|ACTION_SEMANTICS|track.get|comment.reopen" docs buddyswitch tools scripts tests
```

Expected:

- tests pass;
- no live stable surface points to removed semantic files or nonexistent actions.

## Completion Criteria

This full task is complete only when:

- the stale memo is deleted;
- ToolDefinition holds complete static atomic semantics;
- registry/context/status projections are generated from those semantics;
- responses accurately report actual runtime effects;
- AGENTS and shared skills no longer act as semantic mirrors;
- PM workflow guidance exists in a PM skill and is heuristic, not overfit routing;
- drift gates fail on future semantic duplication or stale surfaces;
- focused and broad verification pass in `clean-runtime-env`.
