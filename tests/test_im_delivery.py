#!/usr/bin/env python3

from __future__ import annotations

import unittest
from typing import Any

from env.services import messages as message_service


class ImDeliveryTests(unittest.TestCase):
    def test_actor_target_delivery_uses_only_identity_and_message_refs(self) -> None:
        calls: list[dict[str, Any]] = []
        result = {
            "ok": True,
            "message": {"id": "msg-1", "conversation_id": "conv-1", "reply_to": None},
            "target_identity": {"id": "act-target", "type": "actor"},
            "event_id": "imev-1",
            "delivery_status": "accepted",
        }

        delivered = message_service.attach_post_write_delivery_status(
            result,
            actor_delivery_handler=lambda payload: calls.append(dict(payload))
            or {"actor_handling_status": "submitted"},
        )

        self.assertIs(delivered, result)
        self.assertEqual(delivered["actor_handling_status"], "submitted")
        self.assertEqual(
            calls,
            [
                {
                    "type": "im.message.created",
                    "target_identity_id": "act-target",
                    "message_id": "msg-1",
                    "conversation_id": "conv-1",
                    "event_id": "imev-1",
                }
            ],
        )
        self.assertNotIn("target_role_id", calls[0])
        self.assertNotIn("content", calls[0])
        self.assertNotIn("sender_identity", calls[0])

    def test_external_target_does_not_call_actor_delivery(self) -> None:
        calls: list[dict[str, Any]] = []
        result = {
            "ok": True,
            "message": {"id": "msg-2", "conversation_id": "conv-2", "reply_to": "msg-1"},
            "target_identity": {"id": "ext-target", "type": "external"},
            "event_id": "imev-2",
            "delivery_status": "accepted",
        }

        delivered = message_service.attach_post_write_delivery_status(
            result,
            actor_delivery_handler=lambda payload: calls.append(dict(payload))
            or {"actor_handling_status": "submitted"},
        )

        self.assertIs(delivered, result)
        self.assertEqual(delivered["actor_handling_status"], "not_applicable")
        self.assertEqual(calls, [])

    def test_actor_target_missing_message_refs_fails_without_delivery_call(self) -> None:
        calls: list[dict[str, Any]] = []
        result = {
            "ok": True,
            "target_identity": {"id": "act-target", "type": "actor"},
            "event_id": "imev-3",
        }

        delivered = message_service.attach_post_write_delivery_status(
            result,
            actor_delivery_handler=lambda payload: calls.append(dict(payload))
            or {"actor_handling_status": "submitted"},
        )

        self.assertIs(delivered, result)
        self.assertEqual(delivered["actor_handling_status"], "handling_failed")
        self.assertEqual(calls, [])

    def test_non_ok_write_result_is_returned_without_delivery_status_mutation(self) -> None:
        result = {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": "bad"}}

        delivered = message_service.attach_post_write_delivery_status(
            result,
            actor_delivery_handler=lambda _payload: self.fail("actor delivery must not be called"),
        )

        self.assertIs(delivered, result)
        self.assertEqual(result, {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": "bad"}})


if __name__ == "__main__":
    unittest.main()
