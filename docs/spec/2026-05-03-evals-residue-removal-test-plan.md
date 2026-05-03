# Evals Residue Removal Test Plan

**Goal:** Verify that deleting the legacy `evals/` manual regression suite removes obsolete switch/router/resolve guidance without weakening the current BuddySwitch product contract.

**Testing Principle:** Tests must start from current product requirements: users submit ordinary requests inside locked buddy instances; the host prepares context, runs exactly one selected skill, persists the result, and renders a receipt. Tests must not preserve old eval prompts, parser behavior, or `switch` command flows merely to keep historical examples passing.

---

## Functional Requirements Under Test

FR1. The active checkout must not contain a runnable or searchable `evals/` manual regression suite.

FR2. Active product guidance must not tell humans or agents to run, commit, migrate, or maintain `evals/**`.

FR3. Current behavior formerly described by evals must remain covered by contracts, schemas, and automated tests.

FR4. Legacy command-shaped input remains rejected before state writes; natural language containing the word "switch" remains valid ordinary text.

FR5. Multi-skill buddy turns use `prepare-turn-context` candidate skills and `persist-skill-result` with exactly one selected skill; there is no product `resolve` command path.

FR6. Cleanup behavior is verified through `buddyswitch-codex data cleanup`, not the removed `scripts/cleanup_buddyswitch.sh` or eval documentation.

FR7. Context panel and workspace projection continue to read structured task, track, artifact, and run state without command-string suggestions.

FR8. The residual-risk memo records closure of the eval risk and does not recommend compatibility migration of old evals.

FR9. Broad residue scanning includes enough active paths to prevent hidden reintroduction of switch/router/resolve guidance.

FR10. Full regression remains green after removing eval assets and references.

## Coverage Matrix

| Requirement | Test Type | Primary Proof |
|---|---|---|
| FR1 | Repo consistency | `tests/test_repo_consistency.py::test_legacy_eval_assets_are_removed` and `test ! -e evals` |
| FR2 | Repo consistency and text scan | Active docs/tools/scripts/tests scan for `evals/`, `evals/**`, `evals/cases`, `evals/rubrics` |
| FR3 | Schema/contract/runtime regression | `tests/test_turn_runtime.py`, `tests/test_turn_integration.py`, `tests/test_parallel_contracts.py`, schema guards |
| FR4 | Runtime behavior | `test_command_shaped_legacy_input_is_rejected_before_any_writes`, `test_natural_language_switch_word_is_accepted`, integration follow-up ordinary request test |
| FR5 | Runtime and contract | `test_multi_skill_prepare_requires_exactly_one_selected_skill_for_persist`, prepare/persist contract tests |
| FR6 | Cleanup integration | `tests/test_cleanup_system.py` data cleanup shell integration tests |
| FR7 | Console/projection contract | `tests/test_console_app_contract.py`, workspace projection contract tests |
| FR8 | Docs consistency | New or updated repo consistency check against the residual-risk memo |
| FR9 | Residue guard | Existing legacy switch-wire guard plus explicit eval absence guard |
| FR10 | Full regression | Full relevant pytest command from this plan |

## Test Groups

### TG-01: Evals Tree Is Not Active

**Requirement:** The checkout must not retain the old manual eval suite as active files.

Cases:

1. `evals/` does not exist.
   - Expected: `(ROOT / "evals").exists()` is false.
   - Expected: `test ! -e evals` exits 0.

2. No eval case or rubric files remain tracked.
   - Expected: `find evals -type f` cannot find files because the directory is absent.
   - Expected: `git status --short evals` shows deletions during implementation, and no untracked replacement eval files.

3. Reintroducing any `evals/` directory fails repository consistency.
   - Expected: `test_legacy_eval_assets_are_removed` fails if `evals/` exists, even if empty.

Anti-cheat rule:

- Do not satisfy this group by keeping `evals/` with renamed files, empty marker files, `.gitkeep`, or archived copies in a different active directory.

### TG-02: Active Guidance Does Not Reference Evals

**Requirement:** Current docs, launcher assets, scripts, and framework guidance must not instruct agents to use evals.

Cases:

1. Active product docs do not mention eval paths.
   - Targets: `README.md`, `AGENTS.md`, `framework/docs/**`, `framework/contracts/**`, `tools/launcher/**`, `scripts/**`.
   - Forbidden strings: `evals/`, `evals/**`, `evals/cases`, `evals/rubrics`.
   - Expected: no forbidden string appears in those active targets.

2. `framework/docs/artifacts-runs-git-policy.md` no longer lists `evals/**` under commit-by-default paths.
   - Expected: `projects/app/**` remains present.
   - Expected: `evals/**` is absent.

3. `tests/test_repo_consistency.py` no longer reads `evals/cases/07-cleanup-storage-script.md` as an active documentation source.
   - Expected: the runtime storage documentation test reads only current active docs.
   - Expected: deleting `evals/` does not cause `FileNotFoundError`.

Anti-cheat rule:

- Do not pass by excluding every doc directory from scanning. The scan must still cover current product guidance that a future agent is likely to read.

### TG-03: Residual-Risk Memo Closure

**Requirement:** The memo must not preserve a stale decision path after the cleanup is complete.

Cases:

1. Risk 1 is marked resolved by deletion.
   - Expected: memo states that the active `evals/` tree was removed.
   - Expected: memo says old switch-era evals must not be restored as compatibility fixtures.

2. Risk 1 no longer recommends migrating switch-era evals to the current product loop.
   - Forbidden phrases:
     - `For active evals, replace switch-era setup`
     - `Determine whether evals/ are active verification assets`
     - `move them out of active searchable guidance` as an unresolved action

3. Risk 2 is closed by independent regression rerun.
   - Expected: memo includes independent rerun result with zero failures.

Anti-cheat rule:

- Do not satisfy this group by deleting all mention of the risk without recording the final decision. The useful future fact is the decision: delete old evals, do not migrate them.

### TG-04: Current Runtime Behavior Still Covers Former Eval Intent

**Requirement:** Removing evals must not remove verification of current user-visible behavior.

Cases:

1. Ordinary PM request prepares context and persists a `write-prd` result.
   - Command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py::TurnRuntimeBehaviorTests::test_prepare_turn_context_accepts_ordinary_request_and_creates_reserved_run \
  tests/test_turn_runtime.py::TurnRuntimeBehaviorTests::test_successful_persist_returns_structured_receipt_contract \
  tests/test_turn_integration.py::TurnRuntimeIntegrationTests::test_complete_turn_persists_single_skill_result \
  -q
```

   - Expected: all selected tests pass.

2. Legacy switch-shaped input is rejected without writes.
   - Command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py::TurnRuntimeBehaviorTests::test_command_shaped_legacy_input_is_rejected_before_any_writes \
  tests/test_turn_integration.py::TurnRuntimeIntegrationTests::test_legacy_command_shaped_input_has_no_side_effects_and_followup_ordinary_request_succeeds \
  -q
```

   - Expected: all selected tests pass.

3. Natural language containing "switch" remains accepted.
   - Command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py::TurnRuntimeBehaviorTests::test_natural_language_switch_word_is_accepted \
  tests/test_turn_integration.py::TurnRuntimeIntegrationTests::test_natural_language_switch_request_runs_full_prepare_persist_path \
  -q
```

   - Expected: all selected tests pass.

Anti-cheat rule:

- Do not replace behavior verification with text-only assertions. Runtime tests must inspect state writes or absence of writes.

### TG-05: Schema And Contract Coverage Replaces Eval Output Checks

**Requirement:** Output shape expectations once listed in evals remain enforced by schemas and contracts.

Cases:

1. PM PRD schema requires PRD content fields.
   - Expected: `framework/schemas/pm/write-prd.json` requires `problem`, `goals`, `non_goals`, `users_and_scenarios`, `scope_p0_p1`, `acceptance_criteria`, `risks`, and `open_questions`.

2. Dev implementation schema requires implementation report fields.
   - Expected: `framework/schemas/dev/implement-task.json` requires `task_summary`, `changed_files`, `implementation_notes`, `verification_runs`, and `known_limitations`.

3. Test smoke schema requires pass/fail/blocked fields.
   - Expected: `framework/schemas/test/smoke-test.json` requires `test_scope`, `passed_items`, `failed_items`, `blocked_items`, `reproduction_steps`, and `overall_readiness_summary`.

4. Market schemas and contracts require browser-native evidence and traceability.
   - Expected: market contract requires `chrome-devtools-cockpit` and `browser-native`.
   - Expected: market schemas require `evidence` and `source_traceability`.

5. Persist contract freezes receipt metadata.
   - Expected: `tests/test_parallel_contracts.py::ResolveAndPersistContractTests::test_contract_matches_real_persist_skill_result_surface` passes.

Anti-cheat rule:

- Do not check for field names only in old eval markdown. The source of truth must be schemas, contracts, and runtime output.

### TG-06: Cleanup Coverage Uses Current CLI

**Requirement:** Cleanup behavior is verified through the current `data cleanup` command surface.

Cases:

1. Buddy cleanup dry run reports scoped run content.
   - Expected: market cleanup includes market run paths and excludes PM run paths.

2. Removed cleanup options fail closed.
   - Expected: `--execute`, `--force`, `--agent`, `--all-agents`, `--project`, and `--all-storage` return controlled errors.

3. Source checkout and shared project workspace are preserved.
   - Expected: data cleanup does not delete project source paths.

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_cleanup_system.py \
  -q
```

Expected:

```text
passed
```

Anti-cheat rule:

- Do not satisfy cleanup coverage by testing only helper functions. Shell integration must exercise the public command surface.

### TG-07: Console And Projection Coverage Uses Structured State

**Requirement:** Removing evals must not remove coverage of the context panel boundary.

Cases:

1. Track next-step state reports buddy state without switch commands.
   - Expected: derived state includes current and recommended buddy.
   - Expected: serialized state does not contain `switch`.

2. Task next-step state reports current and recommended buddy without switch commands.
   - Expected: serialized state does not contain `switch`.

3. Workspace projection includes structured task, track, artifact, and run audit shapes.
   - Expected: run audits include `next_state` and `receipt_paths`.
   - Expected: no `recommended_switch` or `reference_switches`.

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_console_app_contract.py \
  tests/test_parallel_contracts.py::WorkspaceProjectionContractTests \
  -q
```

Expected:

```text
passed
```

Anti-cheat rule:

- Do not use command-string suggestions as UI proof. The panel must read structured state.

### TG-08: Launcher Product Workspace Coverage

**Requirement:** The current product workspace model remains verified after eval deletion.

Cases:

1. Product mode `projects/app` resolves to shared project source.
   - Expected: launcher capture reports runtime workspace as cwd and shared project workspace for `projects/app`.

2. Cross-buddy relative `projects/app` access is shared.
   - Expected: PM writes a sentinel through relative product path and dev reads the same shared project file.

3. Buddy prompt assets still require ordinary user requests and receipt/summary rendering.
   - Expected: no buddy prompt exposes `switch <buddy>` or `switch pm:`.

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_product_mode_projects_app_resolves_to_shared_project_app \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_cross_buddy_relative_projects_app_is_shared \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_buddy_prompts_do_not_allow_user_facing_switch_commands \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_prompt_does_not_present_switch_as_product_ui \
  -q
```

Expected:

```text
passed
```

Sandbox note:

- Launcher tests create git worktrees. If sandboxed execution fails with `.git/worktrees` permission errors, rerun outside the sandbox instead of treating the failure as product behavior.

Anti-cheat rule:

- Do not replace launcher integration with source-file string checks only. At least the product workspace path behavior must run through the launcher test harness.

### TG-09: Broad Residue Scan

**Requirement:** Old eval and switch-era residue must not remain in active paths.

Commands:

```bash
rg -n "evals/|evals/\\*\\*|evals/cases|evals/rubrics" \
  README.md AGENTS.md framework tools scripts tests
```

Expected:

```text
```

No output.

```bash
rg -n "scripts/switch_runtime.py|switch_runtime|resolve_context|resolve-context|runtime-AGENTS.md|Receipt -> Commands -> Summary|recommended_switch|reference_switches|codex_router|parse_switch|switch <buddy>|switch pm:" \
  README.md AGENTS.md framework tools scripts tests buddyswitch/manifest.toml
```

Expected:

- No matches in active docs, prompts, launcher code, scripts, or framework contracts.
- Matches in tests are allowed only as explicit forbidden-token assertions or negative behavior tests.

Anti-cheat rule:

- Do not exclude an active path just because it currently fails the scan. Either remove the residue or document why that path is historical and not product guidance.

### TG-10: Full Relevant Regression

**Requirement:** The cleanup must preserve current BuddySwitch behavior.

Command:

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

The latest known baseline before this cleanup plan was `259 passed, 1 skipped`. Exact counts may change if tests are added; zero failures is mandatory.

Sandbox note:

- If the full command fails only because launcher tests cannot create git worktrees under sandbox restrictions, rerun the same command outside the sandbox and record that result.

## Definition Of Done

- `evals/` does not exist in the active checkout.
- `framework/docs/artifacts-runs-git-policy.md` no longer lists `evals/**`.
- `tests/test_repo_consistency.py` no longer reads eval files as active docs.
- A repo consistency guard fails if `evals/` is restored.
- The residual-risk memo records deletion and closed verification, not compatibility migration.
- Targeted current-path tests pass.
- Full relevant regression passes with zero failures.
