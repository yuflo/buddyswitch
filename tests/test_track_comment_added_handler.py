#!/usr/bin/env python3
"""Tests for daemon-side Track comment trigger handling."""

from __future__ import annotations

import importlib.util
import json
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


class FakeDaemonRuntime:
    def __init__(self, *, activity: dict[str, object] | None = None) -> None:
        self.activity = activity or {"status": "idle", "active_turn_id": None}
        self.calls: list[dict[str, object]] = []

    def parent_activity(self) -> dict[str, object]:
        self.calls.append({"method": "parent_activity"})
        return self.activity

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
        return {"turn_id": "turn-parent-track-comment"}

    def submit_side_triage_prompt(self, text: str, *, handler_name: str, origin_id: str | None) -> dict[str, object]:
        self.calls.append(
            {
                "method": "submit_side_triage_prompt",
                "text": text,
                "handler_name": handler_name,
                "origin_id": origin_id,
            }
        )
        return {"action": "start", "side_thread_id": "thr-side-track", "turn_id": "turn-side-track"}


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

    def test_track_comment_handler_ignores_unknown_trigger_types(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime()
        trigger = self._trigger(trigger_type="message.available", payload={"message_id": "msg-1"})

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

    def test_track_comment_handler_routes_idle_parent_to_parent_prompt(self) -> None:
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
        self.assertEqual([call["method"] for call in runtime.calls], ["parent_activity", "submit_parent_prompt"])
        call = runtime.calls[1]
        self.assertEqual(call["handler_name"], "track_comment_added")
        self.assertEqual(call["origin_id"], comment["id"])
        self.assertEqual(call["interrupt_policy"], "none")
        prompt = call["text"]
        self.assertIsInstance(prompt, str)
        self.assertIn("[TRACK COMMENT ATTENTION]", prompt)
        self.assertIn(str(comment["id"]), prompt)
        self.assertIn(str(comment["track_id"]), prompt)
        self.assertIn("track.open", prompt)
        self.assertIn("track.list_comments", prompt)
        self.assertIn("track.add_comment", prompt)
        self.assertIn("track.resolve_comment_thread", prompt)
        forbidden = [
            "notification.",
            "nc.notification",
            "daemon",
            "mailbox",
            "message.available",
            "absorbed",
            "replied",
            "needs_parent",
            "parent_thread_id",
            "side_thread_id",
        ]
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, prompt)

    def test_track_comment_handler_routes_running_parent_to_side_triage(self) -> None:
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
        self.assertEqual([call["method"] for call in runtime.calls], ["parent_activity", "submit_side_triage_prompt"])
        call = runtime.calls[1]
        self.assertEqual(call["handler_name"], "track_comment_added")
        self.assertEqual(call["origin_id"], comment["id"])
        prompt = call["text"]
        self.assertIsInstance(prompt, str)
        self.assertIn("[TRACK COMMENT TRIAGE]", prompt)
        self.assertIn("track.open", prompt)
        self.assertIn("track.list_comments", prompt)
        self.assertIn("track.add_comment", prompt)
        self.assertIn("track.resolve_comment_thread", prompt)
        self.assertNotIn("notification.", prompt)
        self.assertNotIn("side_thread_id", prompt)
        self.assertNotIn("needs_parent", prompt)

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
        self.assertEqual([call["method"] for call in runtime.calls], ["parent_activity", "submit_parent_prompt"])

    def test_track_comment_handler_fails_when_parent_activity_is_unavailable(self) -> None:
        instance = self._instance()
        runtime = FakeDaemonRuntime(activity={"status": "unavailable", "error": "app-server down"})
        comment = self._seed_comment(mentioned_actors=[{"actor_id": "act-dev-track-handler", "role_id": "dev"}])

        result = self.handler.handle(
            instance["context"],
            instance["state"],
            runtime,
            self._trigger(payload=self._payload_for(comment)),
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("app-server down", result.message)
        self.assertEqual([call["method"] for call in runtime.calls], ["parent_activity"])


if __name__ == "__main__":
    unittest.main()
