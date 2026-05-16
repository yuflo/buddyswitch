#!/usr/bin/env python3
"""Shared source_refs normalization helpers for runless durable objects."""

from __future__ import annotations

from typing import Any

import env_store

_ALLOWED_TYPES = {
    "artifact",
    "track",
    "task",
    "handoff",
    "buddybox",
    "external",
    "note",
}
_KNOWN_BUDDY_IDS = {"pm", "design", "dev", "market", "test"}


def validate_buddybox_ref_logical_name(logical_name: Any, *, active_buddy: str) -> str:
    if not isinstance(logical_name, str) or not logical_name.strip():
        raise ValueError("source_refs.buddybox.logical_name must be a non-empty string")
    normalized = logical_name.replace("\\", "/").strip()
    if normalized.startswith("/"):
        raise ValueError("source_refs.buddybox.logical_name must be relative")
    pieces = [piece for piece in normalized.split("/") if piece not in {"", "."}]
    if not pieces:
        raise ValueError("source_refs.buddybox.logical_name must be non-empty")
    if any(piece == ".." for piece in pieces):
        raise ValueError("source_refs.buddybox.logical_name must not include '..' traversal")
    if pieces[0] in (_KNOWN_BUDDY_IDS | {active_buddy}):
        raise ValueError("source_refs.buddybox.logical_name must not include a buddy prefix")
    return "/".join(pieces)


def normalize_source_refs(
    raw_refs: Any,
    *,
    active_buddy: str,
    read_claim: str | None = None,
    allow_buddybox: bool = True,
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
        if ref_type in {"artifact", "track", "task", "handoff"}:
            item["id"] = env_store.require_id(raw.get("id"), f"source_refs.{ref_type}.id")
        elif ref_type == "buddybox":
            if not allow_buddybox:
                raise ValueError("source_refs.buddybox logical names are private provenance and not allowed in handoff payloads")
            if "path" in raw:
                raise ValueError("source_refs.buddybox.logical_name is required; path is retired")
            normalized_name = validate_buddybox_ref_logical_name(raw.get("logical_name"), active_buddy=active_buddy)
            item["logical_name"] = normalized_name
            item["private_to_buddy"] = active_buddy
            item["read_grant"] = False
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
                artifact = env_store.get_artifact(ref_id)
                if artifact is None or artifact.get("buddy") != active_buddy:
                    scope_error = {
                        "permission_boundary": "source_refs.read_scope",
                        "why_blocked": f"cannot claim full summary of unreadable artifact '{ref_id}'",
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
        elif "logical_name" in row:
            entry = {"type": ref_type, "logical_name": row.get("logical_name")}
            if "private_to_buddy" in row:
                entry["private_to_buddy"] = row.get("private_to_buddy")
            if "read_grant" in row:
                entry["read_grant"] = row.get("read_grant")
            summary.append(entry)
        elif "label" in row:
            entry = {"type": ref_type, "label": row.get("label")}
            if "url" in row:
                entry["url"] = row.get("url")
            summary.append(entry)
        else:
            summary.append({"type": ref_type})
    return summary
