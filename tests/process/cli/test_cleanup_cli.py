"""Process contract for the cleanup command's canonical JSON response."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.support.python import PYTHON
from tests.support.paths import REPO_ROOT
from tests.support.processes import run_process


class CleanupCliTests(unittest.TestCase):
    def test_cleanup_cli_reports_active_categories_as_default_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            repo_root = Path(temp_root) / "state"
            manifest_path = repo_root / "buddyswitch" / "manifest.toml"
            manifest_path.parent.mkdir(parents=True)
            shutil.copy2(REPO_ROOT / "src" / "buddyswitch" / "catalog" / "manifest.toml", manifest_path)

            completed = run_process(
                [
                    PYTHON,
                    "-m",
                    "buddyswitch.application.entrypoints.cleanup",
                    "--state-root",
                    str(repo_root),
                    "--manifest",
                    str(manifest_path),
                    "--role",
                    "pm",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stderr, "")
        self.assertEqual(completed.stdout.count("\n"), 1, msg=completed.stdout)
        payload = json.loads(completed.stdout)
        self.assertEqual(
            completed.stdout,
            json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n",
        )
        self.assertNotIn("handoff_object_ids", payload)
        self.assertNotIn("handoff_records", payload)
