# Framework Docs Cleanup Review Memo

Date: 2026-05-15
Updated: 2026-05-16
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem`
Status: handoff memo only; this memo update does not execute the active cleanup.

## Decision

Delete `framework/docs/` as an active documentation layer in a future implementation task.

This is a forward cleanup, not a compatibility migration:

- Do not keep `framework/docs/README.md` as a redirect.
- Do not keep an empty `framework/docs/` directory.
- Do not move the files to `legacy-docs/`, `archive/`, or another active path.
- Do not preserve dual documentation paths.
- Do not keep `framework/docs/` only because historical `docs/memo/**` or `docs/spec/**` files mention it.

Move only still-actionable rules into their owning source, then delete the whole directory.

## Purpose

This memo records the review of whether `framework/docs/` should continue to exist as an active documentation surface, especially for:

- skill-related runtime guidance
- test/runtime-contract-related documentation
- architecture and development-convention prose
- historical cleanup and repo simplification

The user rejected direct cleanup during the original review pass. This document is the handoff artifact for a later implementation task.

## Current Bottleneck

`framework/docs/` has become a second prose contract layer. Its active "usage" is mostly references from README, skill files, and tests that read prose docs for expected words. That is not a strong source of truth.

The actual runtime and skill contracts already live in stronger owners:

- `README.md`
- root `AGENTS.md`
- `buddyswitch/skills/**/SKILL.md`
- `scripts/env/tools/contracts.py`
- `scripts/env/tools/semantics.py`
- `scripts/runtime_kernel/protocol.py`
- `scripts/runtime_kernel/dispatcher.py`
- `framework/contracts/*.json`
- `framework/contracts/{pm,design,dev,market,test}.md`
- behavior tests under `tests/`

Keeping `framework/docs/` creates maintenance drag because the same runtime or skill contract can drift across prose docs, skill files, code, JSON contract files, and tests.

## Confirmed Discussion Consensus

1. `framework/docs/` should not be polished or retained as an active surface.
2. Architecture and development-convention prose under `framework/docs/` is not doing enough real work to justify keeping it.
3. No compatibility retention: no redirects, archive copy, legacy path, empty folder, or replacement framework-doc layer.
4. Historical memo/spec references are not a reason to preserve active docs. Historical cleanup can be a separate task if it becomes noisy.
5. Directly deleting the directory first would break current tests and leave dead skill/README links, so the future task must remove active references and replace prose-doc tests before deleting the directory.
6. The cleanup should not redesign runtime behavior, env tools, launcher behavior, or JSON object shapes.
7. Forward speed matters: retire the stale surface decisively so future runtime iteration only updates canonical owners.

## Current Repo Facts

The worktree currently has 11 files under `framework/docs/`:

- `architecture-overview.md`
- `artifacts-runs-git-policy.md`
- `browser-cockpit.md`
- `buddyswitch-development-constitution.md`
- `interface-spec.md`
- `multi-codex-worktree-guide.md`
- `runtime-broker-v2-runbook.md`
- `skill-architecture-best-practices.md`
- `skill-runtime-shared-rules.md`
- `track-registry.md`
- `turn-runtime-spec.md`

Active references found:

- `README.md` points to:
  - `framework/docs/architecture-overview.md`
  - `framework/docs/turn-runtime-spec.md`
  - `framework/docs/skill-runtime-shared-rules.md`
  - `framework/docs/track-registry.md`
  - `framework/docs/interface-spec.md`
- Active skills reference `framework/docs/browser-cockpit.md` or `framework/docs/skill-runtime-shared-rules.md`:
  - `buddyswitch/skills/market/pmf-recon/SKILL.md`
  - `buddyswitch/skills/market/positioning-copy/SKILL.md`
  - `buddyswitch/skills/market/research-scan/SKILL.md`
  - `buddyswitch/skills/market/launch-prep/SKILL.md`
  - `buddyswitch/skills/market/customer-discovery/SKILL.md`
  - `buddyswitch/skills/market/channel-discovery/SKILL.md`
  - `buddyswitch/skills/pm/write-prd/SKILL.md`
  - `buddyswitch/skills/design/shape-prototype/SKILL.md`
  - `buddyswitch/skills/dev/implement-task/SKILL.md`
  - `buddyswitch/skills/dev/skill-creator-importer/SKILL.md`
  - `buddyswitch/skills/test/smoke-test/SKILL.md`
- Tests directly read prose docs:
  - `tests/test_repo_consistency.py` reads `framework/docs/turn-runtime-spec.md`
  - `tests/test_repo_consistency.py` reads `framework/docs/runtime-broker-v2-runbook.md`
  - `tests/test_parallel_contracts.py` reads `framework/docs/interface-spec.md`
- `framework/docs/skill-architecture-best-practices.md` references other docs in the same folder.

Additional stale active-surface wording exists:

- market skills still say canonical outputs remain `task/artifact/run objects`.
- skill files and `scripts/skill_creator_importer.py` still contain old "current buddy run" / persist-oriented wording.
- importer tests and fixtures still assert or contain some of that older wording.

Review verification on 2026-05-16:

```bash
python3 -m pytest -q tests/test_repo_consistency.py tests/test_parallel_contracts.py tests/test_skill_creator_importer.py
# 34 passed, 36 subtests passed

python3 -m pytest -q
# 399 passed, 436 subtests passed
```

These tests prove the current repo is not broken before cleanup. They do not justify keeping `framework/docs/`.

## Disposition By File

| File | Future treatment | Rule movement |
| --- | --- | --- |
| `framework/docs/architecture-overview.md` | Delete | Keep only the concise runtime model already present in `README.md`; canonical behavior lives in code, JSON contracts, and tests. |
| `framework/docs/turn-runtime-spec.md` | Delete | `README.md` keeps the runless loop; broker/runtime behavior is tested through `scripts/runtime_kernel/**`, env tools, and repo consistency tests. |
| `framework/docs/interface-spec.md` | Delete | Console projection contract lives in `framework/contracts/workspace-projection.json`; runtime tool surface lives in env tool contracts/tests. |
| `framework/docs/runtime-broker-v2-runbook.md` | Delete | `env.tool`, `ping`, and `status` are broker code/test concerns, not prose-doc assertions. |
| `framework/docs/track-registry.md` | Delete | Track/task/artifact/handoff fields are owned by env services, object tests, and `workspace-projection.json`. |
| `framework/docs/skill-runtime-shared-rules.md` | Delete | Inline current runless closing/output rules into active skills and `scripts/skill_creator_importer.py`. |
| `framework/docs/skill-architecture-best-practices.md` | Delete | Skill package and materialization contracts are owned by `buddyswitch/manifest.toml`, `scripts/runtime_agents.py`, active skills, and tests. |
| `framework/docs/browser-cockpit.md` | Delete | Inline only the necessary browser-native market rules into market skills and keep role boundary in `framework/contracts/market.md`. |
| `framework/docs/artifacts-runs-git-policy.md` | Delete | Do not create a replacement policy doc; keep minimum artifact/buddybox boundary in `AGENTS.md`, role contracts, and relevant skills. |
| `framework/docs/buddyswitch-development-constitution.md` | Delete | Root `AGENTS.md` already carries SHARP/testing-bound execution guidance; do not copy the long constitution elsewhere. |
| `framework/docs/multi-codex-worktree-guide.md` | Delete | No migration required for this cleanup. If worktree operating rules become a current bottleneck later, add a separate short root rule then. |

## Canonical Owners After Cleanup

- `README.md`: concise entry point, runless runtime loop, canonical source pointers, focused verification commands.
- `AGENTS.md`: SHARP execution guidance, verification rule, key paths, and the minimum "use env tools; do not edit runtime state paths directly" rule.
- `buddyswitch/skills/**/SKILL.md`: skill-specific behavior and only the runtime rules the skill actually needs.
- `scripts/skill_creator_importer.py`: generated rules for imported skills so old buddy-run/persist wording cannot re-enter.
- `framework/contracts/*.json`: machine-checkable shape and projection contracts.
- `framework/contracts/{pm,design,dev,market,test}.md`: role-specific runtime boundaries.
- `scripts/env/tools/**` and `scripts/runtime_kernel/**`: runtime behavior and broker/tool contracts.
- `tests/**`: behavior and consistency gates.

Do not create a new prose mirror for these owners.

## Implementation Plan For Future Task

Do not execute this plan as part of this memo edit. This is the future cleanup handoff.

### Phase 1: Freeze Current Facts

Run current reference scans:

```bash
rg -n "framework/docs|browser-cockpit\\.md|skill-runtime-shared-rules\\.md|turn-runtime-spec\\.md|runtime-broker-v2-runbook\\.md|interface-spec\\.md|architecture-overview\\.md|track-registry\\.md|artifacts-runs-git-policy\\.md|skill-architecture-best-practices\\.md|multi-codex-worktree-guide\\.md|buddyswitch-development-constitution\\.md" README.md AGENTS.md tests scripts buddyswitch framework tools -g '!docs/**'

rg -n "task/artifact/run objects|current buddy run|buddy run|persist one buddy run|Do not call persist|locked buddy session|framework/docs" README.md AGENTS.md tests scripts buddyswitch framework tools -g '!docs/**'
```

These scans should initially show active references. They define the cleanup target.

### Phase 2: Update Tests Away From Prose Docs

Do not keep tests that pass only because deleted prose docs contain expected words.

Update `tests/test_repo_consistency.py`:

- Replace the `framework/docs/turn-runtime-spec.md` assertion with checks that `README.md` describes the runless loop and points to canonical sources.
- Replace the `framework/docs/runtime-broker-v2-runbook.md` assertion with checks against broker/runtime code or existing broker tests for `env.tool`, `ping`, and `status`.
- Add or update a consistency test that active surfaces no longer reference `framework/docs`.

Update `tests/test_parallel_contracts.py`:

- Replace `framework/docs/interface-spec.md` reads with assertions against `framework/contracts/workspace-projection.json` and, if needed, `README.md` canonical pointers.

Update `tests/test_skill_creator_importer.py` and fixtures:

- Expected imported-skill closing rules should be runless artifact/handoff/buddybox wording.
- Old "current buddy run", "Do not call persist", and "persist one buddy run commit" wording should not be generated.

Important grep rule:

- If a test must mention a retired token only as a negative assertion, split the string in test code, for example `"framework/" + "docs"` or `"buddy " + "run"`.
- The final grep gates should remain useful and should not be polluted by tests that contain retired phrases literally.

### Phase 3: Update README And AGENTS

Update `README.md`:

- Remove the "Architecture Docs" list.
- Add a concise "Canonical Runtime Sources" section pointing to:
  - `scripts/env/tools/contracts.py`
  - `scripts/env/tools/semantics.py`
  - `scripts/runtime_kernel/protocol.py`
  - `scripts/runtime_kernel/dispatcher.py`
  - `framework/contracts/prepare-turn-context.json`
  - `framework/contracts/workspace-projection.json`
  - `framework/contracts/{pm,design,dev,market,test}.md`

Update `AGENTS.md` only if needed, and keep it short:

- use env tools for product-mode runtime state
- do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly
- contract source of truth is code, JSON contracts, role contracts, and tests, not prose mirrors

Do not move long architecture descriptions or the old constitution into `README.md` or `AGENTS.md`.

### Phase 4: Inline Skill-Owned Rules

For the active skills listed in "Current Repo Facts":

- remove links to `framework/docs/browser-cockpit.md`
- remove links to `framework/docs/skill-runtime-shared-rules.md`
- keep only the market browser rules in market skills that actually require browser-native research
- replace `task/artifact/run objects` with `task/artifact/handoff objects` or more precise artifact/handoff/buddybox wording
- replace "current buddy run" wording with explicit runless output wording
- preserve skill-specific behavior and avoid broad rewriting

Update `scripts/skill_creator_importer.py` so imported skills receive current runless closing rules instead of old buddy-run/persist wording.

### Phase 5: Delete `framework/docs/`

After active references and prose-doc tests are removed, delete all files under `framework/docs/`:

- `framework/docs/architecture-overview.md`
- `framework/docs/artifacts-runs-git-policy.md`
- `framework/docs/browser-cockpit.md`
- `framework/docs/buddyswitch-development-constitution.md`
- `framework/docs/interface-spec.md`
- `framework/docs/multi-codex-worktree-guide.md`
- `framework/docs/runtime-broker-v2-runbook.md`
- `framework/docs/skill-architecture-best-practices.md`
- `framework/docs/skill-runtime-shared-rules.md`
- `framework/docs/track-registry.md`
- `framework/docs/turn-runtime-spec.md`

Do not create replacement compatibility docs.

Do not rewrite historical `docs/memo/**` or old `docs/spec/**` references in this task unless the task explicitly expands to archive cleanup.

### Phase 6: Verify

Focused verification:

```bash
python3 -m pytest -q tests/test_repo_consistency.py tests/test_parallel_contracts.py tests/test_skill_creator_importer.py
```

Full verification:

```bash
python3 -m pytest -q
```

Expected cleanup gates:

```bash
rg -n "framework/docs|browser-cockpit\\.md|skill-runtime-shared-rules\\.md|turn-runtime-spec\\.md|runtime-broker-v2-runbook\\.md|interface-spec\\.md|architecture-overview\\.md|track-registry\\.md|artifacts-runs-git-policy\\.md|skill-architecture-best-practices\\.md|multi-codex-worktree-guide\\.md|buddyswitch-development-constitution\\.md" README.md AGENTS.md tests scripts buddyswitch framework tools -g '!docs/**'

rg -n "task/artifact/run objects|current buddy run|buddy run|persist one buddy run|Do not call persist|locked buddy session|framework/docs" README.md AGENTS.md tests scripts buddyswitch framework tools -g '!docs/**'
```

Both scans should return no active hits after cleanup. If a regression test needs retired wording, split the retired phrase so the gate still detects real active-surface regressions.

## Acceptance Criteria

A future implementation is acceptable only when:

1. `framework/docs/` is removed from the active repo surface.
2. Active code, tests, README, AGENTS, and skills no longer reference `framework/docs/`.
3. No compatibility redirect, archive copy, empty directory, replacement framework-doc layer, or dual documentation path remains.
4. Skill-specific rules are self-contained in the relevant skill packages.
5. Imported skills get current runless closing rules from `scripts/skill_creator_importer.py`.
6. Test/runtime contract assertions target code, JSON contracts, role contracts, README pointers, or runtime behavior, not deleted prose docs.
7. Old run/persist/buddy-run wording is removed from active surfaces.
8. Focused tests and full pytest pass.
9. Historical docs are either explicitly out of scope or handled in a separate archive cleanup task.

## Risks And Guardrails

- Deleting `framework/docs/` before updating tests will break current tests.
- Leaving `framework/docs` links in skills would create dead runtime guidance.
- Updating skill text too broadly can change skill behavior; keep edits scoped to runtime-contract wording and known stale references.
- Moving contract summaries into README can bloat README; README should point to canonical sources rather than restating them.
- The importer is easy to miss; if it is not updated, new imported skills will reintroduce retired buddy-run/persist wording.
- Literal retired-token strings inside tests can make grep gates noisy. Use split strings for negative assertions.
- Market browser rules are actual behavior for market skills. Move the needed rules into market skills; do not preserve them as a shared framework doc.

## Non-Goals

- Do not redesign runtime contracts.
- Do not change env tool behavior.
- Do not change JSON object shapes.
- Do not change launcher behavior.
- Do not rewrite historical memo/spec archives in the same task.
- Do not create a replacement docs hierarchy for `framework/docs/`.
- Do not evaluate or delete `framework/agent-registry.md` unless a separate task expands scope beyond `framework/docs/`.

## Recommended Next Task

Create a separate implementation task from this memo:

> Clean active `framework/docs` usage by replacing prose-doc tests with code/contract tests, moving only still-actionable rules into README/AGENTS, active skills, importer-generated rules, and role contracts, deleting `framework/docs/` without compatibility remnants, and verifying with focused tests, full pytest, and no-hit active-surface scans.
