"""Tests for the application's concrete App/Actor daemon host."""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from buddyswitch.application import daemon_host
from buddyswitch.foundation.daemon import contracts


def _context() -> contracts.DaemonContext:
    instance_root = Path("/tmp/instances/act-dev-daed00000001")
    workspace_dir = instance_root / "workspace"
    return contracts.DaemonContext(
        instance_json=instance_root / "instance.json",
        instance_payload={},
        actor_id="act-dev-daed00000001",
        instance_root=instance_root,
        main_thread_id="thr-main",
        role="dev",
        workspace_dir=workspace_dir,
        project_workspace_dir=workspace_dir / "projects" / "app",
        socket_path=instance_root / "runtime" / "app-server.sock",
        permissions="buddyswitch-runtime",
    )


class FakeAppServerClient:
    def __init__(
        self,
        socket_path: Path,
        *,
        timeout_seconds: float,
        client_name: str,
        client_title: str,
    ) -> None:
        self.constructor = {
            "socket_path": socket_path,
            "timeout_seconds": timeout_seconds,
            "client_name": client_name,
            "client_title": client_title,
        }
        self.requests: list[tuple[str, dict[str, Any]]] = []
        self.notification: dict[str, Any] | BaseException = {
            "method": "turn/completed"
        }
        self.resume_result: dict[str, Any] = {"thread": {"id": "thr-main"}}

    def __enter__(self) -> "FakeAppServerClient":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.requests.append((method, params))
        return self.resume_result

    def read_notification(self) -> dict[str, Any]:
        if isinstance(self.notification, BaseException):
            raise self.notification
        return self.notification


class ApplicationDaemonHostTests(unittest.TestCase):
    def test_notification_client_binds_exact_actor_context(self) -> None:
        context = _context()
        with patch.object(
            daemon_host.app_server,
            "AppServerClient",
            FakeAppServerClient,
        ):
            client = daemon_host.AppNotificationClient(context)
            client.bind(context)

        raw = client._client
        self.assertEqual(
            raw.constructor,
            {
                "socket_path": context.socket_path,
                "timeout_seconds": daemon_host.app_server.DEFAULT_RPC_TIMEOUT_SECONDS,
                "client_name": "buddyswitch_daemon",
                "client_title": "BuddySwitch Daemon",
            },
        )
        self.assertEqual(
            raw.requests,
            [
                (
                    "thread/resume",
                    {
                        "threadId": "thr-main",
                        "cwd": str(context.workspace_dir),
                        "runtimeWorkspaceRoots": [
                            str(context.workspace_dir),
                            str(context.project_workspace_dir),
                        ],
                        "permissions": "buddyswitch-runtime",
                        "excludeTurns": True,
                    },
                )
            ],
        )

    def test_notification_client_translates_protocol_and_poll_failures(self) -> None:
        context = _context()
        with patch.object(
            daemon_host.app_server,
            "AppServerClient",
            FakeAppServerClient,
        ):
            client = daemon_host.AppNotificationClient(context)
        raw = client._client
        raw.resume_result = {"thread": {"id": "thr-other"}}
        with self.assertRaisesRegex(contracts.DaemonHostError, "unexpected thread id"):
            client.bind(context)

        raw.notification = daemon_host.app_server.AppServerTimeoutError("idle")
        with self.assertRaisesRegex(contracts.DaemonHostTimeout, "idle"):
            client.read_notification()
        raw.notification = daemon_host.app_server.AppServerUnavailableError("closed")
        with self.assertRaisesRegex(contracts.DaemonHostError, "closed"):
            client.read_notification()

    def test_parent_activity_and_input_are_supplied_by_application_host(self) -> None:
        context = _context()
        host = daemon_host.AppActorDaemonHost()
        with (
            patch.object(
                daemon_host.app_server,
                "thread_read",
                return_value={"thread": {"status": {"type": "active"}}},
            ) as thread_read,
            patch.object(
                daemon_host.app_server,
                "active_turn_id",
                return_value="turn-active",
            ),
            patch.object(
                daemon_host.actor_session,
                "input_actor_turn",
                return_value={"turn": {"id": "turn-new"}},
            ) as input_actor,
        ):
            self.assertEqual(
                host.parent_activity(context),
                {"status": "running", "active_turn_id": "turn-active"},
            )
            self.assertEqual(
                host.input_actor(context, "continue"),
                {"turn": {"id": "turn-new"}},
            )

        thread_read.assert_called_once_with(
            context.socket_path,
            context.main_thread_id,
            include_turns=False,
        )
        input_actor.assert_called_once_with(
            socket_path=context.socket_path,
            instance_json=context.instance_json,
            thread_id=context.main_thread_id,
            text="continue",
            permissions=context.permissions,
        )


if __name__ == "__main__":
    unittest.main()
