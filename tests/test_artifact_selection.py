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


def _market_index_fixture() -> dict:
    return {
        "track_id": "track-market-selection-demo",
        "track_title": "Market Selection Demo",
        "track_summary": "Market track summary",
        "updated_at": "2026-04-13T11:00:00+08:00",
        "tasks": [
            {
                "task_id": "task-market-v1",
                "buddy": "market",
                "task_title": "Market V1",
                "task_summary": "Market summary",
                "artifact_slots": {
                    "market-scan": {
                        "current_artifact_id": "art-task-market-v1-market-scan-r1",
                        "revision_count": 1,
                    },
                    "pmf-report": {
                        "current_artifact_id": "art-task-market-v1-pmf-report-r1",
                        "revision_count": 1,
                    },
                    "customer-discovery": {
                        "current_artifact_id": "art-task-market-v1-customer-discovery-r1",
                        "revision_count": 1,
                    },
                    "positioning-brief": {
                        "current_artifact_id": "art-task-market-v1-positioning-brief-r1",
                        "revision_count": 1,
                    },
                    "channel-plan": {
                        "current_artifact_id": "art-task-market-v1-channel-plan-r1",
                        "revision_count": 1,
                    },
                    "launch-prep": {
                        "current_artifact_id": "art-task-market-v1-launch-prep-r1",
                        "revision_count": 1,
                    },
                },
                "artifacts": [
                    {
                        "artifact_id": "art-task-market-v1-market-scan-r1",
                        "title": "Market Scan r1",
                        "slot": "market-scan",
                        "revision": 1,
                        "supersedes_artifact_id": None,
                        "summary": "Current market scan",
                        "skill_id": "research-scan",
                        "updated_at": "2026-04-13T10:00:00+08:00",
                        "is_current": True,
                    },
                    {
                        "artifact_id": "art-task-market-v1-pmf-report-r1",
                        "title": "PMF Report r1",
                        "slot": "pmf-report",
                        "revision": 1,
                        "supersedes_artifact_id": None,
                        "summary": "Current PMF report",
                        "skill_id": "pmf-recon",
                        "updated_at": "2026-04-13T10:05:00+08:00",
                        "is_current": True,
                    },
                    {
                        "artifact_id": "art-task-market-v1-customer-discovery-r1",
                        "title": "Customer Discovery r1",
                        "slot": "customer-discovery",
                        "revision": 1,
                        "supersedes_artifact_id": None,
                        "summary": "Current customer discovery",
                        "skill_id": "customer-discovery",
                        "updated_at": "2026-04-13T10:10:00+08:00",
                        "is_current": True,
                    },
                    {
                        "artifact_id": "art-task-market-v1-positioning-brief-r1",
                        "title": "Positioning Brief r1",
                        "slot": "positioning-brief",
                        "revision": 1,
                        "supersedes_artifact_id": None,
                        "summary": "Current positioning brief",
                        "skill_id": "positioning-copy",
                        "updated_at": "2026-04-13T10:15:00+08:00",
                        "is_current": True,
                    },
                    {
                        "artifact_id": "art-task-market-v1-channel-plan-r1",
                        "title": "Channel Plan r1",
                        "slot": "channel-plan",
                        "revision": 1,
                        "supersedes_artifact_id": None,
                        "summary": "Current channel plan",
                        "skill_id": "channel-discovery",
                        "updated_at": "2026-04-13T10:20:00+08:00",
                        "is_current": True,
                    },
                    {
                        "artifact_id": "art-task-market-v1-launch-prep-r1",
                        "title": "Launch Prep r1",
                        "slot": "launch-prep",
                        "revision": 1,
                        "supersedes_artifact_id": None,
                        "summary": "Current launch prep",
                        "skill_id": "launch-prep",
                        "updated_at": "2026-04-13T10:25:00+08:00",
                        "is_current": True,
                    },
                ],
            }
        ],
    }


class ArtifactSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.track_artifact_index = _index_fixture()
        self.market_track_artifact_index = _market_index_fixture()

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

    def test_selection_supports_market_v1_slots_for_pm(self) -> None:
        required_slot_artifacts = [
            ("market-scan", "art-task-market-v1-market-scan-r1"),
            ("pmf-report", "art-task-market-v1-pmf-report-r1"),
            ("customer-discovery", "art-task-market-v1-customer-discovery-r1"),
            ("positioning-brief", "art-task-market-v1-positioning-brief-r1"),
            ("channel-plan", "art-task-market-v1-channel-plan-r1"),
            ("launch-prep", "art-task-market-v1-launch-prep-r1"),
        ]
        selected = artifact_selection.select_artifacts_for_run(
            current_buddy="pm",
            demand="Define market buddy v1 scope",
            required_slots=[slot for slot, _ in required_slot_artifacts],
            track_artifact_index=self.market_track_artifact_index,
            current_task_id="task-pm-market-v1",
        )

        self.assertEqual(
            [(item["slot"], item["artifact_id"]) for item in selected["selected_inputs"]],
            required_slot_artifacts,
        )

    def test_selection_dedupes_repeated_required_slots_in_output(self) -> None:
        selected = artifact_selection.select_artifacts_for_run(
            current_buddy="dev",
            demand="Implement the approved onboarding flow",
            required_slots=["prd", "prd", "design-spec"],
            track_artifact_index=self.track_artifact_index,
            current_task_id="task-dev-onboarding",
        )

        self.assertEqual(
            [(item["slot"], item["artifact_id"]) for item in selected["selected_inputs"]],
            [
                ("prd", "art-task-pm-onboarding-prd-r3"),
                ("design-spec", "art-task-design-onboarding-design-spec-r2"),
            ],
        )

    def test_selection_prefers_coherent_task_bundle_over_newer_unrelated_slot(self) -> None:
        track_artifact_index = {
            "track_id": "track-market-bundle-selection",
            "track_title": "Market Bundle Selection",
            "track_summary": "Bundle-aware selection demo",
            "updated_at": "2026-04-15T12:00:00+08:00",
            "tasks": [
                {
                    "task_id": "task-market-bundle-a",
                    "buddy": "market",
                    "task_title": "Market Bundle A",
                    "task_summary": "Coherent positioning and launch prep",
                    "artifact_slots": {
                        "positioning-brief": {
                            "current_artifact_id": "art-task-market-bundle-a-positioning-brief-r1",
                            "revision_count": 1,
                        },
                        "launch-prep": {
                            "current_artifact_id": "art-task-market-bundle-a-launch-prep-r1",
                            "revision_count": 1,
                        },
                    },
                    "artifacts": [
                        {
                            "artifact_id": "art-task-market-bundle-a-positioning-brief-r1",
                            "title": "Bundle A Positioning Brief",
                            "slot": "positioning-brief",
                            "revision": 1,
                            "supersedes_artifact_id": None,
                            "summary": "Task A positioning brief",
                            "skill_id": "positioning-copy",
                            "updated_at": "2026-04-15T10:00:00+08:00",
                            "is_current": True,
                        },
                        {
                            "artifact_id": "art-task-market-bundle-a-launch-prep-r1",
                            "title": "Bundle A Launch Prep",
                            "slot": "launch-prep",
                            "revision": 1,
                            "supersedes_artifact_id": None,
                            "summary": "Task A launch prep",
                            "skill_id": "launch-prep",
                            "updated_at": "2026-04-15T10:05:00+08:00",
                            "is_current": True,
                        },
                    ],
                },
                {
                    "task_id": "task-market-bundle-b",
                    "buddy": "market",
                    "task_title": "Market Bundle B",
                    "task_summary": "Newer but incomplete positioning brief",
                    "artifact_slots": {
                        "positioning-brief": {
                            "current_artifact_id": "art-task-market-bundle-b-positioning-brief-r1",
                            "revision_count": 1,
                        }
                    },
                    "artifacts": [
                        {
                            "artifact_id": "art-task-market-bundle-b-positioning-brief-r1",
                            "title": "Bundle B Positioning Brief",
                            "slot": "positioning-brief",
                            "revision": 1,
                            "supersedes_artifact_id": None,
                            "summary": "Task B positioning brief",
                            "skill_id": "positioning-copy",
                            "updated_at": "2026-04-15T11:00:00+08:00",
                            "is_current": True,
                        }
                    ],
                },
            ],
        }

        selected = artifact_selection.select_artifacts_for_run(
            current_buddy="design",
            demand="Continue the IA spec with the current market bundle",
            required_slots=["positioning-brief", "launch-prep"],
            track_artifact_index=track_artifact_index,
            current_task_id="task-design-bundle-aware",
        )

        self.assertEqual(
            [(item["slot"], item["artifact_id"]) for item in selected["selected_inputs"]],
            [
                ("positioning-brief", "art-task-market-bundle-a-positioning-brief-r1"),
                ("launch-prep", "art-task-market-bundle-a-launch-prep-r1"),
            ],
        )

    def test_selection_prefers_minimal_task_cover_for_overlapping_bundles(self) -> None:
        track_artifact_index = {
            "track_id": "track-overlapping-bundles",
            "track_title": "Overlapping Bundles",
            "track_summary": "Overlap-aware selection demo",
            "updated_at": "2026-04-15T12:30:00+08:00",
            "tasks": [
                {
                    "task_id": "task-bundle-left",
                    "buddy": "market",
                    "task_title": "Bundle Left",
                    "task_summary": "Covers slots a and b",
                    "artifacts": [
                        {
                            "artifact_id": "art-bundle-left-a",
                            "slot": "a",
                            "updated_at": "2026-04-15T10:00:00+08:00",
                            "is_current": True,
                        },
                        {
                            "artifact_id": "art-bundle-left-b",
                            "slot": "b",
                            "updated_at": "2026-04-15T10:00:00+08:00",
                            "is_current": True,
                        },
                    ],
                },
                {
                    "task_id": "task-bundle-middle",
                    "buddy": "market",
                    "task_title": "Bundle Middle",
                    "task_summary": "Newer overlap across b and c",
                    "artifacts": [
                        {
                            "artifact_id": "art-bundle-middle-b",
                            "slot": "b",
                            "updated_at": "2026-04-15T11:00:00+08:00",
                            "is_current": True,
                        },
                        {
                            "artifact_id": "art-bundle-middle-c",
                            "slot": "c",
                            "updated_at": "2026-04-15T11:00:00+08:00",
                            "is_current": True,
                        },
                    ],
                },
                {
                    "task_id": "task-bundle-right",
                    "buddy": "market",
                    "task_title": "Bundle Right",
                    "task_summary": "Covers slots c and d",
                    "artifacts": [
                        {
                            "artifact_id": "art-bundle-right-c",
                            "slot": "c",
                            "updated_at": "2026-04-15T09:00:00+08:00",
                            "is_current": True,
                        },
                        {
                            "artifact_id": "art-bundle-right-d",
                            "slot": "d",
                            "updated_at": "2026-04-15T09:00:00+08:00",
                            "is_current": True,
                        },
                    ],
                },
            ],
        }

        selected = artifact_selection.select_artifacts_for_run(
            current_buddy="design",
            demand="Continue with the cleanest overlapping market evidence bundle",
            required_slots=["a", "b", "c", "d"],
            track_artifact_index=track_artifact_index,
            current_task_id="task-design-overlap-aware",
        )

        self.assertEqual(
            [(item["slot"], item["artifact_id"], item["task_id"]) for item in selected["selected_inputs"]],
            [
                ("a", "art-bundle-left-a", "task-bundle-left"),
                ("b", "art-bundle-left-b", "task-bundle-left"),
                ("c", "art-bundle-right-c", "task-bundle-right"),
                ("d", "art-bundle-right-d", "task-bundle-right"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
