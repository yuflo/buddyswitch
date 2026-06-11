#!/usr/bin/env python3
"""BuddySwitch runless env object store for durable collaboration objects."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from env.repos import artifacts as artifact_repo
from env.repos import runtime_files
from env.repos import tracks as track_repo
from env.repos import track_comments as track_comment_repo
from env.domain import track_artifact_relations as track_artifact_relations_domain
from env.tool_runtime.actor_profile import ActorAddress

VALID_TRACK_STATE = ("active", "blocked", "done")
VALID_UPDATE_KIND = ("progress", "decision", "blocker")
VALID_TASK_STATUS = ("active", "blocked", "done", "archived")
VALID_ARTIFACT_TEMPLATES = ("brief", "proposal", "design", "decision", "proof", "note")
VALID_MESSAGE_DISPOSITIONS = ("unseen", "absorbed", "replied", "needs_parent")

_LEGACY_TASK_RUN_IDS = "run" + "_ids"
_LEGACY_TASK_LATEST_RUN = "latest" + "_run_id"
_LEGACY_SOURCE_RUN = "source" + "_run_id"
_LEGACY_TRACK_ROLE_FIELDS = ("current_role", "next_role")
_LEGACY_TRACK_FIELDS = {
    "status",
    "summary",
    "task_ids",
    "artifact_ids",
    "tasks",
    "missing_task_ids",
}
_LEGACY_TASK_FIELDS = {"artifact_ids", "artifact" + "_slots"}
_LEGACY_ARTIFACT_FIELDS = {"task_id", "kind", "content", "publication_role", "asset", "media", "material", "blocks", "figma_file"}
_KNOWN_ROLE_IDS = {"pm", "design", "dev", "market", "test"}


def refresh_runtime_root_bindings() -> None:
    """Rebind runtime roots from env.repos.runtime_files during staged migration."""

    global ROOT
    global WORKSPACE_ROOT
    global STATE_ROOT
    global OBJECTS_ROOT
    global TRACKS_DIR
    global ARTIFACT_OBJECTS_DIR
    global MESSAGES_DIR
    global TRACK_COMMENTS_DIR
    global CONTENT_ROOT
    global LOCAL_ROOT
    global ACTOR_PRIVATE_DIR

    ROOT = runtime_files.ROOT
    WORKSPACE_ROOT = runtime_files.WORKSPACE_ROOT
    STATE_ROOT = runtime_files.STATE_ROOT
    OBJECTS_ROOT = runtime_files.OBJECTS_ROOT
    TRACKS_DIR = runtime_files.TRACKS_DIR
    ARTIFACT_OBJECTS_DIR = runtime_files.ARTIFACT_OBJECTS_DIR
    MESSAGES_DIR = runtime_files.MESSAGES_DIR
    TRACK_COMMENTS_DIR = runtime_files.TRACK_COMMENTS_DIR
    CONTENT_ROOT = runtime_files.CONTENT_ROOT
    LOCAL_ROOT = runtime_files.LOCAL_ROOT
    ACTOR_PRIVATE_DIR = runtime_files.ACTOR_PRIVATE_DIR


runtime_files.register_runtime_root_listener(refresh_runtime_root_bindings, call_immediately=True)

RUNTIME_WORKSPACE_AGENTS_HEADER = runtime_files.RUNTIME_WORKSPACE_AGENTS_HEADER

now_iso = runtime_files.now_iso
runtime_workspace_root = runtime_files.runtime_workspace_root
actor_private_dir = runtime_files.actor_private_dir
refresh_runtime_roots_from_env = runtime_files.refresh_runtime_roots_from_env
rel = runtime_files.rel
runtime_workspace_agents_file = runtime_files.runtime_workspace_agents_file
is_runtime_workspace = runtime_files.is_runtime_workspace
require_runtime_workspace_write_root = runtime_files.require_runtime_workspace_write_root
ensure_runtime_dirs = runtime_files.ensure_runtime_dirs
require_id = runtime_files.require_id
slugify = runtime_files.slugify
_read_json = runtime_files.read_json_object
_write_json = runtime_files.write_json_object


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


def track_file(track_id: str) -> Path:
    return TRACKS_DIR / f"{require_id(track_id, 'track id')}.json"


def artifact_file(artifact_id: str) -> Path:
    return ARTIFACT_OBJECTS_DIR / f"{require_id(artifact_id, 'artifact id')}.json"


def message_file(message_id: str) -> Path:
    return MESSAGES_DIR / f"{require_id(message_id, 'message id')}.json"


def track_comment_file(track_id: str, comment_id: str) -> Path:
    return track_comment_repo.track_comment_file(track_id, comment_id)


def _validate_actor_private_ref_logical_name(logical_name: Any, *, active_role: str | None = None) -> str:
    if not isinstance(logical_name, str) or not logical_name.strip():
        raise ValueError("source_refs.actor_private.logical_name must be a non-empty string")
    normalized = logical_name.replace("\\", "/").strip()
    if normalized.startswith("/"):
        raise ValueError("source_refs.actor_private.logical_name must be relative")
    parts = [part for part in normalized.split("/") if part not in {"", "."}]
    if not parts:
        raise ValueError("source_refs.actor_private.logical_name must be non-empty")
    if any(part == ".." for part in parts):
        raise ValueError("source_refs.actor_private.logical_name must not include '..' traversal")
    blocked_prefixes = set(_KNOWN_ROLE_IDS)
    if isinstance(active_role, str) and active_role:
        blocked_prefixes.add(active_role)
    if parts[0] in blocked_prefixes:
        raise ValueError("source_refs.actor_private.logical_name must not include a role prefix")
    return "/".join(parts)


def _normalize_source_refs(
    raw_refs: Any,
    *,
    active_role: str | None = None,
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
            row["id"] = require_id(raw.get("id"), f"source_ref.{ref_type}.id")
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


def _require_non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _normalize_now(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("track.now must be an object")
    if set(value) - {"next", "blocker"}:
        extras = ", ".join(sorted(set(value) - {"next", "blocker"}))
        raise ValueError(f"track.now has unsupported fields: {extras}")
    next_value = _require_non_empty_text(value.get("next"), "track.now.next")
    blocker = value.get("blocker")
    if blocker is not None and not isinstance(blocker, str):
        raise ValueError("track.now.blocker must be a string or null")
    blocker_text = blocker.strip() if isinstance(blocker, str) and blocker.strip() else None
    return {"next": next_value, "blocker": blocker_text}


def _normalize_update_ref(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("track.updates[].refs[] must be an object")
    ref_type = row.get("type")
    if ref_type != "artifact":
        raise ValueError("track.updates[].refs[].type must be 'artifact'")
    return {"type": "artifact", "id": require_id(row.get("id"), "track.updates[].refs[].id")}


def _normalize_update_row(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("track.updates[] must be an object")
    kind = row.get("kind")
    if kind not in VALID_UPDATE_KIND:
        raise ValueError(f"track.updates[].kind must be one of {', '.join(VALID_UPDATE_KIND)}")
    refs = row.get("refs", [])
    if not isinstance(refs, list):
        raise ValueError("track.updates[].refs must be a list")
    created_at = _require_non_empty_text(row.get("created_at"), "track.updates[].created_at")
    return {
        "id": _require_non_empty_text(row.get("id"), "track.updates[].id"),
        "by_actor": _message_actor_payload(row.get("by_actor"), "track.updates[].by_actor"),
        "summary": _require_non_empty_text(row.get("summary"), "track.updates[].summary"),
        "kind": kind,
        "refs": [_normalize_update_ref(item) for item in refs],
        "created_at": created_at,
    }


def validate_track(track: dict[str, Any]) -> dict[str, Any]:
    return track_repo.validate_track(track)


def validate_task(task: dict[str, Any]) -> dict[str, Any]:
    if _LEGACY_TASK_RUN_IDS in task or _LEGACY_TASK_LATEST_RUN in task:
        raise ValueError("legacy task run lineage fields are retired")
    forbidden = sorted(field for field in task if field in _LEGACY_TASK_FIELDS)
    if forbidden:
        raise ValueError(f"legacy task fields are retired: {', '.join(forbidden)}")

    task_id = require_id(task.get("id", ""), "task.id")
    role = _require_non_empty_text(task.get("role"), "task.role")
    title = _require_non_empty_text(task.get("title"), "task.title")
    status = task.get("status")
    if status not in VALID_TASK_STATUS:
        raise ValueError(f"task.status must be one of {', '.join(VALID_TASK_STATUS)}")

    track_id = task.get("track_id")
    if track_id is not None:
        require_id(track_id, "task.track_id")

    summary = task.get("summary", "")
    if not isinstance(summary, str):
        raise ValueError("task.summary must be a string")
    created_at = _require_non_empty_text(task.get("created_at"), "task.created_at")
    updated_at = _require_non_empty_text(task.get("updated_at"), "task.updated_at")

    return {
        "id": task_id,
        "role": role,
        "title": title,
        "status": status,
        "track_id": track_id,
        "summary": summary,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def validate_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    return artifact_repo.validate_artifact(artifact)


def _actor_address_for_role(role_id: str) -> dict[str, str]:
    normalized_role = _require_non_empty_text(role_id, "role_id")
    return ActorAddress(
        role_id=normalized_role,
        actor_id=f"act-{normalized_role}-legacy",
    ).to_payload()


def _message_actor_payload(value: Any, field: str) -> dict[str, str]:
    try:
        return ActorAddress.from_payload(value).to_payload()
    except Exception as exc:
        raise ValueError(f"{field} must be a valid ActorAddress: {exc}") from exc


def validate_message(message: dict[str, Any]) -> dict[str, Any]:
    forbidden_fields = {"status", "read_at", "track_id", "task_id", "artifact_id", "recipients", "broadcast"}
    forbidden = sorted(key for key in message if key in forbidden_fields)
    if forbidden:
        raise ValueError(f"unsupported message fields: {', '.join(forbidden)}")

    msg_id = require_id(message.get("id", ""), "message.id")
    if "from_actor_address" in message or "to_actor_address" in message:
        from_actor_address = _message_actor_payload(message.get("from_actor_address"), "message.from_actor_address")
        to_actor_address = _message_actor_payload(message.get("to_actor_address"), "message.to_actor_address")
    else:
        from_actor_address = _actor_address_for_role(_require_non_empty_text(message.get("from_role"), "message.from_role"))
        to_actor_address = _actor_address_for_role(_require_non_empty_text(message.get("to_role"), "message.to_role"))
    content = _require_non_empty_text(message.get("content"), "message.content")
    reply_to = message.get("reply_to")
    if reply_to is not None:
        require_id(reply_to, "message.reply_to")
    created_at = _require_non_empty_text(message.get("created_at"), "message.created_at")
    disposition = message.get("disposition", "unseen")
    if disposition not in VALID_MESSAGE_DISPOSITIONS:
        raise ValueError("message.disposition must be one of absorbed, needs_parent, replied, unseen")
    disposition_reason = message.get("disposition_reason")
    if disposition_reason is not None:
        disposition_reason = _require_non_empty_text(disposition_reason, "message.disposition_reason")
    disposition_updated_at = message.get("disposition_updated_at")
    if disposition_updated_at is not None:
        disposition_updated_at = _require_non_empty_text(disposition_updated_at, "message.disposition_updated_at")
    processed_by_actor_address = message.get("processed_by_actor_address")
    if processed_by_actor_address is not None:
        processed_by_actor_address = _message_actor_payload(
            processed_by_actor_address,
            "message.processed_by_actor_address",
        )

    return {
        "id": msg_id,
        "from_actor_address": from_actor_address,
        "to_actor_address": to_actor_address,
        "content": content,
        "reply_to": reply_to,
        "created_at": created_at,
        "disposition": disposition,
        "disposition_reason": disposition_reason,
        "disposition_updated_at": disposition_updated_at,
        "processed_by_actor_address": processed_by_actor_address,
    }


def list_tracks() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if TRACKS_DIR.exists():
        for path in TRACKS_DIR.glob("*.json"):
            rows.append(validate_track(_read_json(path)))
    rows.sort(key=lambda row: (row.get("updated_at", ""), row["id"]), reverse=True)
    return rows


def list_artifacts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if ARTIFACT_OBJECTS_DIR.exists():
        for path in ARTIFACT_OBJECTS_DIR.glob("*.json"):
            rows.append(validate_artifact(_read_json(path)))
    rows.sort(key=lambda row: (row.get("updated_at", ""), row["id"]), reverse=True)
    return rows


def artifact_revision_chain(artifact_id: str) -> list[dict[str, Any]]:
    current = get_artifact(artifact_id)
    if current is None:
        return []
    by_id = {
        row.get("id"): row
        for row in list_artifacts()
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    chain: list[dict[str, Any]] = []
    visited: set[str] = set()
    while isinstance(current, dict):
        current_id = current.get("id")
        if not isinstance(current_id, str) or not current_id or current_id in visited:
            break
        chain.append(current)
        visited.add(current_id)
        supersedes_id = current.get("supersedes_artifact_id")
        if not isinstance(supersedes_id, str) or not supersedes_id:
            break
        previous = by_id.get(supersedes_id)
        if not isinstance(previous, dict):
            previous = get_artifact(supersedes_id)
        if not isinstance(previous, dict):
            break
        current = previous
    return chain


def build_track_artifact_index(track_id: str | None) -> dict[str, Any] | None:
    if not track_id:
        return None
    track = get_track(track_id)
    if track is None:
        return None
    return {
        "track_id": track["id"],
        "track_title": track["title"],
        "outcome": track["outcome"],
        "artifact_relations": [row for row in track.get("artifact_relations", []) if isinstance(row, dict)],
        "updated_at": track.get("updated_at", ""),
    }


def get_track(track_id: str) -> dict[str, Any] | None:
    path = track_file(track_id)
    if not path.exists():
        return None
    return validate_track(_read_json(path))


def get_artifact(artifact_id: str) -> dict[str, Any] | None:
    path = artifact_file(artifact_id)
    if not path.exists():
        return None
    return validate_artifact(_read_json(path))


def save_track(track: dict[str, Any]) -> dict[str, Any]:
    normalized = validate_track(track)
    ensure_runtime_dirs()
    _write_json(track_file(normalized["id"]), normalized)
    return normalized


def save_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    normalized = validate_artifact(artifact)
    ensure_runtime_dirs()
    _write_json(artifact_file(normalized["id"]), normalized)
    return normalized


def create_track(
    track_id: str,
    title: str,
    *,
    owner_actor: dict[str, Any],
    outcome: str,
    now: dict[str, Any],
    acceptance_criteria: list[str] | None = None,
    non_goals: list[str] | None = None,
) -> dict[str, Any]:
    return track_repo.create_track(
        track_id,
        title,
        outcome=outcome,
        owner_actor=owner_actor,
        now=now,
        acceptance_criteria=acceptance_criteria,
        non_goals=non_goals,
    )


def update_track(track_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    return track_repo.update_track(track_id, patch)


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
    if created_by not in _KNOWN_ROLE_IDS:
        raise ValueError("created_by must be one of known role ids")
    creator_actor = _actor_address_for_role(created_by)
    author_rows: list[dict[str, str]] = [creator_actor]
    if isinstance(authors, list):
        for row in authors:
            if isinstance(row, str) and row in _KNOWN_ROLE_IDS:
                actor = _actor_address_for_role(row)
                if actor not in author_rows:
                    author_rows.append(actor)
    return artifact_repo.create_artifact_revision(
        artifact_id=artifact_id,
        title=title,
        created_by_actor=creator_actor,
        body=body,
        template=template,
        summary=summary,
        source_refs=source_refs,
        supersedes_artifact_id=supersedes_artifact_id,
        author_actors=author_rows,
    )


def update_artifact(artifact_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    return artifact_repo.update_artifact(artifact_id, patch)


def publish_track_material(
    *,
    track_id: str,
    artifact_id: str,
    label: str,
    from_role: str,
    summary: str,
) -> tuple[dict[str, Any], dict[str, Any], str | None]:
    result = track_artifact_relations_domain.add_material_relation(
        track_id=track_id,
        artifact_id=artifact_id,
        label=label,
        from_actor=_actor_address_for_role(from_role),
        summary=summary,
    )
    return result["track"], result["artifact"], result["superseded_artifact_id"]


def publish_track_proof(
    *,
    track_id: str,
    artifact_id: str,
    label: str,
    from_role: str,
    summary: str,
) -> tuple[dict[str, Any], dict[str, Any], str | None]:
    result = track_artifact_relations_domain.add_proof_relation(
        track_id=track_id,
        artifact_id=artifact_id,
        label=label,
        from_actor=_actor_address_for_role(from_role),
        summary=summary,
    )
    return result["track"], result["artifact"], result["superseded_artifact_id"]


def append_track_update(
    *,
    track_id: str,
    by_role: str,
    kind: str,
    summary: str,
    refs: list[dict[str, Any]] | None = None,
    update_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    track = get_track(track_id)
    if track is None:
        raise ValueError(f"track not found: {track_id}")
    if kind not in VALID_UPDATE_KIND:
        raise ValueError(f"kind must be one of {', '.join(VALID_UPDATE_KIND)}")

    row = {
        "id": update_id or f"upd-{uuid.uuid4().hex[:8]}",
        "by_actor": _actor_address_for_role(by_role),
        "summary": summary,
        "kind": kind,
        "refs": refs or [],
        "created_at": now_iso(),
    }
    updates = [entry for entry in track.get("updates", []) if isinstance(entry, dict)]
    updates.append(row)
    track["updates"] = updates
    track["updated_at"] = now_iso()
    track = save_track(track)
    return track, row


def delete_artifact(artifact_id: str) -> dict[str, Any]:
    require_runtime_workspace_write_root()
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {artifact_id}")
    path = artifact_file(artifact_id)
    if path.exists():
        path.unlink()
    return artifact


def delete_artifacts_by_role(
    role_id: str,
    *,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    targets = [
        artifact
        for artifact in list_artifacts()
        if isinstance(artifact.get("created_by_actor"), dict)
        and artifact["created_by_actor"].get("role_id") == role_id
    ]
    if dry_run:
        return targets
    for artifact in targets:
        delete_artifact(artifact["id"])
    return targets


def delete_all_artifacts(*, dry_run: bool = False) -> list[dict[str, Any]]:
    targets = list_artifacts()
    if dry_run:
        return targets
    for artifact in targets:
        delete_artifact(artifact["id"])
    return targets


# ---------------------------------------------------------------------------
# Message object helpers
# ---------------------------------------------------------------------------


def list_messages() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if MESSAGES_DIR.is_dir():
        for path in MESSAGES_DIR.glob("*.json"):
            rows.append(validate_message(_read_json(path)))
    rows.sort(key=lambda row: (row.get("created_at", ""), row["id"]))
    return rows


def get_message(message_id: str) -> dict[str, Any] | None:
    path = message_file(message_id)
    if not path.exists():
        return None
    return validate_message(_read_json(path))


def save_message(message: dict[str, Any]) -> dict[str, Any]:
    normalized_message = validate_message(message)
    ensure_runtime_dirs()
    _write_json(message_file(normalized_message["id"]), normalized_message)
    return normalized_message


def create_message(
    *,
    from_actor_address: dict[str, Any] | ActorAddress | None = None,
    to_actor_address: dict[str, Any] | ActorAddress | None = None,
    from_role: str | None = None,
    to_role: str | None = None,
    content: str,
    reply_to: str | None = None,
) -> dict[str, Any]:
    if from_actor_address is None:
        if not isinstance(from_role, str) or not from_role.strip():
            raise ValueError("from_actor_address or from_role must be provided")
        normalized_from = _actor_address_for_role(from_role)
    else:
        normalized_from = _message_actor_payload(from_actor_address, "from_actor_address")
    if to_actor_address is None:
        if not isinstance(to_role, str) or not to_role.strip():
            raise ValueError("to_actor_address or to_role must be provided")
        normalized_to = _actor_address_for_role(to_role)
    else:
        normalized_to = _message_actor_payload(to_actor_address, "to_actor_address")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("content must be a non-empty string")
    if reply_to is not None:
        require_id(reply_to, "reply_to")

    message_id = f"msg-{uuid.uuid4().hex[:12]}"
    require_id(message_id, "message id")
    message = {
        "id": message_id,
        "from_actor_address": normalized_from,
        "to_actor_address": normalized_to,
        "content": content.strip(),
        "reply_to": reply_to,
        "created_at": now_iso(),
        "disposition": "unseen",
        "disposition_reason": None,
        "disposition_updated_at": None,
        "processed_by_actor_address": None,
    }
    return save_message(message)


# ---------------------------------------------------------------------------
# Comment object helpers
# ---------------------------------------------------------------------------


validate_track_comment = track_comment_repo.validate_track_comment
list_track_comments = track_comment_repo.list_track_comments
get_track_comment = track_comment_repo.get_track_comment
save_track_comment = track_comment_repo.save_track_comment
comments_for_track = track_comment_repo.comments_for_track
comments_for_track_thread = track_comment_repo.comments_for_track_thread
resolve_track_comment_thread = track_comment_repo.resolve_track_comment_thread


def create_track_comment(
    *,
    track_id: str,
    by_role: str | None = None,
    by_actor: dict[str, Any] | None = None,
    author_role: str | None = None,
    content: str,
    reply_to: str | None = None,
    mentioned_actors: list[dict[str, Any]] | None = None,
    thread_id: str | None = None,
    status: str = "open",
) -> dict[str, Any]:
    if isinstance(by_actor, dict):
        author_actor = _message_actor_payload(by_actor, "by_actor")
    else:
        author = by_role if isinstance(by_role, str) and by_role.strip() else author_role
        if not isinstance(author, str) or not author.strip():
            raise ValueError("by_actor must be an ActorAddress payload")
        author_actor = _actor_address_for_role(author)
    if isinstance(reply_to, str) and reply_to.strip():
        return track_comment_repo.reply_to_track_comment(
            track_id=track_id,
            reply_to=reply_to.strip(),
            by_actor=author_actor,
            content=content,
            mentioned_actors=mentioned_actors,
        )
    return track_comment_repo.create_track_comment(
        track_id=track_id,
        by_actor=author_actor,
        content=content,
        mentioned_actors=mentioned_actors,
        thread_id=thread_id,
        status=status,
    )
