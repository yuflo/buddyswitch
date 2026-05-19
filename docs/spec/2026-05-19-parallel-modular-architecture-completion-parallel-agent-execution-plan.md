# Parallel Modular Architecture Completion Parallel Subagent Execution Plan

## Source Plan Summary
- Source artifact: `docs/spec/2026-05-19-parallel-modular-architecture-completion-implementation-plan.md`
- Product outcome: BuddySwitch first-phase parallel modular runtime requirements are complete through the thin path `SKILL -> Tool Contract -> Service -> Domain Ops -> Object Repo -> JSON / Files`.
- Current bottleneck: the full suite has one known failure in buddybox instance workspace root handling, and active object repos / shared tool skills still preserve runtime coupling that blocks modular parallel work.
- Done criteria:
  - `python3 -m pytest -q` passes.
  - Adding a new `message` action requires runtime contract/service/domain/repo/test edits, not shared `message-tool` edits.
  - Editing one buddy-specific skill file does not require Python runtime edits.
  - `message`, `comment`, and `buddybox` tests run independently without `track`, `artifact`, or `task` test modules.
  - Shared tool skills use runtime discovery for action catalogs and payload details.
  - Object repos do not import sibling repos or `env_legacy_store`.
  - Cross-object runtime rules live only in domain modules.
  - `track/artifact` publication keeps one mutation domain entry point.
  - Behavior tests prove persisted writes and no-mutation rejection paths before static scans enforce boundaries.
- Hard constraints:
  - Planning artifact only; do not execute the implementation from this plan.
  - Keep the thin runtime path; do not add workflow engines, plugin systems, event buses, generic repositories, or compatibility layers.
  - Use env tools for product-mode runtime state; do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.
  - Runtime object state remains under temporary `buddyswitch/objects/**`; active-buddy private files remain under temporary workspace-local `buddyswitch/local/buddybox/**`.
  - Preserve existing env.tool response semantics and rejection boundaries where tests already cover them.
- Non-goals:
  - Replacing all test fixture use of `env_legacy_store`.
  - Changing external CLI contracts beyond removing copied shared-skill action catalogs.
  - Broad runtime redesign, scheduler/workflow introduction, or generalized repository abstraction.
- Candidate code paths:
  - `scripts/env/repos/runtime_files.py`
  - `scripts/env/repos/buddybox_files.py`
  - `scripts/env/repos/comments.py`
  - `scripts/env/repos/tasks.py`
  - `scripts/env/repos/tracks.py`
  - `scripts/env/repos/artifacts.py`
  - `scripts/env/domain/comment_targets.py`
  - `scripts/env/domain/tasks.py`
  - `scripts/env/domain/artifact_visibility.py`
  - `scripts/env/domain/publication.py`
  - `scripts/env/services/comments.py`
  - `scripts/env/services/tasks.py`
  - `scripts/env/services/artifacts.py`
  - `scripts/env/services/tracks.py`
  - `buddyswitch/skills/shared/*-tool/SKILL.md`
- Candidate test paths:
  - `tests/test_runtime_broker.py`
  - `tests/test_buddybox_env_tool.py`
  - `tests/test_runtime_skills.py`
  - `tests/test_env_layer_boundaries.py`
  - `tests/test_repo_consistency.py`
  - `tests/test_comment_env_tool.py`
  - `tests/test_task_env_tool.py`
  - `tests/test_artifact_env_tool.py`
  - `tests/test_track_env_tool.py`
  - `tests/test_parallel_contracts.py`
  - `tests/test_env_layer_end_to_end.py`
  - `tests/test_env_tool_semantic_contract.py`
  - `tests/test_env_tool_router.py`
  - `tests/test_env_tool_response_contract.py`
  - `tests/test_runtime_tool_feedback.py`
  - `tests/test_turn_integration.py`

## Repo Recon Summary
- Scanned paths:
  - `docs/spec/2026-05-19-parallel-modular-architecture-completion-implementation-plan.md`
  - `scripts/env/repos/**`
  - `scripts/env/domain/**`
  - `scripts/env/services/**`
  - `scripts/env/tools/contracts.py`
  - `buddyswitch/skills/shared/*-tool/SKILL.md`
  - Target tests listed above.
- Relevant modules and entrypoints:
  - `scripts/env/repos/runtime_files.py` owns runtime root selection, write-root guard, JSON IO, object directory constants, and `buddybox_local_dir(instance_payload)`.
  - `scripts/env/repos/buddybox_files.py` already routes active-buddy private files through `runtime_files.buddybox_local_dir(instance_payload)`.
  - `scripts/env/repos/messages.py` is already direct runtime JSON storage and is the model for direct object repos.
  - `scripts/env/repos/comments.py`, `tasks.py`, `tracks.py`, and `artifacts.py` currently proxy through `env_legacy_store`.
  - `scripts/env/domain/comment_targets.py`, `tasks.py`, and `artifact_visibility.py` are the right homes for cross-object read checks.
  - `scripts/env/domain/publication.py` is already the single track/artifact mutation domain entry point.
  - `scripts/env/services/comments.py`, `artifacts.py`, `tasks.py`, and `tracks.py` are env.tool request/response adapters and should not regain storage ownership.
  - Shared tool skill files still contain action catalogs or route copies in `artifact`, `task`, `track`, `message`, and `comment` skills.
- Existing tests and verification hooks:
  - Known failing main-path test: `tests/test_runtime_broker.py::RuntimeBrokerTests::test_env_tool_buddybox_write_uses_instance_workspace_local_root`.
  - Existing architecture checks live in `tests/test_env_layer_boundaries.py`, `tests/test_repo_consistency.py`, and `tests/test_parallel_contracts.py`.
  - Behavior suites cover broker-routed env.tool surfaces for `message`, `comment`, `buddybox`, `task`, `artifact`, and `track`.
  - Runtime contract checks live in `tests/test_env_tool_semantic_contract.py`, `tests/test_env_tool_router.py`, `tests/test_env_tool_response_contract.py`, and `tests/test_runtime_tool_feedback.py`.
- Shared files and contracts:
  - `scripts/env/repos/runtime_files.py` is a shared storage/root contract and must be changed in the serial seed.
  - `tests/test_env_layer_boundaries.py` is a shared architecture test file; one test package owns all planned edits to avoid merge conflicts.
  - `tests/test_track_env_tool.py` is shared between publication behavior and object repo behavior; one test package owns planned edits.
  - `buddyswitch/skills/shared/*-tool/SKILL.md` are runtime-facing guidance contracts and can be edited independently from Python runtime code.
  - Source plan is currently untracked in this worktree; this plan must not overwrite it.
- Open unknowns and mitigation:
  - Direct repo replacements need exact normalization parity with `env_legacy_store`; mitigate by porting behavior under focused object behavior tests before full suite.
  - Static publication scans may catch harmless explanatory strings; mitigate by keeping scans scoped to active runtime files and known boundary terms.
  - `env_legacy_store` remains acceptable in tests and legacy fixture helpers during this step; active runtime module imports are the boundary under repair.
  - Integration can expose response-classification drift when supersede checks move to domain; mitigate with artifact rejection tests and final runtime feedback verification.

## Dependency Graph
```text
serial-seed:
  D1 -> fix known buddybox workspace-root failure and lock workspace-local root contract

parallel-test-seeds:
  T1 depends on D1
  T2 depends on D1
  T3 depends on D1

parallel-implementation:
  D2 depends on T1
  D3 depends on T2
  D4 depends on T2

integration:
  I1 depends on D2, D3, D4, T3

targeted-review:
  R2 depends on I1

final-review:
  R1 depends on I1, R2, and verification evidence
```

## Conflict Matrix
| Work Package | Role | Owned Write Set | Forbidden Write Set | Can Run With | Notes |
| --- | --- | --- | --- | --- | --- |
| D1 | developer | `scripts/env/repos/runtime_files.py`, `tests/test_runtime_broker.py`, `tests/test_buddybox_env_tool.py` | `scripts/env/repos/{comments,tasks,tracks,artifacts}.py`, `buddyswitch/skills/shared/**` | none in same wave | Serial seed because it fixes the known full-suite failure and touches shared root selection. |
| T1 | test | `tests/test_runtime_skills.py` | `buddyswitch/skills/shared/**`, `scripts/env/**` | T2, T3 | Creates skill runtime-discovery tests only. |
| T2 | test | `tests/test_env_layer_boundaries.py`, `tests/test_comment_env_tool.py`, `tests/test_task_env_tool.py`, `tests/test_artifact_env_tool.py`, `tests/test_track_env_tool.py` | `scripts/env/**`, `buddyswitch/skills/shared/**`, `tests/test_runtime_skills.py`, `tests/test_parallel_contracts.py` | T1, T3 | Owns all shared boundary and object behavior test edits to avoid same-file conflicts. |
| T3 | test | `tests/test_parallel_contracts.py` | `scripts/env/**`, `buddyswitch/skills/shared/**`, T1/T2 owned test files | T1, T2 | Adds independent message/comment/buddybox subprocess proof. |
| D2 | developer | `buddyswitch/skills/shared/message-tool/SKILL.md`, `buddyswitch/skills/shared/comment-tool/SKILL.md`, `buddyswitch/skills/shared/track-tool/SKILL.md`, `buddyswitch/skills/shared/artifact-tool/SKILL.md`, `buddyswitch/skills/shared/task-tool/SKILL.md`, `buddyswitch/skills/shared/buddybox-tool/SKILL.md` | `scripts/env/**`, `tests/**` | D3, D4 | Skills-only runtime discovery cleanup. |
| D3 | developer | `scripts/env/repos/comments.py`, `scripts/env/domain/comment_targets.py`, `scripts/env/services/comments.py` | `scripts/env/repos/{tasks,tracks,artifacts}.py`, `scripts/env/domain/{tasks,artifact_visibility,publication}.py`, `scripts/env/services/{tasks,artifacts,tracks}.py`, `tests/**` | D2, D4 | Comment storage and artifact revision-chain domain move. |
| D4 | developer | `scripts/env/repos/tasks.py`, `scripts/env/repos/tracks.py`, `scripts/env/repos/artifacts.py`, `scripts/env/domain/tasks.py`, `scripts/env/domain/artifact_visibility.py`, `scripts/env/services/artifacts.py` | `scripts/env/repos/comments.py`, `scripts/env/domain/comment_targets.py`, `scripts/env/services/comments.py`, `scripts/env/domain/publication.py`, `tests/**`, `buddyswitch/skills/shared/**` | D2, D3 | Direct object repos and moved cross-object read checks. |
| I1 | developer | D1, D2, D3, D4, T1, T2, T3 owned paths only when required by integration failures | New runtime abstractions, `buddyswitch/objects/**`, `buddyswitch/local/buddybox/**` | after parallel work only | Integration repair and full verification evidence collection. |
| R2 | reviewer | none | `*` | after I1 only | Targeted runtime-boundary review because shared root, object repo, and publication boundaries changed. |
| R1 | reviewer | none | `*` | after I1 and R2 only | Final acceptance review. |

Conflict rules:
- No same-wave packages own the same file.
- Shared test files `tests/test_env_layer_boundaries.py` and `tests/test_track_env_tool.py` have a single owner, T2.
- Shared runtime root selection is serial in D1.
- Publication mutation domain `scripts/env/domain/publication.py` is inspect-only unless integration exposes a concrete defect.

## Execution Waves
- Wave 0 (optional read-only recon):
  - No separate explorer is required unless the execution owner wants fresh recon; this plan already scoped the relevant modules.
- Wave 1 (serial seed):
  - D1
  - Max concurrency: 1
- Wave 2 (parallel requirement-first test seeds):
  - T1, T2, T3
  - Max concurrency: 3
- Wave 3 (parallel implementation):
  - D2, D3, D4
  - Max concurrency: 3
- Wave 4 (integration gate):
  - I1
  - Max concurrency: 1
- Wave 5 (targeted review):
  - R2
  - Max concurrency: 1
- Wave 6 (final review):
  - R1
  - Max concurrency: 1

## Work Packages
```yaml
id: D1
role: developer
agent_type: worker
goal: Fix buddybox workspace-local root selection so broker-routed write/read/list/delete use the instance workspace_dir even when a runtime root override is active.
dependencies: []
owned_write_set:
  - scripts/env/repos/runtime_files.py
  - tests/test_runtime_broker.py
  - tests/test_buddybox_env_tool.py
forbidden_write_set:
  - scripts/env/repos/comments.py
  - scripts/env/repos/tasks.py
  - scripts/env/repos/tracks.py
  - scripts/env/repos/artifacts.py
  - buddyswitch/skills/shared/**
read_context:
  - docs/spec/2026-05-19-parallel-modular-architecture-completion-implementation-plan.md
  - scripts/env/repos/buddybox_files.py
  - tests/runtime_root_test_helper.py
tasks:
  - Add the broker lifecycle test described in source Task 1.
  - Run the focused two-test command and confirm the expected failure before the fix.
  - Change runtime_workspace_root() so instance_payload["workspace_dir"] wins for workspace-local files.
  - Keep STATE_ROOT, OBJECTS_ROOT, and product object roots unchanged.
tests_to_add_or_run:
  - python3 -m pytest tests/test_runtime_broker.py::RuntimeBrokerTests::test_env_tool_buddybox_write_uses_instance_workspace_local_root tests/test_runtime_broker.py::RuntimeBrokerTests::test_env_tool_buddybox_lifecycle_uses_instance_workspace_local_root -q
  - python3 -m pytest tests/test_runtime_broker.py::RuntimeBrokerTests::test_env_tool_buddybox_write_uses_instance_workspace_local_root tests/test_runtime_broker.py::RuntimeBrokerTests::test_env_tool_buddybox_lifecycle_uses_instance_workspace_local_root tests/test_buddybox_env_tool.py -q
done_when:
  - Buddybox files are created under instance workspace_dir/buddyswitch/local/buddybox/<buddy>.
  - Wrong runtime-root and state-root buddybox paths remain absent.
  - Focused verification passes.
return_format:
  - changed files
  - failing-before summary
  - verification output
  - risks or blockers
```

```yaml
id: T1
role: test
agent_type: worker
goal: Replace shared-skill operation-list assertions with runtime-discovery ownership tests.
dependencies:
  - D1
owned_write_set:
  - tests/test_runtime_skills.py
forbidden_write_set:
  - buddyswitch/skills/shared/**
  - scripts/env/**
  - tests/test_env_layer_boundaries.py
  - tests/test_parallel_contracts.py
read_context:
  - docs/spec/2026-05-19-parallel-modular-architecture-completion-implementation-plan.md
  - buddyswitch/skills/shared/message-tool/SKILL.md
  - buddyswitch/skills/shared/comment-tool/SKILL.md
  - buddyswitch/skills/shared/track-tool/SKILL.md
  - buddyswitch/skills/shared/artifact-tool/SKILL.md
  - buddyswitch/skills/shared/task-tool/SKILL.md
  - buddyswitch/skills/shared/buddybox-tool/SKILL.md
tasks:
  - Replace the old track operation-set test with the runtime catalog ownership tests from source Task 2.
  - Update message/comment atomic shared-skill tests so they require env.tool and context.get.tool_catalog rather than copied action names.
  - Run the focused tests and record expected failures before D2 edits skills.
tests_to_add_or_run:
  - python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_shared_tool_skills_do_not_duplicate_runtime_action_catalogs tests/test_runtime_skills.py::RuntimeSkillsTests::test_message_comment_shared_tool_skills_stay_atomic -q
done_when:
  - Tests fail for current copied action catalogs before D2.
  - Assertions are requirement-based and do not encode private helper names.
return_format:
  - changed tests
  - requirement-to-test mapping
  - failing-before output
  - remaining coverage risks
```

```yaml
id: T2
role: test
agent_type: worker
goal: Add behavior-first and boundary coverage for comment repo ownership, direct object repos, and single publication-entry proof.
dependencies:
  - D1
owned_write_set:
  - tests/test_env_layer_boundaries.py
  - tests/test_comment_env_tool.py
  - tests/test_task_env_tool.py
  - tests/test_artifact_env_tool.py
  - tests/test_track_env_tool.py
forbidden_write_set:
  - scripts/env/**
  - buddyswitch/skills/shared/**
  - tests/test_runtime_skills.py
  - tests/test_parallel_contracts.py
read_context:
  - docs/spec/2026-05-19-parallel-modular-architecture-completion-implementation-plan.md
  - scripts/env/repos/comments.py
  - scripts/env/repos/tasks.py
  - scripts/env/repos/tracks.py
  - scripts/env/repos/artifacts.py
  - scripts/env/domain/publication.py
  - scripts/env/services/tracks.py
  - scripts/env/services/artifacts.py
tasks:
  - Extend artifact-section comment revision scope coverage with target and comment-count snapshots.
  - Add the comment repo owns-only-comment-storage boundary test.
  - Add the active object repos do-not-import-env_legacy_store boundary test.
  - Add task track-context read-only validation behavior.
  - Add archived published artifact supersede rejection without new artifact.
  - Add publication write-location boundary test.
  - Tighten existing track.add_material and track.add_proof positive tests with artifact and track mutation assertions if missing.
tests_to_add_or_run:
  - python3 -m pytest tests/test_comment_env_tool.py::CommentEnvToolTests::test_artifact_section_revision_reference_must_belong_to_same_chain tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_comment_repo_owns_only_comment_storage -q
  - python3 -m pytest tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_active_object_repos_do_not_import_env_legacy_store -q
  - python3 -m pytest tests/test_track_env_tool.py tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_track_artifact_publication_writes_only_live_in_publication_domain -q
done_when:
  - New tests fail on current repo proxy and copied boundary behavior before D3/D4.
  - Positive and rejected writes assert persisted state, not only response shape.
  - Static scans are scoped to active runtime files.
return_format:
  - added or changed tests
  - requirement-to-test mapping
  - failing-before output
  - remaining coverage risks
```

```yaml
id: T3
role: test
agent_type: worker
goal: Prove message/comment/buddybox focused tests run as an independent loop.
dependencies:
  - D1
owned_write_set:
  - tests/test_parallel_contracts.py
forbidden_write_set:
  - scripts/env/**
  - buddyswitch/skills/shared/**
  - tests/test_runtime_skills.py
  - tests/test_env_layer_boundaries.py
  - tests/test_comment_env_tool.py
  - tests/test_task_env_tool.py
  - tests/test_artifact_env_tool.py
  - tests/test_track_env_tool.py
read_context:
  - docs/spec/2026-05-19-parallel-modular-architecture-completion-implementation-plan.md
  - tests/test_message_env_tool.py
  - tests/test_comment_env_tool.py
  - tests/test_buddybox_env_tool.py
tasks:
  - Add the subprocess test from source Task 6.
  - Add missing imports only as needed.
  - Verify the subprocess output does not include track/artifact/task test modules.
tests_to_add_or_run:
  - python3 -m pytest tests/test_message_env_tool.py tests/test_comment_env_tool.py tests/test_buddybox_env_tool.py -q
  - python3 -m pytest tests/test_parallel_contracts.py::ParallelContractsTests::test_message_comment_buddybox_focused_tests_run_as_independent_loop -q
done_when:
  - Focused loop passes independently.
  - Contract proof passes and excludes track/artifact/task test module names.
return_format:
  - changed tests
  - verification output
  - risks or blockers
```

```yaml
id: D2
role: developer
agent_type: worker
goal: Remove copied shared tool action catalogs and defer operation/payload details to runtime discovery.
dependencies:
  - T1
owned_write_set:
  - buddyswitch/skills/shared/message-tool/SKILL.md
  - buddyswitch/skills/shared/comment-tool/SKILL.md
  - buddyswitch/skills/shared/track-tool/SKILL.md
  - buddyswitch/skills/shared/artifact-tool/SKILL.md
  - buddyswitch/skills/shared/task-tool/SKILL.md
  - buddyswitch/skills/shared/buddybox-tool/SKILL.md
forbidden_write_set:
  - scripts/env/**
  - tests/**
read_context:
  - tests/test_runtime_skills.py
  - tests/test_repo_consistency.py
  - scripts/env/tools/contracts.py
tasks:
  - Remove `## Operations`, `- Operations:`, and `env.tool -> tool.action` copied route catalogs from shared tool skills.
  - Keep concise runtime route examples and require `context.get.tool_catalog['<tool>']` or `python3 scripts/turn_runtime.py status` for current operations and payloads.
  - Preserve workflow-specific examples only when they demonstrate the current main path rather than an exhaustive catalog.
tests_to_add_or_run:
  - python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py::RepoConsistencyTests::test_skill_and_contract_texts_do_not_copy_payload_field_or_schema_tables -q
done_when:
  - Adding a new message action no longer requires editing `buddyswitch/skills/shared/message-tool/SKILL.md`.
  - Shared tool skill tests pass.
return_format:
  - changed files
  - behavior changes
  - verification output
  - risks or blockers
```

```yaml
id: D3
role: developer
agent_type: worker
goal: Make the comment repo comment-storage-only and move artifact revision-chain checks into domain logic.
dependencies:
  - T2
owned_write_set:
  - scripts/env/repos/comments.py
  - scripts/env/domain/comment_targets.py
  - scripts/env/services/comments.py
forbidden_write_set:
  - scripts/env/repos/tasks.py
  - scripts/env/repos/tracks.py
  - scripts/env/repos/artifacts.py
  - scripts/env/domain/tasks.py
  - scripts/env/domain/artifact_visibility.py
  - scripts/env/domain/publication.py
  - scripts/env/services/tasks.py
  - scripts/env/services/artifacts.py
  - scripts/env/services/tracks.py
  - tests/**
read_context:
  - scripts/env/repos/messages.py
  - tests/test_comment_env_tool.py
  - tests/test_env_layer_boundaries.py
tasks:
  - Replace comment repo legacy proxy with direct JSON storage through runtime_files.
  - Expose `list_comments`, `get_comment`, `save_comment`, `create_comment`, and `comments_for_target` with service-compatible signatures.
  - Keep target readability, artifact checks, and revision-chain logic out of the repo.
  - Add `artifact_revision_chain_ids()` to comment target domain.
  - Change comment service revision chain lookup to call the domain helper.
tests_to_add_or_run:
  - python3 -m pytest tests/test_comment_env_tool.py tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_comment_repo_owns_only_comment_storage -q
done_when:
  - `scripts/env/repos/comments.py` has no `env_legacy_store` import and no artifact/task/track repo imports.
  - Valid same-chain comments mutate only comment objects.
  - Invalid cross-chain comments mutate nothing.
return_format:
  - changed files
  - behavior changes
  - verification output
  - risks or blockers
```

```yaml
id: D4
role: developer
agent_type: worker
goal: Replace task, track, and artifact legacy repo proxies with direct object repos and move cross-object checks into domain modules.
dependencies:
  - T2
owned_write_set:
  - scripts/env/repos/tasks.py
  - scripts/env/repos/tracks.py
  - scripts/env/repos/artifacts.py
  - scripts/env/domain/tasks.py
  - scripts/env/domain/artifact_visibility.py
  - scripts/env/services/artifacts.py
forbidden_write_set:
  - scripts/env/repos/comments.py
  - scripts/env/domain/comment_targets.py
  - scripts/env/services/comments.py
  - scripts/env/domain/publication.py
  - scripts/env/services/tracks.py
  - scripts/env/services/tasks.py
  - tests/**
  - buddyswitch/skills/shared/**
read_context:
  - scripts/env/repos/messages.py
  - scripts/env/domain/publication.py
  - tests/test_task_env_tool.py
  - tests/test_artifact_env_tool.py
  - tests/test_track_env_tool.py
  - tests/test_env_layer_boundaries.py
tasks:
  - Replace `tasks.py` with direct task-only storage and remove `track_exists()`.
  - Move optional task `track_id` existence validation into `scripts/env/domain/tasks.py` using `track_repo.get_track`.
  - Replace `tracks.py` with direct track-only storage and no sibling repo imports.
  - Replace `artifacts.py` with direct artifact-only storage and no track archived/existence checks.
  - Add `assert_supersedes_target_for_revision()` to artifact visibility domain.
  - Call the new domain helper from artifact service before artifact repo creation when supersedes_artifact_id is provided.
tests_to_add_or_run:
  - python3 -m pytest tests/test_task_env_tool.py tests/test_artifact_env_tool.py tests/test_track_env_tool.py -q
  - python3 -m pytest tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_active_object_repos_do_not_import_env_legacy_store -q
done_when:
  - `scripts/env/repos/{tasks,tracks,artifacts}.py` do not import `env_legacy_store`.
  - Object repos do not import sibling repos.
  - Task track context and artifact supersede cross-object checks live in domain logic.
  - Focused object behavior tests pass; full boundary test may require D3 if comments are checked in the same scan.
return_format:
  - changed files
  - behavior changes
  - verification output
  - risks or blockers
```

```yaml
id: I1
role: developer
agent_type: worker
goal: Integrate all completed packages, resolve cross-package failures, and collect final verification evidence.
dependencies:
  - D2
  - D3
  - D4
  - T3
owned_write_set:
  - scripts/env/repos/runtime_files.py
  - scripts/env/repos/comments.py
  - scripts/env/repos/tasks.py
  - scripts/env/repos/tracks.py
  - scripts/env/repos/artifacts.py
  - scripts/env/domain/comment_targets.py
  - scripts/env/domain/tasks.py
  - scripts/env/domain/artifact_visibility.py
  - scripts/env/services/comments.py
  - scripts/env/services/artifacts.py
  - buddyswitch/skills/shared/message-tool/SKILL.md
  - buddyswitch/skills/shared/comment-tool/SKILL.md
  - buddyswitch/skills/shared/track-tool/SKILL.md
  - buddyswitch/skills/shared/artifact-tool/SKILL.md
  - buddyswitch/skills/shared/task-tool/SKILL.md
  - buddyswitch/skills/shared/buddybox-tool/SKILL.md
  - tests/test_runtime_broker.py
  - tests/test_buddybox_env_tool.py
  - tests/test_runtime_skills.py
  - tests/test_env_layer_boundaries.py
  - tests/test_comment_env_tool.py
  - tests/test_task_env_tool.py
  - tests/test_artifact_env_tool.py
  - tests/test_track_env_tool.py
  - tests/test_parallel_contracts.py
forbidden_write_set:
  - buddyswitch/objects/**
  - buddyswitch/local/buddybox/**
  - scripts/env/domain/publication.py unless a verification failure proves a concrete defect
  - new workflow engines, plugin systems, event buses, or generic repository abstractions
read_context:
  - all package return summaries
  - docs/spec/2026-05-19-parallel-modular-architecture-completion-implementation-plan.md
tasks:
  - Run focused architecture verification and fix only concrete integration defects.
  - Run object behavior verification and fix only concrete integration defects.
  - Run runtime integration verification and fix only concrete integration defects.
  - Run the full suite.
  - Record exact command summaries for final implementation reporting.
tests_to_add_or_run:
  - python3 -m pytest tests/test_env_tool_semantic_contract.py tests/test_env_tool_router.py tests/test_env_layer_boundaries.py tests/test_repo_consistency.py tests/test_parallel_contracts.py tests/test_runtime_skills.py -q
  - python3 -m pytest tests/test_message_env_tool.py tests/test_comment_env_tool.py tests/test_buddybox_env_tool.py tests/test_task_env_tool.py tests/test_artifact_env_tool.py tests/test_track_env_tool.py -q
  - python3 -m pytest tests/test_runtime_broker.py tests/test_env_layer_end_to_end.py tests/test_turn_integration.py tests/test_env_tool_response_contract.py tests/test_runtime_tool_feedback.py -q
  - python3 -m pytest -q
done_when:
  - All verification commands pass.
  - No active runtime repo imports `env_legacy_store`.
  - Final evidence is collected with exact pytest summaries.
return_format:
  - changed files
  - integration fixes
  - exact verification output summaries
  - remaining risk
```

```yaml
id: R2
role: reviewer
agent_type: code-reviewer
goal: Targeted review of runtime storage boundaries, publication single-entry ownership, and verification evidence after integration.
dependencies:
  - I1
owned_write_set: []
forbidden_write_set:
  - '*'
read_context:
  - package summaries
  - integrated diff
  - tests/test_env_layer_boundaries.py
  - scripts/env/repos/**
  - scripts/env/domain/**
  - scripts/env/services/**
tasks:
  - Check active repos for forbidden `env_legacy_store` and sibling repo imports.
  - Check publication mutation writes remain centralized in `scripts/env/domain/publication.py`.
  - Check cross-object read rules are in domain modules, not repos.
  - Check behavior tests cover persisted state changes and no-mutation rejection paths before static guards.
tests_to_add_or_run:
  - Review verification evidence from I1; rerun focused commands only if evidence is missing or suspect.
done_when:
  - Findings are reported by severity.
  - Decision is either targeted pass or required corrections.
return_format:
  - findings by severity
  - targeted pass or fail
  - required corrections
```

```yaml
id: R1
role: reviewer
agent_type: code-reviewer
goal: Final acceptance review for the parallel modular architecture completion plan.
dependencies:
  - I1
  - R2
owned_write_set: []
forbidden_write_set:
  - '*'
read_context:
  - docs/spec/2026-05-19-parallel-modular-architecture-completion-implementation-plan.md
  - this parallel execution plan
  - integrated diff
  - test coverage matrix
  - I1 verification evidence
  - R2 targeted review result
tasks:
  - Verify every source done criterion is covered by code, tests, and evidence.
  - Verify package ownership boundaries were respected.
  - Verify final verification is complete and real.
  - Flag behavioral regressions, missing tests, and unresolved integration seams.
tests_to_add_or_run:
  - No code-modifying commands. Validate existing evidence; rerun only read-only verification if needed.
done_when:
  - Final decision is `accept` or `needs changes` with blocking reasons.
return_format:
  - findings by severity
  - decision
  - blocking reasons
  - follow-up checks
```

## Test Coverage Matrix
| Requirement | Behavior | Main Path Test | Boundary/Error Cases | Regression Risks | Owner |
| --- | --- | --- | --- | --- | --- |
| Full suite passes | All modular runtime changes integrate without regressions | `python3 -m pytest -q` | Focused architecture, object behavior, and runtime integration commands isolate failures before full suite | Hidden fixture or legacy coupling only appears in full suite | developer:I1 |
| Buddybox uses instance workspace root | Broker-routed write/read/list/delete operate under `instance_payload["workspace_dir"]/buddyswitch/local/buddybox/<buddy>` | `tests/test_runtime_broker.py::RuntimeBrokerTests::test_env_tool_buddybox_lifecycle_uses_instance_workspace_local_root` | Assert wrong runtime-root and state-root files do not exist | Reordering root selection moves product object state by mistake | developer:D1 |
| Shared skills use runtime discovery | Shared tool skills do not duplicate action catalogs or payload schemas | `tests/test_runtime_skills.py::RuntimeSkillsTests::test_shared_tool_skills_do_not_duplicate_runtime_action_catalogs` | Inactive runtime actions remain owned by `env.tools.contracts`, not shared skill prose | Adding a new action requires skill edits again | test:T1, developer:D2 |
| Message action growth avoids shared skill edits | `message-tool` points to runtime catalog, not `message.send` / `message.list` copies | Runtime skill catalog ownership test | Atomic shared-skill test requires `env.tool` and `context.get.tool_catalog` only | Shared guidance drifts from runtime contracts | test:T1, developer:D2 |
| Comment repo owns only comment storage | Comment repo persists comments directly and does not expose artifact revision-chain behavior | `tests/test_comment_env_tool.py::CommentEnvToolTests::test_artifact_section_revision_reference_must_belong_to_same_chain` | `test_comment_repo_owns_only_comment_storage`; invalid cross-chain comment mutates no comments or artifacts | Artifact revision logic remains hidden in repo | test:T2, developer:D3 |
| Active object repos do not import legacy storage | Task, track, artifact, and comment repos own direct JSON persistence | `tests/test_task_env_tool.py`, `tests/test_artifact_env_tool.py`, `tests/test_track_env_tool.py`, `tests/test_comment_env_tool.py` | `test_active_object_repos_do_not_import_env_legacy_store`; object repos do not import siblings | Monolithic cross-object behavior persists through repo proxies | test:T2, developer:D3, developer:D4 |
| Cross-object runtime rules live in domain modules | Task track context and artifact supersede checks read cross-object state in domain, not repo | Task track context read-only test; archived published artifact supersede rejection test | Rejection cases assert no new artifact and unchanged track state | Error classification drifts or repo regains cross-object authority | test:T2, developer:D4 |
| Track/artifact publication has one mutation domain entry point | `track.add_material` and `track.add_proof` publish through publication domain and atomically update track and artifact | Existing positive track publication tests with tightened artifact/track assertions | `test_track_artifact_publication_writes_only_live_in_publication_domain`; archived/rejected publication paths mutate nothing | Direct publication writes reappear in services or repos | test:T2, developer:I1, reviewer:R2 |
| Message/comment/buddybox independent loops | Focused tests for these modules run without track/artifact/task test modules | Subprocess proof in `tests/test_parallel_contracts.py` | Output excludes `tests/test_track_env_tool.py`, `tests/test_artifact_env_tool.py`, `tests/test_task_env_tool.py` | Test coupling masks modular regressions | test:T3 |
| Runtime contracts and feedback remain stable | Env.tool router, semantic contract, response contract, and feedback suites pass | Task 7 focused architecture and runtime integration commands | Runtime feedback tests preserve rejection shapes and permission boundaries | Moving checks between repo/domain changes host-visible responses | developer:I1, reviewer:R1 |

Coverage rules:
- Behavior proof comes before static scans for each boundary.
- Rejected writes snapshot or compare persisted state.
- Static scans are scoped to active runtime files, not docs.

## Review and Acceptance Gate
Final reviewer verifies:
- Source plan goals and done criteria are fully covered by packages D1, D2, D3, D4, T1, T2, T3, and I1.
- Work package dependencies and ownership constraints were followed.
- Test coverage matrix traces to source requirements, not implementation internals.
- Verification evidence is complete, exact, and relevant:
  - Focused architecture verification.
  - Object behavior verification.
  - Runtime integration verification.
  - Full suite.
- No unauthorized edits exist outside package-owned write sets.
- Active object repos do not import `env_legacy_store` or sibling repos.
- Cross-object runtime rules live only in domain modules.
- Publication mutation writes remain centralized in `scripts/env/domain/publication.py`.
- Shared tool skills rely on runtime discovery for action catalogs and payload details.

Targeted reviewer R2 is required because this plan changes shared runtime root selection, active object repo boundaries, and publication architecture guards.

Acceptance decision:
- `accept` only if I1 verification passes and R2 has no blocking findings.
- `needs changes` if any done criterion lacks behavior proof, final verification is missing, or ownership boundaries were violated.

## Subagent Prompts
### D1 Developer Prompt
```markdown
Role: developer
Mission:
- Deliver D1 with outcome: buddybox workspace-local files use the instance workspace_dir through broker-routed env.tool lifecycle operations.

Context:
- Source plan summary: close BuddySwitch first-phase modular runtime gaps; fix the known full-suite buddybox failure first.
- Dependencies complete: none.
- Read context:
  - docs/spec/2026-05-19-parallel-modular-architecture-completion-implementation-plan.md
  - scripts/env/repos/runtime_files.py
  - scripts/env/repos/buddybox_files.py
  - tests/test_runtime_broker.py
  - tests/test_buddybox_env_tool.py
  - tests/runtime_root_test_helper.py

Write boundaries:
- owned_write_set:
  - scripts/env/repos/runtime_files.py
  - tests/test_runtime_broker.py
  - tests/test_buddybox_env_tool.py
- forbidden_write_set:
  - scripts/env/repos/comments.py
  - scripts/env/repos/tasks.py
  - scripts/env/repos/tracks.py
  - scripts/env/repos/artifacts.py
  - buddyswitch/skills/shared/**

Execution requirements:
- Add the source Task 1 lifecycle test first and confirm focused failure.
- Change only workspace-local root selection; do not move product object roots.
- Keep the fix minimal.

Required verification:
- python3 -m pytest tests/test_runtime_broker.py::RuntimeBrokerTests::test_env_tool_buddybox_write_uses_instance_workspace_local_root tests/test_runtime_broker.py::RuntimeBrokerTests::test_env_tool_buddybox_lifecycle_uses_instance_workspace_local_root -q
- python3 -m pytest tests/test_runtime_broker.py::RuntimeBrokerTests::test_env_tool_buddybox_write_uses_instance_workspace_local_root tests/test_runtime_broker.py::RuntimeBrokerTests::test_env_tool_buddybox_lifecycle_uses_instance_workspace_local_root tests/test_buddybox_env_tool.py -q

Return format:
- Changed files
- Behavior changes
- Failing-before and passing-after verification output
- Risks or blockers
```

### T1 Test Prompt
```markdown
Role: test
Mission:
- Deliver requirement-first coverage for T1.

Context:
- Requirements:
  - Shared tool skills must use runtime discovery for action catalogs and payload details.
  - Adding a new message action must not require editing message-tool shared guidance.
- Related code and tests:
  - tests/test_runtime_skills.py
  - buddyswitch/skills/shared/*-tool/SKILL.md
  - scripts/env/tools/contracts.py

Write boundaries:
- owned_write_set:
  - tests/test_runtime_skills.py
- forbidden_write_set:
  - buddyswitch/skills/shared/**
  - scripts/env/**

Execution requirements:
- Replace operation-list assertions with runtime-discovery assertions.
- Keep tests about requirements, not private helper names.
- Capture expected failing output before D2.

Required verification:
- python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_shared_tool_skills_do_not_duplicate_runtime_action_catalogs tests/test_runtime_skills.py::RuntimeSkillsTests::test_message_comment_shared_tool_skills_stay_atomic -q

Return format:
- Added or changed tests
- Requirement-to-test mapping
- Verification output
- Remaining coverage risks
```

### T2 Test Prompt
```markdown
Role: test
Mission:
- Deliver requirement-first coverage for T2.

Context:
- Requirements:
  - Comment repo owns only comment storage.
  - Active object repos do not import env_legacy_store.
  - Cross-object rules live in domain modules.
  - Publication mutation has one domain entry point.
  - Behavior tests prove persisted changes and no-mutation rejections before static scans.
- Related code and tests:
  - tests/test_env_layer_boundaries.py
  - tests/test_comment_env_tool.py
  - tests/test_task_env_tool.py
  - tests/test_artifact_env_tool.py
  - tests/test_track_env_tool.py
  - scripts/env/repos/**
  - scripts/env/domain/**
  - scripts/env/services/**

Write boundaries:
- owned_write_set:
  - tests/test_env_layer_boundaries.py
  - tests/test_comment_env_tool.py
  - tests/test_task_env_tool.py
  - tests/test_artifact_env_tool.py
  - tests/test_track_env_tool.py
- forbidden_write_set:
  - scripts/env/**
  - buddyswitch/skills/shared/**
  - tests/test_runtime_skills.py
  - tests/test_parallel_contracts.py

Execution requirements:
- Add tests from source Tasks 3, 4, and 5.
- Assert durable state for success paths and unchanged persisted state for rejection paths.
- Scope static scans to active runtime files.

Required verification:
- python3 -m pytest tests/test_comment_env_tool.py::CommentEnvToolTests::test_artifact_section_revision_reference_must_belong_to_same_chain tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_comment_repo_owns_only_comment_storage -q
- python3 -m pytest tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_active_object_repos_do_not_import_env_legacy_store -q
- python3 -m pytest tests/test_track_env_tool.py tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_track_artifact_publication_writes_only_live_in_publication_domain -q

Return format:
- Added or changed tests
- Requirement-to-test mapping
- Verification output
- Remaining coverage risks
```

### T3 Test Prompt
```markdown
Role: test
Mission:
- Deliver independent focused-loop proof for T3.

Context:
- Requirements:
  - message/comment/buddybox tests run independently.
  - track/artifact/task test modules are not pulled into this focused loop.
- Related code and tests:
  - tests/test_parallel_contracts.py
  - tests/test_message_env_tool.py
  - tests/test_comment_env_tool.py
  - tests/test_buddybox_env_tool.py

Write boundaries:
- owned_write_set:
  - tests/test_parallel_contracts.py
- forbidden_write_set:
  - scripts/env/**
  - buddyswitch/skills/shared/**
  - tests/test_runtime_skills.py
  - tests/test_env_layer_boundaries.py
  - tests/test_comment_env_tool.py
  - tests/test_task_env_tool.py
  - tests/test_artifact_env_tool.py
  - tests/test_track_env_tool.py

Execution requirements:
- Add the subprocess proof from source Task 6.
- Keep it deterministic and scoped.

Required verification:
- python3 -m pytest tests/test_message_env_tool.py tests/test_comment_env_tool.py tests/test_buddybox_env_tool.py -q
- python3 -m pytest tests/test_parallel_contracts.py::ParallelContractsTests::test_message_comment_buddybox_focused_tests_run_as_independent_loop -q

Return format:
- Added or changed tests
- Requirement-to-test mapping
- Verification output
- Remaining coverage risks
```

### D2 Developer Prompt
```markdown
Role: developer
Mission:
- Deliver D2 with outcome: shared tool skills no longer duplicate runtime action catalogs or payload schemas.

Context:
- Source plan summary: shared tool skills must defer operation catalogs to runtime discovery.
- Dependencies complete: T1.
- Read context:
  - tests/test_runtime_skills.py
  - tests/test_repo_consistency.py
  - buddyswitch/skills/shared/*-tool/SKILL.md
  - scripts/env/tools/contracts.py

Write boundaries:
- owned_write_set:
  - buddyswitch/skills/shared/message-tool/SKILL.md
  - buddyswitch/skills/shared/comment-tool/SKILL.md
  - buddyswitch/skills/shared/track-tool/SKILL.md
  - buddyswitch/skills/shared/artifact-tool/SKILL.md
  - buddyswitch/skills/shared/task-tool/SKILL.md
  - buddyswitch/skills/shared/buddybox-tool/SKILL.md
- forbidden_write_set:
  - scripts/env/**
  - tests/**

Execution requirements:
- Remove copied operation lists and env.tool action-route copies.
- Keep tool-specific workflow notes concise.
- Use context.get.tool_catalog['<tool>'] and python3 scripts/turn_runtime.py status as authoritative discovery paths.

Required verification:
- python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py::RepoConsistencyTests::test_skill_and_contract_texts_do_not_copy_payload_field_or_schema_tables -q

Return format:
- Changed files
- Behavior changes
- Verification output
- Risks or blockers
```

### D3 Developer Prompt
```markdown
Role: developer
Mission:
- Deliver D3 with outcome: comments repo owns only comment JSON storage and artifact revision-chain checks live in domain logic.

Context:
- Source plan summary: object repos must not inherit hidden cross-object behavior through env_legacy_store.
- Dependencies complete: T2.
- Read context:
  - scripts/env/repos/messages.py
  - scripts/env/repos/comments.py
  - scripts/env/domain/comment_targets.py
  - scripts/env/services/comments.py
  - tests/test_comment_env_tool.py
  - tests/test_env_layer_boundaries.py

Write boundaries:
- owned_write_set:
  - scripts/env/repos/comments.py
  - scripts/env/domain/comment_targets.py
  - scripts/env/services/comments.py
- forbidden_write_set:
  - scripts/env/repos/tasks.py
  - scripts/env/repos/tracks.py
  - scripts/env/repos/artifacts.py
  - scripts/env/domain/tasks.py
  - scripts/env/domain/artifact_visibility.py
  - scripts/env/domain/publication.py
  - scripts/env/services/tasks.py
  - scripts/env/services/artifacts.py
  - scripts/env/services/tracks.py
  - tests/**

Execution requirements:
- Implement direct comment storage through runtime_files.
- Preserve service-facing signatures.
- Move revision-chain traversal to env.domain.comment_targets.
- Do not add compatibility wrappers.

Required verification:
- python3 -m pytest tests/test_comment_env_tool.py tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_comment_repo_owns_only_comment_storage -q

Return format:
- Changed files
- Behavior changes
- Verification output
- Risks or blockers
```

### D4 Developer Prompt
```markdown
Role: developer
Mission:
- Deliver D4 with outcome: task, track, and artifact repos are direct object repos, with cross-object checks in domain modules.

Context:
- Source plan summary: active object repos must stop proxying through env_legacy_store.
- Dependencies complete: T2.
- Read context:
  - scripts/env/repos/messages.py
  - scripts/env/repos/tasks.py
  - scripts/env/repos/tracks.py
  - scripts/env/repos/artifacts.py
  - scripts/env/domain/tasks.py
  - scripts/env/domain/artifact_visibility.py
  - scripts/env/services/artifacts.py
  - scripts/env/domain/publication.py
  - tests/test_task_env_tool.py
  - tests/test_artifact_env_tool.py
  - tests/test_track_env_tool.py

Write boundaries:
- owned_write_set:
  - scripts/env/repos/tasks.py
  - scripts/env/repos/tracks.py
  - scripts/env/repos/artifacts.py
  - scripts/env/domain/tasks.py
  - scripts/env/domain/artifact_visibility.py
  - scripts/env/services/artifacts.py
- forbidden_write_set:
  - scripts/env/repos/comments.py
  - scripts/env/domain/comment_targets.py
  - scripts/env/services/comments.py
  - scripts/env/domain/publication.py
  - scripts/env/services/tracks.py
  - scripts/env/services/tasks.py
  - tests/**
  - buddyswitch/skills/shared/**

Execution requirements:
- Replace legacy repo proxies with direct runtime_files-backed JSON persistence.
- Keep repos object-only; no sibling repo imports.
- Move task track existence validation and artifact supersede publication checks to domain modules.
- Preserve existing service response classification for supersede scope failures.

Required verification:
- python3 -m pytest tests/test_task_env_tool.py tests/test_artifact_env_tool.py tests/test_track_env_tool.py -q
- python3 -m pytest tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_active_object_repos_do_not_import_env_legacy_store -q

Return format:
- Changed files
- Behavior changes
- Verification output
- Risks or blockers
```

### I1 Integration Developer Prompt
```markdown
Role: developer
Mission:
- Integrate D2, D3, D4, and T3; resolve only concrete integration failures; collect final verification evidence.

Context:
- Source goals and done criteria: first-phase parallel modular architecture completion with full suite passing.
- Dependencies complete: D2, D3, D4, T3.
- Read context:
  - package return summaries
  - integrated diff
  - docs/spec/2026-05-19-parallel-modular-architecture-completion-implementation-plan.md

Write boundaries:
- owned_write_set:
  - all completed package write sets, only when required by verification failures
- forbidden_write_set:
  - buddyswitch/objects/**
  - buddyswitch/local/buddybox/**
  - new workflow engines, plugin systems, event buses, or generic repository abstractions

Execution requirements:
- Run focused commands before full suite.
- Fix root causes only within existing package surfaces.
- Record exact pytest summaries.

Required verification:
- python3 -m pytest tests/test_env_tool_semantic_contract.py tests/test_env_tool_router.py tests/test_env_layer_boundaries.py tests/test_repo_consistency.py tests/test_parallel_contracts.py tests/test_runtime_skills.py -q
- python3 -m pytest tests/test_message_env_tool.py tests/test_comment_env_tool.py tests/test_buddybox_env_tool.py tests/test_task_env_tool.py tests/test_artifact_env_tool.py tests/test_track_env_tool.py -q
- python3 -m pytest tests/test_runtime_broker.py tests/test_env_layer_end_to_end.py tests/test_turn_integration.py tests/test_env_tool_response_contract.py tests/test_runtime_tool_feedback.py -q
- python3 -m pytest -q

Return format:
- Changed files
- Integration fixes
- Verification output
- Remaining risk
```

### R2 Targeted Reviewer Prompt
```markdown
Role: reviewer
Mission:
- Review runtime boundary risk for R2 before final acceptance.

Trigger reason:
- Shared root selection, active object repo ownership, and publication-entry guards changed.

Context:
- Related package ids: D1, D3, D4, I1
- Related files:
  - scripts/env/repos/runtime_files.py
  - scripts/env/repos/comments.py
  - scripts/env/repos/tasks.py
  - scripts/env/repos/tracks.py
  - scripts/env/repos/artifacts.py
  - scripts/env/domain/comment_targets.py
  - scripts/env/domain/tasks.py
  - scripts/env/domain/artifact_visibility.py
  - scripts/env/domain/publication.py
  - scripts/env/services/comments.py
  - scripts/env/services/artifacts.py
  - tests/test_env_layer_boundaries.py

Write boundaries:
- owned_write_set:
  - none
- forbidden_write_set:
  - *

Execution requirements:
- Focus only on runtime boundary and publication ownership risk.
- Validate behavior proof exists before static scans.
- Avoid broad style-only feedback.

Required verification:
- Confirm I1 verification evidence quality and relevance.

Return format:
- Findings by severity
- Targeted pass or fail
- Required corrections
```

### R1 Final Reviewer Prompt
```markdown
Role: reviewer
Mission:
- Run final acceptance review for the parallel modular architecture completion plan after integration and targeted review.

Context:
- Source goals and done criteria: BuddySwitch first-phase parallel modular runtime requirements complete.
- Integrated diff or file list: provided by I1.
- Test coverage matrix: this plan.
- Verification evidence: provided by I1.
- Targeted runtime-boundary review: provided by R2.

Write boundaries:
- owned_write_set:
  - none
- forbidden_write_set:
  - *

Execution requirements:
- Output findings first and order by severity.
- Validate requirement coverage and ownership compliance.
- Flag regression risks, test gaps, and unresolved conflicts.
- Do not modify code.

Required verification:
- Confirm verification evidence quality and relevance.
- Confirm review and acceptance gate status.

Return format:
- Findings by severity (`high`, `medium`, `low`)
- Decision (`accept` or `needs changes`)
- Blocking reasons
- Follow-up checks
```
