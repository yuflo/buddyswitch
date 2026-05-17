# Comment Derived Relations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not implement unrelated message changes, task comments, comment edit/delete, resolution status, read receipts, notification fan-out, or a generic indexing system.

**Goal:** Make comment objects the single durable source of truth for track/artifact comment relations, removing target-object `comment_ids` persistence while preserving derived `comment_ids` in read-only workspace views.

**Architecture:** Store every comment as an immutable JSON object under `buddyswitch/objects/comments/<comment-id>.json` with `target_type` and `target_id`. Do not write comment relation state back into track or artifact JSON. Any view that needs `comment_ids` derives them by scanning comment objects and grouping by target.

**Tech Stack:** Python env store/services, broker-routed `env.tool`, JSON object files, runtime workspace projection, cleanup service, Markdown runtime skill docs, pytest/unittest.

---

## 1. Current Bottleneck

The current implementation stores comment relation state twice:

- The durable comment body stores `target_type` and `target_id`.
- The target track/artifact also stores a `comment_ids` list.

This creates a double-write path in `comment.add`: create comment object, then update the target object. Normal broker writes are serialized by runtime lock, but the model still creates avoidable consistency risk:

- comment object exists but target `comment_ids` missed the id;
- target `comment_ids` contains stale or invalid ids;
- cleanup has to mutate surviving targets just to remove deleted comment ids;
- future direct-store callers can reintroduce last-write-wins target updates.

The shortest verified fix is to remove persisted target `comment_ids` and derive relation lists from comments where needed.

## 2. Target Behavior

### Durable Comment Shape

Comment object files remain the source of truth:

```json
{
  "id": "comment-abc123def456",
  "target_type": "track",
  "target_id": "track-alpha",
  "author_buddy": "dev",
  "content": "Plain text comment",
  "reply_to": null,
  "created_at": "2026-05-17T12:00:00+08:00"
}
```

### Track And Artifact Objects

Track and artifact JSON files must not persist `comment_ids`.

New track object shape:

```json
{
  "id": "track-alpha",
  "title": "Alpha",
  "status": "active",
  "owner_buddy": "pm",
  "task_ids": [],
  "summary": "",
  "updated_at": "2026-05-17T12:00:00+08:00"
}
```

New artifact object shape keeps all existing artifact fields except `comment_ids`:

```json
{
  "id": "art-alpha",
  "title": "Alpha Artifact",
  "task_id": "task-alpha",
  "buddy": "dev",
  "kind": "prd",
  "revision": 1,
  "supersedes_artifact_id": null,
  "is_current": true,
  "created_by": "dev",
  "source_refs": null,
  "summary": "",
  "content": {},
  "created_at": "2026-05-17T12:00:00+08:00",
  "updated_at": "2026-05-17T12:00:00+08:00"
}
```

### Read Behavior

- `comment.add` creates one comment object only.
- `comment.add` does not modify the target track/artifact JSON and does not update target `updated_at`.
- `comment.list` returns comments whose stored `target_type` and `target_id` match the readable target.
- `comment.list` ignores any legacy `comment_ids` present in target JSON.
- Workspace projection may continue exposing `comment_ids` on track/artifact views, but those arrays must be derived from comment objects.
- Workspace projection must not expose top-level comment bodies.
- Task objects and task projection rows must not have `comment_ids`.

### Backward Compatibility Boundary

Existing target JSON files may still contain `comment_ids` from the old model. The new implementation must tolerate those files when reading, but normalized saves should drop the field. Stale legacy `comment_ids` must not affect `comment.list` or projection output.

## 3. Files To Change

### Runtime Code

- Modify `scripts/env_store.py`
  - Stop normalizing/persisting `comment_ids` in `validate_track()` and `validate_artifact()`.
  - Stop adding `"comment_ids": []` in `create_track()` and `create_artifact()`.
  - Remove `add_comment_id_to_track()`, `add_comment_id_to_artifact()`, and `remove_comment_id_from_target()`.

- Modify `scripts/env/services/comments.py`
  - Remove target `comment_ids` writes from `add_comment()`.
  - Update success metadata so it reports only the created comment object as mutated.
  - Keep target readability checks and reply-to same-target validation.
  - Keep `list_comments()` filtering by comment object `target_type` and `target_id`.

- Modify `scripts/runtime_store/projections.py`
  - Build a derived comment-id index from `env_store.list_comments()`.
  - Fill track/artifact view `comment_ids` from that derived index.
  - Keep task views without `comment_ids`.

- Modify `framework/contracts/workspace-projection.json`
  - Keep `comment_ids` in track/artifact view shapes if projection keeps the field.
  - Add `buddyswitch/objects/comments/*.json` to `data_sources` because the field is now derived from comment objects.

- Modify `scripts/env_cleanup.py`
  - Remove target `comment_ids` detach logic.
  - Keep deleting comment object files for buddy/all-data cleanup.
  - Keep recreating `buddyswitch/objects/comments`.

### Tests

- Modify `tests/test_env_store_v2.py`
- Modify `tests/test_comment_env_tool.py`
- Modify `tests/test_parallel_contracts.py`
- Modify `tests/test_cleanup_system.py`
- Add or modify contract coverage in `tests/test_console_app_contract.py` or the existing projection contract test if present.

### Docs

- Modify `buddyswitch/skills/shared/comment-tool/SKILL.md`
  - Say relation is stored on comment objects via `target_type` and `target_id`.
  - Say `comment_ids` in workspace projection is derived, not persisted on target objects.

Do not rewrite historical memo/spec documents unless a reviewer explicitly asks. This plan supersedes older message/comment design statements that required persisted target `comment_ids`.

## 4. Testing Principles

Tests must assert product behavior and runtime contracts, not implementation details such as a particular helper function being called.

Good tests:

- create comments through public env.tool dispatch and verify durable externally visible state;
- assert target JSON does not change after comment add;
- seed legacy target `comment_ids` and verify they do not affect comment reads or projection;
- verify projection derives ids from comment objects;
- verify cleanup deletes comment objects without mutating surviving targets.

Bad tests:

- patch `env_store.add_comment_id_to_track()` and assert it is or is not called;
- inspect source text to prove there is no helper call;
- fabricate expected output by calling the same production grouping function under test;
- assert only that `comment_ids` exists without proving where it came from.

## 5. Implementation Tasks

### Task 1: Store Model Stops Persisting Target `comment_ids`

**Files:**
- Modify: `scripts/env_store.py`
- Modify tests: `tests/test_env_store_v2.py`

- [ ] **Step 1: Replace store-model tests first**

Remove imports of `add_comment_id_to_track`, `add_comment_id_to_artifact`, and `remove_comment_id_from_target` from `tests/test_env_store_v2.py`.

Replace the current `CommentStoreTests` target-index tests with behavior tests like these:

```python
def test_track_and_artifact_records_do_not_persist_comment_ids(self):
    track = self._seed_track()
    artifact = self._seed_artifact()

    self.assertNotIn("comment_ids", track)
    self.assertNotIn("comment_ids", get_track(track["id"]))
    self.assertNotIn("comment_ids", artifact)
    self.assertNotIn("comment_ids", get_artifact(artifact["id"]))


def test_legacy_target_comment_ids_are_ignored_and_stripped_on_save(self):
    track_path = env_store.track_file("track-legacy-comments")
    track_path.parent.mkdir(parents=True, exist_ok=True)
    track_path.write_text(
        json.dumps(
            {
                "id": "track-legacy-comments",
                "title": "Legacy Comments",
                "status": "active",
                "owner_buddy": "pm",
                "task_ids": [],
                "comment_ids": ["comment-stale"],
                "summary": "",
                "updated_at": "2026-05-17T00:00:00+08:00",
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    loaded = get_track("track-legacy-comments")
    self.assertNotIn("comment_ids", loaded)

    saved = env_store.save_track(loaded)
    self.assertNotIn("comment_ids", saved)
    raw = json.loads(track_path.read_text(encoding="utf-8"))
    self.assertNotIn("comment_ids", raw)


def test_task_records_still_do_not_gain_comment_ids(self):
    task = create_task("task-no-comment-ids", "No Comment IDs", buddy="dev")
    self.assertNotIn("comment_ids", task)
```

Add `import env_store` near existing imports if the file does not already import the module namespace.

- [ ] **Step 2: Run focused tests and verify they fail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_store_v2.py::CommentStoreTests -q
```

Expected before implementation: failures showing track/artifact still contain `comment_ids` or removed helpers are still imported/tested.

- [ ] **Step 3: Update `scripts/env_store.py`**

In `validate_track()`:

- stop reading `comment_ids`;
- stop validating `track.comment_ids`;
- stop returning `"comment_ids": ...`.

The normalized return must be:

```python
return {
    "id": track_id,
    "title": title.strip(),
    "status": status,
    "owner_buddy": owner_buddy.strip(),
    "task_ids": list(dict.fromkeys(task_ids)),
    "summary": summary or "",
    "updated_at": updated_at,
}
```

In `validate_artifact()`:

- stop reading `comment_ids`;
- stop validating `artifact.comment_ids`;
- stop returning `"comment_ids": ...`.

The normalized return must keep this order around `source_refs`:

```python
return {
    "id": artifact_id,
    "title": title.strip(),
    "task_id": task_id,
    "buddy": buddy.strip(),
    "kind": kind.strip(),
    "revision": revision,
    "supersedes_artifact_id": supersedes_artifact_id,
    "is_current": is_current,
    "created_by": created_by.strip(),
    "source_refs": source_refs,
    "summary": summary or "",
    "content": content,
    "created_at": created_at,
    "updated_at": updated_at,
}
```

In `create_track()`, remove:

```python
"comment_ids": [],
```

In `create_artifact()`, remove:

```python
"comment_ids": [],
```

Delete these helper functions:

```python
def add_comment_id_to_track(...)
def add_comment_id_to_artifact(...)
def remove_comment_id_from_target(...)
```

- [ ] **Step 4: Run focused tests and verify they pass**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_store_v2.py::CommentStoreTests -q
```

Expected: all `CommentStoreTests` pass.

### Task 2: `comment.add` Writes Only Comment Objects

**Files:**
- Modify: `scripts/env/services/comments.py`
- Modify tests: `tests/test_comment_env_tool.py`

- [ ] **Step 1: Replace env-tool behavior tests first**

Rename and rewrite the track/artifact add tests so they assert no target mutation and successful target-scoped reads.

Use this shape for track comments:

```python
def test_add_and_list_track_comment_uses_comment_object_relation_without_target_mutation(self):
    track = self._seed_active_track()
    before_track = env_store.get_track(track["id"])
    instance_json = self._instance_json(instance_id="inst-design-cmt", buddy="design")

    response = self._dispatch(
        instance_json=instance_json,
        instance_id="inst-design-cmt",
        buddy="design",
        tool="comment",
        action="add",
        args={"target_type": "track", "target_id": track["id"], "content": "Nice track design!"},
    )

    self.assertTrue(response.get("ok"), msg=response)
    self.assertIn("comment_id", response)
    self.assertEqual(response["comment"]["target_type"], "track")
    self.assertEqual(response["comment"]["target_id"], track["id"])
    self.assertEqual(response["comment"]["content"], "Nice track design!")
    self.assertEqual(response["comment"]["author_buddy"], "design")

    stored_comment = env_store.get_comment(response["comment_id"])
    self.assertEqual(stored_comment["target_type"], "track")
    self.assertEqual(stored_comment["target_id"], track["id"])
    self.assertEqual(env_store.get_track(track["id"]), before_track)

    list_resp = self._dispatch(
        instance_json=instance_json,
        instance_id="inst-design-cmt",
        buddy="design",
        tool="comment",
        action="list",
        args={"target_type": "track", "target_id": track["id"]},
    )
    self.assertTrue(list_resp.get("ok"), msg=list_resp)
    comments = list_resp.get("comments", [])
    self.assertEqual([row["id"] for row in comments], [response["comment_id"]])
```

Use the same pattern for artifact comments: capture `before_artifact`, add a comment, verify `env_store.get_artifact(artifact["id"]) == before_artifact`, then verify `comment.list` returns the new comment.

Update the cross-buddy artifact relation test to assert:

```python
stored = env_store.get_comment(response["comment_id"])
self.assertEqual(stored["target_type"], "artifact")
self.assertEqual(stored["target_id"], "art-cmt-pm-relation")
```

and remove assertions that inspect artifact `comment_ids`.

Add this regression test to prove legacy target indexes are ignored:

```python
def test_comment_list_ignores_legacy_target_comment_ids_and_uses_comment_objects(self):
    track = self._seed_active_track()
    legacy_track = env_store.get_track(track["id"])
    legacy_track["comment_ids"] = ["comment-stale"]
    env_store.track_file(track["id"]).write_text(
        json.dumps(legacy_track, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )

    real = env_store.create_comment(
        target_type="track",
        target_id=track["id"],
        author_buddy="design",
        content="Real relation",
    )
    instance_json = self._instance_json(instance_id="inst-design-legacy-list", buddy="design")

    response = self._dispatch(
        instance_json=instance_json,
        instance_id="inst-design-legacy-list",
        buddy="design",
        tool="comment",
        action="list",
        args={"target_type": "track", "target_id": track["id"]},
    )

    self.assertTrue(response.get("ok"), msg=response)
    self.assertEqual([row["id"] for row in response.get("comments", [])], [real["id"]])
```

This test intentionally writes legacy raw JSON to simulate old persisted state. It must not call any production helper that would already strip the legacy field.

- [ ] **Step 2: Run focused tests and verify they fail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_comment_env_tool.py::CommentEnvToolTests -q
```

Expected before implementation: failures where `comment.add` mutates target objects or old helper references are still present.

- [ ] **Step 3: Update `scripts/env/services/comments.py`**

Remove this block from `add_comment()`:

```python
if target_type == "track":
    env_store.add_comment_id_to_track(target_id, comment["id"])
else:
    env_store.add_comment_id_to_artifact(target_id, comment["id"])
```

Update the success payload:

```python
return tool_responses.success(
    tool="comment",
    action=action,
    active_buddy=active_buddy,
    effect_summary=f"Added one durable comment to {target_type} '{target_id}'.",
    state_changed=True,
    durability="durable",
    created_ids=[comment["id"]],
    state_changes=[
        {
            "object_type": "comment",
            "change": "added",
            "comment_id": comment["id"],
            "target_type": target_type,
            "target_id": target_id,
        },
    ],
    allowed_next_actions=[
        "Use comment.list to view all comments on this target.",
    ],
    extra={
        "comment_id": comment["id"],
        "comment": comment,
        "target_type": target_type,
        "target_id": target_id,
    },
)
```

Do not change `_readable_target()`, `_validate_reply_to()`, or `list_comments()` except to remove any stale comments saying it reads target `comment_ids`.

- [ ] **Step 4: Run focused tests and verify they pass**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_comment_env_tool.py::CommentEnvToolTests -q
```

Expected: all comment env tool tests pass.

### Task 3: Workspace Projection Derives `comment_ids`

**Files:**
- Modify: `scripts/runtime_store/projections.py`
- Modify: `framework/contracts/workspace-projection.json`
- Modify tests: `tests/test_parallel_contracts.py`

- [ ] **Step 1: Write projection behavior tests first**

Update `tests/test_parallel_contracts.py` so it proves projected `comment_ids` are derived from comment objects.

Seed comments after creating a track/artifact:

```python
track_comment = env_store.create_comment(
    target_type="track",
    target_id=track["id"],
    author_buddy="dev",
    content="Track comment",
)
artifact_comment = env_store.create_comment(
    target_type="artifact",
    target_id=artifact["id"],
    author_buddy="dev",
    content="Artifact comment",
)
```

Also seed stale legacy ids directly into raw target JSON to prove projection ignores old persisted indexes:

```python
raw_track = env_store.get_track(track["id"])
raw_track["comment_ids"] = ["comment-stale-track"]
env_store.track_file(track["id"]).write_text(
    json.dumps(raw_track, ensure_ascii=True, indent=2) + "\n",
    encoding="utf-8",
)

raw_artifact = env_store.get_artifact(artifact["id"])
raw_artifact["comment_ids"] = ["comment-stale-artifact"]
env_store.artifact_file(artifact["id"]).write_text(
    json.dumps(raw_artifact, ensure_ascii=True, indent=2) + "\n",
    encoding="utf-8",
)
```

Assert:

```python
self.assertEqual(row.get("comment_ids"), [track_comment["id"]])

artifact_row = next(r for r in artifacts if isinstance(r, dict) and r.get("id") == artifact["id"])
self.assertEqual(artifact_row.get("comment_ids"), [artifact_comment["id"]])

task_row = next(r for r in tasks if isinstance(r, dict) and r.get("id") == task["id"])
self.assertNotIn("comment_ids", task_row, msg="task view must not expose comment_ids")
self.assertNotIn("comments", payload, msg="workspace projection must not expose top-level comments")
```

Add or update a contract assertion that `framework/contracts/workspace-projection.json` includes `buddyswitch/objects/comments/*.json` in `data_sources` when `comment_ids` remain in projection.

- [ ] **Step 2: Run projection tests and verify they fail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_parallel_contracts.py -q
```

Expected before implementation: projection either returns stale target ids or empty arrays because it is not deriving from comment objects.

- [ ] **Step 3: Update `scripts/runtime_store/projections.py`**

Add a local helper:

```python
def build_comment_ids_by_target(comments: list[dict[str, Any]]) -> dict[tuple[str, str], list[str]]:
    grouped: dict[tuple[str, str], list[str]] = {}
    for comment in comments:
        target_type = comment.get("target_type")
        target_id = comment.get("target_id")
        comment_id = comment.get("id")
        if not isinstance(target_type, str) or target_type not in {"track", "artifact"}:
            continue
        if not isinstance(target_id, str) or not target_id:
            continue
        if not isinstance(comment_id, str) or not comment_id:
            continue
        grouped.setdefault((target_type, target_id), []).append(comment_id)
    return grouped
```

Change `build_artifact_view()` signature:

```python
def build_artifact_view(
    artifact: dict[str, Any],
    comment_ids_by_target: dict[tuple[str, str], list[str]],
) -> dict[str, Any]:
    return {
        **artifact,
        "object_path": artifact_object_path(artifact["id"]),
        "file_name": Path(artifact_object_path(artifact["id"])).name,
        "comment_ids": list(comment_ids_by_target.get(("artifact", artifact["id"]), [])),
        "missing": False,
    }
```

Change `build_track_views()` signature and row construction:

```python
def build_track_views(
    tracks: list[dict[str, Any]],
    task_map: dict[str, dict[str, Any]],
    comment_ids_by_target: dict[tuple[str, str], list[str]],
) -> list[dict[str, Any]]:
```

Inside the track row:

```python
"comment_ids": list(comment_ids_by_target.get(("track", track["id"]), [])),
```

Change `build_workspace_projection()` to build the index once:

```python
comments = env_store.list_comments()
comment_ids_by_target = build_comment_ids_by_target(comments)
artifacts = [
    build_artifact_view(artifact, comment_ids_by_target)
    for artifact in env_store.list_artifacts()
]
```

And pass `comment_ids_by_target` to `build_track_views(...)`.

- [ ] **Step 4: Update workspace projection contract**

In `framework/contracts/workspace-projection.json`, add this item to `data_sources`:

```json
"buddyswitch/objects/comments/*.json"
```

Keep `comment_ids` in track/artifact view shapes because it remains a read-only derived projection field.

- [ ] **Step 5: Run projection tests and verify they pass**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_parallel_contracts.py tests/test_console_app_contract.py -q
```

Expected: projection and contract tests pass, with no top-level comments collection.

### Task 4: Cleanup Stops Detaching Target Comment Ids

**Files:**
- Modify: `scripts/env_cleanup.py`
- Modify tests: `tests/test_cleanup_system.py`

- [ ] **Step 1: Write cleanup regression test first**

Add a test that proves buddy cleanup deletes authored comment objects without mutating surviving target objects.

Test shape:

```python
def test_buddy_cleanup_deletes_authored_comments_without_mutating_surviving_targets(self):
    root = self.repo_root
    track_path = root / "buddyswitch/objects/tracks/track-clean-comment.json"
    track_payload = {
        "id": "track-clean-comment",
        "title": "Clean Comment",
        "status": "active",
        "owner_buddy": "pm",
        "task_ids": [],
        "summary": "",
        "updated_at": "2026-05-17T00:00:00+08:00",
    }
    track_path.parent.mkdir(parents=True, exist_ok=True)
    track_path.write_text(json.dumps(track_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    dev_comment_path = root / "buddyswitch/objects/comments/comment-dev-clean.json"
    design_comment_path = root / "buddyswitch/objects/comments/comment-design-keep.json"
    dev_comment_path.parent.mkdir(parents=True, exist_ok=True)
    dev_comment_path.write_text(
        json.dumps(
            {
                "id": "comment-dev-clean",
                "target_type": "track",
                "target_id": "track-clean-comment",
                "author_buddy": "dev",
                "content": "delete me",
                "reply_to": None,
                "created_at": "2026-05-17T00:00:00+08:00",
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    design_comment_path.write_text(
        json.dumps(
            {
                "id": "comment-design-keep",
                "target_type": "track",
                "target_id": "track-clean-comment",
                "author_buddy": "design",
                "content": "keep me",
                "reply_to": None,
                "created_at": "2026-05-17T00:00:01+08:00",
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    plan = env_cleanup.build_cleanup_plan(root, scope="buddy", buddy="dev")
    result = env_cleanup.execute_cleanup_plan(plan)

    self.assertTrue(result["ok"], msg=result)
    self.assertFalse((root / "buddyswitch/objects/comments/comment-dev-clean.json").exists())
    self.assertTrue((root / "buddyswitch/objects/comments/comment-design-keep.json").exists())
    self.assertEqual(json.loads(track_path.read_text(encoding="utf-8")), track_payload)
```

Use existing helper names in `tests/test_cleanup_system.py`; if the class uses a different temp root or JSON writer, adapt only the fixture access, not the assertions.

- [ ] **Step 2: Run cleanup tests and verify they fail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cleanup_system.py -q
```

Expected before implementation: failures if cleanup still tries to detach target comment ids or if tests still expect target mutation.

- [ ] **Step 3: Update `scripts/env_cleanup.py`**

Delete `detach_comment_id_from_target()`.

In `execute_cleanup_plan()`, remove this block:

```python
# Detach comment ids from surviving targets before deleting comments
for record in plan["comment_records"]:
    target_type = record.get("target_type")
    target_id = record.get("target_id")
    if isinstance(target_type, str) and isinstance(target_id, str) and target_type in {"track", "artifact"}:
        detach_comment_id_from_target(root, target_type, target_id, record["id"], warnings=warnings)
```

Do not change message/comment discovery, all-data cleanup, skeleton recreation, or deletion of selected comment files.

- [ ] **Step 4: Run cleanup tests and verify they pass**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cleanup_system.py -q
```

Expected: cleanup tests pass.

### Task 5: Runtime Skill And Contract Text

**Files:**
- Modify: `buddyswitch/skills/shared/comment-tool/SKILL.md`
- Optional modify: active docs only if tests enforce them

- [ ] **Step 1: Update runtime skill text**

In `buddyswitch/skills/shared/comment-tool/SKILL.md`, replace:

```markdown
- Comments are attached to tracks and artifacts via `comment_ids` list on the target object.
```

with:

```markdown
- Comment relations are stored on comment objects via `target_type` and `target_id`.
- Workspace views may expose `comment_ids` on tracks/artifacts as derived read-only fields; target objects do not persist those lists.
```

Keep all existing exclusions: no task comments, no resolution/status workflow, no edit/delete, no direct messaging.

- [ ] **Step 2: Run runtime skill tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

Expected: skill and repo consistency tests pass. If a repo consistency test asserts old `comment_ids` wording, update that test to assert the new source-of-truth wording instead.

### Task 6: Full Verification

**Files:**
- No new code changes unless verification exposes a missed dependency.

- [ ] **Step 1: Run focused suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_store_v2.py::CommentStoreTests \
  tests/test_comment_env_tool.py::CommentEnvToolTests \
  tests/test_parallel_contracts.py \
  tests/test_cleanup_system.py \
  tests/test_runtime_skills.py \
  -q
```

Expected: all pass.

- [ ] **Step 2: Run broader relevant suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_store_v2.py \
  tests/test_comment_env_tool.py \
  tests/test_message_env_tool.py \
  tests/test_context_binding_env_tool.py \
  tests/test_env_tool_response_contract.py \
  tests/test_env_tool_router.py \
  tests/test_parallel_contracts.py \
  tests/test_console_app_contract.py \
  tests/test_cleanup_system.py \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  -q
```

Expected: all pass.

- [ ] **Step 3: Search for stale runtime references**

Run:

```bash
rg -n "add_comment_id_to_|remove_comment_id_from_target|target object.*comment_ids|via `comment_ids` list on the target object|persist.*comment_ids|persistence updates `comment_ids`" scripts framework tests buddyswitch
```

Expected: no active runtime/test/skill references to persisted target `comment_ids`. Historical docs under `docs/memo` and older superseded plans may still mention the old design, but active runtime instructions must not.

- [ ] **Step 4: Inspect JSON key behavior manually**

Run a tiny Python check in the test sandbox or a temporary runtime root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import os
import tempfile
from pathlib import Path
import sys

root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))
import env_store

with tempfile.TemporaryDirectory() as tmp:
    state = Path(tmp)
    env_store.ROOT = state
    env_store.STATE_ROOT = state
    env_store.OBJECTS_ROOT = state / "buddyswitch" / "objects"
    env_store.TRACKS_DIR = env_store.OBJECTS_ROOT / "tracks"
    env_store.TASKS_DIR = env_store.OBJECTS_ROOT / "tasks"
    env_store.ARTIFACT_OBJECTS_DIR = env_store.OBJECTS_ROOT / "artifacts"
    env_store.MESSAGES_DIR = env_store.OBJECTS_ROOT / "messages"
    env_store.COMMENTS_DIR = env_store.OBJECTS_ROOT / "comments"
    (state / "AGENTS.md").write_text("# BuddySwitch Runtime Workspace\n", encoding="utf-8")
    track = env_store.create_track("track-manual", "Manual")
    task = env_store.create_task("task-manual", "Manual Task", buddy="dev", track_id=track["id"])
    artifact = env_store.create_artifact(
        artifact_id="art-manual",
        title="Manual Artifact",
        buddy="dev",
        kind="prd",
        task_id=task["id"],
        created_by="dev",
    )
    comment = env_store.create_comment(
        target_type="track",
        target_id=track["id"],
        author_buddy="dev",
        content="Manual comment",
    )
    assert "comment_ids" not in env_store.get_track(track["id"])
    assert "comment_ids" not in env_store.get_artifact(artifact["id"])
    assert env_store.get_comment(comment["id"])["target_id"] == track["id"]
print("manual comment relation check passed")
PY
```

Expected output:

```text
manual comment relation check passed
```

## 6. Non-Goals

- Do not add a database.
- Do not add persistent secondary indexes.
- Do not add target-scoped index files such as `comments/by-target/...`.
- Do not expose top-level comments in `/api/workspace`.
- Do not change message storage.
- Do not add comment delete/edit/status/resolution tools.
- Do not add task comments.
- Do not broaden artifact read rules.

## 7. Expected End State

- `comment.add` has one durable write: the comment object.
- Track/artifact JSON no longer stores `comment_ids`.
- Legacy target `comment_ids` are ignored and stripped on normalized saves.
- `comment.list` continues to work by scanning comments and filtering by `target_type + target_id`.
- Workspace projection still exposes track/artifact `comment_ids`, but only as derived read-only fields.
- Cleanup deletes comment objects without mutating surviving target objects.
- Tests prove behavior through public env tool dispatch, object JSON state, projection output, and cleanup results.

## 8. Self-Review Checklist

- [ ] Store model tests fail before code changes and pass after target `comment_ids` are removed.
- [ ] `comment.add` tests prove target JSON is unchanged.
- [ ] `comment.list` tests prove legacy target `comment_ids` are ignored.
- [ ] Projection tests prove derived `comment_ids` come from comment objects, not target JSON.
- [ ] Cleanup tests prove surviving targets are not mutated when comment objects are deleted.
- [ ] Active skill docs no longer teach persisted target `comment_ids`.
- [ ] No runtime helper remains whose only purpose is maintaining target `comment_ids`.
