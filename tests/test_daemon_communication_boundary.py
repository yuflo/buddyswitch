#!/usr/bin/env python3
"""Boundary tests for the new daemon communication path."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAEMON_OWNED_FILES = [
    ROOT / "tools" / "launcher" / "daemon_core.py",
    ROOT / "tools" / "launcher" / "instance_daemon.py",
    ROOT / "tools" / "launcher" / "notification_center.py",
    ROOT / "tools" / "launcher" / "message_inbound.py",
    ROOT / "tools" / "launcher" / "central_daemon.py",
    ROOT / "tools" / "launcher" / "central_daemon_core.py",
    ROOT / "tools" / "launcher" / "daemon_mailbox.py",
    ROOT / "tools" / "launcher" / "message_available_handler.py",
    ROOT / "scripts" / "env" / "tool_runtime" / "daemon_client.py",
    ROOT / "scripts" / "env" / "tool_runtime" / "context.py",
]


def _existing_sources() -> list[Path]:
    return [path for path in DAEMON_OWNED_FILES if path.exists()]


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
            for alias in node.names:
                imported.add(f"{module_name}.{alias.name}" if module_name else alias.name)
    return imported


def _class_source(path: Path, class_name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return ast.get_source_segment(source, node) or ""
    raise AssertionError(f"{class_name} not found in {path}")


def _source_without_functions(path: Path, excluded_names: set[str]) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    segments: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in excluded_names:
            segment = ast.get_source_segment(source, node)
            if segment:
                segments.append(segment)
    for segment in segments:
        source = source.replace(segment, "")
    return source


class DaemonCommunicationBoundaryTests(unittest.TestCase):
    def test_daemon_uses_central_client_not_daemon_presence_helper(self) -> None:
        imports_by_file = {path: _imported_modules(path) for path in _existing_sources()}
        flattened = {module for imports in imports_by_file.values() for module in imports}

        self.assertIn("env.tool_runtime.daemon_client", flattened)
        self.assertNotIn("env.tool_runtime.daemon_presence", flattened)
        self.assertFalse((ROOT / "scripts" / "env" / "tool_runtime" / "daemon_presence.py").exists())

    def test_no_direct_notification_file_append_endpoint_in_daemon_delivery(self) -> None:
        delivery_files = [
            path
            for path in _existing_sources()
            if path.name not in {"central_daemon.py"}
        ]
        source = "\n".join(path.read_text(encoding="utf-8") for path in delivery_files)

        self.assertNotIn("notifications.jsonl", source)
        self.assertNotIn('"daemon_state_file"', source)
        self.assertNotIn("'daemon_state_file'", source)
        self.assertNotIn("_append_event_to_endpoint", source)
        self.assertNotIn("open(\"a\"", source)

    def test_no_fuzzy_to_role_or_ambiguous_status_in_daemon_delivery_path(self) -> None:
        daemon_delivery_files = [
            path
            for path in _existing_sources()
            if path.name not in {"context.py"}
        ]
        source = "\n".join(path.read_text(encoding="utf-8") for path in daemon_delivery_files)
        source += "\n" + _class_source(ROOT / "scripts" / "env" / "tool_runtime" / "context.py", "DaemonAccess")

        self.assertNotIn("to_role: str", source)
        self.assertNotIn("to_role=", source)
        self.assertNotIn("notify_message_available", source)
        self.assertNotIn("resolve_notification_target", source)
        self.assertNotIn("ambiguous_online_actor", source)

    def test_daemon_base_delivery_uses_generic_signal_not_message_event_shape(self) -> None:
        base_files = [
            path
            for path in _existing_sources()
            if path.name not in {"message_available_handler.py", "message_inbound.py", "context.py"}
        ]
        chunks = []
        for path in base_files:
            if path.name == "daemon_mailbox.py":
                chunks.append(_source_without_functions(path, {"_validate_local_trigger_request"}))
            else:
                chunks.append(path.read_text(encoding="utf-8"))
        source = "\n".join(chunks)

        self.assertIn("signal.deliver", source)
        self.assertIn("deliver_signal", source)
        self.assertIn("validate_daemon_signal", source)
        self.assertNotIn("message_available_event", source)
        self.assertNotIn("validate_mailbox_event", source)
        self.assertNotIn("handle_mailbox_event", source)
        self.assertNotIn("from_actor_address", source)
        self.assertNotIn("to_actor_address", source)
        self.assertNotIn('"message_id"', source)

    def test_message_available_handler_owns_message_signal_payload_semantics(self) -> None:
        handler_source = (ROOT / "tools" / "launcher" / "message_available_handler.py").read_text(encoding="utf-8")

        self.assertIn("message.available", handler_source)
        self.assertIn("message_id", handler_source)
        self.assertIn("def handle(", handler_source)
        self.assertNotIn("def handle_signal(", handler_source)

    def test_mailbox_exposes_local_trigger_not_business_specific_parent_required_method(self) -> None:
        mailbox_source = (ROOT / "tools" / "launcher" / "daemon_mailbox.py").read_text(encoding="utf-8")

        self.assertIn("mailbox.local_trigger", mailbox_source)
        self.assertNotIn("mailbox.parent_required", mailbox_source)
        self.assertNotIn("_dispatch_parent_required", mailbox_source)
        self.assertNotIn("_validate_parent_required_request", mailbox_source)

    def test_no_actor_facing_notification_lifecycle_or_nc_wrapper_event(self) -> None:
        production_files = [
            path
            for base in (ROOT / "tools", ROOT / "scripts")
            for path in base.rglob("*.py")
            if "__pycache__" not in path.parts
        ]
        source = "\n".join(path.read_text(encoding="utf-8") for path in production_files)

        forbidden = [
            "notification.mark",
            "notification.archive",
            "notification.needs_parent",
            "notification__mark",
            "notification__archive",
            "notification__needs_parent",
            "nc.notification",
        ]
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
