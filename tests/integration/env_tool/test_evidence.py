"""Runless evidence env.tool integration tests."""

from __future__ import annotations

import json
import sys
import unittest
import uuid
from pathlib import Path

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT

from buddyswitch.env.repos import runtime_files
from buddyswitch.modules.artifact.private.state import artifacts as artifact_repo
from buddyswitch.modules.track.private.state import track_comments as track_comment_repo
from buddyswitch.modules.track.private.state import tracks as track_repo
from tests.support import object_builders
import buddyswitch.runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.support.runtime import RuntimeWorkspaceTestCase  # noqa: E402

MANIFEST = ROOT / "src" / "buddyswitch" / "catalog" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class EvidenceEnvToolTests(RuntimeWorkspaceTestCase):
    def _instance_json(self, *, role: str, actor_id: str) -> Path:
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        path = self._runtime_path(f"instances/{actor_id}/instance.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": role,
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
        self._seed_active_task_for_instance(
            instance_json=path,
            role=role,
            actor_id=actor_id,
            task_slug=f"{role}-evidence-env",
        )
        return path

    def _dispatch(
        self,
        *,
        instance_json: Path,
        actor_id: str,
        role: str,
        action: str,
        args: dict[str, object],
    ) -> dict[str, object]:
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        envelope = runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "request_id": f"req-evidence-{uuid.uuid4().hex}",
                "method": "env.tool",
                "params": {
                    "actor_id": actor_id,
                    "active_role": role,
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

    def _seed_market_targets(self, *, actor_id: str | None = None) -> str:
        if actor_id is not None:
            actor = {"actor_id": self._runtime_actor_id(role="market", label=actor_id), "role_id": "market"}
            artifact = artifact_repo.create_artifact_revision(
                artifact_id="art-market-evidence-r1",
                title="Market brief",
                summary="seed",
                body="market",
                template="brief",
                supersedes_artifact_id=None,
                created_by_identity=actor["actor_id"],
                author_identities=[actor["actor_id"]],
                source_refs=[{"type": "note", "label": "seed"}],
            )
            return artifact["id"]
        artifact = object_builders.create_artifact_revision(
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
        artifact_id = self._seed_market_targets(actor_id="act-market-evidence")
        instance_json = self._instance_json(role="market", actor_id="act-market-evidence")

        issued = self._dispatch(
            instance_json=instance_json,
            actor_id="act-market-evidence",
            role="market",
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
        self.assertEqual(evidence.get("issued_by_identity_id"), self._runtime_actor_id(role="market", label="act-market-evidence"))
        self.assertNotIn("issued_by_identity", evidence)
        self.assertNotIn("active_role", evidence)
        self.assertNotIn("run_id", evidence)

    def test_approve_downgrade_requires_reason_and_owns_target(self) -> None:
        artifact_id = self._seed_market_targets(actor_id="act-market-downgrade")
        instance_json = self._instance_json(role="market", actor_id="act-market-downgrade")

        missing_reason = self._dispatch(
            instance_json=instance_json,
            actor_id="act-market-downgrade",
            role="market",
            action="approve_downgrade",
            args={"target_type": "artifact", "target_id": artifact_id, "reason": " "},
        )
        self.assertFalse(missing_reason.get("ok"), msg=missing_reason)
        self.assertEqual((missing_reason.get("error") or {}).get("code"), "E_EVIDENCE_PAYLOAD")

        rejected_memory = self._dispatch(
            instance_json=instance_json,
            actor_id="act-market-downgrade",
            role="market",
            action="approve_downgrade",
            args={"target_type": "memory", "target_id": "mem-old", "reason": "Manual fallback approved."},
        )
        self.assertFalse(rejected_memory.get("ok"), msg=rejected_memory)
        self.assertEqual((rejected_memory.get("error") or {}).get("code"), "E_EVIDENCE_TARGET_TYPE")
        self.assertEqual(rejected_memory.get("permission_boundary"), "evidence.target_type")
        self.assertNotIn("tool_evidence", rejected_memory)

        approved = self._dispatch(
            instance_json=instance_json,
            actor_id="act-market-downgrade",
            role="market",
            action="approve_downgrade",
            args={"target_type": "artifact", "target_id": artifact_id, "reason": "Manual fallback approved."},
        )
        self.assertTrue(approved.get("ok"), msg=approved)
        evidence = approved.get("tool_evidence")
        self.assertIsInstance(evidence, dict, msg=approved)
        assert isinstance(evidence, dict)
        self.assertEqual(evidence.get("target_type"), "artifact")
        self.assertEqual(evidence.get("target_id"), artifact_id)
        self.assertEqual(evidence.get("issued_by_identity_id"), self._runtime_actor_id(role="market", label="act-market-downgrade"))
        self.assertNotIn("issued_by_identity", evidence)
        self.assertNotIn("active_role", evidence)
        self.assertEqual(evidence.get("reason"), "Manual fallback approved.")

    def test_cross_role_target_is_rejected(self) -> None:
        artifact_id = self._seed_market_targets()
        design_instance = self._instance_json(role="design", actor_id="act-design-evidence")

        denied = self._dispatch(
            instance_json=design_instance,
            actor_id="act-design-evidence",
            role="design",
            action="issue_browser",
            args={"target_type": "artifact", "target_id": artifact_id},
        )
        self.assertFalse(denied.get("ok"), msg=denied)
        self.assertEqual((denied.get("error") or {}).get("code"), "E_EVIDENCE_TARGET_SCOPE")
        self.assertEqual(denied.get("permission_boundary"), "artifact.author_identity_ids")

    def test_missing_artifact_target_is_rejected_without_token(self) -> None:
        instance_json = self._instance_json(role="market", actor_id="act-market-missing-target")
        rejected = self._dispatch(
            instance_json=instance_json,
            actor_id="act-market-missing-target",
            role="market",
            action="issue_browser",
            args={"target_type": "artifact", "target_id": "art-market-missing-target"},
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_EVIDENCE_PAYLOAD")
        self.assertFalse(bool(rejected.get("state_changed")), msg=rejected)
        self.assertNotIn("tool_evidence", rejected)

    def test_readable_but_not_authored_target_is_rejected(self) -> None:
        artifact_id = self._seed_market_targets()
        object_builders.create_track(
            "track-market-readable",
            "Readable Market Track",
            owner_identity="act-market-readable",
            outcome="Readable market outcome",
            now={"next": "seed", "blocker": None},
        )
        object_builders.publish_track_material(
            track_id="track-market-readable",
            artifact_id=artifact_id,
            label="Market published artifact",
            from_role="market",
            summary="readable publication",
        )
        design_instance = self._instance_json(role="design", actor_id="act-design-readable-target")
        rejected = self._dispatch(
            instance_json=design_instance,
            actor_id="act-design-readable-target",
            role="design",
            action="issue_browser",
            args={"target_type": "artifact", "target_id": artifact_id},
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_EVIDENCE_TARGET_SCOPE")
        self.assertEqual(rejected.get("permission_boundary"), "artifact.author_identity_ids")
        self.assertNotIn("tool_evidence", rejected)
