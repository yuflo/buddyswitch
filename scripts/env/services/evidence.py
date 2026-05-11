#!/usr/bin/env python3
"""Browser evidence issuance service for broker-routed env.tool operations."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, TypedDict
from urllib.error import URLError
from urllib.request import Request, urlopen
import uuid

import env_profiles


class EvidenceServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]
    manifest_path: Path | None


def _runtime() -> Any:
    import turn_runtime

    return turn_runtime


def _allowed(*actions: str) -> list[str]:
    return list(actions)


def _payload_error(*, action: str, context: EvidenceServiceContext, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": "evidence",
        "action": action,
        "error": {
            "code": "E_EVIDENCE_PAYLOAD",
            "message": message,
        },
        "permission_boundary": "request-payload",
        "active_buddy": context["active_buddy"],
        "allowed_next_actions": [
            'Send env.tool payload as {"tool":"evidence","action":"<action>","args":{...}}.',
            "Use prepare.runtime_context.env_tools.evidence_manager.payload_fields to shape args.",
        ],
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _context_matches_active_instance(*, prepared_context: dict[str, Any], context: EvidenceServiceContext) -> None:
    rt = _runtime()
    instance_payload = context["instance_payload"]
    active_buddy = context["active_buddy"]
    instance_id = context["instance_id"]

    if prepared_context.get("ok") is not True:
        rt._raise_runtime_feedback(
            "E_RUNTIME_BROKER",
            "context must be successful before issuing browser evidence",
            permission_boundary="prepare.context_revision",
            allowed_next_actions=rt._rerun_prepare_actions(),
        )
    if prepared_context.get("instance_id") != instance_id:
        rt._raise_runtime_feedback(
            "E_RUNTIME_BROKER",
            "context instance_id mismatch for evidence issuance",
            permission_boundary="active-instance",
            allowed_next_actions=rt._rerun_prepare_actions(),
        )
    if prepared_context.get("active_buddy") != active_buddy:
        rt._raise_runtime_feedback(
            "E_RUNTIME_BROKER",
            "context active_buddy mismatch for evidence issuance",
            permission_boundary="active-buddy",
            allowed_next_actions=rt._rerun_prepare_actions(),
        )

    task_id = prepared_context.get("current_task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("context.current_task_id is required for evidence issuance")
    context_track_id = prepared_context.get("current_track_id")
    if context_track_id is not None and not isinstance(context_track_id, str):
        raise ValueError("context.current_track_id must be a string when provided")

    bound_task = instance_payload.get("current_task_id")
    if isinstance(bound_task, str) and bound_task.strip() and bound_task != task_id:
        rt._raise_runtime_feedback(
            "E_RUNTIME_BROKER",
            "context task_id does not match active instance binding",
            permission_boundary="active-instance",
            allowed_next_actions=rt._rerun_prepare_actions(),
        )
    bound_track = instance_payload.get("current_track_id")
    if isinstance(bound_track, str) and bound_track.strip():
        if not isinstance(context_track_id, str) or context_track_id != bound_track:
            rt._raise_runtime_feedback(
                "E_RUNTIME_BROKER",
                "context track_id does not match active instance binding",
                permission_boundary="active-instance",
                allowed_next_actions=rt._rerun_prepare_actions(),
            )

    context_revision = prepared_context.get("context_revision")
    if not isinstance(context_revision, str) or not context_revision.strip():
        raise ValueError("context.context_revision is required for evidence issuance")
    run_envelope = prepared_context.get("run_envelope")
    if not isinstance(run_envelope, dict):
        raise ValueError("context.run_envelope is required for evidence issuance")
    run_id = run_envelope.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("context.run_envelope.run_id is required for evidence issuance")

    rt._validate_context_revision(prepared_context)


def _require_market_evidence_profile(*, context: EvidenceServiceContext) -> None:
    rt = _runtime()
    manifest_path = context["manifest_path"] or rt.DEFAULT_MANIFEST
    profile = env_profiles.require_env_profile(
        context["active_buddy"],
        manifest_path=manifest_path,
        repo_root=rt.REPO_ROOT,
    )
    tool_capability = profile.get("tool_capability")
    if not isinstance(tool_capability, dict):
        raise ValueError("env profile tool_capability must be an object")
    if tool_capability.get("browser_cockpit") != "required":
        raise ValueError("active profile does not require browser cockpit evidence")
    if tool_capability.get("market_research_evidence") != "required":
        raise ValueError("active profile does not require market research evidence")


def _instance_browser_url(instance_payload: dict[str, Any]) -> str:
    port = instance_payload.get("browser_port")
    if not isinstance(port, int):
        raise ValueError("instance browser_port is missing")
    if port < 1 or port > 65535:
        raise ValueError(f"invalid instance browser_port: {port}")
    return f"http://127.0.0.1:{port}"


def _require_browser_endpoint(url: str) -> None:
    probe_url = f"{url}/json/version"
    try:
        with urlopen(probe_url, timeout=3.0) as response:
            if response.status < 200 or response.status >= 300:
                raise ValueError(f"browser endpoint probe failed: HTTP {response.status}")
    except (URLError, OSError, ValueError) as exc:
        raise ValueError(f"browser cockpit endpoint is unreachable: {probe_url}: {exc}") from exc


def _browser_target_is_usable_page(target: Any) -> bool:
    if not isinstance(target, dict):
        return False
    if target.get("type") != "page":
        return False
    url = target.get("url")
    if not isinstance(url, str):
        return False
    normalized = url.strip().lower()
    if not normalized:
        return False
    if normalized == "about:blank":
        return True
    if normalized.startswith("chrome://"):
        return False
    if normalized.startswith("chrome-untrusted://"):
        return False
    if normalized.startswith("devtools://"):
        return False
    return True


def _browser_has_usable_page(url: str) -> bool:
    targets_url = f"{url}/json/list"
    try:
        with urlopen(targets_url, timeout=3.0) as response:
            if response.status < 200 or response.status >= 300:
                return False
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, OSError, ValueError, json.JSONDecodeError):
        return False
    if not isinstance(payload, list):
        return False
    return any(_browser_target_is_usable_page(target) for target in payload)


def _browser_create_blank_page(url: str) -> bool:
    create_url = f"{url}/json/new?about:blank"
    request = Request(create_url, method="PUT")
    try:
        with urlopen(request, timeout=3.0) as response:
            return 200 <= response.status < 300
    except (URLError, OSError, ValueError):
        return False


def _require_browser_ready_page(url: str, *, instance_id: str) -> None:
    rt = _runtime()
    _require_browser_endpoint(url)
    if _browser_has_usable_page(url):
        return
    _browser_create_blank_page(url)
    if _browser_has_usable_page(url):
        return
    rt._raise_runtime_feedback(
        "E_RUNTIME_BROKER",
        "browser cockpit ready page is required before issuing browser evidence",
        permission_boundary="browser-cockpit-ready",
        stop_condition="browser cockpit is not ready for MCP page operations",
        allowed_next_actions=_allowed(
            "Restart or open the launcher-managed instance to rebuild browser cockpit readiness.",
            "Rerun browser ensure for the active launcher-managed instance.",
        ),
        command_hint=f"./buddyswitch-codex env browser ensure --instance {instance_id}",
    )


def evidence_root(instance_json: Path) -> Path:
    return instance_json.parent / "runtime" / "evidence-tokens"


def _write_evidence_token(
    *,
    context: EvidenceServiceContext,
    prepared_context: dict[str, Any],
    mode: str,
    reason: str | None,
    browser_url: str | None,
) -> dict[str, Any]:
    run_envelope = prepared_context["run_envelope"]
    run_id = str(run_envelope["run_id"]).strip()
    context_revision = str(prepared_context["context_revision"]).strip()
    buddy_id = str(prepared_context["active_buddy"]).strip()
    instance_id = str(prepared_context["instance_id"]).strip()
    task_id = str(prepared_context["current_task_id"]).strip()
    track_id = prepared_context.get("current_track_id")
    token_prefix = "evidence" if mode == "browser-cockpit-preflight" else "downgrade"
    token = f"{token_prefix}-{run_id}-{uuid.uuid4().hex[:8]}"

    root = evidence_root(context["instance_json"]) / run_id
    root.mkdir(parents=True, exist_ok=True)
    token_path = root / f"{token}.json"
    payload: dict[str, Any] = {
        "token": token,
        "mode": mode,
        "instance_id": instance_id,
        "buddy_id": buddy_id,
        "task_id": task_id,
        "track_id": track_id if isinstance(track_id, str) and track_id else None,
        "context_revision": context_revision,
        "run_id": run_id,
        "issued_at": _now_iso(),
    }
    if browser_url is not None:
        payload["browser_url"] = browser_url
    if reason is not None:
        payload["reason"] = reason
    token_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    token_scope = {
        "instance_id": instance_id,
        "buddy_id": buddy_id,
        "task_id": task_id,
        "track_id": track_id if isinstance(track_id, str) and track_id else None,
        "context_revision": context_revision,
        "run_id": run_id,
    }
    if mode == "browser-cockpit-preflight":
        return {
            "ok": True,
            "tool_evidence": {"browser_cockpit_token": token},
            "feedback": {
                "mode": mode,
                "browser_url": browser_url,
                "persist_field": "tool_evidence.browser_cockpit_token",
                "token_scope": token_scope,
                "next_action": "Include tool_evidence.browser_cockpit_token in the next artifact-producing persist.",
            },
        }
    return {
        "ok": True,
        "tool_evidence": {"approved_downgrade_token": token},
        "feedback": {
            "mode": mode,
            "reason": reason,
            "persist_field": "tool_evidence.approved_downgrade_token",
            "token_scope": token_scope,
            "next_action": "Include tool_evidence.approved_downgrade_token in the next artifact-producing persist.",
        },
    }


def _issue(
    *,
    action: str,
    args: dict[str, Any],
    context: EvidenceServiceContext,
    mode: str,
    reason: str | None,
) -> dict[str, Any]:
    prepared_context = args.get("context")
    if not isinstance(prepared_context, dict):
        return _payload_error(action=action, context=context, message="context is required")

    _require_market_evidence_profile(context=context)
    _context_matches_active_instance(prepared_context=prepared_context, context=context)

    browser_url: str | None = None
    if mode == "browser-cockpit-preflight":
        browser_url = _instance_browser_url(context["instance_payload"])
        _require_browser_ready_page(browser_url, instance_id=context["instance_id"])

    payload = _write_evidence_token(
        context=context,
        prepared_context=prepared_context,
        mode=mode,
        reason=reason,
        browser_url=browser_url,
    )
    return {
        "tool": "evidence",
        "action": action,
        "active_buddy": context["active_buddy"],
        "allowed_next_actions": [
            "Include the issued evidence token in the next artifact-producing persist payload.",
        ],
        **payload,
    }


def issue_browser_for_active_instance(*, args: dict[str, Any], context: EvidenceServiceContext) -> dict[str, Any]:
    return _issue(
        action="evidence.issue_browser",
        args=args,
        context=context,
        mode="browser-cockpit-preflight",
        reason=None,
    )


def approve_downgrade_for_active_instance(*, args: dict[str, Any], context: EvidenceServiceContext) -> dict[str, Any]:
    reason = args.get("reason")
    normalized_reason = reason.strip() if isinstance(reason, str) else None
    if not isinstance(normalized_reason, str) or not normalized_reason:
        return _payload_error(
            action="evidence.approve_downgrade",
            context=context,
            message="approved downgrade requires a non-empty reason",
        )
    return _issue(
        action="evidence.approve_downgrade",
        args=args,
        context=context,
        mode="approved-downgrade",
        reason=normalized_reason,
    )
