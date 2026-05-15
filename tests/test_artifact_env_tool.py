#!/usr/bin/env python3
"""Runless artifact env.tool integration tests."""

from __future__ import annotations

import json
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class ArtifactEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(self, *, instance_id: str, buddy: str, status: str = "active") -> Path:
        path = self._runtime_path("instance.json")
        path.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": status,
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "updated_at": "2026-05-15T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def _dispatch(self, *, instance_json: Path, instance_id: str, buddy: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        request = {
            "protocol": PROTOCOL,
            "request_id": f"req-art-{uuid.uuid4().hex}",
            "method": "env.tool",
            "params": {
                "instance_id": instance_id,
                "active_buddy": buddy,
                "tool": tool,
                "action": action,
                "args": args,
            },
            "deadline_ms": 35000,
        }
        envelope = runtime_broker.dispatch_runtime_request(
            request=request,
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )
        self.assertIsInstance(envelope, dict)
        assert isinstance(envelope, dict)
        self.assertEqual(envelope.get("protocol"), PROTOCOL)
        if envelope.get("ok") is True:
            result = envelope.get("result")
            self.assertIsInstance(result, dict, msg=envelope)
            assert isinstance(result, dict)
            return result
        error = envelope.get("error") if isinstance(envelope.get("error"), dict) else {}
        payload: dict[str, object] = {
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

    def _seed_pm_track_and_task(self) -> None:
        env_store.create_track("track-artifact-runless", "Artifact Track", current_buddy="pm")
        env_store.create_task("task-pm-artifact", "Artifact Task", buddy="pm", track_id="track-artifact-runless", summary="seed")

    def test_create_revision_requires_explicit_task_id(self) -> None:
        instance_json = self._instance_json(instance_id="inst-pm-art", buddy="pm")
        self._seed_pm_track_and_task()

        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={"kind": "prd", "title": "Missing Task", "summary": "bad", "content": {"body": "..."}},
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_ARTIFACT_PAYLOAD")

    def test_create_get_update_metadata_flow(self) -> None:
        instance_json = self._instance_json(instance_id="inst-pm-art", buddy="pm")
        self._seed_pm_track_and_task()

        created = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "task_id": "task-pm-artifact",
                "kind": "prd",
                "title": "Runless PRD",
                "summary": "seed",
                "content": {"body": "v1"},
                "source_refs": [{"type": "note", "label": "seed"}],
            },
        )
        self.assertTrue(created.get("ok"), msg=created)
        artifact = created.get("artifact")
        self.assertIsInstance(artifact, dict, msg=created)
        assert isinstance(artifact, dict)
        artifact_id = artifact["id"]

        fetched = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="get",
            args={"artifact_id": artifact_id},
        )
        self.assertTrue(fetched.get("ok"), msg=fetched)
        self.assertEqual((fetched.get("artifact") or {}).get("task_id"), "task-pm-artifact")

        updated = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="update_metadata",
            args={"artifact_id": artifact_id, "summary": "updated summary"},
        )
        self.assertTrue(updated.get("ok"), msg=updated)
        self.assertEqual((updated.get("artifact") or {}).get("summary"), "updated summary")

    def test_list_for_track_returns_current_artifacts(self) -> None:
        instance_json = self._instance_json(instance_id="inst-pm-art", buddy="pm")
        self._seed_pm_track_and_task()
        self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "task_id": "task-pm-artifact",
                "kind": "prd",
                "title": "Track PRD",
                "summary": "seed",
                "content": {"body": "v1"},
            },
        )

        listed = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="list",
            args={"track_id": "track-artifact-runless"},
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        artifacts = listed.get("artifacts")
        self.assertIsInstance(artifacts, list, msg=listed)
        assert isinstance(artifacts, list)
        self.assertGreaterEqual(len(artifacts), 1)

    def test_create_revision_rejects_foreign_task_scope(self) -> None:
        instance_json = self._instance_json(instance_id="inst-dev-art", buddy="dev")
        env_store.create_track("track-dev-foreign", "Foreign", current_buddy="pm")
        env_store.create_task("task-pm-foreign", "Foreign PM Task", buddy="pm", track_id="track-dev-foreign")

        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-art",
            buddy="dev",
            tool="artifact",
            action="create_revision",
            args={
                "task_id": "task-pm-foreign",
                "kind": "implementation-report",
                "title": "Should Fail",
                "summary": "bad",
                "content": {"body": "..."},
            },
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_ARTIFACT_TASK_SCOPE")


if __name__ == "__main__":
    unittest.main()
