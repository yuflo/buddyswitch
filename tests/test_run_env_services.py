#!/usr/bin/env python3
"""Service ownership tests for BuddySwitch run persistence."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.services import runs as run_service  # noqa: E402
from runtime_kernel.persist import persist_buddy_run_request  # noqa: E402
import turn_runtime  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"


class RunServiceOwnershipTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def test_runtime_kernel_persist_delegates_to_run_service(self) -> None:
        context = {"ok": True, "run_envelope": {"run_id": "run-service-delegate"}}
        result = {"execution_summary": "delegated"}
        expected = {"ok": True, "receipt": {"run_id": "run-service-delegate"}}

        with patch.object(run_service, "commit_buddy_run", return_value=expected) as commit:
            payload = persist_buddy_run_request(context, result=result, manifest_path=MANIFEST)

        self.assertEqual(payload, expected)
        commit.assert_called_once_with(context, result=result, manifest_path=MANIFEST)

    def test_turn_runtime_public_persist_delegates_to_run_service(self) -> None:
        context = {"ok": True, "run_envelope": {"run_id": "run-public-delegate"}}
        result = {"execution_summary": "delegated"}
        expected = {"ok": True, "receipt": {"run_id": "run-public-delegate"}}

        with patch.object(run_service, "commit_buddy_run", return_value=expected) as commit:
            payload = turn_runtime.persist_buddy_run(context, result=result, manifest_path=MANIFEST)

        self.assertEqual(payload, expected)
        commit.assert_called_once_with(context, result=result, manifest_path=MANIFEST)

    def test_taskless_reservation_rejects_spoofed_turn_identity_without_clearing_reservation(self) -> None:
        run_id = "run-taskless-reservation-identity"
        context_revision = f"ctx-{run_id}"
        original_identity = {
            "instance_id": "inst-pm-original",
            "active_buddy": "pm",
            "request_text": "record taskless audit",
            "task_id": None,
            "track_id": None,
            "context_revision": context_revision,
            "sequence": 1,
            "run_id": run_id,
        }
        run_service.save_run_reservation(
            run_id=run_id,
            context_revision=context_revision,
            sequence=1,
            task_id=None,
            turn_identity=original_identity,
            instance_id="inst-pm-original",
        )
        spoofed_identity = dict(original_identity)
        spoofed_identity["instance_id"] = "inst-pm-spoofed"
        spoofed_context = {
            "ok": True,
            "context_revision": context_revision,
            "instance_id": "inst-pm-spoofed",
            "active_buddy": "pm",
            "request_text": "record taskless audit",
            "current_task_id": None,
            "current_track_id": None,
            "run_envelope": {
                "run_id": run_id,
                "sequence": 1,
                "turn_identity": spoofed_identity,
            },
        }

        with self.assertRaisesRegex(ValueError, "run reservation mismatch: turn_identity differs from reserved envelope"):
            run_service.commit_buddy_run(
                spoofed_context,
                result={"execution_summary": "spoofed taskless audit"},
                manifest_path=MANIFEST,
            )

        self.assertTrue(run_service.reserved_run_path(run_id).exists())
        self.assertFalse(self._runtime_path(f"buddyswitch/content/runs/{run_id}.json").exists())


if __name__ == "__main__":
    unittest.main()
