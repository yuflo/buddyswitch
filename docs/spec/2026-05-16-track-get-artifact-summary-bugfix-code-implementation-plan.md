# Track Get Artifact Summary Bugfix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This is a narrow bugfix plan; do not expand it into broader tool-semantics redesign.

**Goal:** Make `track.get` reliably return relation-aware artifact summaries for tracks that have artifacts, without leaking artifact content or bypassing buddy read-scope rules.

**Architecture:** Keep the existing relation authority in `scripts/env/services/track_relations.py`. Fix `track.get` so its track-context builder passes `active_buddy` into the existing `artifact_summary_row()` contract, matching `artifact.list` and `context.get`. Tests must exercise the public broker-routed env tool behavior, not private helper internals.

**Tech Stack:** Python env services, broker-routed `env.tool`, unittest integration tests, JSON runtime objects.

---

## 1. Problem Statement

`track.get --track-id <track-id>` currently fails when the requested track has at least one artifact. The failure is a service implementation bug:

```text
E_RUNTIME_BROKER_PROTOCOL
artifact_summary_row() missing 1 required positional argument: 'active_buddy'
```

The root cause is in `scripts/env/services/tracks.py`: `_track_context()` calls `track_relations.artifact_summary_row(artifact)` without the required `active_buddy`. The target contract already exists in `scripts/env/services/track_relations.py`:

```python
def artifact_summary_row(
    artifact: dict[str, Any],
    active_buddy: str,
    *,
    track: dict[str, Any] | None = None,
    task: dict[str, Any] | None = None,
) -> dict[str, Any]:
```

This bug blocks the normal source-intake path:

```text
track.get -> inspect artifact_id/readable_by_current_buddy -> artifact.get
```

## 2. Scope

### In Scope

- Add target-behavior regression tests for `track.get` with current artifacts.
- Fix `track.get` by passing `active_buddy` through the track context builder.
- Verify `track.get` returns artifact summaries without full artifact content.
- Verify `track.get` and `artifact.list --track-id` agree on current artifact visibility fields for the same track.

### Out of Scope

- Do not redesign artifact permission rules.
- Do not add fallback behavior to `artifact_summary_row()`.
- Do not add compatibility wrappers, try/except suppression, or alternate summary builders.
- Do not change `artifact.get`, `artifact.list`, `task.get`, `track.join`, or semantic docs unless tests prove this exact bugfix requires it.
- Do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.

## 3. Files

- Modify: `tests/test_track_env_tool.py`
  - Add broker-routed target-behavior tests for `track.get` with PM-owned artifacts.
- Modify: `scripts/env/services/tracks.py`
  - Change `_track_context()` to accept `active_buddy`.
  - Pass `active_buddy`, `track`, and `task` into `track_relations.artifact_summary_row()`.
  - Pass `active_buddy` from `get_track_for_active_buddy()`.

No new production files are needed.

## 4. Target-Result Test Design

Tests must be designed from observable product behavior, not from the current implementation shape.

Valid tests must:

- Dispatch through `runtime_kernel.broker.dispatch_runtime_request()` or another public env-tool dispatch surface.
- Seed a track with at least one task and at least one current artifact.
- Assert the public `track.get` response shape and safety properties.
- Fail on the current bug before implementation.
- Avoid reading or asserting private helper calls.

Invalid tests include:

- Calling `_track_context()` directly.
- Mocking `artifact_summary_row()` and asserting it was called with a specific argument list.
- Seeding a track with no artifacts and claiming `track.get` is fixed.
- Asserting only `ok=true` without checking returned artifact summary rows.
- Catching `TypeError` and returning empty artifacts.
- Adding a default `active_buddy=None` to `artifact_summary_row()` and testing that the crash disappears.
- Reading raw `buddyswitch/objects/**` files as the proof of success.

## 5. Tasks

### Task 1: Add Failing Target-Behavior Tests

**Files:**

- Modify: `tests/test_track_env_tool.py`

- [ ] **Step 1: Add a fixture helper that seeds a PM artifact on a track**

Add this method inside `TrackEnvToolTests` after `_dispatch()`:

```python
    def _seed_pm_track_with_current_artifact(
        self,
        *,
        track_id: str,
        current_buddy: str = "pm",
        next_buddy: str | None = None,
    ) -> str:
        env_store.create_track(
            track_id,
            "Source Intake Track",
            current_buddy=current_buddy,
            next_buddy=next_buddy,
            summary="track with PM source",
        )
        env_store.create_task(
            f"task-pm-{track_id}",
            "PM Source Task",
            buddy="pm",
            track_id=track_id,
            summary="PM produced source material",
        )
        artifact = env_store.create_artifact(
            artifact_id=f"art-pm-{track_id}",
            title="PM PRD",
            buddy="pm",
            kind="prd",
            task_id=f"task-pm-{track_id}",
            summary="PM PRD summary",
            content={"body": "Full PM PRD body must not appear in track.get."},
            created_by="pm",
            source_refs=[{"type": "note", "label": "seed"}],
        )
        return str(artifact["id"])
```

This helper is allowed because it creates target runtime state. It must not inspect service internals or assert implementation details.

- [ ] **Step 2: Add a test that `track.get` returns readable artifact summaries without content**

Add this test method inside `TrackEnvToolTests`:

```python
    def test_track_get_returns_artifact_summaries_for_track_with_pm_artifact(self) -> None:
        instance_json = self._instance_json(instance_id="inst-design-track-artifacts", buddy="design")
        artifact_id = self._seed_pm_track_with_current_artifact(
            track_id="track-get-artifact-summary",
            current_buddy="pm",
            next_buddy="design",
        )

        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-track-artifacts",
            buddy="design",
            tool="track",
            action="get",
            args={"track_id": "track-get-artifact-summary"},
        )

        self.assertTrue(response.get("ok"), msg=response)
        summary = response.get("track_context_summary")
        self.assertIsInstance(summary, dict, msg=response)
        assert isinstance(summary, dict)
        artifacts = summary.get("artifacts")
        self.assertIsInstance(artifacts, list, msg=response)
        assert isinstance(artifacts, list)
        self.assertEqual(len(artifacts), 1, msg=response)
        row = artifacts[0]
        self.assertEqual(row.get("artifact_id"), artifact_id)
        self.assertEqual(row.get("id"), artifact_id)
        self.assertEqual(row.get("track_id"), "track-get-artifact-summary")
        self.assertEqual(row.get("kind"), "prd")
        self.assertEqual(row.get("title"), "PM PRD")
        self.assertEqual(row.get("summary"), "PM PRD summary")
        self.assertEqual(row.get("source_buddy"), "pm")
        self.assertEqual(row.get("source_task_id"), "task-pm-track-get-artifact-summary")
        self.assertEqual(row.get("currentness"), "current")
        self.assertEqual(row.get("relation"), "next_buddy")
        self.assertTrue(row.get("readable_by_current_buddy"), msg=row)
        self.assertNotIn("content", row)
        self.assertNotIn("Full PM PRD body", json.dumps(response, ensure_ascii=False))
```

This test proves the target result: `track.get` is a safe orientation surface that returns artifact ids and readability, not full artifact bodies.

- [ ] **Step 3: Add a test that unreadable foreign artifacts are summarized without leaking content**

Add this test method inside `TrackEnvToolTests`:

```python
    def test_track_get_marks_unrelated_foreign_artifact_unreadable_without_content(self) -> None:
        instance_json = self._instance_json(instance_id="inst-dev-track-artifacts", buddy="dev")
        artifact_id = self._seed_pm_track_with_current_artifact(
            track_id="track-get-unreadable-artifact-summary",
            current_buddy="pm",
            next_buddy="design",
        )

        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-track-artifacts",
            buddy="dev",
            tool="track",
            action="get",
            args={"track_id": "track-get-unreadable-artifact-summary"},
        )

        self.assertTrue(response.get("ok"), msg=response)
        summary = response.get("track_context_summary")
        self.assertIsInstance(summary, dict, msg=response)
        assert isinstance(summary, dict)
        artifacts = summary.get("artifacts")
        self.assertIsInstance(artifacts, list, msg=response)
        assert isinstance(artifacts, list)
        self.assertEqual(len(artifacts), 1, msg=response)
        row = artifacts[0]
        self.assertEqual(row.get("artifact_id"), artifact_id)
        self.assertEqual(row.get("relation"), "observer")
        self.assertFalse(row.get("readable_by_current_buddy"), msg=row)
        self.assertNotIn("content", row)
        self.assertNotIn("Full PM PRD body", json.dumps(response, ensure_ascii=False))
```

This test is important because the fix must pass `active_buddy` into read-decision logic, not assume all summaries are readable.

- [ ] **Step 4: Add a cross-surface consistency test between `track.get` and `artifact.list`**

Add this test method inside `TrackEnvToolTests`:

```python
    def test_track_get_artifact_rows_match_artifact_list_for_same_track(self) -> None:
        instance_json = self._instance_json(instance_id="inst-design-track-artifact-list", buddy="design")
        artifact_id = self._seed_pm_track_with_current_artifact(
            track_id="track-get-list-consistency",
            current_buddy="pm",
            next_buddy="design",
        )

        track_response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-track-artifact-list",
            buddy="design",
            tool="track",
            action="get",
            args={"track_id": "track-get-list-consistency"},
        )
        list_response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-track-artifact-list",
            buddy="design",
            tool="artifact",
            action="list",
            args={"track_id": "track-get-list-consistency"},
        )

        self.assertTrue(track_response.get("ok"), msg=track_response)
        self.assertTrue(list_response.get("ok"), msg=list_response)
        track_summary = track_response.get("track_context_summary")
        self.assertIsInstance(track_summary, dict, msg=track_response)
        assert isinstance(track_summary, dict)
        track_rows = track_summary.get("artifacts")
        list_rows = list_response.get("artifacts")
        self.assertIsInstance(track_rows, list, msg=track_response)
        self.assertIsInstance(list_rows, list, msg=list_response)
        assert isinstance(track_rows, list)
        assert isinstance(list_rows, list)

        self.assertEqual(
            [
                {
                    "artifact_id": row.get("artifact_id"),
                    "source_buddy": row.get("source_buddy"),
                    "source_task_id": row.get("source_task_id"),
                    "currentness": row.get("currentness"),
                    "readable_by_current_buddy": row.get("readable_by_current_buddy"),
                }
                for row in track_rows
            ],
            [
                {
                    "artifact_id": row.get("artifact_id"),
                    "source_buddy": row.get("source_buddy"),
                    "source_task_id": row.get("source_task_id"),
                    "currentness": row.get("currentness"),
                    "readable_by_current_buddy": row.get("readable_by_current_buddy"),
                }
                for row in list_rows
            ],
        )
        self.assertEqual(track_rows[0].get("artifact_id"), artifact_id)
```

This test is not implementation-coupled: it verifies two public orientation surfaces expose the same artifact-summary truth.

- [ ] **Step 5: Run focused tests and verify they fail for the target reason**

Run:

```bash
python3 -m unittest \
  tests.test_track_env_tool.TrackEnvToolTests.test_track_get_returns_artifact_summaries_for_track_with_pm_artifact \
  tests.test_track_env_tool.TrackEnvToolTests.test_track_get_marks_unrelated_foreign_artifact_unreadable_without_content \
  tests.test_track_env_tool.TrackEnvToolTests.test_track_get_artifact_rows_match_artifact_list_for_same_track
```

Expected before implementation:

```text
FAILED or ERROR
```

At least one failure must show the missing `active_buddy` argument, either as an in-process `TypeError` or as an `E_RUNTIME_BROKER_PROTOCOL` envelope when run through a launcher-managed broker. If tests pass before implementation, stop and re-check that the current branch already contains the fix.

Do not weaken the tests to match current broken behavior.

### Task 2: Fix `track.get` by Passing Active Buddy Through the Existing Contract

**Files:**

- Modify: `scripts/env/services/tracks.py`

- [ ] **Step 1: Change `_track_context()` signature**

Replace:

```python
def _track_context(track: dict[str, Any]) -> dict[str, Any]:
```

with:

```python
def _track_context(track: dict[str, Any], active_buddy: str) -> dict[str, Any]:
```

- [ ] **Step 2: Pass relation context into `artifact_summary_row()`**

Inside `_track_context()`, replace:

```python
        for artifact in track_relations.artifacts_for_task(task_id):
            artifacts.append(track_relations.artifact_summary_row(artifact))
```

with:

```python
        for artifact in track_relations.artifacts_for_task(task_id):
            artifacts.append(track_relations.artifact_summary_row(artifact, active_buddy, track=track, task=task))
```

This is the core fix. It uses the existing relation-aware summary function and avoids adding any new permission path.

- [ ] **Step 3: Pass `active_buddy` from `get_track_for_active_buddy()`**

Inside `get_track_for_active_buddy()`, replace:

```python
    context_payload = _track_context(track)
```

with:

```python
    context_payload = _track_context(track, active_buddy)
```

- [ ] **Step 4: Search for stale `_track_context()` call sites**

Run:

```bash
rg -n "_track_context\\(" scripts tests
```

Expected after implementation:

```text
scripts/env/services/tracks.py:<line>:def _track_context(track: dict[str, Any], active_buddy: str) -> dict[str, Any]:
scripts/env/services/tracks.py:<line>:    context_payload = _track_context(track, active_buddy)
```

There must be no remaining call shaped `_track_context(track)`.

### Task 3: Verify Focused Behavior

**Files:**

- Test: `tests/test_track_env_tool.py`
- Modify: no files in this task unless a test reveals a real defect in the Task 2 implementation.

- [ ] **Step 1: Run the new focused tests**

Run:

```bash
python3 -m unittest \
  tests.test_track_env_tool.TrackEnvToolTests.test_track_get_returns_artifact_summaries_for_track_with_pm_artifact \
  tests.test_track_env_tool.TrackEnvToolTests.test_track_get_marks_unrelated_foreign_artifact_unreadable_without_content \
  tests.test_track_env_tool.TrackEnvToolTests.test_track_get_artifact_rows_match_artifact_list_for_same_track
```

Expected after implementation:

```text
Ran 3 tests
OK
```

- [ ] **Step 2: Run the track and artifact env tool suites**

Run:

```bash
python3 -m unittest tests.test_track_env_tool tests.test_artifact_env_tool
```

Expected:

```text
OK
```

These suites are the minimum relevant regression boundary because `track.get` now shares summary behavior with `artifact.list`.

- [ ] **Step 3: Run semantic host decision smoke tests**

Run:

```bash
python3 -m unittest tests.test_host_decision_surface_product_mode
```

Expected:

```text
OK
```

This does not prove the whole host flow, but it guards against breaking the currently registered host-facing decision surface while fixing the service bug.

- [ ] **Step 4: Inspect git diff for scope**

Run:

```bash
git diff -- tests/test_track_env_tool.py scripts/env/services/tracks.py
git status --short
```

Expected:

- Diff only touches the planned test file and service file.
- No runtime object files under `buddyswitch/objects/**`.
- No buddybox files under `buddyswitch/local/buddybox/**`.

## 6. Code Review Checklist

Before calling the implementation complete, verify each item:

- `track.get` no longer raises `E_RUNTIME_BROKER_PROTOCOL` for tracks with artifacts.
- `track_context_summary.artifacts` contains current artifact rows with `artifact_id`, `source_buddy`, `source_task_id`, `currentness`, `relation`, and `readable_by_current_buddy`.
- `track.get` does not include artifact `content`.
- `readable_by_current_buddy` differs correctly for related and unrelated buddies.
- `artifact.list --track-id` and `track.get` agree on the artifact row fields compared in the consistency test.
- No default `active_buddy` was added to `artifact_summary_row()`.
- No try/except suppresses the original TypeError.
- No duplicate artifact summary builder was introduced.
- No permission logic moved out of `track_relations.artifact_read_decision()`.

## 7. Definition of Done

The task is done only when:

- The three new target-behavior tests fail before the code fix and pass after it.
- `python3 -m unittest tests.test_track_env_tool tests.test_artifact_env_tool` passes.
- `python3 -m unittest tests.test_host_decision_surface_product_mode` passes.
- `git diff` shows only the narrow planned change set.
- Final report states the exact tests run and the remaining risk.

## 8. Remaining Risk

This plan fixes the concrete `track.get` crash and adds behavior coverage for artifact summaries. It does not fully solve the broader issue that host-facing tool semantics are still too vague for some workflows. That broader issue should be handled by a separate plan focused on structured `next_action_options`, source-intake host rehearsal tests, and CLI/skill explanation quality.
