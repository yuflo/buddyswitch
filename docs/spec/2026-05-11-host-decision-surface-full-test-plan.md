# Host Decision Surface Full Test Plan

**Goal:** Verify the full host decision surface upgrade from product semantics: prepared runtime context, env tool contracts, discovery responses, handoff validation, evidence requirements, artifact metadata, response recovery options, product-mode flows, and forward-only cleanup.

**Testing Principle:** Tests are the boundary. Every implementation phase starts with failing semantic tests, proves the failure is caused by missing host decision semantics, then lands the smallest direct change, deletes the old active surface, and reruns focused plus regression gates. Tests must not merely assert field existence; they must assert host decision semantics and runtime object relationships.

**Scope:** Python unit and integration tests under `tests/`, product-mode broker and CLI checks, static residue checks, Python compile validation, and manual smoke through launcher-managed buddy instances.

---

## Coverage Matrix

| Group | Coverage | Primary Files | Core Proof |
|---|---|---|---|
| TG-01 | Semantic runtime context tests | `tests/test_prepare_runtime_context.py`, `tests/test_context_binding_env_tool.py` | Host sees binding state, active-buddy relation, context readiness, evidence readiness, and safe read affordances. |
| TG-02 | Structured context source descriptor tests | `tests/test_prepare_runtime_context.py`, `tests/test_context_binding_env_tool.py` | Source descriptors explain content depth, scope, nullability, source, projection, and decision use. |
| TG-03 | Env tool registry consistency tests | `tests/test_prepare_runtime_context.py`, `tests/test_env_tool_router.py`, `tests/test_repo_consistency.py` | Registry, prepare env tools, router, managers, and CLI operation names agree. |
| TG-04 | Track/context/handoff discovery tests | `tests/test_track_manager_env_tool.py`, `tests/test_context_binding_env_tool.py` | Unbound or task-only Market discovers candidate PM handoff tracks without mutation. |
| TG-05 | Response contract tests | `tests/test_env_tool_response_contract.py`, `tests/test_runtime_tool_feedback.py` | Success and rejection responses follow one canonical machine-readable shape. |
| TG-06 | Structured next-action option tests | `tests/test_env_tool_response_contract.py`, service-specific tests | Decision-critical responses include structured options validated against registry semantics. |
| TG-07 | Market evidence tests | `tests/test_market_browser_evidence.py`, `tests/test_runtime_tool_feedback.py` | Market sees evidence readiness and receives exact run-scoped persist guidance. |
| TG-08 | Artifact decision metadata tests | `tests/test_artifact_manager_env_tool.py`, `tests/test_track_manager_env_tool.py` | Artifact surfaces expose metadata for decisions without leaking foreign full content. |
| TG-09 | End-to-end product flow tests | `tests/test_env_layer_end_to_end.py`, `tests/test_host_decision_surface_product_mode.py` | PM to Market to Design flow is discoverable through env surfaces and persists correct objects. |
| TG-10 | Product-mode manual smoke tests | CLI and launcher commands | Real instance JSON and env client output expose the same decision surface. |
| TG-11 | Residue and cleanup tests | `tests/test_repo_consistency.py` | Old active surfaces, duplicated maps, mirrored fields, and shallow tests are gone. |
| TG-12 | Full regression commands | Full pytest and compile gate | The whole repo remains green after the upgrade. |

## TG-01: Semantic Runtime Context Tests

**Purpose:** Prove prepare and context tools expose decision semantics, not just raw fields.

**Test files:**

- `tests/test_prepare_runtime_context.py`
- `tests/test_context_binding_env_tool.py`
- `tests/test_market_browser_evidence.py`

**Setup:**

- Use `RuntimeWorkspaceTestMixin`.
- Seed a PM task with a PRD artifact and a track where `current_buddy == "pm"` and `next_buddy == "market"`.
- Persist a PM run audit with handoff `next_buddy == "market"`.
- Prepare Market once with only a generated or current Market task and no track binding.
- Prepare Market once bound to the PM track and a Market-owned task when needed.

**Specific test case names:**

- `test_market_prepare_decision_surface_marks_task_only_binding_and_candidate_track_absence`
- `test_bound_market_prepare_decision_surface_marks_next_buddy_handoff_and_evidence_requirement`
- `test_context_get_and_summarize_return_same_decision_surface_for_active_binding`
- `test_decision_surface_enum_values_cover_unbound_task_only_track_only_bound_and_stale`

**Key assertions:**

- `runtime_context.decision_surface.binding_state.state == "bound_task_only"` for task-only Market.
- `runtime_context.decision_surface.binding_state.current_track_id is None` when no track is bound.
- `runtime_context.decision_surface.active_buddy_relation.track_role == "none"` for task-only Market.
- `runtime_context.decision_surface.safe_read_affordances[*].id` includes `inspect_candidate_tracks`.
- Bound Market has `active_buddy_relation.track_role == "next_buddy"`.
- Bound Market has `active_buddy_relation.latest_handoff_to_active_buddy is True`.
- `context_readiness.has_track_handoffs is True` for bound PM handoff context.
- Market has `evidence_readiness.market_research_evidence == "required"`.
- Each safe read affordance has `mutates == "none"` and a source ref to env tool metadata.

**Expected failure before implementation:**

- `decision_surface` is absent from prepare and context responses.
- Existing tests only prove `current_context_summary` exists.

**Verification command:**

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_prepare_runtime_context.py \
  tests/test_context_binding_env_tool.py \
  tests/test_market_browser_evidence.py::MarketBrowserEvidenceTests::test_market_profile_requires_browser_evidence \
  -q
```

## TG-02: Structured Context Source Descriptor Tests

**Purpose:** Prove context source descriptors are machine-readable and explain how hosts should interpret each context section.

**Test files:**

- `tests/test_prepare_runtime_context.py`
- `tests/test_context_binding_env_tool.py`

**Setup:**

- Prepare PM and Market contexts.
- Include a PM PRD artifact with full content.
- Compare `prepare.runtime_context.context_sources_desc` and `context.list_sources`.

**Specific test case names:**

- `test_prepare_exposes_structured_context_source_descriptors_for_product_work`
- `test_context_list_sources_matches_prepare_structured_descriptors`
- `test_structured_descriptors_distinguish_full_artifacts_from_compact_summaries`

**Key assertions:**

- Each descriptor is a dict with `description`, `content`, `scope`, and `decision_use`.
- `task_context.artifacts.content == "full"`.
- `task_context.artifacts.summary_projection == "runtime_context.current_context_summary.artifacts"`.
- `current_context_summary.content == "summary"`.
- `track_context.recent_handoffs.scope == "current_track_run_audits"`.
- `decision_use` includes values such as `handoff_continuation`, `read_prior_outputs`, and `first_pass_orientation`.
- Compact summaries omit PRD full content keys such as `problem` while full current task artifacts retain them.

**Expected failure before implementation:**

- `context_sources_desc()` returns strings, so semantic descriptor assertions fail.

**Verification command:**

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_prepare_exposes_context_sources_for_product_work \
  tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_tools_return_current_context_without_raw_global_state \
  -q
```

## TG-03: Env Tool Registry Consistency Tests

**Purpose:** Prove env tool static contracts have one active source and every exposed surface agrees.

**Test files:**

- `tests/test_prepare_runtime_context.py`
- `tests/test_env_tool_router.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_repo_consistency.py`

**Setup:**

- Import `scripts/env/tools/contracts.py`.
- Build prepare runtime context for at least `dev` and `market`.
- Dispatch valid and invalid `env.tool` envelopes through the broker router.

**Specific test case names:**

- `test_prepare_env_tools_are_registry_derived_and_include_operation_semantics`
- `test_router_supported_tools_and_actions_match_registry`
- `test_manager_handler_actions_match_registry_actions`
- `test_cli_operation_names_match_registry_cli_operations`
- `test_registry_payload_fields_match_prepare_payload_schema_views`

**Key assertions:**

- `set(runtime_context.env_tools) == set(tool.manager_name for tool in registry)`.
- Every action in every `ToolSpec` appears in prepare `operations`.
- Every action has `operation_semantics` with `kind`, `mutates`, `authority`, `requires`, and `returns`.
- `track.list.operation_semantics.mutates == "none"`.
- `track.attach_task.operation_semantics.mutates == "runtime_objects"`.
- `handoff.validate.operation_semantics.kind == "validate"`.
- Router unknown-action response is produced by one layer and names registry-supported actions.
- CLI hyphenated operation names normalize to registry action names.

**Expected failure before implementation:**

- `contracts.py` is absent.
- Router, managers, CLI, and prepare each carry separate handwritten action lists.

**Verification command:**

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_prepare_exposes_env_tool_hints \
  tests/test_env_tool_router.py \
  tests/test_env_tool_response_contract.py \
  tests/test_repo_consistency.py \
  -q
```

## TG-04: Track, Context, And Handoff Discovery Tests

**Purpose:** Prove readable track and context responses give hosts enough discovery semantics to continue a handoff without an inbox or auto-route.

**Test files:**

- `tests/test_track_manager_env_tool.py`
- `tests/test_context_binding_env_tool.py`
- `tests/test_artifact_manager_env_tool.py`

**Setup:**

- Seed multiple tracks:
  - A PM track with `next_buddy == "market"` and a recent handoff to Market.
  - A PM track with no handoff but `next_buddy == "market"`.
  - A track where Market already has a task.
  - An unrelated older track.
- Seed PM PRD current artifact metadata on the candidate track.
- Use a Market instance with no current track for discovery calls.

**Specific test case names:**

- `test_track_list_ranks_recent_handoff_and_next_buddy_candidates_for_active_buddy`
- `test_track_list_discovery_summary_names_candidate_tracks_and_basis`
- `test_track_get_returns_compact_track_context_summary_without_foreign_full_content`
- `test_context_summarize_unbound_market_returns_candidate_tracks_without_binding_mutation`
- `test_handoff_validate_returns_track_alignment_and_discoverability`
- `test_handoff_validate_conflict_returns_suggested_next_buddy`

**Key assertions:**

- First `track.list.tracks[0].discovery.active_buddy_role == "next_buddy"` for the PM handoff track.
- Relevance reasons include `track.next_buddy == active_buddy` and `recent_handoff.next_buddy == active_buddy` when both are true.
- `discovery_summary.candidate_track_ids` is sorted deterministically.
- `track.get.track_context_summary.tasks[*].current_artifacts[*]` includes id, kind, title, summary, source buddy, source run, revision, and currentness.
- `track.get.track_context_summary` does not contain PM PRD full content.
- `context.summarize.candidate_tracks` appears when useful and does not mutate instance JSON.
- Handoff success includes `track_alignment.target_matches_track_next_buddy is True`.
- Handoff success includes `discoverability.available_after == "run.commit"`.
- Handoff conflict includes `track_alignment.suggested_next_buddy`.

**Expected failure before implementation:**

- `track.list` has shallow rows only.
- `track.get` lacks compact track context.
- `context.summarize` has no `candidate_tracks`.
- `handoff.validate` lacks alignment and discoverability fields.

**Verification command:**

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_track_manager_env_tool.py \
  tests/test_context_binding_env_tool.py \
  tests/test_artifact_manager_env_tool.py \
  -q
```

## TG-05: Response Contract Tests

**Purpose:** Prove all env tool responses use one canonical machine-readable shape.

**Test files:**

- `tests/test_env_tool_response_contract.py`
- `tests/test_runtime_tool_feedback.py`
- Service-specific env tool tests

**Setup:**

- Reuse existing broker dispatch helpers.
- Exercise one success and one rejection for each env tool: task, track, artifact, context, binding, handoff, run, and evidence.

**Specific test case names:**

- `test_each_env_tool_has_success_response_with_canonical_machine_readable_fields`
- `test_each_env_tool_has_rejection_response_with_canonical_machine_readable_fields`
- `test_response_helpers_do_not_emit_legacy_mirrored_fields`
- `test_runtime_feedback_projection_keeps_authoritative_fields_top_level`

**Key assertions:**

- Success responses include `ok`, `tool`, `action`, `active_buddy`, and `allowed_next_actions`.
- Rejections include `ok is False`, `error.code`, `error.message`, `permission_boundary`, `active_buddy`, and `allowed_next_actions`.
- `command_hint` and `stop_condition` are top-level when present.
- `error` does not duplicate top-level `permission_boundary`.
- No response contains retired mirrored fields after helper migration.

**Expected failure before implementation:**

- Response boilerplate is repeated and not helper-backed.
- Some fields are only shallowly asserted.

**Verification command:**

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

## TG-06: Structured Next-Action Option Tests

**Purpose:** Prove decision-critical responses include structured, registry-valid recovery affordances without prescribing a workflow.

**Test files:**

- `tests/test_env_tool_response_contract.py`
- `tests/test_runtime_tool_feedback.py`
- `tests/test_track_manager_env_tool.py`
- `tests/test_context_binding_env_tool.py`
- `tests/test_market_browser_evidence.py`
- `tests/test_artifact_manager_env_tool.py`

**Setup:**

- Import the registry.
- Exercise fresh context summary, missing current track, track discovery, handoff validation, Market missing evidence, stale context, non-PM track lifecycle rejection, foreign task rejection, and foreign artifact rejection.

**Specific test case names:**

- `test_decision_critical_rejections_include_structured_next_action_options`
- `test_context_summarize_candidate_tracks_option_points_to_track_get`
- `test_track_get_current_without_binding_option_points_to_track_list`
- `test_market_missing_evidence_option_points_to_evidence_issue_browser`
- `test_foreign_scope_rejections_offer_safe_non_raw_state_options`
- `test_next_action_options_match_registry_tool_actions_and_mutability`

**Key assertions:**

- Each option has `id`, `tool`, `action`, `mutates`, `preconditions`, `reason`, and `source_refs`.
- Option `tool` and `action` exist in `contracts.py`.
- Option `mutates` equals registry operation semantics.
- Read-only discovery options have `mutates == "none"`.
- No option points to raw state paths or arbitrary non-PM `binding.set_track`.
- Human-readable `allowed_next_actions` remains a text projection, not the only decision surface.

**Expected failure before implementation:**

- Responses only have string `allowed_next_actions`.

**Verification command:**

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_response_contract.py \
  tests/test_runtime_tool_feedback.py \
  tests/test_track_manager_env_tool.py \
  tests/test_context_binding_env_tool.py \
  tests/test_market_browser_evidence.py \
  tests/test_artifact_manager_env_tool.py \
  -q
```

## TG-07: Market Evidence Tests

**Purpose:** Prove Market evidence requirements are visible before artifact-producing work and enforced through broker-issued run-scoped tokens.

**Test files:**

- `tests/test_market_browser_evidence.py`
- `tests/test_runtime_tool_feedback.py`
- `tests/test_prepare_runtime_context.py`
- `tests/test_env_layer_end_to_end.py`

**Setup:**

- Use Market profile with browser cockpit and market research evidence required.
- Start the existing fake CDP server fixture where browser readiness is needed.
- Prepare Market contexts for current run and stale/wrong-run variants.

**Specific test case names:**

- `test_market_prepare_decision_surface_exposes_evidence_readiness`
- `test_market_missing_evidence_rejection_names_exact_persist_fields_and_issue_option`
- `test_browser_evidence_response_exposes_token_scope_and_persist_payload_hint`
- `test_market_persist_with_token_for_other_run_rejects_with_structured_option`
- `test_market_persist_with_handwritten_token_rejects_before_writes`
- `test_approved_downgrade_token_requires_reason_and_records_reason`

**Key assertions:**

- Market prepare has `evidence_readiness.browser_cockpit == "required"`.
- Market prepare has `evidence_readiness.market_research_evidence == "required"`.
- Missing evidence rejection includes `permission_boundary == "market.browser_evidence"`.
- Structured option points to `evidence.issue_browser` or valid downgrade path.
- Response names `tool_evidence.browser_cockpit_token` and `tool_evidence.approved_downgrade_token`.
- Token scope matches current run id, context revision, instance id, buddy id, and task id.
- Rejected evidence attempts leave runtime object snapshots unchanged.

**Expected failure before implementation:**

- Evidence readiness is not part of `decision_surface`.
- Missing evidence feedback is string-first and lacks structured options.

**Verification command:**

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_market_browser_evidence.py \
  tests/test_runtime_tool_feedback.py \
  tests/test_prepare_runtime_context.py \
  tests/test_env_layer_end_to_end.py \
  -q
```

## TG-08: Artifact Decision Metadata Tests

**Purpose:** Prove artifact surfaces expose enough metadata for host decisions without breaking active-buddy content boundaries.

**Test files:**

- `tests/test_artifact_manager_env_tool.py`
- `tests/test_track_manager_env_tool.py`
- `tests/test_env_layer_end_to_end.py`

**Setup:**

- Seed PM PRD, Market market-scan, and Design design-handoff artifacts on a track.
- Use current active-buddy tasks for allowed artifact manager reads.
- Use foreign task/artifact ids for rejection checks.

**Specific test case names:**

- `test_artifact_list_get_and_get_current_include_decision_metadata`
- `test_track_get_current_artifact_metadata_excludes_foreign_full_content`
- `test_foreign_artifact_rejection_does_not_leak_content_and_offers_safe_context_option`
- `test_run_commit_records_artifact_source_run_and_current_revision_metadata`

**Key assertions:**

- Artifact rows include id, kind, title, summary, buddy or source buddy, task id, source run id, revision, currentness, and updated timestamp.
- Current artifact metadata matches `env_store.build_track_artifact_index`.
- Foreign artifact manager reads reject with `artifact.buddy_scope`.
- Rejections include structured options that point to allowed context or track summary reads, not raw state.
- Track discovery exposes artifact metadata only, not full content.

**Expected failure before implementation:**

- Artifact manager and track discovery metadata are incomplete for decision use.

**Verification command:**

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_artifact_manager_env_tool.py \
  tests/test_track_manager_env_tool.py \
  tests/test_env_layer_end_to_end.py \
  -q
```

## TG-09: End-To-End Product Flow Tests

**Purpose:** Prove the full decision surface supports the target PM handoff to Market scan to Design handoff path.

**Test files:**

- `tests/test_env_layer_end_to_end.py`
- `tests/test_host_decision_surface_product_mode.py`
- `tests/test_prepare_runtime_context.py`
- `tests/test_context_binding_env_tool.py`
- `tests/test_track_manager_env_tool.py`

**Setup:**

- Use broker dispatch and runtime workspace fixtures.
- PM creates a track, writes a PRD artifact, and commits a handoff to Market.
- Market starts with no track binding in one scenario and with bound track/task in another.
- Market issues evidence, commits a market-scan artifact, and hands off to Design.

**Specific test case names:**

- `test_fresh_market_discovers_pm_handoff_track_without_inbox_or_binding_mutation`
- `test_task_only_market_context_summarize_returns_candidate_tracks`
- `test_bound_market_sees_pm_prd_handoff_track_relation_evidence_and_design_handoff_constraints`
- `test_multiple_candidate_tracks_are_ranked_deterministically`
- `test_conflicting_next_buddy_and_recent_handoff_target_are_exposed_as_semantics_not_policy`
- `test_full_buddy_loop_uses_decision_surface_and_persists_market_scan_to_design_handoff`

**Key assertions:**

- Fresh Market sees candidate track ids through `context.summarize` or `track.list`.
- Candidate discovery is based on track next buddy, recent handoff target, and active-buddy participation.
- No scenario response contains an inbox, route selection, or automatic binding mutation.
- Bound Market sees compact PM PRD summary and PM handoff context.
- Market evidence is issued before artifact-producing commit.
- Market run audit includes market-scan artifact, evidence record, track id, and handoff to Design.
- Design can prepare and see Market handoff context through runtime surfaces.

**Expected failure before implementation:**

- Fresh Market lacks candidate discovery.
- Bound Market lacks decision surface and structured evidence readiness.

**Verification command:**

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

## TG-10: Product-Mode Manual Smoke Tests

**Purpose:** Prove real launcher-managed CLI surfaces show the same decision data as automated tests.

**Test files:** Manual verification recorded in branch notes or final implementation summary.

**Setup:**

- Start from `dev2258`.
- Use launcher-managed instances, not direct raw object reads.
- Use a PM turn that creates an onboarding rewrite track and hands off to Market.
- Use a Market instance with browser cockpit available when checking evidence issuance.

**Specific smoke cases:**

- `manual_pm_prepare_and_commit_handoff_track`
- `manual_market_prepare_displays_decision_surface`
- `manual_market_context_summarize_displays_candidate_tracks_when_unbound`
- `manual_market_track_list_displays_discovery_summary`
- `manual_market_evidence_issue_displays_token_scope_and_persist_fields`

**Key assertions:**

- Prepared JSON includes `runtime_context.decision_surface`.
- `context summarize` shows current binding and candidate tracks when useful.
- `track list` shows discovery reasons and deterministic candidate order.
- Market evidence response names accepted persist fields.
- No manual output suggests an inbox, route selection, or automatic binding.

**Expected failure before implementation:**

- Manual output does not include the new semantic surfaces.

**Verification command:**

```bash
./buddyswitch-codex instance start --buddy pm
./buddyswitch-codex instance start --buddy market
python3 scripts/turn_runtime.py prepare "Receive PM's onboarding rewrite handoff, do a quick market scan, produce a market-scan artifact, and hand the next step to Design."
python3 scripts/env/client.py context summarize
python3 scripts/env/client.py track list
```

## TG-11: Residue And Cleanup Tests

**Purpose:** Prove forward-only cleanup happened and retired active surfaces cannot return silently.

**Test files:**

- `tests/test_repo_consistency.py`
- Existing service-specific tests that formerly asserted shallow shape

**Setup:**

- Use tracked active runtime files from `scripts`, `tests`, `framework`, `buddyswitch/skills`, and `tools/launcher/assets`.
- Exclude historical spec files only when a test intentionally scans active product surfaces.

**Specific test case names:**

- `test_env_tool_contract_has_single_static_registry_source`
- `test_router_and_managers_do_not_duplicate_action_allowlists`
- `test_unknown_action_validation_has_single_active_boundary`
- `test_context_source_descriptors_are_not_string_only`
- `test_response_contract_has_no_legacy_mirrored_fields`
- `test_semantic_tests_replaced_shallow_field_existence_checks_for_decision_surface`
- `test_active_surfaces_do_not_advertise_handoff_inbox_or_auto_routing`

**Key assertions:**

- `scripts/env/tools/contracts.py` exists and is imported by prepare and router.
- `turn_runtime._build_env_tools_desc()` is registry-derived.
- Router and managers do not maintain separate action name sets for the same boundary.
- Manager-local unknown-action rejection is absent when router owns action validation.
- `context_sources_desc()` returns descriptor dicts.
- Active responses do not emit retired mirrored fields.
- Active docs do not instruct hosts to use raw-state discovery, inboxes, selected routes, or fixed call order.

**Expected failure before implementation:**

- Current code has hand-authored env tool maps, duplicated action sets, string descriptors, repeated response boilerplate, and shallow tests.

**Verification command:**

```bash
python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
python3 - <<'PY'
from pathlib import Path

roots = [Path("scripts"), Path("tests"), Path("framework"), Path("buddyswitch/skills"), Path("tools/launcher/assets")]
tokens = [
    "handoff_inbox",
    "recommended_route",
    "selected_track",
    "next_workflow_step",
    "auto_bind",
    "must_call_next",
]
hits = []
for root in roots:
    if not root.exists():
        continue
    for path in root.rglob("*"):
        if path.suffix not in {".py", ".md", ".json", ".toml"}:
            continue
        text = path.read_text(encoding="utf-8")
        for token in tokens:
            if token in text:
                hits.append(f"{path}:{token}")
if hits:
    raise SystemExit("\n".join(hits))
PY
```

## TG-12: Full Regression Commands

**Purpose:** Prove the whole repo remains healthy after all semantic surfaces and cleanup land.

**Test files:** All tests under `tests/`.

**Setup:**

- Run from `/Users/chen/Dev/buddyswitch/.worktrees/dev2258`.
- Ensure no long-running launcher command from manual smoke is still active before running the full suite.

**Focused pytest gates:**

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
```

**Full pytest:**

```bash
python3 -m pytest -p no:cacheprovider -q
```

**Python compile:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile $(find scripts tests -name '*.py' -print)
```

**Residue search:**

```bash
python3 - <<'PY'
from pathlib import Path

roots = [Path("scripts"), Path("tests"), Path("framework"), Path("buddyswitch/skills"), Path("tools/launcher/assets")]
tokens = [
    "handoff_inbox",
    "recommended_route",
    "selected_track",
    "next_workflow_step",
    "auto_bind",
    "must_call_next",
]
hits = []
for root in roots:
    if not root.exists():
        continue
    for path in root.rglob("*"):
        if path.suffix not in {".py", ".md", ".json", ".toml"}:
            continue
        text = path.read_text(encoding="utf-8")
        for token in tokens:
            if token in text:
                hits.append(f"{path}:{token}")
if hits:
    raise SystemExit("\n".join(hits))
PY
```

**Manual product-mode smoke:**

```bash
./buddyswitch-codex instance start --buddy pm
./buddyswitch-codex instance start --buddy market
python3 scripts/turn_runtime.py prepare "Receive PM's onboarding rewrite handoff, do a quick market scan, produce a market-scan artifact, and hand the next step to Design."
python3 scripts/env/client.py context summarize
python3 scripts/env/client.py track list
```

**Final acceptance assertions:**

- Focused pytest gates pass.
- Full pytest passes.
- Python compile passes.
- Residue search exits cleanly.
- Manual smoke shows decision surface, candidate tracks, discovery reasons, evidence readiness, and no inbox or automatic route behavior.
- Final implementation summary reports changed files, verification commands, and remaining risk.
