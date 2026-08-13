"""Artifact module selection tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT

from buddyswitch.modules.artifact.entrypoints import artifact_selection  # noqa: E402
from buddyswitch.modules.artifact import public as artifact_public  # noqa: E402
from buddyswitch.modules.artifact.private.state import artifacts  # noqa: E402


class ArtifactSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.track_artifact_index = {
            "track_id": "track-selection",
            "artifacts": [
                {
                    "artifact_id": "art-prd-r1",
                    "template": "brief",
                    "created_by_identity_id": "act-pm-selection",
                    "revision": 1,
                    "updated_at": "2026-05-15T10:00:00+00:00",
                    "current": True,
                },
                {
                    "artifact_id": "art-proof-r1",
                    "template": "proof",
                    "created_by_identity_id": "act-test-selection",
                    "revision": 1,
                    "updated_at": "2026-05-15T11:00:00+00:00",
                    "current": True,
                },
            ],
        }

    def test_selection_uses_required_templates_and_current_track_relations(self) -> None:
        selected = artifact_selection.select_artifacts_for_run(
            active_role="dev",
            demand="Implement onboarding",
            required_templates=["brief", "proof"],
            track_artifact_index=self.track_artifact_index,
        )
        ids = [row["artifact_id"] for row in selected["selected_inputs"]]
        self.assertEqual(ids, ["art-prd-r1", "art-proof-r1"])
        self.assertEqual(selected["selection_mode"], "template-current-v1")
        self.assertEqual(selected["selected_inputs"][0]["created_by_identity_id"], "act-pm-selection")
        self.assertNotIn("created_by", selected["selected_inputs"][0])

    def test_selection_dedupes_repeated_required_templates(self) -> None:
        selected = artifact_selection.select_artifacts_for_run(
            active_role="dev",
            demand="Implement onboarding",
            required_templates=["brief", "brief"],
            track_artifact_index=self.track_artifact_index,
        )
        self.assertEqual([row["artifact_id"] for row in selected["selected_inputs"]], ["art-prd-r1"])

    def test_selection_ignores_unknown_required_templates(self) -> None:
        selected = artifact_selection.select_artifacts_for_run(
            active_role="dev",
            demand="Implement onboarding",
            required_templates=["task", "track", "brief"],
            track_artifact_index=self.track_artifact_index,
        )
        self.assertEqual([row["template"] for row in selected["selected_inputs"]], ["brief"])

    def test_selection_respects_max_default_items_trim(self) -> None:
        selected = artifact_selection.select_artifacts_for_run(
            active_role="dev",
            demand="Implement onboarding",
            required_templates=["brief", "proof"],
            track_artifact_index=self.track_artifact_index,
            max_default_items=1,
        )
        self.assertEqual(len(selected["selected_inputs"]), 1)
        self.assertIn("Trimmed selection", "\n".join(selected["reasons"]))

    def test_public_contract_owns_the_artifact_template_vocabulary(self) -> None:
        expected = ("brief", "proposal", "design", "decision", "proof", "note")
        vocabulary = getattr(artifact_public, "VALID_ARTIFACT_TEMPLATES", None)
        self.assertEqual(vocabulary, expected)
        self.assertIs(artifacts.VALID_ARTIFACT_TEMPLATES, vocabulary)
