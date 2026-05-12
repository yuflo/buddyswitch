#!/usr/bin/env python3
"""Cross-tool identity spoofing tests for broker-routed env.tool operations."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402
from tests.test_market_browser_evidence import MARKET_REQUEST  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v1"


def _pm_result() -> dict[str, object]:
    return {
        "execution_summary": "PM wrote a compact PRD for identity validation.",
        "working_notes": ["Result validation should use prepared runtime identity, not payload-authored identity fields."],
    }


class EnvToolIdentityTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(
        self,
        *,
        instance_id: str,
        buddy: str,
        current_task_id: str | None = None,
        current_track_id: str | None = None,
        browser_port: int | None = None,
    ) -> Path:
        path = self._runtime_path(f"{instance_id}.json")
        path.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": "active",
                    "current_task_id": current_task_id,
                    "current_track_id": current_track_id,
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": browser_port,
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

    def _dispatch(
        self,
        *,
        tool: str,
        action: str,
        args: dict[str, object],
        instance_json: Path,
        instance_id: str,
        buddy: str,
    ) -> dict[str, object]:
        return runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "instance_id": instance_id,
                "active_buddy": buddy,
                "method": "env.tool",
                "payload": {"tool": tool, "action": action, "args": args},
            },
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )

    def _prepare(self, *, text: str, instance_json: Path, instance_id: str, buddy: str) -> dict[str, object]:
        response = runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "instance_id": instance_id,
                "active_buddy": buddy,
                "method": "prepare",
                "payload": {"text": text},
            },
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )
        self.assertTrue(response.get("ok"), msg=response)
        payload = response.get("payload")
        self.assertIsInstance(payload, dict, msg=response)
        assert isinstance(payload, dict)
        return payload

    def _seed_run_reservation(self, *, run_id: str, task_id: str, buddy: str, instance_id: str) -> None:
        path = self._runtime_path(f"buddyswitch/content/runs/reserved/{run_id}.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "status": "reserved",
                    "context_revision": f"ctx-{task_id}-turn-1",
                    "sequence": 1,
                    "task_id": task_id,
                    "instance_id": instance_id,
                    "turn_identity": {
                        "instance_id": instance_id,
                        "active_buddy": buddy,
                        "task_id": task_id,
                        "track_id": None,
                        "context_revision": f"ctx-{task_id}-turn-1",
                        "sequence": 1,
                        "run_id": run_id,
                    },
                    "reserved_at": "2026-05-11T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def test_payload_identity_fields_do_not_override_task_track_artifact_or_binding_identity(self) -> None:
        dev_instance_id = "inst-dev-identity"
        dev_instance = self._instance_json(instance_id=dev_instance_id, buddy="dev")

        created_task = self._dispatch(
            tool="task",
            action="create",
            args={
                "task_id": "task-dev-identity",
                "title": "Dev Identity Task",
                "summary": "payload tries to spoof PM",
                "buddy": "pm",
                "active_buddy": "pm",
            },
            instance_json=dev_instance,
            instance_id=dev_instance_id,
            buddy="dev",
        )
        self.assertTrue(created_task.get("ok"), msg=created_task)
        self.assertEqual(created_task.get("active_buddy"), "dev")
        task = env_store.get_task("task-dev-identity")
        self.assertIsNotNone(task)
        assert task is not None
        self.assertEqual(task["buddy"], "dev")

        bound = self._dispatch(
            tool="binding",
            action="set_task",
            args={"task_id": "task-dev-identity", "active_buddy": "pm", "instance_id": "inst-pm-spoof"},
            instance_json=dev_instance,
            instance_id=dev_instance_id,
            buddy="dev",
        )
        self.assertTrue(bound.get("ok"), msg=bound)
        current_binding = bound.get("current_binding")
        self.assertIsInstance(current_binding, dict, msg=bound)
        assert isinstance(current_binding, dict)
        self.assertEqual(current_binding["instance_id"], dev_instance_id)
        self.assertEqual(current_binding["active_buddy"], "dev")

        self._seed_run_reservation(
            run_id="run-dev-identity",
            task_id="task-dev-identity",
            buddy="dev",
            instance_id=dev_instance_id,
        )
        artifact = self._dispatch(
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-dev-identity-report",
                "task_id": "task-dev-identity",
                "kind": "implementation-report",
                "title": "Identity Report",
                "summary": "spoofed identity fields are ignored",
                "content": {"result": "dev-owned"},
                "source_run_id": "run-dev-identity",
                "buddy": "pm",
                "active_buddy": "pm",
                "instance_id": "inst-pm-spoof",
            },
            instance_json=dev_instance,
            instance_id=dev_instance_id,
            buddy="dev",
        )
        self.assertTrue(artifact.get("ok"), msg=artifact)
        stored_artifact = env_store.get_artifact("art-dev-identity-report")
        self.assertIsNotNone(stored_artifact)
        assert stored_artifact is not None
        self.assertEqual(stored_artifact["buddy"], "dev")

        pm_instance_id = "inst-pm-identity"
        pm_instance = self._instance_json(instance_id=pm_instance_id, buddy="pm")
        created_track = self._dispatch(
            tool="track",
            action="create",
            args={
                "track_id": "track-identity",
                "title": "Identity Track",
                "active_buddy": "dev",
                "buddy": "dev",
                "instance_id": "inst-dev-spoof",
            },
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            buddy="pm",
        )
        self.assertTrue(created_track.get("ok"), msg=created_track)
        self.assertEqual(created_track.get("active_buddy"), "pm")
        track = env_store.get_track("track-identity")
        self.assertIsNotNone(track)
        assert track is not None
        self.assertEqual(track["current_buddy"], "pm")

    def test_run_and_evidence_tools_use_prepared_runtime_identity_not_payload_authored_identity(self) -> None:
        pm_instance_id = "inst-pm-run-identity"
        pm_instance = self._instance_json(instance_id=pm_instance_id, buddy="pm")
        pm_context = self._prepare(
            text="Write the identity contract PRD.",
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            buddy="pm",
        )
        validated = self._dispatch(
            tool="run",
            action="validate_result",
            args={"context": pm_context, "result": _pm_result(), "active_buddy": "dev", "instance_id": "inst-dev-spoof"},
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            buddy="pm",
        )
        self.assertTrue(validated.get("ok"), msg=validated)
        self.assertEqual(validated.get("active_buddy"), "pm")
        self.assertEqual(validated.get("run_id"), pm_context["run_envelope"]["run_id"])

        market_instance_id = "inst-market-evidence-identity"
        market_instance = self._instance_json(instance_id=market_instance_id, buddy="market")
        market_context = self._prepare(
            text=MARKET_REQUEST,
            instance_json=market_instance,
            instance_id=market_instance_id,
            buddy="market",
        )
        evidence = self._dispatch(
            tool="evidence",
            action="approve_downgrade",
            args={
                "context": market_context,
                "reason": "User approved text-only fallback for identity test.",
                "active_buddy": "pm",
                "instance_id": "inst-pm-spoof",
            },
            instance_json=market_instance,
            instance_id=market_instance_id,
            buddy="market",
        )
        self.assertTrue(evidence.get("ok"), msg=evidence)
        self.assertEqual(evidence.get("active_buddy"), "market")
        self.assertEqual(evidence["feedback"]["token_scope"]["instance_id"], market_instance_id)
        self.assertEqual(evidence["feedback"]["token_scope"]["buddy_id"], "market")


if __name__ == "__main__":
    unittest.main()
