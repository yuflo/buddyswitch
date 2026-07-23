"""Product ownership identity persistence tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
SCRIPTS = ROOT / "scripts"

from env.repos import artifacts as artifact_repo  # noqa: E402
from env.domain import task_sys  # noqa: E402
from env.repos import track_comments as comment_repo  # noqa: E402
from env.repos import tracks as track_repo  # noqa: E402
from tests.support.runtime import RuntimeWorkspaceTestCase  # noqa: E402


class ProductOwnershipIdentityTests(RuntimeWorkspaceTestCase):
    def _actor(self, role: str = "dev", actor_id: str = "act-dev-owner") -> dict[str, str]:
        return {"role_id": role, "actor_id": self._runtime_actor_id(role=role, label=actor_id)}

    def _task_instance_payload(self, actor: dict[str, str]) -> dict[str, object]:
        instance_root = self.runtime_root / "instances" / actor["actor_id"]
        workspace = instance_root / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        return {
            "actor_id": actor["actor_id"],
            "role": actor["role_id"],
            "instance_root": str(instance_root),
            "workspace_dir": str(workspace),
        }

    def test_track_new_writes_persist_owner_and_update_identity_ids(self) -> None:
        actor = self._actor()

        created = track_repo.create_track(
            "track-identity-owner",
            "Identity-owned Track",
            owner_identity=actor["actor_id"],
            outcome="Prove identity ownership.",
            now={"next": "Write the test.", "blocker": None},
        )
        updated, _row = track_repo.append_track_update(
            track_id="track-identity-owner",
            by_identity=actor["actor_id"],
            kind="progress",
            summary="Identity update.",
            refs=[],
        )

        self.assertEqual(created["owner_identity_id"], actor["actor_id"])
        self.assertNotIn("owner_actor", created)
        self.assertEqual(updated["updates"][0]["by_identity_id"], actor["actor_id"])
        self.assertNotIn("by_actor", updated["updates"][0])

    def test_task_new_writes_persist_owner_identity_id(self) -> None:
        actor = self._actor(role="pm", actor_id="act-pm-task-owner")

        result = task_sys.create(
            actor_target={"actor_id": actor["actor_id"], "role_id": actor["role_id"]},
            demand_ref={
                "demand_id": "demand-identity-owned-task",
                "basis_revision": 1,
                "demand_ref": "dref-identity-owned-task",
            },
            objective="Verify Task ownership uses the actor identity route.",
            selection_reason="The identity-owned fixture Demand is selected.",
        )
        task = result["task"]

        self.assertEqual(task["actor_target"]["actor_id"], actor["actor_id"])
        self.assertEqual(task["actor_target"]["role_id"], actor["role_id"])
        self.assertNotIn("owner_actor", task)

    def test_artifact_new_writes_persist_creator_and_author_identity_ids(self) -> None:
        creator = self._actor(role="design", actor_id="act-design-artifact-owner")
        coauthor = self._actor(role="pm", actor_id="act-pm-artifact-author")

        artifact = artifact_repo.create_artifact_revision(
            artifact_id="art-identity-owner",
            title="Identity artifact",
            created_by_identity=creator["actor_id"],
            body="Artifact body.",
            template="note",
            summary="Artifact summary.",
            author_identities=[coauthor["actor_id"]],
        )

        self.assertEqual(artifact["created_by_identity_id"], creator["actor_id"])
        self.assertEqual(artifact["author_identity_ids"], [creator["actor_id"], coauthor["actor_id"]])
        self.assertNotIn("created_by_actor", artifact)
        self.assertNotIn("author_actors", artifact)

    def test_track_comment_new_writes_persist_author_mention_and_resolution_identity_ids(self) -> None:
        author = self._actor(role="dev", actor_id="act-dev-comment-author")
        mentioned = self._actor(role="pm", actor_id="act-pm-comment-mentioned")
        resolver = self._actor(role="test", actor_id="act-test-comment-resolver")

        comment = comment_repo.create_track_comment(
            track_id="track-comment-identity",
            by_identity=author["actor_id"],
            content="Identity comment.",
            mentioned_identities=[mentioned["actor_id"]],
        )
        resolved = comment_repo.resolve_track_comment_thread(
            track_id="track-comment-identity",
            comment_id=comment["id"],
            resolved_by_identity=resolver["actor_id"],
            resolution_summary="Resolved by identity.",
        )[0]

        self.assertEqual(comment["by_identity_id"], author["actor_id"])
        self.assertEqual(comment["mentioned_identity_ids"], [mentioned["actor_id"]])
        self.assertNotIn("by_actor", comment)
        self.assertNotIn("mentioned_actors", comment)
        self.assertEqual(resolved["resolved_by_identity_id"], resolver["actor_id"])
        self.assertNotIn("resolved_by_actor", resolved)
