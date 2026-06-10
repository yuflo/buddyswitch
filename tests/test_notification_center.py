#!/usr/bin/env python3
"""Tests for Notification Center source-native inbound registration."""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
import unittest
from itertools import count
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NC_PATH = ROOT / "tools" / "launcher" / "notification_center.py"
MESSAGE_INBOUND_PATH = ROOT / "tools" / "launcher" / "message_inbound.py"
DAEMON_CORE_PATH = ROOT / "tools" / "launcher" / "daemon_core.py"
MODULE_COUNTER = count()


def load_module(path: Path) -> Any:
    if not path.exists():
        raise AssertionError(f"expected module to exist: {path}")
    module_name = f"buddyswitch_{path.stem}_{next(MODULE_COUNTER)}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def imported_modules(path: Path) -> set[str]:
    if not path.exists():
        raise AssertionError(f"expected source file to exist: {path}")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if module_name:
                imports.add(module_name)
            for alias in node.names:
                imports.add(f"{module_name}.{alias.name}" if module_name else alias.name)
    return imports


class ExampleHandler:
    name = "example_handler"

    def handles(self, trigger: object) -> bool:
        return getattr(trigger, "type", None) == "example.ready"

    def handle(self, *_args: object) -> object:
        return {"status": "handled"}


class NotificationCenterTests(unittest.TestCase):
    def test_valid_registration_builds_handlers_subscriptions_and_records(self) -> None:
        nc = load_module(NC_PATH)
        factory_calls: list[str] = []

        def handler_factory() -> ExampleHandler:
            factory_calls.append("called")
            return ExampleHandler()

        registration = nc.InboundSourceRegistration(
            event_type="example.ready",
            payload_contract={"required_fields": ("example_id",)},
            handler_factory=handler_factory,
            owner_module="example.inbound",
        )

        handlers = nc.handlers_from_registrations([registration])
        records = nc.registration_records([registration])

        self.assertEqual(factory_calls, ["called"])
        self.assertEqual(len(handlers), 1)
        self.assertIsInstance(handlers[0], ExampleHandler)
        self.assertEqual(nc.subscriptions_from_registrations([registration]), ["example.ready"])
        self.assertEqual(
            records,
            [
                {
                    "event_type": "example.ready",
                    "payload_contract": {"required_fields": ("example_id",)},
                    "owner_module": "example.inbound",
                    "handler_name": "handler_factory",
                }
            ],
        )

    def test_duplicate_event_types_are_rejected_before_handler_factories_are_called(self) -> None:
        nc = load_module(NC_PATH)
        factory_calls: list[str] = []

        def handler_factory() -> ExampleHandler:
            factory_calls.append("called")
            return ExampleHandler()

        registrations = [
            nc.InboundSourceRegistration(
                event_type="example.ready",
                payload_contract={"required_fields": ("example_id",)},
                handler_factory=handler_factory,
                owner_module="example.inbound",
            ),
            nc.InboundSourceRegistration(
                event_type="example.ready",
                payload_contract={"required_fields": ("other_id",)},
                handler_factory=handler_factory,
                owner_module="other.inbound",
            ),
        ]

        with self.assertRaisesRegex(ValueError, "duplicate event_type"):
            nc.handlers_from_registrations(registrations)
        self.assertEqual(factory_calls, [])

    def test_invalid_registration_fields_are_rejected(self) -> None:
        nc = load_module(NC_PATH)

        cases = [
            (
                nc.InboundSourceRegistration(
                    event_type=" ",
                    payload_contract={"required_fields": ("example_id",)},
                    handler_factory=ExampleHandler,
                    owner_module="example.inbound",
                ),
                "event_type",
            ),
            (
                nc.InboundSourceRegistration(
                    event_type="example.ready",
                    payload_contract=["example_id"],
                    handler_factory=ExampleHandler,
                    owner_module="example.inbound",
                ),
                "payload_contract",
            ),
            (
                nc.InboundSourceRegistration(
                    event_type="example.ready",
                    payload_contract={"required_fields": ("example_id",)},
                    handler_factory=object(),
                    owner_module="example.inbound",
                ),
                "handler_factory",
            ),
            (
                nc.InboundSourceRegistration(
                    event_type="example.ready",
                    payload_contract={"required_fields": ("example_id",)},
                    handler_factory=ExampleHandler,
                    owner_module=" ",
                ),
                "owner_module",
            ),
        ]

        for registration, expected_message in cases:
            with self.subTest(expected_message=expected_message):
                with self.assertRaisesRegex(ValueError, expected_message):
                    nc.normalized_registrations([registration])

    def test_handler_factory_must_return_unified_daemon_handler(self) -> None:
        nc = load_module(NC_PATH)
        registration = nc.InboundSourceRegistration(
            event_type="example.ready",
            payload_contract={"required_fields": ("example_id",)},
            handler_factory=lambda: object(),
            owner_module="example.inbound",
        )

        with self.assertRaisesRegex(ValueError, "handler"):
            nc.handlers_from_registrations([registration])

    def test_notification_center_has_no_source_specific_message_semantics(self) -> None:
        source = NC_PATH.read_text(encoding="utf-8")
        forbidden_tokens = [
            "MessageAvailableHandler",
            "message_id",
            "message body",
            "conversation",
            "disposition",
            "needs_parent",
            "message.mark",
            "message.get",
            "message.send",
            "notification.mark",
            "notification.archive",
            "nc.notification",
            "env.repos.messages",
        ]

        for token in forbidden_tokens:
            with self.subTest(token=token):
                self.assertNotIn(token, source)

        imports = imported_modules(NC_PATH)
        self.assertNotIn("message_available_handler", imports)
        self.assertNotIn("env.domain.messages", imports)
        self.assertNotIn("env.repos.messages", imports)

    def test_message_inbound_registers_message_available_as_source_owned_handler(self) -> None:
        nc = load_module(NC_PATH)
        message_inbound = load_module(MESSAGE_INBOUND_PATH)
        daemon_core = load_module(DAEMON_CORE_PATH)

        registrations = message_inbound.inbound_registrations()

        self.assertEqual(len(registrations), 1)
        registration = registrations[0]
        self.assertEqual(registration.event_type, "message.available")
        self.assertTrue(registration.owner_module.endswith("message_inbound"))
        self.assertEqual(dict(registration.payload_contract), {"required_fields": ("message_id",)})
        contract_text = json.dumps(dict(registration.payload_contract), ensure_ascii=True, default=list)
        self.assertNotIn("body", contract_text.lower())
        self.assertNotIn("conversation", contract_text.lower())
        self.assertNotIn("disposition", contract_text.lower())
        self.assertNotIn("needs_parent", contract_text)

        handler = registration.handler_factory()
        self.assertEqual(type(handler).__name__, "MessageAvailableHandler")
        self.assertEqual(getattr(handler, "name", None), "message_available")

        handlers = nc.handlers_from_registrations(registrations)
        trigger = daemon_core.daemon_triggers.DaemonTrigger(
            source="mailbox_cross_actor_signal",
            type="message.available",
            target_actor_address={"role_id": "dev", "actor_id": "act-dev-nc"},
            origin_id="sig-nc",
            correlation_id=None,
            payload={"message_id": "msg-nc"},
            source_context={
                "signal_id": "sig-nc",
                "source_actor_address": {"role_id": "pm", "actor_id": "act-pm-nc"},
                "created_at": "2026-06-09T00:00:00Z",
            },
        )

        self.assertEqual([type(item).__name__ for item in handlers], ["MessageAvailableHandler"])
        self.assertTrue(handlers[0].handles(trigger))


if __name__ == "__main__":
    unittest.main()
