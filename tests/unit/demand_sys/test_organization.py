"""Demand constrained-hybrid organization and terminal lifecycle tests."""

from __future__ import annotations

from typing import Any, Callable

from env.domain import demand_sys
from env.repos import demands
from tests.support.runtime import RuntimeWorkspaceTestCase


class DemandOrganizationTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.actor_target = {
            "actor_id": self._runtime_actor_id(role="pm", label="demand-organization"),
            "role_id": "pm",
        }
        self._sequence = 0

    def _refs(self, key: str) -> list[dict[str, Any]]:
        return [{"type": "actor.self_requested", "ref": {"key": key}}]

    def _create(
        self,
        label: str,
        *,
        description: str | None = None,
        detail: str | None = None,
        source_refs: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self._sequence += 1
        intake_key = f"actor-self:{label}-{self._sequence}"
        receipt = demand_sys.create(
            self.actor_target,
            intake_key,
            description or f"Demand {label}.",
            detail or f"Detailed requirement for {label}.",
            source_refs if source_refs is not None else self._refs(intake_key),
        )
        return demand_sys.get(
            self.actor_target,
            receipt["changes"][0]["demand_id"],
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

    def test_set_parent_creates_one_live_parent_edge(self) -> None:
        parent = self._create("parent")
        child = self._create("child")

        receipt = demand_sys.set_parent(
            self.actor_target,
            child["id"],
            1,
            parent["id"],
        )

        self.assertEqual(
            receipt["changes"],
            [{"demand_id": child["id"], "revision": 2, "kind": "parent_set"}],
        )
        self.assertEqual(
            demand_sys.get(self.actor_target, child["id"])["parent_id"],
            parent["id"],
        )
        self.assertEqual(demand_sys.get(self.actor_target, parent["id"]), parent)

    def test_set_parent_rejects_self_terminal_missing_and_parent_cycle(self) -> None:
        first = self._create("first")
        second = self._create("second")
        terminal = self._create("terminal-parent")
        demand_sys.cancel(
            self.actor_target,
            terminal["id"],
            1,
            "Parent target retired.",
        )

        self._assert_unchanged_error(
            demand_sys.DemandRelationConflict,
            lambda: demand_sys.set_parent(
                self.actor_target,
                first["id"],
                1,
                first["id"],
            ),
        )
        self._assert_unchanged_error(
            demand_sys.DemandTerminalConflict,
            lambda: demand_sys.set_parent(
                self.actor_target,
                first["id"],
                1,
                terminal["id"],
            ),
        )
        self._assert_unchanged_error(
            demand_sys.DemandNotFound,
            lambda: demand_sys.set_parent(
                self.actor_target,
                first["id"],
                1,
                "demand-missing",
            ),
        )
        demand_sys.set_parent(
            self.actor_target,
            first["id"],
            1,
            second["id"],
        )
        self._assert_unchanged_error(
            demand_sys.DemandRelationConflict,
            lambda: demand_sys.set_parent(
                self.actor_target,
                second["id"],
                1,
                first["id"],
            ),
        )

    def test_set_parent_none_explicitly_detaches_without_an_alias_action(self) -> None:
        parent = self._create("parent")
        child = self._create("child")
        demand_sys.set_parent(self.actor_target, child["id"], 1, parent["id"])

        receipt = demand_sys.set_parent(self.actor_target, child["id"], 2, None)

        self.assertEqual(receipt["changes"][0]["revision"], 3)
        self.assertIsNone(demand_sys.get(self.actor_target, child["id"])["parent_id"])

    def test_add_dependency_is_idempotent_and_rejects_self_or_cycle(self) -> None:
        demand_a = self._create("a")
        demand_b = self._create("b")

        added = demand_sys.add_dependency(
            self.actor_target,
            demand_a["id"],
            1,
            demand_b["id"],
        )
        replay = demand_sys.add_dependency(
            self.actor_target,
            demand_a["id"],
            2,
            demand_b["id"],
        )

        self.assertTrue(added["state_changed"])
        self.assertEqual(
            replay,
            {"state_changed": False, "changes": [], "check_required": False},
        )
        self._assert_unchanged_error(
            demand_sys.DemandRelationConflict,
            lambda: demand_sys.add_dependency(
                self.actor_target,
                demand_b["id"],
                1,
                demand_b["id"],
            ),
        )
        self._assert_unchanged_error(
            demand_sys.DemandRelationConflict,
            lambda: demand_sys.add_dependency(
                self.actor_target,
                demand_b["id"],
                1,
                demand_a["id"],
            ),
        )

    def test_remove_dependency_changes_only_the_source_demand(self) -> None:
        source = self._create("source")
        dependency = self._create("dependency")
        demand_sys.add_dependency(
            self.actor_target,
            source["id"],
            1,
            dependency["id"],
        )
        dependency_before = demand_sys.get(self.actor_target, dependency["id"])

        receipt = demand_sys.remove_dependency(
            self.actor_target,
            source["id"],
            2,
            dependency["id"],
        )

        self.assertEqual(
            receipt["changes"],
            [
                {
                    "demand_id": source["id"],
                    "revision": 3,
                    "kind": "dependency_removed",
                }
            ],
        )
        self.assertEqual(
            demand_sys.get(self.actor_target, source["id"])["depends_on"],
            [],
        )
        self.assertEqual(
            demand_sys.get(self.actor_target, dependency["id"]),
            dependency_before,
        )

    def test_split_revises_parent_and_atomically_creates_two_children(self) -> None:
        parent = self._create(
            "csv-export",
            description="Support user data CSV export.",
            detail="Users can export their data as CSV.",
        )
        children = [
            {
                "intake_key": "actor-self:csv-export-ui",
                "description": "Expose CSV export controls.",
                "detail": "Add the export control and progress feedback.",
                "source_refs": [],
            },
            {
                "intake_key": "actor-self:csv-export-data",
                "description": "Generate CSV export data.",
                "detail": "Serialize the user's exportable data.",
                "source_refs": [],
            },
        ]

        receipt = demand_sys.split(
            self.actor_target,
            parent["id"],
            1,
            "Deliver CSV export as two component demands.",
            "The live parent organizes UI and data components.",
            children,
        )
        records = demand_sys.list_demands(self.actor_target)
        current_parent = demand_sys.get(self.actor_target, parent["id"])
        created_ids = [
            change["demand_id"]
            for change in receipt["changes"]
            if change["kind"] == "created"
        ]

        self.assertEqual(current_parent["revision"], 2)
        self.assertIsNone(current_parent["terminal"])
        self.assertEqual(len(created_ids), 2)
        self.assertEqual(len(records), 3)
        for child_id in created_ids:
            child = demand_sys.get(self.actor_target, child_id)
            self.assertEqual(child["parent_id"], parent["id"])
            self.assertEqual(child["revision"], 1)

    def test_split_requires_at_least_two_children_without_partial_write(self) -> None:
        parent = self._create("split-parent")

        self._assert_unchanged_error(
            demand_sys.DemandPayloadError,
            lambda: demand_sys.split(
                self.actor_target,
                parent["id"],
                1,
                "Insufficient split.",
                "Only one child is invalid.",
                [
                    {
                        "intake_key": "actor-self:only-child",
                        "description": "Only child.",
                        "detail": "A split requires at least two.",
                        "source_refs": [],
                    }
                ],
            ),
        )

    def _revise_to_five(self, record: dict[str, Any]) -> dict[str, Any]:
        current = record
        for revision in range(1, 5):
            demand_sys.revise(
                self.actor_target,
                current["id"],
                revision,
                f"CSV export requirement revision {revision + 1}.",
                f"Canonical CSV export detail revision {revision + 1}.",
            )
            current = demand_sys.get(self.actor_target, current["id"])
        return current

    def test_absorb_d_at_one_into_c_at_five_updates_both_once(self) -> None:
        c_ref = {
            "type": "im.message.created",
            "ref": {
                "message_id": "msg-c",
                "conversation_id": "conv-csv",
                "event_id": "imev-c",
            },
        }
        d_ref = {
            "type": "im.message.created",
            "ref": {
                "message_id": "msg-d",
                "conversation_id": "conv-csv",
                "event_id": "imev-d",
            },
        }
        c_refs = [c_ref, c_ref]
        d_refs = [c_ref, d_ref, d_ref]
        demand_c = self._revise_to_five(
            self._create(
                "c",
                description="Support user data CSV export.",
                detail="Users can export their data as CSV.",
                source_refs=c_refs,
            )
        )
        demand_d = self._create(
            "d",
            description="CSV export must include the user timezone.",
            detail="Add the user timezone to every exported row.",
            source_refs=d_refs,
        )
        merged_target = {
            "description": "Support CSV export with the user timezone.",
            "detail": "Users can export CSV and every row includes the user timezone.",
        }

        receipt = demand_sys.absorb_into(
            self.actor_target,
            demand_d["id"],
            1,
            demand_c["id"],
            5,
            merged_target,
            "Merged the timezone requirement into CSV export.",
        )
        current_c = demand_sys.get(self.actor_target, demand_c["id"])
        current_d = demand_sys.get(self.actor_target, demand_d["id"])

        self.assertEqual(
            receipt["changes"],
            [
                {"demand_id": demand_c["id"], "revision": 6, "kind": "revised"},
                {"demand_id": demand_d["id"], "revision": 2, "kind": "absorbed"},
            ],
        )
        self.assertEqual(current_c["revision"], 6)
        self.assertIsNone(current_c["terminal"])
        self.assertEqual(current_c["description"], merged_target["description"])
        self.assertEqual(current_c["source_refs"], [c_ref, d_ref])
        self.assertEqual(current_d["revision"], 2)
        self.assertEqual(current_d["terminal"]["type"], "absorbed")
        self.assertEqual(current_d["terminal"]["ref"], demand_c["id"])

        replay = demand_sys.absorb_into(
            self.actor_target,
            demand_d["id"],
            1,
            demand_c["id"],
            5,
            merged_target,
            "Merged the timezone requirement into CSV export.",
        )
        self.assertEqual(
            replay,
            {"state_changed": False, "changes": [], "check_required": False},
        )

    def test_absorb_stale_source_or_target_revision_changes_neither_record(self) -> None:
        source = self._create("stale-source")
        target = self._create("stale-target")
        merged = {
            "description": "Merged demand.",
            "detail": "Merged detail.",
        }

        for source_revision, target_revision in ((2, 1), (1, 2)):
            self._assert_unchanged_error(
                demand_sys.DemandRevisionConflict,
                lambda source_revision=source_revision, target_revision=target_revision: demand_sys.absorb_into(
                    self.actor_target,
                    source["id"],
                    source_revision,
                    target["id"],
                    target_revision,
                    merged,
                    "Must remain atomic.",
                ),
            )

    def test_absorb_source_with_live_child_is_rejected(self) -> None:
        source = self._create("source-with-child")
        child = self._create("live-child")
        target = self._create("absorb-target")
        demand_sys.set_parent(self.actor_target, child["id"], 1, source["id"])

        self._assert_unchanged_error(
            demand_sys.DemandRelationConflict,
            lambda: demand_sys.absorb_into(
                self.actor_target,
                source["id"],
                1,
                target["id"],
                1,
                {
                    "description": "Merged demand.",
                    "detail": "Merged detail.",
                },
                "Live children must be handled explicitly.",
            ),
        )

    def test_every_terminal_action_rejects_a_demand_with_live_children(self) -> None:
        for action_name in ("mark_duplicate", "supersede", "complete", "cancel"):
            with self.subTest(action=action_name):
                parent = self._create(f"{action_name}-parent")
                child = self._create(f"{action_name}-child")
                target = self._create(f"{action_name}-target")
                demand_sys.set_parent(
                    self.actor_target,
                    child["id"],
                    1,
                    parent["id"],
                )

                if action_name == "mark_duplicate":
                    action = lambda: demand_sys.mark_duplicate(
                        self.actor_target,
                        parent["id"],
                        1,
                        target["id"],
                        "Live children must remain attached to a live parent.",
                    )
                elif action_name == "supersede":
                    action = lambda: demand_sys.supersede(
                        self.actor_target,
                        parent["id"],
                        1,
                        target["id"],
                        "Live children must remain attached to a live parent.",
                    )
                elif action_name == "complete":
                    action = lambda: demand_sys.complete(
                        self.actor_target,
                        parent["id"],
                        1,
                        "Parent cannot complete before its live children are resolved.",
                        [],
                    )
                else:
                    action = lambda: demand_sys.cancel(
                        self.actor_target,
                        parent["id"],
                        1,
                        "Parent cannot cancel while its live children remain.",
                    )

                error = self._assert_unchanged_error(
                    demand_sys.DemandRelationConflict,
                    action,
                )
                self.assertEqual(error.code, "E_DEMAND_RELATION")

    def test_mark_duplicate_terminalizes_source_only_and_exact_replay_is_noop(self) -> None:
        source = self._create("duplicate-source")
        target = self._create("duplicate-target")
        target_before = demand_sys.get(self.actor_target, target["id"])

        receipt = demand_sys.mark_duplicate(
            self.actor_target,
            source["id"],
            1,
            target["id"],
            "Same canonical demand.",
        )
        replay = demand_sys.mark_duplicate(
            self.actor_target,
            source["id"],
            1,
            target["id"],
            "Same canonical demand.",
        )

        self.assertEqual(receipt["changes"][0]["kind"], "duplicate")
        self.assertEqual(
            demand_sys.get(self.actor_target, source["id"])["terminal"]["ref"],
            target["id"],
        )
        self.assertEqual(demand_sys.get(self.actor_target, target["id"]), target_before)
        self.assertFalse(replay["state_changed"])

    def test_supersede_terminalizes_old_only_and_exact_replay_is_noop(self) -> None:
        old = self._create("old-demand")
        replacement = self._create("replacement")
        replacement_before = demand_sys.get(self.actor_target, replacement["id"])

        receipt = demand_sys.supersede(
            self.actor_target,
            old["id"],
            1,
            replacement["id"],
            "Replacement is the current requirement.",
        )
        replay = demand_sys.supersede(
            self.actor_target,
            old["id"],
            1,
            replacement["id"],
            "Replacement is the current requirement.",
        )

        self.assertEqual(receipt["changes"][0]["kind"], "superseded")
        self.assertEqual(
            demand_sys.get(self.actor_target, old["id"])["terminal"]["ref"],
            replacement["id"],
        )
        self.assertEqual(
            demand_sys.get(self.actor_target, replacement["id"]),
            replacement_before,
        )
        self.assertFalse(replay["state_changed"])

    def test_complete_stores_summary_and_evidence_and_exact_replay_is_noop(self) -> None:
        record = self._create("complete")
        evidence_refs = [
            {"type": "artifact", "ref": {"id": "art-demand-proof"}}
        ]

        receipt = demand_sys.complete(
            self.actor_target,
            record["id"],
            1,
            "Acceptance evidence is complete.",
            evidence_refs,
        )
        replay = demand_sys.complete(
            self.actor_target,
            record["id"],
            1,
            "Acceptance evidence is complete.",
            evidence_refs,
        )
        terminal = demand_sys.get(self.actor_target, record["id"])["terminal"]

        self.assertEqual(receipt["changes"][0]["kind"], "completed")
        self.assertEqual(terminal["summary"], "Acceptance evidence is complete.")
        self.assertEqual(terminal["evidence_refs"], evidence_refs)
        self.assertFalse(replay["state_changed"])

    def test_cancel_stores_summary_without_evidence_and_exact_replay_is_noop(self) -> None:
        record = self._create("cancel")

        receipt = demand_sys.cancel(
            self.actor_target,
            record["id"],
            1,
            "Requirement was withdrawn.",
        )
        replay = demand_sys.cancel(
            self.actor_target,
            record["id"],
            1,
            "Requirement was withdrawn.",
        )
        terminal = demand_sys.get(self.actor_target, record["id"])["terminal"]

        self.assertEqual(receipt["changes"][0]["kind"], "canceled")
        self.assertEqual(
            terminal,
            {
                "type": "canceled",
                "at": terminal["at"],
                "summary": "Requirement was withdrawn.",
            },
        )
        self.assertFalse(replay["state_changed"])

    def test_different_action_against_terminal_demand_is_rejected(self) -> None:
        record = self._create("terminal-conflict")
        demand_sys.cancel(
            self.actor_target,
            record["id"],
            1,
            "Requirement was withdrawn.",
        )

        raised = self._assert_unchanged_error(
            demand_sys.DemandTerminalConflict,
            lambda: demand_sys.complete(
                self.actor_target,
                record["id"],
                1,
                "Cannot complete a canceled Demand.",
                [],
            ),
        )
        self.assertEqual(raised.code, "E_DEMAND_TERMINAL")


if __name__ == "__main__":
    import unittest

    unittest.main()
