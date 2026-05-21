#!/usr/bin/env python3
"""Host-owned runtime context passed into tool black-box entrypoints."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
import uuid

from env.domain import artifact_relations as _artifact_relations_domain
from env.domain import artifact_visibility as _artifact_visibility_domain
from env.domain import buddybox_workspace as _buddybox_workspace_domain
from env.domain import comment_targets as _comment_target_domain
from env.domain import messages as _message_domain
from env.domain import publication as _publication_domain
from env.domain import requests as _request_domain
from env.domain import source_refs as _source_ref_domain
from env.domain import tasks as _task_domain
import env_profiles
from env_manifest import DEFAULT_MANIFEST
from env.repos import artifacts as _artifact_repo
from env.repos import buddybox_files as _buddybox_repo
from env.repos import comments as _comment_repo
from env.repos import messages as _message_repo
from env.repos import requests as _request_repo
from env.repos import runtime_files
from env.repos import tasks as _task_repo
from env.repos import tracks as _track_repo


def _load_registry_module():
    from env.tool_runtime import registry as tool_registry

    return tool_registry


class RuntimeObjectAccess:
    """Concrete runtime-object helpers for tool implementations."""

    def list_tasks(self) -> list[dict[str, Any]]:
        return _task_repo.list_tasks()

    def create_task(self, task_id: str, title: str, summary: str, status: str, track_id: str | None) -> dict[str, Any]:
        return _task_repo.create_task(
            task_id=task_id,
            title=title,
            buddy="",
            track_id=track_id,
            status=status,
            summary=summary,
        )

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        return _task_repo.get_task(task_id)

    def update_task(self, task_id: str, title: str | None, summary: str | None, status: str | None, track_id: str | None) -> dict[str, Any]:
        patch: dict[str, Any] = {}
        if title is not None:
            patch["title"] = title
        if summary is not None:
            patch["summary"] = summary
        if status is not None:
            patch["status"] = status
        if track_id is not None:
            patch["track_id"] = track_id
        return _task_repo.update_task(task_id, patch)

    def archive_task(self, task_id: str) -> dict[str, Any]:
        return _task_repo.update_task(task_id, {"status": "archived"})

    def list_tracks(self) -> list[dict[str, Any]]:
        return _track_repo.list_tracks()

    def create_track(self, track_id: str, title: str, outcome: str, appetite: str, now: dict[str, Any], state: str, health: str) -> dict[str, Any]:
        return _track_repo.create_track(
            track_id,
            title,
            outcome=outcome,
            appetite=appetite,
            now=now,
            state=state,
            health=health,
        )

    def get_track(self, track_id: str) -> dict[str, Any] | None:
        return _track_repo.get_track(track_id)

    def update_track_now(self, track_id: str, now: dict[str, Any], state: str | None, health: str | None) -> dict[str, Any]:
        patch: dict[str, Any] = {"now": now}
        if state is not None:
            patch["state"] = state
        if health is not None:
            patch["health"] = health
        return _track_repo.update_track(track_id, patch)

    def add_track_material(self, track_id: str, artifact_id: str, label: str, summary: str) -> tuple[dict[str, Any], dict[str, Any]]:
        return _track_repo.publish_track_material(
            track_id=track_id,
            artifact_id=artifact_id,
            label=label,
            from_buddy="",
            summary=summary,
        )

    def add_track_update(self, track_id: str, summary: str, kind: str, refs: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
        return _track_repo.append_track_update(
            track_id=track_id,
            by_buddy="",
            kind=kind,
            summary=summary,
            refs=refs,
        )

    def add_track_proof(self, track_id: str, artifact_id: str, label: str, summary: str) -> tuple[dict[str, Any], dict[str, Any]]:
        return _track_repo.publish_track_proof(
            track_id=track_id,
            artifact_id=artifact_id,
            label=label,
            from_buddy="",
            summary=summary,
        )

    def archive_track(self, track_id: str) -> dict[str, Any]:
        return _track_repo.update_track(track_id, {"archived_at": runtime_files.now_iso()})

    def get_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        return _artifact_repo.get_artifact(artifact_id)

    def create_artifact_revision(
        self,
        artifact_id: str | None,
        title: str,
        summary: str,
        template: str,
        body: str,
        source_refs: list[dict[str, Any]] | None,
        read_claim: str | None,
        track_id: str | None,
        publish_as: str | None,
        label: str | None,
    ) -> dict[str, Any]:
        del read_claim, track_id, publish_as, label
        return _artifact_repo.create_artifact_revision(
            artifact_id=artifact_id,
            title=title,
            created_by="",
            body=body,
            template=template,
            summary=summary,
            source_refs=source_refs,
        )

    def update_artifact_metadata(
        self,
        artifact_id: str,
        title: str | None,
        summary: str | None,
        template: str | None,
        body: str | None,
        source_refs: list[dict[str, Any]] | None,
        read_claim: str | None,
    ) -> dict[str, Any]:
        del read_claim
        patch: dict[str, Any] = {}
        if title is not None:
            patch["title"] = title
        if summary is not None:
            patch["summary"] = summary
        if template is not None:
            patch["template"] = template
        if body is not None:
            patch["body"] = body
        if source_refs is not None:
            patch["source_refs"] = source_refs
        return _artifact_repo.update_artifact(artifact_id, patch)

    def add_comment(
        self,
        target_type: str,
        target_id: str,
        content: str,
        reply_to: str | None,
        artifact_revision_id: str | None,
        anchor: str | None,
        mentions: list[str] | None,
    ) -> dict[str, Any]:
        return _comment_repo.create_comment(
            target_type=target_type,
            target_id=target_id,
            by_buddy="",
            content=content,
            reply_to=reply_to,
            artifact_revision_id=artifact_revision_id,
            anchor=anchor,
            mentions=mentions,
        )

    def list_comments(self, target_type: str, target_id: str, status: str | None) -> list[dict[str, Any]]:
        rows = _comment_repo.comments_for_target(target_type, target_id)
        if isinstance(status, str) and status.strip():
            rows = [row for row in rows if row.get("status") == status]
        return rows

    def send_message(self, to_buddy: str, content: str, reply_to: str | None) -> dict[str, Any]:
        return _message_repo.create_message(from_buddy="", to_buddy=to_buddy, content=content, reply_to=reply_to)

    def list_messages(self, buddy: str | None) -> list[dict[str, Any]]:
        rows = _message_repo.list_messages()
        if isinstance(buddy, str) and buddy.strip():
            rows = [row for row in rows if row.get("from_buddy") == buddy]
        return rows

    def runtime_sources(self) -> dict[str, Any]:
        return {
            "tracks": "track.list / track.open",
            "tasks": "task.list / task.get",
            "artifacts": "artifact.list / artifact.get",
            "messages": "message.list",
            "comments": "comment.list",
            "requests": "request.list / request.get",
            "buddybox": "buddybox list/read/write/delete",
        }


class BuddyboxAccess:
    """Active-buddy private buddybox operations."""

    def __init__(self, *, active_buddy: str, manifest: dict[str, Any], instance_payload: dict[str, Any]) -> None:
        self._active_buddy = active_buddy
        self._manifest = manifest
        self._instance_payload = instance_payload

    def _buddy_ids(self) -> set[str]:
        ids = _message_domain.manifest_buddy_ids(self._manifest)
        ids.add(self._active_buddy)
        return ids

    def _root(self) -> Path:
        return _buddybox_repo.ensure_active_buddy_root(
            active_buddy=self._active_buddy,
            instance_payload=self._instance_payload,
        )

    def describe(self) -> dict[str, Any]:
        return _buddybox_workspace_domain.build_buddybox_desc(
            self._active_buddy,
            instance_payload=self._instance_payload,
        )

    def list_files(self, logical_name: str | None = None, recursive: bool = False, limit: int | None = None) -> list[dict[str, Any]]:
        prefix = _buddybox_repo.normalize_logical_prefix(
            logical_name,
            active_buddy=self._active_buddy,
            buddy_ids=self._buddy_ids(),
        )
        max_rows = int(limit) if isinstance(limit, int) and limit > 0 else 100
        return _buddybox_repo.list_private_file_summaries(
            root=self._root(),
            active_buddy=self._active_buddy,
            recursive=bool(recursive),
            limit=max_rows,
            logical_prefix=prefix,
        )

    def read_file(self, logical_name: str, encoding: str | None = None) -> dict[str, Any]:
        normalized = _buddybox_repo.normalize_logical_name(
            logical_name,
            active_buddy=self._active_buddy,
            buddy_ids=self._buddy_ids(),
        )
        raw, content_type = _buddybox_repo.read_private_file(root=self._root(), logical_name=normalized)
        if isinstance(encoding, str) and encoding.strip().lower() == "base64":
            import base64

            return {
                "logical_name": normalized,
                "content_base64": base64.b64encode(raw).decode("ascii"),
                "content_type": content_type,
            }
        return {
            "logical_name": normalized,
            "content": raw.decode("utf-8"),
            "content_type": content_type,
        }

    def write_file(
        self,
        logical_name: str,
        content: str | None = None,
        content_base64: str | None = None,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        del content_type
        normalized = _buddybox_repo.normalize_logical_name(
            logical_name,
            active_buddy=self._active_buddy,
            buddy_ids=self._buddy_ids(),
        )
        payload_bytes: bytes
        if isinstance(content, str) and content_base64 is None:
            payload_bytes = content.encode("utf-8")
        elif isinstance(content_base64, str) and content is None:
            import base64

            payload_bytes = base64.b64decode(content_base64.encode("ascii"))
        else:
            raise ValueError("write_file requires exactly one of content or content_base64")
        existed, guessed_content_type = _buddybox_repo.write_private_file(
            root=self._root(),
            logical_name=normalized,
            content=payload_bytes,
        )
        return {
            "logical_name": normalized,
            "existed": existed,
            "content_type": guessed_content_type,
            "size_bytes": len(payload_bytes),
        }

    def delete_file(self, logical_name: str) -> bool:
        normalized = _buddybox_repo.normalize_logical_name(
            logical_name,
            active_buddy=self._active_buddy,
            buddy_ids=self._buddy_ids(),
        )
        return _buddybox_repo.delete_private_file(root=self._root(), logical_name=normalized)


class BrowserAccess:
    """Browser/evidence helper placeholders owned by host runtime."""

    def __init__(self, *, active_buddy: str, instance_payload: dict[str, Any], manifest_path: Path | None) -> None:
        self._active_buddy = active_buddy
        self._instance_payload = instance_payload
        self._manifest_path = manifest_path or DEFAULT_MANIFEST

    def status(self) -> dict[str, Any]:
        port = self._instance_payload.get("browser_port")
        return {"active_buddy": self._active_buddy, "browser_port": port}

    def request(self, query: str, backend: str | None = None, engine: str | None = None) -> dict[str, Any]:
        del backend, engine
        return {"query": query, "requested": True}

    def open_browser(self, query: str, engine: str | None = None) -> dict[str, Any]:
        del engine
        return {"query": query, "opened": True}

    def issue_evidence_token(self, target_type: str, target_id: str, mode: str | None = None) -> dict[str, Any]:
        return {
            "target_type": target_type,
            "target_id": target_id,
            "mode": mode or "strict",
            "token_id": f"evidence-{uuid.uuid4().hex[:12]}",
        }

    def approve_downgrade(self, target_type: str, target_id: str, reason: str) -> dict[str, Any]:
        return {
            "target_type": target_type,
            "target_id": target_id,
            "reason": reason,
            "approved": True,
        }


class RegistryCatalogAccess:
    """Read-only registry projections for context tool surfaces."""

    def tool_catalog(self) -> dict[str, dict[str, Any]]:
        return _load_registry_module().env_tools_description()

    def operation_semantics(self) -> dict[str, dict[str, Any]]:
        return _load_registry_module().operation_semantics()

    def compact_tool_affordances(self) -> dict[str, dict[str, Any]]:
        return _load_registry_module().compact_tool_affordances()

    def tool_catalog_errors(self) -> list[dict[str, str]]:
        return _load_registry_module().tool_catalog_errors()


@dataclass(frozen=True)
class DomainAccess:
    """Host-owned domain validator/normalizer access."""

    artifact_relations: Any = field(default_factory=lambda: _artifact_relations_domain)
    artifact_visibility: Any = field(default_factory=lambda: _artifact_visibility_domain)
    buddybox_workspace: Any = field(default_factory=lambda: _buddybox_workspace_domain)
    comment_target: Any = field(default_factory=lambda: _comment_target_domain)
    message: Any = field(default_factory=lambda: _message_domain)
    publication: Any = field(default_factory=lambda: _publication_domain)
    request: Any = field(default_factory=lambda: _request_domain)
    source_refs: Any = field(default_factory=lambda: _source_ref_domain)
    task: Any = field(default_factory=lambda: _task_domain)


@dataclass(frozen=True)
class RepoAccess:
    """Host-owned repository and runtime-file access."""

    artifact: Any = field(default_factory=lambda: _artifact_repo)
    buddybox: Any = field(default_factory=lambda: _buddybox_repo)
    comment: Any = field(default_factory=lambda: _comment_repo)
    message: Any = field(default_factory=lambda: _message_repo)
    request: Any = field(default_factory=lambda: _request_repo)
    runtime_files: Any = field(default_factory=lambda: runtime_files)
    task: Any = field(default_factory=lambda: _task_repo)
    track: Any = field(default_factory=lambda: _track_repo)


@dataclass(frozen=True)
class ToolContext(Mapping[str, Any]):
    """Host-owned runtime context object passed to each tool invoke."""

    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]
    manifest_path: Path | None = None
    objects: RuntimeObjectAccess = field(default_factory=RuntimeObjectAccess)
    catalog: RegistryCatalogAccess = field(default_factory=RegistryCatalogAccess)
    rules: DomainAccess = field(default_factory=DomainAccess)
    repos: RepoAccess = field(default_factory=RepoAccess)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "buddybox",
            BuddyboxAccess(
                active_buddy=self.active_buddy,
                manifest=self.manifest,
                instance_payload=self.instance_payload,
            ),
        )
        object.__setattr__(
            self,
            "browser",
            BrowserAccess(
                active_buddy=self.active_buddy,
                instance_payload=self.instance_payload,
                manifest_path=self.manifest_path,
            ),
        )

    def now(self) -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def new_id(self, prefix: str) -> str:
        head = prefix.strip() if isinstance(prefix, str) and prefix.strip() else "id"
        return f"{head}-{uuid.uuid4().hex[:10]}"

    def __getitem__(self, key: str) -> Any:
        if key == "active_buddy":
            return self.active_buddy
        if key == "instance_id":
            return self.instance_id
        if key == "instance_json":
            return self.instance_json
        if key == "instance_payload":
            return self.instance_payload
        if key == "manifest":
            return self.manifest
        if key == "manifest_path":
            return self.manifest_path
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        yield "active_buddy"
        yield "instance_id"
        yield "instance_json"
        yield "instance_payload"
        yield "manifest"
        yield "manifest_path"

    def __len__(self) -> int:
        return 6

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


default_manifest_path = DEFAULT_MANIFEST
