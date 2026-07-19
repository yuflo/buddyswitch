"""Canonical Demand capture, revision, and two-pass check tests."""

from __future__ import annotations

from typing import Any

from env.domain import demand_sys
from env.repos import demands
from tests.support.runtime import RuntimeWorkspaceTestCase


class DemandCaptureAndCheckTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.actor_target = {
            "actor_id": self._runtime_actor_id(role="pm", label="demand-owner"),
            "role_id": "pm",
        }
        self.other_target = {
            "actor_id": self._runtime_actor_id(role="dev", label="other-demand-owner"),
            "role_id": "dev",
        }

    def _source_refs(self, key: str) -> list[dict[str, Any]]:
        return [{"type": "actor.self_requested", "ref": {"key": key}}]

    def _create(
        self,
        *,
        actor_target: dict[str, str] | None = None,
        intake_key: str = "actor-self:csv-export-base",
        description: str = "Support user data CSV export.",
        detail: str = "Users can export their data as CSV.",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        target = actor_target or self.actor_target
        receipt = demand_sys.create(
            target,
            intake_key,
            description,
            detail,
            self._source_refs(intake_key),
        )
        demand_id = receipt["changes"][0]["demand_id"]
        return receipt, demand_sys.get(target, demand_id)

    def _aggregate_bytes(self, actor_target: dict[str, str] | None = None) -> bytes:
        return demands.actor_state_path(actor_target or self.actor_target).read_bytes()

    def test_create_starts_one_live_unchecked_revision_one_demand(self) -> None:
        receipt, record = self._create()

        self.assertEqual(
            receipt,
            {
                "state_changed": True,
                "changes": [
                    {
                        "demand_id": record["id"],
                        "revision": 1,
                        "kind": "created",
                    }
                ],
                "check_required": True,
                "demand_id": record["id"],
                "revision": 1,
            },
        )
        self.assertEqual(
            record,
            {
                "id": record["id"],
                "actor_target": self.actor_target,
                "intake_key": "actor-self:csv-export-base",
                "description": "Support user data CSV export.",
                "detail": "Users can export their data as CSV.",
                "source_refs": self._source_refs("actor-self:csv-export-base"),
                "parent_id": None,
                "depends_on": [],
                "revision": 1,
                "checked_revision": 0,
                "terminal": None,
                "created_at": record["created_at"],
                "updated_at": record["updated_at"],
            },
        )
        self.assertTrue(record["id"].startswith("demand-"))
        self.assertEqual(record["created_at"], record["updated_at"])

    def test_same_intake_key_and_canonical_input_is_idempotent(self) -> None:
        _, record = self._create()
        before = self._aggregate_bytes()

        replay = demand_sys.create(
            self.actor_target,
            "  actor-self:csv-export-base  ",
            "  Support user data CSV export.  ",
            "  Users can export their data as CSV.  ",
            self._source_refs("actor-self:csv-export-base"),
        )

        self.assertEqual(
            replay,
            {
                "state_changed": False,
                "changes": [],
                "check_required": False,
                "demand_id": record["id"],
                "revision": 1,
            },
        )
        self.assertEqual(self._aggregate_bytes(), before)
        self.assertEqual(demand_sys.get(self.actor_target, record["id"]), record)

    def test_same_intake_key_with_different_input_conflicts_without_write(self) -> None:
        self._create()
        before = self._aggregate_bytes()

        with self.assertRaises(demand_sys.DemandIntakeConflict) as raised:
            demand_sys.create(
                self.actor_target,
                "actor-self:csv-export-base",
                "Support JSON export instead.",
                "This is not the same canonical demand.",
                self._source_refs("actor-self:csv-export-base"),
            )

        self.assertEqual(raised.exception.code, "E_DEMAND_INTAKE_CONFLICT")
        self.assertEqual(self._aggregate_bytes(), before)

    def test_revise_changes_description_and_detail_at_one_new_revision(self) -> None:
        _, original = self._create()

        receipt = demand_sys.revise(
            self.actor_target,
            original["id"],
            1,
            "Support CSV export with timezone.",
            "Every exported row includes the user timezone.",
        )
        revised = demand_sys.get(self.actor_target, original["id"])

        self.assertEqual(
            receipt,
            {
                "state_changed": True,
                "changes": [
                    {
                        "demand_id": original["id"],
                        "revision": 2,
                        "kind": "revised",
                    }
                ],
                "check_required": True,
            },
        )
        self.assertEqual(revised["description"], "Support CSV export with timezone.")
        self.assertEqual(
            revised["detail"],
            "Every exported row includes the user timezone.",
        )
        self.assertEqual(revised["source_refs"], original["source_refs"])
        self.assertEqual(revised["revision"], 2)
        self.assertEqual(revised["checked_revision"], 0)

    def test_stale_revise_conflicts_without_any_state_change(self) -> None:
        _, record = self._create()
        demand_sys.revise(
            self.actor_target,
            record["id"],
            1,
            "Support CSV export with timezone.",
            "Every exported row includes the user timezone.",
        )
        before = self._aggregate_bytes()

        with self.assertRaises(demand_sys.DemandRevisionConflict) as raised:
            demand_sys.revise(
                self.actor_target,
                record["id"],
                1,
                "Stale edit.",
                "This must not persist.",
            )

        self.assertEqual(raised.exception.code, "E_DEMAND_REVISION_CONFLICT")
        self.assertEqual(self._aggregate_bytes(), before)

    def test_check_returns_full_pending_rows_and_all_live_descriptions(self) -> None:
        _, demand_c = self._create()
        _, demand_d = self._create(
            intake_key="actor-self:csv-export-timezone",
            description="CSV export must include the user timezone.",
            detail="Add the user timezone to every exported row.",
        )

        result = demand_sys.check(self.actor_target)
        expected_pending = sorted(
            [demand_c, demand_d],
            key=lambda row: (row["created_at"], row["id"]),
        )

        self.assertEqual(result["attention_items"], expected_pending)
        self.assertEqual(
            result["live_index"],
            [
                {"id": row["id"], "description": row["description"]}
                for row in expected_pending
            ],
        )
        self.assertEqual(result["pending_count"], 2)

    def test_get_many_preserves_requested_order_and_rejects_duplicates(self) -> None:
        _, demand_c = self._create()
        _, demand_d = self._create(
            intake_key="actor-self:csv-export-timezone",
            description="CSV export must include the user timezone.",
            detail="Add the user timezone to every exported row.",
        )

        self.assertEqual(
            demand_sys.get_many(self.actor_target, [demand_d["id"], demand_c["id"]]),
            [demand_d, demand_c],
        )
        with self.assertRaises(demand_sys.DemandPayloadError) as raised:
            demand_sys.get_many(self.actor_target, [demand_c["id"], demand_c["id"]])
        self.assertEqual(raised.exception.code, "E_DEMAND_PAYLOAD")

    def test_complete_check_current_revision_catches_up_without_new_revision(self) -> None:
        _, record = self._create()
        original_updated_at = record["updated_at"]

        result = demand_sys.complete_check(
            self.actor_target,
            [{"demand_id": record["id"], "revision": 1}],
        )
        acknowledged = demand_sys.get(self.actor_target, record["id"])

        self.assertEqual(
            result,
            {
                "acknowledged": [{"demand_id": record["id"], "revision": 1}],
                "still_pending": [],
                "state_changed": True,
                "check_required": False,
            },
        )
        self.assertEqual(acknowledged["revision"], 1)
        self.assertEqual(acknowledged["checked_revision"], 1)
        self.assertEqual(acknowledged["updated_at"], original_updated_at)

    def test_complete_check_old_revision_leaves_newer_revision_pending(self) -> None:
        _, record = self._create()
        demand_sys.revise(
            self.actor_target,
            record["id"],
            1,
            "Support CSV export with timezone.",
            "Every exported row includes the user timezone.",
        )

        result = demand_sys.complete_check(
            self.actor_target,
            [{"demand_id": record["id"], "revision": 1}],
        )
        current = demand_sys.get(self.actor_target, record["id"])

        self.assertEqual(current["revision"], 2)
        self.assertEqual(current["checked_revision"], 1)
        self.assertEqual(
            result,
            {
                "acknowledged": [{"demand_id": record["id"], "revision": 1}],
                "still_pending": [{"demand_id": record["id"], "revision": 2}],
                "state_changed": True,
                "check_required": False,
            },
        )

    def test_terminal_pending_row_is_attention_but_not_live_index(self) -> None:
        _, record = self._create()

        def terminalize(state: dict[str, Any]) -> tuple[bool, None]:
            stored = state["demands"][record["id"]]
            stored["revision"] = 2
            stored["terminal"] = {
                "type": "canceled",
                "at": stored["updated_at"],
                "summary": "No longer needed.",
            }
            return True, None

        demands.transact_actor_state(self.actor_target, terminalize)

        result = demand_sys.check(self.actor_target)

        self.assertEqual(result["pending_count"], 1)
        self.assertEqual(result["attention_items"][0]["id"], record["id"])
        self.assertEqual(result["attention_items"][0]["terminal"]["type"], "canceled")
        self.assertEqual(result["live_index"], [])

    def test_cross_actor_reads_and_checks_never_expose_another_aggregate(self) -> None:
        _, own = self._create()
        _, other = self._create(
            actor_target=self.other_target,
            intake_key="actor-self:other-demand",
            description="Other actor demand.",
            detail="This must remain isolated.",
        )

        with self.assertRaises(demand_sys.DemandNotFound):
            demand_sys.get(self.actor_target, other["id"])
        self.assertEqual(demand_sys.list_demands(self.actor_target), [own])
        self.assertEqual(
            [row["id"] for row in demand_sys.check(self.actor_target)["attention_items"]],
            [own["id"]],
        )

    def test_payload_validation_rejects_noncanonical_source_refs_and_observations(self) -> None:
        with self.assertRaises(demand_sys.DemandPayloadError):
            demand_sys.create(
                self.actor_target,
                "actor-self:bad-source-ref",
                "Bad source ref.",
                "Unknown source ref fields are forbidden.",
                [{"type": "actor.self_requested", "ref": {}, "extra": True}],
            )

        _, record = self._create()
        before = self._aggregate_bytes()
        with self.assertRaises(demand_sys.DemandPayloadError):
            demand_sys.complete_check(
                self.actor_target,
                [
                    {"demand_id": record["id"], "revision": 1},
                    {"demand_id": record["id"], "revision": 1},
                ],
            )
        self.assertEqual(self._aggregate_bytes(), before)


if __name__ == "__main__":
    import unittest

    unittest.main()
