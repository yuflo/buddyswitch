# Env Tool Layer Rebuild Residue Removal Implementation Plan

> **For agentic workers:** implement this plan task by task in the `dev2258` worktree. Start each behavior change with the named failing test, then make the smallest direct code change that passes it. Do not preserve old manager names through aliases, import shims, or dual paths.

**Goal:** rebuild the env tool layer into the single path `env.tool -> router -> registry-backed dispatch -> service`, while removing manager naming, duplicate action maps, manager-keyed runtime context, and manager-themed skill ids from active product surfaces.

**Architecture:** the runtime broker remains the only protocol entry and keeps active instance, active buddy, and runtime lock checks. `scripts/env/tools/router.py` remains the host-facing env.tool envelope validator. A new `scripts/env/tools/dispatch.py` binds registry-valid `(tool, action)` pairs to service handlers, and services keep business permission, state, mutation, and response ownership.

**Tech Stack:** Python stdlib, BuddySwitch runtime broker, `pytest`/`unittest`, TOML manifest, Codex-native `.agents/skills/<skill_id>/SKILL.md` materialization.

---

## Task Background Summary

The memo confirms the active external entry point is already unified through broker method `env.tool`. The remaining problem is architecture residue:

- active dispatch modules are named `scripts/env/tools/*_manager.py`;
- every manager module keeps its own `_ACTION_MAP`;
- every manager module contains `_router_contract_error`, so unknown action handling is duplicated outside the router;
- `scripts/env/tools/contracts.py` exposes `manager_name`;
- `prepare.runtime_context.env_tools` is keyed by `task_manager`, `track_manager`, `artifact_manager`, and the same pattern for other tools;
- shared skills and active docs still advertise manager wording;
- tests assert managers and `_ACTION_MAP` as product facts.

The rebuild must remove those surfaces directly. It must not replace Codex CLI native skill discovery. Runtime skills must still materialize into `.agents/skills/<skill_id>/SKILL.md` through `scripts/runtime_skills.py install`.

## Current Bottleneck

The bottleneck is not runtime breakage. It is duplicated product vocabulary and duplicated action authority. Maintainers currently have to understand both env tools and managers, and have to keep registry actions plus `_ACTION_MAP` entries aligned. That weakens the registry as the single public contract and lets stale manager wording leak into host-facing runtime context, docs, skills, and tests.

## Final Target State

- Active env operations enter only through broker method `env.tool`.
- Router owns all host-facing validation for `tool`, `action`, and object-shaped `args`.
- Registry in `scripts/env/tools/contracts.py` is the single public contract source for tool ids, action names, payload fields, operation semantics, permissions, authorities, preconditions, and return fields.
- Dispatch is a single module, `scripts/env/tools/dispatch.py`, that binds registry-valid tool/action pairs to service handlers.
- Services own business permissions, state checks, reads, writes, and response construction.
- `prepare.runtime_context.env_tools` is keyed by tool ids: `task`, `track`, `artifact`, `context`, `binding`, `handoff`, `run`, `evidence`.
- Shared skill ids are renamed from `task-manager`, `track-manager`, and `artifact-manager` to `task-tool`, `track-tool`, and `artifact-tool`, with no old aliases.
- Codex-native skill discovery remains unchanged: launcher/runtime materializes package directories under `.agents/skills/<skill_id>/SKILL.md`.
- Active AGENTS, skills, framework docs, contracts, CLI help, tests, and runtime feedback use env tool language.
- Historical specs that still discuss old manager architecture are explicitly marked superseded so they cannot be mistaken for current guidance.

## Non-Goal Scope

- Do not add compatibility wrappers or import shims for removed manager modules.
- Do not keep old and new skill ids side by side.
- Do not create a BuddySwitch-specific skill discovery layer.
- Do not add workflow engines, event buses, DSLs, automatic routing, handoff inboxes, or hidden route-selection behavior.
- Do not change service-level permissions, object schemas, task/track/artifact semantics, run commit semantics, or browser evidence semantics except to replace manager wording in feedback text.
- Do not change the broker protocol name, env client command shape, or Codex `.agents/skills` discovery mechanism.

## Memo And Code State Differences

- The memo names `task_manager`, `track_manager`, and `artifact_manager` as examples, but the current code exposes manager keys for all eight env tools: `task_manager`, `track_manager`, `artifact_manager`, `context_manager`, `binding_manager`, `handoff_manager`, `run_manager`, and `evidence_manager`.
- The memo calls out AGENTS, shared skills, and active docs. Current code also has manager wording in CLI help, service docstrings, run/evidence feedback hints, framework contracts, and tests.
- The memo makes skill renaming conditional. This plan chooses direct renaming to `task-tool`, `track-tool`, and `artifact-tool` because manager-themed skill ids are host-facing product surface.
- The current launcher workspace sync copies the whole `scripts/env` directory, so deleting manager modules and adding `dispatch.py` is enough for product workspaces; launcher tests still need to assert the new runtime surface files.
- `__pycache__` manager files exist in the local worktree but are not tracked by git and are not part of the active cleanup target.

## Local Assumptions

- `dev2258` is the implementation worktree and must remain isolated from `main`.
- Historical `docs/memo/*.md` files may contain old names as decision records.
- Existing dated `docs/spec/*.md` files that contain old names should be kept only if they receive a clear superseded banner.
- Test source may need to refer to removed tokens; use string construction such as `"task" + "_manager"` in residue tests so simple repository scans do not treat tests as active advertisements.
- The central dispatch handler table is a binding table, not the authority source for supported actions. Router validation must continue to derive supported actions only from the registry.

## Blocking Issues

None found. The memo and current code agree on the required direction, and the skill id rename is a local product-surface decision explicitly allowed by the memo.

## Behaviors To Preserve Or Rebuild

- Preserve broker method `env.tool` as the only active env operation entry.
- Preserve env CLI command shape: `python3 scripts/env/client.py <resource> <operation>`.
- Preserve envelope shape: `{"tool": "<tool-id>", "action": "<action>", "args": {}}`.
- Preserve runtime broker active instance, active buddy, active status, and runtime lock checks.
- Preserve task, track, artifact, context, binding, handoff, run, and evidence service behavior and response contracts.
- Preserve Codex-native skill discovery from `.agents/skills/<skill_id>/SKILL.md`.
- Rebuild runtime context so `prepare.runtime_context.env_tools` uses tool ids and no manager keys.
- Rebuild shared env tool skills under `task-tool`, `track-tool`, and `artifact-tool` only.

## External Interfaces And Runtime Contracts

- Broker protocol method: `env.tool`; legacy `env.task` remains rejected.
- Env client CLI: `python3 scripts/env/client.py task|track|artifact|context|binding|handoff|run|evidence <operation>`.
- Runtime context: `prepare.runtime_context.env_tools.<tool-id>` rows with `command`, `scope`, `broker_method`, `envelope`, `cli_resource`, `operations`, `payload_fields`, `feedback_source`, and `authoritative_fields`.
- Skill materialization: `scripts/runtime_skills.py install --manifest <path> --buddy <id> --workspace <path>` copies manifest-declared packages into `.agents/skills/<skill_id>/`.
- Manifest contract: `buddyswitch/manifest.toml` skill rows remain `id` plus repo-relative `path`, and buddy rows list skill ids directly.
- Launcher workspace contract: product workspaces receive the active runtime surface under `scripts/`, `buddyswitch/manifest.toml`, framework contracts, buddy AGENTS, and native `.agents/skills`.

## Impacted File Inventory

### Runtime Code

- Create: `scripts/env/tools/dispatch.py`
- Modify: `scripts/env/tools/router.py`
- Modify: `scripts/env/tools/contracts.py`
- Modify: `scripts/env/client.py`
- Modify: `scripts/env/services/artifacts.py`
- Modify: `scripts/env/services/evidence.py`
- Modify: `scripts/env/services/runs.py`
- Modify: `scripts/env/services/tasks.py`
- Modify: `scripts/env/services/tracks.py`
- Delete: `scripts/env/tools/task_manager.py`
- Delete: `scripts/env/tools/track_manager.py`
- Delete: `scripts/env/tools/artifact_manager.py`
- Delete: `scripts/env/tools/context_manager.py`
- Delete: `scripts/env/tools/binding_manager.py`
- Delete: `scripts/env/tools/handoff_manager.py`
- Delete: `scripts/env/tools/run_manager.py`
- Delete: `scripts/env/tools/evidence_manager.py`

### Manifest And Skills

- Modify: `buddyswitch/manifest.toml`
- Rename: `buddyswitch/skills/shared/task-manager/` to `buddyswitch/skills/shared/task-tool/`
- Rename: `buddyswitch/skills/shared/track-manager/` to `buddyswitch/skills/shared/track-tool/`
- Rename: `buddyswitch/skills/shared/artifact-manager/` to `buddyswitch/skills/shared/artifact-tool/`
- Modify: `buddyswitch/skills/shared/task-tool/SKILL.md`
- Modify: `buddyswitch/skills/shared/track-tool/SKILL.md`
- Modify: `buddyswitch/skills/shared/artifact-tool/SKILL.md`
- Keep: `buddyswitch/skills/shared/track-tool/assets/track-operation-template.md`

### Active Docs And Runtime Prompts

- Modify: `README.md`
- Modify: `framework/docs/architecture-overview.md`
- Modify: `framework/docs/turn-runtime-spec.md`
- Modify: `framework/docs/skill-runtime-shared-rules.md`
- Modify: `framework/docs/track-registry.md`
- Modify: `framework/contracts/market.md`
- Modify: `framework/contracts/pm.md`
- Modify: `framework/contracts/design.md`
- Modify: `framework/contracts/dev.md`
- Modify: `framework/contracts/test.md`
- Modify: `tools/launcher/assets/buddies/market/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/pm/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/design/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/dev/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/test/AGENTS.md`
- Modify historical specs under `docs/spec/*.md` that contain removed active guidance by adding a superseded banner at the top.

### Tests

- Modify: `tests/test_env_tool_router.py`
- Modify: `tests/test_prepare_runtime_context.py`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_env_manifest_v2.py`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_runtime_broker.py`
- Modify: `tests/test_turn_runtime.py`
- Modify: `tests/test_turn_integration.py`
- Modify: `tests/test_run_env_tool.py`
- Modify: `tests/test_evidence_env_tool.py`
- Modify: `tests/test_cleanup_system.py`
- Rename: `tests/test_task_manager_env_tool.py` to `tests/test_task_env_tool.py`
- Rename: `tests/test_track_manager_env_tool.py` to `tests/test_track_env_tool.py`
- Rename: `tests/test_artifact_manager_env_tool.py` to `tests/test_artifact_env_tool.py`
- Keep behavior coverage in `tests/test_context_binding_env_tool.py` and update docstrings or literals when they mention manager wording.

## Phase 1 - Lock The New Contract With Failing Tests

### Goal

Make the desired architecture executable before changing runtime code. The first test run should fail because manager modules, manager keys, and old skill ids still exist.

### File Scope

- `tests/test_env_tool_router.py`
- `tests/test_prepare_runtime_context.py`
- `tests/test_repo_consistency.py`
- `tests/test_runtime_skills.py`
- `tests/test_env_manifest_v2.py`
- `tests/test_buddyswitch_launcher.py`
- renamed env tool behavior test paths

### Concrete Changes

1. In `tests/test_env_tool_router.py`, replace `test_manager_handler_actions_match_registry_actions` with `test_dispatch_handler_coverage_matches_registry_actions`.
   - Import `env.tools.dispatch`.
   - Assert `dispatch.dispatch_handler_actions()` returns exactly the registry action names for every registry tool.
   - Assert `env.tools.router._TOOL_ACTIONS` equals registry actions.
   - Assert `env.tools.router._TOOL_DISPATCHERS` no longer exists or is no longer a per-tool manager dispatcher map.
   - Assert malformed or unknown tool/action rejection returns `E_ENV_TOOL` or `E_ENV_TOOL_PAYLOAD`, never `E_ENV_TOOL_ROUTER`.

2. Add a router residue test in `tests/test_env_tool_router.py`.
   - Assert importing `env.tools.dispatch` succeeds.
   - Assert importing removed manager modules fails for each old module name built from parts: `env.tools.` + `task` + `_manager`, and the same for all eight tools.
   - Assert active files under `scripts/env/tools` do not contain `_ACTION_MAP`, `_router_contract_error`, or `manager_name`.

3. In `tests/test_prepare_runtime_context.py`, change expected `env_tools` keys to registry tool ids.
   - Expected keys: `artifact`, `binding`, `context`, `evidence`, `handoff`, `run`, `task`, `track`.
   - Keep the existing operations and payload field assertions.
   - Replace `env_tools["task_manager"]` with `env_tools["task"]`, and the same pattern for all tools.
   - Assert no key ends with `_manager`.

4. In `tests/test_runtime_skills.py` and `tests/test_env_manifest_v2.py`, replace repo manifest assertions.
   - Expected shared skill ids: `task-tool`, `track-tool`, `artifact-tool`.
   - Expected paths: `buddyswitch/skills/shared/task-tool`, `buddyswitch/skills/shared/track-tool`, `buddyswitch/skills/shared/artifact-tool`.
   - Assert old ids are absent from repo manifest and buddy skill lists.
   - Keep tests that prove runtime materialization copies opaque packages into `.agents/skills/<skill_id>/SKILL.md`.

5. In `tests/test_buddyswitch_launcher.py`, update runtime skill materialization assertions.
   - Assert `task-tool`, `track-tool`, and `artifact-tool` are installed.
   - Assert `task-manager`, `track-manager`, and `artifact-manager` are absent.
   - Update runtime surface copy assertions to include `scripts/env/tools/dispatch.py` and exclude deleted manager files.

6. In `tests/test_repo_consistency.py`, replace manager-specific tests with env tool residue tests.
   - Rename manifest test to `test_manifest_declares_shared_env_tool_skills_for_every_buddy`.
   - Add an active-surface scan over `README.md`, `framework/docs`, `framework/contracts`, `tools/launcher/assets/buddies`, active manifest skill directories, `scripts`, and `tests`.
   - Forbidden active literals: `manager actions`, `Env manager`, `_ACTION_MAP`, `_router_contract_error`, `manager_name`, `task_manager`, `track_manager`, `artifact_manager`, `context_manager`, `binding_manager`, `handoff_manager`, `run_manager`, `evidence_manager`, `task-manager`, `track-manager`, `artifact-manager`.
   - For removed old product concepts, keep or expand existing checks for `env.task`, `issue_browser_evidence`, `handoff_inbox`, `automatic router`, `auto-routing`, `workflow engine`, `event bus`, and `DSL`.
   - Exclude `docs/memo` and this pair of planning documents from active-surface scans.
   - For `docs/spec/*.md`, require a superseded banner when a file contains removed manager terms.

7. Rename behavior test files with `git mv`.
   - `tests/test_task_manager_env_tool.py` to `tests/test_task_env_tool.py`
   - `tests/test_track_manager_env_tool.py` to `tests/test_track_env_tool.py`
   - `tests/test_artifact_manager_env_tool.py` to `tests/test_artifact_env_tool.py`
   - Update imports and command references in docs/tests that point to the old filenames.

### Expected Code/Test State After Phase

The focused tests fail for the current reasons: missing `dispatch.py`, existing manager modules, manager-keyed runtime context, old skill ids, and active docs containing manager wording.

### Verification Commands

```bash
python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py tests/test_prepare_runtime_context.py tests/test_runtime_skills.py tests/test_env_manifest_v2.py tests/test_repo_consistency.py -q
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_execution_worktree_uses_runtime_workspace_agents_header tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_refreshes_runtime_skills_and_removes_stale_skill -q
```

## Phase 2 - Replace Manager Dispatch With Registry-Backed Dispatch

### Goal

Delete manager dispatch modules and make router call a single dispatch module that binds registry-valid tool/action pairs to service handlers.

### File Scope

- `scripts/env/tools/dispatch.py`
- `scripts/env/tools/router.py`
- `scripts/env/tools/contracts.py`
- all deleted `scripts/env/tools/*_manager.py` files

### Concrete Changes

1. Create `scripts/env/tools/dispatch.py`.
   - Import all service modules directly:
     - `env.services.tasks`
     - `env.services.tracks`
     - `env.services.artifacts`
     - `env.services.context`
     - `env.services.bindings`
     - `env.services.handoffs`
     - `env.services.runs`
     - `env.services.evidence`
   - Define one central handler binding table named `HANDLERS_BY_TOOL`.
   - Bind the current actions to the same service functions:
     - `task.create` -> `create_task_for_active_buddy`
     - `task.list` -> `list_tasks_for_active_buddy`
     - `task.get` -> `get_task_for_active_buddy`
     - `task.get_current` -> `get_current_task`
     - `task.set_current` -> `set_current_task`
     - `task.update` -> `update_task_for_active_buddy`
     - `task.archive` -> `archive_task_for_active_buddy`
     - `track.list` -> `list_tracks_for_active_buddy`
     - `track.get` -> `get_track_for_active_buddy`
     - `track.get_current` -> `get_current_track`
     - `track.create` -> `create_track_for_pm`
     - `track.update` -> `update_track_for_pm`
     - `track.advance` -> `advance_track_for_pm`
     - `track.archive` -> `archive_track_for_pm`
     - `track.attach_task` -> `attach_task_to_track`
     - `track.detach_task` -> `detach_task_from_track`
     - `artifact.list` -> `list_artifacts_for_current_task`
     - `artifact.get` -> `get_artifact_for_active_buddy`
     - `artifact.get_current` -> `get_current_artifacts_for_active_task`
     - `artifact.validate_payload` -> `validate_artifact_payload`
     - `artifact.create_revision` -> `create_artifact_revision`
     - `artifact.update_metadata` -> `update_artifact_metadata`
     - `context.get` -> `get_context`
     - `context.summarize` -> `summarize_context`
     - `context.list_sources` -> `list_sources`
     - `binding.get` -> `get_binding`
     - `binding.set_task` -> `set_task_binding`
     - `binding.set_track` -> `set_track_binding`
     - `binding.clear` -> `clear_binding`
     - `handoff.validate` -> `validate_handoff`
     - `run.commit` -> `commit_for_active_instance`
     - `run.get_receipt` -> `get_receipt_for_active_instance`
     - `run.get_raw` -> `get_raw_for_active_instance`
     - `run.validate_result` -> `validate_result_for_active_instance`
     - `evidence.issue_browser` -> `issue_browser_for_active_instance`
     - `evidence.approve_downgrade` -> `approve_downgrade_for_active_instance`
   - Add `dispatch_handler_actions() -> dict[str, set[str]]` for tests.
   - Add `dispatch_registered_env_tool(...) -> dict[str, Any]` with parameters `tool`, `action`, `args`, `active_buddy`, `instance_id`, `instance_json`, `instance_payload`, `manifest`, and optional `manifest_path`.
   - Build the correct service context for each tool family:
     - task, track, artifact, context, binding, handoff include active buddy, instance id, instance json, instance payload, and manifest;
     - run and evidence also include `manifest_path`.
   - Keep current run and evidence exception normalization in dispatch so `RuntimeFeedbackError`, `ValueError`, `OSError`, and `json.JSONDecodeError` still become structured runtime feedback.
   - Do not return unknown action feedback from dispatch. Unknown action feedback is router-owned.

2. Modify `scripts/env/tools/router.py`.
   - Replace all manager imports with `from env.tools.dispatch import dispatch_registered_env_tool`.
   - Keep `_TOOL_ACTIONS` derived only from `tool_contracts.supported_actions(tool)`.
   - Replace manager hint construction with direct tool id hints:
     - `prepare.runtime_context.env_tools.task`
     - `prepare.runtime_context.env_tools.track`
     - and the same for all tools.
   - Call `dispatch_registered_env_tool(tool=tool, action=action, args=args, ...)`.
   - Keep response enrichment `response.setdefault("tool", tool)`.

3. Modify `scripts/env/tools/contracts.py`.
   - Remove every `manager_name` field from `TOOL_REGISTRY`.
   - Delete `manager_name_for_tool`.
   - Make `env_tools_description()` key rows by `tool`.
   - Keep `cli_resource`, `command`, `scope`, `actions`, `operation_semantics()`, `supported_actions()`, and `supported_tools()` behavior.

4. Delete manager dispatch modules.
   - Remove all eight `scripts/env/tools/*_manager.py` files.
   - Do not add replacement files with old module names.
   - Do not keep import redirects in `scripts/env/tools/__init__.py`.

### Expected Code State After Phase

`scripts/env/tools` contains router, contracts, dispatch, responses, and package init. The only action binding table is central dispatch binding. Router-supported tools and actions are registry-derived, and unknown tool/action responses mention tool ids instead of manager keys.

### Verification Commands

```bash
python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py -q
python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_context_binding_env_tool.py tests/test_run_env_tool.py tests/test_evidence_env_tool.py -q
python3 -m compileall -q scripts/env scripts/runtime_kernel scripts/turn_runtime.py
```

## Phase 3 - Rebuild Runtime Context And Skill-Facing Text Around Tool Ids

### Goal

Make host-visible runtime context, CLI help, and service feedback describe env tools and tool-id keys.

### File Scope

- `scripts/env/tools/contracts.py`
- `scripts/env/client.py`
- `scripts/env/services/artifacts.py`
- `scripts/env/services/evidence.py`
- `scripts/env/services/runs.py`
- `scripts/env/services/tasks.py`
- `scripts/env/services/tracks.py`
- `tests/test_prepare_runtime_context.py`
- `tests/test_env_tool_response_contract.py`

### Concrete Changes

1. In `contracts.env_tools_description()`, return:
   - `env_tools["task"]`
   - `env_tools["track"]`
   - `env_tools["artifact"]`
   - `env_tools["context"]`
   - `env_tools["binding"]`
   - `env_tools["handoff"]`
   - `env_tools["run"]`
   - `env_tools["evidence"]`

2. Preserve each row shape:
   - `command`
   - `scope`
   - `broker_method`
   - `envelope`
   - `cli_resource`
   - `operations`
   - `payload_fields`
   - `feedback_source`
   - `authoritative_fields`

3. In `scripts/env/client.py`, replace help text:
   - `Task manager env operations` -> `Task env tool operations`
   - `Track manager env operations` -> `Track env tool operations`
   - `Artifact manager env operations` -> `Artifact env tool operations`
   - Use matching language for context, binding, handoff, run, and evidence where needed.

4. In service docstrings and error hints:
   - Replace `task manager service` with `task env tool service`.
   - Replace `track manager service` with `track env tool service`.
   - Replace `artifact manager service` with `artifact env tool service`.
   - Replace `prepare.runtime_context.env_tools.run_manager` with `prepare.runtime_context.env_tools.run`.
   - Replace `prepare.runtime_context.env_tools.evidence_manager` with `prepare.runtime_context.env_tools.evidence`.
   - Replace `artifact-manager reads` with `artifact tool reads`.

5. Keep response codes and payload semantics stable.
   - Existing service errors such as `E_TASK_PAYLOAD`, `E_RUNTIME_PERSIST`, and `E_RUNTIME_BROKER` should not change unless the only change is removing manager wording in the message or next action text.

### Expected Code State After Phase

`prepare.runtime_context.env_tools` is tool-id keyed. CLI help and service feedback no longer teach manager keys. Existing main-path task, track, artifact, context, binding, handoff, run, and evidence behavior remains unchanged.

### Verification Commands

```bash
python3 -m pytest -p no:cacheprovider tests/test_prepare_runtime_context.py tests/test_env_tool_response_contract.py -q
python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_context_binding_env_tool.py tests/test_run_env_tool.py tests/test_evidence_env_tool.py -q
```

## Phase 4 - Rename Shared Manager Skills To Env Tool Skills

### Goal

Remove manager-themed skill ids from the host skill surface while preserving Codex-native skill materialization.

### File Scope

- `buddyswitch/manifest.toml`
- `buddyswitch/skills/shared/task-tool/SKILL.md`
- `buddyswitch/skills/shared/track-tool/SKILL.md`
- `buddyswitch/skills/shared/artifact-tool/SKILL.md`
- `scripts/runtime_skills.py` tests only; runtime implementation should not need mechanism changes
- launcher tests that assert materialized skill directories

### Concrete Changes

1. Rename skill directories with git-aware moves:
   - `buddyswitch/skills/shared/task-manager/` -> `buddyswitch/skills/shared/task-tool/`
   - `buddyswitch/skills/shared/track-manager/` -> `buddyswitch/skills/shared/track-tool/`
   - `buddyswitch/skills/shared/artifact-manager/` -> `buddyswitch/skills/shared/artifact-tool/`

2. Update `buddyswitch/manifest.toml`.
   - Replace skill rows:
     - `id = "task-tool"`, `path = "buddyswitch/skills/shared/task-tool"`
     - `id = "track-tool"`, `path = "buddyswitch/skills/shared/track-tool"`
     - `id = "artifact-tool"`, `path = "buddyswitch/skills/shared/artifact-tool"`
   - Replace every buddy skill list entry with the new ids.
   - Confirm old skill ids are absent.

3. Update shared `SKILL.md` frontmatter and headings.
   - `name: task-tool`, heading `# task-tool`
   - `name: track-tool`, heading `# track-tool`
   - `name: artifact-tool`, heading `# artifact-tool`
   - Replace "Runtime/tool feedback asks for a track-manager command" with "Runtime/tool feedback asks for a track env tool command."
   - Replace `prepare.runtime_context.env_tools.task_manager` with `prepare.runtime_context.env_tools.task`.
   - Keep command surfaces unchanged: `python3 scripts/env/client.py task ...`, `track ...`, and `artifact ...`.

4. Keep `scripts/runtime_skills.py` unchanged unless tests expose hardcoded old ids.
   - The correct runtime mechanism is still manifest-driven copy into `.agents/skills/<skill_id>/`.
   - Do not add id translation or fallback aliases.

5. Update tests and fixtures.
   - Replace old skill ids in test manifests, runtime skill tests, launcher tests, turn runtime fixtures, and cleanup fixtures.
   - For tests proving arbitrary community skill ids, use non-manager examples such as `track-tool` or `coordination-tool`.

### Expected Code State After Phase

Runtime skill installation prints and materializes new ids only. Existing Codex skill discovery remains native because package content still lands under `.agents/skills/<skill_id>/SKILL.md`.

### Verification Commands

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py tests/test_env_manifest_v2.py -q
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_execution_worktree_uses_runtime_workspace_agents_header tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_refreshes_runtime_skills_and_removes_stale_skill -q
```

## Phase 5 - Clean Active Docs, AGENTS, Specs, And Residue Guards

### Goal

Remove manager vocabulary and forbidden old concepts from active guidance, while marking historical specs that retain old details as superseded.

### File Scope

- `README.md`
- `framework/docs/architecture-overview.md`
- `framework/docs/turn-runtime-spec.md`
- `framework/docs/skill-runtime-shared-rules.md`
- `framework/docs/track-registry.md`
- `framework/contracts/*.md`
- `tools/launcher/assets/buddies/*/AGENTS.md`
- `docs/spec/*.md`
- `tests/test_repo_consistency.py`

### Concrete Changes

1. Replace active wording:
   - `Env manager actions` -> `Env tool operations`
   - `Env manager operations` -> `Env tool operations`
   - `task-manager`, `track-manager`, `artifact-manager` -> `task-tool`, `track-tool`, `artifact-tool`
   - `context-manager`, `binding-manager`, `handoff-manager`, `run-manager`, `evidence-manager` -> `context`, `binding`, `handoff`, `run`, `evidence` env tools
   - `scripts/env/tools/track_manager.py` -> `scripts/env/tools/dispatch.py` or `scripts/env/tools/router.py`, depending on whether the doc means binding or envelope validation.

2. Keep active docs accurate:
   - Runtime command examples remain `python3 scripts/env/client.py <resource> <operation>`.
   - Broker method remains `env.tool`.
   - Skill discovery remains `.agents/skills/<skill_id>/SKILL.md`.
   - Runtime context examples use `prepare.runtime_context.env_tools.<tool_id>`.

3. Mark stale dated specs.
   - For each `docs/spec/*.md` containing removed manager names, add a top banner:
     - `> Superseded on 2026-05-12 by the env tool layer rebuild residue removal work. This file is historical context, not active implementation guidance.`
   - Do not rewrite historical design details inside those specs unless a line is still referenced from active docs.

4. Expand repo consistency tests.
   - Active docs, launcher AGENTS, manifest-declared skill package files, scripts, and tests should not contain active manager vocabulary.
   - Historical specs are allowed to contain removed terms only when the superseded banner is present.
   - Residue checks should fail on reintroduced `*_manager.py`, `_ACTION_MAP`, `_router_contract_error`, `manager_name`, old skill ids, manager runtime context keys, and forbidden product concepts listed in the memo.

### Expected Code State After Phase

Active guidance teaches one vocabulary: env tools, tool ids, registry, router, dispatch, services, and Codex-native skill materialization. Old specs remain available only as marked history.

### Verification Commands

```bash
python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py tests/test_runtime_agents.py -q
rg -n "Env manager|manager actions|manager operations|_ACTION_MAP|_router_contract_error|manager_name|task_manager|track_manager|artifact_manager|context_manager|binding_manager|handoff_manager|run_manager|evidence_manager|task-manager|track-manager|artifact-manager" README.md framework/docs framework/contracts scripts tools/launcher/assets buddyswitch/manifest.toml buddyswitch/skills tests
```

Expected `rg` result: no matches. If tests need to assert removed tokens, construct those strings in pieces so the scan still protects active vocabulary.

## Phase 6 - Product-Mode Smoke And Full Verification

### Goal

Prove the rebuild still works in product mode: launcher starts an instance, prepares context, env tool CLI uses `env.tool`, and native skill materialization installs only new ids.

### File Scope

- no new implementation scope unless a verification failure identifies a root cause

### Concrete Checks

1. Start a product instance in the implementation worktree:

```bash
./buddyswitch-codex instance start --buddy pm -- debug prompt-input "Env tool residue removal smoke"
```

2. Inspect the created workspace:
   - `.agents/skills/write-prd/SKILL.md` exists.
   - `.agents/skills/task-tool/SKILL.md` exists.
   - `.agents/skills/track-tool/SKILL.md` exists.
   - `.agents/skills/artifact-tool/SKILL.md` exists.
   - old manager skill directories are absent.

3. Run prepare through the runtime broker from inside the instance:

```bash
python3 scripts/turn_runtime.py prepare "Check env tool runtime context"
```

4. Confirm prepare output:
   - `runtime_context.env_tools.task` exists.
   - no `runtime_context.env_tools.task_manager` key exists.
   - `runtime_context.env_tools.track.broker_method` is `env.tool`.

5. Exercise an env tool CLI command from inside the instance:

```bash
python3 scripts/env/client.py task list
```

6. Confirm CLI output:
   - JSON response has `ok` boolean.
   - successful response has `"tool": "task"`.
   - no response text references manager hints.

### Final Verification Commands

```bash
python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py tests/test_prepare_runtime_context.py tests/test_runtime_skills.py tests/test_env_manifest_v2.py tests/test_repo_consistency.py -q
python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_context_binding_env_tool.py tests/test_run_env_tool.py tests/test_evidence_env_tool.py tests/test_env_tool_response_contract.py -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py tests/test_env_layer_boundaries.py tests/test_env_layer_end_to_end.py -q
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_execution_worktree_uses_runtime_workspace_agents_header tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_refreshes_runtime_skills_and_removes_stale_skill -q
python3 -m compileall -q scripts tools
python3 -m pytest -p no:cacheprovider -q
```

## Explicit Old Logic Deletion List

- Delete `scripts/env/tools/task_manager.py`.
- Delete `scripts/env/tools/track_manager.py`.
- Delete `scripts/env/tools/artifact_manager.py`.
- Delete `scripts/env/tools/context_manager.py`.
- Delete `scripts/env/tools/binding_manager.py`.
- Delete `scripts/env/tools/handoff_manager.py`.
- Delete `scripts/env/tools/run_manager.py`.
- Delete `scripts/env/tools/evidence_manager.py`.
- Delete every per-tool `_ACTION_MAP`.
- Delete every manager-local `_router_contract_error`.
- Delete `manager_name` fields from `TOOL_REGISTRY`.
- Delete `manager_name_for_tool()`.
- Delete manager-keyed `prepare.runtime_context.env_tools` rows.
- Delete old shared skill package ids and directories: `task-manager`, `track-manager`, `artifact-manager`.
- Delete tests that import manager modules or assert `_ACTION_MAP` as architecture.
- Delete active doc and prompt wording that advertises manager actions or manager operations.

## Tests To Add Or Modify

- Add dispatch coverage test in `tests/test_env_tool_router.py`.
- Add active env tool residue test in `tests/test_repo_consistency.py`.
- Modify runtime context tests in `tests/test_prepare_runtime_context.py` to use tool ids.
- Modify runtime skill tests in `tests/test_runtime_skills.py` to expect `task-tool`, `track-tool`, and `artifact-tool`.
- Modify manifest tests in `tests/test_env_manifest_v2.py` to reject old ids and accept new ids.
- Modify launcher tests in `tests/test_buddyswitch_launcher.py` to assert new materialized skill ids and new runtime surface files.
- Rename and keep existing task, track, and artifact behavior tests under env tool names.
- Modify run and evidence tests to assert feedback hints use `env_tools.run` and `env_tools.evidence`.
- Modify repo consistency tests to require superseded banners for old dated specs containing removed terms.

## Final Acceptance Criteria

- Active env operations still enter through `env.tool`.
- Router is the single host-facing unknown tool/action boundary.
- `scripts/env/tools/dispatch.py` exists and dispatch handler coverage matches the registry.
- No active env tool `*_manager.py` dispatch modules exist.
- No `_ACTION_MAP` allowlists exist.
- No manager-local `_router_contract_error` exists.
- `contracts.py` no longer exposes `manager_name`.
- `prepare.runtime_context.env_tools` is keyed by tool id.
- Codex CLI skill discovery remains native through `.agents/skills/<skill_id>/SKILL.md`.
- `task-tool`, `track-tool`, and `artifact-tool` are the only shared env tool skill ids; old manager skill ids are absent.
- Active AGENTS, skills, framework docs, contracts, CLI help, tests, and feedback text use env tool language.
- Historical specs with old wording are marked superseded.
- Focused tests, full pytest, compileall, residue checks, and product-mode smoke pass.

## Risks And Mitigations

- **Risk:** Central handler binding silently drifts from registry actions.  
  **Mitigation:** `test_dispatch_handler_coverage_matches_registry_actions` compares registry actions to dispatch bindings for every tool.

- **Risk:** Removing manager modules breaks runtime workspace sync.  
  **Mitigation:** workspace sync copies the whole `scripts/env` tree; launcher tests assert `dispatch.py` is present and old manager files are absent.

- **Risk:** Skill id rename breaks Codex discovery.  
  **Mitigation:** keep `scripts/runtime_skills.py` manifest-driven and assert `.agents/skills/<new-id>/SKILL.md` exists for start and open flows.

- **Risk:** Tests preserve old literals and weaken residue scans.  
  **Mitigation:** construct removed strings from parts inside tests and run a literal `rg` scan over active paths.

- **Risk:** Historical plans continue to guide future implementation.  
  **Mitigation:** add superseded banners to dated specs that contain old manager architecture.

- **Risk:** Run and evidence exception wrappers lose structured feedback during dispatch consolidation.  
  **Mitigation:** move the existing exception normalization into `dispatch.py` and keep response contract tests focused on machine-readable fields.

## Regression Checklist

- [ ] `env.tool` valid task list succeeds through runtime broker.
- [ ] malformed env.tool payloads reject without state mutation.
- [ ] unknown tool and unknown action reject at router boundary with `E_ENV_TOOL`.
- [ ] dispatch handler coverage equals registry coverage.
- [ ] task CRUD, set current, and get current behavior remains unchanged.
- [ ] track lifecycle, attach, detach, discovery, and context summaries remain unchanged.
- [ ] artifact list, get, current, validate, create revision, and update metadata behavior remains unchanged.
- [ ] binding, context, handoff, run, and evidence env tool tests remain green.
- [ ] runtime context exposes only tool-id keys.
- [ ] manifest references only new shared env tool skill ids.
- [ ] launcher start and open materialize only new shared env tool skill ids.
- [ ] active docs and AGENTS use env tool language.
- [ ] old manager modules, action maps, manager registry fields, and manager runtime keys are absent.
- [ ] full test suite and compileall pass.
