"""Tests for profile-derived sandbox roots in launcher codex config patching."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from tests.support.python import PYTHON

from tests.support.paths import REPO_ROOT
from tests.support.processes import run_process

ROOT = REPO_ROOT
CODEX_CONFIG = ROOT / "src" / "buddyswitch" / "foundation" / "cli_runtime" / "config.py"
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


def _profile_filesystem_entries(config_text: str) -> dict[str, object]:
    parsed = tomllib.loads(config_text)
    assert parsed["default_permissions"] == PERMISSION_PROFILE
    return parsed["permissions"][PERMISSION_PROFILE]["filesystem"]


def _parse_profile_filesystem(config_text: str) -> dict[str, object]:
    return _profile_filesystem_entries(config_text)


def _parse_profile_network(config_text: str) -> dict[str, object]:
    parsed = tomllib.loads(config_text)
    return parsed["permissions"][PERMISSION_PROFILE]["network"]


def _assert_codex_filesystem_profile_is_flat(
    test: unittest.TestCase,
    filesystem: dict[str, object],
) -> None:
    test.assertNotIn(":project_roots", filesystem)
    for key, value in filesystem.items():
        test.assertIsInstance(key, str)
        test.assertIsInstance(value, str, msg=key)
        test.assertNotIn("*", key)
        if key != "/":
            test.assertTrue(Path(key).is_absolute(), msg=key)


def _assert_installed_runtime_is_readable_but_not_writable(
    test: unittest.TestCase,
    filesystem: dict[str, object],
) -> None:
    runtime_root_path = Path(os.environ["BUDDYSWITCH_RUNTIME_DIR"]).resolve(strict=False)
    runtime_root = str(runtime_root_path)
    test.assertEqual(filesystem.get(runtime_root), "read")
    test.assertNotEqual(filesystem.get(runtime_root), "write")
    test.assertTrue(Path(sys.prefix).resolve(strict=False).is_relative_to(runtime_root_path))


class BuddyEnvSandboxTests(unittest.TestCase):
    def _run_patch(
        self,
        *,
        config_path: Path,
        shared_root: Path,
        role: str,
        instance_root: Path,
        workspace_dir: Path,
        project_workspace_dir: Path,
        home: Path,
        codex_home: Path,
        xdg_config_home: Path,
        extra_args: list[str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        args = [
            PYTHON,
            "-m",
            "buddyswitch.application.entrypoints.actor_build",
            "patch-config",
            "--config",
            str(config_path),
            "--source-root",
            str(ROOT),
            "--shared-root",
            str(shared_root),
            "--source-codex-home",
            str(shared_root / "source-codex-home"),
            "--role",
            role,
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
            str(instance_root / "tmp"),
        ]
        if extra_args:
            args.extend(extra_args)
        return run_process(
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
            instance_root = shared_root / "instances" / "act-pm-example"
            workspace_dir = instance_root / "workspace"
            project_workspace_dir = shared_root / "project" / "workspace"
            product_source_root = project_workspace_dir / "projects" / "app"
            config_path = temp_root / "config.toml"

            completed = self._run_patch(
                config_path=config_path,
                shared_root=shared_root,
                role="pm",
                instance_root=instance_root,
                workspace_dir=workspace_dir,
                project_workspace_dir=project_workspace_dir,
                home=instance_root / "home",
                codex_home=instance_root / "codex-home",
                xdg_config_home=instance_root / "xdg-config",
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            config_text = config_path.read_text(encoding="utf-8")
            filesystem = _profile_filesystem_entries(config_text)
            writable_paths = {key for key, value in filesystem.items() if value == "write"}
            filesystem_keys = set(filesystem.keys())
            _assert_codex_filesystem_profile_is_flat(self, filesystem)

            self.assertNotIn('sandbox_mode = "workspace-write"', config_text)
            self.assertNotIn("[sandbox_workspace_write]", config_text)
            self.assertEqual(filesystem["/"], "read")
            self.assertIn("sandbox_approval = false", config_text)
            self.assertEqual(filesystem[str(workspace_dir.resolve(strict=False))], "read")
            self.assertEqual(filesystem[str((shared_root / "state").resolve(strict=False))], "none")
            self.assertNotIn(str((workspace_dir / "buddyswitch" / "objects").resolve(strict=False)), filesystem)
            self.assertNotIn(
                str((workspace_dir / "buddyswitch" / "local" / "private" / "pm").resolve(strict=False)),
                filesystem,
            )
            _assert_installed_runtime_is_readable_but_not_writable(self, filesystem)
            self.assertEqual(filesystem[str(product_source_root.resolve(strict=False))], "read")
            self.assertEqual(filesystem[str(ROOT.resolve(strict=False))], "none")
            self.assertIn(str((instance_root / "home").resolve(strict=False)), writable_paths)
            self.assertIn(str((instance_root / "codex-home").resolve(strict=False)), writable_paths)
            self.assertIn(str((instance_root / "xdg-config").resolve(strict=False)), writable_paths)
            self.assertIn(str((workspace_dir / "private").resolve(strict=False)), writable_paths)
            self.assertIn(str((instance_root / "tmp").resolve(strict=False)), writable_paths)
            self.assertNotIn(str(Path("/tmp").resolve(strict=False)), writable_paths)

            forbidden_writes = [
                shared_root,
                shared_root / "project",
                project_workspace_dir,
                product_source_root,
                shared_root / "state",
                workspace_dir,
                instance_root,
            ]
            for root in forbidden_writes:
                self.assertNotIn(str(root.resolve(strict=False)), writable_paths)

            forbidden_keys = [
                shared_root,
                shared_root / "project",
                instance_root,
                shared_root / "source-codex-home",
            ]
            for root in forbidden_keys:
                self.assertNotIn(str(root.resolve(strict=False)), filesystem_keys)
            self.assertEqual(_parse_profile_network(config_text), {"enabled": True, "mode": "full"})

    def test_profile_mode_rejects_temp_roots_inside_protected_project_and_state_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            shared_root = temp_root / "shared"
            instance_root = shared_root / "instances" / "act-pm-example"
            workspace_dir = instance_root / "workspace"
            project_workspace_dir = shared_root / "project" / "workspace"
            config_path = temp_root / "config.toml"
            state_temp = shared_root / "state" / "tmp"
            project_source_temp = project_workspace_dir / "projects" / "app" / "tmp"
            project_workspace_temp = project_workspace_dir / "tmp"
            instance_temp = instance_root / "tmp"
            runtime_workspace_temp = workspace_dir / "tmp"

            completed = self._run_patch(
                config_path=config_path,
                shared_root=shared_root,
                role="pm",
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
                    "--temp-root",
                    str(project_workspace_temp),
                    "--temp-root",
                    str(instance_temp),
                    "--temp-root",
                    str(runtime_workspace_temp),
                ],
            )
            self.assertNotEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertIn("product-mode temp root must be the active instance tmp", completed.stderr)

    def test_dev_permission_profile_writes_source_root_only_and_keeps_state_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            shared_root = temp_root / "shared"
            instance_root = shared_root / "instances" / "act-dev-example"
            workspace_dir = instance_root / "workspace"
            project_workspace_dir = shared_root / "project" / "workspace"
            product_source_root = project_workspace_dir / "projects" / "app"
            config_path = temp_root / "config.toml"

            completed = self._run_patch(
                config_path=config_path,
                shared_root=shared_root,
                role="dev",
                instance_root=instance_root,
                workspace_dir=workspace_dir,
                project_workspace_dir=project_workspace_dir,
                home=instance_root / "home",
                codex_home=instance_root / "codex-home",
                xdg_config_home=instance_root / "xdg-config",
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            config_text = config_path.read_text(encoding="utf-8")
            filesystem = _profile_filesystem_entries(config_text)
            writable_paths = {key for key, value in filesystem.items() if value == "write"}
            _assert_codex_filesystem_profile_is_flat(self, filesystem)

            self.assertEqual(filesystem["/"], "read")
            self.assertEqual(filesystem[str(workspace_dir.resolve(strict=False))], "read")
            self.assertEqual(filesystem[str((shared_root / "state").resolve(strict=False))], "none")
            self.assertNotIn(str((workspace_dir / "buddyswitch" / "objects").resolve(strict=False)), filesystem)
            self.assertNotIn(
                str((workspace_dir / "buddyswitch" / "local" / "private" / "dev").resolve(strict=False)),
                filesystem,
            )
            _assert_installed_runtime_is_readable_but_not_writable(self, filesystem)
            self.assertIn(str(product_source_root.resolve(strict=False)), writable_paths)
            self.assertIn(str((workspace_dir / "private").resolve(strict=False)), writable_paths)
            self.assertIn(str((instance_root / "tmp").resolve(strict=False)), writable_paths)
            self.assertNotIn(str(project_workspace_dir.resolve(strict=False)), writable_paths)
            self.assertNotIn(str((shared_root / "state").resolve(strict=False)), writable_paths)
            self.assertNotIn(str(shared_root.resolve(strict=False)), writable_paths)
            self.assertNotIn(str((shared_root / "project").resolve(strict=False)), writable_paths)
            self.assertNotIn(str(instance_root.resolve(strict=False)), writable_paths)
            self.assertNotIn(str(workspace_dir.resolve(strict=False)), writable_paths)
            self.assertEqual(filesystem[str(ROOT.resolve(strict=False))], "none")

    def test_dev_permission_profile_denies_runtime_workspace_launcher_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            shared_root = temp_root / "shared"
            instance_root = shared_root / "instances" / "act-dev-hardening"
            workspace_dir = instance_root / "workspace"
            project_workspace_dir = shared_root / "project" / "workspace"
            product_source_root = project_workspace_dir / "projects" / "app"
            config_path = temp_root / "config.toml"

            completed = self._run_patch(
                config_path=config_path,
                shared_root=shared_root,
                role="dev",
                instance_root=instance_root,
                workspace_dir=workspace_dir,
                project_workspace_dir=project_workspace_dir,
                home=instance_root / "home",
                codex_home=instance_root / "codex-home",
                xdg_config_home=instance_root / "xdg-config",
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            filesystem = _profile_filesystem_entries(config_path.read_text(encoding="utf-8"))
            writable_paths = {key for key, value in filesystem.items() if value == "write"}
            _assert_codex_filesystem_profile_is_flat(self, filesystem)
            self.assertEqual(filesystem[str(workspace_dir.resolve(strict=False))], "read")
            self.assertEqual(filesystem[str((shared_root / "state").resolve(strict=False))], "none")
            self.assertNotIn(str((workspace_dir / "buddyswitch" / "objects").resolve(strict=False)), filesystem)
            _assert_installed_runtime_is_readable_but_not_writable(self, filesystem)
            self.assertNotIn(str(workspace_dir.resolve(strict=False)), writable_paths)
            self.assertNotIn(
                str((workspace_dir / "buddyswitch/local/private/pm").resolve(strict=False)),
                writable_paths,
            )

            self.assertIn(str(product_source_root.resolve(strict=False)), writable_paths)
            self.assertIn(str((workspace_dir / "private").resolve(strict=False)), writable_paths)
            self.assertNotIn(str(project_workspace_dir.resolve(strict=False)), writable_paths)
            self.assertIn(str((instance_root / "home").resolve(strict=False)), writable_paths)
            self.assertIn(str((instance_root / "codex-home").resolve(strict=False)), writable_paths)
            self.assertIn(str((instance_root / "xdg-config").resolve(strict=False)), writable_paths)
            self.assertIn(str((instance_root / "tmp").resolve(strict=False)), writable_paths)
            self.assertNotIn(str(Path("/tmp").resolve(strict=False)), writable_paths)

    def test_permission_profile_denies_stale_runtime_source_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            shared_root = temp_root / "shared"
            instance_root = shared_root / "instances" / "act-pm-example"
            workspace_dir = instance_root / "workspace"
            project_workspace_dir = shared_root / "project" / "workspace"
            config_path = temp_root / "config.toml"

            completed = self._run_patch(
                config_path=config_path,
                shared_root=shared_root,
                role="pm",
                instance_root=instance_root,
                workspace_dir=workspace_dir,
                project_workspace_dir=project_workspace_dir,
                home=instance_root / "home",
                codex_home=instance_root / "codex-home",
                xdg_config_home=instance_root / "xdg-config",
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            filesystem = _profile_filesystem_entries(config_path.read_text(encoding="utf-8"))
            writable_paths = {key for key, value in filesystem.items() if value == "write"}
            _assert_codex_filesystem_profile_is_flat(self, filesystem)
            self.assertEqual(filesystem[str(workspace_dir.resolve(strict=False))], "read")
            self.assertEqual(filesystem[str((shared_root / "state").resolve(strict=False))], "none")
            self.assertEqual(filesystem[str(ROOT.resolve(strict=False))], "none")
            self.assertNotIn(str((workspace_dir / "buddyswitch" / "objects").resolve(strict=False)), filesystem)
            self.assertNotIn(
                str((workspace_dir / "buddyswitch" / "local" / "private" / "pm").resolve(strict=False)),
                filesystem,
            )
            _assert_installed_runtime_is_readable_but_not_writable(self, filesystem)
            self.assertIn(str((workspace_dir / "private").resolve(strict=False)), writable_paths)
            self.assertIn(str((instance_root / "tmp").resolve(strict=False)), writable_paths)

    def test_patch_keeps_mcp_sections_and_forces_approve(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            shared_root = temp_root / "shared"
            instance_root = shared_root / "instances" / "act-market-example"
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
                role="market",
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
            instance_root = shared_root / "instances" / "act-pm-example"
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
                    role="pm",
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
            instance_root = shared_root / "instances" / "act-pm-example"
            workspace_dir = instance_root / "workspace"
            project_workspace_dir = shared_root / "project" / "workspace"
            config_path = temp_root / "config.toml"
            broker_socket = instance_root / "runtime" / "runtime-broker.sock"

            completed = self._run_patch(
                config_path=config_path,
                shared_root=shared_root,
                role="pm",
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

    def test_codex_macos_sandbox_can_read_runtime_scripts(self) -> None:
        if platform.system() != "Darwin":
            self.skipTest("codex macos sandbox smoke only runs on macOS")
        if shutil.which("codex") is None:
            self.skipTest("codex CLI not available")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            shared_root = temp_root / "shared"
            instance_root = shared_root / "instances" / "act-pm-sandbox-smoke"
            workspace_dir = instance_root / "workspace"
            project_workspace_dir = shared_root / "project" / "workspace"
            config_path = instance_root / "codex-home" / "config.toml"
            workspace_dir.mkdir(parents=True)
            project_workspace_dir.mkdir(parents=True)

            completed = self._run_patch(
                config_path=config_path,
                shared_root=shared_root,
                role="pm",
                instance_root=instance_root,
                workspace_dir=workspace_dir,
                project_workspace_dir=project_workspace_dir,
                home=instance_root / "home",
                codex_home=instance_root / "codex-home",
                xdg_config_home=instance_root / "xdg-config",
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            sandbox_env = os.environ.copy()
            sandbox_env["CODEX_HOME"] = str(instance_root / "codex-home")
            sandboxed = run_process(
                [
                    "codex",
                    "sandbox",
                    "--permissions-profile",
                    PERMISSION_PROFILE,
                    "-C",
                    str(workspace_dir),
                    PYTHON,
                    "-m",
                    "buddyswitch.application.entrypoints.diagnostics",
                    "status",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=sandbox_env,
            )
            self.assertEqual(sandboxed.returncode, 0, msg=sandboxed.stderr)
            self.assertIn('"runtime_mode": "runless"', sandboxed.stdout)

    def test_codex_macos_sandbox_enforces_source_root_write_boundary(self) -> None:
        if platform.system() != "Darwin":
            self.skipTest("codex macos sandbox smoke only runs on macOS")
        if shutil.which("codex") is None:
            self.skipTest("codex CLI not available")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            shared_root = temp_root / "shared"
            dev_instance_root = shared_root / "instances" / "act-dev-source-root-smoke"
            dev_workspace_dir = dev_instance_root / "workspace"
            project_workspace_dir = shared_root / "project" / "workspace"
            product_source_root = project_workspace_dir / "projects" / "app"
            dev_workspace_dir.mkdir(parents=True, exist_ok=True)
            (project_workspace_dir / "tools").mkdir(parents=True, exist_ok=True)
            (project_workspace_dir / "docs").mkdir(parents=True, exist_ok=True)
            (shared_root / "state").mkdir(parents=True, exist_ok=True)
            product_source_root.mkdir(parents=True, exist_ok=True)
            dev_config_path = dev_instance_root / "codex-home" / "config.toml"

            completed = self._run_patch(
                config_path=dev_config_path,
                shared_root=shared_root,
                role="dev",
                instance_root=dev_instance_root,
                workspace_dir=dev_workspace_dir,
                project_workspace_dir=project_workspace_dir,
                home=dev_instance_root / "home",
                codex_home=dev_instance_root / "codex-home",
                xdg_config_home=dev_instance_root / "xdg-config",
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            dev_env = os.environ.copy()
            dev_env["CODEX_HOME"] = str(dev_instance_root / "codex-home")

            allowed_write = run_process(
                [
                    "codex",
                    "sandbox",
                    "--permissions-profile",
                    PERMISSION_PROFILE,
                    "-C",
                    str(dev_workspace_dir),
                    PYTHON,
                    "-c",
                    (
                        "from pathlib import Path; "
                        f"p=Path({json.dumps(str(product_source_root / 'dev-allowed-write.txt'))}); "
                        "p.parent.mkdir(parents=True, exist_ok=True); "
                        "p.write_text('dev-write\\n', encoding='utf-8')"
                    ),
                ],
                text=True,
                capture_output=True,
                check=False,
                env=dev_env,
            )
            self.assertEqual(allowed_write.returncode, 0, msg=allowed_write.stderr)
            self.assertTrue((product_source_root / "dev-allowed-write.txt").exists())

            denied_targets = [
                project_workspace_dir / "tools" / "dev-blocked-tools.txt",
                project_workspace_dir / "docs" / "dev-blocked-docs.txt",
                dev_workspace_dir / "dev-blocked-runtime-workspace.txt",
                shared_root / "state" / "dev-blocked-raw-state.txt",
            ]
            for target in denied_targets:
                denied = run_process(
                    [
                        "codex",
                        "sandbox",
                        "--permissions-profile",
                        PERMISSION_PROFILE,
                        "-C",
                        str(dev_workspace_dir),
                        PYTHON,
                        "-c",
                        (
                            "from pathlib import Path; "
                            f"p=Path({json.dumps(str(target))}); "
                            "p.parent.mkdir(parents=True, exist_ok=True); "
                            "p.write_text('blocked\\n', encoding='utf-8')"
                        ),
                    ],
                    text=True,
                    capture_output=True,
                    check=False,
                    env=dev_env,
                )
                with self.subTest(target=str(target)):
                    self.assertNotEqual(denied.returncode, 0, msg=denied.stdout + denied.stderr)
                    self.assertFalse(target.exists(), msg=str(target))

            pm_instance_root = shared_root / "instances" / "act-pm-source-root-smoke"
            pm_workspace_dir = pm_instance_root / "workspace"
            pm_config_path = pm_instance_root / "codex-home" / "config.toml"
            source_probe = product_source_root / "pm-readable.txt"
            source_probe.write_text("pm can read\n", encoding="utf-8")
            pm_workspace_dir.mkdir(parents=True, exist_ok=True)

            pm_completed = self._run_patch(
                config_path=pm_config_path,
                shared_root=shared_root,
                role="pm",
                instance_root=pm_instance_root,
                workspace_dir=pm_workspace_dir,
                project_workspace_dir=project_workspace_dir,
                home=pm_instance_root / "home",
                codex_home=pm_instance_root / "codex-home",
                xdg_config_home=pm_instance_root / "xdg-config",
            )
            self.assertEqual(pm_completed.returncode, 0, msg=pm_completed.stderr)

            pm_env = os.environ.copy()
            pm_env["CODEX_HOME"] = str(pm_instance_root / "codex-home")
            pm_read = run_process(
                [
                    "codex",
                    "sandbox",
                    "--permissions-profile",
                    PERMISSION_PROFILE,
                    "-C",
                    str(pm_workspace_dir),
                    PYTHON,
                    "-c",
                    f"from pathlib import Path; print(Path({json.dumps(str(source_probe))}).read_text(encoding='utf-8').strip())",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=pm_env,
            )
            self.assertEqual(pm_read.returncode, 0, msg=pm_read.stderr)
            self.assertIn("pm can read", pm_read.stdout)

            pm_blocked_path = product_source_root / "pm-blocked-write.txt"
            pm_write = run_process(
                [
                    "codex",
                    "sandbox",
                    "--permissions-profile",
                    PERMISSION_PROFILE,
                    "-C",
                    str(pm_workspace_dir),
                    PYTHON,
                    "-c",
                    (
                        "from pathlib import Path; "
                        f"p=Path({json.dumps(str(pm_blocked_path))}); "
                        "p.write_text('pm-write\\n', encoding='utf-8')"
                    ),
                ],
                text=True,
                capture_output=True,
                check=False,
                env=pm_env,
            )
            self.assertNotEqual(pm_write.returncode, 0, msg=pm_write.stdout + pm_write.stderr)
            self.assertFalse(pm_blocked_path.exists())

    def test_missing_profile_returns_2_and_leaves_config_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            shared_root = temp_root / "shared"
            instance_root = shared_root / "instances" / "act-unknown-example"
            workspace_dir = instance_root / "workspace"
            project_workspace_dir = shared_root / "project" / "workspace"
            config_path = temp_root / "config.toml"
            initial = "[features]\nplugins = false\n"
            config_path.write_text(initial, encoding="utf-8")

            completed = self._run_patch(
                config_path=config_path,
                shared_root=shared_root,
                role="unknown",
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
