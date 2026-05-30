#!/usr/bin/env python3
"""Runtime actor profile and env.tool auth-boundary tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.tool_runtime import auth_feedback  # noqa: E402
from env.tool_runtime import context as runtime_context  # noqa: E402
from env.tool_runtime import registry as tool_registry  # noqa: E402
from env.tool_runtime.actor_profile import AuthSubject  # noqa: E402
from env.tool_runtime.actor_profile import RuntimeActorAddress  # noqa: E402
from env.tool_runtime.actor_profile import RuntimeInstanceRecord  # noqa: E402
from env.tool_runtime.actor_profile import resolve_runtime_actor_profile  # noqa: E402
from env.tool_runtime.context import ToolContext  # noqa: E402
from env.tool_runtime.role_auth import AuthDecision  # noqa: E402


class RuntimeActorProfileTests(unittest.TestCase):
    def test_runtime_actor_address_serializes_stable_payload(self) -> None:
        address = RuntimeActorAddress(
            buddy_id="  dev  ",
            instance_id="  inst-dev-daemon  ",
        )

        self.assertEqual(address.buddy_id, "dev")
        self.assertEqual(address.instance_id, "inst-dev-daemon")
        self.assertEqual(
            address.to_payload(),
            {"buddy_id": "dev", "instance_id": "inst-dev-daemon"},
        )
        self.assertEqual(RuntimeActorAddress.from_payload(address.to_payload()), address)

    def test_runtime_actor_address_accepts_current_launcher_instance_id_shape(self) -> None:
        address = RuntimeActorAddress(
            buddy_id="dev",
            instance_id="inst-dev-Daemon_1",
        )

        self.assertEqual(address.instance_id, "inst-dev-Daemon_1")

    def test_runtime_actor_address_payload_rejects_non_identity_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-identity fields"):
            RuntimeActorAddress.from_payload(
                {
                    "buddy_id": "dev",
                    "instance_id": "inst-dev-daemon",
                    "endpoint": {"kind": "daemon_state_file"},
                    "heartbeat": {"kind": "daemon_ready_state"},
                    "status": "online",
                }
            )

    def test_runtime_actor_address_rejects_invalid_identity(self) -> None:
        cases = (
            ("", "inst-dev-daemon", "buddy_id"),
            ("Dev", "inst-dev-daemon", "buddy_id"),
            ("dev_ops", "inst-dev-daemon", "buddy_id"),
            ("dev.ops", "inst-dev-daemon", "buddy_id"),
            ("dev", "", "instance_id"),
            ("dev", "dev-daemon", "instance_id"),
            ("dev", "inst-dev daemon", "instance_id"),
            ("dev", "inst-design-1a2b3c4d5e6f", "instance_id"),
        )
        for buddy_id, instance_id, field in cases:
            with self.subTest(buddy_id=buddy_id, instance_id=instance_id):
                with self.assertRaisesRegex(ValueError, field):
                    RuntimeActorAddress(buddy_id=buddy_id, instance_id=instance_id)

    def test_actor_profile_normalizes_trusted_runtime_identity(self) -> None:
        instance_json = ROOT / "tmp" / "inst-dev-1a2b3c4d5e6f" / "instance.json"
        record = RuntimeInstanceRecord(
            instance_id="  inst-dev-1a2b3c4d5e6f  ",
            buddy_id="  dev  ",
            instance_json=instance_json,
            payload={
                "instance_id": "payload-is-not-the-api",
                "buddy": "payload-is-not-the-api",
                "workspace_dir": str(ROOT),
            },
        )

        profile = resolve_runtime_actor_profile(record)

        self.assertEqual(profile.instance_id, "inst-dev-1a2b3c4d5e6f")
        self.assertEqual(profile.active_buddy, "dev")
        self.assertEqual(profile.actor_address, RuntimeActorAddress("dev", "inst-dev-1a2b3c4d5e6f"))
        self.assertEqual(profile.active_buddy, profile.actor_address.buddy_id)
        self.assertEqual(profile.instance_id, profile.actor_address.instance_id)
        self.assertIsInstance(profile.auth_subject, AuthSubject)
        self.assertEqual(profile.auth_subject.role_id, "dev")
        self.assertEqual(profile.instance_record.instance_id, "inst-dev-1a2b3c4d5e6f")
        self.assertEqual(profile.instance_record.buddy_id, "dev")
        self.assertEqual(profile.instance_record.instance_json, instance_json)
        self.assertEqual(profile.instance_record.payload["workspace_dir"], str(ROOT))
        for runtime_fact in ("endpoint", "heartbeat", "presence", "status", "routing", "delivery_status", "message"):
            self.assertFalse(hasattr(profile, runtime_fact), msg=runtime_fact)

    def test_actor_profile_rejects_missing_local_identity(self) -> None:
        cases = (
            ("", "dev", "instance_id"),
            ("   ", "dev", "instance_id"),
            ("inst-dev-1a2b3c4d5e6f", "", "buddy_id"),
            ("inst-dev-1a2b3c4d5e6f", "   ", "buddy_id"),
        )
        for instance_id, buddy_id, field in cases:
            with self.subTest(field=field):
                record = RuntimeInstanceRecord(
                    instance_id=instance_id,
                    buddy_id=buddy_id,
                    instance_json=ROOT / "tmp" / "instance.json",
                    payload={},
                )
                with self.assertRaisesRegex(ValueError, field):
                    resolve_runtime_actor_profile(record)

    def test_auth_feedback_owns_role_auth_rejection_shape(self) -> None:
        decision = AuthDecision(
            allowed=False,
            required_permission="track.create",
            active_role="dev",
            allowed_roles=("pm",),
            reason="active role 'dev' is not allowed to use required permission 'track.create'",
        )

        response = auth_feedback.role_auth_rejection(
            tool="track",
            action="create",
            active_buddy="dev",
            decision=decision,
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_TOOL_ROLE_AUTH")
        self.assertEqual(response.get("permission_boundary"), "tool.role_authority")
        self.assertEqual(response.get("category"), "auth_denied")
        self.assertEqual(response.get("auth_source"), "env.tool role-action policy")
        self.assertEqual(response.get("auth_stage"), "pre_dispatch")
        self.assertIs(response.get("executed"), False)
        self.assertEqual(response.get("required_permission"), "track.create")
        self.assertEqual(response.get("active_role"), "dev")
        self.assertEqual(response.get("allowed_roles"), ["pm"])
        self.assertIs(response.get("state_changed"), False)
        self.assertEqual(response.get("durability"), "none")

    def test_tool_context_can_be_constructed_from_actor_profile(self) -> None:
        instance_json = ROOT / "tmp" / "inst-dev-1a2b3c4d5e6f" / "instance.json"
        profile = resolve_runtime_actor_profile(
            RuntimeInstanceRecord(
                instance_id="inst-dev-1a2b3c4d5e6f",
                buddy_id="dev",
                instance_json=instance_json,
                payload={"instance_id": "inst-dev-1a2b3c4d5e6f", "buddy": "dev", "workspace_dir": str(ROOT)},
            )
        )
        manifest = {"buddies": [{"id": "dev"}, {"id": "pm"}]}

        context = ToolContext.from_actor_profile(
            actor_profile=profile,
            instance_json=instance_json,
            instance_payload=dict(profile.instance_record.payload),
            manifest=manifest,
            manifest_path=None,
        )

        self.assertEqual(context.active_buddy, "dev")
        self.assertEqual(context.instance_id, "inst-dev-1a2b3c4d5e6f")
        self.assertEqual(context.actor_address, RuntimeActorAddress("dev", "inst-dev-1a2b3c4d5e6f"))
        self.assertEqual(context.auth_subject, AuthSubject(role_id="dev"))
        self.assertEqual(context["active_buddy"], "dev")
        self.assertEqual(context["instance_id"], "inst-dev-1a2b3c4d5e6f")
        self.assertEqual(context["instance_json"], instance_json)
        self.assertEqual(context["manifest"], manifest)
        self.assertNotIn("auth_subject", list(context))

        preview = context.runtime_policy_preview(
            {
                "track.create": {"required_permission": "track.create"},
                "track.list": {"required_permission": "track.read"},
            }
        )
        self.assertEqual(preview.get("active_role"), "dev")
        self.assertIn("track.list", preview.get("available_actions", []))
        self.assertIn("track.create", preview.get("restricted_actions", []))

    def test_tool_context_daemon_access_uses_explicit_central_daemon_client(self) -> None:
        instance_json = ROOT / "tmp" / "inst-design-daemon" / "instance.json"
        profile = resolve_runtime_actor_profile(
            RuntimeInstanceRecord(
                instance_id="inst-design-daemon",
                buddy_id="design",
                instance_json=instance_json,
                payload={"instance_id": "inst-design-daemon", "buddy": "design", "workspace_dir": str(ROOT)},
            )
        )
        context = ToolContext.from_actor_profile(
            actor_profile=profile,
            instance_json=instance_json,
            instance_payload=dict(profile.instance_record.payload),
            manifest={"buddies": [{"id": "design"}, {"id": "dev"}]},
            manifest_path=None,
        )
        calls: list[tuple[str, dict[str, object]]] = []

        original_list_contacts = runtime_context.daemon_client.list_contacts
        original_check_reachability = runtime_context.daemon_client.check_reachability
        original_deliver_signal = runtime_context.daemon_client.deliver_signal

        def fake_list_contacts(*, buddy_id: str | None = None) -> dict[str, object]:
            calls.append(("contacts", {"buddy_id": buddy_id}))
            return {"contacts": [], "count": 0}

        def fake_check_reachability(*, target_actor_address: dict[str, object]) -> dict[str, object]:
            calls.append(("reachability", {"target_actor_address": target_actor_address}))
            return {"reachability_status": "online", "target_actor_address": target_actor_address}

        def fake_deliver_signal(*, signal: dict[str, object]) -> dict[str, object]:
            calls.append(("deliver", {"signal": signal}))
            return {"delivery_status": "delivered", "signal": signal}

        try:
            runtime_context.daemon_client.list_contacts = fake_list_contacts
            runtime_context.daemon_client.check_reachability = fake_check_reachability
            runtime_context.daemon_client.deliver_signal = fake_deliver_signal

            context.daemon.list_contacts(buddy_id="dev")
            context.daemon.check_reachability(
                target_actor_address={"buddy_id": "dev", "instance_id": "inst-dev-daemon"}
            )
            context.daemon.deliver_message_available(
                message_id="msg-123",
                target_actor_address=RuntimeActorAddress("dev", "inst-dev-daemon"),
            )
        finally:
            runtime_context.daemon_client.list_contacts = original_list_contacts
            runtime_context.daemon_client.check_reachability = original_check_reachability
            runtime_context.daemon_client.deliver_signal = original_deliver_signal

        self.assertEqual(calls[0], ("contacts", {"buddy_id": "dev"}))
        self.assertEqual(
            calls[1],
            (
                "reachability",
                {"target_actor_address": {"buddy_id": "dev", "instance_id": "inst-dev-daemon"}},
            ),
        )
        signal = calls[2][1]["signal"]
        self.assertEqual(
            {
                "type": signal["type"],
                "source_actor_address": signal["source_actor_address"],
                "target_actor_address": signal["target_actor_address"],
                "payload": signal["payload"],
            },
            {
                "type": "message.available",
                "source_actor_address": {"buddy_id": "design", "instance_id": "inst-design-daemon"},
                "target_actor_address": {"buddy_id": "dev", "instance_id": "inst-dev-daemon"},
                "payload": {"message_id": "msg-123"},
            },
        )
        self.assertRegex(signal["signal_id"], r"^sig-")
        self.assertIsInstance(signal["created_at"], str)
        self.assertNotIn("message_id", signal)
        self.assertNotIn("to_buddy", signal)
        self.assertNotIn("content", signal)

    def test_runtime_boundary_ownership_is_searchable(self) -> None:
        self.assertFalse(hasattr(tool_registry, "_role_auth_rejection"))
        registry_text = (ROOT / "scripts" / "env" / "tool_runtime" / "registry.py").read_text(encoding="utf-8")
        self.assertNotIn("E_TOOL_ROLE_AUTH", registry_text)

        violations: list[str] = []
        tools_root = ROOT / "scripts" / "env" / "tools"
        for path in sorted(tools_root.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            if "env.tool_runtime.actor_profile" in text or "RuntimeActorProfile" in text:
                violations.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
