"""Application Role authority contract tests."""

from __future__ import annotations

import unittest

from buddyswitch.application.build import activate_application
from buddyswitch.foundation.tool_runtime import registry as tool_registry


class RoleActionAuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.application = activate_application()
        self.authority = self.application.role_authority
        self.roles = self.application.role_host.valid_role_ids
        self.operation_semantics = tool_registry.operation_semantics()

    def _allowed_roles(self, required_permission: str) -> frozenset[str]:
        return frozenset(
            role
            for role in self.roles
            if self.authority.authorize(required_permission, role).allowed
        )

    def test_role_host_roles_are_the_only_runtime_roles(self) -> None:
        self.assertTrue(self.roles)
        self.assertEqual(self.authority.role_ids, self.roles)

    def test_every_registered_permission_allows_every_known_role(self) -> None:
        for action_id, semantics in self.operation_semantics.items():
            required_permission = semantics["required_permission"]
            with self.subTest(action=action_id, required_permission=required_permission):
                self.assertEqual(self._allowed_roles(required_permission), self.roles)

    def test_unknown_active_role_is_denied(self) -> None:
        decision = self.authority.authorize("track.read", "ghost")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.allowed_roles, tuple(sorted(self.roles)))
        self.assertIn("unknown", decision.reason)

    def test_unknown_permission_is_denied_without_a_fallback(self) -> None:
        decision = self.authority.authorize(
            "unknown.permission",
            min(self.roles),
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.allowed_roles, ())
        self.assertIn("not declared", decision.reason)

    def test_authorize_rejects_non_string_role_ids(self) -> None:
        with self.assertRaises(TypeError):
            self.authority.authorize("none", {"role_id": "pm"})  # type: ignore[arg-type]

    def test_role_action_summary_projects_the_configured_authority(self) -> None:
        selected_role = min(self.roles)
        summary = tool_registry.role_action_summary(selected_role)
        self.assertEqual(summary["active_role"], selected_role)
        self.assertEqual(summary["source"], "Application RoleHost + Tool registrations")
        self.assertEqual(summary["restricted_actions"], [])
        self.assertEqual(summary["restricted_action_details"], {})
        self.assertIn("track.list", summary["available_actions"])
        self.assertIn("artifact.create_revision", summary["available_actions"])


if __name__ == "__main__":
    unittest.main()
