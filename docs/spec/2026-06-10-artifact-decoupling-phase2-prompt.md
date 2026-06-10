# Artifact Decoupling Phase 2 Execution Prompt

Use this prompt in the `artifacts` worktree:

```text
Continue in /Users/chen/Dev/buddyswitch/.worktrees/artifacts.

Objective:
Execute the Artifact Decoupling Rebuild plans end to end:
- docs/spec/2026-06-10-artifact-decoupling-test-plan.md
- docs/spec/2026-06-10-artifact-decoupling-development-plan.md

Rules:
1. Follow AGENTS.md and SHARP: solve the current bottleneck, use the shortest validated loop,
   avoid speculative abstraction, replace stale structure directly, and verify before claiming done.
2. Use TDD for behavior changes. Write the failing test first, run it, confirm the expected failure,
   implement the smallest direct code change, then rerun the focused test.
3. Rebuild forward. Do not keep old and new Artifact/Track publication behavior side by side.
4. Keep `track.add_material` and `track.add_proof` as actor-facing action names, but make them
   Track-side Artifact relation writes. They must not mutate Artifact content or lifecycle.
5. Remove live `published_to_track`, Artifact publication `status`, Track `shared_materials`,
   Track `close_proof`, and old `publication.py` behavior from active runtime contracts.
6. Preserve capabilities: create/read/list/update/attach Artifacts, Track relation sharing,
   collaborator readability, relation roles for material/proof, proof timeline evidence, and
   Artifact-local revision lineage.
7. Do not implement notification center work, `artifact.shared` handler registration, notification
   tools, or Track-native comment rebuild work in this lane.
8. Be careful with test resources. Use runless focused tests first. Before broad verification, run:
   ps -axo pid,ppid,pgid,command | rg 'buddyswitch-codex|runtime_broker|app-server|fake Codex|Chrom(e|ium)|Playwright' || true
   If new persistent processes appear after a test command, stop and fix cleanup before scaling up.

Execution loop:
1. Start with Task 1 in the development plan.
2. For each task:
   - update or add the specified failing tests;
   - run the exact focused command and confirm expected failure;
   - implement only the smallest direct code change for that task;
   - rerun the focused command until green;
   - remove stale old-path tests and code in the same task.
3. Keep docs/spec plans aligned only if implementation discovers a real contradiction.
4. After all tasks pass focused verification, run:
   python -m unittest tests.test_env_store_v2 tests.test_track_env_tool tests.test_artifact_env_tool
   python -m unittest tests.test_context_binding_env_tool tests.test_env_tool_response_contract tests.test_env_layer_boundaries tests.test_repo_consistency tests.test_runtime_skills
   python -m unittest tests.test_env_layer_end_to_end tests.test_turn_integration
5. Run the residual process check.
6. Run:
   python -m unittest discover tests
7. Run the residual process check again.
8. Review the final diff against the memo acceptance criteria and the development plan review
   checklist. Fix any gap before reporting completion.

Completion requires:
- focused and broad verification pass;
- final review passes;
- no live old publication path remains;
- no new persistent test-owned processes remain.

If a command repeatedly fails for an environmental reason, capture the exact command and output,
identify whether the failure is unrelated to this rebuild, and ask the user before narrowing the
definition of done.
```

## Self-Review

- The prompt is short enough to execute directly and points to the two authoritative Phase 1 plans.
- It preserves the full rebuild scope and does not authorize compatibility dual paths.
- It includes the resource lifecycle check before and after broad verification.
- It defines completion as tests plus review, matching Phase 2 and Phase 3.
