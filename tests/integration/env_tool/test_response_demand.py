"""Response and isolation contracts for actor-facing Demand Sys actions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from env.domain import demand_sys
from env.repos import demands
from env.repos import runtime_files
from tests.integration.env_tool._response_case import EnvToolResponseCase


class EnvToolDemandResponseTests(EnvToolResponseCase):
    def _task_snapshot(self) -> dict[str, bytes]:
        root = runtime_files.OBJECTS_ROOT / "task-sys" / "tasks"
        if not root.exists():
            return {}
        return {
            str(path.relative_to(root)): path.read_bytes()
            for path in sorted(root.rglob("*.json"))
        }

    def _demand_dispatch(
        self,
        *,
        instance_json: Path,
        actor_id: str,
        action: str,
        args: dict[str, object],
        role: str = "dev",
    ) -> dict[str, object]:
        before = self._task_snapshot()
        response = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_id,
            role=role,
            tool="demand_sys",
            action=action,
            args=args,
        )
        self.assertEqual(self._task_snapshot(), before, msg=f"demand_sys.{action} changed Task Sys")
        return response

    def _create(
        self,
        *,
        instance_json: Path,
        actor_id: str,
        intake_key: str,
        description: str | None = None,
        role: str = "dev",
    ) -> tuple[str, int, dict[str, object]]:
        response = self._demand_dispatch(
            instance_json=instance_json,
            actor_id=actor_id,
            role=role,
            action="create",
            args={
                "intake_key": intake_key,
                "description": description or intake_key,
                "detail": f"Detail for {intake_key}",
                "source_refs": [{"type": "actor", "ref": {"key": intake_key}}],
            },
        )
        self._assert_write_success_contract(response)
        changes = response.get("changes")
        self.assertIsInstance(changes, list, msg=response)
        assert isinstance(changes, list)
        change = changes[0]
        self.assertIsInstance(change, dict, msg=response)
        assert isinstance(change, dict)
        return str(change["demand_id"]), int(change["revision"]), response

    def test_payload_revision_and_actor_isolation_rejections_are_stable(self) -> None:
        actor_a_label = "act-dev-demand-a"
        actor_b_label = "act-dev-demand-b"
        instance_a = self._instance_json(role="dev", actor_id=actor_a_label)
        instance_b = self._instance_json(role="dev", actor_id=actor_b_label)
        demand_b, _, _ = self._create(
            instance_json=instance_b,
            actor_id=actor_b_label,
            intake_key="actor-b:demand",
        )
        target_b = {
            "actor_id": self._runtime_actor_id(role="dev", label=actor_b_label),
            "role_id": "dev",
        }
        before_b = demands.load_actor_state(target_b)

        for action, args in (
            ("get", {"demand_id": demand_b}),
            (
                "revise",
                {
                    "demand_id": demand_b,
                    "expected_revision": 1,
                    "description": "Cross-actor mutation",
                    "detail": "Must be rejected.",
                },
            ),
        ):
            with self.subTest(action=action):
                response = self._demand_dispatch(
                    instance_json=instance_a,
                    actor_id=actor_a_label,
                    action=action,
                    args=args,
                )
                self._assert_rejection_contract(response)
                self.assertEqual((response.get("error") or {}).get("code"), "E_DEMAND_NOT_FOUND")
        self.assertEqual(demands.load_actor_state(target_b), before_b)

        target_a = {
            "actor_id": self._runtime_actor_id(role="dev", label=actor_a_label),
            "role_id": "dev",
        }
        before_a = demands.load_actor_state(target_a)
        bad_payload = self._demand_dispatch(
            instance_json=instance_a,
            actor_id=actor_a_label,
            action="create",
            args={
                "intake_key": "actor-a:bad",
                "description": "Bad payload",
                "detail": "Unknown field must be rejected.",
                "source_refs": [],
                "actor_id": target_b["actor_id"],
            },
        )
        self._assert_rejection_contract(bad_payload)
        self.assertEqual((bad_payload.get("error") or {}).get("code"), "E_DEMAND_PAYLOAD")
        self.assertEqual(demands.load_actor_state(target_a), before_a)

        demand_a, _, _ = self._create(
            instance_json=instance_a,
            actor_id=actor_a_label,
            intake_key="actor-a:revision",
        )
        revised = self._demand_dispatch(
            instance_json=instance_a,
            actor_id=actor_a_label,
            action="revise",
            args={
                "demand_id": demand_a,
                "expected_revision": 1,
                "description": "Revision two",
                "detail": "Current Demand revision is now two.",
            },
        )
        self._assert_write_success_contract(revised)
        stale = self._demand_dispatch(
            instance_json=instance_a,
            actor_id=actor_a_label,
            action="revise",
            args={
                "demand_id": demand_a,
                "expected_revision": 1,
                "description": "Stale write",
                "detail": "Must not replace revision two.",
            },
        )
        self._assert_rejection_contract(stale)
        self.assertEqual((stale.get("error") or {}).get("code"), "E_DEMAND_REVISION_CONFLICT")
        guidance = str(stale.get("retry_guidance", "")).lower()
        self.assertIn("get", guidance)
        self.assertIn("check", guidance)
        self.assertIn("current revision", guidance)

    def test_every_demand_action_preserves_task_records_and_returns_demand_receipts(self) -> None:
        actor_label = "act-dev-demand-actions"
        instance_json = self._instance_json(role="dev", actor_id=actor_label)

        root, root_revision, _ = self._create(
            instance_json=instance_json,
            actor_id=actor_label,
            intake_key="root",
        )
        replayed = self._demand_dispatch(
            instance_json=instance_json,
            actor_id=actor_label,
            action="create",
            args={
                "intake_key": "root",
                "description": "root",
                "detail": "Detail for root",
                "source_refs": [{"type": "actor", "ref": {"key": "root"}}],
            },
        )
        self._assert_success_contract(replayed)
        self.assertFalse(replayed["state_changed"], msg=replayed)
        self.assertEqual(replayed["demand_id"], root)
        self.assertEqual(replayed["revision"], root_revision)
        revised = self._demand_dispatch(
            instance_json=instance_json,
            actor_id=actor_label,
            action="revise",
            args={
                "demand_id": root,
                "expected_revision": root_revision,
                "description": "Root revised",
                "detail": "Root revision two.",
            },
        )
        self._assert_write_success_contract(revised)
        root_revision = int(revised["changes"][0]["revision"])  # type: ignore[index]

        for action, args, result_key in (
            ("list", {"state": "all"}, "demands"),
            ("get", {"demand_id": root}, "demand"),
            ("get_many", {"demand_ids": [root]}, "demands"),
            ("check", {}, "attention_items"),
        ):
            response = self._demand_dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                action=action,
                args=args,
            )
            self._assert_success_contract(response)
            self.assertFalse(response["state_changed"], msg=response)
            self.assertIn(result_key, response)

        completed_check = self._demand_dispatch(
            instance_json=instance_json,
            actor_id=actor_label,
            action="complete_check",
            args={"observed": [{"demand_id": root, "revision": root_revision}]},
        )
        self._assert_success_contract(completed_check)
        self.assertEqual(completed_check["acknowledged"], [{"demand_id": root, "revision": root_revision}])
        self.assertEqual(completed_check["still_pending"], [])

        parent, parent_revision, _ = self._create(
            instance_json=instance_json,
            actor_id=actor_label,
            intake_key="parent",
        )
        dependency, _, _ = self._create(
            instance_json=instance_json,
            actor_id=actor_label,
            intake_key="dependency",
        )
        for action, args in (
            (
                "set_parent",
                {"demand_id": root, "expected_revision": root_revision, "parent_id": parent},
            ),
            (
                "add_dependency",
                {"demand_id": root, "expected_revision": root_revision + 1, "dependency_id": dependency},
            ),
            (
                "remove_dependency",
                {"demand_id": root, "expected_revision": root_revision + 2, "dependency_id": dependency},
            ),
        ):
            response = self._demand_dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                action=action,
                args=args,
            )
            self._assert_write_success_contract(response)

        split = self._demand_dispatch(
            instance_json=instance_json,
            actor_id=actor_label,
            action="split",
            args={
                "demand_id": parent,
                "expected_revision": parent_revision,
                "description": "Parent split",
                "detail": "Parent now owns two concrete parts.",
                "children": [
                    {"intake_key": "child:one", "description": "Child one", "detail": "First part.", "source_refs": []},
                    {"intake_key": "child:two", "description": "Child two", "detail": "Second part.", "source_refs": []},
                ],
            },
        )
        self._assert_write_success_contract(split)
        self.assertEqual(len(split["changes"]), 3)  # type: ignore[arg-type]

        target, target_revision, _ = self._create(
            instance_json=instance_json,
            actor_id=actor_label,
            intake_key="absorb:target",
        )
        source, source_revision, _ = self._create(
            instance_json=instance_json,
            actor_id=actor_label,
            intake_key="absorb:source",
        )
        absorbed = self._demand_dispatch(
            instance_json=instance_json,
            actor_id=actor_label,
            action="absorb_into",
            args={
                "source_id": source,
                "source_revision": source_revision,
                "target_id": target,
                "target_revision": target_revision,
                "merged_target": {
                    "description": "Merged target",
                    "detail": "Target now contains the supplemental Demand.",
                },
                "summary": "Supplement absorbed into the active Demand.",
            },
        )
        self._assert_write_success_contract(absorbed)
        changed = {
            (row["demand_id"], row["revision"])
            for row in absorbed["changes"]  # type: ignore[union-attr]
        }
        self.assertEqual(changed, {(target, 2), (source, 2)})

        duplicate_source, duplicate_revision, _ = self._create(
            instance_json=instance_json,
            actor_id=actor_label,
            intake_key="duplicate:source",
        )
        duplicate_target, _, _ = self._create(
            instance_json=instance_json,
            actor_id=actor_label,
            intake_key="duplicate:target",
        )
        superseded, superseded_revision, _ = self._create(
            instance_json=instance_json,
            actor_id=actor_label,
            intake_key="supersede:old",
        )
        replacement, _, _ = self._create(
            instance_json=instance_json,
            actor_id=actor_label,
            intake_key="supersede:new",
        )
        completable, completable_revision, _ = self._create(
            instance_json=instance_json,
            actor_id=actor_label,
            intake_key="complete",
        )
        cancelable, cancelable_revision, _ = self._create(
            instance_json=instance_json,
            actor_id=actor_label,
            intake_key="cancel",
        )

        terminal_actions: tuple[tuple[str, dict[str, Any]], ...] = (
            (
                "mark_duplicate",
                {
                    "source_id": duplicate_source,
                    "source_revision": duplicate_revision,
                    "target_id": duplicate_target,
                    "summary": "Same need.",
                },
            ),
            (
                "supersede",
                {
                    "old_id": superseded,
                    "old_revision": superseded_revision,
                    "replacement_id": replacement,
                    "summary": "Replacement is the current need.",
                },
            ),
            (
                "complete",
                {
                    "demand_id": completable,
                    "expected_revision": completable_revision,
                    "summary": "Need was satisfied.",
                    "evidence_refs": [
                        {"type": "task_sys.task", "ref": {"task_id": "task-demand-proof"}}
                    ],
                },
            ),
            (
                "cancel",
                {
                    "demand_id": cancelable,
                    "expected_revision": cancelable_revision,
                    "summary": "Need is no longer relevant.",
                },
            ),
        )
        for action, args in terminal_actions:
            with self.subTest(action=action):
                response = self._demand_dispatch(
                    instance_json=instance_json,
                    actor_id=actor_label,
                    action=action,
                    args=args,
                )
                self._assert_write_success_contract(response)

        completed = self._demand_dispatch(
            instance_json=instance_json,
            actor_id=actor_label,
            action="get",
            args={"demand_id": completable},
        )
        self.assertEqual(
            completed["demand"]["terminal"]["evidence_refs"],  # type: ignore[index]
            [{"type": "task_sys.task", "ref": {"task_id": "task-demand-proof"}}],
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
