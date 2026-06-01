#!/usr/bin/env python3
"""Actor Identity and env.tool auth-boundary tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.tool_runtime import auth_feedback  # noqa: E402
from env.tool_runtime import context as runtime_context  # noqa: E402
from env.tool_runtime import registry as tool_registry  # noqa: E402
from env.tool_runtime.actor_profile import Actor  # noqa: E402
from env.tool_runtime.actor_profile import ActorAddress  # noqa: E402
from env.tool_runtime.actor_profile import AuthSubject  # noqa: E402
from env.tool_runtime.actor_profile import Role  # noqa: E402
from env.tool_runtime.actor_profile import RuntimeActorRecord  # noqa: E402
from env.tool_runtime.actor_profile import resolve_actor_profile  # noqa: E402
from env.tool_runtime.context import ToolContext  # noqa: E402
from env.tool_runtime.role_auth import AuthDecision  # noqa: E402


class ActorProfileTests(unittest.TestCase):
    def test_actor_address_serializes_stable_payload(self) -> None:
        address = ActorAddress(
            actor_id="  act-dev-daemon  ",
            role_id="  dev  ",
        )

        self.assertEqual(address.actor_id, "act-dev-daemon")
        self.assertEqual(address.role_id, "dev")
        self.assertEqual(
            address.to_payload(),
            {"actor_id": "act-dev-daemon", "role_id": "dev"},
        )
        self.assertEqual(ActorAddress.from_payload(address.to_payload()), address)

    def test_actor_address_accepts_current_launcher_actor_id_shape(self) -> None:
        address = ActorAddress(
            actor_id="act-dev-Daemon_1",
            role_id="dev",
        )

        self.assertEqual(address.actor_id, "act-dev-Daemon_1")

    def test_actor_address_payload_rejects_non_identity_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-identity fields"):
            ActorAddress.from_payload(
                {
                    "actor_id": "act-dev-daemon",
                    "role_id": "dev",
                    "endpoint": {"kind": "daemon_state_file"},
                    "heartbeat": {"kind": "daemon_ready_state"},
                    "status": "online",
                }
            )
        with self.assertRaisesRegex(ValueError, "missing required fields"):
            ActorAddress.from_payload({"actor_id": "act-dev-daemon"})

    def test_actor_address_rejects_invalid_identity(self) -> None:
        cases = (
            ("", "dev", "actor_id"),
            ("dev-daemon", "dev", "actor_id"),
            ("act-dev daemon", "dev", "actor_id"),
            ("act-dev-daemon", "", "role_id"),
            ("act-dev-daemon", "Dev", "role_id"),
            ("act-dev-daemon", "dev_ops", "role_id"),
            ("act-dev-daemon", "dev.ops", "role_id"),
        )
        for actor_id, role_id, field in cases:
            with self.subTest(actor_id=actor_id, role_id=role_id):
                with self.assertRaisesRegex(ValueError, field):
                    ActorAddress(actor_id=actor_id, role_id=role_id)

    def test_actor_profile_normalizes_trusted_runtime_identity(self) -> None:
        instance_json = ROOT / "tmp" / "act-dev-1a2b3c4d5e6f" / "actor.json"
        record = RuntimeActorRecord(
            actor_id="  act-dev-1a2b3c4d5e6f  ",
            role_id="  dev  ",
            instance_json=instance_json,
            payload={
                "actor_id": "payload-is-not-the-api",
                "role": "payload-is-not-the-api",
                "workspace_dir": str(ROOT),
            },
        )

        profile = resolve_actor_profile(record)

        self.assertEqual(profile.actor_id, "act-dev-1a2b3c4d5e6f")
        self.assertEqual(profile.role_id, "dev")
        self.assertEqual(profile.active_actor, Actor(actor_id="act-dev-1a2b3c4d5e6f", role_id="dev"))
        self.assertEqual(profile.active_role, Role(role_id="dev"))
        self.assertEqual(profile.actor_address, ActorAddress("act-dev-1a2b3c4d5e6f", "dev"))
        self.assertEqual(profile.active_actor.actor_id, profile.actor_address.actor_id)
        self.assertEqual(profile.active_actor.role_id, profile.actor_address.role_id)
        self.assertIsInstance(profile.auth_subject, AuthSubject)
        self.assertEqual(profile.auth_subject.role_id, "dev")
        self.assertEqual(profile.actor_record.actor_id, "act-dev-1a2b3c4d5e6f")
        self.assertEqual(profile.actor_record.role_id, "dev")
        self.assertEqual(profile.actor_record.instance_json, instance_json)
        self.assertEqual(profile.actor_record.payload["workspace_dir"], str(ROOT))
        for runtime_fact in ("endpoint", "heartbeat", "presence", "status", "routing", "delivery_status", "message"):
            self.assertFalse(hasattr(profile, runtime_fact), msg=runtime_fact)

    def test_actor_profile_rejects_missing_local_identity(self) -> None:
        cases = (
            ("", "dev", "actor_id"),
            ("   ", "dev", "actor_id"),
            ("act-dev-1a2b3c4d5e6f", "", "role_id"),
            ("act-dev-1a2b3c4d5e6f", "   ", "role_id"),
        )
        for actor_id, role_id, field in cases:
            with self.subTest(field=field):
                record = RuntimeActorRecord(
                    actor_id=actor_id,
                    role_id=role_id,
                    instance_json=ROOT / "tmp" / "actor.json",
                    payload={},
                )
                with self.assertRaisesRegex(ValueError, field):
                    resolve_actor_profile(record)

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
            active_actor=Actor(actor_id="act-dev-1de000000001", role_id="dev"),
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
        self.assertEqual(response.get("active_actor"), {"actor_id": "act-dev-1de000000001", "role_id": "dev"})
        self.assertEqual(response.get("allowed_roles"), ["pm"])
        self.assertIs(response.get("state_changed"), False)
        self.assertEqual(response.get("durability"), "none")

    def test_tool_context_can_be_constructed_from_actor_profile(self) -> None:
        instance_json = ROOT / "tmp" / "act-dev-1a2b3c4d5e6f" / "actor.json"
        profile = resolve_actor_profile(
            RuntimeActorRecord(
                actor_id="act-dev-1a2b3c4d5e6f",
                role_id="dev",
                instance_json=instance_json,
                payload={"actor_id": "act-dev-1a2b3c4d5e6f", "role": "dev", "workspace_dir": str(ROOT)},
            )
        )
        manifest = {"roles": [{"id": "dev"}, {"id": "pm"}]}

        context = ToolContext.from_actor_profile(
            actor_profile=profile,
            instance_json=instance_json,
            instance_payload=dict(profile.actor_record.payload),
            manifest=manifest,
            manifest_path=None,
        )

        self.assertEqual(context.active_actor, Actor(actor_id="act-dev-1a2b3c4d5e6f", role_id="dev"))
        self.assertEqual(context.active_role, Role(role_id="dev"))
        self.assertEqual(context.actor_id, "act-dev-1a2b3c4d5e6f")
        self.assertEqual(context.role_id, "dev")
        self.assertEqual(context.actor_address, ActorAddress("act-dev-1a2b3c4d5e6f", "dev"))
        self.assertEqual(context.auth_subject, AuthSubject(role_id="dev"))
        self.assertEqual(context["active_actor"], {"actor_id": "act-dev-1a2b3c4d5e6f", "role_id": "dev"})
        self.assertEqual(context["active_role"], "dev")
        self.assertEqual(context["actor_id"], "act-dev-1a2b3c4d5e6f")
        self.assertEqual(context["role_id"], "dev")
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

    def test_actor_private_file_summaries_are_actor_owned(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace_dir = Path(temp)
            instance_json = workspace_dir / "instance.json"
            actor = {"actor_id": "act-dev-private-summary", "role_id": "dev"}
            profile = resolve_actor_profile(
                RuntimeActorRecord(
                    actor_id=actor["actor_id"],
                    role_id=actor["role_id"],
                    instance_json=instance_json,
                    payload={"actor_id": actor["actor_id"], "role": actor["role_id"], "workspace_dir": str(workspace_dir)},
                )
            )
            context = ToolContext.from_actor_profile(
                actor_profile=profile,
                instance_json=instance_json,
                instance_payload=dict(profile.actor_record.payload),
                manifest={"roles": [{"id": "dev"}, {"id": "pm"}]},
                manifest_path=None,
            )

            context.actor_private.write_file("notes/private.txt", content="private")
            rows = context.actor_private.list_files(recursive=True)

            self.assertEqual(len(rows), 1, msg=rows)
            self.assertEqual(rows[0].get("owner_actor"), actor)
            self.assertEqual(rows[0].get("visibility"), "active_actor_private")
            retired_field = "private" + "_to_role"
            self.assertNotIn(retired_field, rows[0])

    def test_tool_context_daemon_access_uses_explicit_central_daemon_client(self) -> None:
        instance_json = ROOT / "tmp" / "act-design-daemon" / "actor.json"
        profile = resolve_actor_profile(
            RuntimeActorRecord(
                actor_id="act-design-daemon",
                role_id="design",
                instance_json=instance_json,
                payload={"actor_id": "act-design-daemon", "role": "design", "workspace_dir": str(ROOT)},
            )
        )
        context = ToolContext.from_actor_profile(
            actor_profile=profile,
            instance_json=instance_json,
            instance_payload=dict(profile.actor_record.payload),
            manifest={"roles": [{"id": "design"}, {"id": "dev"}]},
            manifest_path=None,
        )
        calls: list[tuple[str, dict[str, object]]] = []

        original_list_contacts = runtime_context.daemon_client.list_contacts
        original_check_reachability = runtime_context.daemon_client.check_reachability
        original_deliver_signal = runtime_context.daemon_client.deliver_signal

        def fake_list_contacts(*, role_id: str | None = None) -> dict[str, object]:
            calls.append(("contacts", {"role_id": role_id}))
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

            context.daemon.list_contacts(role_id="dev")
            context.daemon.check_reachability(
                target_actor_address={"actor_id": "act-dev-daemon", "role_id": "dev"}
            )
            context.daemon.deliver_message_available(
                message_id="msg-123",
                target_actor_address=ActorAddress("act-dev-daemon", "dev"),
            )
        finally:
            runtime_context.daemon_client.list_contacts = original_list_contacts
            runtime_context.daemon_client.check_reachability = original_check_reachability
            runtime_context.daemon_client.deliver_signal = original_deliver_signal

        self.assertEqual(calls[0], ("contacts", {"role_id": "dev"}))
        self.assertEqual(
            calls[1],
            (
                "reachability",
                {"target_actor_address": {"actor_id": "act-dev-daemon", "role_id": "dev"}},
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
                "source_actor_address": {"actor_id": "act-design-daemon", "role_id": "design"},
                "target_actor_address": {"actor_id": "act-dev-daemon", "role_id": "dev"},
                "payload": {"message_id": "msg-123"},
            },
        )
        self.assertRegex(signal["signal_id"], r"^sig-")
        self.assertIsInstance(signal["created_at"], str)
        self.assertNotIn("message_id", signal)
        self.assertNotIn("to_role", signal)
        self.assertNotIn("content", signal)

    def test_runtime_boundary_ownership_is_searchable(self) -> None:
        self.assertFalse(hasattr(tool_registry, "_role_auth_rejection"))
        registry_text = (ROOT / "scripts" / "env" / "tool_runtime" / "registry.py").read_text(encoding="utf-8")
        self.assertNotIn("E_TOOL_ROLE_AUTH", registry_text)

        violations: list[str] = []
        tools_root = ROOT / "scripts" / "env" / "tools"
        for path in sorted(tools_root.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            if "env.tool_runtime.actor_profile" in text or "ActorProfile" in text:
                violations.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
