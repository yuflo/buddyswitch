# Buddy Env Layer Phase 1-N Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` before implementing any phase in this plan. Use `superpowers:test-driven-development` before production code changes and `superpowers:verification-before-completion` before claiming a phase is complete. Steps use checkbox (`- [ ]`) syntax for phase tracking.

**Goal:** Rebuild BuddySwitch's full buddy env layer so every product state capability uses a unified skill-facing `env.tool` envelope, runtime-injected identity, service-owned permissions, structured feedback, and verified launcher/runtime contracts.

**Architecture:** Keep the skill layer concise and user-facing, route all buddy-callable state operations through one broker method (`env.tool`), and place product semantics in focused env services. `turn_runtime.py` and the existing debug scripts should stop owning product state behavior as each domain moves into `scripts/env/`.

**Tech Stack:** Python stdlib, existing BuddySwitch launcher/runtime broker, `scripts/env_store.py` JSON object store, native skill packages under `buddyswitch/skills`, pytest/unittest, launcher-managed runtime workspaces.

---

## Working Directory

Run all work from:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0210
```

Do not edit the main checkout at `/Users/chen/Dev/buddyswitch`.

## Source Decisions

This plan starts from the completed Phase 1 task-manager slice:

- `docs/spec/2026-05-10-buddy-env-layer-task-manager-development-plan.md`
- `docs/spec/2026-05-10-buddy-env-layer-task-manager-test-plan.md`
- Commit `c07b4ac Add shared task-manager env tool flow`

User-confirmed direction:

- No historical compatibility preservation.
- Rebuild forward while no production instance is online.
- Replace active product paths instead of stacking wrappers.
- Migrate current `env.task` into a unified `env.tool` envelope.
- Phase order: tool envelope, track, artifact, context/binding, persist/run, browser evidence, cleanup/contracts.
- After each phase: implement, test, report to the user, generate a handoff prompt, then stop until the user confirms the next phase.

## Current Bottleneck

Phase 1 proved the first env-service pattern with `task-manager`, but the runtime still has a domain-specific broker method:

```json
{
  "method": "env.task",
  "payload": {
    "action": "list",
    "args": {}
  }
}
```

The current bottleneck is the lack of one stable lower-level tool envelope. Track, artifact, context, persist, and evidence cannot converge while task remains a special broker method.

## Target Env Tool Contract

All buddy-callable env operations use:

```json
{
  "method": "env.tool",
  "payload": {
    "tool": "task",
    "action": "list",
    "args": {}
  }
}
```

Allowed final tool names:

- `task`
- `track`
- `artifact`
- `context`
- `binding`
- `run`
- `evidence`

CLI pattern:

```bash
python3 scripts/env/client.py task list
python3 scripts/env/client.py track get --track-id track-example
python3 scripts/env/client.py artifact list
python3 scripts/env/client.py binding get
python3 scripts/env/client.py run commit --context /tmp/context.json --result /tmp/result.json
python3 scripts/env/client.py evidence issue --payload /tmp/evidence.json
```

There is no final active `env.task`, `issue_browser_evidence`, `scripts/env_tasks.py`, `scripts/env_tracks.py`, or `scripts/env_artifacts.py` product path.

## Response Contract

Every env tool response is a JSON object.

Success shape:

```json
{
  "ok": true,
  "tool": "task",
  "action": "task.list",
  "active_buddy": "dev",
  "payload": {},
  "allowed_next_actions": []
}
```

Rejection shape:

```json
{
  "ok": false,
  "tool": "task",
  "action": "task.set_current",
  "error": {
    "code": "E_TASK_BUDDY_SCOPE",
    "message": "task belongs to buddy 'pm', not active buddy 'dev'"
  },
  "permission_boundary": "task.buddy_scope",
  "active_buddy": "dev",
  "allowed_next_actions": [
    "Choose a task owned by the active buddy.",
    "Use handoff or track context instead of cross-buddy task mutation."
  ]
}
```

Required semantic fields:

- `ok`
- `tool`
- `action`
- `active_buddy` when an active buddy is available
- `error.code` and `error.message` on rejection
- `permission_boundary` on permission, ownership, identity, context, and payload rejection
- `allowed_next_actions` for recoverable rejection
- `stop_condition` for non-recoverable runtime blockage
- `command_hint` only when a command is safe and canonical

## Ownership Rules

These rules are product semantics, not prompt wording:

- Task ownership: `task.buddy == active_buddy` is required for task read detail and mutation.
- Track ownership: track lifecycle mutation is PM-owned through `track.create`, `track.update`, `track.advance`, and `track.archive`; all buddies may read track context through runtime-approved surfaces.
- Artifact ownership: artifact mutation requires the artifact task to belong to the active buddy and the artifact kind to be allowed for the active buddy.
- Context ownership: prepared context belongs to one active instance, one active buddy, one current task, one optional current track, and one context revision.
- Binding ownership: launcher instance binding is runtime-owned; skills cannot mutate instance JSON directly.
- Run ownership: run reservation, commit, receipt, and raw run content are runtime-owned.
- Evidence ownership: evidence tokens are runtime-issued and scoped to active instance, buddy, task, track, context revision, and run.
- Handoff is the legal cross-buddy collaboration signal. Cross-buddy task/artifact mutation remains forbidden.
- Payload-authored `buddy`, `active_buddy`, and `instance_id` never widen authority.

## File Responsibility Map

Create or converge on:

- `scripts/env/client.py`: the only skill-facing env tool CLI.
- `scripts/env/tools/router.py`: validates the `env.tool` envelope and routes to tool dispatchers.
- `scripts/env/tools/task_manager.py`: task action dispatcher.
- `scripts/env/tools/track_manager.py`: track action dispatcher.
- `scripts/env/tools/artifact_manager.py`: artifact action dispatcher.
- `scripts/env/tools/context_manager.py`: context action dispatcher.
- `scripts/env/tools/binding_manager.py`: binding action dispatcher.
- `scripts/env/tools/run_manager.py`: run/persist action dispatcher.
- `scripts/env/tools/evidence_manager.py`: browser evidence action dispatcher.
- `scripts/env/services/tasks.py`: active-buddy task domain rules.
- `scripts/env/services/tracks.py`: PM-owned track lifecycle and read surfaces.
- `scripts/env/services/artifacts.py`: active-buddy artifact read/write/revision rules.
- `scripts/env/services/context.py`: prepare context projection and current context reads.
- `scripts/env/services/bindings.py`: launcher instance binding reads/writes.
- `scripts/env/services/runs.py`: run reservation, persist commit, receipts, state effects, and atomic rejection.
- `scripts/env/services/evidence.py`: browser evidence token validation and issuance.
- `scripts/env/store/objects.py`: optional low-level facade over `scripts/env_store.py` introduced only when a migrated service needs a narrower store boundary.
- `scripts/runtime_kernel/broker.py`: protocol, active instance identity, active buddy identity, active status, runtime lock, and broker dispatch to `env.tool`.
- `scripts/turn_runtime.py`: prepare CLI and orchestration until context/run services replace internal helpers.
- `buddyswitch/skills/shared/task-manager/SKILL.md`: shared task skill.
- `buddyswitch/skills/shared/track-manager/SKILL.md`: shared track skill, with PM-only mutation enforced by service.
- `buddyswitch/skills/shared/artifact-manager/SKILL.md`: shared artifact skill, with active-buddy artifact mutation enforced by service.
- `framework/contracts/prepare-turn-context.json`: required runtime context sections including unified `env_tools`.
- `framework/docs/turn-runtime-spec.md`: active runtime contract.
- `tools/launcher/workspace.sh`: projects `scripts/env/` and required runtime surfaces into product instances.

Do not create a generic plugin system, permission DSL, event bus, workflow engine, or service split outside this tree.

## Phase Completion Protocol

Every phase follows the same stop rule:

1. Implement only the current phase.
2. Run the focused tests for that phase.
3. Run the nearest regression anchors listed in the phase.
4. Run a residue search for replaced active paths.
5. Report the result to the user.
6. Generate a handoff prompt for the next phase.
7. Stop. Do not start the next phase until the user confirms after `/clear`.

Handoff prompt template:

```markdown
Continue BuddySwitch env layer work in `/Users/chen/Dev/buddyswitch/.worktrees/dev0210`.

Completed phase: Phase <number> - <name>.
Current contract: all active buddy env operations use broker method `env.tool` with payload `{tool, action, args}`.
No historical compatibility: replace active paths; do not preserve aliases unless the current phase explicitly needs a temporary internal bridge.

Changed files:
- <path>: <what changed>

Verification already run:
- `<command>` -> <pass/fail and important output>

Residue search:
- `<rg command>` -> <remaining matches and classification>

Next phase to implement:
- Phase <number> - <name>

Next phase scope:
- <exact scope>

Forbidden scope:
- <what not to change in the next phase>

Stop condition:
- After implementing and testing this phase, report verification, generate the next handoff prompt, and wait for user confirmation.
```

## Phase 1: Task Manager First Slice Baseline

**Status:** Completed by `c07b4ac Add shared task-manager env tool flow`.

**Purpose:** Preserve the verified first env-service slice as the baseline before replacing `env.task`.

**Files already in the baseline:**

- `buddyswitch/skills/shared/task-manager/SKILL.md`
- `scripts/env/client.py`
- `scripts/env/services/tasks.py`
- `scripts/env/tools/task_manager.py`
- `scripts/runtime_kernel/broker.py`
- `scripts/turn_runtime.py`
- `tools/launcher/workspace.sh`
- `tests/test_task_manager_env_tool.py`
- `tests/test_runtime_broker.py`
- `tests/test_prepare_runtime_context.py`
- `tests/test_repo_consistency.py`
- `tests/test_buddyswitch_launcher.py`

**Baseline verification:**

- [ ] Run `python3 -m pytest -p no:cacheprovider tests/test_task_manager_env_tool.py -q`.
- [ ] Run `python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py -q`.
- [ ] Run `python3 -m pytest -p no:cacheprovider tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_prepare_exposes_task_manager_env_tool_hints -q`.
- [ ] Confirm Phase 1 docs remain historical/baseline references once Phase 2 replaces `env.task`.

**Stop condition:** Phase 1 remains accepted only if the baseline tests pass before Phase 2 begins.

## Phase 2: Unified `env.tool` Envelope And Task Migration

**Goal:** Replace active `env.task` with one `env.tool` broker method and migrate task-manager to it.

**Create:**

- `scripts/env/tools/router.py`
- `tests/test_env_tool_router.py`

**Modify:**

- `scripts/runtime_kernel/broker.py`
- `scripts/env/client.py`
- `scripts/env/tools/task_manager.py`
- `scripts/env/services/tasks.py` only if response fields need `tool`
- `scripts/turn_runtime.py`
- `framework/contracts/prepare-turn-context.json`
- `framework/docs/turn-runtime-spec.md`
- `buddyswitch/skills/shared/task-manager/SKILL.md`
- `tests/test_task_manager_env_tool.py`
- `tests/test_runtime_broker.py`
- `tests/test_prepare_runtime_context.py`
- `tests/test_runtime_tool_feedback.py`
- `tests/test_repo_consistency.py`
- `tests/test_buddyswitch_launcher.py`

**Implementation steps:**

- [ ] Write failing router tests for valid `env.tool` payloads: `tool=task`, supported task action, object `args`.
- [ ] Write failing router tests for invalid envelopes: missing `tool`, missing `action`, non-object `args`, unknown tool, unknown action.
- [ ] Update task-manager tests so every broker request uses `method="env.tool"` and payload `{"tool": "task", "action": "...", "args": {...}}`.
- [ ] Add `scripts/env/tools/router.py` with a static dispatch map for `task`.
- [ ] Return structured envelope rejection with `permission_boundary="request-payload"` or `permission_boundary="env.tool"`.
- [ ] Add `_env_tool_dispatch()` in `scripts/runtime_kernel/broker.py`.
- [ ] Replace the active `method == "env.task"` branch with `method == "env.tool"`.
- [ ] Update broker unsupported-method feedback to list `prepare`, `persist`, `env.tool`, and `issue_browser_evidence` only until later phases remove the remaining top-level mutation methods.
- [ ] Update `scripts/env/client.py` so all task CLI operations call `request_runtime_broker("env.tool", {"tool": "task", "action": action, "args": args})`.
- [ ] Update task response shaping so success and rejection include `tool="task"`.
- [ ] Update `prepare.runtime_context.env_tools` so it documents the envelope and not `env.task`.
- [ ] Update `task-manager/SKILL.md` to show `scripts/env/client.py task ...` as the CLI and `env.tool` as the broker contract.
- [ ] Add repo consistency checks that active code and docs do not advertise `env.task`.
- [ ] Keep existing Phase 1 docs as historical baseline; classify their `env.task` mentions as historical-only.

**Verification:**

```bash
python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py tests/test_task_manager_env_tool.py tests/test_runtime_broker.py -q
python3 -m pytest -p no:cacheprovider tests/test_prepare_runtime_context.py tests/test_runtime_tool_feedback.py tests/test_repo_consistency.py -q
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/env/client.py scripts/env/tools/router.py scripts/env/tools/task_manager.py scripts/runtime_kernel/broker.py scripts/turn_runtime.py
rg -n "env\\.task|method == \"env.task\"|request_runtime_broker\\(\"env.task\"" scripts tests framework buddyswitch tools
```

**Expected residue:** only Phase 1 historical docs may mention `env.task`.

**User confirmation:** Report Phase 2 verification and provide the Phase 3 handoff prompt before any track work starts.

## Phase 3: Track Manager Shared Env Tool

**Goal:** Rebuild track-manager onto the unified env tool/service model with PM-owned lifecycle mutation and runtime-enforced read boundaries.

**Create:**

- `buddyswitch/skills/shared/track-manager/SKILL.md`
- `scripts/env/services/tracks.py`
- `scripts/env/tools/track_manager.py`
- `tests/test_track_manager_env_tool.py`

**Modify:**

- `buddyswitch/manifest.toml`
- `buddyswitch/skills/pm/track-manager/SKILL.md` or delete it after shared migration
- `scripts/env/client.py`
- `scripts/env/tools/router.py`
- `scripts/turn_runtime.py`
- `framework/contracts/prepare-turn-context.json` if the `env_tools` shape changes
- `framework/docs/turn-runtime-spec.md`
- `tests/test_runtime_skills.py`
- `tests/test_prepare_runtime_context.py`
- `tests/test_repo_consistency.py`
- `tests/test_runtime_broker.py`
- `tests/test_buddyswitch_launcher.py`

**Track operations:**

- `track.list`
- `track.get`
- `track.get_current`
- `track.create`
- `track.update`
- `track.advance`
- `track.archive`
- `track.attach_task`
- `track.detach_task`

**Implementation steps:**

- [ ] Write failing tests for PM `track.create`, `track.update`, `track.advance`, and `track.archive` through `env.tool`.
- [ ] Write failing tests proving non-PM buddies with `track.read` can list/get approved track summaries but cannot mutate lifecycle fields.
- [ ] Write failing tests for `track.attach_task` and `track.detach_task`, including task-track backlink consistency.
- [ ] Write failing tests for `current_buddy` and `next_buddy` validation against manifest buddy ids.
- [ ] Move `track-manager` to `buddyswitch/skills/shared/track-manager` and add it to every buddy in the manifest.
- [ ] Keep skill text concise: purpose, use cases, env client commands, and runtime feedback interpretation.
- [ ] Implement `scripts/env/services/tracks.py` using `env_store.create_track`, `env_store.update_track`, `env_store.list_tracks`, and `env_store.get_track`.
- [ ] Enforce `track.create`, `track.update`, `track.advance`, and `track.archive` permissions through manifest and PM lifecycle authority.
- [ ] Ensure non-PM lifecycle rejection includes `permission_boundary="track.lifecycle_authority"`.
- [ ] Implement `track.get_current` from active instance binding.
- [ ] Implement task attach/detach with backlink consistency and no cross-buddy task mutation.
- [ ] Add `track` to `scripts/env/tools/router.py`.
- [ ] Add track CLI subcommands to `scripts/env/client.py`.
- [ ] Add track tool hints to `prepare.runtime_context.env_tools`.
- [ ] Delete the PM-only skill package or leave it only long enough to move content; final active manifest must point at the shared package.
- [ ] Reclassify or delete `scripts/env_tracks.py` from product surfaces.

**Verification:**

```bash
python3 -m pytest -p no:cacheprovider tests/test_track_manager_env_tool.py tests/test_runtime_broker.py -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py tests/test_prepare_runtime_context.py tests/test_repo_consistency.py -q
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/env/client.py scripts/env/services/tracks.py scripts/env/tools/track_manager.py scripts/env/tools/router.py scripts/runtime_kernel/broker.py
rg -n "scripts/env_tracks.py|buddyswitch/skills/pm/track-manager|track-manager" buddyswitch scripts tests framework tools docs/spec
```

**Stop condition:** Do not proceed if non-PM track lifecycle mutation can succeed or if task-track linkage can become one-sided.

**User confirmation:** Report Phase 3 verification and provide the Phase 4 handoff prompt.

## Phase 4: Artifact Manager Env Service And Tool

**Goal:** Move artifact read, validation, and revision writes behind active-buddy-scoped env services without bypassing run audit requirements.

**Create:**

- `buddyswitch/skills/shared/artifact-manager/SKILL.md`
- `scripts/env/services/artifacts.py`
- `scripts/env/tools/artifact_manager.py`
- `tests/test_artifact_manager_env_tool.py`

**Modify:**

- `buddyswitch/manifest.toml`
- `scripts/env/client.py`
- `scripts/env/tools/router.py`
- `scripts/turn_runtime.py`
- `framework/contracts/prepare-turn-context.json` if the `env_tools` shape changes
- `framework/docs/turn-runtime-spec.md`
- `tests/test_env_store_v2.py` only for product-level invariant coverage gaps
- `tests/test_artifact_selection.py`
- `tests/test_prepare_runtime_context.py`
- `tests/test_repo_consistency.py`
- `tests/test_runtime_skills.py`
- `tests/test_buddyswitch_launcher.py`

**Artifact operations:**

- `artifact.list`
- `artifact.get`
- `artifact.get_current`
- `artifact.validate_payload`
- `artifact.create_revision`
- `artifact.update_metadata`

No buddy-facing `artifact.delete` product operation is introduced. Cleanup remains admin/runtime maintenance.

**Implementation steps:**

- [ ] Write failing tests for `artifact.list` on the active current task.
- [ ] Write failing tests for `artifact.get` when the artifact belongs to the active buddy's task.
- [ ] Write failing tests proving foreign task artifacts are rejected by id with structured boundary feedback and no full content leak.
- [ ] Write failing tests for manifest artifact kind enforcement.
- [ ] Write failing tests for current revision promotion: new revision becomes current, previous revision becomes non-current, and task `artifact_slots` updates.
- [ ] Write failing tests for `source_run_id` validation against active context/run requirements.
- [ ] Add shared `artifact-manager` skill to every buddy manifest row.
- [ ] Implement `scripts/env/services/artifacts.py` as the only product artifact mutation service.
- [ ] Use `env_store.create_artifact`, `env_store.get_artifact`, `env_store.list_artifacts`, and `env_store.update_artifact` as low-level primitives only.
- [ ] Enforce `artifact.create` and `artifact.update` manifest permissions.
- [ ] Enforce `artifact.kind` belongs to active buddy artifact kinds.
- [ ] Enforce artifact task ownership: `artifact.task_id` must resolve to a task whose `buddy` equals active buddy for mutation.
- [ ] Keep cross-buddy upstream artifact access in context projection, not global artifact-manager listing.
- [ ] Add `artifact` to the env tool router and client.
- [ ] Add compact artifact tool hints to runtime context.
- [ ] Reclassify or delete `scripts/env_artifacts.py` from active product surfaces.

**Verification:**

```bash
python3 -m pytest -p no:cacheprovider tests/test_artifact_manager_env_tool.py tests/test_env_store_v2.py tests/test_artifact_selection.py -q
python3 -m pytest -p no:cacheprovider tests/test_prepare_runtime_context.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/env/client.py scripts/env/services/artifacts.py scripts/env/tools/artifact_manager.py scripts/env/tools/router.py
rg -n "scripts/env_artifacts.py|artifact.delete|buddyswitch/objects/artifacts" buddyswitch scripts tests framework tools docs/spec
```

**Stop condition:** Do not proceed if artifact writes can bypass active-buddy task ownership or run/source validation.

**User confirmation:** Report Phase 4 verification and provide the Phase 5 handoff prompt.

## Phase 5: Context, Binding, And Handoff Service Extraction

**Goal:** Move current context and instance binding semantics out of scattered `turn_runtime.py` helpers and task-specific service code.

**Create:**

- `scripts/env/services/context.py`
- `scripts/env/services/bindings.py`
- `scripts/env/services/handoffs.py`
- `scripts/env/tools/context_manager.py`
- `scripts/env/tools/binding_manager.py`
- `tests/test_context_binding_env_tool.py`

**Modify:**

- `scripts/env/services/tasks.py`
- `scripts/env/services/tracks.py`
- `scripts/env/client.py`
- `scripts/env/tools/router.py`
- `scripts/runtime_kernel/broker.py`
- `scripts/turn_runtime.py`
- `framework/contracts/prepare-turn-context.json`
- `framework/docs/turn-runtime-spec.md`
- `tests/test_prepare_runtime_context.py`
- `tests/test_turn_runtime.py`
- `tests/test_runtime_tool_feedback.py`
- `tests/test_artifact_selection.py`
- `tests/test_repo_consistency.py`

**Context and binding operations:**

- `context.get`
- `context.summarize`
- `context.list_sources`
- `binding.get`
- `binding.set_task`
- `binding.set_track`
- `binding.clear`
- `handoff.validate`

**Implementation steps:**

- [ ] Write failing tests proving `binding.get` returns the active instance binding from launcher instance JSON.
- [ ] Write failing tests proving `binding.set_task` accepts only active-buddy-owned tasks and synchronizes `current_track_id`.
- [ ] Write failing tests proving `binding.set_track` is PM-owned unless it is derived from an owned task binding.
- [ ] Write failing tests proving rejected binding mutations leave instance JSON unchanged.
- [ ] Write failing tests proving `context.get` rejects stale or mismatched instance/buddy/context revision payloads.
- [ ] Write failing tests proving `context.summarize` returns current task, track, artifacts, recent handoffs, and source descriptions without raw global state.
- [ ] Extract binding read/write helpers into `scripts/env/services/bindings.py`.
- [ ] Replace direct calls to `turn_runtime._write_product_session_binding()` from task and broker code with binding service calls.
- [ ] Extract current context summarization from `turn_runtime._build_runtime_context()` into `scripts/env/services/context.py` where practical.
- [ ] Extract handoff validation into `scripts/env/services/handoffs.py`.
- [ ] Add `context` and `binding` to the env tool router and client.
- [ ] Update `prepare.runtime_context.env_tools` with context and binding tool hints.
- [ ] Keep user text routing retired; no switch-era parsing returns.

**Verification:**

```bash
python3 -m pytest -p no:cacheprovider tests/test_context_binding_env_tool.py tests/test_prepare_runtime_context.py tests/test_turn_runtime.py -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_tool_feedback.py tests/test_artifact_selection.py tests/test_repo_consistency.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/env/services/context.py scripts/env/services/bindings.py scripts/env/services/handoffs.py scripts/env/tools/context_manager.py scripts/env/tools/binding_manager.py scripts/env/tools/router.py scripts/turn_runtime.py
rg -n "_write_product_session_binding|_build_runtime_context|switch " scripts tests framework tools
```

**Stop condition:** Do not proceed if binding mutation is split across multiple product services or if rejected binding writes are not atomic.

**User confirmation:** Report Phase 5 verification and provide the Phase 6 handoff prompt.

## Phase 6: Persist, Run, And Feedback Unification

**Goal:** Move run reservation, commit validation, state effects, artifact creation, receipts, and refreshed context feedback into env services while preserving host-facing lifecycle behavior.

**Create:**

- `scripts/env/services/runs.py`
- `scripts/env/tools/run_manager.py`
- `tests/test_run_env_tool.py`
- `tests/test_run_env_services.py`

**Modify:**

- `scripts/runtime_kernel/persist.py`
- `scripts/runtime_kernel/broker.py`
- `scripts/turn_runtime.py`
- `scripts/env/services/artifacts.py`
- `scripts/env/services/tracks.py`
- `scripts/env/services/tasks.py`
- `scripts/env/services/handoffs.py`
- `scripts/env/client.py`
- `scripts/env/tools/router.py`
- `framework/contracts/persist-buddy-run.json`
- `framework/docs/turn-runtime-spec.md`
- `tests/test_turn_runtime.py`
- `tests/test_runtime_tool_feedback.py`
- `tests/test_output_schema_boundaries.py`
- `tests/test_market_browser_evidence.py`
- `tests/test_repo_consistency.py`

**Run operations:**

- `run.commit`
- `run.get_receipt`
- `run.get_raw`
- `run.validate_result`

**Implementation steps:**

- [ ] Write failing tests for `env.tool` `tool=run`, `action=commit` with a valid prepared context and result.
- [ ] Write failing tests for stale context revision rejection.
- [ ] Write failing tests for replay rejection when a run id was already committed.
- [ ] Write failing tests for durable signal rejection when result has no artifacts, state effects, or handoff.
- [ ] Write failing tests for malformed artifact, task effect, track effect, handoff, and tool evidence payloads.
- [ ] Write failing tests proving invalid commits write no task, track, artifact, run content, or instance binding changes.
- [ ] Move commit validation and mutation logic from `turn_runtime._persist_buddy_run()` into `scripts/env/services/runs.py`.
- [ ] Make `scripts/runtime_kernel/persist.py` call the run service instead of `turn_runtime.persist_buddy_run()` as product semantics.
- [ ] Add `run` to env tool router and client.
- [ ] Route `python3 scripts/turn_runtime.py persist ...` through the same run service path; it may remain a host CLI, but it must not own a separate mutation implementation.
- [ ] Convert any remaining broker `persist` path into a caller of `scripts/env/services/runs.py`; no separate persist mutation implementation remains after this phase.
- [ ] Make artifact creation during persist call `scripts/env/services/artifacts.py`.
- [ ] Make track effects call `scripts/env/services/tracks.py`.
- [ ] Make task effects call `scripts/env/services/tasks.py`.
- [ ] Make handoff validation call `scripts/env/services/handoffs.py`.
- [ ] Normalize runtime feedback shapes across prepare, run commit, and env tool rejection.

**Verification:**

```bash
python3 -m pytest -p no:cacheprovider tests/test_run_env_tool.py tests/test_run_env_services.py tests/test_turn_runtime.py -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_tool_feedback.py tests/test_output_schema_boundaries.py tests/test_market_browser_evidence.py tests/test_repo_consistency.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/env/services/runs.py scripts/env/tools/run_manager.py scripts/env/tools/router.py scripts/runtime_kernel/persist.py scripts/runtime_kernel/broker.py scripts/turn_runtime.py
rg -n "def _persist_buddy_run|persist_buddy_run\\(|method == \"persist\"|request_runtime_broker\\(\"persist\"" scripts tests framework tools
```

**Expected residue:** host CLI tests/docs may mention `python3 scripts/turn_runtime.py persist` as a command; product state mutation and broker-routed commit behavior must live in the run service.

**Stop condition:** Do not proceed if persist/run can write partial state on rejected payloads or if two product mutation implementations remain active.

**User confirmation:** Report Phase 6 verification and provide the Phase 7 handoff prompt.

## Phase 7: Browser Evidence Env Tool

**Goal:** Move browser evidence issuance behind `env.tool` and preserve Market evidence gates, token scope, and browser ready-page checks.

**Create:**

- `scripts/env/services/evidence.py`
- `scripts/env/tools/evidence_manager.py`
- `tests/test_evidence_env_tool.py`

**Modify:**

- `scripts/runtime_kernel/broker.py`
- `scripts/browser_evidence.py` or delete it from active path
- `scripts/env/client.py`
- `scripts/env/tools/router.py`
- `scripts/turn_runtime.py`
- `framework/docs/browser-cockpit.md`
- `framework/docs/turn-runtime-spec.md`
- `tests/test_market_browser_evidence.py`
- `tests/test_runtime_tool_feedback.py`
- `tests/test_turn_integration.py`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_repo_consistency.py`

**Evidence operations:**

- `evidence.issue_browser`
- `evidence.approve_downgrade`
- `evidence.get_token`

**Implementation steps:**

- [ ] Write failing tests for Market `evidence.issue_browser` through `env.tool`.
- [ ] Write failing tests proving non-Market browser evidence requirements reject when profile does not require Market evidence.
- [ ] Write failing tests proving browser ready-page failure returns `stop_condition`, `permission_boundary="browser-cockpit-ready"`, and canonical `command_hint`.
- [ ] Write failing tests proving token scope includes active instance, buddy, task, track, context revision, and run.
- [ ] Write failing tests proving wrong context, stale run, wrong instance, and wrong buddy reject without issuing a token.
- [x] Extract evidence issuance from `scripts/runtime_kernel/broker.py` into `scripts/env/services/evidence.py`.
- [x] Add `evidence` to env tool router and client.
- [x] Replace active browser evidence broker dispatch with `env.tool` evidence dispatch.
- [x] Keep `scripts/browser_evidence.py` as a host CLI wrapper over `env.tool` evidence operations.
- [x] Keep browser ready-page semantics from the browser cockpit ready gate.

**Verification:**

```bash
python3 -m pytest -p no:cacheprovider tests/test_evidence_env_tool.py tests/test_market_browser_evidence.py tests/test_runtime_tool_feedback.py -q
python3 -m pytest -p no:cacheprovider tests/test_turn_integration.py tests/test_buddyswitch_launcher.py tests/test_repo_consistency.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/env/services/evidence.py scripts/env/tools/evidence_manager.py scripts/env/tools/router.py scripts/runtime_kernel/broker.py scripts/env/client.py
rg -n "issue_browser_evidence|request_runtime_broker\\(\"issue_browser_evidence\"|method == \"issue_browser_evidence\"" scripts tests framework buddyswitch tools
```

**Expected residue:** no active code or tests use the removed browser evidence broker method. The host `scripts/browser_evidence.py` CLI may remain only as a wrapper over `env.tool` evidence.

**Stop condition:** Do not proceed if evidence tokens can be issued outside the active context/run scope.

**User confirmation:** Report Phase 7 verification and provide the Phase 8 handoff prompt.

## Phase 8: Cleanup, Contracts, Launcher, And End-To-End Lock

**Goal:** Delete replaced product paths, lock contracts, and prove the full PM -> Market -> Design -> Dev -> Test env layer loop through launcher-style runtime state.

**Delete or retire from active product path:**

- `scripts/env_tasks.py`
- `scripts/env_tracks.py`
- `scripts/env_artifacts.py`
- `scripts/browser_evidence.py`
- stale PM-only `buddyswitch/skills/pm/track-manager`

**Create:**

- `tests/test_env_layer_boundaries.py`
- `tests/test_env_tool_identity.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_env_layer_end_to_end.py`

**Modify:**

- `framework/contracts/prepare-turn-context.json`
- `framework/contracts/persist-buddy-run.json`
- `framework/docs/turn-runtime-spec.md`
- `framework/docs/browser-cockpit.md`
- `tests/test_repo_consistency.py`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_runtime_skills.py`
- `tools/launcher/workspace.sh`
- `tools/launcher/assets/buddies/*/AGENTS.md` only if active guidance still references removed paths
- `buddyswitch/manifest.toml`

**Implementation steps:**

- [ ] Add repo consistency tests that active docs, skills, AGENTS, launcher scripts, and runtime context agree on `env.tool`.
- [ ] Add repo consistency tests that active surfaces do not reference `env.task`, `scripts/env_tasks.py`, `scripts/env_tracks.py`, `scripts/env_artifacts.py`, or `issue_browser_evidence`.
- [ ] Add prepare lifecycle tests proving `prepare` remains host preflight, returns unified env tool hints, preserves request text, and does not become a second buddy env tool implementation.
- [ ] Add workspace boundary tests proving Dev can write `projects/app`, non-Dev buddies remain read-only, and env tools cannot bypass project/raw-state boundaries.
- [ ] Add cross-tool identity tests proving task, track, artifact, binding, run, and evidence tools use runtime active instance and active buddy instead of payload-authored identity fields.
- [ ] Add response contract tests proving each env tool has one success and one rejection response with the required machine-readable fields.
- [ ] Add launcher tests proving a materialized instance contains `scripts/env/client.py`, all env tool modules, and shared manager skills.
- [ ] Add end-to-end runtime test that creates a PM track, hands off to Market, persists Market artifact evidence, hands off to Design, persists Design artifact, hands off to Dev, persists Dev artifact/task status, hands off to Test, and persists Test report.
- [ ] Assert final state files under `buddyswitch/objects/tracks`, `buddyswitch/objects/tasks`, `buddyswitch/objects/artifacts`, and `buddyswitch/content/runs`.
- [ ] Assert each phase of the end-to-end flow used `env.tool` for buddy env operations.
- [ ] Delete old debug scripts that overlap product behavior.
- [ ] Keep admin cleanup tools only when tests prove they are maintenance-only and not skill-facing product behavior.
- [ ] Update docs with the final env layer architecture and final active command contract.
- [ ] Inspect `git diff --stat` and confirm the change set stays on env layer scope.

**Verification:**

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

rg -n "env\\.task|issue_browser_evidence|scripts/env_tasks.py|scripts/env_tracks.py|scripts/env_artifacts.py|buddyswitch/objects/.+write|permission matrix" \
  buddyswitch scripts tests framework tools docs/spec
```

**Expected final residue:** historical Phase 1 docs may mention `env.task`; active code, active tests, active framework docs, active skills, and active launcher assets do not.

**Final acceptance criteria:**

- Every buddy receives shared manager skills through normal runtime skill materialization.
- Every buddy-callable env operation enters through `env.tool`.
- Active buddy and instance identity are runtime-injected.
- `prepare` has an explicit host lifecycle contract and advertises the unified env tool surface.
- Dev project write access and non-Dev project read-only access are verified.
- Cross-tool identity spoof attempts are rejected or ignored consistently.
- All env tools satisfy the minimum structured response contract.
- Task and artifact cross-buddy mutations are rejected by service code.
- PM owns track lifecycle mutation.
- Handoff remains the legal cross-buddy collaboration mechanism.
- Persist/run writes are atomic and service-owned.
- Browser evidence is env-tool-issued and scoped to active context/run.
- `prepare.runtime_context.env_tools` exposes compact tool hints without becoming a prompt manual.
- Old debug/manual scripts no longer define product behavior.
- Launcher-managed instances contain the final env tool surface.
- Full regression suite passes from `/Users/chen/Dev/buddyswitch/.worktrees/dev0210`.

**User confirmation:** Report full Phase 1-N verification and provide a final handoff prompt that can be used for follow-up cleanup or implementation review, not for another planned phase.
