"""Process-boundary tests for the search env CLI."""

from __future__ import annotations

import json
import unittest

from tests.support.python import PYTHON
from tests.support.paths import REPO_ROOT
from tests.support.processes import run_process

ROOT = REPO_ROOT


class SearchCliTests(unittest.TestCase):
    def test_search_cli_help_exposes_status_and_request_only(self) -> None:
        resource_help = run_process(
            [PYTHON, "scripts/env/client.py", "search", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(resource_help.returncode, 0, msg=resource_help.stderr)
        self.assertIn("status", resource_help.stdout)
        self.assertIn("request", resource_help.stdout)
        self.assertNotIn("open-browser", resource_help.stdout)
        self.assertNotIn("open_browser", resource_help.stdout)
        self.assertNotIn("--query", resource_help.stdout)
        self.assertNotIn("--backend", resource_help.stdout)
        self.assertNotIn("--engine", resource_help.stdout)

        action_help = run_process(
            [PYTHON, "scripts/env/client.py", "search", "request", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(action_help.returncode, 0, msg=action_help.stderr)
        self.assertIn("--payload", action_help.stdout)

    def test_search_cli_rejects_missing_backend_and_removed_open_browser_command(self) -> None:
        missing_backend = run_process(
            [PYTHON, "scripts/env/client.py", "search", "request", "--payload", '{"query":"x"}'],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(missing_backend.returncode, 1)
        missing_backend_payload = json.loads(missing_backend.stdout)
        self.assertFalse(missing_backend_payload.get("ok"), msg=missing_backend_payload)
        self.assertEqual((missing_backend_payload.get("error") or {}).get("code"), "E_RUNTIME_BROKER_UNAVAILABLE")

        removed_open_browser = run_process(
            [
                PYTHON,
                "scripts/env/client.py",
                "search",
                "open-browser",
                "--payload",
                '{"query":"x","engine":"unknown"}',
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(removed_open_browser.returncode, 2)
        self.assertEqual(removed_open_browser.stdout, "")
        self.assertIn("invalid choice", removed_open_browser.stderr)
        self.assertIn("open-browser", removed_open_browser.stderr)

