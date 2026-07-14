"""Regression tests for the BuddySwitch root launcher."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.process.launcher._harness import ProcessLauncherHarness
from tests.support.paths import REPO_ROOT
from tests.support.processes import run_process

ROOT = REPO_ROOT
LAUNCHER = ROOT / "buddyswitch-codex"


class TestLauncherCapabilities(ProcessLauncherHarness, unittest.TestCase):
    def test_instance_capabilities_get_json_returns_creation_default_dto(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            shared_root = temp_root_path / "shared"
            self._write_capability_cli_instance(shared_root)
            env = self._capability_cli_env(temp_root_path, shared_root)

            completed = run_process(
                [str(LAUNCHER), "instance", "capabilities", "act-pm-demo", "get"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=self._output_error_text(completed))
            payload = self._cli_success_data(completed)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["actor_id"], "act-pm-demo")
            self.assertEqual(payload["capabilities"]["parent"]["level"], "balanced")
            self.assertEqual(payload["capabilities"]["side"]["level"], "fast")
    def test_instance_capabilities_set_json_writes_snapshot_and_get_returns_same_dto(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            shared_root = temp_root_path / "shared"
            instance_json = self._write_capability_cli_instance(shared_root)
            env = self._capability_cli_env(temp_root_path, shared_root)

            set_result = run_process(
                [
                    str(LAUNCHER),
                    "instance",
                    "capabilities",
                    "act-pm-demo",
                    "set",
                    "--parent",
                    "deep",
                    "--side",
                    "maximum",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            get_result = run_process(
                [str(LAUNCHER), "instance", "capabilities", "act-pm-demo", "get"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(set_result.returncode, 0, msg=self._output_error_text(set_result))
            self.assertEqual(get_result.returncode, 0, msg=self._output_error_text(get_result))
            set_payload = self._cli_success_data(set_result)
            get_payload = self._cli_success_data(get_result)
            self.assertEqual(set_payload["actor_id"], "act-pm-demo")
            self.assertEqual(set_payload["capabilities"], get_payload["capabilities"])
            self.assertEqual(
                json.loads((instance_json.parent / "capability-config.json").read_text(encoding="utf-8")),
                {
                    "schema_version": 1,
                    "catalog_version": 1,
                    "parent": {"level": "deep", "model": "gpt-5.6-sol", "effort": "xhigh"},
                    "side": {"level": "maximum", "model": "gpt-5.6-sol", "effort": "max"},
                },
            )
    def test_instance_capabilities_invalid_level_exits_nonzero_and_preserves_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            shared_root = temp_root_path / "shared"
            instance_json = self._write_capability_cli_instance(shared_root)
            path = instance_json.parent / "capability-config.json"
            before = path.read_text(encoding="utf-8")
            env = self._capability_cli_env(temp_root_path, shared_root)

            completed = run_process(
                [
                    str(LAUNCHER),
                    "instance",
                    "capabilities",
                    "act-pm-demo",
                    "set",
                    "--parent",
                    "custom",
                    "--side",
                    "fast",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("parent_level", self._output_error_text(completed))
            self.assertEqual(path.read_text(encoding="utf-8"), before)
    def test_instance_capabilities_unknown_option_exits_two(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            shared_root = temp_root_path / "shared"
            self._write_capability_cli_instance(shared_root)
            env = self._capability_cli_env(temp_root_path, shared_root)

            completed = run_process(
                [str(LAUNCHER), "instance", "capabilities", "act-pm-demo", "get", "--bogus"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            self._cli_error(completed, code="INVALID_ARGUMENT")
            self.assertIn("instance capabilities get does not accept: --bogus", self._output_error_text(completed))
