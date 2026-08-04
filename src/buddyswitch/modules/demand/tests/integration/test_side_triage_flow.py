"""Demand ingress resolution through one isolated, capability-bound side."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from buddyswitch.launcher import side_thread_registry
from buddyswitch.modules.communication import public as communication_public
from buddyswitch.launcher import daemon_state
from buddyswitch.modules.demand.private.adapters.daemon import (
    demand_sys_daemon_adapter,
    demand_triage_handler,
    demand_triage_runtime,
)
from buddyswitch.modules.demand.private.domain import demand_sys
from buddyswitch.modules.demand.private.state import demands
from tests.support.runtime import RuntimeWorkspaceTestCase


class _State:
    def __init__(self) -> None:
        self.schedules: list[dict[str, Any]] = []

    def upsert_schedule(self, **kwargs: Any) -> dict[str, Any]:
        self.schedules.append(dict(kwargs))
        return {"schedule_id": f"schedule-{len(self.schedules)}", **kwargs}


class _Runtime:
    def __init__(self, *, parent_status: str = "idle") -> None:
        self.parent_status = parent_status
        self.inputs: list[str] = []

    def parent_activity(self) -> dict[str, Any]:
        return {"status": self.parent_status, "active_turn_id": None}

    def input_actor(self, text: str) -> dict[str, str]:
        self.inputs.append(text)
        return {"action": "start", "turn_id": "turn-parent"}


class DemandSideTriageFlowTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.actor_id = self._runtime_actor_id(
            role="market",
            label="demand-side-triage",
        )
        self.actor_target = {
            "actor_id": self.actor_id,
            "role_id": "market",
        }
        self.instance_root = self._instance_root(self.actor_id)
        self.workspace_dir = self.instance_root / "workspace"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.instance_json = self.instance_root / "instance.json"
        self.instance_record = {
            "actor_id": self.actor_id,
            "role": "market",
            "status": "active",
            "thread_id": "thr-main",
            "instance_root": str(self.instance_root),
            "workspace_dir": str(self.workspace_dir),
            "side_threads": [],
        }
        self._write_instance(self.instance_record)

    def _write_instance(self, payload: dict[str, Any]) -> None:
        self.instance_json.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )

    def _read_instance(self) -> dict[str, Any]:
        return json.loads(self.instance_json.read_text(encoding="utf-8"))

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
            "reason": f"Reason for {decision}.",
            "demand_ref": demand_ref,
            "description": description,
            "detail": detail,
            "reply_content": reply_content,
        }

    def _track_fact(self, source_key: str = "track.comment.added:comment-1") -> dict[str, Any]:
        return {
            "source_key": source_key,
            "description": "Investigate AI market demand.",
            "detail": "Compare adoption and buyer priorities.",
            "source_refs": [{
                "type": "track.comment.added",
                "ref": {
                    "track_id": "track-triage",
                    "comment_id": "comment-triage",
                    "thread_id": "comment-thread-triage",
                },
            }],
        }

    def _claim_and_bind(
        self,
        *,
        fact: dict[str, Any] | None = None,
        purpose: str = "demand-triage",
        parent_thread_id: str = "thr-main",
        side_thread_id: str = "thr-side-1",
        binding_overrides: dict[str, str] | None = None,
    ) -> tuple[str, str]:
        current_fact = fact or self._track_fact()
        demand_sys.claim_ingress(self.actor_target, **current_fact)
        started = demand_sys.begin_ingress_resolution(
            self.actor_target,
            current_fact["source_key"],
        )
        token, token_hash = demand_triage_runtime.mint_capability()
        binding = {
            "source_key": current_fact["source_key"],
            "attempt_id": started["attempt_id"],
        }
        binding.update(binding_overrides or {})
        side_thread_registry.register_side_thread(
            self.instance_json,
            actor_id=self.actor_id,
            parent_thread_id=parent_thread_id,
            side_thread_id=side_thread_id,
            purpose=purpose,
            turn_id="turn-side-1",
            turn_kind="work",
            capability_hash=token_hash,
            binding=binding,
        )
        return token, started["attempt_id"]

    def _resolve(
        self,
        token: str,
        proposal: dict[str, Any],
        *,
        actual_thread_id: str = "thr-side-1",
    ) -> dict[str, Any]:
        return demand_triage_runtime.resolve_request(
            instance_json=self.instance_json,
            instance_record=self._read_instance(),
            capability=token,
            actual_thread_id=actual_thread_id,
            proposal=proposal,
        )

    def _daemon_state(self) -> daemon_state.DaemonState:
        state = daemon_state.DaemonState.load(
            instance_root=self.instance_root,
            actor_id=self.actor_id,
            main_thread_id="thr-main",
        )
        state.register_handlers(["demand_triage"])
        return state

    def test_handler_starts_resolver_side_without_output_schema(self) -> None:
        side_starts: list[dict[str, Any]] = []
        broker_socket = self.runtime_root / "short-runtime-broker.sock"
        broker_marker = self.instance_root / "runtime" / "runtime-broker.socket"
        broker_marker.parent.mkdir(parents=True, exist_ok=True)
        broker_marker.write_text(str(broker_socket), encoding="utf-8")

        def fake_start(**kwargs: Any) -> dict[str, Any]:
            side_starts.append(kwargs)
            return {
                "action": "start",
                "side_thread_id": "thr-side-1",
                "turn_id": "turn-side-1",
            }

        context = SimpleNamespace(
            actor_id=self.actor_id,
            role="market",
            instance_json=self.instance_json,
            instance_root=self.instance_root,
            main_thread_id="thr-main",
            socket_path=self.instance_root / "runtime" / "app-server.sock",
            workspace_dir=self.workspace_dir,
            project_workspace_dir=self.runtime_root,
            permissions="buddyswitch-runtime",
        )
        trigger = SimpleNamespace(
            type=demand_sys_daemon_adapter.DEMAND_INGRESS_TRIAGE_TRIGGER,
            payload=self._track_fact(),
            source_context={"schedule_id": "schedule-source"},
        )

        with patch.object(
            demand_triage_handler.actor_side_thread,
            "start_actor_side_thread",
            side_effect=fake_start,
        ):
            result = demand_triage_handler.DemandTriageHandler().handle(
                context,
                _State(),
                _Runtime(),
                trigger,
            )

        self.assertEqual(result.status, "handled", msg=result.message)
        self.assertEqual(len(side_starts), 1)
        start = side_starts[0]
        self.assertNotIn("output_schema", start)
        self.assertEqual(start["purpose"], "demand-triage")
        self.assertEqual(
            start["binding"]["source_key"],
            self._track_fact()["source_key"],
        )
        self.assertNotIn(
            "mcp_servers.buddyswitch-demand-triage",
            start["config_overrides"],
        )
        raw_token = start["config_overrides"][
            "mcp_servers.buddyswitch-env.env"
        ][demand_triage_handler.BOUND_CAPABILITY_ENV]
        self.assertEqual(
            start["capability_hash"],
            demand_triage_runtime.hash_capability(raw_token),
        )
        self.assertEqual(
            start["config_overrides"][
                "mcp_servers.buddyswitch-env.enabled_tools"
            ],
            [
                "demand_sys__list",
                "demand_sys__get",
                "message__get",
                "message__conversation",
                "demand_sys__resolve_inbound",
            ],
        )
        self.assertEqual(
            start["config_overrides"]["mcp_servers.buddyswitch-env.disabled_tools"],
            [],
        )
        self.assertEqual(
            start["config_overrides"]["skills.config"],
            [
                {"name": "demand-triage", "enabled": True},
                {"name": "demand-orchestration", "enabled": False},
            ],
        )
        receipt = demand_sys.get_ingress_receipt(
            self.actor_target,
            self._track_fact()["source_key"],
        )
        self.assertEqual(receipt["state"], "resolving")
        self.assertNotIn("outputSchema", start["text"])
        self.assertIn("demand_sys__resolve_inbound", start["text"])
        self.assertIn("Use $demand-triage", start["text"])
        self.assertNotIn("canonical live Demands", start["text"])
        self.assertNotIn("acceptance unit", start["text"])
        self.assertNotIn('state="all"', start["text"])
        self.assertIn("Investigate AI market demand", start["text"])
        for duplicated_policy in (
            "no_action_needed",
            "merge_intake",
            "all six schema fields",
            "ask the parent",
            "return a JSON proposal",
        ):
            self.assertNotIn(duplicated_policy, start["text"])

    def test_side_start_failure_returns_receipt_to_pending_and_schedules_retry(self) -> None:
        context = SimpleNamespace(
            actor_id=self.actor_id,
            role="market",
            instance_json=self.instance_json,
            instance_root=self.instance_root,
            main_thread_id="thr-main",
            socket_path=self.instance_root / "runtime" / "app-server.sock",
            workspace_dir=self.workspace_dir,
            project_workspace_dir=self.runtime_root,
            permissions="buddyswitch-runtime",
        )
        state = _State()
        trigger = SimpleNamespace(
            type=demand_sys_daemon_adapter.DEMAND_INGRESS_TRIAGE_TRIGGER,
            payload=self._track_fact(),
            source_context={"schedule_id": "schedule-source"},
        )

        with patch.object(
            demand_triage_handler.actor_side_thread,
            "start_actor_side_thread",
            side_effect=RuntimeError("App Server unavailable"),
        ):
            result = demand_triage_handler.DemandTriageHandler().handle(
                context,
                state,
                _Runtime(),
                trigger,
            )

        self.assertEqual(result.status, "handled", msg=result.message)
        receipt = demand_sys.get_ingress_receipt(
            self.actor_target,
            self._track_fact()["source_key"],
        )
        self.assertEqual(receipt["state"], "pending")
        self.assertIsNone(receipt["attempt_id"])
        self.assertEqual(receipt["last_failure"]["code"], "side_start_failed")
        self.assertEqual(
            state.schedules[-1]["payload"],
            {"source_key": self._track_fact()["source_key"]},
        )

    def test_valid_capability_settles_create_and_consumes_lease(self) -> None:
        token, _attempt = self._claim_and_bind()

        result = self._resolve(
            token,
            self._proposal(
                "create",
                description="Research AI buyer priorities.",
                detail="Compare adoption drivers by buyer segment.",
            ),
        )

        self.assertEqual(result["decision"], "create")
        self.assertTrue(result["demand_changed"])
        receipt = demand_sys.get_ingress_receipt(
            self.actor_target,
            self._track_fact()["source_key"],
        )
        self.assertEqual(receipt["state"], "settled")
        row = self._read_instance()["side_threads"][0]
        self.assertEqual(row["capability_state"], "consumed")
        self.assertEqual(len(demand_sys.list_demands(self.actor_target)), 1)

    def test_capability_binding_rejects_invalid_authority(self) -> None:
        cases = (
            ("unknown", {}, "E_DEMAND_TRIAGE_CAPABILITY"),
            ("purpose", {"purpose": "unrelated-side-purpose"}, "E_DEMAND_TRIAGE_AUTHORITY"),
            ("parent", {"parent_thread_id": "thr-other"}, "E_DEMAND_TRIAGE_AUTHORITY"),
            ("actor", {}, "E_DEMAND_TRIAGE_AUTHORITY"),
            ("side", {}, "E_DEMAND_TRIAGE_AUTHORITY"),
            ("actual-thread", {}, "E_DEMAND_TRIAGE_AUTHORITY"),
            (
                "source",
                {"binding_overrides": {"source_key": "track.comment.added:wrong"}},
                "E_DEMAND_TRIAGE_AUTHORITY",
            ),
            (
                "attempt",
                {"binding_overrides": {"attempt_id": "attempt-wrong"}},
                "E_DEMAND_TRIAGE_AUTHORITY",
            ),
        )
        for label, overrides, code in cases:
            with self.subTest(case=label):
                self._write_instance({**self.instance_record, "side_threads": []})
                token, _attempt = self._claim_and_bind(
                    fact=self._track_fact(
                        f"track.comment.added:comment-{label}"
                    ),
                    **overrides,
                )
                if label == "unknown":
                    token = "capability-unknown"
                elif label == "actor":
                    payload = self._read_instance()
                    payload["actor_id"] = "act-market-wrong-actor"
                    self._write_instance(payload)
                elif label == "side":
                    payload = self._read_instance()
                    payload["side_threads"][0]["thread_id"] = "thr-main"
                    self._write_instance(payload)
                before = demands.load_actor_state(self.actor_target)
                with self.assertRaises(demand_triage_runtime.DemandTriageRuntimeError) as raised:
                    self._resolve(
                        token,
                        self._proposal("no_action_needed"),
                        actual_thread_id=(
                            "thr-forged"
                            if label == "actual-thread"
                            else "thr-side-1"
                        ),
                    )
                self.assertEqual(raised.exception.code, code)
                self.assertEqual(
                    demands.load_actor_state(self.actor_target),
                    before,
                )

    def test_consumed_capability_cannot_be_reused(self) -> None:
        token, _attempt = self._claim_and_bind()
        proposal = self._proposal("no_action_needed")
        self._resolve(token, proposal)

        with self.assertRaises(demand_triage_runtime.DemandTriageRuntimeError) as raised:
            self._resolve(token, proposal)

        self.assertEqual(
            raised.exception.code,
            "E_DEMAND_TRIAGE_CAPABILITY_CONSUMED",
        )

    def _im_fact(self) -> tuple[dict[str, Any], dict[str, Any]]:
        external = {"id": "ext-triage-source", "type": "external"}
        actor = {"id": self.actor_id, "type": "actor"}
        inbound = communication_public.send_im_message(
            sender_identity=external,
            target_identity=actor,
            content="What is the status?",
        )
        self.assertTrue(inbound["ok"], inbound)
        fact = {
            "source_key": (
                "im.message.created:"
                + inbound["message"]["id"]
            ),
            "description": "Respond to an inbound status question.",
            "detail": "Decide whether a durable Demand is needed.",
            "source_refs": [{
                "type": "im.message.created",
                "ref": {
                    "message_id": inbound["message"]["id"],
                    "conversation_id": inbound["message"]["conversation_id"],
                    "event_id": inbound["event_id"],
                },
            }],
        }
        return fact, inbound

    def test_handled_sends_once_through_message_owner(self) -> None:
        fact, inbound = self._im_fact()
        token, _attempt = self._claim_and_bind(fact=fact)

        result = self._resolve(
            token,
            self._proposal(
                "handled",
                reply_content="The work is on track.",
            ),
        )

        self.assertEqual(result["decision"], "handled")
        replies = communication_public.list_im_replies(
            identity={"id": self.actor_id, "type": "actor"},
            message_id=inbound["message"]["id"],
        )
        self.assertTrue(replies["ok"], replies)
        self.assertEqual(replies["count"], 1)
        self.assertEqual(
            replies["replies"][0]["content"],
            "The work is on track.",
        )

    def test_invalid_handled_proposal_is_rejected_before_message_delivery(self) -> None:
        fact, inbound = self._im_fact()
        token, _attempt = self._claim_and_bind(fact=fact)
        invalid = {
            "decision": "handled",
            "reason": "",
            "demand_ref": None,
            "description": None,
            "detail": None,
            "reply_content": "This reply must never be sent.",
        }

        with self.assertRaises(demand_sys.DemandPayloadError):
            self._resolve(token, invalid)

        replies = communication_public.list_im_replies(
            identity={"id": self.actor_id, "type": "actor"},
            message_id=inbound["message"]["id"],
        )
        self.assertTrue(replies["ok"], replies)
        self.assertEqual(replies["count"], 0)
        receipt = demand_sys.get_ingress_receipt(
            self.actor_target,
            fact["source_key"],
        )
        self.assertEqual(receipt["state"], "resolving")
        self.assertEqual(
            self._read_instance()["side_threads"][0]["capability_state"],
            "open",
        )

    def test_retry_after_message_write_reuses_reply_without_duplicate(self) -> None:
        fact, inbound = self._im_fact()
        token, _attempt = self._claim_and_bind(fact=fact)
        proposal = self._proposal(
            "handled",
            reply_content="The work is on track.",
        )
        original_resolve = demand_triage_runtime.demand_sys.resolve_ingress
        calls = 0

        def fail_first(*args: Any, **kwargs: Any) -> dict[str, Any]:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("crash after Message write")
            return original_resolve(*args, **kwargs)

        with patch.object(
            demand_triage_runtime.demand_sys,
            "resolve_ingress",
            side_effect=fail_first,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "crash after Message write",
            ):
                self._resolve(token, proposal)
            result = self._resolve(token, proposal)

        self.assertEqual(result["decision"], "handled")
        replies = communication_public.list_im_replies(
            identity={"id": self.actor_id, "type": "actor"},
            message_id=inbound["message"]["id"],
        )
        self.assertEqual(replies["count"], 1)

    def test_owner_settled_before_capability_consume_is_idempotent(self) -> None:
        token, attempt = self._claim_and_bind()
        proposal = self._proposal("no_action_needed")
        direct = demand_sys.resolve_ingress(
            self.actor_target,
            self._track_fact()["source_key"],
            attempt,
            proposal,
            handled_verified=False,
        )
        aggregate_before = demands.load_actor_state(self.actor_target)

        result = self._resolve(token, proposal)

        self.assertEqual(result["decision"], direct["decision"])
        self.assertEqual(
            demands.load_actor_state(self.actor_target),
            aggregate_before,
        )
        self.assertEqual(
            self._read_instance()["side_threads"][0]["capability_state"],
            "consumed",
        )

    def test_reconcile_recovers_resolution_started_before_side_registration(self) -> None:
        fact = self._track_fact()
        demand_sys.claim_ingress(self.actor_target, **fact)
        original_attempt = demand_sys.begin_ingress_resolution(
            self.actor_target,
            fact["source_key"],
        )["attempt_id"]
        starts: list[dict[str, Any]] = []

        with patch.object(
            demand_triage_handler.actor_side_thread,
            "start_actor_side_thread",
            side_effect=lambda **kwargs: starts.append(kwargs) or {
                "side_thread_id": "thr-side-recovered",
                "turn_id": "turn-side-recovered",
            },
        ):
            result = demand_triage_handler.DemandTriageHandler().reconcile(
                SimpleNamespace(
                    actor_id=self.actor_id,
                    role="market",
                    instance_json=self.instance_json,
                    instance_root=self.instance_root,
                    main_thread_id="thr-main",
                    socket_path=self.instance_root / "runtime" / "app-server.sock",
                    workspace_dir=self.workspace_dir,
                    project_workspace_dir=self.runtime_root,
                    permissions="buddyswitch-runtime",
                ),
                self._daemon_state(),
                _Runtime(),
            )

        self.assertEqual(result.status, "handled", msg=result.message)
        self.assertEqual(len(starts), 1)
        self.assertNotEqual(
            starts[0]["binding"]["attempt_id"],
            original_attempt,
        )

    def test_reconcile_retries_idle_or_system_error_side_without_notification(self) -> None:
        for status in ("idle", "systemError"):
            with self.subTest(status=status):
                source_key = f"track.comment.added:{status}"
                token, original_attempt = self._claim_and_bind(
                    fact=self._track_fact(source_key)
                )
                del token
                starts: list[dict[str, Any]] = []
                with (
                    patch.object(
                        demand_triage_handler.app_server,
                        "thread_read",
                        return_value={
                            "thread": {
                                "id": "thr-side-1",
                                "status": {"type": status},
                            }
                        },
                    ),
                    patch.object(
                        demand_triage_handler.actor_side_thread,
                        "start_actor_side_thread",
                        side_effect=lambda **kwargs: starts.append(kwargs)
                        or {
                            "side_thread_id": "thr-side-retry",
                            "turn_id": "turn-side-retry",
                        },
                    ),
                ):
                    demand_triage_handler.DemandTriageHandler().reconcile(
                        SimpleNamespace(
                            actor_id=self.actor_id,
                            role="market",
                            instance_json=self.instance_json,
                            instance_root=self.instance_root,
                            main_thread_id="thr-main",
                            socket_path=self.instance_root / "runtime" / "app-server.sock",
                            workspace_dir=self.workspace_dir,
                            project_workspace_dir=self.runtime_root,
                            permissions="buddyswitch-runtime",
                        ),
                        self._daemon_state(),
                        _Runtime(),
                    )
                receipt = demand_sys.get_ingress_receipt(
                    self.actor_target,
                    source_key,
                )
                self.assertEqual(len(starts), 1)
                self.assertNotEqual(
                    receipt["attempt_id"],
                    original_attempt,
                )
                demand_sys.fail_ingress_resolution(
                    self.actor_target,
                    source_key,
                    receipt["attempt_id"],
                    {
                        "code": "test_cleanup",
                        "message": "Finish this subtest receipt.",
                    },
                    retriable=False,
                )
                self._write_instance({
                    **self.instance_record,
                    "side_threads": [],
                })

    def test_reconcile_retries_side_thread_missing_after_actor_restart(self) -> None:
        token, original_attempt = self._claim_and_bind()
        del token
        starts: list[dict[str, Any]] = []

        with (
            patch.object(
                demand_triage_handler.app_server,
                "thread_read",
                side_effect=demand_triage_handler.app_server.AppServerRequestError(
                    "thread/read",
                    -32600,
                    "thread not loaded",
                ),
            ),
            patch.object(
                demand_triage_handler.actor_side_thread,
                "start_actor_side_thread",
                side_effect=lambda **kwargs: starts.append(kwargs)
                or {
                    "side_thread_id": "thr-side-restarted",
                    "turn_id": "turn-side-restarted",
                },
            ),
        ):
            result = demand_triage_handler.DemandTriageHandler().reconcile(
                SimpleNamespace(
                    actor_id=self.actor_id,
                    role="market",
                    instance_json=self.instance_json,
                    instance_root=self.instance_root,
                    main_thread_id="thr-main",
                    socket_path=self.instance_root / "runtime" / "app-server.sock",
                    workspace_dir=self.workspace_dir,
                    project_workspace_dir=self.runtime_root,
                    permissions="buddyswitch-runtime",
                ),
                self._daemon_state(),
                _Runtime(),
            )

        receipt = demand_sys.get_ingress_receipt(
            self.actor_target,
            self._track_fact()["source_key"],
        )
        self.assertEqual(result.status, "handled", msg=result.message)
        self.assertEqual(len(starts), 1)
        self.assertNotEqual(receipt["attempt_id"], original_attempt)
        self.assertEqual(
            receipt["last_failure"]["code"],
            "side_thread_unavailable",
        )

    def test_reconcile_cleans_settled_side_without_parent_orchestration(self) -> None:
        token, _attempt = self._claim_and_bind()
        self._resolve(
            token,
            self._proposal(
                "create",
                description="Research AI market timing.",
                detail="Compare current adoption signals.",
            ),
        )
        runtime = _Runtime()
        state = self._daemon_state()
        handler = demand_triage_handler.DemandTriageHandler()
        context = SimpleNamespace(
            actor_id=self.actor_id,
            role="market",
            instance_json=self.instance_json,
            instance_root=self.instance_root,
            main_thread_id="thr-main",
            socket_path=self.instance_root / "runtime" / "app-server.sock",
            workspace_dir=self.workspace_dir,
            project_workspace_dir=self.runtime_root,
            permissions="buddyswitch-runtime",
        )

        first = handler.reconcile(context, state, runtime)
        second = handler.reconcile(context, state, runtime)

        self.assertEqual(first.status, "handled")
        self.assertEqual(second.status, "ignored")
        self.assertEqual(runtime.inputs, [])
        self.assertEqual(self._read_instance()["side_threads"], [])
        self.assertNotIn("checkpoint", state.handler_state("demand_triage"))

    def test_settled_inbound_demand_does_not_reenter_triage_parent_path(self) -> None:
        fact = self._track_fact("track.comment.added:queued")
        demand_sys.claim_ingress(
            self.actor_target,
            **fact,
        )
        attempt_id = demand_sys.begin_ingress_resolution(
            self.actor_target,
            fact["source_key"],
        )["attempt_id"]
        demand_sys.resolve_ingress(
            self.actor_target,
            fact["source_key"],
            attempt_id,
            self._proposal(
                "create",
                description="Research a queued AI market question.",
                detail="Wait behind the active Task.",
            ),
            handled_verified=False,
        )
        state = self._daemon_state()
        runtime = _Runtime()
        handler = demand_triage_handler.DemandTriageHandler()
        context = SimpleNamespace(
            actor_id=self.actor_id,
            role="market",
            instance_json=self.instance_json,
            instance_root=self.instance_root,
            main_thread_id="thr-main",
            socket_path=self.instance_root / "runtime" / "app-server.sock",
            workspace_dir=self.workspace_dir,
            project_workspace_dir=self.runtime_root,
            permissions="buddyswitch-runtime",
        )

        result = handler.reconcile(context, state, runtime)

        self.assertEqual(result.status, "ignored")
        self.assertEqual(runtime.inputs, [])
        self.assertNotIn("checkpoint", state.handler_state("demand_triage"))
