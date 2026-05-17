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

        payload = workspace_data.build_workspace_data()
        self.assertEqual(set(payload), set(_load_json(CONTRACT)["top_level_key_order"]))
        self.assertNotIn("handoffs", payload)

        tracks = payload["tracks"]
        self.assertIsInstance(tracks, list)
        assert isinstance(tracks, list)
        row = next(r for r in tracks if isinstance(r, dict) and r.get("id") == track["id"])
        self.assertEqual(row.get("owner_buddy"), "dev")

        artifacts = payload["artifacts"]
        self.assertIsInstance(artifacts, list)
        assert isinstance(artifacts, list)
        self.assertTrue(any(isinstance(r, dict) and r.get("id") == artifact["id"] for r in artifacts))


if __name__ == "__main__":
    unittest.main()
