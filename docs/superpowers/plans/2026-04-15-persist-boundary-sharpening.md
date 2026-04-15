# Persist Boundary Sharpening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `persist` a sharper boundary by removing redundant skill-resolution logic, treating create/reuse as an already-resolved mode, and keeping task/track/artifact/run writes as the only canonical commit responsibilities.

**Architecture:** Keep the existing `parse -> resolve -> run -> persist` pipeline. Refactor `persist_switch()` into a thin entry layer that resolves one authoritative skill context, validates the run result, materializes the resolved task mode, then hands off to the existing commit paths. Do not move canonical writes out of `persist`; only remove duplicated control logic inside it.

**Tech Stack:** Python 3, unittest, BuddySwitch runtime in `scripts/switch_runtime.py`

---

### Task 1: Lock The New Persist Boundary In Tests

**Files:**
- Modify: `tests/test_switch_runtime.py`
- Test: `tests/test_switch_runtime.py`

- [ ] **Step 1: Add a failing test for single-pass skill resolution**

```python
def test_resolve_persist_skill_requires_successful_resolved_payload(self) -> None:
    with self.assertRaisesRegex(ValueError, "resolved payload must be successful before persist"):
        switch_runtime._resolve_persist_skill(  # type: ignore[attr-defined]
            resolved={"ok": False},
            requested_skill_id=None,
        )
```

- [ ] **Step 2: Add a failing test for one authoritative persist skill lookup**

```python
def test_resolve_persist_skill_returns_selected_skill_doc(self) -> None:
    resolved = switch_runtime.resolve_switch("switch pm: manage the active track")

    buddy_id, skill = switch_runtime._resolve_persist_skill(  # type: ignore[attr-defined]
        resolved=resolved,
        requested_skill_id="track-manager",
    )

    self.assertEqual(buddy_id, "pm")
    self.assertEqual(skill["id"], "track-manager")
```

- [ ] **Step 3: Add a failing test that create/reuse is treated as resolved input, not re-decided in persist**

```python
def test_materialize_resolved_reuse_mode_returns_existing_task(self) -> None:
    task = create_task(
        "task-dev-persist-mode",
        "Persist Mode",
        buddy="dev",
        initial_run_id="run-seed-persist-mode",
    )
    task, run_id = switch_runtime._materialize_task_for_persist(  # type: ignore[attr-defined]
        buddy_id="dev",
        switch_payload={"buddy": "dev", "demand": "continue work", "track_id": None, "task_id": task["id"]},
        resolution={"mode": "reuse", "task_id": task["id"]},
    )

    self.assertEqual(task["id"], "task-dev-persist-mode")
    self.assertRegex(run_id, r"^run-")
```

- [ ] **Step 4: Run targeted tests to see the new failures**

Run: `python3 -m unittest tests.test_switch_runtime -v`  
Expected: new/updated persist-boundary assertions fail before implementation changes.


### Task 2: Refactor Persist Into Boundary Validation Plus Commit Core

**Files:**
- Modify: `scripts/switch_runtime.py`
- Test: `tests/test_switch_runtime.py`

- [ ] **Step 1: Introduce one authoritative skill-resolution helper for persist entry**

```python
def _resolve_persist_skill(
    *,
    resolved: dict[str, Any],
    requested_skill_id: str | None,
) -> tuple[str, dict[str, Any]]:
    switch_payload = resolved.get("switch") or {}
    buddy_id = switch_payload.get("buddy")
    if not isinstance(buddy_id, str) or not buddy_id:
        raise ValueError("resolved.switch.buddy is required")

    selected_skill_id = requested_skill_id or resolved.get("implicit_skill_id")
    selected_card = ...
    output_schema = ...
    return buddy_id, {"id": selected_skill_id, "runtime": {"output_schema": output_schema, ...}}
```

- [ ] **Step 2: Remove duplicated skill checks from `persist_switch()` and use the helper**

```python
buddy_id, skill = _resolve_persist_skill(
    resolved=resolved,
    requested_skill_id=skill_id,
)
selected_skill_id = skill["id"]
schema = load_output_schema(skill["runtime"]["output_schema"])
```

- [ ] **Step 3: Rename the create/reuse block mentally and structurally from “decide mode” to “materialize resolved mode”**

```python
resolution = dict(resolved.get("task_resolution") or {})
task_mode = resolution.get("mode")
task_id = resolution.get("task_id")
if task_mode not in {"create", "reuse"}:
    raise ValueError("resolved.task_resolution.mode must be 'create' or 'reuse'")

if task_mode == "create":
    task = _materialize_create_mode_task(...)
else:
    task = _materialize_reuse_mode_task(...)
```

- [ ] **Step 4: Keep `_ensure_task_binding()` and skill-specific commit paths after task materialization**

```python
task, effective_track_id, _ = _ensure_task_binding(task=task, explicit_track_id=explicit_track_id)
if selected_skill_id == "track-manager":
    return _persist_track_manager(...)
return _persist_artifact_skill(...)
```

- [ ] **Step 5: Run targeted tests until the persist boundary behavior is green**

Run: `python3 -m unittest tests.test_switch_runtime -v`  
Expected: persist-boundary tests pass with no regressions in existing switch runtime coverage.


### Task 3: Tighten Documentation To Match The Sharper Persist Boundary

**Files:**
- Modify: `framework/docs/switch-spec.md`

- [ ] **Step 1: Update the persist description to say it resolves one chosen skill context and commits canonical state**

```markdown
- `persist`
  - resolves the chosen skill context exactly once from the successful `resolved` payload
  - validates the result payload against that skill's output schema
  - materializes the already-resolved task mode (`create` or `reuse`)
  - performs canonical task/track/artifact/run writes
```

- [ ] **Step 2: Remove wording that implies persist is a second routing/orchestration layer**

```markdown
After `resolve`, the host chooses one skill from `eligible_skills` and runs it.
`persist` does not re-route the work; it validates the chosen skill/result pair and commits canonical state.
```

- [ ] **Step 3: Run a quick grep to ensure the docs use the new wording consistently**

Run: `rg -n "re-route|orchestrator|eligible_skills|materializes the already-resolved task mode|chosen skill context" framework/docs/switch-spec.md`  
Expected: the updated persist wording appears once and no stale phrasing remains nearby.


### Task 4: Final Verification

**Files:**
- Modify: `scripts/switch_runtime.py`
- Modify: `tests/test_switch_runtime.py`
- Modify: `framework/docs/switch-spec.md`

- [ ] **Step 1: Run the focused runtime test suites**

Run: `python3 -m unittest tests.test_switch_runtime tests.test_switch_integration`  
Expected: all tests pass.

- [ ] **Step 2: Review the diff for scope discipline**

Run: `git diff -- scripts/switch_runtime.py tests/test_switch_runtime.py framework/docs/switch-spec.md`  
Expected: diff only covers persist-boundary cleanup, not unrelated runtime or communication-model changes.

- [ ] **Step 3: Commit the persist-boundary cleanup**

```bash
git add scripts/switch_runtime.py tests/test_switch_runtime.py framework/docs/switch-spec.md docs/superpowers/plans/2026-04-15-persist-boundary-sharpening.md
git commit -m "refactor: sharpen persist boundary"
```
