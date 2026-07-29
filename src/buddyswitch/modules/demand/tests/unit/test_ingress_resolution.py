"""Private source-keyed Demand ingress resolution contracts."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from buddyswitch.modules.demand.private.domain import demand_sys
from buddyswitch.modules.demand.private.state import demands
from tests.support.runtime import RuntimeWorkspaceTestCase


class DemandIngressResolutionTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.actor_target = {
            "actor_id": self._runtime_actor_id(role="pm", label="demand-ingress"),
            "role_id": "pm",
        }

    def _refs(self, label: str = "one") -> list[dict[str, Any]]:
        return [{
            "type": "im.message.created",
            "ref": {
                "message_id": f"msg-{label}",
                "conversation_id": "conv-demand-ingress",
                "event_id": f"imev-{label}",
            },
        }]

    def _claim(self, label: str = "one") -> dict[str, Any]:
        return demand_sys.claim_ingress(
            self.actor_target,
            f"im.message.created:msg-{label}",
            f"Demand {label}.",
            f"Detailed inbound need for {label}.",
            self._refs(label),
        )

    def _begin(self, label: str = "one") -> str:
        self._claim(label)
        return str(
            demand_sys.begin_ingress_resolution(
                self.actor_target,
                f"im.message.created:msg-{label}",
            )["attempt_id"]
        )

    def _proposal(
        self,
        decision: str,
        *,
        reason: str,
        demand_ref: str | None = None,
        description: str | None = None,
        detail: str | None = None,
        reply_content: str | None = None,
    ) -> dict[str, Any]:
        return {
            "decision": decision,
            "reason": reason,
            "demand_ref": demand_ref,
            "description": description,
            "detail": detail,
            "reply_content": reply_content,
        }

    def _create_ingress_demand(self, label: str) -> dict[str, Any]:
        attempt_id = self._begin(label)
        created = demand_sys.resolve_ingress(
            self.actor_target,
            f"im.message.created:msg-{label}",
            attempt_id,
            self._proposal(
                "create",
                reason="This inbound creates one independent unmet need.",
                description=f"Demand {label}.",
                detail=f"Detailed requirement for {label}.",
            ),
            handled_verified=False,
        )
        return demand_sys.get(self.actor_target, created["demand_id"])

    def test_fresh_aggregate_has_private_receipts_and_pool_revision_only(self) -> None:
        state = demands.load_actor_state(self.actor_target)

        self.assertEqual(
            state,
            {
                "schema_version": 5,
                "actor_target": self.actor_target,
                "demands": {},
                "demand_pool_revision": 0,
                "ingress_receipts": {},
            },
        )
        self.assertNotIn("intakes", state)

    def test_claim_ingress_is_source_key_idempotent_without_creating_demand(self) -> None:
        first = self._claim()
        replay = self._claim()

        self.assertEqual(
            first,
            {
                "state_changed": True,
                "source_key": "im.message.created:msg-one",
                "state": "pending",
            },
        )
        self.assertEqual(
            replay,
            {
                "state_changed": False,
                "source_key": "im.message.created:msg-one",
                "state": "pending",
            },
        )
        receipt = demand_sys.get_ingress_receipt(
            self.actor_target,
            "im.message.created:msg-one",
        )
        self.assertEqual(receipt["state"], "pending")
        self.assertIsNone(receipt["attempt_id"])
        self.assertIsNone(receipt["outcome"])
        self.assertIsNone(receipt["last_failure"])
        self.assertEqual(
            receipt["fact"],
            {
                "description": "Demand one.",
                "detail": "Detailed inbound need for one.",
                "source_refs": self._refs(),
            },
        )
        self.assertEqual(len(receipt["fingerprint"]), 64)
        state = demands.load_actor_state(self.actor_target)
        self.assertEqual(state["demands"], {})
        self.assertEqual(state["demand_pool_revision"], 0)

    def test_same_source_key_with_different_fact_conflicts_without_write(self) -> None:
        self._claim()
        state_path = demands.actor_state_path(self.actor_target)
        before = state_path.read_bytes()

        with self.assertRaises(demand_sys.DemandIngressConflict) as raised:
            demand_sys.claim_ingress(
                self.actor_target,
                "im.message.created:msg-one",
                "Different meaning.",
                "This replay is not the same source fact.",
                self._refs(),
            )

        self.assertEqual(raised.exception.code, "E_DEMAND_INGRESS_CONFLICT")
        self.assertEqual(state_path.read_bytes(), before)

    def test_begin_resolution_claims_exactly_one_current_attempt(self) -> None:
        self._claim()

        first = demand_sys.begin_ingress_resolution(
            self.actor_target,
            "im.message.created:msg-one",
        )
        replay = demand_sys.begin_ingress_resolution(
            self.actor_target,
            "im.message.created:msg-one",
        )

        self.assertTrue(first["state_changed"])
        self.assertTrue(first["attempt_id"].startswith("attempt-"))
        self.assertEqual(
            replay,
            {
                "state_changed": False,
                "source_key": "im.message.created:msg-one",
                "attempt_id": first["attempt_id"],
            },
        )
        receipt = demand_sys.get_ingress_receipt(
            self.actor_target,
            "im.message.created:msg-one",
        )
        self.assertEqual(receipt["state"], "resolving")
        self.assertEqual(receipt["attempt_id"], first["attempt_id"])
        self.assertEqual(
            demand_sys.list_unsettled_ingress(self.actor_target),
            [{
                "source_key": "im.message.created:msg-one",
                **receipt,
            }],
        )
        self.assertEqual(
            demands.load_actor_state(self.actor_target)["demand_pool_revision"],
            0,
        )

    def test_no_action_settles_receipt_without_changing_demand_pool(self) -> None:
        attempt_id = self._begin("no-action")

        result = demand_sys.resolve_ingress(
            self.actor_target,
            "im.message.created:msg-no-action",
            attempt_id,
            self._proposal(
                "no_action_needed",
                reason="This is only an acknowledgement.",
            ),
            handled_verified=False,
        )

        self.assertEqual(
            result,
            {
                "state_changed": True,
                "source_key": "im.message.created:msg-no-action",
                "decision": "no_action_needed",
                "demand_changed": False,
                "demand_pool_revision": 0,
            },
        )
        receipt = demand_sys.get_ingress_receipt(
            self.actor_target,
            "im.message.created:msg-no-action",
        )
        self.assertEqual(receipt["state"], "settled")
        self.assertEqual(receipt["attempt_id"], attempt_id)
        self.assertEqual(
            receipt["outcome"],
            {
                "decision": "no_action_needed",
                "demand_changed": False,
                "demand_pool_revision": 0,
            },
        )
        self.assertEqual(demand_sys.list_unsettled_ingress(self.actor_target), [])
        self.assertEqual(demand_sys.list_demands(self.actor_target), [])

    def test_create_settles_receipt_and_changes_pool_in_one_aggregate_write(self) -> None:
        attempt_id = self._begin("create")

        with patch.object(
            demands.runtime_files,
            "write_json_object",
            wraps=demands.runtime_files.write_json_object,
        ) as write_json_object:
            created = demand_sys.resolve_ingress(
                self.actor_target,
                "im.message.created:msg-create",
                attempt_id,
                self._proposal(
                    "create",
                    reason="This is a new independent obligation.",
                    description="Export user data as CSV.",
                    detail="Provide a downloadable CSV export.",
                ),
                handled_verified=False,
            )

        write_json_object.assert_called_once()
        self.assertTrue(created["state_changed"])
        self.assertEqual(created["decision"], "create")
        self.assertTrue(created["demand_changed"])
        self.assertEqual(created["demand_pool_revision"], 1)
        demand = demand_sys.get(self.actor_target, created["demand_id"])
        self.assertEqual(demand["description"], "Export user data as CSV.")
        self.assertEqual(demand["source_refs"], self._refs("create"))
        receipt = demand_sys.get_ingress_receipt(
            self.actor_target,
            "im.message.created:msg-create",
        )
        self.assertEqual(receipt["state"], "settled")
        self.assertEqual(receipt["outcome"]["demand_id"], demand["id"])
        self.assertEqual(
            demands.load_actor_state(self.actor_target)["demand_pool_revision"],
            1,
        )

    def test_duplicate_successful_resolve_returns_outcome_without_revision_change(self) -> None:
        attempt_id = self._begin("replay")
        proposal = self._proposal(
            "create",
            reason="Create once.",
            description="One durable Demand.",
            detail="Duplicate resolve must not create another Demand.",
        )
        first = demand_sys.resolve_ingress(
            self.actor_target,
            "im.message.created:msg-replay",
            attempt_id,
            proposal,
            handled_verified=False,
        )
        state_path = demands.actor_state_path(self.actor_target)
        before = state_path.read_bytes()

        replay = demand_sys.resolve_ingress(
            self.actor_target,
            "im.message.created:msg-replay",
            attempt_id,
            proposal,
            handled_verified=False,
        )

        self.assertFalse(replay["state_changed"])
        self.assertEqual(replay["demand_id"], first["demand_id"])
        self.assertEqual(replay["demand_pool_revision"], 1)
        self.assertEqual(state_path.read_bytes(), before)
        self.assertEqual(len(demand_sys.list_demands(self.actor_target)), 1)

    def test_handled_requires_verified_delivery_and_never_changes_pool(self) -> None:
        attempt_id = self._begin("handled")
        proposal = self._proposal(
            "handled",
            reason="The source question was answered directly.",
            reply_content="The requested value is 42.",
        )
        state_path = demands.actor_state_path(self.actor_target)
        before = state_path.read_bytes()

        with self.assertRaises(demand_sys.DemandPayloadError):
            demand_sys.resolve_ingress(
                self.actor_target,
                "im.message.created:msg-handled",
                attempt_id,
                proposal,
                handled_verified=False,
            )

        self.assertEqual(state_path.read_bytes(), before)
        handled = demand_sys.resolve_ingress(
            self.actor_target,
            "im.message.created:msg-handled",
            attempt_id,
            proposal,
            handled_verified=True,
        )
        self.assertEqual(handled["decision"], "handled")
        self.assertFalse(handled["demand_changed"])
        self.assertEqual(handled["demand_pool_revision"], 0)
        self.assertEqual(demand_sys.list_demands(self.actor_target), [])

    def test_shared_ingress_and_completion_mutations_increment_pool_revision_once(self) -> None:
        first = self._create_ingress_demand("first")
        self.assertEqual(
            demands.load_actor_state(self.actor_target)["demand_pool_revision"],
            1,
        )

        revise_attempt = self._begin("first-revise")
        revised = demand_sys.resolve_ingress(
            self.actor_target,
            "im.message.created:msg-first-revise",
            revise_attempt,
            self._proposal(
                "revise",
                reason="Scope changed.",
                demand_ref=first["demand_ref"],
                description="Demand first revised.",
                detail="The revised canonical requirement.",
            ),
            handled_verified=False,
        )
        self.assertEqual(revised["demand_pool_revision"], 2)

        completed = demand_sys.complete(
            self.actor_target,
            revised["demand_ref"],
            "The requirement is satisfied.",
            [{"type": "artifact", "ref": {"id": "art-first"}}],
        )
        self.assertEqual(completed["demand_pool_revision"], 3)

        second = self._create_ingress_demand("second")
        self.assertEqual(
            demands.load_actor_state(self.actor_target)["demand_pool_revision"],
            4,
        )
        cancel_attempt = self._begin("second-cancel")
        canceled = demand_sys.resolve_ingress(
            self.actor_target,
            "im.message.created:msg-second-cancel",
            cancel_attempt,
            self._proposal(
                "cancel",
                reason="The requester withdrew this need.",
                demand_ref=second["demand_ref"],
            ),
            handled_verified=False,
        )
        self.assertEqual(canceled["demand_pool_revision"], 5)

    def test_merge_revise_and_cancel_apply_against_current_opaque_refs(self) -> None:
        merge_target = self._create_ingress_demand("merge-target")
        merge_attempt = self._begin("merge")
        merged = demand_sys.resolve_ingress(
            self.actor_target,
            "im.message.created:msg-merge",
            merge_attempt,
            self._proposal(
                "merge_intake",
                reason="This adds detail to the same obligation.",
                demand_ref=merge_target["demand_ref"],
                description="Demand merge-target with timezone.",
                detail="Include the user's timezone in the export.",
            ),
            handled_verified=False,
        )
        current = demand_sys.get(self.actor_target, merge_target["id"])
        self.assertEqual(merged["demand_pool_revision"], 2)
        self.assertEqual(
            current["source_refs"],
            [*merge_target["source_refs"], *self._refs("merge")],
        )

        revise_attempt = self._begin("revise")
        revised = demand_sys.resolve_ingress(
            self.actor_target,
            "im.message.created:msg-revise",
            revise_attempt,
            self._proposal(
                "revise",
                reason="The source changes the requirement boundary.",
                demand_ref=current["demand_ref"],
                description="Export only active users.",
                detail="Archived users are excluded.",
            ),
            handled_verified=False,
        )
        current = demand_sys.get(self.actor_target, merge_target["id"])
        self.assertEqual(revised["demand_pool_revision"], 3)
        self.assertEqual(current["description"], "Export only active users.")

        cancel_attempt = self._begin("cancel")
        canceled = demand_sys.resolve_ingress(
            self.actor_target,
            "im.message.created:msg-cancel",
            cancel_attempt,
            self._proposal(
                "cancel",
                reason="The source explicitly withdraws the requirement.",
                demand_ref=current["demand_ref"],
            ),
            handled_verified=False,
        )
        terminal = demand_sys.get(self.actor_target, merge_target["id"])["terminal"]
        self.assertEqual(canceled["demand_pool_revision"], 4)
        self.assertEqual(terminal["type"], "canceled")
        self.assertEqual(terminal["summary"], canceled["reason"])

    def test_stale_target_ref_retries_receipt_without_partial_demand_write(self) -> None:
        target = self._create_ingress_demand("stale-target")
        attempt_id = self._begin("stale")
        concurrent_attempt = self._begin("stale-concurrent")
        demand_sys.resolve_ingress(
            self.actor_target,
            "im.message.created:msg-stale-concurrent",
            concurrent_attempt,
            self._proposal(
                "revise",
                reason="Another inbound changed this Demand.",
                demand_ref=target["demand_ref"],
                description="Concurrent current description.",
                detail="Concurrent current detail.",
            ),
            handled_verified=False,
        )
        current_before = demand_sys.get(self.actor_target, target["id"])

        result = demand_sys.resolve_ingress(
            self.actor_target,
            "im.message.created:msg-stale",
            attempt_id,
            self._proposal(
                "revise",
                reason="This proposal was based on an old ref.",
                demand_ref=target["demand_ref"],
                description="Stale overwrite.",
                detail="This must not replace current meaning.",
            ),
            handled_verified=False,
        )

        self.assertTrue(result["retry_required"])
        self.assertEqual(result["reason"], "stale_demand_ref")
        receipt = demand_sys.get_ingress_receipt(
            self.actor_target,
            "im.message.created:msg-stale",
        )
        self.assertEqual(receipt["state"], "pending")
        self.assertIsNone(receipt["attempt_id"])
        self.assertEqual(receipt["last_failure"]["code"], "stale_demand_ref")
        self.assertEqual(demand_sys.get(self.actor_target, target["id"]), current_before)

    def test_retriable_failure_returns_receipt_to_pending(self) -> None:
        attempt_id = self._begin("retry")

        result = demand_sys.fail_ingress_resolution(
            self.actor_target,
            "im.message.created:msg-retry",
            attempt_id,
            {
                "code": "model_error",
                "message": "The triage turn ended before resolver call.",
            },
            retriable=True,
        )

        self.assertEqual(
            result,
            {
                "state_changed": True,
                "source_key": "im.message.created:msg-retry",
                "state": "pending",
                "retry_required": True,
            },
        )
        receipt = demand_sys.get_ingress_receipt(
            self.actor_target,
            "im.message.created:msg-retry",
        )
        self.assertEqual(receipt["state"], "pending")
        self.assertIsNone(receipt["attempt_id"])
        self.assertEqual(receipt["last_failure"]["code"], "model_error")
        self.assertEqual(
            demands.load_actor_state(self.actor_target)["demand_pool_revision"],
            0,
        )

    def test_non_retriable_failure_is_terminal_for_receipt_not_demand(self) -> None:
        attempt_id = self._begin("failed")

        result = demand_sys.fail_ingress_resolution(
            self.actor_target,
            "im.message.created:msg-failed",
            attempt_id,
            {
                "code": "invalid_authority",
                "message": "The source does not belong to this actor.",
            },
            retriable=False,
        )

        self.assertEqual(
            result,
            {
                "state_changed": True,
                "source_key": "im.message.created:msg-failed",
                "state": "failed",
                "retry_required": False,
            },
        )
        receipt = demand_sys.get_ingress_receipt(
            self.actor_target,
            "im.message.created:msg-failed",
        )
        self.assertEqual(receipt["state"], "failed")
        self.assertIsNone(receipt["attempt_id"])
        self.assertEqual(receipt["last_failure"]["code"], "invalid_authority")
        self.assertEqual(demand_sys.list_unsettled_ingress(self.actor_target), [])
        self.assertEqual(demand_sys.list_demands(self.actor_target, state="all"), [])


if __name__ == "__main__":
    import unittest

    unittest.main()
