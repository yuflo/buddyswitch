# Host Decision Surface Full Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` before implementing this plan task-by-task. Use `superpowers:test-driven-development` for each behavior phase and `superpowers:verification-before-completion` before claiming a phase is done.

**Goal:** Upgrade BuddySwitch's env layer so a Codex CLI host can infer relevant context, safe operations, evidence requirements, and next product actions from runtime state and env feedback without handoff inboxes, automatic routing, workflow rules, or prompt recipes.

**Architecture:** Keep BuddySwitch as an environment and coordination layer. Replace hand-maintained env contracts and string-only context descriptions with a small static contract registry, structured context descriptors, a runtime decision surface, discovery summaries, canonical response helpers, and semantic tests. Services continue to own dynamic validation, permissions, state mutation, evidence issuance, and run commit behavior.

**Tech Stack:** Python stdlib, `scripts/turn_runtime.py`, broker-routed `env.tool`, service modules under `scripts/env/services/`, static env tool registry under `scripts/env/tools/`, runtime object store via `scripts/env_store.py`, launcher instance JSON, pytest/unittest, product-mode CLI smoke checks.

---

## Working Directory

Run all implementation from:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev2258
```

Do not edit `/Users/chen/Dev/buddyswitch`.

## Source Spec

Primary spec:

- `docs/spec/2026-05-11-host-decision-surface-env-upgrade-plan.md`

This plan covers the full spec, not only the recommended first slice. The shortest validated path is still phase-based: every phase starts with failing semantic tests, lands the smallest direct implementation, deletes or replaces the old active surface in the same change set, and runs a focused gate.

## Product Bottleneck

BuddySwitch already has broker-routed tools, runtime-owned state, track/task/artifact objects, handoff validation, evidence gates, and prepare context. The blocker is that active surfaces expose many fields but not enough host decision semantics. The upgrade must make binding state, active-buddy relation, discovery relevance, operation mutability, evidence readiness, and response recovery options explicit while preserving host autonomy.

## Forward-Only Rules

- Do not add a handoff inbox, automatic router, fixed flow rule, workflow engine, event bus, DSL, or prompt recipe.
- Do not keep old and new active paths side by side.
- Do not keep compatibility wrappers for old response shapes.
- Do not make tests accept either the old or new behavior.
- Delete shallow field-existence assertions as semantic assertions land.
- Keep full artifact content only in allowed current-task context or allowed artifact reads.
- Keep discovery read-only and non-binding.
- Keep dynamic permission and state checks in service code, not in the static registry.

## File Responsibility Map

| File | Action | Responsibility |
|---|---|---|
| `scripts/env/tools/contracts.py` | Create | Static source of truth for env tool names, manager names, CLI resources, action names, payload schema views, operation kind, mutability, required permission, authority, preconditions, and return fields. It must not encode state-dependent workflow policy. |
| `scripts/env/tools/responses.py` | Create | Lightweight canonical response helpers for success, rejection, runtime feedback projection, and structured next-action options. It replaces repeated boilerplate without preserving mirrored legacy fields. |
| `scripts/env/services/context.py` | Modify | Own structured context source descriptors, current context sections, decision surface builder, candidate track summaries for unbound or task-only hosts, and compact context summaries. |
| `scripts/env/services/tracks.py` | Modify | Own track discovery semantics, relevance ranking, `track.list.discovery`, `track.list.discovery_summary`, and `track.get.track_context_summary` without leaking full foreign artifact content. |
| `scripts/env/services/handoffs.py` | Modify | Add outgoing handoff `track_alignment` and post-commit `discoverability` semantics for success and transition-conflict responses. |
| `scripts/env/services/artifacts.py` | Modify | Add artifact decision metadata to list/get/current outputs: kind, title, summary, source buddy, source run, revision, and currentness while preserving active-buddy read boundaries. |
| `scripts/env/services/evidence.py` | Modify | Make evidence issuance responses and rejections expose exact persist fields, active run scope, and structured recovery options. |
| `scripts/env/services/runs.py` | Modify | Preserve run commit atomicity while recording and returning decision-relevant evidence, artifact, handoff, and refreshed context metadata. |
| `scripts/env/services/tasks.py` | Modify | Use shared response helpers and structured next-action options for decision-critical task and stale-binding responses when the response helper phase lands. |
| `scripts/env/services/bindings.py` | Modify | Use shared response helpers and structured next-action options for binding rejection and non-PM track binding feedback. |
| `scripts/turn_runtime.py` | Modify | Replace hand-authored `_build_env_tools_desc()` content with registry-derived output, add `runtime_context.decision_surface`, include operation semantics, and keep prepare context compact. |
| `scripts/env/tools/router.py` | Modify | Derive supported tools, supported actions, dispatcher lookup, and hint text from `contracts.py`. Own the single unknown-tool/action boundary. |
| `scripts/env/tools/*_manager.py` | Modify | Keep thin dispatchers, derive handler maps from registry where practical, and delete duplicated unknown-action validation once router owns it. |
| `scripts/env/client.py` | Modify | Add registry consistency tests first, then derive CLI operation/action consistency from the registry if duplication remains. Keep CLI output JSON-compatible with canonical response shape. |
| `framework/docs/turn-runtime-spec.md` | Modify | Document `runtime_context.decision_surface`, structured context descriptors, env tool operation semantics, discovery responses, and canonical response fields. Remove old string-only descriptor language. |
| `buddyswitch/skills/shared/task-manager/SKILL.md` | Modify | Keep references aligned with runtime feedback as authoritative; do not add permission matrices or decision recipes. |
| `buddyswitch/skills/shared/track-manager/SKILL.md` | Modify | Keep references aligned with track discovery surfaces; do not add a required call order or raw-state guidance. |
| `buddyswitch/skills/shared/artifact-manager/SKILL.md` | Modify | Keep references aligned with artifact decision metadata and active-buddy content boundaries. |
| `tests/test_prepare_runtime_context.py` | Modify | Add semantic runtime context, structured descriptor, decision surface, env tool operation semantics, and Market readiness tests. Replace shallow context field checks. |
| `tests/test_context_binding_env_tool.py` | Modify | Add context summarization, candidate track, decision surface, handoff alignment, and stale context structured recovery tests. |
| `tests/test_track_manager_env_tool.py` | Modify | Add track discovery, ranking, `track.get` context summary, no-mutation, and no foreign full-content leak tests. |
| `tests/test_env_tool_response_contract.py` | Modify | Add canonical response shape and structured next-action option tests across success and rejection responses. Remove mirrored-field expectations. |
| `tests/test_env_tool_router.py` | Modify | Add registry-driven router support and single unknown-action boundary tests. |
| `tests/test_repo_consistency.py` | Modify | Add residue checks for retired active surfaces, registry drift, no prompt recipes, no old string-only descriptors, no mirrored response fields, and no duplicated allowlists. |
| `tests/test_artifact_manager_env_tool.py` | Modify | Add artifact decision metadata and foreign content boundary tests. |
| `tests/test_market_browser_evidence.py` | Modify | Add evidence readiness, exact persist field, structured recovery, and run-scoped evidence tests. |
| `tests/test_runtime_tool_feedback.py` | Modify | Add stale context, handoff conflict, Market evidence, and response helper feedback tests. |
| `tests/test_env_layer_end_to_end.py` | Modify | Add product flow checks for PM handoff to Market, Market evidence, market-scan artifact, and handoff to Design. |
| `tests/test_host_decision_surface_product_mode.py` | Create | Focused product-mode scenario tests using existing broker/runtime fixtures, not a new eval framework. |
| `docs/spec/2026-05-11-host-decision-surface-full-implementation-plan.md` | Create | This full implementation plan. |
| `docs/spec/2026-05-11-host-decision-surface-full-test-plan.md` | Create | Companion full test plan. |

### Delete Or Replace Active Surfaces

No whole source file is expected to be deleted in the current tree. The deletion work is inside active files:

- Delete the hand-authored env tool contract map inside `scripts/turn_runtime.py`.
- Delete duplicated router and manager action allowlists after the registry owns action names.
- Delete manager-local unknown-action rejection paths once router tests prove the router owns that boundary.
- Delete string-only `context_sources_desc()` behavior and tests that accept plain strings.
- Delete response field mirrors that exist only for older tests.
- Delete shallow field-existence tests as semantic tests replace them.
- Delete active docs that imply old context source strings, raw-state discovery, or prompt-level routing.

## Phase 0: Semantic Characterization Tests

**Goal:** Lock the required host decision semantics before production changes.

**Files:**

- Modify `tests/test_prepare_runtime_context.py`
- Modify `tests/test_context_binding_env_tool.py`
- Modify `tests/test_track_manager_env_tool.py`
- Modify `tests/test_env_tool_response_contract.py`
- Modify `tests/test_artifact_manager_env_tool.py`
- Modify `tests/test_market_browser_evidence.py`
- Modify `tests/test_runtime_tool_feedback.py`
- Modify `tests/test_repo_consistency.py`

**Depends on test plan:** TG-01, TG-02, TG-04, TG-05, TG-06, TG-07, TG-11.

**Implementation steps:**

- [ ] Add helper fixtures that seed a PM track with `next_buddy="market"`, a PM PRD artifact, and a committed run audit handoff to Market.
- [ ] Add `test_market_prepare_decision_surface_marks_task_only_binding_and_candidate_track_absence` to `tests/test_prepare_runtime_context.py`.
- [ ] Add `test_bound_market_prepare_decision_surface_marks_next_buddy_handoff_and_evidence_requirement` to `tests/test_prepare_runtime_context.py`.
- [ ] Add `test_context_summarize_unbound_market_returns_candidate_tracks_without_binding_mutation` to `tests/test_context_binding_env_tool.py`.
- [ ] Add `test_track_list_ranks_recent_handoff_and_next_buddy_candidates_for_active_buddy` to `tests/test_track_manager_env_tool.py`.
- [ ] Add `test_handoff_validate_returns_track_alignment_and_discoverability` to `tests/test_context_binding_env_tool.py`.
- [ ] Add `test_decision_critical_rejections_include_structured_next_action_options` to `tests/test_env_tool_response_contract.py`.
- [ ] Add residue tests that initially fail for duplicated allowlists, duplicate unknown-action validation, string-only context descriptors, mirrored response fields, and shallow field-only assertions.
- [ ] Run the focused gate and confirm the new semantic assertions fail for missing new fields, while unrelated existing tests still describe current behavior.

**Must delete or replace in this phase:**

- Replace shallow assertions added for the same surfaces with semantic assertions in the same test edits.
- Delete test expectations that only require `context_sources_desc` values to be non-empty strings.
- Delete any newly discovered test branch that accepts either old or new response shape.

**Focused verification command:**

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_prepare_runtime_context.py \
  tests/test_context_binding_env_tool.py \
  tests/test_track_manager_env_tool.py \
  tests/test_env_tool_response_contract.py \
  tests/test_artifact_manager_env_tool.py \
  tests/test_market_browser_evidence.py \
  tests/test_runtime_tool_feedback.py \
  tests/test_repo_consistency.py \
  -q
```

**Acceptance criteria:**

- New tests fail for absent semantics, not fixture errors.
- Existing ownership, evidence, and run-commit tests remain meaningful.
- No new test asserts only that a field exists or a string is non-empty.

## Phase 1: Structured Context Source Descriptors

**Goal:** Replace string-only context source descriptions with structured descriptors that tell the host content depth, scope, nullability, source of truth, projection, and decision use.

**Files:**

- Modify `scripts/env/services/context.py`
- Modify `scripts/turn_runtime.py`
- Modify `tests/test_prepare_runtime_context.py`
- Modify `tests/test_context_binding_env_tool.py`
- Modify `framework/docs/turn-runtime-spec.md`
- Modify `tests/test_repo_consistency.py`

**Depends on test plan:** TG-02, TG-11.

**Implementation steps:**

- [ ] Write failing descriptor assertions for `request_text`, `task_context.task`, `task_context.artifacts`, `track_context.track`, `track_context.recent_handoffs`, and `current_context_summary`.
- [ ] Change `context_sources_desc()` to return descriptor dictionaries with `description`, `content`, `scope`, `nullable`, and `decision_use`.
- [ ] Add `source_of_truth`, `max_items`, `sorted_by`, or `summary_projection` where the spec defines them.
- [ ] Ensure `task_context.artifacts.content == "full"` and `current_context_summary.content == "summary"`.
- [ ] Update `context.list_sources` to return the same structured descriptors.
- [ ] Update prepare tests to assert descriptor semantics and artifact content boundaries.
- [ ] Update runtime docs to describe the structured descriptor contract.

**Must delete or replace in this phase:**

- Delete string-only descriptor expectations.
- Delete docs that describe `context_sources_desc` as a string dictionary.
- Delete any compatibility branch that exposes a parallel legacy descriptor map.

**Focused verification command:**

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_prepare_exposes_context_sources_for_product_work \
  tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_tools_return_current_context_without_raw_global_state \
  tests/test_repo_consistency.py \
  -q
```

**Acceptance criteria:**

- Prepare and `context.list_sources` expose identical structured descriptor semantics.
- Full artifact content remains in `task_context.artifacts`.
- Compact summaries do not leak full artifact content.

## Phase 2: Runtime Decision Surface

**Goal:** Add `runtime_context.decision_surface` and expose the same surface through `context.get` and `context.summarize`.

**Files:**

- Modify `scripts/env/services/context.py`
- Modify `scripts/turn_runtime.py`
- Modify `tests/test_prepare_runtime_context.py`
- Modify `tests/test_context_binding_env_tool.py`
- Modify `tests/test_market_browser_evidence.py`
- Modify `framework/docs/turn-runtime-spec.md`

**Depends on test plan:** TG-01, TG-06, TG-07.

**Implementation steps:**

- [ ] Write failing tests for each stable enum value path: `unbound`, `bound_task_only`, `bound_track_only`, `bound_task_and_track`, and stale binding when feasible.
- [ ] Add `build_decision_surface(...)` in `scripts/env/services/context.py`.
- [ ] Include `binding_state`, `active_buddy_relation`, `context_readiness`, `evidence_readiness`, and `safe_read_affordances`.
- [ ] Derive task role from active buddy and current task ownership.
- [ ] Derive track role from `track.current_buddy`, `track.next_buddy`, active-buddy participation, and missing track state.
- [ ] Derive latest handoff relevance from committed run audits, not from a new inbox.
- [ ] Add source refs such as `track_context.track.next_buddy` and `track_context.recent_handoffs[0]`.
- [ ] Include Market evidence readiness from `runtime_context.tool_requirements` and `persist_payload_hint.tool_evidence`.
- [ ] Reuse the builder in `_build_runtime_context()` and `current_context_sections()`.

**Must delete or replace in this phase:**

- Delete old tests that infer readiness from unrelated field presence.
- Delete any field name that implies selected route, selected track, required next step, or automatic binding.
- Replace duplicated readiness snippets with the single builder.

**Focused verification command:**

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_prepare_runtime_context.py \
  tests/test_context_binding_env_tool.py \
  tests/test_market_browser_evidence.py::MarketBrowserEvidenceTests::test_market_profile_requires_browser_evidence \
  -q
```

**Acceptance criteria:**

- Fresh Market can see missing track and safe read affordances.
- Bound Market can see `track_role == "next_buddy"` and `latest_handoff_to_active_buddy is True`.
- The decision surface is descriptive and never mutates binding.

## Phase 3: Track And Context Discovery Semantics

**Goal:** Make readable tracks usable as candidate collaboration context without adding an inbox or auto-binding behavior.

**Files:**

- Modify `scripts/env/services/tracks.py`
- Modify `scripts/env/services/context.py`
- Modify `tests/test_track_manager_env_tool.py`
- Modify `tests/test_context_binding_env_tool.py`
- Modify `tests/test_artifact_manager_env_tool.py`
- Modify `framework/docs/turn-runtime-spec.md`

**Depends on test plan:** TG-04, TG-08, TG-09.

**Implementation steps:**

- [ ] Write failing tests for unbound Market discovery through `track.list`, `track.get`, and `context.summarize`.
- [ ] Add a compact discovery builder in `tracks.py` or a shared context helper that takes active buddy, track, tasks, current artifact slots, and recent run audit handoffs.
- [ ] Add `discovery.active_buddy_role`, `relevance_reasons`, task count, buddies with tasks, current artifact kinds, latest handoff to active buddy, latest run timestamp, and `has_context_available` to `track.list` rows.
- [ ] Add `discovery_summary.active_buddy`, candidate count, candidate ids, and basis to `track.list`.
- [ ] Add deterministic sort order: recent handoff to active buddy, `track.next_buddy`, active-buddy task participation, latest handoff timestamp, track `updated_at`, track id.
- [ ] Add `track_context_summary` to `track.get` with compact track, active-buddy relevance, tasks, current artifact metadata, and recent handoffs.
- [ ] Add `candidate_tracks` to `context.summarize` when no track is bound or no handoff to the active buddy is visible in the current track context.
- [ ] Assert no instance JSON changes during discovery calls.

**Must delete or replace in this phase:**

- Delete discovery tests that only assert a returned row count.
- Delete any track discovery branch that exposes full foreign artifact content.
- Delete any behavior that suggests non-PM arbitrary `binding.set_track` as the recovery path for Market.

**Focused verification command:**

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_track_manager_env_tool.py \
  tests/test_context_binding_env_tool.py \
  tests/test_artifact_manager_env_tool.py \
  -q
```

**Acceptance criteria:**

- `track.list` and `context.summarize` expose candidate PM handoff context for unbound Market.
- `track.get` exposes compact track context and artifact metadata, not full foreign content.
- Discovery never changes current task or track binding.

## Phase 4: Handoff Validation Semantics

**Goal:** Clarify outgoing handoff validation and post-commit discoverability.

**Files:**

- Modify `scripts/env/services/handoffs.py`
- Modify `tests/test_context_binding_env_tool.py`
- Modify `tests/test_env_tool_response_contract.py`
- Modify `tests/test_runtime_tool_feedback.py`
- Modify `framework/docs/turn-runtime-spec.md`

**Depends on test plan:** TG-04, TG-05.

**Implementation steps:**

- [ ] Write failing tests for successful `track_alignment` with `target_matches_track_next_buddy is True`.
- [ ] Write failing tests for transition conflict `track_alignment` with `requested_next_buddy`, `target_matches_track_next_buddy is False`, and `suggested_next_buddy`.
- [ ] Add `track_id_source` values for `args`, `active_instance_binding`, and `none`.
- [ ] Add success `discoverability` with `will_be_discoverable_by_next_buddy`, `discovery_basis`, `available_after`, and `discovery_surfaces`.
- [ ] Keep validation non-mutating and prove instance JSON and track objects are unchanged.
- [ ] Update response contract tests to assert handoff semantics rather than only `allowed_next_actions`.

**Must delete or replace in this phase:**

- Delete ambiguity that lets hosts treat `handoff.validate` as incoming discovery.
- Delete conflict responses that omit structured target alignment.
- Delete old tests that check only `permission_boundary == "handoff.track_transition"`.

**Focused verification command:**

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_handoff_validate_accepts_known_target_and_rejects_unknown_or_conflicting_target \
  tests/test_env_tool_response_contract.py \
  tests/test_runtime_tool_feedback.py \
  -q
```

**Acceptance criteria:**

- Host can tell whether the requested next buddy matches the track transition.
- Host can tell discoverability appears after `run.commit` through `track.list`, `track.get`, and `context.summarize`.
- No handoff validation path mutates track lifecycle or binding.

## Phase 5: Env Tool Static Contract Registry

**Goal:** Stop contract drift and expose operation semantics from one static source.

**Files:**

- Create `scripts/env/tools/contracts.py`
- Modify `scripts/turn_runtime.py`
- Modify `scripts/env/tools/router.py`
- Modify `scripts/env/tools/task_manager.py`
- Modify `scripts/env/tools/track_manager.py`
- Modify `scripts/env/tools/artifact_manager.py`
- Modify `scripts/env/tools/context_manager.py`
- Modify `scripts/env/tools/binding_manager.py`
- Modify `scripts/env/tools/handoff_manager.py`
- Modify `scripts/env/tools/run_manager.py`
- Modify `scripts/env/tools/evidence_manager.py`
- Modify `scripts/env/client.py`
- Modify `tests/test_prepare_runtime_context.py`
- Modify `tests/test_env_tool_router.py`
- Modify `tests/test_env_tool_response_contract.py`
- Modify `tests/test_repo_consistency.py`

**Depends on test plan:** TG-03, TG-11.

**Implementation steps:**

- [ ] Write failing registry consistency tests before creating the registry.
- [ ] Add frozen dataclasses `PayloadSchema`, `ActionSpec`, and `ToolSpec`.
- [ ] Register all active tools: task, track, artifact, context, binding, handoff, run, evidence.
- [ ] Encode every active action with CLI operation name, payload schema view, action kind, mutability, required permission, authority, preconditions, and return fields.
- [ ] Replace `_build_env_tools_desc()` hand-authored maps with registry-derived manager descriptions.
- [ ] Add `operation_semantics` for every action in prepare runtime context.
- [ ] Make router supported tools, supported actions, dispatchers, and hint names derive from the registry.
- [ ] Keep manager dispatcher files thin and derive handler validation from the registry where practical.
- [ ] Add CLI operation/action consistency tests. Generate CLI from registry only if the remaining duplication is still a proven maintenance risk.

**Must delete or replace in this phase:**

- Delete hand-authored tool/action allowlists in `scripts/turn_runtime.py`.
- Delete duplicated router allowlists.
- Delete duplicated manager unknown-action validation once router is the single action boundary.
- Delete tests that compare separate hardcoded lists instead of comparing registry-derived surfaces.

**Focused verification command:**

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_prepare_exposes_env_tool_hints \
  tests/test_env_tool_router.py \
  tests/test_env_tool_response_contract.py \
  tests/test_repo_consistency.py \
  -q
```

**Acceptance criteria:**

- Every registry action appears in prepare env tool descriptions.
- Every prepare action has operation semantics.
- Router and manager action names match the registry.
- Static registry contains no dynamic workflow policy.

## Phase 6: Shared Response Helpers And Canonical Shape

**Goal:** Replace repeated response boilerplate with canonical helpers and remove mirrored legacy response fields.

**Files:**

- Create `scripts/env/tools/responses.py`
- Modify `scripts/env/services/tasks.py`
- Modify `scripts/env/services/tracks.py`
- Modify `scripts/env/services/artifacts.py`
- Modify `scripts/env/services/context.py`
- Modify `scripts/env/services/bindings.py`
- Modify `scripts/env/services/handoffs.py`
- Modify `scripts/env/services/runs.py`
- Modify `scripts/env/services/evidence.py`
- Modify `scripts/env/tools/router.py`
- Modify `tests/test_env_tool_response_contract.py`
- Modify `tests/test_runtime_tool_feedback.py`
- Modify `tests/test_repo_consistency.py`

**Depends on test plan:** TG-05, TG-11.

**Implementation steps:**

- [ ] Characterize current success and rejection shape in response contract tests.
- [ ] Add `success_response(...)`, `rejection_response(...)`, and `runtime_feedback_fields(...)` helpers.
- [ ] Keep `permission_boundary`, `allowed_next_actions`, `allowed_next_action_options`, `command_hint`, and `stop_condition` authoritative at top level.
- [ ] Keep `error.code` and `error.message` inside `error`.
- [ ] Migrate one service at a time, running service-specific tests after each migration.
- [ ] Update contract tests to reject mirrored fields that are not part of the canonical shape.
- [ ] Keep dynamic service context in services; the helper only shapes responses.

**Must delete or replace in this phase:**

- Delete copied `_error_payload` implementations where the helper replaces them.
- Delete old mirrored response fields that exist only for tests.
- Delete tests that require duplicated feedback in more than one location.

**Focused verification command:**

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_response_contract.py \
  tests/test_runtime_tool_feedback.py \
  tests/test_task_manager_env_tool.py \
  tests/test_track_manager_env_tool.py \
  tests/test_artifact_manager_env_tool.py \
  tests/test_context_binding_env_tool.py \
  tests/test_run_env_tool.py \
  tests/test_evidence_env_tool.py \
  -q
```

**Acceptance criteria:**

- Success and rejection envelopes are canonical across env tools.
- No active response field mirror remains only to satisfy older tests.
- Service-specific permission and mutation behavior is unchanged.

## Phase 7: Structured Next Action Options

**Goal:** Add machine-readable recovery and safe-affordance options while retaining human-readable `allowed_next_actions`.

**Files:**

- Modify `scripts/env/tools/responses.py`
- Modify `scripts/env/services/context.py`
- Modify `scripts/env/services/tracks.py`
- Modify `scripts/env/services/handoffs.py`
- Modify `scripts/env/services/evidence.py`
- Modify `scripts/env/services/artifacts.py`
- Modify `scripts/env/services/bindings.py`
- Modify `scripts/env/services/tasks.py`
- Modify `scripts/env/services/runs.py`
- Modify `tests/test_env_tool_response_contract.py`
- Modify `tests/test_runtime_tool_feedback.py`
- Modify `tests/test_track_manager_env_tool.py`
- Modify `tests/test_context_binding_env_tool.py`
- Modify `tests/test_market_browser_evidence.py`
- Modify `tests/test_repo_consistency.py`

**Depends on test plan:** TG-06, TG-11.

**Implementation steps:**

- [ ] Write failing tests for decision-critical responses listed in the source spec.
- [ ] Add a helper that validates each option's `tool` and `action` against `contracts.py` and copies static `mutates` semantics from the registry.
- [ ] Add structured options to fresh/unbound `context.summarize`.
- [ ] Add structured options to `track.get_current` with no track, `track.list`, and `track.get`.
- [ ] Add structured options to `handoff.validate` success and conflict responses.
- [ ] Add structured options to Market missing-evidence rejection.
- [ ] Add structured options to stale context, non-PM track lifecycle, foreign task, and foreign artifact rejections.
- [ ] Retain human-readable `allowed_next_actions` as a concise text projection.

**Must delete or replace in this phase:**

- Delete string-only recovery tests for decision-critical responses.
- Delete options that point to raw-state writes, automatic route selection, or binding mutation when the response is read-only.
- Delete duplicated hand-written mutability labels that drift from registry semantics.

**Focused verification command:**

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_response_contract.py \
  tests/test_runtime_tool_feedback.py \
  tests/test_track_manager_env_tool.py \
  tests/test_context_binding_env_tool.py \
  tests/test_market_browser_evidence.py \
  tests/test_repo_consistency.py \
  -q
```

**Acceptance criteria:**

- Decision-critical responses include structured options with `id`, `tool`, `action`, `mutates`, `preconditions`, `reason`, and `source_refs`.
- Options match registry tool/action names.
- Options describe affordances without forcing a workflow.

## Phase 8: Market Evidence And Artifact Decision Surface

**Goal:** Align Market browser evidence, artifact production, artifact metadata, and handoff continuation with the decision surface.

**Files:**

- Modify `scripts/env/services/evidence.py`
- Modify `scripts/env/services/artifacts.py`
- Modify `scripts/env/services/runs.py`
- Modify `scripts/env/services/context.py`
- Modify `scripts/turn_runtime.py`
- Modify `tests/test_market_browser_evidence.py`
- Modify `tests/test_artifact_manager_env_tool.py`
- Modify `tests/test_env_layer_end_to_end.py`
- Modify `tests/test_runtime_tool_feedback.py`

**Depends on test plan:** TG-07, TG-08, TG-09.

**Implementation steps:**

- [ ] Write failing tests that Market prepare exposes evidence readiness before artifact-producing work.
- [ ] Add evidence readiness fields for browser cockpit requirement, market research evidence requirement, issued token state, and source refs.
- [ ] Make evidence responses name the exact accepted persist fields: `tool_evidence.browser_cockpit_token` and `tool_evidence.approved_downgrade_token`.
- [ ] Add structured recovery for missing, stale, wrong-run, wrong-instance, wrong-buddy, and downgrade-without-reason evidence failures.
- [ ] Add artifact decision metadata to artifact list/get/current responses.
- [ ] Include artifact metadata in track discovery summaries without full foreign content.
- [ ] Ensure run audit and receipt preserve evidence record, artifact source run, and track/handoff continuity.

**Must delete or replace in this phase:**

- Delete Market tests that accept handwritten evidence tokens.
- Delete artifact tests that prove only field presence without source/currentness semantics.
- Delete any response that suggests copying fake evidence tokens or writing raw evidence state.

**Focused verification command:**

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_market_browser_evidence.py \
  tests/test_artifact_manager_env_tool.py \
  tests/test_env_layer_end_to_end.py \
  tests/test_runtime_tool_feedback.py \
  -q
```

**Acceptance criteria:**

- Market can infer evidence requirement and exact persist field before artifact-producing commit.
- Broker-issued evidence remains run-scoped.
- Artifact metadata helps host decisions without leaking foreign full content.

## Phase 9: Product-Mode Scenario Evals

**Goal:** Prove the full decision surface supports realistic host reasoning through existing product/runtime paths.

**Files:**

- Create `tests/test_host_decision_surface_product_mode.py`
- Modify `tests/test_env_layer_end_to_end.py`
- Modify `tests/test_prepare_runtime_context.py`
- Modify `tests/test_context_binding_env_tool.py`
- Modify `tests/test_track_manager_env_tool.py`
- Modify `docs/spec/2026-05-11-host-decision-surface-env-upgrade-plan.md` only if the implemented contract intentionally clarifies the source spec
- Modify `framework/docs/turn-runtime-spec.md`

**Depends on test plan:** TG-09, TG-10.

**Implementation steps:**

- [ ] Add scenario test for fresh Market with no track binding and one PM handoff track available.
- [ ] Add scenario test for task-only-bound Market discovering candidate tracks without mutation.
- [ ] Add scenario test for bound Market with PM PRD summary, PM handoff, track next-buddy relation, evidence readiness, market-scan artifact, and handoff to Design.
- [ ] Add scenario test for multiple candidate tracks with deterministic ranking.
- [ ] Add scenario test for conflicting track next buddy and latest handoff target.
- [ ] Add manual product-mode smoke instructions to the runtime docs, focused on observable JSON fields and no automatic route or inbox behavior.

**Must delete or replace in this phase:**

- Delete any new eval harness proposal that introduces a framework before repeated need exists.
- Delete scenario assertions that require a fixed call order from the host.
- Delete manual docs that prescribe a prompt recipe instead of showing observable runtime fields.

**Focused verification command:**

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_env_layer_end_to_end.py \
  tests/test_prepare_runtime_context.py \
  tests/test_context_binding_env_tool.py \
  tests/test_track_manager_env_tool.py \
  tests/test_market_browser_evidence.py \
  -q
```

**Acceptance criteria:**

- Product scenarios prove the environment presents enough information for PM to Market to Design continuation.
- Tests assert semantic fields and object relationships, not LLM text or exact host call order.
- Manual smoke steps match real CLI/broker surfaces.

## Phase 10: Residue Cleanup And Full Gate

**Goal:** Remove retired active surfaces and run full verification.

**Files:**

- Modify `tests/test_repo_consistency.py`
- Modify any active source or doc flagged by residue tests
- Modify `framework/docs/turn-runtime-spec.md`
- Modify shared manager skill docs only when they still advertise retired active surfaces

**Depends on test plan:** TG-11, TG-12.

**Implementation steps:**

- [ ] Add or tighten residue checks for duplicated router/manager action allowlists.
- [ ] Add or tighten residue checks for duplicated unknown-action validation.
- [ ] Add or tighten residue checks for string-only context descriptor behavior.
- [ ] Add or tighten residue checks for mirrored response fields.
- [ ] Add or tighten residue checks for prompt-level routing terms and old active surface names.
- [ ] Run focused gates from every previous phase.
- [ ] Run the full test suite.
- [ ] Run Python compile validation for `scripts` and `tests`.
- [ ] Run product-mode manual smoke from a launcher-managed instance.
- [ ] Record remaining risk only if a verification command is blocked.

**Must delete or replace in this phase:**

- Delete every active reference flagged by the residue tests.
- Delete or rewrite docs that instruct hosts to use old string descriptors, raw-state discovery, automatic binding, or a prompt flow.
- Delete broad shallow tests replaced by semantic gates.

**Focused verification command:**

```bash
python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
python3 -m pytest -p no:cacheprovider -q
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile $(find scripts tests -name '*.py' -print)
```

**Acceptance criteria:**

- Focused gates pass.
- Full pytest passes.
- Python compile passes.
- Residue search finds no retired active surfaces.
- Manual product-mode smoke shows decision surface, candidate discovery, evidence readiness, and no inbox or auto-routing behavior.

## Forward-Only Cleanup Gates

These gates are required before the branch is complete:

- Delete duplicated router/manager action allowlists.
- Delete duplicated unknown-action validation after router ownership is verified.
- Replace string-only context source descriptors.
- Delete mirrored response fields.
- Delete shallow field-existence tests where semantic tests now cover behavior.
- Add residue checks for all retired active surfaces.
- Keep one active env tool contract source: `scripts/env/tools/contracts.py`.
- Keep one active response shape source: `scripts/env/tools/responses.py`.
- Keep dynamic product semantics in services, not in static registry or docs.

## Full Verification Gate

Run the focused phase gates as work lands, then run:

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_prepare_runtime_context.py \
  tests/test_context_binding_env_tool.py \
  tests/test_track_manager_env_tool.py \
  tests/test_env_tool_response_contract.py \
  tests/test_env_tool_router.py \
  tests/test_artifact_manager_env_tool.py \
  tests/test_market_browser_evidence.py \
  tests/test_runtime_tool_feedback.py \
  tests/test_env_layer_end_to_end.py \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_repo_consistency.py \
  -q

python3 -m pytest -p no:cacheprovider -q

PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile $(find scripts tests -name '*.py' -print)
```

Manual smoke after automated gates pass:

```bash
./buddyswitch-codex instance start --buddy pm
./buddyswitch-codex instance start --buddy market
python3 scripts/turn_runtime.py prepare "Receive PM's onboarding rewrite handoff, do a quick market scan, produce a market-scan artifact, and hand the next step to Design."
python3 scripts/env/client.py context summarize
python3 scripts/env/client.py track list
```

Smoke acceptance:

- JSON includes `runtime_context.decision_surface`.
- Fresh or task-only Market sees `candidate_tracks` when a PM handoff track is available.
- Bound Market sees PM handoff context, track relation, and evidence readiness.
- Market missing-evidence feedback names exact persist fields.
- No response or doc advertises inbox, route selection, workflow engine, or automatic binding.

## Definition Of Done

The full upgrade is done when:

1. `prepare.runtime_context` exposes structured source descriptors, `decision_surface`, registry-derived env tool descriptions, and operation semantics.
2. `context.summarize`, `track.list`, `track.get`, and `handoff.validate` expose discovery and alignment semantics without mutation.
3. Fresh Market can discover candidate PM handoff context without an inbox, prompt recipe, raw-state read, or auto-binding.
4. Bound Market can see PM PRD summary, PM handoff context, track relation, evidence requirement, artifact constraints, and handoff constraints.
5. Env tool contracts are generated from one static registry and protected by consistency tests.
6. Decision-critical responses include structured next-action options.
7. Response helpers define one canonical response shape without mirrored fields.
8. Tests assert host decision semantics, not shallow field presence.
9. Ownership, permission, evidence, raw-state, and run commit boundaries remain green.
10. Product-mode scenario tests and manual smoke prove the main PM to Market to Design path.
11. Residue checks prevent old active surfaces from returning.
