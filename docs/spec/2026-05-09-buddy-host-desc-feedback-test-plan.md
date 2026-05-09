# Buddy Host DESC/Feedback Runtime Surface Test Plan

**Goal:** Verify from functional requirements that launcher-managed buddies can complete normal work from `prepare` output plus structured runtime feedback, without source/schema inference for basic boundary decisions.

**Testing principle:** Tests must be requirement-driven. They should validate observable prepare output, persist feedback, state changes, and launcher materialization. They must not be shaped around private helper branches, brittle full-file snapshots, or exact prose copied into implementation.

---

## Functional Requirements

FR1. A buddy host can run prepare and understand the active buddy, active skills, capability boundary, tool requirements, persist shape, and safe next actions from returned JSON.

FR2. Prepare returns an immediately usable `context_save_path` and `persist_command_hint`, and writes the canonical prepare JSON to the buddy scratch path.

FR3. Prepare exposes user-facing DESC for `execution_summary`, `artifacts`, `state_effects.task`, `state_effects.track`, `handoff`, `contributors`, and `tool_evidence`.

FR4. Prepare exposes PM track lifecycle rules: PM can create/update/advance/archive; create binds the current prepared task; non-create actions require an existing/current track; handoff does not implicitly mutate track.

FR5. Prepare exposes non-PM track lifecycle rules: Market, Design, Dev, and Test cannot mutate track lifecycle and should hand off PM-owned lifecycle changes.

FR6. Prepare exposes artifact-kind usage descriptions for only the active buddy's allowed artifact kinds.

FR7. Prepare exposes product/context source descriptions so product-facing buddies can consume task, track, artifact, and handoff context without reading runtime source, contracts, or manifest files.

FR8. Runtime/tool rejections return structured feedback fields for common recoverable validation failures: `permission_boundary`, `allowed_next_actions`, and where useful `command_hint` or `persist_payload_hint`.

FR9. Broker-unavailable product mode returns `E_RUNTIME_BROKER_UNAVAILABLE` with hard stop/report/do-not-bypass behavior.

FR10. AGENTS remains concise framework guidance that points to `prepare.runtime_context` and structured feedback instead of duplicating long recipes.

FR11. Existing buddy boundaries remain unchanged: Dev can write `projects/app`; PM/Market/Design/Test are read-only; raw state remains broker-only; user text does not change active buddy.

FR12. The implementation must not add compatibility wrappers, dual paths, or prompt-heavy workarounds.

## Coverage Matrix

| Requirement | Test Group | Observable Proof |
|---|---|---|
| FR1, FR3 | TG-01 Runtime DESC | `prepare.runtime_context.desc` describes persist fields and safe use |
| FR2 | TG-02 Context Save Path | prepare writes usable context JSON and persist hint points to it |
| FR4, FR5 | TG-03 Track Lifecycle DESC | PM and non-PM lifecycle guidance matches env profile boundaries |
| FR6 | TG-04 Artifact Kind DESC | active buddy descriptions exactly cover allowed artifact kinds |
| FR7 | TG-05 Product Context Sources | downstream buddies receive usable task/artifact/track/handoff context descriptors |
| FR8 | TG-06 Structured Persist Feedback | common validation failures return structured recovery fields and write no state |
| FR9 | TG-07 Broker Hard Stop | broker unavailable remains stop/report/do-not-bypass |
| FR10, FR12 | TG-08 AGENTS And Drift Guards | active host surfaces point to runtime context, not recipes or source inference |
| FR11 | TG-09 Boundary Regression | project access, raw-state boundary, and switch text behavior stay unchanged |
| FR1-FR12 | TG-10 Manual Main Path Probe | representative buddy flow uses prepare DESC, skill work, persist, receipt |

---

## TG-01 Runtime DESC

**Purpose:** Prove prepare returns enough descriptive contract for the host to construct a valid persist payload without reading schemas or source.

**Primary file:** `tests/test_prepare_runtime_context.py`

**Test cases:**

1. `test_prepare_runtime_context_exposes_desc_for_commit_fields`
   - Prepare PM.
   - Assert `runtime_context.desc` includes entries for `execution_summary`, `artifacts`, `state_effects.task`, `state_effects.track`, `handoff`, `contributors`, and `tool_evidence`.
   - Assert each entry has a non-empty `purpose`.
   - Assert `execution_summary.required is True`.
   - Assert `artifacts.item_fields` includes `kind`, `title`, `summary`, `content`.
   - Assert `state_effects.task.allowed_fields` equals `["status", "summary"]`.
   - Assert `handoff.does_not_mutate_track is True`.

2. `test_prepare_runtime_context_desc_is_present_for_each_buddy`
   - Table-drive all manifest buddies.
   - Assert the same DESC keys exist for each buddy.
   - Assert Market `tool_evidence` indicates evidence is required for artifact-producing commits.
   - Assert non-Market `tool_evidence` does not claim mandatory Market evidence.

**Anti-cheat guard:**

- Do not assert exact full prose. Assert required semantic fields, non-empty descriptions, and capability-linked values.
- Do not call private DESC helper functions directly. Inspect public prepare payloads.

## TG-02 Context Save Path

**Purpose:** Prove the host receives a concrete context file and persist command it can use without guessing whether `context_revision` is a path.

**Primary file:** `tests/test_prepare_runtime_context.py`

**Test cases:**

1. `test_prepare_writes_context_file_and_exposes_persist_hint`
   - Prepare each buddy with a representative request.
   - Assert top-level `context_save_path` starts with `runs/raw/<buddy>/`.
   - Assert the path is repo-relative, not absolute.
   - Assert the file exists under the isolated runtime root.
   - Load the file and assert it matches returned `context_revision`, `active_buddy`, `request_text`, `run_envelope.run_id`, `context_save_path`, and `persist_command_hint`.
   - Assert `persist_command_hint` includes `python3 scripts/turn_runtime.py persist`, `--context <context_save_path>`, and `--result runs/raw/<buddy>/persist-result.json`.

2. `test_prepare_context_file_is_not_written_outside_scratch`
   - Prepare each buddy.
   - Resolve the saved path.
   - Assert it is under the test runtime root's `runs/raw/<buddy>/` path.
   - Assert no file is written under `projects/app`, `buddyswitch/objects`, or `buddyswitch/content/runs`.

**Anti-cheat guard:**

- Do not pass by checking only the string format. The test must load the saved JSON file.
- Do not use the main checkout state. Use `RuntimeWorkspaceTestMixin`.

## TG-03 Track Lifecycle DESC

**Purpose:** Prove hosts can decide track actions from prepare output instead of reading `turn_runtime.py` or env profiles.

**Primary file:** `tests/test_prepare_runtime_context.py`

**Test cases:**

1. `test_prepare_exposes_track_lifecycle_desc_for_pm`
   - Prepare PM.
   - Assert `owner == "pm"`.
   - Assert `allowed_actions == ["create", "update", "advance", "archive"]`.
   - Assert create guidance says it binds the current prepared task.
   - Assert `non_create_requires_existing_track is True`.
   - Assert `handoff_does_not_mutate_track is True`.

2. `test_prepare_exposes_track_lifecycle_desc_for_non_pm_buddies`
   - Prepare Market, Design, Dev, and Test.
   - Assert `owner == "pm"`.
   - Assert `allowed_actions == []`.
   - Assert next action guidance mentions PM handoff or no track lifecycle mutation.
   - Assert `handoff_does_not_mutate_track is True`.

3. `test_track_lifecycle_desc_matches_capability_boundary`
   - For each buddy, compare `track_lifecycle_desc.allowed_actions` with `runtime_context.capability_boundary.allowed_state_effects.track`.

**Anti-cheat guard:**

- Do not infer PM from the test fixture alone. Compare public prepare output to the manifest/env-profile-derived boundary already returned in runtime context.

## TG-04 Artifact Kind DESC

**Purpose:** Prove artifact choices are understandable from runtime output for the active buddy.

**Primary files:**

- `tests/test_prepare_runtime_context.py`
- `tests/test_repo_consistency.py`

**Test cases:**

1. `test_prepare_exposes_artifact_kind_desc_for_active_buddy`
   - Table-drive all manifest buddies.
   - Prepare each buddy.
   - Assert `set(runtime_context.artifact_kind_desc) == set(runtime_context.capability_boundary.allowed_artifact_kinds)`.
   - Assert every row has non-empty `label` and `use_when`.
   - Assert no artifact kind owned only by another buddy appears.

2. `test_artifact_kind_desc_covers_manifest_kinds`
   - Load manifest.
   - Inspect the runtime description source through a public module attribute or function chosen by implementation.
   - Assert every manifest artifact kind has a description.

**Anti-cheat guard:**

- Do not accept generic descriptions such as "Use this artifact kind for <kind>". Each `use_when` must include role or artifact-purpose language.
- Do not assert descriptions by exact sentence text.

## TG-05 Product Context Sources

**Purpose:** Prove product-facing buddies can locate useful product context from prepare output and do not need to inspect runtime implementation files.

**Primary file:** `tests/test_prepare_runtime_context.py`

**Test cases:**

1. `test_prepare_exposes_context_sources_for_product_work`
   - Prepare PM, persist a PRD artifact, track creation, task update, and handoff to Market.
   - Prepare Market with the current task/track binding.
   - Assert `runtime_context.context_sources_desc` includes `request_text`, `task_context.task`, `task_context.artifacts`, `track_context.track`, `track_context.recent_handoffs`, and `current_context_summary`.
   - Assert Market `task_context.artifacts` includes the PRD content.
   - Assert `current_context_summary.artifacts` remains compact and does not duplicate full PRD content.

2. `test_design_prepare_can_consume_prior_product_context`
   - Continue from PM-created context or use a compact fixture.
   - Prepare Design on the same task/track.
   - Assert context source DESC points to full prior artifacts and track summary.

**Anti-cheat guard:**

- Do not assert that the host will never read files. Assert that the returned prepare payload contains the required product context and tells the host where to find it.
- Do not use request-specific product names as the only proof. Use artifact content fields and runtime source descriptors.

## TG-06 Structured Persist Feedback

**Purpose:** Prove common user-recoverable persist failures return actionable structured feedback and do not mutate state.

**Primary file:** `tests/test_runtime_tool_feedback.py`

**Shared assertions for every rejection:**

- `ok is False`.
- `error.code == "E_RUNTIME_PERSIST"`.
- `error.permission_boundary` is present and non-empty.
- `error.allowed_next_actions` is a non-empty list of strings.
- `error.persist_payload_hint` is present when the failure can be corrected by changing result JSON.
- Runtime state snapshot before and after is identical for tracks, tasks, artifacts, runs, and reservations except for existing prepare reservations created before the rejection.

**Test cases:**

1. Missing `execution_summary`.
2. Empty `execution_summary`.
3. No durable collaboration signal: no artifacts, no state effects, no handoff.
4. Duplicate artifact kind in one commit.
5. Artifact item missing `kind`, `title`, or object `content`.
6. Invalid artifact kind for active buddy.
7. Non-PM track create/update attempt.
8. PM `state_effects.track.action` is not one of create/update/advance/archive.
9. PM track create when the prepared task is already bound to a track.
10. PM track update/advance/archive without current or explicit track id.
11. PM track update/advance references a missing track.
12. PM track update/advance has no mutable fields.
13. Handoff missing `next_buddy`, `reason`, or `context`.
14. Handoff target is unknown.
15. Handoff target conflicts with `state_effects.track.next_buddy`.
16. Unsupported `state_effects.task` key.

**Anti-cheat guard:**

- Do not only assert that the error string contains a word. Assert structured fields and state atomicity.
- Do not convert all `ValueError` paths at the top level with generic feedback. Tests should verify boundary-specific feedback.

## TG-07 Broker Hard Stop

**Purpose:** Ensure product mode still fails closed when the broker is unavailable.

**Primary file:** `tests/test_runtime_tool_feedback.py`

**Test cases:**

1. Prepare without broker returns `E_RUNTIME_BROKER_UNAVAILABLE`.
2. Persist without broker returns `E_RUNTIME_BROKER_UNAVAILABLE`.
3. Browser evidence issue without broker returns `E_RUNTIME_BROKER_UNAVAILABLE`.

**Assertions:**

- `permission_boundary == "product-mode-runtime-broker"`.
- `stop_condition == "stop_and_report_do_not_bypass_broker"`.
- `allowed_next_actions` mention broker/start/report behavior.
- Feedback does not suggest raw state writes, direct function calls, or bypassing the broker.
- State snapshot remains unchanged.

**Anti-cheat guard:**

- Do not change broker-unavailable into a recoverable local command hint.

## TG-08 AGENTS And Drift Guards

**Purpose:** Prevent the runtime DESC fix from regressing into prompt-heavy instructions or source-inference flows.

**Primary files:**

- `tests/test_runtime_agents.py`
- `tests/test_repo_consistency.py`

**Test cases:**

1. Every buddy AGENTS file still starts with `# BuddySwitch Runtime Workspace`.
2. Every buddy AGENTS file identifies locked active buddy behavior.
3. Every buddy AGENTS file points to `prepare.runtime_context`.
4. Every buddy AGENTS file points to structured tool feedback.
5. AGENTS files do not contain detailed persist payload recipes.
6. AGENTS files do not contain business-specific examples.
7. Active docs/specs do not teach hosts to read `scripts/turn_runtime.py`, `framework/contracts/*.json`, or `buddyswitch/manifest.toml` for ordinary boundary decisions.
8. Active runtime docs mention DESC fields and structured feedback as the source of truth.

**Anti-cheat guard:**

- Avoid full-file snapshots. Assert durable behavioral constraints.
- Keep historical memos outside active-host-surface checks unless they are presented as current instructions.

## TG-09 Boundary Regression

**Purpose:** Prove richer DESC did not change permissions or routing.

**Primary files:**

- `tests/test_prepare_runtime_context.py`
- `tests/test_turn_runtime.py`
- `tests/test_buddy_env_profiles.py`
- `tests/test_buddy_env_sandbox.py`

**Test cases:**

1. Dev prepare context still reports `project.access=write` for `projects/app`.
2. PM, Market, Design, and Test still report `project.access=read-only`.
3. Raw state still reports broker-only access.
4. Market still requires broker-issued evidence for artifact-producing commits.
5. `switch market: do competitor scan` in PM remains ordinary `request_text` and active buddy remains PM.
6. `switch pm: write PRD` in Dev remains ordinary `request_text` and active buddy remains Dev.
7. Persist still commits one active buddy run result and returns receipt/refreshed context.

**Anti-cheat guard:**

- Do not validate only env profile files. Use public prepare and persist paths where feasible.

## TG-10 Manual Main Path Probe

**Purpose:** Provide one observable product-path sanity check after automated tests pass.

**Probe request in a Dev instance:**

```text
请在 projects/app/manual-acceptance-dev.md 写入 manual acceptance，然后读取确认
```

**Expected flow:**

1. Host runs `python3 scripts/turn_runtime.py prepare "<request>"`.
2. Prepare returns `context_save_path`, `persist_command_hint`, and richer `runtime_context`.
3. Host reads `runtime_context.desc`, `capability_boundary`, and `context_sources_desc`.
4. Host performs the file write/read as Dev skill work.
5. Host writes result JSON under `runs/raw/dev/`.
6. Host runs `persist_command_hint`.
7. Final response includes receipt and concise summary.

**Observable proof:**

- File write happens during skill work, not prepare.
- Persist succeeds or returns structured feedback unrelated to command shape.
- No raw `buddyswitch/objects/**` or `buddyswitch/content/runs/**` edits are made by the host.

**Anti-cheat guard:**

- This manual probe supplements automated coverage. It is not a substitute for TG-01 through TG-09.

---

## Required Verification Commands

Focused runtime DESC and feedback:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_prepare_runtime_context.py \
  tests/test_runtime_tool_feedback.py \
  tests/test_turn_runtime.py \
  tests/test_parallel_contracts.py \
  -q
```

Boundary and drift checks:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_runtime_agents.py \
  tests/test_repo_consistency.py \
  tests/test_output_schema_boundaries.py \
  tests/test_buddy_env_profiles.py \
  tests/test_buddy_env_sandbox.py \
  -q
```

Launcher checks when AGENTS or materialization changes:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py \
  -q
```

Direct command checks:

```bash
python3 scripts/turn_runtime.py --help
python3 scripts/runtime_agents.py validate-all
python3 scripts/env_profiles.py validate-all
```

Full suite before completion when implementation touches runtime or launcher contracts:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests -q
```

## Passing Criteria

- All prepare DESC fields are present in public prepare output for every buddy.
- Prepare writes canonical context JSON to the advertised scratch path.
- Persist hint is executable from the instance workspace shape and points to the saved context.
- PM and non-PM track lifecycle guidance matches runtime permission boundaries.
- Artifact-kind descriptions exactly cover active buddy artifact kinds.
- Product/context source guidance is present and prior artifact content remains accessible through prepare payload.
- Common persist validation failures return structured feedback and preserve state atomically.
- Broker-unavailable feedback remains a hard stop.
- AGENTS stays concise and does not become a payload manual.
- Existing permission and routing behavior remains unchanged.

## Explicitly Invalid Test Designs

- A test that passes by asserting a private helper constant only.
- A test that copies an exact long DESC sentence and fails on harmless wording changes.
- A test that uses full AGENTS snapshots instead of behavioral constraints.
- A test that validates only file names while never reading public prepare JSON.
- A test that treats historical memo text as an active host contract.
- A test that ignores state atomicity for rejected persists.
- A test that makes a generic catch-all error look structured without boundary-specific guidance.
- A test that hides old source-inference behavior by excluding active docs or launcher assets from checks.
