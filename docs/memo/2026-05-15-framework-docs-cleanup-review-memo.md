# Framework Docs Cleanup Review Memo

Date: 2026-05-15
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem`
Status: planning memo only; no code or active-doc cleanup is executed in this task.

## Purpose

This memo records the review of whether `framework/docs/` should continue to exist as an active documentation surface, especially for:

- skill-related runtime guidance
- test/runtime-contract-related documentation
- historical cleanup and repo simplification

The user explicitly rejected direct code changes for this review pass. The previous direct-edit attempt should be treated as a rejected spike, not an accepted implementation. This memo is the handoff artifact for a future implementation task.

## Current Bottleneck

`framework/docs/` has become a second prose contract layer. It is currently referenced by README, skills, and tests, so it cannot be deleted blindly. But its content overlaps with:

- `README.md`
- root `AGENTS.md`
- `buddyswitch/skills/**/SKILL.md`
- `framework/contracts/*.json`
- `framework/contracts/{pm,design,dev,market,test}.md`
- runtime implementation under `scripts/`
- tests that already freeze behavior

This creates maintenance drag: a runtime or skill contract can drift across prose docs, skill files, code, JSON contract files, and tests.

## Current Repo Observations

At the time of this memo, the restored worktree still has all 11 files under `framework/docs/`:

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

Active references found after restore:

- `README.md` points to:
  - `framework/docs/architecture-overview.md`
  - `framework/docs/turn-runtime-spec.md`
  - `framework/docs/skill-runtime-shared-rules.md`
  - `framework/docs/track-registry.md`
  - `framework/docs/interface-spec.md`
- Multiple active skills reference:
  - `framework/docs/browser-cockpit.md`
  - `framework/docs/skill-runtime-shared-rules.md`
- Tests directly read:
  - `framework/docs/turn-runtime-spec.md`
  - `framework/docs/runtime-broker-v2-runbook.md`
  - `framework/docs/interface-spec.md`
- `framework/docs/skill-architecture-best-practices.md` references other docs in the same folder.

Additional stale active-surface wording exists today:

- market skills still say canonical outputs remain `task/artifact/run objects`.
- skill files and `scripts/skill_creator_importer.py` still contain old "current buddy run" / persist-oriented wording.
- importer tests assert some of that older wording.

This means a real cleanup must update references and tests together. Deleting files alone would break tests and leave skills pointing at dead paths.

## External Practice Review

Sources reviewed:

- Anthropic Claude Code Skills documentation: https://code.claude.com/docs/en/skills
- Anthropic Agent Skills overview: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
- GitHub contribution guidelines documentation: https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/setting-guidelines-for-repository-contributors
- Google documentation best practices: https://google.github.io/styleguide/docguide/best_practices.html
- Google README guidance: https://google.github.io/styleguide/docguide/READMEs.html
- Diataxis documentation framework: https://diataxis.fr/
- "What Do Contribution Guidelines Say About Software Testing?" arXiv paper: https://arxiv.org/abs/2602.02966

Key takeaways:

1. Skill-specific guidance should live in the skill package.
   Anthropic's Claude Code skill model treats `SKILL.md` as the required entry point and supports optional supporting files such as references, templates, examples, and scripts inside the skill directory. The docs also emphasize progressive disclosure: keep `SKILL.md` focused and load supporting files only when referenced.

2. Shared skill guidance should not become a broad framework-doc dumping ground.
   If a rule is universal and short, put it in the root instruction file or generated/importer template. If it is skill-specific, put it in that skill's `SKILL.md` or a reference file inside that skill package. If it is runtime-enforced, encode it in env tool contracts and tests.

3. Test guidance usually belongs in contribution/README surfaces, not hidden framework prose.
   GitHub documents `CONTRIBUTING` as the normal discoverable surface for contribution rules. Google README guidance expects usage and test commands in README or package-level README. The testing-guidelines study found test docs commonly live in `CONTRIBUTING`, external docs, or README, with the most common content being how to run tests.

4. Runtime contracts should be machine-checkable where possible.
   For this repo, the strongest sources are already code and JSON:
   - `scripts/env/tools/contracts.py`
   - `scripts/env/tools/semantics.py`
   - `scripts/runtime_kernel/protocol.py`
   - `scripts/runtime_kernel/dispatcher.py`
   - `framework/contracts/prepare-turn-context.json`
   - `framework/contracts/workspace-projection.json`
   - `framework/contracts/{pm,design,dev,market,test}.md`
   - behavior tests under `tests/`

5. Documentation taxonomy matters.
   Diataxis separates tutorials, how-to guides, reference, and explanation. The current `framework/docs/` mixes all of these with active runtime contracts, skill rules, Git policy, worktree operations, and philosophy. That mixture is a maintenance smell.

## Analysis

The current `framework/docs/` directory is not pure history today because active files and tests reference it. But its role is not clean:

- Some files are active contract summaries.
- Some files are duplicated principles already covered by `AGENTS.md`.
- Some are skill/runtime usage rules that should be in skill packages or launcher buddy AGENTS.
- Some are operational runbooks that should be README/CONTRIBUTING guidance or code-level tests.
- Some are historical planning residue.

The clean direction is not to keep polishing `framework/docs/`. The clean direction is to remove it as an active surface after moving each useful rule to the right owner.

## Recommended Direction

Recommended end state:

- No active `framework/docs/` directory.
- `README.md` becomes the concise repo entry point:
  - quick start
  - runtime loop
  - where canonical contracts live
  - focused verification commands
- `AGENTS.md` remains the execution philosophy and non-negotiable agent guidance.
- Skill-specific instructions live in `buddyswitch/skills/**/SKILL.md`.
- Future imported skills get current runless closing rules from `scripts/skill_creator_importer.py`.
- Runtime behavior contracts live in code, JSON contracts, and tests.
- Historical memo/spec files may keep old references as history unless a separate archive-cleanup task explicitly targets them.

This is aligned with SHARP: reduce surfaces, remove duplicate contract prose, and keep the shortest verified path.

## Proposed Implementation Plan For A Future Task

Do not execute this plan as part of this memo task. This is a future cleanup handoff.

### Phase 1: Freeze Current Facts

Run current reference scans:

```bash
rg -n "framework/docs|browser-cockpit\\.md|skill-runtime-shared-rules\\.md|turn-runtime-spec\\.md|runtime-broker-v2-runbook\\.md|interface-spec\\.md|architecture-overview\\.md|track-registry\\.md|artifacts-runs-git-policy\\.md|skill-architecture-best-practices\\.md|multi-codex-worktree-guide\\.md|buddyswitch-development-constitution\\.md" README.md AGENTS.md tests scripts buddyswitch framework tools -g '!docs/**'

rg -n "task/artifact/run objects|current buddy run|buddy run|persist one buddy run|Do not call persist|locked buddy session|framework/docs" README.md AGENTS.md tests scripts buddyswitch framework tools -g '!docs/**'
```

These scans should initially show active references; they define the cleanup target.

### Phase 2: Move Canonical Pointers To README And AGENTS

Update `README.md` to remove the "Architecture Docs" list and point to canonical sources:

- `scripts/env/tools/contracts.py`
- `scripts/env/tools/semantics.py`
- `scripts/runtime_kernel/protocol.py`
- `scripts/runtime_kernel/dispatcher.py`
- `framework/contracts/prepare-turn-context.json`
- `framework/contracts/workspace-projection.json`
- `framework/contracts/{pm,design,dev,market,test}.md`

Update `AGENTS.md` with the minimum rule:

- use env tools for product-mode runtime state
- do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly
- contract source of truth is code/JSON/tests, not prose mirrors

### Phase 3: Move Skill Runtime Rules Into Skills

For every active `buddyswitch/skills/**/SKILL.md`:

- remove links to `framework/docs/browser-cockpit.md`
- remove links to `framework/docs/skill-runtime-shared-rules.md`
- keep the browser/runtime rules directly in market skills where they are actually needed
- replace `task/artifact/run objects` with `task/artifact/handoff objects`
- replace "current buddy run" wording with runless artifact/handoff/buddybox wording
- preserve skill-specific behavior and avoid unrelated rewrites

Update `scripts/skill_creator_importer.py` so imported skills receive current runless closing rules instead of old buddy-run/persist wording.

Update `tests/test_skill_creator_importer.py` and fixtures accordingly.

### Phase 4: Replace Tests That Read Prose Docs

Do not keep tests that pass only because prose docs contain expected words. Replace them with tests that check canonical sources:

- README points to canonical contract files.
- broker protocol and dispatcher expose `env.tool`, `ping`, `status`.
- workspace projection tests read `framework/contracts/workspace-projection.json`.
- env tool tests continue using `scripts/env/tools/contracts.py` and runtime behavior.

Known tests to update:

- `tests/test_repo_consistency.py`
- `tests/test_parallel_contracts.py`

### Phase 5: Delete `framework/docs/`

After active references are removed, delete all files under `framework/docs/`.

Recommended deletion list:

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

Do not rewrite historical `docs/memo/**` or old `docs/spec/**` references in the same task unless the task explicitly expands to archive cleanup.

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

Both scans should return no active hits after the future cleanup.

## Acceptance Criteria

A future implementation is acceptable only when:

1. Active code, tests, README, AGENTS, and skills no longer reference `framework/docs/`.
2. `framework/docs/` is removed from the active repo surface.
3. Skill-specific rules are self-contained in the relevant skill packages.
4. Test/runtime contract assertions target code, JSON contracts, or README pointers, not deleted prose docs.
5. Old run/persist/buddy-run wording is removed from active surfaces.
6. Focused tests and full pytest pass.
7. Historical docs remain either explicitly out of scope or are handled in a separate archive cleanup task.

## Risk Notes

- Deleting `framework/docs/` without updating tests will break current tests.
- Updating skill text too broadly can change skill behavior. Keep edits mechanical and scoped to runtime contract references.
- Moving contract summaries into README can bloat README if not kept concise. README should point to canonical sources rather than restating them.
- Historical `docs/spec` and `docs/memo` references will still mention `framework/docs`; that is acceptable only if historical docs are explicitly excluded from active cleanup gates.
- The importer is easy to miss. If it is not updated, new imported skills will reintroduce retired buddy-run/persist wording.

## Non-Goals

- Do not redesign runtime contracts.
- Do not change env tool behavior.
- Do not change JSON object shapes.
- Do not change launcher behavior.
- Do not rewrite historical memo/spec archives in the same task.
- Do not implement code changes as part of this memo task.

## Recommended Next Task

Create a separate implementation task from this memo:

> Clean active `framework/docs` usage by moving canonical pointers to README/AGENTS, inlining skill-owned runtime rules into relevant `SKILL.md` files, updating importer-generated runless closing rules, replacing prose-doc tests with code/contract tests, deleting `framework/docs/`, and verifying with focused scans plus full pytest.

