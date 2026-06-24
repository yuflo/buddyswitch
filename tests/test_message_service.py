#!/usr/bin/env python3
"""Tests for the public message send service."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.repos import messages as message_repo  # noqa: E402
from env.services import messages as message_service  # noqa: E402
from env.tool_runtime import context as runtime_context  # noqa: E402
from env.tool_runtime.actor_profile import ActorAddress  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


WEB_USER_ACTOR_ADDRESS = {"role_id": "user", "actor_id": "act-user-local"}


class _FakeDaemon:
    def __init__(
        self,
        *,
        source_actor_address: dict[str, str],
        reachability: dict[str, object] | None = None,
        delivery: dict[str, object] | None = None,
    ) -> None:
        self.source_actor_address = source_actor_address
        self.reachability = reachability
        self.delivery = delivery
        self.calls: list[tuple[str, dict[str, object]]] = []

    def check_reachability(self, *, target_actor_address: ActorAddress | dict[str, object]) -> dict[str, object]:
        target = target_actor_address.to_payload() if isinstance(target_actor_address, ActorAddress) else dict(target_actor_address)
        self.calls.append(("reachability", {"target_actor_address": target}))
        if self.reachability is not None:
            return dict(self.reachability, target_actor_address=target)
        return {
            "reachability_status": "online",
            "target_actor_address": target,
            "record": {"actor_address": target, "status": "online"},
        }

    def deliver_message_available(
        self,
        *,
        message_id: str,
        target_actor_address: ActorAddress | dict[str, object],
    ) -> dict[str, object]:
        target = target_actor_address.to_payload() if isinstance(target_actor_address, ActorAddress) else dict(target_actor_address)
        signal = {
            "type": "message.available",
            "source_actor_address": dict(self.source_actor_address),
            "target_actor_address": target,
            "payload": {"message_id": message_id},
        }
        self.calls.append(("deliver", {"message_id": message_id, "target_actor_address": target, "signal": signal}))
        if self.delivery is not None:
            return dict(self.delivery, signal=signal)
        return {
            "delivery_status": "delivered",
            "handling_status": "handled",
            "signal": signal,
        }


class _ServiceContext:
    def __init__(
        self,
        *,
        active_actor: dict[str, str],
        manifest_roles: list[str] | None = None,
        reachability: dict[str, object] | None = None,
        delivery: dict[str, object] | None = None,
    ) -> None:
        self.active_actor = dict(active_actor)
        self.actor_address = ActorAddress.from_payload(active_actor)
        self.active_role = self.actor_address.role_id
        self.actor_id = self.actor_address.actor_id
        self.role_id = self.actor_address.role_id
        self.manifest = {"roles": [{"id": role} for role in (manifest_roles or ["pm", "dev", "design", "market"])]}
        self.rules = runtime_context.DomainAccess()
        self.repos = runtime_context.RepoAccess()
        self.daemon = _FakeDaemon(
            source_actor_address=self.actor_address.to_payload(),
            reachability=reachability,
            delivery=delivery,
        )

    def __getitem__(self, key: str) -> Any:
        if key == "active_actor":
            return dict(self.active_actor)
        if key == "active_role":
            return self.active_role
        if key == "actor_id":
            return self.actor_id
        if key == "role_id":
            return self.role_id
        if key == "manifest":
            return self.manifest
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


class MessageServiceTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _actor_address(self, *, role: str, label: str) -> dict[str, str]:
        return ActorAddress(role_id=role, actor_id=self._runtime_actor_id(role=role, label=label)).to_payload()

    def _context(
        self,
        *,
        active_actor: dict[str, str],
        manifest_roles: list[str] | None = None,
        reachability: dict[str, object] | None = None,
        delivery: dict[str, object] | None = None,
    ) -> _ServiceContext:
        return _ServiceContext(
            active_actor=active_actor,
            manifest_roles=manifest_roles,
            reachability=reachability,
            delivery=delivery,
        )

    def test_send_from_actor_creates_durable_message_and_delivers_signal(self) -> None:
        source = self._actor_address(role="design", label="source")
        target = self._actor_address(role="dev", label="target")
        context = self._context(active_actor=source)

        response = message_service.send_from_actor(
            args={"target_actor_address": target, "content": "  Please inspect this.  "},
            context=context,
            source_actor_address=context.actor_address,
            active_actor=context["active_actor"],
            active_role=context["active_role"],
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("delivery_status"), "delivered")
        self.assertEqual(response.get("handling_status"), "handled")
        self.assertEqual(response.get("durability"), "durable")
        self.assertIs(response.get("state_changed"), True)
        rows = message_repo.list_messages()
        self.assertEqual(len(rows), 1)
        message = rows[0]
        self.assertEqual(message["from_actor_address"], source)
        self.assertEqual(message["to_actor_address"], target)
        self.assertEqual(message["content"], "Please inspect this.")
        self.assertEqual(context.daemon.calls[0][0], "reachability")
        self.assertEqual(context.daemon.calls[1][0], "deliver")
        signal = context.daemon.calls[1][1]["signal"]
        self.assertEqual(signal["type"], "message.available")
        self.assertEqual(signal["source_actor_address"], source)
        self.assertEqual(signal["target_actor_address"], target)
        self.assertEqual(signal["payload"], {"message_id": response.get("message_id")})

    def test_send_from_actor_rejects_unknown_fields_before_reachability(self) -> None:
        source = self._actor_address(role="pm", label="source")
        target = self._actor_address(role="dev", label="target")
        context = self._context(active_actor=source)

        response = message_service.send_from_actor(
            args={"target_actor_address": target, "content": "hello", "metadata": {"x": 1}},
            context=context,
            source_actor_address=context.actor_address,
            active_actor=context["active_actor"],
            active_role=context["active_role"],
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_PAYLOAD")
        self.assertEqual(response.get("correctable_fields"), ["metadata"])
        self.assertEqual(message_repo.list_messages(), [])
        self.assertEqual(context.daemon.calls, [])

    def test_send_from_actor_target_not_online_creates_no_message(self) -> None:
        source = self._actor_address(role="pm", label="source")
        target = self._actor_address(role="dev", label="target")
        context = self._context(
            active_actor=source,
            reachability={"reachability_status": "registered_offline", "record": None},
        )

        response = message_service.send_from_actor(
            args={"target_actor_address": target, "content": "hello"},
            context=context,
            source_actor_address=context.actor_address,
            active_actor=context["active_actor"],
            active_role=context["active_role"],
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_TARGET_NOT_ONLINE")
        self.assertEqual(response.get("reachability_status"), "registered_offline")
        self.assertEqual(response.get("durability"), "none")
        self.assertIs(response.get("state_changed"), False)
        self.assertEqual(message_repo.list_messages(), [])
        self.assertEqual([call[0] for call in context.daemon.calls], ["reachability"])

    def test_send_from_actor_delivery_failure_cleans_created_message(self) -> None:
        source = self._actor_address(role="pm", label="source")
        target = self._actor_address(role="dev", label="target")
        context = self._context(
            active_actor=source,
            delivery={"delivery_status": "delivery_failed", "signal_error": "socket gone"},
        )

        response = message_service.send_from_actor(
            args={"target_actor_address": target, "content": "hello"},
            context=context,
            source_actor_address=context.actor_address,
            active_actor=context["active_actor"],
            active_role=context["active_role"],
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("delivery_status"), "delivery_failed")
        self.assertEqual(response.get("cleanup_status"), "cleaned")
        self.assertEqual(response.get("durability"), "none")
        self.assertIs(response.get("state_changed"), False)
        self.assertEqual(message_repo.list_messages(), [])

    def test_send_from_actor_cleanup_failure_reports_indeterminate_state(self) -> None:
        source = self._actor_address(role="pm", label="source")
        target = self._actor_address(role="dev", label="target")
        context = self._context(
            active_actor=source,
            delivery={"delivery_status": "delivery_failed", "signal_error": "socket gone"},
        )
        original_delete = message_repo.delete_message

        def fail_delete(_message_id: str) -> bool:
            raise OSError("unlink failed")

        message_repo.delete_message = fail_delete
        self.addCleanup(setattr, message_repo, "delete_message", original_delete)

        response = message_service.send_from_actor(
            args={"target_actor_address": target, "content": "hello"},
            context=context,
            source_actor_address=context.actor_address,
            active_actor=context["active_actor"],
            active_role=context["active_role"],
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_SEND_INDETERMINATE")
        self.assertEqual(response.get("delivery_status"), "delivery_failed")
        self.assertEqual(response.get("cleanup_status"), "failed")
        self.assertEqual(response.get("durability"), "uncertain")
        self.assertIs(response.get("state_changed"), True)
        self.assertIsInstance(response.get("message_id"), str)
        self.assertEqual(len(message_repo.list_messages()), 1)

    def test_send_from_actor_reply_updates_original_disposition(self) -> None:
        active = self._actor_address(role="dev", label="active")
        sender = self._actor_address(role="pm", label="sender")
        original = message_repo.save_message(
            {
                "id": "msg-needs-reply",
                "from_actor_address": sender,
                "to_actor_address": active,
                "content": "Can you review this?",
                "reply_to": None,
                "created_at": "2026-06-24T00:00:00Z",
            }
        )
        context = self._context(active_actor=active)

        response = message_service.send_from_actor(
            args={"target_actor_address": sender, "content": "Reviewed.", "reply_to": original["id"]},
            context=context,
            source_actor_address=context.actor_address,
            active_actor=context["active_actor"],
            active_role=context["active_role"],
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("reply_to"), original["id"])
        stored = message_repo.get_message(original["id"])
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored["disposition"], "replied")
        self.assertEqual(stored["processed_by_actor_address"], active)

    def test_send_from_web_user_skips_manifest_role_requirement_only_for_web_user_adapter(self) -> None:
        target = self._actor_address(role="dev", label="target")
        context = self._context(active_actor=WEB_USER_ACTOR_ADDRESS, manifest_roles=["dev"])

        actor_response = message_service.send_from_actor(
            args={"target_actor_address": target, "content": "hello"},
            context=context,
            source_actor_address=context.actor_address,
            active_actor=context["active_actor"],
            active_role=context["active_role"],
        )
        web_response = message_service.send_from_web_user(
            context=context,
            target_actor_address=target,
            content="hello",
            web_user_actor_address=WEB_USER_ACTOR_ADDRESS,
        )

        self.assertFalse(actor_response.get("ok"), msg=actor_response)
        self.assertEqual(actor_response.get("permission_boundary"), "message.manifest_role")
        self.assertTrue(web_response.get("ok"), msg=web_response)
        rows = message_repo.list_messages()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["from_actor_address"], WEB_USER_ACTOR_ADDRESS)


if __name__ == "__main__":
    unittest.main()
