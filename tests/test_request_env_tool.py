#!/usr/bin/env python3
"""Request env.tool integration tests."""

from __future__ import annotations

import json
import sys
import unittest
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_legacy_store as env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class RequestEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    _OBJECT_DIRS = ("tracks", "tasks", "artifacts", "comments", "messages", "requests")

    def _objects_state(self) -> dict[str, dict[str, object]]:
        snapshot: dict[str, dict[str, object]] = {}
        for object_dir in self._OBJECT_DIRS:
            root = self._runtime_path(f"buddyswitch/objects/{object_dir}")
            files: dict[str, str] = {}
            if root.is_dir():
                for path in sorted(root.glob("*.json")):
                    files[path.name] = path.read_text(encoding="utf-8")
            snapshot[object_dir] = {
                "exists": root.exists(),
                "files": files,
            }
        return snapshot

    def _assert_non_request_dirs_unchanged(
        self,
        before: dict[str, dict[str, object]],
        after: dict[str, dict[str, object]],
    ) -> None:
        for object_dir in ("tracks", "tasks", "artifacts", "comments", "messages"):
            self.assertEqual(before[object_dir], after[object_dir], msg=object_dir)

    def _instance_json(self, *, instance_id: str, buddy: str, status: str = "active") -> Path:
        path = self._runtime_path(f"instance-{instance_id}.json")
        path.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": status,
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "updated_at": "2026-05-21T00:00:00Z",
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
        tool: str,
        action: str,
        args: dict[str, object],
    ) -> dict[str, object]:
        request = {
            "protocol": PROTOCOL,
            "request_id": f"req-request-{uuid.uuid4().hex}",
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

    def _seed_track(self, track_id: str) -> dict[str, object]:
        return env_store.create_track(track_id, f"{track_id} title", owner_buddy="pm")

    def _seed_published_artifact(self, *, artifact_id: str, track_id: str) -> str:
        if env_store.get_track(track_id) is None:
            self._seed_track(track_id)
        artifact = env_store.create_artifact_revision(
            artifact_id=artifact_id,
            title=f"{artifact_id} title",
            summary="seed summary",
            body="seed body",
            template="brief",
            supersedes_artifact_id=None,
            created_by="pm",
            authors=["pm"],
            source_refs=[{"type": "note", "label": "seed"}],
        )
        env_store.publish_track_material(
            track_id=track_id,
            artifact_id=str(artifact["id"]),
            label="Seed",
            from_buddy="pm",
            summary="seed summary",
        )
        return str(artifact["id"])

    def _request_file(self, request_id: str) -> Path:
        return self._runtime_path(f"buddyswitch/objects/requests/{request_id}.json")

    def _load_request(self, request_id: str) -> dict[str, Any]:
        return json.loads(self._request_file(request_id).read_text(encoding="utf-8"))

    def _create_request(
        self,
        *,
        instance_json: Path,
        instance_id: str,
        buddy: str,
        track_id: str,
        to_buddy: str = "dev",
        title: str = "request-title",
        summary: str = "request-summary",
        target_refs: list[dict[str, str]] | None = None,
    ) -> dict[str, object]:
        args: dict[str, object] = {
            "track_id": track_id,
            "to_buddy": to_buddy,
            "title": title,
            "summary": summary,
        }
        if target_refs is not None:
            args["target_refs"] = target_refs
        return self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy=buddy,
            tool="request",
            action="create",
            args=args,
        )

    @staticmethod
    def _request_ids(payload: dict[str, object]) -> set[str]:
        ids: set[str] = set()
        for row in payload.get("requests", []):
            if isinstance(row, dict):
                request_id = row.get("id")
                if isinstance(request_id, str) and request_id:
                    ids.add(request_id)
        return ids

    def test_create_request_main_path_creates_durable_request(self) -> None:
        track_id = "track-req-main"
        self._seed_track(track_id)
        artifact_id = self._seed_published_artifact(artifact_id="art-design-r1", track_id=track_id)
        instance_json = self._instance_json(instance_id="inst-pm-req-create", buddy="pm")
        before = self._objects_state()

        created = self._create_request(
            instance_json=instance_json,
            instance_id="inst-pm-req-create",
            buddy="pm",
            track_id=track_id,
            to_buddy="dev",
            title="Implement approved scope",
            summary="Build requested flow from design artifact.",
            target_refs=[{"type": "artifact", "id": artifact_id}],
        )
        after = self._objects_state()
        self.assertTrue(created.get("ok"), msg=created)
        self.assertTrue(created.get("state_changed"), msg=created)
        self.assertEqual(created.get("durability"), "durable")
        created_ids = created.get("created_ids")
        self.assertIsInstance(created_ids, list, msg=created)
        assert isinstance(created_ids, list)
        self.assertEqual(len(created_ids), 1, msg=created)
        request_id = str(created_ids[0])

        self._assert_non_request_dirs_unchanged(before, after)
        self.assertNotEqual(before["requests"], after["requests"])
        self.assertTrue(self._request_file(request_id).exists())
        payload = self._load_request(request_id)
        self.assertEqual(payload.get("track_id"), track_id)
        self.assertEqual(payload.get("from_buddy"), "pm")
        self.assertEqual(payload.get("to_buddy"), "dev")
        self.assertEqual(payload.get("status"), "open")
        self.assertIsNone(payload.get("blocker"))
        self.assertEqual(payload.get("result_refs"), [])
        self.assertEqual(payload.get("target_refs"), [{"type": "artifact", "id": artifact_id}])
        self.assertIsInstance(payload.get("created_at"), str)
        self.assertIsInstance(payload.get("updated_at"), str)
        self.assertIsNone(payload.get("accepted_at"))
        self.assertIsNone(payload.get("blocked_at"))
        self.assertIsNone(payload.get("completed_at"))
        self.assertIsNone(payload.get("canceled_at"))

    def test_create_rejects_unknown_field_before_required_fields(self) -> None:
        instance_json = self._instance_json(instance_id="inst-request-unknown", buddy="dev")
        before = self._objects_state()
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-request-unknown",
            buddy="dev",
            tool="request",
            action="create",
            args={"__unexpected_payload_field__": True},
        )
        after = self._objects_state()
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_REQUEST_PAYLOAD")
        self.assertIn("__unexpected_payload_field__", json.dumps(response, ensure_ascii=True))
        self.assertIs(response.get("state_changed"), False)
        self.assertEqual(before, after)

    def test_create_request_rejects_invalid_payloads_without_state_mutation(self) -> None:
        track_id = "track-req-invalid"
        archived_track_id = "track-req-archived"
        self._seed_track(track_id)
        self._seed_track(archived_track_id)
        env_store.update_track(archived_track_id, {"archived_at": "2026-05-21T10:00:00+08:00"})
        self._seed_track("track-other")
        instance_json = self._instance_json(instance_id="inst-pm-req-invalid", buddy="pm")

        cases: list[tuple[str, dict[str, object]]] = [
            (
                "unknown-buddy",
                {"track_id": track_id, "to_buddy": "ops", "title": "x", "summary": "x"},
            ),
            (
                "self-request",
                {"track_id": track_id, "to_buddy": "pm", "title": "x", "summary": "x"},
            ),
            (
                "missing-track",
                {"track_id": "track-missing", "to_buddy": "dev", "title": "x", "summary": "x"},
            ),
            (
                "archived-track",
                {"track_id": archived_track_id, "to_buddy": "dev", "title": "x", "summary": "x"},
            ),
            (
                "bad-target-refs-type",
                {"track_id": track_id, "to_buddy": "dev", "title": "x", "summary": "x", "target_refs": "oops"},
            ),
            (
                "bad-target-ref-shape",
                {"track_id": track_id, "to_buddy": "dev", "title": "x", "summary": "x", "target_refs": [{"type": "artifact"}]},
            ),
            (
                "bad-target-ref-type",
                {"track_id": track_id, "to_buddy": "dev", "title": "x", "summary": "x", "target_refs": [{"type": "task", "id": "task-x"}]},
            ),
            (
                "track-ref-mismatch",
                {"track_id": track_id, "to_buddy": "dev", "title": "x", "summary": "x", "target_refs": [{"type": "track", "id": "track-other"}]},
            ),
            (
                "unsupported-status-input",
                {"track_id": track_id, "to_buddy": "dev", "title": "x", "summary": "x", "status": "done"},
            ),
        ]

        for name, args in cases:
            before = self._objects_state()
            rejected = self._dispatch(
                instance_json=instance_json,
                instance_id="inst-pm-req-invalid",
                buddy="pm",
                tool="request",
                action="create",
                args=args,
            )
            after = self._objects_state()
            with self.subTest(case=name):
                self.assertFalse(rejected.get("ok"), msg=rejected)
                self.assertIs(rejected.get("state_changed"), False, msg=rejected)
                self.assertEqual(rejected.get("durability"), "none", msg=rejected)
                self.assertEqual(after, before)

    def test_request_visibility_get_and_list_filters(self) -> None:
        track_visible = "track-req-visible"
        track_other = "track-req-other"
        self._seed_track(track_visible)
        self._seed_track(track_other)

        pm_instance = self._instance_json(instance_id="inst-pm-req-visible", buddy="pm")
        design_instance = self._instance_json(instance_id="inst-design-req-visible", buddy="design")
        dev_instance = self._instance_json(instance_id="inst-dev-req-visible", buddy="dev")
        market_instance = self._instance_json(instance_id="inst-market-req-visible", buddy="market")

        req_a = self._create_request(
            instance_json=pm_instance,
            instance_id="inst-pm-req-visible",
            buddy="pm",
            track_id=track_visible,
            to_buddy="dev",
            title="A",
            summary="A summary",
        )
        req_b = self._create_request(
            instance_json=design_instance,
            instance_id="inst-design-req-visible",
            buddy="design",
            track_id=track_visible,
            to_buddy="test",
            title="B",
            summary="B summary",
        )
        req_c = self._create_request(
            instance_json=pm_instance,
            instance_id="inst-pm-req-visible",
            buddy="pm",
            track_id=track_other,
            to_buddy="market",
            title="C",
            summary="C summary",
        )
        self.assertTrue(req_a.get("ok"), msg=req_a)
        self.assertTrue(req_b.get("ok"), msg=req_b)
        self.assertTrue(req_c.get("ok"), msg=req_c)
        req_a_id = str((req_a.get("created_ids") or [None])[0])
        req_b_id = str((req_b.get("created_ids") or [None])[0])
        req_c_id = str((req_c.get("created_ids") or [None])[0])

        dev_inbox = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-req-visible",
            buddy="dev",
            tool="request",
            action="list",
            args={"box": "inbox"},
        )
        self.assertTrue(dev_inbox.get("ok"), msg=dev_inbox)
        self.assertEqual(self._request_ids(dev_inbox), {req_a_id})

        pm_visible_track = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-req-visible",
            buddy="pm",
            tool="request",
            action="list",
            args={"track_id": track_visible},
        )
        self.assertTrue(pm_visible_track.get("ok"), msg=pm_visible_track)
        self.assertEqual(self._request_ids(pm_visible_track), {req_a_id, req_b_id})

        design_get_b = self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-req-visible",
            buddy="design",
            tool="request",
            action="get",
            args={"request_id": req_b_id},
        )
        self.assertTrue(design_get_b.get("ok"), msg=design_get_b)
        self.assertEqual((design_get_b.get("request") or {}).get("id"), req_b_id)

        market_get_a = self._dispatch(
            instance_json=market_instance,
            instance_id="inst-market-req-visible",
            buddy="market",
            tool="request",
            action="get",
            args={"request_id": req_a_id},
        )
        self.assertFalse(market_get_a.get("ok"), msg=market_get_a)
        self.assertNotIn("request", market_get_a, msg=market_get_a)

        pm_outbox = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-req-visible",
            buddy="pm",
            tool="request",
            action="list",
            args={"box": "outbox"},
        )
        self.assertTrue(pm_outbox.get("ok"), msg=pm_outbox)
        self.assertEqual(self._request_ids(pm_outbox), {req_a_id, req_c_id})

        pm_filter_buddy = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-req-visible",
            buddy="pm",
            tool="request",
            action="list",
            args={"buddy": "dev"},
        )
        self.assertTrue(pm_filter_buddy.get("ok"), msg=pm_filter_buddy)
        self.assertEqual(self._request_ids(pm_filter_buddy), {req_a_id})

    def test_request_lifecycle_permissions_and_transitions(self) -> None:
        track_id = "track-req-lifecycle"
        self._seed_track(track_id)
        pm_instance = self._instance_json(instance_id="inst-pm-req-life", buddy="pm")
        dev_instance = self._instance_json(instance_id="inst-dev-req-life", buddy="dev")
        design_instance = self._instance_json(instance_id="inst-design-req-life", buddy="design")

        created = self._create_request(
            instance_json=pm_instance,
            instance_id="inst-pm-req-life",
            buddy="pm",
            track_id=track_id,
            to_buddy="dev",
            title="Lifecycle",
            summary="Lifecycle summary",
        )
        self.assertTrue(created.get("ok"), msg=created)
        request_id = str((created.get("created_ids") or [None])[0])

        unauthorized_accept = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-req-life",
            buddy="pm",
            tool="request",
            action="accept",
            args={"request_id": request_id},
        )
        self.assertFalse(unauthorized_accept.get("ok"), msg=unauthorized_accept)
        self.assertEqual(unauthorized_accept.get("permission_boundary"), "request.recipient_scope")

        accepted = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-req-life",
            buddy="dev",
            tool="request",
            action="accept",
            args={"request_id": request_id},
        )
        self.assertTrue(accepted.get("ok"), msg=accepted)
        self.assertEqual((accepted.get("request") or {}).get("status"), "accepted")

        blocked_blank = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-req-life",
            buddy="dev",
            tool="request",
            action="block",
            args={"request_id": request_id, "blocker": "   "},
        )
        self.assertFalse(blocked_blank.get("ok"), msg=blocked_blank)

        blocked = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-req-life",
            buddy="dev",
            tool="request",
            action="block",
            args={"request_id": request_id, "blocker": "Need updated design artifact."},
        )
        self.assertTrue(blocked.get("ok"), msg=blocked)
        self.assertEqual((blocked.get("request") or {}).get("status"), "blocked")

        accepted_again = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-req-life",
            buddy="dev",
            tool="request",
            action="accept",
            args={"request_id": request_id},
        )
        self.assertTrue(accepted_again.get("ok"), msg=accepted_again)
        self.assertEqual((accepted_again.get("request") or {}).get("status"), "accepted")
        self.assertIsNone((accepted_again.get("request") or {}).get("blocker"))

        completed = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-req-life",
            buddy="dev",
            tool="request",
            action="complete",
            args={"request_id": request_id, "result_refs": [{"type": "track", "id": track_id}]},
        )
        self.assertTrue(completed.get("ok"), msg=completed)
        self.assertEqual((completed.get("request") or {}).get("status"), "done")

        before_done = self._load_request(request_id)
        done_to_blocked = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-req-life",
            buddy="dev",
            tool="request",
            action="block",
            args={"request_id": request_id, "blocker": "too late"},
        )
        after_done = self._load_request(request_id)
        self.assertFalse(done_to_blocked.get("ok"), msg=done_to_blocked)
        self.assertEqual(after_done, before_done)

        created_open = self._create_request(
            instance_json=pm_instance,
            instance_id="inst-pm-req-life",
            buddy="pm",
            track_id=track_id,
            to_buddy="dev",
            title="OpenCompleteReject",
            summary="OpenCompleteReject summary",
        )
        open_request_id = str((created_open.get("created_ids") or [None])[0])
        open_to_done = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-req-life",
            buddy="dev",
            tool="request",
            action="complete",
            args={"request_id": open_request_id, "result_refs": [{"type": "track", "id": track_id}]},
        )
        self.assertFalse(open_to_done.get("ok"), msg=open_to_done)

        canceled_open = self._create_request(
            instance_json=pm_instance,
            instance_id="inst-pm-req-life",
            buddy="pm",
            track_id=track_id,
            to_buddy="dev",
            title="CancelOpen",
            summary="CancelOpen summary",
        )
        canceled_open_id = str((canceled_open.get("created_ids") or [None])[0])
        canceled = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-req-life",
            buddy="pm",
            tool="request",
            action="cancel",
            args={"request_id": canceled_open_id},
        )
        self.assertTrue(canceled.get("ok"), msg=canceled)
        self.assertEqual((canceled.get("request") or {}).get("status"), "canceled")

        cancel_by_recipient = self._create_request(
            instance_json=pm_instance,
            instance_id="inst-pm-req-life",
            buddy="pm",
            track_id=track_id,
            to_buddy="dev",
            title="CancelByRecipient",
            summary="CancelByRecipient summary",
        )
        cancel_by_recipient_id = str((cancel_by_recipient.get("created_ids") or [None])[0])
        rejected_cancel = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-req-life",
            buddy="dev",
            tool="request",
            action="cancel",
            args={"request_id": cancel_by_recipient_id},
        )
        self.assertFalse(rejected_cancel.get("ok"), msg=rejected_cancel)

        accepted_then_canceled = self._create_request(
            instance_json=pm_instance,
            instance_id="inst-pm-req-life",
            buddy="pm",
            track_id=track_id,
            to_buddy="dev",
            title="AcceptedCancel",
            summary="AcceptedCancel summary",
        )
        accepted_then_canceled_id = str((accepted_then_canceled.get("created_ids") or [None])[0])
        accepted_ok = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-req-life",
            buddy="dev",
            tool="request",
            action="accept",
            args={"request_id": accepted_then_canceled_id},
        )
        self.assertTrue(accepted_ok.get("ok"), msg=accepted_ok)
        canceled_ok = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-req-life",
            buddy="pm",
            tool="request",
            action="cancel",
            args={"request_id": accepted_then_canceled_id},
        )
        self.assertTrue(canceled_ok.get("ok"), msg=canceled_ok)
        self.assertEqual((canceled_ok.get("request") or {}).get("status"), "canceled")

        blocked_then_canceled = self._create_request(
            instance_json=pm_instance,
            instance_id="inst-pm-req-life",
            buddy="pm",
            track_id=track_id,
            to_buddy="dev",
            title="BlockedCancel",
            summary="BlockedCancel summary",
        )
        blocked_then_canceled_id = str((blocked_then_canceled.get("created_ids") or [None])[0])
        accepted_before_block = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-req-life",
            buddy="dev",
            tool="request",
            action="accept",
            args={"request_id": blocked_then_canceled_id},
        )
        self.assertTrue(accepted_before_block.get("ok"), msg=accepted_before_block)
        blocked_before_cancel = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-req-life",
            buddy="dev",
            tool="request",
            action="block",
            args={"request_id": blocked_then_canceled_id, "blocker": "waiting"},
        )
        self.assertTrue(blocked_before_cancel.get("ok"), msg=blocked_before_cancel)
        canceled_from_blocked = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-req-life",
            buddy="pm",
            tool="request",
            action="cancel",
            args={"request_id": blocked_then_canceled_id},
        )
        self.assertTrue(canceled_from_blocked.get("ok"), msg=canceled_from_blocked)
        self.assertEqual((canceled_from_blocked.get("request") or {}).get("status"), "canceled")

        canceled_to_accept = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-req-life",
            buddy="dev",
            tool="request",
            action="accept",
            args={"request_id": blocked_then_canceled_id},
        )
        self.assertFalse(canceled_to_accept.get("ok"), msg=canceled_to_accept)

        third_party_mutation = self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-req-life",
            buddy="design",
            tool="request",
            action="accept",
            args={"request_id": open_request_id},
        )
        self.assertFalse(third_party_mutation.get("ok"), msg=third_party_mutation)


if __name__ == "__main__":
    unittest.main()
