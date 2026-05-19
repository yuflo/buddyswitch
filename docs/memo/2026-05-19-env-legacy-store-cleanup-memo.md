# Env Legacy Store Cleanup Memo

Date: 2026-05-19
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/track-artifact-pm-runtime-repair`
Status: follow-up cleanup memo only. Current parallel modular architecture first-phase acceptance is not blocked by this cleanup.

## Summary

BuddySwitch now satisfies the first-phase parallel modular architecture requirements from
`docs/memo/buddyswitch-parallel-modular-architecture.md`.

The remaining cleanup is narrower: remove residual active-runtime dependence on
`scripts/env_legacy_store.py` where it still acts as a read/helper shortcut for context,
source-ref, artifact visibility, and evidence surfaces.

This should be a separate cleanup because the core parallel requirements are already verified:

- shared tool SKILL files no longer copy action catalogs;
- `message` / `comment` / `buddybox` tests run independently;
- object repos no longer import `env_legacy_store`;
- `track/artifact` publication remains routed through one domain entry point;
- full suite passes.

## Current Verified Baseline

Current verification in this worktree:

```text
python3 -m pytest tests/test_runtime_broker.py::RuntimeBrokerTests::test_env_tool_buddybox_write_uses_instance_workspace_local_root -q
1 passed

python3 -m pytest tests/test_runtime_skills.py tests/test_env_layer_boundaries.py tests/test_repo_consistency.py tests/test_parallel_contracts.py -q
38 passed, 79 subtests passed

python3 -m pytest tests/test_message_env_tool.py tests/test_comment_env_tool.py tests/test_buddybox_env_tool.py -q
40 passed, 25 subtests passed

python3 -m pytest -q
477 passed, 1 skipped, 395 subtests passed
```

## Residual Legacy Dependence

Active runtime files still importing `env_legacy_store`:

```text
scripts/env/services/context.py
scripts/env/services/source_refs.py
scripts/env/services/artifact_visibility.py
scripts/env/services/evidence.py
```

These are not currently blocking first-phase parallel acceptance because object repos and core
publication/domain boundaries are already protected. They are still worth cleaning because they keep
runtime reads and validation logic tied to the old monolithic object-store module.

Tests still import `env_legacy_store` heavily for fixture setup and state assertions. That is less
urgent than active runtime cleanup. Fixture cleanup should happen after runtime cleanup, not before.

## Cleanup Goal

Make active runtime services stop importing `env_legacy_store`.

Preferred final shape:

```text
Service -> Domain / Object Repo / File Repo -> runtime_files
```

Allowed during cleanup:

- tests may continue using `env_legacy_store` as fixture setup until a later fixture cleanup;
- `scripts/env_store.py` may remain only for runtime-root helpers that are not object APIs;
- `scripts/env_legacy_store.py` may remain as a non-runtime test fixture helper until tests are migrated.

Not allowed:

- adding a generic object framework;
- keeping active-runtime compatibility wrappers or dual paths;
- reintroducing object repo sibling imports;
- moving cross-object decisions back into services;
- weakening existing boundary tests;
- changing tool semantics through prose-only docs.

## Suggested Work Order

### 1. `source_refs` cleanup

Move source ref ID validation and artifact readability checks off `env_legacy_store`.

Likely target:

- `scripts/env/services/source_refs.py`

Use:

- `scripts/env/repos/runtime_files.py` for `require_id`;
- `scripts/env/repos/artifacts.py` for artifact reads;
- `scripts/env/domain/artifact_visibility.py` for readability decisions when needed.

Verification:

```bash
python3 -m pytest tests/test_artifact_env_tool.py tests/test_buddybox_env_tool.py tests/test_runtime_tool_feedback.py -q
```

### 2. `artifact_visibility` service cleanup

There is both:

- `scripts/env/domain/artifact_visibility.py`
- `scripts/env/services/artifact_visibility.py`

Replace active callers so artifact visibility decisions go directly through the domain module.
Do not keep a service-level compatibility import or dual entry point.

Likely target:

- `scripts/env/services/artifact_visibility.py`
- callers that still import it, if any.

Verification:

```bash
python3 -m pytest tests/test_artifact_env_tool.py tests/test_track_env_tool.py tests/test_comment_env_tool.py -q
```

### 3. `context` service cleanup

`context.get` / `context.summarize` should read runtime state through object repos instead of
`env_legacy_store`.

Likely target:

- `scripts/env/services/context.py`

Use:

- `scripts/env/repos/tracks.py`
- `scripts/env/repos/tasks.py`
- `scripts/env/repos/artifacts.py`
- `scripts/env/repos/comments.py` if comments are surfaced through context.

Verification:

```bash
python3 -m pytest tests/test_context_binding_env_tool.py tests/test_host_decision_surface_product_mode.py tests/test_turn_integration.py -q
```

### 4. `evidence` service cleanup

Evidence should read artifact targets through artifact repo/domain helpers, not the legacy store.

Likely target:

- `scripts/env/services/evidence.py`

Use:

- `scripts/env/repos/artifacts.py`
- `scripts/env/repos/runtime_files.py` for timestamps if needed.

Verification:

```bash
python3 -m pytest tests/test_evidence_env_tool.py tests/test_market_browser_evidence.py -q
```

### 5. Add active-runtime legacy import guard

After the four active service imports are removed, add a boundary test that prevents new active
runtime imports of `env_legacy_store`.

Suggested assertion:

```text
scripts/env/services/** and scripts/env/domain/** must not import env_legacy_store.
scripts/env/repos/** must not import env_legacy_store.
tests/** may still import env_legacy_store until fixture cleanup.
```

Likely target:

- `tests/test_env_layer_boundaries.py`
- `tests/test_repo_consistency.py`

Verification:

```bash
python3 -m pytest tests/test_env_layer_boundaries.py tests/test_repo_consistency.py -q
```

### 6. Optional later test fixture cleanup

Only after active runtime cleanup lands, consider replacing test fixture setup imports of
`env_legacy_store` with focused repo/domain fixture helpers.

This is lower priority because tests can use setup helpers without affecting runtime modularity.
Do it only if fixture reliance starts hiding production boundary regressions.

## Acceptance Criteria

Cleanup is done when:

1. `rg -n "import env_legacy_store|from env_legacy_store import" scripts/env/services scripts/env/domain scripts/env/repos scripts/env/tools` returns no imports.
2. Object repo sibling import tests still pass.
3. Tool contract / catalog / dispatch / semantics tests still pass.
4. `track/artifact` publication tests still prove one domain entry point.
5. Context, evidence, artifact, track, comment, buddybox, and message focused tests pass.
6. Full suite passes.

Final verification command:

```bash
python3 -m pytest -q
```

## Why This Is Separate

This cleanup should not be mixed with the completed parallel-architecture acceptance.

The current bottleneck has moved: first-phase parallel development is now verified. The next useful
improvement is reducing legacy read/helper coupling in active services so future runtime work has
fewer hidden dependencies.
