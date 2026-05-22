# Tool Layer Semantic Source Of Truth Task Split

Date: 2026-05-22
Status: execution split for clean-runtime-env only.

## Goal

Stop repeated semantic drift by making runtime-visible tool semantics derive from one static contract
source, then keeping context, responses, AGENTS, and skills as smaller projections or workflow
guidance.

## Current Bottleneck

The runtime has the right direction but still has too many semantic surfaces:

- `scripts/env/tools/<tool>/tool.py::DEFINITION` describes tools and actions.
- `scripts/env/tool_runtime/registry.py` generates `tool_catalog`, `operation_semantics`, and compact
  affordances.
- `scripts/env/tool_runtime/results.py` defines response shape.
- `scripts/env/tools/context/_impl.py` adds another compact semantic surface.
- `tools/launcher/assets/buddies/*/AGENTS.md` names tools and object handling guidance.
- `buddyswitch/skills/shared/*-tool/SKILL.md` teaches tool usage and sometimes repeats boundaries.
- tests and docs contain historical semantic mirrors.

The fix should not add another semantic overlay. It should move stable atomic capability meaning into
`ToolDefinition` and derive every runtime-facing projection from it.

## Non-Goals

- Do not create a workflow engine, routing DSL, rule engine, or phrase-to-tool router.
- Do not encode "every feature request creates a track" or "one request equals one track".
- Do not make AGENTS a tool encyclopedia.
- Do not copy payload schemas or action tables into shared skills.
- Do not preserve stale memo text as durable guidance.

## Task Split

Full implementation plan:

- `docs/spec/2026-05-22-tool-layer-semantic-source-of-truth-implementation-plan.md`

### Task 1: ToolDefinition Semantic Fields And Generated Projections

Plan: `docs/spec/2026-05-22-tool-definition-semantic-fields-projection-implementation-plan.md`

Appendix: `docs/spec/2026-05-22-tool-definition-semantic-fields-projection-appendix.md`

This is the first standalone implementation task.

Deliverables:

- Extend `ToolDefinition` and `ActionDefinition` with explicit semantic fields for object meaning,
  read/write targets, non-write guarantees, visibility, durability, result content level, success
  effect, and failure state guarantee.
- Populate those fields for every currently supported tool and action.
- Generate `context.get.tool_catalog`, `context.get.operation_semantics`,
  `registry.compact_tool_affordances()`, and `turn_runtime.py status` from those fields.
- Add tests that fail when a registered action lacks these fields or when projections fall back to
  generic text such as "completed under declared capability boundary".

Why first:

- It creates the semantic source of truth that later context, response, AGENTS, and skill cleanups
  can reference.
- It avoids trying to patch drift from the outer prompt layers inward.

Verification:

- `python3 -m pytest tests/test_env_tool_semantic_contract.py -q`
- `python3 -m pytest tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_get_metadata_and_source_workspace_semantics -q`
- `python3 -m pytest tests/test_turn_runtime.py tests/test_runtime_skills.py -q`

### Task 2: Context Summary Candidate And Capability Projection Alignment

Depends on Task 1.

Deliverables:

- Make `context.summarize` use only registry-derived compact tool affordances for tool semantics.
- Fix candidate wording so response guidance only names candidate keys actually returned.
- Add active-buddy task candidates or remove `tasks` from summary next-action wording.
- Add a compact capability snapshot derived from manifest permissions plus ToolDefinition semantics:
  active buddy, lifecycle authority, private task scope, artifact publication path, comment target
  support, request lifecycle visibility, search/browser boundary, and evidence token boundary.

Verification:

- `python3 -m pytest tests/test_context_binding_env_tool.py -q`
- `python3 -m pytest tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_context_get_and_summarize_catalog_scope -q`

### Task 3: Runtime Response Consistency With Semantic Contract

Depends on Task 1.

Deliverables:

- Keep `ToolDefinition` as the declared static contract.
- Keep env.tool responses as runtime facts for the actual call.
- Add response contract tests that compare declared action durability/read-write class against
  observed response fields for representative read, write, transient token, private file, and browser
  open actions.
- Preserve response flexibility for action-specific `effect_summary`, `state_changes`,
  `created_ids`, `updated_ids`, and rejection details.

Verification:

- `python3 -m pytest tests/test_env_tool_response_contract.py -q`
- `python3 -m pytest tests/test_runtime_tool_feedback.py -q`

### Task 4: AGENTS And Shared Skill Drift Cleanup

Depends on Tasks 1 and 2.

Deliverables:

- Remove authoritative hardcoded tool lists from buddy AGENTS, or mark any examples as
  non-authoritative and point to `context.get` / `turn_runtime.py status`.
- Fix shared tool skills that contradict runtime definitions, including comment `artifact_section`
  support.
- Keep skills focused on when to use the tool family and how to discover exact payload/response
  fields.
- Add tests that catch shared skill references to stale target enums, old action names, or internal
  implementation paths.

Verification:

- `python3 -m pytest tests/test_runtime_skills.py -q`
- `python3 -m pytest tests/test_buddyswitch_launcher.py -q`

### Task 5: PM Workflow Guidance After Tool Semantics Are Clear

Depends on Tasks 1 through 4.

Deliverables:

- Add or adjust PM skill guidance for track reuse/split/create judgment.
- State PM heuristics as decision bias, not hard routing:
  - use a track for a shared product outcome thread;
  - reuse a track when work advances the same outcome and lifecycle;
  - create a new track when the outcome, lifecycle, proof path, or collaborators are independently
    trackable;
  - use private tasks for active-buddy work management;
  - use requests for durable cross-buddy asks;
  - use comments/messages for discussion, not lifecycle state.
- Avoid case-specific product names, phrase triggers, or exact one-track-per-feature rules.

Verification:

- `python3 -m pytest tests/test_runtime_skills.py -q`
- Manual prompt review of PM skills for overfitting and schema copying.

### Task 6: Drift Gates And Long-Term Maintenance Checks

Depends on Tasks 1 through 5.

Deliverables:

- Add or strengthen tests so new tools/actions fail unless they include full semantic fields.
- Add tests that compare AGENTS named tools, manifest shared tool skills, and runtime supported tools.
- Add tests that reject stable docs or skills claiming internal implementation files are the runtime
  contract.
- Keep docs/spec plans as historical execution records; do not promote memo checklists into durable
  runtime guidance.

Verification:

- `python3 -m pytest tests/test_env_tool_semantic_contract.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q`
- `rg -n "scripts/env/tools/.*/(contract|semantics)\\.py|TOOL_SPEC|ACTION_SEMANTICS|track.get|comment.reopen" buddyswitch/skills tools/launcher/assets docs/spec docs/bitter`

## Recommended Execution Order

1. Complete Task 1 and get registry/context projection tests green.
2. Complete Task 2 so host first-pass orientation no longer drifts from the catalog.
3. Complete Task 3 so responses prove actual runtime effects against the declared contract.
4. Complete Task 4 to remove stale outer-layer mirrors.
5. Complete Task 5 only after the lower semantic layer is clear.
6. Complete Task 6 as the closing drift-prevention pass.

## Why The Old Memo Is Removed

The stale semantic supplement memo mixed current facts, stale facts, and future checklist items. It
is replaced by this task split plus the full implementation plan, Task 1 implementation plan, and
appendix so execution has one clear path.
