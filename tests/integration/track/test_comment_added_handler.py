"""Track module tests for daemon-side comment trigger handling."""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from itertools import count
from pathlib import Path
from typing import Any

from tests.support.paths import REPO_ROOT
from buddyswitch.application.daemon_host import AppActorDaemonHost
from tests.support.runtime import RuntimeWorkspaceTestCase

ROOT = REPO_ROOT
LAUNCHER = ROOT / "src" / "buddyswitch" / "launcher"

from buddyswitch.foundation.daemon import state as daemon_state  # noqa: E402
from tests.support import task_fixtures  # noqa: E402
import buddyswitch.foundation.state.runtime as state_runtime  # noqa: E402
from buddyswitch.modules.track.private.state import track_comments as comment_repo  # noqa: E402
from buddyswitch.modules.track.private.state import tracks as track_repo  # noqa: E402
from buddyswitch.modules.demand.private.domain import demand_sys  # noqa: E402
from buddyswitch.modules.demand.private.state import demands  # noqa: E402

TRACK_COMMENT_DOMAIN_PATH = ROOT / "src" / "buddyswitch" / "modules" / "track" / "private" / "domain" / "track_comments.py"
DAEMON_CORE_PATH = ROOT / "src" / "buddyswitch" / "foundation" / "daemon" / "instance.py"
HANDLER_PATH = ROOT / "src" / "buddyswitch" / "modules" / "track" / "private" / "adapters" / "daemon" / "track_comment_added_handler.py"
MODULE_COUNTER = count()


def load_module(path: Path) -> Any:
    if not path.exists():
        raise AssertionError(f"expected module to exist: {path}")
    module_name = (
        "buddyswitch.foundation.daemon.instance"
        if path == DAEMON_CORE_PATH
        else "buddyswitch.modules.track.private.adapters.daemon.track_comment_added_handler"
    )
    return importlib.reload(importlib.import_module(module_name))


def assert_contains_all(testcase: unittest.TestCase, text: str, expected: tuple[str, ...]) -> None:
    for token in expected:
        with testcase.subTest(token=token):
            testcase.assertIn(token, text)


def assert_contains_none(testcase: unittest.TestCase, text: str, forbidden: tuple[str, ...]) -> None:
    for token in forbidden:
        with testcase.subTest(token=token):
            testcase.assertNotIn(token, text)


class FakeDaemonRuntime:
    def __init__(self, *, result: Any = None, error: BaseException | None = None) -> None:
        self.result = (
            {"action": "start", "turn_id": "turn-demand-track-1"}
            if result is None
            else result
        )
        self.error = error
        self.inputs: list[str] = []

    def input_actor(self, text: str) -> Any:
        self.inputs.append(text)
        if self.error is not None:
            raise self.error
        return self.result

class TrackCommentAddedHandlerTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.instance = load_module(DAEMON_CORE_PATH)
        self.handler_module = load_module(HANDLER_PATH)
        self.handler = self.handler_module.TrackCommentAddedHandler()

    def _restore_runtime_env(self, values: dict[str, str | None]) -> None:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        state_runtime.refresh_runtime_roots_from_env()

    def _instance(self, *, actor_id: str = "act-dev-track-handler", role: str = "dev") -> dict[str, Any]:
        instance_root = self.runtime_root / "instances" / actor_id
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        payload = {
            "actor_id": actor_id,
            "role": role,
            "status": "active",
            "instance_root": str(instance_root),
            "workspace_dir": str(workspace_dir),
            "thread_id": "thr-main-track",
            "app_server_socket": str(instance_root / "runtime" / "app-server.sock"),
        }
        instance_json.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
        context = self.instance.load_daemon_context(instance_json, host=AppActorDaemonHost())
        state = daemon_state.DaemonState.load(
            instance_root=instance_root,
            actor_id=actor_id,
            main_thread_id="thr-main-track",
        )
        return {"context": context, "state": state}

    def _trigger(
        self,
        *,
        trigger_type: str = "track.comment.added",
        to_role: str = "dev",
        to_actor_id: str = "act-dev-track-handler",
        payload: dict[str, Any] | None = None,
        source_context: dict[str, Any] | None = None,
    ) -> object:
        context_payload = (
            {
                "signal_id": "sig-track-comment",
                "source_identity_id": "act-pm-track-source",
                "source_role_id": "pm",
                "created_at": "2026-06-10T00:00:00Z",
            }
            if source_context is None
            else source_context
        )
        return self.instance.triggers.DaemonTrigger(
            source="mailbox_cross_actor_signal" if trigger_type == "track.comment.added" else "mailbox_local_trigger",
            type=trigger_type,
            target_identity_id=to_actor_id,
            target_role_id=to_role,
            origin_id="sig-track-comment",
            correlation_id=None,
            payload=payload if payload is not None else {},
            source_context=context_payload,
        )

    def _seed_track(self, track_id: str, *, archived: bool = False) -> dict[str, Any]:
        track = track_repo.create_track(
            track_id,
            f"Track {track_id}",
            owner_identity={"id": "act-pm-track-source", "type": "actor"},
            outcome="Track comment handler outcome",
            now={"next": "test", "blocker": None},
        )
        if archived:
            track = track_repo.update_track(track_id, {"archived_at": "2026-06-10T00:00:00Z"})
        return track

    def _seed_comment(
        self,
        *,
        track_id: str = "track-comment-handler",
        by_identity: dict[str, str] | None = None,
        mentioned_identities: list[dict[str, str]] | None = None,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        if track_repo.get_track(track_id) is None:
            self._seed_track(track_id)
        author = by_identity or {"id": "act-pm-track-source", "type": "actor"}
        if reply_to is not None:
            return comment_repo.reply_to_track_comment(
                track_id=track_id,
                reply_to=reply_to,
                by_identity=author,
                content="Reply Track comment",
                mentioned_identities=mentioned_identities,
            )
        return comment_repo.create_track_comment(
            track_id=track_id,
            by_identity=author,
            content="Track comment",
            mentioned_identities=mentioned_identities,
        )

    def _payload_for(self, comment: dict[str, Any], *, track_id: str | None = None, thread_id: str | None = None) -> dict[str, str]:
        return {
            "track_id": track_id or str(comment["track_id"]),
            "comment_id": str(comment["id"]),
            "thread_id": thread_id or str(comment["thread_id"]),
        }

    def _task_records(self) -> list[dict[str, Any]]:
        tasks_dir = state_runtime.OBJECTS_ROOT / "task-sys" / "tasks"
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(tasks_dir.glob("*.json"))
        ]

    def _demand_rows(self) -> list[dict[str, Any]]:
        return demand_sys.list_demands(
            {"actor_id": "act-dev-track-handler", "role_id": "dev"},
            state="all",
        )

    def _assert_track_comment_demand(
        self,
        comment: dict[str, Any],
        runtime: FakeDaemonRuntime,
        state: daemon_state.DaemonState,
        *,
        existing_task_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        rows = self._demand_rows()
        self.assertEqual(rows, [])
        track_id = str(comment["track_id"])
        comment_id = str(comment["id"])
        thread_id = str(comment["thread_id"])
        content = str(comment["content"]).strip()
        schedules = [
            row
            for row in state.payload["scheduled_triggers"].values()
            if row.get("status") == "pending"
        ]
        self.assertEqual(len(schedules), 1)
        schedule = schedules[0]
        self.assertEqual(
            schedule["schedule_key"],
            (
                "demand-ingress:"
                f"track.comment.added:{track_id}:{comment_id}"
            ),
        )
        self.assertEqual(
            schedule["payload"]["source_key"],
            f"track.comment.added:{track_id}:{comment_id}",
        )
        self.assertEqual(schedule["payload"]["description"], content)
        self.assertEqual(
            schedule["payload"]["detail"],
            f"Track comment on {track_id} (comment {comment_id}, thread {thread_id}):\n{content}",
        )
        self.assertEqual(
            schedule["payload"]["source_refs"],
            [{
                "type": "track.comment.added",
                "ref": {
                    "track_id": track_id,
                    "comment_id": comment_id,
                    "thread_id": thread_id,
                },
            }],
        )
        self.assertEqual(
            [record["id"] for record in self._task_records()],
            existing_task_ids or [],
        )
        self.assertEqual(runtime.inputs, [])
        return schedule

    def test_track_comment_handler_ignores_unknown_trigger_types(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime()
        trigger = self._trigger(trigger_type="example.ready", payload={"message_id": "msg-1"})

        self.assertFalse(self.handler.handles(trigger))
        result = self.handler.handle(instance["context"], instance["state"], runtime, trigger)

        self.assertEqual(result.status, "ignored")
        self.assertEqual(runtime.inputs, [])

    def test_track_comment_handler_rejects_trigger_for_other_identity(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime()
        comment = self._seed_comment(mentioned_identities=["act-dev-track-handler"])

        result = self.handler.handle(
            instance["context"],
            instance["state"],
            runtime,
            self._trigger(to_role="design", to_actor_id="act-design-track-handler", payload=self._payload_for(comment)),
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("wrong target identity", result.message)
        self.assertEqual(runtime.inputs, [])

    def test_track_comment_handler_rejects_missing_payload_ids(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime()

        result = self.handler.handle(instance["context"], instance["state"], runtime, self._trigger(payload={}))

        self.assertEqual(result.status, "failed")
        self.assertIn("track_id", result.message)
        self.assertEqual(runtime.inputs, [])

    def test_track_comment_handler_rejects_comment_from_wrong_track(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime()
        comment = self._seed_comment(mentioned_identities=["act-dev-track-handler"])
        self._seed_track("track-comment-other")

        result = self.handler.handle(
            instance["context"],
            instance["state"],
            runtime,
            self._trigger(payload=self._payload_for(comment, track_id="track-comment-other")),
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("comment not found", result.message)
        self.assertEqual(runtime.inputs, [])

    def test_track_comment_handler_rejects_wrong_thread_payload(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime()
        comment = self._seed_comment(mentioned_identities=["act-dev-track-handler"])

        result = self.handler.handle(
            instance["context"],
            instance["state"],
            runtime,
            self._trigger(payload=self._payload_for(comment, thread_id="comment-wrong-thread")),
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("thread", result.message)
        self.assertEqual(runtime.inputs, [])

    def test_track_comment_handler_rejects_unintended_target_actor(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime()
        comment = self._seed_comment(mentioned_identities=["act-design-track-handler"])

        result = self.handler.handle(
            instance["context"],
            instance["state"],
            runtime,
            self._trigger(payload=self._payload_for(comment)),
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("not an intended recipient", result.message)
        self.assertEqual(runtime.inputs, [])

    def test_track_comment_handler_rejects_archived_track(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime()
        self._seed_track("track-comment-archived", archived=True)
        comment = self._seed_comment(
            track_id="track-comment-archived",
            mentioned_identities=["act-dev-track-handler"],
        )

        result = self.handler.handle(
            instance["context"],
            instance["state"],
            runtime,
            self._trigger(payload=self._payload_for(comment)),
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("archived", result.message)
        self.assertEqual(runtime.inputs, [])

    def test_track_comment_handler_reads_rows_from_daemon_bound_shared_state_root(self) -> None:
        original_env = {
            key: os.environ.get(key)
            for key in (
                "BUDDYSWITCH_SHARED_ROOT",
                "BUDDYSWITCH_STATE_ROOT",
                "BUDDYSWITCH_INSTANCE_ROOT",
                "BUDDYSWITCH_INSTANCE_JSON",
                "BUDDYSWITCH_WORKSPACE_DIR",
                "BUDDYSWITCH_ACTOR_ID",
                "BUDDYSWITCH_ROLE_ID",
            )
        }
        self.addCleanup(self._restore_runtime_env, original_env)
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_root_text:
            shared_root = Path(temp_root_text)
            state_root = shared_root / "state"
            instance_root = shared_root / "instances" / "act-dev-track-handler"
            workspace_dir = instance_root / "workspace"
            workspace_dir.mkdir(parents=True, exist_ok=True)
            instance_json = instance_root / "instance.json"
            payload = {
                "actor_id": "act-dev-track-handler",
                "role": "dev",
                "status": "active",
                "instance_root": str(instance_root),
                "workspace_dir": str(workspace_dir),
                "thread_id": "thr-main-track",
                "app_server_socket": str(instance_root / "runtime" / "app-server.sock"),
            }
            instance_json.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
            context = self.instance.load_daemon_context(instance_json, host=AppActorDaemonHost())

            os.environ.update(self.instance.derive_daemon_runtime_env(context))
            os.environ["BUDDYSWITCH_ACTOR_ID"] = "act-dev-track-handler"
            state_runtime.refresh_runtime_roots_from_env()

            track_id = "track-comment-shared-root"
            self._seed_track(track_id)
            comment = self._seed_comment(
                track_id=track_id,
                mentioned_identities=["act-dev-track-handler"],
            )
            comment_path = (
                state_root
                / "buddyswitch"
                / "objects"
                / "track-comments"
                / track_id
                / f"{comment['id']}.json"
            )
            self.assertTrue(comment_path.exists())
            self.assertFalse((shared_root / "buddyswitch" / "objects" / "track-comments").exists())

            state = daemon_state.DaemonState.load(
                instance_root=instance_root,
                actor_id="act-dev-track-handler",
                main_thread_id="thr-main-track",
            )
            runtime = FakeDaemonRuntime()

            result = self.handler.handle(
                context,
                state,
                runtime,
                self._trigger(payload=self._payload_for(comment)),
            )

            self.assertEqual(result.status, "handled")
            self._assert_track_comment_demand(comment, runtime, state)

    def test_track_comment_handler_schedules_pending_intake_without_parent_input(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime()
        comment = self._seed_comment(mentioned_identities=["act-dev-track-handler"])

        self.assertTrue(self.handler.handles(self._trigger(payload=self._payload_for(comment))))
        result = self.handler.handle(
            instance["context"],
            instance["state"],
            runtime,
            self._trigger(payload=self._payload_for(comment)),
        )

        self.assertEqual(result.status, "handled")
        self._assert_track_comment_demand(
            comment,
            runtime,
            instance["state"],
        )

    def test_track_comment_handler_replay_keeps_one_pending_intake_schedule(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime()
        comment = self._seed_comment(mentioned_identities=["act-dev-track-handler"])
        trigger = self._trigger(payload=self._payload_for(comment))

        first = self.handler.handle(
            instance["context"],
            instance["state"],
            runtime,
            trigger,
        )
        replay = self.handler.handle(
            instance["context"],
            instance["state"],
            runtime,
            trigger,
        )

        self.assertEqual(first.status, "handled")
        self.assertEqual(replay.status, "handled")
        self.assertEqual(self._demand_rows(), [])
        self.assertEqual(self._task_records(), [])
        pending = [
            row
            for row in instance["state"].payload["scheduled_triggers"].values()
            if row.get("status") == "pending"
        ]
        self.assertEqual(len(pending), 1)
        self.assertEqual(runtime.inputs, [])

    def test_track_comment_handler_schedules_intake_while_another_task_is_active(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime(result={"action": "steer", "turn_id": "turn-demand-track-active"})
        active = task_fixtures.create_task(
            actor_target={"actor_id": "act-dev-track-handler", "role_id": "dev"},
            demand_ref={
                "demand_id": "demand-existing-active",
                "basis_revision": 1,
                "demand_ref": "dref-existing-active",
            },
            objective="Keep this Task active while a Track Demand arrives.",
            selection_reason="This is the existing current Task.",
        )
        comment = self._seed_comment(mentioned_identities=["act-dev-track-handler"])

        result = self.handler.handle(
            instance["context"],
            instance["state"],
            runtime,
            self._trigger(payload=self._payload_for(comment)),
        )

        self.assertEqual(result.status, "handled")
        self._assert_track_comment_demand(
            comment,
            runtime,
            instance["state"],
            existing_task_ids=[str(active["task_id"])],
        )

    def test_track_comment_handler_routes_reply_attention_to_parent_comment_author(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime()
        parent = self._seed_comment(
            by_identity={"id": "act-dev-track-handler", "type": "actor"},
        )
        reply = self._seed_comment(
            by_identity={"id": "act-pm-track-source", "type": "actor"},
            reply_to=parent["id"],
        )

        result = self.handler.handle(
            instance["context"],
            instance["state"],
            runtime,
            self._trigger(payload=self._payload_for(reply)),
        )

        self.assertEqual(result.status, "handled")
        self._assert_track_comment_demand(
            reply,
            runtime,
            instance["state"],
        )

    def test_track_comment_handler_rejects_signal_source_that_is_not_comment_author(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime()
        comment = self._seed_comment(mentioned_identities=["act-dev-track-handler"])

        result = self.handler.handle(
            instance["context"],
            instance["state"],
            runtime,
            self._trigger(
                payload=self._payload_for(comment),
                source_context={
                    "signal_id": "sig-track-comment",
                    "source_identity_id": "act-design-not-author",
                    "source_role_id": "design",
                    "created_at": "2026-06-10T00:00:00Z",
                },
            ),
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("comment author", result.message)
        self.assertEqual(self._demand_rows(), [])
        self.assertEqual(self._task_records(), [])
        self.assertEqual(runtime.inputs, [])

    def test_source_handler_never_calls_actor_input(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime(error=RuntimeError("app-server down"))
        comment = self._seed_comment(mentioned_identities=["act-dev-track-handler"])

        result = self.handler.handle(
            instance["context"],
            instance["state"],
            runtime,
            self._trigger(payload=self._payload_for(comment)),
        )

        self.assertEqual(result.status, "handled")
        self._assert_track_comment_demand(
            comment,
            runtime,
            instance["state"],
        )
        self.assertEqual(self._task_records(), [])

    def test_track_comment_prompt_renderers_are_removed_from_domain_helpers(self) -> None:
        source = TRACK_COMMENT_DOMAIN_PATH.read_text(encoding="utf-8")

        for helper in (
            "_track_comment_header",
            "_track_comment_runtime_context",
            "_track_comment_parent_steps",
            "_track_comment_side_steps",
            "_track_comment_parent_work_demand_tips",
            "_track_comment_side_work_demand_tips",
            "_track_comment_finish",
        ):
            with self.subTest(helper=helper):
                self.assertNotIn(f"def {helper}(", source)
        self.assertNotIn("def render_parent_track_comment_prompt(", source)
        self.assertNotIn("def render_side_track_comment_prompt(", source)
