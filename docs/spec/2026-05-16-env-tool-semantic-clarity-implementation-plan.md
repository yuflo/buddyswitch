# Env Tool Semantic Clarity Implementation Plan

> **For agentic workers:** Implement this plan in `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem` on branch `dev_buddy_mem`. Use test-first changes for behavior, keep each phase runnable, and keep the work limited to the env tool semantic surface defined by the memo.

**Goal:** Make runtime-visible env tool descriptions and runtime feedback clear enough for a host to choose, call, and recover from atomic env tools without reading `scripts/env/services/*.py`.

**Architecture:** The existing env tool registry, semantic projection, response helpers, context discovery, and shared skills remain the delivery surfaces. This plan strengthens text and feedback carried by current fields, then tightens compact discovery and trims shared skills so tool semantics remain the source of action meaning.

**Tech Stack:** Python env services, broker-routed `env.tool`, `scripts/turn_runtime.py status`, Markdown shared skills, pytest/unittest.

---

## 1. Source Inputs

- `docs/memo/2026-05-16-env-tool-semantic-clarity-boundary-memo.md`
- Repository root `AGENTS.md`
- `scripts/env/tools/semantics.py`
- `scripts/env/tools/responses.py`
- `scripts/env/tools/contracts.py`
- `scripts/env/services/context.py`
- `scripts/turn_runtime.py`
- `scripts/env/services/{tasks,tracks,artifacts,handoffs,buddybox,evidence,search}.py`
- `scripts/env/tools/{router,dispatch}.py`
- `buddyswitch/skills/shared/{task,track,artifact,handoff,buddybox}-tool/SKILL.md`
- Existing tests under `tests/test_env_tool_semantic_contract.py`, `tests/test_env_tool_response_contract.py`, `tests/test_context_binding_env_tool.py`, `tests/test_host_decision_surface_product_mode.py`, `tests/test_runtime_tool_feedback.py`, `tests/test_env_layer_end_to_end.py`, `tests/test_repo_consistency.py`, `tests/test_runtime_skills.py`, and tool-specific env tests.

## 2. Current Bottleneck

The repo already exposes the right surfaces: `context.summarize.tool_affordances`, `context.get.tool_catalog`, `context.get.operation_semantics`, `scripts/turn_runtime.py status`, canonical response helpers, and shared skills. The bottleneck is semantic clarity. A host can still encounter template-like text such as "You need tool.action behavior", unclear return-level distinctions, uneven compact affordances, and rejection payloads that do not consistently identify correctable fields or alternative atomic capabilities.

The work should directly replace low-signal runtime-visible semantics and feedback. It should not add a semantic version, a parallel catalog, a workflow engine, a phrase router, a rule engine, a generic search subsystem, or business process instructions inside tool descriptions.

## 3. Layer Boundaries

### Tool Layer

Owned files:

- `scripts/env/tools/contracts.py`
- `scripts/env/tools/semantics.py`
- `scripts/env/tools/responses.py`
- `scripts/env/tools/router.py`
- `scripts/env/tools/dispatch.py`
- `scripts/env/services/*.py`
- runtime projections exposed by `context.get` and `scripts/turn_runtime.py status`

Allowed content:

- Atomic capability purpose.
- Input meaning and the runtime surface where ids usually appear.
- Return meaning at the content level: summary, body, private file content, metadata, token, browser intent, durable object.
- Permission, ownership, visibility, state effect, durability, success meaning, failure meaning.
- Correctable fields and alternative atomic capabilities.

Disallowed content:

- Business process sequences such as market research order, PRD-to-design handoff order, or dev/test process order.
- Phrase-to-tool routing.
- Required step lists in `allowed_next_action_options`.

### Context Discovery Layer

Owned files:

- `scripts/env/services/context.py`
- `scripts/env/tools/semantics.py::compact_tool_affordances`
- `scripts/turn_runtime.py`

Allowed content:

- `context.summarize` gives compact first-pass capability distinctions.
- `context.get` gives the full runtime catalog and operation semantics.
- `scripts/turn_runtime.py status` exposes the same full env tool catalog outside a broker call.

Disallowed content:

- Full action catalog copied into `context.summarize`.
- Business workflows or phrase rules.
- Any replacement for `context.get.tool_catalog`.

### Skill Layer

Owned files:

- `buddyswitch/skills/shared/*-tool/SKILL.md`

Allowed content:

- Repeated operational workflows and short reminders about which runtime catalog and response fields to trust.
- Tool invocation route map.

Disallowed content:

- Long runtime catalogs copied from `context.get`.
- Payload field inventories that mirror every action.
- Text that overrides `permission_boundary`, `why_blocked`, `state_changed`, `durability`, `correctable_fields`, or `alternative_capabilities`.

### AGENTS Layer

Owned files:

- Root `AGENTS.md`
- `tools/launcher/assets/buddies/*/AGENTS.md`

Allowed content:

- Short route map: start with `context summarize`, use `context get` or `turn_runtime.py status` for full catalog, use env tools for runtime state, do not directly edit runtime object or buddybox state.

Disallowed content:

- Full tool manual.
- Payload schema mirror.
- Business workflow catalog.

The current AGENTS files already mostly match this boundary. This plan treats them as verification surfaces, not primary edit targets.

## 4. Required Implementation Order

1. `scripts/env/tools/semantics.py`
2. `scripts/env/tools/responses.py` and response-producing services
3. `context.summarize` compact discovery
4. Shared skills

This order keeps full runtime-visible tool meaning as the source, then aligns actual feedback, then tightens compact discovery, then trims skill guidance that was compensating for unclear tool semantics.

## 5. Non-Goals Kept Out Of Scope

- No semantic v2 or dual semantic path.
- No new workflow engine, rule engine, phrase router, or generic tool-search subsystem.
- No new MCP server.
- No business workflow encoding in tool descriptions.
- No long shared-skill catalog that mirrors runtime behavior.
- No required step list semantics for `allowed_next_action_options`.
- No scenario-by-scenario optimization as the main strategy.

## 6. Phase 0: Baseline And Red Test Selection

### Task 0.1: Capture Baseline Surface

**Current problem:** Implementation needs a factual baseline for the runtime-visible catalog and response fields before changing text.

**Files to read only:**

- `scripts/env/tools/semantics.py`
- `scripts/env/tools/responses.py`
- `scripts/env/tools/contracts.py`
- `scripts/env/services/context.py`
- `scripts/turn_runtime.py`

**Action:**

- Run `python3 scripts/turn_runtime.py status` and save the output only as terminal inspection, not a committed fixture.
- Run `python3 scripts/env/client.py context summarize` only inside a runtime workspace if one is already active; do not create product state for this baseline.
- Run the focused existing tests listed below before editing.

**Do not modify:**

- Runtime object files under `buddyswitch/objects/**`.
- Buddybox private files under `buddyswitch/local/buddybox/**`.
- Any service implementation.

**Observable result:**

- The developer sees current template-like semantic rows and current compact affordance rows before writing red tests.

**Verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_context_binding_env_tool.py \
  tests/test_runtime_skills.py \
  -q
```

## 7. Phase 1: Rewrite Full Tool Semantics

### Task 1.1: Add Semantic Quality Regression Tests

**Current problem:** Existing tests mostly prove field presence and basic text quality. They still allow text that names the action without explaining host-visible meaning, such as "You need task.list behavior", "Execute track.get", or "returned structured state".

**Files to modify:**

- `tests/test_env_tool_semantic_contract.py`

**Behavior or text type to modify:**

- Add a semantic quality test that scans all capability and action semantic fields exposed by `contracts.env_tools_description()`.
- Reject these template patterns in `plain_description`, `use_when`, and `success_means`:
  - `You need <tool>.<action> behavior`
  - `Execute <tool>.<action>`
  - `returned structured state`
  - `completed with explicit ids`
  - `semantic metadata for action`
  - `structured capability feedback`
- Add action-family expectations that prove meaning, not exact prose:
  - list actions identify summary rows or records and say no full body when relevant.
  - get/read actions identify one explicit id or logical name and the returned content level.
  - validate actions identify validation-only behavior and no state mutation.
  - create/update/archive/delete actions identify what durable object or private file changes.
  - evidence actions identify transient target-scoped tokens.
  - search actions distinguish status metadata, target URL/browser intent, and browser session effects.

**Do not modify:**

- Do not use snapshot assertions for full catalog JSON.
- Do not assert one exact sentence.
- Do not inspect private functions inside `semantics.py`.

**Observable result:**

- The new tests fail against current generic semantic text before `semantics.py` is rewritten.

**Verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_semantic_text_rejects_template_action_language \
  tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_action_semantics_explain_content_level_state_effect_and_durability \
  -q
```

### Task 1.2: Rewrite Task And Track Action Semantics

**Current problem:** `task` and `track` actions still contain generic `use_when`, `plain_description`, and `success_means` text that does not fully explain id sources, return level, authority, or mutation effect.

**Files to modify:**

- `scripts/env/tools/semantics.py`

**Behavior or text type to modify:**

- For `task.create`, state that it creates one active-buddy-owned durable task, optionally attached to an explicit `track_id`.
- For `task.list`, state that it returns active-buddy task summary rows and no artifact bodies.
- For `task.get`, state that it reads one active-buddy task record by `task_id` and returns task metadata/artifact ids, not full artifact bodies.
- For `task.update`, state that it patches one active-buddy task and may update the track relation when `track_id` is provided.
- For `task.archive`, state that it changes one active-buddy task status to archived.
- For all task inputs, identify common id sources:
  - `task_id` from `task.create`, `task.list`, `task.get`, `track.get`, or `context.get.tasks`.
  - `track_id` from `context.summarize.candidate_tracks`, `track.list`, or `track.get`.
- For `track.list`, state that it returns track summaries with optional filters.
- For `track.get`, state that it reads one track context with track metadata, related task summaries, and artifact summaries, not full artifact bodies.
- For `track.join`, state that it creates, reuses, or attaches an active-buddy task relation to a track without hidden binding state.
- For `track.create/update/advance/archive`, state that these are PM lifecycle mutations of durable track objects.
- For `track.attach_task/detach_task`, state that these mutate the explicit relation between one owned task and one track.

**Do not modify:**

- Do not add new actions.
- Do not change permission enforcement.
- Do not introduce a current-track or current-task binding concept.
- Do not describe PM, Dev, Design, Test, or Market business workflows.

**Observable result:**

- `context.get.tool_catalog.task.action_semantics` and `track.action_semantics` explain what each action reads or mutates, where ids come from, and what is returned.

**Verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_semantic_contract.py \
  tests/test_track_env_tool.py \
  tests/test_task_env_tool.py \
  -q
```

### Task 1.3: Rewrite Artifact And Handoff Action Semantics

**Current problem:** `artifact` and `handoff` semantics name explicit ids and refs but do not consistently distinguish summaries, full bodies, validation-only output, durable object mutation, and target-readable handoff references.

**Files to modify:**

- `scripts/env/tools/semantics.py`

**Behavior or text type to modify:**

- For `artifact.list`, state that it returns artifact summary rows for a track and never returns full artifact `content`.
- For `artifact.get`, state that it returns one readable artifact record by `artifact_id`, including the full artifact body content.
- For `artifact.validate_payload`, state that it validates and normalizes a future artifact revision payload without mutating state.
- For `artifact.create_revision`, state that it writes a durable product-readable artifact revision for an active-buddy-owned `task_id` and updates task artifact linkage.
- For `artifact.update_metadata`, state that it updates title, summary, and source refs only; it does not replace artifact body content.
- For artifact inputs, identify id sources:
  - `track_id` from `context.summarize.candidate_tracks`, `track.list`, or `track.get`.
  - `task_id` from active-buddy tasks returned by `task.list`, `task.get`, or `track.join`.
  - `artifact_id` from `artifact.list`, `artifact.create_revision`, `track.get` artifact summaries, or `context.get.artifact_summaries`.
- For `handoff.list`, state that it returns explicit handoff records visible to source, target, or PM, not artifact body content.
- For `handoff.validate`, state that it validates target buddy, source ownership, artifact refs, and source refs without writing a handoff.
- For `handoff.create`, state that it writes one durable handoff record that references readable product objects.
- For handoff inputs, identify id sources:
  - `source_task_id` from owned task rows.
  - `artifact_ids` from owned/readable artifact rows.
  - `target_buddy` from manifest buddy ids.
- State that buddybox logical names are private provenance for artifacts only when normalized by artifact source refs and are not handoff-readable payloads.

**Do not modify:**

- Do not make `artifact.list` return full bodies.
- Do not allow handoff to treat buddybox private files as target-readable payloads.
- Do not encode "after writing a PRD, hand off to Design" or any similar business sequence.

**Observable result:**

- Host can tell when to use `artifact.list` versus `artifact.get`, when validation is read-only, and why handoff uses product object references.

**Verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_semantic_contract.py \
  tests/test_artifact_env_tool.py \
  tests/test_handoff_env_tool.py \
  -q
```

### Task 1.4: Rewrite Context, Evidence, Search, And Buddybox Semantics

**Current problem:** These tools contain some of the clearest boundary language, but context, evidence, and search still include generic text. Buddybox should remain the model for content-level clarity while avoiding filesystem or workflow prose.

**Files to modify:**

- `scripts/env/tools/semantics.py`

**Behavior or text type to modify:**

- For `context.get`, state that it returns full runtime context sections plus full `tool_catalog` and `operation_semantics`.
- For `context.summarize`, state that it returns compact orientation, candidate ids, buddybox descriptor, and compact tool affordances; it does not return full tool catalog or artifact bodies.
- For `context.list_sources`, state that it returns source descriptors only.
- For evidence actions, state that they issue target-scoped transient token metadata and do not write durable product objects.
- For `search.status`, state that it reads backend capability and browser readiness metadata.
- For `search.request`, state that it validates a browser/search backend request and returns a target URL/browser intent without opening a browser page.
- For `search.open_browser`, state that it opens a target URL in the launcher-managed browser session and does not write product objects.
- For buddybox actions, preserve the current logical-name/private-file semantics and make sure each action distinguishes descriptor, summary rows, one file body, private file write, and private file delete.

**Do not modify:**

- Do not expose absolute buddybox roots.
- Do not tell the host to use native Codex web search.
- Do not encode market research workflow into `search` descriptions.
- Do not add new semantic fields.

**Observable result:**

- Runtime-visible catalog text covers metadata, token, browser intent, browser session, private file content, and compact context return levels.

**Verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_semantic_contract.py \
  tests/test_context_binding_env_tool.py \
  tests/test_search_env_tool.py \
  tests/test_evidence_env_tool.py \
  tests/test_buddybox_env_tool.py \
  -q
```

### Task 1.5: Preserve Contract Projection Shape

**Current problem:** The semantics can be rewritten without changing the existing catalog structure. A new schema would violate the memo.

**Files to modify:**

- `scripts/env/tools/contracts.py` only if projection wiring is broken by semantic text changes.
- `tests/test_env_tool_semantic_contract.py`

**Behavior or text type to modify:**

- Keep `env_tools_description()` returning the existing fields:
  - `title`
  - `plain_description`
  - `use_when`
  - `do_not_use_when`
  - `capability_boundary`
  - `operations`
  - `payload_fields`
  - `action_semantics`
  - `feedback_source`
  - `authoritative_fields`
- Keep `operation_semantics()` returning the existing machine contract fields.
- Add a regression assertion that no `semantic_v2`, `schema_version=2`, or parallel catalog key appears in `env_tools_description()`.

**Do not modify:**

- Do not add a new top-level semantic version.
- Do not split `operation_semantics` into a second catalog.

**Observable result:**

- `context.get.tool_catalog` and `turn_runtime.py status` expose clearer text with the same projection shape.

**Verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_operation_semantics_machine_contract_is_preserved \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_env_tool_surface_is_runtime_visible_and_runless \
  -q
```

## 8. Phase 2: Clarify Runtime Response Feedback

### Task 2.1: Add Response Quality Tests

**Current problem:** Existing response tests verify canonical fields and a few scenarios, but they do not prove that representative successes and rejections are self-explanatory to a host.

**Files to modify:**

- `tests/test_env_tool_response_contract.py`
- `tests/test_runtime_tool_feedback.py`
- `tests/test_env_layer_end_to_end.py`

**Behavior or text type to modify:**

- Add a representative success matrix for:
  - `task.list`, `task.create`
  - `track.get`, `track.join`
  - `artifact.list`, `artifact.get`, `artifact.validate_payload`, `artifact.create_revision`
  - `handoff.validate`, `handoff.create`
  - `buddybox.list`, `buddybox.read`, `buddybox.write`
  - `context.get`, `context.summarize`
  - `evidence.issue_browser`
  - `search.status`, `search.request`, `search.open_browser`
- Assert each success identifies:
  - `effect_summary`
  - `state_changed`
  - `durability`
  - `read_scope` for read or validation actions
  - `state_changes`, `created_ids`, or `updated_ids` for mutating actions where object ids exist
  - returned content level by action family
- Add representative rejection tests for payload, scope, authority, browser, and target-type failures.
- Assert each rejection identifies:
  - `why_blocked`
  - `impact`
  - `state_changed=false`
  - `retry_guidance`
  - `correctable_fields` or `alternative_capabilities`

**Do not modify:**

- Do not require every action to return `allowed_next_action_options`.
- Do not use exact full-response snapshots.
- Do not count fields as a substitute for checking host-meaningful values.

**Observable result:**

- The tests fail wherever services return vague effect summaries, omit correction fields on representative rejections, or blur return levels.

**Verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_response_contract.py \
  tests/test_runtime_tool_feedback.py \
  tests/test_env_layer_end_to_end.py \
  -q
```

### Task 2.2: Strengthen Response Helper Guardrails

**Current problem:** `scripts/env/tools/responses.py` validates required canonical fields but does not guard conditional affordance wording or normalize reusable correction structures.

**Files to modify:**

- `scripts/env/tools/responses.py`
- `tests/test_env_tool_response_contract.py`

**Behavior or text type to modify:**

- Keep existing response field names and function signatures unless a callsite requires a narrow optional helper.
- Add a private helper that validates `allowed_next_action_options[*].reason` and `tool_affordance(...).condition` as conditional affordance text.
- Reject option reasons containing obvious workflow prescription fragments:
  - `must create artifact`
  - `always create artifact`
  - `only next action`
  - `after writing a PRD`
  - `market research should`
  - `if the user says`
- Add a small helper for alternative capability rows with keys `tool`, `action`, `condition`, and optional `mutates_product_state`; use it only to reduce repeated row construction in service responses.

**Do not modify:**

- Do not add a phrase router.
- Do not route calls based on these phrases.
- Do not add new response-required fields.
- Do not reject ordinary runtime boundary words such as "must be a non-empty string" in validation error messages.

**Observable result:**

- Structured affordance helpers reject workflow-prescriptive option text during tests and service development while keeping response JSON shape stable.

**Verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_next_action_options_are_conditional_affordances_not_workflow_steps \
  -q
```

### Task 2.3: Update Read And Validation Success Responses

**Current problem:** Read and validation responses often have the required fields, but some effect summaries and read scopes do not describe the returned content level clearly enough.

**Files to modify:**

- `scripts/env/services/tasks.py`
- `scripts/env/services/tracks.py`
- `scripts/env/services/artifacts.py`
- `scripts/env/services/handoffs.py`
- `scripts/env/services/buddybox.py`
- `scripts/env/services/context.py`
- `scripts/env/services/evidence.py`
- `scripts/env/services/search.py`

**Behavior or text type to modify:**

- `task.list`: `effect_summary` and `read_scope` say active-buddy task summary rows.
- `task.get`: say one active-buddy task record with metadata and artifact ids, not full artifact bodies.
- `track.list`: say track summary rows.
- `track.get`: say track metadata plus related task summaries and artifact summaries, not full artifact bodies.
- `artifact.list`: say artifact summary rows for a track, no full `content`.
- `artifact.get`: say one readable artifact record including full body content.
- `artifact.validate_payload`: say validation-only normalized payload, no write.
- `handoff.list`: say handoff records visible to this buddy/PM, no artifact bodies.
- `handoff.validate`: say validation-only normalized handoff candidate, no write.
- `buddybox.desc`: say capability descriptor and compact state summary only.
- `buddybox.list`: say private file summary rows only.
- `buddybox.read`: say one private file body and whether `content` or `content_base64` was returned.
- `context.get`: say full context sections plus full tool catalog and operation semantics.
- `context.summarize`: say compact context only and no full catalog.
- `context.list_sources`: say source descriptors only.
- `evidence.issue_browser` and `evidence.approve_downgrade`: say transient token metadata, not durable object state.
- `search.status`: say capability/backend metadata only.
- `search.request`: say target URL/browser intent, page not opened.
- `search.open_browser`: say browser session opened and no product object changed.

**Do not modify:**

- Do not make read actions mutate state.
- Do not add full artifact bodies to summary/list responses.
- Do not change tool permissions or object stores.

**Observable result:**

- Host can inspect a success response and know return level and state effect without reading service code.

**Verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_read_and_validation_successes_explain_return_level_and_no_state_change \
  tests/test_context_binding_env_tool.py \
  tests/test_search_env_tool.py \
  -q
```

### Task 2.4: Update Mutating Success Responses

**Current problem:** Mutating responses usually include `state_changed` and `durability`, but not all of them expose enough detail about which object or state plane changed.

**Files to modify:**

- `scripts/env/services/tasks.py`
- `scripts/env/services/tracks.py`
- `scripts/env/services/artifacts.py`
- `scripts/env/services/handoffs.py`
- `scripts/env/services/buddybox.py`
- `scripts/env/services/evidence.py`
- `scripts/env/services/search.py`

**Behavior or text type to modify:**

- Add or refine `state_changes` rows for durable object mutations:
  - `task.create`: object type `task`, change `created`.
  - `task.update`: object type `task`, change `updated_fields`.
  - `task.archive`: object type `task`, change `archived`; already-archived path keeps `state_changed=false`.
  - `track.join`: object type `task_relation`, change `task_created`, `task_attached`, or `relation_reused`.
  - `track.create/update/advance/archive`: object type `track`, change matching lifecycle action.
  - `track.attach_task/detach_task`: object type `task_track_relation`.
  - `artifact.create_revision`: object type `artifact`, change `revision_created`; include updated task id.
  - `artifact.update_metadata`: object type `artifact`, change `metadata_updated`; explicitly no content replacement.
  - `handoff.create`: object type `handoff`, change `created`.
  - `buddybox.write/delete`: object type `private_file`, change `created`, `overwritten`, `deleted`, or `already_absent`.
  - `evidence.*`: object type `evidence_token`, change `issued`, durability `transient token`.
  - `search.open_browser`: object type `browser_session`, change `opened_search_page`, durability `browser_session`.
- Keep existing `created_ids` and `updated_ids`, correcting them where they refer to returned ids.
- Add `mutates_product_state=false` where a mutating action affects only private files, tokens, or browser session.

**Do not modify:**

- Do not introduce a new `write_scope` response field.
- Do not mark token or browser effects as durable product object writes.
- Do not claim idempotent reads changed state.

**Observable result:**

- Host can distinguish durable product object mutation, active-instance-local private file mutation, transient token issuance, and browser session mutation.

**Verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_mutating_successes_explain_changed_state_plane_and_durability \
  tests/test_env_layer_end_to_end.py \
  tests/test_buddybox_env_tool.py \
  -q
```

### Task 2.5: Update Rejection Feedback Across Services

**Current problem:** Buddybox rejections already expose strong correction fields, but most other services do not consistently expose `correctable_fields` or `alternative_capabilities`.

**Files to modify:**

- `scripts/env/services/tasks.py`
- `scripts/env/services/tracks.py`
- `scripts/env/services/artifacts.py`
- `scripts/env/services/handoffs.py`
- `scripts/env/services/context.py`
- `scripts/env/services/evidence.py`
- `scripts/env/services/search.py`
- `scripts/env/tools/router.py`
- `scripts/env/tools/dispatch.py`

**Behavior or text type to modify:**

- Payload shape rejections:
  - `correctable_fields` names the missing, unsupported, or invalid payload field.
  - `alternative_capabilities` includes `context.get` or `context.summarize` when catalog/id discovery is useful.
- Task scope rejections:
  - `correctable_fields=["task_id"]`.
  - Alternative capability `task.list` or `track.join` when owned task ids are needed.
- Track lifecycle authority rejections:
  - `correctable_fields=["active_buddy"]` only when the issue is PM authority.
  - Alternative capability `track.list` or `track.get` for read-only inspection.
- Artifact payload and scope rejections:
  - `correctable_fields` includes `task_id`, `artifact_id`, `kind`, `title`, `content`, or `source_refs` as applicable.
  - Alternative capability `task.list`, `track.get`, or `artifact.list` when ids need discovery.
- Handoff payload and scope rejections:
  - `correctable_fields` includes `track_id`, `source_task_id`, `target_buddy`, `artifact_ids`, `source_refs`, `reason`, or `context`.
  - Alternative capability `handoff.validate`, `artifact.list`, or `task.list` as applicable.
- Context payload rejections:
  - `correctable_fields` includes unsupported filter keys.
  - Alternative capability `context.list_sources`.
- Evidence rejections:
  - `correctable_fields` includes `target_type`, `target_id`, `mode`, or `reason`.
  - Alternative capability `artifact.list` or `artifact.get`.
- Search rejections:
  - `correctable_fields` includes `query`, `backend`, `engine`, or browser readiness.
  - Alternative capability `search.status` or `search.open_browser` when conditional.
- Router and dispatch rejections:
  - Missing/unsupported tool or action identifies `tool`, `action`, or `args`.
  - Alternative capability points to `context.get`, `context.summarize`, or `turn_runtime.py status` as discovery surfaces.

**Do not modify:**

- Do not mark rejected calls as state-changing unless a service can prove a partial mutation occurred. The expected result for current rejection paths is `state_changed=false`.
- Do not use `allowed_next_action_options` as a mandatory workflow list.
- Do not hide root causes behind generic "try again" guidance.

**Observable result:**

- Representative rejection payloads explain why the call was blocked, whether state changed, what can be corrected, and what atomic capability can help.

**Verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_runtime_tool_feedback.py \
  tests/test_env_tool_router.py \
  tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_rejections_explain_correction_or_atomic_alternative \
  -q
```

### Task 2.6: Keep Allowed Next Action Options Conditional

**Current problem:** `allowed_next_action_options` is useful for conditional affordances, but it must not become a prescribed workflow.

**Files to modify:**

- `scripts/env/services/buddybox.py`
- `scripts/env/services/artifacts.py`
- `scripts/env/services/handoffs.py`
- `scripts/env/services/search.py`
- `scripts/env/services/context.py`
- `scripts/env/tools/responses.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_host_decision_surface_product_mode.py`

**Behavior or text type to modify:**

- Keep `allowed_next_action_options` for:
  - Buddybox private follow-up choices.
  - Artifact payload validation to artifact creation, phrased as "when the host decides to write the validated artifact".
  - Handoff validation to handoff creation, phrased as "when the host decides to persist the validated handoff".
  - Search request to browser open, phrased as "when the host needs to open the planned target".
  - Router discovery recovery, phrased as catalog inspection.
- Ensure each option row has `tool`, `action`, `mutates`, `preconditions`, `reason`, and `source_refs`.

**Do not modify:**

- Do not add `allowed_next_action_options` to every response.
- Do not say "must", "always", "only", or encode a business workflow in option reasons.

**Observable result:**

- Host sees optional atomic capabilities with source refs to the runtime catalog, not step-by-step business instructions.

**Verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_allowed_next_action_options_are_conditional_affordances \
  tests/test_host_decision_surface_product_mode.py \
  -q
```

## 9. Phase 3: Tighten Compact Context Discovery

### Task 3.1: Add Compact Discovery Tests

**Current problem:** `context.summarize.tool_affordances` currently distinguishes buddybox, artifact, handoff, and project source, but it does not cover enough first-pass env tool choices for task, track, context, evidence, and search.

**Files to modify:**

- `tests/test_context_binding_env_tool.py`
- `tests/test_host_decision_surface_product_mode.py`

**Behavior or text type to modify:**

- Assert `context.summarize.tool_affordances` contains compact rows for:
  - `task`
  - `track`
  - `artifact`
  - `handoff`
  - `buddybox`
  - `context`
  - `evidence`
  - `search`
  - `project_source`
- For each row, assert host-meaningful compact fields:
  - `capability`
  - `choose_when`
  - `id_inputs_from`
  - `returns`
  - `state_effect`
  - `durability`
  - `supports`
- Assert `context.summarize` still omits:
  - `tool_catalog`
  - `operation_semantics`
  - `payload_fields`
  - `action_semantics`
  - artifact body `content`
  - buddybox `content` and `content_base64`

**Do not modify:**

- Do not snapshot the entire compact payload.
- Do not require every tool action to appear in `supports`.
- Do not duplicate full catalog semantics.

**Observable result:**

- The test fails until compact affordances support first-round tool selection across env tools while staying compact.

**Verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_exposes_compact_first_pass_tool_affordances \
  tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_tool_affordances_stay_compact \
  -q
```

### Task 3.2: Update Compact Affordance Source

**Current problem:** Compact affordances are generated by `scripts/env/tools/semantics.py::compact_tool_affordances()` and are uneven across capabilities.

**Files to modify:**

- `scripts/env/tools/semantics.py`

**Behavior or text type to modify:**

- Replace the existing compact affordance map with compact rows for the nine first-pass capabilities listed in Task 3.1.
- Use concise values:
  - `task`: active-buddy task work items; ids from task/context/track surfaces; durable writes for create/update/archive.
  - `track`: collaboration tracks and task-track relations; ids from context/track surfaces; PM lifecycle writes and relation writes.
  - `artifact`: product-readable deliverables; ids from task/track/artifact/context surfaces; list summaries vs get body.
  - `handoff`: explicit cross-buddy collaboration records; source ids from owned tasks/artifacts; durable handoff writes.
  - `buddybox`: active-buddy private files; logical names chosen by host; active-instance-local private file writes.
  - `context`: read-only orientation and full catalog discovery; no writes.
  - `evidence`: target-scoped transient evidence tokens; target ids from artifacts.
  - `search`: backend status, target URL/browser intent, browser session open; no product object writes.
  - `project_source`: shared source workspace access; not an env tool, included only to distinguish source edits from product object and buddybox state.
- Keep row count small and values short enough for first-pass orientation.

**Do not modify:**

- Do not include `payload_fields`.
- Do not include `action_semantics`.
- Do not encode business workflows.
- Do not remove full semantics from `context.get`.

**Observable result:**

- `context.summarize.tool_affordances` gives enough information for a host to decide whether the next atomic capability is task, track, artifact, handoff, buddybox, context, evidence, search, or project source.

**Verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_context_binding_env_tool.py \
  tests/test_host_decision_surface_product_mode.py \
  -q
```

### Task 3.3: Update Context Response Text

**Current problem:** `context.summarize` and `context.get` responses are structurally correct, but success text should explicitly distinguish compact orientation from full catalog discovery.

**Files to modify:**

- `scripts/env/services/context.py`

**Behavior or text type to modify:**

- `context.get` success:
  - `effect_summary` says full runtime context sections plus full tool catalog and operation semantics.
  - `read_scope` says readable runtime context sections and catalog metadata.
- `context.summarize` success:
  - `effect_summary` says compact context, candidate ids, buddybox descriptor, and compact first-pass tool affordances.
  - `read_scope` says compact read-only orientation, not full catalog.
- `context.list_sources` success:
  - Keep source descriptor wording concise.

**Do not modify:**

- Do not add full catalog fields to `context.summarize`.
- Do not remove `tool_catalog` or `operation_semantics` from `context.get`.
- Do not change filters or context visibility rules.

**Observable result:**

- Runtime responses themselves tell a host when to use summarize versus get.

**Verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_context_binding_env_tool.py \
  tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_context_get_and_summarize_explain_catalog_scope \
  -q
```

### Task 3.4: Confirm Runtime Status Catalog Uses Full Semantics

**Current problem:** `scripts/turn_runtime.py status` should remain an outside-broker route to the full env tool catalog.

**Files to modify:**

- `tests/test_turn_runtime.py`
- `tests/test_repo_consistency.py`

**Behavior or text type to modify:**

- Add or refine tests that parse `python3 scripts/turn_runtime.py status` output and assert:
  - `env_tools` contains every registered tool.
  - `env_tools[tool].action_semantics` contains the clarified fields.
  - The full status catalog is richer than `context.summarize.tool_affordances`.

**Do not modify:**

- Do not change `scripts/turn_runtime.py` unless tests show it fails to expose `tool_contracts.env_tools_description()`.
- Do not add another CLI catalog command.

**Observable result:**

- Host can use `turn_runtime.py status` as the full catalog route from outside a broker call.

**Verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_env_tool_surface_is_runtime_visible_and_runless \
  -q
```

## 10. Phase 4: Trim Shared Skills To Workflow Guidance

### Task 4.1: Add Shared Skill Boundary Tests

**Current problem:** Shared skills are short overall, but `buddybox-tool` carries action-level details and common flows that belong primarily in runtime semantics and response feedback.

**Files to modify:**

- `tests/test_runtime_skills.py`
- `tests/test_repo_consistency.py`

**Behavior or text type to modify:**

- Add boundary tests for all shared tool skills:
  - They mention `env.tool`.
  - They point to `context.get.tool_catalog`, `context.summarize.tool_affordances`, or runtime response feedback for action details.
  - They do not contain `payload_fields`, `action_semantics`, or full operation inventories beyond a concise operation list.
  - They do not contain business workflow prescriptions such as "after writing a PRD", "market research should", or "if the user says".
  - They do not override `permission_boundary`, `why_blocked`, `state_changed`, `durability`, `correctable_fields`, or `alternative_capabilities`.
- Replace the current buddybox skill test that expects many long sections with a boundary-focused test:
  - skill still explains private active-buddy file use cases.
  - skill still says to trust runtime feedback.
  - skill no longer needs a "Common Flows" catalog.

**Do not modify:**

- Do not test exact full skill prose.
- Do not require skills to contain every payload field.
- Do not let skill tests become a second runtime catalog.

**Observable result:**

- Tests fail if shared skills drift into long action manuals or workflow prescriptions.

**Verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_shared_skills_are_runless \
  -q
```

### Task 4.2: Trim `task-tool`, `track-tool`, `artifact-tool`, And `handoff-tool`

**Current problem:** These skills are already compact, but they should consistently say that runtime catalog and tool feedback own action details.

**Files to modify:**

- `buddyswitch/skills/shared/task-tool/SKILL.md`
- `buddyswitch/skills/shared/track-tool/SKILL.md`
- `buddyswitch/skills/shared/artifact-tool/SKILL.md`
- `buddyswitch/skills/shared/handoff-tool/SKILL.md`

**Behavior or text type to modify:**

- Keep each skill to:
  - purpose
  - CLI route
  - workflow-level reminders
  - verification through `ok`, returned ids, and runtime feedback
- Add one consistent sentence:
  - "For action payloads and return meanings, inspect `context.get.tool_catalog['<tool>']` or `python3 scripts/turn_runtime.py status`; runtime response fields are authoritative for effects and recovery."
- Remove payload examples that duplicate action semantics where they are not needed for repeated workflow guidance.
- Keep operation lists concise because they are route maps, not catalog mirrors.

**Do not modify:**

- Do not add business workflow sequences.
- Do not copy `inputs_explained` from `semantics.py`.
- Do not delete skill identity/frontmatter.

**Observable result:**

- Shared skills tell a host how to orient and where to inspect tool details, while action meaning lives in the runtime catalog.

**Verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_shared_tool_skills_teach_env_tool_not_prepare_persist \
  -q
```

### Task 4.3: Trim `buddybox-tool`

**Current problem:** `buddyswitch/skills/shared/buddybox-tool/SKILL.md` currently includes logical-name rules, payload examples, response checks, promotion rule, runtime closing, and common flows. Some of this is workflow guidance, but action-level detail and catalog-like flows should defer to runtime semantics and responses.

**Files to modify:**

- `buddyswitch/skills/shared/buddybox-tool/SKILL.md`

**Behavior or text type to modify:**

- Keep:
  - Buddybox is active-buddy private file capability.
  - Other buddies cannot list/read/write/delete these files.
  - Product-readable content uses artifact when the host decides sharing is needed.
  - CLI route examples for `desc`, `list`, `read`, `write`, and `delete`.
  - A short reminder to use logical names, not direct filesystem paths.
  - A short response rule: trust `state_changed`, `durability`, `allowed_next_action_options`, `correctable_fields`, and `alternative_capabilities`.
- Remove:
  - Long common-flow catalog.
  - Detailed payload field explanation beyond one text write and one binary write example.
  - Any wording that implies promotion is required after writing private files.
  - Any mention of shell-searching buddybox roots.
- Add:
  - "When an action detail is unclear, inspect `context.get.tool_catalog['buddybox']`; when a call is rejected, runtime feedback wins over this skill."

**Do not modify:**

- Do not reintroduce `--path`.
- Do not expose private filesystem roots.
- Do not say `buddybox.search` exists unless it is registered in the runtime catalog.
- Do not turn the skill into a complete action catalog.

**Observable result:**

- Buddybox skill stays useful for repeated private-file work while runtime semantics own exact action meanings and feedback.

**Verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_runtime_skills.py::RuntimeSkillsTests::test_buddybox_tool_teaches_env_tool_not_direct_filesystem \
  tests/test_runtime_skills.py::RuntimeSkillsTests::test_buddybox_tool_skill_stays_workflow_level_and_defers_to_runtime_feedback \
  -q
```

### Task 4.4: Verify AGENTS Route Maps Stay Short

**Current problem:** AGENTS should point to discovery surfaces and boundaries only. Current files already do this; this task prevents accidental expansion while editing skills or tests.

**Files to modify:**

- `tests/test_repo_consistency.py`
- `tools/launcher/assets/buddies/*/AGENTS.md` only if a route-map test fails because of stale or over-detailed wording.

**Behavior or text type to modify:**

- Add or refine a grep-style test that buddy AGENTS files:
  - contain `context summarize`.
  - contain `context get` or `turn_runtime.py status`.
  - contain env tool names as a short route map.
  - do not contain `payload_fields`, `action_semantics`, `content_base64`, phrase routing, or business workflow steps.

**Do not modify:**

- Do not expand AGENTS into a tool manual.
- Do not remove the direct runtime-state edit prohibition.

**Observable result:**

- AGENTS remains the route map layer and does not duplicate runtime semantics.

**Verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_buddy_agents_contain_direct_id_artifact_read_boundary \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_search_tool_visible_surface_is_projected \
  -q
```

## 11. Final Regression Verification

Run focused semantic and feedback gates:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_context_binding_env_tool.py \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_runtime_tool_feedback.py \
  tests/test_runtime_skills.py \
  -q
```

Run tool behavior suites touched by response text:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_task_env_tool.py \
  tests/test_track_env_tool.py \
  tests/test_artifact_env_tool.py \
  tests/test_handoff_env_tool.py \
  tests/test_buddybox_env_tool.py \
  tests/test_evidence_env_tool.py \
  tests/test_search_env_tool.py \
  tests/test_env_tool_router.py \
  tests/test_env_layer_end_to_end.py \
  -q
```

Run runtime visibility and consistency gates:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py \
  tests/test_run_env_tool.py \
  tests/test_prepare_runtime_context.py \
  tests/test_runless_runtime_contract.py \
  tests/test_repo_consistency.py \
  -q
```

Inspect runtime catalog manually:

```bash
python3 scripts/turn_runtime.py status
```

Expected manual checks:

- `env_tools` contains the registered tools only: `task`, `track`, `artifact`, `handoff`, `buddybox`, `context`, `evidence`, `search`.
- Each tool has `action_semantics`.
- No visible action semantic contains the rejected template phrases.
- `context.summarize.tool_affordances` is compact and does not include `tool_catalog` or `action_semantics`.
- Shared skills remain short workflow guidance and defer action details to runtime catalog and feedback.

## 12. Traceability Matrix

| Memo item | Implementation tasks | Verification |
| --- | --- | --- |
| Host can know what capability a tool provides | Tasks 1.2, 1.3, 1.4, 3.2 | `test_semantic_text_rejects_template_action_language`, compact affordance tests |
| Host can know what an action reads, validates, creates, updates, deletes, issues, or opens | Tasks 1.2, 1.3, 1.4, 2.3, 2.4 | semantic contract tests, response success matrix |
| Host can know where ids or payloads come from | Tasks 1.2, 1.3, 2.5, 3.2 | semantic input tests, rejection correction tests |
| Host can know return content level | Tasks 1.3, 1.4, 2.3, 3.2 | read/list/get content-level tests |
| Host can know whether state changed | Tasks 2.3, 2.4, 2.5 | response contract tests, end-to-end tests |
| Host can know durability | Tasks 1.2, 1.3, 1.4, 2.3, 2.4 | semantic side-effect tests, response success matrix |
| Host can understand rejection reasons | Task 2.5 | runtime feedback tests |
| Host can know rejection state impact | Task 2.5 | rejection tests asserting `state_changed=false` and impact text |
| Host can correct fields or choose alternative atomic capabilities | Tasks 2.5, 2.6 | correction and alternative capability tests |
| Tool layer describes atomic capabilities | Tasks 1.2, 1.3, 1.4 | semantic no-business-workflow tests |
| Tool response explains actual effect and recovery | Tasks 2.3, 2.4, 2.5, 2.6 | response contract and runtime feedback tests |
| Skill layer owns repeated workflows | Tasks 4.1, 4.2, 4.3 | runtime skill boundary tests |
| AGENTS only points to route map | Task 4.4 | repo consistency AGENTS tests |
| No semantic v2 | Task 1.5 | repo consistency and semantic projection tests |
| No workflow engine, phrase router, rule engine, or tool-search subsystem | Tasks 1.5, 2.2, 4.4 | repo consistency forbidden-token tests |
| No business workflow in tool descriptions | Tasks 1.1, 1.2, 1.3, 1.4, 2.6 | semantic and option phrase regression tests |
| `allowed_next_action_options` stays conditional | Tasks 2.2, 2.6 | conditional affordance tests |
| Compact discovery supports first-round choice without copying catalog | Tasks 3.1, 3.2, 3.3 | context summarize compactness tests |
| Shared skills do not replace runtime feedback | Tasks 4.1, 4.2, 4.3 | runtime skill boundary tests |
| Reject obvious template phrases | Task 1.1 | semantic phrase regression tests |
| Mutating actions state what they mutate and do not mutate | Tasks 1.2, 1.3, 1.4, 2.4 | semantic side-effect and response success tests |
| Representative rejections expose impact and recovery fields | Task 2.5 | runtime feedback tests |

## 13. Self-Check

- The plan covers the full memo task across semantics, responses, compact context discovery, shared skills, AGENTS route-map verification, and regression gates.
- The plan contains no placeholder sections or deferred work.
- The plan does not introduce semantic v2, workflow engines, phrase routers, tool-search subsystems, or business workflow encoding in tool descriptions.
- Each development task names current problem, files, behavior/text type, prohibited changes, observable result, and verification.
- The traceability matrix maps memo goals, boundaries, non-goals, and verification direction to concrete tasks.
