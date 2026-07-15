"""Child-process proof that expiry closes one exact Chrome target."""

from tests.integration.browser.cdp_lifecycle_harness import *  # noqa: F401,F403


class TestPageExpiredTargetTransport(CdpBrowserLifecycleHarness):
    def test_handler_child_closes_exact_target_without_mcp_session(self) -> None:
        cdp_state: dict[str, object] = {
            "targets": [
                {"targetId": "target-expired", "type": "page", "url": "https://example.com/expired"},
                {"targetId": "target-survivor", "type": "page", "url": "https://example.com/survivor"},
            ]
        }
        browser_url = _start_cdp_browser_server(self, cdp_state)
        port = urlparse(browser_url).port
        assert port is not None

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"
            instance_root.mkdir(parents=True)
            instance_json = instance_root / "instance.json"
            instance_json.write_text(
                json.dumps({"actor_id": "act-browser", "role": "dev", "browser_port": port}) + "\n",
                encoding="utf-8",
            )
            self.lifecycle._write_page_idle_state(
                instance_root,
                {
                    "targets": {
                        "target-expired": {
                            "tab_target_id": "target-expired",
                            "last_used_at": "2026-07-15T00:00:00Z",
                            "idle_seconds": 40,
                        },
                        "target-survivor": {
                            "tab_target_id": "target-survivor",
                            "last_used_at": "2026-07-15T00:00:00Z",
                            "idle_seconds": 40,
                        },
                    }
                },
            )
            script = """
import json
from pathlib import Path
from types import SimpleNamespace
import sys

repo_root = Path(sys.argv[1])
instance_root = Path(sys.argv[2])
sys.path[:0] = [str(repo_root / "tools" / "launcher"), str(repo_root / "scripts"), str(repo_root / "scripts" / "env")]

from browser_page_expired_handler import BrowserPageExpiredHandler

context = SimpleNamespace(
    actor_id="act-browser",
    role="dev",
    instance_root=instance_root,
    instance_json=instance_root / "instance.json",
    instance_payload={},
)
trigger = SimpleNamespace(
    type="browser.page.expired",
    target_identity_id="act-browser",
    target_role_id="dev",
    payload={"tab_target_id": "target-expired", "idle_seconds": 40},
    source_context={"due_at": "2026-07-15T00:01:00Z"},
)
runtime = SimpleNamespace(parent_activity=lambda: {"status": "idle"})
result = BrowserPageExpiredHandler().handle(context, None, runtime, trigger)
print(json.dumps({"status": result.status, "message": result.message}))
"""
            completed = run_process(
                [PYTHON, "-c", script, str(ROOT), str(instance_root)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertEqual(json.loads(completed.stdout)["status"], "handled")
            state = json.loads(self.lifecycle.page_idle_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(list(state["targets"]), ["target-survivor"])
            self.assertEqual(
                [request["method"] for request in cdp_state.get("rpc_requests", [])],
                ["Target.getTargets", "Target.closeTarget", "Target.getTargets"],
            )
