# Repo HEAD Host Loop Cleanup Action

## Status

- Date: 2026-04-22
- Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/codex-host-loop-contract-cleanup-plan`
- Source of truth: repo `/Users/chen/Dev/buddyswitch` at current `HEAD`
- Review method: repo inspection + reviewer sub-agents

## Goal

Tighten the remaining repo-HEAD drift around the current public BuddySwitch contract:

`resolve_context -> host run -> persist_skill_result -> refreshed_context`

This is a repo-only cleanup pass.

It is **not** a broad runtime cutover pass, and it is **not** based on older runtime workspace logs.

## Repo Boundary

At current repo `HEAD`, the public runtime surface is `resolve` + `persist`.

That is enough to reject old `prepare-execution` logs as evidence for the **current public repo contract**.

It is **not** enough to claim:

- that old packet-era strings are fully absent from the tree
- that `resolve` is read-only inside launcher runtime workspaces
- that every historical runtime workspace or log was wrong for its own commit

## Bottleneck

The broad cutover is already done in repo `HEAD`.

The remaining repo-HEAD problems are narrower:

1. active host prompts omit the `refreshed_context.ok` / `E_RUNTIME_REFRESH_CONTEXT` branch
2. runtime writes `switch.buddy_id`, but workspace projection still reads `switch.buddy`
3. the track command panel can override canonical recommendation with synthetic `switch test -> ...`

Everything else is lower-priority debt or already fixed in the active public contract.

## In Scope

### 1. Fix active host prompt drift

Primary surfaces:

- `tools/launcher/assets/runtime-AGENTS.md`
- `.codex/agents/router.toml`

Required outcome:

- host guidance says to check `refreshed_context.ok`
- host guidance says to rerun `resolve` on `E_RUNTIME_REFRESH_CONTEXT`
- `Recommended` is described as canonical `recommended_switch`, not host-side recomputation

### 2. Fix the run-audit projection bug

Primary surface:

- `scripts/runtime_store/projections.py`

Required outcome:

- projection reads `switch.buddy_id` first
- projection falls back to legacy `switch.buddy` only for compatibility
- tests cover new-style run audits with `switch.buddy_id` and no `switch.buddy`

### 3. Fix track command panel recommendation behavior

Primary surface:

- `framework/console/app.js`

Required outcome:

- canonical `recommended_switch` stays the visible `Recommended`
- track-specific test guidance does not silently replace canonical recommendation
- behavior coverage exists for this command derivation path

## Out of Scope For This Batch

- redoing the public runtime cutover
- removing `prepare-execution` from history docs or every old planning note
- market no-silent-fallback doc cleanup
- restoring `sub_task` to the active runtime contract
- launcher/workspace sync or stale workspace forensics

## Secondary Debt

These items are real repo debt, but not the main execution target for this batch:

- `_legacy_resolve_switch`
- `_build_run_instructions`
- internal `run_instructions_by_skill` computation

If touching `scripts/switch_runtime.py` becomes necessary for a nearby fix, clean them then.
Otherwise do not expand scope.

## Verification

Minimum proof for this batch:

1. repo-consistency tests cover the refresh-error branch in active host prompts
2. projection tests cover `switch.buddy_id`
3. console behavior tests cover canonical recommendation vs synthetic track test hints
4. current public runtime tests still prove:
   - public CLI is `resolve,persist`
   - persist returns `receipt + refreshed_context`
   - refresh failure can happen with `ok: true` + `refreshed_context.ok: false`

## One-Sentence Direction

Treat repo `HEAD` as the only source of truth, fix the live host-prompt drift, fix the `buddy_id` projection bug, stop the track panel from overriding canonical recommendation, and keep packet-era cleanup as secondary debt instead of turning this back into a broad cutover project.
