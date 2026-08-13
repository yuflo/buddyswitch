"""System-tier launcher lifecycle and cleanup test support."""

from __future__ import annotations

from contextlib import ExitStack
import json
import os
import select
import socket
import subprocess
import time
from pathlib import Path

import buddyswitch.foundation.app_server.runtime as app_server
from buddyswitch.foundation.daemon import central_service
from buddyswitch.foundation.daemon import instance
from buddyswitch.foundation.daemon import mailbox
import buddyswitch.foundation.process_runtime.process_identity as process_identity
from buddyswitch.foundation.runtime_broker import lifecycle
from tests.support.launcher import LauncherTestSupport
from tests.support.paths import REPO_ROOT
from tests.support.processes import run_process

ROOT = REPO_ROOT
LAUNCHER = ROOT / "buddyswitch-codex"


class SystemLauncherHarness(LauncherTestSupport):
    _PM_PRODUCT_SKILLS = (
        "read-product-context",
        "synthesize-cross-functional-inputs",
        "frame-product-direction",
        "define-scope",
        "write-requirements",
        "write-acceptance-criteria",
        "make-product-decision",
        "decide-from-proof",
        "triage-track",
        "sequence-product-work",
    )

    @staticmethod
    def _first_available_local_port(start: int, *, limit: int = 50) -> int:
        for port in range(start, start + limit):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    probe.bind(("127.0.0.1", port))
                except OSError:
                    continue
                return port
        raise AssertionError(f"no available localhost TCP port found from {start}")

    def _start_service_instance(
        self,
        temp_root_path: Path,
        source_home_path: Path,
        *,
        cleanup_stack: ExitStack,
        role: str = "pm",
        state_payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        source_codex_home = source_home_path / ".codex"
        source_codex_home.mkdir(parents=True, exist_ok=True)
        (source_codex_home / "auth.json").write_text(
            json.dumps(
                {
                    "auth_mode": "apikey",
                    "openai_api_key": "test-key",
                    "tokens": None,
                    "last_refresh": None,
                    "agent_identity": None,
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        fake_bin = temp_root_path / "bin"
        fake_bin.mkdir(parents=True, exist_ok=True)
        self._write_fake_codex(fake_bin / "codex")
        self._write_fake_curl(fake_bin / "curl")
        self._write_fake_chrome(fake_bin / "fake-chrome")

        capture_path = temp_root_path / "capture.json"
        calls_path = temp_root_path / "calls.jsonl"
        state_file = temp_root_path / "app-server-state.json"
        if state_payload is not None:
            state_file.write_text(json.dumps(state_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

        env = os.environ.copy()
        env["HOME"] = str(source_home_path)
        env.pop("CODEX_HOME", None)
        env.pop("BUDDYSWITCH_SHARED_ROOT", None)
        env.pop("BUDDYSWITCH_STATE_ROOT", None)
        env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
        env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
        env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(temp_root_path / "browser-ready.flag")
        env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)
        env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)
        env["BUDDYSWITCH_TEST_APP_SERVER_STATE_FILE"] = str(state_file)

        shared_root = source_home_path / ".codex-buddyswitch"
        central_paths = central_service.central_daemon_paths(shared_root)
        central_descriptor_id = self._ledger.register_process_descriptor(
            pid_file=central_paths.pid_file,
            cleanup_strategy="central_daemon_stop",
            cleanup_args={"shared_root": str(shared_root)},
            command=["central-daemon", "serve"],
            owned_paths={
                "pid": central_paths.pid_file,
                "pid_identity": central_paths.pid_identity_file,
                "socket": central_paths.socket_path,
            },
        )
        cleanup_stack.callback(
            self._cleanup_process_descriptor,
            central_descriptor_id,
        )

        completed = run_process(
            [str(LAUNCHER), "instance", "start", "--role", role],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        if not capture_path.is_file():
            raise AssertionError(
                "instance start exited before fake Codex capture"
                f"\nreturncode: {completed.returncode}"
                f"\nstdout:\n{completed.stdout}"
                f"\nstderr:\n{completed.stderr}"
            )
        payload = json.loads(capture_path.read_text(encoding="utf-8"))
        actor_id = payload["actor_id"]
        instance_root = shared_root / "instances" / actor_id
        instance_payload = json.loads((instance_root / "instance.json").read_text(encoding="utf-8"))

        app_pid = app_server.pid_file(instance_root)
        app_marker = app_server.marker_file(instance_root)
        app_socket = app_server.effective_socket_path(actor_id, instance_root, app_marker)
        app_descriptor_id = self._ledger.register_process_descriptor(
            pid_file=app_pid,
            cleanup_strategy="app_server_stop",
            cleanup_args={
                "socket_path": str(app_socket),
                "pid_file": str(app_pid),
                "marker_file": str(app_marker),
                "log_file": str(app_server.log_file(instance_root)),
            },
            command=["codex", "app-server"],
            owned_paths={
                "pid": app_pid,
                "pid_identity": process_identity.identity_file(app_pid),
                "socket": app_socket,
                "marker": app_marker,
            },
        )
        cleanup_stack.callback(self._cleanup_process_descriptor, app_descriptor_id)

        runtime_dir = instance_root / "runtime"
        broker_pid = runtime_dir / "runtime-broker.pid"
        broker_marker = runtime_dir / "runtime-broker.socket"
        broker_paths = lifecycle.BrokerPaths(
            socket_path=lifecycle.resolve_socket_path(actor_id, instance_root, broker_marker),
            pid_file=broker_pid,
            marker_file=broker_marker,
            log_file=runtime_dir / "runtime-broker.log",
        )
        broker_descriptor_id = self._ledger.register_process_descriptor(
            pid_file=broker_pid,
            cleanup_strategy="runtime_broker_stop",
            cleanup_args={
                "socket_path": str(broker_paths.socket_path),
                "pid_file": str(broker_paths.pid_file),
                "marker_file": str(broker_paths.marker_file),
                "log_file": str(broker_paths.log_file),
            },
            command=["runtime-broker", "serve"],
            owned_paths={
                "pid": broker_pid,
                "pid_identity": process_identity.identity_file(broker_pid),
                "socket": broker_paths.socket_path,
                "marker": broker_marker,
            },
        )
        cleanup_stack.callback(self._cleanup_process_descriptor, broker_descriptor_id)

        daemon_pid_path = instance.daemon_pid_file(instance_root)
        daemon_descriptor_id = self._ledger.register_process_descriptor(
            pid_file=daemon_pid_path,
            cleanup_strategy="instance_daemon_stop",
            cleanup_args={"instance_json": str(instance_root / "instance.json")},
            command=["instance-daemon", "run"],
            owned_paths={
                "pid": daemon_pid_path,
                "pid_identity": process_identity.identity_file(daemon_pid_path),
                "socket": mailbox.mailbox_socket_path(instance_root),
            },
        )
        cleanup_stack.callback(self._cleanup_process_descriptor, daemon_descriptor_id)
        browser_pid = instance_root / "browser" / "chrome.pid"
        browser_descriptor_id = self._ledger.register_process_descriptor(
            pid_file=browser_pid,
            cleanup_strategy="browser_stop",
            cleanup_args={"instance_root": str(instance_root), "actor_id": actor_id},
            command=[str(fake_bin / "fake-chrome")],
            owned_paths={
                "pid": browser_pid,
                "pid_identity": process_identity.identity_file(browser_pid),
                "profile": instance_root / "browser" / "profile",
            },
        )
        cleanup_stack.callback(self._cleanup_process_descriptor, browser_descriptor_id)
        self._ledger.reconcile_descriptors()

        return {
            "completed": completed,
            "env": env,
            "capture_path": capture_path,
            "calls_path": calls_path,
            "state_file": state_file,
            "payload": payload,
            "shared_root": shared_root,
            "actor_id": actor_id,
            "instance_root": instance_root,
            "instance_payload": instance_payload,
        }

    def _stop_service_instance(self, ctx: dict[str, object]) -> None:
        completed = run_process(
            [str(LAUNCHER), "instance", "stop", str(ctx["actor_id"])],
            cwd=ROOT,
            env=ctx["env"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            msg=self._output_error_text(completed),
        )

    def _reset_service_environment(self, ctx: dict[str, object]) -> None:
        completed = run_process(
            [str(LAUNCHER), "env", "reset", "--yes"],
            cwd=ROOT,
            env=ctx["env"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            msg=self._output_error_text(completed),
        )

    @staticmethod
    def _read_json_lines(path: Path) -> list[dict[str, object]]:
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _read_process_line(
        self,
        proc: subprocess.Popen[str],
        *,
        stream_name: str = "stdout",
        timeout_seconds: float = 5.0,
    ) -> str:
        stream = getattr(proc, stream_name)
        self.assertIsNotNone(stream)
        assert stream is not None
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            readable, _, _ = select.select([stream], [], [], 0.05)
            if readable:
                return stream.readline()
            if proc.poll() is not None:
                return stream.readline()
        stderr = ""
        if proc.stderr is not None:
            readable, _, _ = select.select([proc.stderr], [], [], 0)
            if readable:
                stderr = proc.stderr.read()
        self.fail(
            f"process did not emit a {stream_name} line within {timeout_seconds}s; "
            f"returncode={proc.poll()} stderr={stderr}"
        )

    def _read_available_process_lines(self, proc: subprocess.Popen[str], *, stream_name: str) -> list[str]:
        stream = getattr(proc, stream_name)
        if stream is None:
            return []
        lines: list[str] = []
        while True:
            readable, _, _ = select.select([stream], [], [], 0.05)
            if not readable:
                return lines
            line = stream.readline()
            if not line:
                return lines
            lines.append(line)

    @staticmethod
    def _process_group_has_live_member(pgid: int) -> bool:
        try:
            os.killpg(pgid, 0)
        except OSError:
            return False
        return True

    def _registered_central_daemon_pids(self, shared_root: Path) -> list[int]:
        pid_path = shared_root / "run" / "central-daemon" / "central-daemon.pid"
        try:
            pid = int(pid_path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return []
        return [pid] if pid > 0 else []

    def _read_rpc_rows(self, path: Path) -> list[dict[str, object]]:
        return [row for row in self._read_json_lines(path) if row["argv"][:1] == ["json-rpc"]]

    def _assert_runtime_workspace_excludes_source_surfaces(self, workspace_dir: Path) -> None:
        for relative_path in (
            "buddyswitch/roles",
            "tools",
            "tests",
            "docs",
            "README.md",
            "buddyswitch-codex",
        ):
            candidate = workspace_dir / relative_path
            self.assertFalse(
                candidate.exists() or candidate.is_symlink(),
                msg=f"runtime workspace must not expose source surface: {relative_path}",
            )

    def _assert_pm_runtime_shape(self, workspace_dir: Path, shared_root: Path) -> None:
        self.assertEqual(
            {path.name for path in workspace_dir.iterdir()},
            {".agents", "AGENTS.md", "private", "projects"},
        )
        self._assert_pm_runtime_skills(workspace_dir)

        self.assertEqual(
            (workspace_dir / "projects" / "app").resolve(strict=True),
            (shared_root / "project" / "workspace" / "projects" / "app").resolve(strict=True),
        )

        self.assertFalse((workspace_dir / "buddyswitch" / "objects").exists())
        self.assertFalse((workspace_dir / "buddyswitch" / "objects").is_symlink())
        self.assertTrue((workspace_dir / "private").is_dir())
        self.assertFalse((workspace_dir / "buddyswitch" / "local" / "private" / "pm").exists())
        self.assertFalse((workspace_dir / "buddyswitch" / "local" / "private" / "pm").is_symlink())

    def _assert_pm_runtime_skills(self, workspace_dir: Path) -> None:
        runtime_skills = workspace_dir / ".agents" / "skills"
        for skill_id in self._PM_PRODUCT_SKILLS:
            self.assertTrue((runtime_skills / skill_id / "SKILL.md").exists(), msg=skill_id)
        self.assertTrue((runtime_skills / "demand-orchestration" / "SKILL.md").exists())
        self.assertTrue((runtime_skills / "track-tool" / "SKILL.md").exists())
        self.assertTrue((runtime_skills / "artifact-tool" / "SKILL.md").exists())
        self.assertFalse((runtime_skills / "write-prd").exists())
        self.assertFalse((runtime_skills / "write-prd" / "assets" / "prd-template.md").exists())
