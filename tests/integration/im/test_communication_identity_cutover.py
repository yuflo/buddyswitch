"""Communication identity cutover contract tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
LAUNCHER = ROOT / "src" / "buddyswitch" / "launcher"

from buddyswitch.foundation.identity.model import ActorIdentityProfile, IdentityRef  # noqa: E402
import buddyswitch.foundation.identity.profiles as identity_profiles  # noqa: E402
from buddyswitch.modules.communication.private.state import messages as message_repo  # noqa: E402
from buddyswitch.foundation.tool_runtime import context as runtime_context  # noqa: E402
from buddyswitch.foundation.daemon import client as daemon_client  # noqa: E402
from buddyswitch.modules.communication.private.adapters.actor import im_actor_delivery  # noqa: E402
from buddyswitch.modules.communication.private.adapters.actor import im_client as im_client_module  # noqa: E402
from buddyswitch.foundation.daemon import central_service  # noqa: E402
from tests.support.runtime import RuntimeWorkspaceTestCase  # noqa: E402


class _IdentityContext(dict[str, Any]):
    def __init__(self, *, identity_id: str, role_id: str, capabilities: Any) -> None:
        super().__init__(
            current_identity={"id": identity_id, "type": "actor"},
            active_role=role_id,
            manifest={"roles": [{"id": role_id}]},
        )
        self.actor_directory = capabilities


class _NoActorsCapabilities:
    def list_online_actors(self, *, role_id: str | None = None) -> dict[str, Any]:
        del role_id
        return {"actors": [], "count": 0}

    def check_reachability(self, *, target_identity_id: str) -> dict[str, Any]:
        return {"reachability_status": "offline", "target_identity_id": target_identity_id}

    def deliver(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError(f"unexpected IM actor delivery: {payload!r}")


class CommunicationIdentityCutoverTests(RuntimeWorkspaceTestCase):
    def test_daemon_registry_uses_identity_ids(self) -> None:
        paths = central_service.central_daemon_paths(self.runtime_root)
        service = central_service.CentralDaemonService(paths=paths, now=lambda: "2026-07-04T00:00:00Z")

        registered = service.handle(
            "daemon.register",
            {
                "identity_id": "act-dev-daemon-identity",
                "role_id": "dev",
                "endpoint": {"kind": "test"},
                "heartbeat": {"kind": "test"},
            },
        )

        self.assertEqual(registered["record"]["identity_id"], "act-dev-daemon-identity")
        self.assertEqual(registered["record"]["identity"], {"id": "act-dev-daemon-identity", "type": "actor"})
        self.assertNotIn("actor" + "_address", registered["record"])

    def test_im_message_rows_store_sender_and_target_identity_refs(self) -> None:
        saved = message_repo.save_im_message(
            {
                "id": "msg-identity-row",
                "conversation_id": "conv-identity-row",
                "sender_identity": {"id": "act-pm-im-row", "type": "actor"},
                "target_identity": {"id": "act-dev-im-row", "type": "actor"},
                "content": "identity row",
                "reply_to": None,
                "created_at": "2026-07-04T00:00:00Z",
                "sequence": 1,
            }
        )

        self.assertEqual(saved["sender_identity"], {"id": "act-pm-im-row", "type": "actor"})
        self.assertEqual(saved["target_identity"], {"id": "act-dev-im-row", "type": "actor"})
        self.assertNotIn("from_identity_id", saved)
        self.assertNotIn("to_identity_id", saved)

    def test_runtime_signal_delivery_access_uses_identity_routing(self) -> None:
        captured: dict[str, Any] = {}

        original = daemon_client.deliver_signal
        daemon_client.deliver_signal = lambda *, signal: captured.setdefault("signal", signal) or {"delivery_status": "delivered"}
        try:
            context = runtime_context.ToolContext.from_identity_profile(
                actor_identity_profile=ActorIdentityProfile(
                    identity=IdentityRef(id="act-dev-signal-source", type="actor"),
                    role_id="dev",
                ),
                instance_json=self.runtime_root / "instances" / "act-dev-signal-source" / "instance.json",
                instance_payload={
                    "actor_id": "act-dev-signal-source",
                    "role": "dev",
                    "workspace_dir": str(self.runtime_root / "workspace"),
                },
                manifest={},
            )
            context.signal_delivery.deliver_signal(
                signal_type="track.comment.added",
                target_identity_id="act-pm-signal-target",
                target_role_id="pm",
                payload={"track_id": "track-signal"},
            )
        finally:
            daemon_client.deliver_signal = original

        signal = captured["signal"]
        self.assertEqual(signal["source_identity_id"], "act-dev-signal-source")
        self.assertEqual(signal["source_role_id"], "dev")
        self.assertEqual(signal["target_identity_id"], "act-pm-signal-target")
        self.assertEqual(signal["target_role_id"], "pm")
        self.assertNotIn("source_" + "actor" + "_address", signal)
        self.assertNotIn("target_" + "actor" + "_address", signal)

    def test_im_delivery_payload_uses_target_identity_route(self) -> None:
        calls: dict[str, Any] = {}
        identity_profiles.save_actor_identity_profile(
            {
                "identity": {"id": "act-dev-im-wake", "type": "actor"},
                "role_id": "dev",
                "label": "Dev IM wake",
            }
        )

        def fake_check_reachability(*, target_identity_id: str, socket_path: Path | None = None) -> dict[str, Any]:
            calls["target_identity_id"] = target_identity_id
            self.assertIsNone(socket_path)
            return {
                "reachability_status": "online",
                "record": {
                    "identity_id": target_identity_id,
                    "role_id": "wrong",
                    "endpoint": {"kind": "daemon_mailbox_socket", "socket_path": "/tmp/identity-mailbox.sock"},
                },
            }

        def fake_request_mailbox(method: str, params: dict[str, Any], *, socket_path: Path) -> dict[str, Any]:
            calls["mailbox"] = {"method": method, "params": params, "socket_path": socket_path}
            return {"ok": True, "result": {"handling_status": "handled"}}

        result = im_actor_delivery.deliver(
            {
                "type": "im.message.created",
                "target_identity_id": "act-dev-im-wake",
                "message_id": "msg-im-wake",
                "conversation_id": "conv-im-wake",
                "event_id": "event-im-wake",
            },
            check_reachability_fn=fake_check_reachability,
            request_mailbox_fn=fake_request_mailbox,
        )

        self.assertEqual(result["actor_handling_status"], "submitted")
        self.assertEqual(calls["target_identity_id"], "act-dev-im-wake")
        self.assertEqual(calls["mailbox"]["method"], "mailbox.local_trigger")
        self.assertEqual(calls["mailbox"]["params"]["identity_id"], "act-dev-im-wake")
        self.assertEqual(calls["mailbox"]["params"]["role_id"], "dev")
        self.assertNotEqual(calls["mailbox"]["params"]["role_id"], "wrong")
        self.assertNotIn("actor" + "_address", calls["mailbox"]["params"])

    def test_actor_active_send_to_unknown_external_identity_rejects_as_target_error(self) -> None:
        client = im_client_module.ActorImClient(
            _IdentityContext(
                identity_id="act-dev-im-active-external",
                role_id="dev",
                capabilities=_NoActorsCapabilities(),
            )
        )

        response = client.send(
            {
                "target_identity_id": "ext-user-active-send",
                "content": "hello external",
            }
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_IM_TARGET")
        message = (response.get("error") or {}).get("message", "")
        self.assertIn("external identity profile not found", message)
        self.assertNotIn("reply_to", message)
