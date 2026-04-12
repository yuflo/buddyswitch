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
                "task_id": "task-market-1",
                "buddy": "market",
                "task_title": "Market Task",
                "task_summary": "Market summary",
                "latest_artifact_id": "art-market-2",
                "artifacts": [
                    {
                        "artifact_id": "art-market-2",
                        "title": "Market latest",
                        "summary": "Latest market artifact",
                        "skill_id": "research-scan",
                        "updated_at": "2026-04-13T09:30:00+08:00",
                        "is_latest": True,
                    },
                    {
                        "artifact_id": "art-market-1",
                        "title": "Market previous",
                        "summary": "Previous market artifact",
                        "skill_id": "research-scan",
                        "updated_at": "2026-04-13T08:00:00+08:00",
                        "is_latest": False,
                    },
                ],
            },
            {
                "task_id": "task-pm-1",
                "buddy": "pm",
                "task_title": "PM Task",
                "task_summary": "PM summary",
                "latest_artifact_id": "art-pm-1",
                "artifacts": [
                    {
                        "artifact_id": "art-pm-1",
                        "title": "PM latest",
                        "summary": "Latest pm artifact",
                        "skill_id": "write-prd",
                        "updated_at": "2026-04-13T09:00:00+08:00",
                        "is_latest": True,
                    }
                ],
            },
            {
                "task_id": "task-design-1",
                "buddy": "design",
                "task_title": "Design Task",
                "task_summary": "Design summary",
                "latest_artifact_id": "art-design-1",
                "artifacts": [
                    {
                        "artifact_id": "art-design-1",
                        "title": "Design latest",
                        "summary": "Latest design artifact",
                        "skill_id": "ia-spec",
                        "updated_at": "2026-04-13T09:10:00+08:00",
                        "is_latest": True,
                    }
                ],
            },
            {
                "task_id": "task-dev-1",
                "buddy": "dev",
                "task_title": "Dev Task",
                "task_summary": "Dev summary",
                "latest_artifact_id": "art-dev-1",
                "artifacts": [
                    {
                        "artifact_id": "art-dev-1",
                        "title": "Dev latest",
                        "summary": "Latest dev artifact",
                        "skill_id": "implement-task",
                        "updated_at": "2026-04-13T09:20:00+08:00",
                        "is_latest": True,
                    },
                    {
                        "artifact_id": "art-dev-0",
                        "title": "Dev previous",
                        "summary": "Previous dev artifact",
                        "skill_id": "implement-task",
                        "updated_at": "2026-04-13T08:20:00+08:00",
                        "is_latest": False,
                    },
                ],
            },
        ],
    }


class ArtifactSelectionTests(unittest.TestCase):
    def test_design_defaults_to_market_and_pm_latest(self) -> None:
        selection = artifact_selection.select_artifacts_for_run(
            current_buddy="design",
            demand="follow up design draft",
            track_artifact_index=_index_fixture(),
        )
        self.assertEqual(selection["selected_artifact_ids"], ["art-market-2", "art-pm-1"])
        self.assertEqual(selection["selection_mode"], "deterministic-v1")

    def test_design_continuation_adds_design_latest(self) -> None:
        selection = artifact_selection.select_artifacts_for_run(
            current_buddy="design",
            demand="continue design draft",
            track_artifact_index=_index_fixture(),
            current_task_id="task-design-1",
        )
        self.assertEqual(selection["selected_artifact_ids"], ["art-market-2", "art-pm-1", "art-design-1"])

    def test_explicit_buddy_mention_overrides_default_upstream(self) -> None:
        selection = artifact_selection.select_artifacts_for_run(
            current_buddy="design",
            demand="based on pm buddy requirement only",
            track_artifact_index=_index_fixture(),
        )
        self.assertEqual(selection["selected_artifact_ids"], ["art-pm-1"])

    def test_dev_defaults_to_pm_then_design_latest(self) -> None:
        selection = artifact_selection.select_artifacts_for_run(
            current_buddy="dev",
            demand="implement approved scope",
            track_artifact_index=_index_fixture(),
        )
        self.assertEqual(selection["selected_artifact_ids"], ["art-pm-1", "art-design-1"])

    def test_test_defaults_to_dev_pm_design_latest(self) -> None:
        selection = artifact_selection.select_artifacts_for_run(
            current_buddy="test",
            demand="run smoke checks",
            track_artifact_index=_index_fixture(),
        )
        self.assertEqual(selection["selected_artifact_ids"], ["art-dev-1", "art-pm-1", "art-design-1"])

    def test_history_hint_includes_previous_artifact(self) -> None:
        selection = artifact_selection.select_artifacts_for_run(
            current_buddy="design",
            demand="compare with previous market direction",
            track_artifact_index=_index_fixture(),
        )
        self.assertEqual(selection["selected_artifact_ids"], ["art-market-2", "art-pm-1", "art-market-1"])

    def test_prioritize_word_does_not_trigger_history_hint(self) -> None:
        selection = artifact_selection.select_artifacts_for_run(
            current_buddy="design",
            demand="prioritize market positioning but keep latest only",
            track_artifact_index=_index_fixture(),
        )
        self.assertEqual(selection["selected_artifact_ids"], ["art-market-2", "art-pm-1"])

    def test_selection_respects_max_default_items_trim(self) -> None:
        selection = artifact_selection.select_artifacts_for_run(
            current_buddy="test",
            demand="compare historical outputs from dev buddy and design buddy",
            track_artifact_index=_index_fixture(),
            max_default_items=2,
        )
        self.assertEqual(selection["selected_artifact_ids"], ["art-dev-1", "art-design-1"])
        self.assertTrue(any("max_default_items=2" in reason for reason in selection["reasons"]))

    def test_empty_index_returns_empty_selection(self) -> None:
        selection = artifact_selection.select_artifacts_for_run(
            current_buddy="design",
            demand="continue design",
            track_artifact_index=None,
        )
        self.assertEqual(selection["selected_artifact_ids"], [])


if __name__ == "__main__":
    unittest.main()
