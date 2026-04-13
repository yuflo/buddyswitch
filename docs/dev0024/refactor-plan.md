# BuddySwitch V2 Control Plane Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current latest-artifact and `SKILL.md`-frontmatter MVP flow with slot/revision artifact semantics, runtime-owned control authority, and package-based skill contracts without compatibility shims.

**Architecture:** Start at the object layer so artifact lifecycle semantics become explicit in canonical objects. Then move deterministic control behavior into runtime/workflow and finally migrate skills to package contracts that fit the new control plane instead of preserving the old one.

**Tech Stack:** Python 3.11, local JSON object store, TOML metadata, JSON schemas, `unittest`, Markdown docs

---

## File Map

- `scripts/env_store.py`
  Owns canonical `track`, `task`, `artifact`, and `run` storage plus validation and track index generation.
- `scripts/switch_runtime.py`
  Owns `resolve` and `persist`, including artifact selection input assembly and run audit writing.
- `scripts/artifact_selection.py`
  Owns deterministic artifact input selection.
- `scripts/env_manifest.py`
  Owns skill catalog parsing and runtime metadata loading.
- `scripts/workspace_data.py`
  Owns context-panel-facing projections of tracks, tasks, artifacts, and runs.
- `buddyswitch/manifest.toml`
  Owns buddy-to-skill registration and package entry paths.
- `framework/config/artifact-selection-v2.json`
  New slot-aware selector config that replaces buddy-upstream-only selection rules.
- `framework/schemas/*.json`
  Own output payload validation for each skill.
- `buddyswitch/skills/*/*/skill.toml`
  New machine-readable metadata entry for each skill package.
- `buddyswitch/skills/*/*/SKILL.md`
  Host-readable execution guidance after frontmatter removal.
- `buddyswitch/skills/*/*/assets/*.md`
  Concrete package-local templates referenced by skill guidance.
- `tests/test_env_store_v2.py`
  New focused tests for v2 task/artifact semantics.
- `tests/test_env_manifest_v2.py`
  New focused tests for package-based skill loading.
- `tests/test_artifact_selection.py`
  Slot-aware selection behavior regression coverage.
- `tests/test_switch_runtime.py`
  Resolve/persist regressions for slot/revision and track index behavior.
- `tests/test_switch_integration.py`
  End-to-end runtime contract coverage for run audits and command authority.
- `tests/test_output_schema_boundaries.py`
  Schema-boundary coverage after removing `suggested_next_switch`.
- `tests/test_repo_consistency.py`
  Package-structure and docs consistency checks.
- `framework/docs/switch-spec.md`
  Canonical runtime contract docs.
- `framework/docs/skill-architecture-best-practices.md`
  Canonical skill-architecture guidance.
- `framework/docs/interface-spec.md`
  Context panel contract that must stop speaking in `latest_artifact` terms.

### Task 1: Add V2 Artifact Slot Lifecycle To The Object Store

**Files:**
- Create: `tests/test_env_store_v2.py`
- Modify: `scripts/env_store.py`
- Test: `tests/test_env_store_v2.py`

- [ ] **Step 1: Write the failing object-model tests**

```python
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env_store import create_artifact, create_task, get_artifact, get_task  # noqa: E402


class ArtifactSlotLifecycleTests(unittest.TestCase):
    def test_create_task_initializes_artifact_slots(self) -> None:
        task = create_task(
            "task-pm-v2-slot",
            "V2 Slot Task",
            buddy="pm",
            initial_run_id="run-seed-v2-slot",
        )

        self.assertEqual(task["artifact_slots"], {})
        self.assertNotIn("latest_artifact_id", task)

    def test_create_artifact_builds_revision_chain_for_same_slot(self) -> None:
        task = create_task(
            "task-pm-v2-revision",
            "V2 Revision Task",
            buddy="pm",
            initial_run_id="run-seed-v2-revision",
        )

        first = create_artifact(
            artifact_id="art-task-pm-v2-revision-prd-r1",
            title="PRD revision 1",
            buddy="pm",
            skill_id="write-prd",
            slot="prd",
            task_id=task["id"],
            source_run_id="run-seed-v2-revision",
            summary="Initial PRD",
            content={"task_summary": "Initial PRD"},
        )
        second = create_artifact(
            artifact_id="art-task-pm-v2-revision-prd-r2",
            title="PRD revision 2",
            buddy="pm",
            skill_id="write-prd",
            slot="prd",
            task_id=task["id"],
            source_run_id="run-seed-v2-revision-2",
            summary="Revised PRD",
            content={"task_summary": "Revised PRD"},
        )

        stored_first = get_artifact(first["id"])
        stored_second = get_artifact(second["id"])
        stored_task = get_task(task["id"])

        self.assertEqual(stored_first["revision"], 1)
        self.assertFalse(stored_first["is_current"])
        self.assertEqual(stored_second["revision"], 2)
        self.assertEqual(stored_second["supersedes_artifact_id"], stored_first["id"])
        self.assertTrue(stored_second["is_current"])
        self.assertEqual(
            stored_task["artifact_slots"]["prd"]["current_artifact_id"],
            stored_second["id"],
        )
        self.assertEqual(stored_task["artifact_slots"]["prd"]["revision_count"], 2)
```

- [ ] **Step 2: Run the new tests to verify the current model fails**

Run: `python3 -m unittest tests.test_env_store_v2 -v`

Expected: FAIL with errors such as `KeyError: 'artifact_slots'`, `AssertionError` for `latest_artifact_id`, or `TypeError` because `create_artifact()` does not accept `slot`.

- [ ] **Step 3: Implement the minimal v2 task/artifact lifecycle in the store**

```python
# scripts/env_store.py

def validate_task(task: dict[str, Any]) -> dict[str, Any]:
    artifact_slots = task.get("artifact_slots")
    if not isinstance(artifact_slots, dict):
        raise ValueError("task.artifact_slots must be an object")
    normalized_slots: dict[str, dict[str, Any]] = {}
    for slot, row in artifact_slots.items():
        if not isinstance(slot, str) or not slot:
            raise ValueError("task.artifact_slots keys must be non-empty strings")
        if not isinstance(row, dict):
            raise ValueError("task.artifact_slots values must be objects")
        current_artifact_id = row.get("current_artifact_id")
        revision_count = row.get("revision_count")
        require_id(current_artifact_id, f"task.artifact_slots[{slot}].current_artifact_id")
        if not isinstance(revision_count, int) or revision_count <= 0:
            raise ValueError("task.artifact_slots revision_count must be a positive integer")
        normalized_slots[slot] = {
            "current_artifact_id": current_artifact_id,
            "revision_count": revision_count,
        }

    return {
        "id": task_id,
        "buddy": buddy.strip(),
        "title": title.strip(),
        "status": status,
        "track_id": track_id,
        "artifact_ids": list(dict.fromkeys(artifact_ids)),
        "artifact_slots": normalized_slots,
        "run_ids": list(dict.fromkeys(run_ids)),
        "latest_run_id": latest_run_id,
        "summary": summary or "",
        "created_at": created_at,
        "updated_at": updated_at,
    }


def validate_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    slot = artifact.get("slot")
    revision = artifact.get("revision")
    supersedes_artifact_id = artifact.get("supersedes_artifact_id")
    is_current = artifact.get("is_current")
    if not isinstance(slot, str) or not slot.strip():
        raise ValueError("artifact.slot must be a non-empty string")
    if not isinstance(revision, int) or revision <= 0:
        raise ValueError("artifact.revision must be a positive integer")
    if supersedes_artifact_id is not None:
        require_id(supersedes_artifact_id, "artifact.supersedes_artifact_id")
    if not isinstance(is_current, bool):
        raise ValueError("artifact.is_current must be a boolean")

    return {
        "id": artifact_id,
        "title": title.strip(),
        "task_id": task_id,
        "buddy": buddy.strip(),
        "skill_id": skill_id.strip(),
        "slot": slot.strip(),
        "revision": revision,
        "supersedes_artifact_id": supersedes_artifact_id,
        "is_current": is_current,
        "source_run_id": source_run_id,
        "summary": summary or "",
        "content": content,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def create_task(
    task_id: str,
    title: str,
    *,
    buddy: str,
    track_id: str | None = None,
    status: str = "active",
    summary: str = "",
    initial_run_id: str,
) -> dict[str, Any]:
    task = {
        "id": task_id,
        "buddy": buddy,
        "title": title,
        "status": status,
        "track_id": track_id,
        "artifact_ids": [],
        "artifact_slots": {},
        "run_ids": [initial_run_id],
        "latest_run_id": initial_run_id,
        "summary": summary,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def _advance_task_slot(task_id: str, slot: str, artifact_id: str, revision: int, *, summary: str | None = None) -> dict[str, Any]:
    task = get_task(task_id)
    if task is None:
        raise ValueError(f"task not found: {task_id}")
    if artifact_id not in task["artifact_ids"]:
        task["artifact_ids"].append(artifact_id)
    task["artifact_slots"][slot] = {
        "current_artifact_id": artifact_id,
        "revision_count": revision,
    }
    if summary is not None:
        task["summary"] = summary
    task["updated_at"] = now_iso()
    return save_task(task)


def create_artifact(
    *,
    artifact_id: str | None,
    title: str,
    buddy: str,
    skill_id: str,
    slot: str,
    task_id: str,
    source_run_id: str,
    summary: str = "",
    content: dict[str, Any] | None = None,
    auto_register: bool = True,
) -> dict[str, Any]:
    task = get_task(task_id)
    current_slot = task.get("artifact_slots", {}).get(slot)
    previous = get_artifact(current_slot["current_artifact_id"]) if current_slot else None
    revision = 1 if previous is None else int(previous["revision"]) + 1
    if previous is not None:
        previous["is_current"] = False
        previous["updated_at"] = now_iso()
        save_artifact(previous)

    artifact = {
        "id": resolved_id,
        "title": title,
        "task_id": task_id,
        "buddy": buddy,
        "skill_id": skill_id,
        "slot": slot,
        "revision": revision,
        "supersedes_artifact_id": previous["id"] if previous else None,
        "is_current": True,
        "source_run_id": require_id(source_run_id, "artifact.source_run_id"),
        "summary": summary,
        "content": content or {},
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    artifact = save_artifact(artifact)
    if auto_register:
        _advance_task_slot(task_id, slot, artifact["id"], revision, summary=summary or None)
    return artifact
```

- [ ] **Step 4: Run the object-model tests again**

Run: `python3 -m unittest tests.test_env_store_v2 -v`

Expected: PASS with both v2 lifecycle tests green.

- [ ] **Step 5: Commit the object-store refactor**

```bash
git add tests/test_env_store_v2.py scripts/env_store.py
git commit -m "refactor: add artifact slot revision lifecycle"
```

### Task 2: Make Track Indexes, Selector, And Workspace Views Slot-Aware

**Files:**
- Create: `framework/config/artifact-selection-v2.json`
- Modify: `scripts/env_store.py`
- Modify: `scripts/artifact_selection.py`
- Modify: `scripts/switch_runtime.py`
- Modify: `scripts/workspace_data.py`
- Modify: `tests/test_artifact_selection.py`
- Modify: `tests/test_switch_runtime.py`
- Test: `tests/test_artifact_selection.py`
- Test: `tests/test_switch_runtime.py`

- [ ] **Step 1: Add failing tests for slot-aware index and selector behavior**

```python
# tests/test_switch_runtime.py

    def test_resolve_track_artifact_index_exposes_current_artifacts_by_slot(self) -> None:
        payload = switch_runtime.resolve_switch(
            "switch dev(task-dev-slot-aware) -> track-index-resolve: continue implementation"
        )

        task_rows = payload["track_artifact_index"]["tasks"]
        pm_row = next(row for row in task_rows if row["buddy"] == "pm")
        prd_row = next(item for item in pm_row["artifacts"] if item["slot"] == "prd" and item["is_current"])

        self.assertEqual(pm_row["artifact_slots"]["prd"]["current_artifact_id"], prd_row["artifact_id"])
        self.assertEqual(prd_row["revision"], 2)
        self.assertEqual(prd_row["supersedes_artifact_id"], "art-task-pm-index-resolve-prd-r1")


# tests/test_artifact_selection.py

    def test_selection_uses_required_slots_and_current_artifacts(self) -> None:
        selected = select_artifacts_for_run(
            current_buddy="dev",
            demand="Implement the approved onboarding flow",
            required_slots=["prd", "design-spec"],
            track_artifact_index=self.track_artifact_index,
            current_task_id="task-dev-onboarding",
        )

        self.assertEqual(
            [item["slot"] for item in selected["selected_inputs"]],
            ["prd", "design-spec"],
        )
        self.assertEqual(
            selected["selected_inputs"][0]["artifact_id"],
            "art-task-pm-onboarding-prd-r3",
        )
```

- [ ] **Step 2: Run the selector/index tests to verify they fail**

Run: `python3 -m unittest tests.test_artifact_selection tests.test_switch_runtime -v`

Expected: FAIL because `track_artifact_index` still emits `latest_artifact_id` semantics and `select_artifacts_for_run()` does not accept `required_slots` or return `selected_inputs`.

- [ ] **Step 3: Implement slot-aware index projection and selection**

```python
# scripts/env_store.py

def build_track_artifact_index(track_id: str | None) -> dict[str, Any] | None:
    if not track_id:
        return None
    track = get_track(track_id)
    if track is None:
        return None
    artifact_map = {artifact["id"]: artifact for artifact in list_artifacts()}
    task_rows: list[dict[str, Any]] = []
    for task_id in track.get("task_ids", []):
        task = get_task(task_id)
        if task is None:
            continue
        artifacts = _task_artifacts_from_map(task, artifact_map)
        task_rows.append(
            {
                "task_id": task["id"],
                "buddy": task["buddy"],
                "task_title": task["title"],
                "task_summary": task.get("summary", ""),
                "artifact_slots": task.get("artifact_slots", {}),
                "artifacts": [
                    {
                        "artifact_id": artifact["id"],
                        "title": artifact["title"],
                        "slot": artifact["slot"],
                        "revision": artifact["revision"],
                        "supersedes_artifact_id": artifact["supersedes_artifact_id"],
                        "summary": artifact.get("summary", ""),
                        "skill_id": artifact.get("skill_id", ""),
                        "updated_at": artifact.get("updated_at", ""),
                        "is_current": bool(artifact.get("is_current")),
                    }
                    for artifact in artifacts
                ],
            }
        )
    return {
        "track_id": track["id"],
        "track_title": track["title"],
        "track_summary": track.get("summary", ""),
        "updated_at": track.get("updated_at", ""),
        "tasks": task_rows,
    }


# scripts/workspace_data.py

def build_task_view(task: dict[str, Any], artifact_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    current_artifacts: dict[str, dict[str, Any]] = {}
    for slot, row in task.get("artifact_slots", {}).items():
        artifact_id = row.get("current_artifact_id")
        artifact = artifact_map.get(artifact_id)
        if artifact is not None:
            current_artifacts[slot] = artifact
    return {
        **task,
        "object_path": task_object_path(task["id"]),
        "file_name": Path(task_object_path(task["id"])).name,
        "current_artifacts": current_artifacts,
        "missing": False,
    }


# scripts/artifact_selection.py

DEFAULT_CONFIG_PATH = ROOT / "framework" / "config" / "artifact-selection-v2.json"

def _latest_current_artifact_for_slot(tasks: list[dict[str, Any]], slot: str) -> dict[str, Any] | None:
    rows: list[tuple[str, str, dict[str, Any]]] = []
    for task in tasks:
        for artifact in _as_list(task.get("artifacts")):
            if not isinstance(artifact, dict):
                continue
            if _as_str(artifact.get("slot")) != slot or not bool(artifact.get("is_current")):
                continue
            rows.append(
                (
                    _as_str(artifact.get("updated_at")),
                    _as_str(artifact.get("artifact_id")),
                    artifact,
                )
            )
    rows.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return rows[0][2] if rows else None

def select_artifacts_for_run(
    *,
    current_buddy: str,
    demand: str,
    required_slots: list[str],
    track_artifact_index: dict[str, Any] | None,
    current_task_id: str | None = None,
    max_default_items: int | None = None,
) -> dict[str, Any]:
    selected_inputs: list[dict[str, Any]] = []
    for slot in required_slots:
        artifact = _latest_current_artifact_for_slot(tasks, slot)
        if artifact is None:
            continue
        selected_inputs.append(
            {
                "slot": slot,
                "artifact_id": artifact["artifact_id"],
                "revision": artifact["revision"],
                "selection_reason": "current artifact for required upstream slot",
            }
        )
    return {
        "selected_inputs": selected_inputs[:max_items],
        "selection_mode": selection_mode,
        "reasons": reasons,
    }


# scripts/switch_runtime.py

def _build_artifact_selection_context(
    *,
    buddy_id: str,
    demand: str,
    task_id: str,
    track_artifact_index: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if track_artifact_index is None:
        return None
    manifest = load_manifest(DEFAULT_MANIFEST)
    skill = buddy_skill_docs(manifest, buddy_id)[0]
    return select_artifacts_for_run(
        current_buddy=buddy_id,
        demand=demand,
        required_slots=list(skill["runtime"].get("consumes", [])),
        track_artifact_index=track_artifact_index,
        current_task_id=task_id,
    )
```

```json
// framework/config/artifact-selection-v2.json
{
  "selection_mode": "slot-current-v2",
  "history_hints": [
    "history",
    "previous",
    "prior",
    "earlier",
    "older",
    "compare",
    "evolution",
    "historical",
    "历史",
    "之前",
    "上一版",
    "回看",
    "演进"
  ],
  "max_default_items": 4
}
```

- [ ] **Step 4: Run the slot-aware selector/index tests again**

Run: `python3 -m unittest tests.test_artifact_selection tests.test_switch_runtime -v`

Expected: PASS with slot-aware assertions green.

- [ ] **Step 5: Commit the projection and selector changes**

```bash
git add framework/config/artifact-selection-v2.json scripts/env_store.py scripts/artifact_selection.py scripts/switch_runtime.py scripts/workspace_data.py tests/test_artifact_selection.py tests/test_switch_runtime.py
git commit -m "refactor: make artifact selection slot aware"
```

### Task 3: Move Runtime And Schema Authority To The Deterministic Control Plane

**Files:**
- Modify: `scripts/switch_runtime.py`
- Modify: `scripts/workspace_data.py`
- Modify: `framework/schemas/design/ia-spec.json`
- Modify: `framework/schemas/dev/implement-task.json`
- Modify: `framework/schemas/market/research-scan.json`
- Modify: `framework/schemas/pm/track-manager.json`
- Modify: `framework/schemas/pm/write-prd.json`
- Modify: `framework/schemas/test/smoke-test.json`
- Modify: `tests/test_output_schema_boundaries.py`
- Modify: `tests/test_switch_integration.py`
- Modify: `tests/test_switch_runtime.py`
- Test: `tests/test_output_schema_boundaries.py`
- Test: `tests/test_switch_integration.py`
- Test: `tests/test_switch_runtime.py`

- [ ] **Step 1: Add failing tests for command-authority cleanup**

```python
# tests/test_output_schema_boundaries.py

    def test_dev_schema_rejects_suggested_next_switch(self) -> None:
        schema = load_output_schema("framework/schemas/dev/implement-task.json")
        payload = {
            "execution_summary": "Implemented onboarding flow",
            "working_notes": [],
            "deliverables_or_changed_files": ["projects/app/src/onboarding.tsx"],
            "suggested_next_switch": "switch test: run smoke",
            "artifact_content": {
                "task_summary": "Implemented onboarding flow",
                "changed_files": ["projects/app/src/onboarding.tsx"],
                "implementation_notes": [],
                "verification_runs": [],
                "known_limitations": []
            }
        }
        self.assertNotEqual(validate_output_payload(payload, schema), [])


# tests/test_switch_integration.py

        self.assertNotIn("suggested_next_switch", persisted)
        self.assertNotIn("suggested_next_switch", run_json)
        self.assertEqual(
            persisted["recommended_switch"],
            persisted["reference_switches"]["continue_current_task"],
        )
```

- [ ] **Step 2: Run the runtime/schema tests to verify they fail**

Run: `python3 -m unittest tests.test_output_schema_boundaries tests.test_switch_integration tests.test_switch_runtime -v`

Expected: FAIL because schemas still allow `suggested_next_switch`, run audits still copy it, and runtime still emits legacy artifact-selection fields.

- [ ] **Step 3: Remove model-generated command authority and wire slot-aware artifact writes**

```python
# scripts/switch_runtime.py

def _strip_run_fields(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "execution_summary": result.get("execution_summary"),
        "working_notes": result.get("working_notes") or [],
        "deliverables_or_changed_files": result.get("deliverables_or_changed_files") or [],
    }


def _build_run_instructions(
    implicit_skill_id: str | None,
    artifact_selection: dict[str, Any] | None,
) -> dict[str, Any]:
    selected_inputs = []
    if isinstance(artifact_selection, dict):
        raw_inputs = artifact_selection.get("selected_inputs")
        if isinstance(raw_inputs, list):
            selected_inputs = [item for item in raw_inputs if isinstance(item, dict)]

    next_actions = [
        "Choose one skill_id from eligible_skills." if not implicit_skill_id else f"Use implicit_skill_id '{implicit_skill_id}' for this run.",
        "Read selected_inputs by slot before executing the skill.",
        "Read the selected buddyswitch/skills/<buddy>/<skill>/SKILL.md in the current Codex CLI session.",
        "Produce a structured result payload matching required_output_schema_by_skill[skill_id].",
        "Call persist when you want BuddySwitch to write task/artifact/track state and run audit metadata.",
    ]
    return {
        "host": "codex",
        "selected_inputs": selected_inputs,
        "next_actions": next_actions,
    }


def _persist_artifact_skill(
    *,
    resolved: dict[str, Any],
    skill: dict[str, Any],
    result: dict[str, Any],
    run_id: str,
    task: dict[str, Any],
    effective_track_id: str | None,
) -> dict[str, Any]:
    buddy = resolved["switch"]["buddy"]
    demand = resolved["switch"]["demand"]
    skill_id = skill["id"]
    artifact_id = _derive_artifact_id(task["id"], skill["runtime"]["default_artifact_kind"])
    artifact_summary = str(result.get("execution_summary") or "")
    artifact = create_artifact(
        artifact_id=artifact_id,
        title=_derive_artifact_title(buddy, skill_id, demand),
        buddy=buddy,
        skill_id=skill_id,
        slot=skill["runtime"]["default_artifact_kind"],
        task_id=task["id"],
        source_run_id=run_id,
        summary=artifact_summary,
        content=result["artifact_content"],
        auto_register=True,
    )
```

```json
// framework/schemas/dev/implement-task.json
{
  "type": "object",
  "required": [
    "execution_summary",
    "working_notes",
    "deliverables_or_changed_files",
    "artifact_content"
  ],
  "additionalProperties": false,
  "properties": {
    "execution_summary": { "type": "string" },
    "working_notes": { "type": "array", "items": { "type": "string" } },
    "deliverables_or_changed_files": { "type": "array", "items": { "type": "string" } },
    "artifact_content": {
      "type": "object",
      "required": [
        "task_summary",
        "changed_files",
        "implementation_notes",
        "verification_runs",
        "known_limitations"
      ],
      "additionalProperties": false,
      "properties": {
        "task_summary": { "type": "string" },
        "changed_files": { "type": "array", "items": { "type": "string" } },
        "implementation_notes": { "type": "array", "items": { "type": "string" } },
        "verification_runs": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["command", "result", "notes"],
            "additionalProperties": false,
            "properties": {
              "command": { "type": "string" },
              "result": { "type": "string" },
              "notes": { "type": ["string", "null"] }
            }
          }
        },
        "known_limitations": { "type": "array", "items": { "type": "string" } }
      }
    }
  }
}
```

- [ ] **Step 4: Run the runtime/schema tests again**

Run: `python3 -m unittest tests.test_output_schema_boundaries tests.test_switch_integration tests.test_switch_runtime -v`

Expected: PASS with no `suggested_next_switch` references remaining in runtime payloads or schemas.

- [ ] **Step 5: Commit the authority cleanup**

```bash
git add scripts/switch_runtime.py scripts/workspace_data.py framework/schemas/design/ia-spec.json framework/schemas/dev/implement-task.json framework/schemas/market/research-scan.json framework/schemas/pm/track-manager.json framework/schemas/pm/write-prd.json framework/schemas/test/smoke-test.json tests/test_output_schema_boundaries.py tests/test_switch_integration.py tests/test_switch_runtime.py
git commit -m "refactor: make runtime the only command authority"
```

### Task 4: Replace Markdown Frontmatter With Package Metadata Loading

**Files:**
- Create: `tests/test_env_manifest_v2.py`
- Modify: `buddyswitch/manifest.toml`
- Modify: `scripts/env_manifest.py`
- Modify: `scripts/switch_runtime.py`
- Modify: `tests/test_repo_consistency.py`
- Test: `tests/test_env_manifest_v2.py`
- Test: `tests/test_repo_consistency.py`
- Test: `tests/test_switch_runtime.py`

- [ ] **Step 1: Write the failing package-loader tests**

```python
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402


class SkillPackageLoaderTests(unittest.TestCase):
    def test_load_manifest_reads_skill_package_root(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            package_root = Path(temp_dir) / "demo-skill"
            package_root.mkdir()
            (package_root / "skill.toml").write_text(
                textwrap.dedent(
                    """\
                    id = "demo-skill"
                    buddy = "pm"
                    description = "Demo skill package."
                    produces_artifact = true
                    output_slot = "prd"
                    input_slots = ["research-report"]
                    output_schema = "framework/schemas/pm/write-prd.json"
                    produces = ["prd"]
                    consumes = ["research-report"]
                    side_effect_level = "medium"
                    required_tools = []
                    required_env = []
                    allowed_task_kinds = ["definition"]
                    """
                ),
                encoding="utf-8",
            )
            (package_root / "SKILL.md").write_text(
                textwrap.dedent(
                    """\
                    # demo-skill

                    ## Purpose
                    - Define product scope.

                    ## Use when
                    - The task is about product definition.

                    ## Do not use when
                    - The task is implementation or testing.

                    ## Inputs
                    - Research and scope context.

                    ## Outputs
                    - A structured PRD result.

                    ## Verification
                    - Confirm scope and open questions.

                    ## Examples
                    - `switch pm: define scope`

                    ## Counterexamples
                    - `switch dev: implement scope`

                    ## Gotchas
                    - Keep scope narrow.
                    """
                ),
                encoding="utf-8",
            )

            manifest_path = Path(temp_dir) / "manifest.toml"
            manifest_path.write_text(
                textwrap.dedent(
                    f"""\
                    schema_version = 1

                    [env]
                    id = "demo"
                    label = "Demo"

                    [[adapters]]
                    id = "codex"
                    path = "scripts/codex_router.py"
                    description = "Demo router."

                    [[skills]]
                    id = "demo-skill"
                    path = "{package_root.relative_to(ROOT).as_posix()}"
                    description = "Demo skill package."
                    buddies = ["pm"]
                    objects = ["task", "artifact"]

                    [[buddies]]
                    id = "pm"
                    label = "PM"
                    scope = "Owns scope."
                    skills = ["demo-skill"]
                    permissions = ["task.read", "task.create", "task.update", "artifact.read", "artifact.create", "artifact.update"]
                    """
                ),
                encoding="utf-8",
            )

            manifest = env_manifest.load_manifest(manifest_path)

        runtime = manifest["skills"][0]["runtime"]
        self.assertEqual(runtime["output_slot"], "prd")
        self.assertTrue(runtime["produces_artifact"])
        self.assertEqual(runtime["input_slots"], ["research-report"])
```

- [ ] **Step 2: Run the package-loader tests to verify the current loader fails**

Run: `python3 -m unittest tests.test_env_manifest_v2 tests.test_repo_consistency -v`

Expected: FAIL because `env_manifest` still requires frontmatter in `SKILL.md` and `manifest.toml` still points at markdown files.

- [ ] **Step 3: Implement package-root loading and switch the manifest to package paths**

```python
# scripts/env_manifest.py

def _load_skill_package(package_root: Path, skill_id: str) -> dict[str, Any]:
    if not package_root.exists() or not package_root.is_dir():
        raise ManifestError(f"Skill package not found: {package_root.relative_to(ROOT)}")
    metadata_path = package_root / "skill.toml"
    skill_doc_path = package_root / "SKILL.md"
    if not metadata_path.exists():
        raise ManifestError(f"{metadata_path.relative_to(ROOT)} not found")
    if not skill_doc_path.exists():
        raise ManifestError(f"{skill_doc_path.relative_to(ROOT)} not found")

    metadata = _load_toml(metadata_path)
    required = ("id", "buddy", "description", "produces_artifact", "input_slots", "output_schema")
    missing = [key for key in required if key not in metadata]
    if missing:
        raise ManifestError(
            f"{metadata_path.relative_to(ROOT)} is missing required key(s): {', '.join(missing)}"
        )

    produces_artifact = metadata["produces_artifact"]
    output_slot = metadata.get("output_slot")
    if produces_artifact and (not isinstance(output_slot, str) or not output_slot.strip()):
        raise ManifestError(f"{metadata_path.relative_to(ROOT)} requires output_slot when produces_artifact=true")
    if not produces_artifact and output_slot is not None:
        raise ManifestError(f"{metadata_path.relative_to(ROOT)} must omit output_slot when produces_artifact=false")

    body_lines = skill_doc_path.read_text(encoding="utf-8").splitlines()
    guidance = _parse_skill_guidance(skill_doc_path, body_lines)

    return {
        "name": metadata["id"],
        "description": metadata["description"],
        "produces_artifact": produces_artifact,
        "output_slot": output_slot.strip() if isinstance(output_slot, str) else None,
        "input_slots": [item.strip() for item in metadata.get("input_slots", [])],
        "output_schema": normalize_schema_path(str(metadata["output_schema"]).strip()),
        "side_effect_level": metadata.get("side_effect_level"),
        "required_tools": metadata.get("required_tools", []),
        "required_env": metadata.get("required_env", []),
        "produces": metadata.get("produces", []),
        "consumes": metadata.get("consumes", []),
        "allowed_task_kinds": metadata.get("allowed_task_kinds", []),
        "guidance": guidance,
        "instruction_path": (package_root / "SKILL.md").relative_to(ROOT).as_posix(),
    }


# scripts/switch_runtime.py

def _build_skill_card(skill: dict[str, Any]) -> dict[str, Any]:
    runtime = skill["runtime"]
    return {
        "id": skill["id"],
        "path": skill["path"],
        "instruction_path": runtime["instruction_path"],
        "description": skill["description"],
        "objects": skill["objects"],
        "produces_artifact": runtime["produces_artifact"],
        "output_slot": runtime.get("output_slot"),
        "input_slots": runtime.get("input_slots", []),
        "output_schema": runtime["output_schema"],
    }


def _build_artifact_selection_context(
    *,
    buddy_id: str,
    demand: str,
    task_id: str,
    track_artifact_index: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if track_artifact_index is None:
        return None
    manifest = load_manifest(DEFAULT_MANIFEST)
    skill = buddy_skill_docs(manifest, buddy_id)[0]
    return select_artifacts_for_run(
        current_buddy=buddy_id,
        demand=demand,
        required_slots=list(skill["runtime"].get("input_slots", [])),
        track_artifact_index=track_artifact_index,
        current_task_id=task_id,
    )


def _persist_artifact_skill(
    *,
    resolved: dict[str, Any],
    skill: dict[str, Any],
    result: dict[str, Any],
    run_id: str,
    task: dict[str, Any],
    effective_track_id: str | None,
) -> dict[str, Any]:
    buddy = resolved["switch"]["buddy"]
    demand = resolved["switch"]["demand"]
    skill_id = skill["id"]
    output_slot = str(skill["runtime"]["output_slot"])
    artifact_id = _derive_artifact_id(task["id"], output_slot)
    artifact_summary = str(result.get("execution_summary") or "")
    artifact = create_artifact(
        artifact_id=artifact_id,
        title=_derive_artifact_title(buddy, skill_id, demand),
        buddy=buddy,
        skill_id=skill_id,
        slot=output_slot,
        task_id=task["id"],
        source_run_id=run_id,
        summary=artifact_summary,
        content=result["artifact_content"],
        auto_register=True,
    )
```

```toml
# buddyswitch/manifest.toml

[[skills]]
id = "implement-task"
path = "buddyswitch/skills/dev/implement-task"
description = "Scoped implementation workflow for project code."
buddies = ["dev"]
objects = ["task", "artifact"]
```

- [ ] **Step 4: Run the package-loader tests again**

Run: `python3 -m unittest tests.test_env_manifest_v2 tests.test_repo_consistency tests.test_switch_runtime -v`

Expected: PASS with package-root loading and runtime consuming `input_slots` / `output_slot` metadata.

- [ ] **Step 5: Commit the package-loader infrastructure**

```bash
git add tests/test_env_manifest_v2.py buddyswitch/manifest.toml scripts/env_manifest.py scripts/switch_runtime.py tests/test_repo_consistency.py tests/test_switch_runtime.py
git commit -m "refactor: load BuddySwitch skills from package metadata"
```

### Task 5: Migrate Every Skill To The Package Contract And Materialize Templates

**Files:**
- Create: `buddyswitch/skills/market/research-scan/skill.toml`
- Create: `buddyswitch/skills/market/research-scan/assets/research-report-template.md`
- Modify: `buddyswitch/skills/market/research-scan/SKILL.md`
- Create: `buddyswitch/skills/pm/write-prd/skill.toml`
- Create: `buddyswitch/skills/pm/write-prd/assets/prd-template.md`
- Modify: `buddyswitch/skills/pm/write-prd/SKILL.md`
- Create: `buddyswitch/skills/pm/track-manager/skill.toml`
- Modify: `buddyswitch/skills/pm/track-manager/SKILL.md`
- Create: `buddyswitch/skills/design/ia-spec/skill.toml`
- Create: `buddyswitch/skills/design/ia-spec/assets/design-spec-template.md`
- Modify: `buddyswitch/skills/design/ia-spec/SKILL.md`
- Create: `buddyswitch/skills/dev/implement-task/skill.toml`
- Create: `buddyswitch/skills/dev/implement-task/assets/implementation-report-template.md`
- Modify: `buddyswitch/skills/dev/implement-task/SKILL.md`
- Create: `buddyswitch/skills/test/smoke-test/skill.toml`
- Create: `buddyswitch/skills/test/smoke-test/assets/test-report-template.md`
- Modify: `buddyswitch/skills/test/smoke-test/SKILL.md`
- Modify: `tests/test_repo_consistency.py`
- Test: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add failing consistency tests for package contents and referenced templates**

```python
# tests/test_repo_consistency.py

    def test_every_skill_package_has_metadata_and_instruction_files(self) -> None:
        expected_packages = (
            ROOT / "buddyswitch" / "skills" / "market" / "research-scan",
            ROOT / "buddyswitch" / "skills" / "pm" / "write-prd",
            ROOT / "buddyswitch" / "skills" / "pm" / "track-manager",
            ROOT / "buddyswitch" / "skills" / "design" / "ia-spec",
            ROOT / "buddyswitch" / "skills" / "dev" / "implement-task",
            ROOT / "buddyswitch" / "skills" / "test" / "smoke-test",
        )
        for package_root in expected_packages:
            self.assertTrue((package_root / "skill.toml").exists(), msg=f"missing skill.toml in {package_root}")
            self.assertTrue((package_root / "SKILL.md").exists(), msg=f"missing SKILL.md in {package_root}")

    def test_template_references_are_materialized_in_assets(self) -> None:
        expected_assets = (
            ROOT / "buddyswitch" / "skills" / "market" / "research-scan" / "assets" / "research-report-template.md",
            ROOT / "buddyswitch" / "skills" / "pm" / "write-prd" / "assets" / "prd-template.md",
            ROOT / "buddyswitch" / "skills" / "design" / "ia-spec" / "assets" / "design-spec-template.md",
            ROOT / "buddyswitch" / "skills" / "dev" / "implement-task" / "assets" / "implementation-report-template.md",
            ROOT / "buddyswitch" / "skills" / "test" / "smoke-test" / "assets" / "test-report-template.md",
        )
        for path in expected_assets:
            self.assertTrue(path.exists(), msg=f"missing template asset: {path.relative_to(ROOT)}")
```

- [ ] **Step 2: Run the consistency tests to verify the current package set fails**

Run: `python3 -m unittest tests.test_repo_consistency -v`

Expected: FAIL because no `skill.toml` files or package-local assets exist yet.

- [ ] **Step 3: Migrate the market and PM skill packages**

```toml
# buddyswitch/skills/market/research-scan/skill.toml
id = "research-scan"
buddy = "market"
description = "Browser-first market research scan workflow."
produces_artifact = true
output_slot = "research-report"
input_slots = []
output_schema = "framework/schemas/market/research-scan.json"
produces = ["research-report"]
consumes = ["task"]
side_effect_level = "medium"
required_tools = []
required_env = []
allowed_task_kinds = ["research"]

# buddyswitch/skills/pm/write-prd/skill.toml
id = "write-prd"
buddy = "pm"
description = "PM PRD authoring and scope shaping workflow."
produces_artifact = true
output_slot = "prd"
input_slots = ["research-report"]
output_schema = "framework/schemas/pm/write-prd.json"
produces = ["prd"]
consumes = ["research-report", "task"]
side_effect_level = "medium"
required_tools = []
required_env = []
allowed_task_kinds = ["definition"]

# buddyswitch/skills/pm/track-manager/skill.toml
id = "track-manager"
buddy = "pm"
description = "PM track lifecycle manager workflow."
produces_artifact = false
input_slots = []
output_schema = "framework/schemas/pm/track-manager.json"
produces = ["track-update", "task-update"]
consumes = ["track", "task"]
side_effect_level = "medium"
required_tools = []
required_env = []
allowed_task_kinds = ["track-management"]
```

```md
# buddyswitch/skills/market/research-scan/assets/research-report-template.md
# Research Report

## Demand Summary
- What was researched

## Market Signals
- Demand evidence
- Competitive evidence
- User evidence

## Decision Impact
- What PM should retain
- What remains uncertain

# buddyswitch/skills/pm/write-prd/assets/prd-template.md
# Product Requirements Document

## Problem
- User problem
- Business relevance

## Scope
- In scope
- Out of scope

## Acceptance Criteria
- User-visible outcomes
- Delivery boundaries

## Open Questions
- Unresolved decisions
```

```md
# buddyswitch/skills/market/research-scan/SKILL.md
# research-scan

## Purpose
- Produce a structured research artifact for PM decisions.

## Use when
- The task is about demand, users, competition, or market validation.

## Do not use when
- The task is about scope definition, design specification, coding, or smoke testing.

## Inputs
- Task demand and optional product context.

## Outputs
- A research-report artifact and run audit.

## Verification
- Trace claims to evidence and note uncertainty explicitly.

## Examples
- `switch market: research demand for creator onboarding`

## Counterexamples
- `switch pm: write the onboarding PRD`

## Gotchas
- Keep findings decision-ready rather than exploratory noise.

## Resources
- Template: `assets/research-report-template.md`
```

```md
# buddyswitch/skills/pm/write-prd/SKILL.md
# write-prd

## Purpose
- Define product scope and acceptance criteria that downstream buddies can execute against.

## Use when
- The task is about product definition, scope shaping, or requirement closure.

## Do not use when
- The task is research-only, design-only, implementation, or smoke validation.

## Inputs
- Task request, current PRD context, and optional research artifacts.

## Outputs
- A PRD artifact and run audit.

## Verification
- Confirm the PRD is scoped, explicit, and contains bounded open questions.

## Examples
- `switch pm: define the onboarding rewrite scope`

## Counterexamples
- `switch design: create onboarding IA spec`

## Gotchas
- Do not drift into implementation detail when the task is still product definition.

## Resources
- Template: `assets/prd-template.md`
```

- [ ] **Step 4: Migrate the design, dev, and test skill packages**

```toml
# buddyswitch/skills/design/ia-spec/skill.toml
id = "ia-spec"
buddy = "design"
description = "Information architecture and interaction specification workflow."
produces_artifact = true
output_slot = "design-spec"
input_slots = ["prd"]
output_schema = "framework/schemas/design/ia-spec.json"
produces = ["design-spec"]
consumes = ["prd", "task"]
side_effect_level = "medium"
required_tools = []
required_env = []
allowed_task_kinds = ["design"]

# buddyswitch/skills/dev/implement-task/skill.toml
id = "implement-task"
buddy = "dev"
description = "Scoped implementation workflow for project code."
produces_artifact = true
output_slot = "implementation-report"
input_slots = ["prd", "design-spec"]
output_schema = "framework/schemas/dev/implement-task.json"
produces = ["code-change", "implementation-report"]
consumes = ["prd", "design-spec", "task"]
side_effect_level = "high"
required_tools = []
required_env = []
allowed_task_kinds = ["implementation"]

# buddyswitch/skills/test/smoke-test/skill.toml
id = "smoke-test"
buddy = "test"
description = "Smoke validation workflow with structured outcomes."
produces_artifact = true
output_slot = "test-report"
input_slots = ["implementation-report"]
output_schema = "framework/schemas/test/smoke-test.json"
produces = ["test-report"]
consumes = ["implementation-report", "task"]
side_effect_level = "medium"
required_tools = []
required_env = []
allowed_task_kinds = ["validation"]
```

```md
# buddyswitch/skills/design/ia-spec/assets/design-spec-template.md
# Design Specification

## User Flow
- Entry points
- Transitions

## Screens And States
- Default
- Loading
- Empty
- Error

## Interaction Notes
- Key interactions
- Open questions

# buddyswitch/skills/dev/implement-task/assets/implementation-report-template.md
# Implementation Report

## Scope Summary
- What changed

## Changed Files
- Source files
- Support files

## Verification
- Commands run
- Results

## Limitations
- Known gaps

# buddyswitch/skills/test/smoke-test/assets/test-report-template.md
# Test Report

## Coverage
- Scenarios exercised

## Results
- Passed checks
- Failed checks
- Blocked checks

## Follow-Up
- Required fixes
- Residual risk
```

```md
# buddyswitch/skills/design/ia-spec/SKILL.md
# ia-spec

## Purpose
- Translate approved product scope into a design-spec artifact with clear flows and states.

## Use when
- The task is about IA, screen structure, or interaction behavior.

## Do not use when
- The task is product scoping, coding, or smoke validation.

## Inputs
- PRD context and relevant task notes.

## Outputs
- A design-spec artifact and run audit.

## Verification
- Confirm flows, states, and open questions are explicit.

## Examples
- `switch design: produce the onboarding IA spec`

## Counterexamples
- `switch dev: implement onboarding flow`

## Gotchas
- State coverage must include loading, empty, and error behavior.

## Resources
- Template: `assets/design-spec-template.md`

# buddyswitch/skills/dev/implement-task/SKILL.md
# implement-task

## Purpose
- Implement scoped product changes and produce a verified implementation-report artifact.

## Use when
- The task is about changing behavior in `projects/app/`.

## Do not use when
- The task is really product definition, design specification, or test-only validation.

## Inputs
- Task demand, current PRD, optional design-spec, and codebase constraints.

## Outputs
- Code changes, an implementation-report artifact, and a run audit.

## Verification
- Run relevant local checks and report limitations explicitly.

## Examples
- `switch dev: implement the onboarding CTA fix`

## Counterexamples
- `switch pm: define onboarding CTA scope`

## Gotchas
- Keep refactors local and justified.

## Resources
- Template: `assets/implementation-report-template.md`

# buddyswitch/skills/test/smoke-test/SKILL.md
# smoke-test

## Purpose
- Validate implemented behavior and produce a structured test-report artifact.

## Use when
- The task is about smoke validation, regression confirmation, or blocked verification reporting.

## Do not use when
- The task is product scoping, design specification, or implementation work.

## Inputs
- Implementation context, target scenarios, and optional upstream artifacts.

## Outputs
- A test-report artifact and run audit.

## Verification
- Record pass, fail, and blocked outcomes with enough detail for follow-up.

## Examples
- `switch test: smoke check the onboarding CTA fix`

## Counterexamples
- `switch dev: build the onboarding CTA fix`

## Gotchas
- Report blocked validation explicitly rather than implying pass.

## Resources
- Template: `assets/test-report-template.md`
```

- [ ] **Step 5: Run the package consistency tests again**

Run: `python3 -m unittest tests.test_repo_consistency -v`

Expected: PASS with all skill packages and package-local templates present.

- [ ] **Step 6: Commit the migrated skill packages**

```bash
git add buddyswitch/skills/market/research-scan buddyswitch/skills/pm/write-prd buddyswitch/skills/pm/track-manager buddyswitch/skills/design/ia-spec buddyswitch/skills/dev/implement-task buddyswitch/skills/test/smoke-test tests/test_repo_consistency.py
git commit -m "refactor: migrate BuddySwitch skills to package contracts"
```

### Task 6: Update Canonical Docs And Run The Full Regression Suite

**Files:**
- Modify: `framework/docs/switch-spec.md`
- Modify: `framework/docs/skill-architecture-best-practices.md`
- Modify: `framework/docs/interface-spec.md`
- Modify: `README.md`
- Modify: `tests/test_repo_consistency.py`
- Test: `tests/test_repo_consistency.py`
- Test: `tests/test_switch_routing.py`
- Test: `tests/test_switch_runtime.py`
- Test: `tests/test_switch_integration.py`
- Test: `tests/test_artifact_selection.py`
- Test: `tests/test_output_schema_boundaries.py`
- Test: `tests/test_env_store_v2.py`
- Test: `tests/test_env_manifest_v2.py`

- [ ] **Step 1: Add failing doc-consistency assertions for v2 terminology**

```python
# tests/test_repo_consistency.py

    def test_active_docs_use_slot_revision_and_package_contract_language(self) -> None:
        targets = (
            ROOT / "README.md",
            ROOT / "framework" / "docs" / "switch-spec.md",
            ROOT / "framework" / "docs" / "skill-architecture-best-practices.md",
            ROOT / "framework" / "docs" / "interface-spec.md",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in targets).lower()

        self.assertIn("artifact slot", combined)
        self.assertIn("revision", combined)
        self.assertIn("skill package", combined)
        self.assertNotIn("latest_artifact_id", combined)
        self.assertNotIn("suggested_next_switch", combined)
```

- [ ] **Step 2: Run the doc-consistency test to verify it fails**

Run: `python3 -m unittest tests.test_repo_consistency -v`

Expected: FAIL because canonical docs still describe `SKILL.md`-centered loading and `latest_artifact` semantics.

- [ ] **Step 3: Update the canonical docs to match the v2 contract**

```md
# framework/docs/switch-spec.md
- Runtime entry remains `scripts/switch_runtime.py`.
- BuddySwitch skills are loaded from `buddyswitch/skills/**/skill.toml`.
- Artifact writes use slot/revision semantics with one current artifact per `task + slot`.
- `reference_switches` and `recommended_switch` are the only command authorities.
- `suggested_next_switch` is retired.
```

```md
# framework/docs/interface-spec.md
- Task views expose `current_artifacts` keyed by slot.
- Track views surface slot-aware current artifacts instead of `latest_artifact`.
- Run history surfaces runtime-generated `recommended_switch` only.
```

```md
# framework/docs/skill-architecture-best-practices.md
- Skills are package directories with `skill.toml` and `SKILL.md`.
- Metadata lives in `skill.toml`; execution guidance lives in `SKILL.md`.
- Templates referenced by skills must exist under the package `assets/` directory.
```

- [ ] **Step 4: Run the full regression suite**

Run: `python3 -m unittest tests.test_env_store_v2 tests.test_env_manifest_v2 tests.test_artifact_selection tests.test_output_schema_boundaries tests.test_repo_consistency tests.test_switch_routing tests.test_switch_runtime tests.test_switch_integration -v`

Expected: PASS with all targeted regressions green and no remaining references to retired control-plane fields.

- [ ] **Step 5: Commit the docs and green test baseline**

```bash
git add framework/docs/switch-spec.md framework/docs/skill-architecture-best-practices.md framework/docs/interface-spec.md README.md tests/test_repo_consistency.py
git commit -m "docs: align canonical BuddySwitch docs with v2 control plane"
```
