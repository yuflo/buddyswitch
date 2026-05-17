#!/usr/bin/env python3
"""Workspace projection contract coverage."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_store  # noqa: E402
import workspace_data  # noqa: E402
from env_store import create_artifact, create_task, create_track  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

CONTRACT = ROOT / "framework" / "contracts" / "workspace-projection.json"


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


class ParallelContractsTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
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
        artifact = create_artifact(
            artifact_id="art-dev-contract-freeze",
            title="Implementation Report",
            buddy="dev",
            kind="implementation-report",
            task_id=task["id"],
            summary="Implementation summary",
            content={"result": "ok"},
            created_by="dev",
            source_refs=[{"type": "note", "label": "contract freeze"}],
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
        self.assertIn("comment_ids", row, msg="track view missing comment_ids")
        self.assertEqual(row.get("comment_ids"), [track_comment["id"]])

        artifacts = payload["artifacts"]
        self.assertIsInstance(artifacts, list)
        assert isinstance(artifacts, list)
        artifact_row = next(r for r in artifacts if isinstance(r, dict) and r.get("id") == artifact["id"])
        self.assertEqual(artifact_row.get("comment_ids"), [artifact_comment["id"]])

        tasks = payload["tasks"]
        self.assertIsInstance(tasks, list)
        assert isinstance(tasks, list)
        self.assertTrue(any(isinstance(r, dict) and r.get("id") == task["id"] for r in tasks))
        # Task views must NOT have comment_ids
        task_row = next(r for r in tasks if isinstance(r, dict) and r.get("id") == task["id"])
        self.assertNotIn("comment_ids", task_row, msg="task view must not expose comment_ids")


if __name__ == "__main__":
    unittest.main()
