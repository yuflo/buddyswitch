#!/usr/bin/env python3
"""Central role-action authorization contract tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402
from env.tool_runtime import registry as tool_registry  # noqa: E402
from env.tool_runtime import role_auth  # noqa: E402
from env.tool_runtime.actor_profile import AuthSubject  # noqa: E402


class RoleActionAuthPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        self.roles = frozenset(
            role["id"] for role in self.manifest.get("roles", []) if isinstance(role, dict)
        )
        self.operation_semantics = tool_registry.operation_semantics()

    def _subject(self, role: str) -> AuthSubject:
        return AuthSubject(role_id=role)

    def test_manifest_roles_are_runtime_roles(self) -> None:
        self.assertEqual(self.roles, role_auth.manifest_role_ids(self.manifest))
        self.assertEqual(self.roles, frozenset({"market", "pm", "design", "dev", "test"}))

    def test_policy_covers_every_registered_action_permission(self) -> None:
        for action_id, semantics in self.operation_semantics.items():
            required_permission = semantics["required_permission"]
            with self.subTest(action=action_id, required_permission=required_permission):
                allowed_roles = role_auth.allowed_roles_for_permission(required_permission, self.manifest)
                self.assertTrue(allowed_roles)
                self.assertLessEqual(allowed_roles, self.roles)

    def test_none_permission_allows_every_manifest_role(self) -> None:
        self.assertEqual(role_auth.allowed_roles_for_permission("none", self.manifest), self.roles)
        for role in self.roles:
            decision = role_auth.authorize("none", self._subject(role), self.manifest)
            with self.subTest(role=role):
                self.assertTrue(decision.allowed)
                self.assertEqual(decision.allowed_roles, tuple(sorted(self.roles)))

    def test_authorize_rejects_raw_active_role_strings(self) -> None:
        with self.assertRaises(TypeError):
            role_auth.authorize("none", "pm", self.manifest)  # type: ignore[arg-type]

    def test_pm_only_permissions_allow_only_pm(self) -> None:
        for permission in ("track.create", "track.archive", "comment.resolve"):
            with self.subTest(permission=permission):
                self.assertEqual(role_auth.allowed_roles_for_permission(permission, self.manifest), frozenset({"pm"}))
                self.assertTrue(role_auth.authorize(permission, self._subject("pm"), self.manifest).allowed)
                denied = role_auth.authorize(permission, self._subject("dev"), self.manifest)
                self.assertFalse(denied.allowed)
                self.assertEqual(denied.required_permission, permission)
                self.assertEqual(denied.active_role, "dev")
                self.assertEqual(denied.allowed_roles, ("pm",))

    def test_common_permissions_allow_every_manifest_role(self) -> None:
        for permission in (
            "artifact.create",
            "evidence.approve",
            "track.add_proof",
            "message.conversation",
            "message.get",
            "message.mark",
        ):
            with self.subTest(permission=permission):
                self.assertEqual(role_auth.allowed_roles_for_permission(permission, self.manifest), self.roles)

    def test_unknown_active_role_is_denied(self) -> None:
        decision = role_auth.authorize("track.read", self._subject("ghost"), self.manifest)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.required_permission, "track.read")
        self.assertEqual(decision.active_role, "ghost")
        self.assertEqual(decision.allowed_roles, tuple(sorted(self.roles)))
        self.assertIn("unknown role", decision.reason)

    def test_unknown_permission_is_denied_with_policy_metadata(self) -> None:
        decision = role_auth.authorize("unknown.permission", self._subject("pm"), self.manifest)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.required_permission, "unknown.permission")
        self.assertEqual(decision.active_role, "pm")
        self.assertEqual(decision.allowed_roles, ())
        self.assertIn("not covered", decision.reason)

    def test_role_action_summary_returns_runtime_policy_preview_shape(self) -> None:
        summary = role_auth.role_action_summary(self._subject("market"), self.manifest, self.operation_semantics)
        old_keys = (
            "role_" + "authority_" + "source",
            "allowed_" + "actions",
            "denied_" + "actions",
            "denied_" + "action_" + "details",
            "allowed_" + "action_" + "permissions",
        )
        self.assertEqual(summary.get("active_role"), "market")
        self.assertEqual(summary.get("source"), "env.tool role-action policy")
        self.assertIs(summary.get("not_authorization_boundary"), True)
        self.assertIs(summary.get("not_execution_result"), True)
        self.assertIsInstance(summary.get("available_actions"), list, msg=summary)
        self.assertIsInstance(summary.get("restricted_actions"), list, msg=summary)
        self.assertIsInstance(summary.get("restricted_action_details"), dict, msg=summary)
        for old_key in old_keys:
            self.assertNotIn(old_key, summary)
        self.assertIn("track.list", summary["available_actions"])
        self.assertIn("artifact.create_revision", summary["available_actions"])
        self.assertIn("message.send", summary["available_actions"])
        self.assertIn("track.create", summary["restricted_actions"])
        self.assertIn("track.archive", summary["restricted_actions"])
        self.assertIn("comment.resolve", summary["restricted_actions"])
        details = summary["restricted_action_details"]
        self.assertEqual(details.get("track.create", {}).get("required_permission"), "track.create")
        self.assertEqual(details.get("track.create", {}).get("restricted_to_roles"), ["pm"])

    def test_pm_preview_has_no_pm_only_restricted_actions(self) -> None:
        summary = role_auth.role_action_summary(self._subject("pm"), self.manifest, self.operation_semantics)
        self.assertNotIn("track.create", summary["restricted_actions"])
        self.assertNotIn("track.archive", summary["restricted_actions"])
        self.assertNotIn("comment.resolve", summary["restricted_actions"])
        self.assertIn("track.create", summary["available_actions"])
        self.assertIn("track.archive", summary["available_actions"])
        self.assertIn("comment.resolve", summary["available_actions"])


if __name__ == "__main__":
    unittest.main()
