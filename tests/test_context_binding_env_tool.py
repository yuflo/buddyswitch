#!/usr/bin/env python3
"""Context env.tool integration tests."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_legacy_store as env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"
_EXPECTED_TOOLS = {"task", "track", "artifact", "buddybox", "context", "evidence", "search", "message", "comment", "request"}


class ContextBindingEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(
        self,
        *,
        instance_id: str = "inst-dev-context",
        buddy: str = "dev",
        status: str = "active",
        workspace_dir: Path | None = None,
        path: Path | None = None,
    ) -> Path:
        instance_json_path = path if path is not None else self._runtime_path("instance.json")
        payload: dict[str, object] = {
            "instance_id": instance_id,
            "buddy": buddy,
            "status": status,
            "workspace_dir": str(workspace_dir if workspace_dir is not None else self.runtime_root),
            "browser_port": None,
            "updated_at": "2026-05-15T00:00:00Z",
        }
        instance_json_path.parent.mkdir(parents=True, exist_ok=True)
        instance_json_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2)
            + "\n",
            encoding="utf-8",
        )
        return instance_json_path

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
        task_ids = {row.get("id") for row in full.get("tasks", []) if isinstance(row, dict)}

        self.assertIn("track-context-active", candidate_ids)
        self.assertIn("track-context-active", track_ids)
        self.assertNotIn("track-context-archived", candidate_ids)
        self.assertNotIn("track-context-archived", track_ids)
        self.assertIn("task-dev-context", task_ids)
        self.assertNotIn("task-dev-archived", task_ids)

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
            self.assertNotIn("body", row)

    def test_context_summarize_track_filter_excludes_unpublished_owner_drafts(self) -> None:
        self._seed_context_state()
        draft = env_store.create_artifact_revision(
            artifact_id="art-context-owner-draft-untracked",
            title="Owner Draft",
            summary="private draft",
            body="private",
            template="note",
            supersedes_artifact_id=None,
            created_by="dev",
            authors=["dev"],
            source_refs=[{"type": "note", "label": "private"}],
        )
        self.assertEqual(draft.get("status"), "draft")

        instance_json = self._instance_json()
        payload = self._dispatch(
            instance_json=instance_json,
            tool="context",
            action="summarize",
            args={"track_id": "track-context-active"},
        )
        self.assertTrue(payload.get("ok"), msg=payload)
        ids = [
            row.get("artifact_id")
            for row in payload.get("candidate_artifacts", [])
            if isinstance(row, dict)
        ]
        self.assertIn("art-task-dev-context-note-r2", ids)
        self.assertNotIn("art-task-dev-context-note-r1", ids)
        self.assertNotIn("art-context-owner-draft-untracked", ids)

    def test_context_summarize_includes_compact_active_inbox_message_cues(self) -> None:
        root = env_store.create_message(from_buddy="pm", to_buddy="dev", content="Need proof asset")
        reply = env_store.create_message(from_buddy="design", to_buddy="dev", content="Screenshot ready", reply_to=root["id"])
        env_store.create_message(from_buddy="dev", to_buddy="pm", content="Sent by dev only")
        env_store.create_message(from_buddy="market", to_buddy="pm", content="Not dev inbox")

        instance_json = self._instance_json()
        payload = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={})
        self.assertTrue(payload.get("ok"), msg=payload)
        cues = payload.get("message_cues")
        self.assertIsInstance(cues, dict, msg=payload)
        assert isinstance(cues, dict)
        rows = cues.get("latest")
        self.assertIsInstance(rows, list, msg=cues)
        assert isinstance(rows, list)
        ids = [row.get("message_id") for row in rows if isinstance(row, dict)]
        self.assertIn(root["id"], ids)
        self.assertIn(reply["id"], ids)
        for row in rows:
            if not isinstance(row, dict):
                continue
            self.assertEqual(row.get("to_buddy"), "dev")
            self.assertNotIn("content", row)
        self.assertGreaterEqual(cues.get("count", 0), 2)

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

    def test_context_summarize_includes_source_workspace_facts_for_dev(self) -> None:
        instance_json = self._instance_json(buddy="dev")
        source_root = self._runtime_path("projects/app")
        source_root.mkdir(parents=True, exist_ok=True)
        (source_root / "README.md").write_text("# App\n", encoding="utf-8")

        payload = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={}, buddy="dev")
        self.assertTrue(payload.get("ok"), msg=payload)
        source = payload.get("source_workspace")
        self.assertIsInstance(source, dict, msg=payload)
        assert isinstance(source, dict)
        self.assertEqual(source.get("active_buddy"), "dev")
        self.assertEqual(source.get("path"), "projects/app")
        self.assertEqual(source.get("access"), "write")
        self.assertIs(source.get("can_write_source"), True)
        self.assertEqual(source.get("state"), "readme_only")
        self.assertEqual(source.get("top_level_entries"), ["README.md"])
        self.assertIs(source.get("top_level_entries_truncated"), False)
        self.assertIn("env_profile", str(source.get("source_of_truth")))
        boundary = str(source.get("permission_boundary", "")).lower()
        self.assertIn("read-only", boundary)
        self.assertIn("does not configure", boundary)
        self.assertNotIn("# App", json.dumps(source, ensure_ascii=True))

    def test_context_summarize_includes_source_workspace_facts_for_non_dev(self) -> None:
        instance_json = self._instance_json(buddy="pm")
        source_root = self._runtime_path("projects/app")
        source_root.mkdir(parents=True, exist_ok=True)
        (source_root / "README.md").write_text("# App\n", encoding="utf-8")

        payload = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={}, buddy="pm")
        self.assertTrue(payload.get("ok"), msg=payload)
        source = payload.get("source_workspace")
        self.assertIsInstance(source, dict, msg=payload)
        assert isinstance(source, dict)
        self.assertEqual(source.get("active_buddy"), "pm")
        self.assertEqual(source.get("access"), "read-only")
        self.assertIs(source.get("can_write_source"), False)
        self.assertEqual(source.get("state"), "readme_only")
        self.assertIn("read-only", str(source.get("permission_boundary", "")).lower())

    def test_context_summarize_accepts_launcher_project_symlink_source_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            shared_root = Path(temp_dir) / "shared-root"
            runtime_workspace = shared_root / "instances" / "inst-dev-context" / "workspace"
            runtime_workspace.mkdir(parents=True, exist_ok=True)
            project_workspace = shared_root / "project" / "workspace"
            shared_source_root = project_workspace / "projects" / "app"
            shared_source_root.mkdir(parents=True, exist_ok=True)
            (shared_source_root / "README.md").write_text("# App\n", encoding="utf-8")

            runtime_source_root = runtime_workspace / "projects" / "app"
            runtime_source_root.parent.mkdir(parents=True, exist_ok=True)
            runtime_source_root.symlink_to(shared_source_root, target_is_directory=True)
            instance_json = self._instance_json(
                buddy="dev",
                workspace_dir=runtime_workspace,
                path=shared_root / "instances" / "inst-dev-context" / "instance.json",
            )

            payload = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={}, buddy="dev")

            self.assertTrue(payload.get("ok"), msg=payload)
            source = payload.get("source_workspace")
            self.assertIsInstance(source, dict, msg=payload)
            assert isinstance(source, dict)
            self.assertEqual(source.get("path"), "projects/app")
            self.assertEqual(source.get("access"), "write")
            self.assertIs(source.get("can_write_source"), True)
            self.assertEqual(source.get("state"), "readme_only")
            self.assertEqual(source.get("top_level_entries"), ["README.md"])

    def test_context_summarize_rejects_source_symlink_outside_project_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            shared_root = Path(temp_dir) / "shared-root"
            runtime_workspace = shared_root / "instances" / "inst-dev-context" / "workspace"
            runtime_workspace.mkdir(parents=True, exist_ok=True)
            project_workspace = shared_root / "project" / "workspace"
            (project_workspace / "projects" / "app").mkdir(parents=True, exist_ok=True)

            outside_source_root = Path(temp_dir) / "outside-source"
            outside_source_root.mkdir(parents=True, exist_ok=True)
            (outside_source_root / "README.md").write_text("# Outside\n", encoding="utf-8")

            runtime_source_root = runtime_workspace / "projects" / "app"
            runtime_source_root.parent.mkdir(parents=True, exist_ok=True)
            runtime_source_root.symlink_to(outside_source_root, target_is_directory=True)
            instance_json = self._instance_json(
                buddy="dev",
                workspace_dir=runtime_workspace,
                path=shared_root / "instances" / "inst-dev-context" / "instance.json",
            )

            payload = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={}, buddy="dev")

            self.assertFalse(payload.get("ok"), msg=payload)
            self.assertEqual((payload.get("error") or {}).get("code"), "E_CONTEXT_SOURCE_WORKSPACE")
            self.assertIn("project workspace", str((payload.get("error") or {}).get("message", "")).lower())

    def test_context_source_workspace_state_classification(self) -> None:
        instance_json = self._instance_json(buddy="dev")
        source_root = self._runtime_path("projects/app")
        cases: list[tuple[str, list[str] | None, str]] = [
            ("missing", None, "missing"),
            ("empty", [], "empty"),
            ("readme_only", ["README.md"], "readme_only"),
            ("package", ["package.json"], "has_source"),
            ("src", ["src/index.ts"], "has_source"),
        ]

        for name, entries, expected_state in cases:
            with self.subTest(case=name):
                if source_root.exists():
                    shutil.rmtree(source_root)
                if entries is not None:
                    source_root.mkdir(parents=True, exist_ok=True)
                    for rel in entries:
                        entry_path = source_root / rel
                        entry_path.parent.mkdir(parents=True, exist_ok=True)
                        entry_path.write_text("// seed\n", encoding="utf-8")

                payload = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={}, buddy="dev")
                self.assertTrue(payload.get("ok"), msg=payload)
                source = payload.get("source_workspace")
                self.assertIsInstance(source, dict, msg=payload)
                assert isinstance(source, dict)
                self.assertEqual(source.get("state"), expected_state)
                self.assertIsInstance(source.get("top_level_entries"), list)
                self.assertNotIn("// seed", json.dumps(source, ensure_ascii=True))

    def test_context_list_sources_includes_source_workspace_descriptor(self) -> None:
        instance_json = self._instance_json(buddy="dev")
        listed = self._dispatch(instance_json=instance_json, tool="context", action="list_sources", args={}, buddy="dev")
        self.assertTrue(listed.get("ok"), msg=listed)
        sources = listed.get("sources")
        self.assertIsInstance(sources, dict, msg=listed)
        assert isinstance(sources, dict)
        source_workspace = sources.get("source_workspace")
        self.assertIsInstance(source_workspace, dict, msg=sources)
        assert isinstance(source_workspace, dict)
        self.assertIn("read-only", str(source_workspace.get("scope", "")).lower())
        self.assertIn("env profile", str(source_workspace.get("source_of_truth", "")).lower())
        self.assertFalse(source_workspace.get("mutates_product_state"))
        self.assertFalse(source_workspace.get("grants_write_authority"))
        self.assertFalse(source_workspace.get("configures_source_root"))

    def test_context_get_metadata_and_source_workspace_semantics(self) -> None:
        instance_json = self._instance_json(buddy="dev")
        source_root = self._runtime_path("projects/app")
        source_root.mkdir(parents=True, exist_ok=True)
        (source_root / "README.md").write_text("# App\n", encoding="utf-8")

        payload = self._dispatch(instance_json=instance_json, tool="context", action="get", args={}, buddy="dev")
        self.assertTrue(payload.get("ok"), msg=payload)
        source = payload.get("source_workspace")
        self.assertIsInstance(source, dict, msg=payload)
        assert isinstance(source, dict)
        self.assertEqual(source.get("path"), "projects/app")
        self.assertEqual(source.get("state"), "readme_only")
        self.assertTrue(str(source.get("resolved_path", "")).endswith("/projects/app"))

        operation_semantics = payload.get("operation_semantics")
        self.assertIsInstance(operation_semantics, dict, msg=payload)
        assert isinstance(operation_semantics, dict)
        self.assertIn("source_workspace", operation_semantics["context.get"]["returns"])
        self.assertIn("source_workspace", operation_semantics["context.summarize"]["returns"])

        context_catalog = payload.get("tool_catalog", {}).get("context", {})
        self.assertIsInstance(context_catalog, dict, msg=payload)
        assert isinstance(context_catalog, dict)
        action_semantics = context_catalog.get("action_semantics", {})
        self.assertIsInstance(action_semantics, dict, msg=context_catalog)
        assert isinstance(action_semantics, dict)
        summarize_description = str(action_semantics.get("summarize", {}).get("plain_description", "")).lower()
        self.assertIn("source", summarize_description)
        self.assertIn("read-only", summarize_description)

    def test_context_source_workspace_uses_profile_not_agents_text_and_profile_failure_is_explicit(self) -> None:
        instance_json = self._instance_json(buddy="dev")
        source_root = self._runtime_path("projects/app")
        source_root.mkdir(parents=True, exist_ok=True)
        (source_root / "README.md").write_text("# App\n", encoding="utf-8")
        (self._runtime_path("AGENTS.md")).write_text(
            "# wrong facts\nprojects/app is missing and project.access=read-only\n",
            encoding="utf-8",
        )

        payload = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={}, buddy="dev")
        self.assertTrue(payload.get("ok"), msg=payload)
        source = payload.get("source_workspace")
        self.assertIsInstance(source, dict, msg=payload)
        assert isinstance(source, dict)
        self.assertEqual(source.get("path"), "projects/app")
        self.assertEqual(source.get("access"), "write")
        self.assertIs(source.get("can_write_source"), True)

        with patch("env.tools.context._impl.env_profiles.require_env_profile", side_effect=RuntimeError("boom")):
            rejected = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={}, buddy="dev")
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_CONTEXT_SOURCE_WORKSPACE")
        self.assertNotEqual(((rejected.get("source_workspace") or {}).get("state")), "missing")

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
        tracks = filtered.get("tracks")
        artifacts = filtered.get("artifact_summaries")
        self.assertIsInstance(tasks, list, msg=filtered)
        self.assertIsInstance(tracks, list, msg=filtered)
        self.assertIsInstance(artifacts, list, msg=filtered)
        assert isinstance(tasks, list)
        assert isinstance(tracks, list)
        assert isinstance(artifacts, list)
        self.assertEqual({row.get("id") for row in tasks if isinstance(row, dict)}, {"task-dev-context"})
        self.assertEqual({row.get("id") for row in tracks if isinstance(row, dict)}, {"track-context-active"})
        self.assertEqual({row.get("artifact_id") for row in artifacts if isinstance(row, dict)}, {"art-task-dev-context-note-r2"})

    def test_context_rejects_unknown_payload_field(self) -> None:
        instance_json = self._instance_json()
        rejected = self._dispatch(instance_json=instance_json, tool="context", action="get", args={"unknown": 1})
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_CONTEXT_PAYLOAD")


if __name__ == "__main__":
    unittest.main()
