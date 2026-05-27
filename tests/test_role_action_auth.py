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


class RoleActionAuthPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        self.roles = frozenset(
            buddy["id"] for buddy in self.manifest.get("buddies", []) if isinstance(buddy, dict)
        )
        self.operation_semantics = tool_registry.operation_semantics()

    def test_manifest_buddy_ids_are_runtime_roles(self) -> None:
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
            decision = role_auth.authorize("none", role, self.manifest)
            with self.subTest(role=role):
                self.assertTrue(decision.allowed)
                self.assertEqual(decision.allowed_roles, tuple(sorted(self.roles)))

    def test_pm_only_permissions_allow_only_pm(self) -> None:
        for permission in ("track.create", "track.archive", "comment.resolve"):
            with self.subTest(permission=permission):
                self.assertEqual(role_auth.allowed_roles_for_permission(permission, self.manifest), frozenset({"pm"}))
                self.assertTrue(role_auth.authorize(permission, "pm", self.manifest).allowed)
                denied = role_auth.authorize(permission, "dev", self.manifest)
                self.assertFalse(denied.allowed)
                self.assertEqual(denied.required_permission, permission)
                self.assertEqual(denied.active_role, "dev")
                self.assertEqual(denied.allowed_roles, ("pm",))

    def test_common_permissions_allow_every_manifest_role(self) -> None:
        for permission in ("request.accept", "artifact.create", "evidence.approve", "track.add_proof"):
            with self.subTest(permission=permission):
                self.assertEqual(role_auth.allowed_roles_for_permission(permission, self.manifest), self.roles)

    def test_unknown_active_role_is_denied(self) -> None:
        decision = role_auth.authorize("track.read", "ghost", self.manifest)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.required_permission, "track.read")
        self.assertEqual(decision.active_role, "ghost")
        self.assertEqual(decision.allowed_roles, tuple(sorted(self.roles)))
        self.assertIn("unknown role", decision.reason)

    def test_unknown_permission_is_denied_with_policy_metadata(self) -> None:
        decision = role_auth.authorize("unknown.permission", "pm", self.manifest)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.required_permission, "unknown.permission")
        self.assertEqual(decision.active_role, "pm")
        self.assertEqual(decision.allowed_roles, ())
        self.assertIn("not covered", decision.reason)


if __name__ == "__main__":
    unittest.main()
