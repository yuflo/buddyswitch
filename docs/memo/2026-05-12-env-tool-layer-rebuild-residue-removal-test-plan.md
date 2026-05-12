# Env Tool Layer Rebuild Residue Removal Test Plan

## Scope

This plan verifies the full rebuild described in `docs/memo/2026-05-12-env-tool-layer-rebuild-residue-removal-memo.md`. Tests are designed from observable behavior, runtime contracts, and failure modes. They must not assert private call order or mock-only behavior unless the behavior is itself a stable product contract.

## Functional Requirements And Behavior Contracts

- **FR1 - Unified broker entry:** active env operations enter through broker method `env.tool`.
- **FR2 - Router boundary:** router validates `tool`, `action`, and object-shaped `args`, and is the single host-facing unknown tool/action boundary.
- **FR3 - Registry authority:** registry is the single public source for supported tool ids, actions, payload field hints, operation semantics, permissions, authorities, preconditions, and return fields.
- **FR4 - Dispatch binding:** dispatch binds registry-valid `(tool, action)` pairs to service handlers and has complete coverage for every registry action.
- **FR5 - No manager residue in runtime code:** active env tool manager modules, per-tool `_ACTION_MAP`, manager-local unknown-action boundaries, and `manager_name` registry fields are removed.
- **FR6 - Runtime context surface:** `prepare.runtime_context.env_tools` is keyed by tool id: `task`, `track`, `artifact`, `context`, `binding`, `handoff`, `run`, `evidence`.
- **FR7 - Service behavior preserved:** task, track, artifact, context, binding, handoff, run, and evidence service semantics remain unchanged.
- **FR8 - CLI surface preserved:** `python3 scripts/env/client.py <resource> <operation>` still builds `{"tool": ..., "action": ..., "args": ...}` and calls broker method `env.tool`.
- **FR9 - Native skill discovery preserved:** runtime skills materialize into `.agents/skills/<skill_id>/SKILL.md`; Codex CLI discovery is not replaced or wrapped.
- **FR10 - Skill ids renamed directly:** manager-themed shared skill ids are replaced by `task-tool`, `track-tool`, and `artifact-tool`, with no old aliases.
- **FR11 - Active guidance cleanup:** active AGENTS, shared skills, framework docs, contracts, CLI help, feedback hints, and tests use env tool language rather than manager language.
- **FR12 - Historical guidance marked:** historical specs that retain removed manager architecture are clearly marked superseded.
- **FR13 - Failure safety:** malformed payloads, missing broker socket, missing skill config, unsafe runtime workspace, and rejected service operations fail closed without state mutation.
- **FR14 - Product-mode proof:** a launcher-created instance can prepare context, use env tool CLI, and expose native `.agents/skills` packages after the rebuild.

## Must Automate

- Router validation and unknown tool/action rejection.
- Registry and dispatch coverage equality.
- Absence of active manager modules, `_ACTION_MAP`, `_router_contract_error`, `manager_name`, manager runtime keys, and old skill ids.
- Runtime context tool-id keys and payload hints.
- Runtime skill materialization under only new ids.
- Main-path task, track, artifact, context, binding, handoff, run, and evidence behavior.
- Launcher start/open skill materialization.
- Active docs, AGENTS, shared skills, and framework contracts residue scan.

## Manual Supplemental Checks

- Product-mode smoke with `./buddyswitch-codex instance start --buddy pm`.
- Inspect one generated runtime workspace to confirm `.agents/skills/<skill_id>/SKILL.md` layout is native and no manager skill directory exists.
- Run one env CLI command from inside the instance and inspect the JSON output for tool-id hints.

## Not Recommended To Test

- Internal function call order between router and dispatch.
- Mock-only assertions that a specific service function was called when the same behavior is already proven by state and response.
- Private local variable names inside `dispatch.py`, except stable residue tokens explicitly banned by the memo.
- Full text equality of help output or docs when targeted substring checks prove the contract.
- `__pycache__` contents, because they are generated and not tracked.

## Automated Test Cases

### TC01 - Router routes a valid task env tool request

- **Covers:** FR1, FR2, FR7
- **Preconditions:** runtime workspace has active dev instance and one dev task plus one PM task.
- **Input or operation:** dispatch broker payload `{"tool":"task","action":"list","args":{}}` through `env.tools.router.dispatch_env_tool_request`.
- **Expected result:** response has `ok=true`, `tool="task"`, `action="task.list"`, includes the dev task, excludes the PM task, and does not mutate instance or task state.
- **Layer:** integration
- **Recommended test file path:** `tests/test_env_tool_router.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py::EnvToolRouterTests::test_routes_task_list_through_env_tool_contract -q`

### TC02 - Router rejects malformed envelope without mutation

- **Covers:** FR2, FR13
- **Preconditions:** runtime workspace has an active dev instance with a current task.
- **Input or operation:** dispatch cases for missing tool, blank tool, unknown tool, missing action, blank action, unknown action, and non-object args.
- **Expected result:** rejected payloads return `ok=false`; error code is `E_ENV_TOOL` or `E_ENV_TOOL_PAYLOAD`; `permission_boundary` is `env.tool` or `request-payload`; task files and instance JSON remain byte-equivalent to the pre-call snapshot.
- **Layer:** integration
- **Recommended test file path:** `tests/test_env_tool_router.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py::EnvToolRouterTests::test_rejects_malformed_envelope_without_state_mutation -q`

### TC03 - Unknown action is router-owned and not dispatch-owned

- **Covers:** FR2, FR5
- **Preconditions:** active dev instance exists.
- **Input or operation:** dispatch `{"tool":"track","action":"merge","args":{}}`.
- **Expected result:** response has `ok=false`, error code `E_ENV_TOOL`, `permission_boundary="env.tool"`, no `E_ENV_TOOL_ROUTER`, no `env.tool.router_contract`, and no manager hint in `allowed_next_actions`.
- **Layer:** integration
- **Recommended test file path:** `tests/test_env_tool_router.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py::EnvToolRouterTests::test_unknown_action_is_rejected_by_router_without_manager_boundary -q`

### TC04 - Dispatch handler coverage equals registry action coverage

- **Covers:** FR3, FR4
- **Preconditions:** `env.tools.contracts` and `env.tools.dispatch` import successfully.
- **Input or operation:** compare registry action names for every tool with `dispatch.dispatch_handler_actions()`.
- **Expected result:** every registry tool has a dispatch binding set and each set equals the registry action names exactly.
- **Layer:** unit
- **Recommended test file path:** `tests/test_env_tool_router.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py::EnvToolRouterTests::test_dispatch_handler_coverage_matches_registry_actions -q`

### TC05 - Removed manager modules cannot be imported

- **Covers:** FR5
- **Preconditions:** implementation has deleted old manager files.
- **Input or operation:** attempt to import old module names for task, track, artifact, context, binding, handoff, run, and evidence using string construction for the removed suffix.
- **Expected result:** each import raises `ModuleNotFoundError`; `scripts/env/tools` contains `dispatch.py` and does not contain active `*_manager.py` files.
- **Layer:** unit
- **Recommended test file path:** `tests/test_env_tool_router.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py::EnvToolRouterTests::test_removed_manager_modules_are_not_importable -q`

### TC06 - Active env tool code has no action map or manager registry residue

- **Covers:** FR5, FR11
- **Preconditions:** repository checkout after implementation.
- **Input or operation:** scan `scripts/env/tools`, `scripts/env/services`, and runtime tests for banned active literals.
- **Expected result:** no active file contains `_ACTION_MAP`, `_router_contract_error`, `manager_name`, or manager runtime key literals.
- **Layer:** unit
- **Recommended test file path:** `tests/test_repo_consistency.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_active_env_tool_layer_has_no_manager_dispatch_residue -q`

### TC07 - Runtime context uses tool id keys

- **Covers:** FR3, FR6
- **Preconditions:** `turn_runtime.prepare` can build context for market and PM.
- **Input or operation:** prepare runtime context for one buddy and inspect `runtime_context.env_tools`.
- **Expected result:** keys equal `{"artifact","binding","context","evidence","handoff","run","task","track"}`; no key ends with `_manager`; each row has `broker_method="env.tool"` and envelope keys `tool`, `action`, `args`.
- **Layer:** integration
- **Recommended test file path:** `tests/test_prepare_runtime_context.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_prepare_exposes_env_tool_hints -q`

### TC08 - Runtime context operations and semantics remain registry-derived

- **Covers:** FR3, FR6, FR7
- **Preconditions:** registry contains all eight env tools and operation semantics.
- **Input or operation:** prepare runtime context and compare each `env_tools[tool]["operations"]` with registry actions; inspect `operation_semantics`.
- **Expected result:** operations match registry action names; semantic rows exist for every `tool.action`; selected values such as `track.list.mutates="none"` and `handoff.validate.kind="validate"` remain stable.
- **Layer:** integration
- **Recommended test file path:** `tests/test_prepare_runtime_context.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_prepare_env_tools_are_registry_derived_and_include_operation_semantics -q`

### TC09 - Env client builds env.tool envelopes for CLI commands

- **Covers:** FR1, FR8
- **Preconditions:** live test broker or patched broker client returns structured JSON.
- **Input or operation:** run CLI commands such as `task list`, `track get-current`, and `artifact get-current`.
- **Expected result:** command exits 0 for structured broker responses; outgoing broker method is `env.tool`; payload contains normalized action names such as `get_current`.
- **Layer:** CLI
- **Recommended test file path:** `tests/test_task_env_tool.py`, `tests/test_track_env_tool.py`, `tests/test_artifact_env_tool.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py -q`

### TC10 - Missing runtime broker socket fails closed for env client

- **Covers:** FR8, FR13
- **Preconditions:** `BUDDYSWITCH_RUNTIME_BROKER_SOCKET` is unset.
- **Input or operation:** run `python3 scripts/env/client.py task list`.
- **Expected result:** command prints JSON with `ok=false`, error code `E_RUNTIME_BROKER_UNAVAILABLE`, and broker unavailable feedback; process exits 0 because structured runtime feedback was produced.
- **Layer:** CLI
- **Recommended test file path:** `tests/test_task_env_tool.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py::TaskEnvToolTests::test_cli_prints_structured_ok_false_from_live_broker_and_exits_zero -q`

### TC11 - Runtime broker keeps active identity checks for env.tool

- **Covers:** FR1, FR13
- **Preconditions:** active dev instance JSON exists.
- **Input or operation:** call `runtime_kernel.broker.dispatch_runtime_request` with valid env.tool request, wrong instance id, wrong buddy, and inactive instance.
- **Expected result:** valid request succeeds; wrong instance rejects with boundary `active-instance`; wrong buddy rejects with boundary `active-buddy`; inactive instance rejects with boundary `active-instance-status`.
- **Layer:** integration
- **Recommended test file path:** `tests/test_runtime_broker.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerTests::test_env_tool_supports_active_instance_and_identity_checks -q`

### TC12 - Legacy env.task broker method stays rejected

- **Covers:** FR1, FR5, FR13
- **Preconditions:** active dev instance JSON exists.
- **Input or operation:** call runtime broker with method assembled as `"env" + "." + "task"`.
- **Expected result:** response has `ok=false`, broker-protocol boundary, and supported methods list contains `prepare`, `persist`, and `env.tool` only.
- **Layer:** integration
- **Recommended test file path:** `tests/test_runtime_broker.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerTests::test_legacy_env_task_method_is_rejected -q`

### TC13 - Task env tool CRUD and binding behavior remain unchanged

- **Covers:** FR7
- **Preconditions:** active dev instance and runtime object root exist.
- **Input or operation:** create, list, get, update, archive, set current, and get current task through env.tool.
- **Expected result:** active buddy can mutate only its task objects; archived task has `status=archived`; `set_current` updates instance binding; cross-buddy task operations reject without mutation.
- **Layer:** integration
- **Recommended test file path:** `tests/test_task_env_tool.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py -q`

### TC14 - Track env tool lifecycle and backlink behavior remain unchanged

- **Covers:** FR7
- **Preconditions:** PM and non-PM instances, tracks, and tasks exist.
- **Input or operation:** PM create/update/advance/archive; non-PM read and rejected lifecycle mutation; attach and detach active-buddy task.
- **Expected result:** PM lifecycle writes persist; non-PM lifecycle mutation rejects without state changes; attach/detach keeps track task lists and task track ids consistent.
- **Layer:** integration
- **Recommended test file path:** `tests/test_track_env_tool.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py -q`

### TC15 - Artifact env tool scoping and revision behavior remain unchanged

- **Covers:** FR7
- **Preconditions:** active task, foreign task, artifacts, and reserved run id exist.
- **Input or operation:** list, get, get current, validate payload, create revision, update metadata, and invalid foreign reads/writes.
- **Expected result:** active-buddy artifacts are visible; foreign content does not leak; create revision promotes current artifact and updates task slots; invalid payloads do not mutate state.
- **Layer:** integration
- **Recommended test file path:** `tests/test_artifact_env_tool.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_artifact_env_tool.py -q`

### TC16 - Context, binding, and handoff env tools preserve host decision behavior

- **Covers:** FR7
- **Preconditions:** active instances with task-only, track-only, bound, and unbound states exist.
- **Input or operation:** binding get/set/clear; context get/summarize/list sources; handoff validate with known, unknown, and conflicting targets.
- **Expected result:** binding writes update instance JSON; rejected binding operations leave instance unchanged; context responses omit raw global state; handoff validation returns target, alignment, discoverability, and suggested next buddy when conflicting.
- **Layer:** integration
- **Recommended test file path:** `tests/test_context_binding_env_tool.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_context_binding_env_tool.py -q`

### TC17 - Run env tool structured feedback uses tool-id hints

- **Covers:** FR7, FR11, FR13
- **Preconditions:** active instance with prepared context and invalid result payload.
- **Input or operation:** dispatch `run.commit` or `run.validate_result` with invalid or stale payload.
- **Expected result:** response has structured runtime feedback, allowed next action options when applicable, and any payload hint references `prepare.runtime_context.env_tools.run`.
- **Layer:** integration
- **Recommended test file path:** `tests/test_run_env_tool.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_run_env_tool.py -q`

### TC18 - Evidence env tool structured feedback uses tool-id hints

- **Covers:** FR7, FR11, FR13
- **Preconditions:** market instance with context requiring browser evidence.
- **Input or operation:** issue browser evidence, approve downgrade without reason, and use stale context revision.
- **Expected result:** valid issue writes scoped token; invalid reason and stale context reject without writing token; feedback references `prepare.runtime_context.env_tools.evidence`.
- **Layer:** integration
- **Recommended test file path:** `tests/test_evidence_env_tool.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_evidence_env_tool.py -q`

### TC19 - Manifest declares new shared env tool skill ids only

- **Covers:** FR9, FR10
- **Preconditions:** repo manifest exists.
- **Input or operation:** load `buddyswitch/manifest.toml`.
- **Expected result:** skills include `task-tool`, `track-tool`, and `artifact-tool` with correct repo-relative paths; every buddy references each new id exactly once; old manager skill ids are absent from skill rows and buddy lists.
- **Layer:** unit
- **Recommended test file path:** `tests/test_runtime_skills.py`, `tests/test_env_manifest_v2.py`, `tests/test_repo_consistency.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py::RuntimeSkillsTests::test_repo_manifest_declares_shared_env_tool_skills_for_every_buddy tests/test_env_manifest_v2.py::EnvManifestV2Tests::test_live_manifest_exposes_buddy_artifact_kinds_and_no_skill_persistence_payload tests/test_repo_consistency.py::RepoConsistencyTests::test_manifest_declares_shared_env_tool_skills_for_every_buddy -q`

### TC20 - Runtime skill install materializes only active buddy new ids

- **Covers:** FR9, FR10
- **Preconditions:** temporary workspace and test manifest with active buddy skills exist.
- **Input or operation:** call `runtime_skills.install_runtime_skills`.
- **Expected result:** returns installed new ids; `.agents/skills/<new-id>/SKILL.md` exists; inactive buddy skills and old manager skill dirs do not exist; assets such as `track-operation-template.md` are preserved.
- **Layer:** integration
- **Recommended test file path:** `tests/test_runtime_skills.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py::RuntimeSkillsTests::test_install_materializes_only_active_buddy_skills_and_assets tests/test_runtime_skills.py::RuntimeSkillsTests::test_install_replaces_stale_directories_when_switching_buddies -q`

### TC21 - Runtime skill install rejects missing or unsafe configuration without mutation

- **Covers:** FR9, FR13
- **Preconditions:** temporary manifest and workspace variants exist.
- **Input or operation:** install with missing skill source, unsafe workspace root, source checkout root workspace, non-existent workspace, file workspace, invalid skill id, or symlinked source.
- **Expected result:** raises or returns `RuntimeSkillsError` as existing tests expect; target workspace is not created or mutated beyond safe boundaries.
- **Layer:** integration
- **Recommended test file path:** `tests/test_runtime_skills.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py::RuntimeSkillsTests::test_install_rejects_unsafe_workspace_and_manifest_paths tests/test_runtime_skills.py::RuntimeSkillsTests::test_install_runtime_skills_api_rejects_source_checkout_root_workspace tests/test_runtime_skills.py::RuntimeSkillsTests::test_install_runtime_skills_api_rejects_nonexistent_workspace_without_creating_it tests/test_runtime_skills.py::RuntimeSkillsTests::test_install_rejects_invalid_skill_id_and_symlinked_sources -q`

### TC22 - Launcher start materializes native skills under new ids

- **Covers:** FR9, FR10, FR14
- **Preconditions:** launcher test captures runtime workspace path.
- **Input or operation:** run `./buddyswitch-codex instance start --buddy pm -- debug prompt-input ...` under test harness.
- **Expected result:** workspace has `.agents/skills/write-prd/SKILL.md`, `.agents/skills/task-tool/SKILL.md`, `.agents/skills/track-tool/SKILL.md`, `.agents/skills/artifact-tool/SKILL.md`; old manager skill dirs are absent; runtime AGENTS is copied unchanged from buddy asset.
- **Layer:** CLI
- **Recommended test file path:** `tests/test_buddyswitch_launcher.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_execution_worktree_uses_runtime_workspace_agents_header -q`

### TC23 - Launcher open refreshes native skills and removes stale dirs

- **Covers:** FR9, FR10, FR14
- **Preconditions:** existing inactive instance workspace has stale `.agents/skills/stale-skill`.
- **Input or operation:** run `./buddyswitch-codex instance open <instance-id> debug prompt-input continue` under test harness.
- **Expected result:** stale skill dir is removed; new skill dirs exist; old manager skill dirs are absent; source skill bytes match repo packages for selected buddy.
- **Layer:** CLI
- **Recommended test file path:** `tests/test_buddyswitch_launcher.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_refreshes_runtime_skills_and_removes_stale_skill -q`

### TC24 - Launcher runtime surface sync includes dispatch and excludes manager modules

- **Covers:** FR5, FR14
- **Preconditions:** launcher creates or repairs a runtime workspace.
- **Input or operation:** inspect files copied into runtime workspace after start/open.
- **Expected result:** `scripts/env/tools/dispatch.py`, `router.py`, `contracts.py`, `responses.py`, service modules, runtime kernel, and manifest are copied; old manager module files are absent.
- **Layer:** CLI
- **Recommended test file path:** `tests/test_buddyswitch_launcher.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_execution_worktree_uses_runtime_workspace_agents_header -q`

### TC25 - Active docs, AGENTS, and shared skills use env tool language

- **Covers:** FR11
- **Preconditions:** repository checkout after docs and skill rename.
- **Input or operation:** scan active docs, buddy AGENTS, manifest-declared skill packages, scripts, and tests for banned manager vocabulary.
- **Expected result:** no active surface contains manager action wording, old skill ids, manager runtime context keys, `_ACTION_MAP`, `_router_contract_error`, or `manager_name`.
- **Layer:** unit
- **Recommended test file path:** `tests/test_repo_consistency.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_active_env_tool_surfaces_do_not_advertise_manager_residue -q`

### TC26 - Historical specs with old vocabulary are marked superseded

- **Covers:** FR12
- **Preconditions:** dated specs under `docs/spec` remain in repo.
- **Input or operation:** scan each `docs/spec/*.md` for removed manager vocabulary.
- **Expected result:** any spec containing removed vocabulary starts with or contains the exact superseded banner required by the implementation plan.
- **Layer:** unit
- **Recommended test file path:** `tests/test_repo_consistency.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_historical_specs_with_manager_residue_are_marked_superseded -q`

### TC27 - Old product concepts remain absent from active surfaces

- **Covers:** FR11, FR13
- **Preconditions:** repository checkout after implementation.
- **Input or operation:** scan active paths for removed concepts: `env.task`, `issue_browser_evidence`, `handoff_inbox`, `automatic router`, `auto-routing`, `workflow engine`, `event bus`, and `DSL`.
- **Expected result:** no active runtime code, active docs, AGENTS, shared skills, or tests advertise or accept those concepts. Historical specs are only allowed when marked superseded.
- **Layer:** unit
- **Recommended test file path:** `tests/test_repo_consistency.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_active_env_tool_surfaces_do_not_reintroduce_forbidden_product_concepts -q`

### TC28 - Full env layer end-to-end loop still uses env.tool

- **Covers:** FR1, FR7, FR14
- **Preconditions:** test runtime workspace can seed PM, market, design, dev, and test flows.
- **Input or operation:** run the existing full buddy loop through runtime broker and env tool calls.
- **Expected result:** env tool calls are recorded as `(buddy, tool, action)` tuples using tool ids; persisted state, context, evidence, and run artifacts remain valid.
- **Layer:** integration
- **Recommended test file path:** `tests/test_env_layer_end_to_end.py`
- **Recommended command:** `python3 -m pytest -p no:cacheprovider tests/test_env_layer_end_to_end.py -q`

## Manual Supplemental Test Cases

### MTC01 - Product instance smoke

- **Covers:** FR9, FR10, FR14
- **Preconditions:** worktree `dev2258` is current, launcher dependencies are available.
- **Input or operation:** run `./buddyswitch-codex instance start --buddy pm -- debug prompt-input "Env tool residue removal smoke"`.
- **Expected result:** instance starts, workspace contains `.agents/skills/task-tool`, `.agents/skills/track-tool`, `.agents/skills/artifact-tool`, and no old manager skill dirs.
- **Layer:** manual
- **Recommended test file path:** not applicable
- **Recommended command:** `./buddyswitch-codex instance start --buddy pm -- debug prompt-input "Env tool residue removal smoke"`

### MTC02 - Prepared runtime context inspection

- **Covers:** FR6, FR14
- **Preconditions:** inside the product instance workspace from MTC01.
- **Input or operation:** run `python3 scripts/turn_runtime.py prepare "Inspect env tool context"`.
- **Expected result:** JSON contains `runtime_context.env_tools.task`, `track`, `artifact`, `context`, `binding`, `handoff`, `run`, and `evidence`; no manager-keyed env tools exist.
- **Layer:** manual
- **Recommended test file path:** not applicable
- **Recommended command:** `python3 scripts/turn_runtime.py prepare "Inspect env tool context"`

### MTC03 - Env client smoke from runtime workspace

- **Covers:** FR1, FR8, FR14
- **Preconditions:** inside the product instance workspace from MTC01 with runtime broker env vars present.
- **Input or operation:** run `python3 scripts/env/client.py task list`.
- **Expected result:** command prints JSON with `ok` boolean, uses `tool="task"` when successful, and does not mention manager runtime hints.
- **Layer:** manual
- **Recommended test file path:** not applicable
- **Recommended command:** `python3 scripts/env/client.py task list`

## Final Verification Command Set

Run focused contract and residue tests:

```bash
python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py tests/test_prepare_runtime_context.py tests/test_runtime_skills.py tests/test_env_manifest_v2.py tests/test_repo_consistency.py -q
```

Run env tool behavior tests:

```bash
python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_context_binding_env_tool.py tests/test_run_env_tool.py tests/test_evidence_env_tool.py tests/test_env_tool_response_contract.py -q
```

Run broker, boundary, and end-to-end tests:

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py tests/test_env_layer_boundaries.py tests/test_env_layer_end_to_end.py -q
```

Run launcher skill materialization checks:

```bash
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_execution_worktree_uses_runtime_workspace_agents_header tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_refreshes_runtime_skills_and_removes_stale_skill -q
```

Run compile check:

```bash
python3 -m compileall -q scripts tools
```

Run full suite:

```bash
python3 -m pytest -p no:cacheprovider -q
```

Run a literal residue scan over active paths:

```bash
rg -n "Env manager|manager actions|manager operations|_ACTION_MAP|_router_contract_error|manager_name|task_manager|track_manager|artifact_manager|context_manager|binding_manager|handoff_manager|run_manager|evidence_manager|task-manager|track-manager|artifact-manager" README.md framework/docs framework/contracts scripts tools/launcher/assets buddyswitch/manifest.toml buddyswitch/skills tests
```

Expected residue scan result: no matches.
