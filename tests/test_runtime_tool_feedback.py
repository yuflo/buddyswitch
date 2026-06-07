#!/usr/bin/env python3
"""Runless structured feedback tests for env.tool rejections and recoveries."""

from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402
import env_legacy_store as env_store  # noqa: E402
from env.tool_runtime import registry as tool_router  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


class RuntimeToolFeedbackTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    _ACTION_PLACEHOLDERS = {
        "tbd",
        "todo",
        "n/a",
        "na",
        "none",
        "unknown",
        "placeholder",
    }

    @staticmethod
    def _meaningful_text_entries(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        rows: list[str] = []
        for entry in value:
            if not isinstance(entry, str):
                continue
            normalized = entry.strip()
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered in RuntimeToolFeedbackTests._ACTION_PLACEHOLDERS:
                continue
            rows.append(normalized)
        return rows

    @staticmethod
    def _meaningful_tool_action_options(value: object) -> list[dict[str, str]]:
        if not isinstance(value, list):
            return []
        rows: list[dict[str, str]] = []
        for entry in value:
            if not isinstance(entry, dict):
                continue
            tool = entry.get("tool")
            action = entry.get("action")
            if isinstance(tool, str) and tool.strip() and isinstance(action, str) and action.strip():
                rows.append({"tool": tool.strip(), "action": action.strip()})
        return rows

    def setUp(self) -> None:
        super().setUp()
        self.manifest_path = ROOT / "buddyswitch" / "manifest.toml"
        self.manifest = env_manifest.load_manifest(self.manifest_path)
        self.instance_json = self._runtime_path("instance.json")
        self.actor_id = self._runtime_actor_id(role="pm", label="act-feedback-runless")
        self.instance_payload = {
            "actor_id": self.actor_id,
            "role": "pm",
            "status": "active",
            "workspace_dir": str(self.runtime_root),
            "browser_port": 9444,
        }
        self.instance_json.write_text(json.dumps(self.instance_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def _ensure_active_task(self, *, role: str, actor_id: str) -> None:
        taskbox = self.instance_json.parent / "taskbox" / role
        tasks_dir = taskbox / "tasks"
        tasks_dir.mkdir(parents=True, exist_ok=True)
        task_id = f"task-0001-{role}-feedback"
        (tasks_dir / f"{task_id}.json").write_text(
            json.dumps(
                {
                    "id": task_id,
                    "owner_actor": {"actor_id": actor_id, "role_id": role},
                    "title": "Feedback contract active task",
                    "summary": "Active task for handler-level feedback contract tests.",
                    "body": "Active task for handler-level feedback contract tests.",
                    "status": "active",
                    "priority": "normal",
                    "origin": {"type": "manual"},
                    "track_id": None,
                    "refs": [],
                    "progress_summary": "Active task for handler-level feedback contract tests.",
                    "created_at": "2026-06-07T10:00:00+08:00",
                    "updated_at": "2026-06-07T10:00:00+08:00",
                    "closed_at": None,
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (taskbox / "history.md").write_text(
            f"- 2026-06-07T10:00:00+08:00 task.selected {task_id} reason=\"seed feedback active task\"\n",
            encoding="utf-8",
        )

    def _dispatch(self, *, role: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        actor_id = self._runtime_actor_id(role=role, label="act-feedback-runless")
        self._ensure_active_task(role=role, actor_id=actor_id)
        return tool_router.dispatch_env_tool_request(
            payload={"tool": tool, "action": action, "args": args},
            active_role=role,
            actor_id=actor_id,
            instance_json=self.instance_json,
            instance_payload={**self.instance_payload, "actor_id": actor_id, "role": role},
            manifest=self.manifest,
            manifest_path=self.manifest_path,
        )

    def _assert_rejection_contract(self, payload: dict[str, object]) -> None:
        self.assertFalse(payload["ok"])
        self.assertIn("permission_boundary", payload)
        self.assertIn("why_blocked", payload)
        self.assertIn("impact", payload)
        self.assertIn("retryable", payload)
        self.assertIn("retry_guidance", payload)
        self.assertTrue(str(payload.get("permission_boundary", "")).strip(), msg=payload)
        self.assertTrue(str(payload.get("why_blocked", "")).strip(), msg=payload)
        self.assertTrue(str(payload.get("impact", "")).strip(), msg=payload)
        self.assertTrue(str(payload.get("retry_guidance", "")).strip(), msg=payload)
        self.assertIn("allowed_next_actions", payload, msg=payload)
        self.assertIsInstance(payload.get("allowed_next_actions"), list, msg=payload)
        if "allowed_next_action_options" in payload:
            self.assertIsInstance(payload.get("allowed_next_action_options"), list, msg=payload)
        next_actions = self._meaningful_text_entries(payload.get("allowed_next_actions"))
        next_options = self._meaningful_tool_action_options(payload.get("allowed_next_action_options"))
        self.assertTrue(
            bool(next_actions) or bool(next_options),
            msg=payload,
        )
        self.assertFalse(payload.get("state_changed"), msg=payload)
        self.assertEqual(payload.get("durability"), "none", msg=payload)

    def _assert_write_success_contract(self, payload: dict[str, object]) -> None:
        self.assertTrue(payload.get("ok"), msg=payload)
        self.assertTrue(payload.get("state_changed"), msg=payload)
        self.assertIsInstance(payload.get("durability"), str, msg=payload)
        self.assertNotEqual(payload.get("durability"), "none", msg=payload)
        self.assertIsInstance(payload.get("state_changes"), list, msg=payload)
        self.assertGreater(len(payload.get("state_changes", [])), 0, msg=payload)
        has_next_actions = isinstance(payload.get("allowed_next_actions"), list) and len(payload["allowed_next_actions"]) > 0
        has_next_options = isinstance(payload.get("allowed_next_action_options"), list) and len(payload["allowed_next_action_options"]) > 0
        self.assertTrue(has_next_actions or has_next_options, msg=payload)

    def test_actor_private_tool_rejection_has_structured_feedback(self) -> None:
        payload = self._dispatch(
            role="pm",
            tool="actor_private",
            action="write",
            args={"logical_name": "../escape.txt", "content": "x"},
        )
        self.assertFalse(payload.get("ok"), msg=payload)
        self.assertEqual(payload.get("permission_boundary"), "env.tool")
        self.assertTrue(str(payload.get("why_blocked", "")).strip(), msg=payload)
        self.assertTrue(str(payload.get("impact", "")).strip(), msg=payload)
        self.assertTrue(str(payload.get("retry_guidance", "")).strip(), msg=payload)
        self.assertIs(payload.get("state_changed"), False, msg=payload)
        self.assertEqual(payload.get("durability"), "none", msg=payload)
        self.assertIsInstance(payload.get("allowed_next_actions"), list, msg=payload)
        self.assertEqual(payload["permission_boundary"], "env.tool")
        self.assertFalse(payload["state_changed"])

    def test_artifact_owner_scope_rejection_has_structured_feedback(self) -> None:
        env_store.create_artifact_revision(
            artifact_id="art-pm-owner-scope-r1",
            title="Owner scope",
            summary="pm private",
            body="private",
            template="note",
            supersedes_artifact_id=None,
            created_by="pm",
            authors=["pm"],
            source_refs=[{"type": "note", "label": "seed"}],
        )
        payload = self._dispatch(
            role="design",
            tool="artifact",
            action="update_metadata",
            args={"artifact_id": "art-pm-owner-scope-r1", "summary": "rewrite"},
        )
        self._assert_rejection_contract(payload)
        self.assertEqual(payload["permission_boundary"], "artifact.actor_scope")

    def test_artifact_direct_publish_rejection_has_structured_feedback(self) -> None:
        track = self._dispatch(
            role="pm",
            tool="track",
            action="create",
            args={
                "track_id": "track-feedback-direct-publish",
                "title": "direct publish",
                "outcome": "reject",
                "appetite": "1 day",
                "now": {"next": "seed", "blocker": None},
            },
        )
        self.assertTrue(track["ok"], msg=track)

        rejected = self._dispatch(
            role="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-feedback-direct-r1",
                "title": "reject direct publish",
                "summary": "reject",
                "template": "brief",
                "body": "reject",
                "published_to_track": "track-feedback-direct-publish",
            },
        )
        self._assert_rejection_contract(rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_ARTIFACT_PUBLICATION_PATH")
        self.assertEqual(rejected.get("permission_boundary"), "artifact.publication_path")
        self.assertIn("published_to_track", rejected.get("correctable_fields", []))

    def test_evidence_target_rejection_has_structured_feedback(self) -> None:
        payload = self._dispatch(
            role="market",
            tool="evidence",
            action="issue_browser",
            args={"target_type": "artifact"},
        )
        self._assert_rejection_contract(payload)
        self.assertEqual(payload["permission_boundary"], "request-payload")

    def test_search_request_requires_explicit_backend(self) -> None:
        payload = self._dispatch(
            role="market",
            tool="search",
            action="request",
            args={"query": "onboarding competitors"},
        )
        self._assert_rejection_contract(payload)
        self.assertEqual(payload["permission_boundary"], "request-payload")
        self.assertIn("backend", payload["why_blocked"].lower())

    def test_publish_rejections_have_actionable_feedback_and_no_state_change(self) -> None:
        track_a = self._dispatch(
            role="pm",
            tool="track",
            action="create",
            args={
                "track_id": "track-feedback-a",
                "title": "a",
                "outcome": "a",
                "appetite": "1 day",
                "now": {"next": "seed", "blocker": None},
            },
        )
        track_b = self._dispatch(
            role="pm",
            tool="track",
            action="create",
            args={
                "track_id": "track-feedback-b",
                "title": "b",
                "outcome": "b",
                "appetite": "1 day",
                "now": {"next": "seed", "blocker": None},
            },
        )
        self.assertTrue(track_a["ok"], msg=track_a)
        self.assertTrue(track_b["ok"], msg=track_b)

        draft = self._dispatch(
            role="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-feedback-r1",
                "title": "brief",
                "summary": "brief",
                "template": "brief",
                "body": "brief",
            },
        )
        self.assertTrue(draft["ok"], msg=draft)
        published = self._dispatch(
            role="pm",
            tool="track",
            action="add_material",
            args={"track_id": "track-feedback-a", "artifact_id": "art-feedback-r1", "label": "Brief", "summary": "a"},
        )
        self.assertTrue(published["ok"], msg=published)

        before_track_a = deepcopy(env_store.get_track("track-feedback-a"))
        before_track_b = deepcopy(env_store.get_track("track-feedback-b"))
        before_artifact = deepcopy(env_store.get_artifact("art-feedback-r1"))

        duplicate = self._dispatch(
            role="pm",
            tool="track",
            action="add_material",
            args={"track_id": "track-feedback-a", "artifact_id": "art-feedback-r1", "label": "Brief", "summary": "dup"},
        )
        self._assert_rejection_contract(duplicate)
        self.assertIn("artifact_id", duplicate.get("correctable_fields", []))

        cross_track = self._dispatch(
            role="pm",
            tool="track",
            action="add_material",
            args={"track_id": "track-feedback-b", "artifact_id": "art-feedback-r1", "label": "Brief", "summary": "cross"},
        )
        self._assert_rejection_contract(cross_track)
        self.assertIn("track_id", cross_track.get("correctable_fields", []))

        wrong_owner = self._dispatch(
            role="design",
            tool="track",
            action="add_material",
            args={"track_id": "track-feedback-a", "artifact_id": "art-feedback-r1", "label": "Brief", "summary": "owner"},
        )
        self._assert_rejection_contract(wrong_owner)
        self.assertEqual((wrong_owner.get("error") or {}).get("code"), "E_TRACK_ARTIFACT_SCOPE")

        self.assertEqual(env_store.get_track("track-feedback-a"), before_track_a)
        self.assertEqual(env_store.get_track("track-feedback-b"), before_track_b)
        self.assertEqual(env_store.get_artifact("art-feedback-r1"), before_artifact)

    def test_write_actions_report_state_change_durability_state_changes_and_next_steps(self) -> None:
        track = self._dispatch(
            role="pm",
            tool="track",
            action="create",
            args={
                "track_id": "track-feedback-write-contract",
                "title": "write contract",
                "outcome": "verify write response fields",
                "appetite": "1 day",
                "now": {"next": "seed", "blocker": None},
            },
        )
        self._assert_write_success_contract(track)

        artifact = self._dispatch(
            role="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-feedback-write-contract-r1",
                "title": "write contract",
                "summary": "verify",
                "template": "brief",
                "body": "verify",
            },
        )
        self._assert_write_success_contract(artifact)

        publish = self._dispatch(
            role="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-feedback-write-contract",
                "artifact_id": "art-feedback-write-contract-r1",
                "label": "brief",
                "summary": "publish",
            },
        )
        self._assert_write_success_contract(publish)

    def test_rejections_expose_impact_retry_and_recovery_fields_across_boundaries(self) -> None:
        payload_cases = [
            self._dispatch(
                role="pm",
                tool="task",
                action="create",
                args={"summary": "missing title"},
            ),
            self._dispatch(
                role="design",
                tool="track",
                action="create",
                args={"track_id": "x", "title": "x"},
            ),
            self._dispatch(
                role="pm",
                tool="context",
                action="get",
                args={"unknown_filter": 1},
            ),
            self._dispatch(
                role="pm",
                tool="evidence",
                action="issue_browser",
                args={"target_type": "run", "target_id": "old"},
            ),
        ]
        for payload in payload_cases:
            with self.subTest(action=payload.get("action")):
                self._assert_rejection_contract(payload)
                self.assertTrue(
                    isinstance(payload.get("correctable_fields"), list)
                    or isinstance(payload.get("alternative_capabilities"), list),
                    msg=payload,
                )

    def test_removed_track_relation_actions_expose_recovery_contract(self) -> None:
        env_store.create_track(
            "track-feedback-foreign",
            "Foreign scope track",
            owner_role="pm",
            outcome="scope",
        )
        self._write_taskbox_task(
            actor_id="act-feedback-runless",
            role="pm",
            task_id="task-pm-feedback-foreign",
            title="PM foreign task",
            summary="scope",
            track_id=None,
        )
        for action in ("join", "attach_task", "detach_task"):
            payload = self._dispatch(
                role="dev",
                tool="track",
                action=action,
                args={"track_id": "track-feedback-foreign", "task_id": "task-pm-feedback-foreign"},
            )
            with self.subTest(action=action):
                self._assert_rejection_contract(payload)
                self.assertEqual(payload.get("permission_boundary"), "env.tool", msg=payload)
                self.assertEqual((payload.get("error") or {}).get("code"), "E_ENV_TOOL", msg=payload)
                self.assertIn("action", payload.get("correctable_fields", []), msg=payload)


if __name__ == "__main__":
    unittest.main()
