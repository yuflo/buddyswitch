"""Architecture and boundary tests for daemon core decoupling."""

from __future__ import annotations

import ast
import builtins
import importlib
import json
import os
import sys
import tempfile
import unittest
from itertools import count
from pathlib import Path
from typing import Any


from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
DAEMON_CORE_PATH = ROOT / "tools" / "launcher" / "daemon_core.py"
DAEMON_CONTRACTS_PATH = ROOT / "tools" / "launcher" / "daemon_contracts.py"
DAEMON_STATE_PATH = ROOT / "tools" / "launcher" / "daemon_state.py"
INSTANCE_DAEMON_PATH = ROOT / "tools" / "launcher" / "instance_daemon.py"
CENTRAL_DAEMON_CORE_PATH = ROOT / "tools" / "launcher" / "central_daemon_core.py"
IM_WAKE_HANDLER_PATH = ROOT / "tools" / "launcher" / "im_wake_handler.py"
DAEMON_MAILBOX_PATH = ROOT / "tools" / "launcher" / "daemon_mailbox.py"
DAEMON_RUNTIME_PATH = ROOT / "tools" / "launcher" / "daemon_runtime.py"
BROWSER_RUNTIME_MANAGER_PATH = ROOT / "tools" / "launcher" / "browser_runtime_manager.py"
DAEMON_CLIENT_PATH = ROOT / "scripts" / "env" / "tool_runtime" / "daemon_client.py"
NOTIFICATION_CENTER_PATH = ROOT / "tools" / "launcher" / "notification_center.py"
MODULE_COUNTER = count()
TASK_DOMAIN_IMPORTS = {"env.domain.task_management", "env.domain.task_tui"}
TASK_DOMAIN_SYMBOLS = {"task_management", "task_tui"}
RUNTIME_ENV_KEYS = (
    "BUDDYSWITCH_SHARED_ROOT",
    "BUDDYSWITCH_STATE_ROOT",
    "BUDDYSWITCH_INSTANCE_ROOT",
    "BUDDYSWITCH_INSTANCE_JSON",
    "BUDDYSWITCH_WORKSPACE_DIR",
    "BUDDYSWITCH_ACTOR_ID",
    "BUDDYSWITCH_ROLE_ID",
)


def _load_module(path: Path, *, block_task_imports: bool = False) -> Any:
    if not path.exists():
        raise AssertionError(f"expected module to exist: {path}")
    module = importlib.import_module(path.stem)
    if not block_task_imports:
        return importlib.reload(module)

    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] | list[str] = (),
        level: int = 0,
    ) -> Any:
        fromlist_items = tuple(fromlist or ())
        if name in TASK_DOMAIN_IMPORTS:
            raise AssertionError(f"blocked task-domain import: {name}")
        if name == "env.domain" and TASK_DOMAIN_SYMBOLS.intersection(fromlist_items):
            raise AssertionError(f"blocked task-domain import via env.domain: {fromlist_items!r}")
        return original_import(name, globals, locals, fromlist, level)

    try:
        builtins.__import__ = guarded_import
        module = importlib.reload(module)
    finally:
        builtins.__import__ = original_import
    return module


def _imported_modules(path: Path) -> set[str]:
    if not path.exists():
        raise AssertionError(f"expected source file to exist: {path}")
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


class StopDaemonLoop(RuntimeError):
    pass


class FakeRunDaemonClient:
    def __init__(self, *, notifications: list[dict[str, object] | BaseException]) -> None:
        self.notifications = list(notifications)
        self.requests: list[dict[str, object]] = []

    def __enter__(self) -> FakeRunDaemonClient:
        return self

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        return None

    def request(self, method: str, params: dict[str, object] | None) -> dict[str, object]:
        self.requests.append({"method": method, "params": params or {}})
        if method == "thread/resume":
            thread_id = (params or {}).get("threadId")
            return {"thread": {"id": thread_id}}
        raise AssertionError(f"unexpected request method: {method}")

    def read_notification(self) -> dict[str, object]:
        if not self.notifications:
            raise StopDaemonLoop("stop")
        item = self.notifications.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


class DaemonCoreDecouplingTests(unittest.TestCase):
    def setUp(self) -> None:
        saved_runtime_env = {key: os.environ.get(key) for key in RUNTIME_ENV_KEYS}
        self.addCleanup(self._restore_runtime_env, saved_runtime_env)

    def _restore_runtime_env(self, values: dict[str, str | None]) -> None:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        runtime_files = sys.modules.get("env.repos.runtime_files")
        if runtime_files is not None:
            runtime_files.refresh_runtime_roots_from_env()

    def test_generic_daemon_command_modules_have_no_task_runtime_semantics(self) -> None:
        for path in (DAEMON_MAILBOX_PATH, DAEMON_RUNTIME_PATH, DAEMON_CLIENT_PATH):
            source = path.read_text(encoding="utf-8")
            imports = _imported_modules(path)
            with self.subTest(path=path.name):
                self.assertFalse([name for name in imports if "task_sys" in name], imports)
                self.assertNotIn("task_sys", source)
                self.assertNotIn("Task Sys", source)

        core_source = DAEMON_CORE_PATH.read_text(encoding="utf-8")
        for token in (
            "task_sys_runtime",
            "task_sys_daemon_adapter",
            "task_sys_" + "dispatcher",
            "execute_" + "task_sys_instruction",
            "cleanup_" + "task_sys_side_lease",
            "mailbox." + "task_sys",
        ):
            self.assertNotIn(token, core_source)

    def test_instance_daemon_is_only_generic_daemon_task_adapter_composition_root(self) -> None:
        candidates = sorted((ROOT / "tools" / "launcher").glob("*.py"))
        combined = []
        for path in candidates:
            imports = _imported_modules(path)
            if "daemon_core" in imports and "task_sys_daemon_adapter" in imports:
                combined.append(path.name)
        self.assertEqual(combined, ["instance_daemon.py"])

    def test_current_state_is_owned_outside_daemon_core(self) -> None:
        self.assertTrue(DAEMON_STATE_PATH.exists(), DAEMON_STATE_PATH)
        core_tree = ast.parse(DAEMON_CORE_PATH.read_text(encoding="utf-8"), filename=str(DAEMON_CORE_PATH))
        core_classes = {node.name for node in ast.walk(core_tree) if isinstance(node, ast.ClassDef)}
        self.assertNotIn("DaemonState", core_classes)
        self.assertIn("daemon_state", _imported_modules(DAEMON_CORE_PATH))
        self.assertNotIn("daemon_core", _imported_modules(DAEMON_STATE_PATH))

    def test_browser_runtime_manager_uses_only_public_daemon_state_api(self) -> None:
        source = BROWSER_RUNTIME_MANAGER_PATH.read_text(encoding="utf-8")
        imports = _imported_modules(BROWSER_RUNTIME_MANAGER_PATH)

        self.assertIn("daemon_state", imports)
        self.assertNotIn("daemon_core", imports)
        for token in (
            "DaemonState",
            "daemon_state_file",
            "state.json",
            "scheduled_trigger_ids",
            "scheduled_triggers",
        ):
            with self.subTest(token=token):
                self.assertNotIn(token, source)

    def test_stable_contracts_are_owned_outside_daemon_core(self) -> None:
        self.assertTrue(DAEMON_CONTRACTS_PATH.exists(), DAEMON_CONTRACTS_PATH)
        core_source = DAEMON_CORE_PATH.read_text(encoding="utf-8")
        core_tree = ast.parse(core_source, filename=str(DAEMON_CORE_PATH))
        core_classes = {node.name for node in ast.walk(core_tree) if isinstance(node, ast.ClassDef)}
        self.assertFalse({"HandlerResult", "DaemonContext", "DaemonHandler"}.intersection(core_classes))

        contract_imports = _imported_modules(DAEMON_CONTRACTS_PATH)
        self.assertNotIn("daemon_core", contract_imports)
        self.assertFalse(
            {
                "task_sys",
                "task_sys_runtime",
                "im_wake_handler",
                "track_comment_added_handler",
                "browser_page_expired_handler",
                "browser_release_handler",
                "web_management",
            }.intersection(contract_imports)
        )

    def _instance(self, temp_root: str) -> dict[str, Path]:
        actor_id = "act-dev-daed00000002"
        instance_root = Path(temp_root) / "instances" / actor_id
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        payload = {
            "actor_id": actor_id,
            "role": "dev",
            "status": "active",
            "instance_root": str(instance_root),
            "workspace_dir": str(workspace_dir),
            "thread_id": "thr-main",
            "app_server_socket": str(instance_root / "runtime" / "app-server.sock"),
        }
        instance_json.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
        return {"instance_root": instance_root, "instance_json": instance_json}

    def _completed(self, *, thread_id: str = "thr-main", turn_id: str = "turn-user-1") -> dict[str, object]:
        return {
            "method": "turn/completed",
            "params": {
                "threadId": thread_id,
                "turn": {
                    "id": turn_id,
                    "items": [],
                    "itemsView": "summary",
                    "status": "completed",
                    "error": None,
                    "startedAt": 0,
                    "completedAt": 1,
                    "durationMs": 1,
                },
            },
        }

    def _patch_app_server_client(self, daemon_core: Any, fake_client: FakeRunDaemonClient) -> None:
        original_client = daemon_core.app_server.AppServerClient

        def fake_factory(*_args: object, **_kwargs: object) -> FakeRunDaemonClient:
            return fake_client

        self.addCleanup(setattr, daemon_core.app_server, "AppServerClient", original_client)
        daemon_core.app_server.AppServerClient = fake_factory

    def _patch_daemon_communication(self, daemon_core: Any) -> None:
        original_start_mailbox = daemon_core.start_daemon_mailbox
        original_register = daemon_core.register_daemon_actor
        original_heartbeat = daemon_core.heartbeat_daemon_actor
        original_unregister = daemon_core.unregister_daemon_actor

        class FakeMailbox:
            def close(self) -> None:
                return None

        self.addCleanup(setattr, daemon_core, "start_daemon_mailbox", original_start_mailbox)
        self.addCleanup(setattr, daemon_core, "register_daemon_actor", original_register)
        self.addCleanup(setattr, daemon_core, "heartbeat_daemon_actor", original_heartbeat)
        self.addCleanup(setattr, daemon_core, "unregister_daemon_actor", original_unregister)
        daemon_core.start_daemon_mailbox = lambda **_kwargs: FakeMailbox()
        daemon_core.register_daemon_actor = lambda _context, identity_route: {
            "record": {"identity_id": identity_route["identity_id"], "role_id": identity_route["role_id"]}
        }
        daemon_core.heartbeat_daemon_actor = lambda _context, identity_route: {
            "record": {"identity_id": identity_route["identity_id"], "role_id": identity_route["role_id"]}
        }
        daemon_core.unregister_daemon_actor = lambda _context, identity_route: {
            "record": {"identity_id": identity_route["identity_id"], "role_id": identity_route["role_id"]}
        }

    def test_daemon_core_imports_without_task_domain_modules(self) -> None:
        module = _load_module(DAEMON_CORE_PATH, block_task_imports=True)
        self.assertIsNotNone(module)

    def test_daemon_side_handlers_do_not_import_taskbox_domain_modules(self) -> None:
        daemon_core_imports = _imported_modules(DAEMON_CORE_PATH)
        instance_daemon_imports = _imported_modules(INSTANCE_DAEMON_PATH)

        self.assertFalse(
            TASK_DOMAIN_IMPORTS.intersection(daemon_core_imports),
            "daemon_core.py must not import task domain modules",
        )
        self.assertFalse(
            TASK_DOMAIN_IMPORTS.intersection(instance_daemon_imports),
            "instance_daemon.py must not import task domain modules directly",
        )
        for path in (DAEMON_CORE_PATH, INSTANCE_DAEMON_PATH):
            source = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertNotIn("task_tui", source)
                self.assertNotIn("task_management", source)
                self.assertNotIn("stop_tui", source)

    def test_daemon_core_does_not_import_message_handler_or_message_domain(self) -> None:
        daemon_core_imports = _imported_modules(DAEMON_CORE_PATH)
        self.assertNotIn("message" + "_available" + "_handler", daemon_core_imports)
        self.assertNotIn("env.domain.message", daemon_core_imports)
        self.assertNotIn("env.domain.messages", daemon_core_imports)

    def test_notification_center_does_not_import_message_handler_domain_or_repo(self) -> None:
        imports = _imported_modules(NOTIFICATION_CENTER_PATH)
        source = NOTIFICATION_CENTER_PATH.read_text(encoding="utf-8")

        self.assertNotIn("message" + "_available" + "_handler", imports)
        self.assertNotIn("env.domain.messages", imports)
        self.assertNotIn("env.repos.messages", imports)
        self.assertNotIn("MessageAvailableHandler", source)
        self.assertNotIn("message_id", source)
        self.assertNotIn("needs_parent", source)

    def test_daemon_core_registers_notify_subscriptions_in_mailbox_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            daemon_core = _load_module(DAEMON_CORE_PATH)
            instance = self._instance(temp_root)
            context = daemon_core.load_daemon_context(instance["instance_json"])
            identity_route = daemon_core.identity_route_for_context(context)
            recorded: dict[str, object] = {}
            original_register_actor = daemon_core.daemon_client.register_actor

            def fake_register_actor(
                *,
                identity_id: str,
                role_id: str,
                endpoint: dict[str, object],
                heartbeat: dict[str, object],
                socket_path: Path,
            ) -> dict[str, object]:
                recorded["identity_id"] = identity_id
                recorded["role_id"] = role_id
                recorded["endpoint"] = endpoint
                recorded["heartbeat"] = heartbeat
                recorded["socket_path"] = socket_path
                return {"record": {"identity_id": identity_id, "role_id": role_id, "endpoint": endpoint}}

            self.addCleanup(setattr, daemon_core.daemon_client, "register_actor", original_register_actor)
            daemon_core.daemon_client.register_actor = fake_register_actor

            result = daemon_core.register_daemon_actor(
                context,
                identity_route,
                notify_subscriptions=["example.ready", "example.ready", " "],
            )

            endpoint = recorded["endpoint"]
            assert isinstance(endpoint, dict)
            self.assertEqual(endpoint["kind"], "daemon_mailbox_socket")
            self.assertEqual(endpoint["subscriptions"], ["example.ready"])
            self.assertEqual(result["record"]["endpoint"]["subscriptions"], ["example.ready"])

    def test_daemon_status_reports_notify_subscriptions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            daemon_core = _load_module(DAEMON_CORE_PATH)
            instance = self._instance(temp_root)

            status = daemon_core.daemon_status(
                instance["instance_json"],
                handlers=[],
                notify_subscriptions=["example.ready", "example.ready"],
            )

            self.assertEqual(status["notify"], {"subscriptions": ["example.ready"]})

    def test_central_daemon_remains_reachability_only_without_thread_activity_imports(self) -> None:
        imports = _imported_modules(CENTRAL_DAEMON_CORE_PATH)
        source = CENTRAL_DAEMON_CORE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("app_server", imports)
        self.assertNotIn("daemon_core", imports)
        self.assertNotIn("message" + "_available" + "_handler", imports)
        self.assertNotIn("thread_read", source)
        self.assertNotIn("active_turn_id", source)
        self.assertNotIn("parent_activity", source)

    def test_im_wake_handler_does_not_directly_interrupt_or_mutate_side_registry(self) -> None:
        source = IM_WAKE_HANDLER_PATH.read_text(encoding="utf-8")
        self.assertIn("im.message.created", source)
        self.assertIn("message_id", source)
        self.assertNotIn("interrupt_turn", source)
        self.assertNotIn("launcher_submit_turn", source)
        self.assertNotIn("side_thread_registry", source)
        self.assertNotIn("submit_turn(", source)

    def test_mailbox_local_trigger_support_is_generic_without_business_hardcoding(self) -> None:
        source = DAEMON_MAILBOX_PATH.read_text(encoding="utf-8")
        self.assertIn("mailbox.local_trigger", source)
        self.assertNotIn("message." + "parent_required", source)
        self.assertNotIn("require_" + "side_thread", source)
        self.assertNotIn("mailbox.parent_required", source)
        self.assertNotIn("workflow", source.lower())
        self.assertNotIn("plugin", source.lower())
        self.assertNotIn("event_bus", source.lower())

    def test_daemon_core_has_no_old_action_gateway_or_action_record_vocabulary(self) -> None:
        source = DAEMON_CORE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("Action" + "Gateway", source)
        self.assertNotIn("record_daemon_" + "action", source)
        self.assertNotIn("daemon_" + "actions", source)
        self.assertNotIn("daemon_" + "action_ids", source)
        self.assertNotIn("last_" + "action" + "_turn_id", source)
        self.assertNotIn("_" + "action_status_payload", source)

    def test_daemon_core_can_dispatch_to_noop_handler(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            daemon_core = _load_module(DAEMON_CORE_PATH)
            instance = self._instance(temp_root)
            notification = self._completed()
            fake_client = FakeRunDaemonClient(
                notifications=[
                    notification,
                    StopDaemonLoop("stop"),
                ]
            )
            self._patch_app_server_client(daemon_core, fake_client)
            self._patch_daemon_communication(daemon_core)
            handled: list[object] = []

            class NoopHandler:
                name = "noop"

                def handles(self, trigger: object) -> bool:
                    return getattr(trigger, "type", None) == "app_server.turn_completed"

                def handle(
                    self,
                    context: object,
                    state: object,
                    runtime: object,
                    trigger: object,
                ) -> object:
                    del context, state, runtime
                    handled.append(trigger)
                    import daemon_contracts

                    return daemon_contracts.HandlerResult.ignored()

            with self.assertRaises(StopDaemonLoop):
                daemon_core.run_daemon(instance["instance_json"], handlers=[NoopHandler()])

            self.assertEqual([trigger.type for trigger in handled], ["app_server.turn_completed"])
            self.assertEqual([trigger.origin_id for trigger in handled], ["turn-user-1"])
            self.assertEqual([request["method"] for request in fake_client.requests], ["thread/resume"])

    def test_no_task_handler_means_no_checkout_turn_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            daemon_core = _load_module(DAEMON_CORE_PATH)
            instance = self._instance(temp_root)
            fake_client = FakeRunDaemonClient(
                notifications=[
                    self._completed(),
                    StopDaemonLoop("stop"),
                ]
            )
            self._patch_app_server_client(daemon_core, fake_client)
            self._patch_daemon_communication(daemon_core)

            with self.assertRaises(StopDaemonLoop):
                daemon_core.run_daemon(instance["instance_json"], handlers=[])

            self.assertEqual([request["method"] for request in fake_client.requests], ["thread/resume"])
