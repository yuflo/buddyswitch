#!/usr/bin/env python3
"""Host-owned runtime context passed into tool black-box entrypoints."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any
import sys
import uuid

from env.domain import artifact_relations as _artifact_relations_domain
from env.domain import artifact_visibility as _artifact_visibility_domain
from env.domain import actor_private_workspace as _actor_private_workspace_domain
from env.domain import source_refs as _source_ref_domain
from env.domain import tasks as _task_domain
from env.domain import track_comments as _track_comment_domain
from env.domain import track_artifact_relations as _track_artifact_relations_domain
from env.domain.identity import IdentityRef
import env_profiles
from env_manifest import DEFAULT_MANIFEST
from env.repos import artifacts as _artifact_repo
from env.repos import actor_private_files as _actor_private_repo
from env.repos import messages as _message_repo
from env.repos import runtime_files
from env.repos import tasks as _task_repo
from env.repos import track_comments as _track_comment_repo
from env.repos import tracks as _track_repo
from env.tool_runtime.actor_profile import Actor
from env.tool_runtime.actor_profile import ActorAddress
from env.tool_runtime.actor_profile import ActorProfile
from env.tool_runtime.actor_profile import AuthSubject
from env.tool_runtime.actor_profile import Role
from env.tool_runtime.actor_profile import actor_identity_to_address
from env.tool_runtime import daemon_client
from env.tool_runtime import role_auth as _role_auth


def _load_registry_module():
    from env.tool_runtime import registry as tool_registry

    return tool_registry


class RuntimeObjectAccess:
    """Concrete runtime-object helpers for tool implementations."""

    def list_tracks(self) -> list[dict[str, Any]]:
        return _track_repo.list_tracks()

    def create_track(self, track_id: str, title: str, outcome: str, owner_actor: dict[str, Any], now: dict[str, Any]) -> dict[str, Any]:
        return _track_repo.create_track(
            track_id,
            title,
            outcome=outcome,
            owner_actor=owner_actor,
            now=now,
        )

    def get_track(self, track_id: str) -> dict[str, Any] | None:
        return _track_repo.get_track(track_id)

    def update_track_status(self, track_id: str, now: dict[str, Any], state: str) -> dict[str, Any]:
        return _track_repo.update_track(track_id, {"now": now, "state": state})

    def add_track_material(self, track_id: str, artifact_id: str, label: str, summary: str) -> tuple[dict[str, Any], dict[str, Any]]:
        result = _track_artifact_relations_domain.add_material_relation(
            track_id=track_id,
            artifact_id=artifact_id,
            label=label,
            from_actor={"actor_id": "act-pm-system", "role_id": "pm"},
            summary=summary,
        )
        return result["track"], result["artifact"]

    def add_track_update(self, track_id: str, summary: str, kind: str, refs: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
        return _track_repo.append_track_update(
            track_id=track_id,
            by_actor={"actor_id": "act-pm-system", "role_id": "pm"},
            kind=kind,
            summary=summary,
            refs=refs,
        )

    def add_track_proof(self, track_id: str, artifact_id: str, label: str, summary: str) -> tuple[dict[str, Any], dict[str, Any]]:
        result = _track_artifact_relations_domain.add_proof_relation(
            track_id=track_id,
            artifact_id=artifact_id,
            label=label,
            from_actor={"actor_id": "act-pm-system", "role_id": "pm"},
            summary=summary,
        )
        return result["track"], result["artifact"]

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
            created_by_actor={"actor_id": "act-pm-system", "role_id": "pm"},
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

    def add_track_comment(
        self,
        track_id: str,
        content: str,
        reply_to: str | None,
        mentioned_actors: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        return _track_comment_repo.create_track_comment(
            track_id=track_id,
            by_actor={"actor_id": "act-pm-system", "role_id": "pm"},
            content=content,
            reply_to=reply_to,
            mentioned_actors=mentioned_actors,
        )

    def list_track_comments(self, track_id: str, status: str | None) -> list[dict[str, Any]]:
        rows = _track_comment_repo.comments_for_track(track_id)
        if isinstance(status, str) and status.strip():
            rows = [row for row in rows if row.get("status") == status]
        return rows

    def runtime_sources(self) -> dict[str, Any]:
        return {
            "tracks": "track.list / track.open",
            "tasks": "task.current / task.capture / task.select / task.switch_request / task.switch_confirm / task.progress / task.checkout / task.review",
            "artifacts": "artifact.list / artifact.get",
            "messages": "message.list",
            "track_comments": "track.list_comments",
            "writable_surfaces": "context.get / context.summarize",
        }


class ActorPrivateAccess:
    """Active actor actor_private operations."""

    def __init__(self, *, active_actor: dict[str, Any], active_role: str, manifest: dict[str, Any], instance_payload: dict[str, Any]) -> None:
        self._active_actor = dict(active_actor)
        self._active_role = active_role
        self._manifest = manifest
        self._instance_payload = instance_payload

    def _role_ids(self) -> set[str]:
        ids = set(_role_auth.manifest_role_ids(self._manifest))
        ids.add(self._active_role)
        return ids

    def _root(self) -> Path:
        return _actor_private_repo.ensure_active_actor_private_root(
            active_role=self._active_role,
            instance_payload=self._instance_payload,
        )

    def describe(self) -> dict[str, Any]:
        return _actor_private_workspace_domain.build_actor_private_desc(
            self._active_role,
            active_actor=self._active_actor,
            instance_payload=self._instance_payload,
        )

    def list_files(self, logical_name: str | None = None, recursive: bool = False, limit: int | None = None) -> list[dict[str, Any]]:
        prefix = _actor_private_repo.normalize_logical_prefix(
            logical_name,
            active_role=self._active_role,
            role_ids=self._role_ids(),
        )
        max_rows = int(limit) if isinstance(limit, int) and limit > 0 else 100
        return _actor_private_repo.list_private_file_summaries(
            root=self._root(),
            owner_actor=self._active_actor,
            recursive=bool(recursive),
            limit=max_rows,
            logical_prefix=prefix,
        )

    def read_file(self, logical_name: str, encoding: str | None = None) -> dict[str, Any]:
        normalized = _actor_private_repo.normalize_logical_name(
            logical_name,
            active_role=self._active_role,
            role_ids=self._role_ids(),
        )
        raw, content_type = _actor_private_repo.read_private_file(root=self._root(), logical_name=normalized)
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
        normalized = _actor_private_repo.normalize_logical_name(
            logical_name,
            active_role=self._active_role,
            role_ids=self._role_ids(),
        )
        payload_bytes: bytes
        if isinstance(content, str) and content_base64 is None:
            payload_bytes = content.encode("utf-8")
        elif isinstance(content_base64, str) and content is None:
            import base64

            payload_bytes = base64.b64decode(content_base64.encode("ascii"))
        else:
            raise ValueError("write_file requires exactly one of content or content_base64")
        existed, guessed_content_type = _actor_private_repo.write_private_file(
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
        normalized = _actor_private_repo.normalize_logical_name(
            logical_name,
            active_role=self._active_role,
            role_ids=self._role_ids(),
        )
        return _actor_private_repo.delete_private_file(root=self._root(), logical_name=normalized)


class BrowserAccess:
    """Browser/evidence helper placeholders owned by host runtime."""

    def __init__(self, *, active_role: str, instance_payload: dict[str, Any], manifest_path: Path | None) -> None:
        self._active_role = active_role
        self._instance_payload = instance_payload
        self._manifest_path = manifest_path or DEFAULT_MANIFEST

    def status(self) -> dict[str, Any]:
        port = self._instance_payload.get("browser_port")
        return {"active_role": self._active_role, "browser_port": port}

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


def _actor_address_payload(value: ActorAddress | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, ActorAddress):
        return value.to_payload()
    return ActorAddress.from_payload(value).to_payload()


def _launcher_dir_for_runtime() -> Path:
    repo_root = os.environ.get("BUDDYSWITCH_REPO_ROOT")
    if isinstance(repo_root, str) and repo_root.strip():
        return Path(repo_root.strip()).expanduser().resolve(strict=False) / "tools" / "launcher"
    return Path(__file__).resolve().parents[3] / "tools" / "launcher"


class DaemonAccess:
    """Explicit central daemon access for runtime tools."""

    def __init__(self, *, current_identity: IdentityRef, role_id: str, instance_json: Path) -> None:
        self.current_identity = current_identity
        self._actor_address = actor_identity_to_address(current_identity, role_id=role_id)
        self._instance_json = instance_json

    def list_contacts(self, *, role_id: str | None = None) -> dict[str, Any]:
        return daemon_client.list_contacts(role_id=role_id)

    def check_reachability(self, *, target_actor_address: ActorAddress | dict[str, Any]) -> dict[str, Any]:
        return daemon_client.check_reachability(
            target_actor_address=_actor_address_payload(target_actor_address),
        )

    def deliver_signal(
        self,
        *,
        signal_type: str,
        target_actor_address: ActorAddress | dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        signal = {
            "signal_id": f"sig-{uuid.uuid4().hex}",
            "type": signal_type,
            "source_actor_address": self._actor_address.to_payload(),
            "target_actor_address": _actor_address_payload(target_actor_address),
            "payload": dict(payload),
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        return daemon_client.deliver_signal(signal=signal)

    def deliver_track_comment_added(
        self,
        *,
        track_id: str,
        comment_id: str,
        thread_id: str,
        target_actor_address: ActorAddress | dict[str, Any],
    ) -> dict[str, Any]:
        return self.deliver_signal(
            signal_type="track.comment.added",
            target_actor_address=target_actor_address,
            payload={"track_id": track_id, "comment_id": comment_id, "thread_id": thread_id},
        )

    def request_parent_message_handling(self, *, message_id: str, prompt: str) -> dict[str, Any]:
        launcher_dir = _launcher_dir_for_runtime()
        if str(launcher_dir) not in sys.path:
            sys.path.insert(0, str(launcher_dir))
        import daemon_core  # type: ignore[import-not-found]

        daemon_context = daemon_core.load_daemon_context(self._instance_json)
        daemon_state = daemon_core.DaemonState.load(
            instance_root=daemon_context.instance_root,
            actor_id=daemon_context.actor_id,
            main_thread_id=daemon_context.main_thread_id,
        )
        runtime = daemon_core.DaemonRuntime(context=daemon_context, state=daemon_state)
        return runtime.submit_parent_prompt(
            prompt,
            handler_name="message_mark",
            origin_id=message_id,
            interrupt_policy="ensure_stopped",
        )

    def wake_im_actor(self, payload: dict[str, Any]) -> dict[str, Any]:
        return daemon_client.wake_im_actor(payload)


@dataclass(frozen=True)
class DomainAccess:
    """Host-owned domain validator/normalizer access."""

    artifact_relations: Any = field(default_factory=lambda: _artifact_relations_domain)
    artifact_visibility: Any = field(default_factory=lambda: _artifact_visibility_domain)
    actor_private_workspace: Any = field(default_factory=lambda: _actor_private_workspace_domain)
    source_refs: Any = field(default_factory=lambda: _source_ref_domain)
    task: Any = field(default_factory=lambda: _task_domain)
    track_comment: Any = field(default_factory=lambda: _track_comment_domain)
    track_artifact_relations: Any = field(default_factory=lambda: _track_artifact_relations_domain)


@dataclass(frozen=True)
class RepoAccess:
    """Host-owned repository and runtime-file access."""

    artifact: Any = field(default_factory=lambda: _artifact_repo)
    actor_private: Any = field(default_factory=lambda: _actor_private_repo)
    message: Any = field(default_factory=lambda: _message_repo)
    runtime_files: Any = field(default_factory=lambda: runtime_files)
    task: Any = field(default_factory=lambda: _task_repo)
    track_comment: Any = field(default_factory=lambda: _track_comment_repo)
    track: Any = field(default_factory=lambda: _track_repo)


@dataclass(frozen=True)
class ToolContext(Mapping[str, Any]):
    """Host-owned runtime context object passed to each tool invoke."""

    current_identity: IdentityRef
    active_actor: Actor
    active_role: Role
    actor_id: str
    role_id: str
    actor_address: ActorAddress
    auth_subject: AuthSubject
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
            "actor_private",
            ActorPrivateAccess(
                active_actor=self.active_actor.to_payload(),
                active_role=self.role_id,
                manifest=self.manifest,
                instance_payload=self.instance_payload,
            ),
        )
        object.__setattr__(
            self,
            "browser",
            BrowserAccess(
                active_role=self.role_id,
                instance_payload=self.instance_payload,
                manifest_path=self.manifest_path,
            ),
        )
        object.__setattr__(
            self,
            "daemon",
            DaemonAccess(
                current_identity=self.current_identity,
                role_id=self.role_id,
                instance_json=self.instance_json,
            ),
        )

    @classmethod
    def from_actor_profile(
        cls,
        *,
        actor_profile: ActorProfile,
        instance_json: Path,
        instance_payload: dict[str, Any],
        manifest: dict[str, Any],
        manifest_path: Path | None = None,
    ) -> "ToolContext":
        return cls(
            current_identity=actor_profile.current_identity,
            active_actor=actor_profile.active_actor,
            active_role=actor_profile.active_role,
            actor_id=actor_profile.actor_id,
            role_id=actor_profile.role_id,
            actor_address=actor_profile.actor_address,
            auth_subject=actor_profile.auth_subject,
            instance_json=instance_json,
            instance_payload=instance_payload,
            manifest=manifest,
            manifest_path=manifest_path,
        )

    def runtime_policy_preview(self, operation_semantics: dict[str, dict[str, Any]]) -> dict[str, Any]:
        from env.tool_runtime import role_auth

        return role_auth.role_action_summary(self.auth_subject, self.manifest, operation_semantics)

    def now(self) -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def new_id(self, prefix: str) -> str:
        head = prefix.strip() if isinstance(prefix, str) and prefix.strip() else "id"
        return f"{head}-{uuid.uuid4().hex[:10]}"

    def __getitem__(self, key: str) -> Any:
        if key == "current_identity":
            return self.current_identity.to_payload()
        if key == "active_actor":
            return self.active_actor.to_payload()
        if key == "active_role":
            return self.active_role.role_id
        if key == "actor_id":
            return self.actor_id
        if key == "role_id":
            return self.role_id
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
        yield "current_identity"
        yield "active_actor"
        yield "active_role"
        yield "actor_id"
        yield "role_id"
        yield "instance_json"
        yield "instance_payload"
        yield "manifest"
        yield "manifest_path"

    def __len__(self) -> int:
        return 9

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


default_manifest_path = DEFAULT_MANIFEST
