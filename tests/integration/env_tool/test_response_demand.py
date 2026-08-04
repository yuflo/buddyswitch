"""Wire and response contracts for the four-action Demand tool."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from buddyswitch.launcher import side_thread_registry
from tests.support import task_fixtures
from buddyswitch.modules.communication.private.domain import messages as message_service
from buddyswitch.modules.demand.private.adapters.daemon import (
    demand_triage_runtime,
)
from buddyswitch.modules.demand.private.domain import demand_sys
from buddyswitch.modules.demand.private.state import demands
from tests.integration.env_tool._response_case import EnvToolResponseCase


class EnvToolResponseDemandTests(EnvToolResponseCase):
    def _seed_active_task(
        self,
        *,
        instance_json: Path,
        role: str,
        actor_id: str,
    ) -> None:
        del instance_json, role, actor_id

    @staticmethod
    def _proposal(
        decision: str,
        *,
        demand_ref: str | None = None,
        description: str | None = None,
        detail: str | None = None,
        reply_content: str | None = None,
    ) -> dict[str, Any]:
        return {
            "decision": decision,
            "reason": f"Grounded reason for {decision}.",
            "demand_ref": demand_ref,
            "description": description,
            "detail": detail,
            "reply_content": reply_content,
        }

    def _prepare_instance(
        self,
        *,
        actor_label: str,
        role: str = "dev",
    ) -> tuple[Path, str, dict[str, str]]:
        instance_json = self._instance_json(role=role, actor_id=actor_label)
        actor_id = self._runtime_actor_id(role=role, label=actor_label)
        payload = json.loads(instance_json.read_text(encoding="utf-8"))
        payload["thread_id"] = "thr-main"
        payload["side_threads"] = []
        instance_json.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return instance_json, actor_id, {
            "actor_id": actor_id,
            "role_id": role,
        }

    def _task_snapshot(self) -> dict[str, str]:
        tasks_root = (
            self.runtime_root
            / "buddyswitch"
            / "objects"
            / "task-sys"
            / "tasks"
        )
        if not tasks_root.exists():
            return {}
        return {
            path.relative_to(tasks_root).as_posix(): path.read_text(
                encoding="utf-8"
            )
            for path in sorted(tasks_root.glob("*.json"))
        }

    def _create_domain_demand(
        self,
        *,
        actor_target: dict[str, str],
        label: str,
    ) -> dict[str, Any]:
        source_key = f"track.comment.added:{label}"
        demand_sys.claim_ingress(
            actor_target,
            source_key,
            f"Deliver {label}.",
            f"Provide durable delivery evidence for {label}.",
            [{
                "type": "track.comment.added",
                "ref": {
                    "track_id": "track-demand-completion",
                    "comment_id": label,
                    "thread_id": "comment-thread-demand-completion",
                },
            }],
        )
        attempt_id = demand_sys.begin_ingress_resolution(
            actor_target,
            source_key,
        )["attempt_id"]
        created = demand_sys.resolve_ingress(
            actor_target,
            source_key,
            attempt_id,
            self._proposal(
                "create",
                description=f"Deliver {label}.",
                detail=f"Provide durable delivery evidence for {label}.",
            ),
            handled_verified=False,
        )
        return demand_sys.get(actor_target, created["demand_id"])

    def _task_for(
        self,
        *,
        actor_target: dict[str, str],
        demand: dict[str, Any],
        status: str,
        label: str,
    ) -> dict[str, Any]:
        created = task_fixtures.create_task(
            actor_target=actor_target,
            demand_ref=demand_sys.resolve_demand_ref(
                actor_target=actor_target,
                demand_ref=demand["demand_ref"],
            ),
            objective=f"Deliver the observable result for {label}.",
            selection_reason=f"{label} is the selected live Demand.",
        )
        task_id = str(created["task_id"])
        if status == task_fixtures.CANCELED:
            task_fixtures.record_task_cancel(task_id, "Fixture canceled.")
        elif status == task_fixtures.COMPLETED:
            goal = {
                "threadId": f"thr-goal-{label}",
                "objective": created["task"]["objective"],
                "status": "complete",
                "tokenBudget": None,
                "tokensUsed": 10,
                "timeUsedSeconds": 2,
                "createdAt": 100,
                "updatedAt": 120,
            }
            task_fixtures.bind_goal(task_id, goal)
            task_fixtures.record_goal_complete(task_id, goal)
        return task_fixtures.get_task_record(task_id)

    @staticmethod
    def _completion_evidence(task_id: str) -> list[dict[str, Any]]:
        return [
            {"type": "task_sys.task", "ref": {"task_id": task_id}},
            {"type": "artifact", "ref": {"id": f"art-{task_id}"}},
        ]

    def _claim_side(
        self,
        *,
        instance_json: Path,
        actor_target: dict[str, str],
        source_key: str,
        description: str,
        detail: str,
        side_thread_id: str,
        source_refs: list[dict[str, Any]] | None = None,
    ) -> str:
        demand_sys.claim_ingress(
            actor_target,
            source_key,
            description,
            detail,
            source_refs
            or [{
                "type": "track.comment.added",
                "ref": {
                    "track_id": "track-demand-wire",
                    "comment_id": source_key.rsplit(":", 1)[-1],
                    "thread_id": "comment-thread-demand-wire",
                },
            }],
        )
        started = demand_sys.begin_ingress_resolution(
            actor_target,
            source_key,
        )
        token, token_hash = demand_triage_runtime.mint_capability()
        side_thread_registry.register_side_thread(
            instance_json,
            actor_id=actor_target["actor_id"],
            parent_thread_id="thr-main",
            side_thread_id=side_thread_id,
            purpose=demand_triage_runtime.PURPOSE,
            turn_id=f"turn-{side_thread_id}",
            turn_kind="work",
            capability_hash=token_hash,
            binding={
                "source_key": source_key,
                "attempt_id": started["attempt_id"],
            },
        )
        return token

    def _resolve(
        self,
        *,
        instance_json: Path,
        actor_label: str,
        token: str | None,
        side_thread_id: str,
        proposal: dict[str, Any],
        role: str = "dev",
    ) -> dict[str, object]:
        invocation = {
            "thread_id": side_thread_id,
            "turn_id": f"turn-{side_thread_id}",
            "request_id": f"req-{side_thread_id}",
        }
        if token is not None:
            invocation["bound_capability"] = token
        return self._dispatch(
            instance_json=instance_json,
            actor_id=actor_label,
            role=role,
            tool="demand_sys",
            action="resolve_inbound",
            args=proposal,
            invocation=invocation,
        )

    def test_resolve_inbound_create_agrees_across_wire_state_and_reads(self) -> None:
        actor_label = "act-dev-demand-wire-create"
        instance_json, actor_id, actor_target = self._prepare_instance(
            actor_label=actor_label,
        )
        source_key = "track.comment.added:create-wire"
        token = self._claim_side(
            instance_json=instance_json,
            actor_target=actor_target,
            source_key=source_key,
            description="Ship a calendar.",
            detail="Provide a runnable calendar and verification.",
            side_thread_id="thr-side-create",
        )
        task_before = self._task_snapshot()

        result = self._resolve(
            instance_json=instance_json,
            actor_label=actor_label,
            token=token,
            side_thread_id="thr-side-create",
            proposal=self._proposal(
                "create",
                description="Ship a calendar.",
                detail="Provide a runnable calendar and verification.",
            ),
        )

        self._assert_write_success_contract(result)
        self.assertEqual(result["action"], "demand_sys.resolve_inbound")
        self.assertEqual(result["decision"], "create")
        self.assertTrue(result["demand_changed"])
        self.assertEqual(self._task_snapshot(), task_before)
        stored = demands.load_actor_state(actor_target)
        self.assertEqual(stored["demand_pool_revision"], 1)
        self.assertEqual(len(stored["demands"]), 1)
        self.assertEqual(stored["ingress_receipts"][source_key]["state"], "settled")
        lease = json.loads(instance_json.read_text(encoding="utf-8"))["side_threads"][0]
        self.assertEqual(lease["capability_state"], "consumed")

        listed = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_label,
            role="dev",
            tool="demand_sys",
            action="list",
            args={},
        )
        self._assert_success_contract(listed)
        self.assertEqual(len(listed["demands"]), 1)
        opened = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_label,
            role="dev",
            tool="demand_sys",
            action="get",
            args={"demand_id": result["demand_id"]},
        )
        self._assert_success_contract(opened)
        self.assertEqual(opened["demand"]["description"], "Ship a calendar.")
        self.assertNotIn("bound_capability", json.dumps(result))

    def test_resolve_inbound_handled_reports_one_verified_durable_reply(self) -> None:
        actor_label = "act-dev-demand-wire-handled"
        instance_json, actor_id, actor_target = self._prepare_instance(
            actor_label=actor_label,
        )
        inbound = message_service.send_im_message(
            sender_identity={"id": "ext-demand-wire", "type": "external"},
            target_identity={"id": actor_id, "type": "actor"},
            content="Is the calendar work on track?",
        )
        self.assertTrue(inbound["ok"], inbound)
        source_key = "im.message.created:" + inbound["message"]["id"]
        token = self._claim_side(
            instance_json=instance_json,
            actor_target=actor_target,
            source_key=source_key,
            description="Respond to an inbound status question.",
            detail="Resolve it without creating a new unmet need.",
            side_thread_id="thr-side-handled",
            source_refs=[{
                "type": "im.message.created",
                "ref": {
                    "message_id": inbound["message"]["id"],
                    "conversation_id": inbound["message"]["conversation_id"],
                    "event_id": inbound["event_id"],
                },
            }],
        )
        proposal = self._proposal(
            "handled",
            reply_content="The calendar work is on track.",
        )

        result = self._resolve(
            instance_json=instance_json,
            actor_label=actor_label,
            token=token,
            side_thread_id="thr-side-handled",
            proposal=proposal,
        )

        self._assert_write_success_contract(result)
        self.assertEqual(result["decision"], "handled")
        self.assertIsInstance(result["handled_message_id"], str)
        replies = message_service.list_im_replies(
            identity={"id": actor_id, "type": "actor"},
            message_id=inbound["message"]["id"],
        )
        self.assertTrue(replies["ok"], replies)
        self.assertEqual(replies["count"], 1)
        self.assertEqual(
            replies["replies"][0]["id"],
            result["handled_message_id"],
        )
        self.assertEqual(
            demands.load_actor_state(actor_target)["ingress_receipts"][
                source_key
            ]["state"],
            "settled",
        )

        replay = self._resolve(
            instance_json=instance_json,
            actor_label=actor_label,
            token=token,
            side_thread_id="thr-side-handled",
            proposal=proposal,
        )
        self._assert_rejection_contract(replay)
        self.assertEqual(
            replay["error"]["code"],
            "E_DEMAND_TRIAGE_CAPABILITY_CONSUMED",
        )
        self.assertEqual(
            message_service.list_im_replies(
                identity={"id": actor_id, "type": "actor"},
                message_id=inbound["message"]["id"],
            )["count"],
            1,
        )

    def test_resolve_inbound_authority_failures_have_no_partial_effect(self) -> None:
        cases = (
            ("missing", None, "thr-side-authority"),
            ("wrong-token", "wrong-token", "thr-side-authority"),
            ("wrong-thread", "bound-token", "thr-forged"),
            ("parent-thread", "bound-token", "thr-main"),
        )
        for label, supplied, actual_thread in cases:
            with self.subTest(case=label):
                actor_label = f"act-dev-demand-{label}"
                instance_json, _actor_id, actor_target = self._prepare_instance(
                    actor_label=actor_label,
                )
                source_key = f"track.comment.added:{label}"
                real_token = self._claim_side(
                    instance_json=instance_json,
                    actor_target=actor_target,
                    source_key=source_key,
                    description="Do not commit this Demand.",
                    detail="Authority rejection must leave state unchanged.",
                    side_thread_id="thr-side-authority",
                )
                token = real_token if supplied == "bound-token" else supplied
                before = demands.load_actor_state(actor_target)

                result = self._resolve(
                    instance_json=instance_json,
                    actor_label=actor_label,
                    token=token,
                    side_thread_id=actual_thread,
                    proposal=self._proposal(
                        "create",
                        description="Forbidden Demand.",
                        detail="Must not persist.",
                    ),
                )

                self._assert_rejection_contract(result)
                self.assertIn(
                    result["error"]["code"],
                    {
                        "E_DEMAND_TRIAGE_CAPABILITY",
                        "E_DEMAND_TRIAGE_AUTHORITY",
                    },
                )
                self.assertEqual(demands.load_actor_state(actor_target), before)

    def test_complete_rejects_invalid_task_or_delivery_evidence_without_effect(
        self,
    ) -> None:
        cases = (
            "no-task-evidence",
            "missing-task",
            "other-actor-task",
            "active-task",
            "canceled-task",
            "other-demand-task",
            "missing-delivery-evidence",
        )
        for label in cases:
            with self.subTest(case=label):
                actor_label = f"act-dev-completion-{label}"
                instance_json, actor_id, actor_target = self._prepare_instance(
                    actor_label=actor_label,
                )
                demand = self._create_domain_demand(
                    actor_target=actor_target,
                    label=f"target-{label}",
                )
                evidence: list[dict[str, Any]]
                if label == "no-task-evidence":
                    evidence = [
                        {"type": "artifact", "ref": {"id": "art-only"}}
                    ]
                elif label == "missing-task":
                    evidence = self._completion_evidence(
                        "task-demand-missing"
                    )
                elif label == "other-actor-task":
                    other_target = {
                        "actor_id": self._runtime_actor_id(
                            role="dev",
                            label=f"other-{label}",
                        ),
                        "role_id": "dev",
                    }
                    other_demand = self._create_domain_demand(
                        actor_target=other_target,
                        label=f"other-{label}",
                    )
                    task = self._task_for(
                        actor_target=other_target,
                        demand=other_demand,
                        status=task_fixtures.COMPLETED,
                        label=label,
                    )
                    evidence = self._completion_evidence(task["id"])
                elif label == "other-demand-task":
                    other_demand = self._create_domain_demand(
                        actor_target=actor_target,
                        label=f"other-{label}",
                    )
                    task = self._task_for(
                        actor_target=actor_target,
                        demand=other_demand,
                        status=task_fixtures.COMPLETED,
                        label=label,
                    )
                    evidence = self._completion_evidence(task["id"])
                else:
                    status = (
                        task_fixtures.ACTIVE
                        if label == "active-task"
                        else task_fixtures.CANCELED
                        if label == "canceled-task"
                        else task_fixtures.COMPLETED
                    )
                    task = self._task_for(
                        actor_target=actor_target,
                        demand=demand,
                        status=status,
                        label=label,
                    )
                    evidence = (
                        [{
                            "type": "task_sys.task",
                            "ref": {"task_id": task["id"]},
                        }]
                        if label == "missing-delivery-evidence"
                        else self._completion_evidence(task["id"])
                    )
                demand_before = demands.load_actor_state(actor_target)
                tasks_before = self._task_snapshot()

                result = self._dispatch(
                    instance_json=instance_json,
                    actor_id=actor_label,
                    role="dev",
                    tool="demand_sys",
                    action="complete",
                    args={
                        "demand_ref": demand["demand_ref"],
                        "summary": "The observable result is delivered.",
                        "evidence_refs": evidence,
                    },
                )

                self._assert_rejection_contract(result)
                self.assertIn(
                    result["error"]["code"],
                    {
                        "E_DEMAND_COMPLETION_EVIDENCE",
                        "E_DEMAND_COMPLETION_TASK",
                    },
                )
                self.assertEqual(
                    demands.load_actor_state(actor_target),
                    demand_before,
                )
                self.assertEqual(self._task_snapshot(), tasks_before)

    def test_complete_accepts_completed_same_demand_task_and_delivery_evidence(
        self,
    ) -> None:
        actor_label = "act-dev-completion-valid"
        instance_json, _actor_id, actor_target = self._prepare_instance(
            actor_label=actor_label,
        )
        demand = self._create_domain_demand(
            actor_target=actor_target,
            label="completion-valid",
        )
        task = self._task_for(
            actor_target=actor_target,
            demand=demand,
            status=task_fixtures.COMPLETED,
            label="completion-valid",
        )
        task_before = self._task_snapshot()

        result = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_label,
            role="dev",
            tool="demand_sys",
            action="complete",
            args={
                "demand_ref": demand["demand_ref"],
                "summary": "The observable result is delivered.",
                "evidence_refs": self._completion_evidence(task["id"]),
            },
        )

        self._assert_write_success_contract(result)
        self.assertEqual(
            demand_sys.get(actor_target, demand["id"])["terminal"]["type"],
            "completed",
        )
        self.assertEqual(self._task_snapshot(), task_before)

    def test_complete_rejects_stale_demand_ref_after_task_completion(
        self,
    ) -> None:
        actor_label = "act-dev-completion-stale"
        instance_json, _actor_id, actor_target = self._prepare_instance(
            actor_label=actor_label,
        )
        demand = self._create_domain_demand(
            actor_target=actor_target,
            label="completion-stale-target",
        )
        task = self._task_for(
            actor_target=actor_target,
            demand=demand,
            status=task_fixtures.COMPLETED,
            label="completion-stale",
        )
        source_key = "track.comment.added:completion-stale-revise"
        demand_sys.claim_ingress(
            actor_target,
            source_key,
            "Refine the target.",
            "The current satisfaction contract changed.",
            [{
                "type": "track.comment.added",
                "ref": {
                    "track_id": "track-demand-completion",
                    "comment_id": "completion-stale-revise",
                    "thread_id": "comment-thread-demand-completion",
                },
            }],
        )
        attempt_id = demand_sys.begin_ingress_resolution(
            actor_target,
            source_key,
        )["attempt_id"]
        demand_sys.resolve_ingress(
            actor_target,
            source_key,
            attempt_id,
            self._proposal(
                "revise",
                demand_ref=demand["demand_ref"],
                description="Deliver the refined target.",
                detail="The current satisfaction contract changed.",
            ),
            handled_verified=False,
        )
        demand_before = demands.load_actor_state(actor_target)
        tasks_before = self._task_snapshot()

        result = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_label,
            role="dev",
            tool="demand_sys",
            action="complete",
            args={
                "demand_ref": demand["demand_ref"],
                "summary": "The stale result is delivered.",
                "evidence_refs": self._completion_evidence(task["id"]),
            },
        )

        self._assert_rejection_contract(result)
        self.assertEqual(
            result["error"]["code"],
            "E_DEMAND_REVISION_CONFLICT",
        )
        self.assertEqual(demands.load_actor_state(actor_target), demand_before)
        self.assertEqual(self._task_snapshot(), tasks_before)

    def test_resolve_inbound_stale_target_returns_receipt_to_pending_only(self) -> None:
        actor_label = "act-dev-demand-stale-wire"
        instance_json, _actor_id, actor_target = self._prepare_instance(
            actor_label=actor_label,
        )
        create_token = self._claim_side(
            instance_json=instance_json,
            actor_target=actor_target,
            source_key="track.comment.added:stale-create",
            description="Ship initial calendar.",
            detail="Initial satisfaction contract.",
            side_thread_id="thr-side-stale-create",
        )
        created = self._resolve(
            instance_json=instance_json,
            actor_label=actor_label,
            token=create_token,
            side_thread_id="thr-side-stale-create",
            proposal=self._proposal(
                "create",
                description="Ship initial calendar.",
                detail="Initial satisfaction contract.",
            ),
        )
        stale_ref = str(created["demand_ref"])
        stale_token = self._claim_side(
            instance_json=instance_json,
            actor_target=actor_target,
            source_key="track.comment.added:stale-supplement",
            description="Add persistence.",
            detail="Refresh must retain calendar entries.",
            side_thread_id="thr-side-stale-target",
        )
        concurrent_token = self._claim_side(
            instance_json=instance_json,
            actor_target=actor_target,
            source_key="track.comment.added:stale-concurrent",
            description="Add keyboard shortcuts.",
            detail="Keyboard operation must work across the calendar.",
            side_thread_id="thr-side-stale-concurrent",
        )
        concurrent = self._resolve(
            instance_json=instance_json,
            actor_label=actor_label,
            token=concurrent_token,
            side_thread_id="thr-side-stale-concurrent",
            proposal=self._proposal(
                "revise",
                demand_ref=stale_ref,
                description="Ship initial calendar with keyboard shortcuts.",
                detail="Initial contract plus keyboard shortcuts.",
            ),
        )
        self._assert_write_success_contract(concurrent)
        before = demands.load_actor_state(actor_target)

        result = self._resolve(
            instance_json=instance_json,
            actor_label=actor_label,
            token=stale_token,
            side_thread_id="thr-side-stale-target",
            proposal=self._proposal(
                "merge_intake",
                demand_ref=stale_ref,
                description="Ship calendar with persistence.",
                detail="Refresh must retain calendar entries.",
            ),
        )

        self._assert_write_success_contract(result)
        self.assertTrue(result["retry_required"])
        self.assertEqual(result["reason"], "stale_demand_ref")
        after = demands.load_actor_state(actor_target)
        self.assertEqual(after["demands"], before["demands"])
        self.assertEqual(
            after["demand_pool_revision"],
            before["demand_pool_revision"],
        )
        self.assertEqual(
            after["ingress_receipts"]["track.comment.added:stale-supplement"]["state"],
            "pending",
        )

    def test_resolve_inbound_rejects_model_authored_host_fields(self) -> None:
        actor_label = "act-dev-demand-host-fields"
        instance_json, _actor_id, actor_target = self._prepare_instance(
            actor_label=actor_label,
        )
        token = self._claim_side(
            instance_json=instance_json,
            actor_target=actor_target,
            source_key="track.comment.added:host-fields",
            description="Reject forged authority.",
            detail="Only host invocation metadata carries authority.",
            side_thread_id="thr-side-host-fields",
        )
        before = demands.load_actor_state(actor_target)
        proposal = self._proposal("no_action_needed")
        proposal["capability"] = token
        proposal["thread_id"] = "thr-side-host-fields"

        result = self._resolve(
            instance_json=instance_json,
            actor_label=actor_label,
            token=token,
            side_thread_id="thr-side-host-fields",
            proposal=proposal,
        )

        self._assert_rejection_contract(result)
        self.assertEqual(result["error"]["code"], "E_DEMAND_PAYLOAD")
        self.assertEqual(demands.load_actor_state(actor_target), before)
