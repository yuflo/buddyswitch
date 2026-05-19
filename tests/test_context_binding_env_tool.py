#!/usr/bin/env python3
"""Context env.tool integration tests."""

from __future__ import annotations

import json
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_legacy_store as env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"
_EXPECTED_TOOLS = {"task", "track", "artifact", "buddybox", "context", "evidence", "search", "message", "comment"}


class ContextBindingEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(self, *, instance_id: str = "inst-dev-context", buddy: str = "dev", status: str = "active") -> Path:
        path = self._runtime_path("instance.json")
        path.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": status,
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "updated_at": "2026-05-15T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def _dispatch(self, *, instance_json: Path, tool: str, action: str, args: dict[str, object], instance_id: str = "inst-dev-context", buddy: str = "dev") -> dict[str, object]:
        request = {
            "protocol": PROTOCOL,
            "request_id": f"req-context-{uuid.uuid4().hex}",
            "method": "env.tool",
            "params": {
                "instance_id": instance_id,
                "active_buddy": buddy,
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
        self.assertEqual(envelope.get("protocol"), PROTOCOL)
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

    def _seed_context_state(self) -> None:
        env_store.create_track("track-context-active", "Context Track", owner_buddy="pm")
        env_store.create_task("task-dev-context", "Context Task", buddy="dev", track_id="track-context-active", summary="seed")
        env_store.create_artifact_revision(
            artifact_id="art-task-dev-context-note-r1",
            title="Context Artifact v1",
            summary="artifact summary v1",
            body="artifact body v1",
            template="note",
            supersedes_artifact_id=None,
            created_by="dev",
            authors=["dev"],
            source_refs=[{"type": "note", "label": "context"}],
        )
        env_store.publish_track_material(
            track_id="track-context-active",
            artifact_id="art-task-dev-context-note-r1",
            label="Context",
            from_buddy="dev",
            summary="artifact summary v1",
        )
        env_store.create_artifact_revision(
            artifact_id="art-task-dev-context-note-r2",
            title="Context Artifact v2",
            summary="artifact summary v2",
            body="artifact body v2",
            template="note",
            supersedes_artifact_id="art-task-dev-context-note-r1",
            created_by="dev",
            authors=None,
            source_refs=[{"type": "note", "label": "context"}],
        )
        env_store.publish_track_material(
            track_id="track-context-active",
            artifact_id="art-task-dev-context-note-r2",
            label="Context",
            from_buddy="dev",
            summary="artifact summary v2",
        )

        env_store.create_track(
            "track-context-archived",
            "Archived Track",
            owner_buddy="pm",
            state="done",
            health="ok",
        )
        env_store.create_task("task-dev-archived", "Archived task", buddy="dev", track_id="track-context-archived")
        archived_artifact = env_store.create_artifact_revision(
            artifact_id="art-task-dev-archived-r1",
            title="Archived Artifact",
            summary="archived",
            body="archived",
            template="note",
            supersedes_artifact_id=None,
            created_by="dev",
            authors=["dev"],
            source_refs=[{"type": "note", "label": "context"}],
        )
        env_store.publish_track_material(
            track_id="track-context-archived",
            artifact_id=str(archived_artifact["id"]),
            label="Archived",
            from_buddy="dev",
            summary="archived",
        )
        env_store.update_track(
            "track-context-archived",
            {"archived_at": "2026-05-18T10:00:00+08:00"},
        )

    def test_context_summarize_exposes_compact_tool_affordances(self) -> None:
        instance_json = self._instance_json()
        summary = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={})
        self.assertTrue(summary.get("ok"), msg=summary)

        affordances = summary.get("tool_affordances")
        self.assertIsInstance(affordances, dict, msg=summary)
        assert isinstance(affordances, dict)
        self.assertEqual(set(affordances), _EXPECTED_TOOLS)
        self.assertNotIn("handoff", affordances)
        for tool_name in ("track", "artifact", "task", "buddybox", "context"):
            with self.subTest(tool=tool_name):
                compact = affordances.get(tool_name)
                self.assertIsInstance(compact, dict, msg=summary)
                assert isinstance(compact, dict)
                self.assertIsInstance(compact.get("capability"), str, msg=compact)
                self.assertIsInstance(compact.get("returns"), str, msg=compact)
                self.assertIsInstance(compact.get("state_effect"), str, msg=compact)
                self.assertIsInstance(compact.get("when_to_use"), list, msg=compact)
                self.assertIsInstance(compact.get("when_not_to_use"), list, msg=compact)

    def test_context_candidate_tracks_use_owner_buddy_only(self) -> None:
        self._seed_context_state()
        instance_json = self._instance_json()
        payload = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={})
        self.assertTrue(payload.get("ok"), msg=payload)
        rows = payload.get("candidate_tracks")
        self.assertIsInstance(rows, list, msg=payload)
        assert isinstance(rows, list)
        self.assertTrue(rows)
        for row in rows:
            if not isinstance(row, dict):
                continue
            self.assertIn("owner_buddy", row)
            self.assertIn(row.get("active_buddy_role"), {"owner", "observer", "collaborator"})
            self.assertNotIn("current_buddy", row)
            self.assertNotIn("next_buddy", row)
            self.assertNotIn("participant", row)

    def test_context_omits_archived_tracks_from_active_context(self) -> None:
        self._seed_context_state()
        instance_json = self._instance_json()

        summary = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={})
        full = self._dispatch(instance_json=instance_json, tool="context", action="get", args={})
        self.assertTrue(summary.get("ok"), msg=summary)
        self.assertTrue(full.get("ok"), msg=full)

        candidate_ids = {row.get("track_id") for row in summary.get("candidate_tracks", []) if isinstance(row, dict)}
        track_ids = {row.get("id") for row in full.get("tracks", []) if isinstance(row, dict)}

        self.assertIn("track-context-active", candidate_ids)
        self.assertIn("track-context-active", track_ids)
        self.assertNotIn("track-context-archived", candidate_ids)
        self.assertNotIn("track-context-archived", track_ids)

    def test_context_artifact_summaries_are_current_only(self) -> None:
        self._seed_context_state()
        instance_json = self._instance_json()
        payload = self._dispatch(instance_json=instance_json, tool="context", action="get", args={})
        self.assertTrue(payload.get("ok"), msg=payload)

        rows = payload.get("artifact_summaries")
        self.assertIsInstance(rows, list, msg=payload)
        assert isinstance(rows, list)
        ids = [row.get("artifact_id") for row in rows if isinstance(row, dict)]
        self.assertIn("art-task-dev-context-note-r2", ids)
        self.assertNotIn("art-task-dev-context-note-r1", ids)
        self.assertNotIn("art-task-dev-archived-r1", ids)
        for row in rows:
            if not isinstance(row, dict):
                continue
            self.assertIn("readable_by_active_buddy", row)
            self.assertNotIn("readable_by_current_buddy", row)

    def test_context_list_sources_excludes_handoffs(self) -> None:
        instance_json = self._instance_json()
        listed = self._dispatch(instance_json=instance_json, tool="context", action="list_sources", args={})
        self.assertTrue(listed.get("ok"), msg=listed)
        sources = listed.get("sources")
        self.assertIsInstance(sources, dict, msg=listed)
        assert isinstance(sources, dict)
        self.assertNotIn("handoffs", sources)
        self.assertIn("tracks", sources)
        self.assertIn("artifacts", sources)

    def test_context_get_applies_filters(self) -> None:
        self._seed_context_state()
        instance_json = self._instance_json()

        filtered = self._dispatch(
            instance_json=instance_json,
            tool="context",
            action="get",
            args={"track_id": "track-context-active", "task_id": "task-dev-context", "limit": 5},
        )
        self.assertTrue(filtered.get("ok"), msg=filtered)
        tasks = filtered.get("tasks")
        self.assertIsInstance(tasks, list, msg=filtered)
        assert isinstance(tasks, list)
        self.assertEqual({row.get("id") for row in tasks if isinstance(row, dict)}, {"task-dev-context"})

    def test_context_rejects_unknown_payload_field(self) -> None:
        instance_json = self._instance_json()
        rejected = self._dispatch(instance_json=instance_json, tool="context", action="get", args={"unknown": 1})
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_CONTEXT_PAYLOAD")


if __name__ == "__main__":
    unittest.main()
