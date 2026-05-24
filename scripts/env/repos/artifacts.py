#!/usr/bin/env python3
"""Artifact repository helpers backed by runtime object files."""

from __future__ import annotations

import hashlib
import mimetypes
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from . import runtime_files

VALID_ARTIFACT_STATUS = ("draft", "published", "archived")
VALID_ARTIFACT_TEMPLATES = ("brief", "proposal", "design", "decision", "proof", "note")
_LEGACY_SOURCE_RUN = "source" + "_run_id"
_LEGACY_ARTIFACT_FIELDS = {"task_id", "kind", "content", "publication_role", "asset", "media", "material", "blocks", "figma_file"}
_KNOWN_BUDDY_IDS = {"pm", "design", "dev", "market", "test"}
_SHA256_HEX_LENGTH = 64


def _template_from_legacy_kind(kind: str) -> str:
    normalized = kind.strip().lower()
    if normalized in {"design-handoff", "design"}:
        return "design"
    if normalized in {"solution-spec", "technical-proposal", "proposal"}:
        return "proposal"
    if normalized in {"pm-decision", "decision"}:
        return "decision"
    if normalized in {"verification-proof", "smoke-test", "test-report", "proof"}:
        return "proof"
    if normalized in {"prd", "brief"}:
        return "brief"
    return "note"


def _require_non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _normalize_source_refs(
    raw_refs: Any,
    *,
    active_buddy: str | None = None,
) -> list[dict[str, Any]] | None:
    if raw_refs is None:
        return None
    if not isinstance(raw_refs, list):
        raise ValueError("source_refs must be a list when provided")

    normalized: list[dict[str, Any]] = []
    for raw in raw_refs:
        if not isinstance(raw, dict):
            raise ValueError("each source_ref must be an object")
        ref_type = raw.get("type")
        if not isinstance(ref_type, str) or not ref_type.strip():
            raise ValueError("source_ref.type must be a non-empty string")
        ref_type = ref_type.strip()
        row: dict[str, Any] = {"type": ref_type}

        if ref_type in {"artifact", "track", "task"}:
            row["id"] = runtime_files.require_id(raw.get("id"), f"source_ref.{ref_type}.id")
        elif ref_type == "external":
            label = raw.get("label")
            if not isinstance(label, str) or not label.strip():
                raise ValueError("source_ref.external.label must be a non-empty string")
            row["label"] = label.strip()
            url = raw.get("url")
            if url is not None:
                if not isinstance(url, str) or not url.strip():
                    raise ValueError("source_ref.external.url must be a non-empty string when provided")
                row["url"] = url.strip()
        elif ref_type == "note":
            label = raw.get("label")
            if not isinstance(label, str) or not label.strip():
                raise ValueError("source_ref.note.label must be a non-empty string")
            row["label"] = label.strip()
        else:
            raise ValueError(f"unsupported source_ref type: {ref_type}")

        normalized.append(row)
    return normalized


def _normalize_attachment_filename(value: Any) -> str:
    filename = _require_non_empty_text(value, "attachment.filename")
    if filename in {".", ".."}:
        raise ValueError("attachment.filename must not be '.' or '..'")
    if "/" in filename or "\\" in filename or ".." in filename:
        raise ValueError("attachment.filename must not include path separators or traversal")
    return filename


def _normalize_attachment_rows(raw_rows: Any) -> list[dict[str, Any]]:
    if raw_rows is None:
        return []
    if not isinstance(raw_rows, list):
        raise ValueError("artifact.attachments must be a list")

    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        if not isinstance(raw, dict):
            raise ValueError("artifact.attachments rows must be objects")
        attachment_id = runtime_files.require_id(raw.get("attachment_id"), "attachment.attachment_id")
        filename = _normalize_attachment_filename(raw.get("filename"))
        content_type = _require_non_empty_text(raw.get("content_type"), "attachment.content_type")
        size_bytes = raw.get("size_bytes")
        if not isinstance(size_bytes, int) or size_bytes < 0:
            raise ValueError("attachment.size_bytes must be a non-negative integer")
        sha256 = _require_non_empty_text(raw.get("sha256"), "attachment.sha256")
        if len(sha256) != _SHA256_HEX_LENGTH or any(ch not in "0123456789abcdef" for ch in sha256):
            raise ValueError("attachment.sha256 must be 64 lowercase hex chars")
        created_by = _require_non_empty_text(raw.get("created_by"), "attachment.created_by")
        if created_by not in _KNOWN_BUDDY_IDS:
            raise ValueError("attachment.created_by must be one of known buddy ids")
        created_at = _require_non_empty_text(raw.get("created_at"), "attachment.created_at")
        rows.append(
            {
                "attachment_id": attachment_id,
                "filename": filename,
                "content_type": content_type,
                "size_bytes": size_bytes,
                "sha256": sha256,
                "created_by": created_by,
                "created_at": created_at,
            }
        )
    return rows


def now_iso() -> str:
    return runtime_files.now_iso()


def artifact_file(artifact_id: str) -> Path:
    return runtime_files.ARTIFACT_OBJECTS_DIR / f"{runtime_files.require_id(artifact_id, 'artifact id')}.json"


def attachment_file(artifact_id: str, attachment_id: str) -> Path:
    return (
        runtime_files.ARTIFACT_ATTACHMENTS_DIR
        / runtime_files.require_id(artifact_id, "artifact id")
        / f"{runtime_files.require_id(attachment_id, 'attachment id')}.bin"
    )


def list_artifacts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if runtime_files.ARTIFACT_OBJECTS_DIR.exists():
        for path in runtime_files.ARTIFACT_OBJECTS_DIR.glob("*.json"):
            rows.append(validate_artifact(runtime_files.read_json_object(path)))
    rows.sort(key=lambda row: (row.get("updated_at", ""), row["id"]), reverse=True)
    return rows


def get_artifact(artifact_id: str) -> dict[str, Any] | None:
    path = artifact_file(artifact_id)
    if not path.exists():
        return None
    return validate_artifact(runtime_files.read_json_object(path))


def save_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    normalized = validate_artifact(artifact)
    runtime_files.require_runtime_workspace_write_root()
    runtime_files.ARTIFACT_OBJECTS_DIR.mkdir(parents=True, exist_ok=True)
    runtime_files.write_json_object(artifact_file(normalized["id"]), normalized)
    return normalized


def attachment_summaries(artifact_id: str) -> list[dict[str, Any]]:
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {artifact_id}")
    attachments = artifact.get("attachments")
    return list(attachments) if isinstance(attachments, list) else []


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def create_artifact_revision(
    *,
    artifact_id: str | None,
    title: str,
    created_by: str,
    body: str,
    template: str,
    summary: str = "",
    source_refs: list[dict[str, Any]] | None = None,
    supersedes_artifact_id: str | None = None,
    authors: list[str] | None = None,
    legacy_source_run: str | None = None,
) -> dict[str, Any]:
    if legacy_source_run is not None:
        raise ValueError("legacy artifact run lineage field is retired; use source_refs")

    resolved_id = artifact_id or f"art-{uuid.uuid4().hex[:10]}"
    runtime_files.require_id(resolved_id, "artifact id")
    if get_artifact(resolved_id):
        raise ValueError(f"artifact already exists: {resolved_id}")

    if created_by not in _KNOWN_BUDDY_IDS:
        raise ValueError("created_by must be one of known buddy ids")
    if not isinstance(body, str) or not body.strip():
        raise ValueError("body must be a non-empty string")
    if template not in VALID_ARTIFACT_TEMPLATES:
        raise ValueError(f"template must be one of {', '.join(VALID_ARTIFACT_TEMPLATES)}")
    if not isinstance(summary, str):
        raise ValueError("summary must be a string")
    normalized_refs = _normalize_source_refs(source_refs, active_buddy=created_by)

    revision = 1
    supersedes_id: str | None = None
    new_is_current = False
    demote_previous: dict[str, Any] | None = None
    if supersedes_artifact_id is not None:
        runtime_files.require_id(supersedes_artifact_id, "artifact.supersedes_artifact_id")
        previous = get_artifact(supersedes_artifact_id)
        if previous is None:
            raise ValueError(f"artifact not found: {supersedes_artifact_id}")
        if not bool(previous.get("is_current")):
            raise ValueError(f"artifact '{supersedes_artifact_id}' is not current and cannot be superseded")

        previous_status = previous.get("status")
        previous_owner = previous.get("created_by")
        revision = int(previous.get("revision", 1)) + 1
        supersedes_id = supersedes_artifact_id

        if previous_status == "draft":
            if previous_owner != created_by:
                raise ValueError("supersedes_artifact_id must reference an active-buddy-owned current draft")
            new_is_current = True
            previous_patch = dict(previous)
            previous_patch["is_current"] = False
            previous_patch["updated_at"] = now_iso()
            validate_artifact(previous_patch)
            demote_previous = previous_patch
        elif previous_status == "published":
            new_is_current = False
        else:
            raise ValueError("supersedes_artifact_id must reference a current draft or published artifact")

    author_rows = [created_by]
    if isinstance(authors, list):
        for row in authors:
            if isinstance(row, str) and row in _KNOWN_BUDDY_IDS and row not in author_rows:
                author_rows.append(row)

    timestamp = now_iso()
    artifact = {
        "id": resolved_id,
        "title": _require_non_empty_text(title, "artifact.title"),
        "summary": summary,
        "body": body,
        "template": template,
        "status": "draft",
        "published_to_track": None,
        "revision": revision,
        "is_current": new_is_current,
        "supersedes_artifact_id": supersedes_id,
        "created_by": created_by,
        "authors": author_rows,
        "source_refs": normalized_refs,
        "attachments": [],
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    created = save_artifact(artifact)
    if demote_previous is not None:
        save_artifact(demote_previous)
    return created


def update_artifact(artifact_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {artifact_id}")
    if _LEGACY_SOURCE_RUN in patch:
        raise ValueError("legacy artifact run lineage field is retired; use source_refs")

    retired = sorted(key for key in patch if key in {"kind", "content", "publication_role", "task_id"})
    if retired:
        raise ValueError(f"retired artifact fields are unsupported: {', '.join(retired)}")

    allowed = {
        "title",
        "summary",
        "body",
        "template",
        "status",
        "source_refs",
        "published_to_track",
        "supersedes_artifact_id",
        "is_current",
        "revision",
        "authors",
    }
    for key, value in patch.items():
        if key not in allowed:
            raise ValueError(f"unsupported artifact field: {key}")
        artifact[key] = value
    artifact["updated_at"] = now_iso()
    return save_artifact(artifact)


def adopt_local_attachment(
    artifact_id: str,
    filename: str,
    created_by: str,
    source_path: Path,
    content_type: str | None,
    context: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {artifact_id}")

    root = context.repos.runtime_files.buddybox_local_dir(context.instance_payload).resolve(strict=False)
    try:
        resolved_source = source_path.expanduser().resolve(strict=True)
    except FileNotFoundError as exc:
        raise FileNotFoundError(str(source_path)) from exc
    if not _path_is_within(resolved_source, root):
        raise ValueError("source_path must resolve inside the active instance buddybox directory")
    if resolved_source.is_dir():
        raise IsADirectoryError(str(source_path))
    if not resolved_source.is_file():
        raise ValueError("source_path must resolve to a regular file")

    raw = resolved_source.read_bytes()
    if not raw:
        raise ValueError("source_path must reference a non-empty file")

    attachment_id = f"att-{uuid.uuid4().hex[:10]}"
    inferred_content_type = mimetypes.guess_type(resolved_source.name)[0] or "application/octet-stream"
    content_type_value = content_type.strip() if isinstance(content_type, str) and content_type.strip() else inferred_content_type
    timestamp = now_iso()
    attachment = {
        "attachment_id": attachment_id,
        "filename": _normalize_attachment_filename(filename),
        "content_type": content_type_value,
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "created_by": created_by,
        "created_at": timestamp,
    }

    target_path = attachment_file(artifact_id, attachment_id)
    runtime_files.require_runtime_workspace_write_root()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(resolved_source, target_path)
    except OSError:
        shutil.copyfile(resolved_source, target_path)

    updated_artifact = dict(artifact)
    updated_artifact["attachments"] = attachment_summaries(artifact_id) + [attachment]
    updated_artifact["updated_at"] = timestamp
    saved = save_artifact(updated_artifact)
    return saved, attachment


def get_attachment_content(artifact_id: str, attachment_id: str) -> tuple[dict[str, Any], bytes]:
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {artifact_id}")

    attachments = artifact.get("attachments")
    rows = attachments if isinstance(attachments, list) else []
    for row in rows:
        if isinstance(row, dict) and row.get("attachment_id") == attachment_id:
            path = attachment_file(artifact_id, attachment_id)
            if not path.exists() or not path.is_file():
                raise FileNotFoundError(attachment_id)
            return row, path.read_bytes()
    raise ValueError(f"attachment not found: {attachment_id}")


def validate_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    if _LEGACY_SOURCE_RUN in artifact:
        raise ValueError("legacy artifact run lineage field is retired; use source_refs")
    forbidden = sorted(field for field in artifact if field in _LEGACY_ARTIFACT_FIELDS)
    legacy_fields_present = any(field in artifact for field in ("task_id", "kind", "content", "buddy"))
    canonical_fields_present = any(
        field in artifact for field in ("body", "template", "status", "published_to_track", "authors")
    )
    allow_legacy = legacy_fields_present and not canonical_fields_present
    if forbidden:
        if not allow_legacy:
            raise ValueError(f"legacy artifact fields are retired: {', '.join(forbidden)}")
        legacy_normalizable = {"task_id", "kind", "content"}
        unsupported_legacy = [field for field in forbidden if field not in legacy_normalizable]
        if unsupported_legacy:
            raise ValueError(f"legacy artifact fields are retired: {', '.join(unsupported_legacy)}")

    artifact_id = runtime_files.require_id(artifact.get("id", ""), "artifact.id")
    title = _require_non_empty_text(artifact.get("title"), "artifact.title")

    created_by_raw = artifact.get("created_by")
    if not isinstance(created_by_raw, str) or not created_by_raw.strip():
        created_by_raw = artifact.get("buddy") if allow_legacy else created_by_raw
    created_by = _require_non_empty_text(created_by_raw, "artifact.created_by")
    if created_by not in _KNOWN_BUDDY_IDS:
        raise ValueError("artifact.created_by must be one of known buddy ids")

    body = artifact.get("body")
    if not isinstance(body, str) or not body.strip():
        if allow_legacy:
            content = artifact.get("content")
            if isinstance(content, dict):
                legacy_body = content.get("body")
                if isinstance(legacy_body, str) and legacy_body.strip():
                    body = legacy_body
        if not isinstance(body, str) or not body.strip():
            raise ValueError("artifact.body must be a non-empty string")

    template = artifact.get("template")
    if not isinstance(template, str) or not template.strip():
        if allow_legacy:
            kind = artifact.get("kind")
            if isinstance(kind, str) and kind.strip():
                template = _template_from_legacy_kind(kind)
    if not isinstance(template, str) or template not in VALID_ARTIFACT_TEMPLATES:
        raise ValueError(f"artifact.template must be one of {', '.join(VALID_ARTIFACT_TEMPLATES)}")

    published_to_track = artifact.get("published_to_track")
    if published_to_track is not None:
        runtime_files.require_id(published_to_track, "artifact.published_to_track")

    status = artifact.get("status")
    if not isinstance(status, str):
        if allow_legacy:
            status = "draft" if published_to_track is None else "published"
    if status not in VALID_ARTIFACT_STATUS:
        raise ValueError(f"artifact.status must be one of {', '.join(VALID_ARTIFACT_STATUS)}")
    if status == "draft" and published_to_track is not None:
        raise ValueError("artifact.published_to_track must be null for draft artifacts")
    if status in {"published", "archived"} and published_to_track is None:
        raise ValueError("artifact.published_to_track is required for published/archived artifacts")

    summary = artifact.get("summary", "")
    if not isinstance(summary, str):
        raise ValueError("artifact.summary must be a string")

    source_refs = _normalize_source_refs(artifact.get("source_refs"), active_buddy=created_by)

    revision = artifact.get("revision")
    if not isinstance(revision, int) or revision <= 0:
        raise ValueError("artifact.revision must be a positive integer")

    supersedes_artifact_id = artifact.get("supersedes_artifact_id")
    if supersedes_artifact_id is not None:
        runtime_files.require_id(supersedes_artifact_id, "artifact.supersedes_artifact_id")

    is_current = artifact.get("is_current")
    if not isinstance(is_current, bool):
        raise ValueError("artifact.is_current must be a boolean")

    authors_raw = artifact.get("authors")
    authors: list[str] = []
    if isinstance(authors_raw, list):
        for row in authors_raw:
            if isinstance(row, str) and row in _KNOWN_BUDDY_IDS and row not in authors:
                authors.append(row)
    if created_by not in authors:
        authors.insert(0, created_by)

    attachments = _normalize_attachment_rows(artifact.get("attachments"))
    created_at = _require_non_empty_text(artifact.get("created_at"), "artifact.created_at")
    updated_at = _require_non_empty_text(artifact.get("updated_at"), "artifact.updated_at")

    return {
        "id": artifact_id,
        "title": title,
        "summary": summary,
        "body": body,
        "template": template,
        "status": status,
        "published_to_track": published_to_track,
        "revision": revision,
        "is_current": is_current,
        "supersedes_artifact_id": supersedes_artifact_id,
        "created_by": created_by,
        "authors": authors,
        "source_refs": source_refs,
        "attachments": attachments,
        "created_at": created_at,
        "updated_at": updated_at,
    }
