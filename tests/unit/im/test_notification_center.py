"""Tests for Notification Center source-native inbound registration."""

from __future__ import annotations

import ast
import importlib
import json
import sys
import unittest
from itertools import count
from pathlib import Path
from typing import Any


from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
NC_PATH = ROOT / "src" / "buddyswitch" / "launcher" / "notification_center.py"
MESSAGE_INBOUND_PATH = ROOT / "src" / "buddyswitch" / "launcher" / "message_inbound.py"
TRACK_COMMENT_INBOUND_PATH = (
    ROOT
    / "src"
    / "buddyswitch"
    / "modules"
    / "track"
    / "private"
    / "adapters"
    / "daemon"
    / "track_comment_inbound.py"
)
DAEMON_CORE_PATH = ROOT / "src" / "buddyswitch" / "launcher" / "daemon_core.py"
MODULE_COUNTER = count()


def load_module(path: Path) -> Any:
    if not path.exists():
        raise AssertionError(f"expected module to exist: {path}")
    module_name = ".".join(path.relative_to(ROOT / "src").with_suffix("").parts)
    return importlib.reload(importlib.import_module(module_name))


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
            "dispo" + "sition",
            "needs_parent",
            "message." + "mark",
            "message.get",
            "message.send",
            "TrackCommentAddedHandler",
            "track_id",
            "comment_id",
            "track.open",
            "track.list_comments",
            "notification.mark",
            "notification.archive",
            "nc.notification",
            "buddyswitch.env.repos.messages",
            "buddyswitch.modules.track.private.state.track_comments",
        ]

        for token in forbidden_tokens:
            with self.subTest(token=token):
                self.assertNotIn(token, source)

        imports = imported_modules(NC_PATH)
        self.assertNotIn("message" + "_available" + "_handler", imports)
        self.assertNotIn("track_comment_added_handler", imports)
        self.assertNotIn("buddyswitch.env.domain.messages", imports)
        self.assertNotIn("buddyswitch.env.repos.messages", imports)
        self.assertNotIn(
            "buddyswitch.modules.track.private.state.track_comments",
            imports,
        )

    def test_message_inbound_registers_im_message_created_as_source_owned_handler(self) -> None:
        nc = load_module(NC_PATH)
        message_inbound = load_module(MESSAGE_INBOUND_PATH)
        daemon_core = load_module(DAEMON_CORE_PATH)

        registrations = message_inbound.inbound_registrations()

        self.assertEqual(len(registrations), 1)
        registration = registrations[0]
        self.assertEqual(registration.event_type, "im.message.created")
        self.assertTrue(registration.owner_module.endswith("message_inbound"))
        self.assertEqual(dict(registration.payload_contract), {"required_fields": ("message_id", "conversation_id", "event_id")})
        contract_text = json.dumps(dict(registration.payload_contract), ensure_ascii=True, default=list)
        self.assertNotIn("body", contract_text.lower())
        self.assertNotIn("dispo" + "sition", contract_text.lower())
        self.assertNotIn("needs_parent", contract_text)

        handler = registration.handler_factory()
        self.assertEqual(type(handler).__name__, "ImMessageCreatedHandler")
        self.assertEqual(getattr(handler, "name", None), "im_message_created")

        handlers = nc.handlers_from_registrations(registrations)
        trigger = daemon_core.daemon_triggers.DaemonTrigger(
            source="mailbox_cross_actor_signal",
            type="im.message.created",
            target_identity_id="act-dev-nc",
            target_role_id="dev",
            origin_id="sig-nc",
            correlation_id=None,
            payload={"message_id": "msg-nc", "conversation_id": "conv-nc", "event_id": "imev-nc"},
            source_context={"signal_id": "sig-nc", "created_at": "2026-06-09T00:00:00Z"},
        )

        self.assertEqual([type(item).__name__ for item in handlers], ["ImMessageCreatedHandler"])
        self.assertTrue(handlers[0].handles(trigger))

    def test_track_comment_inbound_registers_track_comment_added_as_source_owned_handler(self) -> None:
        nc = load_module(NC_PATH)
        track_comment_inbound = load_module(TRACK_COMMENT_INBOUND_PATH)
        daemon_core = load_module(DAEMON_CORE_PATH)

        registrations = track_comment_inbound.inbound_registrations()

        self.assertEqual(len(registrations), 1)
        registration = registrations[0]
        self.assertEqual(registration.event_type, "track.comment.added")
        self.assertTrue(registration.owner_module.endswith("track_comment_inbound"))
        self.assertEqual(
            dict(registration.payload_contract),
            {"required_fields": ("track_id", "comment_id", "thread_id")},
        )
        contract_text = json.dumps(dict(registration.payload_contract), ensure_ascii=True, default=list)
        self.assertNotIn("content", contract_text.lower())
        self.assertNotIn("body", contract_text.lower())
        self.assertNotIn("notification", contract_text.lower())

        handler = registration.handler_factory()
        self.assertEqual(type(handler).__name__, "TrackCommentAddedHandler")
        self.assertEqual(getattr(handler, "name", None), "track_comment_added")

        handlers = nc.handlers_from_registrations(registrations)
        trigger = daemon_core.daemon_triggers.DaemonTrigger(
            source="mailbox_cross_actor_signal",
            type="track.comment.added",
            target_identity_id="act-dev-track-nc",
            target_role_id="dev",
            origin_id="sig-track-nc",
            correlation_id=None,
            payload={"track_id": "track-nc", "comment_id": "comment-nc", "thread_id": "comment-nc"},
            source_context={
                "signal_id": "sig-track-nc",
                "source_identity_id": "act-pm-track-nc",
                "source_role_id": "pm",
                "created_at": "2026-06-10T00:00:00Z",
            },
        )

        self.assertEqual([type(item).__name__ for item in handlers], ["TrackCommentAddedHandler"])
        self.assertTrue(handlers[0].handles(trigger))
