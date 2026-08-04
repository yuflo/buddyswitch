"""Artifact response contract tests for broker-routed Tool actions."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import sys
import threading
import unittest
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import urlparse

from tests.support.paths import REPO_ROOT
from tests.support.fake_cdp import (
    read_client_text_frame as _read_client_text_frame,
    websocket_accept_value as _websocket_accept_value,
    write_server_text_frame as _write_server_text_frame,
)

ROOT = REPO_ROOT

import buddyswitch.runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.support import task_fixtures  # noqa: E402
from buddyswitch.modules.communication.private.state import messages as message_repo  # noqa: E402
from buddyswitch.modules.communication.private.domain import messages as message_service  # noqa: E402
from buddyswitch.foundation.tool_runtime import registry as tool_catalog  # noqa: E402
from buddyswitch.foundation.tool_runtime import results as tool_results  # noqa: E402
from buddyswitch.foundation.tool_runtime import context as runtime_context  # noqa: E402
from buddyswitch.runtime_support import turn_runtime  # noqa: E402
from tests.integration.env_tool._response_case import EnvToolResponseCase

MANIFEST = ROOT / "src" / "buddyswitch" / "catalog" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class EnvToolArtifactResponseTests(EnvToolResponseCase):
    def test_track_and_artifact_success_contract(self) -> None:
        actor_id = "act-pm-success"
        instance_json = self._instance_json(role="pm", actor_id=actor_id)

        track = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_id,
            role="pm",
            tool="track",
            action="create",
            args={
                "track_id": "track-response",
                "title": "Response",
                "outcome": "Response outcome",
                "now": {"next": "seed", "blocker": None},
            },
        )
        self._assert_write_success_contract(track)

        artifact = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_id,
            role="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-response-r1",
                "title": "Title",
                "summary": "Summary",
                "template": "brief",
                "body": "x",
            },
        )
        self._assert_write_success_contract(artifact)
        self.assertTrue((artifact.get("artifact") or {}).get("id"))
        self.assertNotIn("status", artifact.get("artifact") or {})
        self.assertNotIn("published_to_track", artifact.get("artifact") or {})
        self.assertEqual((artifact.get("artifact") or {}).get("currentness"), "draft")
        self.assertIn("track.add_material", "\n".join(str(x) for x in artifact.get("allowed_next_actions", [])))
        self.assertIn("track.add_proof", "\n".join(str(x) for x in artifact.get("allowed_next_actions", [])))

        published = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_id,
            role="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-response",
                "artifact_id": "art-response-r1",
                "label": "Brief",
                "summary": "published",
            },
        )
        self._assert_write_success_contract(published)
        self.assertEqual(set(published.get("updated_ids", [])), {"track-response"})
        changes = {row.get("change") for row in published.get("state_changes", []) if isinstance(row, dict)}
        self.assertIn("material_relation_added", changes)

    def test_artifact_template_permission_rejection_uses_structured_contract(self) -> None:
        actor_id = "act-pm-template-contract"
        instance_json = self._instance_json(role="pm", actor_id=actor_id)
        rejected = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_id,
            role="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-template-contract-denied",
                "title": "Wrong template",
                "summary": "deny",
                "template": "design",
                "body": "pm cannot write design",
            },
        )

        self._assert_rejection_contract(rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_ARTIFACT_TEMPLATE_PERMISSION")
        self.assertEqual(rejected.get("permission_boundary"), "artifact.template_permission")
        self.assertEqual(rejected.get("correctable_fields"), ["template"])
        self.assertEqual(rejected.get("durability"), "none")
        self.assertFalse(bool(rejected.get("state_changed")), msg=rejected)

    def test_artifact_attach_file_inline_blob_rejection_uses_structured_contract(self) -> None:
        actor_id = "act-design-attach-contract"
        instance_json = self._instance_json(role="design", actor_id=actor_id)
        created = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_id,
            role="design",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-design-attach-contract",
                "title": "Design handoff",
                "summary": "seed",
                "template": "design",
                "body": "# Handoff",
            },
        )
        self.assertTrue(created.get("ok"), msg=created)

        rejected = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_id,
            role="design",
            tool="artifact",
            action="attach_file",
            args={
                "artifact_id": "art-design-attach-contract",
                "filename": "desktop.png",
                "source_path": str(self._runtime_path(f"instances/{actor_id}/workspace/private/screenshots/desktop.png")),
                "content_base64": "aGVsbG8=",
            },
        )

        self._assert_rejection_contract(rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_ARTIFACT_PAYLOAD")
        self.assertEqual(rejected.get("permission_boundary"), "request-payload")

    def test_relation_success_responses_describe_object_mutations(self) -> None:
        actor_id = "act-pm-mutation-response"
        pm_instance = self._instance_json(role="pm", actor_id=actor_id)
        track = self._dispatch(
            instance_json=pm_instance,
            actor_id=actor_id,
            role="pm",
            tool="track",
            action="create",
            args={
                "track_id": "track-mutation-response",
                "title": "Mutation response",
                "outcome": "outcome",
                "now": {"next": "seed", "blocker": None},
            },
        )
        self.assertTrue(track.get("ok"), msg=track)

        test_instance = self._instance_json(role="test", actor_id=actor_id)
        proof_draft = self._dispatch(
            instance_json=test_instance,
            actor_id=actor_id,
            role="test",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-proof-response-r1",
                "title": "proof",
                "summary": "pass",
                "template": "proof",
                "body": "pass",
            },
        )
        self.assertTrue(proof_draft.get("ok"), msg=proof_draft)

        proof = self._dispatch(
            instance_json=test_instance,
            actor_id=actor_id,
            role="test",
            tool="track",
            action="add_proof",
            args={
                "track_id": "track-mutation-response",
                "artifact_id": "art-proof-response-r1",
                "label": "Smoke",
                "summary": "pass",
            },
        )
        self._assert_write_success_contract(proof)
        self.assertEqual(set(proof.get("updated_ids", [])), {"track-mutation-response"})
        changes = {row.get("change") for row in proof.get("state_changes", []) if isinstance(row, dict)}
        self.assertIn("proof_relation_added", changes)
        self.assertNotIn("update_added", changes)
