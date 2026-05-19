#!/usr/bin/env python3
"""Workspace projection contract coverage."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_legacy_store as env_store  # noqa: E402
import workspace_data  # noqa: E402
from env_legacy_store import create_artifact_revision, create_task, create_track  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

CONTRACT = ROOT / "framework" / "contracts" / "workspace-projection.json"


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


class ParallelContractsTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def test_projection_integration_surfaces_avoid_env_store_import(self) -> None:
        for relative in ("scripts/runtime_store/projections.py", "scripts/workspace_data.py"):
            source = (ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("import env_store", source, msg=relative)
            self.assertNotIn("from env_store import", source, msg=relative)

    def test_workspace_projection_contract_excludes_handoffs(self) -> None:
        contract = _load_json(CONTRACT)
        top_keys = set(contract["top_level_key_order"])
        self.assertNotIn("handoffs", top_keys)
        self.assertIn("tracks", top_keys)
        self.assertIn("tasks", top_keys)
        self.assertIn("artifacts", top_keys)

        sources = contract["data_sources"]
        self.assertFalse(any("handoffs" in str(row) for row in sources))
        self.assertIn("buddyswitch/objects/comments/*.json", sources)

    def test_projected_track_shape_uses_owner_buddy(self) -> None:
        contract = _load_json(CONTRACT)
        shape = contract["view_shapes"]["track"]
        key_order = set(shape["key_order"])
        self.assertIn("owner_buddy", key_order)
        self.assertNotIn("current_buddy", key_order)
        self.assertNotIn("next_buddy", key_order)

    def test_workspace_projection_runtime_payload_matches_contract_surface(self) -> None:
        track = create_track("track-contract-freeze", "Contract Freeze Track", owner_buddy="dev")
        task = create_task("task-dev-contract-freeze", "Implement contract freeze", buddy="dev", track_id=track["id"])
        artifact = create_artifact_revision(
            artifact_id="art-dev-contract-freeze",
            title="Implementation Report",
            summary="Implementation summary",
            body="Implementation summary",
            template="brief",
            supersedes_artifact_id=None,
            created_by="dev",
            authors=["dev"],
            source_refs=[{"type": "note", "label": "contract freeze"}],
        )
        _, artifact, _ = env_store.publish_track_material(
            track_id=track["id"],
            artifact_id=artifact["id"],
            label="Implementation Report",
            from_buddy="dev",
            summary="Implementation summary",
        )
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

        payload = workspace_data.build_workspace_data()
        self.assertEqual(set(payload), set(_load_json(CONTRACT)["top_level_key_order"]))
        self.assertNotIn("handoffs", payload)
        self.assertNotIn("comments", payload, msg="workspace projection must not expose top-level comments")

        tracks = payload["tracks"]
        self.assertIsInstance(tracks, list)
        assert isinstance(tracks, list)
        row = next(r for r in tracks if isinstance(r, dict) and r.get("id") == track["id"])
        self.assertEqual(row.get("owner_buddy"), "dev")
        shared_materials = row.get("shared_materials")
        self.assertIsInstance(shared_materials, list, msg=row)
        assert isinstance(shared_materials, list)
        self.assertEqual([entry.get("artifact_id") for entry in shared_materials], [artifact["id"]])
        self.assertIn("comment_ids", row, msg="track view missing comment_ids")
        self.assertEqual(row.get("comment_ids"), [track_comment["id"]])
        self.assertNotIn("tasks", row)
        self.assertNotIn("task_ids", row)

        artifacts = payload["artifacts"]
        self.assertIsInstance(artifacts, list)
        assert isinstance(artifacts, list)
        artifact_row = next(r for r in artifacts if isinstance(r, dict) and r.get("id") == artifact["id"])
        self.assertEqual(artifact_row.get("comment_ids"), [artifact_comment["id"]])
        self.assertEqual(artifact_row.get("template"), "brief")
        self.assertEqual(artifact_row.get("published_to_track"), track["id"])
        self.assertEqual(artifact_row.get("status"), "published")

        tasks = payload["tasks"]
        self.assertIsInstance(tasks, list)
        assert isinstance(tasks, list)
        self.assertTrue(any(isinstance(r, dict) and r.get("id") == task["id"] for r in tasks))
        # Task views must NOT have comment_ids
        task_row = next(r for r in tasks if isinstance(r, dict) and r.get("id") == task["id"])
        self.assertNotIn("comment_ids", task_row, msg="task view must not expose comment_ids")

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


if __name__ == "__main__":
    unittest.main()
