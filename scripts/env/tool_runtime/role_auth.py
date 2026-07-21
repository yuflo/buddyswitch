"""Central role-action authorization policy for env.tool dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

COMMON_ROLE_PERMISSIONS = frozenset(
    {
        "track.read",
        "track.create",
        "track.update_requirements",
        "track.update_status",
        "track.add_material",
        "track.add_update",
        "track.add_proof",
        "track.archive",
        "track.resolve_comment_thread",
        "task_sys.list",
        "task_sys.get",
        "task_sys.create",
        "task_sys.close",
        "task_sys.need_parent",
        "task_sys.cancel",
        "demand_sys.create",
        "demand_sys.revise",
        "demand_sys.list",
        "demand_sys.get",
        "demand_sys.get_many",
        "demand_sys.check",
        "demand_sys.complete_check",
        "demand_sys.absorb_into",
        "demand_sys.complete",
        "demand_sys.cancel",
        "artifact.read",
        "artifact.create",
        "artifact.update",
        "message.contacts",
        "message.send",
        "message.get",
        "message.mark",
        "message.list",
        "message.conversation",
        "track.add_comment",
        "track.list_comments",
        "evidence.issue",
        "evidence.approve",
    }
)

ROLE_PERMISSION_ADDITIONS: dict[str, frozenset[str]] = {}


@dataclass(frozen=True)
class AuthDecision:
    allowed: bool
    required_permission: str
    active_role: str
    allowed_roles: tuple[str, ...]
    reason: str


def manifest_role_ids(manifest: dict[str, Any]) -> frozenset[str]:
    roles: set[str] = set()
    for role in manifest.get("roles", []):
        if isinstance(role, dict) and isinstance(role.get("id"), str):
            roles.add(role["id"])
    return frozenset(roles)


def allowed_permissions_for_role(role: str, manifest: dict[str, Any]) -> frozenset[str]:
    roles = manifest_role_ids(manifest)
    if role not in roles:
        return frozenset()
    return frozenset({"none", *COMMON_ROLE_PERMISSIONS, *ROLE_PERMISSION_ADDITIONS.get(role, frozenset())})


def allowed_roles_for_permission(required_permission: str, manifest: dict[str, Any]) -> frozenset[str]:
    roles = manifest_role_ids(manifest)
    if required_permission == "none":
        return roles
    if required_permission in COMMON_ROLE_PERMISSIONS:
        return roles
    return frozenset(
        role
        for role, additions in ROLE_PERMISSION_ADDITIONS.items()
        if role in roles and required_permission in additions
    )


def _require_role_id(role_id: Any) -> str:
    if not isinstance(role_id, str) or not role_id.strip():
        raise TypeError("role_auth requires a non-empty role_id string")
    return role_id.strip()


def authorize(required_permission: str, role_id: str, manifest: dict[str, Any]) -> AuthDecision:
    active_role = _require_role_id(role_id)
    allowed_roles = tuple(sorted(allowed_roles_for_permission(required_permission, manifest)))
    roles = manifest_role_ids(manifest)
    if not allowed_roles:
        return AuthDecision(
            allowed=False,
            required_permission=required_permission,
            active_role=active_role,
            allowed_roles=(),
            reason=f"required permission '{required_permission}' is not covered by env.tool role action policy",
        )
    if active_role not in roles:
        return AuthDecision(
            allowed=False,
            required_permission=required_permission,
            active_role=active_role,
            allowed_roles=allowed_roles,
            reason=f"active role '{active_role}' is an unknown role for this manifest",
        )
    if active_role not in allowed_roles:
        return AuthDecision(
            allowed=False,
            required_permission=required_permission,
            active_role=active_role,
            allowed_roles=allowed_roles,
            reason=(
                f"active role '{active_role}' is not allowed to use required permission "
                f"'{required_permission}'"
            ),
        )
    return AuthDecision(
        allowed=True,
        required_permission=required_permission,
        active_role=active_role,
        allowed_roles=allowed_roles,
        reason="active role is allowed by env.tool role action policy",
    )


def role_action_summary(
    role_id: str,
    manifest: dict[str, Any],
    operation_semantics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    active_role = _require_role_id(role_id)
    available_actions: list[str] = []
    restricted_actions: list[str] = []
    restricted_action_details: dict[str, dict[str, Any]] = {}

    for action_id, semantics in sorted(operation_semantics.items()):
        required_permission = str(semantics.get("required_permission", ""))
        decision = authorize(required_permission, active_role, manifest)
        if decision.allowed:
            available_actions.append(action_id)
            continue
        restricted_actions.append(action_id)
        restricted_action_details[action_id] = {
            "required_permission": required_permission,
            "active_role": active_role,
            "restricted_to_roles": list(decision.allowed_roles),
            "reason": f"active role '{active_role}' is not allowed by env.tool role-action policy",
        }

    return {
        "active_role": active_role,
        "source": "env.tool role-action policy",
        "not_authorization_boundary": True,
        "not_execution_result": True,
        "available_actions": available_actions,
        "restricted_actions": restricted_actions,
        "restricted_action_details": restricted_action_details,
    }
