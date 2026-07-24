"""Actor-facing six-intent Demand Sys response contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

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
        turn_id: str = "turn-demand-1",
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
            invocation={
                "thread_id": "thr-main",
                "turn_id": turn_id,
                "request_id": f"req-{turn_id}",
            },
        )
        self.assertEqual(
            self._task_snapshot(),
            before,
            msg=f"demand_sys.{action} changed Task Sys",
        )
        return response

    def _create(
        self,
        *,
        instance_json: Path,
        actor_id: str,
        description: str,
        turn_id: str,
        role: str = "dev",
    ) -> dict[str, object]:
        response = self._demand_dispatch(
            instance_json=instance_json,
            actor_id=actor_id,
            role=role,
            action="create",
            turn_id=turn_id,
            args={
                "description": description,
                "detail": f"Detail for {description}",
            },
        )
        return response

    def _assert_no_internal_concurrency_keys(self, value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                self.assertNotIn(
                    key,
                    {
                        "revision",
                        "expected_revision",
                        "checked_revision",
                        "basis_revision",
                        "intake_key",
                        "demand_pool_revision",
                        "ingress_receipts",
                    },
                    msg=value,
                )
                self._assert_no_internal_concurrency_keys(nested)
        elif isinstance(value, list):
            for nested in value:
                self._assert_no_internal_concurrency_keys(nested)

    def test_same_turn_create_replays_and_a_different_turn_creates_again(self) -> None:
        actor_label = "act-dev-demand-create-identity"
        instance_json = self._instance_json(role="dev", actor_id=actor_label)

        first = self._create(
            instance_json=instance_json,
            actor_id=actor_label,
            description="Export CSV",
            turn_id="turn-1",
        )
        self._assert_write_success_contract(first)
        replay = self._create(
            instance_json=instance_json,
            actor_id=actor_label,
            description="Export CSV",
            turn_id="turn-1",
        )
        self._assert_success_contract(replay)
        self.assertFalse(replay["state_changed"], msg=replay)
        self.assertEqual(replay["demand_id"], first["demand_id"])
        self.assertIn("no new Demand or mutation occurred", replay["effect_summary"])
        self.assertIn("No Task or native Goal was created", replay["effect_summary"])

        second = self._create(
            instance_json=instance_json,
            actor_id=actor_label,
            description="Export CSV",
            turn_id="turn-2",
        )
        self._assert_write_success_contract(second)
        self.assertNotEqual(second["demand_id"], first["demand_id"])

        target = {
            "actor_id": self._runtime_actor_id(role="dev", label=actor_label),
            "role_id": "dev",
        }
        stored = demands.load_actor_state(target)
        self.assertEqual(len(stored["demands"]), 2)
        self.assertEqual(stored["ingress_receipts"], {})
        for record in stored["demands"].values():
            self.assertEqual(
                record["source_refs"],
                [{
                    "type": "actor.self_requested",
                    "ref": {
                        "thread_id": "thr-main",
                        "turn_id": (
                            "turn-1"
                            if record["id"] == first["demand_id"]
                            else "turn-2"
                        ),
                    },
                }],
            )

    def test_all_six_actions_expose_only_actor_level_fields(self) -> None:
        actor_label = "act-dev-demand-six-intents"
        instance_json = self._instance_json(role="dev", actor_id=actor_label)
        created = self._create(
            instance_json=instance_json,
            actor_id=actor_label,
            description="Ship calendar",
            turn_id="turn-create",
        )
        demand_id = str(created["demand_id"])

        listed = self._demand_dispatch(
            instance_json=instance_json,
            actor_id=actor_label,
            action="list",
            args={},
        )
        self._assert_success_contract(listed)
        self.assertEqual(
            set(listed["demands"][0]),
            {"id", "description", "terminal", "updated_at"},
        )

        opened = self._demand_dispatch(
            instance_json=instance_json,
            actor_id=actor_label,
            action="get",
            args={"demand_id": demand_id},
        )
        self._assert_success_contract(opened)
        self.assertEqual(
            set(opened["demand"]),
            {
                "id",
                "description",
                "detail",
                "source_refs",
                "terminal",
                "created_at",
                "updated_at",
                "demand_ref",
            },
        )

        revised = self._demand_dispatch(
            instance_json=instance_json,
            actor_id=actor_label,
            action="revise",
            args={
                "demand_ref": opened["demand"]["demand_ref"],
                "description": "Ship calendar with recurring events",
                "detail": "Support daily and weekly recurrence.",
                "reason": "The goal now includes recurrence.",
            },
        )
        self._assert_write_success_contract(revised)

        completed = self._demand_dispatch(
            instance_json=instance_json,
            actor_id=actor_label,
            action="complete",
            args={
                "demand_ref": revised["demand_ref"],
                "summary": "Calendar behavior is verified.",
                "evidence_refs": [{
                    "type": "task_sys.task",
                    "ref": {"task_id": "task-calendar"},
                }],
            },
        )
        self._assert_write_success_contract(completed)

        cancel_created = self._create(
            instance_json=instance_json,
            actor_id=actor_label,
            description="Discarded idea",
            turn_id="turn-cancel",
        )
        canceled = self._demand_dispatch(
            instance_json=instance_json,
            actor_id=actor_label,
            action="cancel",
            args={
                "demand_ref": cancel_created["demand_ref"],
                "summary": "The actor withdrew the need.",
            },
        )
        self._assert_write_success_contract(canceled)

        expected_effects = {
            "create": (created, "Created one live canonical Demand", "No Task or native Goal was created"),
            "revise": (revised, "Replaced the live Demand's canonical meaning", "No Task or native Goal was changed"),
            "complete": (completed, "Terminalized the Demand as completed", "No Task or native Goal was changed"),
            "cancel": (canceled, "Terminalized the Demand as canceled", "No Task or native Goal was changed"),
        }
        for action, (payload, effect, boundary) in expected_effects.items():
            with self.subTest(action=action):
                effect_summary = str(payload.get("effect_summary", ""))
                self.assertIn(effect, effect_summary)
                self.assertIn(boundary, effect_summary)

        for payload in (
            created,
            listed,
            opened,
            revised,
            completed,
            canceled,
        ):
            self._assert_no_internal_concurrency_keys(payload)

    def test_unknown_fields_cross_actor_access_and_stale_refs_are_rejected(self) -> None:
        actor_a = "act-dev-demand-a"
        actor_b = "act-dev-demand-b"
        instance_a = self._instance_json(role="dev", actor_id=actor_a)
        instance_b = self._instance_json(role="dev", actor_id=actor_b)
        created = self._create(
            instance_json=instance_a,
            actor_id=actor_a,
            description="Actor A need",
            turn_id="turn-a",
        )

        unknown = self._demand_dispatch(
            instance_json=instance_a,
            actor_id=actor_a,
            action="create",
            args={
                "description": "Bad",
                "detail": "Host fields are forbidden.",
                "source_refs": [],
            },
        )
        self._assert_rejection_contract(unknown)
        self.assertEqual(unknown["error"]["code"], "E_DEMAND_PAYLOAD")

        cross_actor = self._demand_dispatch(
            instance_json=instance_b,
            actor_id=actor_b,
            action="get",
            args={"demand_id": created["demand_id"]},
        )
        self._assert_rejection_contract(cross_actor)
        self.assertEqual(cross_actor["error"]["code"], "E_DEMAND_NOT_FOUND")

        revised = self._demand_dispatch(
            instance_json=instance_a,
            actor_id=actor_a,
            action="revise",
            args={
                "demand_ref": created["demand_ref"],
                "description": "Actor A need revised",
                "detail": "The current canonical meaning.",
                "reason": "Clarified.",
            },
        )
        self._assert_write_success_contract(revised)
        stale = self._demand_dispatch(
            instance_json=instance_a,
            actor_id=actor_a,
            action="revise",
            args={
                "demand_ref": created["demand_ref"],
                "description": "Stale overwrite",
                "detail": "Must not replace the current meaning.",
                "reason": "Uses an old opaque ref.",
            },
        )
        self._assert_rejection_contract(stale)
        self.assertEqual(stale["error"]["code"], "E_DEMAND_REVISION_CONFLICT")
        self.assertIn("no demand, task, daemon, or inbound state was changed", stale["impact"].lower())
        self.assertIn("demand_sys.get", str(stale["retry_guidance"]).lower())
        self.assertIn("re-evaluate", str(stale["retry_guidance"]).lower())
