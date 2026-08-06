from tests.integration.browser.cdp_lifecycle_harness import *  # noqa: F401,F403


class TestCdpPageLocking(CdpBrowserLifecycleHarness):
    def test_forget_target_waits_for_page_idle_state_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"
            self.lifecycle._write_page_idle_state(
                instance_root,
                {
                    "active_tab_target_id": "target-lock-wait",
                    "targets": {
                        "target-lock-wait": {
                            "tab_target_id": "target-lock-wait",
                            "last_used_at": "2026-07-15T00:00:00Z",
                            "idle_seconds": 40,
                        }
                    },
                },
            )
            lock_path = instance_root / "runtime" / "browser" / "page_idle.lock"
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_file = lock_path.open("a+", encoding="utf-8")
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            script = """
from pathlib import Path

import sys

instance_root = Path(sys.argv[2])

from buddyswitch.foundation.browser_runtime import lifecycle

lifecycle.forget_tab_idle_target(
    instance_root=instance_root,
    tab_target_id="target-lock-wait",
)
print("done", flush=True)
"""
            process = ResourceLedger.from_environment().start_process(
                [PYTHON, "-c", script, str(ROOT), str(instance_root)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    process.communicate(timeout=0.25)
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                stdout, stderr = process.communicate(timeout=2)
                self.assertEqual(process.returncode, 0, msg=stderr)
                self.assertIn("done", stdout)
            finally:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass
                lock_file.close()
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=2)

            state = json.loads(self.lifecycle.page_idle_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(state, {"targets": {}})
