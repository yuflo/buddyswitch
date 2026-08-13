"""Identity global convergence tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT

from tests.support.runtime import RuntimeWorkspaceTestCase  # noqa: E402


class IdentityGlobalConvergenceTests(RuntimeWorkspaceTestCase):
    def test_actor_identity_profile_is_the_actor_static_identity_owner(self) -> None:
        from buddyswitch.foundation.identity.model import ActorIdentityProfile
        from buddyswitch.foundation.identity.model import IdentityRef

        profile = ActorIdentityProfile.from_payload(
            {
                "identity": {"id": "act-pm-global", "type": "actor"},
                "role_id": "pm",
                "label": "PM",
                "created_at": "2026-07-04T00:00:00Z",
            }
        )

        self.assertEqual(profile.identity, IdentityRef(id="act-pm-global", type="actor"))
        self.assertEqual(profile.role_id, "pm")
        self.assertEqual(profile.label, "PM")
        self.assertEqual(profile.created_at, "2026-07-04T00:00:00Z")
        self.assertEqual(profile.to_payload()["identity"], {"id": "act-pm-global", "type": "actor"})
        self.assertEqual(profile.to_payload()["role_id"], "pm")
        self.assertNotIn("actor_id", profile.to_payload())
        self.assertNotIn("actor_address", profile.to_payload())

    def test_external_identity_profile_is_the_external_static_identity_owner(self) -> None:
        from buddyswitch.foundation.identity.model import ExternalIdentityProfile
        from buddyswitch.foundation.identity.model import IdentityRef

        profile = ExternalIdentityProfile.from_payload(
            {
                "identity": {"id": "ext-web-global", "type": "external"},
                "display_name": "Web",
                "created_at": "2026-07-04T00:00:00Z",
            }
        )

        self.assertEqual(profile.identity, IdentityRef(id="ext-web-global", type="external"))
        self.assertEqual(profile.display_name, "Web")
        self.assertEqual(profile.created_at, "2026-07-04T00:00:00Z")
        self.assertEqual(profile.to_payload()["identity"], {"id": "ext-web-global", "type": "external"})
        self.assertNotIn("external_id", profile.to_payload())

    def test_identity_helpers_reject_cross_type_ids(self) -> None:
        from buddyswitch.foundation.identity.model import actor_identity
        from buddyswitch.foundation.identity.model import external_identity

        with self.assertRaisesRegex(ValueError, "actor identity id"):
            actor_identity("ext-not-actor")
        with self.assertRaisesRegex(ValueError, "external identity id"):
            external_identity("act-not-external")

    def test_identity_domain_has_no_im_participant_adapter(self) -> None:
        import buddyswitch.foundation.identity.model as identity_model

        legacy_adapter = "identity" + "_from_im_participant"
        self.assertFalse(hasattr(identity_model, legacy_adapter))

    def test_identity_repo_persists_actor_and_external_profiles(self) -> None:
        import buddyswitch.foundation.identity.profiles as identity_profiles

        actor = identity_profiles.save_actor_identity_profile(
            {
                "identity": {"id": "act-dev-repo", "type": "actor"},
                "role_id": "dev",
                "label": "Dev",
            }
        )
        external = identity_profiles.save_external_profile(
            {
                "identity": {"id": "ext-web-repo", "type": "external"},
                "display_name": "Web",
            }
        )

        self.assertEqual(actor["identity"], {"id": "act-dev-repo", "type": "actor"})
        self.assertEqual(identity_profiles.get_actor_identity_profile("act-dev-repo")["role_id"], "dev")
        self.assertEqual([row["identity"]["id"] for row in identity_profiles.list_actor_identity_profiles()], ["act-dev-repo"])
        self.assertEqual(external["identity"], {"id": "ext-web-repo", "type": "external"})
        self.assertEqual(identity_profiles.get_external_profile("ext-web-repo")["display_name"], "Web")
        self.assertEqual([row["identity"]["id"] for row in identity_profiles.list_external_profiles()], ["ext-web-repo"])
        self.assertTrue(
            (self.runtime_state_root / "buddyswitch" / "objects" / "identities" / "actors" / "act-dev-repo.json").is_file()
        )
        self.assertTrue(
            (
                self.runtime_state_root
                / "buddyswitch"
                / "objects"
                / "identities"
                / "externals"
                / "ext-web-repo.json"
            ).is_file()
        )

    def test_tool_context_uses_identity_profile_without_actor_address(self) -> None:
        from buddyswitch.foundation.identity.model import ActorIdentityProfile
        from buddyswitch.foundation.role_host import RoleRuntime
        from buddyswitch.foundation.tool_runtime.context import ToolContext

        instance_root = self.runtime_root / "instances" / "act-dev-context"
        instance_json = instance_root / "actor.json"
        profile = ActorIdentityProfile.from_payload(
            {"identity": {"id": "act-dev-context", "type": "actor"}, "role_id": "dev", "label": "Dev"}
        )
        context = ToolContext.from_identity_profile(
            actor_identity_profile=profile,
            instance_json=instance_json,
            instance_payload={
                "identity_id": "act-dev-context",
                "instance_root": str(instance_root),
                "workspace_dir": str(self.runtime_root),
            },
            role=RoleRuntime(
                id="dev",
                artifact_templates=("brief", "note"),
                project_path="projects/app",
                source_access="write",
                browser_cockpit="available",
                search_api="available",
            ),
        )

        self.assertEqual(context.current_identity.to_payload(), {"id": "act-dev-context", "type": "actor"})
        self.assertEqual(context.current_actor_identity_profile, profile)
        self.assertEqual(context.role_id, "dev")
        self.assertEqual(context["current_identity"], {"id": "act-dev-context", "type": "actor"})
        self.assertEqual(context["active_role"], "dev")
        with self.assertRaises(KeyError):
            _ = context["active" + "_actor"]
        self.assertFalse(hasattr(context, "actor_address"))
