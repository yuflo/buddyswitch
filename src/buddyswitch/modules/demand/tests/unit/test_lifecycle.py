"""Demand completed and canceled lifecycle contracts."""

from __future__ import annotations

from typing import Any, Callable

from buddyswitch.modules.demand.private.domain import demand_sys
from buddyswitch.modules.demand.private.state import demands
from tests.support.runtime import RuntimeWorkspaceTestCase


class DemandLifecycleTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.actor_target = {
            "actor_id": self._runtime_actor_id(role="pm", label="demand-lifecycle"),
            "role_id": "pm",
        }
        self._sequence = 0

    def _create(self, label: str) -> dict[str, Any]:
        self._sequence += 1
        source_key = f"im.message.created:{label}-{self._sequence}"
        demand_sys.claim_ingress(
            self.actor_target,
            source_key,
            f"Demand {label}.",
            f"Detailed requirement for {label}.",
            [{
                "type": "im.message.created",
                "ref": {
                    "message_id": f"msg-{label}-{self._sequence}",
                    "conversation_id": "conv-demand-lifecycle",
                    "event_id": f"imev-{label}-{self._sequence}",
                },
            }],
        )
        attempt_id = demand_sys.begin_ingress_resolution(
            self.actor_target,
            source_key,
        )["attempt_id"]
        receipt = demand_sys.resolve_ingress(
            self.actor_target,
            source_key,
            attempt_id,
            {
                "decision": "create",
                "reason": "This inbound creates one independent unmet need.",
                "demand_ref": None,
                "description": f"Demand {label}.",
                "detail": f"Detailed requirement for {label}.",
                "reply_content": None,
            },
            handled_verified=False,
        )
        return demand_sys.get(self.actor_target, receipt["demand_id"])

    def _cancel(self, record: dict[str, Any], label: str) -> dict[str, Any]:
        self._sequence += 1
        source_key = f"im.message.created:{label}-{self._sequence}"
        demand_sys.claim_ingress(
            self.actor_target,
            source_key,
            "Withdraw the existing need.",
            "The requester explicitly withdrew this requirement.",
            [{
                "type": "im.message.created",
                "ref": {
                    "message_id": f"msg-{label}-{self._sequence}",
                    "conversation_id": "conv-demand-lifecycle",
                    "event_id": f"imev-{label}-{self._sequence}",
                },
            }],
        )
        attempt_id = demand_sys.begin_ingress_resolution(
            self.actor_target,
            source_key,
        )["attempt_id"]
        return demand_sys.resolve_ingress(
            self.actor_target,
            source_key,
            attempt_id,
            {
                "decision": "cancel",
                "reason": "Requirement was withdrawn.",
                "demand_ref": record["demand_ref"],
                "description": None,
                "detail": None,
                "reply_content": None,
            },
            handled_verified=False,
        )

    def _bytes(self) -> bytes:
        return demands.actor_state_path(self.actor_target).read_bytes()

    def _assert_unchanged_error(
        self,
        error_type: type[Exception],
        action: Callable[[], object],
    ) -> Exception:
        before = self._bytes()
        with self.assertRaises(error_type) as raised:
            action()
        self.assertEqual(self._bytes(), before)
        return raised.exception

    def test_complete_stores_exact_summary_and_evidence_shape(self) -> None:
        record = self._create("complete")
        evidence_refs = [
            {"type": "artifact", "ref": {"id": "art-demand-proof"}},
            {"type": "task_sys.task", "ref": {"task_id": "task-demand-proof"}},
        ]

        receipt = demand_sys.complete(
            self.actor_target,
            record["demand_ref"],
            "Acceptance evidence is complete.",
            evidence_refs,
        )
        terminal = demand_sys.get(self.actor_target, record["id"])["terminal"]

        self.assertEqual(
            receipt["changes"],
            [{"demand_id": record["id"], "kind": "completed"}],
        )
        self.assertEqual(
            terminal,
            {
                "type": "completed",
                "at": terminal["at"],
                "summary": "Acceptance evidence is complete.",
                "evidence_refs": evidence_refs,
            },
        )

    def test_complete_rejects_missing_evidence_without_write(self) -> None:
        record = self._create("complete-missing-evidence")

        raised = self._assert_unchanged_error(
            demand_sys.DemandPayloadError,
            lambda: demand_sys.complete(
                self.actor_target,
                record["demand_ref"],
                "Evidence is required before completion.",
                None,
            ),
        )

        self.assertEqual(raised.code, "E_DEMAND_PAYLOAD")
        self.assertEqual(demand_sys.get(self.actor_target, record["id"]), record)

    def test_cancel_stores_exact_summary_shape(self) -> None:
        record = self._create("cancel")

        receipt = self._cancel(record, "cancel")
        terminal = demand_sys.get(self.actor_target, record["id"])["terminal"]

        self.assertEqual(
            (receipt["decision"], receipt["demand_id"], receipt["demand_changed"]),
            ("cancel", record["id"], True),
        )
        self.assertEqual(
            terminal,
            {
                "type": "canceled",
                "at": terminal["at"],
                "summary": "Requirement was withdrawn.",
            },
        )

    def test_terminal_exact_replay_is_noop(self) -> None:
        record = self._create("replay")
        evidence_refs = [{"type": "task_sys.task", "ref": {"task_id": "task-replay"}}]
        demand_sys.complete(
            self.actor_target,
            record["demand_ref"],
            "Satisfied.",
            evidence_refs,
        )
        before = self._bytes()

        replay = demand_sys.complete(
            self.actor_target,
            record["demand_ref"],
            "Satisfied.",
            evidence_refs,
        )

        self.assertEqual(
            replay,
            {
                "state_changed": False,
                "changes": [],
                "demand_id": record["id"],
                "demand_ref": replay["demand_ref"],
                "demand_pool_revision": 2,
            },
        )
        self.assertEqual(self._bytes(), before)

    def test_different_action_against_terminal_demand_rejects_without_write(self) -> None:
        record = self._create("terminal-conflict")
        self._cancel(record, "terminal-conflict")

        raised = self._assert_unchanged_error(
            demand_sys.DemandTerminalConflict,
            lambda: demand_sys.complete(
                self.actor_target,
                record["demand_ref"],
                "Cannot complete a canceled Demand.",
                [{"type": "task_sys.task", "ref": {"task_id": "task-conflict"}}],
            ),
        )
        self.assertEqual(raised.code, "E_DEMAND_TERMINAL")

    def test_retired_duplicate_and_superseded_terminal_shapes_are_invalid(self) -> None:
        for terminal_type in ("duplicate", "superseded"):
            with self.subTest(terminal_type=terminal_type):
                record = self._create(terminal_type)

                def inject_retired_terminal(state: dict[str, Any]) -> tuple[bool, None]:
                    stored = state["demands"][record["id"]]
                    stored["revision"] = 2
                    stored["terminal"] = {
                        "type": terminal_type,
                        "at": stored["updated_at"],
                        "ref": "demand-retired-target",
                        "summary": "Retired terminal shape.",
                    }
                    return True, None

                demands.transact_actor_state(self.actor_target, inject_retired_terminal)
                before = self._bytes()

                with self.assertRaises(demand_sys.DemandPayloadError):
                    demand_sys.get(self.actor_target, record["id"])

                self.assertEqual(self._bytes(), before)
                demands.actor_state_path(self.actor_target).unlink()


if __name__ == "__main__":
    import unittest

    unittest.main()
