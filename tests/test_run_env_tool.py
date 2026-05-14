#!/usr/bin/env python3
"""Functional coverage for broker-routed env.tool run env tool operations."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
import turn_runtime  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"
INSTANCE_ID = "inst-pm-run-example"
PM_REQUEST = "给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track"


def _pm_commit() -> dict[str, object]:
    return {
        "execution_summary": "PM wrote the AI schedule tool landing page PRD and created the delivery track.",
        "working_notes": ["PM completed planning and queued next research step."],
        "contributors": {
            "skills": ["write-prd", "track-tool"],
            "agents": [],
        },
    }


def _result_hash(result: dict[str, object]) -> str:
    body = json.dumps(result, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


class RunManagerEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _session(self, *, buddy: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        return {
            "instance_id": INSTANCE_ID,
            "active_buddy": buddy,
            "payload": payload or {},
        }

    def _instance_json(
        self,
        *,
        instance_id: str = INSTANCE_ID,
        buddy: str = "pm",
        status: str = "active",
        current_task_id: str | None = None,
        current_track_id: str | None = None,
    ) -> Path:
        instance_json = self._runtime_path("instance.json")
        instance_json.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": status,
                    "current_task_id": current_task_id,
                    "current_track_id": current_track_id,
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "created_at": "2026-05-10T00:00:00Z",
                    "updated_at": "2026-05-10T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return instance_json

    def _prepare(
        self,
        request_text: str = PM_REQUEST,
        *,
        buddy: str = "pm",
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        with patch.object(turn_runtime, "_load_product_mode_session", return_value=self._session(buddy=buddy, payload=payload)):
            context = turn_runtime.prepare_turn_context(request_text, manifest_path=MANIFEST)
        self.assertTrue(context["ok"], msg=context)
        return context

    def _dispatch(
        self,
        *,
        action: str,
        args: dict[str, object],
        instance_json: Path,
        instance_id: str = INSTANCE_ID,
        buddy: str = "pm",
    ) -> dict[str, object]:
        params: dict[str, object] = {
            "instance_id": instance_id,
            "active_buddy": buddy,
            "tool": "run",
            "action": action,
            "args": args,
        }
        request: dict[str, object] = {
            "protocol": PROTOCOL,
            "request_id": f"req-run-tool-{uuid.uuid4().hex}",
            "method": "env.tool",
            "params": params,
            "deadline_ms": 35000,
        }
        if action == "commit":
            context = args.get("context")
            result = args.get("result")
            if isinstance(context, dict) and isinstance(result, dict):
                run_id = str(context["run_envelope"]["turn_identity"]["run_id"])
                result_hash = _result_hash(result)
                request["idempotency_key"] = f"persist:{run_id}:{result_hash}"
                request["result_hash"] = result_hash
        envelope = runtime_broker.dispatch_runtime_request(
            request=request,
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )
        self.assertIsInstance(envelope, dict)
        assert isinstance(envelope, dict)
        self.assertEqual(envelope.get("protocol"), PROTOCOL)
        if envelope.get("ok") is True:
            payload = envelope.get("result")
            self.assertIsInstance(payload, dict, msg=envelope)
            assert isinstance(payload, dict)
            return payload
        error = envelope.get("error")
        self.assertIsInstance(error, dict, msg=envelope)
        assert isinstance(error, dict)
        payload = {
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

    def _runtime_state_snapshot(self) -> dict[str, object]:
        def _load_dir(dir_path: Path) -> dict[str, object]:
            rows: dict[str, object] = {}
            if not dir_path.exists():
                return rows
            for path in sorted(dir_path.glob("*.json")):
                rows[path.name] = json.loads(path.read_text(encoding="utf-8"))
            return rows

        return {
            "tracks": _load_dir(self._runtime_path("buddyswitch/objects/tracks")),
            "tasks": _load_dir(self._runtime_path("buddyswitch/objects/tasks")),
            "artifacts": _load_dir(self._runtime_path("buddyswitch/objects/artifacts")),
            "runs": _load_dir(self._runtime_path("buddyswitch/content/runs")),
            "reservations": _load_dir(self._runtime_path("buddyswitch/content/runs/reserved")),
        }

    def _load_instance(self, instance_json: Path) -> dict[str, object]:
        return json.loads(instance_json.read_text(encoding="utf-8"))

    def test_run_commit_persists_buddy_run_without_mutating_instance_binding(self) -> None:
        context = self._prepare()
        instance_json = self._instance_json()
        instance_before = self._load_instance(instance_json)

        response = self._dispatch(
            action="commit",
            args={"context": context, "result": _pm_commit()},
            instance_json=instance_json,
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("tool"), "run")
        self.assertEqual(response.get("action"), "run.commit")
        receipt = response.get("receipt")
        self.assertIsInstance(receipt, dict, msg=response)
        assert isinstance(receipt, dict)
        run_id = receipt.get("run_id")
        self.assertIsInstance(run_id, str, msg=response)
        assert isinstance(run_id, str)
        self.assertTrue(self._runtime_path(f"buddyswitch/content/runs/{run_id}.json").exists())
        self.assertFalse(self._runtime_path(f"buddyswitch/content/runs/reserved/{run_id}.json").exists())
        next_state = receipt.get("next_state")
        self.assertIsInstance(next_state, dict, msg=response)
        assert isinstance(next_state, dict)
        self.assertEqual(next_state.get("mode"), "taskless_audit")
        self.assertIsNone(next_state.get("task_id"))
        self.assertIsNone(next_state.get("track_id"))
        self.assertIsNone(next_state.get("next_buddy"))

        instance_payload = self._load_instance(instance_json)
        self.assertEqual(instance_payload, instance_before)

    def test_invalid_run_commit_returns_feedback_without_mutating_state(self) -> None:
        context = self._prepare()
        instance_json = self._instance_json()
        state_before = copy.deepcopy(self._runtime_state_snapshot())
        instance_before = self._load_instance(instance_json)

        response = self._dispatch(
            action="commit",
            args={
                "context": context,
                "result": {
                    "execution_summary": "legacy host payload",
                    "state_effects": {"task": {"status": "done"}},
                },
            },
            instance_json=instance_json,
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("tool"), "run")
        self.assertEqual(response.get("action"), "run.commit")
        error = response.get("error")
        self.assertIsInstance(error, dict, msg=response)
        assert isinstance(error, dict)
        self.assertEqual(error.get("code"), "E_RUNTIME_PERSIST")
        self.assertEqual(response.get("permission_boundary"), "persist.state_effects")
        self.assertEqual(self._runtime_state_snapshot(), state_before)
        self.assertEqual(self._load_instance(instance_json), instance_before)

    def test_duplicate_run_commit_returns_existing_receipt_for_same_idempotency_key(self) -> None:
        from env.services import runs as run_service

        context = self._prepare()
        result = _pm_commit()
        run_id = context["run_envelope"]["turn_identity"]["run_id"]
        result_hash = _result_hash(result)
        idempotency_key = f"persist:{run_id}:{result_hash}"

        first = run_service.commit_buddy_run(
            context,
            result=result,
            manifest_path=MANIFEST,
            idempotency_key=idempotency_key,
            result_hash=result_hash,
        )
        run_path = self._runtime_path(f"buddyswitch/content/runs/{run_id}.json")
        first_audit = json.loads(run_path.read_text(encoding="utf-8"))

        second = run_service.commit_buddy_run(
            context,
            result=result,
            manifest_path=MANIFEST,
            idempotency_key=idempotency_key,
            result_hash=result_hash,
        )
        second_audit = json.loads(run_path.read_text(encoding="utf-8"))

        self.assertEqual(second["receipt"], first["receipt"])
        self.assertEqual(second_audit, first_audit)
        self.assertEqual(first_audit["idempotency_key"], idempotency_key)
        self.assertEqual(first_audit["result_hash"], result_hash)
        self.assertNotIn("idempotency_key", second["receipt"])
        self.assertNotIn("result_hash", second["receipt"])

    def test_duplicate_run_commit_conflicts_for_different_result_hash(self) -> None:
        from env.services import runs as run_service
        import turn_runtime

        context = self._prepare()
        first_result = _pm_commit()
        run_id = context["run_envelope"]["turn_identity"]["run_id"]
        first_hash = _result_hash(first_result)
        first_key = f"persist:{run_id}:{first_hash}"
        run_service.commit_buddy_run(
            context,
            result=first_result,
            manifest_path=MANIFEST,
            idempotency_key=first_key,
            result_hash=first_hash,
        )
        run_path = self._runtime_path(f"buddyswitch/content/runs/{run_id}.json")
        first_audit = json.loads(run_path.read_text(encoding="utf-8"))

        conflicting_result = _pm_commit()
        conflicting_result["execution_summary"] = "PM wrote a different summary for the same prepared run."
        conflicting_hash = _result_hash(conflicting_result)
        conflicting_key = f"persist:{run_id}:{conflicting_hash}"

        with self.assertRaises(turn_runtime.RuntimeFeedbackError) as raised:
            run_service.commit_buddy_run(
                context,
                result=conflicting_result,
                manifest_path=MANIFEST,
                idempotency_key=conflicting_key,
                result_hash=conflicting_hash,
            )

        self.assertEqual(raised.exception.code, "E_RUNTIME_PERSIST_CONFLICT")
        self.assertEqual(json.loads(run_path.read_text(encoding="utf-8")), first_audit)

    def test_run_validate_result_rejects_invalid_handoff_ids_and_retired_mutation_fields(self) -> None:
        env_store.create_track(
            "track-dev-run-validate",
            "Run Validate Track",
            status="active",
            current_buddy="pm",
            next_buddy="dev",
            summary="run validate",
        )
        env_store.create_task(
            "task-dev-run-validate",
            "Dev Run Validate",
            buddy="dev",
            track_id="track-dev-run-validate",
            status="active",
            summary="",
            initial_run_id=None,
        )
        env_store.create_task(
            "task-pm-run-validate",
            "PM Run Validate",
            buddy="pm",
            track_id="track-dev-run-validate",
            status="active",
            summary="",
            initial_run_id=None,
        )
        env_store.create_artifact(
            artifact_id="art-dev-run-validate-old-r1",
            title="Dev Run Validate Old",
            buddy="dev",
            kind="implementation-report",
            task_id="task-dev-run-validate",
            source_run_id="run-dev-run-validate-r1",
            summary="old",
            content={"body": "old"},
        )
        env_store.create_artifact(
            artifact_id="art-dev-run-validate-new-r2",
            title="Dev Run Validate New",
            buddy="dev",
            kind="implementation-report",
            task_id="task-dev-run-validate",
            source_run_id="run-dev-run-validate-r2",
            summary="new",
            content={"body": "new"},
        )
        env_store.create_artifact(
            artifact_id="art-pm-run-validate-r1",
            title="PM Run Validate",
            buddy="pm",
            kind="prd",
            task_id="task-pm-run-validate",
            source_run_id="run-pm-run-validate-r1",
            summary="pm",
            content={"body": "pm"},
        )
        context = self._prepare(
            request_text="validate run payload",
            buddy="dev",
            payload={
                "current_task_id": "task-dev-run-validate",
                "current_track_id": "track-dev-run-validate",
            },
        )
        instance_json = self._instance_json(
            instance_id=INSTANCE_ID,
            buddy="dev",
            current_task_id="task-dev-run-validate",
            current_track_id="track-dev-run-validate",
        )
        run_id = str(context["run_envelope"]["run_id"])

        def _result() -> dict[str, object]:
            return {
                "execution_summary": "validate result",
                "task_id": "task-dev-run-validate",
                "track_id": "track-dev-run-validate",
                "artifact_ids": ["art-dev-run-validate-new-r2"],
                "handoff": {
                    "track_id": "track-dev-run-validate",
                    "source_task_id": "task-dev-run-validate",
                    "source_run_id": run_id,
                    "target_buddy": "test",
                    "artifact_ids": ["art-dev-run-validate-new-r2"],
                    "historical_artifact_ids": [],
                    "reason": "Test should verify implementation.",
                    "context": "Use implementation artifact.",
                },
                "contributors": {"skills": ["implement-task"], "agents": []},
            }

        cases = [
            ("persist.task_id", {"task_id": "task-dev-run-missing"}),
            ("persist.track_id", {"track_id": "track-dev-run-missing"}),
            ("persist.artifact_ids", {"artifact_ids": ["art-dev-run-missing-r1"]}),
            ("manifest.buddies", {"handoff": {**_result()["handoff"], "target_buddy": "unknown"}}),
            ("handoff.source_artifact_scope", {"handoff": {**_result()["handoff"], "artifact_ids": ["art-pm-run-validate-r1"]}}),
            (
                "handoff.historical_marker",
                {"handoff": {**_result()["handoff"], "artifact_ids": ["art-dev-run-validate-old-r1"], "historical_artifact_ids": []}},
            ),
            ("persist.state_effects", {"state_effects": {"track": {"status": "done"}}}),
            ("persist.artifacts", {"artifacts": [{"id": "legacy-inline"}]}),
        ]
        for expected_boundary, patch in cases:
            with self.subTest(boundary=expected_boundary):
                candidate = _result()
                candidate.update(patch)
                response = self._dispatch(
                    action="validate_result",
                    args={"context": context, "result": candidate},
                    instance_json=instance_json,
                    instance_id=INSTANCE_ID,
                    buddy="dev",
                )
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual(response.get("permission_boundary"), expected_boundary)

    def test_run_validate_result_infers_handoff_artifact_ids_from_top_level_association(self) -> None:
        env_store.create_track(
            "track-dev-run-validate-infer",
            "Run Validate Infer",
            status="active",
            current_buddy="pm",
            next_buddy="dev",
            summary="run validate infer",
        )
        env_store.create_task(
            "task-dev-run-validate-infer",
            "Dev Run Validate Infer",
            buddy="dev",
            track_id="track-dev-run-validate-infer",
            status="active",
            summary="",
            initial_run_id=None,
        )
        env_store.create_artifact(
            artifact_id="art-dev-run-validate-infer-r1",
            title="Dev Run Validate Infer",
            buddy="dev",
            kind="implementation-report",
            task_id="task-dev-run-validate-infer",
            source_run_id="run-dev-run-validate-infer-r1",
            summary="infer",
            content={"body": "infer"},
        )
        context = self._prepare(
            request_text="validate inferred handoff payload",
            buddy="dev",
            payload={
                "current_task_id": "task-dev-run-validate-infer",
                "current_track_id": "track-dev-run-validate-infer",
            },
        )
        instance_json = self._instance_json(
            instance_id=INSTANCE_ID,
            buddy="dev",
            current_task_id="task-dev-run-validate-infer",
            current_track_id="track-dev-run-validate-infer",
        )
        response = self._dispatch(
            action="validate_result",
            args={
                "context": context,
                "result": {
                    "execution_summary": "validate inferred handoff payload",
                    "task_id": "task-dev-run-validate-infer",
                    "track_id": "track-dev-run-validate-infer",
                    "artifact_ids": ["art-dev-run-validate-infer-r1"],
                    "handoff": {
                        "next_buddy": "test",
                        "reason": "Test should validate implementation output.",
                        "context": "Use the inferred artifact association.",
                    },
                },
            },
            instance_json=instance_json,
            instance_id=INSTANCE_ID,
            buddy="dev",
        )
        self.assertTrue(response.get("ok"), msg=response)
        validated_handoff = response.get("validated_handoff")
        self.assertIsInstance(validated_handoff, dict, msg=response)
        assert isinstance(validated_handoff, dict)
        self.assertEqual(validated_handoff.get("track_id"), "track-dev-run-validate-infer")
        self.assertEqual(validated_handoff.get("source_task_id"), "task-dev-run-validate-infer")
        self.assertEqual(validated_handoff.get("artifact_ids"), ["art-dev-run-validate-infer-r1"])
        self.assertEqual(validated_handoff.get("next_buddy"), "test")

    def test_run_validate_result_legacy_handoff_unknown_target_returns_manifest_boundary(self) -> None:
        context = self._prepare(
            request_text="legacy unknown handoff target",
            buddy="pm",
            payload={},
        )
        instance_json = self._instance_json(
            instance_id=INSTANCE_ID,
            buddy="pm",
            current_task_id=None,
            current_track_id=None,
        )
        response = self._dispatch(
            action="validate_result",
            args={
                "context": context,
                "result": {
                    "execution_summary": "legacy unknown handoff target",
                    "handoff": {
                        "next_buddy": "sales",
                        "reason": "Need sales review.",
                        "context": "legacy handoff shape without source ids.",
                    },
                },
            },
            instance_json=instance_json,
            instance_id=INSTANCE_ID,
            buddy="pm",
        )
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("permission_boundary"), "manifest.buddies")

    def test_run_validate_result_rejects_retired_mutation_fields_with_existing_tool_hints(self) -> None:
        context = self._prepare(
            request_text="validate retired fields hints",
            buddy="dev",
            payload={},
        )
        instance_json = self._instance_json(
            instance_id=INSTANCE_ID,
            buddy="dev",
            current_task_id=None,
            current_track_id=None,
        )

        state_effects = self._dispatch(
            action="validate_result",
            args={
                "context": context,
                "result": {
                    "execution_summary": "invalid lifecycle mutation",
                    "state_effects": {"track": {"status": "done"}},
                },
            },
            instance_json=instance_json,
            instance_id=INSTANCE_ID,
            buddy="dev",
        )
        self.assertFalse(state_effects.get("ok"), msg=state_effects)
        self.assertEqual(state_effects.get("permission_boundary"), "persist.state_effects")
        lifecycle_hints = state_effects.get("allowed_next_actions")
        self.assertIsInstance(lifecycle_hints, list, msg=state_effects)
        assert isinstance(lifecycle_hints, list)
        lifecycle_text = "\n".join(str(item) for item in lifecycle_hints)
        self.assertIn("python3 scripts/env/client.py task update --payload <json-file>", lifecycle_text)
        self.assertIn("python3 scripts/env/client.py track update --payload <json-file>", lifecycle_text)
        self.assertIn("python3 scripts/env/client.py track advance --payload <json-file>", lifecycle_text)
        self.assertIn("python3 scripts/env/client.py track join --track-id <track-id>", lifecycle_text)
        self.assertNotIn("artifact.list_revisions", lifecycle_text)

        embedded_artifacts = self._dispatch(
            action="validate_result",
            args={
                "context": context,
                "result": {
                    "execution_summary": "invalid embedded artifacts",
                    "artifacts": [{"id": "legacy-inline"}],
                },
            },
            instance_json=instance_json,
            instance_id=INSTANCE_ID,
            buddy="dev",
        )
        self.assertFalse(embedded_artifacts.get("ok"), msg=embedded_artifacts)
        self.assertEqual(embedded_artifacts.get("permission_boundary"), "persist.artifacts")
        artifact_hints = embedded_artifacts.get("allowed_next_actions")
        self.assertIsInstance(artifact_hints, list, msg=embedded_artifacts)
        assert isinstance(artifact_hints, list)
        artifact_text = "\n".join(str(item) for item in artifact_hints)
        self.assertIn("python3 scripts/env/client.py artifact create-revision --payload <json-file>", artifact_text)
        self.assertNotIn("artifact.list_revisions", artifact_text)

        serialized = json.dumps({"state_effects": state_effects, "embedded_artifacts": embedded_artifacts}, sort_keys=True)
        self.assertNotIn("buddyswitch/objects", serialized)
        self.assertNotIn("buddyswitch/content/runs", serialized)
        self.assertNotIn("runs/raw", serialized)

    def test_run_commit_does_not_repair_missing_join_or_handoff_relation(self) -> None:
        env_store.create_track(
            "track-dev-run-commit-main",
            "Run Commit Main",
            status="active",
            current_buddy="pm",
            next_buddy="dev",
            summary="run commit main",
        )
        env_store.create_task(
            "task-dev-run-untracked",
            "Dev Untracked",
            buddy="dev",
            track_id=None,
            status="active",
            summary="",
            initial_run_id=None,
        )
        env_store.create_artifact(
            artifact_id="art-dev-run-untracked-r1",
            title="Dev Untracked Artifact",
            buddy="dev",
            kind="implementation-report",
            task_id="task-dev-run-untracked",
            source_run_id="run-dev-run-untracked-r1",
            summary="untracked",
            content={"body": "untracked body"},
        )
        track_before = copy.deepcopy(env_store.get_track("track-dev-run-commit-main"))
        task_before = copy.deepcopy(env_store.get_task("task-dev-run-untracked"))
        assert isinstance(track_before, dict)
        assert isinstance(task_before, dict)

        context = self._prepare(
            request_text="commit without join should fail",
            buddy="dev",
            payload={"current_task_id": "task-dev-run-untracked"},
        )
        instance_json = self._instance_json(
            instance_id=INSTANCE_ID,
            buddy="dev",
            current_task_id="task-dev-run-untracked",
            current_track_id=None,
        )
        run_id = str(context["run_envelope"]["turn_identity"]["run_id"])
        result = {
            "execution_summary": "attempt commit without join",
            "task_id": "task-dev-run-untracked",
            "track_id": "track-dev-run-commit-main",
            "artifact_ids": ["art-dev-run-untracked-r1"],
            "handoff": {
                "track_id": "track-dev-run-commit-main",
                "source_task_id": "task-dev-run-untracked",
                "source_run_id": run_id,
                "target_buddy": "test",
                "artifact_ids": ["art-dev-run-untracked-r1"],
                "historical_artifact_ids": [],
                "reason": "test should continue",
                "context": "uses untracked task artifact",
            },
        }
        response = self._dispatch(
            action="commit",
            args={"context": context, "result": result},
            instance_json=instance_json,
            instance_id=INSTANCE_ID,
            buddy="dev",
        )
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("permission_boundary"), "track.task_linkage")
        self.assertEqual(env_store.get_task("task-dev-run-untracked"), task_before)
        self.assertEqual(env_store.get_track("track-dev-run-commit-main"), track_before)
        self.assertFalse(self._runtime_path(f"buddyswitch/content/runs/{run_id}.json").exists())


if __name__ == "__main__":
    unittest.main()
