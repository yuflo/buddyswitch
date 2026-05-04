# Track-Manager Despecialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `track-manager` a normal PM artifact-producing skill while keeping track lifecycle mutation explicit, validated, and owned by PM.

**Architecture:** `track-manager` will use `framework/schemas/pm/pm-result.json` and the same artifact persistence path as `write-prd`. PM results may optionally declare `state_effects.track_operation`; `persist` validates the result schema, validates the state effect before writes, applies the track mutation through one PM-only state-effect helper, then persists the artifact, run audit, receipt, and track/task updates without checking `skill_id == "track-manager"`.

**Tech Stack:** Python runtime scripts, TOML manifest, JSON schemas, Markdown skill docs/templates, `unittest`/`pytest`.

---

## Working Directory

Run all implementation and verification from:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0210
```

Do not edit `/Users/chen/Dev/buddyswitch` main checkout for this task.

## Preflight Gate

Target outcome and bottleneck:

- Outcome: `track-manager` creates a PM artifact and may apply an explicit PM track state effect through the ordinary `persist` artifact path.
- Current bottleneck: runtime still treats `track-manager` as a non-artifact skill with a dedicated `_persist_track_manager` branch and a `track-manager`-only manifest exception.
- Verifiable improvement: no active runtime branch, manifest rule, schema, test, or prompt depends on non-artifact `track-manager` persistence.

Confirmed facts from current code:

- `buddyswitch/manifest.toml` marks `track-manager` as `produces_artifact = false` and points it at `framework/schemas/pm/track-manager.json`.
- `scripts/env_manifest.py` permits non-artifact persistence only for `track-manager`.
- `scripts/turn_runtime.py` has `_persist_track_manager(...)` and branches on `selected_skill_id == "track-manager"`.
- `framework/schemas/pm/pm-result.json` is currently PRD-shaped and rejects top-level `state_effects`.
- `tests/test_turn_runtime.py` and `tests/test_parallel_contracts.py` currently expect track-manager receipts with `artifact_ids = []` and no `artifact_id`.
- Task 1 has moved artifact skills to direct buddy-level JSON; there is no runtime bridge to preserve.

Design adjustments from the original memo:

- Replace "Task 1 bridge behavior" language with "direct buddy-level result emission."
- Do not keep the old top-level `track_operation` result shape.
- Do not keep `framework/schemas/pm/track-manager.json`.
- Do not fake PRD fields for track operations. Instead, make PM artifact content a general PM result surface and move PRD-specific detail under `artifact_content.specialized_sections.prd`.
- Add optional top-level `state_effects.track_operation` only to the PM schema. Non-PM schemas should reject `state_effects` through `additionalProperties: false`.

Open assumptions and invalidators:

- Assumption: it is acceptable to update the generic PM result schema from PRD-only to PM-buddy-level output because `track-manager` must not produce fake PRD content.
- Assumption: old persisted run objects with `track_action` can remain readable through existing projection fallback behavior, but new persist requests do not need backward-compatible input support.
- Invalidator: if any external contract requires accepting old `track_operation` payloads after this task, stop and ask because that conflicts with the forward-only requirement.
- Invalidator: if non-PM buddies must mutate track lifecycle in this task, stop and split that into a separate product decision.

Permissions and boundaries:

- Use normal workspace writes inside `.worktrees/dev0210`.
- Do not run destructive git commands.
- Do not add a compatibility adapter, fallback converter, dual persist path, or old-payload shim.
- Do not infer track mutations from vague request text; only apply a validated `state_effects.track_operation`.
- Do not broaden state effects into a generic workflow engine. Implement only the PM track operation effect needed now.

Verification plan and stop condition:

- Stop when focused tests prove PM schema shape, manifest mapping, direct `track-manager` artifact persistence, create/update/advance/archive track effects, non-PM rejection before writes, no old non-artifact path, docs/templates consistency, and launcher/runtime materialization.
- Completion requires fresh output from the final verification commands in Task 8.

## Target Runtime Flow

```text
prepare-turn-context
-> Codex CLI discovers .agents/skills/track-manager
-> native track-manager emits PM buddy-level result JSON directly
-> result includes artifact_content and optional state_effects.track_operation
-> persist --skill-id track-manager validates pm-result.json
-> persist validates and applies PM state effects without checking skill_id
-> persist writes artifact, task, track, run audit, and receipt
```

No step accepts old top-level `track_operation` payloads.

## Target Result Shape

`track-manager` should emit this shape for create:

```json
{
  "execution_summary": "Created onboarding delivery track.",
  "working_notes": ["Track lifecycle request was explicit."],
  "deliverables_or_changed_files": [],
  "artifact_content": {
    "summary": "Created onboarding delivery track.",
    "decisions": ["Created a PM-owned delivery track for onboarding."],
    "risks": [],
    "open_questions": [],
    "suggested_next_step": "Hand off to design after PM scope is ready.",
    "specialized_sections": {
      "track_operation": {
        "action": "create",
        "track_id": "track-onboarding-delivery",
        "title": "Onboarding Delivery",
        "status": "active",
        "current_buddy": "pm",
        "next_buddy": "design",
        "summary": "Cross-functional onboarding delivery flow."
      }
    }
  },
  "state_effects": {
    "track_operation": {
      "action": "create",
      "track_id": "track-onboarding-delivery",
      "title": "Onboarding Delivery",
      "status": "active",
      "current_buddy": "pm",
      "next_buddy": "design",
      "summary": "Cross-functional onboarding delivery flow."
    }
  }
}
```

For `write-prd`, PRD-specific fields move under `artifact_content.specialized_sections.prd`:

```json
{
  "execution_summary": "Captured onboarding PRD updates.",
  "working_notes": ["Focused on P0 scope and acceptance criteria."],
  "deliverables_or_changed_files": ["runs/raw/prd-notes.md"],
  "artifact_content": {
    "summary": "Captured onboarding PRD updates.",
    "decisions": ["Ship guided onboarding flow before broader redesign."],
    "risks": ["Unknown migration edge cases."],
    "open_questions": ["Need follow-up QA pass?"],
    "suggested_next_step": "Hand off to design for a flow draft.",
    "specialized_sections": {
      "prd": {
        "problem": "Users need clearer onboarding scope.",
        "user_value": "Faster onboarding completion with clearer guidance.",
        "requirements": ["Define launch acceptance criteria", "Capture follow-up questions"],
        "scope": {
          "in_scope": ["Onboarding flow scope and acceptance criteria"],
          "out_of_scope": ["Implementation delivery code"]
        }
      }
    }
  }
}
```

## File Map

Delete:

- `framework/schemas/pm/track-manager.json`

Modify:

- `buddyswitch/manifest.toml`
- `buddyswitch/skills/pm/track-manager/SKILL.md`
- `buddyswitch/skills/pm/write-prd/SKILL.md`
- `buddyswitch/skills/pm/write-prd/assets/prd-template.md`
- `framework/contracts/pm.md`
- `framework/contracts/persist-skill-result.json`
- `framework/docs/architecture-overview.md`
- `framework/docs/skill-runtime-shared-rules.md`
- `framework/docs/track-registry.md`
- `framework/docs/turn-runtime-spec.md`
- `framework/schemas/pm/pm-result.json`
- `scripts/env_manifest.py`
- `scripts/turn_runtime.py`
- `tests/test_env_manifest_v2.py`
- `tests/test_output_schema_boundaries.py`
- `tests/test_parallel_contracts.py`
- `tests/test_repo_consistency.py`
- `tests/test_runtime_skills.py`
- `tests/test_turn_runtime.py`

Create:

- `buddyswitch/skills/pm/track-manager/assets/track-operation-template.md`

Preserve:

- PM-only ownership of track lifecycle mutation.
- Existing track operations: `create`, `update`, `advance`, `archive`.
- Existing track/task object shapes and storage paths.
- Existing run audit field `track_action` as output metadata for current UI/projection use.

## Implementation Tasks

### Task 1: Lock PM Schema Direction With Red Tests

**Files:**

- Modify: `tests/test_output_schema_boundaries.py`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add a schema test for general PM artifact content**

In `tests/test_output_schema_boundaries.py`, replace the PM entry in `BUDDY_ARTIFACT_REQUIRED_FIELDS` with:

```python
"pm": {
    "summary",
    "decisions",
    "risks",
    "open_questions",
    "suggested_next_step",
    "specialized_sections",
},
```

Update `_sample_payload_for_buddy("pm")` so `artifact_content` is:

```python
{
    "summary": "PRD summary",
    "decisions": ["Ship guided flow first."],
    "risks": ["Copy may still be unclear."],
    "open_questions": ["Need localization in v1?"],
    "suggested_next_step": "Hand off to design for flow draft.",
    "specialized_sections": {
        "prd": {
            "problem": "Users cannot complete onboarding quickly.",
            "user_value": "Faster onboarding completion.",
            "requirements": ["Define scope", "Capture acceptance criteria"],
            "scope": {"in_scope": ["Onboarding copy"], "out_of_scope": ["Billing refactor"]},
        }
    },
}
```

- [ ] **Step 2: Add a PM-only state effects schema test**

Add this test to `tests/test_output_schema_boundaries.py`:

```python
def test_only_pm_schema_accepts_track_operation_state_effect(self) -> None:
    pm_schema = self._load_buddy_schema("pm")
    payload = self._sample_payload_for_buddy("pm")
    payload["state_effects"] = {
        "track_operation": {
            "action": "create",
            "track_id": "track-onboarding-delivery",
            "title": "Onboarding Delivery",
            "status": "active",
            "current_buddy": "pm",
            "next_buddy": "design",
            "summary": "Cross-functional onboarding delivery flow.",
        }
    }
    self.assertEqual(output_schema.validate_output_payload(payload, pm_schema), [])

    for buddy_id in ("dev", "test", "market", "design"):
        with self.subTest(buddy=buddy_id):
            schema = self._load_buddy_schema(buddy_id)
            invalid = self._sample_payload_for_buddy(buddy_id)
            invalid["state_effects"] = payload["state_effects"]
            errors = output_schema.validate_output_payload(invalid, schema)
            self.assertIn("$: unsupported property 'state_effects'", errors)
```

- [ ] **Step 3: Add a repo consistency test banning the old track-manager schema**

Add this test to `tests/test_repo_consistency.py`:

```python
def test_track_manager_no_longer_uses_non_artifact_schema_or_runtime_branch(self) -> None:
    manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
    skills = {skill["id"]: skill for skill in manifest.get("skills", []) if isinstance(skill, dict)}
    track_manager = skills["track-manager"]["persistence"]

    self.assertTrue(track_manager["produces_artifact"])
    self.assertEqual(track_manager["output_slot"], "track-operation")
    self.assertEqual(track_manager["output_schema"], "framework/schemas/pm/pm-result.json")
    self.assertFalse((ROOT / "framework" / "schemas" / "pm" / "track-manager.json").exists())

    runtime_text = (ROOT / "scripts" / "turn_runtime.py").read_text(encoding="utf-8")
    self.assertNotIn('selected_skill_id == "track-manager"', runtime_text)
    self.assertNotIn("def _persist_track_manager", runtime_text)
    self.assertNotIn("track_operation = dict(result.get(\"track_operation\")", runtime_text)
```

- [ ] **Step 4: Run the red tests**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_output_schema_boundaries.py::OutputSchemaBoundaryTests::test_only_pm_schema_accepts_track_operation_state_effect \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_track_manager_no_longer_uses_non_artifact_schema_or_runtime_branch \
  -q
```

Expected before implementation: fail because `pm-result.json` rejects `state_effects`, `track-manager` is still non-artifact, and runtime still has the special branch.

### Task 2: Replace PM Schema With General PM Result Plus Track Effect

**Files:**

- Modify: `framework/schemas/pm/pm-result.json`
- Delete: `framework/schemas/pm/track-manager.json`
- Modify: `tests/test_output_schema_boundaries.py`

- [ ] **Step 1: Replace `framework/schemas/pm/pm-result.json`**

Use this schema:

```json
{
  "type": "object",
  "required": [
    "execution_summary",
    "working_notes",
    "deliverables_or_changed_files",
    "artifact_content"
  ],
  "properties": {
    "execution_summary": {"type": "string"},
    "working_notes": {
      "type": "array",
      "items": {"type": "string"}
    },
    "deliverables_or_changed_files": {
      "type": "array",
      "items": {"type": "string"}
    },
    "artifact_content": {
      "type": "object",
      "required": [
        "summary",
        "decisions",
        "risks",
        "open_questions",
        "suggested_next_step",
        "specialized_sections"
      ],
      "properties": {
        "summary": {"type": "string"},
        "decisions": {
          "type": "array",
          "items": {"type": "string"}
        },
        "risks": {
          "type": "array",
          "items": {"type": "string"}
        },
        "open_questions": {
          "type": "array",
          "items": {"type": "string"}
        },
        "suggested_next_step": {"type": "string"},
        "specialized_sections": {
          "type": "object"
        }
      },
      "additionalProperties": false
    },
    "state_effects": {
      "type": "object",
      "required": ["track_operation"],
      "properties": {
        "track_operation": {
          "type": "object",
          "required": ["action"],
          "additionalProperties": false,
          "properties": {
            "action": {
              "type": "string",
              "enum": ["create", "update", "advance", "archive"]
            },
            "track_id": {"type": ["string", "null"]},
            "title": {"type": ["string", "null"]},
            "status": {
              "type": ["string", "null"],
              "enum": ["active", "blocked", "done", "archived", null]
            },
            "current_buddy": {"type": ["string", "null"]},
            "next_buddy": {"type": ["string", "null"]},
            "summary": {"type": ["string", "null"]}
          }
        }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}
```

- [ ] **Step 2: Delete `framework/schemas/pm/track-manager.json`**

Remove the file completely. Do not leave a replacement schema, symlink, alias, or redirect.

- [ ] **Step 3: Run schema tests**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_output_schema_boundaries.py -q
```

Expected after implementation: output schema boundary tests pass.

### Task 3: Make `track-manager` Artifact-Producing in Manifest and Skills

**Files:**

- Modify: `buddyswitch/manifest.toml`
- Modify: `buddyswitch/skills/pm/track-manager/SKILL.md`
- Create: `buddyswitch/skills/pm/track-manager/assets/track-operation-template.md`
- Modify: `buddyswitch/skills/pm/write-prd/SKILL.md`
- Modify: `buddyswitch/skills/pm/write-prd/assets/prd-template.md`
- Modify: `tests/test_env_manifest_v2.py`
- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Update `buddyswitch/manifest.toml`**

Change the `track-manager` entry to:

```toml
[[skills]]
id = "track-manager"
path = "buddyswitch/skills/pm/track-manager"
produces_artifact = true
output_slot = "track-operation"
output_schema = "framework/schemas/pm/pm-result.json"
```

- [ ] **Step 2: Update `track-manager` skill docs**

In `buddyswitch/skills/pm/track-manager/SKILL.md`, update `## Outputs` to say:

```markdown
## Outputs
- A PM artifact object in `buddyswitch/objects/artifacts/` with `slot = "track-operation"`.
- Optional explicit `state_effects.track_operation` in the PM result JSON when a track lifecycle mutation is requested.
- Updated track objects in `buddyswitch/objects/tracks/` only after `persist` validates and applies the declared state effect.
- A run audit under `buddyswitch/content/runs/`.
```

Add this under `## Core Rules`:

```markdown
- Emit full PM buddy-level result JSON directly.
- Put human-readable track operation detail under `artifact_content.specialized_sections.track_operation`.
- Put the executable track mutation under `state_effects.track_operation`.
- Do not emit the retired top-level `track_operation` payload.
```

- [ ] **Step 3: Create `track-operation-template.md`**

Create `buddyswitch/skills/pm/track-manager/assets/track-operation-template.md` with:

```json
{
  "execution_summary": "Created onboarding delivery track.",
  "working_notes": [
    "The request explicitly asked for track lifecycle mutation."
  ],
  "deliverables_or_changed_files": [],
  "artifact_content": {
    "summary": "Created onboarding delivery track.",
    "decisions": [
      "Created a PM-owned delivery track for onboarding."
    ],
    "risks": [],
    "open_questions": [],
    "suggested_next_step": "Hand off to design after PM scope is ready.",
    "specialized_sections": {
      "track_operation": {
        "action": "create",
        "track_id": "track-onboarding-delivery",
        "title": "Onboarding Delivery",
        "status": "active",
        "current_buddy": "pm",
        "next_buddy": "design",
        "summary": "Cross-functional onboarding delivery flow."
      }
    }
  },
  "state_effects": {
    "track_operation": {
      "action": "create",
      "track_id": "track-onboarding-delivery",
      "title": "Onboarding Delivery",
      "status": "active",
      "current_buddy": "pm",
      "next_buddy": "design",
      "summary": "Cross-functional onboarding delivery flow."
    }
  }
}
```

- [ ] **Step 4: Update `write-prd` docs and template for general PM schema**

Replace the `artifact_content` in `buddyswitch/skills/pm/write-prd/assets/prd-template.md` with the target PRD shape from this plan's "Target Result Shape" section.

In `buddyswitch/skills/pm/write-prd/SKILL.md`, replace buddy-specific output fields with:

```markdown
Buddy-specific fields inside `artifact_content`:

- `summary`
- `decisions`
- `risks`
- `open_questions`
- `suggested_next_step`
- `specialized_sections`

PRD-specific fields belong under `artifact_content.specialized_sections.prd`.
```

- [ ] **Step 5: Update manifest tests**

In `tests/test_env_manifest_v2.py`:

- Replace `test_load_manifest_rejects_non_track_manager_non_artifact_persistence` with a test that rejects every `produces_artifact=false` skill.
- Replace `test_load_manifest_allows_track_manager_non_artifact_without_output_slot` with a test that proves `track-manager` loads as an artifact skill with `output_slot == "track-operation"` and `output_schema == "framework/schemas/pm/pm-result.json"`.
- Update live manifest assertions so `track-manager` is included in the PM artifact mapping.

The live mapping should include:

```python
"track-manager": "framework/schemas/pm/pm-result.json",
```

- [ ] **Step 6: Update runtime skill materialization tests**

In `tests/test_runtime_skills.py`, change fixture manifests that currently define `track-manager` with:

```python
"produces_artifact": "false",
"output_slot": "",
"output_schema": "framework/schemas/pm/track-manager.json",
```

to:

```python
"produces_artifact": "true",
"output_slot": "track-operation",
"output_schema": "framework/schemas/pm/pm-result.json",
```

- [ ] **Step 7: Run manifest/materialization tests**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_manifest_v2.py tests/test_runtime_skills.py tests/test_repo_consistency.py \
  -q
```

Expected after implementation: tests pass without `track-manager` non-artifact exceptions.

### Task 4: Replace Runtime Skill Branch With PM State Effect Application

**Files:**

- Modify: `scripts/turn_runtime.py`
- Modify: `tests/test_turn_runtime.py`
- Modify: `tests/test_parallel_contracts.py`

- [ ] **Step 1: Update test payload helpers**

In `tests/test_turn_runtime.py`, add:

```python
@staticmethod
def _pm_track_operation_result_payload(
    *,
    action: str = "create",
    track_id: str = "track-onboarding-delivery",
    title: str = "Onboarding Delivery",
    status: str = "active",
    current_buddy: str = "pm",
    next_buddy: str | None = "design",
    summary: str = "Cross-functional onboarding delivery flow.",
) -> dict[str, object]:
    operation = {
        "action": action,
        "track_id": track_id,
        "title": title,
        "status": status,
        "current_buddy": current_buddy,
        "next_buddy": next_buddy,
        "summary": summary,
    }
    return {
        "execution_summary": f"{action.title()} onboarding track.",
        "working_notes": ["Track lifecycle mutation was explicit."],
        "deliverables_or_changed_files": [],
        "artifact_content": {
            "summary": f"{action.title()} onboarding track.",
            "decisions": [f"Requested track action: {action}."],
            "risks": [],
            "open_questions": [],
            "suggested_next_step": "Continue from receipt.next_state.",
            "specialized_sections": {"track_operation": operation},
        },
        "state_effects": {"track_operation": operation},
    }
```

Update `_pm_result_payload()` to use the general PM artifact content shape with `specialized_sections.prd`.

- [ ] **Step 2: Replace old track-manager receipt tests**

Replace `test_track_manager_persist_receipt_uses_empty_artifact_ids` with:

```python
def test_track_manager_persists_artifact_and_applies_create_track_effect(self) -> None:
    instance_json = self._write_instance_json(instance_id="inst-ut-track-create-effect", buddy="pm")
    env = self._product_env(
        instance_json,
        buddy="pm",
        instance_id="inst-ut-track-create-effect",
        shared_root=self.runtime_root,
    )
    context = self._prepare("Create onboarding delivery track", env=env)
    self.assertTrue(context["ok"])

    payload = self._persist(
        context,
        skill_id="track-manager",
        result=self._pm_track_operation_result_payload(track_id="track-onboarding-delivery"),
        env=env,
    )

    self.assertTrue(payload["ok"])
    receipt = payload["receipt"]
    self.assertIsInstance(receipt, dict)
    assert isinstance(receipt, dict)
    self.assertEqual(receipt["skill_id"], "track-manager")
    self.assertEqual(receipt["track_action"], "create")
    self.assertIsInstance(receipt["artifact_id"], str)
    self.assertIn(receipt["artifact_id"], receipt["artifact_ids"])
    self.assertEqual(receipt["track_id"], "track-onboarding-delivery")

    artifact_object = self._load_runtime_json(receipt["receipt_paths"]["artifacts"][0])
    self.assertEqual(artifact_object["skill_id"], "track-manager")
    self.assertEqual(artifact_object["slot"], "track-operation")
    self.assertEqual(artifact_object["content"]["specialized_sections"]["track_operation"]["action"], "create")

    track_object = self._load_runtime_json(receipt["receipt_paths"]["track"])
    self.assertEqual(track_object["id"], "track-onboarding-delivery")
    self.assertIn(receipt["task_id"], track_object["task_ids"])
```

- [ ] **Step 3: Add a negative test for old top-level payload rejection**

Add:

```python
def test_track_manager_rejects_retired_top_level_track_operation_without_writes(self) -> None:
    instance_json = self._write_instance_json(instance_id="inst-ut-track-old-payload", buddy="pm")
    env = self._product_env(
        instance_json,
        buddy="pm",
        instance_id="inst-ut-track-old-payload",
        shared_root=self.runtime_root,
    )
    context = self._prepare("Create onboarding delivery track", env=env)
    self.assertTrue(context["ok"])
    snapshot_before = self._runtime_state_snapshot()
    instance_before = instance_json.read_text(encoding="utf-8")

    with self.assertRaises(ValueError):
        self._persist(
            context,
            skill_id="track-manager",
            result={
                "execution_summary": "Created onboarding track.",
                "working_notes": ["Old payload shape."],
                "deliverables_or_changed_files": [],
                "track_operation": {
                    "action": "create",
                    "track_id": "track-legacy-top-level",
                },
            },
            env=env,
        )

    self.assertEqual(self._runtime_state_snapshot(), snapshot_before)
    self.assertEqual(instance_json.read_text(encoding="utf-8"), instance_before)
```

- [ ] **Step 4: Add non-PM rejection before writes**

Add:

```python
def test_non_pm_state_effect_rejected_without_partial_writes(self) -> None:
    instance_json = self._write_instance_json(instance_id="inst-ut-dev-track-effect", buddy="dev")
    env = self._product_env(
        instance_json,
        buddy="dev",
        instance_id="inst-ut-dev-track-effect",
        shared_root=self.runtime_root,
    )
    context = self._prepare("Implement onboarding task", env=env)
    self.assertTrue(context["ok"])
    invalid = self._dev_result_payload()
    invalid["state_effects"] = {
        "track_operation": {
            "action": "create",
            "track_id": "track-dev-should-not-write",
        }
    }
    snapshot_before = self._runtime_state_snapshot()
    instance_before = instance_json.read_text(encoding="utf-8")

    with self.assertRaises(ValueError):
        self._persist(context, skill_id="implement-task", result=invalid, env=env)

    self.assertEqual(self._runtime_state_snapshot(), snapshot_before)
    self.assertEqual(instance_json.read_text(encoding="utf-8"), instance_before)
```

- [ ] **Step 5: Add invalid track effect rejection before writes**

Add:

```python
def test_pm_track_effect_update_requires_existing_track_without_partial_writes(self) -> None:
    instance_json = self._write_instance_json(instance_id="inst-ut-track-missing-update", buddy="pm")
    env = self._product_env(
        instance_json,
        buddy="pm",
        instance_id="inst-ut-track-missing-update",
        shared_root=self.runtime_root,
    )
    context = self._prepare("Advance missing onboarding track", env=env)
    self.assertTrue(context["ok"])
    snapshot_before = self._runtime_state_snapshot()
    instance_before = instance_json.read_text(encoding="utf-8")

    with self.assertRaises(ValueError):
        self._persist(
            context,
            skill_id="track-manager",
            result=self._pm_track_operation_result_payload(
                action="advance",
                track_id="track-does-not-exist",
                next_buddy="dev",
            ),
            env=env,
        )

    self.assertEqual(self._runtime_state_snapshot(), snapshot_before)
    self.assertEqual(instance_json.read_text(encoding="utf-8"), instance_before)
```

- [ ] **Step 6: Run red runtime tests**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py::TurnRuntimeBehaviorTests::test_track_manager_persists_artifact_and_applies_create_track_effect \
  tests/test_turn_runtime.py::TurnRuntimeBehaviorTests::test_track_manager_rejects_retired_top_level_track_operation_without_writes \
  tests/test_turn_runtime.py::TurnRuntimeBehaviorTests::test_non_pm_state_effect_rejected_without_partial_writes \
  tests/test_turn_runtime.py::TurnRuntimeBehaviorTests::test_pm_track_effect_update_requires_existing_track_without_partial_writes \
  -q
```

Expected before implementation: create test fails because `track-manager` does not produce an artifact; old-payload rejection may fail because the old schema still accepts it; non-PM rejection should fail through schema only after Task 2; missing-track effect should fail after schema/runtime wiring.

- [ ] **Step 7: Implement effect planning helpers in `scripts/turn_runtime.py`**

Add these helpers above `_persist_artifact_skill`:

```python
def _track_operation_from_result(result: dict[str, Any]) -> dict[str, Any] | None:
    effects = result.get("state_effects")
    if effects is None:
        return None
    if not isinstance(effects, dict):
        raise ValueError("state_effects must be an object")
    operation = effects.get("track_operation")
    if operation is None:
        return None
    if not isinstance(operation, dict):
        raise ValueError("state_effects.track_operation must be an object")
    return dict(operation)


def _validate_track_operation_effect(
    *,
    active_buddy: str,
    request_text: str,
    operation: dict[str, Any] | None,
    effective_track_id: str | None,
) -> dict[str, Any] | None:
    if operation is None:
        return None
    if active_buddy != "pm":
        raise ValueError("state_effects.track_operation is only allowed for active buddy 'pm'")
    action = str(operation.get("action") or "").lower()
    if action not in TRACK_ACTIONS:
        raise ValueError("state_effects.track_operation.action must be one of create/update/advance/archive")
    normalized = dict(operation)
    normalized["action"] = action
    if action == "create":
        track_id = normalized.get("track_id") or _derive_track_id(request_text)
        if get_track(track_id):
            raise ValueError(f"track already exists: {track_id}")
        normalized["track_id"] = track_id
        status = normalized.get("status") or "active"
        if status not in STATUS_VALUES:
            raise ValueError(f"state_effects.track_operation.status must be one of {', '.join(STATUS_VALUES)}")
        normalized["status"] = status
        return normalized
    target_track_id = normalized.get("track_id") or effective_track_id
    if not target_track_id:
        raise ValueError("state_effects.track_operation requires track_id for non-create actions")
    track = get_track(target_track_id)
    if track is None:
        raise ValueError(f"Track not found: {target_track_id}")
    normalized["track_id"] = target_track_id
    if action in {"update", "advance"}:
        patch = {
            key: normalized.get(key)
            for key in ("title", "status", "current_buddy", "next_buddy", "summary")
            if key in normalized and normalized.get(key) is not None
        }
        if not patch:
            raise ValueError("state_effects.track_operation for update/advance must include at least one mutable field")
        if "status" in patch and patch["status"] not in STATUS_VALUES:
            raise ValueError(f"state_effects.track_operation.status must be one of {', '.join(STATUS_VALUES)}")
    return normalized
```

- [ ] **Step 8: Implement a concrete track effect applier**

Add:

```python
def _apply_track_operation_effect(
    *,
    active_buddy: str,
    request_text: str,
    task: dict[str, Any],
    effective_track_id: str | None,
    operation: dict[str, Any] | None,
) -> tuple[dict[str, Any], str | None, str | None, str | None, str | None, list[str]]:
    planned = _validate_track_operation_effect(
        active_buddy=active_buddy,
        request_text=request_text,
        operation=operation,
        effective_track_id=effective_track_id,
    )
    if planned is None:
        track_title = None
        next_buddy = None
        if effective_track_id:
            track = get_track(effective_track_id)
            if track:
                track_title = track["title"]
                next_buddy = track.get("next_buddy")
        return task, effective_track_id, track_title, next_buddy, None, []

    action = planned["action"]
    writes: list[str] = []
    if action == "create":
        track = create_track(
            planned["track_id"],
            planned.get("title") or str(planned["track_id"]).replace("-", " ").title(),
            status=planned.get("status") or "active",
            current_buddy=planned.get("current_buddy") or active_buddy,
            next_buddy=planned.get("next_buddy"),
            summary=planned.get("summary") or "",
        )
        task = register_task_to_track(track["id"], task["id"])
        writes.extend([_track_object_path(track["id"]), _task_object_path(task["id"])])
        return task, track["id"], track["title"], track.get("next_buddy"), action, writes

    target_track_id = planned["track_id"]
    track = get_track(target_track_id)
    if track is None:
        raise ValueError(f"Track not found: {target_track_id}")
    if action in {"update", "advance"}:
        patch = {
            key: planned.get(key)
            for key in ("title", "status", "current_buddy", "next_buddy", "summary")
            if key in planned and planned.get(key) is not None
        }
        track = update_track(target_track_id, patch)
    elif action == "archive":
        track = update_track(target_track_id, {"status": "archived"})
    writes.append(_track_object_path(track["id"]))
    return task, track["id"], track["title"], track.get("next_buddy"), action, writes
```

- [ ] **Step 9: Remove `_persist_track_manager`**

Delete the entire `_persist_track_manager(...)` function from `scripts/turn_runtime.py`.

- [ ] **Step 10: Update `_persist_artifact_skill`**

Inside `_persist_artifact_skill`, before deriving the artifact id, add:

```python
track_operation = _track_operation_from_result(result)
task, effective_track_id, track_title, next_buddy, track_action, effect_writes = _apply_track_operation_effect(
    active_buddy=active_buddy,
    request_text=request_text,
    task=task,
    effective_track_id=effective_track_id,
    operation=track_operation,
)
```

Remove the old block that manually loads `track_title` and `next_buddy`.

Pass `track_action=track_action` to `_build_next_state(...)` and `_build_run_audit(...)`.

Build writes as:

```python
writes = [
    _task_object_path(task["id"]),
    _artifact_object_path(artifact["id"]),
    run_content_path_value,
    *effect_writes,
]
```

Keep `writes = list(dict.fromkeys(writes))`.

- [ ] **Step 11: Remove the skill-id branch in `_persist_skill_result`**

Replace:

```python
if selected_skill_id == "track-manager":
    receipt = _persist_track_manager(...)
else:
    receipt = _persist_artifact_skill(...)
```

with:

```python
receipt = _persist_artifact_skill(
    resolved=persist_context,
    skill=selected_skill,
    result=result,
    run_id=run_id,
    task=task,
    effective_track_id=effective_track_id,
)
```

- [ ] **Step 12: Update `tests/test_parallel_contracts.py`**

Rename `test_track_manager_persist_returns_receipt_without_artifact_id` to:

```python
def test_track_manager_persist_returns_artifact_receipt_with_track_metadata(self) -> None:
```

Update the result payload to the target track operation shape and assert:

```python
self.assertEqual(receipt.get("track_action"), "create")
self.assertIsInstance(receipt.get("artifact_id"), str)
self.assertIn(receipt["artifact_id"], receipt["artifact_ids"])
self.assertIsInstance(receipt.get("track_id"), str)
self.assertIsInstance(receipt.get("track_title"), str)
```

- [ ] **Step 13: Run runtime tests**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py tests/test_parallel_contracts.py \
  -q
```

Expected after implementation: tests pass.

### Task 5: Update Docs and Contracts to the Forward-Only Model

**Files:**

- Modify: `framework/contracts/pm.md`
- Modify: `framework/contracts/persist-skill-result.json`
- Modify: `framework/docs/architecture-overview.md`
- Modify: `framework/docs/skill-runtime-shared-rules.md`
- Modify: `framework/docs/track-registry.md`
- Modify: `framework/docs/turn-runtime-spec.md`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_parallel_contracts.py`

- [ ] **Step 1: Update PM contract wording**

In `framework/contracts/pm.md`, replace:

```markdown
- PM can write artifact objects through the resolved task and bind tasks to tracks through track-manager operations.
- Track state changes should remain explicit in demand text or track-manager output.
```

with:

```markdown
- PM can write artifact objects through the resolved task.
- PM can mutate track lifecycle state only through an explicit `state_effects.track_operation` in a validated PM result.
- Track state changes should remain explicit in demand text and result JSON; runtime must not infer them from vague task language.
```

- [ ] **Step 2: Update runtime docs**

In `framework/docs/turn-runtime-spec.md`, add to the persist section:

```markdown
PM results may include `state_effects.track_operation`.
`persist` validates the PM result schema, applies the declared track operation for active buddy `pm`, then writes the artifact and run receipt.
Non-PM result schemas do not allow `state_effects`.
The retired top-level `track_operation` payload is not accepted.
```

In `framework/docs/skill-runtime-shared-rules.md`, add:

```markdown
- Track lifecycle mutation is an explicit PM state effect: `state_effects.track_operation`.
- Artifact content describes the user-visible PM output; state effects declare runtime state writes.
- Do not emit retired top-level `track_operation`.
```

- [ ] **Step 3: Update track registry docs**

In `framework/docs/track-registry.md`, replace the track-manager permission sentence with:

```markdown
- PM controls track lifecycle operations (`create`, `update`, `advance`, `archive`) through validated `state_effects.track_operation` in PM results.
```

- [ ] **Step 4: Update contract JSON if needed**

Keep `track_action` as an optional receipt key in `framework/contracts/persist-skill-result.json`, because receipts still expose track metadata when a state effect runs. Do not add new top-level response fields.

- [ ] **Step 5: Add docs consistency assertions**

In `tests/test_repo_consistency.py`, add assertions that active docs include:

```python
"state_effects.track_operation"
"retired top-level `track_operation`"
```

and do not contain:

```python
"produces_artifact = false"
"framework/schemas/pm/track-manager.json"
"non-artifact track-manager"
```

- [ ] **Step 6: Run docs/contract tests**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py tests/test_parallel_contracts.py \
  -q
```

Expected after implementation: tests pass.

### Task 6: Remove Manifest Non-Artifact Compatibility

**Files:**

- Modify: `scripts/env_manifest.py`
- Modify: `tests/test_env_manifest_v2.py`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Simplify non-artifact persistence handling**

In `scripts/env_manifest.py`, replace the `else` branch in `_parse_skill_persistence(...)` with:

```python
else:
    raise ManifestError(f"{label}.produces_artifact=false is not supported")
```

This removes the `track-manager` exception and does not introduce another non-artifact contract.

- [ ] **Step 2: Update tests**

In `tests/test_env_manifest_v2.py`, assert any `produces_artifact=false` skill raises:

```python
with self.assertRaisesRegex(env_manifest.ManifestError, "produces_artifact=false is not supported"):
    env_manifest.load_manifest(manifest_path)
```

Delete tests that assert `track-manager` can be non-artifact.

- [ ] **Step 3: Add a static consistency assertion**

In `tests/test_repo_consistency.py`, add:

```python
def test_manifest_parser_has_no_track_manager_non_artifact_exception(self) -> None:
    text = (ROOT / "scripts" / "env_manifest.py").read_text(encoding="utf-8")
    self.assertNotIn("only track-manager currently supports non-artifact persistence", text)
    self.assertNotIn('skill_id != "track-manager"', text)
```

- [ ] **Step 4: Run manifest tests**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_manifest_v2.py tests/test_repo_consistency.py \
  -q
```

Expected after implementation: tests pass.

### Task 7: Runtime Skill and Launcher Regression Coverage

**Files:**

- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Update runtime skill fixture manifests**

Ensure every test manifest that includes `track-manager` declares it as:

```python
{
    "id": "track-manager",
    "path": track_manager.relative_to(ROOT).as_posix(),
    "produces_artifact": "true",
    "output_slot": "track-operation",
    "output_schema": "framework/schemas/pm/pm-result.json",
}
```

- [ ] **Step 2: Add launcher/materialization assertion for assets**

Where launcher tests assert PM runtime skills materialize, add:

```python
self.assertTrue((runtime_skills / "track-manager" / "assets" / "track-operation-template.md").exists())
```

- [ ] **Step 3: Run runtime skill and launcher tests**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_runtime_skills.py tests/test_buddyswitch_launcher.py \
  -q
```

Expected after implementation: tests pass. If launcher tests create known `projects/app/*sentinel*.txt` files, remove only those generated sentinel files after the run and verify `git status --short projects/app` is empty.

### Task 8: Full Verification

- [ ] **Step 1: Compile runtime scripts**

```bash
PYTHONPYCACHEPREFIX=/private/tmp/buddyswitch-pycache-track-manager \
PYTHONDONTWRITEBYTECODE=1 \
python3 -m py_compile scripts/turn_runtime.py scripts/env_manifest.py scripts/output_schema.py scripts/runtime_skills.py
```

- [ ] **Step 2: Run focused acceptance suite**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_output_schema_boundaries.py \
  tests/test_turn_runtime.py \
  tests/test_env_manifest_v2.py \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  tests/test_parallel_contracts.py \
  tests/test_buddyswitch_launcher.py \
  -q
```

- [ ] **Step 3: Run residue scans**

```bash
rg -n "selected_skill_id == \"track-manager\"|def _persist_track_manager|produces_artifact = false|framework/schemas/pm/track-manager.json|top-level track_operation" \
  scripts tests framework buddyswitch README.md tools
```

Expected: no active dependency matches except tests/docs that explicitly assert retired strings are absent.

```bash
rg -n "\"track_operation\"|state_effects.track_operation|track_action" \
  scripts tests framework buddyswitch README.md tools
```

Expected: `track_operation` appears only under `state_effects.track_operation`, artifact specialized sections, track effect tests, docs, and existing output metadata `track_action`.

- [ ] **Step 4: Verify generated sentinel cleanup**

```bash
git status --short projects/app
find projects/app -maxdepth 1 -name '*sentinel*.txt' -print
```

Expected: no output after cleanup.

## Completion Criteria

This task is complete only when:

- `track-manager` is `produces_artifact = true`.
- `track-manager` uses `output_slot = "track-operation"`.
- `track-manager` uses `framework/schemas/pm/pm-result.json`.
- `framework/schemas/pm/track-manager.json` is gone.
- `scripts/turn_runtime.py` has no `selected_skill_id == "track-manager"` branch and no `_persist_track_manager`.
- PM result schema accepts optional `state_effects.track_operation`.
- Non-PM schemas reject `state_effects`.
- `track-manager` create/update/advance/archive persist a PM artifact and mutate track/task state.
- Old top-level `track_operation` payloads fail before writes.
- Manifest validation no longer supports non-artifact skills.
- Docs and tests no longer describe non-artifact track-manager persistence as active behavior.
- Fresh verification commands pass.

## Stop And Confirm Cases

Stop and ask before proceeding if:

- A real published input contract requires accepting old top-level `track_operation` payloads.
- Non-PM buddies must mutate track lifecycle in this same task.
- The implementation appears to require a generic workflow engine or event bus.
- Verification shows existing tracked state files need migration for this task.
