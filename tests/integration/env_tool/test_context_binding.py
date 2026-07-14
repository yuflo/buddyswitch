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

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
SCRIPTS = ROOT / "scripts"

import env_legacy_store as env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from env.domain import task_sys  # noqa: E402
from env.services import messages as message_service  # noqa: E402
from env.tool_runtime import context as runtime_context  # noqa: E402
from env.tool_runtime import registry as tool_registry  # noqa: E402
from tests.support.runtime import RuntimeWorkspaceTestCase  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"
_EXPECTED_TOOLS = {"task_sys", "track", "artifact", "context", "evidence", "search", "message"}


class ContextBindingEnvToolTests(RuntimeWorkspaceTestCase):
    def test_tool_context_exposes_only_explicit_runtime_capabilities(self) -> None:
        profile = runtime_context.ActorIdentityProfile(
            identity=runtime_context.IdentityRef(id="act-dev-capability", type="actor"),
            role_id="dev",
        )
        context = runtime_context.ToolContext.from_identity_profile(
            actor_identity_profile=profile,
            instance_json=self.runtime_root / "instances" / "act-dev-capability" / "instance.json",
            instance_payload={"actor_id": "act-dev-capability", "role": "dev"},
            manifest={},
        )

        self.assertIsInstance(context.actor_directory, runtime_context.ActorDirectoryAccess)
        self.assertIsInstance(context.signal_delivery, runtime_context.SignalDeliveryAccess)
        self.assertIsInstance(context.task_sys_runtime, runtime_context.TaskSysRuntimeAccess)
        self.assertIsInstance(context.im_actor_delivery, runtime_context.ImActorDeliveryAccess)
        self.assertFalse(hasattr(context, "daemon"))
        self.assertFalse(hasattr(runtime_context, "Daemon" + "Access"))

    def _write_json(self, path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def _seed_task_sys_task(
        self,
        *,
        actor_id: str,
        role: str,
        source_type: str,
        track_id: str | None = None,
    ) -> str:
        source_ref: dict[str, object] = {"fixture": source_type}
        if track_id is not None:
            source_ref["track_id"] = track_id
        result = task_sys.ingest(
            {
                "source": {"type": source_type, "ref": source_ref},
                "actor_target": {"actor_id": actor_id, "role_id": role},
                "context": {"fixture": "context binding"},
            },
        )
        task_id = str(result["task_id"])
        task_sys.record_task_analysis_update(
            task_id,
            {
                "task_desc": "Context binding",
                "task_relation": {"kind": "independent", "target_task_id": None},
            },
        )
        return task_id

    def _seed_legacy_shared_task(self) -> None:
        self._write_json(
            self._state_path("buddyswitch/objects" + "/tasks/task-legacy-shared.json"),
            {
                "id": "task-legacy-shared",
                "role": "dev",
                "title": "Legacy shared task",
                "status": "active",
                "track_id": "track-context-active",
                "summary": "legacy",
                "created_at": "2026-05-23T12:00:00+08:00",
                "updated_at": "2026-05-23T12:00:00+08:00",
            },
        )

    def _instance_json(
        self,
        *,
        actor_id: str = "act-dev-context",
        role: str = "dev",
        status: str = "active",
        workspace_dir: Path | None = None,
        path: Path | None = None,
    ) -> Path:
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        instance_root = self._runtime_path(f"instances/{actor_id}")
        instance_json_path = path if path is not None else instance_root / "instance.json"
        resolved_workspace_dir = workspace_dir if workspace_dir is not None else self.runtime_root
        resolved_workspace_dir.mkdir(parents=True, exist_ok=True)
        payload: dict[str, object] = {
            "actor_id": actor_id,
            "role": role,
            "status": status,
            "instance_root": str(instance_root),
            "workspace_dir": str(resolved_workspace_dir),
            "browser_port": None,
            "updated_at": "2026-05-15T00:00:00Z",
        }
        instance_json_path.parent.mkdir(parents=True, exist_ok=True)
        instance_json_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2)
            + "\n",
            encoding="utf-8",
        )
        self._seed_active_task_for_instance(
            instance_json=instance_json_path,
            role=role,
            actor_id=actor_id,
            task_slug=f"{role}-context-env",
        )
        return instance_json_path

    def _dispatch(self, *, instance_json: Path, tool: str, action: str, args: dict[str, object], actor_id: str = "act-dev-context", role: str = "dev") -> dict[str, object]:
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        request = {
            "protocol": PROTOCOL,
            "request_id": f"req-context-{uuid.uuid4().hex}",
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
        actor_id = self._runtime_actor_id(role="dev", label="act-dev-context")
        env_store.create_track(
            "track-context-active",
            "Context Track",
            owner_identity=actor_id,
            outcome="Context outcome",
            now={"next": "seed", "blocker": None},
        )
        self.context_task_id = self._seed_task_sys_task(
            actor_id=actor_id,
            role="dev",
            source_type="test.context.active",
            track_id="track-context-active",
        )
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
            from_role="dev",
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
            from_role="dev",
            summary="artifact summary v2",
        )

        env_store.create_track(
            "track-context-archived",
            "Archived Track",
            owner_identity=self._runtime_actor_id(role="pm", label="act-pm-context"),
            outcome="Archived outcome",
            now={"next": "archived", "blocker": None},
        )
        self.archived_task_id = self._seed_task_sys_task(
            actor_id=actor_id,
            role="dev",
            source_type="test.context.archived",
            track_id="track-context-archived",
        )
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
            from_role="dev",
            summary="archived",
        )
        env_store.update_track(
            "track-context-archived",
            {"archived_at": "2026-05-18T10:00:00+08:00"},
        )
        self._seed_legacy_shared_task()

    def test_context_summarize_exposes_compact_tool_affordances(self) -> None:
        instance_json = self._instance_json()
        summary = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={})
        self.assertTrue(summary.get("ok"), msg=summary)

        affordances = summary.get("tool_affordances")
        self.assertIsInstance(affordances, dict, msg=summary)
        assert isinstance(affordances, dict)
        self.assertEqual(
            affordances,
            tool_registry.compact_tool_affordances(exclude_tools={"actor_private"}),
        )
        self.assertEqual(set(affordances), _EXPECTED_TOOLS)
        self.assertNotIn("handoff", affordances)
        dumped = json.dumps(affordances, ensure_ascii=True)
        self.assertNotIn("input_schemas", dumped)
        self.assertNotIn("payload_fields", dumped)
        self.assertNotIn("action_semantics", dumped)
        self.assertNotIn('"properties"', dumped)
        for tool_name in ("track", "artifact", "task_sys", "context"):
            with self.subTest(tool=tool_name):
                compact = affordances.get(tool_name)
                self.assertIsInstance(compact, dict, msg=summary)
                assert isinstance(compact, dict)
                self.assertIsInstance(compact.get("object_model"), str, msg=compact)
                self.assertIsInstance(compact.get("capability"), str, msg=compact)
                self.assertIsInstance(compact.get("returns"), str, msg=compact)
                self.assertIsInstance(compact.get("state_effect"), str, msg=compact)
                self.assertIsInstance(compact.get("when_to_use"), list, msg=compact)
                self.assertIsInstance(compact.get("when_not_to_use"), list, msg=compact)

    def test_context_summarize_candidate_keys_match_next_action_guidance(self) -> None:
        self._seed_context_state()
        instance_json = self._instance_json()
        payload = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={})
        self.assertTrue(payload.get("ok"), msg=payload)

        for key in ("candidate_tracks", "candidate_artifacts", "candidate_tasks"):
            self.assertIn(key, payload, msg=payload)
            self.assertIsInstance(payload.get(key), list, msg=payload)
        removed_candidate_section = "candidate_" + "requests"
        self.assertNotIn(removed_candidate_section, payload, msg=payload)

        key_expectations = {
            "candidate_tracks": "track_id",
            "candidate_artifacts": "artifact_id",
            "candidate_tasks": "task_id",
        }
        for section, id_key in key_expectations.items():
            for row in payload.get(section, []):
                if not isinstance(row, dict):
                    continue
                with self.subTest(section=section):
                    self.assertIn(id_key, row, msg=row)
                    self.assertNotIn("body", row, msg=row)

        next_text = " ".join(str(row) for row in payload.get("allowed_next_actions", [])).lower()
        mentioned_groups = {
            key
            for word, key in (
                ("tracks", "candidate_tracks"),
                ("artifacts", "candidate_artifacts"),
                ("tasks", "candidate_tasks"),
            )
            if word in next_text
        }
        self.assertTrue(mentioned_groups.issubset(set(key_expectations)), msg=payload)

    def test_context_summarize_includes_generated_capability_snapshot(self) -> None:
        instance_json = self._instance_json(role="dev")
        payload = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={}, role="dev")
        self.assertTrue(payload.get("ok"), msg=payload)

        snapshot = payload.get("capability_snapshot")
        self.assertIsInstance(snapshot, dict, msg=payload)
        assert isinstance(snapshot, dict)
        old_keys = (
            "role_" + "authority_" + "source",
            "allowed_" + "actions",
            "denied_" + "actions",
            "denied_" + "action_" + "details",
            "allowed_" + "action_" + "permissions",
        )
        for old_key in old_keys:
            self.assertNotIn(old_key, snapshot)
        preview = snapshot.get("runtime_policy_preview")
        self.assertIsInstance(preview, dict, msg=snapshot)
        assert isinstance(preview, dict)
        self.assertEqual(preview.get("active_role"), "dev")
        self.assertEqual(preview.get("source"), "env.tool role-action policy")
        self.assertIs(preview.get("not_authorization_boundary"), True)
        self.assertIs(preview.get("not_execution_result"), True)
        self.assertIn("track.list", preview.get("available_actions", []))
        self.assertIn("artifact.create_revision", preview.get("available_actions", []))
        self.assertIn("message.send", preview.get("available_actions", []))
        self.assertIn("track.create", preview.get("available_actions", []))
        self.assertIn("track.update_requirements", preview.get("available_actions", []))
        self.assertIn("track.update_status", preview.get("available_actions", []))
        self.assertIn("track.archive", preview.get("available_actions", []))
        self.assertIn("track.resolve_comment_thread", preview.get("available_actions", []))
        self.assertEqual(preview.get("restricted_actions"), [])
        self.assertEqual(preview.get("restricted_action_details"), {})
        self.assertNotIn("object_" + "permissions", json.dumps(snapshot, ensure_ascii=True))
        self.assertIn("Task Sys frames", str(snapshot.get("task_visibility")))
        artifact_create = tool_registry.operation_semantics()["artifact.create_revision"]
        self.assertEqual(
            snapshot.get("artifact_publication_path"),
            " ".join(
                [
                    str(artifact_create["success_effect"]),
                    "Does not write:",
                    ", ".join(str(row) for row in artifact_create["does_not_write"]),
                ]
            ),
        )
        self.assertIn("track.add_material", str(snapshot.get("artifact_publication_path")))
        self.assertIn("track-scoped", str(snapshot.get("track_comment_support")).lower())
        self.assertIn("browser", str(snapshot.get("search_boundary")).lower())

    def test_context_candidate_tracks_use_owner_identity_and_exact_actor_relation(self) -> None:
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
            self.assertIn("owner_identity_id", row)
            self.assertNotIn("owner_identity", row)
            self.assertNotIn("owner_role", row)
            self.assertNotIn("created_by_identity", row)
            self.assertIn(row.get("current_identity_relation"), {"owner", "collaborator"})
            self.assertIn(row.get("active_role_relation"), {"owner", "collaborator"})
            if row.get("track_id") == "track-context-active":
                self.assertEqual(row.get("current_identity_relation"), "owner")
            self.assertNotIn("current_role", row)
            self.assertNotIn("next_role", row)
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
        self.assertIn(self.context_task_id, task_ids)
        self.assertNotIn(self.archived_task_id, task_ids)

    def test_context_candidate_tasks_use_task_sys_metadata_and_ignore_legacy_shared_tasks(self) -> None:
        self._seed_context_state()
        instance_json = self._instance_json()

        payload = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={})
        self.assertTrue(payload.get("ok"), msg=payload)

        candidate_tasks = payload.get("candidate_tasks")
        self.assertIsInstance(candidate_tasks, list, msg=payload)
        assert isinstance(candidate_tasks, list)
        task_ids = {row.get("task_id") for row in candidate_tasks if isinstance(row, dict)}
        self.assertIn(self.context_task_id, task_ids)
        self.assertNotIn("task-legacy-shared", task_ids)

        candidate_task = next(row for row in candidate_tasks if isinstance(row, dict) and row.get("task_id") == self.context_task_id)
        self.assertEqual(candidate_task.get("source_type"), "test.context.active")
        self.assertEqual(candidate_task.get("status"), "in_progress")
        self.assertEqual(candidate_task.get("task_desc"), "Context binding")
        self.assertEqual(candidate_task.get("task_relation"), {"kind": "independent", "target_task_id": None})
        self.assertEqual(candidate_task.get("execution", {}).get("processor"), "side")
        self.assertNotIn("active_processor", candidate_task)

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
        self.assertNotIn("status", draft)

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

    def test_context_candidates_show_only_current_identity_private_drafts(self) -> None:
        owner_identity = "act-dev-context-draft-owner"
        other_actor = "act-dev-context-draft-other"
        owner_instance = self._instance_json(actor_id=owner_identity, role="dev")
        other_instance = self._instance_json(actor_id=other_actor, role="dev")

        own_draft = self._dispatch(
            instance_json=owner_instance,
            actor_id=owner_identity,
            role="dev",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-context-own-private-draft",
                "title": "Own private draft",
                "summary": "active actor draft",
                "template": "note",
                "body": "private body",
            },
        )
        self.assertTrue(own_draft.get("ok"), msg=own_draft)
        other_draft = self._dispatch(
            instance_json=other_instance,
            actor_id=other_actor,
            role="dev",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-context-other-private-draft",
                "title": "Other private draft",
                "summary": "same role other actor draft",
                "template": "note",
                "body": "other private body",
            },
        )
        self.assertTrue(other_draft.get("ok"), msg=other_draft)

        owner_summary = self._dispatch(
            instance_json=owner_instance,
            actor_id=owner_identity,
            role="dev",
            tool="context",
            action="summarize",
            args={},
        )
        self.assertTrue(owner_summary.get("ok"), msg=owner_summary)
        owner_ids = {
            row.get("artifact_id")
            for row in owner_summary.get("candidate_artifacts", [])
            if isinstance(row, dict)
        }
        self.assertIn("art-context-own-private-draft", owner_ids)
        self.assertNotIn("art-context-other-private-draft", owner_ids)

        owner_full = self._dispatch(
            instance_json=owner_instance,
            actor_id=owner_identity,
            role="dev",
            tool="context",
            action="get",
            args={},
        )
        self.assertTrue(owner_full.get("ok"), msg=owner_full)
        full_ids = {
            row.get("artifact_id")
            for row in owner_full.get("candidate_artifacts", [])
            if isinstance(row, dict)
        }
        self.assertIn("art-context-own-private-draft", full_ids)
        self.assertNotIn("art-context-other-private-draft", full_ids)

    def test_context_summarize_includes_compact_identity_inbox_message_cues(self) -> None:
        dev = {"role_id": "dev", "actor_id": self._runtime_actor_id(role="dev", label="act-dev-context")}
        pm = {"role_id": "pm", "actor_id": self._runtime_actor_id(role="pm", label="act-pm-context")}
        design = {"role_id": "design", "actor_id": self._runtime_actor_id(role="design", label="act-design-context")}
        market = {"role_id": "market", "actor_id": self._runtime_actor_id(role="market", label="act-market-context")}
        dev_identity = {"id": dev["actor_id"], "type": "actor"}
        pm_identity = {"id": pm["actor_id"], "type": "actor"}
        design_identity = {"id": design["actor_id"], "type": "actor"}
        market_identity = {"id": market["actor_id"], "type": "actor"}
        root = message_service.send_im_message(
            sender_identity=pm_identity,
            target_identity=dev_identity,
            content="Need proof asset",
        )
        reply = message_service.send_im_message(
            sender_identity=design_identity,
            target_identity=dev_identity,
            content="Screenshot ready",
        )
        message_service.send_im_message(
            sender_identity=dev_identity,
            target_identity=pm_identity,
            content="Sent by dev only",
        )
        message_service.send_im_message(
            sender_identity=market_identity,
            target_identity=pm_identity,
            content="Not dev inbox",
        )

        instance_json = self._instance_json()
        payload = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={})
        self.assertTrue(payload.get("ok"), msg=payload)
        self.assertEqual(payload.get("current_identity"), {"id": dev["actor_id"], "type": "actor"})
        self.assertNotIn("actor_address", payload)
        cues = payload.get("message_cues")
        self.assertIsInstance(cues, dict, msg=payload)
        assert isinstance(cues, dict)
        self.assertEqual(cues.get("inbox_source_of_truth"), "message.list")
        self.assertEqual(cues.get("conversation_source_of_truth"), "message.conversation")
        self.assertIn("target identities", cues.get("target_discovery", ""))
        rows = cues.get("latest_inbox")
        self.assertIsInstance(rows, list, msg=cues)
        assert isinstance(rows, list)
        ids = [row.get("message_id") for row in rows if isinstance(row, dict)]
        self.assertIn(root["message"]["id"], ids)
        self.assertIn(reply["message"]["id"], ids)
        for row in rows:
            if not isinstance(row, dict):
                continue
            target_identity = row.get("target_identity")
            sender_identity = row.get("sender_identity")
            self.assertIsInstance(target_identity, dict)
            self.assertIsInstance(sender_identity, dict)
            assert isinstance(target_identity, dict)
            assert isinstance(sender_identity, dict)
            self.assertEqual(target_identity.get("id"), dev["actor_id"])
            self.assertEqual(target_identity.get("type"), "actor")
            self.assertIn(sender_identity.get("id"), [pm["actor_id"], design["actor_id"]])
            self.assertEqual(sender_identity.get("type"), "actor")
            self.assertEqual(row.get("visible_to_identity_id"), dev["actor_id"])
            self.assertNotIn("from_actor_address", row)
            self.assertNotIn("to_actor_address", row)
            self.assertNotIn("from_identity_id", row)
            self.assertNotIn("to_identity_id", row)
            self.assertNotIn("content", row)
        self.assertGreaterEqual(cues.get("count", 0), 2)
        message_source = payload.get("context_sources", {}).get("messages", {})
        self.assertIn("message.list", str(message_source.get("source_of_truth")))
        self.assertIn("message.conversation", str(message_source.get("source_of_truth")))

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
        self.assertIn("tasks", sources)
        task_source = sources["tasks"]
        task_source_text = json.dumps(task_source, ensure_ascii=True, sort_keys=True)
        self.assertIn("task_sys.list", task_source_text)
        self.assertIn("task_sys.get", task_source_text)
        self.assertIn("task_sys.close", task_source_text)
        self.assertIn("task_sys.need_parent", task_source_text)
        self.assertNotIn("checkpoint_update", task_source_text)

    def test_context_outputs_writable_surfaces_without_actor_private_tool_methods(self) -> None:
        instance_json = self._instance_json(role="pm")
        listed = self._dispatch(instance_json=instance_json, tool="context", action="list_sources", args={}, role="pm")
        self.assertTrue(listed.get("ok"), msg=listed)
        sources = listed.get("sources")
        self.assertIsInstance(sources, dict, msg=listed)
        assert isinstance(sources, dict)
        writable_surfaces_source = sources.get("writable_surfaces")
        self.assertIsInstance(writable_surfaces_source, dict, msg=sources)
        assert isinstance(writable_surfaces_source, dict)
        self.assertFalse(writable_surfaces_source.get("mutates_product_state"))
        self.assertFalse(writable_surfaces_source.get("grants_write_authority"))

        summarized = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={}, role="pm")
        self.assertTrue(summarized.get("ok"), msg=summarized)
        surfaces = summarized.get("writable_surfaces")
        self.assertIsInstance(surfaces, dict, msg=summarized)
        assert isinstance(surfaces, dict)
        persistent = surfaces.get("persistent_files")
        self.assertIsInstance(persistent, dict, msg=surfaces)
        assert isinstance(persistent, dict)
        self.assertEqual(persistent.get("env"), "BUDDYSWITCH_ACTOR_PRIVATE_DIR")
        self.assertEqual(persistent.get("workspace_relative_root"), "private")
        self.assertFalse(persistent.get("mutates_product_state"))
        temporary = surfaces.get("temporary_files")
        self.assertIsInstance(temporary, dict, msg=surfaces)
        assert isinstance(temporary, dict)
        self.assertEqual(temporary.get("env"), "BUDDYSWITCH_INSTANCE_TMP")

        self.assertIn("actor_private", json.dumps(summarized, ensure_ascii=True))
        retired_tokens = (
            "actor_private_desc",
            "describe_capability",
            "_".join(("write", "private", "text")),
            "_".join(("write", "private", "binary")),
            "_".join(("logical", "name", "policy")),
        )
        for payload in (listed, summarized):
            packed = json.dumps(payload, ensure_ascii=True)
            self.assertNotIn("buddyswitch/local/actor_private", packed)
            self.assertNotIn("state/buddyswitch/local/actor_private", packed)
            self.assertNotIn("buddyswitch/content/actor_private", packed)
            self.assertNotIn("/private/tmp", packed)
            self.assertNotIn("/tmp/ai-calendar", packed)
            for retired in retired_tokens:
                self.assertNotIn(retired, packed)

    def test_context_summarize_includes_source_workspace_facts_for_dev(self) -> None:
        instance_json = self._instance_json(role="dev")
        source_root = self._runtime_path("projects/app")
        source_root.mkdir(parents=True, exist_ok=True)
        (source_root / "README.md").write_text("# App\n", encoding="utf-8")

        payload = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={}, role="dev")
        self.assertTrue(payload.get("ok"), msg=payload)
        source = payload.get("source_workspace")
        self.assertIsInstance(source, dict, msg=payload)
        assert isinstance(source, dict)
        self.assertEqual(source.get("active_role"), "dev")
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
        instance_json = self._instance_json(role="pm")
        source_root = self._runtime_path("projects/app")
        source_root.mkdir(parents=True, exist_ok=True)
        (source_root / "README.md").write_text("# App\n", encoding="utf-8")

        payload = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={}, role="pm")
        self.assertTrue(payload.get("ok"), msg=payload)
        source = payload.get("source_workspace")
        self.assertIsInstance(source, dict, msg=payload)
        assert isinstance(source, dict)
        self.assertEqual(source.get("active_role"), "pm")
        self.assertEqual(source.get("access"), "read-only")
        self.assertIs(source.get("can_write_source"), False)
        self.assertEqual(source.get("state"), "readme_only")
        self.assertIn("read-only", str(source.get("permission_boundary", "")).lower())

    def test_context_summarize_accepts_launcher_project_symlink_source_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            shared_root = Path(temp_dir) / "shared-root"
            actor_id = self._runtime_actor_id(role="dev", label="act-dev-context")
            runtime_workspace = shared_root / "instances" / actor_id / "workspace"
            runtime_workspace.mkdir(parents=True, exist_ok=True)
            project_workspace = shared_root / "project" / "workspace"
            shared_source_root = project_workspace / "projects" / "app"
            shared_source_root.mkdir(parents=True, exist_ok=True)
            (shared_source_root / "README.md").write_text("# App\n", encoding="utf-8")

            runtime_source_root = runtime_workspace / "projects" / "app"
            runtime_source_root.parent.mkdir(parents=True, exist_ok=True)
            runtime_source_root.symlink_to(shared_source_root, target_is_directory=True)
            instance_json = self._instance_json(
                role="dev",
                workspace_dir=runtime_workspace,
                path=shared_root / "instances" / actor_id / "instance.json",
            )

            payload = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={}, role="dev")

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
            actor_id = self._runtime_actor_id(role="dev", label="act-dev-context")
            runtime_workspace = shared_root / "instances" / actor_id / "workspace"
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
                role="dev",
                workspace_dir=runtime_workspace,
                path=shared_root / "instances" / actor_id / "instance.json",
            )

            payload = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={}, role="dev")

            self.assertFalse(payload.get("ok"), msg=payload)
            self.assertEqual((payload.get("error") or {}).get("code"), "E_CONTEXT_SOURCE_WORKSPACE")
            self.assertIn("project workspace", str((payload.get("error") or {}).get("message", "")).lower())

    def test_context_source_workspace_state_classification(self) -> None:
        instance_json = self._instance_json(role="dev")
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

                payload = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={}, role="dev")
                self.assertTrue(payload.get("ok"), msg=payload)
                source = payload.get("source_workspace")
                self.assertIsInstance(source, dict, msg=payload)
                assert isinstance(source, dict)
                self.assertEqual(source.get("state"), expected_state)
                self.assertIsInstance(source.get("top_level_entries"), list)
                self.assertNotIn("// seed", json.dumps(source, ensure_ascii=True))

    def test_context_list_sources_includes_source_workspace_descriptor(self) -> None:
        instance_json = self._instance_json(role="dev")
        listed = self._dispatch(instance_json=instance_json, tool="context", action="list_sources", args={}, role="dev")
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
        instance_json = self._instance_json(role="dev")
        source_root = self._runtime_path("projects/app")
        source_root.mkdir(parents=True, exist_ok=True)
        (source_root / "README.md").write_text("# App\n", encoding="utf-8")

        payload = self._dispatch(instance_json=instance_json, tool="context", action="get", args={}, role="dev")
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
        snapshot = payload.get("capability_snapshot")
        self.assertIsInstance(snapshot, dict, msg=payload)
        assert isinstance(snapshot, dict)
        old_keys = (
            "role_" + "authority_" + "source",
            "allowed_" + "actions",
            "denied_" + "actions",
            "denied_" + "action_" + "details",
            "allowed_" + "action_" + "permissions",
        )
        for old_key in old_keys:
            self.assertNotIn(old_key, snapshot)
        preview = snapshot.get("runtime_policy_preview")
        self.assertIsInstance(preview, dict, msg=snapshot)
        assert isinstance(preview, dict)
        self.assertIn("track.resolve_comment_thread", preview.get("available_actions", []))
        self.assertEqual(preview.get("restricted_action_details"), {})
        self.assertNotIn("object_" + "permissions", json.dumps(payload, ensure_ascii=True))
        self.assertIn("source_workspace", operation_semantics["context.get"]["returns"])
        self.assertIn("writable_surfaces", operation_semantics["context.get"]["returns"])
        self.assertIn("source_workspace", operation_semantics["context.summarize"]["returns"])
        self.assertIn("writable_surfaces", operation_semantics["context.summarize"]["returns"])
        self.assertNotIn("actor_private.desc", operation_semantics)
        self.assertNotIn("actor_private.write", operation_semantics)
        for key in ("context.get", "context.summarize"):
            with self.subTest(operation=key):
                self.assertIn("reads", operation_semantics[key])
                self.assertIn("writes", operation_semantics[key])
                self.assertIn("does_not_write", operation_semantics[key])
                self.assertIn("visibility", operation_semantics[key])
                self.assertIn("durability", operation_semantics[key])
                self.assertIn("result_content_level", operation_semantics[key])
                self.assertIn("success_effect", operation_semantics[key])
                self.assertIn("failure_state_guarantee", operation_semantics[key])

        context_catalog = payload.get("tool_catalog", {}).get("context", {})
        self.assertIsInstance(context_catalog, dict, msg=payload)
        assert isinstance(context_catalog, dict)
        self.assertNotIn("actor_private", payload.get("tool_catalog", {}))
        action_semantics = context_catalog.get("action_semantics", {})
        self.assertIsInstance(action_semantics, dict, msg=context_catalog)
        assert isinstance(action_semantics, dict)
        summarize_description = str(action_semantics.get("summarize", {}).get("plain_description", "")).lower()
        self.assertIn("source", summarize_description)
        self.assertIn("read-only", summarize_description)

        track_catalog = payload.get("tool_catalog", {}).get("track", {})
        track_model = str(track_catalog.get("object_model", "")).lower()
        self.assertIn("owner_identity_id", track_model)
        self.assertIn("collaboration facts", track_model)
        track_create = track_catalog.get("action_semantics", {}).get("create", {})
        self.assertIn("visibility", track_create)
        self.assertIn("failure_state_guarantee", track_create)
        artifact_catalog = payload.get("tool_catalog", {}).get("artifact", {})
        self.assertIsInstance(artifact_catalog, dict, msg=payload)
        assert isinstance(artifact_catalog, dict)
        artifact_ops = artifact_catalog.get("operations")
        self.assertIsInstance(artifact_ops, list, msg=artifact_catalog)
        assert isinstance(artifact_ops, list)
        self.assertIn("attach_file", artifact_ops)
        self.assertIn("list_attachments", artifact_ops)
        self.assertIn("get_attachment", artifact_ops)
        self.assertIn("artifact.attach_file", operation_semantics)
        self.assertIn("artifact.list_attachments", operation_semantics)
        self.assertIn("artifact.get_attachment", operation_semantics)

    def test_context_source_workspace_uses_profile_not_agents_text_and_profile_failure_is_explicit(self) -> None:
        instance_json = self._instance_json(role="dev")
        source_root = self._runtime_path("projects/app")
        source_root.mkdir(parents=True, exist_ok=True)
        (source_root / "README.md").write_text("# App\n", encoding="utf-8")
        (self._runtime_path("AGENTS.md")).write_text(
            "# wrong facts\nprojects/app is missing and project.access=read-only\n",
            encoding="utf-8",
        )

        payload = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={}, role="dev")
        self.assertTrue(payload.get("ok"), msg=payload)
        source = payload.get("source_workspace")
        self.assertIsInstance(source, dict, msg=payload)
        assert isinstance(source, dict)
        self.assertEqual(source.get("path"), "projects/app")
        self.assertEqual(source.get("access"), "write")
        self.assertIs(source.get("can_write_source"), True)

        with patch("env.tools.context._impl.env_profiles.require_env_profile", side_effect=RuntimeError("boom")):
            rejected = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={}, role="dev")
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
            args={"track_id": "track-context-active", "task_id": self.context_task_id, "limit": 5},
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
        self.assertEqual({row.get("id") for row in tasks if isinstance(row, dict)}, {self.context_task_id})
        self.assertEqual({row.get("id") for row in tracks if isinstance(row, dict)}, {"track-context-active"})
        self.assertEqual({row.get("artifact_id") for row in artifacts if isinstance(row, dict)}, {"art-task-dev-context-note-r2"})

    def test_context_rejects_unknown_payload_field(self) -> None:
        instance_json = self._instance_json()
        rejected = self._dispatch(instance_json=instance_json, tool="context", action="get", args={"unknown": 1})
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_CONTEXT_PAYLOAD")
