"""Standard auth-denied feedback for env.tool pre-dispatch role auth."""

from __future__ import annotations

from typing import Any

from buddyswitch.env.tool_runtime import results as tool_results
from buddyswitch.env.tool_runtime import role_auth


def _semantic_action(*, tool: str, action: str | None) -> str:
    normalized = action.strip() if isinstance(action, str) and action.strip() else "unknown"
    return f"{tool}.{normalized}"


def role_auth_rejection(
    *,
    tool: str,
    action: str,
    current_identity: dict[str, Any],
    active_role: str,
    decision: role_auth.AuthDecision,
) -> dict[str, Any]:
    allowed_roles = list(decision.allowed_roles)
    allowed_roles_text = ", ".join(allowed_roles) if allowed_roles else "none"
    return tool_results.rejection(
        tool=tool,
        action=_semantic_action(tool=tool, action=action),
        current_identity=current_identity,
        active_role=active_role,
        code="E_TOOL_ROLE_AUTH",
        message="active role is not allowed to run this tool action",
        permission_boundary="tool.role_authority",
        human_summary="Active role is not allowed to run this tool action.",
        why_blocked=(
            f"Action {tool}.{action} is restricted by env.tool role-action policy. "
            f"Active role '{decision.active_role}' is not allowed; allowed roles: {allowed_roles_text}."
        ),
        impact="No env action ran and runtime state was unchanged.",
        state_changed=False,
        durability="none",
        retryable=False,
        retry_guidance="Use an action allowed for this role, or ask an allowed role to perform this action.",
        allowed_next_actions=[
            "Use context.summarize to inspect runtime policy preview for this role.",
            "Use context.get to inspect tool payload schema and runtime policy preview.",
        ],
        alternative_capabilities=[
            tool_results.alternative_capability(
                tool="context",
                action="summarize",
                condition="Inspect runtime policy preview before choosing another env.tool action.",
                mutates_product_state=False,
            ),
            tool_results.alternative_capability(
                tool="context",
                action="get",
                condition="Inspect tool payload schema and runtime policy preview before retrying.",
                mutates_product_state=False,
            ),
        ],
        extra={
            "category": "auth_denied",
            "auth_source": "env.tool role-action policy",
            "auth_stage": "pre_dispatch",
            "executed": False,
            "required_permission": decision.required_permission,
            "allowed_roles": allowed_roles,
        },
    )
