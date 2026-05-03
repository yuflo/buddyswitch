# Buddy Instance Contract Residue Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every launcher-managed buddy instance produce the complete current BuddySwitch receipt output contract, while deleting old switch/router/resolve-era contract sources that can mislead future work.

**Architecture:** Collapse product mode around one contract chain: ordinary user request -> `turn_runtime.py prepare` -> host executes exactly one selected skill -> `turn_runtime.py persist` -> final `Receipt` and `Summary` rendering. Runtime metadata belongs in the persist receipt contract; skill output schemas remain artifact/business-output schemas and must not absorb runtime IDs. Remove stale active contract sources instead of layering compatibility guidance.

**Tech Stack:** Python runtime and tests, Bash launcher assets, JSON contract files, Markdown contract docs, pytest/unittest.

---

## Confirmed Target

The user-facing product path is a locked buddy instance. A normal user request in that instance must end with a final terminal output that follows:

```text
Receipt
Persisted: ok|failed
Task: <task_title> [<task_id>]
Track: <track_title> [<track_id>]   # only when present
Artifact: <artifact_id|none>
Run: <run_id>
Related Runs: <run_id_1>, <run_id_2> # only when present

Summary
<1-2 line execution summary, plus at most 4 open questions>
```

The runtime receipt is the source for IDs and paths. The selected skill schema is the source for the business artifact payload.

## Current Evidence From Dev0210

Run from `/Users/chen/Dev/buddyswitch/.worktrees/dev0210`.

- `git status --short --branch` returned `## dev0210...origin/dev0210`, with no dirty files.
- `tools/launcher/env.sh` sets `BUDDYSWITCH_RUNTIME_AGENTS_TEMPLATE` from `tools/launcher/assets/buddies/<buddy>/AGENTS.md` during `instance start --buddy` and `instance open`.
- `tools/launcher/workspace.sh` still has a default template path to `tools/launcher/assets/runtime-AGENTS.md`.
- `tools/launcher/assets/runtime-AGENTS.md` contains the full `Receipt Contract`.
- `tools/launcher/assets/buddies/{market,pm,design,dev,test}/AGENTS.md` are the actual buddy instance prompt assets, but only say `Final terminal output must use Receipt -> Summary`; they do not list required receipt fields.
- `framework/contracts/persist-skill-result.json` freezes only the top-level response keys: `ok`, `receipt`, `refreshed_context`.
- Existing runtime tests prove the real persist receipt already includes `task_id`, `run_id`, `skill_id`, `receipt_paths`, and `next_state`.
- Manifest buddies are `market`, `pm`, `design`, `dev`, and `test`.
- Prompt assets exist for all manifest buddies.
- Buddy contract markdown exists for `market`, `pm`, `dev`, and `test`; `framework/contracts/design.md` is missing.
- Skill output schemas exist for all registered skills and all top-level schemas use `additionalProperties: false`.
- `.codex/agents/router.toml` still references old product concepts: `switch <buddy>`, `scripts/switch_runtime.py`, and `resolve_context`.
- Active docs and tests still contain `resolve_context` naming in browser/market contract language.
- Older `docs/spec` and `docs/memo` files preserve completed or obsolete migration plans that still teach `switch_runtime`, `recommended_switch`, `runtime-AGENTS.md` as prompt source, and old command output contracts.

## Product Boundary Decisions

- Keep `scripts/turn_runtime.py` as the only product runtime entry.
- Keep `scripts/turn_runtime.py prepare` and `scripts/turn_runtime.py persist` CLI names.
- Rename current product contract language from `resolve-context` / `resolve_context` to `prepare-turn-context` / `prepare_context` in active docs, tests, and JSON contract files.
- Do not add `task_id`, `run_id`, `artifact_id`, or `receipt_paths` to skill output schemas.
- Freeze receipt inner shape in `framework/contracts/persist-skill-result.json`.
- Make the five buddy prompt assets carry the full receipt rendering contract.
- Remove `tools/launcher/assets/runtime-AGENTS.md` as an active prompt contract source. Product instance startup must require a buddy prompt template.
- Remove `.codex/agents/router.toml` unless a current product path proves it is still required. The current repo search shows it is stale.
- Delete obsolete switch-era docs and memo files rather than preserving active-looking stale guidance.

## Files To Create, Modify, Or Delete

Create:

- `framework/contracts/prepare-turn-context.json`
- `framework/contracts/design.md`
- New or updated tests in `tests/test_repo_consistency.py`
- New or updated tests in `tests/test_parallel_contracts.py`
- New or updated launcher prompt tests in `tests/test_buddyswitch_launcher.py`

Modify:

- `framework/contracts/persist-skill-result.json`
- `framework/contracts/pm.md`
- `framework/contracts/dev.md`
- `framework/contracts/test.md`
- `framework/contracts/market.md`
- `framework/docs/turn-runtime-spec.md`
- `framework/docs/browser-cockpit.md`
- `framework/docs/architecture-overview.md`
- `framework/docs/skill-architecture-best-practices.md`
- `README.md`
- `AGENTS.md`
- `tools/launcher/env.sh`
- `tools/launcher/workspace.sh`
- `tools/launcher/assets/buddies/market/AGENTS.md`
- `tools/launcher/assets/buddies/pm/AGENTS.md`
- `tools/launcher/assets/buddies/design/AGENTS.md`
- `tools/launcher/assets/buddies/dev/AGENTS.md`
- `tools/launcher/assets/buddies/test/AGENTS.md`
- `tests/test_turn_runtime.py`
- `tests/test_turn_integration.py`
- `tests/test_parallel_contracts.py`
- `tests/test_repo_consistency.py`
- `tests/test_buddyswitch_launcher.py`

Delete:

- `framework/contracts/resolve-context.json`
- `tools/launcher/assets/runtime-AGENTS.md`
- `.codex/agents/router.toml`
- Obsolete docs that are no longer true product contract references:
  - `docs/memo/2026-04-23-online-loop-skill-selection-and-next-turn-memo.md`
  - `docs/memo/2026-04-25-skill-orchestration-gap-review.md`
  - `docs/spec/2026-04-29-buddyswitch-runtime-automation-permissions-plan.md`
  - `docs/spec/2026-04-30-buddyswitch-post-persist-reservation-plan.md`
  - `docs/spec/2026-04-30-buddyswitch-post-persist-reservation-test-plan.md`
  - `docs/spec/2026-05-01-unified-project-app-runtime-projection-plan.md`
  - `docs/spec/2026-05-02-buddy-instance-native-turn-development-plan.md`
  - `docs/spec/2026-05-02-buddy-instance-native-turn-test-plan.md`
  - `docs/spec/2026-05-02-no-switch-buddy-instance-single-turn-plan.md`
  - `docs/spec/2026-05-02-buddy-instance-switch-residue-cleanup-plan.md`
  - `docs/spec/2026-05-02-buddy-instance-switch-residue-cleanup-test-plan.md`

Keep unless direct evidence says otherwise:

- `scripts/turn_runtime.py`
- `framework/schemas/**`
- `buddyswitch/skills/**/skill.toml`
- `buddyswitch/skills/**/SKILL.md`
- `framework/contracts/workspace-projection.json`
- `framework/docs/interface-spec.md`

## Implementation Tasks

### Task 1: Freeze Current Product Contract Names

**Files:**

- Create: `framework/contracts/prepare-turn-context.json`
- Delete: `framework/contracts/resolve-context.json`
- Modify: `tests/test_parallel_contracts.py`
- Modify: `tests/test_repo_consistency.py`
- Modify: `framework/docs/turn-runtime-spec.md`

- [ ] **Step 1: Add a failing contract test for the new prepare contract file**

Add or update tests so the current product context contract is named `prepare-turn-context`, not `resolve-context`.

Required assertions:

```python
EXPECTED_PREPARE_TURN_CONTEXT_CONTRACT = {
    "contract_id": "prepare-turn-context",
    "contract_version": "2026-05-03",
    "response_key_order": [
        "ok",
        "context_revision",
        "instance_id",
        "active_buddy",
        "request_text",
        "current_task_id",
        "current_track_id",
        "task_context",
        "track_context",
        "skills",
        "inputs_by_skill",
        "run_envelope",
        "warnings",
    ],
}
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_parallel_contracts.py::ResolveAndPersistContractTests::test_contract_matches_real_resolve_context_surface -q
```

Expected before implementation: fail because `framework/contracts/prepare-turn-context.json` does not exist or the old test still reads `resolve-context`.

- [ ] **Step 2: Rename the contract file and contract id**

Replace `framework/contracts/resolve-context.json` with:

```json
{
  "contract_id": "prepare-turn-context",
  "contract_version": "2026-05-03",
  "response_key_order": [
    "ok",
    "context_revision",
    "instance_id",
    "active_buddy",
    "request_text",
    "current_task_id",
    "current_track_id",
    "task_context",
    "track_context",
    "skills",
    "inputs_by_skill",
    "run_envelope",
    "warnings"
  ]
}
```

Update test names and constants from `resolve` to `prepare` where those names describe the product turn context.

- [ ] **Step 3: Update active docs to reference the new file**

Change `framework/docs/turn-runtime-spec.md` so the prepare section points to `framework/contracts/prepare-turn-context.json`. Remove references to `framework/contracts/resolve-context.json`.

Run:

```bash
rg -n "framework/contracts/resolve-context.json|contract_id.*resolve-context|RESOLVE_CONTEXT_CONTRACT" framework tests README.md AGENTS.md .codex tools scripts
```

Expected after implementation: no matches outside the cleanup plan and test-plan documents.

- [ ] **Step 4: Verify task**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_parallel_contracts.py tests/test_repo_consistency.py -q
```

Expected: pass.

### Task 2: Freeze Receipt Inner Shape In Persist Contract

**Files:**

- Modify: `framework/contracts/persist-skill-result.json`
- Modify: `tests/test_parallel_contracts.py`
- Modify: `tests/test_turn_runtime.py`
- Modify: `framework/docs/turn-runtime-spec.md`

- [ ] **Step 1: Add failing tests for receipt field presence and semantics**

The persist contract must freeze both top-level response keys and required receipt fields.

Required contract shape:

```json
{
  "contract_id": "persist-skill-result",
  "contract_version": "2026-05-03",
  "response_key_order": ["ok", "receipt", "refreshed_context"],
  "receipt_required_keys": [
    "ok",
    "skill_id",
    "task_id",
    "task_title",
    "artifact_ids",
    "run_id",
    "next_state",
    "receipt_paths",
    "related_run_ids"
  ],
  "receipt_optional_keys": [
    "artifact_id",
    "track_id",
    "track_title",
    "track_action",
    "warnings"
  ],
  "receipt_forbidden_keys": [
    "reference_switches",
    "recommended_switch"
  ]
}
```

Test artifact skill behavior:

- `receipt.task_id` is a non-empty string.
- `receipt.task_title` is a non-empty string.
- `receipt.artifact_id` is present for artifact-producing skills.
- `receipt.artifact_ids` contains `receipt.artifact_id`.
- `receipt.run_id` equals the prepared `run_envelope.run_id`.
- `receipt.receipt_paths.task`, `receipt.receipt_paths.run`, and artifact paths exist.
- `receipt.next_state.task_id` equals `receipt.task_id`.
- `receipt.reference_switches` and `receipt.recommended_switch` are absent.

Test track-manager behavior:

- `receipt.artifact_ids` is an empty list.
- `receipt.artifact_id` is absent or treated as `none` by prompt rendering.
- `receipt.track_id` is present when a track is created or updated.
- `receipt.track_action` matches the track operation.

- [ ] **Step 2: Update `persist-skill-result.json`**

Add the receipt key lists exactly enough for contract freeze. Do not embed full JSON Schema unless the tests require schema validation; keep it a contract manifest, not a new framework.

- [ ] **Step 3: Update runtime spec**

In `framework/docs/turn-runtime-spec.md`, add a `Receipt Contract` section that lists the same required and optional receipt keys and states that terminal rendering must derive user-visible IDs from `receipt`.

- [ ] **Step 4: Verify task**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_turn_runtime.py::TurnRuntimeBehaviorTests::test_successful_persist_returns_structured_receipt_contract tests/test_parallel_contracts.py -q
```

Expected: pass.

### Task 3: Make Buddy Prompt Assets The Complete Runtime Prompt Contract

**Files:**

- Modify: `tools/launcher/assets/buddies/market/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/pm/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/design/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/dev/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/test/AGENTS.md`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add failing prompt asset tests**

For every manifest buddy, assert the buddy prompt includes:

```text
Receipt
Persisted: ok|failed
Task: <task_title> [<task_id>]
Track: <track_title> [<track_id>]
Artifact: <artifact_id|none>
Run: <run_id>
Related Runs: <run_id_1>, <run_id_2>
Summary
```

Also assert the prompt does not contain:

```text
Receipt -> Commands -> Summary
switch <buddy>
switch pm:
recommended_switch
reference_switches
```

- [ ] **Step 2: Update all five buddy prompts**

Replace the current short `Persistence And Final Output` section with explicit `Receipt Contract` and `Summary Contract` sections. The text must instruct the host to render IDs from the persist `receipt`, not from object path debug output.

Required shared block:

```markdown
## Receipt Contract

- Final terminal output must use exactly two sections in this order: `Receipt`, `Summary`.
- In `Receipt`, render:
  - `Persisted: ok|failed`
  - `Task: <task_title> [<task_id>]`
  - `Track: <track_title> [<track_id>]` only when `receipt.track_id` exists
  - `Artifact: <artifact_id|none>`
  - `Run: <run_id>`
  - `Related Runs: <run_id_1>, <run_id_2>` only when present
- Use IDs and titles from `receipt`; object paths stay debug-only details.

## Summary Contract

- Keep execution summary to 1-2 lines.
- Keep open questions to at most 4 items.
- Do not lead with object paths or artifact filenames.
```

- [ ] **Step 3: Update launcher integration tests**

For `instance start --buddy pm` and one non-PM buddy, assert generated workspace `AGENTS.md` equals the relevant buddy prompt and contains the complete receipt fields.

- [ ] **Step 4: Verify task**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_buddy_prompt_assets_exist_for_every_manifest_buddy tests/test_buddyswitch_launcher.py -q
```

Expected: pass.

### Task 4: Remove Generic Runtime Prompt As Active Source

**Files:**

- Delete: `tools/launcher/assets/runtime-AGENTS.md`
- Modify: `tools/launcher/workspace.sh`
- Modify: `tools/launcher/env.sh`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `AGENTS.md`

- [ ] **Step 1: Add failing tests that no product path defaults to `runtime-AGENTS.md`**

Required behavior:

- `instance start --buddy <buddy>` and `instance open <instance-id>` must explicitly select `tools/launcher/assets/buddies/<buddy>/AGENTS.md`.
- No product launcher path should install `tools/launcher/assets/runtime-AGENTS.md`.
- If a generic workspace path tries to install an AGENTS template without a buddy template, it must fail with a clear error instead of silently using a stale generic prompt.

- [ ] **Step 2: Remove the default template path**

In `tools/launcher/workspace.sh`, remove the default assignment:

```bash
default_template="${repo_root}/tools/launcher/assets/runtime-AGENTS.md"
export BUDDYSWITCH_RUNTIME_AGENTS_TEMPLATE="${BUDDYSWITCH_RUNTIME_AGENTS_TEMPLATE:-${default_template}}"
```

Replace it with an unset-by-default contract. `buddyswitch_workspace_install_runtime_agents` must require `BUDDYSWITCH_RUNTIME_AGENTS_TEMPLATE` to be set and point to an existing file.

- [ ] **Step 3: Delete the stale generic prompt file**

Delete `tools/launcher/assets/runtime-AGENTS.md`.

- [ ] **Step 4: Update root guidance**

In `AGENTS.md`, replace the stale statement that the execution worktree carries the full contract in `tools/launcher/assets/runtime-AGENTS.md`. State that product instances load `tools/launcher/assets/buddies/<buddy>/AGENTS.md`.

- [ ] **Step 5: Verify task**

Run:

```bash
rg -n "runtime-AGENTS.md|assets/runtime-AGENTS" README.md AGENTS.md tools tests framework buddyswitch/manifest.toml .codex
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py tests/test_repo_consistency.py -q
```

Expected: no `runtime-AGENTS.md` matches outside current cleanup documents; tests pass.

### Task 5: Complete Buddy Contract Coverage

**Files:**

- Create: `framework/contracts/design.md`
- Modify: `framework/contracts/pm.md`
- Modify: `framework/contracts/dev.md`
- Modify: `framework/contracts/test.md`
- Modify: `framework/contracts/market.md`
- Modify: `framework/docs/browser-cockpit.md`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add failing manifest-to-contract coverage test**

For every manifest buddy, assert `framework/contracts/<buddy>.md` exists and includes:

```text
Terminal final output must follow `Receipt -> Summary`
Task with [task-id]
Artifact
Run
Related Runs
persist-skill-result
```

- [ ] **Step 2: Create `framework/contracts/design.md`**

The design contract must describe `shape-prototype` responsibilities, artifact output boundaries, and the same terminal receipt rules used by the other buddies.

- [ ] **Step 3: Align existing buddy contracts**

Replace old `resolve_context.skills[*]` wording with `prepare_context.skills[*]` where the doc is describing the current product context. Keep browser-native market behavior, but remove old naming.

- [ ] **Step 4: Verify task**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
rg -n "resolve_context" framework/contracts framework/docs README.md AGENTS.md tools .codex
```

Expected: no active docs or prompt matches for `resolve_context`.

### Task 6: Delete Old Router And Switch-Era Active Config

**Files:**

- Delete: `.codex/agents/router.toml`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_turn_integration.py`

- [ ] **Step 1: Add failing residue guard for active config**

Assert `.codex/agents/router.toml` does not exist, or if a future router config is introduced, it must not mention:

```text
switch <buddy>
scripts/switch_runtime.py
resolve_context
scripts/debug/codex_router.py
scripts/debug/parse_switch.py
```

- [ ] **Step 2: Delete `.codex/agents/router.toml`**

The current file references deleted or retired concepts and is not part of launcher-managed product mode.

- [ ] **Step 3: Update tests that mention debug router deletion**

Keep negative assertions that product runtime does not import `parse_switch` or `codex_router`, but avoid relying on deleted module paths as active runtime concepts.

- [ ] **Step 4: Verify task**

Run:

```bash
rg -n "codex_router|parse_switch|switch <buddy>|scripts/switch_runtime.py|resolve_context" .codex tools scripts framework README.md AGENTS.md buddyswitch/manifest.toml tests
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_turn_runtime.py tests/test_turn_integration.py tests/test_repo_consistency.py -q
```

Expected: no active config or runtime matches except guard tests that assert absence.

### Task 7: Delete Obsolete Historical Contract Docs

**Files:**

- Delete stale files listed in the Delete section.
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add a docs residue guard**

For current product docs, assert no old product protocol terms remain:

```text
scripts/switch_runtime.py
receipt.recommended_switch
reference_switches
recommended_switch
Receipt -> Commands -> Summary
tools/launcher/assets/runtime-AGENTS.md
switch <buddy>
switch pm:
```

Allow only this current cleanup plan and its paired test plan to mention old terms as historical evidence.

- [ ] **Step 2: Delete obsolete docs/memo and docs/spec files**

Delete the stale files listed earlier. These were useful during migration but now encode the wrong product path and should not remain as searchable guidance.

- [ ] **Step 3: Verify task**

Run:

```bash
rg -n "scripts/switch_runtime.py|receipt.recommended_switch|reference_switches|recommended_switch|Receipt -> Commands -> Summary|runtime-AGENTS.md|switch <buddy>|switch pm:" docs README.md AGENTS.md framework tools .codex
```

Expected: matches only in `docs/spec/2026-05-03-buddy-instance-contract-residue-cleanup-plan.md` and `docs/spec/2026-05-03-buddy-instance-contract-residue-cleanup-test-plan.md`.

### Task 8: Guard Skill Schema Boundary

**Files:**

- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_turn_runtime.py`

- [ ] **Step 1: Add schema boundary tests**

For every `framework/schemas/**.json`, assert top-level `properties` does not include runtime receipt keys:

```python
runtime_keys = {
    "task_id",
    "task_title",
    "artifact_id",
    "artifact_ids",
    "run_id",
    "receipt_paths",
    "next_state",
    "related_run_ids",
}
```

Also assert each schema still requires the skill output fields:

```text
execution_summary
working_notes
deliverables_or_changed_files
```

For artifact-producing skills, assert `artifact_content` remains required.

- [ ] **Step 2: Add behavior test for wrong metadata placement**

Persist a valid skill result that contains a top-level extra `task_id`; it must fail schema validation before writing state. Then persist the valid result without extra runtime metadata; it must succeed and return `receipt.task_id`.

- [ ] **Step 3: Verify task**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_turn_runtime.py tests/test_repo_consistency.py -q
```

Expected: pass.

### Task 9: Full Verification And Residue Scan

**Files:** No new source files unless failures reveal a missed active path.

- [ ] **Step 1: Run targeted contract suites**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py \
  tests/test_turn_integration.py \
  tests/test_parallel_contracts.py \
  tests/test_buddyswitch_launcher.py \
  tests/test_repo_consistency.py \
  -q
```

Expected: pass.

- [ ] **Step 2: Run broader relevant suite**

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

Expected: pass.

- [ ] **Step 3: Run final residue scan**

```bash
rg -n "scripts/switch_runtime.py|switch_runtime|resolve_context|resolve-context|runtime-AGENTS.md|Receipt -> Commands -> Summary|recommended_switch|reference_switches|codex_router|parse_switch|switch <buddy>|switch pm:" \
  README.md AGENTS.md .codex tools scripts framework tests buddyswitch/manifest.toml docs
```

Expected: matches only where tests define forbidden-token guards and in this cleanup plan/test plan. Active runtime, launcher, prompt, contract, and current docs must have no old product-path guidance.

- [ ] **Step 4: Run syntax checks**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/turn_runtime.py scripts/env_manifest.py scripts/output_schema.py scripts/runtime_store/projections.py
git diff --check
```

Expected: pass.

## Acceptance Criteria

- Every manifest buddy has a buddy prompt asset and a buddy contract markdown file.
- Generated buddy instance `AGENTS.md` includes the full `Receipt` and `Summary` rendering contract.
- `persist-skill-result.json` freezes receipt inner fields, not just top-level keys.
- `prepare-turn-context` naming replaces product-facing `resolve-context` naming.
- `runtime-AGENTS.md` is not an active or fallback product prompt source.
- `.codex/agents/router.toml` and old router/switch files are not active config.
- Skill output schemas remain business-output schemas and reject runtime receipt metadata.
- Obsolete docs that teach old product paths are deleted, not patched around.
- Automated tests prove both successful output and absence of old active paths.

## Self-Review Checklist

- This plan targets the confirmed bottleneck: buddy instances produce incomplete final receipts because actual buddy prompts and runtime contracts are not aligned.
- This plan avoids speculative abstraction: no new prompt-generation system, no workflow engine, no broad schema framework.
- This plan replaces baggage: delete stale generic prompt, router config, old contract filename, and obsolete docs.
- This plan preserves valid boundaries: runtime receipt metadata remains separate from skill output schemas.
- This plan includes direct verification commands and final residue scans.
