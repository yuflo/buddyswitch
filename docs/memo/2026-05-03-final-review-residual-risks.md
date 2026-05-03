# Final Review Residual Risks

Date: 2026-05-03

Source: final review for `docs/spec/2026-05-03-buddy-instance-contract-residue-cleanup-plan.md`.

Purpose: preserve every residual risk surfaced during final acceptance review as a follow-up starting point for deeper inspection. This memo is not a new cleanup plan.

## Risk 1: Switch-Era Evals Remain Outside The Scoped Residue Scan

Status: Closed by follow-up cleanup.

Follow-up cleanup completed the deferred scope from final review:

- The active `evals/` tree was removed instead of migrated.
- Old switch-era evals must not be restored as compatibility fixtures.
- Repo consistency guards now enforce both eval-tree absence and active-doc exclusion of eval references.

Verification artifacts:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_legacy_eval_assets_are_removed -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_active_docs_do_not_reference_legacy_evals_as_verification_assets -q
test ! -e evals
```

## Risk 2: Final Reviewer Did Not Independently Rerun The Full Pytest Suite

Status: Closed by independent rerun.

Independent rerun result: 259 passed, 1 skipped.

Independent rerun command:

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
