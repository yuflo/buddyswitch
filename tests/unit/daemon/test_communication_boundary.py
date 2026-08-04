"""Boundary tests for the new daemon communication path."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
DAEMON_OWNED_FILES = [
    ROOT / "src" / "buddyswitch" / "launcher" / "daemon_core.py",
    ROOT / "src" / "buddyswitch" / "launcher" / "instance_daemon.py",
    ROOT / "src" / "buddyswitch" / "launcher" / "notification_center.py",
    ROOT / "src/buddyswitch/modules/communication/private/adapters/daemon/message_inbound.py",
    ROOT / "src" / "buddyswitch" / "modules" / "track" / "private" / "adapters" / "daemon" / "track_comment_inbound.py",
    ROOT / "src" / "buddyswitch" / "launcher" / "central_daemon.py",
    ROOT / "src" / "buddyswitch" / "launcher" / "central_daemon_core.py",
    ROOT / "src" / "buddyswitch" / "launcher" / "daemon_mailbox.py",
    ROOT / "src/buddyswitch/modules/communication/private/adapters/daemon/im_wake_handler.py",
    ROOT / "src" / "buddyswitch" / "modules" / "track" / "private" / "adapters" / "daemon" / "track_comment_added_handler.py",
    ROOT / "src" / "buddyswitch" / "modules" / "demand" / "private" / "adapters" / "daemon" / "demand_triage_handler.py",
    ROOT / "src" / "buddyswitch" / "modules" / "task" / "private" / "adapters" / "goal" / "handler.py",
    ROOT / "src" / "buddyswitch" / "modules" / "demand" / "private" / "adapters" / "daemon" / "demand_orchestration_handler.py",
    ROOT / "src" / "buddyswitch" / "foundation" / "daemon" / "client.py",
    ROOT / "src" / "buddyswitch" / "foundation" / "tool_runtime" / "context.py",
]
DAEMON_CONTRACTS_PATH = ROOT / "src" / "buddyswitch" / "launcher" / "daemon_contracts.py"
CONTEXT_PATH = ROOT / "src" / "buddyswitch" / "foundation" / "tool_runtime" / "context.py"
DAEMON_CLIENT_PATH = ROOT / "src" / "buddyswitch" / "foundation" / "daemon" / "client.py"
IM_ACTOR_DELIVERY_PATH = ROOT / "src/buddyswitch/modules/communication/private/adapters/actor/im_actor_delivery.py"
PRODUCT_HANDLER_PATHS = (
    ROOT / "src/buddyswitch/modules/communication/private/adapters/daemon/im_wake_handler.py",
    ROOT / "src" / "buddyswitch" / "modules" / "track" / "private" / "adapters" / "daemon" / "track_comment_added_handler.py",
    ROOT / "src" / "buddyswitch" / "modules" / "demand" / "private" / "adapters" / "daemon" / "demand_triage_handler.py",
    ROOT / "src" / "buddyswitch" / "modules" / "task" / "private" / "adapters" / "goal" / "handler.py",
    ROOT / "src" / "buddyswitch" / "modules" / "demand" / "private" / "adapters" / "daemon" / "demand_orchestration_handler.py",
    ROOT / "src" / "buddyswitch" / "launcher" / "browser_page_expired_handler.py",
    ROOT / "src" / "buddyswitch" / "launcher" / "browser_release_handler.py",
)


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
    def test_explicit_capabilities_replace_daemon_service_locator(self) -> None:
        self.assertTrue(IM_ACTOR_DELIVERY_PATH.exists(), IM_ACTOR_DELIVERY_PATH)
        context_source = CONTEXT_PATH.read_text(encoding="utf-8")
        context_tree = ast.parse(context_source, filename=str(CONTEXT_PATH))
        class_names = {node.name for node in ast.walk(context_tree) if isinstance(node, ast.ClassDef)}
        self.assertNotIn("Daemon" + "Access", class_names)
        self.assertNotIn("TaskGoalRuntimeAccess", class_names)
        self.assertNotIn('"daemon"', context_source)
        for name in ("_ActorDirectoryAccess", "_SignalDeliveryAccess"):
            self.assertIn(name, class_names)
        self.assertNotIn("ActorDirectoryAccess", class_names)
        self.assertNotIn("SignalDeliveryAccess", class_names)
        self.assertNotIn("ImActorDeliveryAccess", class_names)
        self.assertNotIn("im_actor_delivery", context_source)

    def test_generic_daemon_client_contains_no_im_product_delivery(self) -> None:
        source = DAEMON_CLIENT_PATH.read_text(encoding="utf-8")
        for token in (
            "wake_" + "im_actor",
            "im.message.created",
            "conversation_id",
            "event_id",
            "actor_handling_status",
            "runtime_target",
        ):
            self.assertNotIn(token, source)

    def test_product_handlers_depend_on_stable_contracts_not_core(self) -> None:
        self.assertTrue(DAEMON_CONTRACTS_PATH.exists(), DAEMON_CONTRACTS_PATH)
        for path in PRODUCT_HANDLER_PATHS:
            imports = _imported_modules(path)
            with self.subTest(path=path.name):
                self.assertIn("buddyswitch.launcher.daemon_contracts", imports)
                self.assertNotIn("buddyswitch.launcher.daemon_core", imports)

    def test_daemon_uses_central_client_not_daemon_presence_helper(self) -> None:
        imports_by_file = {path: _imported_modules(path) for path in _existing_sources()}
        flattened = {module for imports in imports_by_file.values() for module in imports}

        self.assertIn("buddyswitch.foundation.daemon.client", flattened)
        self.assertNotIn("buddyswitch.env.tool_runtime.daemon_presence", flattened)
        self.assertFalse((ROOT / "src" / "buddyswitch" / "env" / "tool_runtime" / "daemon_presence.py").exists())

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
        source += "\n" + _class_source(CONTEXT_PATH, "_SignalDeliveryAccess")

        self.assertNotIn("to_role: str", source)
        self.assertNotIn("to_role=", source)
        self.assertNotIn("notify_message" + "_available", source)
        self.assertNotIn("resolve_notification_target", source)
        self.assertNotIn("ambiguous_online_actor", source)

    def test_daemon_base_delivery_uses_generic_signal_not_message_event_shape(self) -> None:
        base_files = [
            path
            for path in _existing_sources()
            if path.name
            not in {
                "message" + "_available" + "_handler.py",
                "message_inbound.py",
                "track_comment_added_handler.py",
                "track_comment_inbound.py",
                "im_wake_handler.py",
                "context.py",
            }
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
        self.assertNotIn("message" + "_available" + "_event", source)
        self.assertNotIn("validate_mailbox_event", source)
        self.assertNotIn("handle_mailbox_event", source)
        self.assertNotIn("from_actor_address", source)
        self.assertNotIn("to_actor_address", source)
        self.assertNotIn('"message_id"', source)
        self.assertNotIn('"track_id"', source)
        self.assertNotIn('"comment_id"', source)

    def test_im_wake_handler_owns_im_signal_payload_semantics(self) -> None:
        handler_source = (
            ROOT
            / "src/buddyswitch/modules/communication/private/adapters/daemon/im_wake_handler.py"
        ).read_text(encoding="utf-8")

        self.assertIn("im.message.created", handler_source)
        self.assertIn("message_id", handler_source)
        self.assertIn("def handle(", handler_source)
        self.assertNotIn("def handle_signal(", handler_source)

    def test_track_comment_handler_owns_track_signal_payload_semantics(self) -> None:
        handler_path = (
            ROOT
            / "src"
            / "buddyswitch"
            / "modules"
            / "track"
            / "private"
            / "adapters"
            / "daemon"
            / "track_comment_added_handler.py"
        )
        handler_source = handler_path.read_text(encoding="utf-8")
        handler_imports = _imported_modules(handler_path)
        nc_source = (ROOT / "src" / "buddyswitch" / "launcher" / "notification_center.py").read_text(encoding="utf-8")

        self.assertIn("track.comment.added", handler_source)
        self.assertIn("track_id", handler_source)
        self.assertIn("comment_id", handler_source)
        self.assertIn("thread_id", handler_source)
        self.assertIn("def handle(", handler_source)
        self.assertIn("buddyswitch.modules.demand.public", handler_imports)
        self.assertFalse(any("task_sys" in name for name in handler_imports), msg=handler_imports)
        self.assertNotIn("track_id", nc_source)
        self.assertNotIn("comment_id", nc_source)
        self.assertNotIn(
            "buddyswitch.modules.track.private.state.track_comments",
            nc_source,
        )

    def test_mailbox_exposes_local_trigger_not_business_specific_parent_required_method(self) -> None:
        mailbox_source = (ROOT / "src" / "buddyswitch" / "launcher" / "daemon_mailbox.py").read_text(encoding="utf-8")

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

    def test_no_artifact_inbound_is_implemented_for_this_task(self) -> None:
        production_files = [
            path
            for base in (ROOT / "tools", ROOT / "scripts")
            for path in base.rglob("*.py")
            if "__pycache__" not in path.parts
        ]
        source = "\n".join(path.read_text(encoding="utf-8") for path in production_files)

        forbidden = ["artifact.shared", "ArtifactSharedHandler", "artifact_inbound"]
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, source)
