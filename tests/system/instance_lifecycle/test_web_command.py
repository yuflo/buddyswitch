from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path

from buddyswitch.foundation.daemon import central_service
from buddyswitch.foundation.process_runtime import process_identity
from tests.system.support.launcher import SystemLauncherHarness
from tests.support.paths import REPO_ROOT


LAUNCHER = REPO_ROOT / "buddyswitch-codex"


class TestWebCommandLifecycle(SystemLauncherHarness, unittest.TestCase):
    @staticmethod
    def _direct_child_processes(parent_pid: int) -> list[tuple[int, int, str]]:
        completed = subprocess.run(
            ["ps", "-axo", "pid=,ppid=,pgid=,stat=,command="],
            text=True,
            capture_output=True,
            check=True,
        )
        children: list[tuple[int, int, str]] = []
        for line in completed.stdout.splitlines():
            fields = line.strip().split(maxsplit=4)
            if len(fields) != 5 or not fields[0].isdigit() or not fields[1].isdigit():
                continue
            if int(fields[1]) != parent_pid or fields[3].startswith("Z"):
                continue
            children.append((int(fields[0]), int(fields[2]), fields[4]))
        return children

    def _register_web_child(
        self,
        proc: subprocess.Popen[str],
        *,
        parent_pgid: int,
    ) -> tuple[int, int]:
        web_children = [
            child
            for child in self._direct_child_processes(proc.pid)
            if "buddyswitch.application.entrypoints.web" in child[2]
        ]
        self.assertEqual(len(web_children), 1, msg=web_children)
        child_pid, child_pgid, child_command = web_children[0]
        self.assertEqual(child_pgid, child_pid)
        self.assertNotEqual(child_pgid, parent_pgid)
        child_identity = process_identity.start_identity(child_pid)
        self.assertIsNotNone(child_identity)
        self._ledger.register_process(
            pid=child_pid,
            pgid=child_pgid,
            start_identity=str(child_identity),
            command=[child_command],
            cleanup_strategy="terminate_owned_pgid",
            cleanup_args={},
        )
        return child_pid, child_pgid

    def test_web_command_sigint_keeps_stdout_single_line_and_stops_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            port = self._first_available_local_port(18865)
            env = os.environ.copy()
            env["HOME"] = source_home
            env.pop("CODEX_HOME", None)
            central_paths = central_service.central_daemon_paths(shared_root)
            self._ledger.register_process_descriptor(
                pid_file=central_paths.pid_file,
                cleanup_strategy="central_daemon_stop",
                cleanup_args={"shared_root": str(shared_root)},
                command=["central-daemon"],
                owned_paths={
                    "pid": central_paths.pid_file,
                    "pid_identity": central_paths.pid_identity_file,
                    "socket": central_paths.socket_path,
                },
            )
            proc = self._ledger.start_process(
                [str(LAUNCHER), "web", "--host", "127.0.0.1", "--port", str(port)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            pgid = os.getpgid(proc.pid)
            web_child_pid: int | None = None
            web_child_pgid: int | None = None
            try:
                line = self._read_process_line(proc, timeout_seconds=8.0)
                if not line.endswith("\n"):
                    self.fail(
                        "web command emitted no ready line; "
                        f"returncode={proc.poll()!r}, "
                        f"stderr={self._read_available_process_lines(proc, stream_name='stderr')!r}"
                    )
                self.assertNotIn("listening", line.lower())
                payload = json.loads(line)
                self.assertEqual(payload["ok"], True)
                self.assertEqual(payload["kind"], "web.ready")
                self.assertEqual(
                    payload["data"],
                    {"url": f"http://127.0.0.1:{port}"},
                )
                diagnostic = self._read_process_line(
                    proc,
                    stream_name="stderr",
                    timeout_seconds=8.0,
                )
                self.assertIn("BuddySwitch web management listening on", diagnostic)
                self.assertIn(f"http://127.0.0.1:{port}", diagnostic)
                web_child_pid, web_child_pgid = self._register_web_child(
                    proc,
                    parent_pgid=pgid,
                )
                self._ledger.reconcile_descriptors()
                central_daemon_pids = self._registered_central_daemon_pids(shared_root)
                self.assertTrue(
                    central_daemon_pids,
                    "web command should start a registered central daemon",
                )

                os.killpg(pgid, signal.SIGINT)
                proc.wait(timeout=8)

                stderr_lines = self._read_available_process_lines(
                    proc,
                    stream_name="stderr",
                )

                self.assertEqual(proc.returncode, 0, msg="".join(stderr_lines))
                self.assertEqual(
                    self._read_available_process_lines(proc, stream_name="stdout"),
                    [],
                )
                self.assertNotIn("Traceback", "".join(stderr_lines))
                self.assertNotIn("KeyboardInterrupt", "".join(stderr_lines))
                self.assertFalse(self._process_group_has_live_member(pgid))
                self.assertFalse(self._pid_is_live(web_child_pid))
                self.assertFalse(self._process_group_has_live_member(web_child_pgid))
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as released:
                    released.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    released.bind(("127.0.0.1", port))
                for pid in central_daemon_pids:
                    self.assertFalse(
                        self._pid_is_live(pid),
                        f"central daemon pid should stop after web SIGINT: {pid}",
                    )
            finally:
                if proc.poll() is None:
                    try:
                        os.killpg(pgid, signal.SIGTERM)
                    except OSError:
                        proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        try:
                            os.killpg(pgid, signal.SIGKILL)
                        except OSError:
                            proc.kill()
                        proc.wait(timeout=5)
                if web_child_pid is not None and self._pid_is_live(web_child_pid):
                    self._terminate_registered_process(web_child_pid, web_child_pgid)
                for pid in self._registered_central_daemon_pids(shared_root):
                    self._terminate_registered_process(pid)
                if proc.stdout is not None:
                    proc.stdout.close()
                if proc.stderr is not None:
                    proc.stderr.close()

    def test_web_command_sigterm_stops_detached_child_and_releases_port(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            port = self._first_available_local_port(18915)
            env = os.environ.copy()
            env["HOME"] = source_home
            env.pop("CODEX_HOME", None)
            central_paths = central_service.central_daemon_paths(shared_root)
            self._ledger.register_process_descriptor(
                pid_file=central_paths.pid_file,
                cleanup_strategy="central_daemon_stop",
                cleanup_args={"shared_root": str(shared_root)},
                command=["central-daemon"],
                owned_paths={
                    "pid": central_paths.pid_file,
                    "pid_identity": central_paths.pid_identity_file,
                    "socket": central_paths.socket_path,
                },
            )
            proc = self._ledger.start_process(
                [str(LAUNCHER), "web", "--host", "127.0.0.1", "--port", str(port)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            pgid = os.getpgid(proc.pid)
            web_child_pid: int | None = None
            web_child_pgid: int | None = None
            try:
                ready_line = self._read_process_line(proc, timeout_seconds=8.0)
                self.assertEqual(json.loads(ready_line)["kind"], "web.ready")
                diagnostic = self._read_process_line(
                    proc,
                    stream_name="stderr",
                    timeout_seconds=8.0,
                )
                self.assertIn(f"http://127.0.0.1:{port}", diagnostic)
                web_child_pid, web_child_pgid = self._register_web_child(
                    proc,
                    parent_pgid=pgid,
                )
                self._ledger.reconcile_descriptors()
                central_daemon_pids = self._registered_central_daemon_pids(shared_root)
                self.assertTrue(central_daemon_pids)

                os.killpg(pgid, signal.SIGTERM)
                proc.wait(timeout=8)

                self.assertFalse(self._process_group_has_live_member(pgid))
                self.assertFalse(self._pid_is_live(web_child_pid))
                self.assertFalse(self._process_group_has_live_member(web_child_pgid))
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as released:
                    released.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    released.bind(("127.0.0.1", port))
                for pid in central_daemon_pids:
                    self.assertFalse(
                        self._pid_is_live(pid),
                        f"central daemon pid should stop after web SIGTERM: {pid}",
                    )
            finally:
                if proc.poll() is None:
                    try:
                        os.killpg(pgid, signal.SIGKILL)
                    except OSError:
                        proc.kill()
                    proc.wait(timeout=5)
                if web_child_pid is not None and self._pid_is_live(web_child_pid):
                    self._terminate_registered_process(web_child_pid, web_child_pgid)
                for pid in self._registered_central_daemon_pids(shared_root):
                    self._terminate_registered_process(pid)
                if proc.stdout is not None:
                    proc.stdout.close()
                if proc.stderr is not None:
                    proc.stderr.close()
