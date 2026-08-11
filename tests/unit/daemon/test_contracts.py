"""Behavior and source-boundary tests for stable daemon contracts."""

from __future__ import annotations

import ast
import importlib
import tempfile
import unittest
from pathlib import Path
from typing import Any


from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
DAEMON_CONTRACTS_PATH = ROOT / "src" / "buddyswitch" / "foundation" / "daemon" / "contracts.py"
DAEMON_CORE_PATH = ROOT / "src" / "buddyswitch" / "foundation" / "daemon" / "instance.py"
HANDLER_PATHS = (
    ROOT / "src/buddyswitch/modules/communication/private/adapters/daemon/im_wake_handler.py",
    ROOT / "src" / "buddyswitch" / "modules" / "track" / "private" / "adapters" / "daemon" / "track_comment_added_handler.py",
    ROOT / "src" / "buddyswitch" / "foundation" / "browser_runtime" / "page_handlers.py",
    ROOT / "src" / "buddyswitch" / "foundation" / "browser_runtime" / "release_handler.py",
)


def _load_contracts() -> Any:
    if not DAEMON_CONTRACTS_PATH.exists():
        raise AssertionError(f"expected module to exist: {DAEMON_CONTRACTS_PATH}")
    return importlib.import_module("buddyswitch.foundation.daemon.contracts")


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


class DaemonContractsTests(unittest.TestCase):
    def test_contract_module_exists(self) -> None:
        self.assertTrue(DAEMON_CONTRACTS_PATH.exists(), DAEMON_CONTRACTS_PATH)

    def test_handler_result_preserves_observable_shape(self) -> None:
        contracts = _load_contracts()

        self.assertEqual(contracts.HandlerResult.ignored().__dict__, {"status": "ignored", "message": None})
        self.assertEqual(contracts.HandlerResult.handled().__dict__, {"status": "handled", "message": None})
        self.assertEqual(
            contracts.HandlerResult.failed("boom").__dict__,
            {"status": "failed", "message": "boom"},
        )
        self.assertEqual(
            contracts.HandlerResult.failed("").__dict__,
            {"status": "failed", "message": "handler failed"},
        )
        with self.assertRaisesRegex(ValueError, "invalid handler result status"):
            contracts.HandlerResult("unknown")

    def test_daemon_context_preserves_stable_host_facts(self) -> None:
        contracts = _load_contracts()
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            instance_json = root / "instance.json"
            context = contracts.DaemonContext(
                instance_json=instance_json,
                instance_payload={"actor_id": "act-dev-contract"},
                actor_id="act-dev-contract",
                instance_root=root,
                main_thread_id="thr-contract-main",
                role="dev",
                workspace_dir=root / "workspace",
                project_workspace_dir=root / "project",
                socket_path=root / "runtime" / "app-server.sock",
            )

            self.assertEqual(
                context.__dict__,
                {
                    "instance_json": instance_json,
                    "instance_payload": {"actor_id": "act-dev-contract"},
                    "actor_id": "act-dev-contract",
                    "instance_root": root,
                    "main_thread_id": "thr-contract-main",
                    "role": "dev",
                    "workspace_dir": root / "workspace",
                    "project_workspace_dir": root / "project",
                    "socket_path": root / "runtime" / "app-server.sock",
                    "permissions": "buddyswitch-runtime",
                },
            )

    def test_handler_protocol_exposes_current_dispatch_methods(self) -> None:
        contracts = _load_contracts()

        self.assertEqual(contracts.DaemonHandler.__annotations__, {"name": str})
        self.assertTrue(callable(getattr(contracts.DaemonHandler, "handles", None)))
        self.assertTrue(callable(getattr(contracts.DaemonHandler, "handle", None)))

    def test_contract_module_does_not_import_core_or_product_modules(self) -> None:
        self.assertTrue(DAEMON_CONTRACTS_PATH.exists(), DAEMON_CONTRACTS_PATH)
        imports = _imported_modules(DAEMON_CONTRACTS_PATH)
        forbidden_tokens = (
            "buddyswitch.foundation.daemon.instance",
            "task_sys",
            "im_",
            "track_",
            "browser_",
            "web_management",
            "buddyswitch.env.repos",
        )

        self.assertFalse(
            [name for name in imports if any(token in name for token in forbidden_tokens)],
            imports,
        )

    def test_core_no_longer_defines_or_reexports_stable_contracts(self) -> None:
        source = DAEMON_CORE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(DAEMON_CORE_PATH))
        class_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
        assignments = {
            target.id
            for node in ast.walk(tree)
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            for target in (
                node.targets if isinstance(node, ast.Assign) else [node.target]
            )
            if isinstance(target, ast.Name)
        }

        self.assertFalse({"HandlerResult", "DaemonContext", "DaemonHandler"}.intersection(class_names))
        self.assertFalse({"HandlerResult", "DaemonContext", "DaemonHandler"}.intersection(assignments))

    def test_product_handlers_import_stable_contract_module_only(self) -> None:
        for path in HANDLER_PATHS:
            imports = _imported_modules(path)
            with self.subTest(path=path.name):
                self.assertIn("buddyswitch.foundation.daemon.contracts", imports)
                self.assertNotIn("buddyswitch.foundation.daemon.instance", imports)
