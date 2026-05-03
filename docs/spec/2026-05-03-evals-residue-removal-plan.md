# Evals Residue Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the obsolete `evals/` manual regression suite and every active reference that can reintroduce the retired switch/router/resolve product path.

**Architecture:** Treat `evals/` as an active-looking legacy asset, not as a compatibility surface to migrate. Delete the obsolete eval files, keep current product behavior covered by prepare/persist contracts, skill schemas, runtime integration tests, launcher tests, cleanup tests, and console/projection tests. Add a direct repository guard so future broad scans cannot silently exclude `evals/` again.

**Tech Stack:** Markdown specs, Python `unittest`/pytest, JSON schemas/contracts, shell `rg` verification, BuddySwitch launcher/runtime tests.

---

## Scope Decision

This task is intentionally narrow.

Do:

- Delete the tracked `evals/` manual regression assets.
- Remove active docs and tests that classify `evals/**` as current verification or commit-by-default guidance.
- Update the residual-risk memo so it no longer suggests compatibility migration of old evals.
- Add repository consistency checks that fail if `evals/` is restored as an active path.
- Verify current product behavior through existing prepare/persist, launcher, cleanup, console, and contract tests.

Do not:

- Migrate old `switch pm:` eval prompts to new `prepare`/`persist` eval prompts.
- Preserve a historical eval archive inside the active checkout.
- Rebuild the product verification system.
- Delete unrelated historical implementation plans unless a test proves they still act as active product guidance.

## Preflight Gate

Target outcome and bottleneck:

- Target outcome: the active checkout has no `evals/` tree and no active guidance telling agents or humans to run old switch-era evals.
- Current bottleneck: `evals/` still looks like an active manual regression suite while teaching retired `switch`, `scripts/switch_runtime.py`, `scripts/codex_router.py`, `scripts/parse_switch.py`, and `resolve` flow.

Confirmed facts:

- `evals/rubrics/regression-loop.md` tells readers to run a 10-case manual suite after framework/runtime changes.
- `evals/cases/01-switch-pm-prd.md`, `05-invalid-switch-error.md`, `09-track-registry-lifecycle.md`, and `10-resolve-skill-candidates.md` use retired switch/router/resolve commands.
- `tests/test_repo_consistency.py::test_runtime_storage_docs_point_to_launcher_workspace_without_gitkeep_language` currently includes `ROOT / "evals" / "cases" / "07-cleanup-storage-script.md"` as a documentation target.
- `framework/docs/artifacts-runs-git-policy.md` still lists `evals/**` under "Commit by default".
- Current product behavior is covered by `prepare-turn-context`, `persist-skill-result`, skill schemas, launcher tests, cleanup tests, and workspace projection tests.

Open assumptions and invalidators:

- Assumption: no external CI job outside this checkout runs files from `evals/`. If a hidden CI job is found, update that CI job to current pytest commands rather than preserving `evals/`.
- Assumption: historical review context can remain in docs/spec or docs/memo only if it does not instruct future agents to use or migrate old evals.
- Invalidator: if a current product requirement is only covered by an eval and not by tests/contracts, create a fresh current-path test before deleting that eval. The review so far found no such gap.

Tools, permissions, and boundary checks:

- Work only from `/Users/chen/Dev/buddyswitch/.worktrees/dev0210`.
- Do not edit the main checkout at `/Users/chen/Dev/buddyswitch`.
- Use `apply_patch` for file edits and file deletions.
- Do not use destructive shell deletion for this task unless the user explicitly asks during implementation.

Verification plan:

- Run targeted repo consistency tests after guard and doc edits.
- Run runtime/contract tests that prove the current product path still covers the behavior formerly described by evals.
- Run the full relevant regression before declaring the branch ready.
- Run a broad residue scan that includes the whole active checkout and confirms no active `evals/` tree remains.

Stop condition:

- `evals/` is absent.
- No active docs, prompts, launcher code, scripts, framework docs, or tests rely on `evals/` as current verification.
- Existing current-path automated tests pass.
- The residual-risk memo no longer recommends migrating old switch-era evals.

## Replacement Map

| Removed eval intent | Current replacement |
|---|---|
| `01-switch-pm-prd.md`: PRD shape and PM output | `framework/schemas/pm/write-prd.json`, `framework/contracts/pm.md`, `tests/test_turn_integration.py::test_complete_turn_persists_single_skill_result` |
| `03-switch-dev-boundary.md`: dev changes under `projects/app` | `framework/schemas/dev/implement-task.json`, `tests/test_buddyswitch_launcher.py::test_product_mode_projects_app_resolves_to_shared_project_app`, `tests/test_buddyswitch_launcher.py::test_cross_buddy_relative_projects_app_is_shared` |
| `04-switch-test-structure.md`: structured test report | `framework/schemas/test/smoke-test.json`, shared artifact schema guard tests |
| `05-invalid-switch-error.md`: invalid switch parser behavior | Current product requirement rejects command-shaped input before writes in `tests/test_turn_runtime.py::test_command_shaped_legacy_input_is_rejected_before_any_writes` and `tests/test_turn_integration.py::test_legacy_command_shaped_input_has_no_side_effects_and_followup_ordinary_request_succeeds` |
| `06-switch-market-deep-research.md`: market evidence and source traceability | `framework/contracts/market.md`, `framework/schemas/market/*.json`, market browser-native guards in `tests/test_repo_consistency.py` |
| `07-cleanup-storage-script.md`: cleanup safety and scope | `tests/test_cleanup_system.py` and launcher `data cleanup` tests; old `scripts/cleanup_buddyswitch.sh` is already removed |
| `08-interface-context-panel.md`: read-only context panel | `tests/test_console_app_contract.py`, `tests/test_parallel_contracts.py::WorkspaceProjectionContractTests` |
| `09-track-registry-lifecycle.md`: track-manager lifecycle | `tests/test_turn_runtime.py::test_track_manager_persist_receipt_uses_empty_artifact_ids`, `tests/test_parallel_contracts.py::test_track_manager_persist_returns_receipt_without_artifact_id` |
| `10-resolve-skill-candidates.md`: multi-skill candidates | `prepare-turn-context` contract and `tests/test_turn_integration.py::test_multi_skill_prepare_requires_exactly_one_selected_skill_for_persist` |

## Files To Delete

- `evals/cases/01-switch-pm-prd.md`
- `evals/cases/03-switch-dev-boundary.md`
- `evals/cases/04-switch-test-structure.md`
- `evals/cases/05-invalid-switch-error.md`
- `evals/cases/06-switch-market-deep-research.md`
- `evals/cases/07-cleanup-storage-script.md`
- `evals/cases/08-interface-context-panel.md`
- `evals/cases/09-track-registry-lifecycle.md`
- `evals/cases/10-resolve-skill-candidates.md`
- `evals/rubrics/base-rubric.md`
- `evals/rubrics/regression-loop.md`

## Files To Modify

- `tests/test_repo_consistency.py`
  - Remove `evals/cases/07-cleanup-storage-script.md` from active documentation checks.
  - Add a guard that fails if `evals/` exists.
  - Add a guard that active docs do not present `evals/` as verification assets.
- `framework/docs/artifacts-runs-git-policy.md`
  - Remove `evals/**` from commit-by-default guidance.
- `docs/memo/2026-05-03-final-review-residual-risks.md`
  - Mark Risk 1 as resolved by deletion.
  - Mark Risk 2 as closed by fresh full-regression verification.
  - Remove any recommendation to migrate switch-era evals.

## Task 1: Add Failing Guards For Evals Removal

**Files:**

- Modify: `tests/test_repo_consistency.py`
- Test: `tests/test_repo_consistency.py`

- [ ] **Step 1: Remove the eval file from the runtime storage documentation target list**

Find `test_runtime_storage_docs_point_to_launcher_workspace_without_gitkeep_language` and change `targets` from:

```python
        targets = (
            ROOT / "README.md",
            ROOT / "framework" / "docs" / "artifacts-runs-git-policy.md",
            ROOT / "evals" / "cases" / "07-cleanup-storage-script.md",
        )
```

to:

```python
        targets = (
            ROOT / "README.md",
            ROOT / "framework" / "docs" / "artifacts-runs-git-policy.md",
        )
```

- [ ] **Step 2: Add a direct guard that the legacy eval tree is absent**

Add this test method inside `RepoConsistencyTests` near the other legacy-removal guards:

```python
    def test_legacy_eval_assets_are_removed(self) -> None:
        self.assertFalse(
            (ROOT / "evals").exists(),
            "legacy evals must not remain in the active checkout; current behavior is covered by contracts and pytest",
        )
```

- [ ] **Step 3: Add a guard that active product guidance does not point to evals**

Add this helper inside `RepoConsistencyTests` or inline in the new test:

```python
    def test_active_docs_do_not_reference_legacy_evals_as_verification_assets(self) -> None:
        targets = (
            ROOT / "README.md",
            ROOT / "AGENTS.md",
            ROOT / "framework" / "docs",
            ROOT / "framework" / "contracts",
            ROOT / "tools" / "launcher",
            ROOT / "scripts",
        )
        forbidden_tokens = ("evals/", "evals/**", "evals/cases", "evals/rubrics")

        checked_files: list[Path] = []
        for target in targets:
            if target.is_file():
                candidates = [target]
            else:
                candidates = [path for path in target.rglob("*") if path.is_file()]
            for path in candidates:
                if "__pycache__" in path.parts:
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                checked_files.append(path)
                lower = text.lower()
                for token in forbidden_tokens:
                    self.assertNotIn(token, lower, msg=f"{path.relative_to(ROOT)} must not reference legacy eval assets")

        self.assertTrue(checked_files)
```

- [ ] **Step 4: Run the new direct guard and confirm it fails before deletion**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_legacy_eval_assets_are_removed \
  -q
```

Expected before implementation:

```text
FAILED ... legacy evals must not remain in the active checkout
```

- [ ] **Step 5: Run the active-doc guard and confirm it fails before doc cleanup**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_docs_do_not_reference_legacy_evals_as_verification_assets \
  -q
```

Expected before implementation:

```text
FAILED ... artifacts-runs-git-policy.md must not reference legacy eval assets
```

## Task 2: Delete The Legacy Eval Assets

**Files:**

- Delete: every file under `evals/cases/`
- Delete: every file under `evals/rubrics/`
- Test: `tests/test_repo_consistency.py`

- [ ] **Step 1: Delete the tracked eval files**

Use `apply_patch` delete hunks for each file:

```patch
*** Begin Patch
*** Delete File: evals/cases/01-switch-pm-prd.md
*** Delete File: evals/cases/03-switch-dev-boundary.md
*** Delete File: evals/cases/04-switch-test-structure.md
*** Delete File: evals/cases/05-invalid-switch-error.md
*** Delete File: evals/cases/06-switch-market-deep-research.md
*** Delete File: evals/cases/07-cleanup-storage-script.md
*** Delete File: evals/cases/08-interface-context-panel.md
*** Delete File: evals/cases/09-track-registry-lifecycle.md
*** Delete File: evals/cases/10-resolve-skill-candidates.md
*** Delete File: evals/rubrics/base-rubric.md
*** Delete File: evals/rubrics/regression-loop.md
*** End Patch
```

- [ ] **Step 2: Verify no tracked eval files remain**

Run:

```bash
find evals -type f | sort
```

Expected after implementation:

```text
find: evals: No such file or directory
```

If empty directories remain because the patch deleted all files, remove the empty directories only after confirming no tracked files remain:

```bash
rmdir evals/cases evals/rubrics evals
```

Expected:

```text
```

No output. If `rmdir` reports a directory is not empty, inspect it before removing anything else.

- [ ] **Step 3: Run the direct removal guard**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_legacy_eval_assets_are_removed \
  -q
```

Expected after implementation:

```text
1 passed
```

## Task 3: Remove Active Documentation References To Evals

**Files:**

- Modify: `framework/docs/artifacts-runs-git-policy.md`
- Modify: `docs/memo/2026-05-03-final-review-residual-risks.md`
- Test: `tests/test_repo_consistency.py`

- [ ] **Step 1: Remove `evals/**` from commit-by-default guidance**

In `framework/docs/artifacts-runs-git-policy.md`, change:

```markdown
- `projects/app/**`
- `evals/**`
```

to:

```markdown
- `projects/app/**`
```

- [ ] **Step 2: Update the residual-risk memo to record closure, not compatibility migration**

In `docs/memo/2026-05-03-final-review-residual-risks.md`, rewrite Risk 1 so it says:

```markdown
## Risk 1: Switch-Era Evals Remain Outside The Scoped Residue Scan

Status: Resolved by follow-up cleanup.

Resolution: the active `evals/` tree was removed instead of migrated. The useful product requirements are covered by current contracts, schemas, and pytest suites for `prepare-turn-context`, `persist-skill-result`, cleanup, launcher workspaces, and workspace projection. Do not restore switch-era evals as compatibility fixtures.
```

Also rewrite Risk 2 status to include these lines:

```markdown
Status: Closed by independent rerun.

Independent rerun result: 259 passed, 1 skipped.
```

Remove the old suggested action that says:

```text
For active evals, replace switch-era setup with the current product loop
```

- [ ] **Step 3: Run active-doc guard**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_docs_do_not_reference_legacy_evals_as_verification_assets \
  -q
```

Expected after implementation:

```text
1 passed
```

- [ ] **Step 4: Run a focused text scan**

Run:

```bash
rg -n "evals/|evals/\\*\\*|evals/cases|evals/rubrics" \
  README.md AGENTS.md framework tools scripts tests
```

Expected after implementation:

```text
```

No output.

## Task 4: Confirm Current Product Coverage Still Holds

**Files:**

- Test only: `tests/test_turn_runtime.py`
- Test only: `tests/test_turn_integration.py`
- Test only: `tests/test_parallel_contracts.py`
- Test only: `tests/test_cleanup_system.py`
- Test only: `tests/test_console_app_contract.py`
- Test only: `tests/test_buddyswitch_launcher.py`
- Test only: `tests/test_repo_consistency.py`

- [ ] **Step 1: Run current-path runtime and contract tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py \
  tests/test_turn_integration.py \
  tests/test_parallel_contracts.py \
  -q
```

Expected:

```text
passed
```

The exact count may change as tests evolve; there must be zero failures.

- [ ] **Step 2: Run cleanup and console/projection coverage**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_cleanup_system.py \
  tests/test_console_app_contract.py \
  -q
```

Expected:

```text
passed
```

The exact count may change as tests evolve; there must be zero failures.

- [ ] **Step 3: Run launcher and repo consistency coverage**

Run outside the sandbox if needed because launcher tests create git worktrees:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py \
  tests/test_repo_consistency.py \
  -q
```

Expected:

```text
passed
```

The exact count may change as tests evolve; there must be zero failures. A skip caused by an unavailable busy-port precondition is acceptable only if the test output explicitly marks it skipped rather than failed.

## Task 5: Final Residue Scan And Full Regression

**Files:**

- No code edits.
- Verification only.

- [ ] **Step 1: Confirm the eval tree is absent**

Run:

```bash
test ! -e evals
```

Expected:

```text
```

No output and exit code 0.

- [ ] **Step 2: Confirm old eval paths are gone from active paths**

Run:

```bash
rg -n "evals/|evals/\\*\\*|evals/cases|evals/rubrics" \
  README.md AGENTS.md framework tools scripts tests
```

Expected:

```text
```

No output.

- [ ] **Step 3: Confirm retired switch/router/resolve flow remains excluded from active product paths**

Run:

```bash
rg -n "scripts/switch_runtime.py|switch_runtime|resolve_context|resolve-context|runtime-AGENTS.md|Receipt -> Commands -> Summary|recommended_switch|reference_switches|codex_router|parse_switch|switch <buddy>|switch pm:" \
  README.md AGENTS.md framework tools scripts tests buddyswitch/manifest.toml
```

Expected after implementation:

- Matches may exist only in negative guard assertions inside tests.
- No active docs, prompts, launcher code, scripts, or framework contracts may teach the old product flow.

- [ ] **Step 4: Run full relevant regression**

Run outside the sandbox if launcher worktree creation is blocked:

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

Expected:

```text
passed
```

The last observed baseline before this plan was `259 passed, 1 skipped`. The exact count may change if tests are added; there must be zero failures.

## Self-Review Checklist

- [ ] The plan deletes old evals instead of migrating them.
- [ ] Every deleted eval intent has a current replacement or is explicitly obsolete.
- [ ] The guard fails when `evals/` exists.
- [ ] Active product docs no longer classify `evals/**` as commit-worthy or runnable verification.
- [ ] Residual-risk memo no longer recommends compatibility migration.
- [ ] Verification includes current product behavior, not only text searches.
- [ ] No implementation step requires editing the main checkout.
