# BuddySwitch v1 Regression Loop (Manual)

## When To Run

Run the 9-case suite after any change to:
- `AGENTS.md`
- `.codex/agents/*.toml`
- `framework/contracts/**`
- `framework/templates/**`
- `.agents/skills/**/SKILL.md`
- `framework/docs/switch-spec.md`
- `framework/docs/artifacts-runs-git-policy.md`
- `framework/docs/interface-spec.md`
- `framework/docs/track-registry.md`
- `framework/console/**`
- `artifacts/workspace-registry.json`
- `scripts/cleanup_buddyswitch.sh`
- `scripts/build_console_snapshot.py`

## How To Run (Lightweight)

1. Execute each case prompt from `evals/cases/`.
2. Check outputs against that case's pass criteria.
3. Score each case using `evals/rubrics/base-rubric.md`.
4. Write a compact result summary to `runs/summaries/`.

## Minimal Regression Summary Template

```md
# BuddySwitch v1 Eval Summary

- date:
- runner:
- version/branch:

## Case Results

- 01-switch-pm-prd: pass/fail
- 02-switch-design-state-coverage: pass/fail
- 03-switch-dev-boundary: pass/fail
- 04-switch-test-structure: pass/fail
- 05-invalid-switch-error: pass/fail
- 06-switch-market-deep-research: pass/fail
- 07-cleanup-storage-script: pass/fail
- 08-interface-context-panel: pass/fail
- 09-track-registry-lifecycle: pass/fail

## Regressions

- issue:
- impact:
- fix owner:

## Next Action

- immediate fix:
- re-run date:
```

## Exit Rule

- If any case fails, do not declare framework behavior stable.
- Fix the weakest failing instruction first, then rerun the affected case and full suite.
