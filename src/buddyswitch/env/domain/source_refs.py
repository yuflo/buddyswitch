"""Shared source_refs normalization helpers for runless durable objects.

source_refs are provenance-only metadata. They must never become the required
reading path for artifact understanding.
"""

from __future__ import annotations

from typing import Any

from buddyswitch.env.domain import artifact_visibility as artifact_visibility_domain
from buddyswitch.env.repos import artifacts as artifact_repo
from buddyswitch.env.repos import runtime_files

_ALLOWED_TYPES = {
    "artifact",
    "track",
    "task",
    "external",
    "note",
}
PROVENANCE_ONLY_NOTE = "source_refs are provenance-only metadata, not a required reading path"


def normalize_source_refs(
    raw_refs: Any,
    *,
    active_role: str,
    current_identity: dict[str, Any],
    read_claim: str | None = None,
) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None]:
    if raw_refs is None:
        return None, None
    if not isinstance(raw_refs, list):
        raise ValueError("source_refs must be a list")

    normalized: list[dict[str, Any]] = []
    for raw in raw_refs:
        if not isinstance(raw, dict):
            raise ValueError("each source_ref must be an object")
        ref_type = raw.get("type")
        if not isinstance(ref_type, str) or not ref_type.strip():
            raise ValueError("source_ref.type must be a non-empty string")
        ref_type = ref_type.strip()
        if ref_type not in _ALLOWED_TYPES:
            raise ValueError(f"unsupported source_ref type: {ref_type}")

        item: dict[str, Any] = {"type": ref_type}
        if ref_type in {"artifact", "track", "task"}:
            item["id"] = runtime_files.require_id(raw.get("id"), f"source_refs.{ref_type}.id")
        elif ref_type == "external":
            label = raw.get("label")
            if not isinstance(label, str) or not label.strip():
                raise ValueError("source_refs.external.label must be a non-empty string")
            item["label"] = label.strip()
            url = raw.get("url")
            if url is not None:
                if not isinstance(url, str) or not url.strip():
                    raise ValueError("source_refs.external.url must be a non-empty string when provided")
                item["url"] = url.strip()
        elif ref_type == "note":
            label = raw.get("label")
            if not isinstance(label, str) or not label.strip():
                raise ValueError("source_refs.note.label must be a non-empty string")
            item["label"] = label.strip()

        normalized.append(item)

    scope_error: dict[str, Any] | None = None
    if isinstance(read_claim, str) and read_claim.strip() == "summarized-full-content":
        for row in normalized:
            ref_type = row["type"]
            if ref_type == "artifact":
                ref_id = row["id"]
                artifact = artifact_repo.get_artifact(ref_id)
                if artifact is None:
                    scope_error = {
                        "permission_boundary": "source_refs.read_scope",
                        "why_blocked": (
                            f"cannot claim full summary of unreadable artifact '{ref_id}'; "
                            f"{PROVENANCE_ONLY_NOTE}"
                        ),
                    }
                    break
                decision = artifact_visibility_domain.artifact_read_decision(artifact, current_identity)
                if not bool(decision.get("allowed")):
                    scope_error = {
                        "permission_boundary": "source_refs.read_scope",
                        "why_blocked": (
                            f"cannot claim full summary of unreadable artifact '{ref_id}'; "
                            f"{PROVENANCE_ONLY_NOTE}"
                        ),
                    }
                    break

    return normalized, scope_error


def source_ref_summary(refs: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not isinstance(refs, list):
        return []
    summary: list[dict[str, Any]] = []
    for row in refs:
        if not isinstance(row, dict):
            continue
        ref_type = row.get("type")
        if not isinstance(ref_type, str) or not ref_type:
            continue
        if "id" in row:
            summary.append({"type": ref_type, "id": row.get("id")})
        elif "label" in row:
            entry = {"type": ref_type, "label": row.get("label")}
            if "url" in row:
                entry["url"] = row.get("url")
            summary.append(entry)
        else:
            summary.append({"type": ref_type})
    return summary
