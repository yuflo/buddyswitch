"""Regression tests for the BuddySwitch root launcher."""

from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from tests.process.launcher._harness import ProcessLauncherHarness
from tests.support.paths import REPO_ROOT
from tests.support.processes import run_process
from tests.support.python import PYTHON
from tests.support.cli import write_executable

from buddyswitch.application import build as application_build
from buddyswitch.application import cli_runtime as application_cli_runtime
from buddyswitch.application.entrypoints import actor_build
from buddyswitch.foundation.cli_runtime import config as codex_config
from buddyswitch.foundation.cli_runtime import runtime as cli_runtime
from buddyswitch.runtime_support import env_manifest

ROOT = REPO_ROOT
LAUNCHER = ROOT / "buddyswitch-codex"


def _cli_runtime_shell_environment(
    base: dict[str, str] | None = None,
) -> dict[str, str]:
    application = application_build.activate_application()
    return cli_runtime.application_environment(
        application_cli_runtime.assemble_cli_runtime(application),
        base=os.environ.copy() if base is None else base,
    )


class TestLauncherBootstrapConfig(ProcessLauncherHarness, unittest.TestCase):
    def test_actor_bootstrap_projects_selected_role_skills_and_config_once(self) -> None:
        application = application_build.activate_application()
        projection = actor_build.resolve_actor_bootstrap(
            "pm",
            application=application,
        )
        manifest = env_manifest.load_manifest()
        role = env_manifest.require_role(manifest, "pm")
        package_root = Path(actor_build.__file__).resolve().parents[2]
        self.assertEqual(projection.source_root, package_root)
        self.assertEqual(
            projection.agents_source,
            package_root / "launcher" / "assets" / "roles" / "pm" / "AGENTS.md",
        )
        self.assertEqual(
            tuple(skill.skill_id for skill in projection.skills),
            tuple(role["skills"]),
        )
        self.assertTrue(all(skill.source.is_dir() for skill in projection.skills))
        existing = (
            projection.codex_config
            + """

[mcp_servers.buddyswitch-env]
command = "/runtime/python"
args = ["/runtime/env_tool_mcp_server.py"]
"""
        )

        rendered = codex_config.patched_config_text(
            existing,
            [],
            parent_disabled_tools=("demand_sys__resolve_inbound",),
            profile_mode=True,
            profile_filesystem_entries={"/": "read"},
        )

        self.assertIn(
            'disabled_tools = ["demand_sys__resolve_inbound"]',
            rendered,
        )
        self.assertIn('name = "demand-triage"', rendered)
        triage_skill = rendered.split('name = "demand-triage"', 1)[1].split("[[", 1)[0]
        self.assertIn("enabled = false", triage_skill)
        self.assertNotIn('name = "demand-orchestration"', rendered)
    def test_shared_environment_bootstrap_creates_browser_ttl_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            shared_root = Path(temp_root) / ".codex-buddyswitch"
            command = r'''
set -euo pipefail
source "$BUDDYSWITCH_PACKAGE_ROOT/foundation/cli_runtime/shell/env.sh"
export BUDDYSWITCH_SHARED_ROOT="$1"
buddyswitch_env_init
buddyswitch_ensure_browser_ttl_config
'''

            completed = run_process(
                ["/bin/bash", "-c", command, "browser-ttl-bootstrap", str(shared_root)],
                cwd=ROOT,
                env=_cli_runtime_shell_environment(),
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=self._output_error_text(completed))
            self.assertEqual(
                (shared_root / "config" / "browser.toml").read_text(encoding="utf-8"),
                "schema_version = 1\n\n[ttl]\npage_idle_seconds = 40\nrelease_delay_seconds = 10\n",
            )

    def test_shared_environment_bootstrap_rejects_invalid_existing_browser_ttl_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            shared_root = Path(temp_root) / ".codex-buddyswitch"
            config_path = shared_root / "config" / "browser.toml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("schema_version = 2\n", encoding="utf-8")
            command = r'''
set -euo pipefail
source "$BUDDYSWITCH_PACKAGE_ROOT/foundation/cli_runtime/shell/env.sh"
export BUDDYSWITCH_SHARED_ROOT="$1"
buddyswitch_env_init
buddyswitch_ensure_browser_ttl_config
'''

            completed = run_process(
                ["/bin/bash", "-c", command, "browser-ttl-bootstrap", str(shared_root)],
                cwd=ROOT,
                env=_cli_runtime_shell_environment(),
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            self.assertIn(str(config_path), self._output_error_text(completed))
            self.assertEqual(config_path.read_text(encoding="utf-8"), "schema_version = 2\n")

    def test_public_launcher_missing_runtime_emits_contract_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            launcher = Path(temp_root) / "buddyswitch-codex"
            launcher.write_text(LAUNCHER.read_text(encoding="utf-8"), encoding="utf-8")
            launcher.chmod(LAUNCHER.stat().st_mode | stat.S_IXUSR)

            completed = run_process(
                [str(launcher), "instance", "roles"],
                cwd=ROOT,
                env={"HOME": temp_root, "PATH": os.environ.get("PATH", "")},
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 5)
            self.assertEqual(completed.stderr, "")
            error = self._cli_error(completed, code="RUNTIME_UNAVAILABLE")
            self.assertIn("activation.json", str(error["message"]))
    def test_public_launcher_missing_runtime_python_emits_contract_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            launcher = Path(temp_root) / "buddyswitch-codex"
            launcher.write_text(LAUNCHER.read_text(encoding="utf-8"), encoding="utf-8")
            launcher.chmod(LAUNCHER.stat().st_mode | stat.S_IXUSR)
            runtime_dir = Path(temp_root) / ".buddyswitch-runtime"
            runtime_dir.mkdir()
            (runtime_dir / "activation.json").write_text("{}\n", encoding="utf-8")

            completed = run_process(
                [str(launcher), "instance", "roles"],
                cwd=ROOT,
                env={"HOME": temp_root, "PATH": os.environ.get("PATH", "")},
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 5)
            self.assertEqual(completed.stderr, "")
            error = self._cli_error(completed, code="RUNTIME_UNAVAILABLE")
            self.assertIn("venv/bin/python", str(error["message"]))
    def test_python_resolver_preserves_verified_absolute_interpreter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            bin_dir = Path(temp_root) / "bin"
            bin_dir.mkdir()
            (bin_dir / "python").symlink_to(PYTHON)

            command = r'''
set -euo pipefail
source "$BUDDYSWITCH_PACKAGE_ROOT/foundation/cli_runtime/shell/env.sh"
PATH="$1"
buddyswitch_resolve_python
printf '%s\n' "$BUDDYSWITCH_PYTHON"
'''
            completed = run_process(
                ["/bin/bash", "-c", command, "resolver-test", str(bin_dir)],
                cwd=ROOT,
                env=_cli_runtime_shell_environment(
                    {**os.environ, "BUDDYSWITCH_PYTHON": PYTHON}
                ),
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=self._output_error_text(completed))
            self.assertEqual(completed.stdout.strip(), PYTHON)
    def test_python_resolver_fails_without_verified_interpreter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            command = r'''
set -euo pipefail
source "$BUDDYSWITCH_PACKAGE_ROOT/foundation/cli_runtime/shell/env.sh"
PATH="$1"
buddyswitch_resolve_python
'''
            completed = run_process(
                ["/bin/bash", "-c", command, "resolver-test", temp_root],
                cwd=ROOT,
                env=_cli_runtime_shell_environment(
                    {
                        name: value
                        for name, value in os.environ.items()
                        if name != "BUDDYSWITCH_PYTHON"
                    }
                ),
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("verified absolute runtime Python", self._output_error_text(completed))
    def test_python_resolver_rejects_unusable_verified_python(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            bin_dir = Path(temp_root) / "bin"
            bin_dir.mkdir()
            fake_python = bin_dir / "python"
            fake_python.write_text("#!/bin/sh\nexit 64\n", encoding="utf-8")
            fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)

            command = r'''
set -euo pipefail
source "$BUDDYSWITCH_PACKAGE_ROOT/foundation/cli_runtime/shell/env.sh"
PATH="$1"
buddyswitch_resolve_python
'''
            completed = run_process(
                ["/bin/bash", "-c", command, "resolver-test", str(bin_dir)],
                cwd=ROOT,
                env=_cli_runtime_shell_environment(
                    {**os.environ, "BUDDYSWITCH_PYTHON": str(fake_python)}
                ),
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("verified absolute runtime Python", self._output_error_text(completed))
    def test_python_resolver_accepts_verified_executable_without_path_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            bin_dir = Path(temp_root) / "bin"
            bin_dir.mkdir()
            fake_python = bin_dir / "python"
            write_executable(
                fake_python,
                "#!/bin/sh\n"
                "if [ \"$1\" = \"-c\" ] && [ \"$2\" = \"import sys\" ]; then\n"
                "  exit 0\n"
                "fi\n"
                "exit 64\n",
            )

            command = r'''
set -euo pipefail
source "$BUDDYSWITCH_PACKAGE_ROOT/foundation/cli_runtime/shell/env.sh"
PATH="$1"
buddyswitch_resolve_python
printf '%s\n' "$BUDDYSWITCH_PYTHON"
'''
            completed = run_process(
                ["/bin/bash", "-c", command, "resolver-test", str(bin_dir)],
                cwd=ROOT,
                env=_cli_runtime_shell_environment(
                    {**os.environ, "BUDDYSWITCH_PYTHON": str(fake_python)}
                ),
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=self._output_error_text(completed))
            self.assertEqual(completed.stdout.strip(), str(fake_python))
    def test_env_mcp_reconciles_stale_interpreter_path_with_resolved_python(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")

            codex_home = temp_root_path / "codex-home"
            calls_path = temp_root_path / "calls.jsonl"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)
            env = _cli_runtime_shell_environment(env)
            expected_python = self._expected_python_for_env(env)

            command = r'''
set -euo pipefail
temp_root="$1"
source_home="$2"
codex_home="$3"
source "$BUDDYSWITCH_PACKAGE_ROOT/foundation/cli_runtime/shell/env.sh"
export BUDDYSWITCH_SOURCE_HOME="${source_home}"
export BUDDYSWITCH_CODEX_HOME="${codex_home}"
export BUDDYSWITCH_CODEX_BIN="${temp_root}/bin/codex"
export BUDDYSWITCH_HOME="${temp_root}/home"
export BUDDYSWITCH_XDG_CONFIG_HOME="${temp_root}/xdg-config"
buddyswitch_env_init
export BUDDYSWITCH_ACTOR_ID="act-pm-env-stale-python"
export BUDDYSWITCH_ROLE_ID="pm"
export BUDDYSWITCH_INSTANCE_ROOT="${temp_root}/instance"
export BUDDYSWITCH_WORKSPACE_DIR="${BUDDYSWITCH_INSTANCE_ROOT}/workspace"
export BUDDYSWITCH_PROJECT_WORKSPACE_DIR="${PWD}"
export BUDDYSWITCH_INSTANCE_TMP="${BUDDYSWITCH_INSTANCE_ROOT}/tmp"
export BUDDYSWITCH_ACTOR_PRIVATE_DIR="${BUDDYSWITCH_WORKSPACE_DIR}/private"
export BUDDYSWITCH_RUNTIME_BROKER_SOCKET="${BUDDYSWITCH_INSTANCE_ROOT}/runtime/runtime-broker.sock"
mkdir -p "${BUDDYSWITCH_CODEX_HOME}" "${BUDDYSWITCH_HOME}" "${BUDDYSWITCH_XDG_CONFIG_HOME}" "${BUDDYSWITCH_INSTANCE_TMP}" "${BUDDYSWITCH_WORKSPACE_DIR}"
cat > "${BUDDYSWITCH_CODEX_HOME}/config.toml" <<EOF
[mcp_servers.buddyswitch-env]
command = "/stale/runtime/python"
args = ["-m", "buddyswitch.application.entrypoints.env_mcp", "--actor-id", "${BUDDYSWITCH_ACTOR_ID}", "--role", "${BUDDYSWITCH_ROLE_ID}", "--broker-socket", "${BUDDYSWITCH_RUNTIME_BROKER_SOCKET}"]
EOF
buddyswitch_env_mcp_ensure
'''
            completed = run_process(
                ["/bin/bash", "-c", command, "env-mcp-stale", str(temp_root_path), str(source_home_path), str(codex_home)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=f"stdout:\n{completed.stdout}\nstderr:\n{self._output_error_text(completed)}")
            call_entries = [
                json.loads(line)
                for line in calls_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertTrue(any(entry["argv"][:3] == ["mcp", "remove", "buddyswitch-env"] for entry in call_entries))
            env_mcp_add = next(entry for entry in call_entries if entry["argv"][:3] == ["mcp", "add", "buddyswitch-env"])
            self._assert_env_mcp_registration(
                env_mcp_add["argv"],
                expected_python=expected_python,
                actor_id="act-pm-env-stale-python",
                role="pm",
                broker_socket=f"{temp_root_path}/instance/runtime/runtime-broker.sock",
            )
    def test_browser_mcp_reconciles_stale_interpreter_path_with_resolved_python(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")

            codex_home = temp_root_path / "codex-home"
            calls_path = temp_root_path / "calls.jsonl"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)
            env = _cli_runtime_shell_environment(env)
            expected_python = self._expected_python_for_env(env)
            broker_socket = f"{temp_root_path}/instance/runtime/runtime-broker.sock"

            command = r'''
set -euo pipefail
temp_root="$1"
source_home="$2"
codex_home="$3"
source "$BUDDYSWITCH_PACKAGE_ROOT/foundation/cli_runtime/shell/env.sh"
source "$BUDDYSWITCH_PACKAGE_ROOT/foundation/cli_runtime/shell/browser_cockpit.sh"
export BUDDYSWITCH_SOURCE_HOME="${source_home}"
export BUDDYSWITCH_CODEX_HOME="${codex_home}"
export BUDDYSWITCH_CODEX_BIN="${temp_root}/bin/codex"
export BUDDYSWITCH_HOME="${temp_root}/home"
export BUDDYSWITCH_XDG_CONFIG_HOME="${temp_root}/xdg-config"
buddyswitch_env_init
export BUDDYSWITCH_ACTOR_ID="act-pm-browser-stale-python"
export BUDDYSWITCH_ROLE_ID="pm"
export BUDDYSWITCH_INSTANCE_ROOT="${temp_root}/instance"
export BUDDYSWITCH_WORKSPACE_DIR="${BUDDYSWITCH_INSTANCE_ROOT}/workspace"
export BUDDYSWITCH_PROJECT_WORKSPACE_DIR="${PWD}"
export BUDDYSWITCH_INSTANCE_TMP="${BUDDYSWITCH_INSTANCE_ROOT}/tmp"
export BUDDYSWITCH_ACTOR_PRIVATE_DIR="${BUDDYSWITCH_WORKSPACE_DIR}/private"
export BUDDYSWITCH_RUNTIME_BROKER_SOCKET="${BUDDYSWITCH_INSTANCE_ROOT}/runtime/runtime-broker.sock"
mkdir -p "${BUDDYSWITCH_CODEX_HOME}" "${BUDDYSWITCH_HOME}" "${BUDDYSWITCH_XDG_CONFIG_HOME}" "${BUDDYSWITCH_INSTANCE_TMP}" "${BUDDYSWITCH_WORKSPACE_DIR}"
buddyswitch_browser_init_defaults
cat > "${BUDDYSWITCH_CODEX_HOME}/config.toml" <<EOF
[mcp_servers.chrome-devtools-cockpit]
command = "/stale/runtime/python"
args = ["-m", "buddyswitch.application.entrypoints.browser_cockpit_proxy", "--upstream-command", "npx ${BUDDYSWITCH_BROWSER_COCKPIT_UPSTREAM_PACKAGE}", "--broker-socket", "${BUDDYSWITCH_RUNTIME_BROKER_SOCKET}", "--instance-root=${BUDDYSWITCH_INSTANCE_ROOT}"]
EOF
buddyswitch_browser_ensure_cockpit_mcp
'''
            completed = run_process(
                ["/bin/bash", "-c", command, "browser-mcp-stale", str(temp_root_path), str(source_home_path), str(codex_home)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=f"stdout:\n{completed.stdout}\nstderr:\n{self._output_error_text(completed)}")
            call_entries = [
                json.loads(line)
                for line in calls_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertTrue(any(entry["argv"][:3] == ["mcp", "remove", "chrome-devtools-cockpit"] for entry in call_entries))
            cockpit_add = next(entry for entry in call_entries if entry["argv"][:3] == ["mcp", "add", "chrome-devtools-cockpit"])
            self._assert_cockpit_proxy_registration(
                cockpit_add["argv"],
                temp_root_path / "instance",
                expected_python=expected_python,
                broker_socket=broker_socket,
            )
            config_text = (codex_home / "config.toml").read_text(encoding="utf-8")
            self.assertIn(f'command = "{expected_python}"', config_text)
            self.assertNotIn("/stale/runtime/python", config_text)
    def test_codex_config_patch_removes_prior_misnested_managed_settings_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            config_path = temp_root_path / "config.toml"
            config_path.write_text(
                """[skills.bundled]
enabled = false

[features]
plugins = false
# BuddySwitch managed automation permissions
sandbox_mode = "workspace-write"
approval_policy = { granular = {
  sandbox_approval = false,
  rules = false,
  mcp_elicitations = false,
  request_permissions = false,
  skill_approval = false,
} }

[mcp_servers.chrome-devtools-cockpit]
command = "npx"
args = ["chrome-devtools-mcp@latest", "--browser-url=http://127.0.0.1:9222"]

[mcp_servers.notion]
url = "https://mcp.notion.com/mcp"
default_tools_approval_mode = "ask"

[sandbox_workspace_write] # old managed table with an inline comment
network_access = false
writable_roots = ["/old"]
""",
                encoding="utf-8",
            )

            command = [
                PYTHON,
                "-m",
                "buddyswitch.application.entrypoints.actor_build",
                "patch-config",
                "--config",
                str(config_path),
                "--shared-root",
                str(shared_root),
                "--source-root",
                str(ROOT),
                "--temp-root",
                "/tmp",
            ]
            for _ in range(2):
                completed = run_process(
                    command,
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, msg=self._output_error_text(completed))

            config_text = config_path.read_text(encoding="utf-8")
            features_section = config_text.split("[features]", 1)[1].split("\n[", 1)[0]
            self._assert_codex_automation_config(config_text, shared_root=shared_root)
            self.assertEqual(config_text.count("# BuddySwitch managed automation permissions"), 1)
            self.assertNotIn("[sandbox_workspace_write] # old", config_text)
            self.assertNotIn("network_access = false", config_text)
            self.assertNotIn('writable_roots = ["/old"]', config_text)
            self.assertNotIn("sandbox_mode", features_section)
            self.assertNotIn("approval_policy", features_section)
            self.assertEqual(config_text.count('default_tools_approval_mode = "approve"'), 2)
            self.assertIn("[mcp_servers.chrome-devtools-cockpit]", config_text)
            self.assertIn("[mcp_servers.notion]", config_text)
            self.assertNotIn('default_tools_approval_mode = "ask"', config_text)
            self.assertNotIn("supports_parallel_tool_calls", config_text)
    def test_codex_config_patch_rejects_shared_root_that_grants_forbidden_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            source_codex_home = source_home_path / ".codex"
            source_codex_home.mkdir(parents=True)
            custom_codex_home = source_home_path / "custom-codex-home"
            custom_codex_home.mkdir()

            safe_shared_root = source_home_path / ".codex-buddyswitch"
            cases = (
                ("source-root", ROOT, []),
                ("source-root-child", ROOT / ".unsafe-buddyswitch-shared-root", []),
                ("source-codex-home", source_codex_home, []),
                ("custom-source-codex-home", custom_codex_home, ["--source-codex-home", str(custom_codex_home)]),
            )
            for label, shared_root, extra_args in cases:
                config_path = temp_root_path / f"{label}-config.toml"
                completed = run_process(
                    [
                        PYTHON,
                        "-m",
                        "buddyswitch.application.entrypoints.actor_build",
                        "patch-config",
                        "--config",
                        str(config_path),
                        "--shared-root",
                        str(shared_root),
                        "--source-root",
                        str(ROOT),
                        "--temp-root",
                        "/tmp",
                        *extra_args,
                    ],
                    cwd=ROOT,
                    env=_cli_runtime_shell_environment(
                        {**os.environ, "HOME": str(source_home_path)}
                    ),
                    text=True,
                    capture_output=True,
                    check=False,
                )

                self.assertEqual(completed.returncode, 2)
                self.assertIn("refusing writable root", self._output_error_text(completed))
                self.assertFalse(config_path.exists())
    def test_codex_config_patch_skips_unsafe_temp_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            custom_codex_home = source_home_path / "custom-codex-home"
            custom_codex_home.mkdir()
            config_path = temp_root_path / "config.toml"

            completed = run_process(
                [
                    PYTHON,
                    "-m",
                    "buddyswitch.application.entrypoints.actor_build",
                    "patch-config",
                    "--config",
                    str(config_path),
                    "--shared-root",
                    str(shared_root),
                    "--source-codex-home",
                    str(custom_codex_home),
                    "--source-root",
                    str(ROOT),
                    "--temp-root",
                    "/tmp",
                    "--temp-root",
                    str(ROOT),
                    "--temp-root",
                    str(custom_codex_home),
                    "--temp-root",
                    str(ROOT / "projects" / "app" / ".runtime"),
                ],
                cwd=ROOT,
                env=_cli_runtime_shell_environment(
                    {**os.environ, "HOME": str(source_home_path)}
                ),
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=self._output_error_text(completed))
            config_text = config_path.read_text(encoding="utf-8")
            self._assert_codex_automation_config(config_text, shared_root=shared_root)
            self.assertNotIn(str(ROOT.resolve(strict=False)), config_text.replace(str(self._repo_git_common_dir()), ""))
            self.assertNotIn(str(custom_codex_home.resolve(strict=False)), config_text)
            self.assertNotIn(str((ROOT / "projects" / "app" / ".runtime").resolve(strict=False)), config_text)
