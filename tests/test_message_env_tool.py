#!/usr/bin/env python3
"""Message env.tool integration tests."""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import sys
import unittest
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_legacy_store as env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from runtime_kernel import dispatcher  # noqa: E402
from env.repos import messages as message_repo  # noqa: E402
from env.tool_runtime import context as runtime_context  # noqa: E402
from env.tool_runtime.actor_profile import ActorAddress  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class MessageEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    _OBJECT_DIRS = ("tracks", "tasks", "artifacts", "comments", "messages")

    def _normalized_actor_id(self, *, role: str, label: str) -> str:
        try:
            return ActorAddress(role_id=role, actor_id=label).actor_id
        except ValueError:
            suffix = uuid.uuid5(uuid.NAMESPACE_DNS, f"{role}:{label}").hex[:12]
            return f"act-{role}-{suffix}"

    def _actor_address(self, *, role: str, label: str) -> dict[str, str]:
        return ActorAddress(
            role_id=role,
            actor_id=self._normalized_actor_id(role=role, label=label),
        ).to_payload()

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

    def _message_rows(self) -> list[dict[str, object]]:
        root = self._runtime_path("buddyswitch/objects/messages")
        rows: list[dict[str, object]] = []
        if root.is_dir():
            for path in sorted(root.glob("*.json")):
                rows.append(json.loads(path.read_text(encoding="utf-8")))
        return rows

    def _assert_non_message_dirs_unchanged(
        self,
        before: dict[str, dict[str, object]],
        after: dict[str, dict[str, object]],
    ) -> None:
        for object_dir in ("tracks", "tasks", "artifacts", "comments"):
            self.assertEqual(before[object_dir], after[object_dir], msg=object_dir)

    def _instance_json(self, *, actor_id: str, role: str, status: str = "active") -> Path:
        normalized_actor_id = self._normalized_actor_id(role=role, label=actor_id)
        path = self._runtime_path("instance.json")
        path.write_text(
            json.dumps(
                {
                    "actor_id": normalized_actor_id,
                    "role": role,
                    "status": status,
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "updated_at": "2026-05-15T00:00:00Z",
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
        actor_id: str,
        role: str,
        tool: str,
        action: str,
        args: dict[str, object],
    ) -> dict[str, object]:
        normalized_actor_id = self._normalized_actor_id(role=role, label=actor_id)
        request = {
            "protocol": PROTOCOL,
            "request_id": f"req-msg-{uuid.uuid4().hex}",
            "method": "env.tool",
            "params": {
                "actor_id": normalized_actor_id,
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

    def _load_projected_context_module(self, workspace_root: Path):
        projected_context = workspace_root / "scripts" / "env" / "tool_runtime" / "context.py"
        projected_context.parent.mkdir(parents=True, exist_ok=True)
        projected_context.write_text(
            (ROOT / "scripts" / "env" / "tool_runtime" / "context.py").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        module_name = f"projected_context_{uuid.uuid4().hex}"
        spec = importlib.util.spec_from_file_location(module_name, projected_context)
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertIsNotNone(spec.loader)
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        self.addCleanup(sys.modules.pop, module_name, None)
        spec.loader.exec_module(module)
        return module

    def _patch_daemon(
        self,
        *,
        contacts: dict[str, object] | None = None,
        reachability: dict[str, object] | None = None,
        delivery: dict[str, object] | None = None,
    ) -> list[tuple[str, dict[str, object]]]:
        calls: list[tuple[str, dict[str, object]]] = []
        original_list_contacts = runtime_context.daemon_client.list_contacts
        original_check_reachability = runtime_context.daemon_client.check_reachability
        original_deliver_signal = runtime_context.daemon_client.deliver_signal

        def fake_list_contacts(*, role_id: str | None = None) -> dict[str, object]:
            calls.append(("contacts", {"role_id": role_id}))
            if contacts is not None:
                return contacts
            return {"contacts": [], "count": 0}

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
                return delivery
            return {
                "delivery_status": "delivered",
                "handling_status": "handled",
                "signal": signal,
            }

        def restore() -> None:
            runtime_context.daemon_client.list_contacts = original_list_contacts
            runtime_context.daemon_client.check_reachability = original_check_reachability
            runtime_context.daemon_client.deliver_signal = original_deliver_signal

        runtime_context.daemon_client.list_contacts = fake_list_contacts
        runtime_context.daemon_client.check_reachability = fake_check_reachability
        runtime_context.daemon_client.deliver_signal = fake_deliver_signal
        self.addCleanup(restore)
        return calls

    def _patch_parent_message_handling(self) -> list[dict[str, object]]:
        calls: list[dict[str, object]] = []
        original = getattr(runtime_context.DaemonAccess, "request_parent_message_handling", None)

        def fake_request_parent_message_handling(
            daemon_access: object,
            *,
            message_id: str,
            prompt: str,
        ) -> dict[str, object]:
            calls.append({"message_id": message_id, "prompt": prompt})
            return {"turn_id": "turn-parent-required", "interrupted_turn_id": "turn-main-1"}

        def restore() -> None:
            if original is None:
                delattr(runtime_context.DaemonAccess, "request_parent_message_handling")
            else:
                runtime_context.DaemonAccess.request_parent_message_handling = original

        runtime_context.DaemonAccess.request_parent_message_handling = fake_request_parent_message_handling
        self.addCleanup(restore)
        return calls

    def _patch_parent_message_handling_with_failures(
        self,
        *,
        failures: int,
        operations: list[str] | None = None,
    ) -> list[dict[str, object]]:
        calls: list[dict[str, object]] = []
        original = getattr(runtime_context.DaemonAccess, "request_parent_message_handling", None)

        def fake_request_parent_message_handling(
            daemon_access: object,
            *,
            message_id: str,
            prompt: str,
        ) -> dict[str, object]:
            del daemon_access
            calls.append({"message_id": message_id, "prompt": prompt})
            if operations is not None:
                operations.append("parent_prompt")
            if len(calls) <= failures:
                raise RuntimeError(f"parent prompt unavailable on attempt {len(calls)}")
            return {"turn_id": "turn-parent-required", "interrupted_turn_id": "turn-main-1"}

        def restore() -> None:
            if original is None:
                delattr(runtime_context.DaemonAccess, "request_parent_message_handling")
            else:
                runtime_context.DaemonAccess.request_parent_message_handling = original

        runtime_context.DaemonAccess.request_parent_message_handling = fake_request_parent_message_handling
        self.addCleanup(restore)
        return calls

    def _patch_message_save_failures(
        self,
        *,
        should_fail: object,
        failures: int,
        operations: list[str] | None = None,
        operation_label: str = "save",
    ) -> list[dict[str, object]]:
        attempts: list[dict[str, object]] = []
        original = message_repo.save_message

        def fake_save_message(message: dict[str, object]) -> dict[str, object]:
            if callable(should_fail) and should_fail(message):
                attempts.append(dict(message))
                if operations is not None:
                    operations.append(operation_label)
                if len(attempts) <= failures:
                    raise OSError(f"injected message save failure {len(attempts)}")
            return original(message)

        def restore() -> None:
            message_repo.save_message = original

        message_repo.save_message = fake_save_message
        self.addCleanup(restore)
        return attempts

    def _patch_message_retry_sleep(self) -> list[float]:
        from env.tools.message import _impl as message_impl

        calls: list[float] = []
        original = getattr(message_impl, "_sleep_for_message_mutation_retry", None)
        if original is None:
            return calls

        def fake_sleep(seconds: float) -> None:
            calls.append(seconds)

        message_impl._sleep_for_message_mutation_retry = fake_sleep
        self.addCleanup(setattr, message_impl, "_sleep_for_message_mutation_retry", original)
        return calls

    def test_message_contacts_lists_online_actor_contacts(self) -> None:
        dev_address = self._actor_address(role="dev", label="act-dev-contact")
        calls = self._patch_daemon(
            contacts={
                "contacts": [
                    {
                        "actor_address": dev_address,
                        "status": "online",
                        "last_seen_at": "2026-05-30T00:00:00Z",
                    }
                ],
                "count": 1,
            }
        )
        instance_json = self._instance_json(actor_id="act-pm-contacts", role="pm")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-contacts",
            role="pm",
            tool="message",
            action="contacts",
            args={"role": "dev"},
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(calls, [("contacts", {"role_id": "dev"})])
        self.assertEqual(response.get("count"), 1)
        contact = response.get("contacts", [])[0]
        self.assertEqual(contact["role_id"], "dev")
        self.assertEqual(contact["actor_address"], dev_address)
        self.assertEqual(contact["contact_status"], "online")
        self.assertIs(contact["sendable"], True)
        self.assertEqual(contact["last_seen_at"], "2026-05-30T00:00:00Z")

    def test_message_contacts_marks_only_active_actor_row_not_sendable(self) -> None:
        active_pm = self._actor_address(role="pm", label="act-pm-contacts-self")
        other_pm = self._actor_address(role="pm", label="act-pm-other")
        market = self._actor_address(role="market", label="act-market-contacts")
        market_same_actor_id = {"role_id": "market", "actor_id": active_pm["actor_id"]}
        self._patch_daemon(
            contacts={
                "contacts": [
                    {"actor_address": active_pm, "status": "online"},
                    {"actor_address": other_pm, "status": "online"},
                    {"actor_address": market, "status": "online"},
                    {"actor_address": market_same_actor_id, "status": "online"},
                ],
                "count": 4,
            }
        )
        instance_json = self._instance_json(actor_id="act-pm-contacts-self", role="pm")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-contacts-self",
            role="pm",
            tool="message",
            action="contacts",
            args={},
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("count"), 4)
        self.assertEqual(response.get("sendable_count"), 3)
        contacts = response.get("contacts")
        self.assertIsInstance(contacts, list, msg=response)
        assert isinstance(contacts, list)
        by_address = {
            (row["actor_address"]["role_id"], row["actor_address"]["actor_id"]): row
            for row in contacts
            if isinstance(row, dict) and isinstance(row.get("actor_address"), dict)
        }
        active_row = by_address[(active_pm["role_id"], active_pm["actor_id"])]
        self.assertEqual(active_row["role_id"], "pm")
        self.assertIs(active_row["sendable"], False)
        why_not_sendable = active_row.get("why_not_sendable", "")
        self.assertIn("active full ActorAddress itself", why_not_sendable)
        self.assertNotIn("same role", why_not_sendable.lower())
        other_pm_row = by_address[(other_pm["role_id"], other_pm["actor_id"])]
        self.assertEqual(other_pm_row["role_id"], "pm")
        self.assertIs(other_pm_row["sendable"], True)
        self.assertIs(by_address[(market["role_id"], market["actor_id"])]["sendable"], True)
        same_actor_id_row = by_address[(market_same_actor_id["role_id"], market_same_actor_id["actor_id"])]
        self.assertIs(same_actor_id_row["sendable"], True)
        self.assertIn("target_actor_address", " ".join(response.get("allowed_next_actions", [])))

    def test_message_contacts_rejects_unknown_role_filter(self) -> None:
        calls = self._patch_daemon()
        instance_json = self._instance_json(actor_id="act-pm-contacts-unknown", role="pm")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-contacts-unknown",
            role="pm",
            tool="message",
            action="contacts",
            args={"role": "ops"},
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_PAYLOAD")
        self.assertEqual(response.get("correctable_fields"), ["role"])
        self.assertEqual(calls, [])

    def test_message_send_rejects_to_role_field(self) -> None:
        calls = self._patch_daemon()
        instance_json = self._instance_json(actor_id="act-design-old-send", role="design")
        before_state = self._objects_state()

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-design-old-send",
            role="design",
            tool="message",
            action="send",
            args={"to_role": "dev", "content": "Please inspect the prototype."},
        )

        after_state = self._objects_state()
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_PAYLOAD")
        self.assertEqual(response.get("correctable_fields"), ["to_role"])
        self.assertEqual(before_state, after_state)
        self.assertEqual(calls, [])

    def test_message_send_rejects_invalid_target_actor_address_without_state_change(self) -> None:
        calls = self._patch_daemon()
        instance_json = self._instance_json(actor_id="act-design-invalid-target", role="design")
        before_state = self._objects_state()

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-design-invalid-target",
            role="design",
            tool="message",
            action="send",
            args={
                "target_actor_address": {"role_id": "Dev", "actor_id": "act-Dev-daemon"},
                "content": "hello",
            },
        )

        after_state = self._objects_state()
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("correctable_fields"), ["target_actor_address"])
        self.assertEqual(before_state, after_state)
        self.assertEqual(calls, [])

    def test_message_send_rejects_same_actor_target_without_state_change(self) -> None:
        calls = self._patch_daemon()
        instance_json = self._instance_json(actor_id="act-dev-self", role="dev")
        target = self._actor_address(role="dev", label="act-dev-self")
        before_state = self._objects_state()

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-self",
            role="dev",
            tool="message",
            action="send",
            args={"target_actor_address": target, "content": "self"},
        )

        after_state = self._objects_state()
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("permission_boundary"), "message.self_send")
        self.assertEqual(response.get("correctable_fields"), ["target_actor_address"])
        self.assertEqual(before_state, after_state)
        self.assertEqual(calls, [])

    def test_message_send_allows_same_role_different_actor(self) -> None:
        calls = self._patch_daemon()
        instance_json = self._instance_json(actor_id="act-pm-source", role="pm")
        source = self._actor_address(role="pm", label="act-pm-source")
        target = self._actor_address(role="pm", label="act-pm-target")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-source",
            role="pm",
            tool="message",
            action="send",
            args={"target_actor_address": target, "content": "same role works"},
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("delivery_status"), "delivered")
        rows = self._message_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["from_actor_address"], source)
        self.assertEqual(rows[0]["to_actor_address"], target)
        self.assertEqual([call[0] for call in calls], ["reachability", "deliver"])

    def test_message_send_target_not_online_creates_no_message(self) -> None:
        calls = self._patch_daemon(reachability={"reachability_status": "registered_offline", "record": None})
        instance_json = self._instance_json(actor_id="act-pm-offline", role="pm")
        target = self._actor_address(role="dev", label="act-dev-offline")
        before_state = self._objects_state()

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-offline",
            role="pm",
            tool="message",
            action="send",
            args={"target_actor_address": target, "content": "hello"},
        )

        after_state = self._objects_state()
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("permission_boundary"), "message.reachability")
        self.assertEqual(response.get("reachability_status"), "registered_offline")
        self.assertEqual(response.get("durability"), "none")
        self.assertIs(response.get("state_changed"), False)
        self.assertEqual(before_state, after_state)
        self.assertEqual([call[0] for call in calls], ["reachability"])

    def test_message_send_never_registered_guides_contacts_refresh(self) -> None:
        self._patch_daemon(reachability={"reachability_status": "never_registered", "record": None})
        instance_json = self._instance_json(actor_id="act-pm-never-registered", role="pm")
        target = self._actor_address(role="dev", label="act-dev-never")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-never-registered",
            role="pm",
            tool="message",
            action="send",
            args={"target_actor_address": target, "content": "hello"},
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("reachability_status"), "never_registered")
        self.assertIn("message.contacts", " ".join(response.get("allowed_next_actions", [])))

    def test_message_send_online_target_creates_actor_address_message_and_delivers_signal(self) -> None:
        calls = self._patch_daemon()
        instance_json = self._instance_json(actor_id="act-design-success", role="design")
        source = self._actor_address(role="design", label="act-design-success")
        target = self._actor_address(role="dev", label="act-dev-success")
        before_state = self._objects_state()

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-design-success",
            role="design",
            tool="message",
            action="send",
            args={"target_actor_address": target, "content": "Please inspect the prototype."},
        )

        after_state = self._objects_state()
        self.assertTrue(response.get("ok"), msg=response)
        self._assert_non_message_dirs_unchanged(before_state, after_state)
        self.assertEqual(response.get("delivery_status"), "delivered")
        self.assertEqual(response.get("created_ids"), [response.get("message_id")])
        rows = self._message_rows()
        self.assertEqual(len(rows), 1)
        msg = rows[0]
        self.assertEqual(msg["from_actor_address"], source)
        self.assertEqual(msg["to_actor_address"], target)
        self.assertEqual(msg["content"], "Please inspect the prototype.")
        self.assertEqual(msg["disposition"], "unseen")
        self.assertIsNone(msg["disposition_reason"])
        self.assertIsNone(msg["disposition_updated_at"])
        self.assertIsNone(msg["processed_by_actor_address"])
        self.assertNotIn("from_role", msg)
        self.assertNotIn("to_role", msg)

        self.assertEqual([call[0] for call in calls], ["reachability", "deliver"])
        signal = calls[1][1]["signal"]
        self.assertEqual(signal["type"], "message.available")
        self.assertEqual(signal["source_actor_address"], source)
        self.assertEqual(signal["target_actor_address"], target)
        self.assertEqual(signal["payload"], {"message_id": response.get("message_id")})
        self.assertNotIn("content", signal)
        self.assertNotIn("message", signal)
        self.assertNotIn("from_role", signal)
        self.assertNotIn("to_role", signal)

    def test_message_send_delivery_failed_cleanup_succeeded_removes_message(self) -> None:
        self._patch_daemon(delivery={"delivery_status": "delivery_failed", "signal_error": "socket gone"})
        instance_json = self._instance_json(actor_id="act-pm-cleanup", role="pm")
        target = self._actor_address(role="dev", label="act-dev-cleanup")
        before_state = self._objects_state()

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-cleanup",
            role="pm",
            tool="message",
            action="send",
            args={"target_actor_address": target, "content": "hello"},
        )

        after_state = self._objects_state()
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("delivery_status"), "delivery_failed")
        self.assertEqual(response.get("cleanup_status"), "cleaned")
        self.assertIs(response.get("state_changed"), False)
        self.assertEqual(response.get("durability"), "none")
        self.assertIs(response.get("retryable"), True)
        self.assertEqual(before_state, after_state)

    def test_message_send_delivery_failed_cleanup_failed_reports_indeterminate(self) -> None:
        self._patch_daemon(delivery={"delivery_status": "delivery_failed", "signal_error": "socket gone"})
        original_delete = getattr(message_repo, "delete_message", None)

        def fail_delete(_message_id: str) -> None:
            raise OSError("unlink failed")

        def restore_delete() -> None:
            if original_delete is None:
                delattr(message_repo, "delete_message")
            else:
                message_repo.delete_message = original_delete

        message_repo.delete_message = fail_delete
        self.addCleanup(restore_delete)
        instance_json = self._instance_json(actor_id="act-pm-indeterminate", role="pm")
        target = self._actor_address(role="dev", label="act-dev-indeterminate")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-indeterminate",
            role="pm",
            tool="message",
            action="send",
            args={"target_actor_address": target, "content": "hello"},
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_SEND_INDETERMINATE")
        self.assertEqual(response.get("delivery_status"), "delivery_failed")
        self.assertEqual(response.get("cleanup_status"), "failed")
        self.assertIs(response.get("state_changed"), True)
        self.assertEqual(response.get("durability"), "uncertain")
        self.assertIs(response.get("retryable"), False)
        self.assertIsInstance(response.get("message_id"), str)
        self.assertIn("Do not blindly retry", response.get("retry_guidance", ""))

    def test_message_list_returns_only_messages_to_current_actor_address(self) -> None:
        active = self._actor_address(role="dev", label="act-dev-list")
        other_dev = self._actor_address(role="dev", label="act-dev-other-list")
        pm = self._actor_address(role="pm", label="act-pm-list")
        design = self._actor_address(role="design", label="act-design-list")
        env_store.create_message(from_actor_address=pm, to_actor_address=active, content="PM to active Dev")
        env_store.create_message(from_actor_address=design, to_actor_address=active, content="Design to active Dev")
        env_store.create_message(from_actor_address=pm, to_actor_address=other_dev, content="PM to other Dev")
        env_store.create_message(from_actor_address=active, to_actor_address=pm, content="Dev sent")

        instance_json = self._instance_json(actor_id="act-dev-list", role="dev")
        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-list",
            role="dev",
            tool="message",
            action="list",
            args={},
        )

        self.assertTrue(response.get("ok"), msg=response)
        messages = response.get("messages", [])
        self.assertEqual(len(messages), 2, msg=response)
        self.assertEqual({row["to_actor_address"]["actor_id"] for row in messages}, {active["actor_id"]})
        self.assertNotIn("from_role", json.dumps(messages, ensure_ascii=True))
        self.assertNotIn("to_role", json.dumps(messages, ensure_ascii=True))

    def test_message_list_filters_by_sender_role_from_actor_address(self) -> None:
        active = self._actor_address(role="dev", label="act-dev-filter")
        pm = self._actor_address(role="pm", label="act-pm-filter")
        design = self._actor_address(role="design", label="act-design-filter")
        env_store.create_message(from_actor_address=pm, to_actor_address=active, content="PM to Dev")
        env_store.create_message(from_actor_address=design, to_actor_address=active, content="Design to Dev")

        instance_json = self._instance_json(actor_id="act-dev-filter", role="dev")
        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-filter",
            role="dev",
            tool="message",
            action="list",
            args={"role": "design"},
        )

        self.assertTrue(response.get("ok"), msg=response)
        messages = response.get("messages", [])
        self.assertEqual(len(messages), 1, msg=response)
        self.assertEqual(messages[0]["from_actor_address"], design)

    def test_message_get_returns_exact_processable_inbound_message(self) -> None:
        active = self._actor_address(role="dev", label="act-dev-get")
        pm = self._actor_address(role="pm", label="act-pm-get")
        seed = message_repo.save_message(
            {
                "id": "msg-get-processable",
                "from_actor_address": pm,
                "to_actor_address": active,
                "content": "Please review this exact message.",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:01Z",
            }
        )
        instance_json = self._instance_json(actor_id="act-dev-get", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-get",
            role="dev",
            tool="message",
            action="get",
            args={"message_id": seed["id"]},
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("message_id"), seed["id"])
        self.assertEqual(response.get("disposition"), "unseen")
        message = response.get("message")
        self.assertIsInstance(message, dict, msg=response)
        assert isinstance(message, dict)
        self.assertEqual(message["content"], "Please review this exact message.")
        self.assertEqual(message["from_actor_address"], pm)
        self.assertEqual(message["to_actor_address"], active)
        self.assertEqual(message["reply_to"], None)
        self.assertEqual(message["disposition"], "unseen")
        self.assertIsNone(message["disposition_reason"])
        self.assertIsNone(message["disposition_updated_at"])
        self.assertIsNone(message["processed_by_actor_address"])

    def test_message_get_rejects_unknown_invisible_and_completed_messages(self) -> None:
        active = self._actor_address(role="dev", label="act-dev-get-reject")
        other_dev = self._actor_address(role="dev", label="act-dev-get-reject-other")
        pm = self._actor_address(role="pm", label="act-pm-get-reject")
        message_repo.save_message(
            {
                "id": "msg-get-invisible",
                "from_actor_address": pm,
                "to_actor_address": other_dev,
                "content": "not for active dev",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:01Z",
            }
        )
        for message_id, disposition in (("msg-get-absorbed", "absorbed"), ("msg-get-replied", "replied")):
            message_repo.save_message(
                {
                    "id": message_id,
                    "from_actor_address": pm,
                    "to_actor_address": active,
                    "content": f"completed {disposition}",
                    "reply_to": None,
                    "created_at": "2026-05-30T00:00:02Z",
                    "disposition": disposition,
                    "disposition_reason": None,
                    "disposition_updated_at": "2026-05-30T00:00:03Z",
                    "processed_by_actor_address": active,
                }
            )
        instance_json = self._instance_json(actor_id="act-dev-get-reject", role="dev")

        for message_id in ("msg-get-missing", "msg-get-invisible", "msg-get-absorbed", "msg-get-replied"):
            with self.subTest(message_id=message_id):
                response = self._dispatch(
                    instance_json=instance_json,
                    actor_id="act-dev-get-reject",
                    role="dev",
                    tool="message",
                    action="get",
                    args={"message_id": message_id},
                )

                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual(response.get("state_changed"), False)

    def test_message_mark_absorbed_transitions_unseen_and_needs_parent(self) -> None:
        active = self._actor_address(role="dev", label="act-dev-mark-absorb")
        pm = self._actor_address(role="pm", label="act-pm-mark-absorb")
        unseen = message_repo.save_message(
            {
                "id": "msg-mark-absorbed-unseen",
                "from_actor_address": pm,
                "to_actor_address": active,
                "content": "FYI only",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:01Z",
            }
        )
        needs_parent = message_repo.save_message(
            {
                "id": "msg-mark-absorbed-parent",
                "from_actor_address": pm,
                "to_actor_address": active,
                "content": "Parent reviewed now",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:02Z",
                "disposition": "needs_parent",
                "disposition_reason": "Requires parent context.",
                "disposition_updated_at": "2026-05-30T00:00:03Z",
                "processed_by_actor_address": active,
            }
        )
        instance_json = self._instance_json(actor_id="act-dev-mark-absorb", role="dev")

        for seed in (unseen, needs_parent):
            with self.subTest(message_id=seed["id"]):
                response = self._dispatch(
                    instance_json=instance_json,
                    actor_id="act-dev-mark-absorb",
                    role="dev",
                    tool="message",
                    action="mark",
                    args={"message_id": seed["id"], "disposition": "absorbed"},
                )

                self.assertTrue(response.get("ok"), msg=response)
                stored = message_repo.get_message(seed["id"])
                self.assertIsNotNone(stored)
                assert stored is not None
                self.assertEqual(stored["disposition"], "absorbed")
                self.assertIsNone(stored["disposition_reason"])
                self.assertIsInstance(stored["disposition_updated_at"], str)
                self.assertEqual(stored["processed_by_actor_address"], active)

    def test_message_mark_needs_parent_stores_reason_and_requests_parent_prompt(self) -> None:
        parent_calls = self._patch_parent_message_handling()
        active = self._actor_address(role="dev", label="act-dev-mark-parent")
        pm = self._actor_address(role="pm", label="act-pm-mark-parent")
        seed = message_repo.save_message(
            {
                "id": "msg-mark-needs-parent",
                "from_actor_address": pm,
                "to_actor_address": active,
                "content": "This changes your current work.",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:01Z",
            }
        )
        instance_json = self._instance_json(actor_id="act-dev-mark-parent", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-mark-parent",
            role="dev",
            tool="message",
            action="mark",
            args={
                "message_id": seed["id"],
                "disposition": "needs_parent",
                "reason": "It changes the active implementation direction.",
            },
        )

        self.assertTrue(response.get("ok"), msg=response)
        stored = message_repo.get_message(seed["id"])
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored["disposition"], "needs_parent")
        self.assertEqual(stored["disposition_reason"], "It changes the active implementation direction.")
        self.assertIsInstance(stored["disposition_updated_at"], str)
        self.assertEqual(stored["processed_by_actor_address"], active)
        self.assertEqual(len(parent_calls), 1)
        self.assertEqual(parent_calls[0]["message_id"], seed["id"])
        prompt = parent_calls[0]["prompt"]
        self.assertIsInstance(prompt, str)
        assert isinstance(prompt, str)
        self.assertIn("[MESSAGE NEEDS PARENT]", prompt)
        self.assertIn(seed["id"], prompt)
        self.assertIn("It changes the active implementation direction.", prompt)
        self.assertIn("Runtime context:", prompt)
        self.assertIn("task.current", prompt)
        self.assertIn("task.capture/task.select", prompt)
        self.assertIn("If the requested work is small enough to complete now", prompt)

    def test_projected_runtime_context_uses_repo_root_for_parent_handoff_import(self) -> None:
        instance_json = self._instance_json(actor_id="act-dev-projected-parent", role="dev")
        projected_workspace = self._runtime_path("projection/workspace")
        fake_repo_root = self._runtime_path("projection/source-repo")
        launcher_dir = fake_repo_root / "tools" / "launcher"
        launcher_dir.mkdir(parents=True, exist_ok=True)
        (launcher_dir / "daemon_core.py").write_text(
            "\n".join(
                (
                    "from pathlib import Path",
                    "",
                    "class _DaemonContext:",
                    "    def __init__(self, instance_json):",
                    "        self.instance_root = Path(instance_json).resolve().parent",
                    "        self.actor_id = 'act-parent-projected'",
                    "        self.main_thread_id = 'thr-parent-projected'",
                    "",
                    "def load_daemon_context(instance_json):",
                    "    return _DaemonContext(instance_json)",
                    "",
                    "class DaemonState:",
                    "    @staticmethod",
                    "    def load(*, instance_root, actor_id, main_thread_id):",
                    "        return {",
                    "            'instance_root': str(instance_root),",
                    "            'actor_id': actor_id,",
                    "            'main_thread_id': main_thread_id,",
                    "        }",
                    "",
                    "class DaemonRuntime:",
                    "    def __init__(self, *, context, state):",
                    "        self.context = context",
                    "        self.state = state",
                    "",
                    "    def submit_parent_prompt(self, prompt, *, handler_name, origin_id, interrupt_policy):",
                    "        return {",
                    "            'prompt': prompt,",
                    "            'handler_name': handler_name,",
                    "            'origin_id': origin_id,",
                    "            'interrupt_policy': interrupt_policy,",
                    "            'instance_root': str(self.context.instance_root),",
                    "            'actor_id': self.context.actor_id,",
                    "            'main_thread_id': self.context.main_thread_id,",
                    "        }",
                )
            )
            + "\n",
            encoding="utf-8",
        )

        projected_module = self._load_projected_context_module(projected_workspace)
        self.assertFalse((projected_workspace / "tools" / "launcher").exists())

        original_daemon_core = sys.modules.pop("daemon_core", None)
        try:
            with patch.dict(os.environ, {"BUDDYSWITCH_REPO_ROOT": str(fake_repo_root)}, clear=False):
                access = projected_module.DaemonAccess(
                    actor_address=ActorAddress(actor_id="act-dev-projected-parent", role_id="dev"),
                    instance_json=instance_json,
                )
                result = access.request_parent_message_handling(
                    message_id="msg-projected-parent",
                    prompt="projected parent prompt",
                )
        finally:
            if original_daemon_core is not None:
                sys.modules["daemon_core"] = original_daemon_core
            else:
                sys.modules.pop("daemon_core", None)
            with contextlib.suppress(ValueError):
                sys.path.remove(str(launcher_dir))

        self.assertEqual(result["handler_name"], "message_mark")
        self.assertEqual(result["origin_id"], "msg-projected-parent")
        self.assertEqual(result["interrupt_policy"], "ensure_stopped")
        self.assertEqual(result["actor_id"], "act-parent-projected")

    def test_message_mark_needs_parent_uses_source_repo_root_when_broker_manifest_is_projected(self) -> None:
        active = self._actor_address(role="dev", label="act-dev-projected-broker-parent")
        pm = self._actor_address(role="pm", label="act-pm-projected-broker-parent")
        seed = message_repo.save_message(
            {
                "id": "msg-mark-needs-parent-projected-root",
                "from_actor_address": pm,
                "to_actor_address": active,
                "content": "This changes the active parent-thread objective.",
                "reply_to": None,
                "created_at": "2026-06-04T00:00:00Z",
            }
        )
        instance_json = self._instance_json(actor_id="act-dev-projected-broker-parent", role="dev")
        projected_workspace = self._runtime_path("projected-broker-workspace")
        projected_manifest = projected_workspace / "buddyswitch" / "manifest.toml"
        projected_manifest.parent.mkdir(parents=True, exist_ok=True)
        projected_manifest.write_text(MANIFEST.read_text(encoding="utf-8"), encoding="utf-8")
        fake_source_root = self._runtime_path("projected-broker-source")
        launcher_dir = fake_source_root / "tools" / "launcher"
        launcher_dir.mkdir(parents=True, exist_ok=True)
        (launcher_dir / "daemon_core.py").write_text(
            "\n".join(
                (
                    "from pathlib import Path",
                    "import json",
                    "",
                    "class _DaemonContext:",
                    "    def __init__(self, instance_json):",
                    "        payload = json.loads(Path(instance_json).read_text(encoding='utf-8'))",
                    "        self.instance_root = Path(instance_json).resolve().parent",
                    "        self.actor_id = payload['actor_id']",
                    "        self.main_thread_id = payload.get('main_thread_id') or 'thread-main-projected'",
                    "",
                    "def load_daemon_context(instance_json):",
                    "    return _DaemonContext(instance_json)",
                    "",
                    "class DaemonState:",
                    "    @staticmethod",
                    "    def load(*, instance_root, actor_id, main_thread_id):",
                    "        return {",
                    "            'instance_root': str(instance_root),",
                    "            'actor_id': actor_id,",
                    "            'main_thread_id': main_thread_id,",
                    "        }",
                    "",
                    "class DaemonRuntime:",
                    "    def __init__(self, *, context, state):",
                    "        self.context = context",
                    "        self.state = state",
                    "",
                    "    def submit_parent_prompt(self, prompt, *, handler_name, origin_id, interrupt_policy):",
                    "        payload = {",
                    "            'prompt': prompt,",
                    "            'handler_name': handler_name,",
                    "            'origin_id': origin_id,",
                    "            'interrupt_policy': interrupt_policy,",
                    "            'state': self.state,",
                    "        }",
                    "        runtime_dir = Path(self.context.instance_root) / 'runtime'",
                    "        runtime_dir.mkdir(parents=True, exist_ok=True)",
                    "        (runtime_dir / 'parent-request.json').write_text(",
                    "            json.dumps(payload, ensure_ascii=True, indent=2) + '\\n',",
                    "            encoding='utf-8',",
                    "        )",
                    "        return payload",
                )
            )
            + "\n",
            encoding="utf-8",
        )
        self.assertFalse((projected_workspace / "tools" / "launcher").exists())

        request = {
            "protocol": PROTOCOL,
            "request_id": "req-message-needs-parent-projected-root",
            "method": "env.tool",
            "params": {
                "actor_id": active["actor_id"],
                "active_role": "dev",
                "tool": "message",
                "action": "mark",
                "args": {
                    "message_id": seed["id"],
                    "disposition": "needs_parent",
                    "reason": "This changes the active parent-thread objective.",
                },
            },
            "deadline_ms": 35000,
        }
        session = dispatcher.RuntimeBrokerSession(
            instance_json_path=instance_json,
            manifest_path=projected_manifest,
            repo_root_path=fake_source_root,
        )

        original_daemon_core = sys.modules.pop("daemon_core", None)
        try:
            response = dispatcher.dispatch_runtime_request(request, session)
        finally:
            if original_daemon_core is not None:
                sys.modules["daemon_core"] = original_daemon_core
            else:
                sys.modules.pop("daemon_core", None)
            with contextlib.suppress(ValueError):
                sys.path.remove(str(launcher_dir))

        self.assertTrue(response.get("ok"), msg=response)
        self.assertIs(response.get("parent_prompt_submitted"), True, msg=response)
        response_parent_request = response.get("parent_request")
        self.assertIsInstance(response_parent_request, dict, msg=response)
        assert isinstance(response_parent_request, dict)
        self.assertEqual(response_parent_request["handler_name"], "message_mark")
        self.assertEqual(response_parent_request["origin_id"], seed["id"])
        self.assertEqual(response_parent_request["interrupt_policy"], "ensure_stopped")
        stored = message_repo.get_message(seed["id"])
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored["disposition"], "needs_parent")
        self.assertEqual(stored["disposition_reason"], "This changes the active parent-thread objective.")
        parent_request_path = self.runtime_root / "runtime" / "parent-request.json"
        parent_request = json.loads(parent_request_path.read_text(encoding="utf-8"))
        self.assertEqual(parent_request["handler_name"], "message_mark")
        self.assertEqual(parent_request["origin_id"], seed["id"])
        self.assertEqual(parent_request["interrupt_policy"], "ensure_stopped")

    def test_message_mark_needs_parent_submits_parent_prompt_before_saving_disposition(self) -> None:
        operations: list[str] = []
        self._patch_parent_message_handling_with_failures(failures=0, operations=operations)
        active = self._actor_address(role="dev", label="act-dev-mark-parent-order")
        pm = self._actor_address(role="pm", label="act-pm-mark-parent-order")
        seed = message_repo.save_message(
            {
                "id": "msg-mark-needs-parent-order",
                "from_actor_address": pm,
                "to_actor_address": active,
                "content": "This needs parent ordering.",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:01Z",
            }
        )
        self._patch_message_save_failures(
            should_fail=lambda row: row.get("id") == seed["id"] and row.get("disposition") == "needs_parent",
            failures=0,
            operations=operations,
            operation_label="save_needs_parent",
        )
        instance_json = self._instance_json(actor_id="act-dev-mark-parent-order", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-mark-parent-order",
            role="dev",
            tool="message",
            action="mark",
            args={
                "message_id": seed["id"],
                "disposition": "needs_parent",
                "reason": "Parent must decide ordering.",
            },
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(operations[:2], ["parent_prompt", "save_needs_parent"])

    def test_message_mark_needs_parent_retries_parent_prompt_before_save(self) -> None:
        sleeps = self._patch_message_retry_sleep()
        parent_calls = self._patch_parent_message_handling_with_failures(failures=1)
        active = self._actor_address(role="dev", label="act-dev-mark-parent-retry-prompt")
        pm = self._actor_address(role="pm", label="act-pm-mark-parent-retry-prompt")
        seed = message_repo.save_message(
            {
                "id": "msg-mark-needs-parent-retry-prompt",
                "from_actor_address": pm,
                "to_actor_address": active,
                "content": "Retry parent prompt once.",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:01Z",
            }
        )
        instance_json = self._instance_json(actor_id="act-dev-mark-parent-retry-prompt", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-mark-parent-retry-prompt",
            role="dev",
            tool="message",
            action="mark",
            args={
                "message_id": seed["id"],
                "disposition": "needs_parent",
                "reason": "Parent prompt is briefly unavailable.",
            },
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(len(parent_calls), 2)
        self.assertIn(0.1, sleeps)
        stored = message_repo.get_message(seed["id"])
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored["disposition"], "needs_parent")

    def test_message_mark_needs_parent_prompt_failure_leaves_original_unchanged(self) -> None:
        sleeps = self._patch_message_retry_sleep()
        parent_calls = self._patch_parent_message_handling_with_failures(failures=3)
        active = self._actor_address(role="dev", label="act-dev-mark-parent-prompt-fail")
        pm = self._actor_address(role="pm", label="act-pm-mark-parent-prompt-fail")
        seed = message_repo.save_message(
            {
                "id": "msg-mark-needs-parent-prompt-fail",
                "from_actor_address": pm,
                "to_actor_address": active,
                "content": "Parent prompt never submits.",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:01Z",
            }
        )
        instance_json = self._instance_json(actor_id="act-dev-mark-parent-prompt-fail", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-mark-parent-prompt-fail",
            role="dev",
            tool="message",
            action="mark",
            args={
                "message_id": seed["id"],
                "disposition": "needs_parent",
                "reason": "Parent prompt is unavailable.",
            },
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(len(parent_calls), 3)
        self.assertIn(0.1, sleeps)
        self.assertIn(0.25, sleeps)
        self.assertIs(response.get("state_changed"), False, msg=response)
        self.assertEqual(response.get("durability"), "none", msg=response)
        self.assertEqual(response.get("original_final_disposition"), "unseen")
        self.assertIn("parent prompt", response.get("why_blocked", "").lower())
        self.assertEqual(message_repo.get_message(seed["id"]), seed)

    def test_message_mark_needs_parent_retries_disposition_save_after_prompt(self) -> None:
        sleeps = self._patch_message_retry_sleep()
        parent_calls = self._patch_parent_message_handling_with_failures(failures=0)
        active = self._actor_address(role="dev", label="act-dev-mark-parent-save-retry")
        pm = self._actor_address(role="pm", label="act-pm-mark-parent-save-retry")
        seed = message_repo.save_message(
            {
                "id": "msg-mark-needs-parent-save-retry",
                "from_actor_address": pm,
                "to_actor_address": active,
                "content": "Save needs retry after prompt.",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:01Z",
            }
        )
        save_attempts = self._patch_message_save_failures(
            should_fail=lambda row: row.get("id") == seed["id"] and row.get("disposition") == "needs_parent",
            failures=1,
        )
        instance_json = self._instance_json(actor_id="act-dev-mark-parent-save-retry", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-mark-parent-save-retry",
            role="dev",
            tool="message",
            action="mark",
            args={
                "message_id": seed["id"],
                "disposition": "needs_parent",
                "reason": "Disposition save is briefly unavailable.",
            },
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(len(parent_calls), 1)
        self.assertEqual(len(save_attempts), 2)
        self.assertIn(0.1, sleeps)
        stored = message_repo.get_message(seed["id"])
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored["disposition"], "needs_parent")

    def test_message_mark_needs_parent_save_failure_reports_prompt_submitted_and_unchanged_original(self) -> None:
        sleeps = self._patch_message_retry_sleep()
        parent_calls = self._patch_parent_message_handling_with_failures(failures=0)
        active = self._actor_address(role="dev", label="act-dev-mark-parent-save-fail")
        pm = self._actor_address(role="pm", label="act-pm-mark-parent-save-fail")
        seed = message_repo.save_message(
            {
                "id": "msg-mark-needs-parent-save-fail",
                "from_actor_address": pm,
                "to_actor_address": active,
                "content": "Save never succeeds after prompt.",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:01Z",
            }
        )
        save_attempts = self._patch_message_save_failures(
            should_fail=lambda row: row.get("id") == seed["id"] and row.get("disposition") == "needs_parent",
            failures=3,
        )
        instance_json = self._instance_json(actor_id="act-dev-mark-parent-save-fail", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-mark-parent-save-fail",
            role="dev",
            tool="message",
            action="mark",
            args={
                "message_id": seed["id"],
                "disposition": "needs_parent",
                "reason": "Disposition store is unavailable.",
            },
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(len(parent_calls), 1)
        self.assertEqual(len(save_attempts), 3)
        self.assertIn(0.1, sleeps)
        self.assertIn(0.25, sleeps)
        self.assertIs(response.get("state_changed"), True, msg=response)
        self.assertEqual(response.get("durability"), "durable", msg=response)
        self.assertEqual(response.get("message_id"), seed["id"])
        self.assertEqual(response.get("original_previous_disposition"), "unseen")
        self.assertEqual(response.get("original_final_disposition"), "unseen")
        self.assertIn("parent_request", response)
        self.assertIn("disposition save failed", response.get("why_blocked", "").lower())
        self.assertEqual(message_repo.get_message(seed["id"]), seed)

    def test_message_mark_rejects_missing_parent_reason_and_invalid_transitions(self) -> None:
        active = self._actor_address(role="dev", label="act-dev-mark-reject")
        pm = self._actor_address(role="pm", label="act-pm-mark-reject")
        message_repo.save_message(
            {
                "id": "msg-mark-no-reason",
                "from_actor_address": pm,
                "to_actor_address": active,
                "content": "needs reason",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:01Z",
            }
        )
        for message_id, disposition in (("msg-mark-done-absorbed", "absorbed"), ("msg-mark-done-replied", "replied")):
            message_repo.save_message(
                {
                    "id": message_id,
                    "from_actor_address": pm,
                    "to_actor_address": active,
                    "content": f"done {disposition}",
                    "reply_to": None,
                    "created_at": "2026-05-30T00:00:02Z",
                    "disposition": disposition,
                    "disposition_reason": None,
                    "disposition_updated_at": "2026-05-30T00:00:03Z",
                    "processed_by_actor_address": active,
                }
            )
        instance_json = self._instance_json(actor_id="act-dev-mark-reject", role="dev")
        cases = (
            ("msg-mark-no-reason", {"message_id": "msg-mark-no-reason", "disposition": "needs_parent"}),
            ("msg-mark-done-absorbed", {"message_id": "msg-mark-done-absorbed", "disposition": "absorbed"}),
            (
                "msg-mark-done-replied",
                {"message_id": "msg-mark-done-replied", "disposition": "needs_parent", "reason": "retry"},
            ),
        )

        for message_id, args in cases:
            with self.subTest(message_id=message_id):
                before = message_repo.get_message(message_id)
                response = self._dispatch(
                    instance_json=instance_json,
                    actor_id="act-dev-mark-reject",
                    role="dev",
                    tool="message",
                    action="mark",
                    args=args,
                )
                after = message_repo.get_message(message_id)

                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual(after, before)

    def test_message_conversation_returns_visible_bidirectional_actor_messages(self) -> None:
        active = self._actor_address(role="dev", label="act-dev-conversation")
        other_dev = self._actor_address(role="dev", label="act-dev-conversation-other")
        pm = self._actor_address(role="pm", label="act-pm-conversation")
        design = self._actor_address(role="design", label="act-design-conversation")
        market = self._actor_address(role="market", label="act-market-conversation")
        first = message_repo.save_message(
            {
                "id": "msg-conv-visible-1",
                "from_actor_address": pm,
                "to_actor_address": active,
                "content": "PM to active Dev",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:01Z",
            }
        )
        second = message_repo.save_message(
            {
                "id": "msg-conv-visible-2",
                "from_actor_address": active,
                "to_actor_address": pm,
                "content": "Dev to PM",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:02Z",
            }
        )
        message_repo.save_message(
            {
                "id": "msg-conv-visible-other-dev",
                "from_actor_address": pm,
                "to_actor_address": other_dev,
                "content": "PM to other Dev",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:03Z",
            }
        )
        message_repo.save_message(
            {
                "id": "msg-conv-visible-design",
                "from_actor_address": design,
                "to_actor_address": pm,
                "content": "Design to PM",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:04Z",
            }
        )
        message_repo.save_message(
            {
                "id": "msg-conv-visible-market",
                "from_actor_address": market,
                "to_actor_address": active,
                "content": "Market to Dev",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:05Z",
            }
        )
        instance_json = self._instance_json(actor_id="act-dev-conversation", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-conversation",
            role="dev",
            tool="message",
            action="conversation",
            args={"target_actor_address": pm},
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("read_scope"), "active actor visible direct conversation messages")
        self.assertEqual(response.get("selector"), {"target_actor_address": pm})
        messages = response.get("messages")
        self.assertIsInstance(messages, list, msg=response)
        assert isinstance(messages, list)
        self.assertEqual([row["id"] for row in messages], [first["id"], second["id"]])
        self.assertEqual(response.get("count"), 2)
        self.assertEqual({row["content"] for row in messages}, {"PM to active Dev", "Dev to PM"})

    def test_message_conversation_rejects_role_field(self) -> None:
        instance_json = self._instance_json(actor_id="act-dev-conversation-role", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-conversation-role",
            role="dev",
            tool="message",
            action="conversation",
            args={"role": "dev"},
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_PAYLOAD")
        self.assertEqual(response.get("correctable_fields"), ["role"])

    def test_message_conversation_requires_target_actor_address(self) -> None:
        instance_json = self._instance_json(actor_id="act-dev-conversation-selector", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-conversation-selector",
            role="dev",
            tool="message",
            action="conversation",
            args={},
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_PAYLOAD")
        self.assertEqual(response.get("correctable_fields"), ["target_actor_address"])

    def test_message_conversation_rejects_old_direction_fields(self) -> None:
        instance_json = self._instance_json(actor_id="act-dev-conversation-old-fields", role="dev")
        target = self._actor_address(role="pm", label="act-pm-conversation-old-fields")
        for field, value in (("box", "inbox"), ("to_role", "pm"), ("from_role", "pm")):
            with self.subTest(field=field):
                response = self._dispatch(
                    instance_json=instance_json,
                    actor_id="act-dev-conversation-old-fields",
                    role="dev",
                    tool="message",
                    action="conversation",
                    args={"target_actor_address": target, field: value},
                )
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_PAYLOAD")
                self.assertEqual(response.get("correctable_fields"), [field])

    def test_message_conversation_applies_latest_limit_then_returns_chronological(self) -> None:
        active = self._actor_address(role="dev", label="act-dev-conversation-limit")
        pm = self._actor_address(role="pm", label="act-pm-conversation-limit")
        rows = []
        for index in range(5):
            row = message_repo.save_message(
                {
                    "id": f"msg-conv-limit-{index}",
                    "from_actor_address": pm if index % 2 == 0 else active,
                    "to_actor_address": active if index % 2 == 0 else pm,
                    "content": f"message {index}",
                    "reply_to": None,
                    "created_at": f"2026-05-30T00:00:0{index}Z",
                }
            )
            rows.append(row)
        instance_json = self._instance_json(actor_id="act-dev-conversation-limit", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-conversation-limit",
            role="dev",
            tool="message",
            action="conversation",
            args={"target_actor_address": pm, "limit": 3},
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual([row["id"] for row in response.get("messages", [])], [row["id"] for row in rows[2:5]])

    def test_message_conversation_accepts_external_user_participant(self) -> None:
        active = self._actor_address(role="dev", label="act-dev-user-conversation")
        web_user = {"role_id": "user", "actor_id": "act-user-local"}
        first = message_repo.save_message(
            {
                "id": "msg-user-conv-1",
                "from_actor_address": web_user,
                "to_actor_address": active,
                "content": "Browser message",
                "reply_to": None,
                "created_at": "2026-06-23T00:00:01Z",
            }
        )
        second = message_repo.save_message(
            {
                "id": "msg-user-conv-2",
                "from_actor_address": active,
                "to_actor_address": web_user,
                "content": "Actor reply",
                "reply_to": first["id"],
                "created_at": "2026-06-23T00:00:02Z",
            }
        )
        instance_json = self._instance_json(actor_id="act-dev-user-conversation", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-user-conversation",
            role="dev",
            tool="message",
            action="conversation",
            args={"target_actor_address": web_user},
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual([row["id"] for row in response.get("messages", [])], [first["id"], second["id"]])
        self.assertEqual(response.get("selector"), {"target_actor_address": web_user})

    def test_message_send_reply_to_accepts_same_visible_actor_conversation_pair(self) -> None:
        self._patch_daemon()
        dev = self._actor_address(role="dev", label="act-dev-reply")
        pm = self._actor_address(role="pm", label="act-pm-reply")
        seed = env_store.create_message(from_actor_address=pm, to_actor_address=dev, content="Hello from PM")
        instance_json = self._instance_json(actor_id="act-dev-reply", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-reply",
            role="dev",
            tool="message",
            action="send",
            args={"target_actor_address": pm, "content": "ack", "reply_to": seed["id"]},
        )

        self.assertTrue(response.get("ok"), msg=response)
        rows = self._message_rows()
        reply = next(row for row in rows if row["id"] == response["message_id"])
        self.assertEqual(reply["reply_to"], seed["id"])
        original = message_repo.get_message(seed["id"])
        self.assertIsNotNone(original)
        assert original is not None
        self.assertEqual(original["disposition"], "replied")
        self.assertEqual(original["processed_by_actor_address"], dev)
        self.assertIsInstance(original["disposition_updated_at"], str)

    def test_message_send_reply_to_transitions_needs_parent_to_replied(self) -> None:
        self._patch_daemon()
        dev = self._actor_address(role="dev", label="act-dev-reply-parent")
        pm = self._actor_address(role="pm", label="act-pm-reply-parent")
        seed = message_repo.save_message(
            {
                "id": "msg-reply-needs-parent",
                "from_actor_address": pm,
                "to_actor_address": dev,
                "content": "Needs parent before reply",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:01Z",
                "disposition": "needs_parent",
                "disposition_reason": "Requires parent context.",
                "disposition_updated_at": "2026-05-30T00:00:02Z",
                "processed_by_actor_address": dev,
            }
        )
        instance_json = self._instance_json(actor_id="act-dev-reply-parent", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-reply-parent",
            role="dev",
            tool="message",
            action="send",
            args={"target_actor_address": pm, "content": "parent-approved reply", "reply_to": seed["id"]},
        )

        self.assertTrue(response.get("ok"), msg=response)
        original = message_repo.get_message(seed["id"])
        self.assertIsNotNone(original)
        assert original is not None
        self.assertEqual(original["disposition"], "replied")
        self.assertIsNone(original["disposition_reason"])
        self.assertEqual(original["processed_by_actor_address"], dev)

    def test_message_send_reply_to_retries_replied_save_after_delivery(self) -> None:
        self._patch_daemon()
        sleeps = self._patch_message_retry_sleep()
        dev = self._actor_address(role="dev", label="act-dev-reply-save-retry")
        pm = self._actor_address(role="pm", label="act-pm-reply-save-retry")
        seed = env_store.create_message(from_actor_address=pm, to_actor_address=dev, content="Retry save after reply")
        save_attempts = self._patch_message_save_failures(
            should_fail=lambda row: row.get("id") == seed["id"] and row.get("disposition") == "replied",
            failures=1,
        )
        instance_json = self._instance_json(actor_id="act-dev-reply-save-retry", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-reply-save-retry",
            role="dev",
            tool="message",
            action="send",
            args={"target_actor_address": pm, "content": "ack after retry", "reply_to": seed["id"]},
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(len(save_attempts), 2)
        self.assertIn(0.1, sleeps)
        self.assertEqual(response.get("delivery_status"), "delivered")
        self.assertEqual(response.get("reply_to"), seed["id"])
        self.assertEqual(response.get("original_message_id"), seed["id"])
        self.assertEqual(response.get("original_final_disposition"), "replied")
        original = message_repo.get_message(seed["id"])
        self.assertIsNotNone(original)
        assert original is not None
        self.assertEqual(original["disposition"], "replied")

    def test_message_send_reply_to_save_failure_reports_delivered_reply_and_unchanged_original(self) -> None:
        self._patch_daemon()
        sleeps = self._patch_message_retry_sleep()
        dev = self._actor_address(role="dev", label="act-dev-reply-save-fail")
        pm = self._actor_address(role="pm", label="act-pm-reply-save-fail")
        seed = env_store.create_message(from_actor_address=pm, to_actor_address=dev, content="Reply save will fail")
        save_attempts = self._patch_message_save_failures(
            should_fail=lambda row: row.get("id") == seed["id"] and row.get("disposition") == "replied",
            failures=3,
        )
        instance_json = self._instance_json(actor_id="act-dev-reply-save-fail", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-reply-save-fail",
            role="dev",
            tool="message",
            action="send",
            args={"target_actor_address": pm, "content": "ack but save fails", "reply_to": seed["id"]},
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(len(save_attempts), 3)
        self.assertIn(0.1, sleeps)
        self.assertIn(0.25, sleeps)
        self.assertIs(response.get("state_changed"), True, msg=response)
        self.assertEqual(response.get("durability"), "durable", msg=response)
        self.assertEqual(response.get("delivery_status"), "delivered")
        self.assertIsInstance(response.get("message_id"), str, msg=response)
        self.assertEqual(response.get("reply_to"), seed["id"])
        self.assertEqual(response.get("original_message_id"), seed["id"])
        self.assertEqual(response.get("original_previous_disposition"), "unseen")
        self.assertEqual(response.get("original_final_disposition"), "unseen")
        self.assertIn("Do not blindly send another reply", response.get("retry_guidance", ""))
        rows = self._message_rows()
        reply = next(row for row in rows if row["id"] == response.get("message_id"))
        self.assertEqual(reply["reply_to"], seed["id"])
        original = message_repo.get_message(seed["id"])
        self.assertIsNotNone(original)
        assert original is not None
        self.assertEqual(original["disposition"], "unseen")
        self.assertIsNone(original["processed_by_actor_address"])

    def test_message_send_reply_to_delivery_failure_does_not_transition_original(self) -> None:
        self._patch_daemon(delivery={"delivery_status": "delivery_failed", "signal_error": "socket gone"})
        dev = self._actor_address(role="dev", label="act-dev-reply-failed")
        pm = self._actor_address(role="pm", label="act-pm-reply-failed")
        seed = env_store.create_message(from_actor_address=pm, to_actor_address=dev, content="Hello from PM")
        instance_json = self._instance_json(actor_id="act-dev-reply-failed", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-reply-failed",
            role="dev",
            tool="message",
            action="send",
            args={"target_actor_address": pm, "content": "ack", "reply_to": seed["id"]},
        )

        self.assertFalse(response.get("ok"), msg=response)
        original = message_repo.get_message(seed["id"])
        self.assertIsNotNone(original)
        assert original is not None
        self.assertEqual(original["disposition"], "unseen")
        self.assertIsNone(original["processed_by_actor_address"])

    def test_message_send_reply_to_accepts_external_user_participant(self) -> None:
        calls = self._patch_daemon()
        dev = self._actor_address(role="dev", label="act-dev-user-reply")
        web_user = {"role_id": "user", "actor_id": "act-user-local"}
        seed = env_store.create_message(
            from_actor_address=web_user,
            to_actor_address=dev,
            content="Hello from the browser",
        )
        instance_json = self._instance_json(actor_id="act-dev-user-reply", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-user-reply",
            role="dev",
            tool="message",
            action="send",
            args={"target_actor_address": web_user, "content": "ack to browser", "reply_to": seed["id"]},
        )

        self.assertTrue(response.get("ok"), msg=response)
        rows = self._message_rows()
        reply = next(row for row in rows if row["id"] == response["message_id"])
        self.assertEqual(reply["from_actor_address"], dev)
        self.assertEqual(reply["to_actor_address"], web_user)
        self.assertEqual(reply["reply_to"], seed["id"])
        original = message_repo.get_message(seed["id"])
        self.assertIsNotNone(original)
        assert original is not None
        self.assertEqual(original["disposition"], "replied")
        self.assertEqual(original["processed_by_actor_address"], dev)
        self.assertEqual([call[0] for call in calls], ["reachability", "deliver"])
        self.assertEqual(calls[1][1]["signal"]["target_actor_address"], web_user)

    def test_message_send_reply_to_rejects_duplicate_completed_processing(self) -> None:
        self._patch_daemon()
        dev = self._actor_address(role="dev", label="act-dev-reply-duplicate")
        pm = self._actor_address(role="pm", label="act-pm-reply-duplicate")
        seed = message_repo.save_message(
            {
                "id": "msg-reply-duplicate",
                "from_actor_address": pm,
                "to_actor_address": dev,
                "content": "Already handled",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:01Z",
                "disposition": "replied",
                "disposition_reason": None,
                "disposition_updated_at": "2026-05-30T00:00:02Z",
                "processed_by_actor_address": dev,
            }
        )
        instance_json = self._instance_json(actor_id="act-dev-reply-duplicate", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-reply-duplicate",
            role="dev",
            tool="message",
            action="send",
            args={"target_actor_address": pm, "content": "second reply", "reply_to": seed["id"]},
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(message_repo.get_message(seed["id"]), seed)

    def test_message_send_reply_to_requires_same_visible_actor_conversation_pair(self) -> None:
        self._patch_daemon()
        dev = self._actor_address(role="dev", label="act-dev-cross")
        pm = self._actor_address(role="pm", label="act-pm-cross")
        design = self._actor_address(role="design", label="act-design-cross")
        seed = env_store.create_message(from_actor_address=design, to_actor_address=pm, content="Design to PM")
        instance_json = self._instance_json(actor_id="act-dev-cross", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-cross",
            role="dev",
            tool="message",
            action="send",
            args={"target_actor_address": pm, "content": "bad", "reply_to": seed["id"]},
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("permission_boundary"), "message.reply_to_scope")
        self.assertEqual(self._message_rows(), [seed])

    def test_message_send_rejects_blank_content(self) -> None:
        self._patch_daemon()
        instance_json = self._instance_json(actor_id="act-pm-blank", role="pm")
        target = self._actor_address(role="dev", label="act-dev-blank")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-blank",
            role="pm",
            tool="message",
            action="send",
            args={"target_actor_address": target, "content": "   "},
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertIn("E_MESSAGE_PAYLOAD", response.get("error", {}).get("code", ""))

    def test_message_send_rejects_broadcast_recipient_and_status_payload_fields(self) -> None:
        self._patch_daemon()
        instance_json = self._instance_json(actor_id="act-pm-extra-fields", role="pm")
        target = self._actor_address(role="dev", label="act-dev-extra-fields")
        for field, value in (("broadcast", True), ("recipients", ["dev"]), ("status", "unread")):
            with self.subTest(field=field):
                response = self._dispatch(
                    instance_json=instance_json,
                    actor_id="act-pm-extra-fields",
                    role="pm",
                    tool="message",
                    action="send",
                    args={"target_actor_address": target, "content": "x", field: value},
                )
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual(response.get("correctable_fields"), [field])

    def test_message_list_rejects_product_binding_and_status_fields(self) -> None:
        instance_json = self._instance_json(actor_id="act-dev-message-bindings", role="dev")
        for field, value in (
            ("track_id", "track-x"),
            ("artifact_id", "art-x"),
            ("request_id", "req-x"),
            ("refs", []),
            ("status", "unread"),
        ):
            with self.subTest(field=field):
                response = self._dispatch(
                    instance_json=instance_json,
                    actor_id="act-dev-message-bindings",
                    role="dev",
                    tool="message",
                    action="list",
                    args={field: value},
                )
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_PAYLOAD")

    def test_message_storage_boundary_has_no_role_level_fields(self) -> None:
        source = (ROOT / "scripts" / "env" / "repos" / "messages.py").read_text(encoding="utf-8")
        self.assertNotIn("from_role", source)
        self.assertNotIn("to_role", source)

    def test_message_active_user_role_is_not_manifest_declared(self) -> None:
        domain = runtime_context.DomainAccess().message
        manifest_roles = domain.manifest_role_ids(
            {"roles": [{"id": "pm"}, {"id": "dev"}, {"id": "design"}]}
        )

        with self.assertRaises(domain.MessageScopeError):
            domain.ensure_active_role_is_manifest_declared(
                active_role="user",
                manifest_role_ids=manifest_roles,
            )

    def test_message_edit_delete_and_read_receipt_actions_are_unsupported(self) -> None:
        instance_json = self._instance_json(actor_id="act-dev-unsup", role="dev")
        for action in ("edit", "update", "delete", "mark_read", "read"):
            with self.subTest(action=action):
                response = self._dispatch(
                    instance_json=instance_json,
                    actor_id="act-dev-unsup",
                    role="dev",
                    tool="message",
                    action=action,
                    args={},
                )
                self.assertFalse(response.get("ok"), msg=response)
                self.assertIn("E_ENV_TOOL", response.get("error", {}).get("code", ""))


if __name__ == "__main__":
    unittest.main()
