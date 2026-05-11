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

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"


class RunServiceOwnershipTests(unittest.TestCase):
    def test_runtime_kernel_persist_delegates_to_run_service(self) -> None:
        context = {"ok": True, "run_envelope": {"run_id": "run-service-delegate"}}
        result = {"execution_summary": "delegated", "state_effects": {"task": {"summary": "delegated"}}}
        expected = {"ok": True, "receipt": {"run_id": "run-service-delegate"}}

        with patch.object(run_service, "commit_buddy_run", return_value=expected) as commit:
            payload = persist_buddy_run_request(context, result=result, manifest_path=MANIFEST)

        self.assertEqual(payload, expected)
        commit.assert_called_once_with(context, result=result, manifest_path=MANIFEST)

    def test_turn_runtime_public_persist_delegates_to_run_service(self) -> None:
        context = {"ok": True, "run_envelope": {"run_id": "run-public-delegate"}}
        result = {"execution_summary": "delegated", "state_effects": {"task": {"summary": "delegated"}}}
        expected = {"ok": True, "receipt": {"run_id": "run-public-delegate"}}

        with patch.object(run_service, "commit_buddy_run", return_value=expected) as commit:
            payload = turn_runtime.persist_buddy_run(context, result=result, manifest_path=MANIFEST)

        self.assertEqual(payload, expected)
        commit.assert_called_once_with(context, result=result, manifest_path=MANIFEST)


if __name__ == "__main__":
    unittest.main()
