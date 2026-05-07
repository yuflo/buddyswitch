# BuddySwitch Historical Residue Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove active historical residue that still teaches or enforces old BuddySwitch runtime models, and converge active code, contracts, schemas, skills, templates, tests, and docs on one compact buddy-run product path.

**Architecture:** Keep the current product-mode runtime direction: locked buddy identity comes from launcher instance metadata, env profiles define capability boundaries, `prepare` reserves a buddy run, and `persist` commits one compact buddy-run payload. Remove active old authoring shapes and legacy-labeled store indirection instead of preserving parallel compatibility models.

**Tech Stack:** Python runtime and tests, JSON schema files validated by `scripts/output_schema.py`, Markdown contracts/skills/templates, local `pytest`, repository consistency scans.

---

## Working Directory

Run all work from:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0210
```

Do not edit `/Users/chen/Dev/buddyswitch` main checkout. The `dev0210` worktree is already present and separate from `main`.

## Source Inputs

Primary task memo:

- `docs/memo/2026-05-07-buddyswitch-historical-residue-cleanup-audit-memo.md`

Already separated sub-plan:

- `docs/spec/2026-05-07-switch-command-residue-cleanup-development-plan.md`
- `docs/spec/2026-05-07-switch-command-residue-cleanup-test-plan.md`

Current canonical runtime contract:

- `framework/contracts/persist-buddy-run.json`
- `scripts/turn_runtime.py::_validate_buddy_run_commit`

## Current Bottleneck

The env/tool-layer iteration moved the runtime toward the correct model, but active surfaces still preserve old mental models:

- old result authoring keys: `deliverables_or_changed_files`, `artifact_content`, and `specialized_sections`
- retired PM track mutation key: `state_effects.track_operation`
- store implementation names and wrappers still labeled `_legacy_*`
- smaller active wording that still implies selected-skill or compatibility-era execution

These are active product-path residues, not archived historical notes. They can cause buddies to inspect source or schemas to reconcile conflicting instructions instead of following one concise product recipe.

## Preflight Gate

Target outcome:

- Active schemas, contracts, skills, templates, and runtime docs describe one compact buddy-run commit payload.
- PM track lifecycle authoring uses `state_effects.track`, not `track_operation`.
- Store code no longer calls the current object store implementation `legacy`.
- Runtime behavior covered by existing buddy-run persist tests remains intact.
- Archived specs and memos may keep historical language, but active product surfaces must not.

Confirmed facts:

- `framework/contracts/persist-buddy-run.json` already names the compact commit keys: `execution_summary`, optional `working_notes`, `artifacts`, `state_effects`, `handoff`, `contributors`, and `tool_evidence`.
- `scripts/turn_runtime.py` validates `artifacts[]`, `state_effects.track`, `state_effects.task`, `handoff`, `contributors`, and market `tool_evidence`.
- `framework/schemas/*/*-result.json` still require the old `deliverables_or_changed_files` and `artifact_content` envelope.
- `tests/test_output_schema_boundaries.py` still treats the old envelope as the common schema boundary.
- `buddyswitch/skills/**/SKILL.md` and `buddyswitch/skills/**/assets/*.md` still teach old result keys in active packages.
- `scripts/env_store.py` still defines current store implementation functions as `_legacy_*`.
- `scripts/runtime_store/repositories.py` delegates repository entrypoints back to `env_store._legacy_*`.
- `tests/test_env_store_v2.py` explicitly asserts the legacy delegation layer.
- `scripts/turn_runtime.py` no longer contains the old switch-shaped request rejection path, so Batch 1 is now a verification guardrail, not fresh implementation.

Open assumptions and invalidators:

- Do not change runtime semantics merely to satisfy schema cleanup. The compact schema should match the existing persist validator unless a failing test proves the validator contract is wrong.
- Do not weaken market browser evidence gate behavior while updating market authoring docs.
- Do not remove manual debug APIs in this change set; evaluate them after the four main groups.
- If any external CLI command contract relies on `runtime_store` repository entrypoints, stop and decide whether to keep a renamed compatibility facade. Do not preserve wrappers only because tests assert them today.

Tools and permissions:

- No network access is required.
- Use `apply_patch` for manual edits.
- Keep edits in the `dev0210` worktree.
- Use targeted `pytest` loops first, then active-surface scans and focused integration tests.

Verification plan:

- Add or update tests from public behavior and active contracts first.
- Confirm targeted tests fail before implementation where practical.
- Make one batch of changes at a time.
- Run targeted tests after each batch.
- Run final residue scans against active surfaces only.

Stop condition:

- Targeted tests pass.
- Active surface scans find no old authoring contract, `track_operation`, or `_legacy_*` store residue in active paths.
- Existing buddy-run persist and browser evidence tests still pass.

## Target Compact Buddy-Run Commit

All active authoring surfaces should teach this shape as the only commit model:

```json
{
  "execution_summary": "Non-empty summary suitable for downstream artifact selection.",
  "working_notes": [
    "Optional concise note about choices, evidence, or verification."
  ],
  "artifacts": [
    {
      "kind": "manifest-artifact-kind",
      "title": "Human-readable artifact title",
      "summary": "Optional artifact summary; defaults to empty string at persist time.",
      "content": {
        "buddy_specific_field": "Structured content owned by the active skill or buddy."
      }
    }
  ],
  "state_effects": {
    "task": {
      "status": "active",
      "summary": "Optional current task summary."
    },
    "track": {
      "action": "advance",
      "track_id": "track-example",
      "next_buddy": "dev",
      "summary": "Optional PM-owned track lifecycle summary."
    }
  },
  "handoff": {
    "next_buddy": "dev",
    "reason": "Why another buddy should continue.",
    "context": "What the next buddy needs to know."
  },
  "contributors": {
    "skills": ["write-prd"],
    "agents": ["pm"]
  },
  "tool_evidence": {
    "browser_cockpit_token": "broker-issued-token-for-market-artifact-runs"
  }
}
```

Rules:

- `execution_summary` is required.
- At least one durable signal must be present at runtime: `artifacts`, `state_effects`, or `handoff`.
- `state_effects.track` is PM-only through env profile capabilities.
- Non-PM buddies may use `state_effects.task` where their env profile allows `status` or `summary`.
- `tool_evidence` is only meaningful when the runtime broker issued it; active docs must not tell users to hand-write token strings.
- Runtime receipt IDs and paths are not authored inside the result payload.

## File Map

Verify only:

- `scripts/turn_runtime.py`
- `tests/test_turn_runtime.py`
- `docs/spec/2026-05-07-switch-command-residue-cleanup-development-plan.md`
- `docs/spec/2026-05-07-switch-command-residue-cleanup-test-plan.md`

Modify schema and schema tests:

- `framework/schemas/pm/pm-result.json`
- `framework/schemas/market/market-result.json`
- `framework/schemas/design/design-result.json`
- `framework/schemas/dev/dev-result.json`
- `framework/schemas/test/test-result.json`
- `tests/test_output_schema_boundaries.py`

Modify active contracts:

- `framework/contracts/pm.md`
- `framework/contracts/market.md`
- `framework/contracts/design.md`
- `framework/contracts/dev.md`
- `framework/contracts/test.md`

Modify active skill docs and templates:

- `buddyswitch/skills/pm/write-prd/SKILL.md`
- `buddyswitch/skills/pm/write-prd/assets/prd-template.md`
- `buddyswitch/skills/pm/track-manager/SKILL.md`
- `buddyswitch/skills/pm/track-manager/assets/track-operation-template.md`
- `buddyswitch/skills/market/research-scan/SKILL.md`
- `buddyswitch/skills/market/research-scan/assets/research-report-template.md`
- `buddyswitch/skills/market/pmf-recon/SKILL.md`
- `buddyswitch/skills/market/pmf-recon/assets/evidence-log-template.md`
- `buddyswitch/skills/market/pmf-recon/assets/pmf-report-template.md`
- `buddyswitch/skills/market/customer-discovery/SKILL.md`
- `buddyswitch/skills/market/customer-discovery/assets/interview-brief-template.md`
- `buddyswitch/skills/market/positioning-copy/SKILL.md`
- `buddyswitch/skills/market/positioning-copy/assets/positioning-brief-template.md`
- `buddyswitch/skills/market/channel-discovery/SKILL.md`
- `buddyswitch/skills/market/channel-discovery/assets/channel-plan-template.md`
- `buddyswitch/skills/market/launch-prep/SKILL.md`
- `buddyswitch/skills/market/launch-prep/assets/launch-prep-template.md`
- `buddyswitch/skills/design/shape-prototype/SKILL.md`
- `buddyswitch/skills/design/shape-prototype/assets/design-handoff-template.md`
- `buddyswitch/skills/dev/implement-task/SKILL.md`
- `buddyswitch/skills/dev/implement-task/assets/implementation-report-template.md`
- `buddyswitch/skills/dev/skill-creator-importer/SKILL.md`
- `buddyswitch/skills/dev/skill-creator-importer/assets/skill-import-report-template.md`
- `buddyswitch/skills/test/smoke-test/SKILL.md`
- `buddyswitch/skills/test/smoke-test/assets/test-report-template.md`

Modify store flattening files:

- `scripts/env_store.py`
- `scripts/runtime_store/__init__.py`
- `scripts/runtime_store/projections.py`
- Delete: `scripts/runtime_store/repositories.py`
- `tests/test_env_store_v2.py`
- `framework/docs/interface-spec.md`

Modify small wording and guardrails:

- `framework/docs/browser-cockpit.md`
- `scripts/env_manifest.py`
- `tests/test_repo_consistency.py`

Do not modify in this task:

- `docs/memo/**`
- archived `docs/spec/2026-05-05-*` plans
- manual debug APIs: `scripts/env_tracks.py`, `scripts/env_artifacts.py`, `scripts/env_tasks.py`
- launcher retired public command behavior

## Implementation Tasks

### Task 1: Add Active Residue Guardrails

**Files:**

- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add an active authoring surface residue test**

Add a test that scans only active authoring surfaces and avoids archived specs/memos:

```python
    def test_active_authoring_surfaces_use_buddy_run_commit_shape(self) -> None:
        tracked = self._git_ls_files(
            "framework/contracts",
            "framework/schemas",
            "buddyswitch/skills",
        )
        forbidden_tokens = (
            "deliverables_or_changed" + "_files",
            "artifact" + "_content",
            "specialized" + "_sections",
            "track" + "_operation",
        )
        for rel_path in tracked:
            path = ROOT / rel_path
            if not path.exists() or path.suffix not in {".md", ".json"}:
                continue
            text = path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                with self.subTest(path=rel_path, token=token):
                    self.assertNotIn(token, text)
```

- [ ] **Step 2: Add a store legacy-name guardrail**

Add a test that targets the active store implementation, not unrelated launcher migration tests:

```python
    def test_active_store_has_no_legacy_named_repository_layer(self) -> None:
        active_paths = (
            ROOT / "scripts" / "env_store.py",
            ROOT / "scripts" / "runtime_store" / "__init__.py",
            ROOT / "scripts" / "runtime_store" / "projections.py",
            ROOT / "tests" / "test_env_store_v2.py",
        )
        for path in active_paths:
            with self.subTest(path=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("_legacy_", text)
        self.assertFalse((ROOT / "scripts" / "runtime_store" / "repositories.py").exists())
```

- [ ] **Step 3: Run guardrails before implementation**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_authoring_surfaces_use_buddy_run_commit_shape \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_store_has_no_legacy_named_repository_layer \
  -q
```

Expected before implementation:

```text
FAILED
```

The failures should point to active schemas, skills, templates, contracts, and store files. If the failures come from `docs/memo` or archived `docs/spec/2026-05-05-*`, fix the test scope before changing product code.

### Task 2: Convert Result Schemas To Compact Buddy-Run Commit Shape

**Files:**

- Modify: `framework/schemas/pm/pm-result.json`
- Modify: `framework/schemas/market/market-result.json`
- Modify: `framework/schemas/design/design-result.json`
- Modify: `framework/schemas/dev/dev-result.json`
- Modify: `framework/schemas/test/test-result.json`
- Modify: `tests/test_output_schema_boundaries.py`

- [ ] **Step 1: Update schema boundary constants**

In `tests/test_output_schema_boundaries.py`, replace the old common envelope constants with:

```python
COMMON_REQUIRED_COMMIT_KEYS = {
    "execution_summary",
}

COMMON_OPTIONAL_COMMIT_KEYS = {
    "working_notes",
    "artifacts",
    "state_effects",
    "handoff",
    "contributors",
    "tool_evidence",
}

RETIRED_AUTHORING_KEYS = {
    "deliverables_or_changed_files",
    "artifact_content",
    "specialized_sections",
    "track_operation",
}
```

- [ ] **Step 2: Replace sample payloads with compact commit payloads**

Change `_sample_payload_for_buddy` so every buddy sample uses `artifacts[]` instead of `artifact_content`:

```python
        content_by_buddy: dict[str, dict[str, object]] = {
            "pm": {
                "summary": "PRD summary",
                "decisions": ["Ship guided flow first."],
                "risks": ["Copy may still be unclear."],
                "open_questions": ["Need localization in v1?"],
                "suggested_next_step": "Hand off to design for flow draft.",
                "prd": {
                    "problem": "Users cannot complete onboarding quickly.",
                    "user_value": "Faster onboarding completion.",
                    "requirements": ["Define scope", "Capture acceptance criteria"],
                    "scope": {"in_scope": ["Onboarding copy"], "out_of_scope": ["Billing refactor"]},
                },
            },
            "dev": {
                "task_summary": "Implemented onboarding banner behavior.",
                "changed_files": ["projects/app/main.js"],
                "implementation_notes": ["Kept state mutation local."],
                "verification": {
                    "checks_run": ["python3 -m pytest tests/test_turn_runtime.py -q"],
                    "passed": ["Runtime tests passed"],
                    "failed": [],
                    "blocked": [],
                },
                "risks": ["Browser smoke not executed."],
                "follow_ups": ["Run manual browser check."],
            },
            "test": {
                "test_scope": "Smoke validation for onboarding path.",
                "checks_run": ["npm test -- smoke"],
                "passed_items": ["Core route loads"],
                "failed_items": [],
                "blocked_items": [],
                "reproduction_notes": [],
                "readiness": "ready",
            },
            "market": {
                "research_question": "Do founders need faster validation loops?",
                "evidence": ["Interview themes from founder calls."],
                "insights": ["Speed and confidence are both required."],
                "assumptions": ["SMB focus remains stable."],
                "risks": ["Sample size still small."],
                "conclusion": "Demand appears real but incomplete.",
                "recommended_next_step": "Run 5 targeted interviews.",
                "source_traceability": [{"source_id": "src-1"}],
            },
            "design": {
                "design_goal": "Clarify onboarding decisions.",
                "flow_or_screen_summary": "Single-step guidance panel in setup flow.",
                "interaction_notes": ["Primary CTA keeps user in context."],
                "assets_or_preview_refs": ["runs/raw/design-preview.png"],
                "handoff_notes": ["Include empty/loading states."],
                "open_questions": ["Need accessibility review before handoff?"],
            },
        }
        kind_by_buddy = {
            "pm": "prd",
            "dev": "implementation-report",
            "test": "smoke-test",
            "market": "market-scan",
            "design": "design-handoff",
        }
        return {
            "execution_summary": f"{buddy_id} result summary",
            "working_notes": ["Focused on buddy-run commit contract."],
            "artifacts": [
                {
                    "kind": kind_by_buddy[buddy_id],
                    "title": f"{buddy_id} artifact",
                    "summary": f"{buddy_id} artifact summary",
                    "content": content_by_buddy[buddy_id],
                }
            ],
        }
```

- [ ] **Step 3: Replace schema boundary tests**

Update tests so they prove these public contracts:

```python
    def test_buddy_result_schema_uses_compact_buddy_run_commit_boundary(self) -> None:
        expected_properties = COMMON_REQUIRED_COMMIT_KEYS | COMMON_OPTIONAL_COMMIT_KEYS
        for buddy_id in BUDDY_RESULT_SCHEMA_PATHS:
            with self.subTest(buddy=buddy_id):
                schema = self._load_buddy_schema(buddy_id)
                self.assertEqual(set(schema.get("required", [])), COMMON_REQUIRED_COMMIT_KEYS)
                self.assertFalse(schema.get("additionalProperties"))
                properties = schema.get("properties")
                self.assertIsInstance(properties, dict)
                assert isinstance(properties, dict)
                self.assertTrue(expected_properties.issubset(set(properties)))
                for retired_key in RETIRED_AUTHORING_KEYS:
                    self.assertNotIn(retired_key, properties)
```

```python
    def test_buddy_result_schema_accepts_compact_artifact_commit_examples(self) -> None:
        for buddy_id in BUDDY_RESULT_SCHEMA_PATHS:
            with self.subTest(buddy=buddy_id):
                schema = self._load_buddy_schema(buddy_id)
                payload = self._sample_payload_for_buddy(buddy_id)
                self.assertEqual(output_schema.validate_output_payload(payload, schema), [])
```

```python
    def test_pm_schema_accepts_track_state_effect_and_rejects_track_operation(self) -> None:
        schema = self._load_buddy_schema("pm")
        payload = self._sample_payload_for_buddy("pm")
        payload["state_effects"] = {
            "track": {
                "action": "advance",
                "track_id": "track-onboarding",
                "next_buddy": "dev",
            }
        }
        self.assertEqual(output_schema.validate_output_payload(payload, schema), [])

        retired_payload = self._sample_payload_for_buddy("pm")
        retired_payload["state_effects"] = {
            "track_operation": {
                "action": "advance",
                "track_id": "track-onboarding",
            }
        }
        errors = output_schema.validate_output_payload(retired_payload, schema)
        self.assertIn("$.state_effects: unsupported property 'track_operation'", errors)
```

```python
    def test_non_pm_schemas_reject_track_state_effects_but_allow_task_effects(self) -> None:
        for buddy_id in ("dev", "test", "market", "design"):
            with self.subTest(buddy=buddy_id):
                schema = self._load_buddy_schema(buddy_id)
                payload = self._sample_payload_for_buddy(buddy_id)
                payload["state_effects"] = {"task": {"status": "active", "summary": "Still in progress."}}
                self.assertEqual(output_schema.validate_output_payload(payload, schema), [])

                payload = self._sample_payload_for_buddy(buddy_id)
                payload["state_effects"] = {
                    "track": {
                        "action": "advance",
                        "track_id": "track-onboarding",
                    }
                }
                errors = output_schema.validate_output_payload(payload, schema)
                self.assertIn("$.state_effects: unsupported property 'track'", errors)
```

- [ ] **Step 4: Replace the five schema files**

For PM schema, allow `state_effects.track` and `state_effects.task`.

For Market, Design, Dev, and Test schemas, allow `state_effects.task` only.

All five schemas must:

- require only `execution_summary`
- allow optional `working_notes`, `artifacts`, `state_effects`, `handoff`, `contributors`, and `tool_evidence`
- define `artifacts[]` items with required `kind`, `title`, and `content`, optional `summary`, and `additionalProperties: false`
- forbid old top-level runtime receipt metadata fields by keeping `additionalProperties: false`
- not contain `deliverables_or_changed_files`, `artifact_content`, `specialized_sections`, or `track_operation`

- [ ] **Step 5: Run schema boundary tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_output_schema_boundaries.py \
  -q
```

Expected after implementation:

```text
... passed
```

### Task 3: Rewrite Active Contracts, Skills, And Templates

**Files:**

- Modify all files listed under "Modify active contracts" and "Modify active skill docs and templates".

- [ ] **Step 1: Update all five buddy contracts to name the compact commit boundary**

Each contract should say:

```markdown
## Buddy Run Commit Structure

Every run contributes to one `persist-buddy-run` commit.

Required:
- `execution_summary`

Optional:
- `working_notes`
- `artifacts`
- `state_effects`
- `handoff`
- `contributors`
- `tool_evidence`

Artifact-producing runs write artifact content under `artifacts[].content`.
Runtime receipt IDs, object paths, run IDs, and task IDs are generated by persist and must not be authored in the result payload.
```

Remove `deliverables or changed files` from chat return blocks. If the contract needs a human final-response section, call it `summary`, `verification`, or `handoff note`, not an output-payload key.

- [ ] **Step 2: Update PM-specific contract language**

In `framework/contracts/pm.md`, replace PRD and track wording with:

```markdown
- Put PRD-specific detail in `artifacts[].content.prd` for `kind="prd"` commits.
- PM track lifecycle changes use `state_effects.track` with action `create|update|advance|archive`.
- Do not emit `track_operation` in any location.
```

- [ ] **Step 3: Update Market-specific contract language**

In `framework/contracts/market.md`, replace specialized-section wording with:

```markdown
Market artifact detail belongs in `artifacts[].content`.

Typical content keys:
- `research_scan`: `research_strategy`, `channel_plan`, `iteration_log`, `source_traceability`
- `pmf_recon`: `candidate_icps`, `pmf_confidence`, `suggested_interview_angles`
- `customer_discovery`: `interview_guide`, `hypotheses_to_test`
- `positioning_copy`: `message_house`, `homepage_angles`
- `channel_discovery`: `channel_scores`, `experiment_plan`
- `launch_prep`: `launch_assets`, `instrumentation_plan`, `feedback_collection_plan`

Market artifact-producing persists require broker-issued `tool_evidence`. Do not hand-write or fake evidence tokens.
```

- [ ] **Step 4: Update every active `SKILL.md` closing/output section**

Use this pattern, customized only for buddy, skill id, artifact kind, and content keys:

```markdown
## BuddySwitch Commit Output

Contribute to one buddy-run commit. Do not call persist from inside the skill.

Required top-level field:
- `execution_summary`

Use `artifacts` when this skill produces a durable artifact:
- `kind`: `<manifest-artifact-kind>`
- `title`: concise artifact title
- `summary`: short downstream selection summary
- `content`: skill-specific structured content

Use optional `working_notes` for concise reasoning or verification notes.
Use optional `state_effects.task` only for the current prepared task.
Use optional `handoff` when another manifest buddy should continue.
```

PM `track-manager` should be state-effect first and should include:

```markdown
Use `state_effects.track`, not an artifact-only placeholder, when the requested outcome is a track lifecycle change.
```

Market skills should include:

```markdown
Market artifact commits require broker-issued `tool_evidence` from the browser evidence gate. Do not invent token strings.
```

- [ ] **Step 5: Update every active template asset to compact JSON examples**

Replace old template examples with concrete compact commits. Example for `buddyswitch/skills/pm/write-prd/assets/prd-template.md`:

```json
{
  "execution_summary": "PRD summary for the requested product outcome.",
  "working_notes": [
    "Key assumption, evidence note, or scope decision."
  ],
  "artifacts": [
    {
      "kind": "prd",
      "title": "PRD: Requested Outcome",
      "summary": "Selection-ready PRD summary for downstream design/dev/test.",
      "content": {
        "prd": {
          "problem": "",
          "user_value": "",
          "requirements": [],
          "acceptance_criteria": [],
          "scope": {
            "in_scope": [],
            "out_of_scope": []
          }
        },
        "decisions": [],
        "risks": [],
        "open_questions": [],
        "suggested_next_step": ""
      }
    }
  ]
}
```

Example for `buddyswitch/skills/pm/track-manager/assets/track-operation-template.md`:

```json
{
  "execution_summary": "Updated the active delivery track.",
  "working_notes": [
    "Track mutation is PM-owned and uses state_effects.track."
  ],
  "state_effects": {
    "track": {
      "action": "advance",
      "track_id": "track-example",
      "next_buddy": "dev",
      "summary": "Why the track should move to Dev."
    }
  },
  "handoff": {
    "next_buddy": "dev",
    "reason": "Implementation should continue from the approved product scope.",
    "context": "Include the relevant artifact or task context here."
  }
}
```

Example for any Market artifact template:

```json
{
  "execution_summary": "Market evidence summary for the requested research question.",
  "working_notes": [
    "Browser evidence was captured through the instance cockpit."
  ],
  "artifacts": [
    {
      "kind": "market-scan",
      "title": "Market Scan: Requested Question",
      "summary": "Selection-ready market scan summary for PM/design.",
      "content": {
        "research_question": "",
        "evidence": [],
        "insights": [],
        "assumptions": [],
        "risks": [],
        "conclusion": "",
        "recommended_next_step": "",
        "source_traceability": []
      }
    }
  ],
  "tool_evidence": {
    "browser_cockpit_token": "<broker-issued-token-from-current-run>"
  }
}
```

For non-market templates, omit `tool_evidence` unless the runtime broker produced a real token for that run.

- [ ] **Step 6: Run active authoring guardrail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_authoring_surfaces_use_buddy_run_commit_shape \
  -q
```

Expected after implementation:

```text
. passed
```

### Task 4: Preserve Runtime Persist Behavior After Authoring Cleanup

**Files:**

- Modify only if tests reveal a real mismatch: `scripts/turn_runtime.py`
- Prefer no runtime code change in this task.

- [ ] **Step 1: Run focused buddy-run persist tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py \
  tests/test_parallel_contracts.py \
  tests/test_market_browser_evidence.py \
  -q
```

Expected:

```text
... passed
```

- [ ] **Step 2: If a test fails because docs/schemas changed, do not weaken runtime validation**

Fix the changed schema/test/doc instead of relaxing:

- `execution_summary` non-empty requirement
- allowed artifact kinds from manifest
- duplicate artifact kind rejection
- PM-only track lifecycle effects
- handoff target validation
- market broker-issued evidence token requirement
- no durable signal rejection

- [ ] **Step 3: Re-run the same focused tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py \
  tests/test_parallel_contracts.py \
  tests/test_market_browser_evidence.py \
  -q
```

Expected:

```text
... passed
```

### Task 5: Flatten Store Implementation And Remove `_legacy_*`

**Files:**

- Modify: `scripts/env_store.py`
- Modify: `scripts/runtime_store/__init__.py`
- Modify: `scripts/runtime_store/projections.py`
- Delete: `scripts/runtime_store/repositories.py`
- Modify: `tests/test_env_store_v2.py`
- Modify: `framework/docs/interface-spec.md`

- [ ] **Step 1: Remove repository delegation tests that assert legacy wiring**

Delete these tests from `tests/test_env_store_v2.py`:

- `RuntimeStoreFacadeTests::test_runtime_store_package_exports_repository_entrypoints`
- `RuntimeStoreFacadeTests::test_runtime_store_list_tracks_entrypoint_delegates_to_legacy_store`
- `RuntimeStoreFacadeTests::test_runtime_store_create_task_entrypoint_delegates_to_legacy_store`
- `RuntimeStoreFacadeTests::test_runtime_store_save_run_content_entrypoint_delegates_to_legacy_store`
- `ResolveTimeTaskMaterializationTests::test_runtime_store_list_tracks_facade_delegates`
- `ResolveTimeTaskMaterializationTests::test_runtime_store_create_task_facade_delegates`
- `ResolveTimeTaskMaterializationTests::test_runtime_store_save_run_content_facade_delegates`

These tests assert the residue and should not be preserved.

- [ ] **Step 2: Rename current store implementations in `env_store.py`**

Rename each current implementation by removing `_legacy_`:

```text
_legacy_list_tracks -> list_tracks
_legacy_list_tasks -> list_tasks
_legacy_list_artifacts -> list_artifacts
_legacy_list_task_artifacts -> list_task_artifacts
_legacy_build_track_artifact_index -> build_track_artifact_index
_legacy_get_track -> get_track
_legacy_get_task -> get_task
_legacy_get_artifact -> get_artifact
_legacy_save_track -> save_track
_legacy_save_task -> save_task
_legacy_save_artifact -> save_artifact
_legacy_create_track -> create_track
_legacy_update_track -> update_track
_legacy_advance_track -> advance_track
_legacy_create_task -> create_task
_legacy_update_task -> update_task
_legacy_register_task_to_track -> register_task_to_track
_legacy_add_run_to_task -> add_run_to_task
_legacy_add_artifact_to_task -> add_artifact_to_task
_legacy_remove_artifact_from_task -> remove_artifact_from_task
_legacy_create_artifact -> create_artifact
_legacy_update_artifact -> update_artifact
_legacy_delete_artifact -> delete_artifact
_legacy_delete_artifacts_by_buddy -> delete_artifacts_by_buddy
_legacy_delete_all_artifacts -> delete_all_artifacts
_legacy_save_run_content -> save_run_content
```

Then delete `_runtime_repositories()` and the bottom public wrapper definitions that only delegate into `runtime_store`.

- [ ] **Step 3: Delete `scripts/runtime_store/repositories.py`**

Remove the file. The canonical object store implementation is now `env_store.py`; `runtime_store` remains the read-only projection package.

- [ ] **Step 4: Update `runtime_store/__init__.py`**

Replace repository exports with a minimal package marker:

```python
#!/usr/bin/env python3
"""Runtime store projection package."""
```

- [ ] **Step 5: Update `runtime_store/projections.py` imports**

Remove:

```python
from .repositories import list_artifacts, list_tasks, list_tracks
```

Use `env_store.list_artifacts()`, `env_store.list_tasks()`, and `env_store.list_tracks()` at call sites.

- [ ] **Step 6: Update interface docs**

In `framework/docs/interface-spec.md`, remove `runtime_store.repositories` from the list of runtime internals. Keep `runtime_store.projections` because browser UI must still not import it directly.

- [ ] **Step 7: Run store and projection tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_store_v2.py \
  tests/test_debug_apis.py \
  tests/test_console_app_contract.py \
  -q
```

Expected:

```text
... passed
```

- [ ] **Step 8: Run store legacy guardrail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_store_has_no_legacy_named_repository_layer \
  -q
```

Expected:

```text
. passed
```

### Task 6: Clean Smaller Active Wording And Compatibility Residue

**Files:**

- Modify: `framework/docs/browser-cockpit.md`
- Modify: `scripts/env_manifest.py`

- [ ] **Step 1: Replace selected-skill wording in browser cockpit docs**

Change this line:

```markdown
- The host executes selected skill work locally while treating the browser contract in this doc as binding runtime constraints.
```

To:

```markdown
- Codex executes active native skill package work inside the locked buddy run while this browser contract remains the binding runtime constraint.
```

- [ ] **Step 2: Remove compatibility-era comment in `env_manifest.py`**

Delete:

```python
# Retained for compatibility with older turn-runtime imports.
```

Keep `BROWSER_COCKPIT_HOST_EXECUTION` if current manifest/profile tests still use it.

- [ ] **Step 3: Run wording guardrail scan**

Run:

```bash
rg -n "selected skill work locally|older turn-runtime imports" \
  framework/docs/browser-cockpit.md scripts/env_manifest.py
```

Expected:

```text
no matches
```

### Task 7: Final Active-Surface Verification

**Files:**

- No source changes unless a verification command exposes residue in active surfaces.

- [ ] **Step 1: Run switch-command cleanup verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py::TurnRuntimeBuddyRunTests::test_prepare_accepts_switch_prefixed_text_as_ordinary_request \
  tests/test_turn_runtime.py::TurnRuntimeBuddyRunTests::test_prepare_uses_locked_buddy_for_switch_prefixed_text \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_legacy_public_commands_fail_closed_with_hints \
  -q
```

Expected:

```text
... passed
```

- [ ] **Step 2: Run active residue scans**

Run:

```bash
rg -n "deliverables_or_changed_files|artifact_content|specialized_sections|track_operation" \
  framework/contracts framework/schemas buddyswitch/skills
```

Expected:

```text
no matches
```

Run:

```bash
rg -n "_legacy_" \
  scripts/env_store.py scripts/runtime_store tests/test_env_store_v2.py
```

Expected:

```text
no matches
```

Run:

```bash
rg -n "selected skill work locally|older turn-runtime imports" \
  framework/docs/browser-cockpit.md scripts/env_manifest.py
```

Expected:

```text
no matches
```

- [ ] **Step 3: Run final focused suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_output_schema_boundaries.py \
  tests/test_turn_runtime.py \
  tests/test_parallel_contracts.py \
  tests/test_market_browser_evidence.py \
  tests/test_env_store_v2.py \
  tests/test_debug_apis.py \
  tests/test_console_app_contract.py \
  tests/test_repo_consistency.py \
  -q
```

Expected:

```text
... passed
```

## Self-Review Checklist

Before declaring implementation complete:

- The change fixes active runtime/documentation model conflict, not archived memo wording.
- The compact buddy-run payload is the only active authoring model.
- `state_effects.track` replaces `track_operation`; there is no compatibility branch for both.
- Store cleanup removes or renames legacy labels instead of adding another wrapper layer.
- Market browser evidence gate remains intact.
- Runtime persist behavior is verified by public behavior tests, not private helper assertions.
- Active residue scans exclude historical memo/archive docs but cover active code, contracts, schemas, skills, templates, and tests.

