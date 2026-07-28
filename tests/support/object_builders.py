"""Explicit test-only builders for current BuddySwitch collaboration objects."""

from __future__ import annotations

from typing import Any

from buddyswitch.env.domain import track_artifact_relations
from buddyswitch.env.repos import artifacts, track_comments, tracks


KNOWN_ROLE_IDS = frozenset({"pm", "design", "dev", "market", "test"})


def role_identity_id(role_id: str) -> str:
    if role_id not in KNOWN_ROLE_IDS:
        raise ValueError(f"unknown test role: {role_id}")
    return f"act-{role_id}-fixture"


def identity_id(value: dict[str, Any] | str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        direct = value.get("identity_id") or value.get("actor_id")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        identity = value.get("identity")
        if isinstance(identity, dict) and isinstance(identity.get("id"), str):
            return identity["id"].strip()
        role_id = value.get("role_id")
        if isinstance(role_id, str):
            return role_identity_id(role_id)
    raise ValueError("test identity must be an identity id or current route payload")


def create_track(
    track_id: str,
    title: str,
    *,
    owner_identity: dict[str, Any] | str | None = None,
    owner_actor: dict[str, Any] | None = None,
    outcome: str,
    now: dict[str, Any],
    acceptance_criteria: list[str] | None = None,
    non_goals: list[str] | None = None,
) -> dict[str, Any]:
    owner = owner_identity if owner_identity is not None else owner_actor
    if owner is None:
        raise ValueError("test track owner is required")
    return tracks.create_track(
        track_id,
        title,
        owner_identity=identity_id(owner),
        outcome=outcome,
        now=now,
        acceptance_criteria=acceptance_criteria,
        non_goals=non_goals,
    )


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
    creator = role_identity_id(created_by)
    author_identities = [role_identity_id(role) for role in authors or []]
    return artifacts.create_artifact_revision(
        artifact_id=artifact_id,
        title=title,
        created_by_identity=creator,
        body=body,
        template=template,
        summary=summary,
        source_refs=source_refs,
        supersedes_artifact_id=supersedes_artifact_id,
        author_identities=author_identities,
        legacy_source_run=legacy_source_run,
    )


def publish_track_material(
    *,
    track_id: str,
    artifact_id: str,
    label: str,
    from_role: str,
    summary: str,
) -> tuple[dict[str, Any], dict[str, Any], str | None]:
    result = track_artifact_relations.add_material_relation(
        track_id=track_id,
        artifact_id=artifact_id,
        label=label,
        from_identity=role_identity_id(from_role),
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
    result = track_artifact_relations.add_proof_relation(
        track_id=track_id,
        artifact_id=artifact_id,
        label=label,
        from_identity=role_identity_id(from_role),
        summary=summary,
    )
    return result["track"], result["artifact"], result["superseded_artifact_id"]


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
    author = identity_id(by_actor) if by_actor is not None else role_identity_id(by_role or author_role or "")
    mentions = [identity_id(row) for row in mentioned_actors or []]
    if reply_to:
        return track_comments.reply_to_track_comment(
            track_id=track_id,
            reply_to=reply_to,
            by_identity=author,
            content=content,
            mentioned_identities=mentions,
        )
    return track_comments.create_track_comment(
        track_id=track_id,
        by_identity=author,
        content=content,
        mentioned_identities=mentions,
        thread_id=thread_id,
        status=status,
    )
