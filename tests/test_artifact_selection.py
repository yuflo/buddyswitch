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
            "shared_materials": [
                {
                    "type": "artifact",
                    "artifact_id": "art-prd-r1",
                    "kind": "prd",
                    "label": "PRD",
                    "from_buddy": "pm",
                    "current": True,
                    "published_at": "2026-05-15T10:00:00+00:00",
                },
                {
                    "type": "artifact",
                    "artifact_id": "art-impl-r1",
                    "kind": "implementation-report",
                    "label": "Implementation",
                    "from_buddy": "dev",
                    "current": True,
                    "published_at": "2026-05-15T11:00:00+00:00",
                },
            ],
        }

    def test_selection_uses_required_kinds_and_current_artifacts(self) -> None:
        selected = artifact_selection.select_artifacts_for_run(
            active_buddy="dev",
            demand="Implement onboarding",
            required_kinds=["prd", "implementation-report"],
            track_artifact_index=self.track_artifact_index,
        )
        ids = [row["artifact_id"] for row in selected["selected_inputs"]]
        self.assertEqual(ids, ["art-prd-r1", "art-impl-r1"])
        self.assertEqual(selected["selection_mode"], "kind-current-v2")
        self.assertNotIn("task_id", selected["selected_inputs"][0])

    def test_selection_dedupes_repeated_required_kinds(self) -> None:
        selected = artifact_selection.select_artifacts_for_run(
            active_buddy="dev",
            demand="Implement onboarding",
            required_kinds=["prd", "prd"],
            track_artifact_index=self.track_artifact_index,
        )
        self.assertEqual([row["artifact_id"] for row in selected["selected_inputs"]], ["art-prd-r1"])

    def test_selection_ignores_unknown_required_kinds(self) -> None:
        selected = artifact_selection.select_artifacts_for_run(
            active_buddy="dev",
            demand="Implement onboarding",
            required_kinds=["task", "track", "prd"],
            track_artifact_index=self.track_artifact_index,
        )
        self.assertEqual([row["kind"] for row in selected["selected_inputs"]], ["prd"])

    def test_selection_respects_max_default_items_trim(self) -> None:
        selected = artifact_selection.select_artifacts_for_run(
            active_buddy="dev",
            demand="Implement onboarding",
            required_kinds=["prd", "implementation-report"],
            track_artifact_index=self.track_artifact_index,
            max_default_items=1,
        )
        self.assertEqual(len(selected["selected_inputs"]), 1)
        self.assertIn("Trimmed selection", "\n".join(selected["reasons"]))

    def test_parser_omits_retired_current_task_flag(self) -> None:
        parser = artifact_selection.build_parser()
        help_text = parser.format_help()
        self.assertNotIn("current-task" + "-id", help_text)


if __name__ == "__main__":
    unittest.main()
