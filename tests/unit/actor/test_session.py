"""Tests for actor-level input and attach boundaries."""

from __future__ import annotations

import importlib
import inspect
import json
import os
import sys
import tempfile
import unittest
from unittest import mock
from itertools import count
from pathlib import Path
from typing import Any


from tests.support.paths import REPO_ROOT
from tests.support.runtime import RuntimeWorkspaceTestCase

ROOT = REPO_ROOT
HELPER_DIR = ROOT / "src" / "buddyswitch" / "launcher"
ACTOR_SESSION_PATH = HELPER_DIR / "actor_session.py"

from buddyswitch.env.domain import task_sys  # noqa: E402
from buddyswitch.env.repos import runtime_files  # noqa: E402
from buddyswitch.launcher import actor_capability  # noqa: E402

MODULE_COUNTER = count()


def load_module(path: Path) -> Any:
    if not path.exists():
        raise AssertionError(f"expected module to exist: {path}")
    return importlib.reload(
        importlib.import_module(f"buddyswitch.launcher.{path.stem}")
    )


class ActorSessionTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.actor_session = load_module(ACTOR_SESSION_PATH)
        self.root = self.runtime_root
        self._validate_codex_runtime = (
            self.actor_session.codex_runtime.validate_codex_runtime
        )
        self.addCleanup(
            setattr,
            self.actor_session.codex_runtime,
            "validate_codex_runtime",
            self._validate_codex_runtime,
        )
        self.actor_session.codex_runtime.validate_codex_runtime = lambda runtime: runtime

    def _write_instance(
        self,
        *,
        actor_id: str = "act-pm-session",
        role: str = "pm",
        thread_id: str = "thr-main",
        status: str = "active",
        app_server_socket: str | None = None,
    ) -> Path:
        shared_root = self.root / "shared"
        instance_root = shared_root / "instances" / actor_id
        workspace_dir = instance_root / "workspace"
        project_workspace_dir = shared_root / "project" / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        project_workspace_dir.mkdir(parents=True, exist_ok=True)
        runtime_dir = instance_root / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        codex_bin = self.root / "bin" / "codex-test"
        codex_bin.parent.mkdir(parents=True, exist_ok=True)
        codex_bin.write_text("#!/bin/sh\nprintf '%s\\n' 'codex-cli test-runtime'\n", encoding="utf-8")
        codex_bin.chmod(0o755)
        socket_path = app_server_socket or str(runtime_dir / "app-server.sock")
        instance_json = instance_root / "instance.json"
        instance_json.write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": role,
                    "status": status,
                    "instance_root": str(instance_root),
                    "workspace_dir": str(workspace_dir),
                    "project_workspace_dir": str(project_workspace_dir),
                    "thread_id": thread_id,
                    "app_server_socket": socket_path,
                    "runtime_identity": self.actor_session.current_runtime_identity().to_record(),
                    "codex_runtime": {
                        "executable": str(codex_bin.resolve(strict=False)),
                        "version": "codex-cli test-runtime",
                    },
                    "updated_at": "2026-07-13T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        actor_capability.seed_actor_capabilities(instance_json)
        return instance_json

    def test_actor_session_constructor_has_no_runtime_override(self) -> None:
        self.assertEqual(
            list(inspect.signature(self.actor_session.ActorSession).parameters),
            ["shared_root"],
        )

    def test_input_actor_turn_updates_capability_then_uses_shared_input_turn_for_start_and_steer(self) -> None:
        instance_json = self._write_instance()
        actor_capability.replace_actor_capabilities(instance_json, parent_level="deep", side_level="fast")
        calls: list[dict[str, Any]] = []
        original_update = self.actor_session.app_server.thread_settings_update
        original_input = self.actor_session.app_server.input_turn

        def fake_update(socket_path: Path, thread_id: str, *, model: str | None, effort: str | None) -> dict[str, Any]:
            calls.append(
                {
                    "helper": "thread_settings_update",
                    "socket_path": socket_path,
                    "thread_id": thread_id,
                    "model": model,
                    "effort": effort,
                }
            )
            return {"ok": True}

        def fake_input(socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, Any]:
            calls.append(
                {
                    "helper": "input_turn",
                    "socket_path": socket_path,
                    "thread_id": thread_id,
                    "text": text,
                    "permissions": permissions,
                }
            )
            if text == "idle parent":
                return {"action": "start", "turn_id": "turn-start-1"}
            return {"action": "steer", "turn_id": "turn-steer-1", "expected_turn_id": "turn-active-1"}

        self.addCleanup(setattr, self.actor_session.app_server, "thread_settings_update", original_update)
        self.addCleanup(setattr, self.actor_session.app_server, "input_turn", original_input)
        self.actor_session.app_server.thread_settings_update = fake_update
        self.actor_session.app_server.input_turn = fake_input

        started = self.actor_session.input_actor_turn(
            socket_path=Path("/tmp/app-server.sock"),
            instance_json=instance_json,
            thread_id="thr-main",
            text="idle parent",
            permissions="buddyswitch-runtime",
        )
        steered = self.actor_session.input_actor_turn(
            socket_path=Path("/tmp/app-server.sock"),
            instance_json=instance_json,
            thread_id="thr-main",
            text="active parent",
            permissions="buddyswitch-runtime",
        )

        self.assertEqual(started["action"], "start")
        self.assertEqual(steered["action"], "steer")
        self.assertEqual([call["helper"] for call in calls], ["thread_settings_update", "input_turn", "thread_settings_update", "input_turn"])
        self.assertEqual(calls[0]["model"], "gpt-5.6-sol")
        self.assertEqual(calls[0]["effort"], "xhigh")
        self.assertEqual(calls[1]["text"], "idle parent")
        self.assertEqual(calls[3]["text"], "active parent")

    def test_actor_session_input_resolves_actor_context_and_leaves_task_sys_repository_unchanged(self) -> None:
        instance_json = self._write_instance(actor_id="act-dev-session", role="dev", thread_id="thr-dev")
        original_update = self.actor_session.app_server.thread_settings_update
        original_input = self.actor_session.app_server.input_turn

        def fake_update(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {"ok": True}

        def fake_input(_socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, Any]:
            return {"action": "start", "turn_id": "turn-direct", "thread_id": thread_id, "text": text, "permissions": permissions}

        self.addCleanup(setattr, self.actor_session.app_server, "thread_settings_update", original_update)
        self.addCleanup(setattr, self.actor_session.app_server, "input_turn", original_input)
        self.actor_session.app_server.thread_settings_update = fake_update
        self.actor_session.app_server.input_turn = fake_input
        before = task_sys.list_tasks()

        session = self.actor_session.ActorSession(shared_root=instance_json.parents[2])
        result = session.input("act-dev-session", "direct parent input")

        self.assertEqual(result["action"], "start")
        self.assertEqual(result["turn_id"], "turn-direct")
        self.assertEqual(task_sys.list_tasks(), before)

    def test_input_rejects_empty_text_missing_actor_and_runtime_unavailable_with_stable_errors(self) -> None:
        instance_json = self._write_instance()
        session = self.actor_session.ActorSession(shared_root=instance_json.parents[2])

        with self.assertRaisesRegex(self.actor_session.ActorSessionError, "input text is required"):
            session.input("act-pm-session", "")
        with self.assertRaisesRegex(self.actor_session.ActorSessionError, "actor not found"):
            session.input("act-missing", "hello")

        original_update = self.actor_session.app_server.thread_settings_update
        original_input = self.actor_session.app_server.input_turn

        def fake_update(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {"ok": True}

        def fail_input(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            raise self.actor_session.app_server.AppServerUnavailableError("thread not loaded")

        self.addCleanup(setattr, self.actor_session.app_server, "thread_settings_update", original_update)
        self.addCleanup(setattr, self.actor_session.app_server, "input_turn", original_input)
        self.actor_session.app_server.thread_settings_update = fake_update
        self.actor_session.app_server.input_turn = fail_input

        with self.assertRaisesRegex(self.actor_session.ActorSessionError, "input turn failed: thread not loaded"):
            session.input("act-pm-session", "hello")

    def test_resolve_attach_builds_validated_descriptor_from_actor_record(self) -> None:
        instance_json = self._write_instance(thread_id="thr-attach", app_server_socket="/tmp/app-server-attach.sock")
        original_resume = self.actor_session.app_server.thread_resume
        calls: list[dict[str, Any]] = []

        def fake_resume(
            socket_path: Path,
            thread_id: str,
            *,
            workspace_dir: Path,
            shared_project_workspace_dir: Path,
            permissions: str,
        ) -> dict[str, Any]:
            calls.append(
                {
                    "socket_path": socket_path,
                    "thread_id": thread_id,
                    "workspace_dir": workspace_dir,
                    "shared_project_workspace_dir": shared_project_workspace_dir,
                    "permissions": permissions,
                }
            )
            return {"thread": {"id": thread_id, "status": {"type": "idle"}}}

        self.addCleanup(setattr, self.actor_session.app_server, "thread_resume", original_resume)
        self.actor_session.app_server.thread_resume = fake_resume

        session = self.actor_session.ActorSession(shared_root=instance_json.parents[2])
        with mock.patch.dict(
            os.environ,
            {"BUDDYSWITCH_TEST_PRIVATE_SENTINEL": "must-not-propagate"},
        ):
            descriptor = session.resolve_attach("act-pm-session")
        expected_instance_root = instance_json.parent.resolve(strict=False)
        expected_workspace = expected_instance_root / "workspace"

        self.assertEqual(descriptor.actor_id, "act-pm-session")
        self.assertEqual(descriptor.thread_id, "thr-attach")
        self.assertEqual(descriptor.cwd, expected_workspace)
        self.assertEqual(
            descriptor.argv,
            (
                str((self.root / "bin" / "codex-test").resolve(strict=False)),
                "resume",
                "--remote",
                "unix:///tmp/app-server-attach.sock",
                "thr-attach",
            ),
        )
        self.assertEqual(descriptor.env["BUDDYSWITCH_ACTOR_ID"], "act-pm-session")
        self.assertEqual(descriptor.env["BUDDYSWITCH_SHARED_ROOT"], str(instance_json.parents[2].resolve(strict=False)))
        self.assertEqual(descriptor.env["BUDDYSWITCH_INSTANCE_JSON"], str(expected_instance_root / "instance.json"))
        self.assertEqual(descriptor.env["BUDDYSWITCH_ROLE_ID"], "pm")
        self.assertNotIn("BUDDYSWITCH_TEST_PRIVATE_SENTINEL", descriptor.env)
        self.assertEqual(descriptor.env["HOME"], str(expected_instance_root / "home"))
        self.assertEqual(descriptor.env["CODEX_HOME"], str(expected_instance_root / "codex-home"))
        self.assertEqual(descriptor.env["XDG_CONFIG_HOME"], str(expected_instance_root / "xdg-config"))
        self.assertEqual(calls[0]["thread_id"], "thr-attach")
        self.assertEqual(calls[0]["workspace_dir"], expected_workspace)
        self.assertEqual(calls[0]["shared_project_workspace_dir"], instance_json.parents[2].resolve(strict=False) / "project" / "workspace")
        self.assertEqual(descriptor.env["BUDDYSWITCH_PROJECT_WORKSPACE_DIR"], str(instance_json.parents[2].resolve(strict=False) / "project" / "workspace"))
        self.assertEqual(calls[0]["permissions"], "buddyswitch-runtime")

    def test_resolve_attach_requires_recorded_codex_runtime_before_app_server_call(self) -> None:
        instance_json = self._write_instance(thread_id="thr-attach")
        payload = json.loads(instance_json.read_text(encoding="utf-8"))
        payload.pop("codex_runtime")
        instance_json.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        calls: list[bool] = []
        original_resume = self.actor_session.app_server.thread_resume

        def fake_resume(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            calls.append(True)
            return {"thread": {"id": "thr-attach"}}

        self.addCleanup(setattr, self.actor_session.app_server, "thread_resume", original_resume)
        self.actor_session.app_server.thread_resume = fake_resume
        session = self.actor_session.ActorSession(shared_root=instance_json.parents[2])

        with self.assertRaises(self.actor_session.codex_runtime.CodexRuntimeError) as raised:
            session.resolve_attach("act-pm-session")

        self.assertEqual(raised.exception.code, "INVALID_RUNTIME_RECORD")
        self.assertEqual(calls, [])

    def test_resolve_attach_rejects_changed_codex_runtime_before_app_server_call(self) -> None:
        instance_json = self._write_instance(thread_id="thr-attach")
        codex_bin = self.root / "bin" / "codex-test"
        codex_bin.write_text("#!/bin/sh\nprintf '%s\\n' 'codex-cli changed-runtime'\n", encoding="utf-8")
        codex_bin.chmod(0o755)
        calls: list[bool] = []
        original_resume = self.actor_session.app_server.thread_resume

        def fake_resume(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            calls.append(True)
            return {"thread": {"id": "thr-attach"}}

        self.addCleanup(setattr, self.actor_session.app_server, "thread_resume", original_resume)
        self.actor_session.app_server.thread_resume = fake_resume
        original_read_version = self.actor_session.codex_runtime._read_version
        self.addCleanup(
            setattr,
            self.actor_session.codex_runtime,
            "_read_version",
            original_read_version,
        )
        self.actor_session.codex_runtime.validate_codex_runtime = self._validate_codex_runtime
        self.actor_session.codex_runtime._read_version = (
            lambda _executable, *, code: "codex-cli changed-runtime"
        )
        session = self.actor_session.ActorSession(shared_root=instance_json.parents[2])

        with self.assertRaises(self.actor_session.codex_runtime.CodexRuntimeError) as raised:
            session.resolve_attach("act-pm-session")

        self.assertEqual(raised.exception.code, "RUNTIME_MISMATCH")
        self.assertEqual(calls, [])

    def test_resolve_attach_rejects_tampered_absolute_instance_root_and_workspace_dir(self) -> None:
        instance_json = self._write_instance(thread_id="thr-attach", app_server_socket="/tmp/app-server-attach.sock")
        payload = json.loads(instance_json.read_text(encoding="utf-8"))
        payload["instance_root"] = str(self.root / "attacker-instance")
        payload["workspace_dir"] = str(self.root / "attacker-workspace")
        instance_json.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        original_resume = self.actor_session.app_server.thread_resume

        def fake_resume(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {"thread": {"id": "thr-attach"}}

        self.addCleanup(setattr, self.actor_session.app_server, "thread_resume", original_resume)
        self.actor_session.app_server.thread_resume = fake_resume
        session = self.actor_session.ActorSession(shared_root=instance_json.parents[2])

        with self.assertRaisesRegex(self.actor_session.ActorSessionError, "instance root"):
            session.resolve_attach("act-pm-session")

    def test_resolve_attach_rejects_tampered_relative_instance_root_and_workspace_dir(self) -> None:
        instance_json = self._write_instance(thread_id="thr-attach", app_server_socket="/tmp/app-server-attach.sock")
        payload = json.loads(instance_json.read_text(encoding="utf-8"))
        payload["instance_root"] = "../attacker-instance"
        payload["workspace_dir"] = "../attacker-workspace"
        instance_json.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        original_resume = self.actor_session.app_server.thread_resume

        def fake_resume(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {"thread": {"id": "thr-attach"}}

        self.addCleanup(setattr, self.actor_session.app_server, "thread_resume", original_resume)
        self.actor_session.app_server.thread_resume = fake_resume
        session = self.actor_session.ActorSession(shared_root=instance_json.parents[2])

        with self.assertRaisesRegex(self.actor_session.ActorSessionError, "instance root"):
            session.resolve_attach("act-pm-session")

    def test_resolve_attach_rejects_tampered_absolute_project_workspace_dir(self) -> None:
        instance_json = self._write_instance(thread_id="thr-attach", app_server_socket="/tmp/app-server-attach.sock")
        payload = json.loads(instance_json.read_text(encoding="utf-8"))
        payload["project_workspace_dir"] = str(self.root / "attacker-project" / "workspace")
        instance_json.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        original_resume = self.actor_session.app_server.thread_resume
        calls: list[dict[str, Any]] = []

        def fake_resume(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            calls.append({"called": True})
            return {"thread": {"id": "thr-attach"}}

        self.addCleanup(setattr, self.actor_session.app_server, "thread_resume", original_resume)
        self.actor_session.app_server.thread_resume = fake_resume
        session = self.actor_session.ActorSession(shared_root=instance_json.parents[2])

        with self.assertRaisesRegex(self.actor_session.ActorSessionError, "project workspace"):
            session.resolve_attach("act-pm-session")
        self.assertEqual(calls, [])

    def test_resolve_attach_rejects_tampered_relative_project_workspace_dir(self) -> None:
        instance_json = self._write_instance(thread_id="thr-attach", app_server_socket="/tmp/app-server-attach.sock")
        payload = json.loads(instance_json.read_text(encoding="utf-8"))
        payload["project_workspace_dir"] = "../attacker-project/workspace"
        instance_json.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        original_resume = self.actor_session.app_server.thread_resume
        calls: list[dict[str, Any]] = []

        def fake_resume(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            calls.append({"called": True})
            return {"thread": {"id": "thr-attach"}}

        self.addCleanup(setattr, self.actor_session.app_server, "thread_resume", original_resume)
        self.actor_session.app_server.thread_resume = fake_resume
        session = self.actor_session.ActorSession(shared_root=instance_json.parents[2])

        with self.assertRaisesRegex(self.actor_session.ActorSessionError, "project workspace"):
            session.resolve_attach("act-pm-session")
        self.assertEqual(calls, [])

    def test_exec_attach_uses_os_execvpe_with_resolved_descriptor(self) -> None:
        instance_json = self._write_instance(thread_id="thr-exec", app_server_socket="/tmp/app-server-exec.sock")
        original_resume = self.actor_session.app_server.thread_resume
        original_execvpe = self.actor_session.os.execvpe
        exec_calls: list[dict[str, Any]] = []

        def fake_resume(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {"thread": {"id": "thr-exec"}}

        def fake_execvpe(file: str, argv: tuple[str, ...], env: dict[str, str]) -> None:
            exec_calls.append({"file": file, "argv": argv, "env": env})
            raise RuntimeError("execvpe called")

        self.addCleanup(setattr, self.actor_session.app_server, "thread_resume", original_resume)
        self.addCleanup(setattr, self.actor_session.os, "execvpe", original_execvpe)
        self.actor_session.app_server.thread_resume = fake_resume
        self.actor_session.os.execvpe = fake_execvpe
        session = self.actor_session.ActorSession(shared_root=instance_json.parents[2])

        with self.assertRaisesRegex(RuntimeError, "execvpe called"):
            session.exec_attach("act-pm-session")

        self.assertEqual(exec_calls[0]["file"], str((self.root / "bin" / "codex-test").resolve(strict=False)))
        self.assertEqual(exec_calls[0]["argv"][-1], "thr-exec")
        self.assertEqual(exec_calls[0]["env"]["BUDDYSWITCH_ACTOR_ID"], "act-pm-session")

    def test_actor_session_source_has_no_task_sys_or_side_handoff_runtime_coupling(self) -> None:
        source = ACTOR_SESSION_PATH.read_text(encoding="utf-8")
        forbidden = (
            "task_sys",
            "task_sys_ingress",
            "task_sys_runtime_client",
            "task_id",
            "side_thread",
            "task_sys.side_frame",
            "handoff",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, source)
