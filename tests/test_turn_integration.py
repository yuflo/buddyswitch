#!/usr/bin/env python3
"""Turn runtime integration tests aligned with track-page flow."""

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

import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class TurnRuntimeIntegrationTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(self, buddy: str) -> Path:
        path = self._runtime_path(f"instance-{buddy}.json")
        path.write_text(
            json.dumps(
                {
                    "instance_id": f"inst-{buddy}",
                    "buddy": buddy,
                    "status": "active",
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "updated_at": "2026-05-18T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def _dispatch(self, *, buddy: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        instance_json = self._instance_json(buddy)
        request = {
            "protocol": PROTOCOL,
            "request_id": f"req-turn-{uuid.uuid4().hex}",
            "method": "env.tool",
            "params": {
                "instance_id": f"inst-{buddy}",
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

    def test_cross_buddy_flow_uses_track_open_and_artifact_get(self) -> None:
        created = self._dispatch(
            buddy="pm",
            tool="track",
            action="create",
            args={
                "track_id": "track-turn-flow",
                "title": "Turn flow",
                "outcome": "validate flow",
                "appetite": "1 day",
                "now": {"next": "publish prd", "blocker": None},
            },
        )
        self.assertTrue(created.get("ok"), msg=created)

        prd = self._dispatch(
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-turn-flow",
                "kind": "prd",
                "label": "PRD",
                "title": "PRD",
                "summary": "scope",
                "content": {"body": "prd"},
            },
        )
        self.assertTrue(prd.get("ok"), msg=prd)

        opened = self._dispatch(
            buddy="design",
            tool="track",
            action="open",
            args={"track_id": "track-turn-flow"},
        )
        self.assertTrue(opened.get("ok"), msg=opened)

        read = self._dispatch(
            buddy="design",
            tool="artifact",
            action="get",
            args={"artifact_id": prd["artifact_id"]},
        )
        self.assertTrue(read.get("ok"), msg=read)

        serialized = json.dumps({"created": created, "prd": prd, "opened": opened, "read": read}, ensure_ascii=True)
        self.assertNotIn("track" + ".join", serialized)


if __name__ == "__main__":
    unittest.main()
