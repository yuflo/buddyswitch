#!/usr/bin/env python3
"""Artifact repository adapters for runtime artifact persistence access."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import env_legacy_store as env_store

VALID_ARTIFACT_STATUS = tuple(env_store.VALID_ARTIFACT_STATUS)
VALID_ARTIFACT_TEMPLATES = tuple(env_store.VALID_ARTIFACT_TEMPLATES)


def now_iso() -> str:
    return env_store.now_iso()


def artifact_file(artifact_id: str) -> Path:
    return env_store.artifact_file(artifact_id)


def list_artifacts() -> list[dict[str, Any]]:
    return env_store.list_artifacts()


def get_artifact(artifact_id: str) -> dict[str, Any] | None:
    return env_store.get_artifact(artifact_id)


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
    return env_store.create_artifact_revision(
        artifact_id=artifact_id,
        title=title,
        created_by=created_by,
        body=body,
        template=template,
        summary=summary,
        source_refs=source_refs,
        supersedes_artifact_id=supersedes_artifact_id,
        authors=authors,
        legacy_source_run=legacy_source_run,
    )


def update_artifact(artifact_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    return env_store.update_artifact(artifact_id, patch)


def validate_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    return env_store.validate_artifact(artifact)


def save_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    return env_store.save_artifact(artifact)
