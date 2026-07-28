from __future__ import annotations

import json
import os
import signal
import subprocess
import tempfile
import unittest
from pathlib import Path

from buddyswitch.launcher import central_daemon_core
from tests.system.support.launcher import SystemLauncherHarness
from tests.support.paths import REPO_ROOT


LAUNCHER = REPO_ROOT / "buddyswitch-codex"


class TestWebCommandLifecycle(SystemLauncherHarness, unittest.TestCase):
    def test_web_command_sigint_keeps_stdout_single_line_and_stops_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            port = self._first_available_local_port(18865)
            env = os.environ.copy()
            env["HOME"] = source_home
            env.pop("CODEX_HOME", None)
            central_paths = central_daemon_core.central_daemon_paths(shared_root)
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
                self._ledger.reconcile_descriptors()
                central_daemon_pids = self._registered_central_daemon_pids(shared_root)
                self.assertTrue(
                    central_daemon_pids,
                    "web command should start a registered central daemon",
                )

                os.killpg(pgid, signal.SIGINT)
                proc.wait(timeout=8)

                self.assertEqual(
                    self._read_available_process_lines(proc, stream_name="stdout"),
                    [],
                )
                self.assertFalse(self._process_group_has_live_member(pgid))
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
                for pid in self._registered_central_daemon_pids(shared_root):
                    self._terminate_registered_process(pid)
                if proc.stdout is not None:
                    proc.stdout.close()
                if proc.stderr is not None:
                    proc.stderr.close()
