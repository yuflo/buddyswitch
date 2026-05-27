#!/usr/bin/env python3
"""Central role-action authorization policy for env.tool dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

COMMON_ROLE_PERMISSIONS = frozenset(
    {
        "track.read",
        "track.update_now",
        "track.add_material",
        "track.add_update",
        "track.add_proof",
        "task.read",
        "task.propose",
        "task.confirm",
        "artifact.read",
        "artifact.create",
        "artifact.update",
        "message.send",
        "message.list",
        "comment.add",
        "comment.list",
        "request.read",
        "request.create",
        "request.accept",
        "request.block",
        "request.complete",
        "request.cancel",
        "evidence.issue",
        "evidence.approve",
    }
)

ROLE_PERMISSION_ADDITIONS = {
    "pm": frozenset({"track.create", "track.archive", "comment.resolve"}),
}


@dataclass(frozen=True)
class AuthDecision:
    allowed: bool
    required_permission: str
    active_role: str
    allowed_roles: tuple[str, ...]
    reason: str


def manifest_role_ids(manifest: dict[str, Any]) -> frozenset[str]:
    roles: set[str] = set()
    for buddy in manifest.get("buddies", []):
        if isinstance(buddy, dict) and isinstance(buddy.get("id"), str):
            roles.add(buddy["id"])
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


def authorize(required_permission: str, active_role: str, manifest: dict[str, Any]) -> AuthDecision:
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
    active_role: str,
    manifest: dict[str, Any],
    operation_semantics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    allowed_actions: list[str] = []
    denied_actions: list[str] = []
    denied_action_details: dict[str, dict[str, Any]] = {}
    allowed_permissions: dict[str, str] = {}

    for action_id, semantics in sorted(operation_semantics.items()):
        required_permission = str(semantics.get("required_permission", ""))
        decision = authorize(required_permission, active_role, manifest)
        if decision.allowed:
            allowed_actions.append(action_id)
            allowed_permissions[action_id] = required_permission
            continue
        denied_actions.append(action_id)
        denied_action_details[action_id] = {
            "required_permission": required_permission,
            "active_role": active_role,
            "allowed_roles": list(decision.allowed_roles),
            "reason": decision.reason,
        }

    return {
        "active_role": active_role,
        "role_authority_source": "env.tool role action policy",
        "allowed_actions": allowed_actions,
        "denied_actions": denied_actions,
        "denied_action_details": denied_action_details,
        "allowed_action_permissions": allowed_permissions,
    }
