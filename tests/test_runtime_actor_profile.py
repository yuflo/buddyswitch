"""Identity-owned env.tool runtime context tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.domain.identity import ActorIdentityProfile  # noqa: E402
from env.domain.identity import ExternalIdentityProfile  # noqa: E402
from env.domain.identity import IdentityRef  # noqa: E402
from env.domain.identity import actor_identity  # noqa: E402
from env.domain.identity import external_identity  # noqa: E402
from env.tool_runtime import context as context_module  # noqa: E402
from env.tool_runtime.context import ToolContext  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


class IdentityRuntimeTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _context(self, *, actor_id: str = "act-dev-runtime", role_id: str = "dev") -> ToolContext:
        instance_root = self.runtime_root / "instances" / actor_id
        profile = ActorIdentityProfile(
            identity=IdentityRef(id=actor_id, type="actor"),
            role_id=role_id,
            label=role_id.title(),
        )
        return ToolContext.from_identity_profile(
            actor_identity_profile=profile,
            instance_json=instance_root / "actor.json",
            instance_payload={
                "identity_id": actor_id,
                "instance_root": str(instance_root),
                "workspace_dir": str(self.runtime_root),
            },
            manifest={"roles": [{"id": role_id}, {"id": "pm"}]},
            manifest_path=None,
        )

    def test_identity_ref_serializes_stable_payload_and_validates_type(self) -> None:
        actor_ref = IdentityRef(id="  act-dev-daemon  ", type="actor")
        external_ref = IdentityRef(id="  ext-local-web  ", type="external")

        self.assertEqual(actor_ref.to_payload(), {"id": "act-dev-daemon", "type": "actor"})
        self.assertEqual(external_ref.to_payload(), {"id": "ext-local-web", "type": "external"})
        with self.assertRaisesRegex(ValueError, "actor identity id"):
            IdentityRef(id="dev-daemon", type="actor")
        with self.assertRaisesRegex(ValueError, "external identity id"):
            IdentityRef(id="web", type="external")
        with self.assertRaisesRegex(ValueError, "identity.type"):
            IdentityRef(id="act-dev-daemon", type="role")

    def test_identity_helpers_resolve_actor_and_external_profiles(self) -> None:
        actor_ref = actor_identity("  act-dev-daemon  ")
        external_ref = external_identity("  ext-local-web  ")

        self.assertEqual(actor_ref, IdentityRef(id="act-dev-daemon", type="actor"))
        self.assertEqual(external_ref, IdentityRef(id="ext-local-web", type="external"))
        self.assertEqual(
            ActorIdentityProfile(identity=actor_ref, role_id="dev").to_payload(),
            {"identity": {"id": "act-dev-daemon", "type": "actor"}, "role_id": "dev"},
        )
        self.assertEqual(
            ExternalIdentityProfile(identity=external_ref, display_name="Web").to_payload(),
            {"identity": {"id": "ext-local-web", "type": "external"}, "display_name": "Web"},
        )

    def test_tool_context_can_be_constructed_from_identity_profile(self) -> None:
        context = self._context(actor_id="act-dev-context", role_id="dev")

        self.assertEqual(context.current_identity, IdentityRef(id="act-dev-context", type="actor"))
        self.assertEqual(context.current_actor_identity_profile.role_id, "dev")
        self.assertEqual(context.role_id, "dev")
        self.assertEqual(context["current_identity"], {"id": "act-dev-context", "type": "actor"})
        self.assertEqual(context["active_role"], "dev")
        self.assertEqual(context["role_id"], "dev")
        with self.assertRaises(KeyError):
            _ = context["active" + "_actor"]
        self.assertFalse(hasattr(context, "actor_address"))

    def test_signal_delivery_derives_source_route_without_actor_address_class(self) -> None:
        context = self._context(actor_id="act-dev-route", role_id="dev")

        with mock.patch.object(context_module.daemon_client, "deliver_signal", return_value={"ok": True}) as deliver:
            context.signal_delivery.deliver_signal(
                signal_type="track.comment.added",
                target_identity_id="act-pm-route",
                target_role_id="pm",
                payload={"track_id": "track-route"},
            )

        signal = deliver.call_args.kwargs["signal"]
        self.assertEqual(signal["source_identity_id"], "act-dev-route")
        self.assertEqual(signal["source_role_id"], "dev")
        self.assertEqual(signal["target_identity_id"], "act-pm-route")
        self.assertEqual(signal["target_role_id"], "pm")

    def test_actor_private_file_summaries_are_identity_owned(self) -> None:
        context = self._context(actor_id="act-dev-private-summary", role_id="dev")

        context.actor_private.write_file("notes.md", content="private")
        summaries = context.actor_private.list_files()

        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["owner_identity"], {"id": "act-dev-private-summary", "type": "actor"})
        self.assertNotIn("owner" + "_actor", summaries[0])
        self.assertEqual(summaries[0]["visibility"], "current_identity_private")


if __name__ == "__main__":
    unittest.main()
