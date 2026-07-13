"""Target-scoped evidence services for runless runtime."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, TypedDict

from .tool import DEFINITION
from env.tool_runtime import results as tool_results


_ACTION_DEFINITION_MAP = {
    'actions': [
        {
            'name': row.name,
            'payload_fields': [
                field
                for field in (row.input_schema.get('properties') or {})
                if isinstance(field, str)
            ],
        }
        for row in DEFINITION.actions
    ]
}

class EvidenceServiceContext(TypedDict):
    active_role: str
    current_identity: dict[str, Any]
    actor_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]
    manifest_path: Path | None


def _reject_payload(*, action: str, current_identity: dict[str, Any], active_role: str, message: str) -> dict[str, Any]:
    correctable_fields: list[str] | None = None
    for field in ("target_type", "target_id", "mode", "reason"):
        if field in message:
            correctable_fields = [field]
            break
    if "unsupported payload fields:" in message:
        suffix = message.split("unsupported payload fields:", 1)[1].strip()
        if suffix:
            correctable_fields = [row.strip() for row in suffix.split(",") if row.strip()]
    return tool_results.rejection(
        tool="evidence",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
        code="E_EVIDENCE_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        human_summary="Evidence payload is invalid.",
        why_blocked=message,
        impact="No evidence token state changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Fix evidence payload and retry.",
        allowed_next_actions=[
            "Use context.summarize to inspect target ids.",
            "Retry with explicit target_type and target_id.",
        ],
        correctable_fields=correctable_fields,
        alternative_capabilities=[
            tool_results.alternative_capability(
                tool="track",
                action="open",
                condition="Use when you need shared material/proof artifact ids before retrying evidence actions.",
            ),
            tool_results.alternative_capability(
                tool="artifact",
                action="get",
                condition="Use when you need to confirm one artifact target before issuing token metadata.",
            ),
        ],
    )


def _reject_scope(
    *,
    action: str,
    current_identity: dict[str, Any],
    active_role: str,
    boundary: str,
    message: str,
    code: str = "E_EVIDENCE_SCOPE",
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="evidence",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
        code=code,
        message=message,
        permission_boundary=boundary,
        human_summary="Evidence scope check failed.",
        why_blocked=message,
        impact="No evidence token state changed.",
        state_changed=False,
        retryable=False,
        retry_guidance="Use readable active-actor-authored artifact targets.",
        allowed_next_actions=[
            "Use track.open to inspect shared material/proof artifact ids.",
            "Use artifact.get to confirm one artifact target.",
            "Retry with a target authored by the active actor.",
        ],
        correctable_fields=["target_type", "target_id"],
        alternative_capabilities=[
            tool_results.alternative_capability(
                tool="track",
                action="open",
                condition="Use when you need readable/owned artifact ids from shared track pages.",
            )
        ],
    )


def _require_allowed_fields(action: str, args: dict[str, Any], current_identity: dict[str, Any], active_role: str) -> dict[str, Any] | None:
    _, action_name = action.split(".", 1)
    allowed = set()
    for row in _ACTION_DEFINITION_MAP.get("actions", []):
        if isinstance(row, dict) and row.get("name") == action_name:
            allowed = {field for field in row.get("payload_fields", []) if isinstance(field, str)}
            break
    unknown = sorted(key for key in args if key not in allowed)
    if unknown:
        return _reject_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message=f"unsupported payload fields: {', '.join(unknown)}",
        )
    return None


def _resolve_target(
    *,
    target_type: str,
    target_id: str,
    active_role: str,
    action: str,
    context: EvidenceServiceContext,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if target_type == "artifact":
        artifact = context.repos.artifact.get_artifact(target_id)
        if artifact is None:
            return None, _reject_payload(
                action=action,
                current_identity=context["current_identity"],
                active_role=active_role,
                message=f"artifact not found: {target_id}",
            )
        current_identity = context["current_identity"]
        active_identity_id = current_identity.get("id") if isinstance(current_identity, dict) else None
        authors = artifact.get("author_identity_ids") if isinstance(artifact.get("author_identity_ids"), list) else []
        if active_identity_id not in [row for row in authors if isinstance(row, str)]:
            return None, _reject_scope(
                action=action,
                current_identity=current_identity,
                active_role=active_role,
                boundary="artifact.author_identity_ids",
                code="E_EVIDENCE_TARGET_SCOPE",
                message=f"artifact '{target_id}' is not authored by the active actor",
            )
        return artifact, None
    return None, _reject_scope(
        action=action,
        current_identity=context["current_identity"],
        active_role=active_role,
        boundary="evidence.target_type",
        code="E_EVIDENCE_TARGET_TYPE",
        message="target_type must be: artifact",
    )


def _issue_token(
    *,
    target_type: str,
    target_id: str,
    mode: str | None,
    kind: str,
    current_identity: dict[str, Any],
    context: EvidenceServiceContext,
) -> dict[str, Any]:
    return {
        "token_id": f"evidence-{uuid.uuid4().hex[:16]}",
        "target_type": target_type,
        "target_id": target_id,
        "issued_by_identity_id": current_identity["id"],
        "mode": mode or "default",
        "evidence_kind": kind,
        "issued_at": context.repos.runtime_files.now_iso(),
    }


def issue_browser_for_active_instance(*, args: dict[str, Any], context: EvidenceServiceContext) -> dict[str, Any]:
    action = "evidence.issue_browser"
    active_role = context["active_role"]
    current_identity = context["current_identity"]
    payload_error = _require_allowed_fields(action, args, current_identity, active_role)
    if payload_error is not None:
        return payload_error

    target_type = args.get("target_type")
    target_id = args.get("target_id")
    if not isinstance(target_type, str) or not target_type.strip():
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="target_type is required")
    if not isinstance(target_id, str) or not target_id.strip():
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="target_id is required")

    _, scope_error = _resolve_target(
        target_type=target_type.strip(),
        target_id=target_id.strip(),
        active_role=active_role,
        action=action,
        context=context,
    )
    if scope_error is not None:
        return scope_error

    mode = args.get("mode")
    if mode is not None and (not isinstance(mode, str) or not mode.strip()):
        return _reject_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message="mode must be a non-empty string when provided",
        )

    token = _issue_token(
        target_type=target_type.strip(),
        target_id=target_id.strip(),
        mode=mode.strip() if isinstance(mode, str) and mode.strip() else None,
        kind="browser",
        current_identity=current_identity,
        context=context,
    )

    return tool_results.success(
        tool="evidence",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
        effect_summary=f"Issued transient target-scoped evidence token metadata for {target_type.strip()} '{target_id.strip()}'.",
        state_changed=True,
        durability="transient",
        created_ids=[token["token_id"]],
        state_changes=[
            {
                "object_type": "evidence_token",
                "change": "issued",
                "token_id": token["token_id"],
                "target_id": target_id.strip(),
            }
        ],
        allowed_next_actions=[
            "Attach evidence token metadata via artifact source_refs when persisting outputs.",
            "Issue another token for a different target when needed.",
        ],
        extra={"tool_evidence": token, "mutates_product_state": False},
    )


def approve_downgrade_for_active_instance(*, args: dict[str, Any], context: EvidenceServiceContext) -> dict[str, Any]:
    action = "evidence.approve_downgrade"
    active_role = context["active_role"]
    current_identity = context["current_identity"]
    payload_error = _require_allowed_fields(action, args, current_identity, active_role)
    if payload_error is not None:
        return payload_error

    target_type = args.get("target_type")
    target_id = args.get("target_id")
    reason = args.get("reason")
    if not isinstance(target_type, str) or not target_type.strip():
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="target_type is required")
    if not isinstance(target_id, str) or not target_id.strip():
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="target_id is required")
    if not isinstance(reason, str) or not reason.strip():
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="reason is required")

    _, scope_error = _resolve_target(
        target_type=target_type.strip(),
        target_id=target_id.strip(),
        active_role=active_role,
        action=action,
        context=context,
    )
    if scope_error is not None:
        return scope_error

    token = _issue_token(
        target_type=target_type.strip(),
        target_id=target_id.strip(),
        mode="downgrade-approved",
        kind="downgrade",
        current_identity=current_identity,
        context=context,
    )
    token["reason"] = reason.strip()

    return tool_results.success(
        tool="evidence",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
        effect_summary=f"Issued transient downgrade-approval token metadata for {target_type.strip()} '{target_id.strip()}'.",
        state_changed=True,
        durability="transient",
        created_ids=[token["token_id"]],
        state_changes=[
            {
                "object_type": "evidence_token",
                "change": "issued",
                "token_id": token["token_id"],
                "target_id": target_id.strip(),
            }
        ],
        allowed_next_actions=[
            "Persist downgrade reason in artifact source_refs when writing outputs.",
            "Use evidence.issue_browser when browser evidence can be produced later.",
        ],
        extra={"tool_evidence": token, "mutates_product_state": False},
    )


_ACTION_HANDLERS = {
    'approve_downgrade': approve_downgrade_for_active_instance,
    'issue_browser': issue_browser_for_active_instance,
}


def invoke(*, action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    handler = _ACTION_HANDLERS.get(action)
    if handler is None:
        raise ValueError(f"unsupported action: {action}")
    return handler(args=args, context=context)
