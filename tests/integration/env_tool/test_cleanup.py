"""Cleanup backend tests for active collaboration surfaces."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
from buddyswitch.application.build import build_application  # noqa: E402
from buddyswitch.runtime_support import env_cleanup  # noqa: E402


class CleanupRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.shared_root = Path(self._tmp.name)
        self.repo_root = self.shared_root / "state"
        self.repo_root.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.repo_root / "buddyswitch" / "manifest.toml"
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "src" / "buddyswitch" / "catalog" / "manifest.toml", self.manifest_path)
        self.product_cleanup = build_application().cleanup

        self._write_json(
            "buddyswitch/objects/tracks/track-demo.json",
            {
                "id": "track-demo",
                "title": "Demo",
                "outcome": "Cleanup fixture",
                "owner_role": "pm",
                "state": "active",
                "health": "ok",
                "appetite": "1 day",
                "now": {"next": "fixture", "blocker": None},
                "shared_materials": [],
                "updates": [],
                "close_proof": [],
                "created_at": "2026-05-15T00:00:00+00:00",
                "updated_at": "2026-05-15T00:00:00+00:00",
                "archived_at": None,
            },
        )
        self._write_json(
            "buddyswitch/objects/artifacts/art-pm-r1.json",
            {
                "id": "art-pm-r1",
                "kind": "prd",
                "title": "PM PRD",
                "created_by_actor": {"actor_id": "act-pm-clean", "role_id": "pm"},
                "published_to_track": None,
                "publication_role": None,
                "summary": "",
                "content": {"body": "x"},
                "revision": 1,
                "source_refs": [],
                "supersedes_artifact_id": None,
                "is_current": True,
                "created_at": "2026-05-15T00:00:00+00:00",
                "updated_at": "2026-05-15T00:00:00+00:00",
            },
        )
        self._write_json(
            "buddyswitch/objects/artifacts/art-dev-r1.json",
            {
                "id": "art-dev-r1",
                "kind": "implementation-report",
                "title": "DEV report",
                "created_by_actor": {"actor_id": "act-dev-clean", "role_id": "dev"},
                "published_to_track": None,
                "publication_role": None,
                "summary": "",
                "content": {"body": "x"},
                "revision": 1,
                "source_refs": [],
                "supersedes_artifact_id": None,
                "is_current": True,
                "created_at": "2026-05-15T00:00:00+00:00",
                "updated_at": "2026-05-15T00:00:00+00:00",
            },
        )
        self._write_json(
            "buddyswitch/objects/handoffs/handoff-stale.json",
            {
                "id": "handoff-stale",
                "source_role": "pm",
                "target_role": "dev",
            },
        )
    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _path(self, rel: str) -> Path:
        return self.repo_root / rel

    def _write_json(self, rel: str, payload: dict[str, object]) -> None:
        path = self._path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def _instance_workspace(self, *, actor_id: str, role: str) -> Path:
        instance_root = self.shared_root / "instances" / actor_id
        workspace = instance_root / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        (instance_root / "instance.json").write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": role,
                    "status": "active",
                    "instance_root": str(instance_root),
                    "workspace_dir": str(workspace),
                    "browser_port": None,
                    "updated_at": "2026-05-19T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return workspace

    def test_cleanup_plan_excludes_handoff_indexing(self) -> None:
        plan = env_cleanup.build_cleanup_plan(
            scope="role",
            role="pm",
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            contributions=self.product_cleanup,
        )
        self.assertEqual(plan["scope"], "role")
        self.assertIn("art-pm-r1", plan["artifact_object_ids"])
        self.assertNotIn("task_" + "object_ids", plan)
        self.assertNotIn("task_" + "records", plan)
        self.assertNotIn("handoff_object_ids", plan)
        self.assertNotIn("handoff_records", plan)
        self.assertNotIn("handoff_objects", plan.get("counts_by_category", {}))
        self.assertNotIn("task_" + "objects", plan.get("counts_by_category", {}))

    def test_execute_all_data_cleanup_recreates_active_skeleton_only(self) -> None:
        plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            role=None,
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            contributions=self.product_cleanup,
        )
        result = env_cleanup.execute_cleanup_plan(
            plan,
            contributions=self.product_cleanup,
        )
        self.assertTrue(result["ok"])

        for directory in (
            "buddyswitch/objects/tracks",
            "buddyswitch/objects/artifacts",
            "im/messages",
            "buddyswitch/objects/track-comments",
        ):
            self.assertTrue(self._path(directory).is_dir(), f"missing recreated dir: {directory}")
        self.assertFalse(self._path("buddyswitch/objects" + "/tasks").exists())

    def test_cleanup_plan_includes_message_and_comment_objects(self) -> None:
        """MCT-RUN-003: All-data cleanup plan discovers message and comment objects."""
        self._write_json(
            "im/messages/msg-test.json",
            {
                "id": "msg-test",
                "conversation_id": "conv-test",
                "sender_identity": {"id": "act-pm-clean", "type": "actor"},
                "target_identity": {"id": "act-dev-clean", "type": "actor"},
                "content": "hello",
                "reply_to": None,
                "created_at": "2026-05-17T00:00:00+08:00",
            },
        )
        retired_shape = {
            "id": "msg-retired",
            "from_" + "actor_" + "address": {"actor_id": "act-pm-clean", "role_id": "pm"},
            "to_" + "actor_" + "address": {"actor_id": "act-dev-clean", "role_id": "dev"},
            "content": "old",
            "created_at": "2026-05-17T00:00:00+08:00",
        }
        self._write_json("buddyswitch/objects/messages/msg-retired.json", retired_shape)
        self._write_json(
            "buddyswitch/objects/track-comments/track-demo/comment-test.json",
            {
                "id": "comment-test",
                "track_id": "track-demo",
                "thread_id": "comment-test",
                "by_actor": {"actor_id": "act-design-clean", "role_id": "design"},
                "content": "looks good",
                "reply_to": None,
                "mentioned_actors": [],
                "status": "open",
                "created_at": "2026-05-17T00:00:00+08:00",
                "resolved_by_actor": None,
                "resolved_at": None,
                "resolution_summary": None,
            },
        )
        for role in ("pm", "dev"):
            role_plan = env_cleanup.build_cleanup_plan(
                scope="role",
                role=role,
                repo_root=self.repo_root,
                manifest_path=self.manifest_path,
                contributions=self.product_cleanup,
            )
            self.assertEqual(
                {
                    path
                    for path, category in role_plan["path_categories"].items()
                    if category == "message_objects"
                },
                {"im/messages/msg-test.json"},
                msg=role_plan,
            )
            self.assertEqual(role_plan["message_object_ids"], ["msg-test"])
        unrelated_plan = env_cleanup.build_cleanup_plan(
            scope="role",
            role="design",
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            contributions=self.product_cleanup,
        )
        self.assertNotIn(
            "im/messages/msg-test.json",
            unrelated_plan["path_categories"],
            msg=unrelated_plan,
        )
        plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            role=None,
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            contributions=self.product_cleanup,
        )
        self.assertIn("message_object_ids", plan)
        self.assertIn("msg-test", plan["message_object_ids"])
        self.assertNotIn("msg-retired", plan["message_object_ids"])
        self.assertTrue(
            any("retired message object schema" in warning for warning in plan["warnings"]),
            msg=plan["warnings"],
        )
        self.assertIn("comment_object_ids", plan)
        self.assertIn("comment-test", plan["comment_object_ids"])

    def test_message_cleanup_recurses_owned_residue_without_following_leaf_symlinks(self) -> None:
        valid_path = "im/messages/nested/msg-owned.json"
        malformed_path = "im/messages/nested/broken.json"
        non_json_path = "im/messages/orphan.bin"
        leaf_link_path = "im/messages/nested/external-link.json"
        retired_root_path = "buddyswitch/objects/messages"
        retired_non_json_path = f"{retired_root_path}/orphan.bin"
        retired_nested_path = f"{retired_root_path}/nested/broken.json"
        valid_message = {
            "id": "msg-owned",
            "conversation_id": "conv-owned",
            "sender_identity": {"id": "act-pm-clean", "type": "actor"},
            "target_identity": {"id": "act-dev-clean", "type": "actor"},
            "content": "cleanup me",
            "reply_to": None,
            "created_at": "2026-08-03T00:00:00+08:00",
        }
        self._write_json(valid_path, valid_message)
        malformed = self._path(malformed_path)
        malformed.parent.mkdir(parents=True, exist_ok=True)
        malformed.write_text("{", encoding="utf-8")
        non_json = self._path(non_json_path)
        non_json.write_bytes(b"not-json")

        external_target = self.shared_root / "external-message.json"
        external_target.write_text(
            json.dumps(
                {
                    **valid_message,
                    "id": "msg-external-target",
                    "conversation_id": "conv-external-target",
                },
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )
        leaf_link = self._path(leaf_link_path)
        leaf_link.symlink_to(external_target)

        retired_non_json = self._path(retired_non_json_path)
        retired_non_json.parent.mkdir(parents=True, exist_ok=True)
        retired_non_json.write_bytes(b"retired")
        retired_nested = self._path(retired_nested_path)
        retired_nested.parent.mkdir(parents=True, exist_ok=True)
        retired_nested.write_text("{", encoding="utf-8")

        role_plan = env_cleanup.build_cleanup_plan(
            scope="role",
            role="pm",
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            contributions=self.product_cleanup,
        )
        self.assertEqual(
            {
                path
                for path, category in role_plan["path_categories"].items()
                if category == "message_objects"
            },
            {valid_path},
            msg=role_plan,
        )
        self.assertEqual(role_plan["message_object_ids"], ["msg-owned"])
        self.assertEqual(
            role_plan["message_records"],
            [{
                "id": "msg-owned",
                "conversation_id": "conv-owned",
                "sender_identity_id": "act-pm-clean",
                "target_identity_id": "act-dev-clean",
                "from_role": "pm",
                "to_role": "dev",
                "object_path": valid_path,
            }],
        )
        warning_paths = {
            malformed_path,
            non_json_path,
            leaf_link_path,
            retired_root_path,
            retired_non_json_path,
            retired_nested_path,
        }
        for warning_path in warning_paths:
            self.assertTrue(
                any(
                    warning_path in warning
                    and "will be skipped" in warning
                    and "all-data cleanup will delete" in warning
                    for warning in role_plan["warnings"]
                ),
                msg=(warning_path, role_plan["warnings"]),
            )

        role_result = env_cleanup.execute_cleanup_plan(
            role_plan,
            contributions=self.product_cleanup,
        )
        self.assertTrue(role_result["ok"], msg=role_result)
        self.assertEqual(
            {
                path
                for path in role_result["deleted_paths"]
                if role_plan["path_categories"].get(path) == "message_objects"
            },
            {valid_path},
        )
        self.assertFalse(self._path(valid_path).exists())
        self.assertTrue(malformed.exists())
        self.assertTrue(non_json.exists())
        self.assertTrue(leaf_link.is_symlink())
        self.assertTrue(retired_non_json.exists())
        self.assertTrue(retired_nested.exists())
        external_before_all_data = external_target.read_text(encoding="utf-8")

        self._write_json(valid_path, valid_message)
        all_data_plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            role=None,
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            contributions=self.product_cleanup,
        )
        expected_message_paths = {
            valid_path,
            malformed_path,
            non_json_path,
            leaf_link_path,
            retired_root_path,
            retired_non_json_path,
            retired_nested_path,
        }
        self.assertEqual(
            {
                path
                for path, category in all_data_plan["path_categories"].items()
                if category == "message_objects"
            },
            expected_message_paths,
            msg=all_data_plan,
        )
        self.assertEqual(all_data_plan["message_object_ids"], ["msg-owned"])
        self.assertEqual(len(all_data_plan["message_records"]), 1)
        self.assertEqual(
            all_data_plan["counts_by_category"]["message_objects"],
            len(expected_message_paths),
        )

        all_data_result = env_cleanup.execute_cleanup_plan(
            all_data_plan,
            contributions=self.product_cleanup,
        )
        self.assertTrue(all_data_result["ok"], msg=all_data_result)
        self.assertEqual(
            {
                path
                for path in all_data_result["deleted_paths"]
                if all_data_plan["path_categories"].get(path) == "message_objects"
            },
            expected_message_paths,
        )
        self.assertTrue(self._path("im/messages").is_dir())
        self.assertFalse(self._path(retired_root_path).exists())
        for deleted_path in expected_message_paths - {
            "im/messages",
            retired_root_path,
        }:
            self.assertFalse(self._path(deleted_path).is_symlink())
            self.assertFalse(self._path(deleted_path).exists())
        self.assertEqual(
            external_target.read_text(encoding="utf-8"),
            external_before_all_data,
        )

    def test_role_cleanup_deletes_authored_comments_without_mutating_surviving_targets(self) -> None:
        track_path = self._path("buddyswitch/objects/tracks/track-clean-comment.json")
        track_payload = {
            "id": "track-clean-comment",
            "title": "Clean Comment",
            "outcome": "clean comment",
            "owner_role": "pm",
            "state": "active",
            "health": "ok",
            "appetite": "1 day",
            "now": {"next": "clean", "blocker": None},
            "shared_materials": [],
            "updates": [],
            "close_proof": [],
            "created_at": "2026-05-17T00:00:00+08:00",
            "updated_at": "2026-05-17T00:00:00+08:00",
            "archived_at": None,
        }
        self._write_json("buddyswitch/objects/tracks/track-clean-comment.json", track_payload)
        self._write_json(
            "buddyswitch/objects/track-comments/track-clean-comment/comment-dev-clean.json",
            {
                "id": "comment-dev-clean",
                "track_id": "track-clean-comment",
                "thread_id": "comment-dev-clean",
                "by_actor": {"actor_id": "act-dev-clean", "role_id": "dev"},
                "content": "delete me",
                "reply_to": None,
                "mentioned_actors": [],
                "status": "open",
                "created_at": "2026-05-17T00:00:00+08:00",
                "resolved_by_actor": None,
                "resolved_at": None,
                "resolution_summary": None,
            },
        )
        self._write_json(
            "buddyswitch/objects/track-comments/track-clean-comment/comment-design-keep.json",
            {
                "id": "comment-design-keep",
                "track_id": "track-clean-comment",
                "thread_id": "comment-design-keep",
                "by_actor": {"actor_id": "act-design-clean", "role_id": "design"},
                "content": "keep me",
                "reply_to": None,
                "mentioned_actors": [],
                "status": "open",
                "created_at": "2026-05-17T00:00:01+08:00",
                "resolved_by_actor": None,
                "resolved_at": None,
                "resolution_summary": None,
            },
        )

        plan = env_cleanup.build_cleanup_plan(
            scope="role",
            role="dev",
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            contributions=self.product_cleanup,
        )
        result = env_cleanup.execute_cleanup_plan(
            plan,
            contributions=self.product_cleanup,
        )

        self.assertTrue(result["ok"], msg=result)
        self.assertFalse(self._path("buddyswitch/objects/track-comments/track-clean-comment/comment-dev-clean.json").exists())
        self.assertTrue(self._path("buddyswitch/objects/track-comments/track-clean-comment/comment-design-keep.json").exists())
        self.assertEqual(json.loads(track_path.read_text(encoding="utf-8")), track_payload)

    def test_role_cleanup_uses_instance_actor_private_owner_boundary(self) -> None:
        pm_workspace = self._instance_workspace(actor_id="act-pm-cleanup", role="pm")
        dev_workspace = self._instance_workspace(actor_id="act-dev-cleanup", role="dev")

        pm_owned = pm_workspace / "private" / "notes" / "draft.md"
        pm_owned.parent.mkdir(parents=True, exist_ok=True)
        pm_owned.write_text("pm-owned", encoding="utf-8")

        dev_owned = dev_workspace / "private" / "notes" / "keep.md"
        dev_owned.parent.mkdir(parents=True, exist_ok=True)
        dev_owned.write_text("dev-owned", encoding="utf-8")

        plan = env_cleanup.build_cleanup_plan(
            scope="role",
            role="pm",
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            shared_root=self.shared_root,
            contributions=self.product_cleanup,
        )
        self.assertIn("path_categories", plan)
        self.assertTrue(
            any(
                category == "actor_private_files"
                for category in plan["path_categories"].values()
            ),
            msg=plan,
        )
        result = env_cleanup.execute_cleanup_plan(
            plan,
            contributions=self.product_cleanup,
        )
        self.assertTrue(result["ok"], msg=result)
        self.assertFalse(pm_owned.exists())
        self.assertTrue(dev_owned.exists())

        all_data_plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            role=None,
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            shared_root=self.shared_root,
            contributions=self.product_cleanup,
        )
        all_data_result = env_cleanup.execute_cleanup_plan(
            all_data_plan,
            contributions=self.product_cleanup,
        )
        self.assertTrue(all_data_result["ok"], msg=all_data_result)
        self.assertFalse(dev_owned.exists())

    def test_cleanup_executor_revalidates_relative_parent_and_filters_index(self) -> None:
        relative_path = "buddyswitch/objects/stale-parent/record.json"
        selected = self._path(relative_path)
        selected.parent.mkdir(parents=True, exist_ok=True)
        selected.write_text("planned", encoding="utf-8")
        contribution = env_cleanup.CleanupContribution(
            category="indexed_stale",
            discover=lambda _root: (
                env_cleanup.OwnedStatePath(
                    relative_path=relative_path,
                    owner_roles=("pm",),
                    index_record={
                        "id": "art-stale-execution",
                        "producer_role": "pm",
                        "object_path": relative_path,
                    },
                ),
            ),
            index_projection=env_cleanup.CleanupIndexProjection(
                object_ids_field="artifact_object_ids",
                records_field="artifact_records",
            ),
        )
        plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            role=None,
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            contributions=(contribution,),
        )
        self.assertEqual(plan["artifact_object_ids"], ["art-stale-execution"])

        original_parent = selected.parent.with_name("stale-parent-original")
        selected.parent.rename(original_parent)
        outside_parent = self.shared_root / "outside-relative-parent"
        outside_parent.mkdir()
        outside_target = outside_parent / selected.name
        outside_target.write_text("outside-relative", encoding="utf-8")
        selected.parent.symlink_to(outside_parent, target_is_directory=True)

        result = env_cleanup.execute_cleanup_plan(plan, contributions=(contribution,))

        self.assertEqual(outside_target.read_text(encoding="utf-8"), "outside-relative")
        self.assertNotIn(relative_path, result["deleted_paths"])
        self.assertEqual(result["deleted_count"], 0)
        self.assertEqual(result["artifact_object_ids"], [])
        self.assertTrue(
            any(
                relative_path in warning
                and "execution" in warning.lower()
                and "symlink" in warning.lower()
                for warning in result["warnings"]
            ),
            msg=result,
        )

    def test_cleanup_executor_revalidates_state_root_before_effects(self) -> None:
        relative_path = "owned/record.json"
        selected = self._path(relative_path)
        selected.parent.mkdir(parents=True, exist_ok=True)
        selected.write_text("planned", encoding="utf-8")
        contribution = env_cleanup.CleanupContribution(
            category="state_root_swap",
            discover=lambda _root: (
                env_cleanup.OwnedStatePath(
                    relative_path=relative_path,
                    owner_roles=("pm",),
                ),
            ),
            required_directories=("required/current",),
        )
        plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            role=None,
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            contributions=(contribution,),
        )

        original_state = self.shared_root / "state-original"
        self.repo_root.rename(original_state)
        outside_state = self.shared_root / "outside-state"
        outside_target = outside_state / relative_path
        outside_target.parent.mkdir(parents=True, exist_ok=True)
        outside_target.write_text("outside-state", encoding="utf-8")
        self.repo_root.symlink_to(outside_state, target_is_directory=True)

        raised: ValueError | None = None
        try:
            env_cleanup.execute_cleanup_plan(plan, contributions=(contribution,))
        except ValueError as exc:
            raised = exc

        self.assertTrue(outside_target.exists(), msg="executor followed the replaced state root")
        self.assertEqual(outside_target.read_text(encoding="utf-8"), "outside-state")
        self.assertFalse((outside_state / "required" / "current").exists())
        self.assertIsNotNone(raised)
        self.assertIn("root", str(raised).lower())
        self.assertIn("symlink", str(raised).lower())

    def test_cleanup_executor_revalidates_actor_private_parent_without_fallback(self) -> None:
        workspace = self._instance_workspace(actor_id="act-pm-execution", role="pm")
        selected = workspace / "private" / "notes" / "draft.md"
        selected.parent.mkdir(parents=True, exist_ok=True)
        selected.write_text("planned-private", encoding="utf-8")
        plan = env_cleanup.build_cleanup_plan(
            scope="role",
            role="pm",
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            shared_root=self.shared_root,
            contributions=(),
        )
        display_path = selected.relative_to(self.shared_root).as_posix()
        self.assertIn(display_path, plan["direct_delete_paths"])

        original_parent = selected.parent.with_name("notes-original")
        selected.parent.rename(original_parent)
        outside_parent = self.shared_root / "outside-private-parent"
        outside_parent.mkdir()
        outside_target = outside_parent / selected.name
        outside_target.write_text("outside-private", encoding="utf-8")
        selected.parent.symlink_to(outside_parent, target_is_directory=True)

        result = env_cleanup.execute_cleanup_plan(plan, contributions=())

        self.assertEqual(outside_target.read_text(encoding="utf-8"), "outside-private")
        self.assertEqual(
            (original_parent / selected.name).read_text(encoding="utf-8"),
            "planned-private",
        )
        self.assertNotIn(display_path, result["deleted_paths"])
        self.assertEqual(result["deleted_count"], 0)
        self.assertTrue(
            any(
                display_path in warning
                and "execution" in warning.lower()
                and "symlink" in warning.lower()
                for warning in result["warnings"]
            ),
            msg=result,
        )

    def test_cleanup_executor_revalidates_shared_root_before_effects(self) -> None:
        declared_shared = self.shared_root / "declared-shared"
        instance_root = declared_shared / "instances" / "act-pm-shared"
        workspace = instance_root / "workspace"
        selected = workspace / "private" / "notes" / "draft.md"
        selected.parent.mkdir(parents=True, exist_ok=True)
        selected.write_text("planned-shared", encoding="utf-8")
        (instance_root / "instance.json").write_text(
            json.dumps({"actor_id": "act-pm-shared", "role": "pm"}),
            encoding="utf-8",
        )
        plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            role=None,
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            shared_root=declared_shared,
            contributions=(),
        )
        display_path = selected.relative_to(declared_shared).as_posix()
        self.assertIn(display_path, plan["direct_delete_paths"])

        original_shared = self.shared_root / "declared-shared-original"
        declared_shared.rename(original_shared)
        outside_shared = self.shared_root / "outside-shared"
        outside_target = outside_shared / display_path
        outside_target.parent.mkdir(parents=True, exist_ok=True)
        outside_target.write_text("outside-shared", encoding="utf-8")
        declared_shared.symlink_to(outside_shared, target_is_directory=True)

        raised: ValueError | None = None
        try:
            env_cleanup.execute_cleanup_plan(plan, contributions=())
        except ValueError as exc:
            raised = exc

        self.assertTrue(outside_target.exists(), msg="executor followed the replaced shared root")
        self.assertEqual(outside_target.read_text(encoding="utf-8"), "outside-shared")
        self.assertEqual(
            (original_shared / display_path).read_text(encoding="utf-8"),
            "planned-shared",
        )
        self.assertIsNotNone(raised)
        self.assertIn("shared root", str(raised).lower())
        self.assertIn("symlink", str(raised).lower())

    def test_cleanup_executor_omits_missing_path_and_index_after_plan(self) -> None:
        relative_path = "buddyswitch/objects/stale-missing/record.json"
        selected = self._path(relative_path)
        selected.parent.mkdir(parents=True, exist_ok=True)
        selected.write_text("planned", encoding="utf-8")
        contribution = env_cleanup.CleanupContribution(
            category="indexed_missing",
            discover=lambda _root: (
                env_cleanup.OwnedStatePath(
                    relative_path=relative_path,
                    owner_roles=("pm",),
                    index_record={
                        "id": "art-missing-execution",
                        "producer_role": "pm",
                        "object_path": relative_path,
                    },
                ),
            ),
            index_projection=env_cleanup.CleanupIndexProjection(
                object_ids_field="artifact_object_ids",
                records_field="artifact_records",
            ),
        )
        plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            role=None,
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            contributions=(contribution,),
        )
        self.assertEqual(plan["artifact_object_ids"], ["art-missing-execution"])
        selected.unlink()

        result = env_cleanup.execute_cleanup_plan(plan, contributions=(contribution,))

        self.assertNotIn(relative_path, result["deleted_paths"])
        self.assertEqual(result["deleted_count"], 0)
        self.assertEqual(result["artifact_object_ids"], [])
        self.assertTrue(
            any(
                relative_path in warning
                and "execution" in warning.lower()
                and "missing" in warning.lower()
                for warning in result["warnings"]
            ),
            msg=result,
        )

    def test_cleanup_projection_fields_are_derived_from_selected_contributions(self) -> None:
        relative_path = "buddyswitch/objects/probe/record.json"
        selected = self._path(relative_path)
        selected.parent.mkdir(parents=True, exist_ok=True)
        selected.write_text("probe", encoding="utf-8")
        contribution = env_cleanup.CleanupContribution(
            category="probe_objects",
            discover=lambda _root: (
                env_cleanup.OwnedStatePath(
                    relative_path=relative_path,
                    owner_roles=("pm",),
                    index_record={
                        "id": "probe-1",
                        "object_path": relative_path,
                    },
                ),
            ),
            index_projection=env_cleanup.CleanupIndexProjection(
                object_ids_field="probe_object_ids",
                records_field="probe_records",
            ),
        )

        plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            role=None,
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            contributions=(contribution,),
        )

        self.assertEqual(plan["probe_object_ids"], ["probe-1"])
        self.assertEqual(plan["probe_records"][0]["object_path"], relative_path)
        for unselected_field in (
            "artifact_object_ids",
            "artifact_records",
            "message_object_ids",
            "message_records",
            "comment_object_ids",
            "comment_records",
        ):
            self.assertNotIn(unselected_field, plan)

        result = env_cleanup.execute_cleanup_plan(
            plan,
            contributions=(contribution,),
        )

        self.assertTrue(result["ok"], msg=result)
        self.assertEqual(result["probe_object_ids"], ["probe-1"])
        self.assertNotIn("artifact_object_ids", result)
        self.assertNotIn("message_object_ids", result)
        self.assertNotIn("comment_object_ids", result)
        self.assertFalse(selected.exists())

    def test_cleanup_executor_deletes_nested_paths_deepest_first(self) -> None:
        parent_path = "buddyswitch/objects/messages-retired"
        child_path = f"{parent_path}/nested/child.json"
        child = self._path(child_path)
        child.parent.mkdir(parents=True, exist_ok=True)
        child.write_text("nested", encoding="utf-8")
        contribution = env_cleanup.CleanupContribution(
            category="nested_cleanup",
            discover=lambda _root: (
                env_cleanup.OwnedStatePath(relative_path=parent_path),
                env_cleanup.OwnedStatePath(relative_path=child_path),
            ),
        )
        plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            role=None,
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            contributions=(contribution,),
        )
        observed_effect_targets: list[tuple[str, bool]] = []
        delete_relative_path = env_cleanup.delete_relative_path

        def observe_delete(root: Path, relative_path: str) -> bool:
            target = root / relative_path
            observed_effect_targets.append(
                (relative_path, target.exists() or target.is_symlink())
            )
            return bool(delete_relative_path(root, relative_path))

        with mock.patch.object(
            env_cleanup,
            "delete_relative_path",
            side_effect=observe_delete,
        ):
            result = env_cleanup.execute_cleanup_plan(plan, contributions=(contribution,))

        self.assertEqual(
            observed_effect_targets,
            [(child_path, True), (parent_path, True)],
        )
        self.assertEqual(result["deleted_paths"], [child_path, parent_path])
        self.assertEqual(result["deleted_count"], 2)
        self.assertFalse(self._path(parent_path).exists())

    def test_cleanup_executor_unlinks_stable_relative_and_actor_private_leaf_links(self) -> None:
        relative_target = self.shared_root / "relative-leaf-target.txt"
        relative_target.write_bytes(b"relative-target")
        relative_path = "buddyswitch/objects/stable-link.json"
        relative_link = self._path(relative_path)
        relative_link.parent.mkdir(parents=True, exist_ok=True)
        relative_link.symlink_to(relative_target)

        workspace = self._instance_workspace(actor_id="act-pm-leaf", role="pm")
        private_target = self.shared_root / "private-leaf-target.txt"
        private_target.write_bytes(b"private-target")
        private_link = workspace / "private" / "notes" / "stable-link.txt"
        private_link.parent.mkdir(parents=True, exist_ok=True)
        private_link.symlink_to(private_target)
        private_display_path = private_link.relative_to(self.shared_root).as_posix()

        contribution = env_cleanup.CleanupContribution(
            category="stable_leaf_links",
            discover=lambda _root: (
                env_cleanup.OwnedStatePath(relative_path=relative_path),
            ),
        )
        plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            role=None,
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            shared_root=self.shared_root,
            contributions=(contribution,),
        )
        result = env_cleanup.execute_cleanup_plan(plan, contributions=(contribution,))

        self.assertFalse(relative_link.is_symlink())
        self.assertFalse(private_link.is_symlink())
        self.assertEqual(relative_target.read_bytes(), b"relative-target")
        self.assertEqual(private_target.read_bytes(), b"private-target")
        self.assertEqual(
            set(result["deleted_paths"]),
            {relative_path, private_display_path},
        )
        self.assertEqual(result["deleted_count"], 2)

    def test_demand_cleanup_contribution_attributes_role_and_all_data_paths(self) -> None:
        module_path = ROOT / "src" / "buddyswitch" / "modules" / "demand" / "module.py"
        self.assertTrue(module_path.is_file(), msg=module_path)

        from buddyswitch.modules.demand.module import DEMAND

        demand_root = self._path("buddyswitch/objects/demand-sys/actors")
        pm_path = demand_root / "act-pm-clean-pm.json"
        dev_path = demand_root / "act-dev-clean-dev.json"
        malformed_path = demand_root / "malformed.json"
        invalid_utf8_path = demand_root / "invalid-utf8.json"
        self._write_json(
            "buddyswitch/objects/demand-sys/actors/act-pm-clean-pm.json",
            {
                "schema_version": 5,
                "actor_target": {"actor_id": "act-pm-clean", "role_id": "pm"},
                "demands": {},
                "demand_pool_revision": 0,
                "ingress_receipts": {},
            },
        )
        self._write_json(
            "buddyswitch/objects/demand-sys/actors/act-dev-clean-dev.json",
            {
                "schema_version": 5,
                "actor_target": {"actor_id": "act-dev-clean", "role_id": "dev"},
                "demands": {},
                "demand_pool_revision": 0,
                "ingress_receipts": {},
            },
        )
        malformed_path.parent.mkdir(parents=True, exist_ok=True)
        malformed_path.write_text("{", encoding="utf-8")
        invalid_utf8_path.write_bytes(b"\xff")

        role_plan = env_cleanup.build_cleanup_plan(
            scope="role",
            role="pm",
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            contributions=DEMAND.cleanup,
        )
        self.assertEqual(
            {
                path
                for path, category in role_plan["path_categories"].items()
                if category == "demand_aggregates"
            },
            {"buddyswitch/objects/demand-sys/actors/act-pm-clean-pm.json"},
        )
        self.assertTrue(
            any("cannot be safely attributed" in warning for warning in role_plan["warnings"]),
            msg=role_plan,
        )
        role_result = env_cleanup.execute_cleanup_plan(
            role_plan,
            contributions=self.product_cleanup,
        )
        self.assertTrue(role_result["ok"], msg=role_result)
        self.assertFalse(pm_path.exists())
        self.assertTrue(dev_path.exists())
        self.assertTrue(malformed_path.exists())
        self.assertTrue(invalid_utf8_path.exists())

        all_data_plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            role=None,
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            contributions=DEMAND.cleanup,
        )
        self.assertEqual(
            {
                path
                for path, category in all_data_plan["path_categories"].items()
                if category == "demand_aggregates"
            },
            {
                "buddyswitch/objects/demand-sys/actors/act-dev-clean-dev.json",
                "buddyswitch/objects/demand-sys/actors/invalid-utf8.json",
                "buddyswitch/objects/demand-sys/actors/malformed.json",
            },
        )
        all_data_result = env_cleanup.execute_cleanup_plan(
            all_data_plan,
            contributions=self.product_cleanup,
        )
        self.assertTrue(all_data_result["ok"], msg=all_data_result)
        self.assertFalse(dev_path.exists())
        self.assertFalse(invalid_utf8_path.exists())
        self.assertFalse(malformed_path.exists())

    def test_task_cleanup_contribution_attributes_role_and_guards_unknown_records(self) -> None:
        module_path = ROOT / "src" / "buddyswitch" / "modules" / "task" / "module.py"
        self.assertTrue(module_path.is_file(), msg=module_path)

        from buddyswitch.application.composition import TASK

        pm_path = self._path("buddyswitch/objects/task-sys/tasks/task-demand-pm.json")
        dev_path = self._path("buddyswitch/objects/task-sys/tasks/task-demand-dev.json")
        malformed_path = self._path("buddyswitch/objects/task-sys/tasks/malformed.json")
        self._write_json(
            "buddyswitch/objects/task-sys/tasks/task-demand-pm.json",
            {
                "schema_version": 1,
                "id": "task-demand-pm",
                "actor_target": {"actor_id": "act-pm-clean", "role_id": "pm"},
            },
        )
        self._write_json(
            "buddyswitch/objects/task-sys/tasks/task-demand-dev.json",
            {
                "schema_version": 1,
                "id": "task-demand-dev",
                "actor_target": {"actor_id": "act-dev-clean", "role_id": "dev"},
            },
        )
        malformed_path.parent.mkdir(parents=True, exist_ok=True)
        malformed_path.write_text("{", encoding="utf-8")

        role_plan = env_cleanup.build_cleanup_plan(
            scope="role",
            role="pm",
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            contributions=TASK.cleanup,
        )
        self.assertEqual(
            {
                path
                for path, category in role_plan["path_categories"].items()
                if category == "task_records"
            },
            {"buddyswitch/objects/task-sys/tasks/task-demand-pm.json"},
        )
        self.assertTrue(
            any("cannot be safely attributed" in warning for warning in role_plan["warnings"]),
            msg=role_plan,
        )
        role_result = env_cleanup.execute_cleanup_plan(
            role_plan,
            contributions=self.product_cleanup,
        )
        self.assertTrue(role_result["ok"], msg=role_result)
        self.assertFalse(pm_path.exists())
        self.assertTrue(dev_path.exists())
        self.assertTrue(malformed_path.exists())

        all_data_plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            role=None,
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            contributions=TASK.cleanup,
        )
        self.assertEqual(
            {
                path
                for path, category in all_data_plan["path_categories"].items()
                if category == "task_records"
            },
            {
                "buddyswitch/objects/task-sys/tasks/task-demand-dev.json",
                "buddyswitch/objects/task-sys/tasks/malformed.json",
            },
        )
        all_data_result = env_cleanup.execute_cleanup_plan(
            all_data_plan,
            contributions=self.product_cleanup,
        )
        self.assertTrue(all_data_result["ok"], msg=all_data_result)
        self.assertFalse(dev_path.exists())
        self.assertFalse(malformed_path.exists())

    def test_cleanup_host_unlinks_leaf_symlink_but_rejects_escaping_and_symlinked_parents(self) -> None:
        self.assertTrue(
            (ROOT / "src" / "buddyswitch" / "runtime_support" / "env_cleanup.py").is_file()
        )
        self.assertTrue(hasattr(env_cleanup, "CleanupContribution"))
        self.assertTrue(hasattr(env_cleanup, "OwnedStatePath"))
        from buddyswitch.runtime_support.env_cleanup import (
            CleanupContribution,
            OwnedStatePath,
        )

        outside = self.shared_root / "outside.json"
        outside.write_text("outside", encoding="utf-8")
        symlink = self._path("buddyswitch/objects/demand-sys/actors/escape.json")
        symlink.parent.mkdir(parents=True, exist_ok=True)
        symlink.symlink_to(outside)
        outside_directory = self.shared_root / "outside-directory"
        outside_directory.mkdir()
        outside_child = outside_directory / "child.json"
        outside_child.write_text("outside-child", encoding="utf-8")
        symlinked_parent = self._path("buddyswitch/objects/demand-sys/linked-parent")
        symlinked_parent.symlink_to(outside_directory, target_is_directory=True)

        contribution = CleanupContribution(
            category="unsafe",
            discover=lambda _root: (
                OwnedStatePath(relative_path="../outside.json", owner_roles=("pm",)),
                OwnedStatePath(relative_path=str(outside), owner_roles=("pm",)),
                OwnedStatePath(
                    relative_path="buddyswitch/objects/demand-sys/actors/escape.json",
                    owner_roles=("pm",),
                ),
                OwnedStatePath(
                    relative_path="buddyswitch/objects/demand-sys/linked-parent/child.json",
                    owner_roles=("pm",),
                ),
            ),
        )
        plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            role=None,
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            contributions=(contribution,),
        )
        self.assertEqual(
            {
                path
                for path, category in plan["path_categories"].items()
                if category == "unsafe"
            },
            {"buddyswitch/objects/demand-sys/actors/escape.json"},
            msg=plan,
        )
        self.assertGreaterEqual(
            sum("Skipping unsafe cleanup path" in warning for warning in plan["warnings"]),
            3,
            msg=plan,
        )
        result = env_cleanup.execute_cleanup_plan(
            plan,
            contributions=self.product_cleanup,
        )
        self.assertTrue(result["ok"], msg=result)
        self.assertEqual(outside.read_text(encoding="utf-8"), "outside")
        self.assertFalse(symlink.is_symlink())
        self.assertTrue(symlinked_parent.is_symlink())
        self.assertEqual(outside_child.read_text(encoding="utf-8"), "outside-child")
