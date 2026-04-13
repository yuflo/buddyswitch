#!/usr/bin/env python3
"""Deterministic artifact selection tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import artifact_selection  # noqa: E402


def _index_fixture() -> dict:
    return {
        "track_id": "track-selection-demo",
        "track_title": "Selection Demo",
        "track_summary": "Track summary",
        "updated_at": "2026-04-13T10:00:00+08:00",
        "tasks": [
            {
                "task_id": "task-pm-onboarding",
                "buddy": "pm",
                "task_title": "PM Onboarding",
                "task_summary": "PM summary",
                "artifact_slots": {
                    "prd": {
                        "current_artifact_id": "art-task-pm-onboarding-prd-r3",
                        "revision_count": 3,
                    }
                },
                "artifacts": [
                    {
                        "artifact_id": "art-task-pm-onboarding-prd-r3",
                        "title": "PRD r3",
                        "slot": "prd",
                        "revision": 3,
                        "supersedes_artifact_id": "art-task-pm-onboarding-prd-r2",
                        "summary": "Current PRD",
                        "skill_id": "write-prd",
                        "updated_at": "2026-04-13T09:30:00+08:00",
                        "is_current": True,
                    },
                    {
                        "artifact_id": "art-task-pm-onboarding-prd-r2",
                        "title": "PRD r2",
                        "slot": "prd",
                        "revision": 2,
                        "supersedes_artifact_id": "art-task-pm-onboarding-prd-r1",
                        "summary": "Previous PRD",
                        "skill_id": "write-prd",
                        "updated_at": "2026-04-13T08:30:00+08:00",
                        "is_current": False,
                    },
                ],
            },
            {
                "task_id": "task-design-onboarding",
                "buddy": "design",
                "task_title": "Design Onboarding",
                "task_summary": "Design summary",
                "artifact_slots": {
                    "design-spec": {
                        "current_artifact_id": "art-task-design-onboarding-design-spec-r2",
                        "revision_count": 2,
                    }
                },
                "artifacts": [
                    {
                        "artifact_id": "art-task-design-onboarding-design-spec-r2",
                        "title": "Design r2",
                        "slot": "design-spec",
                        "revision": 2,
                        "supersedes_artifact_id": "art-task-design-onboarding-design-spec-r1",
                        "summary": "Current design spec",
                        "skill_id": "ia-spec",
                        "updated_at": "2026-04-13T09:20:00+08:00",
                        "is_current": True,
                    }
                ],
            },
            {
                "task_id": "task-dev-onboarding",
                "buddy": "dev",
                "task_title": "Dev Onboarding",
                "task_summary": "Dev summary",
                "artifact_slots": {
                    "implementation-report": {
                        "current_artifact_id": "art-task-dev-onboarding-implementation-report-r1",
                        "revision_count": 1,
                    }
                },
                "artifacts": [
                    {
                        "artifact_id": "art-task-dev-onboarding-implementation-report-r1",
                        "title": "Implementation r1",
                        "slot": "implementation-report",
                        "revision": 1,
                        "supersedes_artifact_id": None,
                        "summary": "Current implementation report",
                        "skill_id": "implement-task",
                        "updated_at": "2026-04-13T09:40:00+08:00",
                        "is_current": True,
                    }
                ],
            },
        ],
    }


class ArtifactSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.track_artifact_index = _index_fixture()

    def test_selection_uses_required_slots_and_current_artifacts(self) -> None:
        selected = artifact_selection.select_artifacts_for_run(
            current_buddy="dev",
            demand="Implement the approved onboarding flow",
            required_slots=["prd", "design-spec"],
            track_artifact_index=self.track_artifact_index,
            current_task_id="task-dev-onboarding",
        )

        self.assertEqual(
            [item["slot"] for item in selected["selected_inputs"]],
            ["prd", "design-spec"],
        )
        self.assertEqual(
            selected["selected_inputs"][0]["artifact_id"],
            "art-task-pm-onboarding-prd-r3",
        )
        self.assertEqual(selected["selected_inputs"][0]["revision"], 3)
        self.assertEqual(selected["selection_mode"], "slot-current-v2")

    def test_selection_ignores_non_artifact_slots(self) -> None:
        selected = artifact_selection.select_artifacts_for_run(
            current_buddy="dev",
            demand="Implement the approved onboarding flow",
            required_slots=["task", "prd", "track", "design-spec"],
            track_artifact_index=self.track_artifact_index,
            current_task_id="task-dev-onboarding",
        )

        self.assertEqual(
            [item["slot"] for item in selected["selected_inputs"]],
            ["prd", "design-spec"],
        )

    def test_selection_respects_max_default_items_trim(self) -> None:
        selected = artifact_selection.select_artifacts_for_run(
            current_buddy="dev",
            demand="Implement the approved onboarding flow",
            required_slots=["prd", "design-spec", "implementation-report"],
            track_artifact_index=self.track_artifact_index,
            current_task_id="task-dev-onboarding",
            max_default_items=2,
        )

        self.assertEqual(
            [item["slot"] for item in selected["selected_inputs"]],
            ["prd", "design-spec"],
        )
        self.assertTrue(any("max_default_items=2" in reason for reason in selected["reasons"]))

    def test_empty_index_returns_empty_selection(self) -> None:
        selected = artifact_selection.select_artifacts_for_run(
            current_buddy="design",
            demand="Continue design",
            required_slots=["prd"],
            track_artifact_index=None,
        )

        self.assertEqual(selected["selected_inputs"], [])


if __name__ == "__main__":
    unittest.main()
