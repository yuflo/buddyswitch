"""Thin four-action adapter over the Demand Sys application boundary."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any, Callable

from env.tool_runtime.context import DemandIngressApplicationError
from env.tool_runtime import results as tool_results
from .tool import DEFINITION


_ACTION_ALLOWED_FIELDS = {
    action.name: set((action.input_schema.get("properties") or {}).keys())
    for action in DEFINITION.actions
}
def _profile(context: Any) -> Any:
    profile = getattr(context, "current_actor_identity_profile", None)
    if profile is None:
        raise ValueError("current_actor_identity_profile is required")
    return profile


def _current_identity(context: Any) -> dict[str, str]:
    identity = getattr(_profile(context), "identity", None)
    actor_id = getattr(identity, "id", None)
    if (
        not isinstance(actor_id, str)
        or not actor_id.strip()
        or getattr(identity, "type", None) != "actor"
    ):
        raise ValueError("current actor identity profile must contain an actor identity")
    return {"id": actor_id.strip(), "type": "actor"}


def _active_role(context: Any) -> str:
    role_id = getattr(_profile(context), "role_id", None)
    if not isinstance(role_id, str) or not role_id.strip():
        raise ValueError("current actor identity profile must contain role_id")
    return role_id.strip()


def _actor_target(context: Any) -> dict[str, str]:
    return {
        "actor_id": _current_identity(context)["id"],
        "role_id": _active_role(context),
    }


def _domain(context: Any) -> Any:
    domain = getattr(getattr(context, "rules", None), "demand_sys", None)
    if domain is None:
        raise RuntimeError("Demand Sys domain access is unavailable")
    return domain


def _task_domain(context: Any) -> Any:
    domain = getattr(getattr(context, "rules", None), "task_sys", None)
    if domain is None:
        raise RuntimeError("Task Sys domain access is unavailable")
    return domain


class _CompletionEvidenceError(ValueError):
    code = "E_DEMAND_COMPLETION_EVIDENCE"


def _demand_ingress_application(context: Any) -> Any:
    application = getattr(context, "demand_ingress_application", None)
    if application is None:
        raise RuntimeError("Demand ingress application access is unavailable")
    return application


def _invocation(context: Any) -> Any:
    invocation = getattr(context, "invocation", None)
    if invocation is None:
        raise ValueError("host invocation identity is required")
    return invocation


def _rejection(
    *,
    action: str,
    context: Any,
    code: str,
    message: str,
    retryable: bool = True,
    correctable_fields: list[str] | None = None,
) -> dict[str, Any]:
    if code == "E_DEMAND_REVISION_CONFLICT":
        guidance = (
            "Use demand_sys.get to reread the current Demand, re-evaluate the change, "
            "and retry with the refreshed demand_ref."
        )
    elif code == "E_DEMAND_NOT_FOUND":
        guidance = "Use demand_sys.list, then demand_sys.get for an actor-owned Demand."
    else:
        guidance = "Inspect the Demand response and retry with documented actor-level fields."
    return tool_results.rejection(
        tool="demand_sys",
        action=f"demand_sys.{action}",
        current_identity=_current_identity(context),
        active_role=_active_role(context),
        code=code,
        message=message,
        permission_boundary=(
            "demand_sys.bound_inbound_side_capability"
            if action == "resolve_inbound"
            else "demand_sys.actor_owned_aggregate"
        ),
        human_summary="Demand Sys rejected the requested intent.",
        why_blocked=message,
        impact="No Demand, Task, daemon, or inbound state was changed.",
        state_changed=False,
        retryable=retryable,
        retry_guidance=guidance,
        allowed_next_actions=[
            "Use demand_sys.list to inspect the canonical Demand pool.",
            "Use demand_sys.get before completing one selected Demand.",
        ],
        correctable_fields=list(correctable_fields or []),
    )


def _reject_unknown_fields(
    *, action: str, args: dict[str, Any], context: Any
) -> dict[str, Any] | None:
    unknown = sorted(set(args) - _ACTION_ALLOWED_FIELDS.get(action, set()))
    if not unknown:
        return None
    return _rejection(
        action=action,
        context=context,
        code="E_DEMAND_PAYLOAD",
        message=f"unsupported payload fields: {', '.join(unknown)}",
        correctable_fields=unknown,
    )


def _list_projection(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record["id"],
        "description": record["description"],
        "terminal": deepcopy(record["terminal"]),
        "updated_at": record["updated_at"],
    }


def _get_projection(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(record[key])
        for key in (
            "id",
            "description",
            "detail",
            "source_refs",
            "terminal",
            "created_at",
            "updated_at",
            "demand_ref",
        )
    }


def _read_success(
    *, action: str, context: Any, extra: dict[str, Any]
) -> dict[str, Any]:
    return tool_results.success(
        tool="demand_sys",
        action=f"demand_sys.{action}",
        current_identity=_current_identity(context),
        active_role=_active_role(context),
        effect_summary=(
            "Listed actor-owned Demands."
            if action == "list"
            else "Read one actor-owned Demand."
        ),
        state_changed=False,
        durability="none",
        read_scope="active actor Demand aggregate",
        allowed_next_actions=[
            "Use demand_sys.get to reread one selected Demand.",
            "Use demand_sys.complete only after its terminal Task evidence is verified.",
        ],
        extra=extra,
    )


def _write_success(
    *, action: str, context: Any, receipt: dict[str, Any]
) -> dict[str, Any]:
    changes = [
        dict(change)
        for change in receipt.get("changes", [])
        if isinstance(change, dict)
    ]
    state_changes = [
        {
            "object": "demand_sys.demand",
            "id": change.get("demand_id"),
            "kind": change.get("kind"),
        }
        for change in changes
    ]
    created_ids = [
        str(change["demand_id"])
        for change in changes
        if change.get("kind") == "created"
    ]
    updated_ids = [
        str(change["demand_id"])
        for change in changes
        if change.get("kind") != "created"
    ]
    public = {
        key: deepcopy(value)
        for key, value in receipt.items()
        if key not in {
            "state_changed",
            "changes",
            "demand_pool_revision",
        }
    }
    state_changed = bool(receipt.get("state_changed"))
    if action == "resolve_inbound":
        if bool(receipt.get("ingress_state_changed")):
            state_changes.append(
                {
                    "object": "demand_sys.ingress_receipt",
                    "id": receipt.get("source_key"),
                    "kind": (
                        "pending"
                        if receipt.get("retry_required") is True
                        else "settled"
                    ),
                }
            )
        if receipt.get("demand_changed") is True:
            demand_id = receipt.get("demand_id")
            decision = str(receipt.get("decision") or "updated")
            state_changes.append(
                {
                    "object": "demand_sys.demand",
                    "id": demand_id,
                    "kind": "created" if decision == "create" else decision,
                }
            )
            if decision == "create" and isinstance(demand_id, str):
                created_ids.append(demand_id)
            elif isinstance(demand_id, str):
                updated_ids.append(demand_id)
        if isinstance(receipt.get("handled_message_id"), str):
            state_changes.append(
                {
                    "object": "message.im",
                    "id": receipt["handled_message_id"],
                    "kind": "created",
                }
            )
        if receipt.get("lease_consumed") is True:
            state_changes.append(
                {
                    "object": "actor.side_thread_capability",
                    "id": getattr(_invocation(context), "thread_id", None),
                    "kind": "consumed",
                }
            )
    changed_effects = {
        "resolve_inbound": (
            "Committed the bound inbound resolution and consumed its one-shot side "
            "capability. Any Demand or Message effect is reported in state_changes. "
            "No Task or native Goal was changed."
        ),
        "complete": (
            "Terminalized the Demand as completed with the supplied summary and "
            "evidence references. No Task or native Goal was changed."
        ),
    }
    replay_effects = {
        "resolve_inbound": (
            "The bound inbound resolution was already durable; the one-shot side "
            "capability was consumed without duplicating a Demand or Message effect."
        ),
        "complete": (
            "The Demand was already completed with the same summary and evidence "
            "references; no new mutation occurred. No Task or native Goal was changed."
        ),
    }
    effect_summary = (
        changed_effects[action]
        if state_changed
        else replay_effects[action]
    )
    allowed_next_actions = (
        [
            "Use demand_sys.get to observe the exact current terminal Demand.",
            "Do not submit this terminal Demand for new Task selection.",
        ]
        if action == "complete"
        else [
            "Use demand_sys.list and demand_sys.get to observe the resulting Demand pool.",
            "Return control to the Parent after the bound inbound receipt is settled.",
        ]
    )
    return tool_results.success(
        tool="demand_sys",
        action=f"demand_sys.{action}",
        current_identity=_current_identity(context),
        active_role=_active_role(context),
        effect_summary=effect_summary,
        state_changed=state_changed,
        durability="durable",
        state_changes=state_changes,
        created_ids=created_ids,
        updated_ids=updated_ids,
        allowed_next_actions=allowed_next_actions,
        extra=public,
    )


def _completion_task_ids(evidence_refs: Any) -> list[str]:
    if not isinstance(evidence_refs, list):
        raise _CompletionEvidenceError(
            "Demand completion evidence_refs must be a list"
        )
    task_ids: list[str] = []
    has_delivery_evidence = False
    for row in evidence_refs:
        if not isinstance(row, Mapping):
            continue
        evidence_type = row.get("type")
        ref = row.get("ref")
        if evidence_type == "task_sys.task":
            task_id = ref.get("task_id") if isinstance(ref, Mapping) else None
            if not isinstance(task_id, str) or not task_id.strip():
                raise _CompletionEvidenceError(
                    "task_sys.task evidence requires ref.task_id"
                )
            task_ids.append(task_id.strip())
            continue
        if evidence_type == "artifact" and isinstance(ref, Mapping):
            artifact_id = ref.get("id")
            has_delivery_evidence = (
                isinstance(artifact_id, str) and bool(artifact_id.strip())
            ) or has_delivery_evidence
        elif evidence_type == "im.message.reply" and isinstance(ref, Mapping):
            message_id = ref.get("id")
            reply_key = ref.get("key")
            has_delivery_evidence = (
                isinstance(message_id, str)
                and bool(message_id.strip())
                and isinstance(reply_key, str)
                and bool(reply_key.strip())
            ) or has_delivery_evidence
    if not task_ids:
        raise _CompletionEvidenceError(
            "Demand completion requires completed Task evidence"
        )
    if not has_delivery_evidence:
        raise _CompletionEvidenceError(
            "Demand completion requires durable delivery evidence in addition "
            "to Task status"
        )
    return list(dict.fromkeys(task_ids))


def _complete(
    *,
    domain: Any,
    task_domain: Any,
    target: dict[str, str],
    args: dict[str, Any],
) -> dict[str, Any]:
    task_ids = _completion_task_ids(args.get("evidence_refs"))
    resolved = domain.resolve_demand_ref(
        actor_target=target,
        demand_ref=args.get("demand_ref"),
    )
    for task_id in task_ids:
        task_domain.require_completed_task_for_demand(
            task_id=task_id,
            actor_target=target,
            demand_id=resolved["demand_id"],
        )
    return domain.complete(
        target,
        args.get("demand_ref"),
        args.get("summary"),
        args.get("evidence_refs"),
    )


def _handlers(
    domain: Any,
    task_domain: Any,
    target: dict[str, str],
    context: Any,
) -> dict[str, Callable[[dict[str, Any]], Any]]:
    invocation = _invocation(context)
    return {
        "list": lambda args: domain.list_demands(
            target, args.get("state") or "live"
        ),
        "get": lambda args: domain.get(target, args.get("demand_id")),
        "resolve_inbound": lambda args: (
            _demand_ingress_application(context).resolve_inbound(
                proposal=args,
                capability=invocation.demand_inbound_capability,
                actual_thread_id=invocation.thread_id,
            )
        ),
        "complete": lambda args: _complete(
            domain=domain,
            task_domain=task_domain,
            target=target,
            args=args,
        ),
    }


def invoke(*, action: str, args: dict[str, Any], context: Any) -> dict[str, Any]:
    rejection = _reject_unknown_fields(action=action, args=args, context=context)
    if rejection is not None:
        return rejection
    domain = _domain(context)
    task_domain = _task_domain(context)
    handler = _handlers(
        domain,
        task_domain,
        _actor_target(context),
        context,
    ).get(action)
    if handler is None:
        raise ValueError(f"unsupported action: {action}")
    try:
        result = handler(args)
    except _CompletionEvidenceError as exc:
        return _rejection(
            action=action,
            context=context,
            code=exc.code,
            message=str(exc),
        )
    except DemandIngressApplicationError as exc:
        return _rejection(
            action=action,
            context=context,
            code=exc.code,
            message=exc.message,
            retryable=exc.retriable,
        )
    except task_domain.TaskCompletionEvidenceError as exc:
        return _rejection(
            action=action,
            context=context,
            code="E_DEMAND_COMPLETION_TASK",
            message=str(exc),
        )
    except domain.DemandError as exc:
        return _rejection(
            action=action,
            context=context,
            code=str(exc.code),
            message=str(exc),
        )
    if action == "list":
        return _read_success(
            action=action,
            context=context,
            extra={"demands": [_list_projection(row) for row in result]},
        )
    if action == "get":
        return _read_success(
            action=action,
            context=context,
            extra={"demand": _get_projection(result)},
        )
    return _write_success(
        action=action,
        context=context,
        receipt=dict(result),
    )
