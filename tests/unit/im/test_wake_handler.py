"""Runtime wake handling tests for Central IM."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import buddyswitch.foundation.identity.profiles as identity_profiles
import buddyswitch.foundation.state.runtime as state_runtime
from buddyswitch.modules.communication.private.adapters.daemon import (
    im_wake_handler,
)
from buddyswitch.modules.communication.private.domain import (
    messages as message_service,
)
from tests.support.runtime import RuntimeWorkspaceTestCase


@dataclass
class _Context:
    actor_id: str
    role: str


@dataclass
class _Trigger:
    type: str
    target_identity_id: str
    target_role_id: str
    payload: dict[str, str]


class _Runtime:
    def parent_activity(self) -> dict[str, str]:
        raise AssertionError("IM wake handler must not inspect parent activity")

    def input_actor(self, _text: str) -> dict[str, str]:
        raise AssertionError("IM wake handler must delegate attention through the Demand adapter")


class _State:
    pass


class ImWakeHandlerTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.route = {
            "identity_id": self._runtime_actor_id(role="market", label="im-demand-target"),
            "role_id": "market",
        }
        self.context = _Context(
            actor_id=self.route["identity_id"],
            role=self.route["role_id"],
        )
        self._save_actor(self.route["identity_id"], self.route["role_id"])
        self.enqueue_calls: list[dict[str, Any]] = []

    def _save_actor(self, actor_id: str, role_id: str) -> None:
        identity_profiles.save_actor_identity_profile({
            "identity": {"id": actor_id, "type": "actor"},
            "role_id": role_id,
        })

    def _external_identity(self, display_name: str = "wake sender") -> dict[str, str]:
        created = message_service.create_external_session(display_name=display_name)
        authenticated = message_service.authenticate_external_session_key(
            created["external_session_key"]
        )
        self.assertTrue(authenticated["ok"], authenticated)
        return authenticated["identity"]

    def _persist_message(
        self,
        *,
        sender_identity: dict[str, str] | None = None,
        target_identity: dict[str, str] | None = None,
        content: str = "Support user data CSV export.",
    ) -> tuple[dict[str, Any], _Trigger]:
        sent = message_service.send_im_message(
            sender_identity=sender_identity or self._external_identity(),
            target_identity=target_identity or {
                "id": self.route["identity_id"],
                "type": "actor",
            },
            content=content,
        )
        self.assertTrue(sent["ok"], sent)
        trigger = _Trigger(
            type="im.message.created",
            target_identity_id=self.route["identity_id"],
            target_role_id=self.route["role_id"],
            payload={
                "message_id": sent["message"]["id"],
                "conversation_id": sent["message"]["conversation_id"],
                "event_id": sent["event_id"],
            },
        )
        return sent, trigger

    def _enqueue_inbound(
        self,
        state: Any,
        **intake: Any,
    ) -> dict[str, Any]:
        self.enqueue_calls.append({"state": state, **intake})
        return {"schedule_id": "schedule-handler-probe"}

    def _task_records(self) -> list[dict[str, Any]]:
        tasks_dir = state_runtime.OBJECTS_ROOT / "task-sys" / "tasks"
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(tasks_dir.glob("*.json"))
        ]

    def test_exact_target_visible_message_maps_to_one_demand_intake_schedule(self) -> None:
        sent, trigger = self._persist_message()
        runtime = _Runtime()
        state = _State()

        result = im_wake_handler.ImMessageCreatedHandler(self._enqueue_inbound).handle(
            self.context,
            state,
            runtime,
            trigger,
        )

        message_id = sent["message"]["id"]
        conversation_id = sent["message"]["conversation_id"]
        event_id = sent["event_id"]
        self.assertEqual(result.status, "handled")
        self.assertEqual(
            self.enqueue_calls,
            [{
                "state": state,
                "source_key": f"im.message.created:{message_id}",
                "description": "Support user data CSV export.",
                "detail": "Support user data CSV export.",
                "source_refs": [{
                    "type": "im.message.created",
                    "ref": {
                        "message_id": message_id,
                        "conversation_id": conversation_id,
                        "event_id": event_id,
                    },
                }],
            }],
        )
        self.assertEqual(self._task_records(), [])

    def test_wrong_target_actor_fails_before_capture(self) -> None:
        _sent, trigger = self._persist_message()
        trigger.target_identity_id = self._runtime_actor_id(
            role="market",
            label="wrong-im-target",
        )

        result = im_wake_handler.ImMessageCreatedHandler(self._enqueue_inbound).handle(
            self.context,
            None,
            _Runtime(),
            trigger,
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("wrong target identity", result.message or "")
        self.assertEqual(self.enqueue_calls, [])
        self.assertEqual(self._task_records(), [])

    def test_missing_message_or_event_fails_before_capture(self) -> None:
        _sent, valid_trigger = self._persist_message()
        cases = (
            ("message_id", "msg-missing"),
            ("event_id", "imev-missing"),
        )
        for field, value in cases:
            with self.subTest(field=field):
                trigger = _Trigger(
                    type=valid_trigger.type,
                    target_identity_id=valid_trigger.target_identity_id,
                    target_role_id=valid_trigger.target_role_id,
                    payload={**valid_trigger.payload, field: value},
                )
                result = im_wake_handler.ImMessageCreatedHandler(self._enqueue_inbound).handle(
                    self.context,
                    None,
                    _Runtime(),
                    trigger,
                )
                self.assertEqual(result.status, "failed")

        self.assertEqual(self.enqueue_calls, [])
        self.assertEqual(self._task_records(), [])

    def test_mismatched_conversation_or_event_link_fails_before_capture(self) -> None:
        _first, first_trigger = self._persist_message(content="first need")
        _second, second_trigger = self._persist_message(content="second need")
        cases = (
            {**first_trigger.payload, "conversation_id": "conv-mismatch"},
            {**first_trigger.payload, "event_id": second_trigger.payload["event_id"]},
        )
        for payload in cases:
            with self.subTest(payload=payload):
                trigger = _Trigger(
                    type=first_trigger.type,
                    target_identity_id=first_trigger.target_identity_id,
                    target_role_id=first_trigger.target_role_id,
                    payload=payload,
                )
                result = im_wake_handler.ImMessageCreatedHandler(self._enqueue_inbound).handle(
                    self.context,
                    None,
                    _Runtime(),
                    trigger,
                )
                self.assertEqual(result.status, "failed")

        self.assertEqual(self.enqueue_calls, [])
        self.assertEqual(self._task_records(), [])

    def test_conversation_member_that_is_not_message_target_fails_before_capture(self) -> None:
        other_actor_id = self._runtime_actor_id(role="dev", label="other-im-target")
        self._save_actor(other_actor_id, "dev")
        _sent, trigger = self._persist_message(
            sender_identity={"id": self.route["identity_id"], "type": "actor"},
            target_identity={"id": other_actor_id, "type": "actor"},
            content="Message for a different actor.",
        )

        result = im_wake_handler.ImMessageCreatedHandler(self._enqueue_inbound).handle(
            self.context,
            None,
            _Runtime(),
            trigger,
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("target", result.message or "")
        self.assertEqual(self.enqueue_calls, [])
        self.assertEqual(self._task_records(), [])

    def test_enqueue_error_returns_failed_and_keeps_task_projection_empty(self) -> None:
        _sent, trigger = self._persist_message()
        failing_enqueue = lambda *_args, **_kwargs: (
            (_ for _ in ()).throw(RuntimeError("demand schedule unavailable"))
        )

        result = im_wake_handler.ImMessageCreatedHandler(failing_enqueue).handle(
            self.context,
            None,
            _Runtime(),
            trigger,
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("demand schedule unavailable", result.message or "")
        self.assertEqual(self.enqueue_calls, [])
        self.assertEqual(self._task_records(), [])

    def test_handler_does_not_handle_unrelated_event(self) -> None:
        handler = im_wake_handler.ImMessageCreatedHandler(self._enqueue_inbound)
        trigger = _Trigger(
            "example.ready",
            self.route["identity_id"],
            self.route["role_id"],
            {"message_id": "msg-unrelated"},
        )

        self.assertFalse(handler.handles(trigger))
        result = handler.handle(self.context, None, _Runtime(), trigger)
        self.assertEqual(result.status, "ignored")
        self.assertEqual(self.enqueue_calls, [])
