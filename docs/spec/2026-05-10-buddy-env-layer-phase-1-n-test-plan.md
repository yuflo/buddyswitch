> Superseded on 2026-05-12 by the env tool layer rebuild residue removal work. This file is historical context, not active implementation guidance.

# Buddy Env Layer Phase 1-N Test Plan

**Goal:** Verify from product requirements that BuddySwitch buddies can operate task, track, artifact, context, binding, run, evidence, and handoff state through one runtime-owned env layer, without prompt-based permission enforcement or old debug/manual product paths.

**Testing principle:** Start from observable product behavior: active buddy identity, active instance identity, ownership, lifecycle state, structured feedback, persisted object state, launcher materialization, and runtime context. Do not construct tests around private helper branches, incidental prose, or fixtures chosen only to make the current implementation pass.

---

## Working Directory

Run all tests from:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0210
```

Do not run or edit from the main checkout at `/Users/chen/Dev/buddyswitch`.

## Source Baseline

Phase 1 task-manager first slice is already planned and implemented:

- `docs/spec/2026-05-10-buddy-env-layer-task-manager-development-plan.md`
- `docs/spec/2026-05-10-buddy-env-layer-task-manager-test-plan.md`
- `tests/test_task_manager_env_tool.py`
- `scripts/env/services/tasks.py`
- `scripts/env/tools/task_manager.py`
- `scripts/env/client.py`

This full Phase 1-N test plan supersedes the active `env.task` shape. Existing `env.task` references are acceptable only as historical Phase 1 documentation until Phase 2 removes the active path.

## Current Final Rerun Baseline

This plan now has two uses:

- **Phase development mode:** run each phase's focused tests, regression anchors, residue search, report, and handoff prompt before continuing.
- **Final rerun mode:** after Phases 1-8 have been implemented once, use the final regression gate plus active-surface residue checks to prove the product env layer still holds.

Most follow-up verification should use final rerun mode. Do not try to reconstruct historical per-phase report/handoff prompts from repository state; those are process artifacts, not product behavior.

Latest observed full gate before this cleanup:

- `python3 -m pytest -p no:cacheprovider ... -q` over the final gate: `370 passed, 3071 subtests passed in 229.86s`.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile ...`: exit code `0`.
- Active surface residue search for retired product paths across `buddyswitch scripts tests framework tools`: no matches.
- Retired active files absent: `scripts/env_tasks.py`, `scripts/env_tracks.py`, `scripts/env_artifacts.py`, and the stale PM-only `buddyswitch/skills/pm/track-manager/SKILL.md`.

Known cleanup distinction:

- Development-plan checkbox state is not itself a test failure after final rerun mode starts; product behavior is judged by tests, compile proof, active-surface residue search, and end-to-end state inspection.
- Historical specs may keep `env.task` and retired-script references when they are clearly baseline/history. Active docs, skills, AGENTS, launcher assets, active tests, and runtime code must not advertise them.
- `artifact.delete` must not exist as a buddy-facing artifact env tool or skill instruction. A manifest/admin permission string alone is not a product API failure unless an active buddy-facing path exposes artifact deletion.

## Final Public Contract Under Test

Every buddy env operation must enter through:

```json
{
  "method": "env.tool",
  "payload": {
    "tool": "task|track|artifact|context|binding|run|evidence",
    "action": "...",
    "args": {}
  }
}
```

Host lifecycle entrypoints are tested separately:

- `prepare` remains the host preflight entrypoint unless a later phase explicitly replaces it.
- `prepare` must not become a hidden buddy state mutation path outside runtime-owned reservation and binding behavior.
- `prepare.runtime_context.env_tools` must advertise the unified `env.tool` envelope for buddy-callable env operations.

The test suite must prove behavior through at least one of these public surfaces per phase:

- broker request to `scripts/runtime_kernel/broker.py`
- `scripts/env/client.py`
- launcher-materialized runtime workspace
- `prepare.runtime_context.env_tools`

Private service helper tests are allowed only as supporting coverage; they cannot be the only proof of product behavior.

## Functional Requirements

FR1. Every buddy-callable env operation enters through one broker-routed `env.tool` envelope.

FR2. Active buddy and instance identity come only from launcher/runtime context.

FR3. Payload-authored `buddy`, `active_buddy`, `instance_id`, `task_id`, `track_id`, or `source_run_id` cannot widen authority.

FR4. Task operations support create, list, get, get-current, set-current, update, and archive for active-buddy-owned tasks.

FR5. Task reads and mutations for foreign tasks are rejected by service/runtime code with structured feedback and no mutation.

FR6. Track read surfaces expose coordination context; track lifecycle mutation is PM-owned.

FR7. Track task linkage remains bidirectionally consistent between task `track_id` and track `task_ids`.

FR8. Artifact read/list surfaces do not expose global foreign artifacts; artifact mutation requires active-buddy task ownership and allowed artifact kind.

FR9. Artifact revisions preserve current-slot semantics: new revision becomes current, previous revision becomes non-current, and task `artifact_slots` updates.

FR10. Context tools expose current context, source descriptions, selected artifacts, track context, and recent handoff context without raw global state writes.

FR11. Binding tools read and mutate only the active launcher instance binding; rejected binding updates leave instance JSON unchanged.

FR12. Handoff is the legal cross-buddy collaboration signal; handoff validation rejects unknown buddies and conflicting transition targets.

FR13. Run commit validates one prepared context, one reserved run, one result payload, one atomic commit, and no replay.

FR14. Persisted run output records task, track, artifact, handoff, contributors, evidence, receipt paths, and related run ids consistently.

FR15. Invalid run commits write no task, track, artifact, run content, evidence, or instance binding changes.

FR16. Browser evidence issuance is env-tool-routed, Market-gated, ready-page-gated, and scoped to active instance, buddy, task, track, context revision, and run.

FR17. `prepare.runtime_context.env_tools` advertises the unified envelope and compact payload hints for available tools.

FR18. Skills and AGENTS remain concise and never become permission sources or raw state mutation manuals.

FR19. Old manual/debug scripts such as `scripts/env_tasks.py`, `scripts/env_tracks.py`, `scripts/env_artifacts.py`, and `scripts/browser_evidence.py` do not define product behavior after their replacement phases.

FR20. Existing prepare, persist, browser cockpit, project access, output schema, cleanup, launcher, and runtime skill behavior does not regress.

FR21. A launcher-style end-to-end loop can move work across PM, Market, Design, Dev, and Test with coherent task, track, artifact, run, evidence, and handoff state.

FR22. `prepare` has an explicit tested lifecycle contract: it is host preflight, returns current env tool capability, preserves user request text, and does not act as a second buddy env tool implementation.

FR23. Workspace and project permissions are enforced across the env layer: Dev can write `projects/app`, PM/Market/Design/Test cannot, and no env tool can bypass raw-state or project boundaries.

FR24. Cross-tool identity injection is consistent: task, track, artifact, binding, run, and evidence tools reject or ignore payload-authored identity fields and use only runtime active instance and active buddy.

FR25. All env tools share a minimum machine-readable response contract for success and rejection so Codex can proceed from structured feedback.

## Coverage Matrix

| Requirement | Phase | User-Facing Capability | `env.tool` Payload | Positive Proof | Boundary/Rejection Proof | Persisted State Proof | Public Surface Proof | Regression Command |
|---|---:|---|---|---|---|---|---|---|
| FR1, FR17 | 2 | Unified env tool envelope | `{tool:"task", action:"list", args:{}}` | task list succeeds through `env.tool` | malformed envelope rejects | no state mutation on bad envelope | runtime context and env client show `env.tool` | `tests/test_env_tool_router.py` |
| FR4, FR5 | 2 | Task management | `{tool:"task", action:"set_current", args:{task_id}}` | own task operations pass | foreign task rejects | task JSON and instance JSON inspected | task-manager skill and launcher workspace | `tests/test_task_manager_env_tool.py` |
| FR6, FR7 | 3 | Track coordination | `{tool:"track", action:"advance", args:{...}}` | PM lifecycle changes pass | non-PM lifecycle rejects | track/task JSON inspected | shared track-manager skill | `tests/test_track_manager_env_tool.py` |
| FR8, FR9 | 4 | Artifact management | `{tool:"artifact", action:"create_revision", args:{...}}` | active-buddy revision pass | foreign task/kind rejects | artifact/task slot JSON inspected | shared artifact-manager skill | `tests/test_artifact_manager_env_tool.py` |
| FR10, FR11, FR12 | 5 | Context, binding, handoff | `{tool:"binding", action:"set_task", args:{task_id}}` | binding/context reads pass | stale/mismatch rejects | instance JSON unchanged on rejection | runtime context hints | `tests/test_context_binding_env_tool.py` |
| FR13, FR14, FR15 | 6 | Run commit | `{tool:"run", action:"commit", args:{context,result}}` | valid commit writes receipt | stale/replay/bad payload rejects | task/track/artifact/run files inspected | persist CLI uses same service | `tests/test_run_env_tool.py` |
| FR16 | 7 | Browser evidence | `{tool:"evidence", action:"issue_browser", args:{...}}` | Market token issues when ready | wrong context/browser rejects | evidence token JSON inspected | env client evidence command | `tests/test_evidence_env_tool.py` |
| FR18, FR19, FR20 | 8 | Active surface consistency | all | active docs agree | old product paths fail checks | no raw state recipes | launcher materialization | `tests/test_repo_consistency.py` |
| FR21 | 8 | Full buddy loop | all relevant tools | PM -> Market -> Design -> Dev -> Test passes | mismatched handoff rejected | final object graph inspected | launcher-style runtime workspace | `tests/test_env_layer_end_to_end.py` |
| FR22 | 5, 8 | Prepare lifecycle contract | host `prepare`, then `env.tool` | prepare returns env tool capability | no hidden env mutation path | reservation/binding state inspected | runtime context contract | `tests/test_prepare_runtime_context.py` |
| FR23 | 8 | Workspace/project permission | representative tools | Dev write allowed | non-Dev write rejected | project/source state inspected | launcher workspace | `tests/test_env_layer_boundaries.py` |
| FR24 | 2-8 | Runtime identity authority | representative mutations per tool | runtime identity succeeds | payload identity spoof rejects | state snapshots unchanged | broker/client public path | `tests/test_env_tool_identity.py` |
| FR25 | 2-8 | Unified response schema | one success/reject per tool | required success fields exist | required rejection fields exist | no mutation needed | broker/client public path | `tests/test_env_tool_response_contract.py` |

## Universal Test Rules

- Every phase must include at least one public broker/client/launcher test.
- Every mutation test must re-read persisted state from disk, not only assert response JSON.
- Every rejection test that reaches, or could plausibly reach, a mutation boundary must prove no partial mutation by comparing state snapshots before and after. Envelope validation and read-only rejection tests should assert structured feedback, and only snapshot state when the request could otherwise mutate state.
- Do not assert exact long prose strings. Assert semantic fields such as `ok`, `tool`, `action`, `error.code`, `permission_boundary`, `allowed_next_actions`, `stop_condition`, and `command_hint`.
- Do not make cross-buddy tests pass by hiding all foreign ids. Named foreign access should reject with boundary feedback while avoiding full foreign detail leaks.
- Do not put permission matrices into `AGENTS.md` or `SKILL.md` to satisfy tests. Permissions must be enforced by runtime/tool/service code.
- Do not preserve dual active paths. A replaced path must be deleted, migrated, or classified as historical/debug-only by a repo consistency test.
- Do not use the main checkout or tracked source state directories as writable test state. Use launcher-style temporary runtime roots.
- Every operation advertised in `prepare.runtime_context.env_tools` should have at least one public-surface smoke or response-contract test. Keep deep state assertions focused on the primary mutation paths instead of exhaustively duplicating every action.
- Residue checks must be active-surface aware. Do not fail final rerun solely because historical specs mention old paths; fail when active code, active tests, active framework docs, active skills, AGENTS, or launcher assets advertise or call retired product paths.

## Horizontal Contract Test Groups

These groups are intentionally small and representative. They prevent cross-phase drift without expanding into full action-by-action duplication.

### HTG-01 Prepare Lifecycle Contract

**Purpose:** Prove `prepare` is a clear host lifecycle preflight and not an untracked second env tool layer.

**Create/modify tests:**

- Modify `tests/test_prepare_runtime_context.py`
- Modify `tests/test_turn_runtime.py`
- Modify `tests/test_runtime_broker.py`
- Modify `tests/test_repo_consistency.py`

**Test cases:**

1. Broker `prepare` accepts ordinary user text and returns `request_text` unchanged.
2. Switch-era text remains ordinary request text and does not route buddy/task.
3. `prepare.runtime_context.env_tools` advertises `env.tool` and not a domain-specific `env.task` path.
4. `prepare` output includes active instance id, active buddy, current task id, optional track id, context revision, and run envelope.
5. `prepare` does not expose raw state write instructions in runtime context, AGENTS, or skills.
6. Runtime feedback that asks for another prepare uses the canonical prepare command.

**Proof:** Inspect prepare payload, launcher instance binding where prepare is expected to bind context, and repo consistency surfaces.

### HTG-02 Workspace And Project Permission Boundary

**Purpose:** Prove env tools cannot bypass the BuddySwitch workspace contract.

**Create/modify tests:**

- Create `tests/test_env_layer_boundaries.py`
- Modify `tests/test_buddy_env_sandbox.py`
- Modify `tests/test_buddyswitch_launcher.py`
- Modify `tests/test_repo_consistency.py`

**Test cases:**

1. Dev prepare context reports `projects/app` write access.
2. PM, Market, Design, and Test prepare contexts report `projects/app` read-only access.
3. A Dev runtime workspace can write inside `projects/app` only through normal project write paths, not raw state paths.
4. Non-Dev attempts to write `projects/app` through env tool payloads or runtime outputs reject or remain impossible.
5. No env tool writes outside launcher-managed shared root, runtime root, scratch, or allowed project workspace.
6. Cleanup/admin paths cannot delete or mutate `projects/app`, the source checkout, or symlink escapes.

**Proof:** Inspect prepare payloads, attempted writes, filesystem snapshots, and cleanup boundary assertions.

### HTG-03 Cross-Tool Runtime Identity Authority

**Purpose:** Prove runtime identity is enforced uniformly across tools.

**Create/modify tests:**

- Create `tests/test_env_tool_identity.py`
- Modify each phase-specific env tool test only where a representative mutation is already present.

**Representative spoof attempts:**

1. `task.create` payload includes `buddy="pm"` from a Dev instance; created task remains Dev-owned.
2. `track.create` payload includes `active_buddy="pm"` from a Dev instance; lifecycle mutation rejects.
3. `artifact.create_revision` payload includes foreign `buddy` or foreign task id; mutation rejects.
4. `binding.set_task` payload includes foreign `instance_id`; active launcher instance remains authoritative.
5. `run.commit` payload includes mismatched buddy/instance/context identity; commit rejects.
6. `evidence.issue_browser` payload includes mismatched buddy/instance/run scope; token is not issued.

**Proof:** Compare object directories and launcher instance JSON before and after each rejected spoof attempt.

### HTG-04 Unified Env Tool Response Contract

**Purpose:** Prove every tool gives Codex machine-readable feedback.

**Create/modify tests:**

- Create `tests/test_env_tool_response_contract.py`
- Reuse phase-specific fixtures for task, track, artifact, context, binding, run, and evidence.

**Minimum success fields:**

- `ok=true`
- `tool`
- `action`
- `active_buddy` when a buddy context exists
- resource payload or receipt
- `allowed_next_actions` when a next action is useful

**Minimum rejection fields:**

- `ok=false`
- `tool`
- `action`
- `error.code`
- `error.message`
- `permission_boundary` for permission, payload, ownership, identity, and context failures
- `allowed_next_actions` for recoverable failures or `stop_condition` for non-recoverable failures
- `command_hint` only when the hinted command is canonical and safe

**Representative coverage:** One success and one rejection per final public tool: `task`, `track`, `artifact`, `context`, `binding`, `run`, and `evidence`.

## Phase 1: Task Manager Baseline Verification

**Purpose:** Confirm the completed task-manager first slice is a safe baseline before migrating it to `env.tool`.

**Existing test groups:**

- `tests/test_task_manager_env_tool.py`
- `tests/test_runtime_broker.py`
- `tests/test_prepare_runtime_context.py`
- `tests/test_runtime_skills.py`
- `tests/test_repo_consistency.py`
- `tests/test_buddyswitch_launcher.py`

**Test cases:**

1. Every buddy materializes the shared `task-manager` skill.
2. Active buddy can create, list, get, update, archive, get-current, and set-current own tasks.
3. Foreign task get/update/archive/set-current rejects with structured feedback.
4. `task.set_current` updates active instance `current_task_id` and synchronizes `current_track_id`.
5. `prepare.runtime_context.env_tools` contains compact task-manager hints.
6. Product tests do not call `scripts/env_tasks.py` as the task-manager path.

**Commands:**

```bash
python3 -m pytest -p no:cacheprovider tests/test_task_manager_env_tool.py -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py -q
python3 -m pytest -p no:cacheprovider tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_prepare_exposes_task_manager_env_tool_hints -q
```

**Anti-cheat guard:** Do not treat Phase 1 `env.task` as the final contract. It is a baseline that Phase 2 must replace.

## Phase 2: Unified Env Tool Envelope Tests

**Purpose:** Prove active product runtime uses `env.tool` and task-manager still behaves exactly as Phase 1 after migration.

**Create/modify tests:**

- Create `tests/test_env_tool_router.py`
- Modify `tests/test_task_manager_env_tool.py`
- Modify `tests/test_runtime_broker.py`
- Modify `tests/test_prepare_runtime_context.py`
- Modify `tests/test_runtime_tool_feedback.py`
- Modify `tests/test_repo_consistency.py`
- Modify `tests/test_buddyswitch_launcher.py`

**Positive test cases:**

1. Broker accepts `method="env.tool"` with `tool="task"` and `action="list"`.
2. Env client task commands send `env.tool`, not `env.task`.
3. Task create/list/get/update/archive/set-current behavior remains equivalent to Phase 1.
4. `prepare.runtime_context.env_tools.task_manager` documents the unified envelope and task payload fields.
5. Launcher-materialized runtime workspace includes `scripts/env/client.py` and task tool modules.

**Boundary test cases:**

1. Missing `payload.tool` rejects with `permission_boundary="env.tool"`.
2. Missing `payload.action` rejects with `permission_boundary="env.tool"`.
3. Non-object `payload.args` rejects with `permission_boundary="request-payload"`.
4. Unknown tool rejects without importing arbitrary modules.
5. Unknown task action rejects with supported action hints.
6. Active code does not retain `method == "env.task"` or `request_runtime_broker("env.task", ...)`.

**Persisted state proof:**

- For successful task mutation, re-read `buddyswitch/objects/tasks/<task-id>.json`.
- For `set_current`, re-read launcher instance JSON.
- For malformed envelope rejection, compare task and instance snapshots before/after.

**Commands:**

```bash
python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py tests/test_task_manager_env_tool.py tests/test_runtime_broker.py -q
python3 -m pytest -p no:cacheprovider tests/test_prepare_runtime_context.py tests/test_runtime_tool_feedback.py tests/test_repo_consistency.py tests/test_buddyswitch_launcher.py -q
rg -n "env\\.task|method == \"env.task\"|request_runtime_broker\\(\"env.task\"" scripts tests framework buddyswitch tools
```

**Anti-cheat guard:** Do not keep `env.task` as an accepted active alias to pass old tests. Tests must migrate to the final envelope.

## Phase 3: Track Manager Env Tool Tests

**Purpose:** Prove tracks are coordination objects, PM owns lifecycle mutation, and task-track linkage remains consistent.

**Create/modify tests:**

- Create `tests/test_track_manager_env_tool.py`
- Modify `tests/test_runtime_skills.py`
- Modify `tests/test_prepare_runtime_context.py`
- Modify `tests/test_repo_consistency.py`
- Modify `tests/test_buddyswitch_launcher.py`

**Positive test cases:**

1. Every buddy materializes shared `track-manager`.
2. PM creates a track with `title`, `status`, `current_buddy`, `next_buddy`, and `summary`.
3. PM updates track metadata.
4. PM advances `current_buddy` and `next_buddy`.
5. PM archives a track.
6. Any buddy with `track.read` can get permitted track summary.
7. `track.get_current` reads active instance `current_track_id`.
8. `track.attach_task` links a task to a track and updates both task and track state.
9. `track.detach_task` removes the link and updates both task and track state.

**Boundary test cases:**

1. Non-PM `track.create` rejects with `permission_boundary="track.lifecycle_authority"`.
2. Non-PM `track.update`, `track.advance`, and `track.archive` reject with no mutation.
3. Unknown `current_buddy` or `next_buddy` rejects.
4. Attaching a foreign-buddy task rejects.
5. Attaching a missing task or track rejects with lookup feedback.
6. Payload-authored `active_buddy` cannot turn a Dev request into PM authority.

**Persisted state proof:**

- Re-read `buddyswitch/objects/tracks/<track-id>.json`.
- Re-read linked `buddyswitch/objects/tasks/<task-id>.json`.
- Compare snapshots after rejected non-PM mutation.

**Commands:**

```bash
python3 -m pytest -p no:cacheprovider tests/test_track_manager_env_tool.py tests/test_runtime_skills.py tests/test_prepare_runtime_context.py -q
python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py tests/test_buddyswitch_launcher.py -q
rg -n "scripts/env_tracks.py|buddyswitch/skills/pm/track-manager" scripts tests framework buddyswitch tools
```

**Anti-cheat guard:** Do not satisfy PM authority by hiding the track tool from non-PM buddies. Non-PM calls should reach the service and receive structured rejection.

## Phase 4: Artifact Manager Env Tool Tests

**Purpose:** Prove artifact state is active-buddy scoped, revision-safe, and does not expose global foreign artifacts as a product API.

**Create/modify tests:**

- Create `tests/test_artifact_manager_env_tool.py`
- Modify `tests/test_env_store_v2.py` only for missing product invariants
- Modify `tests/test_artifact_selection.py`
- Modify `tests/test_runtime_skills.py`
- Modify `tests/test_prepare_runtime_context.py`
- Modify `tests/test_repo_consistency.py`
- Modify `tests/test_buddyswitch_launcher.py`

**Positive test cases:**

1. Every buddy materializes shared `artifact-manager`.
2. Active buddy lists artifacts for its current task.
3. Active buddy gets an artifact belonging to its task.
4. Active buddy validates an artifact payload with an allowed kind.
5. Active buddy creates a first artifact revision for its task.
6. Active buddy creates a second revision for the same kind; the second is current and the first is non-current.
7. Task `artifact_slots` records current artifact id and revision count.
8. Artifact selection still chooses current upstream artifacts for track context.
9. `artifact.update_metadata` has a lightweight public-surface smoke test and persists allowed metadata without changing artifact content.

**Boundary test cases:**

1. Listing without current task does not reveal global artifacts.
2. Getting an artifact from a foreign task rejects without full content leak.
3. Creating an artifact on a foreign task rejects.
4. Creating an artifact with a kind not allowed for the active buddy rejects.
5. Creating an artifact with malformed content rejects.
6. Payload-authored `buddy` cannot create an artifact for another buddy.
7. In-place content overwrite is not accepted as a replacement for revision creation.
8. Updating metadata for a foreign-task artifact rejects without leaking full content.

**Persisted state proof:**

- Re-read `buddyswitch/objects/artifacts/<artifact-id>.json`.
- Re-read current task JSON and inspect `artifact_ids` and `artifact_slots`.
- Compare artifact/task snapshots after rejected mutation.

**Commands:**

```bash
python3 -m pytest -p no:cacheprovider tests/test_artifact_manager_env_tool.py tests/test_env_store_v2.py tests/test_artifact_selection.py -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py tests/test_prepare_runtime_context.py tests/test_repo_consistency.py tests/test_buddyswitch_launcher.py -q
rg -n "scripts/env_artifacts.py|artifact\\.delete" scripts/env buddyswitch/skills/shared/artifact-manager framework/docs/turn-runtime-spec.md tests/test_artifact_manager_env_tool.py tests/test_repo_consistency.py
```

**Anti-cheat guard:** Do not make foreign artifact reads pass by globally omitting ids while still allowing direct id reads. Named direct foreign reads must reject with structured boundary feedback.
Do not treat a manifest/admin permission string as a buddy-facing artifact delete API; fail only if the env tool, skill, active docs, or active tests expose artifact deletion as product behavior.

## Phase 5: Context, Binding, And Handoff Tests

**Purpose:** Prove runtime context and launcher instance binding are service-owned, identity-scoped, and atomic.

**Create/modify tests:**

- Create `tests/test_context_binding_env_tool.py`
- Modify `tests/test_prepare_runtime_context.py`
- Modify `tests/test_turn_runtime.py`
- Modify `tests/test_runtime_tool_feedback.py`
- Modify `tests/test_artifact_selection.py`
- Modify `tests/test_repo_consistency.py`

**Positive test cases:**

1. `binding.get` returns active instance id, active buddy, current task id, and current track id.
2. `binding.set_task` to an active-buddy-owned untracked task sets `current_task_id` and clears `current_track_id`.
3. `binding.set_task` to an active-buddy-owned tracked task sets both `current_task_id` and `current_track_id`.
4. `binding.set_track` by PM sets current track when the track exists.
5. `context.get` returns current task summary, current track summary, selected artifacts, recent handoffs, and source descriptions.
6. `context.list_sources` returns stable names matching `prepare.runtime_context.context_sources_desc`.
7. `handoff.validate` accepts a known next buddy with reason and context.
8. `binding.clear` has a lightweight public-surface smoke test and clears only the active instance binding.

**Boundary test cases:**

1. `binding.set_task` to a foreign task rejects and leaves instance JSON unchanged.
2. `binding.set_track` by non-PM rejects unless derived from a valid owned task binding.
3. Missing active instance rejects.
4. Inactive instance rejects.
5. Context payload with wrong `instance_id` rejects.
6. Context payload with wrong `active_buddy` rejects.
7. Stale context revision rejects.
8. Handoff to unknown buddy rejects.
9. Handoff conflict with track `next_buddy` rejects.
10. Switch-era text remains ordinary request text and does not change active buddy/task.
11. Payload-authored `instance_id` cannot make `binding.clear` mutate another instance.

**Persisted state proof:**

- Re-read launcher instance JSON after binding success and rejection.
- Re-read task/track JSON only when binding action is expected to link state.
- Compare state snapshots after context and handoff rejection.

**Commands:**

```bash
python3 -m pytest -p no:cacheprovider tests/test_context_binding_env_tool.py tests/test_prepare_runtime_context.py tests/test_turn_runtime.py -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_tool_feedback.py tests/test_artifact_selection.py tests/test_repo_consistency.py -q
rg -n "_write_product_session_binding\\(" scripts/env scripts/runtime_kernel scripts/turn_runtime.py
rg -n "switch (pm|market|design|dev|test):" buddyswitch framework tools README.md
```

**Anti-cheat guard:** Do not validate only `turn_runtime.py` private helpers. At least one context and one binding test must go through `env.tool`.
Do not fail merely because `turn_runtime.py` keeps a prepare-context assembly helper; fail when binding mutation is split across product services or switch-era text routes state.

## Phase 6: Run, Persist, And Feedback Tests

**Purpose:** Prove persist/run state writes are service-owned, atomic, replay-safe, and feedback-consistent.

**Create/modify tests:**

- Create `tests/test_run_env_tool.py`
- Create `tests/test_run_env_services.py`
- Modify `tests/test_turn_runtime.py`
- Modify `tests/test_runtime_tool_feedback.py`
- Modify `tests/test_output_schema_boundaries.py`
- Modify `tests/test_market_browser_evidence.py`
- Modify `tests/test_repo_consistency.py`

**Positive test cases:**

1. `run.validate_result` accepts a well-formed result with execution summary and durable signal.
2. `run.commit` with a prepared context and artifact writes one run audit.
3. `run.commit` with task effect updates task status/summary.
4. `run.commit` with PM track effect creates or advances a track.
5. `run.commit` with artifact creates artifact revision through artifact service.
6. `run.commit` with handoff records handoff in run audit and next state.
7. Receipt includes task id, run id, artifact ids, track id when present, receipt paths, related run ids, and next state.
8. Host CLI `python3 scripts/turn_runtime.py persist ...` and broker `env.tool` run commit use the same run service implementation.
9. `run.get_receipt` and `run.get_raw` have lightweight public-surface read tests after a successful commit.

**Boundary test cases:**

1. Context with `ok=false` rejects.
2. Context with wrong instance rejects.
3. Context with wrong active buddy rejects.
4. Stale context revision rejects.
5. Reused run id rejects.
6. Missing `execution_summary` rejects with `permission_boundary="persist.execution_summary"`.
7. Summary-only commit with no artifact, state effect, or handoff rejects.
8. Artifact kind outside active buddy manifest rejects.
9. Non-PM track lifecycle effect rejects.
10. Handoff and track `next_buddy` mismatch rejects.
11. Market artifact-producing commit without evidence rejects.
12. Any invalid commit leaves task, track, artifact, run content, and instance binding unchanged.
13. Unknown or out-of-scope run read requests reject with structured feedback and no mutation.

**Persisted state proof:**

- Re-read `buddyswitch/content/runs/<run-id>.json`.
- Re-read task, track, and artifact object JSON.
- Re-read launcher instance JSON when refreshed binding is expected.
- Snapshot object directories before rejected commits and compare after rejection.

**Commands:**

```bash
python3 -m pytest -p no:cacheprovider tests/test_run_env_tool.py tests/test_run_env_services.py tests/test_turn_runtime.py -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_tool_feedback.py tests/test_output_schema_boundaries.py tests/test_market_browser_evidence.py tests/test_repo_consistency.py -q
rg -n "def _persist_buddy_run|request_runtime_broker\\(\"persist\"" scripts tests framework tools
```

**Anti-cheat guard:** Do not keep a second active mutation implementation in `turn_runtime.py` just to satisfy old persist tests. Tests should prove the service path owns writes.
Do not fail final rerun merely because host lifecycle wrappers such as `persist_buddy_run()` or broker `method == "persist"` still exist; fail if they contain a separate product mutation implementation instead of routing to the run service.

## Phase 7: Browser Evidence Env Tool Tests

**Purpose:** Prove browser evidence is issued by env tool, scoped to the active run/context, and still enforces Market browser requirements.

**Create/modify tests:**

- Create `tests/test_evidence_env_tool.py`
- Modify `tests/test_market_browser_evidence.py`
- Modify `tests/test_runtime_tool_feedback.py`
- Modify `tests/test_turn_integration.py`
- Modify `tests/test_buddyswitch_launcher.py`
- Modify `tests/test_repo_consistency.py`

**Positive test cases:**

1. Market `evidence.issue_browser` succeeds when browser cockpit ready page exists.
2. Issued browser token contains active instance id, buddy id, task id, track id, context revision, and run id.
3. Market `evidence.approve_downgrade` succeeds only with a non-empty reason.
4. A subsequent Market run commit accepts the token only for the same active run/context scope.

**Boundary test cases:**

1. Evidence call with wrong instance id rejects.
2. Evidence call with wrong active buddy rejects.
3. Evidence call with stale context revision rejects.
4. Evidence call with missing run envelope rejects.
5. Browser endpoint unavailable rejects with stop condition.
6. Browser endpoint ready but no usable page rejects or repairs according to browser ready-page contract.
7. Non-Market profile without required market evidence rejects evidence issuance.
8. Token from one run cannot be reused for another run.
9. Approved downgrade without reason rejects.

**Persisted state proof:**

- Re-read evidence token JSON under launcher runtime evidence-token directory.
- Confirm no token file is written after rejected calls.
- Confirm Market run audit includes accepted token in `tool_evidence`.

**Commands:**

```bash
python3 -m pytest -p no:cacheprovider tests/test_evidence_env_tool.py tests/test_market_browser_evidence.py tests/test_runtime_tool_feedback.py -q
python3 -m pytest -p no:cacheprovider tests/test_turn_integration.py tests/test_buddyswitch_launcher.py tests/test_repo_consistency.py -q
rg -n "issue_browser_evidence|request_runtime_broker\\(\"issue_browser_evidence\"|method == \"issue_browser_evidence\"" scripts tests framework buddyswitch tools
```

**Anti-cheat guard:** Do not downgrade Market browser evidence requirements through prompt text or ordinary web fallback. The token gate must remain runtime-enforced.

## Phase 8: Cleanup, Contracts, Launcher, And End-To-End Tests

**Purpose:** Prove the full env layer is the only active product path and works across the complete buddy collaboration loop.

**Create/modify tests:**

- Create `tests/test_env_layer_end_to_end.py`
- Create `tests/test_env_layer_boundaries.py`
- Create `tests/test_env_tool_identity.py`
- Create `tests/test_env_tool_response_contract.py`
- Modify `tests/test_repo_consistency.py`
- Modify `tests/test_buddyswitch_launcher.py`
- Modify `tests/test_runtime_skills.py`
- Modify `tests/test_prepare_runtime_context.py`
- Modify `tests/test_cleanup_system.py` if cleanup boundaries are affected

**Active surface consistency test cases:**

1. Active code does not contain accepted `env.task` broker dispatch.
2. Active code does not call `scripts/env_tasks.py`, `scripts/env_tracks.py`, or `scripts/env_artifacts.py` as product paths.
3. Active docs, AGENTS, and SKILL files do not instruct buddies to write raw `buddyswitch/objects/**` or `buddyswitch/content/runs/**`.
4. `prepare.runtime_context.env_tools` lists task, track, artifact, context, binding, run, and evidence tools with the unified envelope.
5. Launcher-materialized runtime workspace contains all required `scripts/env/` modules.
6. Launcher-materialized runtime workspace contains shared task, track, and artifact manager skills.
7. Historical Phase 1 docs may retain `env.task` only when classified as historical baseline.
8. Prepare remains a documented host preflight entrypoint and not a hidden second env tool implementation.
9. Cross-tool response shapes satisfy the unified success/rejection contract.
10. Cross-tool identity spoof attempts fail or are ignored consistently.

**End-to-end test flow:**

1. PM instance prepares a product iteration request.
2. PM creates a track through `env.tool track.create`.
3. PM creates or binds a PM task through `env.tool task.create` and `binding.set_task`.
4. PM commits a PRD artifact and handoff to Market through `env.tool run.commit`.
5. Market prepares on the handed-off context.
6. Market issues browser evidence through `env.tool evidence.issue_browser`.
7. Market commits market artifact and handoff to Design.
8. Design commits design artifact and handoff to Dev.
9. Dev commits implementation artifact, task status/summary update, and handoff to Test.
10. Test commits test report artifact and closes the task or reports blocked status.

**End-to-end assertions:**

- One track object exists with expected task linkage and final status.
- Each buddy task belongs to the active buddy that created it.
- Artifacts exist with allowed kinds and correct source buddies.
- Artifact current slots point to the latest revision.
- Run content exists for each commit and records handoff continuity.
- Evidence token is scoped to the Market run that used it.
- No raw state mutation recipe appears in active skills or AGENTS.
- Every env operation in the flow uses `env.tool`.

**Cleanup and boundary test cases:**

1. Old debug/manual product-overlap scripts are deleted or classified admin-only.
2. Cleanup tools cannot delete `projects/app` or source checkout paths.
3. Cleanup tools respect symlink and shared-root boundaries.
4. Runtime state remains under launcher-managed shared root and projected runtime paths.
5. Dev project write access and non-Dev project read-only access are still enforced.

**Commands:**

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_router.py \
  tests/test_task_manager_env_tool.py \
  tests/test_track_manager_env_tool.py \
  tests/test_artifact_manager_env_tool.py \
  tests/test_context_binding_env_tool.py \
  tests/test_run_env_tool.py \
  tests/test_evidence_env_tool.py \
  tests/test_env_tool_identity.py \
  tests/test_env_tool_response_contract.py \
  tests/test_env_layer_boundaries.py \
  tests/test_env_layer_end_to_end.py -q

python3 -m pytest -p no:cacheprovider \
  tests/test_runtime_broker.py \
  tests/test_prepare_runtime_context.py \
  tests/test_turn_runtime.py \
  tests/test_runtime_tool_feedback.py \
  tests/test_market_browser_evidence.py \
  tests/test_env_store_v2.py \
  tests/test_artifact_selection.py \
  tests/test_output_schema_boundaries.py \
  tests/test_cleanup_system.py \
  tests/test_repo_consistency.py \
  tests/test_buddyswitch_launcher.py \
  tests/test_runtime_skills.py -q

rg -n "env\\.task|issue_browser_evidence|scripts/env_tasks.py|scripts/env_tracks.py|scripts/env_artifacts.py" \
  buddyswitch scripts tests framework tools
rg -n "buddyswitch/objects/.+write|permission matrix" \
  buddyswitch/skills tools/launcher/assets/buddies framework/docs/turn-runtime-spec.md framework/docs/skill-runtime-shared-rules.md README.md
test ! -e scripts/env_tasks.py
test ! -e scripts/env_tracks.py
test ! -e scripts/env_artifacts.py
test ! -e buddyswitch/skills/pm/track-manager/SKILL.md
```

**Anti-cheat guard:** Do not satisfy cleanup by deleting search strings only. The end-to-end test must prove the replacement product path works.

## Required Per-Phase Confirmation And Handoff

This section applies to future phased development mode. In final rerun mode, do not block acceptance on reconstructing historical phase reports or handoff prompts; rerun the final gate, active-surface residue checks, and any focused tests for changed areas.

After each phase:

1. Run the focused phase tests.
2. Run the listed regression anchors.
3. Run the phase residue search.
4. Summarize pass/fail output and any remaining risk.
5. Ask the user to confirm the tested phase is accepted.
6. Generate a handoff prompt for the next phase.
7. Stop until the user uses that handoff prompt after `/clear`.

Handoff prompt must include:

- completed phase number and name;
- exact changed files;
- current active `env.tool` contract;
- tests run and pass/fail output;
- persisted state proof used by the tests;
- residue search command and remaining matches;
- next phase goal, scope, and forbidden scope;
- stop condition for the next phase.

## Final Regression Gate

The final full gate is:

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_router.py \
  tests/test_task_manager_env_tool.py \
  tests/test_track_manager_env_tool.py \
  tests/test_artifact_manager_env_tool.py \
  tests/test_context_binding_env_tool.py \
  tests/test_run_env_tool.py \
  tests/test_run_env_services.py \
  tests/test_evidence_env_tool.py \
  tests/test_env_tool_identity.py \
  tests/test_env_tool_response_contract.py \
  tests/test_env_layer_boundaries.py \
  tests/test_env_layer_end_to_end.py \
  tests/test_runtime_broker.py \
  tests/test_prepare_runtime_context.py \
  tests/test_turn_runtime.py \
  tests/test_runtime_tool_feedback.py \
  tests/test_market_browser_evidence.py \
  tests/test_env_store_v2.py \
  tests/test_artifact_selection.py \
  tests/test_output_schema_boundaries.py \
  tests/test_cleanup_system.py \
  tests/test_repo_consistency.py \
  tests/test_buddyswitch_launcher.py \
  tests/test_runtime_skills.py -q

PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile \
  scripts/env/client.py \
  scripts/env/tools/router.py \
  scripts/env/tools/task_manager.py \
  scripts/env/tools/track_manager.py \
  scripts/env/tools/artifact_manager.py \
  scripts/env/tools/context_manager.py \
  scripts/env/tools/binding_manager.py \
  scripts/env/tools/run_manager.py \
  scripts/env/tools/evidence_manager.py \
  scripts/env/services/tasks.py \
  scripts/env/services/tracks.py \
  scripts/env/services/artifacts.py \
  scripts/env/services/context.py \
  scripts/env/services/bindings.py \
  scripts/env/services/handoffs.py \
  scripts/env/services/runs.py \
  scripts/env/services/evidence.py \
  scripts/runtime_kernel/broker.py \
  scripts/runtime_kernel/persist.py \
  scripts/turn_runtime.py
```

Then run the active-surface residue and retired-file checks:

```bash
rg -n "env\\.task|issue_browser_evidence|scripts/env_tasks.py|scripts/env_tracks.py|scripts/env_artifacts.py" \
  buddyswitch scripts tests framework tools
rg -n "buddyswitch/objects/.+write|permission matrix" \
  buddyswitch/skills tools/launcher/assets/buddies framework/docs/turn-runtime-spec.md framework/docs/skill-runtime-shared-rules.md README.md
test ! -e scripts/env_tasks.py
test ! -e scripts/env_tracks.py
test ! -e scripts/env_artifacts.py
test ! -e buddyswitch/skills/pm/track-manager/SKILL.md
```

The task is not complete unless focused tests, regression tests, compile proof, residue search, and end-to-end state inspection all support the claimed final env layer behavior.
