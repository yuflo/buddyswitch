# Final Review Residual Risks

Date: 2026-05-03

Source: final review for `docs/spec/2026-05-03-buddy-instance-contract-residue-cleanup-plan.md`.

Purpose: preserve every residual risk surfaced during final acceptance review as a follow-up starting point for deeper inspection. This memo is not a new cleanup plan.

## Risk 1: Switch-Era Evals Remain Outside The Scoped Residue Scan

Status: Open.

The required residue scan intentionally covered:

```text
README.md AGENTS.md .codex tools scripts framework tests buddyswitch/manifest.toml docs
```

Final review also noted that a broader repo-wide scan still finds old switch-era examples under `evals/`, which was outside the accepted cleanup scope.

Observed matches:

```text
evals/rubrics/regression-loop.md
evals/cases/01-switch-pm-prd.md
evals/cases/05-invalid-switch-error.md
evals/cases/09-track-registry-lifecycle.md
evals/cases/10-resolve-skill-candidates.md
```

Observed old-flow terms include:

```text
scripts/switch_runtime.py
scripts/codex_router.py
scripts/parse_switch.py
switch pm:
switch <buddy>: <task>
resolve
```

Why it matters:

- Future agents may treat `evals/` as active product guidance and reintroduce the retired switch/router/resolve flow.
- If evals are still run manually or in CI, they may encode obsolete expected behavior.
- A future repo-wide residue guard would fail unless `evals/` are updated, deleted, or explicitly classified as historical fixtures.

Suggested starting checks:

1. Determine whether `evals/` are active verification assets, historical examples, or dead documentation.
2. Search for references to `evals/` in CI, scripts, README, docs, and developer workflows.
3. For active evals, replace switch-era setup with the current product loop: `prepare-turn-context -> host executes exactly one skill -> persist-skill-result`.
4. For obsolete evals, delete them or move them out of active searchable guidance.
5. Add or update a guard so future broad scans classify `evals/` deliberately instead of silently excluding them.

Suggested verification:

```bash
rg -n "scripts/switch_runtime.py|switch_runtime|resolve_context|resolve-context|runtime-AGENTS.md|Receipt -> Commands -> Summary|recommended_switch|reference_switches|codex_router|parse_switch|switch <buddy>|switch pm:" evals
rg -n "evals/" .github scripts README.md docs framework tests
```

## Risk 2: Final Reviewer Did Not Independently Rerun The Full Pytest Suite

Status: Mitigated for current acceptance, but rerun before merge if the branch sits or changes again.

Final review accepted the work after reviewing the testing sub-agent evidence and running targeted checks, but did not independently rerun the full pytest command itself.

Evidence reviewed by final review:

```text
Targeted behavior/contract tests: 210 passed
Projection and console coverage: 12 passed
Full relevant regression: 260 passed
py_compile: passed
git diff --check: passed
Scoped residue scan: only cleanup docs and guard-test assertions matched
```

Why it matters:

- The acceptance decision depends on fresh testing-agent evidence rather than duplicate full-suite execution by the reviewer.
- If more changes are made after this memo, the old evidence no longer proves the final state.

Suggested stop condition before merge or PR:

Rerun the full relevant regression from the test plan if any source, test, contract, prompt, launcher, or docs file changes after the accepted review:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_cleanup_system.py \
  tests/test_console_app_contract.py \
  tests/test_artifact_selection.py \
  tests/test_turn_runtime.py \
  tests/test_turn_integration.py \
  tests/test_parallel_contracts.py \
  tests/test_buddyswitch_launcher.py \
  tests/test_repo_consistency.py \
  -q
```

