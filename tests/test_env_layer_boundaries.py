#!/usr/bin/env python3
"""Phase 8 boundary tests for env layer workspace and state access."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - python<3.11 fallback
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

CODEX_CONFIG = ROOT / "tools" / "launcher" / "codex_config.py"
MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"
PERMISSION_PROFILE = "buddyswitch-runtime"


class EnvLayerBoundaryTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _patch_config(
        self,
        *,
        temp_root: Path,
        buddy: str,
        shared_root: Path,
    ) -> str:
        instance_root = shared_root / "instances" / f"inst-{buddy}-boundary"
        workspace_dir = instance_root / "workspace"
        project_workspace_dir = shared_root / "project" / "workspace"
        config_path = temp_root / f"{buddy}-config.toml"
        completed = subprocess.run(
            [
                "python3",
                str(CODEX_CONFIG),
                "--config",
                str(config_path),
                "--repo-root",
                str(ROOT),
                "--shared-root",
                str(shared_root),
                "--source-codex-home",
                str(shared_root / "source-codex-home"),
                "--buddy",
                buddy,
                "--instance-root",
                str(instance_root),
                "--workspace-dir",
                str(workspace_dir),
                "--project-workspace-dir",
                str(project_workspace_dir),
                "--home",
                str(instance_root / "home"),
                "--codex-home",
                str(instance_root / "codex-home"),
                "--xdg-config-home",
                str(instance_root / "xdg-config"),
                "--temp-root",
                "/tmp",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        return config_path.read_text(encoding="utf-8")

    def _filesystem_entries(self, config_text: str) -> dict[str, object]:
        parsed = tomllib.loads(config_text)
        return parsed["permissions"][PERMISSION_PROFILE]["filesystem"]

    def _writable_paths(self, config_text: str) -> set[str]:
        filesystem = self._filesystem_entries(config_text)
        return {key for key, value in filesystem.items() if value == "write"}

    def _instance_json(self) -> Path:
        path = self._runtime_path("instance.json")
        path.write_text(
            json.dumps(
                {
                    "instance_id": "inst-dev-boundary",
                    "buddy": "dev",
                    "status": "active",
                    "current_task_id": None,
                    "current_track_id": None,
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "created_at": "2026-05-11T00:00:00Z",
                    "updated_at": "2026-05-11T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def _dispatch_dev_task_create(self, args: dict[str, object]) -> dict[str, object]:
        envelope = runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "request_id": f"req-env-layer-{uuid.uuid4().hex}",
                "method": "env.tool",
                "params": {
                    "instance_id": "inst-dev-boundary",
                    "active_buddy": "dev",
                    "tool": "task",
                    "action": "create",
                    "args": args,
                },
                "deadline_ms": 35000,
            },
            instance_json_path=self._instance_json(),
            manifest_path=MANIFEST,
        )
        self.assertEqual(envelope.get("protocol"), PROTOCOL)
        if envelope.get("ok") is True:
            payload = envelope.get("result")
            self.assertIsInstance(payload, dict, msg=envelope)
            assert isinstance(payload, dict)
            return payload
        error = envelope.get("error")
        self.assertIsInstance(error, dict, msg=envelope)
        assert isinstance(error, dict)
        payload = {
            "ok": False,
            "error": {
                "code": error.get("code"),
                "message": error.get("message"),
                "retriable": error.get("retriable"),
            },
        }
        for key, value in envelope.items():
            if key in {"protocol", "request_id", "ok", "error"}:
                continue
            payload[key] = value
        return payload

    def test_dev_project_workspace_is_writable_and_non_dev_project_workspace_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            shared_root = temp_root / "shared"
            project_workspace_dir = shared_root / "project" / "workspace"

            dev_writable = self._writable_paths(
                self._patch_config(temp_root=temp_root, buddy="dev", shared_root=shared_root)
            )
            pm_writable = self._writable_paths(
                self._patch_config(temp_root=temp_root, buddy="pm", shared_root=shared_root)
            )

            self.assertIn(str(project_workspace_dir.resolve(strict=False)), dev_writable)
            self.assertNotIn(str(project_workspace_dir.resolve(strict=False)), pm_writable)
            self.assertNotIn(str((shared_root / "state").resolve(strict=False)), dev_writable)
            self.assertNotIn(str(shared_root.resolve(strict=False)), dev_writable)

    def test_permission_profile_does_not_grant_pm_project_or_design_sandbox_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            shared_root = temp_root / "shared"
            instance_root = shared_root / "instances" / "inst-pm-boundary"
            workspace_dir = instance_root / "workspace"
            project_workspace_dir = shared_root / "project" / "workspace"

            config_text = self._patch_config(temp_root=temp_root, buddy="pm", shared_root=shared_root)
            writable_paths = self._writable_paths(config_text)
            self.assertNotIn(str(project_workspace_dir.resolve(strict=False)), writable_paths)
            self.assertNotIn(str(workspace_dir.resolve(strict=False)), writable_paths)
            self.assertNotIn(str((workspace_dir / ".sandbox").resolve(strict=False)), writable_paths)
            self.assertNotIn(str((workspace_dir / ".sandbox" / "design").resolve(strict=False)), writable_paths)
            self.assertNotIn(str(shared_root.resolve(strict=False)), writable_paths)
            self.assertIn(
                str((workspace_dir / "buddyswitch" / "local" / "buddybox" / "pm").resolve(strict=False)),
                writable_paths,
            )

    def test_permission_profile_keeps_dev_project_write_and_runtime_reads(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            shared_root = temp_root / "shared"
            project_workspace_dir = shared_root / "project" / "workspace"
            config_text = self._patch_config(temp_root=temp_root, buddy="dev", shared_root=shared_root)
            writable_paths = self._writable_paths(config_text)
            filesystem = self._filesystem_entries(config_text)
            project_roots = filesystem[":project_roots"]
            self.assertIsInstance(project_roots, dict)
            assert isinstance(project_roots, dict)
            self.assertIn(str(project_workspace_dir.resolve(strict=False)), writable_paths)
            self.assertEqual(project_roots["."], "read")
            self.assertEqual(project_roots["buddyswitch/skills/**"], "none")
            self.assertEqual(project_roots["tools/**"], "none")

    def test_env_tool_rejects_payload_paths_instead_of_bypassing_project_or_raw_state_boundaries(self) -> None:
        project_probe = self._runtime_path("projects/app/env-tool-bypass.txt")
        raw_probe = self._runtime_path("buddyswitch/objects/tasks/env-tool-bypass.json")

        response = self._dispatch_dev_task_create(
            {
                "title": "Boundary bypass attempt",
                "summary": "should reject before write",
                "project_path": "projects/app/env-tool-bypass.txt",
                "raw_state_path": "buddyswitch/objects/tasks/env-tool-bypass.json",
            }
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("permission_boundary"), "request-payload")
        self.assertFalse(project_probe.exists())
        self.assertFalse(raw_probe.exists())


if __name__ == "__main__":
    unittest.main()
