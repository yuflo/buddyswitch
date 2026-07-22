"""Tests for external-safe Task and Track read projections."""

from __future__ import annotations

from copy import deepcopy
import importlib
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from tests.support.runtime import RuntimeWorkspaceTestCase


from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
SCRIPTS = ROOT / "scripts"

from env.domain.identity import ActorIdentityProfile, IdentityRef  # noqa: E402
from env.domain import track_read  # noqa: E402


TASK_KEYS = ("task_id", "source_type", "demand_ref", "status", "actor", "updated_at")
TASK_ACTOR_KEYS = ("actor_id", "role_id")
TRACK_LIST_KEYS = (
    "id",
    "title",
    "outcome",
    "owner_identity_id",
    "state",
    "now",
    "acceptance_criteria",
    "non_goals",
    "updated_at",
    "comment_summary",
)
TRACK_DETAIL_KEYS = TRACK_LIST_KEYS + ("materials", "proofs", "updates", "comment_threads")


def _task_read_module() -> Any:
    try:
        return importlib.import_module("env.domain.task_read")
    except ModuleNotFoundError as exc:
        raise AssertionError("env.domain.task_read should provide external Task read projections") from exc


class ExternalQueryProjectionTests(RuntimeWorkspaceTestCase):
    def _actor_profile(self, *, actor_id: str = "act-pm-demo", role_id: str = "pm") -> ActorIdentityProfile:
        return ActorIdentityProfile(identity=IdentityRef(id=actor_id, type="actor"), role_id=role_id)

    def _task_record(
        self,
        *,
        task_id: str,
        actor_id: str = "act-pm-demo",
        role_id: str = "pm",
        updated_at: str,
        status: str = "in_progress.side_processing",
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "id": task_id,
            "source_type": "demand",
            "source_ref": {"demand_id": f"demand-{task_id}", "basis_revision": 1},
            "actor_target": {"actor_id": actor_id, "role_id": role_id, "internal_stack": "hidden"},
            "inbound_context": {"prompt": "secret prompt"},
            "status": status,
            "execution": {
                "processor": None if result is not None else "side",
                "handoff": {"side_thread_id": "thr-secret"},
                "result": result,
            },
            "events": [{"type": "created", "at": "2026-07-13T00:00:00Z", "raw_payload": {"secret": True}}],
            "runtime_instruction": {"type": "start_side"},
            "side_thread_id": "thr-secret",
            "handoff": {"parent_frame_context": {"secret": True}},
            "raw_payload": {"private": True},
            "repo_path": "/Users/private/worktree",
            "internal_stack": ["traceback"],
            "created_at": "2026-07-13T00:00:00Z",
            "updated_at": updated_at,
        }

    def _track_record(
        self,
        *,
        track_id: str,
        owner_identity_id: str = "act-pm-demo",
        updated_at: str,
        archived_at: str | None = None,
    ) -> dict[str, Any]:
        return {
            "id": track_id,
            "title": f"Track {track_id}",
            "outcome": "External track outcome.",
            "owner_identity_id": owner_identity_id,
            "state": "active",
            "now": {"next": "Keep moving.", "blocker": None},
            "acceptance_criteria": ["Exact allowlist."],
            "non_goals": ["Raw runtime data."],
            "artifact_relations": [
                {
                    "type": "artifact",
                    "relation_id": "rel-material",
                    "artifact_id": "artifact-material",
                    "role": "material",
                    "label": "Brief",
                    "template": "markdown",
                    "from_identity_id": owner_identity_id,
                    "summary": "Material summary.",
                    "current": True,
                    "created_at": "2026-07-13T10:00:00Z",
                },
                {
                    "type": "artifact",
                    "relation_id": "rel-proof",
                    "artifact_id": "artifact-proof",
                    "role": "proof",
                    "label": "Proof",
                    "template": "markdown",
                    "from_identity_id": owner_identity_id,
                    "summary": "Proof summary.",
                    "current": True,
                    "created_at": "2026-07-13T10:05:00Z",
                },
            ],
            "updates": [
                {
                    "id": "upd-track",
                    "by_identity_id": owner_identity_id,
                    "summary": "Update summary.",
                    "kind": "progress",
                    "refs": [{"type": "artifact", "id": "artifact-proof"}],
                    "created_at": "2026-07-13T10:10:00Z",
                }
            ],
            "execution": {"processor": "side"},
            "raw_payload": {"private": True},
            "repo_path": "/Users/private/worktree",
            "internal_stack": ["traceback"],
            "created_at": "2026-07-13T09:00:00Z",
            "updated_at": updated_at,
            "archived_at": archived_at,
        }

    def _comments(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "comment-root",
                "track_id": "track-alpha",
                "thread_id": "thread-open",
                "by_identity_id": "act-dev-demo",
                "content": "Open comment.",
                "reply_to": None,
                "mentioned_identity_ids": ["act-pm-demo"],
                "status": "open",
                "created_at": "2026-07-13T10:11:00Z",
                "resolved_by_identity_id": None,
                "resolved_at": None,
                "resolution_summary": None,
                "raw_payload": {"private": True},
            }
        ]

    def test_task_external_actor_projection_filters_sorts_and_allowlists_exact_keys(self) -> None:
        task_read = _task_read_module()
        actor_id = "act-pm-demo"
        records = [
            self._task_record(task_id="task-old", updated_at="2026-07-13T10:00:00Z"),
            self._task_record(
                task_id="task-completed",
                updated_at="2026-07-13T13:00:00Z",
                status="completed",
            ),
            self._task_record(
                task_id="task-canceled",
                updated_at="2026-07-13T12:00:00Z",
                status="canceled",
            ),
            self._task_record(
                task_id="task-other-actor",
                actor_id="act-dev-demo",
                role_id="dev",
                updated_at="2026-07-13T14:00:00Z",
                status="completed",
            ),
            self._task_record(
                task_id="task-recoverable",
                updated_at="2026-07-13T11:00:00Z",
                result={"type": "failure", "reason": "runtime_failed", "stage": "side_input", "internal_stack": "hidden"},
            ),
        ]
        before = deepcopy(records)

        with mock.patch.object(task_read.task_sys, "list_tasks", return_value=records) as list_tasks:
            projection = task_read.actor_external_task_projection(actor_profile=self._actor_profile(actor_id=actor_id))

        list_tasks.assert_called_once_with(actor_target={"actor_id": actor_id, "role_id": "pm"})
        self.assertEqual(
            [row["task_id"] for row in projection["tasks"]],
            ["task-completed", "task-canceled", "task-recoverable", "task-old"],
        )
        self.assertEqual(
            [row["task_id"] for row in projection["active_tasks"]],
            ["task-recoverable", "task-old"],
        )
        self.assertEqual([row["task_id"] for row in projection["recoverable_tasks"]], ["task-recoverable"])
        self.assertEqual(
            [row["task_id"] for row in projection["terminal_tasks"]],
            ["task-completed", "task-canceled"],
        )
        self.assertEqual(projection["task_count"], 4)
        self.assertEqual(projection["active_count"], 2)
        self.assertEqual(projection["recoverable_count"], 1)
        self.assertEqual(projection["terminal_count"], 2)
        self.assertEqual(records, before)

        for group in ("tasks", "active_tasks", "recoverable_tasks", "terminal_tasks"):
            for row in projection[group]:
                self.assertEqual(tuple(row.keys()), TASK_KEYS)
                self.assertEqual(tuple(row["actor"].keys()), TASK_ACTOR_KEYS)
                self.assertEqual(row["actor"], {"actor_id": actor_id, "role_id": "pm"})
                self.assertEqual(
                    row["demand_ref"],
                    {"demand_id": f"demand-{row['task_id']}", "basis_revision": 1},
                )
                for sensitive in (
                    "execution",
                    "events",
                    "runtime_instruction",
                    "context",
                    "inbound_context",
                    "side_thread_id",
                    "handoff",
                    "raw_payload",
                    "repo_path",
                    "internal_stack",
                    "source_ref",
                    "task_desc",
                    "relation",
                    "task_relation",
                ):
                    self.assertNotIn(sensitive, row)

        projection["tasks"][0]["actor"]["role_id"] = "changed"
        completed_record = next(record for record in records if record["id"] == "task-completed")
        self.assertEqual(completed_record["actor_target"]["role_id"], "pm")

    def test_task_external_get_returns_projection_or_none_without_raw_refs(self) -> None:
        task_read = _task_read_module()
        record = self._task_record(task_id="task-get", updated_at="2026-07-13T10:00:00Z")

        with mock.patch.object(task_read.task_sys, "get_task", return_value=record):
            row = task_read.get_external_task("task-get", actor_profile=self._actor_profile())

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(tuple(row.keys()), TASK_KEYS)
        self.assertIsNot(row["actor"], record["actor_target"])

        with mock.patch.object(task_read.task_sys, "get_task", side_effect=ValueError("task not found: task-missing")):
            self.assertIsNone(task_read.get_external_task("task-missing", actor_profile=self._actor_profile()))

    def test_external_task_projection_requires_one_exact_demand_ref(self) -> None:
        task_read = _task_read_module()
        demand_record = self._task_record(
            task_id="task-demand-external",
            updated_at="2026-07-13T10:00:00Z",
        )
        demand_record["source_ref"] = {
            "demand_id": "demand-external-safe",
            "basis_revision": 7,
        }

        demand_row = task_read.external_task_projection(demand_record)

        self.assertEqual(
            demand_row["demand_ref"],
            {"demand_id": "demand-external-safe", "basis_revision": 7},
        )
        self.assertEqual(tuple(demand_row), TASK_KEYS)

        malformed = deepcopy(demand_record)
        malformed["source_ref"]["detail"] = "must not leak"
        non_demand = deepcopy(demand_record)
        non_demand["source_type"] = "track.comment.added"
        for record in (malformed, non_demand):
            with self.subTest(record=record):
                with self.assertRaises(ValueError):
                    task_read.external_task_projection(record)

    def test_external_task_and_track_lists_return_empty_lists(self) -> None:
        task_read = _task_read_module()
        with mock.patch.object(task_read.task_sys, "list_tasks", return_value=[]):
            self.assertEqual(task_read.list_external_tasks(actor_profile=self._actor_profile()), [])
            self.assertEqual(
                task_read.actor_external_task_projection(actor_profile=self._actor_profile()),
                {
                    "tasks": [],
                    "active_tasks": [],
                    "recoverable_tasks": [],
                    "terminal_tasks": [],
                    "task_count": 0,
                    "active_count": 0,
                    "recoverable_count": 0,
                    "terminal_count": 0,
                },
            )

        with mock.patch.object(track_read.track_repo, "list_tracks", return_value=[]):
            self.assertEqual(track_read.list_external_tracks(owner_identity="act-pm-demo"), [])

    def test_track_external_list_filters_sorts_and_allowlists_exact_keys(self) -> None:
        tracks = [
            self._track_record(track_id="track-old", updated_at="2026-07-13T10:00:00Z"),
            self._track_record(track_id="track-other-owner", owner_identity_id="act-dev-demo", updated_at="2026-07-13T12:00:00Z"),
            self._track_record(track_id="track-new", updated_at="2026-07-13T11:00:00Z"),
            self._track_record(track_id="track-archived", updated_at="2026-07-13T12:30:00Z", archived_at="2026-07-13T12:31:00Z"),
        ]
        comments = self._comments()
        before_tracks = deepcopy(tracks)
        before_comments = deepcopy(comments)

        with mock.patch.object(track_read.track_repo, "list_tracks", return_value=tracks), mock.patch.object(
            track_read.track_comment_repo,
            "comments_for_track",
            return_value=comments,
        ):
            rows = track_read.list_external_tracks(owner_identity="act-pm-demo")

        self.assertEqual([row["id"] for row in rows], ["track-new", "track-old"])
        for row in rows:
            self.assertEqual(tuple(row.keys()), TRACK_LIST_KEYS)
            self.assertNotIn("materials", row)
            self.assertNotIn("proofs", row)
            self.assertNotIn("updates", row)
            self.assertNotIn("comment_threads", row)
            for sensitive in ("execution", "raw_payload", "repo_path", "internal_stack", "artifact_relations"):
                self.assertNotIn(sensitive, row)
        self.assertEqual(tracks, before_tracks)
        self.assertEqual(comments, before_comments)

        rows[0]["now"]["next"] = "mutated"
        rows[0]["acceptance_criteria"].append("mutated")
        self.assertEqual(tracks[2]["now"]["next"], "Keep moving.")
        self.assertEqual(tracks[2]["acceptance_criteria"], ["Exact allowlist."])

    def test_track_external_get_adds_detail_allowlist_and_returns_none_for_missing(self) -> None:
        track = self._track_record(track_id="track-alpha", updated_at="2026-07-13T10:00:00Z")
        comments = self._comments()
        before_track = deepcopy(track)
        before_comments = deepcopy(comments)

        with mock.patch.object(track_read.track_repo, "get_track", return_value=track), mock.patch.object(
            track_read.track_comment_repo,
            "comments_for_track",
            return_value=comments,
        ):
            detail = track_read.get_external_track("track-alpha", current_identity={"id": "act-pm-demo", "type": "actor"})

        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(tuple(detail.keys()), TRACK_DETAIL_KEYS)
        self.assertEqual([row["artifact_id"] for row in detail["materials"]], ["artifact-material"])
        self.assertEqual([row["artifact_id"] for row in detail["proofs"]], ["artifact-proof"])
        self.assertEqual([row["id"] for row in detail["updates"]], ["upd-track"])
        self.assertEqual([row["thread_id"] for row in detail["comment_threads"]], ["thread-open"])
        self.assertEqual(track, before_track)
        self.assertEqual(comments, before_comments)

        detail["updates"][0]["refs"][0]["id"] = "mutated"
        detail["comment_threads"][0]["comments"][0]["mentioned_identity_ids"].append("mutated")
        self.assertEqual(track["updates"][0]["refs"][0]["id"], "artifact-proof")
        self.assertEqual(comments[0]["mentioned_identity_ids"], ["act-pm-demo"])

        with mock.patch.object(track_read.track_repo, "get_track", return_value=None):
            self.assertIsNone(track_read.get_external_track("track-missing"))

        archived = dict(track)
        archived["archived_at"] = "2026-07-13T12:00:00Z"
        with mock.patch.object(track_read.track_repo, "get_track", return_value=archived):
            self.assertIsNone(track_read.get_external_track("track-alpha"))
