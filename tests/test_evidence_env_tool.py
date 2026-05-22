#!/usr/bin/env python3
"""Runless evidence env.tool integration tests."""

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

import env_legacy_store as env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class EvidenceEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(self, *, buddy: str, instance_id: str) -> Path:
        path = self._runtime_path(f"instances/{instance_id}/instance.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": "active",
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

    def _dispatch(
        self,
        *,
        instance_json: Path,
        instance_id: str,
        buddy: str,
        action: str,
        args: dict[str, object],
    ) -> dict[str, object]:
        envelope = runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "request_id": f"req-evidence-{uuid.uuid4().hex}",
                "method": "env.tool",
                "params": {
                    "instance_id": instance_id,
                    "active_buddy": buddy,
                    "tool": "evidence",
                    "action": action,
                    "args": args,
                },
                "deadline_ms": 35000,
            },
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )
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

    def _seed_market_targets(self) -> str:
        artifact = env_store.create_artifact_revision(
            artifact_id="art-market-evidence-r1",
            title="Market brief",
            summary="seed",
            body="market",
            template="brief",
            supersedes_artifact_id=None,
            created_by="market",
            authors=["market"],
            source_refs=[{"type": "note", "label": "seed"}],
        )
        return artifact["id"]

    def test_issue_browser_is_target_scoped_and_runless(self) -> None:
        artifact_id = self._seed_market_targets()
        instance_json = self._instance_json(buddy="market", instance_id="inst-market-evidence")

        issued = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-market-evidence",
            buddy="market",
            action="issue_browser",
            args={"target_type": "artifact", "target_id": artifact_id, "mode": "browser-cockpit-preflight"},
        )
        self.assertTrue(issued.get("ok"), msg=issued)
        self.assertTrue(issued.get("state_changed"), msg=issued)
        self.assertEqual(issued.get("durability"), "transient")
        evidence = issued.get("tool_evidence")
        self.assertIsInstance(evidence, dict, msg=issued)
        assert isinstance(evidence, dict)
        self.assertEqual(evidence.get("target_type"), "artifact")
        self.assertEqual(evidence.get("target_id"), artifact_id)
        self.assertEqual(evidence.get("active_buddy"), "market")
        self.assertNotIn("run_id", evidence)

    def test_approve_downgrade_requires_reason_and_owns_target(self) -> None:
        artifact_id = self._seed_market_targets()
        instance_json = self._instance_json(buddy="market", instance_id="inst-market-downgrade")

        missing_reason = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-market-downgrade",
            buddy="market",
            action="approve_downgrade",
            args={"target_type": "artifact", "target_id": artifact_id, "reason": " "},
        )
        self.assertFalse(missing_reason.get("ok"), msg=missing_reason)
        self.assertEqual((missing_reason.get("error") or {}).get("code"), "E_EVIDENCE_PAYLOAD")

        rejected_memory = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-market-downgrade",
            buddy="market",
            action="approve_downgrade",
            args={"target_type": "memory", "target_id": "mem-old", "reason": "Manual fallback approved."},
        )
        self.assertFalse(rejected_memory.get("ok"), msg=rejected_memory)
        self.assertEqual((rejected_memory.get("error") or {}).get("code"), "E_EVIDENCE_TARGET_TYPE")
        self.assertEqual(rejected_memory.get("permission_boundary"), "evidence.target_type")
        self.assertNotIn("tool_evidence", rejected_memory)

        approved = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-market-downgrade",
            buddy="market",
            action="approve_downgrade",
            args={"target_type": "artifact", "target_id": artifact_id, "reason": "Manual fallback approved."},
        )
        self.assertTrue(approved.get("ok"), msg=approved)
        evidence = approved.get("tool_evidence")
        self.assertIsInstance(evidence, dict, msg=approved)
        assert isinstance(evidence, dict)
        self.assertEqual(evidence.get("target_type"), "artifact")
        self.assertEqual(evidence.get("target_id"), artifact_id)
        self.assertEqual(evidence.get("reason"), "Manual fallback approved.")

    def test_cross_buddy_target_is_rejected(self) -> None:
        artifact_id = self._seed_market_targets()
        design_instance = self._instance_json(buddy="design", instance_id="inst-design-evidence")

        denied = self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-evidence",
            buddy="design",
            action="issue_browser",
            args={"target_type": "artifact", "target_id": artifact_id},
        )
        self.assertFalse(denied.get("ok"), msg=denied)
        self.assertEqual((denied.get("error") or {}).get("code"), "E_EVIDENCE_TARGET_SCOPE")
        self.assertEqual(denied.get("permission_boundary"), "artifact.authors")

    def test_missing_artifact_target_is_rejected_without_token(self) -> None:
        instance_json = self._instance_json(buddy="market", instance_id="inst-market-missing-target")
        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-market-missing-target",
            buddy="market",
            action="issue_browser",
            args={"target_type": "artifact", "target_id": "art-market-missing-target"},
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_EVIDENCE_PAYLOAD")
        self.assertFalse(bool(rejected.get("state_changed")), msg=rejected)
        self.assertNotIn("tool_evidence", rejected)

    def test_readable_but_not_authored_target_is_rejected(self) -> None:
        artifact_id = self._seed_market_targets()
        env_store.create_track("track-market-readable", "Readable Market Track", owner_buddy="market")
        env_store.publish_track_material(
            track_id="track-market-readable",
            artifact_id=artifact_id,
            label="Market published artifact",
            from_buddy="market",
            summary="readable publication",
        )
        design_instance = self._instance_json(buddy="design", instance_id="inst-design-readable-target")
        rejected = self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-readable-target",
            buddy="design",
            action="issue_browser",
            args={"target_type": "artifact", "target_id": artifact_id},
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_EVIDENCE_TARGET_SCOPE")
        self.assertEqual(rejected.get("permission_boundary"), "artifact.authors")
        self.assertNotIn("tool_evidence", rejected)


if __name__ == "__main__":
    unittest.main()
