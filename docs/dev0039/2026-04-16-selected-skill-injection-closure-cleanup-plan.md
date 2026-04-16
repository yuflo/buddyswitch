# Selected Skill Injection Closure And Cleanup Plan

> Status: Draft for confirmation. Do not execute implementation or spawn sub-agents from this document until the user explicitly approves.
>
> Relationship to active contract: `2026-04-16-selected-skill-injection-execution-plan.md` remains the implementation target. This document defines the cleanup and closure pass needed to finish that target under `framework/docs/buddyswitch-development-constitution.md`.

## Goal

Finish dev0039 by making `selected-skill-injection` the only active execution contract surface for this iteration, while deleting unrelated doc baggage that now interferes with clarity and review.

This pass exists because the code path has mostly converged, but the repo still carries stale dev0039 documents and one small runtime leftover that weaken the final state:

- `docs/dev0039/2026-04-16-market-cockpit-host-execution-bridge-plan.md` is historical baggage.
- `docs/dev0039/2026-04-16-market-research-cockpit-implementation-plan.md` is historical baggage.
- `docs/dev0039/2026-04-16-market-research-cockpit-design.md` still contains speculative future-state cockpit design that is broader than the implemented contract.
- `tests/test_repo_consistency.py` still preserves those old documents as if they were active requirements.
- `scripts/switch_runtime.py` still contains `_selected_skill_card(...)`, which appears to be dead code after the `prepare-execution` refactor.

The user has explicitly clarified that unrelated documents may be deleted. This plan follows that direction.

## Constraints

- Work only in `/Users/chen/Dev/buddyswitch/.worktrees/dev0039-market-research-cockpit`.
- Do not reset, clean, or discard existing uncommitted work.
- Keep `BuddySwitch` as a control layer only. No BuddySwitch-side host tool execution may be introduced.
- Use sub-agent mode only after plan approval.
- Before any cleanup that changes live expectations, add or adjust tests first.

## Non-Goals

- No new runtime architecture.
- No new browser orchestration layer.
- No expansion beyond the `selected_skill_packet` contract already defined by the active plan.
- No preservation of superseded dev0039 documents merely for history.

## Execution Strategy After Approval

Run the implementation in three lanes:

1. `spec/compliance review` sub-agent
- Re-check the repo against `2026-04-16-selected-skill-injection-execution-plan.md` and the constitution.
- Focus on trust boundaries, contract drift, stale doc surfaces, and whether any deleted content still carries active requirements.

2. `code-quality / regression review` sub-agent
- Re-check `prepare_execution_payload`, `selected_skill_packet`, market metadata validation, dead code, and regression risk.
- Focus on whether cleanup leaves any test, import, or reference drift behind.

3. Main session integration
- Convert valid findings into failing tests where needed.
- Apply the smallest cleanup that leaves one clear contract surface.
- Re-run the mandatory fresh verification set at the end.

If the two review lanes disagree, resolve in the main session before editing.

## Planned File Changes

Delete:

- `docs/dev0039/2026-04-16-market-cockpit-host-execution-bridge-plan.md`
- `docs/dev0039/2026-04-16-market-research-cockpit-implementation-plan.md`
- `docs/dev0039/2026-04-16-market-research-cockpit-design.md`

Modify:

- `docs/dev0039/2026-04-16-selected-skill-injection-execution-plan.md`
- `framework/docs/market-research-cockpit.md`
- `tests/test_repo_consistency.py`
- `tests/test_switch_runtime.py`
- `scripts/switch_runtime.py`

Potentially modify only if review proves drift remains:

- `framework/contracts/market.md`
- `framework/docs/switch-spec.md`
- the six `buddyswitch/skills/market/*/SKILL.md` files
- the six `buddyswitch/skills/market/*/skill.toml` files
- the six `framework/schemas/market/*.json` files
- the six `buddyswitch/skills/market/*/assets/*.md` templates

## Task Breakdown

### Task 1: Collapse dev0039 to the active contract surface

Files:

- Modify: `tests/test_repo_consistency.py`
- Modify: `docs/dev0039/2026-04-16-selected-skill-injection-execution-plan.md`
- Delete: `docs/dev0039/2026-04-16-market-cockpit-host-execution-bridge-plan.md`
- Delete: `docs/dev0039/2026-04-16-market-research-cockpit-implementation-plan.md`
- Delete: `docs/dev0039/2026-04-16-market-research-cockpit-design.md`

- [ ] Add failing repo-consistency coverage that no longer treats the three superseded dev0039 docs as required artifacts.
- [ ] Add or adjust coverage so the active dev0039 surface is the selected-skill plan plus this cleanup plan, not the old bridge/design/implementation docs.
- [ ] Update the active selected-skill plan only as needed so it no longer points to deleted docs as if they remain live deliverables.
- [ ] Delete the three superseded docs.
- [ ] Re-run the focused repo consistency tests.

### Task 2: Make `framework/docs/market-research-cockpit.md` the only live market cockpit contract doc

Files:

- Modify: `framework/docs/market-research-cockpit.md`
- Modify: `tests/test_repo_consistency.py`

- [ ] Add failing coverage for the live cockpit contract that matters now:
  - selected skill only, not multi-skill execution
  - shared headed cockpit metadata
  - mandatory takeover and no silent degrade
  - BuddySwitch remains control layer only
- [ ] Move any still-needed non-speculative contract text from deleted dev0039 docs into `framework/docs/market-research-cockpit.md`.
- [ ] Do not preserve speculative product ideas such as warm-start tab restore, future workspace semantics, or broader product vision unless they are already part of the implemented contract.
- [ ] Re-run the focused consistency tests.

### Task 3: Remove runtime leftovers exposed by the cleanup pass

Files:

- Modify: `scripts/switch_runtime.py`
- Modify: `tests/test_switch_runtime.py`

- [ ] Confirm `_selected_skill_card(...)` is dead and remove it if no remaining caller depends on it.
- [ ] Add or adjust tests so `prepare_execution_payload(...)` remains covered after cleanup.
- [ ] Verify no runtime behavior regresses while removing the leftover helper.

### Task 4: Re-run the market surface drift review and patch only real mismatches

Files:

- Possible modifies only if failing evidence appears:
  - `framework/contracts/market.md`
  - `framework/docs/switch-spec.md`
  - `buddyswitch/skills/market/*/SKILL.md`
  - `buddyswitch/skills/market/*/skill.toml`
  - `framework/schemas/market/*.json`
  - `buddyswitch/skills/market/*/assets/*.md`
  - `tests/test_output_schema_boundaries.py`
  - `tests/test_repo_consistency.py`

- [ ] Re-check the six market skills, templates, schemas, and contracts after the doc cleanup.
- [ ] Fix only concrete drift: trust boundary mismatch, order contradiction, schema/template mismatch, or missing error-code docs.
- [ ] Avoid speculative rewording where tests and contract surfaces already agree.

### Task 5: Fresh verification before any completion claim

- [ ] Run:

```bash
python3 -m unittest discover -s tests -p 'test_env_manifest_v2.py' -v
python3 -m unittest discover -s tests -p 'test_switch_runtime.py' -v
python3 -m unittest discover -s tests -p 'test_repo_consistency.py' -v
python3 -m unittest discover -s tests -p 'test_output_schema_boundaries.py' -v
git -C /Users/chen/Dev/buddyswitch/.worktrees/dev0039-market-research-cockpit diff --check
```

- [ ] If any focused regression from Task 1-4 fails, fix it before rerunning the full set.
- [ ] Only after the fresh verification set passes should the branch be judged `continue development`, `ready to commit`, or `needs rework`.

## Acceptance Criteria

- `2026-04-16-selected-skill-injection-execution-plan.md` is still the implementation target.
- Unrelated dev0039 documents are removed rather than preserved as historical baggage.
- `framework/docs/market-research-cockpit.md` is the live market cockpit contract surface.
- `tests/test_repo_consistency.py` stops enforcing the presence of superseded dev0039 docs.
- No runtime regression is introduced in `prepare-execution` or `selected_skill_packet`.
- BuddySwitch still does not execute host tools.
- The fresh verification set passes cleanly.

## Planned Final Report Format

After execution, report only:

- current active plan
- what each sub-agent found
- what changed
- verification result
- final judgment: `继续开发` / `可提交` / `仍需重做`
