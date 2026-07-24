"""Demand product handler for isolated inbound triage."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Mapping


HELPER_DIR = Path(__file__).resolve().parent
ROOT = HELPER_DIR.parents[1]
SCRIPTS = ROOT / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import actor_side_thread  # noqa: E402
import app_server  # noqa: E402
import daemon_contracts  # noqa: E402
import demand_sys_daemon_adapter  # noqa: E402
import demand_triage_mcp_server  # noqa: E402
import demand_triage_runtime  # noqa: E402
import side_thread_registry  # noqa: E402
from env.domain import demand_sys  # noqa: E402
from env.repos import runtime_files  # noqa: E402
from runtime_kernel import lifecycle as runtime_broker_lifecycle  # noqa: E402


RETRY_SECONDS = 5

TRIAGE_PROMPT = """[DEMAND TRIAGE — isolated side]

Use $demand-triage to resolve this one inbound fact against the Actor's current
canonical live Demands. Commit one final resolution through
`demand_triage.resolve` before ending this turn.

Inbound fact:
{fact}
"""

TRIAGE_ENV_TOOLS = [
    "demand_sys__list",
    "demand_sys__get",
    "message__get",
    "message__conversation",
]


def _actor_target(context: Any) -> dict[str, str]:
    return {
        "actor_id": runtime_files.require_id(
            getattr(context, "actor_id", ""),
            "context.actor_id",
        ),
        "role_id": runtime_files.require_id(
            getattr(context, "role", ""),
            "context.role",
        ),
    }


def _trigger_payload(trigger: Any) -> dict[str, Any]:
    payload = getattr(trigger, "payload", None)
    if not isinstance(payload, Mapping):
        raise ValueError("Demand ingress trigger payload must be an object")
    source_key = payload.get("source_key")
    if not isinstance(source_key, str) or not source_key.strip():
        raise ValueError("Demand ingress trigger source_key is required")
    result: dict[str, Any] = {"source_key": source_key.strip()}
    present = {
        key
        for key in ("description", "detail", "source_refs")
        if key in payload
    }
    if present and present != {"description", "detail", "source_refs"}:
        raise ValueError(
            "Demand ingress fact requires description, detail, and source_refs"
        )
    for key in present:
        result[key] = payload[key]
    return result


def _claim_or_get(
    actor_target: Mapping[str, Any],
    trigger: Any,
) -> tuple[str, dict[str, Any]]:
    payload = _trigger_payload(trigger)
    source_key = payload["source_key"]
    if "description" in payload:
        demand_sys.claim_ingress(actor_target, **payload)
    return source_key, demand_sys.get_ingress_receipt(
        actor_target,
        source_key,
    )


def _schedule_retry(state: Any, source_key: str) -> None:
    state.upsert_schedule(
        delay_seconds=RETRY_SECONDS,
        trigger_type=demand_sys_daemon_adapter.DEMAND_INGRESS_TRIAGE_TRIGGER,
        payload={"source_key": source_key},
        source_context={"owner": "demand_sys", "reason": "triage_retry"},
        schedule_key=f"demand-ingress:{source_key}",
    )


def _runtime_broker_socket(context: Any) -> Path:
    instance_root = Path(
        getattr(
            context,
            "instance_root",
            Path(context.instance_json).parent,
        )
    )
    actor_id = runtime_files.require_id(
        getattr(context, "actor_id", ""),
        "context.actor_id",
    )
    return runtime_broker_lifecycle.resolve_socket_path(
        actor_id,
        instance_root,
        instance_root / "runtime" / "runtime-broker.socket",
    )


def _triage_thread_config(
    context: Any,
    capability: str,
) -> dict[str, Any]:
    return {
        "mcp_servers.buddyswitch-demand-triage": {
            "command": sys.executable,
            "args": [
                str(HELPER_DIR / "demand_triage_mcp_server.py"),
                "--broker-socket",
                str(_runtime_broker_socket(context)),
            ],
            "env": {
                demand_triage_mcp_server.CAPABILITY_ENV: capability,
            },
            "default_tools_approval_mode": "approve",
        },
        "mcp_servers.buddyswitch-env.enabled_tools": list(TRIAGE_ENV_TOOLS),
    }


def _side_status(payload: Mapping[str, Any]) -> str:
    thread = payload.get("thread")
    status = thread.get("status") if isinstance(thread, Mapping) else None
    if isinstance(status, Mapping):
        value = status.get("type")
        return value if isinstance(value, str) else ""
    return status if isinstance(status, str) else ""


class DemandTriageHandler:
    """Product owner for Demand ingress side work."""

    name = "demand_triage"

    def handles(self, trigger: Any) -> bool:
        return (
            getattr(trigger, "type", None)
            == demand_sys_daemon_adapter.DEMAND_INGRESS_TRIAGE_TRIGGER
        )

    def _start_triage(
        self,
        context: Any,
        state: Any,
        trigger: Any,
    ) -> daemon_contracts.HandlerResult:
        actor_target = _actor_target(context)
        source_key, receipt = _claim_or_get(actor_target, trigger)
        if receipt["state"] in {"settled", "failed"}:
            return daemon_contracts.HandlerResult.handled()
        self._launch_resolution(
            context,
            state,
            actor_target=actor_target,
            source_key=source_key,
        )
        return daemon_contracts.HandlerResult.handled()

    def _launch_resolution(
        self,
        context: Any,
        state: Any,
        *,
        actor_target: Mapping[str, Any],
        source_key: str,
    ) -> None:
        started = demand_sys.begin_ingress_resolution(
            actor_target,
            source_key,
        )
        receipt = demand_sys.get_ingress_receipt(actor_target, source_key)
        capability, capability_hash = demand_triage_runtime.mint_capability()
        try:
            actor_side_thread.start_actor_side_thread(
                socket_path=Path(context.socket_path),
                instance_json=Path(context.instance_json),
                actor_id=context.actor_id,
                parent_thread_id=context.main_thread_id,
                text=TRIAGE_PROMPT.format(
                    fact=json.dumps(
                        receipt["fact"],
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                ),
                purpose=demand_triage_runtime.PURPOSE,
                workspace_dir=Path(context.workspace_dir),
                shared_project_workspace_dir=Path(
                    context.project_workspace_dir
                ),
                permissions=context.permissions,
                config_overrides=_triage_thread_config(
                    context,
                    capability,
                ),
                capability_hash=capability_hash,
                binding={
                    "source_key": source_key,
                    "attempt_id": started["attempt_id"],
                },
            )
        except Exception as exc:
            demand_sys.fail_ingress_resolution(
                actor_target,
                source_key,
                started["attempt_id"],
                {
                    "code": "side_start_failed",
                    "message": str(exc),
                },
                retriable=True,
            )
            _schedule_retry(state, source_key)

    def _retry_resolution(
        self,
        context: Any,
        state: Any,
        *,
        actor_target: Mapping[str, Any],
        source_key: str,
        attempt_id: str,
        leases: list[Mapping[str, Any]],
        failure_code: str,
        failure_message: str,
    ) -> None:
        for row in leases:
            side_thread_id = row.get("thread_id")
            if isinstance(side_thread_id, str):
                side_thread_registry.unregister_side_thread(
                    Path(context.instance_json),
                    actor_id=context.actor_id,
                    parent_thread_id=context.main_thread_id,
                    side_thread_id=side_thread_id,
                )
        demand_sys.fail_ingress_resolution(
            actor_target,
            source_key,
            attempt_id,
            {
                "code": failure_code,
                "message": failure_message,
            },
            retriable=True,
        )
        self._launch_resolution(
            context,
            state,
            actor_target=actor_target,
            source_key=source_key,
        )

    def _reconcile_ingress(
        self,
        context: Any,
        state: Any,
        actor_target: Mapping[str, Any],
    ) -> bool:
        changed = False
        leases = side_thread_registry.find_side_threads_by_purpose(
            Path(context.instance_json),
            actor_id=context.actor_id,
            parent_thread_id=context.main_thread_id,
            purpose=demand_triage_runtime.PURPOSE,
        )
        for receipt in demand_sys.list_unsettled_ingress(actor_target):
            source_key = receipt["source_key"]
            if receipt["state"] == "pending":
                self._launch_resolution(
                    context,
                    state,
                    actor_target=actor_target,
                    source_key=source_key,
                )
                changed = True
                continue
            attempt_id = receipt["attempt_id"]
            matching = [
                row
                for row in leases
                if isinstance(row.get("binding"), Mapping)
                and row["binding"].get("source_key") == source_key
                and row["binding"].get("attempt_id") == attempt_id
            ]
            if len(matching) != 1:
                self._retry_resolution(
                    context,
                    state,
                    actor_target=actor_target,
                    source_key=source_key,
                    attempt_id=attempt_id,
                    leases=matching,
                    failure_code="side_lease_missing",
                    failure_message=(
                        "Demand triage resolving receipt has no exact open side lease"
                    ),
                )
                changed = True
                continue
            row = matching[0]
            try:
                thread = app_server.thread_read(
                    Path(context.socket_path),
                    str(row["thread_id"]),
                    include_turns=False,
                )
            except app_server.AppServerRequestError as exc:
                normalized_message = exc.message.lower()
                if (
                    exc.method != "thread/read"
                    or (
                        "thread not loaded" not in normalized_message
                        and "no rollout found for thread id"
                        not in normalized_message
                    )
                ):
                    continue
                self._retry_resolution(
                    context,
                    state,
                    actor_target=actor_target,
                    source_key=source_key,
                    attempt_id=attempt_id,
                    leases=matching,
                    failure_code="side_thread_unavailable",
                    failure_message=(
                        "Demand triage side is unavailable after runtime restart"
                    ),
                )
                changed = True
                continue
            except app_server.AppServerError:
                continue
            status = _side_status(thread)
            if status == "active":
                continue
            self._retry_resolution(
                context,
                state,
                actor_target=actor_target,
                source_key=source_key,
                attempt_id=attempt_id,
                leases=matching,
                failure_code=(
                    "side_system_error"
                    if status == "systemError"
                    else "side_ended_without_resolver"
                ),
                failure_message=(
                    f"Demand triage side ended in {status or 'unknown'} "
                    "before resolving ingress"
                ),
            )
            changed = True

        for row in leases:
            binding = row.get("binding")
            source_key = (
                binding.get("source_key")
                if isinstance(binding, Mapping)
                else None
            )
            try:
                receipt = (
                    demand_sys.get_ingress_receipt(actor_target, source_key)
                    if isinstance(source_key, str)
                    else None
                )
            except demand_sys.DemandError:
                receipt = None
            if (
                receipt is not None
                and receipt.get("state") in {"pending", "resolving"}
            ):
                continue
            side_thread_registry.unregister_side_thread(
                Path(context.instance_json),
                actor_id=context.actor_id,
                parent_thread_id=context.main_thread_id,
                side_thread_id=str(row["thread_id"]),
            )
            changed = True
        return changed

    def reconcile(
        self,
        context: Any,
        state: Any,
        runtime: Any,
    ) -> daemon_contracts.HandlerResult:
        del runtime
        actor_target = _actor_target(context)
        ingress_changed = self._reconcile_ingress(
            context,
            state,
            actor_target,
        )
        if ingress_changed:
            return daemon_contracts.HandlerResult.handled()
        return daemon_contracts.HandlerResult.ignored()

    def handle(
        self,
        context: Any,
        state: Any,
        runtime: Any,
        trigger: Any,
    ) -> daemon_contracts.HandlerResult:
        if not self.handles(trigger):
            return daemon_contracts.HandlerResult.ignored()
        try:
            return self._start_triage(context, state, trigger)
        except Exception as exc:
            return daemon_contracts.HandlerResult.failed(str(exc))
