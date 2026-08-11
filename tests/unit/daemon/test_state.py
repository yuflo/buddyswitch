"""Tests for the current-only generic daemon state owner."""

from __future__ import annotations

import ast
import importlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock


from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
DAEMON_STATE_PATH = ROOT / "src" / "buddyswitch" / "foundation" / "daemon" / "state.py"
DAEMON_CORE_PATH = ROOT / "src" / "buddyswitch" / "foundation" / "daemon" / "instance.py"
EXPECTED_CURRENT_STATE_KEYS = frozenset(
    {
        "actor_id",
        "main_thread_id",
        "ready",
        "last_error",
        "handlers",
        "scheduled_trigger_ids",
        "scheduled_triggers",
    }
)


def _load_state_module() -> Any:
    if not DAEMON_STATE_PATH.exists():
        raise AssertionError(f"expected module to exist: {DAEMON_STATE_PATH}")
    return importlib.reload(importlib.import_module("buddyswitch.foundation.daemon.state"))


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if module_name:
                imported.add(module_name)
            imported.update(
                f"{module_name}.{alias.name}" if module_name else alias.name
                for alias in node.names
            )
    return imported


class DaemonStateTests(unittest.TestCase):
    def test_state_module_exists(self) -> None:
        self.assertTrue(DAEMON_STATE_PATH.exists(), DAEMON_STATE_PATH)

    def test_current_state_keys_are_exact(self) -> None:
        state_module = _load_state_module()
        self.assertEqual(state_module.CURRENT_STATE_KEYS, EXPECTED_CURRENT_STATE_KEYS)

    def test_new_state_uses_exact_current_payload_and_atomic_save(self) -> None:
        state_module = _load_state_module()
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instance"
            state = state_module.DaemonState.load(
                instance_root=instance_root,
                actor_id="act-dev-state-current",
                main_thread_id="thr-state-main",
            )

            self.assertEqual(set(state.payload), EXPECTED_CURRENT_STATE_KEYS)
            self.assertEqual(state.payload["actor_id"], "act-dev-state-current")
            self.assertEqual(state.payload["main_thread_id"], "thr-state-main")
            state.record_ready(pid=4321, main_thread_id="thr-state-main")

            saved = json.loads(state.path.read_text(encoding="utf-8"))
            self.assertEqual(saved["ready"]["pid"], 4321)
            self.assertEqual(list(state.path.parent.glob(f".{state.path.name}.*.tmp")), [])

    def test_non_object_state_is_rejected(self) -> None:
        state_module = _load_state_module()
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instance"
            path = state_module.daemon_state_file(instance_root)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("[]\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "daemon state must contain an object"):
                state_module.DaemonState.load(
                    instance_root=instance_root,
                    actor_id="act-dev-state-current",
                    main_thread_id="thr-state-main",
                )

    def test_unknown_state_field_is_rejected_without_rewrite(self) -> None:
        state_module = _load_state_module()
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instance"
            path = state_module.daemon_state_file(instance_root)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps({"actor_id": "act-dev-state-current", "unexpected_field": {}}) + "\n",
                encoding="utf-8",
            )
            original = path.read_text(encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "unsupported fields.*unexpected_field"):
                state_module.DaemonState.load(
                    instance_root=instance_root,
                    actor_id="act-dev-state-current",
                    main_thread_id="thr-state-main",
                )

            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_handler_state_contains_only_current_dispatch_facts(self) -> None:
        state_module = _load_state_module()
        with tempfile.TemporaryDirectory() as temp_root:
            state = state_module.DaemonState.load(
                instance_root=Path(temp_root) / "instance",
                actor_id="act-dev-state-current",
                main_thread_id="thr-state-main",
            )
            state.register_handlers(["example_handler"])
            state.record_handler_result(
                "example_handler",
                type("Result", (), {"status": "handled", "message": None})(),
                origin_turn_id="turn-current-1",
            )

            handler = state.payload["handlers"]["example_handler"]
            self.assertEqual(
                set(handler),
                {"registered", "enabled", "active", "last_result", "last_handled_at", "last_error"},
            )
            self.assertEqual(handler["last_result"], "handled")
            self.assertIsNone(handler["last_error"])

    def test_handler_checkpoint_persists_opaque_consumer_identity(self) -> None:
        state_module = _load_state_module()
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instance"
            state = state_module.DaemonState.load(
                instance_root=instance_root,
                actor_id="act-dev-state-current",
                main_thread_id="thr-state-main",
            )
            state.update_handler_state(
                "task_sys_progress_check",
                {
                    "checkpoint": {
                        "source_turn_id": "turn-parent-work-1",
                        "submitted_turn_id": "turn-parent-check-1",
                    }
                },
            )

            reloaded = state_module.DaemonState.load(
                instance_root=instance_root,
                actor_id="act-dev-state-current",
                main_thread_id="thr-state-main",
            )

            self.assertEqual(
                reloaded.handler_state("task_sys_progress_check")["checkpoint"],
                {
                    "source_turn_id": "turn-parent-work-1",
                    "submitted_turn_id": "turn-parent-check-1",
                },
            )

    def test_owner_scoped_schedule_cancellation_preserves_other_schedules(self) -> None:
        state_module = _load_state_module()
        with tempfile.TemporaryDirectory() as temp_root:
            state = state_module.DaemonState.load(
                instance_root=Path(temp_root) / "instance",
                actor_id="act-dev-state-current",
                main_thread_id="thr-state-main",
            )
            browser = state.create_schedule(
                delay_seconds=60,
                trigger_type="example.browser",
                payload={},
                source_context={"owner": "browser"},
                now="2026-07-12T00:00:00Z",
            )
            other = state.create_schedule(
                delay_seconds=60,
                trigger_type="example.other",
                payload={},
                source_context={"owner": "other"},
                now="2026-07-12T00:00:00Z",
            )

            canceled = state_module.cancel_pending_schedules_by_source_owner(
                instance_root=Path(temp_root) / "instance",
                actor_id="act-dev-state-current",
                main_thread_id="thr-state-main",
                source_owner="browser",
                now="2026-07-12T00:00:10Z",
            )

            self.assertEqual([row["schedule_id"] for row in canceled], [browser["schedule_id"]])
            saved = state_module.DaemonState.load(
                instance_root=Path(temp_root) / "instance",
                actor_id="act-dev-state-current",
                main_thread_id="thr-state-main",
            )
            self.assertEqual(saved.payload["scheduled_triggers"][browser["schedule_id"]]["status"], "canceled")
            self.assertEqual(saved.payload["scheduled_triggers"][other["schedule_id"]]["status"], "pending")

    def test_public_owner_cancellation_preserves_mismatched_actor_and_thread_state(self) -> None:
        state_module = _load_state_module()
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instance"
            state = state_module.DaemonState.load(
                instance_root=instance_root,
                actor_id="act-dev-state-current",
                main_thread_id="thr-state-main",
            )
            schedule = state.create_schedule(
                delay_seconds=60,
                trigger_type="example.owner",
                payload={},
                source_context={"owner": "example-owner"},
                now="2026-07-12T00:00:00Z",
            )
            original = state_module.daemon_state_file(instance_root).read_text(encoding="utf-8")

            wrong_actor = state_module.cancel_pending_schedules_by_source_owner(
                instance_root=instance_root,
                actor_id="act-dev-state-other",
                main_thread_id="thr-state-main",
                source_owner="example-owner",
            )
            wrong_thread = state_module.cancel_pending_schedules_by_source_owner(
                instance_root=instance_root,
                actor_id="act-dev-state-current",
                main_thread_id="thr-state-other",
                source_owner="example-owner",
            )

            self.assertEqual(wrong_actor, [])
            self.assertEqual(wrong_thread, [])
            self.assertEqual(state_module.daemon_state_file(instance_root).read_text(encoding="utf-8"), original)
            persisted = json.loads(original)
            self.assertEqual(persisted["scheduled_triggers"][schedule["schedule_id"]]["status"], "pending")

    def test_public_owner_cancellation_missing_state_is_empty_and_does_not_create_file(self) -> None:
        state_module = _load_state_module()
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instance"

            canceled = state_module.cancel_pending_schedules_by_source_owner(
                instance_root=instance_root,
                actor_id="act-dev-state-current",
                main_thread_id="thr-state-main",
                source_owner="example-owner",
            )
            canceled_without_thread = state_module.cancel_pending_schedules_by_source_owner(
                instance_root=instance_root,
                actor_id="act-dev-state-current",
                main_thread_id=None,
                source_owner="example-owner",
            )

            self.assertEqual(canceled, [])
            self.assertEqual(canceled_without_thread, [])
            self.assertFalse(state_module.daemon_state_file(instance_root).exists())

    def test_public_owner_cancellation_propagates_save_failure(self) -> None:
        state_module = _load_state_module()
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instance"
            state = state_module.DaemonState.load(
                instance_root=instance_root,
                actor_id="act-dev-state-current",
                main_thread_id="thr-state-main",
            )
            state.create_schedule(
                delay_seconds=60,
                trigger_type="example.owner",
                payload={},
                source_context={"owner": "example-owner"},
                now="2026-07-12T00:00:00Z",
            )

            with mock.patch.object(state_module.DaemonState, "save", side_effect=OSError("state save failed")):
                with self.assertRaisesRegex(OSError, "state save failed"):
                    state_module.cancel_pending_schedules_by_source_owner(
                        instance_root=instance_root,
                        actor_id="act-dev-state-current",
                        main_thread_id="thr-state-main",
                        source_owner="example-owner",
                    )

    def test_state_module_has_no_core_or_product_imports(self) -> None:
        self.assertTrue(DAEMON_STATE_PATH.exists(), DAEMON_STATE_PATH)
        imports = _imported_modules(DAEMON_STATE_PATH)
        forbidden = ("instance", "task_sys", "im_", "track_", "browser_", "web_management", "buddyswitch.env.repos")
        self.assertFalse([name for name in imports if any(token in name for token in forbidden)], imports)

    def test_core_does_not_define_or_reexport_state(self) -> None:
        source = DAEMON_CORE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(DAEMON_CORE_PATH))
        class_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
        assignments = {
            target.id
            for node in ast.walk(tree)
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
            if isinstance(target, ast.Name)
        }
        self.assertNotIn("DaemonState", class_names)
        self.assertNotIn("DaemonState", assignments)
