#!/usr/bin/env python3
"""Tests for daemon-side Track comment trigger handling."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from itertools import count
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.repos import runtime_files  # noqa: E402
from env.repos import track_comments as comment_repo  # noqa: E402
from env.repos import tracks as track_repo  # noqa: E402

TRACK_COMMENT_DOMAIN_PATH = ROOT / "scripts" / "env" / "domain" / "track_comments.py"
DAEMON_CORE_PATH = ROOT / "tools" / "launcher" / "daemon_core.py"
HANDLER_PATH = ROOT / "tools" / "launcher" / "track_comment_added_handler.py"
MODULE_COUNTER = count()


def load_module(path: Path) -> Any:
    if not path.exists():
        raise AssertionError(f"expected module to exist: {path}")
    module_name = f"buddyswitch_{path.stem}_{next(MODULE_COUNTER)}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_contains_all(testcase: unittest.TestCase, text: str, expected: tuple[str, ...]) -> None:
    for token in expected:
        with testcase.subTest(token=token):
            testcase.assertIn(token, text)


def assert_contains_none(testcase: unittest.TestCase, text: str, forbidden: tuple[str, ...]) -> None:
    for token in forbidden:
        with testcase.subTest(token=token):
            testcase.assertNotIn(token, text)


class FakeDaemonRuntime:
    def __init__(self, *, activity: dict[str, object] | None = None) -> None:
        self.activity = activity or {"status": "idle", "active_turn_id": None}
        self.calls: list[dict[str, object]] = []

    def parent_activity(self) -> dict[str, object]:
        self.calls.append({"method": "parent_activity"})
        raise AssertionError("Track comment handler must not inspect parent activity")

    def submit_parent_prompt(
        self,
        text: str,
        *,
        handler_name: str,
        origin_id: str | None,
        interrupt_policy: str,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "method": "submit_parent_prompt",
                "text": text,
                "handler_name": handler_name,
                "origin_id": origin_id,
                "interrupt_policy": interrupt_policy,
            }
        )
        raise AssertionError("Track comment handler must not submit parent prompts")

    def submit_side_triage_prompt(self, text: str, *, handler_name: str, origin_id: str | None) -> dict[str, object]:
        self.calls.append(
            {
                "method": "submit_side_triage_prompt",
                "text": text,
                "handler_name": handler_name,
                "origin_id": origin_id,
            }
        )
        raise AssertionError("Track comment handler must not submit side prompts")

    def execute_task_sys_instruction(self, instruction: dict[str, Any]) -> dict[str, object]:
        self.calls.append({"method": "execute_task_sys_instruction", "instruction": instruction})
        return {"action": instruction["type"], "task_id": instruction["task_id"]}


class TrackCommentAddedHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory(dir=ROOT)
        self.runtime_root = Path(self._tmp_dir.name)
        (self.runtime_root / "AGENTS.md").write_text(
            "# BuddySwitch Runtime Workspace\n\nTrack comment handler test root.\n",
            encoding="utf-8",
        )
        runtime_files.set_runtime_root_override(self.runtime_root)
        self.daemon_core = load_module(DAEMON_CORE_PATH)
        self.handler_module = load_module(HANDLER_PATH)
        self.handler = self.handler_module.TrackCommentAddedHandler()

    def tearDown(self) -> None:
        runtime_files.reset_runtime_root_override()
        self._tmp_dir.cleanup()
        super().tearDown()

    def _restore_runtime_env(self, values: dict[str, str | None]) -> None:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        runtime_files.reset_runtime_root_override()
        runtime_files.refresh_runtime_roots_from_env()

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
        context = self.daemon_core.load_daemon_context(instance_json)
        state = self.daemon_core.DaemonState.load(
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
                "source_actor_address": {"role_id": "pm", "actor_id": "act-pm-track-source"},
                "created_at": "2026-06-10T00:00:00Z",
            }
            if source_context is None
            else source_context
        )
        return self.daemon_core.daemon_triggers.DaemonTrigger(
            source="mailbox_cross_actor_signal" if trigger_type == "track.comment.added" else "mailbox_local_trigger",
            type=trigger_type,
            target_actor_address={"role_id": to_role, "actor_id": to_actor_id},
            origin_id="sig-track-comment",
            correlation_id=None,
            payload=payload if payload is not None else {},
            source_context=context_payload,
        )

    def _seed_track(self, track_id: str, *, archived: bool = False) -> dict[str, Any]:
        track = track_repo.create_track(
            track_id,
            f"Track {track_id}",
            owner_actor={"actor_id": "act-pm-track-source", "role_id": "pm"},
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
        by_actor: dict[str, str] | None = None,
        mentioned_actors: list[dict[str, str]] | None = None,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        if track_repo.get_track(track_id) is None:
            self._seed_track(track_id)
        author = by_actor or {"actor_id": "act-pm-track-source", "role_id": "pm"}
        if reply_to is not None:
            return comment_repo.reply_to_track_comment(
                track_id=track_id,
                reply_to=reply_to,
                by_actor=author,
                content="Reply Track comment",
                mentioned_actors=mentioned_actors,
            )
        return comment_repo.create_track_comment(
            track_id=track_id,
            by_actor=author,
            content="Track comment",
            mentioned_actors=mentioned_actors,
        )

    def _payload_for(self, comment: dict[str, Any], *, track_id: str | None = None, thread_id: str | None = None) -> dict[str, str]:
        return {
            "track_id": track_id or str(comment["track_id"]),
            "comment_id": str(comment["id"]),
            "thread_id": thread_id or str(comment["thread_id"]),
        }

    def _task_records(self) -> list[dict[str, Any]]:
        tasks_dir = runtime_files.OBJECTS_ROOT / "task-sys" / "tasks"
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(tasks_dir.glob("*.json"))
        ]

    def _assert_track_comment_task(self, comment: dict[str, Any], runtime: FakeDaemonRuntime) -> dict[str, Any]:
        records = self._task_records()
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["source_type"], "track.comment.added")
        self.assertEqual(
            record["source_ref"],
            {
                "track_id": str(comment["track_id"]),
                "comment_id": str(comment["id"]),
                "thread_id": str(comment["thread_id"]),
            },
        )
        self.assertEqual(record["actor_target"], {"actor_id": "act-dev-track-handler", "role_id": "dev"})
        self.assertEqual(record["inbound_context"]["track_id"], str(comment["track_id"]))
        self.assertEqual(record["inbound_context"]["comment_id"], str(comment["id"]))
        self.assertEqual(record["inbound_context"]["thread_id"], str(comment["thread_id"]))
        self.assertEqual(record["inbound_context"]["source_actor_address"], {"actor_id": "act-pm-track-source", "role_id": "pm"})
        self.assertEqual(record["status"], "side_processing")
        self.assertEqual(record["active_processor"], "side")
        execute_calls = [call for call in runtime.calls if call["method"] == "execute_task_sys_instruction"]
        self.assertEqual(len(execute_calls), 1)
        self.assertEqual(execute_calls[0]["instruction"]["type"], "start_side")
        self.assertEqual(execute_calls[0]["instruction"]["task_id"], record["id"])
        return record

    def test_track_comment_handler_ignores_unknown_trigger_types(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime()
        trigger = self._trigger(trigger_type="example.ready", payload={"message_id": "msg-1"})

        self.assertFalse(self.handler.handles(trigger))
        result = self.handler.handle(instance["context"], instance["state"], runtime, trigger)

        self.assertEqual(result.status, "ignored")
        self.assertEqual(runtime.calls, [])

    def test_track_comment_handler_rejects_trigger_for_other_actor_address(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime()
        comment = self._seed_comment(mentioned_actors=[{"actor_id": "act-dev-track-handler", "role_id": "dev"}])

        result = self.handler.handle(
            instance["context"],
            instance["state"],
            runtime,
            self._trigger(to_role="design", to_actor_id="act-design-track-handler", payload=self._payload_for(comment)),
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("wrong target actor", result.message)
        self.assertEqual(runtime.calls, [])

    def test_track_comment_handler_rejects_missing_payload_ids(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime()

        result = self.handler.handle(instance["context"], instance["state"], runtime, self._trigger(payload={}))

        self.assertEqual(result.status, "failed")
        self.assertIn("track_id", result.message)
        self.assertEqual(runtime.calls, [])

    def test_track_comment_handler_rejects_comment_from_wrong_track(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime()
        comment = self._seed_comment(mentioned_actors=[{"actor_id": "act-dev-track-handler", "role_id": "dev"}])
        self._seed_track("track-comment-other")

        result = self.handler.handle(
            instance["context"],
            instance["state"],
            runtime,
            self._trigger(payload=self._payload_for(comment, track_id="track-comment-other")),
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("comment not found", result.message)
        self.assertEqual(runtime.calls, [])

    def test_track_comment_handler_rejects_wrong_thread_payload(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime()
        comment = self._seed_comment(mentioned_actors=[{"actor_id": "act-dev-track-handler", "role_id": "dev"}])

        result = self.handler.handle(
            instance["context"],
            instance["state"],
            runtime,
            self._trigger(payload=self._payload_for(comment, thread_id="comment-wrong-thread")),
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("thread", result.message)
        self.assertEqual(runtime.calls, [])

    def test_track_comment_handler_rejects_unintended_target_actor(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime()
        comment = self._seed_comment(mentioned_actors=[{"actor_id": "act-design-track-handler", "role_id": "design"}])

        result = self.handler.handle(
            instance["context"],
            instance["state"],
            runtime,
            self._trigger(payload=self._payload_for(comment)),
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("not an intended recipient", result.message)
        self.assertEqual(runtime.calls, [])

    def test_track_comment_handler_rejects_archived_track(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime()
        self._seed_track("track-comment-archived", archived=True)
        comment = self._seed_comment(
            track_id="track-comment-archived",
            mentioned_actors=[{"actor_id": "act-dev-track-handler", "role_id": "dev"}],
        )

        result = self.handler.handle(
            instance["context"],
            instance["state"],
            runtime,
            self._trigger(payload=self._payload_for(comment)),
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("archived", result.message)
        self.assertEqual(runtime.calls, [])

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
            )
        }
        self.addCleanup(self._restore_runtime_env, original_env)
        runtime_files.reset_runtime_root_override()
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
            context = self.daemon_core.load_daemon_context(instance_json)

            os.environ.update(self.daemon_core.derive_daemon_runtime_env(context))
            os.environ["BUDDYSWITCH_ACTOR_ID"] = "act-dev-track-handler"
            runtime_files.refresh_runtime_roots_from_env()

            track_id = "track-comment-shared-root"
            self._seed_track(track_id)
            comment = self._seed_comment(
                track_id=track_id,
                mentioned_actors=[{"actor_id": "act-dev-track-handler", "role_id": "dev"}],
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

            state = self.daemon_core.DaemonState.load(
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
            self._assert_track_comment_task(comment, runtime)

    def test_track_comment_handler_ingests_task_without_parent_prompt(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime(activity={"status": "idle", "active_turn_id": None})
        comment = self._seed_comment(mentioned_actors=[{"actor_id": "act-dev-track-handler", "role_id": "dev"}])

        self.assertTrue(self.handler.handles(self._trigger(payload=self._payload_for(comment))))
        result = self.handler.handle(
            instance["context"],
            instance["state"],
            runtime,
            self._trigger(payload=self._payload_for(comment)),
        )

        self.assertEqual(result.status, "handled")
        self._assert_track_comment_task(comment, runtime)

    def test_track_comment_handler_ignores_parent_activity_when_ingesting_task(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime(activity={"status": "running", "active_turn_id": "turn-main-1"})
        comment = self._seed_comment(mentioned_actors=[{"actor_id": "act-dev-track-handler", "role_id": "dev"}])

        result = self.handler.handle(
            instance["context"],
            instance["state"],
            runtime,
            self._trigger(payload=self._payload_for(comment)),
        )

        self.assertEqual(result.status, "handled")
        self._assert_track_comment_task(comment, runtime)

    def test_track_comment_handler_routes_reply_attention_to_parent_comment_author(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime()
        parent = self._seed_comment(
            by_actor={"actor_id": "act-dev-track-handler", "role_id": "dev"},
        )
        reply = self._seed_comment(
            by_actor={"actor_id": "act-pm-track-source", "role_id": "pm"},
            reply_to=parent["id"],
        )

        result = self.handler.handle(
            instance["context"],
            instance["state"],
            runtime,
            self._trigger(payload=self._payload_for(reply)),
        )

        self.assertEqual(result.status, "handled")
        self._assert_track_comment_task(reply, runtime)

    def test_track_comment_handler_ingests_task_when_parent_activity_is_unavailable(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime(activity={"status": "unavailable", "error": "app-server down"})
        comment = self._seed_comment(mentioned_actors=[{"actor_id": "act-dev-track-handler", "role_id": "dev"}])

        result = self.handler.handle(
            instance["context"],
            instance["state"],
            runtime,
            self._trigger(payload=self._payload_for(comment)),
        )

        self.assertEqual(result.status, "handled")
        self._assert_track_comment_task(comment, runtime)

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


if __name__ == "__main__":
    unittest.main()
