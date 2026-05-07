#!/usr/bin/env python3
"""Checks for debug/admin BuddySwitch CLI APIs."""

from __future__ import annotations

import io
import json
import subprocess
import sys
import unittest
from argparse import Namespace
from contextlib import redirect_stderr, redirect_stdout
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

    def test_track_parser_does_not_expose_attach_or_detach_artifact_commands(self) -> None:
        parser = env_tracks.build_parser()
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(["attach-artifact", "track-debug", "--artifact-id", "art-debug"])
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(["detach-artifact", "track-debug", "--artifact-id", "art-debug"])

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
            kind="track-note",
            task_id="task-debug-ref",
            source_run_id="run-debug-ref",
            summary=None,
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
            kind="market-scan",
            task_id="task-market-debug-content",
            source_run_id="run-market-debug-content",
            summary="created",
            content_json='{"summary":"created"}',
            content_file=None,
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
            kind=None,
            task_id=None,
            source_run_id=None,
            summary=None,
            content_json='{"summary":"updated"}',
            content_file=None,
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
        )

    def test_artifact_get_command_alias_reads_by_id(self) -> None:
        parser = env_artifacts.build_parser()
        args = parser.parse_args(["get", "art-debug-get", "--actor", "pm"])
        artifact = {"id": "art-debug-get", "title": "Debug Artifact"}
        buffer = io.StringIO()

        with patch.object(env_artifacts, "get_artifact", return_value=artifact) as mocked:
            with redirect_stdout(buffer):
                result = args.func(args)

        self.assertEqual(result, 0)
        mocked.assert_called_once_with("art-debug-get")
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["id"], "art-debug-get")


class AdminCleanupCommandTests(unittest.TestCase):
    def test_cleanup_buddy_runs_as_admin_helper(self) -> None:
        args = Namespace(buddy="market", dry_run=True)
        buffer = io.StringIO()
        with patch.object(env_artifacts, "delete_artifacts_by_buddy", return_value=[]) as mocked:
            with redirect_stdout(buffer):
                result = env_artifacts.cmd_cleanup_buddy(args)

        self.assertEqual(result, 0)
        mocked.assert_called_once_with("market", dry_run=True)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["count"], 0)

    def test_cleanup_all_runs_as_admin_helper(self) -> None:
        args = Namespace(dry_run=True)
        buffer = io.StringIO()
        with patch.object(env_artifacts, "delete_all_artifacts", return_value=[]) as mocked:
            with redirect_stdout(buffer):
                result = env_artifacts.cmd_cleanup_all(args)

        self.assertEqual(result, 0)
        mocked.assert_called_once_with(dry_run=True)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["count"], 0)


class ArtifactCliHelpSurfaceTests(unittest.TestCase):
    def _help_output(self, *args: str) -> str:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "env_artifacts.py"), *args, "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        return completed.stdout

    def test_create_help_does_not_expose_no_auto_register(self) -> None:
        output = self._help_output("create")
        self.assertNotIn("--no-auto-register", output)

    def test_update_help_does_not_expose_no_auto_register(self) -> None:
        output = self._help_output("update")
        self.assertNotIn("--no-auto-register", output)

    def test_delete_help_does_not_expose_delete_file(self) -> None:
        output = self._help_output("delete")
        self.assertNotIn("--delete-file", output)

    def test_cleanup_help_does_not_expose_delete_files(self) -> None:
        buddy_output = self._help_output("cleanup-buddy")
        all_output = self._help_output("cleanup-all")
        self.assertNotIn("--delete-files", buddy_output)
        self.assertNotIn("--delete-files", all_output)

if __name__ == "__main__":
    unittest.main()
