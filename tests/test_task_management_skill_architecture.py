#!/usr/bin/env python3
"""Regression coverage for task-management skill architecture boundaries."""

from __future__ import annotations

import copy
import json
import re
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
PM_REQUEST = "创建3个task关于为三款产品分别制作简单的landing page"


class TaskManagementSkillArchitectureTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(
        self,
        *,
        buddy: str,
        instance_id: str,
        current_task_id: str | None = None,
        current_track_id: str | None = None,
    ) -> Path:
        path = self._runtime_path(f"{instance_id}.json")
        path.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": "active",
                    "current_task_id": current_task_id,
                    "current_track_id": current_track_id,
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "created_at": "2026-05-12T00:00:00Z",
                    "updated_at": "2026-05-12T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def _dispatch(
        self,
        *,
        method: str,
        payload: dict[str, object],
        instance_json: Path,
        instance_id: str,
        buddy: str,
    ) -> dict[str, object]:
        envelope = runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "request_id": f"req-task-arch-{uuid.uuid4().hex}",
                "method": method,
                "params": {
                    "instance_id": instance_id,
                    "active_buddy": buddy,
                    **payload,
                },
                "deadline_ms": 35000,
            },
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )
        self.assertEqual(envelope.get("protocol"), PROTOCOL)
        if envelope.get("ok") is True:
            result = envelope.get("result")
            self.assertIsInstance(result, dict, msg=envelope)
            assert isinstance(result, dict)
            return result
        error = envelope.get("error")
        self.assertIsInstance(error, dict, msg=envelope)
        assert isinstance(error, dict)
        response: dict[str, object] = {
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
            response[key] = value
        return response

    def _env_tool(
        self,
        *,
        instance_json: Path,
        instance_id: str,
        buddy: str,
        tool: str,
        action: str,
        args: dict[str, object],
    ) -> dict[str, object]:
        response = self._dispatch(
            method="env.tool",
            payload={"tool": tool, "action": action, "args": args},
            instance_json=instance_json,
            instance_id=instance_id,
            buddy=buddy,
        )
        return response

    def _prepare(
        self,
        *,
        text: str,
        instance_json: Path,
        instance_id: str,
        buddy: str,
    ) -> dict[str, object]:
        response = self._dispatch(
            method="prepare",
            payload={"text": text},
            instance_json=instance_json,
            instance_id=instance_id,
            buddy=buddy,
        )
        self.assertTrue(response.get("ok"), msg=response)
        payload = response.get("payload") if isinstance(response.get("payload"), dict) else response
        self.assertIsInstance(payload, dict, msg=response)
        assert isinstance(payload, dict)
        return payload

    def _tasks_dir(self) -> Path:
        return self._runtime_path("buddyswitch/objects/tasks")

    def _tracks_dir(self) -> Path:
        return self._runtime_path("buddyswitch/objects/tracks")

    def _artifacts_dir(self) -> Path:
        return self._runtime_path("buddyswitch/objects/artifacts")

    def _task_file_ids(self) -> list[str]:
        tasks_dir = self._tasks_dir()
        if not tasks_dir.exists():
            return []
        return sorted(path.stem for path in tasks_dir.glob("*.json"))

    def _read_json(self, path: Path) -> dict[str, object]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsInstance(payload, dict, msg={"path": str(path), "payload": payload})
        return payload

    def _load_instance(self, path: Path) -> dict[str, object]:
        return self._read_json(path)

    def _reserved_payload(self, run_id: str) -> dict[str, object]:
        path = self._runtime_path(f"buddyswitch/content/runs/reserved/{run_id}.json")
        self.assertTrue(path.exists(), msg=path)
        return self._read_json(path)

    def test_unbound_prepare_creates_no_task_files(self) -> None:
        instance_id = "inst-pm-unbound-prepare"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        prepared = self._prepare(
            text=PM_REQUEST,
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
        )
        self.assertIsNone(prepared.get("current_task_id"))
        self.assertIsNone(prepared.get("task_context"))
        decision_surface = prepared["runtime_context"]["decision_surface"]
        self.assertEqual(decision_surface["binding_state"]["state"], "unbound")
        run_id = prepared["run_envelope"]["run_id"]
        reservation = self._reserved_payload(str(run_id))
        self.assertIsNone(reservation.get("task_id"))
        self.assertEqual(self._task_file_ids(), [])

    def test_stale_task_binding_is_reported_without_repair(self) -> None:
        instance_id = "inst-pm-stale-task"
        instance_json = self._instance_json(
            buddy="pm",
            instance_id=instance_id,
            current_task_id="task-missing",
        )
        prepared = self._prepare(
            text="继续当前任务",
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
        )
        self.assertFalse(self._runtime_path("buddyswitch/objects/tasks/task-missing.json").exists())
        self.assertEqual(prepared["runtime_context"]["decision_surface"]["binding_state"]["state"], "stale")
        warnings = prepared.get("warnings")
        self.assertIsInstance(warnings, list, msg=prepared)
        warning_codes = {
            row.get("code")
            for row in warnings
            if isinstance(row, dict)
        }
        self.assertIn("W_STALE_TASK_BINDING", warning_codes)

    def test_stale_track_binding_is_reported_without_repair(self) -> None:
        instance_id = "inst-pm-stale-track"
        instance_json = self._instance_json(
            buddy="pm",
            instance_id=instance_id,
            current_track_id="track-missing",
        )
        prepared = self._prepare(
            text="继续当前track",
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
        )
        self.assertFalse(self._runtime_path("buddyswitch/objects/tracks/track-missing.json").exists())
        self.assertEqual(prepared["runtime_context"]["decision_surface"]["binding_state"]["state"], "stale")
        warnings = prepared.get("warnings")
        self.assertIsInstance(warnings, list, msg=prepared)
        warning_codes = {
            row.get("code")
            for row in warnings
            if isinstance(row, dict)
        }
        self.assertIn("W_STALE_TRACK_BINDING", warning_codes)

    def test_three_explicit_task_creates_produce_exactly_three_task_files(self) -> None:
        instance_id = "inst-pm-three-explicit"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        self._prepare(
            text=PM_REQUEST,
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
        )
        explicit_ids = [
            "task-pm-landing-page-50cefcd4",
            "task-pm-landing-page-ab3fd1f8",
            "task-pm-landing-page-7ad912e7",
        ]
        for task_id in explicit_ids:
            created = self._env_tool(
                instance_json=instance_json,
                instance_id=instance_id,
                buddy="pm",
                tool="task",
                action="create",
                args={"task_id": task_id, "title": f"Task {task_id[-8:]}", "summary": "explicit task create"},
            )
            self.assertTrue(created.get("ok"), msg=created)

        task_ids = self._task_file_ids()
        self.assertEqual(task_ids, sorted(explicit_ids))
        hidden = [task_id for task_id in task_ids if re.match(r"task-pm-3-task-landing-page-", task_id)]
        self.assertEqual(hidden, [])

    def test_taskless_persist_writes_run_audit_only(self) -> None:
        instance_id = "inst-pm-taskless-persist"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        prepared = self._prepare(
            text="记录讨论，无需创建任务",
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
        )
        persisted = self._env_tool(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="run",
            action="commit",
            args={"context": prepared, "result": {"execution_summary": "recorded taskless discussion"}},
        )
        self.assertTrue(persisted.get("ok"), msg=persisted)
        receipt = persisted.get("receipt")
        self.assertIsInstance(receipt, dict, msg=persisted)
        assert isinstance(receipt, dict)
        self.assertNotIn("task_id", receipt)
        run_id = receipt["run_id"]
        run_path = self._runtime_path(f"buddyswitch/content/runs/{run_id}.json")
        self.assertTrue(run_path.exists(), msg=run_path)
        run_payload = self._read_json(run_path)
        self.assertEqual(run_payload.get("writes"), [f"buddyswitch/content/runs/{run_id}.json"])
        self.assertEqual(self._task_file_ids(), [])
        self.assertEqual(sorted(path.name for path in self._tracks_dir().glob("*.json")) if self._tracks_dir().exists() else [], [])
        self.assertEqual(
            sorted(path.name for path in self._artifacts_dir().glob("*.json")) if self._artifacts_dir().exists() else [],
            [],
        )

    def test_taskless_commit_rejects_spoofed_product_context_without_clearing_reservation(self) -> None:
        instance_id = "inst-pm-taskless-identity"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        prepared = self._prepare(
            text="记录一个无任务审计",
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
        )
        self.assertIsNone(prepared.get("current_task_id"))
        run_id = str(prepared["run_envelope"]["run_id"])
        reserved_path = self._runtime_path(f"buddyswitch/content/runs/reserved/{run_id}.json")
        self.assertTrue(reserved_path.exists(), msg=reserved_path)

        spoofed_context = copy.deepcopy(prepared)
        spoofed_context["instance_id"] = "inst-pm-spoofed"
        run_envelope = spoofed_context["run_envelope"]
        self.assertIsInstance(run_envelope, dict, msg=spoofed_context)
        assert isinstance(run_envelope, dict)
        turn_identity = run_envelope["turn_identity"]
        self.assertIsInstance(turn_identity, dict, msg=spoofed_context)
        assert isinstance(turn_identity, dict)
        turn_identity["instance_id"] = "inst-pm-spoofed"

        rejected = self._env_tool(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="run",
            action="commit",
            args={"context": spoofed_context, "result": {"execution_summary": "spoofed taskless audit"}},
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        error = rejected.get("error")
        self.assertIsInstance(error, dict, msg=rejected)
        assert isinstance(error, dict)
        self.assertEqual(error.get("code"), "E_RUNTIME_PERSIST")
        self.assertIn("product-mode context instance mismatch", str(error.get("message")))
        self.assertTrue(reserved_path.exists(), msg="failed commit must leave reservation for a valid retry")
        self.assertFalse(self._runtime_path(f"buddyswitch/content/runs/{run_id}.json").exists())

    def test_persist_rejects_state_effects_task_with_task_tool_guidance(self) -> None:
        instance_id = "inst-pm-reject-state-task"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        prepared = self._prepare(
            text="记录讨论",
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
        )
        rejected = self._env_tool(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="run",
            action="commit",
            args={
                "context": prepared,
                "result": {
                    "execution_summary": "old host payload",
                    "state_effects": {"task": {"status": "done"}},
                },
            },
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual(rejected.get("permission_boundary"), "persist.state_effects")
        actions = rejected.get("allowed_next_actions")
        self.assertIsInstance(actions, list, msg=rejected)
        assert isinstance(actions, list)
        self.assertTrue(any("task update" in str(item).lower() for item in actions))

    def test_persist_rejects_state_effects_track_with_track_tool_guidance(self) -> None:
        instance_id = "inst-pm-reject-state-track"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        prepared = self._prepare(
            text="记录讨论",
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
        )
        rejected = self._env_tool(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="run",
            action="commit",
            args={
                "context": prepared,
                "result": {
                    "execution_summary": "old host payload",
                    "state_effects": {"track": {"action": "create", "track_id": "track-old"}},
                },
            },
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual(rejected.get("permission_boundary"), "persist.state_effects")
        actions = rejected.get("allowed_next_actions")
        self.assertIsInstance(actions, list, msg=rejected)
        assert isinstance(actions, list)
        lowered_actions = [str(item).lower() for item in actions]
        self.assertTrue(any("track update" in item or "track attach_task" in item for item in lowered_actions))

    def test_persist_does_not_mutate_task_object_or_instance_binding(self) -> None:
        instance_id = "inst-pm-bound-no-mutate"
        task_id = "task-pm-stable-object"
        env_store.create_task(
            task_id,
            "Stable task object",
            buddy="pm",
            track_id=None,
            status="active",
            summary="before",
            initial_run_id=None,
        )
        instance_json = self._instance_json(
            buddy="pm",
            instance_id=instance_id,
            current_task_id=task_id,
        )
        task_path = self._runtime_path(f"buddyswitch/objects/tasks/{task_id}.json")
        before_task_text = task_path.read_text(encoding="utf-8")
        before_instance_text = instance_json.read_text(encoding="utf-8")
        prepared = self._prepare(
            text="只记录run审计",
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
        )
        persisted = self._env_tool(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="run",
            action="commit",
            args={"context": prepared, "result": {"execution_summary": "bound task audit only", "task_id": task_id}},
        )
        self.assertTrue(persisted.get("ok"), msg=persisted)
        self.assertEqual(task_path.read_text(encoding="utf-8"), before_task_text)
        self.assertEqual(instance_json.read_text(encoding="utf-8"), before_instance_text)

    def test_prepare_and_persist_do_not_rewrite_instance_binding(self) -> None:
        instance_id = "inst-pm-binding-stable"
        instance_json = self._instance_json(
            buddy="pm",
            instance_id=instance_id,
            current_task_id=None,
            current_track_id=None,
        )
        before_instance = copy.deepcopy(self._load_instance(instance_json))
        prepared = self._prepare(
            text="taskless run",
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
        )
        after_prepare = self._load_instance(instance_json)
        self.assertEqual(after_prepare, before_instance)
        persisted = self._env_tool(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="run",
            action="commit",
            args={"context": prepared, "result": {"execution_summary": "taskless persisted"}},
        )
        self.assertTrue(persisted.get("ok"), msg=persisted)
        after_persist = self._load_instance(instance_json)
        self.assertEqual(after_persist, before_instance)

    def test_prepare_and_persist_paths_do_not_call_task_mutation_apis(self) -> None:
        checks = {
            ROOT / "scripts/turn_runtime.py": [
                "create_task(",
                "register_task_to_track(",
                "state_effects.track",
                "state_effects.task",
                "write_product_session_binding(",
                "resolve_binding_from_payload(",
                "persist_binding_from_payload(",
            ],
            ROOT / "scripts/env/services/runs.py": [
                "register_task_to_track(",
                "update_task(",
                "create_artifact(",
                "add_run_to_task(",
                "persist_binding_from_payload(",
                "write_product_session_binding(",
            ],
            ROOT / "scripts/runtime_kernel/broker.py": [
                "persist_binding_from_payload(",
                "write_product_session_binding(",
            ],
        }
        for path, forbidden_tokens in checks.items():
            text = path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                with self.subTest(path=str(path.relative_to(ROOT)), token=token):
                    self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
