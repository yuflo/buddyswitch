"""Tests for Communication-owned actor delivery."""

from __future__ import annotations

import importlib
import tempfile
import unittest
from pathlib import Path
from typing import Any


from tests.support.paths import REPO_ROOT
from tests.support.runtime import RuntimeWorkspaceTestCase

ROOT = REPO_ROOT
IM_DELIVERY_PATH = (
    ROOT
    / "src"
    / "buddyswitch"
    / "modules"
    / "communication"
    / "private"
    / "adapters"
    / "actor"
    / "im_actor_delivery.py"
)


def _load_module() -> Any:
    if not IM_DELIVERY_PATH.exists():
        raise AssertionError(f"expected module to exist: {IM_DELIVERY_PATH}")
    return importlib.reload(
        importlib.import_module(
            "buddyswitch.modules.communication.private.adapters.actor.im_actor_delivery"
        )
    )


class ImActorDeliveryTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.module = None

    def _module(self) -> Any:
        module = _load_module()
        self.module = module
        return module

    def _profile(self, module: Any) -> None:
        module.identity_profiles.save_actor_identity_profile(
            {
                "identity": {"id": "act-market-delivery", "type": "actor"},
                "role_id": "market",
            }
        )

    def _payload(self) -> dict[str, object]:
        return {
            "type": "im.message.created",
            "wake_id": "imwake-delivery123",
            "target_identity_id": "act-market-delivery",
            "message_id": "msg-delivery123",
            "conversation_id": "conv-delivery123",
            "event_id": "imev-delivery123",
        }

    def test_module_exists(self) -> None:
        self.assertTrue(IM_DELIVERY_PATH.exists(), IM_DELIVERY_PATH)

    def test_online_actor_delivery_builds_current_local_trigger(self) -> None:
        module = self._module()
        self._profile(module)
        calls: list[dict[str, object]] = []

        def check_reachability(**kwargs: object) -> dict[str, object]:
            calls.append({"kind": "reachability", **kwargs})
            return {
                "reachability_status": "online",
                "record": {
                    "endpoint": {"kind": "daemon_mailbox_socket", "socket_path": "/tmp/im-delivery.sock"}
                },
            }

        def request_mailbox(method: str, params: dict[str, object], **kwargs: object) -> dict[str, object]:
            calls.append({"kind": "mailbox", "method": method, "params": params, **kwargs})
            return {"ok": True, "result": {"handling_status": "handled"}}

        result = module.deliver(
            self._payload(),
            check_reachability_fn=check_reachability,
            request_mailbox_fn=request_mailbox,
        )

        self.assertEqual(result["actor_handling_status"], "submitted")
        self.assertEqual(result["handling_status"], "handled")
        self.assertEqual(calls[0]["target_identity_id"], "act-market-delivery")
        mailbox = calls[1]
        self.assertEqual(mailbox["method"], "mailbox.local_trigger")
        self.assertEqual(mailbox["socket_path"], Path("/tmp/im-delivery.sock"))
        params = mailbox["params"]
        self.assertEqual(params["identity_id"], "act-market-delivery")
        self.assertEqual(params["role_id"], "market")
        self.assertEqual(params["type"], "im.message.created")
        self.assertEqual(
            params["payload"],
            {
                "message_id": "msg-delivery123",
                "conversation_id": "conv-delivery123",
                "event_id": "imev-delivery123",
            },
        )
        self.assertEqual(params["origin_id"], "msg-delivery123")
        self.assertEqual(params["correlation_id"], "imwake-delivery123")
        self.assertEqual(params["source_context"], {"source": "central_im"})

    def test_daemon_failed_or_ignored_handling_is_not_reported_as_submitted(self) -> None:
        module = self._module()
        self._profile(module)

        def online_reachability(**_kwargs: object) -> dict[str, object]:
            return {
                "reachability_status": "online",
                "record": {
                    "endpoint": {
                        "kind": "daemon_mailbox_socket",
                        "socket_path": "/tmp/im-delivery.sock",
                    }
                },
            }

        for status in ("failed", "ignored", None):
            with self.subTest(status=status):
                response: dict[str, Any] = {"ok": True, "result": {}}
                if status is not None:
                    response["result"]["handling_status"] = status
                result = module.deliver(
                    self._payload(),
                    check_reachability_fn=online_reachability,
                    request_mailbox_fn=lambda *_args, response=response, **_kwargs: response,
                )
                self.assertEqual(result["actor_handling_status"], "handling_failed")
                self.assertEqual(result["handling_status"], status)
                self.assertIn("did not handle", result["error"])

    def test_delivery_rejects_role_injection_and_missing_profile(self) -> None:
        module = self._module()
        injected = self._payload()
        injected["target_role_id"] = "dev"

        rejected = module.deliver(injected)
        missing = module.deliver(self._payload())

        self.assertEqual(rejected["actor_handling_status"], "handling_failed")
        self.assertIn("target_role_id", rejected["error"])
        self.assertEqual(missing["actor_handling_status"], "handling_failed")
        self.assertIn("actor identity profile not found", missing["error"])

    def test_offline_invalid_endpoint_and_mailbox_error_are_observable(self) -> None:
        module = self._module()
        self._profile(module)
        offline = module.deliver(
            self._payload(),
            check_reachability_fn=lambda **_kwargs: {"reachability_status": "offline"},
        )
        invalid_endpoint = module.deliver(
            self._payload(),
            check_reachability_fn=lambda **_kwargs: {
                "reachability_status": "online",
                "record": {"endpoint": {"kind": "other"}},
            },
        )
        mailbox_error = module.deliver(
            self._payload(),
            check_reachability_fn=lambda **_kwargs: {
                "reachability_status": "online",
                "record": {
                    "endpoint": {"kind": "daemon_mailbox_socket", "socket_path": "/tmp/im-delivery.sock"}
                },
            },
            request_mailbox_fn=lambda *_args, **_kwargs: {
                "ok": False,
                "error": {"message": "local trigger failed"},
            },
        )

        self.assertEqual(offline["actor_handling_status"], "target_not_online")
        self.assertEqual(invalid_endpoint["actor_handling_status"], "handling_failed")
        self.assertIn("daemon_mailbox_socket", invalid_endpoint["error"])
        self.assertEqual(mailbox_error["error"], "local trigger failed")
