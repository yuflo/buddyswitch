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
from env.tool_runtime import registry as tool_registry  # noqa: E402
from env.tool_runtime.actor_profile import AuthSubject  # noqa: E402
from env.tool_runtime.actor_profile import RuntimeInstanceRecord  # noqa: E402
from env.tool_runtime.actor_profile import resolve_runtime_actor_profile  # noqa: E402
from env.tool_runtime.context import ToolContext  # noqa: E402
from env.tool_runtime.role_auth import AuthDecision  # noqa: E402


class RuntimeActorProfileTests(unittest.TestCase):
    def test_actor_profile_normalizes_trusted_runtime_identity(self) -> None:
        instance_json = ROOT / "tmp" / "inst-dev" / "instance.json"
        record = RuntimeInstanceRecord(
            instance_id="  inst-dev  ",
            buddy_id="  dev  ",
            instance_json=instance_json,
            payload={
                "instance_id": "payload-is-not-the-api",
                "buddy": "payload-is-not-the-api",
                "workspace_dir": str(ROOT),
            },
        )

        profile = resolve_runtime_actor_profile(record)

        self.assertEqual(profile.instance_id, "inst-dev")
        self.assertEqual(profile.active_buddy, "dev")
        self.assertIsInstance(profile.auth_subject, AuthSubject)
        self.assertEqual(profile.auth_subject.role_id, "dev")
        self.assertEqual(profile.instance_record.instance_id, "inst-dev")
        self.assertEqual(profile.instance_record.buddy_id, "dev")
        self.assertEqual(profile.instance_record.instance_json, instance_json)
        self.assertEqual(profile.instance_record.payload["workspace_dir"], str(ROOT))

    def test_actor_profile_rejects_missing_local_identity(self) -> None:
        cases = (
            ("", "dev", "instance_id"),
            ("   ", "dev", "instance_id"),
            ("inst-dev", "", "buddy_id"),
            ("inst-dev", "   ", "buddy_id"),
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
        instance_json = ROOT / "tmp" / "inst-dev" / "instance.json"
        profile = resolve_runtime_actor_profile(
            RuntimeInstanceRecord(
                instance_id="inst-dev",
                buddy_id="dev",
                instance_json=instance_json,
                payload={"instance_id": "inst-dev", "buddy": "dev", "workspace_dir": str(ROOT)},
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
        self.assertEqual(context.instance_id, "inst-dev")
        self.assertEqual(context.auth_subject, AuthSubject(role_id="dev"))
        self.assertEqual(context["active_buddy"], "dev")
        self.assertEqual(context["instance_id"], "inst-dev")
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
