#!/usr/bin/env python3
"""Runless context env.tool integration tests."""

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

import env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"
_RETIRED_BUDDYBOX_FILE_ROWS_FIELD = "buddybox_" + "files"
_RETIRED_BUDDYBOX_READINESS_FIELD = "has_" + "buddybox_" + "files"


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
        env_store.create_track("track-context-runless", "Context Track", current_buddy="pm", next_buddy="dev")
        env_store.create_task("task-dev-context", "Context Task", buddy="dev", track_id="track-context-runless", summary="seed")
        env_store.create_artifact(
            artifact_id="art-task-dev-context-note-r1",
            title="Context Artifact",
            buddy="dev",
            kind="track-note",
            task_id="task-dev-context",
            summary="artifact summary",
            content={"body": "artifact body"},
            created_by="dev",
            source_refs=[{"type": "note", "label": "context"}],
        )
        buddybox = env_store.BUDDYBOX_LOCAL_DIR / "dev" / "notes"
        buddybox.mkdir(parents=True, exist_ok=True)
        (buddybox / "context.txt").write_text("hello\n", encoding="utf-8")

    def test_context_summarize_is_runless_without_prepare_or_binding_fields(self) -> None:
        self._seed_context_state()
        instance_json = self._instance_json()

        summary = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={})
        self.assertTrue(summary.get("ok"), msg=summary)
        self.assertEqual(summary.get("action"), "context.summarize")
        self.assertNotIn("run_envelope", summary)
        self.assertNotIn("persist_command_hint", summary)
        self.assertNotIn("current_binding", summary)
        self.assertNotIn("current_task_id", summary)
        self.assertNotIn("current_track_id", summary)
        decision_surface = summary.get("decision_surface")
        self.assertIsInstance(decision_surface, dict, msg=summary)
        assert isinstance(decision_surface, dict)
        self.assertEqual(((decision_surface.get("binding_state") or {}).get("state")), "runless")
        self.assertIn("buddybox_desc", summary)
        self.assertNotIn(_RETIRED_BUDDYBOX_FILE_ROWS_FIELD, summary)

    def test_context_summarize_exposes_compact_tool_affordances(self) -> None:
        instance_json = self._instance_json()
        summary = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={})
        self.assertTrue(summary.get("ok"), msg=summary)

        affordances = summary.get("tool_affordances")
        self.assertIsInstance(affordances, dict, msg=summary)
        assert isinstance(affordances, dict)
        self.assertEqual(set(affordances), {"buddybox", "artifact"})

        buddybox = affordances.get("buddybox")
        self.assertIsInstance(buddybox, dict, msg=affordances)
        assert isinstance(buddybox, dict)
        buddybox_use_for = str(buddybox.get("use_for", "")).lower()
        for token in (
            "private local",
            "drafts",
            "lightweight prototypes",
            "exports",
            "reports",
            "logs",
            "generated files",
            "binary outputs",
        ):
            self.assertIn(token, buddybox_use_for)
        self.assertIn("cross-buddy readable", str(buddybox.get("not_for", "")).lower())
        self.assertIn("product objects", str(buddybox.get("not_for", "")).lower())
        self.assertIn("artifact.create_revision", str(buddybox.get("promote_with", "")).lower())

        artifact = affordances.get("artifact")
        self.assertIsInstance(artifact, dict, msg=affordances)
        assert isinstance(artifact, dict)
        self.assertIn("product-readable deliverables", str(artifact.get("use_for", "")).lower())

        self.assertEqual(set(buddybox), {"use_for", "not_for", "promote_with", "inspect_with"})
        self.assertEqual(set(artifact), {"use_for", "not_for", "inspect_with"})
        for row in (buddybox, artifact):
            for value in row.values():
                self.assertIsInstance(value, str)

    def test_context_uses_buddybox_desc_not_file_projection(self) -> None:
        self._seed_context_state()
        instance_json = self._instance_json()
        payload = self._dispatch(instance_json=instance_json, tool="context", action="get", args={})
        self.assertTrue(payload.get("ok"), msg=payload)
        self.assertIn("buddybox_desc", payload)
        self.assertNotIn(_RETIRED_BUDDYBOX_FILE_ROWS_FIELD, payload)
        desc = payload.get("buddybox_desc")
        self.assertIsInstance(desc, dict, msg=payload)
        assert isinstance(desc, dict)
        self.assertEqual(desc.get("active_buddy"), "dev")
        self.assertEqual(desc.get("logical_root"), "buddyswitch/local/buddybox/dev")
        self.assertIn("private", str(desc.get("message", "")).lower())

    def test_context_summarize_tool_affordances_stay_compact(self) -> None:
        self._seed_context_state()
        instance_json = self._instance_json()

        summary = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={})

        self.assertTrue(summary.get("ok"), msg=summary)
        self.assertIn("buddybox_desc", summary)
        self.assertNotIn("tool_catalog", summary)
        self.assertNotIn("operation_semantics", summary)
        affordances = summary.get("tool_affordances")
        self.assertIsInstance(affordances, dict, msg=summary)
        assert isinstance(affordances, dict)
        for tool_name, row in affordances.items():
            with self.subTest(tool=tool_name):
                self.assertIsInstance(row, dict, msg=summary)
                assert isinstance(row, dict)
                for forbidden in ("payload_fields", "action_semantics", "content", "content_base64", "files"):
                    self.assertNotIn(forbidden, row)

    def test_context_get_exposes_full_tool_catalog_for_inspection(self) -> None:
        instance_json = self._instance_json()

        payload = self._dispatch(instance_json=instance_json, tool="context", action="get", args={})

        self.assertTrue(payload.get("ok"), msg=payload)
        tool_catalog = payload.get("tool_catalog")
        operation_semantics = payload.get("operation_semantics")
        self.assertIsInstance(tool_catalog, dict, msg=payload)
        self.assertIsInstance(operation_semantics, dict, msg=payload)
        assert isinstance(tool_catalog, dict)
        assert isinstance(operation_semantics, dict)
        self.assertIn("buddybox", tool_catalog)
        buddybox = tool_catalog["buddybox"]
        self.assertIsInstance(buddybox, dict, msg=payload)
        assert isinstance(buddybox, dict)
        self.assertIn("action_semantics", buddybox)
        self.assertIn("payload_fields", buddybox)
        self.assertIn("buddybox.write", operation_semantics)

    def test_context_list_sources_excludes_memory_and_includes_buddybox(self) -> None:
        instance_json = self._instance_json()
        listed = self._dispatch(instance_json=instance_json, tool="context", action="list_sources", args={})
        self.assertTrue(listed.get("ok"), msg=listed)
        sources = listed.get("sources")
        self.assertIsInstance(sources, dict, msg=listed)
        assert isinstance(sources, dict)
        self.assertNotIn("memories", sources)
        self.assertIn("buddybox", sources)
        buddybox = sources["buddybox"]
        self.assertIsInstance(buddybox, dict, msg=listed)
        assert isinstance(buddybox, dict)
        self.assertIn("private local workspace", str(buddybox.get("description", "")).lower())
        self.assertEqual(buddybox.get("source_of_truth"), "buddyswitch/local/buddybox/<active_buddy>/**")

    def test_context_get_applies_filters(self) -> None:
        self._seed_context_state()
        instance_json = self._instance_json()

        filtered = self._dispatch(
            instance_json=instance_json,
            tool="context",
            action="get",
            args={"track_id": "track-context-runless", "task_id": "task-dev-context", "limit": 5},
        )
        self.assertTrue(filtered.get("ok"), msg=filtered)
        tasks = filtered.get("tasks")
        self.assertIsInstance(tasks, list, msg=filtered)
        assert isinstance(tasks, list)
        self.assertEqual({row.get("id") for row in tasks if isinstance(row, dict)}, {"task-dev-context"})
        self.assertIn("buddybox_desc", filtered)
        self.assertNotIn(_RETIRED_BUDDYBOX_FILE_ROWS_FIELD, filtered)
        decision_surface = filtered.get("decision_surface")
        self.assertIsInstance(decision_surface, dict, msg=filtered)
        assert isinstance(decision_surface, dict)
        readiness = decision_surface.get("context_readiness")
        self.assertIsInstance(readiness, dict, msg=filtered)
        assert isinstance(readiness, dict)
        self.assertIn("has_buddybox_workspace", readiness)
        self.assertNotIn(_RETIRED_BUDDYBOX_READINESS_FIELD, readiness)

    def test_context_rejects_unknown_payload_field(self) -> None:
        instance_json = self._instance_json()
        rejected = self._dispatch(
            instance_json=instance_json,
            tool="context",
            action="get",
            args={"unknown": 1},
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_CONTEXT_PAYLOAD")


if __name__ == "__main__":
    unittest.main()
