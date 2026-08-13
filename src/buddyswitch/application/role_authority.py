"""Application-owned Tool authority derived from Roles and Tool definitions."""

from __future__ import annotations

from dataclasses import dataclass

from buddyswitch.foundation.tool_runtime.definition import AuthorizationDecision


@dataclass(frozen=True)
class RoleAuthority:
    role_ids: frozenset[str]
    permissions: frozenset[str]

    def __post_init__(self) -> None:
        if not self.role_ids or not all(
            isinstance(role_id, str) and role_id.strip() == role_id
            for role_id in self.role_ids
        ):
            raise ValueError("Role authority requires normalized Role ids")
        if not self.permissions or not all(
            isinstance(permission, str) and permission.strip() == permission
            for permission in self.permissions
        ):
            raise ValueError("Role authority requires normalized permissions")

    def authorize(
        self,
        required_permission: str,
        role_id: str,
    ) -> AuthorizationDecision:
        if not isinstance(role_id, str) or not role_id.strip():
            raise TypeError("Role authority requires a non-empty role_id string")
        active_role = role_id.strip()
        allowed_roles = tuple(sorted(self.role_ids))
        if required_permission not in self.permissions:
            return AuthorizationDecision(
                allowed=False,
                required_permission=required_permission,
                active_role=active_role,
                allowed_roles=(),
                reason=(
                    f"required permission '{required_permission}' is not declared "
                    "by an active Tool registration"
                ),
            )
        if active_role not in self.role_ids:
            return AuthorizationDecision(
                allowed=False,
                required_permission=required_permission,
                active_role=active_role,
                allowed_roles=allowed_roles,
                reason=f"active role '{active_role}' is unknown to RoleHost",
            )
        return AuthorizationDecision(
            allowed=True,
            required_permission=required_permission,
            active_role=active_role,
            allowed_roles=allowed_roles,
            reason="active Role and Tool-declared permission are valid",
        )
