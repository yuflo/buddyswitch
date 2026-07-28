"""Track-native comment env.tool integration tests."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from typing import Any

from tests.support.paths import REPO_ROOT
from tests.support.runtime import RuntimeWorkspaceTestCase

ROOT = REPO_ROOT

import buddyswitch.runtime_kernel.broker as runtime_broker  # noqa: E402
from buddyswitch.env.domain import task_sys  # noqa: E402
from buddyswitch.env.tool_runtime import context as context_module  # noqa: E402
from buddyswitch.env.repos import runtime_files  # noqa: E402
from buddyswitch.env.repos import track_comments as comment_repo  # noqa: E402
from buddyswitch.env.repos import tracks as track_repo  # noqa: E402

MANIFEST = ROOT / "src" / "buddyswitch" / "catalog" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class TrackCommentEnvToolTests(RuntimeWorkspaceTestCase):

    def _runtime_actor_id(self, *, role: str, label: str) -> str:
        if label.startswith(f"act-{role}-"):
            suffix = label.removeprefix(f"act-{role}-")
            if len(suffix) == 12 and all(char in "0123456789abcdef" for char in suffix):
                return label
        digest = hashlib.sha1(f"{role}:{label}".encode("utf-8")).hexdigest()[:12]
        return f"act-{role}-{digest}"

    def _instance_json(self, *, actor_id: str, role: str) -> Path:
        normalized_actor_id = self._runtime_actor_id(role=role, label=actor_id)
        instance_root = self.runtime_root / "instances" / normalized_actor_id
        instance_root.mkdir(parents=True, exist_ok=True)
        path = instance_root / "instance.json"
        path.write_text(
            json.dumps(
                {
                    "actor_id": normalized_actor_id,
                    "role": role,
                    "status": "active",
                    "workspace_dir": str(self.runtime_root),
                    "instance_root": str(instance_root),
                    "browser_port": None,
                    "updated_at": "2026-06-10T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self._seed_active_task(instance_root=instance_root, actor_id=normalized_actor_id, role=role)
        return path

    def _seed_active_task(self, *, instance_root: Path, actor_id: str, role: str) -> None:
        task_id = f"task-0001-{role}-track-comment"
        task_sys.create(
            actor_target={"actor_id": actor_id, "role_id": role},
            demand_ref={
                "demand_id": f"demand-track-comment-{role}",
                "basis_revision": 1,
                "demand_ref": f"dref-track-comment-{role}",
            },
            objective=f"Exercise Track comment tooling for {task_id}.",
            selection_reason="The Task slot is empty and this fixture Demand is selected.",
        )

    def _dispatch(self, *, actor_id: str, role: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        instance_json = self._instance_json(actor_id=actor_id, role=role)
        request = {
            "protocol": PROTOCOL,
            "request_id": f"req-track-comment-{uuid.uuid4().hex}",
            "method": "env.tool",
            "params": {
                "actor_id": self._runtime_actor_id(role=role, label=actor_id),
                "active_role": role,
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

    def _patch_daemon_delivery(
        self,
        *,
        delivery: dict[str, object] | None = None,
        exc: BaseException | None = None,
    ) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        original_deliver_signal = context_module.daemon_client.deliver_signal

        def fake_deliver_signal(*, signal: dict[str, Any]) -> dict[str, object]:
            calls.append(signal)
            if exc is not None:
                raise exc
            if delivery is not None:
                result = dict(delivery)
                result.setdefault("target_identity_id", signal.get("target_identity_id"))
                result.setdefault("signal", signal)
                return result
            return {
                "delivery_status": "delivered",
                "handling_status": "handled",
                "target_identity_id": signal.get("target_identity_id"),
                "signal": signal,
            }

        def restore() -> None:
            context_module.daemon_client.deliver_signal = original_deliver_signal

        context_module.daemon_client.deliver_signal = fake_deliver_signal
        self.addCleanup(restore)
        return calls

    def _patch_online_actors(self, actor_rows: list[dict[str, Any]]) -> None:
        original_list_online_actors = context_module.daemon_client.list_online_actors

        def fake_list_online_actors(*, role_id: str | None = None, socket_path: Path | None = None) -> dict[str, object]:
            del socket_path
            rows = []
            for row in actor_rows:
                identity_id = row.get("identity_id") if isinstance(row, dict) else None
                row_role_id = row.get("role_id") if isinstance(row, dict) else None
                if not isinstance(identity_id, str) or not isinstance(row_role_id, str):
                    continue
                if role_id is not None and row_role_id != role_id:
                    continue
                rows.append(dict(row))
            return {"actors": rows, "count": len(rows)}

        def restore() -> None:
            context_module.daemon_client.list_online_actors = original_list_online_actors

        context_module.daemon_client.list_online_actors = fake_list_online_actors
        self.addCleanup(restore)

    def _seed_track(self, track_id: str) -> dict[str, object]:
        return track_repo.create_track(
            track_id,
            f"Track {track_id}",
            owner_identity=self._runtime_actor_id(role="pm", label="act-pm-resolve-comment"),
            outcome="Track comment test outcome",
            now={"next": "test", "blocker": None},
        )

    def test_add_comment_delivers_track_comment_added_to_mentions_once(self) -> None:
        self._seed_track("track-comment-delivery-mentions")
        calls = self._patch_daemon_delivery()
        source_identity_id = self._runtime_actor_id(role="dev", label="act-dev-track-delivery")
        target_pm = {"identity_id": "act-route-track-mentioned", "role_id": "pm"}
        self._patch_online_actors([{**target_pm, "status": "online"}])

        response = self._dispatch(
            actor_id="act-dev-track-delivery",
            role="dev",
            tool="track",
            action="add_comment",
            args={
                "track_id": "track-comment-delivery-mentions",
                "content": "Please review this Track point.",
                "mentioned_identity_ids": [target_pm["identity_id"], target_pm["identity_id"], source_identity_id],
            },
        )

        self.assertTrue(response.get("ok"), msg=response)
        comment = response.get("comment")
        self.assertIsInstance(comment, dict, msg=response)
        assert isinstance(comment, dict)
        self.assertEqual(len(calls), 1)
        signal = calls[0]
        self.assertEqual(signal["type"], "track.comment.added")
        self.assertEqual(signal["source_identity_id"], source_identity_id)
        self.assertEqual(signal["source_role_id"], "dev")
        self.assertEqual(signal["target_identity_id"], target_pm["identity_id"])
        self.assertEqual(signal["target_role_id"], target_pm["role_id"])
        self.assertEqual(
            signal["payload"],
            {
                "track_id": "track-comment-delivery-mentions",
                "comment_id": comment["id"],
                "thread_id": comment["thread_id"],
            },
        )
        self.assertNotIn("content", signal["payload"])
        self.assertNotIn("comment", signal["payload"])
        self.assertNotIn("to_role", signal)
        self.assertNotIn("nc.notification", json.dumps(signal, ensure_ascii=True))
        self.assertEqual(response.get("delivery_status"), "delivered")
        self.assertEqual(
            response.get("delivery_summary"),
            {"target_count": 1, "delivered_count": 1, "failed_count": 0},
        )
        results = response.get("delivery_results")
        self.assertIsInstance(results, list, msg=response)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].get("target_identity_id"), target_pm["identity_id"])
        self.assertNotIn("target_" + "actor_address", results[0])
        self.assertEqual(results[0].get("delivery_status"), "delivered")

    def test_add_comment_reply_notifies_parent_author_once(self) -> None:
        self._seed_track("track-comment-delivery-reply")
        calls = self._patch_daemon_delivery()
        root = self._dispatch(
            actor_id="act-dev-track-reply-source",
            role="dev",
            tool="track",
            action="add_comment",
            args={"track_id": "track-comment-delivery-reply", "content": "Root question"},
        )
        self.assertTrue(root.get("ok"), msg=root)
        root_comment = root.get("comment")
        self.assertIsInstance(root_comment, dict, msg=root)
        assert isinstance(root_comment, dict)
        self.assertEqual(calls, [])
        root_author = {
            "identity_id": self._runtime_actor_id(role="dev", label="act-dev-track-reply-source"),
            "role_id": "dev",
        }
        self._patch_online_actors([{**root_author, "status": "online"}])

        reply = self._dispatch(
            actor_id="act-pm-track-reply-author",
            role="pm",
            tool="track",
            action="add_comment",
            args={
                "track_id": "track-comment-delivery-reply",
                "content": "Reply for the original author.",
                "reply_to": root_comment["id"],
                "mentioned_identity_ids": [root_author["identity_id"], root_author["identity_id"]],
            },
        )

        self.assertTrue(reply.get("ok"), msg=reply)
        reply_comment = reply.get("comment")
        self.assertIsInstance(reply_comment, dict, msg=reply)
        assert isinstance(reply_comment, dict)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["target_identity_id"], root_author["identity_id"])
        self.assertEqual(calls[0]["target_role_id"], root_author["role_id"])
        self.assertEqual(
            calls[0]["payload"],
            {
                "track_id": "track-comment-delivery-reply",
                "comment_id": reply_comment["id"],
                "thread_id": root_comment["thread_id"],
            },
        )
        self.assertEqual(reply.get("delivery_status"), "delivered")
        self.assertEqual(
            reply.get("delivery_summary"),
            {"target_count": 1, "delivered_count": 1, "failed_count": 0},
        )

    def test_add_comment_deduplicates_targets_by_identity_id(self) -> None:
        self._seed_track("track-comment-delivery-address-dedupe")
        calls = self._patch_daemon_delivery()
        target_pm = {"identity_id": "act-pm-shared-track-target", "role_id": "pm"}
        self._patch_online_actors([{**target_pm, "status": "online"}])

        response = self._dispatch(
            actor_id="act-dev-track-address-dedupe",
            role="dev",
            tool="track",
            action="add_comment",
            args={
                "track_id": "track-comment-delivery-address-dedupe",
                "content": "One actor identity appears twice.",
                "mentioned_identity_ids": [target_pm["identity_id"], target_pm["identity_id"]],
            },
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(
            [signal["target_identity_id"] for signal in calls],
            [target_pm["identity_id"]],
        )
        self.assertEqual(
            response.get("delivery_summary"),
            {"target_count": 1, "delivered_count": 1, "failed_count": 0},
        )

    def test_add_comment_without_attention_creates_state_without_delivery(self) -> None:
        self._seed_track("track-comment-delivery-none")
        calls = self._patch_daemon_delivery()

        response = self._dispatch(
            actor_id="act-dev-track-no-attention",
            role="dev",
            tool="track",
            action="add_comment",
            args={"track_id": "track-comment-delivery-none", "content": "No direct attention."},
        )

        self.assertTrue(response.get("ok"), msg=response)
        comment = response.get("comment")
        self.assertIsInstance(comment, dict, msg=response)
        assert isinstance(comment, dict)
        self.assertTrue(comment_repo.track_comment_file("track-comment-delivery-none", str(comment["id"])).exists())
        self.assertEqual(calls, [])
        self.assertEqual(response.get("delivery_status"), "no_targets")
        self.assertEqual(
            response.get("delivery_summary"),
            {"target_count": 0, "delivered_count": 0, "failed_count": 0},
        )
        self.assertEqual(response.get("delivery_results"), [])

    def test_add_comment_delivery_failure_keeps_comment_and_reports_status(self) -> None:
        self._seed_track("track-comment-delivery-failed")
        target_pm = {"identity_id": "act-pm-track-offline", "role_id": "pm"}
        self._patch_online_actors([{**target_pm, "status": "offline"}])
        self._patch_daemon_delivery(
            delivery={
                "delivery_status": "target_not_online",
                "handling_status": "ignored",
                "reachability_status": "registered_offline",
            }
        )

        response = self._dispatch(
            actor_id="act-dev-track-failure",
            role="dev",
            tool="track",
            action="add_comment",
            args={
                "track_id": "track-comment-delivery-failed",
                "content": "Delivery may fail but state should remain.",
                "mentioned_identity_ids": [target_pm["identity_id"]],
            },
        )

        self.assertTrue(response.get("ok"), msg=response)
        comment = response.get("comment")
        self.assertIsInstance(comment, dict, msg=response)
        assert isinstance(comment, dict)
        self.assertTrue(comment_repo.track_comment_file("track-comment-delivery-failed", str(comment["id"])).exists())
        self.assertEqual(response.get("delivery_status"), "failed")
        self.assertEqual(
            response.get("delivery_summary"),
            {"target_count": 1, "delivered_count": 0, "failed_count": 1},
        )
        results = response.get("delivery_results")
        self.assertIsInstance(results, list, msg=response)
        self.assertEqual(results[0].get("target_identity_id"), target_pm["identity_id"])
        self.assertNotIn("target_" + "actor_address", results[0])
        self.assertEqual(results[0].get("delivery_status"), "target_not_online")
        self.assertEqual(results[0].get("reachability_status"), "registered_offline")

    def test_add_comment_delivery_exception_keeps_comment_and_reports_signal_error(self) -> None:
        self._seed_track("track-comment-delivery-exception")
        target_pm = {"identity_id": "act-pm-track-exception", "role_id": "pm"}
        self._patch_online_actors([{**target_pm, "status": "online"}])
        self._patch_daemon_delivery(exc=RuntimeError("socket gone"))

        response = self._dispatch(
            actor_id="act-dev-track-exception",
            role="dev",
            tool="track",
            action="add_comment",
            args={
                "track_id": "track-comment-delivery-exception",
                "content": "Delivery exception should be visible.",
                "mentioned_identity_ids": [target_pm["identity_id"]],
            },
        )

        self.assertTrue(response.get("ok"), msg=response)
        comment = response.get("comment")
        self.assertIsInstance(comment, dict, msg=response)
        assert isinstance(comment, dict)
        self.assertTrue(comment_repo.track_comment_file("track-comment-delivery-exception", str(comment["id"])).exists())
        self.assertEqual(response.get("delivery_status"), "failed")
        results = response.get("delivery_results")
        self.assertIsInstance(results, list, msg=response)
        self.assertEqual(results[0].get("target_identity_id"), target_pm["identity_id"])
        self.assertNotIn("target_" + "actor_address", results[0])
        self.assertEqual(results[0].get("delivery_status"), "delivery_failed")
        self.assertIn("socket gone", str(results[0].get("signal_error")))

    def test_add_list_reply_and_open_are_track_native(self) -> None:
        self._seed_track("track-comment-a")
        self._seed_track("track-comment-b")
        target_pm = {"identity_id": "act-pm-mentioned", "role_id": "pm"}
        self._patch_online_actors([{**target_pm, "status": "online"}])

        root = self._dispatch(
            actor_id="act-dev-track-comment",
            role="dev",
            tool="track",
            action="add_comment",
            args={
                "track_id": "track-comment-a",
                "content": "Root Track A",
                "mentioned_identity_ids": ["act-pm-mentioned"],
            },
        )
        self.assertTrue(root.get("ok"), msg=root)
        comment = root.get("comment")
        self.assertIsInstance(comment, dict, msg=root)
        assert isinstance(comment, dict)
        self.assertEqual(comment.get("track_id"), "track-comment-a")
        self.assertEqual(comment.get("thread_id"), comment.get("id"))
        self.assertIsNone(comment.get("reply_to"))
        self.assertNotIn("target_type", comment)
        self.assertNotIn("target_id", comment)
        self.assertTrue(comment_repo.track_comment_file("track-comment-a", str(comment["id"])).exists())
        self.assertFalse((self.runtime_root / "buddyswitch" / "objects" / "comments").exists())

        reply = self._dispatch(
            actor_id="act-design-track-comment",
            role="design",
            tool="track",
            action="add_comment",
            args={"track_id": "track-comment-a", "content": "Reply Track A", "reply_to": comment["id"]},
        )
        self.assertTrue(reply.get("ok"), msg=reply)
        reply_comment = reply.get("comment")
        self.assertIsInstance(reply_comment, dict, msg=reply)
        assert isinstance(reply_comment, dict)
        self.assertEqual(reply_comment.get("thread_id"), comment["thread_id"])

        other = self._dispatch(
            actor_id="act-dev-track-comment",
            role="dev",
            tool="track",
            action="add_comment",
            args={"track_id": "track-comment-b", "content": "Root Track B"},
        )
        self.assertTrue(other.get("ok"), msg=other)
        bad_reply = self._dispatch(
            actor_id="act-dev-track-comment",
            role="dev",
            tool="track",
            action="add_comment",
            args={
                "track_id": "track-comment-a",
                "content": "Bad cross-track reply",
                "reply_to": (other.get("comment") or {}).get("id"),
            },
        )
        self.assertFalse(bad_reply.get("ok"), msg=bad_reply)
        self.assertEqual(bad_reply.get("permission_boundary"), "track_comment.reply_to_scope")

        listed = self._dispatch(
            actor_id="act-dev-track-comment",
            role="dev",
            tool="track",
            action="list_comments",
            args={"track_id": "track-comment-a", "status": "all"},
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        self.assertEqual([row.get("track_id") for row in listed.get("comments", [])], ["track-comment-a", "track-comment-a"])
        self.assertEqual(len(listed.get("threads", [])), 1)

        opened = self._dispatch(
            actor_id="act-dev-track-comment",
            role="dev",
            tool="track",
            action="open",
            args={"track_id": "track-comment-a"},
        )
        self.assertTrue(opened.get("ok"), msg=opened)
        cues = ((opened.get("track") or {}).get("comment_cues") or {})
        self.assertEqual(cues.get("open_thread_count"), 1)
        self.assertLessEqual(len(cues.get("recent_comments", [])), 3)

    def test_resolve_is_owner_only_and_exact_track_scoped(self) -> None:
        self._seed_track("track-resolve-a")
        self._seed_track("track-resolve-b")
        root_a = self._dispatch(
            actor_id="act-dev-resolve-comment",
            role="dev",
            tool="track",
            action="add_comment",
            args={"track_id": "track-resolve-a", "content": "Root A"},
        )
        root_b = self._dispatch(
            actor_id="act-dev-resolve-comment",
            role="dev",
            tool="track",
            action="add_comment",
            args={"track_id": "track-resolve-b", "content": "Root B"},
        )
        self.assertTrue(root_a.get("ok"), msg=root_a)
        self.assertTrue(root_b.get("ok"), msg=root_b)
        root_a_id = str((root_a.get("comment") or {}).get("id"))
        root_b_id = str((root_b.get("comment") or {}).get("id"))

        non_pm = self._dispatch(
            actor_id="act-dev-resolve-comment",
            role="dev",
            tool="track",
            action="resolve_comment_thread",
            args={"track_id": "track-resolve-a", "comment_id": root_a_id, "resolution_summary": "Nope"},
        )
        self.assertFalse(non_pm.get("ok"), msg=non_pm)
        self.assertEqual((non_pm.get("error") or {}).get("code"), "E_TRACK_AUTHORITY")
        self.assertEqual(non_pm.get("permission_boundary"), "track.owner_identity_id")

        cross_track = self._dispatch(
            actor_id="act-pm-resolve-comment",
            role="pm",
            tool="track",
            action="resolve_comment_thread",
            args={"track_id": "track-resolve-a", "comment_id": root_b_id, "resolution_summary": "Wrong track"},
        )
        self.assertFalse(cross_track.get("ok"), msg=cross_track)
        self.assertEqual(cross_track.get("permission_boundary"), "track_comment.thread_scope")
        self.assertEqual(comment_repo.get_track_comment("track-resolve-b", root_b_id)["status"], "open")

        resolved = self._dispatch(
            actor_id="act-pm-resolve-comment",
            role="pm",
            tool="track",
            action="resolve_comment_thread",
            args={"track_id": "track-resolve-a", "comment_id": root_a_id, "resolution_summary": "Resolved."},
        )
        self.assertTrue(resolved.get("ok"), msg=resolved)
        self.assertEqual(resolved.get("updated_ids"), [root_a_id])
        self.assertEqual((resolved.get("comments") or [])[0].get("status"), "resolved")

        repeat = self._dispatch(
            actor_id="act-pm-resolve-comment",
            role="pm",
            tool="track",
            action="resolve_comment_thread",
            args={"track_id": "track-resolve-a", "comment_id": root_a_id, "resolution_summary": "Again."},
        )
        self.assertFalse(repeat.get("ok"), msg=repeat)
        self.assertEqual(repeat.get("permission_boundary"), "track_comment.state")

    def test_old_comment_tool_and_old_payload_fields_are_rejected(self) -> None:
        self._seed_track("track-old-comment-fields")
        old_tool = self._dispatch(
            actor_id="act-dev-old-comment",
            role="dev",
            tool="comment",
            action="add",
            args={"target_type": "track", "target_id": "track-old-comment-fields", "content": "old"},
        )
        self.assertFalse(old_tool.get("ok"), msg=old_tool)
        self.assertEqual((old_tool.get("error") or {}).get("code"), "E_ENV_TOOL")

        old_fields = self._dispatch(
            actor_id="act-dev-old-comment",
            role="dev",
            tool="track",
            action="add_comment",
            args={
                "track_id": "track-old-comment-fields",
                "target_type": "artifact",
                "target_id": "art-old",
                "anchor": "section",
                "artifact_revision_id": "art-old-r1",
                "content": "old fields",
            },
        )
        self.assertFalse(old_fields.get("ok"), msg=old_fields)
        self.assertEqual(old_fields.get("permission_boundary"), "request-payload")
        self.assertEqual(
            old_fields.get("correctable_fields"),
            ["anchor", "artifact_revision_id", "target_id", "target_type"],
        )
