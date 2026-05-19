# Parallel Modular Architecture Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Tests are written from required runtime outcomes first; static scans are boundary guards, not substitutes for behavior proof.

**Goal:** Close the remaining gaps so BuddySwitch satisfies `docs/memo/buddyswitch-parallel-modular-architecture.md` first-phase parallel development requirements.

**Architecture:** Keep the thin path `SKILL -> Tool Contract -> Service -> Domain Ops -> Object Repo -> JSON / Files`. Fix the current blockers directly: buddybox must honor instance workspace roots, shared tool skills must stop copying action catalogs, object repos must stop depending on monolithic cross-object storage behavior, and comment revision checks must live in domain logic. Do not introduce workflow engines, plugin systems, event buses, generic repositories, or long-lived compatibility paths.

**Tech Stack:** Python runtime env tools, broker-routed `env.tool`, `pytest`/`unittest`, static AST/text boundary checks, runtime JSON state under temporary `buddyswitch/objects/**`, active-buddy private files under temporary `buddyswitch/local/buddybox/**`, markdown skills under `buddyswitch/skills/**`.

---

## Current Verified State

The review that triggered this plan found:

- Focused parallel-runtime tests passed:
  `python3 -m pytest tests/test_env_tool_semantic_contract.py tests/test_env_tool_router.py tests/test_env_layer_boundaries.py tests/test_message_env_tool.py tests/test_comment_env_tool.py tests/test_buddybox_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_repo_consistency.py tests/test_parallel_contracts.py -q`
  produced `100 passed, 160 subtests passed`.
- Independent `message/comment/buddybox` tests passed:
  `python3 -m pytest tests/test_message_env_tool.py tests/test_comment_env_tool.py tests/test_buddybox_env_tool.py -q`
  produced `40 passed, 25 subtests passed`.
- Full suite failed:
  `python3 -m pytest -q`
  produced `1 failed, 468 passed, 1 skipped, 389 subtests passed`.
- The full-suite failure is `tests/test_runtime_broker.py::RuntimeBrokerTests::test_env_tool_buddybox_write_uses_instance_workspace_local_root`.
- Shared tool skills still duplicate action catalogs, especially `buddyswitch/skills/shared/message-tool/SKILL.md`.
- `scripts/env/repos/comments.py` still imports `env_legacy_store` and exposes `artifact_revision_chain`, which keeps comment storage tied to artifact history behavior outside the domain layer.
- `scripts/env/repos/tasks.py`, `scripts/env/repos/tracks.py`, and `scripts/env/repos/artifacts.py` still proxy through `env_legacy_store`; this keeps hidden cross-object behavior available through object repos even when sibling repo imports are absent.

## Done Criteria

This plan is complete only when all items below are true:

1. Full suite passes with `python3 -m pytest -q`.
2. Adding a new `message` action requires runtime contract/service/domain/repo/test edits, and does not require editing `buddyswitch/skills/shared/message-tool/SKILL.md`.
3. Editing one buddy-specific skill file does not require Python runtime edits.
4. `message`, `comment`, and `buddybox` tests run independently and do not require `track`, `artifact`, or `task` test modules.
5. Shared tool skills use runtime discovery for action catalogs and payload details.
6. Object repos do not import sibling repos or `env_legacy_store`.
7. Cross-object runtime rules live only in domain modules.
8. `track/artifact` publication still has one mutation domain entry point.
9. Behavior tests prove persisted state changes and no-mutation rejection paths; static scans only enforce boundaries after behavior is covered.

## Test Design Rules

- Start each task by writing or tightening a failing test against user-visible runtime behavior.
- Prefer broker-routed `env.tool` tests for runtime behavior because that is the host-visible surface.
- Snapshot persisted JSON/files before rejected writes and compare after rejection.
- Verify positive writes by checking response shape and actual files on disk.
- Do not write tests that pass only because a private helper has a specific name.
- Use static scans only for architectural boundaries that cannot be proven through one runtime action.
- Exclude `docs/**` from active-code residue scans unless a task explicitly targets docs.
- Keep high coverage targeted: each boundary gets positive behavior, negative behavior, and state isolation checks.

## File Map

Primary code files:

- `scripts/env/repos/runtime_files.py`: runtime root selection, JSON IO, ID validation, timestamps.
- `scripts/env/repos/buddybox_files.py`: active-buddy private file root and logical-name file operations.
- `scripts/env/repos/comments.py`: comment-only persistence and validation.
- `scripts/env/repos/tasks.py`: task-only persistence and validation.
- `scripts/env/repos/tracks.py`: track-only persistence and validation.
- `scripts/env/repos/artifacts.py`: artifact-only persistence and validation.
- `scripts/env/domain/comment_targets.py`: comment target readability and artifact revision chain checks.
- `scripts/env/domain/tasks.py`: task business rules and `track_id` context validation.
- `scripts/env/domain/artifact_visibility.py`: artifact readability and published revision visibility checks.
- `scripts/env/domain/publication.py`: the only track/artifact shared publication mutation module.
- `scripts/env/services/comments.py`: comment env.tool request/response adaptation.
- `scripts/env/services/tasks.py`: task env.tool request/response adaptation.
- `scripts/env/services/artifacts.py`: artifact env.tool request/response adaptation.
- `scripts/env/services/tracks.py`: track env.tool request/response adaptation.

Primary guidance files:

- `buddyswitch/skills/shared/message-tool/SKILL.md`
- `buddyswitch/skills/shared/comment-tool/SKILL.md`
- `buddyswitch/skills/shared/track-tool/SKILL.md`
- `buddyswitch/skills/shared/artifact-tool/SKILL.md`
- `buddyswitch/skills/shared/task-tool/SKILL.md`
- `buddyswitch/skills/shared/buddybox-tool/SKILL.md`

Primary tests:

- `tests/test_runtime_broker.py`
- `tests/test_buddybox_env_tool.py`
- `tests/test_runtime_skills.py`
- `tests/test_env_layer_boundaries.py`
- `tests/test_repo_consistency.py`
- `tests/test_comment_env_tool.py`
- `tests/test_task_env_tool.py`
- `tests/test_artifact_env_tool.py`
- `tests/test_track_env_tool.py`
- `tests/test_env_layer_end_to_end.py`

## Task 1: Fix Buddybox Instance Workspace Root

**Current bottleneck:** Full suite fails because buddybox writes ignore the instance `workspace_dir` when a runtime root override is active.

**Files:**

- Modify: `tests/test_runtime_broker.py`
- Modify: `tests/test_buddybox_env_tool.py`
- Modify: `scripts/env/repos/runtime_files.py`
- Verify existing behavior in: `scripts/env/repos/buddybox_files.py`

- [ ] **Step 1: Add a target-result broker lifecycle test**

Add this test next to `test_env_tool_buddybox_write_uses_instance_workspace_local_root` in `tests/test_runtime_broker.py`:

```python
    def test_env_tool_buddybox_lifecycle_uses_instance_workspace_local_root(self) -> None:
        workspace_dir = self._runtime_path("alt-workspace-lifecycle")
        workspace_dir.mkdir(parents=True, exist_ok=True)
        (workspace_dir / "AGENTS.md").write_text("# BuddySwitch Runtime Workspace\n", encoding="utf-8")
        instance_json = self._runtime_path("instance-alt-workspace-lifecycle.json")
        instance_json.write_text(
            json.dumps(
                {
                    "instance_id": "inst-pm-alt-workspace-lifecycle",
                    "buddy": "pm",
                    "status": "active",
                    "current_task_id": None,
                    "current_track_id": None,
                    "workspace_dir": str(workspace_dir),
                    "browser_port": None,
                    "created_at": "2026-05-19T00:00:00Z",
                    "updated_at": "2026-05-19T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        write_payload = self._dispatch(
            method="env.tool",
            params={
                "tool": "buddybox",
                "action": "write",
                "args": {"logical_name": "broker/lifecycle.txt", "content": "lifecycle\n"},
            },
            instance_id="inst-pm-alt-workspace-lifecycle",
            buddy="pm",
            instance_json=instance_json,
        )
        self.assertTrue(write_payload.get("ok"), msg=write_payload)

        target = workspace_dir / "buddyswitch" / "local" / "buddybox" / "pm" / "broker" / "lifecycle.txt"
        wrong_runtime_root = self._runtime_path("buddyswitch/local/buddybox/pm/broker/lifecycle.txt")
        wrong_state_root = self._runtime_path("state/buddyswitch/local/buddybox/pm/broker/lifecycle.txt")
        self.assertTrue(target.exists(), msg=target)
        self.assertFalse(wrong_runtime_root.exists(), msg=wrong_runtime_root)
        self.assertFalse(wrong_state_root.exists(), msg=wrong_state_root)

        read_payload = self._dispatch(
            method="env.tool",
            params={
                "tool": "buddybox",
                "action": "read",
                "args": {"logical_name": "broker/lifecycle.txt"},
            },
            instance_id="inst-pm-alt-workspace-lifecycle",
            buddy="pm",
            instance_json=instance_json,
        )
        self.assertTrue(read_payload.get("ok"), msg=read_payload)
        self.assertEqual(read_payload.get("content"), "lifecycle\n")

        list_payload = self._dispatch(
            method="env.tool",
            params={
                "tool": "buddybox",
                "action": "list",
                "args": {"recursive": True},
            },
            instance_id="inst-pm-alt-workspace-lifecycle",
            buddy="pm",
            instance_json=instance_json,
        )
        self.assertTrue(list_payload.get("ok"), msg=list_payload)
        files = list_payload.get("files")
        self.assertIsInstance(files, list, msg=list_payload)
        assert isinstance(files, list)
        self.assertIn("broker/lifecycle.txt", {row.get("logical_name") for row in files if isinstance(row, dict)})

        delete_payload = self._dispatch(
            method="env.tool",
            params={
                "tool": "buddybox",
                "action": "delete",
                "args": {"logical_name": "broker/lifecycle.txt"},
            },
            instance_id="inst-pm-alt-workspace-lifecycle",
            buddy="pm",
            instance_json=instance_json,
        )
        self.assertTrue(delete_payload.get("ok"), msg=delete_payload)
        self.assertFalse(target.exists(), msg=target)
```

- [ ] **Step 2: Run the focused failing test**

Run:

```bash
python3 -m pytest tests/test_runtime_broker.py::RuntimeBrokerTests::test_env_tool_buddybox_write_uses_instance_workspace_local_root tests/test_runtime_broker.py::RuntimeBrokerTests::test_env_tool_buddybox_lifecycle_uses_instance_workspace_local_root -q
```

Expected before the fix: at least one assertion fails because the file is not under the instance `workspace_dir`.

- [ ] **Step 3: Implement the root selection fix**

Change `runtime_workspace_root()` in `scripts/env/repos/runtime_files.py` so instance payload workspace wins for workspace-local files:

```python
def runtime_workspace_root(instance_payload: dict[str, Any] | None = None) -> Path:
    if isinstance(instance_payload, dict):
        candidate = instance_payload.get("workspace_dir")
        if isinstance(candidate, str) and candidate.strip():
            return Path(candidate.strip()).expanduser().resolve(strict=False)
    if _RUNTIME_ROOT_OVERRIDE is not None:
        return ROOT
    for env_key in ("BUDDYSWITCH_WORKSPACE_DIR", "BUDDYSWITCH_RUNTIME_WORKSPACE_ROOT"):
        raw = os.environ.get(env_key)
        if isinstance(raw, str) and raw.strip():
            return Path(raw.strip()).expanduser().resolve(strict=False)
    return ROOT
```

Do not change `STATE_ROOT`, `OBJECTS_ROOT`, or product object repo roots in this task.

- [ ] **Step 4: Run focused verification**

Run:

```bash
python3 -m pytest tests/test_runtime_broker.py::RuntimeBrokerTests::test_env_tool_buddybox_write_uses_instance_workspace_local_root tests/test_runtime_broker.py::RuntimeBrokerTests::test_env_tool_buddybox_lifecycle_uses_instance_workspace_local_root tests/test_buddybox_env_tool.py -q
```

Expected after the fix: all selected tests pass.

## Task 2: Remove Shared Tool Skill Action Catalog Copies

**Current bottleneck:** Shared tool skills still list complete operation sets. That violates the requirement that adding a tool action should not require shared SKILL edits.

**Files:**

- Modify: `tests/test_runtime_skills.py`
- Modify: `buddyswitch/skills/shared/message-tool/SKILL.md`
- Modify: `buddyswitch/skills/shared/comment-tool/SKILL.md`
- Modify: `buddyswitch/skills/shared/track-tool/SKILL.md`
- Modify: `buddyswitch/skills/shared/artifact-tool/SKILL.md`
- Modify: `buddyswitch/skills/shared/task-tool/SKILL.md`
- Modify: `buddyswitch/skills/shared/buddybox-tool/SKILL.md`

- [ ] **Step 1: Replace operation-list tests with runtime-discovery tests**

In `tests/test_runtime_skills.py`, replace `test_track_tool_operation_set_excludes_advance` with:

```python
    def test_shared_tool_skills_do_not_duplicate_runtime_action_catalogs(self) -> None:
        skill_paths = {
            "task": ROOT / "buddyswitch/skills/shared/task-tool/SKILL.md",
            "track": ROOT / "buddyswitch/skills/shared/track-tool/SKILL.md",
            "artifact": ROOT / "buddyswitch/skills/shared/artifact-tool/SKILL.md",
            "buddybox": ROOT / "buddyswitch/skills/shared/buddybox-tool/SKILL.md",
            "message": ROOT / "buddyswitch/skills/shared/message-tool/SKILL.md",
            "comment": ROOT / "buddyswitch/skills/shared/comment-tool/SKILL.md",
        }
        for tool, path in skill_paths.items():
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(tool=tool):
                self.assertNotIn("## operations", text)
                self.assertNotRegex(text, r"(?m)^- operations:")
                self.assertNotRegex(text, rf"env\.tool\s*[→>\-]+\s*{tool}\.")
                self.assertIn(f"context.get.tool_catalog['{tool}']", text)
                self.assertIn("python3 scripts/turn_runtime.py status", text)

    def test_runtime_contract_not_shared_skill_owns_inactive_actions(self) -> None:
        from env.tools import contracts

        self.assertNotIn("advance", contracts.supported_actions("track"))
        self.assertNotIn("resolve", contracts.supported_actions("comment"))
        self.assertNotIn("reopen", contracts.supported_actions("comment"))
```

Also update `test_message_comment_shared_tool_skills_stay_atomic` so it does not require `message.send` or `comment.add` text:

```python
                self.assertIn("env.tool", skill_text)
                self.assertIn("context.get.tool_catalog", skill_text)
```

- [ ] **Step 2: Run the new skill tests and confirm they fail**

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_shared_tool_skills_do_not_duplicate_runtime_action_catalogs tests/test_runtime_skills.py::RuntimeSkillsTests::test_message_comment_shared_tool_skills_stay_atomic -q
```

Expected before skill edits: failures in shared tool skills that contain operation lists or `env.tool -> tool.action` route copies.

- [ ] **Step 3: Edit shared tool skills to defer operation catalogs to runtime**

Use this standard runtime route shape in each shared tool skill:

```markdown
## Runtime Route

- CLI: `python3 scripts/env/client.py message send --payload '{"to_buddy":"design","content":"Please review track-alpha."}'`
- Broker method: `env.tool`
- Discover current operations, payload keys, effects, and recovery guidance with the matching runtime catalog entry, for example `context.get.tool_catalog['message']`, or `python3 scripts/turn_runtime.py status`.
```

For each tool skill, replace the example command and runtime catalog key with that skill's concrete tool id: `task`, `track`, `artifact`, `buddybox`, `message`, or `comment`.

For `message-tool`, replace the `## Operations` section with:

```markdown
## Workflow Notes

- Use this tool for direct buddy-to-buddy inbox communication.
- Start with `python3 scripts/env/client.py context summarize` so message actions run against current runtime-visible buddy ids and state.
- For exact operations, payload keys, optional keys, and response fields, inspect `context.get.tool_catalog['message']` or `python3 scripts/turn_runtime.py status`.
```

For `comment-tool`, replace the `## Operations` section with:

```markdown
## Workflow Notes

- Use this tool for plain-text discussion on readable track and artifact targets.
- Start with `python3 scripts/env/client.py context summarize` so comment actions run against current runtime-visible ids and state.
- For exact operations, payload keys, optional keys, and response fields, inspect `context.get.tool_catalog['comment']` or `python3 scripts/turn_runtime.py status`.
```

For `track-tool`, `artifact-tool`, `task-tool`, and `buddybox-tool`, remove every line that starts with `- Operations:`. Keep workflow-specific examples only where they demonstrate the current main path, not an exhaustive action catalog.

- [ ] **Step 4: Run focused skill verification**

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py::RepoConsistencyTests::test_skill_and_contract_texts_do_not_copy_payload_field_or_schema_tables -q
```

Expected after edits: all selected tests pass.

## Task 3: Move Comment Revision Scope Out of Comment Repo

**Current bottleneck:** Comment repo owns comment storage but still exposes artifact revision-chain behavior through `env_legacy_store`.

**Files:**

- Modify: `tests/test_comment_env_tool.py`
- Modify: `tests/test_env_layer_boundaries.py`
- Modify: `scripts/env/repos/comments.py`
- Modify: `scripts/env/domain/comment_targets.py`
- Modify: `scripts/env/services/comments.py`

- [ ] **Step 1: Add behavior coverage for artifact-section revision scope without target mutation**

Extend `test_artifact_section_revision_reference_must_belong_to_same_chain` in `tests/test_comment_env_tool.py` with target snapshots:

```python
        before_target = self._snapshot_artifact_json("art-cmt-chain-r2")
        before_other = self._snapshot_artifact_json("art-cmt-other-r1")

        # existing valid dispatch stays here
        self.assertTrue(valid.get("ok"), msg=valid)
        self.assertEqual(self._snapshot_artifact_json("art-cmt-chain-r2"), before_target)
        self.assertEqual(self._snapshot_artifact_json("art-cmt-other-r1"), before_other)

        before_comment_count = len(env_store.list_comments())

        # existing invalid dispatch stays here
        self.assertFalse(invalid.get("ok"), msg=invalid)
        self.assertEqual(invalid.get("permission_boundary"), "comment.artifact_revision_scope")
        self.assertEqual(self._snapshot_artifact_json("art-cmt-chain-r2"), before_target)
        self.assertEqual(self._snapshot_artifact_json("art-cmt-other-r1"), before_other)
        self.assertEqual(len(env_store.list_comments()), before_comment_count)
```

Keep this as behavior proof: valid same-chain comments create only comment objects; invalid cross-chain comments mutate nothing.

- [ ] **Step 2: Add a boundary test for comment repo ownership**

In `tests/test_env_layer_boundaries.py`, add:

```python
    def test_comment_repo_owns_only_comment_storage(self) -> None:
        path = ROOT / "scripts/env/repos/comments.py"
        source = path.read_text(encoding="utf-8")
        self.assertNotIn("env_legacy_store", source)
        self.assertNotIn("artifact_revision_chain", source)
        tree = ast.parse(source, filename=str(path))
        imported_modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.append(node.module)
        forbidden = [name for name in imported_modules if "artifacts" in name or "tracks" in name or "tasks" in name]
        self.assertEqual(forbidden, [], msg=", ".join(forbidden))
```

- [ ] **Step 3: Run tests and confirm the boundary test fails first**

Run:

```bash
python3 -m pytest tests/test_comment_env_tool.py::CommentEnvToolTests::test_artifact_section_revision_reference_must_belong_to_same_chain tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_comment_repo_owns_only_comment_storage -q
```

Expected before code edits: boundary test fails because `comments.py` imports `env_legacy_store`.

- [ ] **Step 4: Replace `scripts/env/repos/comments.py` with direct comment-only storage**

Use `runtime_files` for IO and keep all target/artifact logic out of this repo. The resulting module should expose these functions with the call signatures already used by `scripts/env/services/comments.py`: `list_comments`, `get_comment`, `save_comment`, `create_comment`, and `comments_for_target`. `create_comment` keeps keyword-only arguments for `target_type`, `target_id`, `by_buddy`, `content`, `reply_to`, `mentions`, `thread_id`, `status`, `anchor`, and `artifact_revision_id`.

The repo-level validation rules are:

```python
_TARGET_TYPES = {"track", "artifact", "artifact_section"}
_COMMENT_STATUSES = {"open", "resolved"}
_FORBIDDEN_COMMENT_FIELDS = {"resolved", "resolved_at", "task_id", "edit_history", "attachment"}
```

Persistence must use:

```python
def _comment_file(comment_id: str) -> Path:
    return runtime_files.COMMENTS_DIR / f"{runtime_files.require_id(comment_id, 'comment id')}.json"
```

`save_comment()` must call:

```python
runtime_files.require_runtime_workspace_write_root()
runtime_files.COMMENTS_DIR.mkdir(parents=True, exist_ok=True)
runtime_files.write_json_object(_comment_file(normalized["id"]), normalized)
```

- [ ] **Step 5: Move artifact revision chain checking into domain**

Add this function to `scripts/env/domain/comment_targets.py`:

```python
def artifact_revision_chain_ids(artifact_id: str) -> set[str]:
    current = artifact_repo.get_artifact(artifact_id)
    if current is None:
        return set()
    by_id = {
        row.get("id"): row
        for row in artifact_repo.list_artifacts()
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    ids: set[str] = set()
    visited: set[str] = set()
    while isinstance(current, dict):
        current_id = current.get("id")
        if not isinstance(current_id, str) or not current_id or current_id in visited:
            break
        ids.add(current_id)
        visited.add(current_id)
        supersedes_id = current.get("supersedes_artifact_id")
        if not isinstance(supersedes_id, str) or not supersedes_id:
            break
        previous = by_id.get(supersedes_id)
        if not isinstance(previous, dict):
            previous = artifact_repo.get_artifact(supersedes_id)
        if not isinstance(previous, dict):
            break
        current = previous
    return ids
```

Then change `_revision_chain_ids()` in `scripts/env/services/comments.py` to:

```python
def _revision_chain_ids(artifact_id: str) -> set[str]:
    return comment_target_domain.artifact_revision_chain_ids(artifact_id)
```

- [ ] **Step 6: Run focused comment verification**

Run:

```bash
python3 -m pytest tests/test_comment_env_tool.py tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_comment_repo_owns_only_comment_storage -q
```

Expected after edits: all selected tests pass.

## Task 4: Remove Monolithic Storage Imports from Active Object Repos

**Current bottleneck:** `tracks.py`, `artifacts.py`, and `tasks.py` still proxy through `env_legacy_store`, which lets object repos inherit hidden cross-object behavior.

**Files:**

- Modify: `tests/test_env_layer_boundaries.py`
- Modify: `tests/test_task_env_tool.py`
- Modify: `tests/test_artifact_env_tool.py`
- Modify: `tests/test_track_env_tool.py`
- Modify: `scripts/env/repos/tasks.py`
- Modify: `scripts/env/repos/tracks.py`
- Modify: `scripts/env/repos/artifacts.py`
- Modify: `scripts/env/domain/tasks.py`
- Modify: `scripts/env/domain/artifact_visibility.py`
- Modify: `scripts/env/services/artifacts.py`

- [ ] **Step 1: Add a boundary test that active object repos do not import `env_legacy_store`**

In `tests/test_env_layer_boundaries.py`, add:

```python
    def test_active_object_repos_do_not_import_env_legacy_store(self) -> None:
        repo_files = sorted(path for path in (ROOT / "scripts/env/repos").glob("*.py") if path.name != "__init__.py")
        violations: list[str] = []
        for path in repo_files:
            if path.name == "runtime_files.py":
                continue
            source = path.read_text(encoding="utf-8")
            if "env_legacy_store" in source:
                violations.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(violations, [], msg="\n".join(violations))
```

This test is a boundary requirement: object repos must own their storage directly.

- [ ] **Step 2: Add target behavior tests for moved cross-object checks**

In `tests/test_task_env_tool.py`, add or extend a test that proves task `track_id` validation is a domain rule and does not mutate track state:

```python
    def test_task_track_context_validates_read_only_track_state(self) -> None:
        track = env_store.create_track(
            "track-task-context-readonly",
            "Task Context",
            owner_buddy="pm",
            outcome="Track remains unchanged",
            appetite="1 day",
            now={"next": "seed", "blocker": None},
        )
        before_track = json.dumps(env_store.get_track(str(track["id"])), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        instance_json = self._instance_json(buddy="dev", instance_id="inst-dev-task-context-readonly")

        created = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-task-context-readonly",
            buddy="dev",
            action="create",
            args={
                "task_id": "task-dev-track-context-readonly",
                "title": "Use track as private context",
                "summary": "Task only",
                "track_id": str(track["id"]),
            },
        )
        self.assertTrue(created.get("ok"), msg=created)
        after_track = json.dumps(env_store.get_track(str(track["id"])), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        self.assertEqual(after_track, before_track)
```

In `tests/test_artifact_env_tool.py`, add or extend a test that creating a revision from a published artifact rejects archived-track targets without writing a new artifact:

```python
    def test_create_revision_from_archived_published_artifact_rejects_without_new_artifact(self) -> None:
        track = env_store.create_track("track-art-revision-archived", "Archived Revision", owner_buddy="pm")
        artifact = env_store.create_artifact_revision(
            artifact_id="art-revision-archived-r1",
            title="Archived source",
            summary="source",
            body="source body",
            template="brief",
            supersedes_artifact_id=None,
            created_by="pm",
            authors=["pm"],
            source_refs=[{"type": "note", "label": "seed"}],
        )
        env_store.publish_track_material(
            track_id=str(track["id"]),
            artifact_id=str(artifact["id"]),
            label="Archived source",
            from_buddy="pm",
            summary="source",
        )
        env_store.update_track(str(track["id"]), {"archived_at": "2026-05-19T00:00:00Z"})
        before_artifacts = {row["id"] for row in env_store.list_artifacts()}
        instance_json = self._instance_json(instance_id="inst-pm-art-archived-revision", buddy="pm")

        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-art-archived-revision",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-revision-archived-r2",
                "title": "New archived revision",
                "summary": "new",
                "template": "brief",
                "body": "new body",
                "supersedes_artifact_id": str(artifact["id"]),
            },
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual(set(row["id"] for row in env_store.list_artifacts()), before_artifacts)
```

- [ ] **Step 3: Run the boundary test and confirm it fails first**

Run:

```bash
python3 -m pytest tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_active_object_repos_do_not_import_env_legacy_store -q
```

Expected before repo edits: failures for `artifacts.py`, `tracks.py`, `tasks.py`, and `comments.py` unless Task 3 has already removed comments.

- [ ] **Step 4: Replace `scripts/env/repos/tasks.py` with direct task-only storage**

Use constants and validation in the task repo:

```python
VALID_TASK_STATUS = ("active", "blocked", "done", "archived")
_LEGACY_TASK_FIELDS = {"artifact_ids", "artifact_slots"}
```

The repo must expose these public functions with the same call signatures currently used by `scripts/env/services/tasks.py`: `valid_task_statuses`, `slugify`, `list_tasks`, `get_task`, `save_task`, `create_task`, and `update_task`.

Remove `track_exists()` from `tasks.py`.

In `scripts/env/domain/tasks.py`, import track repo and move track existence validation there:

```python
from env.repos import tasks as task_repo
from env.repos import tracks as track_repo

def optional_track_context(track_id: Any) -> str | None:
    if track_id is None:
        return None
    if not isinstance(track_id, str):
        raise TaskPayloadError("track_id must be a string or null")
    normalized = track_id.strip()
    if not normalized:
        raise TaskPayloadError("track_id must be a string or null")
    if track_repo.get_track(normalized) is None:
        raise TaskPayloadError(f"track not found: {normalized}")
    return normalized
```

- [ ] **Step 5: Replace `scripts/env/repos/tracks.py` with direct track-only storage**

Use these repo-owned constants:

```python
VALID_TRACK_STATE = ("active", "blocked", "review", "done")
VALID_TRACK_HEALTH = ("ok", "risk", "blocked", "stale")
VALID_UPDATE_KIND = ("progress", "decision", "blocker", "proof")
```

The repo must expose direct implementations for these public functions with the same call signatures currently used by track services and publication domain code: `now_iso`, `list_tracks`, `get_track`, `save_track`, `validate_track`, `create_track`, `update_track`, and `append_track_update`.

`tracks.py` must not import artifact, task, comment, message, buddybox, or legacy store modules.

- [ ] **Step 6: Replace `scripts/env/repos/artifacts.py` with direct artifact-only storage**

Use these repo-owned constants:

```python
VALID_ARTIFACT_STATUS = ("draft", "published", "archived")
VALID_ARTIFACT_TEMPLATES = ("brief", "proposal", "design", "decision", "proof", "note")
```

The repo must expose direct implementations for these public functions with the same call signatures currently used by artifact services and publication domain code: `now_iso`, `artifact_file`, `list_artifacts`, `get_artifact`, `save_artifact`, `validate_artifact`, `create_artifact_revision`, and `update_artifact`.

`artifacts.py` may validate artifact fields and demote a previous active draft owned by the same buddy. It must not check track existence or track archived state.

- [ ] **Step 7: Move published-artifact supersede checks into domain**

Add a domain helper in `scripts/env/domain/artifact_visibility.py`:

```python
def assert_supersedes_target_for_revision(
    *,
    supersedes_artifact_id: str,
    active_buddy: str,
) -> dict[str, Any]:
    artifact = artifact_repo.get_artifact(supersedes_artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {supersedes_artifact_id}")
    if not bool(artifact.get("is_current")):
        raise ValueError(f"artifact '{supersedes_artifact_id}' is not current and cannot be superseded")
    if artifact.get("status") == "draft":
        if artifact.get("created_by") != active_buddy:
            raise ValueError("supersedes_artifact_id must reference an active-buddy-owned current draft")
        return artifact
    if artifact.get("status") != "published":
        raise ValueError("supersedes_artifact_id must reference a current draft or published artifact")
    track_id = artifact.get("published_to_track")
    if not isinstance(track_id, str) or not track_id:
        raise ValueError("supersedes published artifact is missing track publication id")
    track = track_repo.get_track(track_id)
    if track is None:
        raise ValueError(f"track not found: {track_id}")
    if track.get("archived_at") is not None:
        raise ValueError("supersedes published artifact belongs to an archived track")
    in_shared = any(
        isinstance(row, dict)
        and row.get("type") == "artifact"
        and row.get("artifact_id") == supersedes_artifact_id
        and bool(row.get("current"))
        for row in track.get("shared_materials", [])
    )
    in_proof = any(
        isinstance(row, dict)
        and row.get("type") == "artifact"
        and row.get("artifact_id") == supersedes_artifact_id
        and bool(row.get("current", True))
        for row in track.get("close_proof", [])
    )
    if not (in_shared or in_proof):
        raise ValueError("supersedes_artifact_id must reference current published material/proof on a readable track")
    return artifact
```

In `scripts/env/services/artifacts.py`, call this helper before `artifact_repo.create_artifact_revision()` when `supersedes_artifact_id` is provided. The service should translate the domain `ValueError` into the existing `E_ARTIFACT_SCOPE` rejection path.

- [ ] **Step 8: Run focused object repo verification**

Run:

```bash
python3 -m pytest tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_active_object_repos_do_not_import_env_legacy_store tests/test_task_env_tool.py tests/test_artifact_env_tool.py tests/test_track_env_tool.py tests/test_comment_env_tool.py -q
```

Expected after edits: all selected tests pass.

## Task 5: Strengthen Publication Domain Single-Entry Proof

**Current bottleneck:** Publication is already centralized through `scripts/env/domain/publication.py`, but the final requirement needs a guard that prevents future direct track/artifact publication writes from services or repos.

**Files:**

- Modify: `tests/test_env_layer_boundaries.py`
- Modify: `tests/test_track_env_tool.py`
- Inspect: `scripts/env/domain/publication.py`
- Inspect: `scripts/env/services/tracks.py`
- Inspect: `scripts/env/services/artifacts.py`

- [ ] **Step 1: Add a static boundary test for publication writes**

In `tests/test_env_layer_boundaries.py`, add:

```python
    def test_track_artifact_publication_writes_only_live_in_publication_domain(self) -> None:
        publication_terms = (
            "published_to_track",
            '"status": "published"',
            "'status': 'published'",
            "shared_materials",
            "close_proof",
        )
        allowed_paths = {
            "scripts/env/domain/publication.py",
            "scripts/env/repos/artifacts.py",
            "scripts/env/repos/tracks.py",
            "scripts/env/domain/artifact_visibility.py",
        }
        scanned_roots = [ROOT / "scripts/env/services", ROOT / "scripts/env/domain"]
        violations: list[str] = []
        for root in scanned_roots:
            for path in sorted(root.glob("*.py")):
                rel = path.relative_to(ROOT).as_posix()
                source = path.read_text(encoding="utf-8")
                if rel in allowed_paths:
                    continue
                if any(term in source for term in publication_terms):
                    violations.append(rel)
        self.assertEqual(violations, [], msg="\n".join(violations))
```

This is a boundary guard only. Behavior proof remains in `tests/test_track_env_tool.py`.

- [ ] **Step 2: Ensure behavior tests cover atomic publication state**

In `tests/test_track_env_tool.py`, verify existing tests assert all of the following after `track.add_material` and `track.add_proof`:

```python
self.assertEqual(artifact.get("status"), "published")
self.assertEqual(artifact.get("published_to_track"), track_id)
self.assertTrue(artifact.get("is_current"))
self.assertIn(artifact_id, [row.get("artifact_id") for row in track.get("shared_materials", []) if row.get("current")])
```

For proof:

```python
self.assertIn(artifact_id, [row.get("artifact_id") for row in track.get("close_proof", []) if row.get("current", True)])
self.assertTrue(any(row.get("kind") == "proof" for row in track.get("updates", [])))
```

If these assertions are missing, add them to the existing positive publication tests instead of creating duplicate setup.

- [ ] **Step 3: Run publication verification**

Run:

```bash
python3 -m pytest tests/test_track_env_tool.py tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_track_artifact_publication_writes_only_live_in_publication_domain -q
```

Expected after edits: all selected tests pass.

## Task 6: Prove Independent Module Test Loops

**Current bottleneck:** The memo requires `message/comment/buddybox` tests to run independently and not be dragged through `track/artifact/task` test modules.

**Files:**

- Modify: `tests/test_parallel_contracts.py`
- Verify: `tests/test_message_env_tool.py`
- Verify: `tests/test_comment_env_tool.py`
- Verify: `tests/test_buddybox_env_tool.py`

- [ ] **Step 1: Add a subprocess proof for independent focused loops**

In `tests/test_parallel_contracts.py`, add:

```python
    def test_message_comment_buddybox_focused_tests_run_as_independent_loop(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_message_env_tool.py",
                "tests/test_comment_env_tool.py",
                "tests/test_buddybox_env_tool.py",
                "-q",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stdout + completed.stderr)
        output = completed.stdout + completed.stderr
        self.assertIn("passed", output)
        self.assertNotIn("tests/test_track_env_tool.py", output)
        self.assertNotIn("tests/test_artifact_env_tool.py", output)
        self.assertNotIn("tests/test_task_env_tool.py", output)
```

Add `import subprocess` to the top of `tests/test_parallel_contracts.py` if not present.

- [ ] **Step 2: Run the independent loop directly**

Run:

```bash
python3 -m pytest tests/test_message_env_tool.py tests/test_comment_env_tool.py tests/test_buddybox_env_tool.py -q
```

Expected: selected tests pass without running `test_track_env_tool.py`, `test_artifact_env_tool.py`, or `test_task_env_tool.py`.

- [ ] **Step 3: Run the contract proof**

Run:

```bash
python3 -m pytest tests/test_parallel_contracts.py::ParallelContractsTests::test_message_comment_buddybox_focused_tests_run_as_independent_loop -q
```

Expected: subprocess proof passes.

## Task 7: Final Runtime Contract and End-to-End Verification

**Current bottleneck:** Passing focused tests is not enough. The memo requires runtime contract tests and the full suite to pass after the boundary changes.

**Files:**

- No code files should be edited in this task unless a verification command exposes a concrete defect.

- [ ] **Step 1: Run focused architecture verification**

Run:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py tests/test_env_tool_router.py tests/test_env_layer_boundaries.py tests/test_repo_consistency.py tests/test_parallel_contracts.py tests/test_runtime_skills.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run object behavior verification**

Run:

```bash
python3 -m pytest tests/test_message_env_tool.py tests/test_comment_env_tool.py tests/test_buddybox_env_tool.py tests/test_task_env_tool.py tests/test_artifact_env_tool.py tests/test_track_env_tool.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Run runtime integration verification**

Run:

```bash
python3 -m pytest tests/test_runtime_broker.py tests/test_env_layer_end_to_end.py tests/test_turn_integration.py tests/test_env_tool_response_contract.py tests/test_runtime_tool_feedback.py -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Run full suite**

Run:

```bash
python3 -m pytest -q
```

Expected: full suite passes with no failures.

- [ ] **Step 5: Record final evidence in the implementation summary**

The final implementation summary must include:

```text
Focused architecture verification: paste the exact command from Task 7 Step 1 and its pytest summary.
Object behavior verification: paste the exact command from Task 7 Step 2 and its pytest summary.
Runtime integration verification: paste the exact command from Task 7 Step 3 and its pytest summary.
Full suite: paste `python3 -m pytest -q` and its pytest summary.
Remaining risk: state the concrete residual risk found during execution, or write `none known from executed verification` when no residual risk is known.
```

## Execution Order

Use this order to keep the shortest validated loop:

1. Task 1: Fix the known full-suite failure first.
2. Task 2: Remove shared SKILL action catalog copies.
3. Task 3: Detach comment repo and move revision-chain checks to domain.
4. Task 4: Remove monolithic storage imports from active object repos.
5. Task 5: Strengthen single publication-entry proof.
6. Task 6: Prove independent module test loops.
7. Task 7: Run focused and full verification.

Parallel execution is possible only after Task 1:

- One worker may do Task 2 because it touches skills and skill tests only.
- One worker may do Task 3 because it touches comment repo/domain/service and comment tests.
- One worker may do Task 4 only after coordinating write ownership for `scripts/env/repos/artifacts.py`, `scripts/env/repos/tracks.py`, and `scripts/env/repos/tasks.py`.
- Task 5 waits until Task 4 lands because publication boundary scans are stricter after repo detachment.

## Residual Risk to Watch

- Tests still import `env_legacy_store` for fixture setup in many files. That is acceptable during this completion step only if active runtime modules do not import it. A later cleanup can replace fixture setup with repo/domain helpers.
- Static scans can become too broad if they match harmless explanatory strings. Keep scans scoped to active runtime files and known boundary terms.
- Moving artifact supersede checks from repo to domain can change error classification. Preserve existing `E_ARTIFACT_SCOPE` rejection behavior in service tests.
- Reordering `runtime_workspace_root()` must not move product object state out of the runtime state root. Task 1 intentionally changes only workspace-local buddybox behavior.
