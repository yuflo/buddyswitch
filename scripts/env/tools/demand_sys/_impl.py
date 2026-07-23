"""Thin six-intent adapter over the Demand Sys domain owner."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from env.tool_runtime import results as tool_results
from .tool import DEFINITION


_ACTION_ALLOWED_FIELDS = {
    action.name: set((action.input_schema.get("properties") or {}).keys())
    for action in DEFINITION.actions
}
_READ_ACTIONS = {"list", "get"}


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
        permission_boundary="demand_sys.actor_owned_aggregate",
        human_summary="Demand Sys rejected the requested intent.",
        why_blocked=message,
        impact="No Demand, Task, daemon, or inbound state was changed.",
        state_changed=False,
        retryable=True,
        retry_guidance=guidance,
        allowed_next_actions=[
            "Use demand_sys.list to inspect the canonical Demand pool.",
            "Use demand_sys.get before mutating one selected Demand.",
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
            "Use demand_sys.get to reread one selected Demand before mutation.",
            "Use create, revise, complete, or cancel only for the matching actor intent.",
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
    return tool_results.success(
        tool="demand_sys",
        action=f"demand_sys.{action}",
        current_identity=_current_identity(context),
        active_role=_active_role(context),
        effect_summary=f"Applied demand_sys.{action} to the actor's Demand aggregate.",
        state_changed=bool(receipt.get("state_changed")),
        durability="durable",
        state_changes=state_changes,
        created_ids=created_ids,
        updated_ids=updated_ids,
        allowed_next_actions=[
            "Use demand_sys.get to observe the exact current Demand.",
            "Allow demand-orchestration to select Task work from live Demands.",
        ],
        extra=public,
    )


def _handlers(
    domain: Any,
    target: dict[str, str],
    context: Any,
) -> dict[str, Callable[[dict[str, Any]], Any]]:
    invocation = _invocation(context)
    return {
        "list": lambda args: domain.list_demands(
            target, args.get("state") or "live"
        ),
        "get": lambda args: domain.get(target, args.get("demand_id")),
        "create": lambda args: domain.create(
            target,
            domain.actor_creation_key(
                target,
                thread_id=invocation.thread_id,
                turn_id=invocation.turn_id,
                description=args.get("description"),
                detail=args.get("detail"),
            ),
            args.get("description"),
            args.get("detail"),
            [{
                "type": "actor.self_requested",
                "ref": {
                    "thread_id": invocation.thread_id,
                    "turn_id": invocation.turn_id,
                },
            }],
        ),
        "revise": lambda args: domain.revise(
            target,
            args.get("demand_ref"),
            args.get("description"),
            args.get("detail"),
            args.get("reason"),
        ),
        "complete": lambda args: domain.complete(
            target,
            args.get("demand_ref"),
            args.get("summary"),
            args.get("evidence_refs"),
        ),
        "cancel": lambda args: domain.cancel(
            target,
            args.get("demand_ref"),
            args.get("summary"),
        ),
    }


def invoke(*, action: str, args: dict[str, Any], context: Any) -> dict[str, Any]:
    rejection = _reject_unknown_fields(action=action, args=args, context=context)
    if rejection is not None:
        return rejection
    domain = _domain(context)
    handler = _handlers(domain, _actor_target(context), context).get(action)
    if handler is None:
        raise ValueError(f"unsupported action: {action}")
    try:
        result = handler(args)
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
