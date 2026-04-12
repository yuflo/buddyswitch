#!/usr/bin/env python3
"""Checks for debug/admin BuddySwitch CLI APIs."""

from __future__ import annotations

import io
import json
import sys
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_artifacts  # noqa: E402
import env_manifest  # noqa: E402
import env_tracks  # noqa: E402
from env_manifest import load_manifest  # noqa: E402


class DebugApiPermissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_manifest()

    def test_manifest_authority_profile_marks_debug_permission_scope(self) -> None:
        authority = env_manifest.buddy_authority_profile(self.manifest, "pm")

        self.assertEqual(authority["permission_scope"], "manual_debug_apis")
        self.assertIn("track-manager", authority["routing_skills"])
        self.assertIn("track.create", authority["object_permissions"])

    def test_track_debug_api_enforces_permissions(self) -> None:
        env_tracks.require_permission(self.manifest, "pm", "track.create")
        with self.assertRaisesRegex(ValueError, "not allowed"):
            env_tracks.require_permission(self.manifest, "market", "track.create")

    def test_track_debug_api_rejects_unknown_buddy_refs(self) -> None:
        args = Namespace(
            manifest=env_tracks.DEFAULT_MANIFEST,
            actor="pm",
            track_id="track-debug-ref",
            title="Debug Ref",
            status="active",
            current_buddy="unknown",
            next_buddy=None,
            summary=None,
        )

        with self.assertRaisesRegex(ValueError, "current_buddy must reference a known buddy"):
            env_tracks.cmd_create(args)

    def test_track_parser_leaves_status_validation_to_store(self) -> None:
        parser = env_tracks.build_parser()
        args = parser.parse_args(
            ["create", "track-debug-status", "--title", "Debug Status", "--status", "not-a-status"]
        )
        self.assertEqual(args.status, "not-a-status")
        with self.assertRaisesRegex(ValueError, "track.status must be one of"):
            args.func(args)

    def test_artifact_debug_api_enforces_permissions(self) -> None:
        env_artifacts.require_permission(self.manifest, "market", "artifact.create")
        with self.assertRaisesRegex(ValueError, "not allowed"):
            env_artifacts.require_permission(self.manifest, "market", "artifact.delete")

    def test_artifact_debug_api_rejects_unknown_buddy(self) -> None:
        args = Namespace(
            manifest=env_artifacts.DEFAULT_MANIFEST,
            actor="pm",
            artifact_id="art-debug-ref",
            title="Debug Ref",
            buddy="unknown",
            skill_id="track-manager",
            track_id=None,
            summary=None,
            no_auto_register=True,
            content_json=None,
            content_file=None,
        )

        with self.assertRaisesRegex(ValueError, "buddy must reference a known buddy"):
            env_artifacts.cmd_create(args)

    def test_artifact_debug_create_accepts_structured_content(self) -> None:
        args = Namespace(
            manifest=env_artifacts.DEFAULT_MANIFEST,
            actor="market",
            artifact_id="art-debug-content",
            title="Debug Content",
            buddy="market",
            skill_id="research-scan",
            track_id=None,
            summary="created",
            content_json='{"summary":"created"}',
            content_file=None,
            no_auto_register=True,
        )
        artifact = {"id": "art-debug-content", "content": {"summary": "created"}}
        buffer = io.StringIO()

        with patch.object(env_artifacts, "create_artifact", return_value=artifact) as mocked:
            with redirect_stdout(buffer):
                result = env_artifacts.cmd_create(args)

        self.assertEqual(result, 0)
        mocked.assert_called_once()
        self.assertEqual(mocked.call_args.kwargs["content"], {"summary": "created"})
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["content"], {"summary": "created"})

    def test_artifact_debug_update_accepts_structured_content_only_patch(self) -> None:
        args = Namespace(
            manifest=env_artifacts.DEFAULT_MANIFEST,
            actor="market",
            artifact_id="art-debug-content",
            title=None,
            buddy=None,
            skill_id=None,
            track_id=None,
            summary=None,
            content_json='{"summary":"updated"}',
            content_file=None,
            no_auto_register=True,
        )
        artifact = {"id": "art-debug-content", "content": {"summary": "updated"}}
        buffer = io.StringIO()

        with patch.object(env_artifacts, "update_artifact", return_value=artifact) as mocked:
            with redirect_stdout(buffer):
                result = env_artifacts.cmd_update(args)

        self.assertEqual(result, 0)
        mocked.assert_called_once_with(
            "art-debug-content",
            {"content": {"summary": "updated"}},
            auto_register=False,
        )


class AdminCleanupCommandTests(unittest.TestCase):
    def test_cleanup_buddy_runs_as_admin_helper(self) -> None:
        args = Namespace(buddy="market", delete_files=False, dry_run=True)
        buffer = io.StringIO()
        with patch.object(env_artifacts, "delete_artifacts_by_buddy", return_value=[]) as mocked:
            with redirect_stdout(buffer):
                result = env_artifacts.cmd_cleanup_buddy(args)

        self.assertEqual(result, 0)
        mocked.assert_called_once_with("market", delete_files=False, dry_run=True)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["count"], 0)

    def test_cleanup_all_runs_as_admin_helper(self) -> None:
        args = Namespace(delete_files=False, dry_run=True)
        buffer = io.StringIO()
        with patch.object(env_artifacts, "delete_all_artifacts", return_value=[]) as mocked:
            with redirect_stdout(buffer):
                result = env_artifacts.cmd_cleanup_all(args)

        self.assertEqual(result, 0)
        mocked.assert_called_once_with(delete_files=False, dry_run=True)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["count"], 0)


if __name__ == "__main__":
    unittest.main()
