"""Demand canonicalization contracts without a relation graph."""

from __future__ import annotations

from typing import Any, Callable

from env.domain import demand_sys
from env.repos import demands
from tests.support.runtime import RuntimeWorkspaceTestCase


class DemandCanonicalizationTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.actor_target = {
            "actor_id": self._runtime_actor_id(role="pm", label="demand-canonicalization"),
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

    def test_absorb_supplement_updates_target_and_terminalizes_source_atomically(self) -> None:
        target_ref = {"type": "im.message.created", "ref": {"id": "msg-target"}}
        source_ref = {"type": "im.message.created", "ref": {"id": "msg-source"}}
        target = self._create(
            "target",
            description="Support CSV export.",
            detail="Users can export CSV.",
            source_refs=[target_ref],
        )
        source = self._create(
            "source",
            description="CSV export includes timezone.",
            detail="Add timezone to each exported row.",
            source_refs=[source_ref],
        )
        merged = {
            "description": "Support CSV export with timezone.",
            "detail": "Users can export CSV with timezone on every row.",
        }

        receipt = demand_sys.absorb_into(
            self.actor_target,
            source["id"],
            1,
            target["id"],
            1,
            merged,
            "Same canonical need.",
        )
        target_after = demand_sys.get(self.actor_target, target["id"])
        source_after = demand_sys.get(self.actor_target, source["id"])

        self.assertEqual(
            receipt["changes"],
            [
                {"demand_id": target["id"], "revision": 2, "kind": "revised"},
                {"demand_id": source["id"], "revision": 2, "kind": "absorbed"},
            ],
        )
        self.assertEqual(target_after["description"], merged["description"])
        self.assertEqual(target_after["detail"], merged["detail"])
        self.assertEqual(target_after["source_refs"], [target_ref, source_ref])
        self.assertEqual(
            source_after["terminal"],
            {
                "type": "absorbed",
                "at": source_after["terminal"]["at"],
                "summary": "Same canonical need.",
                "target_demand_id": target["id"],
            },
        )

    def test_absorb_semantic_duplicate_merges_provenance_even_when_content_is_unchanged(self) -> None:
        shared = {"type": "im.message.created", "ref": {"id": "msg-shared"}}
        extra = {"type": "track.comment.added", "ref": {"id": "comment-extra"}}
        target = self._create(
            "duplicate-target",
            description="Export data as CSV.",
            detail="Users can export their data as CSV.",
            source_refs=[shared],
        )
        source = self._create(
            "duplicate-source",
            description=target["description"],
            detail=target["detail"],
            source_refs=[shared, extra, extra],
        )

        demand_sys.absorb_into(
            self.actor_target,
            source["id"],
            1,
            target["id"],
            1,
            {"description": target["description"], "detail": target["detail"]},
            "Two intakes express the same canonical need.",
        )

        target_after = demand_sys.get(self.actor_target, target["id"])
        source_after = demand_sys.get(self.actor_target, source["id"])
        self.assertEqual(target_after["revision"], 2)
        self.assertEqual(target_after["source_refs"], [shared, extra])
        self.assertEqual(source_after["terminal"]["target_demand_id"], target["id"])

    def test_absorb_stale_source_or_target_changes_neither_record(self) -> None:
        source = self._create("stale-source")
        target = self._create("stale-target")
        merged = {"description": "Merged demand.", "detail": "Merged detail."}

        for source_revision, target_revision in ((2, 1), (1, 2)):
            with self.subTest(source=source_revision, target=target_revision):
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

    def test_absorb_rejects_self_without_write(self) -> None:
        demand = self._create("self")

        raised = self._assert_unchanged_error(
            demand_sys.DemandPayloadError,
            lambda: demand_sys.absorb_into(
                self.actor_target,
                demand["id"],
                1,
                demand["id"],
                1,
                {"description": demand["description"], "detail": demand["detail"]},
                "Self absorption is invalid.",
            ),
        )
        self.assertEqual(raised.code, "E_DEMAND_PAYLOAD")

    def test_absorb_exact_replay_is_noop(self) -> None:
        source = self._create("replay-source")
        target = self._create("replay-target")
        merged = {"description": "Merged demand.", "detail": "Merged detail."}
        args = (
            self.actor_target,
            source["id"],
            1,
            target["id"],
            1,
            merged,
            "Same canonical need.",
        )
        demand_sys.absorb_into(*args)
        before = self._bytes()

        replay = demand_sys.absorb_into(*args)

        self.assertEqual(
            replay,
            {"state_changed": False, "changes": [], "check_required": False},
        )
        self.assertEqual(self._bytes(), before)

    def test_absorbed_terminal_uses_target_demand_id_not_ref(self) -> None:
        source = self._create("terminal-source")
        target = self._create("terminal-target")
        demand_sys.absorb_into(
            self.actor_target,
            source["id"],
            1,
            target["id"],
            1,
            {"description": target["description"], "detail": target["detail"]},
            "Same canonical need.",
        )

        terminal = demand_sys.get(self.actor_target, source["id"])["terminal"]

        self.assertEqual(terminal["target_demand_id"], target["id"])
        self.assertNotIn("ref", terminal)


if __name__ == "__main__":
    import unittest

    unittest.main()
