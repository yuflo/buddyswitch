#!/usr/bin/env python3
"""Runless artifact selection tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import artifact_selection  # noqa: E402


class ArtifactSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.track_artifact_index = {
            "track_id": "track-selection",
            "artifacts": [
                {
                    "artifact_id": "art-prd-r1",
                    "template": "brief",
                    "created_by": "pm",
                    "revision": 1,
                    "status": "published",
                    "updated_at": "2026-05-15T10:00:00+00:00",
                    "is_current": True,
                },
                {
                    "artifact_id": "art-proof-r1",
                    "template": "proof",
                    "created_by": "test",
                    "revision": 1,
                    "status": "published",
                    "updated_at": "2026-05-15T11:00:00+00:00",
                    "is_current": True,
                },
            ],
        }

    def test_selection_uses_required_templates_and_current_published_artifacts(self) -> None:
        selected = artifact_selection.select_artifacts_for_run(
            active_buddy="dev",
            demand="Implement onboarding",
            required_templates=["brief", "proof"],
            track_artifact_index=self.track_artifact_index,
        )
        ids = [row["artifact_id"] for row in selected["selected_inputs"]]
        self.assertEqual(ids, ["art-prd-r1", "art-proof-r1"])
        self.assertEqual(selected["selection_mode"], "template-current-v1")

    def test_selection_dedupes_repeated_required_templates(self) -> None:
        selected = artifact_selection.select_artifacts_for_run(
            active_buddy="dev",
            demand="Implement onboarding",
            required_templates=["brief", "brief"],
            track_artifact_index=self.track_artifact_index,
        )
        self.assertEqual([row["artifact_id"] for row in selected["selected_inputs"]], ["art-prd-r1"])

    def test_selection_ignores_unknown_required_templates(self) -> None:
        selected = artifact_selection.select_artifacts_for_run(
            active_buddy="dev",
            demand="Implement onboarding",
            required_templates=["task", "track", "brief"],
            track_artifact_index=self.track_artifact_index,
        )
        self.assertEqual([row["template"] for row in selected["selected_inputs"]], ["brief"])

    def test_selection_respects_max_default_items_trim(self) -> None:
        selected = artifact_selection.select_artifacts_for_run(
            active_buddy="dev",
            demand="Implement onboarding",
            required_templates=["brief", "proof"],
            track_artifact_index=self.track_artifact_index,
            max_default_items=1,
        )
        self.assertEqual(len(selected["selected_inputs"]), 1)
        self.assertIn("Trimmed selection", "\n".join(selected["reasons"]))


if __name__ == "__main__":
    unittest.main()
