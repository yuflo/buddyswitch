# BuddySwitch Complete Residue Cleanup Test Plan

**Goal:** Verify that the complete residue cleanup converges active BuddySwitch behavior, docs, tests, launcher paths, browser setup, skills, manifest kinds, and debug APIs on the current locked-buddy broker-owned runtime model without preserving old compatibility paths.

**Testing Principle:** Start from product requirements and observable contracts. Do not construct tests around private helper deletion as the primary proof. Use scans only for active source surfaces where the product requirement is "do not teach this old model." Negative tests are valid when they prove retired public contracts fail closed or retired payload shapes remain rejected.

---

## Functional Requirements

FR1. Runtime request text is ordinary text. A locked buddy instance gets active buddy identity from launcher metadata, not from user text. Text resembling retired `switch <buddy>:` syntax prepares successfully and is preserved as `request_text`.

FR2. Active runtime docs and guardrails must not say command-shaped request text is rejected or routed.

FR3. Retired public launcher commands and removed destructive cleanup flags still fail closed without launching Codex or mutating runtime state.

FR4. Active native skills describe contribution to one compact buddy-run commit. They must not imply that the skill itself directly writes broker-owned state under `buddyswitch/objects/**` or `buddyswitch/content/runs/**`.

FR5. Buddy runtime AGENTS consistently state that user text does not change the locked active buddy.

FR6. Market artifact-producing templates must not include copyable fake browser evidence tokens. Market artifact persist must still require broker-issued browser evidence or an approved broker-issued downgrade token.

FR7. Every active manifest artifact kind must either have active first-party guidance/asset coverage or an explicit current non-template reason. Orphan artifact kinds are removed rather than preserved for imagined future skills.

FR8. Old framework Markdown templates are not active authoring surfaces. Runtime-native skill assets are the only first-party templates for buddy output.

FR9. Active `docs/spec` files must not contain stale implementation plans that teach superseded payloads, old routing, old selected-skill persist, old store wrappers, or pre-implementation failure expectations.

FR10. Product launcher startup is instance-first. Old private workspace sync and no-buddy bootstrap paths are not supported product paths.

FR11. Browser cockpit setup is instance-scoped. Product setup must not create a shared browser profile or generic `chrome-devtools` MCP server.

FR12. Debug/admin artifact APIs expose only supported v2 object-store operations. Unsupported flags such as non-auto-register creation and markdown file deletion are not advertised.

FR13. Store cleanup removes unused helpers and redundant wrappers without changing object lifecycle behavior.

FR14. Cleanup backend uses current public vocabulary (`buddy`, `all-data`) while preserving fail-closed behavior for removed public cleanup options.

FR15. Runtime persist, broker dispatch, schema boundaries, context panel projections, cleanup, and launcher lifecycle behavior remain stable after cleanup.

## Anti-Cheating Constraints

- Do not make tests pass by excluding active paths that users, launcher sessions, skills, or developers still read.
- Do not replace behavior tests with string scans. Behavior tests prove runtime and launcher outcomes; scans only prove active surfaces do not teach retired models.
- Do not assert that a private helper was deleted as the main product proof. Prove the public or supported behavior first.
- Do not keep both old and new authoring contracts. Cleanup must converge on the compact buddy-run commit model.
- Do not remove fail-closed guards just because they mention retired commands.
- Do not preserve orphan artifact kinds by adding a placeholder producer or fake template.
- Do not satisfy Market evidence tests with hand-written token strings.
- Do not delete stale docs by hiding them in another active source-of-truth path.
- Do not touch the pre-existing untracked memo `docs/memo/2026-05-07-buddy-instance-context-tool-feedback-direction-memo.md`.

## Coverage Matrix

| Requirement | Test Groups | Observable Proof |
| --- | --- | --- |
| FR1 | TG-01 | `prepare` succeeds for switch-prefixed text and locked buddy remains unchanged |
| FR2 | TG-02 | active runtime docs and guardrails do not teach command-shaped rejection |
| FR3 | TG-03 | retired public launcher commands fail closed without Codex invocation or writes |
| FR4 | TG-04 | all manifest skills describe compact buddy-run contribution, not direct state writes |
| FR5 | TG-05 | all buddy AGENTS state user text does not change active buddy |
| FR6 | TG-06 | Market templates lack fake tokens; browser evidence gate still rejects handwritten tokens |
| FR7 | TG-07 | active manifest artifact kinds have current guidance; orphan Market kind is gone |
| FR8 | TG-08 | framework Markdown templates are deleted and unreferenced |
| FR9 | TG-09 | active specs do not contain superseded payload/routing/plan wording |
| FR10 | TG-10 | no-buddy bootstrap and private workspace sync are unsupported; instance start still works |
| FR11 | TG-11 | browser setup is instance-scoped and does not add generic MCP |
| FR12 | TG-12 | debug artifact help surfaces expose only supported flags |
| FR13 | TG-13 | store/debug/runtime behavior passes without unused helper paths |
| FR14 | TG-14 | cleanup current scopes pass; old public flags fail closed |
| FR15 | TG-15 | focused and full regression suites pass |

## Test Data Rules

Use product-meaningful data:

- Switch-shaped ordinary requests:
  - `switch market: do competitor scan`
  - `switch dev: summarize positioning gaps`
  - `switch pm: implement launcher cleanup`
- Active Market artifact kinds:
  - `market-scan`
  - `pmf-report`
  - `customer-discovery`
  - `positioning-brief`
  - `channel-plan`
  - `launch-prep`
- PM artifact kinds:
  - `prd`
  - `pm-decision`
  - `track-note`
- Dev artifact kinds:
  - `implementation-report`
  - `skill-import-report`
- Design artifact kinds:
  - `design-handoff`
  - `prototype-brief`
- Test artifact kinds:
  - `smoke-test`
  - `test-report`

Do not use `market-landing-page-brief` after this cleanup unless the product explicitly adds an active producer.

## Test Groups

### TG-01: Locked Buddy Authority And Ordinary Switch-Shaped Text

**Purpose:** Prove request text never routes the buddy and old switch-like syntax is ordinary input.

Functional scenarios:

1. Prepare a PM product session with `switch market: do competitor scan`.
2. Assert `ok=true`.
3. Assert `active_buddy == "pm"`.
4. Assert `request_text` exactly preserves `switch market: do competitor scan`.
5. Assert `run_envelope.turn_identity.request_text` also preserves the text.
6. Repeat with locked Market session and `switch dev: summarize positioning gaps`.
7. Repeat with locked Dev session and `switch pm: implement launcher cleanup`.

Primary command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py::TurnRuntimeBuddyRunTests::test_prepare_accepts_switch_prefixed_text_as_ordinary_request \
  tests/test_turn_runtime.py::TurnRuntimeBuddyRunTests::test_prepare_uses_locked_buddy_for_switch_prefixed_text \
  -q
```

Expected proof:

- Switch-like request text prepares successfully.
- Active buddy comes only from session metadata.
- A run reservation is created normally.

### TG-02: Active Runtime Docs Do Not Re-Teach Switch Rejection

**Purpose:** Prove active documentation and guardrails match TG-01 behavior.

Functional scenarios:

1. Scan active docs, scripts, launcher assets, contracts, and skills for retired switch-router fields.
2. Scan active runtime docs for semantically stale phrases such as command-shaped input being rejected.
3. Assert the scan excludes historical memos only when they are intentionally not active product guidance.

Primary command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_product_paths_exclude_legacy_switch_wire \
  -q
```

Supplemental scan:

```bash
rg -n 'Command-shaped routing input is rejected|command-shaped routing input is rejected|router-era guard|recommended_switch|reference_switches' \
  README.md AGENTS.md framework/docs framework/contracts scripts tools/launcher/assets buddyswitch/skills
```

Expected proof:

- No active source says runtime request text is rejected because it looks like old switch syntax.
- No active source exposes old switch-router fields.

### TG-03: Retired Public Launcher Commands Still Fail Closed

**Purpose:** Prove cleanup does not reopen old public CLI surfaces.

Functional scenarios:

1. Run retired public commands: `start`, `buddy`, `cleanup`, `reset`, `browser`, `workspace`.
2. Assert each returns non-zero.
3. Assert each prints the current replacement hint.
4. Assert no Codex invocation marker is created.
5. Assert no runtime state write occurs.

Primary command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_legacy_public_commands_fail_closed_with_hints \
  -q
```

Expected proof:

- Retired public commands are guardrails, not compatibility paths.

### TG-04: Active Skill Guidance Uses Compact Buddy-Run Contribution

**Purpose:** Prove all first-party runtime skills guide agents to contribute to one compact commit.

Functional scenarios:

1. Load skill paths from `buddyswitch/manifest.toml`.
2. For each active skill, read `SKILL.md`.
3. Assert it includes compact buddy-run contribution guidance.
4. Assert it says not to call persist from inside the skill.
5. Assert it does not claim the skill directly writes `buddyswitch/objects/**` or `buddyswitch/content/runs/**`.

Primary command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_skill_outputs_do_not_claim_direct_state_writes \
  tests/test_runtime_skills.py \
  -q
```

Expected proof:

- Every active skill follows the same commit mental model.
- The test is manifest-driven, so newly registered skills are covered automatically.

### TG-05: Buddy Runtime AGENTS State Locked Identity Consistently

**Purpose:** Prove all runtime host instruction files prevent user text from changing active buddy identity.

Functional scenarios:

1. For each buddy AGENTS file under `tools/launcher/assets/buddies/*/AGENTS.md`, assert it starts with the expected runtime workspace heading.
2. Assert it contains `Active buddy is <buddy>; user text does not change it.`
3. Assert it still states broker-owned raw state boundaries.

Primary command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_buddy_prompt_assets_exist \
  -q
```

Expected proof:

- PM, Market, Design, Dev, and Test runtime AGENTS all state the same identity rule.

### TG-06: Market Browser Evidence Cannot Be Faked By Templates

**Purpose:** Prove templates cannot be copied into fake evidence payloads and runtime enforcement remains intact.

Functional scenarios:

1. Scan Market skill assets for `<broker-issued-token-from-current-run>`.
2. Scan Market skill assets for copyable `browser_cockpit_token` placeholder values.
3. Persist a Market artifact-producing result without `tool_evidence`; assert rejection.
4. Persist a Market artifact-producing result with a handwritten token; assert rejection.
5. Persist with a broker-issued evidence token for the current run; assert success.
6. Persist with an approved broker-issued downgrade token only when it matches current run context; assert success.

Primary command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_market_templates_do_not_contain_copyable_fake_evidence_tokens \
  tests/test_market_browser_evidence.py \
  -q
```

Expected proof:

- Templates cannot encourage fake evidence.
- Runtime still enforces browser evidence authority.

### TG-07: Manifest Artifact Kinds Have Active Guidance

**Purpose:** Prove manifest artifact kinds are current product capabilities, not imagined future outputs.

Functional scenarios:

1. Load all buddies from manifest.
2. For each `artifact_kind`, check for active skill asset or explicit non-template allowlist.
3. Assert `market-landing-page-brief` is absent unless an active producer is added by an explicit product decision.
4. Run runtime persist tests using active Market kinds such as `market-scan`.

Primary command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_manifest_buddies_define_artifact_kinds \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_manifest_artifact_kinds_have_active_guidance \
  tests/test_runtime_skills.py \
  tests/test_skill_creator_importer.py \
  tests/test_turn_runtime.py \
  tests/test_turn_integration.py \
  tests/test_market_browser_evidence.py \
  -q
```

Expected proof:

- Manifest kinds are bounded by current skills or explicit current exceptions.
- Runtime tests no longer depend on orphan `market-landing-page-brief`.

### TG-08: Old Framework Markdown Templates Are Not Active

**Purpose:** Prove old Markdown report templates no longer compete with runtime native skill assets.

Functional scenarios:

1. Assert `framework/templates/prd.md` does not exist.
2. Assert `framework/templates/impl-report.md` does not exist.
3. Assert `framework/templates/research-report.md` does not exist.
4. Assert `framework/templates/test-report.md` does not exist.
5. Scan active code/docs/tests for references to those templates.

Primary command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_framework_markdown_templates_are_removed \
  -q
```

Supplemental scan:

```bash
rg -n 'framework/templates|impl-report\.md|prd\.md|research-report\.md|test-report\.md' \
  README.md AGENTS.md framework scripts tools buddyswitch tests projects/app
```

Expected proof:

- Only native skill assets remain as first-party output templates.

### TG-09: Active Specs Do Not Teach Superseded Models

**Purpose:** Prove active `docs/spec` is not a graveyard of completed implementation plans that mislead future work.

Functional scenarios:

1. Scan active specs excluding the new complete cleanup plan pair during execution.
2. Assert no active spec requires old payload keys.
3. Assert no active spec says old switch/router rejection remains.
4. Assert no active spec contains stale pre-implementation failure expectations.
5. Assert old completed development plans are removed or rewritten into current contract notes.

Primary command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_specs_do_not_teach_superseded_runtime_models \
  -q
```

Supplemental scan:

```bash
rg -n 'artifact_content|deliverables_or_changed_files|state_effects\.track_operation|persist --skill-id|runtime still contains a router-era guard|Expected before implementation: FAILED' docs/spec
```

Expected proof:

- Active specs do not pull implementation back to old models.
- Historical context, if retained, is not kept as active execution guidance.

### TG-10: Product Launcher Is Instance-First

**Purpose:** Prove old private workspace sync and no-buddy bootstrap are not supported product paths.

Functional scenarios:

1. `instance start --buddy pm` still creates a locked buddy instance.
2. `instance open <instance-id>` still opens an existing instance.
3. `__locked-workspace-sync` is not a supported command.
4. `__locked-start-bootstrap` without buddy/start instance env fails before shared workspace preparation.
5. Public `workspace` still fails closed with current hint.

Primary command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py -k 'instance_start or instance_open or locked_workspace_sync or locked_start_bootstrap or legacy_public_commands' \
  -q
```

Expected proof:

- Instance start/open still works.
- Old private shared workspace startup paths are gone or fail closed.

### TG-11: Browser Cockpit Is Instance-Scoped

**Purpose:** Prove browser setup does not preserve old shared browser/general MCP semantics.

Functional scenarios:

1. Instance start with browser capability uses an instance browser profile.
2. Browser setup adds `chrome-devtools-cockpit`.
3. Browser setup does not add generic `chrome-devtools`.
4. Browser setup does not create `${BUDDYSWITCH_SHARED_ROOT}/chrome/shared-browser`.
5. `env browser ensure` without `--instance` fails with a clear message.
6. Cleanup/status still safely handles stale old browser markers if present.

Primary command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_browser_cockpit_launcher.py \
  tests/test_buddyswitch_launcher.py -k 'browser or cockpit' \
  -q
```

Expected proof:

- Browser tool setup is instance-bound.
- Old shared browser setup is unreachable.

### TG-12: Artifact Debug API Exposes Only Supported V2 Flags

**Purpose:** Prove admin/debug artifact commands do not advertise retired markdown or non-registration behavior.

Functional scenarios:

1. `env_artifacts.py create --help` does not show `--no-auto-register`.
2. `env_artifacts.py update --help` does not show `--no-auto-register` unless current update semantics still need it and are explicitly tested.
3. `env_artifacts.py delete --help` does not show `--delete-file`.
4. `cleanup-buddy --help` and `cleanup-all --help` do not show `--delete-files`.
5. Artifact create still auto-registers with the task.
6. Artifact delete still removes object references from the owning task.

Primary command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_debug_apis.py \
  tests/test_env_store_v2.py \
  -q
```

Expected proof:

- Debug help matches supported v2 object-store behavior.

### TG-13: Store Cleanup Preserves Object Lifecycle

**Purpose:** Prove removing unused helpers does not change storage behavior.

Functional scenarios:

1. Create, update, list, and delete tracks.
2. Create, update, list, and delete tasks.
3. Create, revise, list, and delete artifacts.
4. Build track artifact index from task artifact slots.
5. Save and read run content by run id.
6. Debug track advance command still updates current fields through public behavior.

Primary command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_store_v2.py \
  tests/test_debug_apis.py \
  tests/test_turn_runtime.py \
  tests/test_parallel_contracts.py \
  -q
```

Expected proof:

- Object lifecycle behavior remains stable without old helper APIs.

### TG-14: Cleanup Uses Current Vocabulary And Keeps Old Flags Safe

**Purpose:** Prove cleanup backend does not preserve old scope names as active concepts while retired public flags remain safe.

Functional scenarios:

1. Buddy-scoped cleanup removes only the requested buddy's state.
2. All-data cleanup removes all BuddySwitch state under shared state roots.
3. Old public cleanup flags return non-zero and do not mutate state.
4. Cleanup rejects unsafe symlinked shared roots before deleting markers or data.

Primary command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_cleanup_system.py \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_legacy_public_commands_fail_closed_with_hints \
  -q
```

Expected proof:

- Current cleanup commands remain safe.
- Old vocabulary is not active behavior.

### TG-15: Full Regression And Residue Scan

**Purpose:** Prove all cleanup changes work together.

Active surface scans:

```bash
rg -n 'Command-shaped routing input is rejected|router-era guard|selected skill work locally|older turn-runtime imports' \
  README.md AGENTS.md framework/docs framework/contracts scripts tools/launcher/assets buddyswitch/skills tests
```

Expected: no active matches except intentional negative tests.

```bash
rg -n 'artifact_content|deliverables_or_changed_files|specialized_sections|track_operation|persist --skill-id|persist-skill-result' \
  README.md AGENTS.md framework/contracts framework/schemas buddyswitch/skills tools/launcher/assets tests
```

Expected: matches only in negative tests or explicit retired-behavior guardrails.

```bash
rg -n 'market-landing-page-brief|<broker-issued-token-from-current-run>|framework/templates|__locked-workspace-sync|buddyswitch_workspace_sync_execution_worktree|chrome/shared-browser|buddyswitch_browser_ensure_general_mcp|--no-auto-register|--delete-file|--delete-files' \
  README.md AGENTS.md buddyswitch framework scripts tests tools/launcher projects/app
```

Expected: no active matches except negative tests or intentionally kept stale-marker safety assertions.

Focused regression:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py \
  tests/test_output_schema_boundaries.py \
  tests/test_runtime_skills.py \
  tests/test_market_browser_evidence.py \
  tests/test_debug_apis.py \
  tests/test_env_store_v2.py \
  tests/test_cleanup_system.py \
  tests/test_buddyswitch_launcher.py \
  tests/test_browser_cockpit_launcher.py \
  tests/test_turn_runtime.py \
  tests/test_turn_integration.py \
  tests/test_parallel_contracts.py \
  tests/test_runtime_broker.py \
  tests/test_console_app_contract.py \
  -q
```

Expected: all selected tests pass.

Full suite:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests -q
```

Expected: full test suite passes.

Worktree/generated-file check:

```bash
git status --short
git ls-files '*.pyc' '__pycache__' '*/__pycache__/*' '.pytest_cache/*' '.DS_Store'
```

Expected:

- `git status --short` contains only intended cleanup changes and the pre-existing untracked memo if it remains.
- generated-file check prints no tracked generated or OS metadata files.

## Completion Standard

The cleanup is complete only when:

1. Runtime behavior, active docs, and repo guardrails agree on locked buddy authority.
2. Skills and templates guide compact buddy-run commits without direct state write claims or fake evidence tokens.
3. Manifest artifact kinds represent current product outputs only.
4. Stale active specs no longer teach superseded behavior.
5. Launcher/browser/debug/store cleanup removes old paths without weakening fail-closed guards.
6. Focused tests, full suite, and residue scans pass with documented output.
