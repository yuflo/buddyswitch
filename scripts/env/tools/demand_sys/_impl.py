"""Thin actor-scoped adapter for the Demand Sys domain owner."""

from __future__ import annotations

from typing import Any, Callable

from env.tool_runtime import results as tool_results
from .tool import DEFINITION


_ACTION_ALLOWED_FIELDS = {
    row.name: {
        field
        for field in (row.input_schema.get("properties") or {})
        if isinstance(field, str)
    }
    for row in DEFINITION.actions
}
_READ_ACTIONS = {"list", "get", "get_many", "check"}


def _profile(context: Any) -> Any:
    profile = getattr(context, "current_actor_identity_profile", None)
    if profile is None:
        raise ValueError("current_actor_identity_profile is required")
    return profile


def _current_identity(context: Any) -> dict[str, str]:
    identity = getattr(_profile(context), "identity", None)
    actor_id = getattr(identity, "id", None)
    identity_type = getattr(identity, "type", None)
    if not isinstance(actor_id, str) or not actor_id.strip() or identity_type != "actor":
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
    rules = getattr(context, "rules", None)
    domain = getattr(rules, "demand_sys", None)
    if domain is None:
        raise RuntimeError("Demand Sys domain access is unavailable")
    return domain


def _rejection(
    *,
    action: str,
    context: Any,
    code: str,
    message: str,
    correctable_fields: list[str] | None = None,
) -> dict[str, Any]:
    if code == "E_DEMAND_REVISION_CONFLICT":
        retry_guidance = (
            "Use demand_sys.get or demand_sys.check to read the current revision, then retry "
            "with that current revision after re-evaluating the intended change."
        )
    elif code == "E_DEMAND_NOT_FOUND":
        retry_guidance = "Use demand_sys.check or demand_sys.list to select an actor-owned Demand id."
    else:
        retry_guidance = "Inspect the Demand response and retry with current actor-owned ids, revisions, and documented fields."
    return tool_results.rejection(
        tool="demand_sys",
        action=f"demand_sys.{action}",
        current_identity=_current_identity(context),
        active_role=_active_role(context),
        code=code,
        message=message,
        permission_boundary="demand_sys.actor_owned_aggregate",
        human_summary="Demand Sys rejected the requested action.",
        why_blocked=message,
        impact="No Demand, Task Sys, daemon, or inbound state was changed.",
        state_changed=False,
        retryable=True,
        retry_guidance=retry_guidance,
        allowed_next_actions=[
            "Use demand_sys.check to review unchecked revisions and the current live Demand index.",
            "Use demand_sys.get or demand_sys.get_many before retrying an exact-revision mutation.",
        ],
        correctable_fields=list(correctable_fields or []),
    )


def _reject_unknown_fields(
    *,
    action: str,
    args: dict[str, Any],
    context: Any,
) -> dict[str, Any] | None:
    allowed = _ACTION_ALLOWED_FIELDS.get(action, set())
    unknown = sorted(field for field in args if field not in allowed)
    if not unknown:
        return None
    return _rejection(
        action=action,
        context=context,
        code="E_DEMAND_PAYLOAD",
        message=f"unsupported payload fields: {', '.join(unknown)}",
        correctable_fields=unknown,
    )


def _read_success(
    *,
    action: str,
    context: Any,
    extra: dict[str, Any],
) -> dict[str, Any]:
    summaries = {
        "list": "Listed actor-owned Demands.",
        "get": "Read one actor-owned Demand.",
        "get_many": "Read selected actor-owned Demands.",
        "check": "Read unchecked Demand revisions and the live Demand index.",
    }
    return tool_results.success(
        tool="demand_sys",
        action=f"demand_sys.{action}",
        current_identity=_current_identity(context),
        active_role=_active_role(context),
        effect_summary=summaries[action],
        state_changed=False,
        durability="none",
        read_scope="active actor Demand aggregate",
        allowed_next_actions=[
            "Use demand_sys.get_many when the live index yields a small detailed-match candidate set.",
            "Use the exact Demand organization action that matches the actor's judgment.",
            "Use demand_sys.complete_check only after recording every intended Demand change.",
        ],
        extra=extra,
    )


def _write_success(
    *,
    action: str,
    context: Any,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    changes = receipt.get("changes")
    change_rows = [dict(row) for row in changes if isinstance(row, dict)] if isinstance(changes, list) else []
    acknowledged = receipt.get("acknowledged")
    acknowledged_rows = (
        [dict(row) for row in acknowledged if isinstance(row, dict)]
        if isinstance(acknowledged, list)
        else []
    )
    state_changes = [
        {
            "object": "demand_sys.demand",
            "id": row.get("demand_id"),
            "revision": row.get("revision"),
            "kind": row.get("kind"),
        }
        for row in change_rows
    ]
    if action == "complete_check" and receipt.get("state_changed") is True:
        state_changes = [
            {
                "object": "demand_sys.demand",
                "id": row.get("demand_id"),
                "revision": row.get("revision"),
                "kind": "checked",
            }
            for row in acknowledged_rows
        ]
    created_ids = [
        str(row["demand_id"])
        for row in change_rows
        if row.get("kind") == "created" and isinstance(row.get("demand_id"), str)
    ]
    updated_ids = [
        str(row["demand_id"])
        for row in change_rows
        if row.get("kind") != "created" and isinstance(row.get("demand_id"), str)
    ]
    if action == "complete_check":
        updated_ids = [
            str(row["demand_id"])
            for row in acknowledged_rows
            if isinstance(row.get("demand_id"), str)
        ]
    extra = dict(receipt)
    extra.pop("state_changed", None)
    return tool_results.success(
        tool="demand_sys",
        action=f"demand_sys.{action}",
        current_identity=_current_identity(context),
        active_role=_active_role(context),
        effect_summary=f"Applied demand_sys.{action} to the active actor Demand aggregate.",
        state_changed=bool(receipt.get("state_changed")),
        durability="durable",
        state_changes=state_changes,
        created_ids=created_ids,
        updated_ids=updated_ids,
        allowed_next_actions=[
            "Use demand_sys.check to inspect any Demand revision still requiring actor attention.",
            "Use demand_sys.get for the exact current record before a later revision-guarded mutation.",
        ],
        extra=extra,
    )


def _handlers(domain: Any, target: dict[str, str]) -> dict[str, Callable[[dict[str, Any]], Any]]:
    return {
        "create": lambda args: domain.create(
            target,
            args.get("intake_key"),
            args.get("description"),
            args.get("detail"),
            args.get("source_refs"),
        ),
        "revise": lambda args: domain.revise(
            target,
            args.get("demand_id"),
            args.get("expected_revision"),
            args.get("description"),
            args.get("detail"),
            args.get("source_refs"),
        ),
        "list": lambda args: domain.list_demands(target, args.get("state") or "live"),
        "get": lambda args: domain.get(target, args.get("demand_id")),
        "get_many": lambda args: domain.get_many(target, args.get("demand_ids")),
        "check": lambda _args: domain.check(target),
        "complete_check": lambda args: domain.complete_check(target, args.get("observed")),
        "set_parent": lambda args: domain.set_parent(
            target,
            args.get("demand_id"),
            args.get("expected_revision"),
            args.get("parent_id"),
        ),
        "add_dependency": lambda args: domain.add_dependency(
            target,
            args.get("demand_id"),
            args.get("expected_revision"),
            args.get("dependency_id"),
        ),
        "remove_dependency": lambda args: domain.remove_dependency(
            target,
            args.get("demand_id"),
            args.get("expected_revision"),
            args.get("dependency_id"),
        ),
        "split": lambda args: domain.split(
            target,
            args.get("demand_id"),
            args.get("expected_revision"),
            args.get("description"),
            args.get("detail"),
            args.get("children"),
        ),
        "absorb_into": lambda args: domain.absorb_into(
            target,
            args.get("source_id"),
            args.get("source_revision"),
            args.get("target_id"),
            args.get("target_revision"),
            args.get("merged_target"),
            args.get("summary"),
        ),
        "mark_duplicate": lambda args: domain.mark_duplicate(
            target,
            args.get("source_id"),
            args.get("source_revision"),
            args.get("target_id"),
            args.get("summary"),
        ),
        "supersede": lambda args: domain.supersede(
            target,
            args.get("old_id"),
            args.get("old_revision"),
            args.get("replacement_id"),
            args.get("summary"),
        ),
        "complete": lambda args: domain.complete(
            target,
            args.get("demand_id"),
            args.get("expected_revision"),
            args.get("summary"),
            args.get("evidence_refs"),
        ),
        "cancel": lambda args: domain.cancel(
            target,
            args.get("demand_id"),
            args.get("expected_revision"),
            args.get("summary"),
        ),
    }


def invoke(*, action: str, args: dict[str, Any], context: Any) -> dict[str, Any]:
    rejection = _reject_unknown_fields(action=action, args=args, context=context)
    if rejection is not None:
        return rejection
    domain = _domain(context)
    handler = _handlers(domain, _actor_target(context)).get(action)
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
    if action in _READ_ACTIONS:
        if action == "list":
            return _read_success(action=action, context=context, extra={"demands": result})
        if action == "get":
            return _read_success(action=action, context=context, extra={"demand": result})
        if action == "get_many":
            return _read_success(action=action, context=context, extra={"demands": result})
        return _read_success(action=action, context=context, extra=dict(result))
    return _write_success(action=action, context=context, receipt=dict(result))
