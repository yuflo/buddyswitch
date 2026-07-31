"""Track module owner-actor collaboration tests."""

from __future__ import annotations

import json
import sys
import unittest
import uuid
from pathlib import Path

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT

from buddyswitch.env.repos import runtime_files
from buddyswitch.modules.artifact.private.state import artifacts as artifact_repo
from buddyswitch.modules.track.private.state import track_comments as track_comment_repo
from buddyswitch.modules.track.private.state import tracks as track_repo
from tests.support import object_builders
import buddyswitch.runtime_kernel.broker as runtime_broker  # noqa: E402
from buddyswitch.modules.track.private.adapters.tool.tool import DEFINITION as TRACK_DEFINITION  # noqa: E402
from tests.support.runtime import RuntimeWorkspaceTestCase  # noqa: E402

MANIFEST = ROOT / "src" / "buddyswitch" / "catalog" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"
ALL_ROLES = ("pm", "design", "dev", "market", "test")
OLD_TRACK_FIELDS = ("owner_role", "created_by_actor", "health", "appetite")


class TrackOwnerActorModelTests(RuntimeWorkspaceTestCase):
    def _instance_json(self, *, actor_id: str, role: str, status: str = "active") -> Path:
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        instance_root = self._instance_root(actor_id)
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        path = instance_root / "instance.json"
        path.write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": role,
                    "status": status,
                    "instance_root": str(instance_root),
                    "workspace_dir": str(workspace_dir),
                    "browser_port": None,
                    "updated_at": "2026-06-11T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self._seed_active_task_for_instance(
            instance_json=path,
            role=role,
            actor_id=actor_id,
            task_slug=f"{role}-track-owner-actor",
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
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        request = {
            "protocol": PROTOCOL,
            "request_id": f"req-track-owner-{uuid.uuid4().hex}",
            "method": "env.tool",
            "params": {
                "actor_id": actor_id,
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

    def _create_track(self, *, role: str, actor_id: str, track_id: str) -> tuple[Path, dict[str, object]]:
        instance_json = self._instance_json(actor_id=actor_id, role=role)
        created = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_id,
            role=role,
            tool="track",
            action="create",
            args={
                "track_id": track_id,
                "title": f"Track {track_id}",
                "outcome": "Owner actor collaboration outcome",
                "now": {"next": "start collaboration", "blocker": None},
            },
        )
        return instance_json, created

    def _create_draft(self, *, instance_json: Path, actor_id: str, role: str, artifact_id: str) -> dict[str, object]:
        return self._dispatch(
            instance_json=instance_json,
            actor_id=actor_id,
            role=role,
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": artifact_id,
                "title": artifact_id,
                "summary": "proof body",
                "template": "proof",
                "body": "proof body",
            },
        )

    def test_track_definition_exposes_owner_identity_surface_only(self) -> None:
        action_names = [row.name for row in TRACK_DEFINITION.actions]
        self.assertEqual(
            action_names,
            [
                "create",
                "list",
                "open",
                "add_comment",
                "list_comments",
                "resolve_comment_thread",
                "update_requirements",
                "update_status",
                "add_material",
                "add_update",
                "add_proof",
                "archive",
            ],
        )
        self.assertNotIn("update_now", action_names)

        by_name = {row.name: row for row in TRACK_DEFINITION.actions}
        create_schema = by_name["create"].input_schema
        self.assertEqual(create_schema["required"], ["track_id", "title", "outcome", "now"])
        for old_field in OLD_TRACK_FIELDS:
            self.assertNotIn(old_field, create_schema["properties"])
        self.assertNotIn("state", create_schema["properties"])

        state_filter = by_name["list"].input_schema["properties"]["state"]
        self.assertEqual(state_filter["enum"], ["active", "blocked", "done"])
        update_kind = by_name["add_update"].input_schema["properties"]["kind"]
        self.assertEqual(update_kind["enum"], ["progress", "decision", "blocker"])

    def test_every_role_can_create_track_owned_by_active_actor(self) -> None:
        for role in ALL_ROLES:
            actor_label = f"act-{role}-owner-create"
            track_id = f"track-owner-create-{role}"
            with self.subTest(role=role):
                _, created = self._create_track(role=role, actor_id=actor_label, track_id=track_id)
                self.assertTrue(created.get("ok"), msg=created)
                track = created.get("track")
                self.assertIsInstance(track, dict, msg=created)
                assert isinstance(track, dict)
                self.assertEqual(track.get("owner_identity_id"), self._runtime_actor_id(role=role, label=actor_label))
                self.assertNotIn("owner_actor", track)
                self.assertEqual(track.get("state"), "active")
                self.assertEqual(track.get("now"), {"next": "start collaboration", "blocker": None})
                self.assertEqual(track.get("acceptance_criteria"), [])
                self.assertEqual(track.get("non_goals"), [])
                for old_field in OLD_TRACK_FIELDS:
                    self.assertNotIn(old_field, track)

    def test_non_owner_cannot_mutate_requirement_status_archive_or_resolve(self) -> None:
        owner_instance, created = self._create_track(role="dev", actor_id="act-dev-owner", track_id="track-owner-auth")
        self.assertTrue(created.get("ok"), msg=created)

        comment = self._dispatch(
            instance_json=owner_instance,
            actor_id="act-dev-owner",
            role="dev",
            tool="track",
            action="add_comment",
            args={"track_id": "track-owner-auth", "content": "Open point"},
        )
        self.assertTrue(comment.get("ok"), msg=comment)
        comment_id = str(comment.get("comment_id"))

        market_instance = self._instance_json(actor_id="act-market-non-owner", role="market")
        for action, args in (
            ("update_requirements", {"track_id": "track-owner-auth", "title": "Non-owner title"}),
            (
                "update_status",
                {
                    "track_id": "track-owner-auth",
                    "state": "blocked",
                    "now": {"next": "wait", "blocker": "Need owner"},
                },
            ),
            ("archive", {"track_id": "track-owner-auth"}),
            (
                "resolve_comment_thread",
                {
                    "track_id": "track-owner-auth",
                    "comment_id": comment_id,
                    "resolution_summary": "Non-owner closure",
                },
            ),
        ):
            with self.subTest(action=action):
                rejected = self._dispatch(
                    instance_json=market_instance,
                    actor_id="act-market-non-owner",
                    role="market",
                    tool="track",
                    action=action,
                    args=args,
                )
                self.assertFalse(rejected.get("ok"), msg=rejected)
                self.assertEqual((rejected.get("error") or {}).get("code"), "E_TRACK_AUTHORITY")
                self.assertIs(rejected.get("state_changed"), False)

        owner_update = self._dispatch(
            instance_json=owner_instance,
            actor_id="act-dev-owner",
            role="dev",
            tool="track",
            action="update_requirements",
            args={
                "track_id": "track-owner-auth",
                "title": "Owner title",
                "outcome": "Owner outcome",
                "acceptance_criteria": ["proof exists"],
                "non_goals": ["compatibility alias"],
            },
        )
        self.assertTrue(owner_update.get("ok"), msg=owner_update)
        track = owner_update.get("track")
        self.assertIsInstance(track, dict, msg=owner_update)
        assert isinstance(track, dict)
        self.assertEqual(track.get("title"), "Owner title")
        self.assertEqual(track.get("acceptance_criteria"), ["proof exists"])
        self.assertEqual(track.get("non_goals"), ["compatibility alias"])

    def test_status_invariants_and_proof_acceptance_are_owner_only(self) -> None:
        owner_instance, created = self._create_track(role="test", actor_id="act-test-owner", track_id="track-status-proof")
        self.assertTrue(created.get("ok"), msg=created)

        blocked_without_blocker = self._dispatch(
            instance_json=owner_instance,
            actor_id="act-test-owner",
            role="test",
            tool="track",
            action="update_status",
            args={
                "track_id": "track-status-proof",
                "state": "blocked",
                "now": {"next": "wait", "blocker": None},
            },
        )
        self.assertFalse(blocked_without_blocker.get("ok"), msg=blocked_without_blocker)
        self.assertIs(blocked_without_blocker.get("state_changed"), False)

        done_without_proof = self._dispatch(
            instance_json=owner_instance,
            actor_id="act-test-owner",
            role="test",
            tool="track",
            action="update_status",
            args={
                "track_id": "track-status-proof",
                "state": "done",
                "now": {"next": "ship", "blocker": None},
            },
        )
        self.assertFalse(done_without_proof.get("ok"), msg=done_without_proof)
        self.assertIs(done_without_proof.get("state_changed"), False)

        blocker_update = self._dispatch(
            instance_json=owner_instance,
            actor_id="act-test-owner",
            role="test",
            tool="track",
            action="add_update",
            args={"track_id": "track-status-proof", "kind": "blocker", "summary": "Blocked by missing proof"},
        )
        self.assertTrue(blocker_update.get("ok"), msg=blocker_update)
        track = track_repo.get_track("track-status-proof")
        self.assertIsInstance(track, dict)
        assert isinstance(track, dict)
        self.assertEqual(track.get("state"), "active")

        proof_kind = self._dispatch(
            instance_json=owner_instance,
            actor_id="act-test-owner",
            role="test",
            tool="track",
            action="add_update",
            args={"track_id": "track-status-proof", "kind": "proof", "summary": "old proof path"},
        )
        self.assertFalse(proof_kind.get("ok"), msg=proof_kind)
        self.assertIs(proof_kind.get("state_changed"), False)

        draft = self._create_draft(
            instance_json=owner_instance,
            actor_id="act-test-owner",
            role="test",
            artifact_id="art-status-proof-r1",
        )
        self.assertTrue(draft.get("ok"), msg=draft)
        before_proof = track_repo.get_track("track-status-proof")
        self.assertIsInstance(before_proof, dict)
        assert isinstance(before_proof, dict)
        before_update_count = len([row for row in before_proof.get("updates", []) if isinstance(row, dict)])

        proof = self._dispatch(
            instance_json=owner_instance,
            actor_id="act-test-owner",
            role="test",
            tool="track",
            action="add_proof",
            args={
                "track_id": "track-status-proof",
                "artifact_id": "art-status-proof-r1",
                "label": "Verification",
                "summary": "Proof exists",
            },
        )
        self.assertTrue(proof.get("ok"), msg=proof)
        after_proof = track_repo.get_track("track-status-proof")
        self.assertIsInstance(after_proof, dict)
        assert isinstance(after_proof, dict)
        self.assertEqual(after_proof.get("state"), "active")
        self.assertEqual(
            len([row for row in after_proof.get("updates", []) if isinstance(row, dict)]),
            before_update_count,
        )

        done = self._dispatch(
            instance_json=owner_instance,
            actor_id="act-test-owner",
            role="test",
            tool="track",
            action="update_status",
            args={
                "track_id": "track-status-proof",
                "state": "done",
                "now": {"next": "ship", "blocker": None},
            },
        )
        self.assertTrue(done.get("ok"), msg=done)
        track = done.get("track")
        self.assertIsInstance(track, dict, msg=done)
        assert isinstance(track, dict)
        self.assertEqual(track.get("state"), "done")
        self.assertEqual(track.get("now"), {"next": "ship", "blocker": None})
