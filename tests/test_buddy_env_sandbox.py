#!/usr/bin/env python3
"""Tests for profile-derived sandbox roots in launcher codex config patching."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - python<3.11 fallback
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
CODEX_CONFIG = ROOT / "tools" / "launcher" / "codex_config.py"
PERMISSION_PROFILE = "buddyswitch-runtime"


def _parse_writable_roots(config_text: str) -> list[str]:
    marker = "writable_roots = ["
    start = config_text.find(marker)
    if start < 0:
        raise AssertionError("writable_roots block not found")
    start += len(marker)
    end = config_text.find("\n]", start)
    if end < 0:
        raise AssertionError("writable_roots closing bracket not found")
    block = config_text[start:end]
    roots: list[str] = []
    for line in block.splitlines():
        item = line.strip()
        if not item:
            continue
        if item.endswith(","):
            item = item[:-1].rstrip()
        roots.append(json.loads(item))
    return roots


def _parse_profile_filesystem(config_text: str) -> dict[str, object]:
    parsed = tomllib.loads(config_text)
    assert parsed["default_permissions"] == PERMISSION_PROFILE
    return parsed["permissions"][PERMISSION_PROFILE]["filesystem"]


def _parse_profile_network(config_text: str) -> dict[str, object]:
    parsed = tomllib.loads(config_text)
    return parsed["permissions"][PERMISSION_PROFILE]["network"]


class BuddyEnvSandboxTests(unittest.TestCase):
    def _run_patch(
        self,
        *,
        config_path: Path,
        shared_root: Path,
        buddy: str,
        instance_root: Path,
        workspace_dir: Path,
        project_workspace_dir: Path,
        home: Path,
        codex_home: Path,
        xdg_config_home: Path,
        extra_args: list[str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        args = [
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
            str(home),
            "--codex-home",
            str(codex_home),
            "--xdg-config-home",
            str(xdg_config_home),
            "--temp-root",
            "/tmp",
        ]
        if extra_args:
            args.extend(extra_args)
        return subprocess.run(
            args,
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_non_dev_permission_profile_keeps_workspace_read_only_and_writes_only_safe_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            shared_root = temp_root / "shared"
            instance_root = shared_root / "instances" / "inst-pm-example"
            workspace_dir = instance_root / "workspace"
            project_workspace_dir = shared_root / "project" / "workspace"
            config_path = temp_root / "config.toml"

            completed = self._run_patch(
                config_path=config_path,
                shared_root=shared_root,
                buddy="pm",
                instance_root=instance_root,
                workspace_dir=workspace_dir,
                project_workspace_dir=project_workspace_dir,
                home=instance_root / "home",
                codex_home=instance_root / "codex-home",
                xdg_config_home=instance_root / "xdg-config",
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            config_text = config_path.read_text(encoding="utf-8")
            filesystem = _parse_profile_filesystem(config_text)
            writable_paths = {key for key, value in filesystem.items() if value == "write"}

            self.assertNotIn('sandbox_mode = "workspace-write"', config_text)
            self.assertNotIn("[sandbox_workspace_write]", config_text)
            self.assertEqual(filesystem["/"], "read")
            self.assertEqual(filesystem[":project_roots"], {".": "read"})
            self.assertIn(str((instance_root / "home").resolve(strict=False)), writable_paths)
            self.assertIn(str((instance_root / "codex-home").resolve(strict=False)), writable_paths)
            self.assertIn(str((instance_root / "xdg-config").resolve(strict=False)), writable_paths)
            self.assertIn(str((workspace_dir / "buddyswitch/content/buddybox/pm").resolve(strict=False)), writable_paths)
            self.assertIn(str(Path("/tmp").resolve(strict=False)), writable_paths)

            forbidden = [
                shared_root,
                shared_root / "project",
                project_workspace_dir,
                shared_root / "state",
                workspace_dir,
                instance_root,
            ]
            for root in forbidden:
                self.assertNotIn(str(root.resolve(strict=False)), writable_paths)
            self.assertEqual(_parse_profile_network(config_text), {"enabled": True, "mode": "full"})

    def test_profile_mode_rejects_temp_roots_inside_protected_project_and_state_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            shared_root = temp_root / "shared"
            instance_root = shared_root / "instances" / "inst-pm-example"
            workspace_dir = instance_root / "workspace"
            project_workspace_dir = shared_root / "project" / "workspace"
            config_path = temp_root / "config.toml"
            state_temp = shared_root / "state" / "tmp"
            project_source_temp = project_workspace_dir / "projects" / "app" / "tmp"

            completed = self._run_patch(
                config_path=config_path,
                shared_root=shared_root,
                buddy="pm",
                instance_root=instance_root,
                workspace_dir=workspace_dir,
                project_workspace_dir=project_workspace_dir,
                home=instance_root / "home",
                codex_home=instance_root / "codex-home",
                xdg_config_home=instance_root / "xdg-config",
                extra_args=[
                    "--temp-root",
                    str(state_temp),
                    "--temp-root",
                    str(project_source_temp),
                ],
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            filesystem = _parse_profile_filesystem(config_path.read_text(encoding="utf-8"))
            writable_paths = {key for key, value in filesystem.items() if value == "write"}

            self.assertNotIn(str(state_temp.resolve(strict=False)), writable_paths)
            self.assertNotIn(str(project_source_temp.resolve(strict=False)), writable_paths)

    def test_dev_permission_profile_includes_project_workspace_but_keeps_state_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            shared_root = temp_root / "shared"
            instance_root = shared_root / "instances" / "inst-dev-example"
            workspace_dir = instance_root / "workspace"
            project_workspace_dir = shared_root / "project" / "workspace"
            config_path = temp_root / "config.toml"

            completed = self._run_patch(
                config_path=config_path,
                shared_root=shared_root,
                buddy="dev",
                instance_root=instance_root,
                workspace_dir=workspace_dir,
                project_workspace_dir=project_workspace_dir,
                home=instance_root / "home",
                codex_home=instance_root / "codex-home",
                xdg_config_home=instance_root / "xdg-config",
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            config_text = config_path.read_text(encoding="utf-8")
            filesystem = _parse_profile_filesystem(config_text)
            writable_paths = {key for key, value in filesystem.items() if value == "write"}

            self.assertEqual(filesystem["/"], "read")
            self.assertEqual(filesystem[":project_roots"], {".": "read"})
            self.assertIn(str(project_workspace_dir.resolve(strict=False)), writable_paths)
            self.assertIn(str((workspace_dir / "buddyswitch/content/buddybox/dev").resolve(strict=False)), writable_paths)
            self.assertNotIn(str((shared_root / "state").resolve(strict=False)), writable_paths)
            self.assertNotIn(str(shared_root.resolve(strict=False)), writable_paths)
            self.assertNotIn(str((shared_root / "project").resolve(strict=False)), writable_paths)
            self.assertNotIn(str(instance_root.resolve(strict=False)), writable_paths)
            self.assertNotIn(str(workspace_dir.resolve(strict=False)), writable_paths)

    def test_patch_keeps_mcp_sections_and_forces_approve(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            shared_root = temp_root / "shared"
            instance_root = shared_root / "instances" / "inst-market-example"
            workspace_dir = instance_root / "workspace"
            project_workspace_dir = shared_root / "project" / "workspace"
            config_path = temp_root / "config.toml"
            config_path.write_text(
                """
[mcp_servers.chrome-devtools-cockpit]
command = "npx"
args = ["chrome-devtools-mcp@latest"]

[mcp_servers.notion]
url = "https://mcp.notion.com/mcp"
default_tools_approval_mode = "ask"
""".strip()
                + "\n",
                encoding="utf-8",
            )

            completed = self._run_patch(
                config_path=config_path,
                shared_root=shared_root,
                buddy="market",
                instance_root=instance_root,
                workspace_dir=workspace_dir,
                project_workspace_dir=project_workspace_dir,
                home=instance_root / "home",
                codex_home=instance_root / "codex-home",
                xdg_config_home=instance_root / "xdg-config",
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            text = config_path.read_text(encoding="utf-8")
            self.assertIn("[mcp_servers.chrome-devtools-cockpit]", text)
            self.assertIn("[mcp_servers.notion]", text)
            self.assertNotIn('default_tools_approval_mode = "ask"', text)
            self.assertEqual(text.count('default_tools_approval_mode = "approve"'), 2)

    def test_patch_forces_web_search_disabled_and_removes_existing_web_search_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            shared_root = temp_root / "shared"
            instance_root = shared_root / "instances" / "inst-pm-example"
            workspace_dir = instance_root / "workspace"
            project_workspace_dir = shared_root / "project" / "workspace"
            config_path = temp_root / "config.toml"
            config_path.write_text(
                """
web_search = "live"

[features]
plugins = false
web_search = "cached"
""".lstrip(),
                encoding="utf-8",
            )

            for _ in range(2):
                completed = self._run_patch(
                    config_path=config_path,
                    shared_root=shared_root,
                    buddy="pm",
                    instance_root=instance_root,
                    workspace_dir=workspace_dir,
                    project_workspace_dir=project_workspace_dir,
                    home=instance_root / "home",
                    codex_home=instance_root / "codex-home",
                    xdg_config_home=instance_root / "xdg-config",
                )
                self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            config_text = config_path.read_text(encoding="utf-8")
            parsed = tomllib.loads(config_text)
            top_level_text = config_text.split("[", 1)[0]
            features_text = config_text.split("[features]", 1)[1].split("\n[", 1)[0]
            self.assertEqual(parsed["web_search"], "disabled")
            self.assertEqual(config_text.count('web_search = "disabled"'), 1)
            self.assertIn('web_search = "disabled"', top_level_text)
            self.assertNotIn("web_search", features_text)
            self.assertNotIn('"live"', config_text)
            self.assertNotIn('"cached"', config_text)

    def test_profile_mode_with_broker_socket_includes_unix_socket_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            shared_root = temp_root / "shared"
            instance_root = shared_root / "instances" / "inst-pm-example"
            workspace_dir = instance_root / "workspace"
            project_workspace_dir = shared_root / "project" / "workspace"
            config_path = temp_root / "config.toml"
            broker_socket = instance_root / "runtime" / "runtime-broker.sock"

            completed = self._run_patch(
                config_path=config_path,
                shared_root=shared_root,
                buddy="pm",
                instance_root=instance_root,
                workspace_dir=workspace_dir,
                project_workspace_dir=project_workspace_dir,
                home=instance_root / "home",
                codex_home=instance_root / "codex-home",
                xdg_config_home=instance_root / "xdg-config",
                extra_args=["--broker-socket", str(broker_socket)],
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            network = _parse_profile_network(config_path.read_text(encoding="utf-8"))
            self.assertEqual(network["enabled"], True)
            self.assertEqual(network["mode"], "full")
            self.assertEqual(
                network["unix_sockets"],
                {str(broker_socket.resolve(strict=False)): "allow"},
            )

    def test_missing_profile_returns_2_and_leaves_config_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            shared_root = temp_root / "shared"
            instance_root = shared_root / "instances" / "inst-unknown-example"
            workspace_dir = instance_root / "workspace"
            project_workspace_dir = shared_root / "project" / "workspace"
            config_path = temp_root / "config.toml"
            initial = "[features]\nplugins = false\n"
            config_path.write_text(initial, encoding="utf-8")

            completed = self._run_patch(
                config_path=config_path,
                shared_root=shared_root,
                buddy="unknown",
                instance_root=instance_root,
                workspace_dir=workspace_dir,
                project_workspace_dir=project_workspace_dir,
                home=instance_root / "home",
                codex_home=instance_root / "codex-home",
                xdg_config_home=instance_root / "xdg-config",
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("Env profile invalid:", completed.stderr)
            self.assertEqual(config_path.read_text(encoding="utf-8"), initial)


if __name__ == "__main__":
    unittest.main()
