# Repo HEAD Host Loop Cleanup Development Plan

> **For implementation in this worktree only:** `/Users/chen/Dev/buddyswitch/.worktrees/codex-host-loop-contract-cleanup-plan`

**Goal:** Fix the remaining repo-HEAD host-loop drift without reopening the already-completed public runtime cutover.

**Architecture:** Preserve the current public repo contract:

`resolve_context -> host run -> persist_skill_result -> refreshed_context`

This plan is for repo `HEAD` only. It does not treat older runtime-workspace logs as the source of truth.

**Tech Stack:** Python runtime/docs/tests, plain JS context panel, markdown contract docs, `pytest`

---

## Scope

This plan covers:

- fixing active host prompt guidance for `refreshed_context.ok` / `E_RUNTIME_REFRESH_CONTEXT`
- aligning host prompt wording so `Recommended` renders from canonical `recommended_switch`
- fixing the `switch.buddy_id` vs `switch.buddy` workspace projection bug
- fixing track command panel behavior so synthetic test guidance does not replace canonical recommendation
- adding focused regression coverage for those repo-HEAD behaviors

This plan does not cover:

- public runtime cutover or `prepare-execution` removal work
- market fallback contract cleanup
- restoring `sub_task` into the active runtime contract
- launcher/workspace sync or historical runtime-workspace forensics
- broad packet-era debt cleanup outside touched files

## File Map

**Primary modify**

- `tools/launcher/assets/runtime-AGENTS.md`
- `.codex/agents/router.toml`
- `scripts/runtime_store/projections.py`
- `framework/console/app.js`
- `tests/test_repo_consistency.py`
- `tests/test_switch_runtime.py`
- `tests/test_switch_integration.py`

**Likely add**

- `tests/test_console_app_contract.py`

**Secondary only if touched and kept small**

- `scripts/switch_runtime.py`
- `framework/docs/architecture-overview.md`
- `framework/docs/skill-architecture-best-practices.md`

## Task 0: Freeze Repo-HEAD Regressions First

**Intent:** Put the remaining repo-HEAD issues under test before changing behavior.

**Files**

- Add: `tests/test_console_app_contract.py`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_switch_runtime.py`

**Coverage to add**

- `runtime-AGENTS.md` requires `check refreshed_context.ok`
- `runtime-AGENTS.md` requires rerun-`resolve` on `E_RUNTIME_REFRESH_CONTEXT`
- `.codex/agents/router.toml` requires the same refresh-error branch
- `runtime-AGENTS.md` renders `Recommended` from canonical `recommended_switch`
- run-audit projection handles `switch.buddy_id` without requiring legacy `switch.buddy`
- track command derivation keeps canonical recommendation visible even when test hints exist

**Verification**

- `python3 -m pytest tests/test_repo_consistency.py tests/test_switch_runtime.py -q`

## Task 1: Fix Active Host Prompt Drift

**Intent:** Align the active runtime workspace prompt surfaces with the already-canonical README/spec contract.

**Files**

- Modify: `tools/launcher/assets/runtime-AGENTS.md`
- Modify: `.codex/agents/router.toml`
- Test: `tests/test_repo_consistency.py`

**Change**

- Replace “continue from refreshed_context after a successful persist” with:
  - check `refreshed_context.ok`
  - continue only when true
  - rerun `resolve` on `E_RUNTIME_REFRESH_CONTEXT`
- Replace host-side `Recommended` derivation wording with canonical `receipt.recommended_switch`
- Keep wording anchored to the **current public repo contract**

**Verification**

- `python3 -m pytest tests/test_repo_consistency.py -q -k 'runtime_agents_doc_uses_context_then_persist_flow or readme_and_switch_spec_describe_refresh_context_fallback'`

## Task 2: Fix The `buddy_id` Projection Bug

**Intent:** Make workspace projection reflect current run-audit shape.

**Files**

- Modify: `scripts/runtime_store/projections.py`
- Modify: `tests/test_switch_runtime.py`

**Change**

- Read `switch.buddy_id` first in `scan_run_audits()`
- Fall back to legacy `switch.buddy` only for compatibility
- Update the existing run-audit projection test to use new-style payload shape

**Verification**

- `python3 -m pytest tests/test_switch_runtime.py -q -k 'scan_run_audits'`

## Task 3: Fix Track Command Panel Recommendation Behavior

**Intent:** Stop the track command panel from silently replacing canonical recommendation with synthetic test guidance.

**Files**

- Modify: `framework/console/app.js`
- Add or modify: `tests/test_console_app_contract.py`

**Change**

- Preserve persisted `recommended_switch` as the visible `Recommended`
- Keep any `switch test -> ...` suggestion as a secondary hint, not a replacement recommendation
- Scope this fix to track-level command generation; do not rewrite unrelated console panels

**Verification**

- `python3 -m pytest tests/test_console_app_contract.py -q`

## Task 4: Opportunistic Cleanup Only If The Diff Naturally Touches It

**Intent:** Remove nearby repo debt without reopening the cutover scope.

**Files**

- Optional modify: `scripts/switch_runtime.py`
- Optional modify: secondary docs listed above

**Change**

- If `scripts/switch_runtime.py` is already being edited for a necessary adjacent fix, remove obviously retired helpers such as `_legacy_resolve_switch`
- If secondary docs are directly contradicted by touched behavior, align them narrowly
- Do not add a standalone “packet-era sweep” to this batch

**Verification**

- Run only the focused tests impacted by the touched file set

## Execution Order

1. Task 0: freeze repo-HEAD regressions first
2. Task 1: fix active host prompt drift
3. Task 2: fix the `buddy_id` projection bug
4. Task 3: fix track command panel recommendation behavior
5. Task 4 only if the primary implementation naturally touches those files
6. Run focused tests after each task
7. Run final combined verification and scope check

## Final Verification Gate

- `python3 -m pytest tests/test_console_app_contract.py tests/test_switch_runtime.py tests/test_repo_consistency.py tests/test_switch_integration.py -q`
- `git -C /Users/chen/Dev/buddyswitch/.worktrees/codex-host-loop-contract-cleanup-plan diff --name-only`

Expected:

- active host prompts include the refresh-error branch
- active host prompts treat `recommended_switch` as canonical render data
- workspace projection reports buddy correctly from new-style run audits
- track command panel no longer overrides canonical recommendation with synthetic test command
- diff stays inside the declared repo-only scope

## Deferred From This Batch

These are acknowledged but intentionally not the main execution target:

- full packet-era debt purge from `scripts/switch_runtime.py`
- stale historical planning docs that still mention `prepare-execution`
- market fallback doc cleanup
- `sub_task` contract expansion
- launcher/workspace sync work
