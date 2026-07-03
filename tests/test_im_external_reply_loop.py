#!/usr/bin/env python3
"""External-user Central IM reply loop acceptance tests."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))

from tools.launcher import daemon_mailbox  # noqa: E402
from tools.launcher import im_http_router  # noqa: E402
from tools.launcher import im_wake_handler  # noqa: E402
from env.tool_runtime import daemon_client  # noqa: E402
from env.tool_runtime import im_client as im_client_module  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


class _ActorContext(dict[str, Any]):
    def __init__(self, *, identity_id: str, role_id: str, daemon: Any) -> None:
        super().__init__(
            current_identity={"id": identity_id, "type": "actor"},
            active_role=role_id,
            manifest={"roles": [{"id": role_id}]},
        )
        self.daemon = daemon


class _WakeDaemon:
    def __init__(self) -> None:
        self.wake_calls: list[dict[str, Any]] = []

    def wake_im_actor(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.wake_calls.append(dict(payload))
        return {"wake_status": "submitted", "runtime_target": "parent", "error": None}


class _RecordingTriggerDispatcher:
    def __init__(self) -> None:
        self.triggers: list[Any] = []

    def __call__(self, trigger: Any) -> dict[str, Any]:
        self.triggers.append(trigger)
        return {
            "accepted": True,
            "handled_count": 1,
            "matched_count": 1,
            "handling_status": "handled",
        }


class _Runtime:
    def __init__(self, *, identity_id: str, role_id: str) -> None:
        self.identity_id = identity_id
        self.role_id = role_id
        self.parent_prompts: list[dict[str, Any]] = []
        self.task_sys_instructions: list[dict[str, Any]] = []

    def parent_activity(self) -> dict[str, str]:
        return {"status": "idle"}

    def submit_parent_prompt(self, prompt: str, **kwargs: Any) -> None:
        self.parent_prompts.append({"prompt": prompt, **kwargs})

    def execute_task_sys_instruction(self, instruction: dict[str, Any]) -> dict[str, Any]:
        expected = {"actor_id": self.identity_id, "role_id": self.role_id}
        if instruction.get("actor_target") != expected:
            raise AssertionError(f"wrong task sys target: {instruction.get('actor_target')!r}")
        self.task_sys_instructions.append(instruction)
        return {"action": instruction["type"], "task_id": instruction["task_id"]}


class _WakeHandlerDispatcher:
    def __init__(self, *, identity_id: str, role_id: str) -> None:
        self.context = type("Context", (), {"actor_id": identity_id, "role": role_id})()
        self.runtime = _Runtime(identity_id=identity_id, role_id=role_id)
        self.handler = im_wake_handler.ImMessageCreatedHandler()
        self.triggers: list[Any] = []
        self.task_sys_instructions = self.runtime.task_sys_instructions

    def __call__(self, trigger: Any) -> dict[str, Any]:
        self.triggers.append(trigger)
        result = self.handler.handle(self.context, None, self.runtime, trigger)
        return {
            "accepted": True,
            "handled_count": 1 if result.status == "handled" else 0,
            "matched_count": 1,
            "handling_status": result.status,
        }

class ImExternalReplyLoopTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _create_connection(self, router: im_http_router.ImHttpRouter) -> str:
        status, created = router.handle(
            "POST",
            "/api/im/connections",
            json.dumps({"display_name": "local acceptance"}).encode("utf-8"),
            {},
        )
        self.assertEqual(status, 200, msg=created)
        self.assertTrue(created.get("ok"), msg=created)
        self.assertIsInstance(created.get("connection_key"), str, msg=created)
        self.assertNotIn("participant_" + "token", created)
        self.assertNotIn("event_" + "cursor", created)
        return str(created["connection_key"])

    def test_external_send_actor_reply_to_external_visible_once_without_cursor(self) -> None:
        actor_identity_id = self._runtime_actor_id(role="market", label="reply-loop")
        daemon = _WakeDaemon()
        router = im_http_router.ImHttpRouter(
            actor_lister=lambda _role_id: [
                {
                    "identity_id": actor_identity_id,
                    "identity": {"id": actor_identity_id, "type": "actor"},
                    "role_id": "market",
                    "status": "online",
                }
            ],
            wake_actor=daemon.wake_im_actor,
        )
        key = self._create_connection(router)

        status, sent = router.handle(
            "POST",
            "/api/im/messages",
            json.dumps(
                {
                    "target_identity_id": actor_identity_id,
                    "content": "ping",
                }
            ).encode("utf-8"),
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200, msg=sent)
        self.assertEqual(sent["delivery_status"], "accepted")
        self.assertEqual(sent["wake_status"], "submitted")
        self.assertNotIn("next_cursor", sent)
        self.assertEqual(len(daemon.wake_calls), 1)
        original_message_id = sent["message"]["id"]

        actor_client = im_client_module.ActorImClient(_ActorContext(identity_id=actor_identity_id, role_id="market", daemon=daemon))
        reply = actor_client.send({"content": "pong", "reply_to": original_message_id})

        self.assertTrue(reply.get("ok"), msg=reply)
        self.assertEqual(reply["message"]["reply_to"], original_message_id)
        self.assertEqual(reply["wake_status"], "not_applicable")

        status, events = router.handle(
            "GET",
            "/api/im/events?wait_ms=0",
            b"",
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200, msg=events)
        self.assertEqual([event["message_id"] for event in events["events"]], [reply["message"]["id"]])
        self.assertNotIn("next_cursor", events)

        status, repeated = router.handle(
            "GET",
            "/api/im/events?wait_ms=0",
            b"",
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200, msg=repeated)
        self.assertEqual([event["message_id"] for event in repeated["events"]], [reply["message"]["id"]])

        status, acked = router.handle(
            "POST",
            "/api/im/events/ack",
            json.dumps({"event_id": reply["event_id"]}).encode("utf-8"),
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200, msg=acked)
        self.assertTrue(acked["ok"], msg=acked)

        status, after_ack = router.handle(
            "GET",
            "/api/im/events?wait_ms=0",
            b"",
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200, msg=after_ack)
        self.assertEqual(after_ack["events"], [])

        status, fetched = router.handle(
            "GET",
            f"/api/im/messages/{reply['message']['id']}",
            b"",
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200, msg=fetched)
        self.assertEqual(fetched["message"]["content"], "pong")
        self.assertEqual(fetched["message"]["reply_to"], original_message_id)

    def test_wake_bridge_submits_local_im_trigger_to_target_mailbox(self) -> None:
        target_identity_id = "act-market-wake"
        target_role_id = "market"
        mailbox_calls: list[dict[str, Any]] = []

        def fake_check_reachability(*, target_identity_id: str, socket_path: Path | None = None) -> dict[str, Any]:
            self.assertEqual(target_identity_id, "act-market-wake")
            self.assertIsNone(socket_path)
            return {
                "reachability_status": "online",
                "target_identity_id": target_identity_id,
                "record": {
                    "identity_id": target_identity_id,
                    "role_id": target_role_id,
                    "endpoint": {
                        "kind": "daemon_mailbox_socket",
                        "socket_path": "/tmp/buddyswitch-test-mailbox.sock",
                    },
                    "status": "online",
                },
            }

        def fake_request_mailbox(method: str, params: dict[str, Any], *, socket_path: Path) -> dict[str, Any]:
            mailbox_calls.append({"method": method, "params": params, "socket_path": str(socket_path)})
            return {"ok": True, "result": {"handling_status": "handled"}}

        result = daemon_client.wake_im_actor(
            {
                "type": "im.message.created",
                "wake_id": "imwake-1",
                "target_identity_id": target_identity_id,
                "target_role_id": target_role_id,
                "message_id": "msg-1",
                "conversation_id": "conv-1",
                "event_id": "imev-1",
            },
            check_reachability_fn=fake_check_reachability,
            request_mailbox_fn=fake_request_mailbox,
        )

        self.assertEqual(result["wake_status"], "submitted")
        self.assertEqual(len(mailbox_calls), 1)
        self.assertEqual(mailbox_calls[0]["method"], "mailbox.local_trigger")
        self.assertEqual(mailbox_calls[0]["socket_path"], "/tmp/buddyswitch-test-mailbox.sock")
        self.assertEqual(
            mailbox_calls[0]["params"],
            {
                "identity_id": target_identity_id,
                "role_id": target_role_id,
                "type": "im.message.created",
                "payload": {"message_id": "msg-1", "conversation_id": "conv-1", "event_id": "imev-1"},
                "origin_id": "msg-1",
                "correlation_id": "imwake-1",
                "source_context": {"source": "central_im"},
            },
        )

    def test_wake_bridge_reaches_real_mailbox_socket_and_im_handler(self) -> None:
        target_identity_id = "act-market-wake"
        target_role_id = "market"
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = Path(temp_root) / "mailbox.sock"
            dispatcher = _WakeHandlerDispatcher(identity_id=target_identity_id, role_id=target_role_id)
            server = daemon_mailbox.DaemonMailboxServer(
                socket_path=socket_path,
                local_identity_id=target_identity_id,
                local_role_id=target_role_id,
                handlers=[],
                trigger_dispatcher=dispatcher,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.close)
            self.addCleanup(thread.join, 2)

            result = daemon_client.wake_im_actor(
                {
                    "type": "im.message.created",
                    "wake_id": "imwake-socket",
                    "target_identity_id": target_identity_id,
                    "target_role_id": target_role_id,
                    "message_id": "msg-socket",
                    "conversation_id": "conv-socket",
                    "event_id": "imev-socket",
                },
                check_reachability_fn=lambda **_kwargs: {
                    "reachability_status": "online",
                    "record": {
                        "identity_id": target_identity_id,
                        "role_id": target_role_id,
                        "endpoint": {"kind": "daemon_mailbox_socket", "socket_path": str(socket_path)},
                    },
                },
            )
            server.close()
            thread.join(timeout=2)

        self.assertEqual(result["wake_status"], "submitted", msg=result)
        self.assertEqual(result["handling_status"], "handled")
        self.assertEqual(len(dispatcher.triggers), 1)
        trigger = dispatcher.triggers[0]
        self.assertEqual(trigger.type, "im.message.created")
        self.assertEqual(trigger.origin_id, "msg-socket")
        self.assertEqual(trigger.correlation_id, "imwake-socket")
        self.assertEqual(trigger.payload, {"message_id": "msg-socket", "conversation_id": "conv-socket", "event_id": "imev-socket"})
        self.assertEqual(trigger.source_context, {"source": "central_im"})
        self.assertEqual(dispatcher.runtime.parent_prompts, [])
        self.assertEqual(len(dispatcher.task_sys_instructions), 1)
        instruction = dispatcher.task_sys_instructions[0]
        self.assertEqual(instruction["type"], "start_side")
        self.assertEqual(instruction["actor_target"], {"actor_id": target_identity_id, "role_id": target_role_id})
        frame = instruction["frame"]
        self.assertEqual(frame["kind"], "task_sys.side_frame")
        self.assertEqual(frame["source"]["type"], "im.message.created")
        self.assertEqual(
            frame["source"]["ref"],
            {"message_id": "msg-socket", "conversation_id": "conv-socket", "event_id": "imev-socket"},
        )

    def test_wake_bridge_reports_offline_target_without_mailbox_request(self) -> None:
        mailbox_calls: list[dict[str, Any]] = []

        result = daemon_client.wake_im_actor(
            {
                "type": "im.message.created",
                "wake_id": "imwake-1",
                "target_identity_id": "act-market-offline",
                "target_role_id": "market",
                "message_id": "msg-1",
                "conversation_id": "conv-1",
                "event_id": "imev-1",
            },
            check_reachability_fn=lambda **_kwargs: {
                "reachability_status": "registered_offline",
                "record": None,
            },
            request_mailbox_fn=lambda *args, **kwargs: mailbox_calls.append({"args": args, "kwargs": kwargs}) or {},
        )

        self.assertEqual(result["wake_status"], "target_not_online")
        self.assertEqual(result["runtime_target"], "none")
        self.assertEqual(mailbox_calls, [])

    def test_no_external_reply_loop_shortcuts_in_active_surfaces(self) -> None:
        active_surface = "\n".join(
            (
                (ROOT / "tools/launcher/web_management.py").read_text(encoding="utf-8"),
                (ROOT / "tools/launcher/assets/web-management/app.js").read_text(encoding="utf-8"),
                (ROOT / "scripts/env/tool_runtime/im_client.py").read_text(encoding="utf-8"),
                (ROOT / "scripts/env/tools/message/_impl.py").read_text(encoding="utf-8"),
            )
        )

        self.assertNotIn("/api/messages" + "/send", active_surface)
        self.assertNotIn("act-user" + "-local", active_surface)
        self.assertNotIn("WebUser" + "ActorRuntime", active_surface)
        self.assertNotIn("send_from_web" + "_user", active_surface)
        self.assertNotIn("message" + ".available", active_surface)


if __name__ == "__main__":
    unittest.main()
