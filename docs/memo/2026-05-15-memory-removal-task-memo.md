# Memory Removal Task Memo

Date: 2026-05-15
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/dev2258`
Branch: `dev2258`

## Target

Remove `memory` from BuddySwitch completely for the current iteration.

This is not a local-memory redesign. The product decision is to remove memory because the local buddy-level memory model is not designed yet. Buddybox remains in scope as a separate capability, but buddybox local-vs-shared cleanup is not part of this task.

## Scope

In scope:

- Remove the `memory` env tool and all memory tool actions.
- Remove memory permissions from buddy manifest/profile-facing capability surfaces.
- Remove memory from context discovery, workspace projection, console data shape, runtime contracts, launcher projection, docs, and tests.
- Remove memory as a valid `source_refs` type.
- Remove memory as an evidence target.
- Remove handoff `memory_ids`.
- Delete memory-specific service code and tests.

Out of scope:

- Designing a replacement local buddy memory model.
- Migrating or cleaning already-created runtime memory files.
- Changing buddybox semantics beyond removing references that mention memory.
- Reworking artifact/task/track behavior except where they reference memory.

Important cleanup boundary: existing `buddyswitch/objects/memories/*.json` data may exist in old runtime state. This task should remove all code paths that create/read/project/use it. It should not add a cleanup or migration process.

## Current Memory Surfaces Found

Runtime object store:

- `scripts/env_store.py`
  - `MEMORY_OBJECTS_DIR`
  - `VALID_MEMORY_STATUS`
  - `VALID_MEMORY_KINDS`
  - `memory_file`
  - `validate_memory`
  - `list_memories`
  - `get_memory`
  - `save_memory`
  - `create_memory`
  - `update_memory`
  - memory fields inside handoff validation and creation
  - memory accepted in internal source refs normalization

Env tool surface:

- `scripts/env/services/memories.py`
- `scripts/env/tools/contracts.py`
- `scripts/env/tools/dispatch.py`
- `scripts/env/tools/semantics.py`
- `scripts/env/client.py`
- `scripts/turn_runtime.py` indirectly through env tool description

Context and projection:

- `scripts/env/services/context.py`
  - `memory_kind`
  - `memory_summaries`
  - `has_memories`
  - `memories` count
  - `context_sources_desc()["memories"]`
- `scripts/runtime_store/projections.py`
- `scripts/workspace_data.py`
- `framework/contracts/workspace-projection.json`
- `framework/console/app.js`

Related runtime flows:

- `scripts/env/services/evidence.py`
  - memory evidence target support
- `scripts/env/services/handoffs.py`
  - `memory_ids`
  - memory ownership validation
- `scripts/env/services/source_refs.py`
  - `memory` allowed source ref type
  - full-summary read claim checks against memories
- `scripts/env/services/buddybox.py`
  - user-facing guidance that says buddybox paths can be referenced by memory

Manifest, launcher, and buddy-facing text:

- `buddyswitch/manifest.toml`
  - all `memory.*` permissions
- `tools/launcher/assets/buddies/*/AGENTS.md`
  - tool list includes `memory`
  - market text says evidence targets artifact or memory
  - final output text mentions memories
- `buddyswitch/env-profiles/*.json` should be checked for memory-capability drift even if current hits are manifest-heavy.
- `scripts/env_manifest.py`
  - known capability/tool lists and generated guidance
- `tools/launcher/workspace.sh`
  - memory projection paths
- `tools/launcher/codex_config.py` and launcher tests mention memory service/path coverage.

Docs and specs:

- Runtime docs currently describe memory as durable product state. Update active docs/contracts.
- Existing historical memos/specs under `docs/memo` and `docs/spec` may remain as historical records unless repo consistency tests require active-doc cleanup. New docs should state memory is removed.

Tests:

- `tests/test_memory_env_tool.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_repo_consistency.py`
- `tests/test_evidence_env_tool.py`
- `tests/test_handoff_env_tool.py`
- `tests/test_run_env_tool.py`
- `tests/test_cleanup_system.py`
- `tests/test_env_layer_end_to_end.py`
- `tests/test_parallel_contracts.py`
- `tests/test_host_decision_surface_product_mode.py`
- `tests/test_runtime_tool_feedback.py`
- `tests/test_runless_runtime_contract.py`
- `tests/test_prepare_runtime_context.py`
- `tests/test_context_binding_env_tool.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_buddyswitch_launcher.py`
- `tests/runtime_root_test_helper.py`

## Required Behavior After Removal

Runtime tools:

- `memory` is not present in `TOOL_REGISTRY`.
- `memory` is not present in router supported tools.
- `memory` is not present in `turn_runtime.py status` `env_tools`.
- `python3 scripts/env/client.py memory ...` is not a valid CLI resource.
- `env.tool` payload `{ "tool": "memory", ... }` returns unsupported tool feedback and does not mutate state.

Manifest and buddy instructions:

- No buddy has `memory.read`, `memory.write`, `memory.update`, or `memory.archive`.
- Buddy AGENTS files list `task`, `track`, `artifact`, `handoff`, `buddybox`, `context`, `evidence`, and `search`, but not `memory`.

Context and projection:

- `context.get` and `context.summarize` do not accept `memory_kind`.
- Context responses do not include `memory_summaries`, `has_memories`, or memory counts.
- `context.list_sources` does not include `memories`.
- Workspace projection does not include top-level `memories`.
- Console app does not normalize or render `memories`.

Related flows:

- Evidence targets are artifacts only.
- Handoff payloads do not accept `memory_ids`.
- Handoff records no longer contain `memory_ids`.
- `source_refs` no longer accept `{ "type": "memory", ... }`.
- Artifact/handoff/buddybox guidance does not tell buddies to use memory.

Storage:

- Runtime directory setup no longer creates `buddyswitch/objects/memories`.
- New runtime writes never create memory object files.
- Existing old memory files are ignored by the active runtime instead of migrated or cleaned.

## Recommended Implementation Order

1. Reconfirm worktree state.
   - Run `pwd`, `git branch --show-current`, and `git status --short`.
   - Expected branch is `dev2258`.
   - Do not work from main.

2. Add failing tests for the removal contract.
   - Tool registry excludes `memory`.
   - Router rejects `memory`.
   - `turn_runtime.py status` excludes `memory`.
   - Manifest permissions exclude `memory.*`.
   - Context sources exclude `memories`.
   - Client help excludes the `memory` resource.
   - Evidence rejects `target_type=memory`.
   - Handoff rejects or no longer accepts `memory_ids`.
   - Source refs reject `type=memory`.

3. Remove env tool registration and CLI.
   - Delete `scripts/env/services/memories.py`.
   - Remove memory handler import and map from `scripts/env/tools/dispatch.py`.
   - Remove memory registry block from `scripts/env/tools/contracts.py`.
   - Remove memory action semantics and capability text from `scripts/env/tools/semantics.py`.
   - Remove memory parser and dispatch branch from `scripts/env/client.py`.

4. Remove store-level memory support.
   - Remove memory constants, file helpers, validators, list/get/save/create/update functions from `scripts/env_store.py`.
   - Remove memory handling from internal source ref normalization.
   - Remove memory fields from handoff validation and creation payloads.

5. Remove memory from context and projection.
   - Remove memory filters and sections from `scripts/env/services/context.py`.
   - Remove memory projection helpers from `scripts/runtime_store/projections.py` and `scripts/workspace_data.py`.
   - Remove memory shape and data source from `framework/contracts/workspace-projection.json`.
   - Remove memory normalization/render support from `framework/console/app.js`.

6. Remove memory from adjacent runtime flows.
   - Make evidence artifact-only.
   - Remove `memory_ids` from handoff contracts and service logic.
   - Remove `memory` from `source_refs` allowed types and read-claim validation.
   - Update response guidance strings that mention memory.

7. Update manifest, launcher, and active docs.
   - Remove all `memory.*` permissions from `buddyswitch/manifest.toml`.
   - Update buddy AGENTS tool lists and final-output guidance.
   - Update active framework contracts/docs to remove memory as state, evidence target, and handoff/source ref object.
   - Update launcher workspace/projection expectations that include `buddyswitch/objects/memories`.

8. Update or delete tests.
   - Delete memory lifecycle tests.
   - Replace them with unsupported-memory-surface tests if useful.
   - Rewrite tests that seed memory to use artifacts, tasks, handoffs, buddybox files, external refs, or notes depending on the purpose.

9. Run verification.
   - Focused:
     - `python3 -m pytest tests/test_env_tool_router.py tests/test_turn_runtime.py tests/test_env_manifest_v2.py tests/test_env_tool_identity.py -q`
     - `python3 -m pytest tests/test_evidence_env_tool.py tests/test_handoff_env_tool.py tests/test_context_binding_env_tool.py tests/test_env_tool_semantic_contract.py -q`
   - Launcher/projection:
     - `python3 -m pytest tests/test_buddyswitch_launcher.py tests/test_parallel_contracts.py tests/test_console_app_contract.py -q`
   - Broader env/runtime:
     - `python3 -m pytest tests/test_runless_runtime_contract.py tests/test_env_tool_response_contract.py tests/test_env_layer_end_to_end.py tests/test_repo_consistency.py -q`
   - Final grep gate:
     - `rg -n "memory|memories|memory_ids|memory_kind|MEMORY_|create_memory|get_memory|list_memories|update_memory|memory\\." scripts framework buddyswitch tools tests`
     - Expected result should be empty for active code/tests/docs, except historical migration notes explicitly allowed by the owner.

## Risks

- Tests and docs are currently built around memory as a runless replacement output. Removing it will touch many contract tests.
- Handoff schema changes may affect stored historical records with `memory_ids`. The current task should remove active read/write support, not migrate old objects.
- Evidence currently supports `memory` as a target. Making evidence artifact-only may require updating market workflow tests and docs.
- Source refs may currently allow `memory` from artifacts/handoffs. Removing it must be done consistently or stale refs will pass validation unexpectedly.

## Definition of Done

- No active runtime path exposes, accepts, writes, reads, validates, or projects memory.
- No buddy-facing tool list or manifest permission mentions memory.
- No active test expects memory lifecycle, memory projection, memory evidence, or memory handoff refs.
- Verification commands pass.
- Existing old memory files are left untouched and ignored.
