# Buddy-Level Schema-Only Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move artifact persistence from skill-specific schemas to five buddy-level result schemas without keeping a runtime bridge or compatibility adapter.

**Architecture:** Codex executes the native skill from `.agents/skills/<skill-id>`. The skill emits buddy-level result JSON directly, then `scripts/turn_runtime.py persist --skill-id <native-skill-id>` validates that JSON through the manifest `output_schema` and writes canonical task, artifact, run, and receipt state. In this task, "bridge" means the buddy-level schema surface is the bridge; it does not mean a separate runtime conversion module.

**Tech Stack:** Python runtime scripts, TOML manifest, JSON schemas validated by `scripts/output_schema.py`, Markdown skill/runtime docs, pytest/unittest.

---

## Working Directory

Run all implementation and verification from:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0210
```

Do not edit the main checkout at `/Users/chen/Dev/buddyswitch` for this task.

## Preflight Gate

Target outcome and bottleneck:

- Outcome: artifact-producing PM, Dev, Test, Market, and Design skills persist through one schema per buddy while preserving the native producing `skill_id`.
- Current bottleneck: dev0210 still contains bridge-module residue that turns a schema simplification into a runtime compatibility layer.
- Verifiable improvement: no active runtime path, prompt, test, or required file depends on a native-output conversion module; representative current skills and a community-style compatible skill persist directly with buddy-level JSON.

Confirmed facts:

- `scripts/turn_runtime.py` resolves the selected native skill by active buddy membership before persistence.
- `scripts/turn_runtime.py` validates `result` with `skill.persistence.output_schema` before writing artifact or run state.
- `scripts/turn_runtime.py` writes artifact and run metadata with the selected native `skill_id`.
- `buddyswitch/manifest.toml` already maps artifact skills to `pm-result`, `dev-result`, `test-result`, `market-result`, or `design-result`.
- `framework/schemas/*/*-result.json` already exist for the five buddy-level artifact surfaces.
- `scripts/result_bridge.py`, `tests/test_result_bridge.py`, bridge-only runtime docs, and bridge-required prompt assertions are the current historical/transition burden.

Open assumptions and invalidators:

- Assumption: Task 1 may require community/generated-like skills to emit BuddySwitch buddy-level result JSON directly.
- Assumption: arbitrary native output conversion is outside Task 1 unless a future product decision explicitly revives it.
- Invalidator: if an external user or published API already depends on `scripts/result_bridge.py`, stop and confirm whether compatibility outweighs SHARP removal.
- Invalidator: if the desired product semantics still require "community skill never emits BuddySwitch JSON", stop and confirm because that reintroduces a runtime adapter.
- Invalidator: if any implementation step needs to change `track-manager` state semantics, stop and split that into Task 2.

Permissions and boundaries:

- Use normal workspace writes inside `.worktrees/dev0210`.
- Do not run destructive git commands.
- Do not change `track-manager` except to keep existing tests passing.
- Do not add compatibility wrappers, dual paths, or fallback conversion branches.

Verification plan and stop condition:

- Stop when focused tests prove schema contracts, manifest mapping, direct persist success, community direct persist, docs consistency, launcher prompt copy, runtime skill materialization, and `track-manager` non-regression.
- Completion requires fresh test output from the commands in the final verification section.

## Target Runtime Flow

```text
Codex CLI executes .agents/skills/<skill-id>/SKILL.md
-> skill emits buddy-level result JSON
-> scripts/turn_runtime.py persist --skill-id <native-skill-id> --result <result.json>
-> persist validates the buddy-level schema from manifest
-> persist writes artifact/run/receipt with the native skill_id
```

No step calls a runtime bridge module.

## Scope

Keep:

- Five buddy-level artifact schemas:
  - `framework/schemas/pm/pm-result.json`
  - `framework/schemas/dev/dev-result.json`
  - `framework/schemas/test/test-result.json`
  - `framework/schemas/market/market-result.json`
  - `framework/schemas/design/design-result.json`
- Manifest mapping from each artifact-producing native skill id to its buddy-level schema.
- Product-visible `output_slot` values such as `prd`, `implementation-report`, and `market-scan`.
- Native `skill_id` in receipt, artifact object, and run audit.
- `persist` as the only canonical validation/write boundary.
- `track-manager` as the current non-artifact PM special case.

Delete:

- `scripts/result_bridge.py`
- `tests/test_result_bridge.py`
- Bridge-only tests that prove conversion from arbitrary native output.
- Active docs and prompts that instruct `native output -> result bridge -> persist`.
- Test assertions that require active docs or prompt assets to mention the bridge module.

Rewrite:

- Current skill docs and templates to say the skill must emit buddy-level result JSON directly.
- Community-style fixture and tests to prove a registered compatible skill can persist a valid buddy-level payload with its own native `skill_id`.
- Repo consistency tests to reject active references to the removed runtime bridge module.
- Output schema tests that still use retired schema names as negative fixtures; use neutral invalid paths instead.

## Buddy-Level Result Contract

All artifact-producing skills emit this top-level envelope:

```json
{
  "execution_summary": "string",
  "working_notes": ["string"],
  "deliverables_or_changed_files": ["string"],
  "artifact_content": {}
}
```

Runtime receipt metadata stays outside result payloads:

- `task_id`
- `task_title`
- `track_id`
- `track_title`
- `artifact_id`
- `artifact_ids`
- `run_id`
- `receipt_paths`
- `related_run_ids`
- `next_state`
- `paths`
- `writes`

Buddy-specific required `artifact_content` surfaces:

| Buddy | Required content fields |
| --- | --- |
| PM | `summary`, `problem`, `user_value`, `requirements`, `scope`, `decisions`, `risks`, `open_questions`, `suggested_next_step` |
| Dev | `task_summary`, `changed_files`, `implementation_notes`, `verification`, `risks`, `follow_ups` |
| Test | `test_scope`, `checks_run`, `passed_items`, `failed_items`, `blocked_items`, `reproduction_notes`, `readiness` |
| Market | `research_question`, `evidence`, `insights`, `assumptions`, `risks`, `conclusion`, `recommended_next_step`, `specialized_sections` |
| Design | `design_goal`, `flow_or_screen_summary`, `interaction_notes`, `assets_or_preview_refs`, `handoff_notes`, `open_questions` |

## File Map

Delete:

- `scripts/result_bridge.py`
- `tests/test_result_bridge.py`

Modify:

- `README.md`
- `buddyswitch/skills/pm/write-prd/SKILL.md`
- `buddyswitch/skills/dev/implement-task/SKILL.md`
- `buddyswitch/skills/test/smoke-test/SKILL.md`
- `buddyswitch/skills/design/shape-prototype/SKILL.md`
- `buddyswitch/skills/market/research-scan/SKILL.md`
- `buddyswitch/skills/market/pmf-recon/SKILL.md`
- `buddyswitch/skills/market/customer-discovery/SKILL.md`
- `buddyswitch/skills/market/positioning-copy/SKILL.md`
- `buddyswitch/skills/market/channel-discovery/SKILL.md`
- `buddyswitch/skills/market/launch-prep/SKILL.md`
- `buddyswitch/skills/**/assets/*.md`
- `framework/docs/skill-runtime-shared-rules.md`
- `framework/docs/skill-architecture-best-practices.md`
- `framework/docs/turn-runtime-spec.md`
- `framework/contracts/pm.md`
- `framework/contracts/dev.md`
- `framework/contracts/test.md`
- `framework/contracts/market.md`
- `framework/contracts/design.md`
- `tools/launcher/assets/buddies/pm/AGENTS.md`
- `tools/launcher/assets/buddies/dev/AGENTS.md`
- `tools/launcher/assets/buddies/test/AGENTS.md`
- `tools/launcher/assets/buddies/design/AGENTS.md`
- `tools/launcher/assets/buddies/market/AGENTS.md`
- `tests/fixtures/community-skills/dev-summary/SKILL.md`
- `tests/test_turn_runtime.py`
- `tests/test_repo_consistency.py`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_output_schema_boundaries.py`
- `tests/test_env_manifest_v2.py`
- `tests/test_runtime_skills.py`

Preserve:

- `framework/schemas/pm/pm-result.json`
- `framework/schemas/dev/dev-result.json`
- `framework/schemas/test/test-result.json`
- `framework/schemas/market/market-result.json`
- `framework/schemas/design/design-result.json`
- `framework/schemas/pm/track-manager.json`
- `buddyswitch/skills/pm/track-manager/SKILL.md`

## Implementation Tasks

### Task 1: Remove Runtime Bridge Code

**Files:**

- Delete: `scripts/result_bridge.py`
- Delete: `tests/test_result_bridge.py`
- Modify: `tests/test_turn_runtime.py`

- [ ] **Step 1: Delete the bridge module and its dedicated test file**

Remove the files entirely. Do not replace them with shims, wrappers, deprecation aliases, or compatibility imports.

- [ ] **Step 2: Remove bridge imports from runtime tests**

In `tests/test_turn_runtime.py`, delete any `importlib.import_module("result_bridge")` usage and any test setup that calls bridge code.

- [ ] **Step 3: Convert the community runtime test to direct buddy-level output**

Rename the test from bridge behavior to direct persistence behavior. The test should register `dev-summary` as a Dev skill and persist this kind of payload directly:

```python
direct_dev_result = {
    "execution_summary": "Summarized checkout banner implementation.",
    "working_notes": ["Kept changes scoped to projects/app."],
    "deliverables_or_changed_files": ["projects/app/main.js"],
    "artifact_content": {
        "task_summary": "Summarized checkout banner implementation.",
        "changed_files": ["projects/app/main.js"],
        "implementation_notes": ["Confirmed implementation details from changed files."],
        "verification": {
            "checks_run": ["npm test"],
            "passed": ["Unit tests passed"],
            "failed": [],
            "blocked": ["Manual browser smoke not run"],
        },
        "risks": ["Manual browser smoke not run"],
        "follow_ups": ["Run browser smoke test before release."],
    },
}
```

Assert the receipt, artifact object, and run audit all keep `skill_id == "dev-summary"`.

- [ ] **Step 4: Keep wrong-buddy membership rejection**

Use the same direct payload and assert PM context rejects `skill_id="dev-summary"` without writing state.

- [ ] **Step 5: Run focused runtime test**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_turn_runtime.py::TurnRuntimeTests::test_community_skill_direct_buddy_result_persists_with_native_skill_id -q
```

Expected after implementation: one test passes.

### Task 2: Make Active Runtime Docs Direct-Emit Only

**Files:**

- Modify: `README.md`
- Modify: `framework/docs/skill-runtime-shared-rules.md`
- Modify: `framework/docs/skill-architecture-best-practices.md`
- Modify: `framework/docs/turn-runtime-spec.md`
- Modify: `tools/launcher/assets/buddies/*/AGENTS.md`

- [ ] **Step 1: Replace the runtime loop wording**

Use this flow in active docs and prompt assets:

```text
prepare-turn-context
-> Codex CLI discovers .agents/skills/<skill-id>
-> native skill emits buddy-level result JSON
-> persist-skill-result with the native skill_id
```

- [ ] **Step 2: Remove bridge CLI examples**

Delete any active CLI example that runs the removed bridge module. Keep only `prepare` and `persist` examples.

- [ ] **Step 3: Preserve the receipt contract**

Keep the documented receipt fields:

- `ok`
- `skill_id`
- `task_id`
- `task_title`
- `artifact_id`
- `artifact_ids`
- `run_id`
- `next_state`
- `receipt_paths`
- `related_run_ids`

- [ ] **Step 4: Run docs residue scan**

```bash
rg -n "result_bridge|native output ->|bridge it with" README.md framework tools
```

Expected after implementation: no matches in active runtime docs or buddy prompt assets.

### Task 3: Update Skill Instructions And Templates

**Files:**

- Modify: `buddyswitch/skills/pm/write-prd/SKILL.md`
- Modify: `buddyswitch/skills/dev/implement-task/SKILL.md`
- Modify: `buddyswitch/skills/test/smoke-test/SKILL.md`
- Modify: `buddyswitch/skills/design/shape-prototype/SKILL.md`
- Modify: `buddyswitch/skills/market/*.md`
- Modify: `buddyswitch/skills/**/assets/*.md`
- Modify: `framework/contracts/*.md`

- [ ] **Step 1: Replace bridge language with direct output language**

Use this invariant:

```text
Emit the buddy-level result JSON directly, then call persist with the native skill_id.
```

- [ ] **Step 2: Keep workflow-specific product guidance**

Preserve each skill's useful product workflow. Only the persistence contract changes.

- [ ] **Step 3: Keep market specialization under `specialized_sections`**

For market skills, keep skill-specific details under `artifact_content.specialized_sections` while requiring the shared market fields.

- [ ] **Step 4: Verify no deleted schema filenames remain in active skill docs**

```bash
rg -n "write-prd\\.json|implement-task\\.json|smoke-test\\.json|shape-prototype\\.json|research-scan\\.json|pmf-recon\\.json|customer-discovery\\.json|positioning-copy\\.json|channel-discovery\\.json|launch-prep\\.json" buddyswitch framework tools README.md
```

Expected after implementation: no active references to deleted artifact-producing schema files.

### Task 4: Tighten Repo And Launcher Consistency Tests

**Files:**

- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Remove required bridge tokens**

Delete assertions that require prompt assets or copied launcher workspaces to contain bridge-module text.

- [ ] **Step 2: Add direct-emission required tokens**

Require these active runtime semantics instead:

- `.agents/skills`
- `codex cli`
- `native skill`
- `buddy-level result json`
- `persist`
- `skill_id`
- `runs/raw/`
- `projects/app`
- `## receipt contract`
- `## summary contract`

- [ ] **Step 3: Add bridge absence assertions**

Assert active docs and prompt assets do not contain:

- `result_bridge`
- `scripts/result_bridge.py`
- `bridge it with`
- `native output ->`

- [ ] **Step 4: Keep launcher copy behavior unchanged**

The launcher test should still prove `tools/launcher/assets/buddies/<buddy>/AGENTS.md` is copied byte-for-byte into the runtime workspace.

- [ ] **Step 5: Run consistency tests**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py tests/test_buddyswitch_launcher.py -q
```

Expected after implementation: tests pass without bridge-required assertions.

### Task 5: Lock Schema And Manifest Boundaries

**Files:**

- Modify: `tests/test_output_schema_boundaries.py`
- Modify: `tests/test_env_manifest_v2.py`

- [ ] **Step 1: Keep five buddy-level schema tests**

Ensure tests validate the common envelope, required buddy-specific fields, `additionalProperties: false`, and rejection of runtime metadata.

- [ ] **Step 2: Use neutral invalid schema paths**

If a negative test needs an invalid schema path, use a neutral path such as:

```python
"framework/schemas/dev/not-a-real-schema.json"
```

Do not keep retired schema filenames as test fixtures.

- [ ] **Step 3: Assert artifact-producing manifest entries use buddy-level schemas**

Expected mapping:

- PM artifact skills use `framework/schemas/pm/pm-result.json`
- Dev artifact skills use `framework/schemas/dev/dev-result.json`
- Test artifact skills use `framework/schemas/test/test-result.json`
- Market artifact skills use `framework/schemas/market/market-result.json`
- Design artifact skills use `framework/schemas/design/design-result.json`

- [ ] **Step 4: Keep `track-manager` exception explicit**

Assert `track-manager` remains `produces_artifact = false` and keeps `framework/schemas/pm/track-manager.json`.

- [ ] **Step 5: Run schema and manifest tests**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_output_schema_boundaries.py tests/test_env_manifest_v2.py -q
```

Expected after implementation: tests pass.

### Task 6: Update Community-Compatible Fixture

**Files:**

- Modify: `tests/fixtures/community-skills/dev-summary/SKILL.md`
- Modify: `tests/test_runtime_skills.py`

- [ ] **Step 1: Reword the fixture as BuddySwitch-compatible, not bridge-only**

The fixture should describe a normal Codex skill that emits the Dev buddy-level result JSON directly. It must not mention retired schema filenames or a runtime bridge.

- [ ] **Step 2: Keep package materialization checks**

The fixture still proves a registered external-style package can materialize under `.agents/skills/dev-summary`.

- [ ] **Step 3: Run runtime skill materialization tests**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py -q
```

Expected after implementation: tests pass.

### Task 7: Full Verification

- [ ] **Step 1: Compile runtime scripts**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/turn_runtime.py scripts/env_manifest.py scripts/output_schema.py scripts/runtime_skills.py
```

- [ ] **Step 2: Run focused test set**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_output_schema_boundaries.py tests/test_turn_runtime.py tests/test_env_manifest_v2.py tests/test_runtime_skills.py tests/test_repo_consistency.py tests/test_buddyswitch_launcher.py -q
```

- [ ] **Step 3: Run bridge residue scan**

```bash
rg -n "result_bridge|scripts/result_bridge.py|bridge it with|native output ->" README.md framework buddyswitch tools tests
```

Expected after implementation: matches are absent except in tests that explicitly assert those strings are forbidden.

- [ ] **Step 4: Run retired schema residue scan**

```bash
rg -n "write-prd\\.json|implement-task\\.json|smoke-test\\.json|shape-prototype\\.json|research-scan\\.json|pmf-recon\\.json|customer-discovery\\.json|positioning-copy\\.json|channel-discovery\\.json|launch-prep\\.json" README.md framework buddyswitch tools tests
```

Expected after implementation: matches are absent except historical memo/spec documents if intentionally scanned separately.

## Completion Criteria

This task is complete only when:

- `scripts/result_bridge.py` and `tests/test_result_bridge.py` are gone.
- No active runtime docs or prompt assets require a runtime bridge.
- Artifact-producing skills emit buddy-level result JSON directly.
- Representative current skills persist through buddy-level schemas.
- A community-style compatible Dev skill persists directly under its native `skill_id`.
- Invalid buddy-level outputs fail before state writes.
- `track-manager` remains unchanged.
- Fresh verification commands prove the claims.

## Stop And Confirm Cases

Stop and ask the user before proceeding if any of these occur:

- A real external compatibility contract requires keeping the runtime bridge module.
- The product requirement changes back to "community skills must not emit BuddySwitch buddy-level JSON."
- A fix requires changing `track-manager` persistence semantics.
- A compatibility wrapper, fallback converter, or long-lived dual path appears necessary.
- Verification shows old persisted state needs migration for this task.
