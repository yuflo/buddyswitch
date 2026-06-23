#!/usr/bin/env python3
"""Tests for the web-user actor message adapter."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
LAUNCHER = ROOT / "tools" / "launcher"
for candidate in (SCRIPTS, LAUNCHER):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

WEB_USER_ACTOR_PATH = ROOT / "tools" / "launcher" / "web_user_actor.py"
if not WEB_USER_ACTOR_PATH.exists():
    raise AssertionError(f"expected module to exist: {WEB_USER_ACTOR_PATH}")

SPEC = importlib.util.spec_from_file_location("buddyswitch_web_user_actor", WEB_USER_ACTOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load spec for {WEB_USER_ACTOR_PATH}")
WEB_USER_ACTOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = WEB_USER_ACTOR
SPEC.loader.exec_module(WEB_USER_ACTOR)

import daemon_mailbox  # noqa: E402
from env.repos import messages as message_repo  # noqa: E402
from env.tool_runtime import daemon_client  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


class _Trigger:
    def __init__(self, *, trigger_type: str, payload: dict[str, Any]) -> None:
        self.type = trigger_type
        self.payload = payload


class WebUserActorTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _message_rows(self) -> list[dict[str, object]]:
        return message_repo.list_messages()

    def _patch_daemon(
        self,
        *,
        reachability: dict[str, object] | None = None,
        delivery: dict[str, object] | None = None,
    ) -> list[tuple[str, dict[str, object]]]:
        calls: list[tuple[str, dict[str, object]]] = []
        original_check_reachability = daemon_client.check_reachability
        original_deliver_signal = daemon_client.deliver_signal

        def fake_check_reachability(*, target_actor_address: dict[str, object]) -> dict[str, object]:
            calls.append(("reachability", {"target_actor_address": target_actor_address}))
            if reachability is not None:
                return dict(reachability, target_actor_address=target_actor_address)
            return {
                "reachability_status": "online",
                "target_actor_address": target_actor_address,
                "record": {"actor_address": target_actor_address, "status": "online"},
            }

        def fake_deliver_signal(*, signal: dict[str, object]) -> dict[str, object]:
            calls.append(("deliver", {"signal": signal}))
            if delivery is not None:
                return dict(delivery, signal=signal)
            return {
                "delivery_status": "delivered",
                "handling_status": "handled",
                "signal": signal,
            }

        def restore() -> None:
            daemon_client.check_reachability = original_check_reachability
            daemon_client.deliver_signal = original_deliver_signal

        daemon_client.check_reachability = fake_check_reachability
        daemon_client.deliver_signal = fake_deliver_signal
        self.addCleanup(restore)
        return calls

    def test_web_user_actor_address_is_external_user(self) -> None:
        self.assertEqual(
            WEB_USER_ACTOR.WEB_USER_ACTOR_ADDRESS,
            {"role_id": "user", "actor_id": "act-user-local"},
        )
        manifest = json.loads(json.dumps({"roles": [{"id": "pm"}, {"id": "dev"}]}))
        roles = WEB_USER_ACTOR.runtime_context.DomainAccess().message.manifest_role_ids(manifest)
        self.assertNotIn("user", roles)

    def test_web_user_business_strings_stay_out_of_daemon_infrastructure(self) -> None:
        infrastructure_files = [
            ROOT / "tools" / "launcher" / "daemon_core.py",
            ROOT / "tools" / "launcher" / "daemon_mailbox.py",
            ROOT / "tools" / "launcher" / "daemon_triggers.py",
            ROOT / "tools" / "launcher" / "central_daemon_core.py",
            ROOT / "scripts" / "env" / "tool_runtime" / "daemon_client.py",
        ]
        source = "\n".join(path.read_text(encoding="utf-8") for path in infrastructure_files)

        for forbidden in (
            "act-user-local",
            "web_user",
            "web-user",
            "send_web_message",
            "role_id.*user",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

        manifest = (ROOT / "buddyswitch" / "manifest.toml").read_text(encoding="utf-8")
        self.assertNotIn('id = "user"', manifest)

    def test_send_web_user_message_creates_normal_message_and_delivers_signal(self) -> None:
        calls = self._patch_daemon()
        target = {"role_id": "dev", "actor_id": "act-dev-target"}

        response = WEB_USER_ACTOR.send_web_user_message(
            target_actor_address=target,
            content="Please review this from the browser.",
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertIsInstance(response.get("message_id"), str)
        self.assertEqual(response.get("delivery_status"), "delivered")
        self.assertEqual(response.get("handling_status"), "handled")
        rows = self._message_rows()
        self.assertEqual(len(rows), 1)
        message = rows[0]
        self.assertEqual(message["from_actor_address"], WEB_USER_ACTOR.WEB_USER_ACTOR_ADDRESS)
        self.assertEqual(message["to_actor_address"], target)
        self.assertEqual(message["content"], "Please review this from the browser.")
        self.assertIsNone(message["reply_to"])
        self.assertEqual(message["disposition"], "unseen")
        self.assertEqual([call[0] for call in calls], ["reachability", "deliver"])
        signal = calls[1][1]["signal"]
        self.assertEqual(signal["type"], "message.available")
        self.assertEqual(signal["source_actor_address"], WEB_USER_ACTOR.WEB_USER_ACTOR_ADDRESS)
        self.assertEqual(signal["target_actor_address"], target)
        self.assertEqual(signal["payload"], {"message_id": response.get("message_id")})
        for forbidden in ("content", "message", "from_role", "to_role"):
            self.assertNotIn(forbidden, signal)

    def test_send_web_user_message_target_not_online_creates_no_message(self) -> None:
        calls = self._patch_daemon(reachability={"reachability_status": "registered_offline", "record": None})
        target = {"role_id": "dev", "actor_id": "act-dev-offline"}

        response = WEB_USER_ACTOR.send_web_user_message(target_actor_address=target, content="hello")

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("permission_boundary"), "message.reachability")
        self.assertEqual(response.get("reachability_status"), "registered_offline")
        self.assertEqual(self._message_rows(), [])
        self.assertEqual([call[0] for call in calls], ["reachability"])

    def test_send_web_user_message_delivery_failure_cleans_created_message(self) -> None:
        self._patch_daemon(delivery={"delivery_status": "delivery_failed", "signal_error": "socket gone"})
        target = {"role_id": "dev", "actor_id": "act-dev-delivery-fails"}

        response = WEB_USER_ACTOR.send_web_user_message(target_actor_address=target, content="hello")

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("delivery_status"), "delivery_failed")
        self.assertEqual(response.get("cleanup_status"), "cleaned")
        self.assertEqual(self._message_rows(), [])

    def test_web_user_sink_acknowledges_message_available(self) -> None:
        result = WEB_USER_ACTOR.web_user_sink_dispatcher(
            _Trigger(trigger_type="message.available", payload={"message_id": "msg-web-reply"})
        )

        self.assertEqual(
            result,
            {
                "accepted": True,
                "handled_count": 1,
                "matched_count": 1,
                "handling_status": "acknowledged",
            },
        )

    def test_web_user_sink_socket_is_mailbox_compatible_and_cleaned_up(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = Path(temp_root) / "web-user-mailbox.sock"
            server = WEB_USER_ACTOR.build_web_user_sink_server(socket_path=socket_path)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.close)
            deadline = time.monotonic() + 2
            while not socket_path.exists() and time.monotonic() < deadline:
                time.sleep(0.01)

            signal = daemon_mailbox.daemon_signal_envelope(
                signal_id="sig-web-user-reply",
                signal_type="message.available",
                source_actor_address={"role_id": "dev", "actor_id": "act-dev-reply"},
                target_actor_address=WEB_USER_ACTOR.WEB_USER_ACTOR_ADDRESS,
                payload={"message_id": "msg-web-user-reply"},
                created_at="2026-06-23T00:00:00Z",
            )
            envelope = daemon_client.request_mailbox(
                "mailbox.deliver",
                {"signal": signal},
                socket_path=socket_path,
            )
            server.close()
            thread.join(timeout=2)

            self.assertTrue(envelope.get("ok"), msg=envelope)
            result = envelope.get("result")
            self.assertIsInstance(result, dict, msg=envelope)
            assert isinstance(result, dict)
            self.assertEqual(result.get("handling_status"), "acknowledged")
            self.assertFalse(thread.is_alive())
            self.assertFalse(socket_path.exists())

    def test_web_user_runtime_registers_sink_and_cleans_up(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = Path(temp_root) / "web-user-runtime.sock"
            calls: list[tuple[str, dict[str, object]]] = []

            def fake_register(*, socket_path: Path) -> dict[str, object]:
                calls.append(("register", {"socket_path": socket_path}))
                return {"record": {"actor_address": WEB_USER_ACTOR.WEB_USER_ACTOR_ADDRESS, "status": "online"}}

            def fake_unregister() -> dict[str, object]:
                calls.append(("unregister", {}))
                return {
                    "record": {
                        "actor_address": WEB_USER_ACTOR.WEB_USER_ACTOR_ADDRESS,
                        "status": "registered_offline",
                    }
                }

            runtime = WEB_USER_ACTOR.WebUserActorRuntime(
                socket_path=socket_path,
                register_actor=fake_register,
                unregister_actor=fake_unregister,
            )
            self.addCleanup(runtime.close)

            runtime.start()
            self.assertTrue(socket_path.exists())

            runtime.close()

            self.assertEqual(
                calls,
                [
                    ("register", {"socket_path": socket_path}),
                    ("unregister", {}),
                ],
            )
            self.assertIsNone(runtime.thread)
            self.assertFalse(socket_path.exists())


if __name__ == "__main__":
    unittest.main()
